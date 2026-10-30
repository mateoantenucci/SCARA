"""Sesión de la URC con la UCI por scara/1 (docs/PROTOCOLO_SCARA_1.md).

La URC escucha (D1) y la UCI se conecta: el controlador de Webots, socat o un
Arduino con Ethernet. Un hilo posee los sockets; la interfaz HTTP solo consulta
el estado y deja órdenes en una cola.
"""

from collections import deque
import queue
import select
import socket
import threading
import time

from urc.protocol import LINE_MAX, PROTOCOL, check_order, parse_message


PING_PERIOD = 0.25           # s (D27)
JOG_SPEED = 500              # centésimas por segundo: jog articular lento
JOG_HOLD = 0.5               # s sin renovar el jog desde la página => JOG STOP
ALL_HOMED = 0x0F


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
        self.jogging = None          # (articulación, sentido) enviado a la UCI
        self.jog_deadline = 0.0
        self.message = f"Esperando a la UCI en el puerto {self.port}"
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="scara-uci", daemon=True)
        self.thread.start()

    # --- Órdenes desde la interfaz ---------------------------------------

    def order(self, line):
        """Envía una orden de scara/1 tal cual, si su forma es válida.

        Un JOG enviado así no vence como el de jog(): solo lo frenan JOG STOP,
        STOP o HALT. Por eso la página no lo expone.
        """
        line = check_order(line)
        with self.lock:
            self._require_robot()
            self._queue(line)

    def jog(self, joint, direction):
        """Mantiene el jog mientras la página lo renueve antes de jog_hold."""
        if type(joint) is not int or joint not in range(1, 5):
            raise ValueError("La articulación debe ser 1, 2, 3 o 4")
        if direction not in ("+", "-"):
            raise ValueError("El sentido debe ser + o -")
        with self.lock:
            self._require_robot()
            self.jog_deadline = time.monotonic() + self.jog_hold
            if self.jogging != (joint, direction):
                self.jogging = (joint, direction)
                self._queue(f"JOG {joint} {direction} {self.jog_speed}")

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
                "jog": None if self.jogging is None else {"joint": self.jogging[0], "direction": self.jogging[1]},
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
            self._queue(line)

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
            if not line.startswith("S "):
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
            elif kind == "ERR":
                self.errors.append(f"ERR {message['code']} {message['word']}: {message['cause']}")
            self.greeted = True

    def _booted(self):
        """La UCI arrancó: toda referencia y toda orden pendiente quedan sin valor."""
        self.boots += 1
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
            except OSError as exc:
                if client is not None:
                    client.close()
                client, buffer = None, b""
                self._detach(exc)
        if client is not None:
            client.close()
