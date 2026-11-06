"""Canal de instrumentación: lo que solo existe en la simulación (ADR 0004, D59).

El controlador de Webots se conecta a la URC en otro puerto (9001) y habla
scara-sim/1, un protocolo de texto aparte de scara/1:

    controlador → URC   SIM HELLO scara-sim/1
                        SIM J1 J2 J3 J4 hall corriente f2 f3 f4 carga i1 i2 i3 i4 p1 p2 p3 p4
                        (20 por segundo)
    URC → controlador   F1 m porcentaje · F2 0|1 · F3 j activo|inactivo|libre
                        F4 0|1 · F5 · CARGA gramos · RECARGA
                        OBSTACULO maceta X Y | OBSTACULO mesa X Y altura | OBSTACULO ninguno
                        EMPUJON fuerza_cN direccion_grados duracion_ms
                        MANO articulacion posicion
    controlador → URC   SIM OBSTACULO tipo X Y altura
                        SIM CONTACTO tipo cuerpo e1 e2 e3 e4 p1 p2 p3 p4 l1 l2 l3 l4
                        SIM EMPUJON fuerza_cN direccion_grados duracion_ms
                        SIM MANO j posicion (aplicada) · SIM ERR motivo (rechazada)

X, Y y altura van en mm. e, p y l son esfuerzo actual, pico y límite
provisional de J1–J4 (N·m en J1–J3; N en J4), respectivamente.

J1–J4 es la posición física simulada en unidades de scara/1; f3 tiene un
carácter por articulación: "-" libre, "A" trabado activo, "I" inactivo.
La carga es la que se agrega a la herramienta, sin el pistón ni su soporte
(150 g): 0 g es la herramienta sola (D85). i1–i4 es la corriente de cada
driver en % de la nominal (F1: con menos, el motor tiene menos par) y p1–p4,
los pasos completos que perdió cada motor desde el último homing de su eje o
desde que recuperó la corriente (D64, D67, D86).
MANO usa las mismas centésimas y límites de las articulaciones; solo coloca
la posición física con todos los drivers sin corriente. La estimada sigue
igual y ENABLE no recupera la referencia perdida con DISABLE (D40).

Solo lo usa el banco de ensayo de la página. La sesión con la UCI, el
planificador y la validación no lo importan: capturan y planifican con la
posición estimada por pasos, como con el robot real, que no tiene este canal.

Cada orden que cambia el estado (carga, F1–F4) espera su confirmación: el
simulador la aplicó cuando el estado SIM la muestra. El registro de eventos
anota lo que cambió y avisa si una orden no se aplicó en CONFIRM (D79).
"""

from collections import deque
import math
import select
import socket
import threading
import time

from urc.events import EventLog
from scara.kinematics import load_config


