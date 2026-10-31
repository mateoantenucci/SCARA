"""Planificador de la URC: tramos PTP y LIN en segmentos temporizados (ADR 0005).

Módulo puro, sin red ni estado. Trabaja en las unidades de scara/1:
centésimas de grado en J1–J3 y centésimas de mm en J4 (ADR 0003).

Un tramo PTP interpola todas las articulaciones con un mismo perfil
trapezoidal de velocidad, así empiezan, aceleran, frenan y llegan a la vez.
El perfil lo fija la restricción más exigente entre las articulaciones del
modelo (config/scara.json) y los motores (D45), con el acople: M2 sigue a
J1 + J2. Después se parte en segmentos de 20 ms (D27) que el firmware
ejecuta con su reloj.

Un tramo LIN aplica el mismo perfil a la recta del punto de herramienta y al
rumbo, y resuelve la cinemática inversa en cada muestra (D54). Lo que puede
fallar en el camino lo verifica urc/validation.py antes de enviar nada.
"""

from dataclasses import dataclass
import math

from scara.collisions import CollisionChecker
from scara.kinematics import arm_angles, forward, inverse, load_config, validate_joints


SEGMENT_MS = 20              # D27
NAMES = ("J1", "J2", "J3", "J4")
# Límites de cada motor (D45, firmware/config.h) en las unidades de su
# articulación: M1 mueve J1, M2 mueve J1 + J2, M3 mueve J3 (θM/4) y M4 mueve
# J4 (8 mm por vuelta). Centésimas por segundo y por segundo².
MOTOR_SPEED = (2000, 2000, 2800, 3000)
MOTOR_ACCELERATION = (3400, 3400, 5100, 6000)
# Tramo LIN al 100 % (D54): velocidad y aceleración del punto de herramienta
# sobre la recta (centésimas de mm) y del rumbo (centésimas de grado). Son
# las de J4 y M1: una recta vertical o un giro en el lugar nunca las superan.
TOOL_SPEED = (3000, 2000)
TOOL_ACCELERATION = (6000, 3400)
# Grados o metros del modelo → unidades de scara/1.
SCALE = (100 * 180 / math.pi,) * 3 + (100 * 1000,)


@dataclass(frozen=True)
class Limits:
    joint_speed: tuple           # J1–J4, centésimas/s
    joint_acceleration: tuple    # J1–J4, centésimas/s²
    motor_speed: tuple = MOTOR_SPEED
    motor_acceleration: tuple = MOTOR_ACCELERATION
    tool_speed: tuple = TOOL_SPEED                # LIN: recta y rumbo
    tool_acceleration: tuple = TOOL_ACCELERATION


@dataclass(frozen=True)
class Ptp:
    duration: float              # s, del perfil sin partir en segmentos
    segments: list               # [(ms, (J1, J2, J3, J4)), ...]; el último es el destino


def default_limits(config=None):
    """Límites del modelo de Webots (max_velocity, max_acceleration) y de los motores."""
    config = config or load_config()
    return Limits(tuple(v * s for v, s in zip(config["max_velocity"], SCALE)),
                  tuple(a * s for a, s in zip(config["max_acceleration"], SCALE)))


def motor_travel(delta):
    """Recorrido de cada motor en las unidades de su articulación: M2 sigue a J1 + J2."""
    return (delta[0], delta[0] + delta[1], delta[2], delta[3])


