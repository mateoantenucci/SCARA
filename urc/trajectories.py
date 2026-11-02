"""Gestor de trayectorias de la URC (D13, D22, D29, D34).

La URC guarda la trayectoria que se está editando: la página solo la
muestra y pide cambios por HTTP (urc/app.py delega acá las rutas
/api/trayectoria*). Cada punto de trayectoria es una configuración articular
en las unidades de scara/1 (ADR 0003), que incluye la configuración del codo,
más cómo se llega a él: tipo de tramo, velocidad y espera.

Cada trayectoria es un archivo JSON con versión de formato y unidades. Todo
punto se valida al capturarlo, escribirlo, editarlo y cargarlo: límites
articulares, alcance (si se escribió en XYZ) y choque en reposo. La
validación de los tramos, que depende del orden y del tipo, es de la
reproducción (#13, D55).
"""

import datetime
import json
import math
import os
import re
import threading
import unicodedata
from pathlib import Path

from urc import planner


FORMAT, VERSION = "scara-trayectoria", 1
UNITS = {
    "joints": "centésimas de grado (J1–J3) y de mm (J4)",
    "tool": "mm (x, y, z) y grados (rumbo)",
    "speed": "% de la velocidad máxima",
    "wait": "s",
}
KINDS = ("LIN", "PTP")
DEFAULTS = {"kind": "LIN", "speed": 50, "wait": 0}   # D22
MAX_WAIT = 600               # s
GO_SPEED = 0.25              # «Ir al punto»: como el tramo de aproximación (D33)
STATUS_AGE = 1.0             # s: un estado S más viejo no sirve para capturar (llega 20/s)
NAME_MAX = 60
FILE_MAX = 1024 * 1024       # bytes
FILE_PATTERN = re.compile(r"[A-Za-z0-9_-]+\.json")
# Nombres de dispositivo de Windows: no pueden ser archivos.
RESERVED = re.compile(r"(con|prn|aux|nul|com[0-9]|lpt[0-9])")
POINT_KEYS = {"joints", "tool", "kind", "speed", "wait"}
REQUIRED_KEYS = {"format", "version", "name", "units", "points"}
DEFAULT_FOLDER = Path(__file__).resolve().parents[1] / "trayectorias"


class Conflict(Exception):
    """El pedido descartaría trabajo: hay que confirmarlo (HTTP 409)."""