PROTOCOL = "scara-sim/1"
STUCK = {"-": "libre", "A": "activo", "I": "inactivo"}
# Gramos de carga: con los 150 g del pistón y su soporte, los 5 kg con los que
# se verificaron los límites de los motores (D76, D85).
LOAD_MAX = 4850
CURRENT_MIN = 10             # % de la corriente nominal de un driver (F1)
FIELDS = 19
CONFIRM = 2.0                # s para que el estado SIM muestre una orden aplicada
MANUAL_LIMITS = [tuple(round(q * (18000 / math.pi if j < 3 else 100000)) for q in bounds)
                 for j, bounds in enumerate(load_config()["limits"])]


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
        self.experiment = {}
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
                **self.experiment,
                "protocol": PROTOCOL,
                "connected": self.client is not None and self.greeted,
                "simulated": state.get("simulated"),
                "hall": state.get("hall"),
                "power": state.get("power"),
                "faults": state.get("faults"),
                "load_g": state.get("load_g"),
                "load_max": LOAD_MAX,        # el tope del campo de la página sale de acá
                "current_pct": state.get("current_pct"),
                "lost_steps": state.get("lost_steps"),
                "manual_limits": MANUAL_LIMITS,
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
            if line.startswith("MANO ") and (self.state is None or self.state["power"] != 0):
                raise ValueError("Mover a mano requiere todos los drivers sin corriente: usá DISABLE")
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
                if key in ("mano", "empujon"):
                    self.events.add("aviso", "Banco", f"Sin confirmación de {_name(key)}: {_value(key, value)}")
                    continue
                current = "sin estado" if self.state is None else _value(key, _values(self.state).get(key, self.experiment.get("obstacle")))
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
            if len(fields) == 4 and fields[:2] == ["SIM", "MANO"]:
                joint, value = int(fields[2]), int(fields[3])
                if not 1 <= joint <= 4 or not MANUAL_LIMITS[joint - 1][0] <= value <= MANUAL_LIMITS[joint - 1][1]:
                    raise ValueError("confirmación MANO inválida")
                wanted = self.pending.get("mano")
                if wanted is not None and wanted[0] == (joint, value):
                    del self.pending["mano"]
                self.events.add("ok", "Banco", describe(f"MANO {joint} {value}"))
                return
            if len(fields) == 5 and fields[:2] == ["SIM", "EMPUJON"]:
                force_cn, direction, duration_ms = int(fields[2]), int(fields[3]), int(fields[4])
                if not 1 <= force_cn <= 5000 or not -180 <= direction <= 180 or not 50 <= duration_ms <= 2000:
                    raise ValueError("confirmación EMPUJON inválida")
                wanted = self.pending.get("empujon")
                if wanted is not None and wanted[0] == (force_cn, direction, duration_ms):
                    del self.pending["empujon"]
                self.experiment["push"] = {"fuerza_n": round(force_cn / 100, 2), "direccion": direction,
                                           "duracion_ms": duration_ms}
                self.events.add("ok", "Banco", describe(f"EMPUJON {force_cn} {direction} {duration_ms}"))
                return
            if fields[:2] == ["SIM", "ERR"]:
                self.rejected.append(line)
                self.events.add("aviso", "Banco", f"Orden rechazada por el simulador: {' '.join(fields[2:])}")
                return
            if fields[:2] == ["SIM", "OBSTACULO"] and len(fields) == 6:
                kind = fields[2]
                if kind not in ("ninguno", "maceta", "mesa"):
                    raise ValueError("obstáculo desconocido")
                values = [int(v) for v in fields[3:]]
                obstacle = {"tipo": kind, "x": values[0], "y": values[1], "altura": values[2]}
                self.experiment["obstacle"] = obstacle
                if "obstaculo" in self.pending and self.pending["obstaculo"][0] == obstacle:
                    del self.pending["obstaculo"]
                    self.events.add("ok", "Banco", f"Obstáculo de ensayo: {_value('obstaculo', obstacle)}")
                return
            if fields[:2] == ["SIM", "CONTACTO"] and len(fields) == 16:
                values = [float(v) for v in fields[4:]]
                if (fields[2] not in ("ninguno", "maceta", "mesa")
                        or fields[3] not in ("ninguno", "ARM", "FOREARM", "WRIST", "TOOL")
                        or not all(math.isfinite(v) for v in values)
                        or any(v < 0 for v in values[4:8]) or any(v <= 0 for v in values[8:])):
                    raise ValueError("contacto o esfuerzo inválido")
                contact = fields[3] != "ninguno"
                if contact and self.experiment.get("contact") != fields[3]:
                    self.events.add("aviso", "Banco", f"Contacto: {fields[3]} con {fields[2]} (solo instrumentación)")
                self.experiment.update(contact=fields[3] if contact else None,
                                       effort=values[:4], peak_effort=values[4:8], effort_limit=values[8:])
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
                        self.experiment.clear()
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
    if "obstaculo" in request:
        obstacle = request["obstaculo"]
        if not isinstance(obstacle, dict) or obstacle.get("tipo") not in ("ninguno", "maceta", "mesa"):
            raise ValueError("obstaculo lleva tipo ninguno, maceta o mesa")
        if obstacle["tipo"] == "ninguno":
            return "OBSTACULO ninguno"
        x, y = obstacle.get("x"), obstacle.get("y")
        if any(type(v) is not int or not -1000 <= v <= 1000 for v in (x, y)):
            raise ValueError("X e Y van en mm enteros de −1000 a 1000")
        if obstacle["tipo"] == "maceta":
            return f"OBSTACULO maceta {x} {y}"
        height = obstacle.get("altura")
        if type(height) is not int or not -20 <= height <= 90:
            raise ValueError("La altura de la mesa va en mm enteros de −20 a 90")
        return f"OBSTACULO mesa {x} {y} {height}"
    if "empujon" in request:
        push = request["empujon"]
        if not isinstance(push, dict):
            raise ValueError("empujon requiere fuerza_n y direccion")
        force = push.get("fuerza_n")
        direction = push.get("direccion")
        duration = push.get("duracion_ms", 500)
        if isinstance(force, bool) or not isinstance(force, (int, float)) or not math.isfinite(force):
            raise ValueError("La fuerza del empujón tiene que ser un número")
        force_cn = round(float(force) * 100)
        if not 1 <= force_cn <= 5000:
            raise ValueError("La fuerza del empujón va de 0.01 a 50 N")
        if type(direction) is not int or not -180 <= direction <= 180:
            raise ValueError("La dirección del empujón va en grados enteros de −180 a 180")
        if type(duration) is not int or not 50 <= duration <= 2000:
            raise ValueError("La duración del empujón va en ms enteros de 50 a 2000")
        return f"EMPUJON {force_cn} {direction} {duration}"
    if "mano" in request:
        move = request["mano"]
        if not isinstance(move, dict):
            raise ValueError("mano requiere articulacion y posicion")
        joint, value = move.get("articulacion"), move.get("posicion")
        if type(joint) is not int or not 1 <= joint <= 4 or type(value) is not int:
            raise ValueError("Mover a mano lleva articulacion (1 a 4) y posicion en centésimas")
        low, high = MANUAL_LIMITS[joint - 1]
        if not low <= value <= high:
            raise ValueError(f"La posición de J{joint} va de {low} a {high} centésimas")
        return f"MANO {joint} {value}"
    raise ValueError("Se espera falla, carga, recarga, obstaculo, empujon o mano")


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
    return {"mano": "Mover a mano", "empujon": "Empujón", "obstaculo": "Obstáculo de ensayo",
            "carga": "Carga en la herramienta", "F1": f"F1 · corriente del driver de M{index}",
            "F2": "F2 · driver de M4 sin corriente", "F3": f"F3 · Hall de J{index}",
            "F4": "F4 · enlace scara/1 cortado"}[kind]


