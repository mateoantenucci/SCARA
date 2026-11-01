"""Validación previa de los tramos (D14, D54): nunca arranca uno que no puede terminar.

Módulo puro, como urc/planner.py. Planifica el tramo y verifica cada
segmento de 20 ms, que es lo que va a ejecutar el firmware: alcance, cambio
de configuración del codo, límites articulares, velocidades y aceleraciones
de articulaciones y motores, y choques. Si algo falla lanza Rejection con el
tramo, el motivo y qué probar. Un tramo LIN imposible sugiere PTP (D14).
"""

import math

from scara.collisions import CollisionChecker
from scara.kinematics import load_config
from urc import planner
from urc.planner import NAMES, SEGMENT_MS


REASONS = {
    "alcance": "fuera de alcance",
    "codo": "cambio de codo",
    "limite": "límite articular",
    "velocidad": "velocidad excesiva",
    "colision": "colisión",
}
MOTORS = ("M1 (J1)", "M2 (J1 + J2)", "M3 (J3)", "M4 (J4)")


class Rejection(ValueError):
    """Un tramo que no se puede ejecutar: cuál, por qué y qué probar."""

    def __init__(self, reason, detail, kind="LIN", tramo=None):
        self.reason, self.detail, self.kind, self.tramo = reason, detail, kind, tramo
        if kind != "LIN":
            self.suggestion = None
        elif reason == "velocidad":
            self.suggestion = "Bajá la velocidad del tramo o usá un tramo PTP."
        else:
            self.suggestion = "Usá un tramo PTP."
        where = f"Tramo {tramo} ({kind})" if tramo is not None else f"Tramo {kind}"
        text = f"{where}, {REASONS[reason]}: {detail}."
        super().__init__(f"{text} {self.suggestion}" if self.suggestion else text)


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
    del recorrido o dentro de la zona de margen de un obstáculo: un PTP tiene
    que poder traerlo de vuelta.
    """
    config = config or load_config()
    plan = planner.plan_ptp(start, target, speed, limits or planner.default_limits(config))
    problem = planner.out_of_range(target, config)
    if problem:
        raise Rejection("limite", f"el destino tiene {problem}", "PTP", tramo)
    checker = checker or CollisionChecker(config)
    conflict = checker.first_conflict_leaving(planner.inside_range(start, config), planner.units_to_si(target))
    if conflict:
        raise Rejection("colision", _collision(conflict, checker), "PTP", tramo)
    return plan


def check_lin(start, target, speed=1.0, tramo=None, limits=None, config=None, checker=None):
    """Tramo LIN: planifica la recta y verifica cada segmento antes de enviar nada."""
    config = config or load_config()
    limits = limits or planner.default_limits(config)
    for name, units in (("el inicio", start), ("el destino", target)):
        problem = planner.out_of_range(planner.check_units(units, name.capitalize()), config)
        if problem:
            raise Rejection("limite", f"{name} tiene {problem}", tramo=tramo)
    if planner.lin_elbow(start, target) is None:
        raise Rejection("codo", f"J2 pasa de {start[1] / 100:g}° a {target[1] / 100:g}°; para cambiar de lado "
                                "el brazo tendría que estirarse, que es una singularidad", tramo=tramo)
    _check_reach(start, target, config, tramo)
    plan = planner.plan_lin(start, target, speed, limits, config)
    count = len(plan.segments)
    for index, (_, units) in enumerate(plan.segments):
        problem = planner.out_of_range(units, config)
        if problem:
            raise Rejection("limite", f"{problem} al {_percent(index, count)} del tramo", tramo=tramo)
    _check_speeds(start, plan, limits, tramo)
    checker = checker or CollisionChecker(config)
    previous = planner.inside_range(start, config)
    for index, (_, units) in enumerate(plan.segments):
        current = planner.units_to_si(units)
        conflict = checker.first_conflict(previous, current)
        if conflict:
            raise Rejection("colision", f"{_collision(conflict, checker)} al {_percent(index, count)} del tramo",
                            tramo=tramo)
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
        raise Rejection("alcance", f"la recta pasa a {closest * 1000:.0f} mm del eje de J1 y el brazo no llega "
                                   f"a menos de {inner * 1000:.0f} mm (J2 hasta ±{math.degrees(fold):.0f}°)",
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
                    where = f"al {_percent(min(index, count - 1), count)} del tramo"
                    if abs(sample[1]) < 3000:
                        where += f", con el brazo casi estirado (J2 = {sample[1] / 100:.1f}°)"
                    raise Rejection("velocidad", f"{names[axis]} necesitaría {what} de {abs(value) / 100:.2f} "
                                                 f"{unit}{rate} (máximo {maximum / 100:.2f}) {where}", tramo=tramo)
        previous = velocity


def _collision(conflict, checker):
    return (f"{conflict['instance']} puede tocar {conflict['obstacle']} "
            f"(envolventes y margen de {checker.margin * 1000:g} mm)")


def _percent(index, count):
    return f"{100 * (index + 1) / count:.0f} %"