class TrajectoryManager:
    def __init__(self, session, folder=DEFAULT_FOLDER):
        self.session = session
        self.folder = Path(folder)
        self.config, self.checker = session.config, session.checker
        self.lock = threading.Lock()
        self._reset()

    def _reset(self, name=None, file=None, points=()):
        self.name, self.file = name, file
        self.points = list(points)
        self.dirty = False
        self.selected = None     # el último punto agregado o cambiado; la página lo resalta

    # --- Consultas ---------------------------------------------------------

    def state(self):
        with self.lock:
            return self._state()

    def files(self):
        if not self.folder.is_dir():
            return {"files": []}
        return {"files": sorted(p.name for p in self.folder.iterdir()
                                if p.is_file() and FILE_PATTERN.fullmatch(p.name))}

    def _describe(self, point):
        joints = point["joints"]
        return {"joints": list(joints), "tool": self._tool(joints), "elbow": (joints[1] > 0) - (joints[1] < 0),
                "kind": point["kind"], "speed": point["speed"], "wait": point["wait"]}

    def _tool(self, joints):
        """XYZ (mm) y rumbo (°, J1 + J2 + J3 sin envolver), derivados de las articulaciones."""
        x, y, z = (round(v * 1000, 2) for v in planner.tool_point(joints, self.config))
        return {"x": x, "y": y, "z": z, "heading": round(sum(joints[:3]) / 100, 2)}

    # --- Edición -------------------------------------------------------------

    def capture(self, request):
        """Espacio: la posición estimada por pasos, después de `after` (D21, D29)."""
        joints = self._robot_pose()
        with self.lock:
            index = self._after(request)
            self.points.insert(index, dict(DEFAULTS, joints=self._check_point(joints, index + 1)))
            return self._changed(index)

    def add(self, request):
        """Punto escrito a mano: J1–J4 o XYZ y rumbo, con el codo preferido o el pedido (D34)."""
        with self.lock:
            index = self._after(request)
            if "pose" in request:
                pose = request["pose"]
                if not isinstance(pose, dict):
                    raise ValueError("pose: se esperan X, Y, Z, rumbo y codo")
                # J1 y J3 dan la vuelta más cercana al punto anterior.
                near = self.points[index - 1]["joints"] if index else None
                joints = self._from_pose(pose, pose.get("elbow", -1), near, index + 1)
            elif "joints" in request:
                joints = _joints(request["joints"])
            else:
                raise ValueError("Se espera joints (J1–J4) o pose (X, Y, Z y rumbo)")
            self.points.insert(index, dict(DEFAULTS, joints=self._check_point(joints, index + 1)))
            return self._changed(index)

    def edit(self, request):
        """Cambia la pose o cómo se llega al punto; al escribir XYZ conserva su codo (D34)."""
        with self.lock:
            index = self._index(request.get("index"))
            point = dict(self.points[index])
            fields = {"joints", "pose", "kind", "speed", "wait"} & request.keys()
            if not fields:
                raise ValueError("Nada para editar: se espera joints, pose, kind, speed o wait")
            if {"joints", "pose"} <= fields:
                raise ValueError("Se espera joints o pose, no los dos")
            if "pose" in request:
                pose = request["pose"]
                if not isinstance(pose, dict) or "elbow" in pose:
                    raise ValueError("pose: se esperan X, Y, Z y rumbo; el punto conserva su codo "
                                     "(para cambiarlo, editá J1–J4)")
                elbow = 1 if point["joints"][1] > 0 else -1
                point["joints"] = self._from_pose(pose, elbow, point["joints"], index + 1)
            elif "joints" in request:
                point["joints"] = _joints(request["joints"])
            point.update(_tramo({key: request[key] for key in ("kind", "speed", "wait") if key in request}))
            point["joints"] = self._check_point(point["joints"], index + 1)
            self.points[index] = point
            return self._changed(index)

    def overwrite(self, request):
        """Sobrescribe la pose de un punto con la actual; cómo se llega a él no cambia."""
        joints = self._robot_pose()
        with self.lock:
            index = self._index(request.get("index"))
            self.points[index] = dict(self.points[index], joints=self._check_point(joints, index + 1))
            return self._changed(index)

    def delete(self, request):
        """Retroceso borra el seleccionado, que después de capturar es el último capturado."""
        with self.lock:
            index = self._index(request.get("index"))
            del self.points[index]
            return self._changed(max(index - 1, 0) if self.points else None)

    def move(self, request):
        with self.lock:
            index = self._index(request.get("index"))
            target = self._index(request.get("to"), "to")
            self.points.insert(target, self.points.pop(index))
            return self._changed(target)

    def go(self, request):
        """«Ir al punto»: PTP desde la pose actual; sin confirm solo planifica (D29).

        La confirmación trae el destino que vio el operador: si el punto cambió
        mientras tanto, no se mueve.
        """
        with self.lock:
            index = self._index(request.get("index"))
            joints = self.points[index]["joints"]
        confirm = request.get("confirm", False) is True
        if confirm and request.get("target") != list(joints):
            raise ValueError("El punto cambió desde que se planificó: volvé a pedir «Ir al punto»")
        return (202 if confirm else 200), self.session.move_ptp(joints, GO_SPEED, dry_run=not confirm,
                                                                name=f"punto {index + 1}")

    # --- Archivo -------------------------------------------------------------

    def new(self, request):
        with self.lock:
            self._keep_unsaved(request)
            self._reset()
        return self.state()

    def save(self, request):
        """Sin name guarda en su archivo; con name es «Guardar como» (Enter pide el nombre)."""
        with self.lock:
            if not self.points:
                raise ValueError("La trayectoria no tiene puntos: capturá o agregá alguno antes de guardar")
            if request.get("name") is None:
                if self.file is None:
                    raise ValueError("La trayectoria todavía no tiene nombre: usá «Guardar como»")
                name, file = self.name, self.file
            else:
                name = _name(request["name"])
                file = _file_for(name)
                if file != self.file and (self.folder / file).exists() and request.get("overwrite") is not True:
                    raise Conflict(f"Ya existe {file}: ¿reemplazarlo?")
            document = {"format": FORMAT, "version": VERSION, "name": name,
                        "saved": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                        "units": UNITS,
                        "points": [{key: value for key, value in self._describe(point).items() if key != "elbow"}
                                   for point in self.points]}
            self._write(file, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
            self.name, self.file, self.dirty = name, file, False
        return self.state()

    def load(self, request):
        """Carga un archivo de la carpeta; si algo falla, dice qué punto y por qué (D34)."""
        file = request.get("file")
        if not isinstance(file, str) or not FILE_PATTERN.fullmatch(file):
            raise ValueError("Se espera el nombre de un archivo .json de la carpeta de trayectorias")
        path = self.folder / file
        if not path.is_file():
            raise ValueError(f"No existe {file} en la carpeta de trayectorias")
        if path.stat().st_size > FILE_MAX:
            raise ValueError(f"{file} es demasiado grande para ser una trayectoria")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{file} no es JSON válido: {exc}") from exc
        try:
            name, points = self._parse(document)
        except ValueError as exc:
            raise ValueError(f"{file}: {exc}") from exc
        with self.lock:
            self._keep_unsaved(request)
            self._reset(name, file, points)
        return self.state()

    def _parse(self, document):
        if not isinstance(document, dict):
            raise ValueError("no es un objeto JSON")
        if document.get("format") != FORMAT:
            raise ValueError(f"formato desconocido: se espera «{FORMAT}»")
        if document.get("version") != VERSION:
            raise ValueError(f"versión {document.get('version')} del formato no soportada; esta URC lee la {VERSION}")
        _keys(document, REQUIRED_KEYS, REQUIRED_KEYS | {"saved"})
        if document["units"] != UNITS:
            raise ValueError(f"unidades distintas de las de la URC: se esperan {UNITS}")
        try:
            name = _name(document["name"])
        except ValueError as exc:
            raise ValueError(f"nombre inválido: {exc}") from exc
        points = document["points"]
        if not isinstance(points, list) or not points:
            raise ValueError("la trayectoria no tiene puntos")
        return name, [self._parse_point(point, number) for number, point in enumerate(points, 1)]

    def _parse_point(self, point, number):
        try:
            if not isinstance(point, dict):
                raise ValueError("no es un objeto")
            _keys(point, POINT_KEYS - {"tool"}, POINT_KEYS)
            joints = planner.check_units(point["joints"], "J1–J4")
            parsed = dict(_tramo({key: point[key] for key in ("kind", "speed", "wait")}), joints=joints)
        except ValueError as exc:
            raise ValueError(f"Punto {number}: {exc}") from exc
        self._check_point(joints, number)
        # Mandan las articulaciones (D13); los XYZ son para leer, y no se aceptan si no coinciden.
        if "tool" in point and not _same_tool(point["tool"], self._tool(joints)):
            raise ValueError(f"Punto {number}: X, Y, Z y rumbo no coinciden con J1–J4, que son los que valen; "
                             "corregilos o borralos")
        return parsed

    # --- Ayudas (con self.lock tomado) ---------------------------------------

    def _robot_pose(self):
        return robot_pose(self.session.snapshot(), "capturar")

    def _check_point(self, joints, number):
        """Límites articulares y choque en reposo (D34)."""
        problem = planner.out_of_range(joints, self.config)
        if problem:
            raise ValueError(f"Punto {number}: {problem}")
        pose = planner.units_to_si(joints)
        conflict = self.checker.first_conflict(pose, pose)
        if conflict:
            raise ValueError(f"Punto {number}: colisión en reposo, {conflict['instance']} puede tocar "
                             f"{conflict['obstacle']} (envolventes y margen de {self.checker.margin * 1000:g} mm)")
        return tuple(joints)

    def _from_pose(self, pose, elbow, near, number):
        values = [pose.get(key) for key in ("x", "y", "z", "heading")]
        if isinstance(elbow, bool) or elbow not in (-1, 1):
            raise ValueError("El codo debe ser -1 (J2 negativo) o 1 (J2 positivo)")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError("X, Y, Z y rumbo tienen que ser números")
        try:
            return planner.joints_from_pose(*values, elbow=elbow, config=self.config, current=near)
        except ValueError as exc:
            raise ValueError(f"Punto {number}: fuera de alcance o de los límites: {exc}") from exc

    def _after(self, request):
        """Dónde se inserta: después del punto `after` (−1: al principio; sin after: al final)."""
        after = request.get("after", len(self.points) - 1)
        if type(after) is not int or not -1 <= after < len(self.points):
            raise ValueError(f"after tiene que ser un punto de la trayectoria (0 a {len(self.points) - 1}) o -1")
        return after + 1

    def _index(self, value, name="index"):
        if type(value) is not int or not 0 <= value < len(self.points):
            raise ValueError(f"{name} tiene que ser un punto de la trayectoria (hay {len(self.points)})")
        return value

    def _state(self):
        return {"name": self.name, "file": self.file, "dirty": self.dirty, "selected": self.selected,
                "points": [self._describe(point) for point in self.points]}

    def _changed(self, selected):
        self.dirty, self.selected = True, selected
        return self._state()

    def _keep_unsaved(self, request):
        if self.dirty and request.get("discard") is not True:
            raise Conflict("Hay cambios sin guardar en la trayectoria: ¿descartarlos?")

    def _write(self, file, text):
        """Escribe completo o nada: un corte a mitad no deja un archivo roto."""
        self.folder.mkdir(parents=True, exist_ok=True)
        temporary = self.folder / f".{file}.tmp"
        try:
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, self.folder / file)
        finally:
            temporary.unlink(missing_ok=True)