def plan_ptp(start, target, speed=1.0, limits=None):
    """Tramo PTP de start a target, al `speed` (0–1] de la velocidad máxima.

    La fracción reduce la velocidad máxima de cada articulación y de cada
    motor; la aceleración queda en su máximo.
    """
    start, target = check_units(start, "Inicio"), check_units(target, "Destino")
    _fraction(speed)
    limits = limits or default_limits()
    delta = [b - a for a, b in zip(start, target)]
    # El perfil s(t) va de 0 a 1; cada articulación y cada motor se mueve
    # |recorrido| · s. Velocidad y aceleración máximas de s:
    distances = [abs(d) for d in delta] + [abs(d) for d in motor_travel(delta)]
    speeds = list(limits.joint_speed) + list(limits.motor_speed)
    accelerations = list(limits.joint_acceleration) + list(limits.motor_acceleration)
    moving = [i for i, d in enumerate(distances) if d > 0]
    if not moving:
        return Ptp(0.0, [])
    peak = min(speeds[i] * speed / distances[i] for i in moving)
    acceleration = min(accelerations[i] / distances[i] for i in moving)
    profile = _trapezoid(peak, acceleration)
    segments = [(SEGMENT_MS, tuple(_round(a + d * s) for a, d in zip(start, delta))) for s in _samples(profile)]
    segments[-1] = (SEGMENT_MS, tuple(target))
    return Ptp(profile.duration, segments)


def _samples(profile):
    """Avance s del perfil al final de cada segmento de 20 ms.

    El perfil se estira para que los segmentos entren justos, así que nunca
    supera sus máximos.
    """
    count = max(1, math.ceil(profile.duration * 1000 / SEGMENT_MS - 1e-9))
    return [profile.position(profile.duration * k / count) for k in range(1, count + 1)]


def _fraction(speed):
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0 < speed <= 1:
        raise ValueError("La velocidad debe ser una fracción mayor que 0 y hasta 1")


# --- Tramo LIN -------------------------------------------------------------

@dataclass(frozen=True)
class Lin:
    duration: float              # s, del perfil sin partir en segmentos
    segments: list               # [(ms, (J1, J2, J3, J4)), ...]; el último es el destino
    samples: list                # los mismos destinos sin redondear, en centésimas
    elbow: int                   # configuración del codo del tramo: signo de J2
    deviation: float             # mm: lo más que se aparta de la recta lo que ejecuta el firmware


def lin_elbow(start, target):
    """Configuración del codo de un tramo LIN (−1 o 1), o None si cambia entre sus extremos.

    El brazo estirado (J2 = 0) admite las dos: el tramo toma la del otro
    extremo y, si los dos están estirados, la preferida (J2 negativo, D31).
    """
    sides = {(q > 0) - (q < 0) for q in (start[1], target[1])} - {0}
    if len(sides) > 1:
        return None
    return sides.pop() if sides else -1


def plan_lin(start, target, speed=1.0, limits=None, config=None):
    """Tramo LIN de start a target, al `speed` (0–1] de la velocidad del punto de herramienta.

    El punto de herramienta recorre la recta entre los dos extremos y el
    rumbo J1 + J2 + J3 va de uno al otro, los dos con el mismo perfil
    trapezoidal. A diferencia del PTP, la fracción reduce también la
    aceleración: cerca del brazo estirado, la de J2 crece con la del punto de
    herramienta, y bajar la velocidad tiene que alcanzar para resolverlo.
    En cada muestra se resuelve la cinemática inversa con la
    configuración del codo del tramo. No verifica límites, velocidades de las
    articulaciones ni choques: eso es de urc/validation.py.
    """
    start, target = check_units(start, "Inicio"), check_units(target, "Destino")
    _fraction(speed)
    limits = limits or default_limits()
    config = config or load_config()
    elbow = lin_elbow(start, target)
    if elbow is None:
        raise ValueError("Un tramo LIN no puede cambiar la configuración del codo")
    origin, end = tool_point(start, config), tool_point(target, config)
    path = [b - a for a, b in zip(origin, end)]
    # Centésimas de mm sobre la recta y de grado de rumbo; el rumbo es la
    # suma sin envolver, así va al destino por el lado que indica J3.
    distances = (math.hypot(*path) * SCALE[3], abs(sum(target[:3]) - sum(start[:3])))
    moving = [i for i, d in enumerate(distances) if d > 1e-6]
    if not moving:
        return Lin(0.0, [], [], elbow, 0.0)
    peak = min(limits.tool_speed[i] * speed / distances[i] for i in moving)
    acceleration = min(limits.tool_acceleration[i] * speed / distances[i] for i in moving)
    profile = _trapezoid(peak, acceleration)
    heading, turn = sum(start[:3]), sum(target[:3]) - sum(start[:3])
    samples, previous = [], start[0] / SCALE[0]
    for s in _samples(profile):
        q1, q2 = arm_angles(origin[0] + path[0] * s, origin[1] + path[1] * s, elbow, config)
        # J1 continuo: de las vueltas posibles, la más cercana a la muestra anterior.
        q1 += math.tau * round((previous - q1) / math.tau)
        previous = q1
        j1, j2 = q1 * SCALE[0], q2 * SCALE[1]
        samples.append((j1, j2, heading + turn * s - j1 - j2, start[3] + (target[3] - start[3]) * s))
    # La última muestra no se reemplaza por el destino: si el camino da la
    # vuelta por detrás, J1 termina una vuelta corrido y la validación lo ve.
    segments = [(SEGMENT_MS, tuple(_round(v) for v in q)) for q in samples]
    return Lin(profile.duration, segments, samples, elbow, _deviation(start, segments, origin, end, config))


