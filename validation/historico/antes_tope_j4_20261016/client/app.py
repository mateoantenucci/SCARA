"""Interfaz local: python3 -m client.app. Solo usa la biblioteca estándar."""

import argparse
from collections import deque
import json
import math
from pathlib import Path
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from scara.kinematics import forward, inverse, load_config, validate_joints
from scara.collisions import CollisionChecker


PROTOCOL = "scara-dev/1"
MAX_FRAME = 16 * 1024


def finite_json(raw):
    """JSON estricto, también para exponentes que desbordan a infinito."""
    def invalid_constant(value):
        raise ValueError(f"Valor JSON no válido: {value}")

    value = json.loads(raw, parse_constant=invalid_constant)

    def check(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Los números deben ser finitos")
        if isinstance(item, dict):
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)

    check(value)
    return value


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} debe ser un número")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} está fuera de rango") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} debe ser finito")
    return value


class Bridge:
    """Un hilo posee el socket; HTTP solo consulta estado y encola órdenes."""

    def __init__(self, host="127.0.0.1", port=9000, config=None, retry_delay=1):
        self.host, self.port = host, port
        self.config = config if config is not None else load_config()
        self.retry_delay = retry_delay
        self.lock = threading.Lock()
        self.pending = queue.Queue(maxsize=64)
        self.responses = deque(maxlen=20)
        self.connected = False
        self.desired = True
        self.generation = 0
        self.state = None
        self.message = "Esperando al controlador de Webots"
        self.closed = threading.Event()
        self.changed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="scara-tcp", daemon=True)
        self.thread.start()

    def _discard_pending(self):
        while True:
            try:
                self.pending.get_nowait()
            except queue.Empty:
                return

    def connection(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("connect debe ser true o false")
        with self.lock:
            self.desired = enabled
            self.connected = False
            self.state = None
            self.generation += 1
            self._discard_pending()
            self.message = ("Reconectando; luego habilitá el robot explícitamente"
                            if enabled else "Desconectado por el usuario")
        self.changed.set()

    def snapshot(self):
        with self.lock:
            return {
                "protocol": PROTOCOL,
                "connected": self.connected,
                "connection_enabled": self.desired,
                "connection_message": self.message,
                "state": self.state,
                "responses": list(self.responses),
                "initial_pose": forward(self.config["initial_positions"], config=self.config),
            }

    def command(self, request):
        if not isinstance(request, dict):
            raise ValueError("La orden debe ser un objeto JSON")
        command = request.get("command")
        message = {"id": str(uuid4()), "command": command}
        if command == "move_cartesian":
            with self.lock:
                current = list((self.state or {}).get("estimated", self.config["initial_positions"]))
            yaw = request.get("yaw_deg")
            yaw = None if yaw is None else math.radians(number(yaw, "La orientación"))
            positions = inverse(
                number(request.get("x_mm"), "X") / 1000,
                number(request.get("y_mm"), "Y") / 1000,
                number(request.get("z_mm"), "Z") / 1000,
                yaw=yaw, current=current, config=self.config,
            )
            validate_joints(positions, config=self.config)
            with self.lock:
                payload = (self.state or {}).get("payload_mass", 0.0)
            CollisionChecker(self.config).validate_path(current, positions, payload)
            speed = number(request.get("speed"), "La velocidad")
            if not 0.1 <= speed <= 1:
                raise ValueError("La velocidad debe estar entre 10 y 100 %")
            message.update(command="move_joints", positions=positions, speed=speed)
        elif command == "fault":
            axis, kind = request.get("axis"), request.get("kind")
            if type(axis) is not int or axis not in range(1, 5):
                raise ValueError("Elegí un eje entre 1 y 4")
            if kind not in ("effort_loss", "hall_stuck"):
                raise ValueError("Tipo de falla desconocido")
            factor = number(request.get("factor", 0), "El factor de esfuerzo")
            if not 0 <= factor <= 1:
                raise ValueError("El factor debe estar entre 0 y 1")
            if kind == "hall_stuck" and factor not in (0, 1):
                raise ValueError("El sensor Hall atascado debe quedar activo (1) o inactivo (0)")
            message.update(kind=kind, axis=axis, factor=factor)
        elif command == "payload":
            mass = number(request.get("mass"), "La masa")
            if not 0 <= mass <= 2:
                raise ValueError("La carga de ensayo debe estar entre 0 y 2 kg")
            message["mass"] = mass
        elif command not in ("stop", "rearm", "clear_faults", "status", "reset_trial"):
            raise ValueError("Orden desconocida")

        frame = json.dumps(message, allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(frame) > MAX_FRAME:
            raise ValueError("La orden supera 16 KiB")
        with self.lock:
            if not self.connected:
                raise ConnectionError("Webots no está conectado. La orden no se guardó ni se enviará al reconectar.")
            if command in ("stop", "reset_trial"):
                self._discard_pending()
            try:
                self.pending.put_nowait((self.generation, frame))
            except queue.Full as exc:
                raise ValueError("Hay demasiadas órdenes pendientes; esperá una respuesta") from exc
        return {"id": message["id"], "event": "queued", "message": "Orden encolada; falta la respuesta de Webots"}

    def _receive(self, frame):
        if len(frame) > MAX_FRAME:
            raise ValueError("Webots envió un mensaje mayor a 16 KiB")
        event = finite_json(frame.decode("utf-8"))
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            raise ValueError("Webots envió un mensaje sin tipo de evento")
        with self.lock:
            if event["event"] == "state":
                if not isinstance(event.get("state"), dict):
                    raise ValueError("Webots envió un estado inválido")
                for key in ("estimated", "commanded", "simulated", "estimated_pose", "simulated_pose"):
                    values = event["state"].get(key)
                    if values is not None:
                        if not isinstance(values, list) or len(values) != 4:
                            raise ValueError(f"Webots envió {key} sin cuatro valores")
                        for value in values:
                            number(value, key)
                self.state = event["state"]
            else:
                self.responses.append(event)

    def _run(self):
        sock, buffer = None, b""
        while not self.closed.is_set():
            with self.lock:
                desired, generation = self.desired, self.generation
            if not desired:
                if sock is not None:
                    sock.close()
                    sock, buffer = None, b""
                self.changed.wait(0.1)
                self.changed.clear()
                continue
            try:
                if sock is None:
                    sock = socket.create_connection((self.host, self.port), timeout=0.3)
                    sock.settimeout(0.1)
                    with self.lock:
                        if not self.desired or generation != self.generation:
                            sock.close()
                            sock = None
                            continue
                        self.connected = True
                        self.state = None
                        self.message = "Conectado. Habilitá explícitamente antes de mover."
                    buffer = b""
                with self.lock:
                    if generation != self.generation or not self.connected:
                        sock.close()
                        sock, buffer = None, b""
                        continue
                while True:
                    try:
                        queued_generation, frame = self.pending.get_nowait()
                    except queue.Empty:
                        break
                    with self.lock:
                        active = (self.connected and self.desired
                                  and queued_generation == self.generation)
                    if active:
                        sock.sendall(frame)
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    continue
                if not chunk:
                    raise ConnectionError("Webots cerró la conexión")
                buffer += chunk
                while b"\n" in buffer:
                    frame, buffer = buffer.split(b"\n", 1)
                    self._receive(frame)
                if len(buffer) > MAX_FRAME:
                    raise ValueError("Webots envió un mensaje mayor a 16 KiB")
            except (OSError, ValueError, UnicodeError, RecursionError) as exc:
                if sock is not None:
                    sock.close()
                    sock, buffer = None, b""
                with self.lock:
                    self.connected = False
                    self.generation += 1
                    self._discard_pending()
                    self.message = f"Sin conexión: {exc}. Reintento automático; no se repetirán órdenes."
                self.changed.wait(self.retry_delay)
                self.changed.clear()
        if sock is not None:
            sock.close()

    def close(self):
        self.closed.set()
        self.changed.set()
        self.thread.join(timeout=2)


def handler_for(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, data, content_type="application/json; charset=utf-8"):
            body = data if isinstance(data, bytes) else json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.reply(200, Path(__file__).with_name("index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self.reply(200, bridge.snapshot())
            else:
                self.reply(404, {"error": "Ruta desconocida"})

        def do_POST(self):
            # La aplicación escucha solo en loopback. No permitir órdenes desde otra página.
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.reply(403, {"error": "Origen externo rechazado"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Se requiere application/json"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_FRAME:
                    raise ValueError("El mensaje debe ocupar entre 1 byte y 16 KiB")
                request = finite_json(self.rfile.read(size))
                if not isinstance(request, dict):
                    raise ValueError("Se requiere un objeto JSON")
                if self.path == "/api/connection":
                    bridge.connection(request.get("connect"))
                    self.reply(200, {"message": "Solicitud de conexión actualizada"})
                elif self.path == "/api/command":
                    self.reply(202, bridge.command(request))
                else:
                    self.reply(404, {"error": "Ruta desconocida"})
            except ConnectionError as exc:
                self.reply(409, {"error": str(exc)})
            except (ValueError, UnicodeError, RecursionError) as exc:
                self.reply(400, {"error": str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765, help="Puerto HTTP local")
    parser.add_argument("--webots-port", type=int, default=9000, help="Puerto TCP del controlador")
    args = parser.parse_args()
    bridge = Bridge(port=args.webots_port)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(bridge))
    print(f"Interfaz SCARA: http://127.0.0.1:{args.port}", flush=True)
    print(f"Protocolo de desarrollo {PROTOCOL}; pendiente del protocolo del profesor.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        bridge.close()


if __name__ == "__main__":
    main()