def robot_pose(state, action):
    """La posición estimada por pasos de un snapshot de la sesión, con el robot referenciado y quieto.

    action dice para qué se pide («capturar», «reproducir»), para el mensaje.
    """
    if not state["connected"]:
        raise ConnectionError("No hay una UCI conectada")
    status = state["status"]
    if status is None or not state["referenced"]:
        raise ValueError(f"Para {action}, el robot tiene que estar referenciado (homing o referencia manual)")
    tramo, segments = state["tramo"], state["segments"]
    running = (segments["pending"] or segments["in_flight"] is not None
               or (tramo is not None and tramo["cancelled"] is None and tramo["done"] < tramo["segments"]))
    if status["mode"] != "IDLE" or state["jog"] is not None or running:
        raise ValueError(f"El robot se está moviendo: para {action}, esperá a que quede quieto")
    if status["age_s"] > STATUS_AGE:
        raise ValueError(f"El último estado de la UCI tiene {status['age_s']:.1f} s: la posición no está al día")
    return tuple(status["position"])


def _joints(values):
    """J1–J3 en grados y J4 en mm, como los escribe el operador → centésimas."""
    if not isinstance(values, list) or len(values) != 4:
        raise ValueError("Se esperan J1–J4")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e6
           for v in values):
        raise ValueError("J1–J4 tienen que ser números")
    return planner.check_units([round(v * 100) for v in values], "J1–J4")


