"""Canal de instrumentación: lo que solo existe en la simulación (ADR 0004, D59).

El controlador de Webots se conecta a la URC en otro puerto (9001) y habla
scara-sim/1, un protocolo de texto aparte de scara/1:

    controlador → URC   SIM HELLO scara-sim/1
                        SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga i1 i2 i3 i4 p1 p2 p3 p4
                        (20 por segundo)
    URC → controlador   F1 m porcentaje · F2 0|1 · F3 j activo|inactivo|libre
                        F4 0|1 · F5 · CARGA gramos · RECARGA

J1–J4 es la posición física simulada en unidades de scara/1; f3 tiene un
carácter por articulación: "-" libre, "A" trabado activo, "I" inactivo.
i1–i4 es la corriente de cada driver en % de la nominal (F1: con menos, el
motor tiene menos par) y p1–p4, los pasos completos que perdió cada motor
(D64, D67).

Solo lo usa el banco de ensayo de la página. La sesión con la UCI, el
planificador y la validación no lo importan: capturan y planifican con la
posición estimada por pasos, como con el robot real, que no tiene este canal.

Cada orden que cambia el estado (carga, F1–F4) espera su confirmación: el
simulador la aplicó cuando el estado SIM la muestra. El registro de eventos
anota lo que cambió y avisa si una orden no se aplicó en CONFIRM (D79).
"""

from collections import deque
import select
import socket
import threading
import time

from urc.events import EventLog


PROTOCOL = "scara-sim/1"
STUCK = {"-": "libre", "A": "activo", "I": "inactivo"}
LOAD_MAX = 5000              # gramos
CURRENT_MIN = 10             # % de la corriente nominal de un driver (F1)
FIELDS = 19
CONFIRM = 2.0                # s para que el estado SIM muestre una orden aplicada


class Instrumentation:
    def __init__(self, host="127.0.0.1", port=9001, events=None):
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
        # La URC le pasa el registro de la sesión: el banco anota en el mismo.
        self.events = events if events is not None else EventLog()
        self.pending = {}            # orden sin confirmar: clave → (valor pedido, hasta cuándo)
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
                "current_pct": state.get("current_pct"),
                "lost_steps": state.get("lost_steps"),
                "age_s": None if self.state_time is None else round(time.monotonic() - self.state_time, 3),
                "rejected": list(self.rejected),
                "pending": [{"key": key, "value": value} for key, (value, _) in self.pending.items()],
            }

    def order(self, request):
        """Una orden del banco de ensayo, como la manda la página; devuelve cómo se lee."""
        line = order_line(request)
        with self.lock:
            if self.client is None or not self.greeted:
                raise ConnectionError("No hay canal de instrumentación: solo existe en la simulación")
            try:
                self.client.sendall(line.encode() + b"\n")
            except OSError as exc:  # el controlador se fue (por ejemplo, recargando el mundo)
                raise ConnectionError(f"El canal de instrumentación se cortó: {exc}") from exc
            expected = _expected(line)
            if expected is not None:
                self.pending[expected[0]] = (expected[1], time.monotonic() + CONFIRM)
        return describe(line)

    def _confirm(self, previous):
        """Anota lo que cambió en el simulador y las órdenes que ya rigen (con el lock tomado)."""
        after = _values(self.state)
        if previous is None:
            faults = [f"{_name(key)} {_value(key, value)}" for key, value in after.items()
                      if key in NOMINAL and value != NOMINAL[key]]
            self.events.add("info", "Banco", f"Canal de instrumentación conectado: carga {after['carga']} g, "
                            + ("fallas: " + "; ".join(faults) if faults else "sin fallas"))
        before = _values(previous) if previous is not None else after
        for key, value in after.items():
            wanted = self.pending.get(key)
            applied = wanted is not None and wanted[0] == value
            if value != before[key]:
                self.events.add("ok" if applied else "info", "Banco",
                                f"{_name(key)}: {_value(key, before[key])} → {_value(key, value)}")
            elif applied:
                self.events.add("ok", "Banco", f"{_name(key)}: {_value(key, value)}, ya regía")
            if applied:
                del self.pending[key]

    def _expire(self):
        """Las órdenes que el simulador no aplicó a tiempo (con el lock tomado)."""
        now = time.monotonic()
        for key, (value, deadline) in list(self.pending.items()):
            if now > deadline:
                del self.pending[key]
                current = "sin estado" if self.state is None else _value(key, _values(self.state)[key])
                self.events.add("aviso", "Banco", f"No se aplicó {_name(key)}: se pidió {_value(key, value)} "
                                f"y el simulador sigue en {current}")

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
            if (len(fields) != FIELDS or fields[0] != "SIM" or len(fields[8]) != 4
                    or any(c not in STUCK for c in fields[8])):
                raise ValueError("línea de scara-sim/1 mal formada")
            numbers = [int(value) for value in fields[1:8] + fields[9:]]
        except ValueError as exc:
            self.rejected.append(f"{raw[:64]!r}: {exc}")
            return
        previous, self.state = self.state, {
            "simulated": numbers[0:4],
            "hall": numbers[4],
            "power": numbers[5],
            "faults": {"F2": numbers[6] == 1, "F3": [STUCK[c] for c in fields[8]], "F4": numbers[7] == 1},
            "load_g": numbers[8],
            "current_pct": numbers[9:13],
            "lost_steps": numbers[13:17],
        }
        self.state_time = time.monotonic()
        self._confirm(previous)

    def _run(self):
        buffer = b""
        while not self.closed.is_set():
            client = self.client
            readable, _, _ = select.select([self.listener] + ([client] if client else []), [], [], 0.05)
            with self.lock:
                self._expire()
            try:
                if self.listener in readable:
                    # Una conexión nueva reemplaza a la anterior: Webots se recargó.
                    new_client, _ = self.listener.accept()
                    with self.lock:
                        if self.client is not None:
                            self.client.close()
                        self.client, self.greeted, self.state, self.state_time = new_client, False, None, None
                        self.pending.clear()
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
                        if self.greeted:
                            self.events.add("aviso", "Banco", "Canal de instrumentación desconectado")
                    self.client, self.greeted, self.state, self.state_time = None, False, None, None
                    self.pending.clear()
                buffer = b""
        if self.client is not None:
            self.client.close()


