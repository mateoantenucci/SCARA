"""Sesión de la URC con la UCI por scara/1 (docs/PROTOCOLO_SCARA_1.md).

La URC escucha (D1) y la UCI se conecta: el controlador de Webots, socat o un
Arduino con Ethernet. Un hilo posee los sockets; la interfaz HTTP solo consulta
el estado y deja órdenes en una cola.

Los segmentos de un tramo salen de a uno: la URC envía el próximo SEG cuando
llega el OK del anterior (D6). Con la cola del firmware llena, el OK se demora
y la URC espera.
"""

from collections import deque
import queue
import select
import socket
import threading
import time

from scara.collisions import CollisionChecker
from scara.kinematics import load_config
from urc import planner
from urc.protocol import LINE_MAX, PROTOCOL, check_order, parse_message, segment_line


PING_PERIOD = 0.25           # s (D27)
JOG_SPEED = 500              # centésimas por segundo: jog articular lento
JOG_HOLD = 0.5               # s sin renovar el jog desde la página => JOG STOP
ALL_HOMED = 0x0F
REST = (0, 0, 0, 12000)      # pose de reposo (D30), en centésimas
PARK_SPEED = 0.5             # «Estacionar» y la vuelta al reposo del homing (D56)
HOME_ORDER = (4, 1, 2, 3)    # D11
HOME_START = 1.0             # s para que S muestre HOMING después de enviar HOME


