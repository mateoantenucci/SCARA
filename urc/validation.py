"""Validación previa de los tramos (D14, D54): nunca arranca uno que no puede terminar.

Módulo puro, como urc/planner.py. Planifica el tramo y verifica cada
segmento de 20 ms, que es lo que va a ejecutar el firmware: alcance, cambio
de configuración del codo, límites articulares, velocidades y aceleraciones
de articulaciones y motores, y choques. Si algo falla lanza Rejection: un
mensaje corto con el tramo, qué pasa y qué cambiar, y el porqué aparte (D77).
Un tramo LIN imposible sugiere PTP (D14).
"""

from dataclasses import dataclass
import math
import re

from scara.collisions import CollisionChecker
from scara.kinematics import load_config
from urc import planner
from urc.planner import NAMES, SEGMENT_MS


REASONS = ("alcance", "codo", "limite", "velocidad", "colision")
MOTORS = ("M1 (J1)", "M2 (J1 + J2)", "M3 (J3)", "M4 (J4)")
PARTS = {"arm": "el brazo", "forearm": "el antebrazo", "wrist": "la muñeca", "tool": "el efector"}


@dataclass(frozen=True)
class Place:
    """Dónde está el tramo en la trayectoria: nombra sus extremos y el punto que hay que cambiar."""
    tramo: object            # 0 (aproximación), 3, "de vuelta" o None: un movimiento suelto
    origin: str              # "punto 2", "pose actual"
    target: str              # "punto 3", "destino"
    point: int = None        # número del punto cuyo tipo y velocidad usa el tramo, si es uno


class Rejection(ValueError):
    """Un tramo que no se puede ejecutar (D77).

    El mensaje es corto: qué tramo, qué pasa y qué cambiar. detail explica
    por qué, con los valores, y da las alternativas; la página lo muestra
    plegado. summary y why pueden nombrar los extremos con {origin} y
    {target}. tramo es un número, un texto o un Place; hint afina la
    sugerencia: el lado del codo del inicio o dónde se sale del recorrido
    (inicio, destino o camino).
    """

    def __init__(self, reason, summary, why, kind="LIN", tramo=None, hint=None):
        self.reason, self.kind, self.tramo, self.hint = reason, kind, tramo, hint
        self.place = tramo if isinstance(tramo, Place) else None
        names = _names(self.place)
        self.summary = summary.format(**names)
        self.suggestion, also = _suggestion(reason, kind, hint, self.place, names)
        parts = [why.format(**names), also]
        if self.place and self.place.tramo == "de vuelta" and kind == "LIN":
            parts.append(f"La vuelta del loop usa el tipo y la velocidad del punto {self.place.point}. Sin loop no "
                         "existe: a ese punto se llega con el tramo de aproximación, que es PTP.")
        self.detail = " ".join(part for part in parts if part)
        super().__init__(f"{self._where()}: {self.summary}. {self.suggestion}")

    def _where(self):
        place, kind = self.place, self.kind
        if place is None:
            return f"Tramo {self.tramo} ({kind})" if self.tramo is not None else f"Tramo {kind}"
        ends = f"{place.origin} → {place.target}"
        if place.tramo is None:
            return f"Movimiento {kind} ({ends})"
        if place.tramo == 0:
            return f"Tramo 0 ({ends}, {kind} de aproximación)"
        if place.tramo == "de vuelta":
            return f"Tramo de vuelta del loop ({ends}, {kind})"
        return f"Tramo {place.tramo} ({ends}, {kind})"


def _names(place):
    """Los extremos con artículo, para las oraciones: «el punto 2», «la pose actual»."""
    if place is None:
        return {"origin": "el inicio", "target": "el destino"}
    return {key: ("la " if name.startswith("pose") else "el ") + name
            for key, name in (("origin", place.origin), ("target", place.target))}


def _suggestion(reason, kind, hint, place, names):
    """Qué cambiar, nombrando el punto si se sabe cuál es, y las alternativas para el detalle."""
    point = f"el punto {place.point}" if place and place.point else None
    ptp = f"Cambiá {point} a PTP." if point else "Usá un tramo PTP."
    if reason == "codo":
        return ptp, f"También podés grabar {names['target']} con J2 {hint}, del mismo lado que {names['origin']}."
    if reason == "alcance":
        return ptp, "También podés agregar un punto intermedio para que la recta pase más lejos."
    if reason == "limite":
        if hint == "destino":
            return f"Corregí {names['target']}.", None
        if hint == "inicio":
            return ptp, "Un PTP puede traer el robot de vuelta al recorrido; una recta no puede arrancar afuera."
        return ptp, "También podés agregar un punto intermedio para que la recta no la lleve tan lejos."
    if reason == "velocidad":
        slower = f"Bajá la velocidad {_from(point)} o la global." if point else "Bajá la velocidad del tramo."
        return slower, f"Si no alcanza, {ptp[0].lower()}{ptp[1:]}"
    if place and place.tramo == 0:
        return "Llevá el robot con jog a una pose más despejada.", "También podés arrancar desde otro punto."
    if place and place.tramo is None:
        return "Llevá el robot con jog a una pose intermedia que lo esquive.", None
    if kind == "PTP":
        return f"Agregá un punto intermedio antes {_from(names['target'])} que lo esquive.", None
    return ptp, "También podés agregar un punto intermedio que lo esquive."