def order_line(request):
    """Orden de scara-sim/1 para un pedido de la página; ValueError si no es válido."""
    if not isinstance(request, dict):
        raise ValueError("Se requiere un objeto JSON")
    fault = request.get("falla")
    if fault == "F1":
        motor, current = request.get("motor"), request.get("corriente")
        if type(motor) is not int or not 1 <= motor <= 4 or type(current) is not int or not CURRENT_MIN <= current <= 100:
            raise ValueError(f"F1 lleva motor (1 a 4) y corriente ({CURRENT_MIN} a 100 % de la nominal)")
        return f"F1 {motor} {current}"
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
        raise ValueError("Las fallas del banco son F1, F2, F3, F4 y F5")
    if "carga" in request:
        grams = request["carga"]
        if type(grams) is not int or not 0 <= grams <= LOAD_MAX:
            raise ValueError(f"La carga va en gramos, de 0 a {LOAD_MAX}")
        return f"CARGA {grams}"
    if request.get("recarga") is True:
        return "RECARGA"
    raise ValueError("Se espera falla, carga o recarga")


# Lo que el banco puede confirmar, por clave: la carga, la corriente de cada
# driver (F1 1…F1 4), F2, el Hall de cada articulación (F3 1…F3 4) y F4.
NOMINAL = {**{f"F1 {m}": 100 for m in range(1, 5)}, "F2": False,
           **{f"F3 {j}": "libre" for j in range(1, 5)}, "F4": False}


def _values(state):
    values = {"carga": state["load_g"]}
    values.update({f"F1 {m}": current for m, current in enumerate(state["current_pct"], 1)})
    values["F2"] = state["faults"]["F2"]
    values.update({f"F3 {j}": stuck for j, stuck in enumerate(state["faults"]["F3"], 1)})
    values["F4"] = state["faults"]["F4"]
    return values


def _name(key):
    kind, _, index = key.partition(" ")
    return {"carga": "Carga en la herramienta", "F1": f"F1 · corriente del driver de M{index}",
            "F2": "F2 · driver de M4 sin corriente", "F3": f"F3 · Hall de J{index}",
            "F4": "F4 · enlace scara/1 cortado"}[kind]


def _value(key, value):
    kind = key.split()[0]
    if kind == "carga":
        return f"{value} g"
    if kind == "F1":
        return f"{value} %"
    if kind == "F3":
        return value if value == "libre" else f"trabado {value}"
    return "activa" if value else "inactiva"


def _expected(line):
    """(clave, valor) que el estado SIM tiene que mostrar después de la orden; None si no hay qué confirmar."""
    words = line.split()
    if words[0] == "F1":
        return f"F1 {words[1]}", int(words[2])
    if words[0] in ("F2", "F4"):
        return words[0], words[1] == "1"
    if words[0] == "F3":
        return f"F3 {words[1]}", words[2]
    if words[0] == "CARGA":
        return "carga", int(words[1])
    return None


def describe(line):
    """Una orden de scara-sim/1 como la lee el operador, para el registro de eventos."""
    expected = _expected(line)
    if expected is not None:
        return f"{_name(expected[0])}: {_value(*expected)}"
    return {"F5": "F5 · reiniciar la UCI", "RECARGA": "Recargar el mundo"}[line]