def _tramo(fields):
    """Tipo, velocidad (% entero) y espera (s) de cómo se llega al punto (D22)."""
    if "kind" in fields and fields["kind"] not in KINDS:
        raise ValueError("El tipo de tramo es LIN o PTP")
    if "speed" in fields and (type(fields["speed"]) is not int or not 1 <= fields["speed"] <= 100):
        raise ValueError("La velocidad es un porcentaje entero de 1 a 100")
    wait = fields.get("wait")
    if "wait" in fields and (isinstance(wait, bool) or not isinstance(wait, (int, float)) or not 0 <= wait <= MAX_WAIT):
        raise ValueError(f"La espera va de 0 a {MAX_WAIT} s")
    return fields


def _keys(document, required, allowed):
    for key in document:
        if key not in allowed:
            raise ValueError(f"clave desconocida «{key}»")
    for key in sorted(required):
        if key not in document:
            raise ValueError(f"falta «{key}»")


def _same_tool(written, derived):
    return (isinstance(written, dict) and written.keys() == derived.keys()
            and all(isinstance(written[k], (int, float)) and not isinstance(written[k], bool)
                    and abs(written[k] - derived[k]) <= 0.01 for k in derived))


def _name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("La trayectoria necesita un nombre")
    name = name.strip()
    if len(name) > NAME_MAX:
        raise ValueError(f"El nombre puede tener hasta {NAME_MAX} caracteres")
    if not _slug(name):
        raise ValueError("El nombre necesita alguna letra o número")
    if RESERVED.fullmatch(_slug(name)):
        raise ValueError(f"«{name}» es un nombre reservado de Windows: elegí otro")
    return name


def _slug(name):
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _file_for(name):
    return _slug(name) + ".json"


ROUTES = {
    "/api/trayectoria/capturar": TrajectoryManager.capture,
    "/api/trayectoria/punto": TrajectoryManager.add,
    "/api/trayectoria/editar": TrajectoryManager.edit,
    "/api/trayectoria/sobrescribir": TrajectoryManager.overwrite,
    "/api/trayectoria/borrar": TrajectoryManager.delete,
    "/api/trayectoria/mover": TrajectoryManager.move,
    "/api/trayectoria/ir": TrajectoryManager.go,
    "/api/trayectoria/nueva": TrajectoryManager.new,
    "/api/trayectoria/guardar": TrajectoryManager.save,
    "/api/trayectoria/cargar": TrajectoryManager.load,
}


def route(manager, path, request):
    """(estado HTTP, respuesta) de un POST del gestor; None si la ruta no es suya."""
    action = ROUTES.get(path)
    if action is None:
        return None
    result = action(manager, request)
    return result if isinstance(result, tuple) else (200, result)