class Session:
    def __init__(self, host="127.0.0.1", port=9000, jog_speed=JOG_SPEED, jog_hold=JOG_HOLD):
        self.jog_speed, self.jog_hold = jog_speed, jog_hold
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.lock = threading.Lock()
        self.outgoing = queue.Queue(maxsize=32)
        self.traffic = deque(maxlen=40)
        self.errors = deque(maxlen=10)       # ERR que informó la UCI
        self.rejected = deque(maxlen=10)     # líneas de la UCI que no respetan scara/1
        self.connected = False
        self.peer = None
        self.firmware = None
        self.boots = 0
        self.received = 0                    # líneas recibidas de la UCI, válidas o no
        self.greeted = False                 # la UCI ya habló en esta conexión
        self.status = None
        self.status_time = None
        self.jogging = None          # (eje, sentido, por motor) enviado a la UCI
        self.jog_deadline = 0.0
        self.segments = deque()      # SEG por enviar, en orden
        self.in_flight = None        # número del SEG enviado que espera su OK
        self.next_segment = 1        # los números no se repiten en la sesión
        self.last_ok = None
        self.tramo = None            # el último tramo planificado, para la página
        self.homing = None           # el último homing: ejes encontrados y estado
        self.park_requested = False  # homing terminado: falta volver al reposo
        # EV LOST desde la última referencia (F1, D65): la referencia de esos
        # ejes es dudosa hasta su homing.
        self.doubtful = []
        # El modelo para planificar se lee una vez.
        self.config = load_config()
        self.checker = CollisionChecker(self.config)
        self.limits = planner.default_limits(self.config)
        self.message = f"Esperando a la UCI en el puerto {self.port}"
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="scara-uci", daemon=True)
        self.thread.start()

    # --- Órdenes desde la interfaz ---------------------------------------

    def order(self, line):
        """Envía una orden de scara/1 tal cual, si su forma es válida.

        Un JOG enviado así no vence como el de jog(): solo lo frenan JOG STOP,
        STOP o HALT. Por eso la página no lo expone. Un SEG espera su turno
        detrás de los demás segmentos, con el control de flujo.
        """
        line = check_order(line)
        with self.lock:
            self._require_robot()
            if line.split()[0] == "SEG":
                self.segments.append(line)
            else:
                self._queue(line)

    def move_ptp(self, target, speed=0.25, dry_run=False):
        """Tramo PTP desde la posición estimada hasta target (J1–J4 en centésimas).

        Valida límites y choques en todo el camino. Con dry_run solo planifica:
        la página muestra la duración y pide confirmación.
        """
        with self.lock:
            self._require_robot()
            status = self.status
            if status is None or status["homed"] != ALL_HOMED:
                raise ValueError("El robot tiene que estar referenciado para un tramo PTP")
            if status["mode"] != "IDLE" or self.jogging is not None or self._segments_pending():
                raise ValueError("El robot se está moviendo: esperá a que frene")
            start = tuple(status["position"])
        planner.check_target(start, target, self.config, self.checker)
        plan = planner.plan_ptp(start, target, speed, self.limits)
        summary = {"start": list(start), "target": list(target), "speed": speed, "segments": len(plan.segments),
                   "duration_s": len(plan.segments) * planner.SEGMENT_MS / 1000}
        if dry_run or not plan.segments:
            return summary
        with self.lock:
            self._require_robot()
            if self.status is None or tuple(self.status["position"]) != start or self._segments_pending():
                raise ValueError("El robot cambió de estado mientras se planificaba; volvé a intentar")
            self.tramo = dict(summary, kind="PTP", first=self.next_segment, last=self.next_segment - 1,
                              cancelled=None)
            self._enqueue(plan.segments)
            self.message = f"Tramo PTP en curso: {len(plan.segments)} segmentos, {summary['duration_s']:.2f} s"
        return summary

    def run_segments(self, segments, start=None, follows=None, **summary):
        """Encola segmentos (ms, J1–J4 en centésimas) ya validados por quien los planificó.

        Con start, empiezan un movimiento nuevo: el robot tiene que estar
        referenciado, quieto y en start. Con follows (el primer número del
        movimiento), lo continúan sin pausa, si no se canceló: así la
        reproducción encola un tramo detrás de otro. Devuelve los números
        del primero y del último segmento encolados.
        """
        if not segments:
            raise ValueError("No hay segmentos para enviar")
        with self.lock:
            self._require_robot()
            if follows is None:
                if self.status is None or self.status["homed"] != ALL_HOMED:
                    raise ValueError("El robot tiene que estar referenciado")
                self._require_still("mover el robot")
                if tuple(self.status["position"]) != tuple(start):
                    raise ValueError("El robot cambió de estado mientras se planificaba; volvé a intentar")
                self.tramo = dict(summary, segments=0, duration_s=0.0, first=self.next_segment,
                                  last=self.next_segment - 1, cancelled=None)
            elif self.tramo is None or self.tramo["first"] != follows or self.tramo["cancelled"] is not None:
                raise ValueError("El movimiento ya no está en curso")
            first = self.next_segment
            self._enqueue(segments)
            self.tramo["duration_s"] = round(self.tramo["duration_s"] + sum(ms for ms, _ in segments) / 1000, 3)
            return first, self.next_segment - 1

    def home(self):
        """Homing de los cuatro ejes (D11); al terminar, la URC estaciona el robot.

        La página pide antes confirmar que el robot está en la pose de reposo
        (D30): sin referencia, nadie verifica choques.
        """
        with self.lock:
            self._require_robot()
            if self.homing is not None and self.homing["state"] == "en curso":
                raise ValueError("El homing ya está en curso")
            self._require_still("el homing")
            self.homing = {"axes": [], "state": "en curso", "park": True, "seen": False,
                           "sent": time.monotonic()}
            self.message = "Homing en curso: J4, J1, J2 y J3"
            self._queue("HOME")

    def park(self):
        """Estacionar: PTP a la pose de reposo (D30), con el robot referenciado."""
        return self.move_ptp(REST, PARK_SPEED)

    def jog(self, joint, direction, motor=False):
        """Mantiene el jog mientras la página lo renueve antes de jog_hold.

        Con motor=True mueve solo el motor M<joint>, sin compensar el acople
        M1/M2: es el modo de prueba que muestra la cadena híbrida (D46).
        """
        if type(joint) is not int or joint not in range(1, 5):
            raise ValueError("La articulación debe ser 1, 2, 3 o 4")
        if direction not in ("+", "-"):
            raise ValueError("El sentido debe ser + o -")
        if type(motor) is not bool:
            raise ValueError("motor debe ser true o false")
        with self.lock:
            self._require_robot()
            if self._tramo_running():
                raise ValueError("Hay un tramo en curso: frenalo con Stop antes del jog")
            if self.status is not None and self.status["mode"] == "HOMING":
                raise ValueError("El homing está en curso: frenalo con Stop antes del jog")
            self.jog_deadline = time.monotonic() + self.jog_hold
            if self.jogging != (joint, direction, motor):
                self.jogging = (joint, direction, motor)
                self._queue(f"JOG {'M' if motor else ''}{joint} {direction} {self.jog_speed}")

    def jog_stop(self):
        self._stop("JOG STOP")

    def stop(self):
        """Frena todo y conserva la referencia."""
        self._stop("STOP")

    def halt(self):
        """Parada inmediata: si había movimiento, la referencia se pierde (D41)."""
        self._stop("HALT")

    def disable(self):
        """Corta la corriente de los drivers: la referencia se pierde (D40)."""
        self._stop("DISABLE")

    def enable(self):
        self.order("ENABLE")

    def zero(self):
        self.order("ZERO")

    def snapshot(self):
        with self.lock:
            status = None
            if self.status is not None:
                status = dict(self.status, age_s=round(time.monotonic() - self.status_time, 3))
            tramo = None
            if self.tramo is not None:
                tramo = dict(self.tramo)
                done = 0 if status is None else status["last"] - tramo["first"] + 1
                tramo["done"] = max(0, min(done, tramo["segments"]))
            return {
                "protocol": PROTOCOL,
                "connected": self.connected,
                "peer": self.peer,
                "message": self.message,
                "firmware": self.firmware,
                "boots": self.boots,
                "received": self.received,
                "status": status,
                "referenced": status is not None and status["homed"] == ALL_HOMED,
                "doubtful": [dict(item) for item in self.doubtful],
                "jog": None if self.jogging is None else dict(zip(("joint", "direction", "motor"), self.jogging)),
                "segments": {"pending": len(self.segments), "in_flight": self.in_flight, "last_ok": self.last_ok},
                "tramo": tramo,
                "homing": None if self.homing is None else dict(self.homing, axes=list(self.homing["axes"])),
                "traffic": list(self.traffic),
                "errors": list(self.errors),
                "rejected": list(self.rejected),
            }

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)
        self.listener.close()

    # --- Hilo del enlace (con self.lock tomado en los helpers) -------------

    def _stop(self, line):
        with self.lock:
            self._require_robot()
            self.jogging = None
            self._cancel_segments("frenado por el operador")
            self._end_homing("frenado por el operador")
            self._queue(line)

    def _require_still(self, what):
        if self.status is None:
            raise ValueError("Todavía no llegó el estado de la UCI")
        if self.status["mode"] == "OFF":
            raise ValueError("Los motores están sin corriente: habilitalos primero")
        if self.status["mode"] != "IDLE" or self.jogging is not None or self._tramo_running():
            raise ValueError(f"El robot se está moviendo: esperá a que frene antes de {what}")

    def _follow_homing(self):
        """El modo de S dice cómo va el homing.

        Si terminó sin los cuatro ejes, abortó; si nunca empezó, la UCI rechazó
        el HOME (el ERR dice por qué). Con los cuatro y el robot quieto, pide
        volver al reposo.
        """
        homing, mode = self.homing, self.status["mode"]
        if homing is None:
            return
        if homing["state"] == "terminado" and homing["park"] and mode == "IDLE" and self.status["homed"] == ALL_HOMED:
            homing["park"] = False
            self.park_requested = True
        if homing["state"] != "en curso":
            return
        if mode == "HOMING":
            homing["seen"] = True
        elif homing["seen"] and len(homing["axes"]) < len(HOME_ORDER):
            self._end_homing("el robot se detuvo sin terminar")
        elif not homing["seen"] and time.monotonic() - homing["sent"] > HOME_START:
            self._end_homing("la UCI no empezó el homing")

    def _end_homing(self, reason):
        if self.homing is not None and self.homing["state"] == "en curso":
            self.homing.update(state=f"abortado: {reason}", park=False)

    def _park_after_homing(self):
        """Con los cuatro ejes encontrados y el robot quieto, vuelve al reposo (D11, D56).

        Lo planifica la URC, como cualquier PTP: verifica choques en el camino
        desde las referencias, con J1 y J2 plegados en −130°.
        """
        if not self.park_requested:
            return
        self.park_requested = False
        try:
            plan = self.park()
        except (ValueError, ConnectionError) as exc:
            with self.lock:
                self.message = f"Homing terminado, pero no se pudo volver al reposo: {exc}"
            return
        with self.lock:
            self.message = f"Homing terminado; volviendo al reposo en {plan['duration_s']:.1f} s"

    def _enqueue(self, segments):
        """Numera los segmentos y los suma al tramo actual: salen de a uno, con cada OK."""
        first = self.next_segment
        self.segments.extend(segment_line(first + index, ms, units) for index, (ms, units) in enumerate(segments))
        self.next_segment += len(segments)
        self.tramo["last"] = self.next_segment - 1
        self.tramo["segments"] = self.tramo["last"] - self.tramo["first"] + 1

    def _segments_pending(self):
        return bool(self.segments) or self.in_flight is not None

    def _tramo_running(self):
        """Quedan segmentos por enviar, o el robot todavía no terminó los enviados."""
        if self._segments_pending():
            return True
        return (self.tramo is not None and self.tramo["cancelled"] is None
                and (self.status is None or self.status["last"] < self.tramo["last"]))

    def _cancel_segments(self, reason):
        """Descarta lo que falta enviar del tramo; un OK que llegue tarde se ignora."""
        if self.tramo is not None and self._tramo_running():
            self.tramo["cancelled"] = reason
        self.segments.clear()
        self.in_flight = None

    def _require_robot(self):
        if not self.connected:
            raise ConnectionError("No hay una UCI conectada; la orden no se guardó")

    def _queue(self, line):
        try:
            self.outgoing.put_nowait(line)
        except queue.Full as exc:
            raise ValueError("Hay demasiadas órdenes pendientes") from exc

    def _discard_outgoing(self):
        while True:
            try:
                self.outgoing.get_nowait()
            except queue.Empty:
                return

    def _attach(self, client, address):
        with self.lock:
            self.connected = True
            self.peer = f"{address[0]}:{address[1]}"
            self._cancel_segments("la UCI se volvió a conectar")
            self.firmware = None
            self.status = None
            self.greeted = False
            self.jogging = None
            self._discard_outgoing()
            self.message = "UCI conectada"
            self._queue("HELLO")

    def _detach(self, reason):
        with self.lock:
            self.connected = False
            self.peer = None
            self.jogging = None
            self._discard_outgoing()
            self._cancel_segments("la UCI se desconectó")
            self.message = f"UCI desconectada: {reason}. Esperando que se vuelva a conectar."

    def _receive(self, raw):
        """Una línea mala se informa y se descarta; no corta el enlace."""
        with self.lock:
            self.received += 1
            try:
                if len(raw) + 1 > LINE_MAX:
                    raise ValueError("línea de más de 64 bytes")
                line = raw.decode("ascii").rstrip("\r")
            except ValueError as exc:
                self.rejected.append(f"{raw[:LINE_MAX]!r}: {exc}")
                return
            if not line.strip():
                return
            # El estado y los OK llegan decenas de veces por segundo.
            if not line.startswith(("S ", "OK ")):
                self.traffic.append({"direction": "<", "line": line})
            try:
                message = parse_message(line)
            except ValueError as exc:
                self.rejected.append(f"{line!r}: {exc}")
                return
            kind = message["kind"]
            if kind in ("BOOT", "HI"):
                self.firmware = {"protocol": message["protocol"], "version": message["version"]}
            if kind == "BOOT":
                self._booted()
            elif kind == "S":
                self.status = {key: value for key, value in message.items() if key != "kind"}
                self.status_time = time.monotonic()
                self._follow_homing()
                # Un eje sin referencia ya no tiene una referencia dudosa.
                self.doubtful = [item for item in self.doubtful
                                 if self.status["homed"] >> (item["joint"] - 1) & 1]
                # Todo enviado y el robot quieto antes del último segmento: el
                # firmware frenó por algo que la URC no vio (un ERR ilegible).
                if (self.status["mode"] == "IDLE" and not self._segments_pending()
                        and self._tramo_running()):
                    self._cancel_segments("el robot se detuvo antes de terminar")
            elif kind == "EV" and message["event"] == "LOST":
                self._lost_steps(message["joint"], message["steps"])
            elif kind == "EV":
                self.doubtful = [item for item in self.doubtful if item["joint"] != message["joint"]]
                if self.homing is not None and message["joint"] not in self.homing["axes"]:
                    self.homing["axes"].append(message["joint"])
                    if sorted(self.homing["axes"]) == sorted(HOME_ORDER) and self.homing["state"] == "en curso":
                        self.homing["state"] = "terminado"
                        self.message = "Homing terminado: los cuatro ejes referenciados"
            elif kind == "OK":
                self.last_ok = message["number"]
                if message["number"] == self.in_flight:
                    self.in_flight = None
            elif kind == "ERR":
                self.errors.append(f"ERR {message['code']} {message['word']}: {message['cause']}")
                # Con segmentos en ejecución, el firmware frena con rampa ante
                # todo ERR: el resto del tramo ya no se envía.
                if self._tramo_running():
                    self._cancel_segments(f"la UCI respondió ERR {message['code']} {message['word']}")
                    self.message = f"Tramo cancelado: ERR {message['code']} {message['word']}"
                if message["code"] in (4, 11, 12):  # los que abortan el homing
                    self._end_homing(f"ERR {message['code']} {message['word']}: {message['cause']}")
            self.greeted = True

    def _lost_steps(self, joint, steps):
        """F1: al cruzar su Hall, el eje no estaba donde contó el firmware (D65).

        El firmware sigue referenciado y no corrige su cuenta; la URC marca la
        referencia como dudosa y lo avisa, también en la lista de errores, que
        no se pisa con el próximo mensaje. Solo el homing de ese eje la limpia.
        Cada eje aparece una vez, con lo último que informó.
        """
        self.doubtful = [item for item in self.doubtful if item["joint"] != joint]
        self.doubtful.append({"joint": joint, "steps": steps})
        self.message = (f"Pérdida de pasos en J{joint}: {steps:+d} pasos completos al cruzar su Hall. "
                        "La referencia es dudosa: conviene hacer homing.")
        self.errors.append(f"EV LOST {joint} {steps}: referencia dudosa de J{joint}, conviene hacer homing")

    def _booted(self):
        """La UCI arrancó: toda referencia y toda orden pendiente quedan sin valor."""
        self.boots += 1
        self.doubtful = []
        self._cancel_segments("la UCI se reinició")
        self._end_homing("la UCI se reinició")
        self.status = None
        self.jogging = None
        self._discard_outgoing()
        if self.greeted:
            # A mitad de una conexión: la UCI se reinició sola (falla F5).
            self.message = "BOOT inesperado: la UCI se reinició y perdió la referencia (F5)"
        else:
            self.message = "La UCI arrancó: sin referencia hasta ZERO u homing"

    def _send_pending(self, client, now):
        lines = []
        with self.lock:
            if self.jogging is not None and now > self.jog_deadline:
                self.jogging = None
                lines.append("JOG STOP")
            while True:
                try:
                    lines.append(self.outgoing.get_nowait())
                except queue.Empty:
                    break
            for line in lines:
                self.traffic.append({"direction": ">", "line": line})
            # Un solo SEG sin confirmar: el próximo sale con el OK.
            if self.in_flight is None and self.segments:
                line = self.segments.popleft()
                self.in_flight = int(line.split()[1])
                lines.append(line)
        if now - self.last_ping >= PING_PERIOD:
            self.last_ping = now
            lines.append("PING")
        if lines:
            client.sendall("".join(line + "\n" for line in lines).encode())

    def _run(self):
        client, buffer = None, b""
        self.last_ping = 0.0
        while not self.closed.is_set():
            readable, _, _ = select.select([self.listener] + ([client] if client else []), [], [], 0.05)
            try:
                if self.listener in readable:
                    # Una conexión nueva reemplaza a la anterior: Webots reinició.
                    new_client, address = self.listener.accept()
                    if client is not None:
                        client.close()
                    client, buffer = new_client, b""
                    self._attach(client, address)
                if client is None:
                    continue
                if client in readable:
                    chunk = client.recv(4096)
                    if not chunk:
                        raise ConnectionError("cerró la conexión")
                    buffer += chunk
                    *lines, buffer = buffer.split(b"\n")
                    for raw in lines:
                        self._receive(raw)
                    # Lo que pasa de 64 bytes sin LF ya es una línea inválida.
                    buffer = buffer[:LINE_MAX]
                self._send_pending(client, time.monotonic())
                self._park_after_homing()
            except OSError as exc:
                if client is not None:
                    client.close()
                client, buffer = None, b""
                self._detach(exc)
        if client is not None:
            client.close()