def tool_point(units, config=None):
    """Punto de herramienta (x, y, z) en metros para una configuración en centésimas."""
    return forward(units_to_si(units), config or load_config())[:3]


def distance_to_line(point, origin, end):
    """Distancia de un punto al segmento de recta origin–end."""
    path = [b - a for a, b in zip(origin, end)]
    squared = sum(d * d for d in path)
    s = sum((p - a) * d for p, a, d in zip(point, origin, path)) / squared if squared else 0.0
    s = min(max(s, 0.0), 1.0)
    return math.dist(point, [a + d * s for a, d in zip(origin, path)])


def _deviation(start, segments, origin, end, config):
    """Lo más que se aparta de la recta, en mm, lo que ejecuta el firmware.

    El firmware interpola lineal en articulaciones entre los destinos
    redondeados de los segmentos: se mide en cuatro puntos de cada uno.
    """
    worst, previous = 0.0, start
    for _, units in segments:
        for u in (0.0, 0.25, 0.5, 0.75):
            point = tool_point([a + (b - a) * u for a, b in zip(previous, units)], config)
            worst = max(worst, distance_to_line(point, origin, end))
        previous = units
    return worst * 1000


def lin_tolerance(config=None, limits=None):
    """Cota, en mm, de cuánto se aparta de la recta un tramo LIN válido (D54).

    Suma dos efectos:
    - Redondeo a la centésima: J1 y J2 se apartan hasta media centésima de
      grado cada uno, y el antebrazo (J1 + J2) una entera; J4, media
      centésima de mm. El punto de herramienta se corre hasta l1·e + l2·2e
      en el plano.
    - Cuerda: dentro de un segmento el firmware interpola lineal en
      articulaciones y el extremo describe arcos. Si el brazo y el antebrazo
      giran Δ1 y Δφ en el segmento, la flecha es a lo sumo (l1·Δ1² + l2·Δφ²)/8.
      M1 y M2 los acotan (D45), y la validación rechaza lo que los supere.
    """
    config = config or load_config()
    limits = limits or default_limits(config)
    l1, l2 = config["geometry"]["l1"], config["geometry"]["l2"]
    half = 0.5 / SCALE[0]
    rounding = math.hypot(l1 * half + l2 * 2 * half, 0.5 / SCALE[3])
    arm, forearm = (limits.motor_speed[i] * SEGMENT_MS / 1000 / SCALE[0] for i in (0, 1))
    chord = (l1 * arm ** 2 + l2 * forearm ** 2) / 8
    return (rounding + chord) * 1000


