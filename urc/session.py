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
from urc import jog as jogging, planner, validation
from urc.events import EventLog
from urc.protocol import LINE_MAX, PROTOCOL, check_order, parse_message, segment_line


PING_PERIOD = 0.25           # s (D27)
JOG_SPEED = 1000             # centésimas por segundo, con referencia: el máximo sin rampa del firmware
JOG_SPEED_UNREFERENCED = 500  # sin referencia, el firmware no pasa de acá (D58)
JOG_SPEED_SLOW = 200         # con Mayús, el jog que ejecuta el firmware
JOG_HOLD = 0.5               # s sin renovar el jog desde la página => frena
# Con referencia, el jog articular y el cartesiano son segmentos que planifica
# y verifica la URC (D28, D75): mantiene encolados JOG_QUEUE, así el robot
# frena apenas se suelta la tecla. Los cuenta en el reloj de la UCI, que
# puede ir más lento que el de la PC (Webots por debajo del tiempo real): lo
# mide por el período de S, que la UCI envía cada STATUS_PERIOD.
JOG_QUEUE = 3                # segmentos
STATUS_PERIOD = 0.05         # s del reloj de la UCI (D27)
JOG_POLL = 0.01              # s entre vueltas del hilo del enlace durante ese jog
# El jog por motor lo ejecuta el firmware (D46): con referencia, frena antes
# del límite de recorrido y de un choque (D70). El estado S llega cada 50 ms
# y el JOG STOP tarda otro tanto: frena si en JOG_STOP_AHEAD pasaría el
# límite, o si en JOG_LOOKAHEAD entraría en la zona de margen de un obstáculo.
JOG_STOP_AHEAD = 0.15        # s
JOG_LOOKAHEAD = (0.15, 0.3)  # s
# Un pedido de jog que estaba en camino al frenar con Stop, Parada inmediata
# o Deshabilitar no lo reanuda: la página pide cada 150 ms.
STOP_GUARD = 0.3             # s
ALL_HOMED = 0x0F
REST = (0, 0, 0, 12000)      # pose de reposo (D30), en centésimas
PARK_SPEED = 1.0             # «Estacionar» y la vuelta al reposo del homing (D56)
HOME_ORDER = (4, 1, 2, 3)    # D11
HOME_START = 1.0             # s para que S muestre HOMING después de enviar HOME
LINK_LATE = 1.0              # s sin S: el enlace se cortó (F4) y el watchdog del firmware ya frenó (D37)


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
        self.status_times = deque(maxlen=11)  # llegada de los últimos S, para el ritmo de la UCI
        self.jogging = None          # (modo, eje, sentido, por motor, lento) del jog en curso
        self.jog_plan = None         # el jog por segmentos en curso: orden, codo y adónde llega
        self.jog_end = None          # dónde termina el último segmento del jog, sin redondear
        self.jog_last = None         # número del último SEG del jog que el robot no descartó
        self.jog_deadline = 0.0
        self.stopped_jog = None      # (jog, cuándo) frenado por STOP, HALT o DISABLE
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
        self.link_late = False       # pasó LINK_LATE sin S: ya se avisó
        # El modelo para planificar se lee una vez.
        self.config = load_config()
        self.checker = CollisionChecker(self.config)
        self.limits = planner.default_limits(self.config)
        self.travel = planner.travel(self.config)
        # El registro de eventos de la página (D78): lo que informa la UCI y lo
        # que decide la URC, con número y hora; el servidor HTTP y el banco de
        # ensayo anotan ahí también.
        self.events = EventLog()
        self._say(f"Esperando a la UCI en el puerto {self.port}")
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

    def move_ptp(self, target, speed=0.25, dry_run=False, name="destino"):
        """Tramo PTP desde la posición estimada hasta target (J1–J4 en centésimas).

        Valida límites y choques en todo el camino; name nombra el destino en
        el rechazo («punto 3»). Con dry_run solo planifica: la página
        muestra la duración y pide confirmación.
        """
        with self.lock:
            self._require_robot()
            status = self.status
            if status is None or status["homed"] != ALL_HOMED:
                raise ValueError("El robot tiene que estar referenciado para un tramo PTP")
            if (status["mode"] != "IDLE" or self.jogging is not None or self._segments_pending()
                    or self._jog_draining()):
                raise ValueError("El robot se está moviendo: esperá a que frene")
            start = tuple(status["position"])
        place = validation.Place(None, "pose actual", name)
        plan = validation.check_ptp(start, planner.check_units(target, "Destino"), speed, place, self.limits,
                                    self.config, self.checker)
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
            self._say(f"Tramo PTP en curso: {len(plan.segments)} segmentos, {summary['duration_s']:.2f} s")
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
            self._say("Homing en curso: J4, J1, J2 y J3")
            self._queue("HOME")

    def park(self):
        """Estacionar: PTP a la pose de reposo (D30), con el robot referenciado."""
        return self.move_ptp(REST, PARK_SPEED, name="pose de reposo")

    def jog(self, joint, direction, motor=False, mode="articular", slow=False):
        """Mantiene el jog mientras la página lo renueve antes de jog_hold.

        joint es la tecla, 1–4, igual en los dos modos (urc/jog.py). Con
        referencia, el articular y el cartesiano son segmentos verificados que
        planifica la URC (D28, D75). Sin referencia solo hay jog articular,
        que el firmware lleva lento y solo lo frena el Hall (D58). Con
        motor=True mueve solo el motor M<joint>, sin compensar el acople
        M1/M2 (D46): lo ejecuta el firmware y, con referencia, la URC lo frena
        antes del límite de recorrido o de la zona de choque (D70). slow es
        el jog lento (Mayús).
        """
        if type(joint) is not int or joint not in range(1, 5):
            raise ValueError("La articulación debe ser 1, 2, 3 o 4")
        if direction not in ("+", "-"):
            raise ValueError("El sentido debe ser + o -")
        if type(motor) is not bool:
            raise ValueError("motor debe ser true o false")
        if mode not in jogging.MODES:
            raise ValueError("El modo de jog debe ser articular o cartesiano")
        if type(slow) is not bool:
            raise ValueError("slow debe ser true o false")
        if motor and mode != "articular":
            raise ValueError("El jog por motor es articular")
        jog = (mode, joint, direction, motor, slow)
        with self.lock:
            self._require_robot()
            if self._tramo_running():
                raise ValueError("Hay un tramo en curso: frenalo con Stop antes del jog")
            if self.status is not None and self.status["mode"] == "HOMING":
                raise ValueError("El homing está en curso: frenalo con Stop antes del jog")
            if (self.jogging is None and self.stopped_jog is not None and self.stopped_jog[0] == jog
                    and time.monotonic() - self.stopped_jog[1] < STOP_GUARD):
                return
            if mode == "cartesiano" and not self._referenced():
                raise ValueError("Sin referencia, el jog cartesiano está deshabilitado: hacé homing o referencia manual")
            if self._referenced() and not motor:
                self._jog_segments(jog)
                return
            speed = self._firmware_jog_speed(jog)
            if self.jogging != jog and (self.jog_plan is not None or self._jog_draining()):
                raise ValueError("El robot todavía está frenando el jog anterior")
            blocked = self._jog_blocked(joint, direction, motor, speed)
            if blocked:
                raise ValueError(f"Jog frenado: {blocked}")
            self.jog_deadline = time.monotonic() + self.jog_hold
            if self.jogging != jog:
                self._end_jog()
                self.jogging = jog
                self._queue(f"JOG {'M' if motor else ''}{joint} {direction} {speed}")

    def jog_stop(self):
        """Soltar la tecla: frena el jog y nada más.

        El jog por segmentos no envía nada: el robot termina lo encolado y
        frena. Sin jog en curso no hay nada que frenar; un tramo o un homing
        siguen (la página avisa al soltar aunque el jog se haya rechazado).
        """
        with self.lock:
            self._require_robot()
            firmware = self.jogging is not None and self.jog_plan is None
            self._end_jog()
            if firmware:
                self._queue("JOG STOP")

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
                "message_time": self.message_time,
                "firmware": self.firmware,
                "boots": self.boots,
                "received": self.received,
                "status": status,
                "referenced": status is not None and status["homed"] == ALL_HOMED,
                "travel": [list(bounds) for bounds in self.travel],
                "doubtful": [dict(item) for item in self.doubtful],
                "jog": None if self.jogging is None else dict(zip(("mode", "joint", "direction", "motor", "slow"),
                                                                  self.jogging)),
                "elbow": None if status is None else jogging.elbow_name(status["position"]),
                "tool": None if status is None else self._tool(status["position"]),
                "segments": {"pending": len(self.segments), "in_flight": self.in_flight, "last_ok": self.last_ok},
                "tramo": tramo,
                "homing": None if self.homing is None else dict(self.homing, axes=list(self.homing["axes"])),
                "traffic": list(self.traffic),
                "errors": list(self.errors),
                "rejected": list(self.rejected),
                "events_version": self.events.version,
            }

    def _tool(self, units):
        """Punto de herramienta en mm y rumbo en centésimas de grado, para la página."""
        x, y, z = planner.tool_point(units, self.config)
        return {"x": round(x * 1000, 2), "y": round(y * 1000, 2), "z": round(z * 1000, 2),
                "heading": sum(units[:3])}

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)
        self.listener.close()

    # --- Hilo del enlace (con self.lock tomado en los helpers) -------------

    def _stop(self, line):
        """STOP, HALT o DISABLE: frenan todo, también el jog."""
        with self.lock:
            self._require_robot()
            if self.jogging is not None:
                self.stopped_jog = (self.jogging, time.monotonic())
            self._end_jog()
            # El firmware vacía la cola: lo que quedaba del jog no se ejecuta.
            self.jog_last = None
            self._cancel_segments("frenado por el operador")
            self._end_homing("frenado por el operador")
            self._queue(line)

    def _referenced(self):
        return self.status is not None and self.status["homed"] == ALL_HOMED

    def _say(self, text, level="info"):
        """El mensaje de la URC que muestra la página; también va al registro de eventos."""
        self.message, self.message_time = text, time.time()
        self.events.add(level, "URC", text)

    def _reject_line(self, text):
        self.rejected.append(text)
        # Aviso y no error: el Arduino suele mandar ruido al reiniciarse (D49).
        self.events.add("aviso", "UCI", f"Línea de la UCI que no respeta scara/1: {text}")

    def _jog_segments(self, jog):
        """Jog articular o cartesiano con referencia: la URC lo planifica en segmentos (D28, D75).

        Verifica ya el primer paso, así la página muestra enseguida por qué
        no puede seguir. Si el robot todavía termina otro jog, el nuevo
        arranca cuando frene, desde donde frenó: los segmentos arrancan y
        frenan sin rampa, y un cambio de sentido sin frenar sería el doble.
        """
        self.jog_deadline = time.monotonic() + self.jog_hold
        if self.jogging == jog and self.jog_plan is not None:
            return
        mode, joint, direction, _, slow = jog
        command = jogging.Command(mode, joint, 1 if direction == "+" else -1, slow)
        start = self.jog_end if self._jog_draining() and self.jog_end is not None else self.status["position"]
        try:
            jogging.step(start, command, jogging.elbow_of(start), self.config, self.checker, self.travel)
        except jogging.Blocked as exc:
            raise ValueError(f"Jog frenado: {exc}") from None
        if self.jogging is not None and self.jog_plan is None:
            self._queue("JOG STOP")  # un jog por motor en curso
        self.jogging = jog
        self.jog_plan = {"command": command, "q": None, "elbow": None, "clock": 0.0}

    def _feed_jog(self, now):
        """El próximo SEG del jog por segmentos, o None si la cola ya tiene lo suyo.

        Un SEG sin confirmar por vez (D50). El primero espera al robot quieto
        y arranca de la posición estimada; los demás siguen del último
        segmento sin redondear, así el punto de herramienta no acumula el
        redondeo.
        """
        plan = self.jog_plan
        if plan is None or self.in_flight is not None or self.segments or self.status is None:
            return None
        if plan["q"] is None:
            if self.status["mode"] != "IDLE" or self._jog_draining():
                return None
            plan["q"] = tuple(float(v) for v in self.status["position"])
            plan["elbow"] = jogging.elbow_of(plan["q"])
            plan["clock"] = now
        # Lo que tarda un segmento en el reloj de la PC. La cola se mide de
        # dos maneras: por lo enviado desde que arrancó, y por lo que el
        # último S dice que terminó más lo que pasó desde entonces.
        seconds = jogging.SEGMENT_MS / 1000 / self._uci_rate()
        if max(plan["clock"], now) + seconds - now > JOG_QUEUE * seconds + 1e-6:
            return None
        # Sin un S nuevo en dos períodos, la UCI pudo trabarse (Webots
        # cargado): no se supone que siguió avanzando, o la cola se llenaría.
        elapsed = min(now - self.status_time, 2 * STATUS_PERIOD * seconds / (jogging.SEGMENT_MS / 1000))
        executed = self.status["last"] + elapsed / seconds
        if self.jog_last is not None and self.jog_last - executed >= JOG_QUEUE:
            return None
        try:
            q = jogging.step(plan["q"], plan["command"], plan["elbow"], self.config, self.checker, self.travel)
        except jogging.Blocked as exc:
            self._say(f"Jog frenado: {exc}", "aviso")
            self._end_jog()
            return None
        number = self.next_segment
        self.next_segment += 1
        plan["q"] = self.jog_end = q
        plan["clock"] = max(plan["clock"], now) + seconds
        self.jog_last = self.in_flight = number
        return segment_line(number, jogging.SEGMENT_MS, jogging.rounded(q))

    def _uci_rate(self):
        """Segundos del reloj de la UCI por segundo de la PC, por el período de los últimos S; hasta 1.

        Un hueco de más de cuatro períodos es el enlace, no el reloj: no cuenta.
        """
        times = list(self.status_times)
        gaps = [b - a for a, b in zip(times, times[1:]) if b - a <= 4 * STATUS_PERIOD]
        if not gaps or sum(gaps) <= 0:
            return 1.0
        return min(1.0, max(0.2, STATUS_PERIOD * len(gaps) / sum(gaps)))

    def _jog_draining(self):
        """El robot todavía no terminó los segmentos de un jog que ya no se alimenta."""
        return (self.jog_last is not None and self.status is not None
                and self.status["last"] < self.jog_last)

    def _end_jog(self):
        self.jogging = None
        self.jog_plan = None

    def _firmware_jog_speed(self, jog):
        """Centésimas por segundo del jog que ejecuta el firmware: sin referencia o por motor."""
        speed = JOG_SPEED_SLOW if jog[4] else self.jog_speed
        return speed if self._referenced() else min(speed, JOG_SPEED_UNREFERENCED)

    def _jog_blocked(self, joint, direction, motor, speed):
        """Por qué un jog del firmware no puede seguir con referencia, o None (D70).

        Mira adelante en el sentido del jog, desde la posición estimada del
        último S: el límite de recorrido de cada articulación que mueve y la
        zona de margen de los obstáculos. Dentro de esa zona puede salir: solo
        frena si la separación disminuye. Sin referencia no sabe dónde está el
        robot: lo protege el Hall (D21, D58).
        """
        if not self._referenced():
            return None
        # El jog articular mueve una articulación; el de M1 gira el brazo y J2
        # cambia al revés (D46); M2, M3 y M4 mueven J2, J3 y J4.
        axes = [0, 0, 0, 0]
        axes[joint - 1] = 1
        if motor and joint == 1:
            axes[1] = -1
        velocity = [(1 if direction == "+" else -1) * axis * speed for axis in axes]
        position = self.status["position"]
        for name, value, speed, (low, high) in zip(planner.NAMES, position, velocity, self.travel):
            ahead = value + speed * JOG_STOP_AHEAD
            if (speed > 0 and ahead > high) or (speed < 0 and ahead < low):
                bound, unit = (high if speed > 0 else low) / 100, " mm" if name == "J4" else "°"
                return f"{name} llegó al límite de su recorrido ({bound:g}{unit})"
        here = self.checker.clearance(planner.inside_range(position, self.config))
        for seconds in JOG_LOOKAHEAD:
            ahead = planner.inside_range([v + s * seconds for v, s in zip(position, velocity)], self.config)
            if self.checker.clearance(ahead) < min(here, self.checker.margin):
                conflict = self.checker.first_conflict(ahead, ahead)
                where = f"{conflict['instance']} tocaría {conflict['obstacle']}" if conflict else "habría un choque"
                return f"{where} (envolventes y margen de {self.checker.margin * 1000:g} mm)"
        return None

    def _guard_jog(self):
        """Con cada S, el jog del firmware en curso frena antes del límite o del choque.

        El jog por segmentos se verifica antes de enviar cada uno; sin la
        referencia, ya no se alimenta.
        """
        if self.jog_plan is not None and not self._referenced():
            self._say("Jog frenado: el robot perdió la referencia", "aviso")
            self._end_jog()
        if self.jogging is None or self.jog_plan is not None or self.status["mode"] != "JOG":
            return
        _, joint, direction, motor, _ = self.jogging
        blocked = self._jog_blocked(joint, direction, motor, self._firmware_jog_speed(self.jogging))
        if blocked:
            # _send_pending envía el JOG STOP; las renovaciones de la página lo rechazan.
            self.jog_deadline = 0.0
            self._say(f"Jog frenado: {blocked}", "aviso")

    def _require_still(self, what):
        if self.status is None:
            raise ValueError("Todavía no llegó el estado de la UCI")
        if self.status["mode"] == "OFF":
            raise ValueError("Los motores están sin corriente: habilitalos primero")
        if (self.status["mode"] != "IDLE" or self.jogging is not None or self._tramo_running()
                or self._jog_draining()):
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
        """El homing abortado deja sin referencia los ejes de ese HOME, y la
        página lo dice en el mensaje, no solo en la línea del homing (D87)."""
        if self.homing is not None and self.homing["state"] == "en curso":
            self.homing.update(state=f"abortado: {reason}", park=False)
            self._say(f"Homing abortado, sin referencia: {reason.replace('homing abortado: ', '')}", "aviso")

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
                self._say(f"Homing terminado, pero no se pudo volver al reposo: {exc}", "aviso")
            return
        with self.lock:
            self._say(f"Homing terminado; volviendo al reposo en {plan['duration_s']:.1f} s")

    def _watch_link(self, now):
        """Avisa una vez cuando el estado S deja de llegar por más de LINK_LATE, y cuando vuelve (D78)."""
        with self.lock:
            if self.status is None:
                return
            late = now - self.status_time > LINK_LATE
            if late and not self.link_late:
                self.events.add("error", "URC", f"Sin estado de la UCI hace más de {LINK_LATE:g} s: el enlace "
                                "se cortó o la UCI se trabó. El firmware frena solo (watchdog).")
            elif self.link_late and not late:
                self.events.add("ok", "URC", "Volvió a llegar el estado de la UCI")
            self.link_late = late

    def _enqueue(self, segments):
        """Numera los segmentos y los suma al tramo actual: salen de a uno, con cada OK."""
        first = self.next_segment
        self.segments.extend(segment_line(first + index, ms, units) for index, (ms, units) in enumerate(segments))
        self.next_segment += len(segments)
        self.tramo["last"] = self.next_segment - 1
        self.tramo["segments"] = self.tramo["last"] - self.tramo["first"] + 1

    def _segments_pending(self):
        """Segmentos de un tramo por enviar o sin confirmar; los del jog van aparte."""
        return bool(self.segments) or (self.in_flight is not None and self.in_flight != self.jog_last)

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
            self.status_times.clear()
            self.greeted = False
            self._end_jog()
            self.jog_last = None
            self._discard_outgoing()
            self._say("UCI conectada", "ok")
            self._queue("HELLO")

    def _detach(self, reason):
        with self.lock:
            self.connected = False
            self.peer = None
            self._end_jog()
            self._discard_outgoing()
            self._cancel_segments("la UCI se desconectó")
            self._say(f"UCI desconectada: {reason}. Esperando que se vuelva a conectar.", "error")

    def _receive(self, raw):
        """Una línea mala se informa y se descarta; no corta el enlace."""
        with self.lock:
            self.received += 1
            try:
                if len(raw) + 1 > LINE_MAX:
                    raise ValueError("línea de más de 64 bytes")
                line = raw.decode("ascii").rstrip("\r")
            except ValueError as exc:
                self._reject_line(f"{raw[:LINE_MAX]!r}: {exc}")
                return
            if not line.strip():
                return
            # El estado y los OK llegan decenas de veces por segundo.
            if not line.startswith(("S ", "OK ")):
                self.traffic.append({"direction": "<", "line": line})
            try:
                message = parse_message(line)
            except ValueError as exc:
                self._reject_line(f"{line!r}: {exc}")
                return
            kind = message["kind"]
            if kind in ("BOOT", "HI"):
                self.firmware = {"protocol": message["protocol"], "version": message["version"]}
            if kind == "BOOT":
                self._booted()
            elif kind == "S":
                self.status = {key: value for key, value in message.items() if key != "kind"}
                self.status_time = time.monotonic()
                self.status_times.append(self.status_time)
                self._follow_homing()
                self._guard_jog()
                # Quieto, sin nada en camino y antes del último segmento del
                # jog: el firmware descartó la cola por algo que la URC no vio.
                if (self.jog_plan is None and self.in_flight is None and self.status["mode"] == "IDLE"
                        and self._jog_draining()):
                    self.jog_last = None
                # Un eje sin referencia ya no tiene una referencia dudosa.
                self.doubtful = [item for item in self.doubtful
                                 if self.status["homed"] >> (item["joint"] - 1) & 1]
                # Todo enviado y el robot quieto antes del último segmento: el
                # firmware frenó por algo que la URC no vio (un ERR ilegible).
                if (self.status["mode"] == "IDLE" and not self._segments_pending()
                        and self._tramo_running()):
                    self._cancel_segments("el robot se detuvo antes de terminar")
                    self._say("Movimiento cancelado: el robot se detuvo antes de terminar", "aviso")
            elif kind == "EV" and message["event"] == "LOST":
                self._lost_steps(message["joint"], message["steps"])
            elif kind == "EV":
                self.doubtful = [item for item in self.doubtful if item["joint"] != message["joint"]]
                self.events.add("info", "UCI", f"EV HOMED {message['joint']}: J{message['joint']} referenciado")
                if self.homing is not None and message["joint"] not in self.homing["axes"]:
                    self.homing["axes"].append(message["joint"])
                    if sorted(self.homing["axes"]) == sorted(HOME_ORDER) and self.homing["state"] == "en curso":
                        self.homing["state"] = "terminado"
                        self._say("Homing terminado: los cuatro ejes referenciados", "ok")
            elif kind == "OK":
                self.last_ok = message["number"]
                if message["number"] == self.in_flight:
                    self.in_flight = None
            elif kind == "ERR":
                self.errors.append(f"ERR {message['code']} {message['word']}: {message['cause']}")
                self.events.add("error", "UCI", self.errors[-1])
                # Con segmentos en ejecución, el firmware frena con rampa ante
                # todo ERR: el resto del tramo ya no se envía.
                if self._tramo_running():
                    self._cancel_segments(f"la UCI respondió ERR {message['code']} {message['word']}")
                    self._say(f"Tramo cancelado: ERR {message['code']} {message['word']}", "aviso")
                if self._jog_draining() or self.jog_plan is not None:
                    # Igual con los del jog, aunque ya se haya soltado la tecla:
                    # frena y descarta la cola.
                    if self.jog_plan is not None:
                        self._say(f"Jog frenado: ERR {message['code']} {message['word']}", "aviso")
                    self._end_jog()
                    self.jog_last = None
                    if self.in_flight is not None and not self._segments_pending():
                        self.in_flight = None
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
        self._say(f"Pérdida de pasos en J{joint}: {steps:+d} pasos completos al cruzar su Hall. "
                  "La referencia es dudosa: conviene hacer homing.", "error")
        self.errors.append(f"EV LOST {joint} {steps}: referencia dudosa de J{joint}, conviene hacer homing")

    def _booted(self):
        """La UCI arrancó: toda referencia y toda orden pendiente quedan sin valor."""
        self.boots += 1
        self.doubtful = []
        self._cancel_segments("la UCI se reinició")
        self._end_homing("la UCI se reinició")
        self.status = None
        self._end_jog()
        self.jog_last = None
        self._discard_outgoing()
        if self.greeted:
            # A mitad de una conexión: la UCI se reinició sola (falla F5).
            # También va a la lista de errores, que no la pisa el próximo
            # mensaje (D87).
            self._say("BOOT inesperado: la UCI se reinició y perdió la referencia (F5)", "error")
            self.errors.append("BOOT inesperado: la UCI se reinició sin corriente y sin referencia (F5)")
        else:
            self._say("La UCI arrancó: sin referencia hasta ZERO u homing")

    def _send_pending(self, client, now):
        lines = []
        with self.lock:
            if self.jogging is not None and now > self.jog_deadline:
                if self.jog_plan is None:
                    lines.append("JOG STOP")
                self._end_jog()
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
            elif (line := self._feed_jog(now)) is not None:
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
            # Durante el jog por segmentos, la cola se repone cada 10 ms.
            timeout = JOG_POLL if self.jog_plan is not None else 0.05
            readable, _, _ = select.select([self.listener] + ([client] if client else []), [], [], timeout)
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
                self._watch_link(time.monotonic())
            except OSError as exc:
                if client is not None:
                    client.close()
                client, buffer = None, b""
                self._detach(exc)
        if client is not None:
            client.close()