def check_tramo(kind, start, target, speed, tramo=None, limits=None, config=None, checker=None):
    """Valida y planifica un tramo LIN o PTP; devuelve el plan o lanza Rejection."""
    if kind == "LIN":
        return check_lin(start, target, speed, tramo, limits, config, checker)
    if kind == "PTP":
        return check_ptp(start, target, speed, tramo, limits, config, checker)
    raise ValueError(f"Tipo de tramo desconocido: {kind}")


def check_ptp(start, target, speed=1.0, tramo=None, limits=None, config=None, checker=None):
    """Tramo PTP: límites del destino y choques en la recta en articulaciones (D53).

    Sus velocidades ya las respeta el perfil, y el inicio puede estar fuera
    del recorrido (un jog lo llevó ahí, o el redondeo a pasos junto a un
    límite) o dentro de la zona de margen de un obstáculo: un PTP tiene que
    poder traerlo de vuelta. El chequeo de colisiones arranca entonces desde
    el punto más cercano dentro del recorrido, y deja salir de la zona de
    margen si el camino se aleja. También valida los PTP sueltos: «Ir al
    punto», el PTP manual y «Estacionar».
    """
    config = config or load_config()
    plan = planner.plan_ptp(start, target, speed, limits or planner.default_limits(config))
    found = planner.outside(target, config)
    if found:
        raise Rejection("limite", f"{found[0]} fuera de su recorrido en {{target}}",
                        f"En {{target}}, {_range(found)}", "PTP", tramo, "destino")
    checker = checker or CollisionChecker(config)
    conflict = checker.first_conflict_leaving(planner.inside_range(start, config), planner.units_to_si(target))
    if conflict:
        part, obstacle, why = _collision(conflict, checker)
        raise Rejection("colision", f"{part} puede chocar con {obstacle}", f"En el camino, {why}", "PTP", tramo)
    return plan


def check_lin(start, target, speed=1.0, tramo=None, limits=None, config=None, checker=None):
    """Tramo LIN: planifica la recta y verifica cada segmento antes de enviar nada."""
    config = config or load_config()
    limits = limits or planner.default_limits(config)
    for end, units in (("inicio", start), ("destino", target)):
        found = planner.outside(planner.check_units(units, end.capitalize()), config)
        if found:
            name = "{origin}" if end == "inicio" else "{target}"
            raise Rejection("limite", f"{found[0]} fuera de su recorrido en {name}", f"En {name}, {_range(found)}",
                            tramo=tramo, hint=end)
    if planner.lin_elbow(start, target) is None:
        raise Rejection("codo", "el codo cambia de lado",
                        f"En {{origin}}, J2 = {start[1] / 100:g}°, y en {{target}}, J2 = {target[1] / 100:g}°: el "
                        "codo está de lados opuestos. Para pasar de uno al otro el brazo tiene que estirarse del "
                        "todo (J2 = 0°), y ahí ninguna recta se puede seguir: es una singularidad.", tramo=tramo,
                        hint="negativo" if start[1] < 0 else "positivo")
    _check_reach(start, target, config, tramo)
    plan = planner.plan_lin(start, target, speed, limits, config)
    count = len(plan.segments)
    for index, (_, units) in enumerate(plan.segments):
        found = planner.outside(units, config)
        if found:
            raise Rejection("limite", f"{found[0]} sale de su recorrido al {_percent(index, count)} de la recta",
                            f"Ahí {_range(found, 'llegaría a')} Los dos extremos están dentro: es el camino recto "
                            f"entre ellos el que saca a {found[0]}.", tramo=tramo, hint="camino")
    _check_speeds(start, plan, limits, tramo)
    checker = checker or CollisionChecker(config)
    previous = planner.inside_range(start, config)
    for index, (_, units) in enumerate(plan.segments):
        current = planner.units_to_si(units)
        conflict = checker.first_conflict(previous, current)
        if conflict:
            part, obstacle, why = _collision(conflict, checker)
            raise Rejection("colision", f"{part} puede chocar con {obstacle}",
                            f"Al {_percent(index, count)} de la recta, {why}", tramo=tramo)
        previous = current
    return plan