@dataclass(frozen=True)
class _trapezoid:
    """Perfil trapezoidal de 0 a 1, o triangular si no llega a la velocidad máxima."""
    peak: float
    acceleration: float

    def __post_init__(self):
        if self.peak * self.peak / self.acceleration > 1:
            object.__setattr__(self, "peak", math.sqrt(self.acceleration))

    @property
    def ramp(self):
        return self.peak / self.acceleration

    @property
    def duration(self):
        return 1 / self.peak + self.ramp

    def position(self, t):
        t = min(max(t, 0.0), self.duration)
        if t < self.ramp:
            return self.acceleration * t * t / 2
        if t > self.duration - self.ramp:
            left = self.duration - t
            return 1 - self.acceleration * left * left / 2
        return self.peak * (t - self.ramp / 2)


def _round(value):
    return math.floor(value + 0.5)


def check_units(values, name):
    if (not isinstance(values, (list, tuple)) or len(values) != 4
            or any(isinstance(v, bool) or not isinstance(v, int) for v in values)):
        raise ValueError(f"{name}: se esperan J1–J4 como cuatro enteros en centésimas")
    if any(abs(v) > 99999 for v in values):
        raise ValueError(f"{name}: fuera del rango de scara/1")
    return tuple(values)


# --- Poses escritas a mano ----------------------------------------------

def units_to_si(units):
    """Centésimas de scara/1 → radianes y metros del modelo."""
    return [q / s for q, s in zip(units, SCALE)]


def si_to_units(q):
    """Radianes y metros del modelo → centésimas de scara/1, redondeadas."""
    return tuple(_round(v * s) for v, s in zip(q, SCALE))


def joints_from_pose(x, y, z, heading, elbow=-1, config=None):
    """Configuración articular para un punto de herramienta en mm y un rumbo en grados.

    elbow es la configuración del codo, por el signo de J2: −1 (la preferida,
    D31) o +1.
    """
    if isinstance(elbow, bool) or elbow not in (-1, 1):
        raise ValueError("El codo debe ser -1 (J2 negativo) o 1 (J2 positivo)")
    config = config or load_config()
    numbers = [x, y, z, heading]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in numbers):
        raise ValueError("X, Y, Z y rumbo tienen que ser números")
    q = inverse(x / 1000, y / 1000, z / 1000, math.radians(heading), elbow=elbow, config=config)
    return si_to_units(q)


def check_target(start, target, config=None, checker=None):
    """Valida un PTP antes de enviarlo: límites articulares y choques en todo el camino.

    El camino de un PTP es la recta en articulaciones de start a target, la
    misma que verifica el chequeo de colisiones. El inicio puede estar fuera
    del recorrido (un jog lo llevó ahí, o el redondeo a pasos junto a un
    límite): un PTP tiene que poder traerlo de vuelta. El chequeo de
    colisiones arranca entonces desde el punto más cercano dentro del recorrido.
    """
    config = config or load_config()
    start, target = check_units(start, "Inicio"), check_units(target, "Destino")
    problem = out_of_range(target, config)
    if problem:
        raise ValueError(problem)
    checker = checker or CollisionChecker(config)
    checker.validate_path(inside_range(start, config), units_to_si(target))


def out_of_range(units, config=None):
    """La primera articulación fuera de su recorrido, como texto para el operador, o None."""
    config = config or load_config()
    for name, value, bounds, scale in zip(NAMES, units, config["limits"], SCALE):
        low, high = (_round(b * scale) for b in bounds)
        if not low <= value <= high:
            return f"{name} fuera de su recorrido: {value} no está entre {low} y {high} centésimas"
    return None


def inside_range(units, config=None):
    """El punto del recorrido más cercano a una configuración, en radianes y metros."""
    config = config or load_config()
    inside = [min(max(q, low), high) for q, (low, high) in zip(units_to_si(units), config["limits"])]
    return validate_joints(inside, config)
