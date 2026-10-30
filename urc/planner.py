"""Planificador de la URC: tramos PTP en segmentos temporizados (ADR 0005).

Módulo puro, sin red ni estado. Trabaja en las unidades de scara/1:
centésimas de grado en J1–J3 y centésimas de mm en J4 (ADR 0003).

Un tramo PTP interpola todas las articulaciones con un mismo perfil
trapezoidal de velocidad, así empiezan, aceleran, frenan y llegan a la vez.
El perfil lo fija la restricción más exigente entre las articulaciones del
modelo (config/scara.json) y los motores (D45), con el acople: M2 sigue a
J1 + J2. Después se parte en segmentos de 20 ms (D27) que el firmware
ejecuta con su reloj.
"""

from dataclasses import dataclass
import math

from scara.collisions import CollisionChecker
from scara.kinematics import inverse, load_config, validate_joints


SEGMENT_MS = 20              # D27
NAMES = ("J1", "J2", "J3", "J4")
# Límites de cada motor (D45, firmware/config.h) en las unidades de su
# articulación: M1 mueve J1, M2 mueve J1 + J2, M3 mueve J3 (θM/4) y M4 mueve
# J4 (8 mm por vuelta). Centésimas por segundo y por segundo².
MOTOR_SPEED = (2000, 2000, 2800, 3000)
MOTOR_ACCELERATION = (3400, 3400, 5100, 6000)
# Grados o metros del modelo → unidades de scara/1.
SCALE = (100 * 180 / math.pi,) * 3 + (100 * 1000,)


@dataclass(frozen=True)
class Limits:
    joint_speed: tuple           # J1–J4, centésimas/s
    joint_acceleration: tuple    # J1–J4, centésimas/s²
    motor_speed: tuple = MOTOR_SPEED
    motor_acceleration: tuple = MOTOR_ACCELERATION


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
    start, target = _units(start, "Inicio"), _units(target, "Destino")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0 < speed <= 1:
        raise ValueError("La velocidad debe ser una fracción mayor que 0 y hasta 1")
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
    # Segmentos de 20 ms; el perfil se estira para que entren justos, así que
    # nunca supera sus máximos.
    count = max(1, math.ceil(profile.duration * 1000 / SEGMENT_MS - 1e-9))
    segments = []
    for k in range(1, count + 1):
        s = profile.position(profile.duration * k / count)
        segments.append((SEGMENT_MS, tuple(_round(a + d * s) for a, d in zip(start, delta))))
    segments[-1] = (SEGMENT_MS, tuple(target))
    return Ptp(profile.duration, segments)


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


def _units(values, name):
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
    start, target = _units(start, "Inicio"), _units(target, "Destino")
    for name, value, bounds, scale in zip(NAMES, target, config["limits"], SCALE):
        low, high = (_round(b * scale) for b in bounds)
        if not low <= value <= high:
            raise ValueError(f"{name} fuera de su recorrido: {value} no está entre {low} y {high} centésimas")
    inside = [min(max(q, low), high) for q, (low, high) in zip(units_to_si(start), config["limits"])]
    checker = checker or CollisionChecker(config)
    checker.validate_path(validate_joints(inside, config), units_to_si(target))