def _value(key, value):
    kind = key.split()[0]
    if kind == "mano":
        joint, position = value
        return f"J{joint} a {position / 100:g} {'mm' if joint == 4 else '°'}"
    if kind == "empujon":
        force_cn, direction, duration_ms = value
        return f"{force_cn / 100:g} N a {direction}° durante {duration_ms / 1000:g} s"
    if kind == "obstaculo":
        if not isinstance(value, dict) or value.get("tipo") == "ninguno":
            return "ninguno"
        extra = f", altura {value['altura']} mm" if value.get("tipo") == "mesa" else ""
        return f"{value['tipo']}, X {value['x']} mm, Y {value['y']} mm{extra}"
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
    if words[0] == "MANO":
        return "mano", (int(words[1]), int(words[2]))
    if words[0] == "EMPUJON":
        return "empujon", (int(words[1]), int(words[2]), int(words[3]))
    if words[0] == "OBSTACULO":
        kind = words[1]
        height = 150 if kind == "maceta" else int(words[4]) if kind == "mesa" else 0
        return "obstaculo", {"tipo": kind, "x": int(words[2]) if len(words) > 2 else 0,
                             "y": int(words[3]) if len(words) > 3 else 0,
                             "altura": height}
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
    if line.startswith("MANO "):
        _, joint, value = line.split()
        return f"Movido a mano: J{joint} a {int(value) / 100:g} {'mm' if joint == '4' else '°'} (sin corriente)"
    if line.startswith("EMPUJON "):
        _, force_cn, direction, duration_ms = line.split()
        return f"Empujón: {int(force_cn) / 100:g} N a {int(direction)}° durante {int(duration_ms) / 1000:g} s"
    expected = _expected(line)
    if expected is not None:
        return f"{_name(expected[0])}: {_value(*expected)}"
    return {"F5": "F5 · reiniciar la UCI", "RECARGA": "Recargar el mundo"}[line]
