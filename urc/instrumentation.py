"""Canal de instrumentación: lo que solo existe en la simulación (ADR 0004, D59).

El controlador de Webots se conecta a la URC en otro puerto (9001) y habla
scara-sim/1, un protocolo de texto aparte de scara/1:

    controlador → URC   SIM HELLO scara-sim/1
                        SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga   (20 por segundo)
    URC → controlador   F2 0|1 · F3 j activo|inactivo|libre · F4 0|1 · F5
                        CARGA gramos · RECARGA

J1–J4 es la posición física simulada en unidades de scara/1; f3 tiene un
carácter por articulación: "-" libre, "A" trabado activo, "I" inactivo.

Solo lo usa el banco de ensayo de la página. La sesión con la UCI, el
planificador y la validación no lo importan: capturan y planifican con la
posición estimada por pasos, como con el robot real, que no tiene este canal.
"""

from collections import deque
import select
import socket
import threading
import time


PROTOCOL = "scara-sim/1"
STUCK = {"-": "libre", "A": "activo", "I": "inactivo"}
LOAD_MAX = 5000              # gramos


class Instrumentation:
    def __init__(self, host="127.0.0.1", port=9001):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.lock = threading.Lock()
        self.client = None
        self.greeted = False
        self.state = None
        self.state_time = None
        self.rejected = deque(maxlen=10)
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="scara-sim", daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            state = dict(self.state) if self.state else {}
            return {
                "protocol": PROTOCOL,
                "connected": self.client is not None and self.greeted,
                "simulated": state.get("simulated"),
                "hall": state.get("hall"),
                "power": state.get("power"),
                "faults": state.get("faults"),
                "load_g": state.get("load_g"),
                "age_s": None if self.state_time is None else round(time.monotonic() - self.state_time, 3),
                "rejected": list(self.rejected),
            }

    def order(self, request):
        """Una orden del banco de ensayo, como la manda la página."""
        line = order_line(request)
        with self.lock:
            if self.client is None or not self.greeted:
                raise ConnectionError("No hay canal de instrumentación: solo existe en la simulación")
            try:
                self.client.sendall(line.encode() + b"\n")
            except OSError as exc:  # el controlador se fue (por ejemplo, recargando el mundo)
                raise ConnectionError(f"El canal de instrumentación se cortó: {exc}") from exc

    def close(self):
        self.closed.set()
        self.thread.join(timeout=2)
        self.listener.close()

    def _receive(self, raw):
        try:
            line = raw.decode("ascii").strip()
            fields = line.split()
            if fields == ["SIM", "HELLO", PROTOCOL]:
                self.greeted = True
                return
            if len(fields) != 11 or fields[0] != "SIM" or len(fields[8]) != 4 or any(c not in STUCK for c in fields[8]):
                raise ValueError("línea de scara-sim/1 mal formada")
            numbers = [int(value) for value in fields[1:8] + fields[9:]]
        except ValueError as exc:
            self.rejected.append(f"{raw[:64]!r}: {exc}")
            return
        self.state = {
            "simulated": numbers[0:4],
            "hall": numbers[4],
            "power": numbers[5],
            "faults": {"F2": numbers[6] == 1, "F3": [STUCK[c] for c in fields[8]], "F4": numbers[7] == 1},
            "load_g": numbers[8],
        }
        self.state_time = time.monotonic()

    def _run(self):
        buffer = b""
        while not self.closed.is_set():
            client = self.client
            readable, _, _ = select.select([self.listener] + ([client] if client else []), [], [], 0.05)
            try:
                if self.listener in readable:
                    # Una conexión nueva reemplaza a la anterior: Webots se recargó.
                    new_client, _ = self.listener.accept()
                    with self.lock:
                        if self.client is not None:
                            self.client.close()
                        self.client, self.greeted, self.state, self.state_time = new_client, False, None, None
                    buffer = b""
                    continue
                if client is not None and client in readable:
                    chunk = client.recv(4096)
                    if not chunk:
                        raise ConnectionError("cerró la conexión")
                    buffer += chunk
                    *lines, buffer = buffer.split(b"\n")
                    with self.lock:
                        for raw in lines:
                            if raw.strip():
                                self._receive(raw)
                    buffer = buffer[:256]
            except OSError:
                with self.lock:
                    if self.client is not None:
                        self.client.close()
                    self.client, self.greeted, self.state, self.state_time = None, False, None, None
                buffer = b""
        if self.client is not None:
            self.client.close()


def order_line(request):
    """Orden de scara-sim/1 para un pedido de la página; ValueError si no es válido."""
    if not isinstance(request, dict):
        raise ValueError("Se requiere un objeto JSON")
    fault = request.get("falla")
    if fault in ("F2", "F4"):
        active = request.get("activa")
        if not isinstance(active, bool):
            raise ValueError("activa tiene que ser true o false")
        return f"{fault} {int(active)}"
    if fault == "F3":
        joint, state = request.get("articulacion"), request.get("estado")
        if type(joint) is not int or not 1 <= joint <= 4 or state not in STUCK.values():
            raise ValueError("F3 lleva articulacion (1 a 4) y estado (activo, inactivo o libre)")
        return f"F3 {joint} {state}"
    if fault == "F5":
        return "F5"
    if fault is not None:
        raise ValueError("Las fallas del banco son F2, F3, F4 y F5")
    if "carga" in request:
        grams = request["carga"]
        if type(grams) is not int or not 0 <= grams <= LOAD_MAX:
            raise ValueError(f"La carga va en gramos, de 0 a {LOAD_MAX}")
        return f"CARGA {grams}"
    if request.get("recarga") is True:
        return "RECARGA"
    raise ValueError("Se espera falla, carga o recarga")