def _check_reach(start, target, config, tramo):
    """La recta tiene que quedar en la corona que alcanza el brazo.

    Por fuera la limita el brazo estirado; por dentro, J2: con el codo
    plegado a su límite el extremo queda a r_min del eje de J1. Los extremos
    son poses válidas y el círculo exterior es convexo, así que la recta solo
    puede salir por el agujero del centro, al pasar cerca de la torre.
    """
    l1, l2 = config["geometry"]["l1"], config["geometry"]["l2"]
    fold = min(abs(b) for b in config["limits"][1])
    inner = math.sqrt(l1 * l1 + l2 * l2 + 2 * l1 * l2 * math.cos(fold))
    origin, end = (planner.tool_point(q, config)[:2] for q in (start, target))
    closest = planner.distance_to_line((0.0, 0.0), origin, end)
    # Un micrón de holgura: un extremo puede estar justo en el límite de J2.
    if closest < inner - 1e-6:
        raise Rejection("alcance", "la recta pasa demasiado cerca de la torre",
                        f"Pasa a {closest * 1000:.0f} mm del eje de J1, y el extremo no llega a menos de "
                        f"{inner * 1000:.0f} mm: el codo se pliega hasta J2 = ±{math.degrees(fold):.0f}°.",
                        tramo=tramo)


def _check_speeds(start, plan, limits, tramo):
    """Velocidad y aceleración de cada articulación y motor, segmento a segmento.

    Se miden sobre las muestras sin redondear: el redondeo agrega a lo sumo
    una centésima por articulación, dentro de lo que admite el firmware (D51).
    Cerca del brazo estirado, una recta pide a J2 velocidades sin cota.
    """
    seconds = SEGMENT_MS / 1000
    points = [tuple(map(float, start))] + list(plan.samples)
    velocities = [[(b - a) / seconds for a, b in zip(p, q)] for p, q in zip(points, points[1:])]
    count = len(velocities)
    previous = [0.0] * 4
    for index, velocity in enumerate(velocities + [[0.0] * 4]):
        acceleration = [(v - w) / seconds for v, w in zip(velocity, previous)]
        checks = (
            (NAMES, velocity, limits.joint_speed, "velocidad"),
            (NAMES, acceleration, limits.joint_acceleration, "aceleración"),
            (MOTORS, planner.motor_travel(velocity), limits.motor_speed, "velocidad"),
            (MOTORS, planner.motor_travel(acceleration), limits.motor_acceleration, "aceleración"),
        )
        for names, values, maxima, what in checks:
            for axis, (value, maximum) in enumerate(zip(values, maxima)):
                if abs(value) > maximum * (1 + 1e-9):
                    unit = "mm" if axis == 3 else "°"
                    rate = "/s" if what == "velocidad" else "/s²"
                    sample = plan.samples[min(index, count - 1)]
                    why = (f"Al {_percent(min(index, count - 1), count)} de la recta, {names[axis]} necesitaría "
                           f"{abs(value) / 100:.2f} {unit}{rate}, y su máximo es {maximum / 100:.2f} {unit}{rate}.")
                    if abs(sample[1]) < 3000:
                        why += (f" Ahí el brazo está casi estirado (J2 = {sample[1] / 100:.1f}°): cerca de esa "
                                "pose, para seguir una recta el brazo y el antebrazo tienen que girar cada vez más "
                                "rápido, y bajar la velocidad puede no alcanzar.")
                    raise Rejection("velocidad", f"{names[axis]} no da la {what} que pide la recta", why, tramo=tramo)
        previous = velocity


def _collision(conflict, checker):
    """La parte del robot, el obstáculo y el porqué, para el rechazo."""
    obstacle = conflict["obstacle"]
    if any(box["name"] == obstacle for box in checker.exact_fixed_base):
        # Nombres del CAD: «0-Torre-1» → «Torre».
        obstacle = f"la pieza {re.sub(r'^[0-9A-Z]-', '', re.sub(r'(-registro)?-[0-9]+$', '', obstacle))} de la base"
    else:
        obstacle = f"el obstáculo «{obstacle.replace('_', ' ')}»"
    part = PARTS.get(conflict.get("group"), "una pieza")
    why = (f"las envolventes {_from(part)} ({conflict['instance']}) y {_from(obstacle)} quedan a menos de "
           f"{checker.margin * 1000:g} mm.")
    return part, obstacle, why


def _range(found, verb="="):
    """«J1 = 140°, y su recorrido va de -135° a 135°.», de planner.outside."""
    name, value, low, high = found
    return f"{name} {verb} {value}, y su recorrido va de {low} a {high}."


def _percent(index, count):
    return f"{100 * (index + 1) / count:.0f} %"


def _from(name):
    return "del " + name[3:] if name.startswith("el ") else "de " + name
