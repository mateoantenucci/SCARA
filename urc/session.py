"""Sesión de la URC con la UCI por scara/1 (docs/PROTOCOLO_SCARA_1.md).

La URC escucha (D1) y la UCI se conecta: el controlador de Webots, socat o un
Arduino con Ethernet. Un hilo posee los sockets; la interfaz HTTP solo consulta
el estado y deja órdenes en una cola.
"""

from collections import deque
import queue
import re
import select
import socket
import threading
import time


PROTOCOL = "scara/1"
LINE_MAX = 64                # bytes con el LF (D4)
PING_PERIOD = 0.25           # s (D27)
JOG_SPEED = 500              # centésimas por segundo: jog articular lento
JOG_HOLD = 0.5               # s sin renovar el jog desde la página => JOG STOP
MODES = ("IDLE", "JOG")
INTEGER = re.compile(r"-?[0-9]+")


def integer(text):
    """Entero del protocolo: solo cifras ASCII y un signo menos opcional."""
    if not INTEGER.fullmatch(text):
        raise ValueError(f"{text!r} no es un entero")
    return int(text)


def parse_status(fields):
    """S modo referenciados J1 J2 J3 J4 hall libres último."""
    if len(fields) != 9 or fields[0] not in MODES:
        raise ValueError("estado S mal formado")
    numbers = [integer(value) for value in fields[1:]]
    return {
        "mode": fields[0],
        "homed": numbers[0],
        "position": numbers[1:5],
        "hall": numbers[5],
        "free": numbers[6],
        "last": numbers[7],
    }


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
        self.errors = deque(maxlen=10)
        self.connected = False
        self.peer = None
        self.firmware = None
        self.boots = 0
        self.status = None
        self.status_time = None
        self.jogging = None          # (articulación, sentido) enviado a la UCI
        self.jog_deadline = 0.0
        self.message = f"Esperando a la UCI en el puerto {self.port}"
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="scara-uci", daemon=True)
        self.thread.start()

    # --- Órdenes desde la interfaz ---------------------------------------

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
        with self.lock:
            self._require_robot()
            self.jogging = None
            self._queue("JOG STOP")

    def zero(self):
        with self.lock:
            self._require_robot()
            self._queue("ZERO")

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
                "status": status,
                "jog": None if self.jogging is None else {"joint": self.jogging[0], "direction": self.jogging[1]},
                "traffic": list(self.traffic),
                "errors": list(self.errors),
            }

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)
        self.listener.close()

    # --- Hilo del enlace (con self.lock tomado en los helpers) -------------

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
        try:
            if len(raw) + 1 > LINE_MAX:
                raise ValueError("línea de más de 64 bytes")
            line = raw.decode("ascii").rstrip("\r")
        except ValueError as exc:
            with self.lock:
                self.errors.append(f"{raw[:LINE_MAX]!r}: {exc}")
            return
        fields = line.split()
        with self.lock:
            if fields and fields[0] != "S":
                self.traffic.append({"direction": "<", "line": line})
            try:
                if not fields:
                    return
                if fields[0] in ("BOOT", "HI"):
                    if len(fields) != 3:
                        raise ValueError(f"{fields[0]} mal formado")
                    if fields[1] != PROTOCOL:
                        raise ValueError(f"la UCI habla {fields[1]}, no {PROTOCOL}")
                    self.firmware = {"protocol": fields[1], "version": integer(fields[2])}
                    if fields[0] == "BOOT":
                        # Arranque de la UCI: toda referencia anterior se perdió.
                        self.boots += 1
                        self.message = "La UCI arrancó: sin referencia hasta ZERO u homing"
                elif fields[0] == "S":
                    self.status = parse_status(fields[1:])
                    self.status_time = time.monotonic()
                elif fields[0] == "ERR":
                    self.errors.append(line)
                else:
                    raise ValueError("mensaje desconocido")
            except ValueError as exc:
                self.errors.append(f"{line!r}: {exc}")

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
