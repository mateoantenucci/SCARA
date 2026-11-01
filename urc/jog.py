"""Jog verificado: el próximo segmento del jog con el robot referenciado (D28, D75).

Módulo puro, sin red ni estado, en las unidades de scara/1 (ADR 0003). La
sesión pide un paso por vez, de 20 ms, y mantiene unos tres en la cola del
firmware: al soltar la tecla deja de pedir, y el robot frena cuando termina
lo encolado.

Las mismas teclas en los dos modos (D12): cada una es un eje (1–4) y un
sentido.
- Articular: el eje es la articulación.
- Cartesiano: A/D (eje 1) mueven el punto de herramienta en Y, W/S (eje 2)
  en X, Q/E (eje 3) giran el rumbo con J3 y R/F (eje 4) suben y bajan con
  J4. En la pose de reposo, cada tecla mueve hacia el mismo lado que en el
  modo articular.

Cada paso se verifica antes de enviarlo: el recorrido de cada articulación,
el borde del alcance sin cambiar la configuración del codo, y la zona de
margen de los obstáculos, de la que solo se puede salir. Como el robot frena
en el último segmento verificado, no hace falta mirar más adelante.
"""

from dataclasses import dataclass
import math

from scara.kinematics import arm_angles
from urc import planner


SEGMENT_MS = planner.SEGMENT_MS
# El firmware arranca y frena un segmento sin rampa: ningún motor pasa de
# la velocidad del jog sin rampa (JOG_SPEED_MAX, D70), en las unidades de
# su articulación.
NO_RAMP_SPEED = 1000         # centésimas por segundo
# Normal y lento (Mayús): J1–J3 y el rumbo en centésimas de grado por
# segundo, J4 en centésimas de mm por segundo; el punto de herramienta en el
# plano, en mm/s.
JOINT_SPEED = (1000, 200)
TOOL_SPEED = (20, 4)
# El jog cartesiano frena antes del brazo estirado, donde la configuración
# del codo se podría dar vuelta (D31): |J2| no baja de 2°.
ELBOW_MIN = 200
MODES = ("articular", "cartesiano")


class Blocked(ValueError):
    """El jog no puede seguir en ese sentido; el texto dice por qué."""


@dataclass(frozen=True)
class Command:
    mode: str                    # "articular" o "cartesiano"
    axis: int                    # 1–4: la tecla, igual en los dos modos
    direction: int               # 1 o −1
    slow: bool = False


def elbow_of(units):
    """Configuración del codo del jog cartesiano: el signo de J2; estirado, la preferida (D31)."""
    return 1 if units[1] > 0 else -1


def elbow_name(units):
    """La configuración del codo para la interfaz (D31): por el signo de J2, o estirado."""
    return "positivo" if units[1] > 0 else "negativo" if units[1] < 0 else "estirado"


def step(q, command, elbow, config, checker, travel):
    """La configuración (centésimas, sin redondear) al final del próximo segmento.

    q es donde termina el último segmento enviado, sin redondear, así el
    punto de herramienta no acumula el redondeo. Si el paso pasaría un
    límite, saldría del alcance, cambiaría el codo o entraría en la zona de
    margen de un obstáculo, levanta Blocked.
    """
    q = tuple(float(v) for v in q)
    seconds = SEGMENT_MS / 1000
    speed = JOINT_SPEED[command.slow]
    if command.mode == "articular" or command.axis in (3, 4):
        # En el cartesiano, el rumbo es J3 y la altura es J4: R sube, J4 baja de valor.
        after = list(q)
        after[command.axis - 1] += command.direction * speed * seconds
        after = tuple(after)
    else:
        after = _planar(q, command, elbow, TOOL_SPEED[command.slow] / 1000 * seconds, config)
    _check_travel(q, after, travel)
    if command.mode == "cartesiano" and abs(after[1]) < ELBOW_MIN and abs(after[1]) < abs(q[1]):
        raise Blocked(_edge())
    _check_obstacles(q, after, config, checker)
    return after


def _planar(q, command, elbow, distance, config):
    """Mueve el punto de herramienta `distance` metros en X o Y, con el rumbo y la altura fijos.

    Si algún motor pasaría de la velocidad sin rampa, acorta el paso: cerca
    del brazo estirado o de la torre, la cinemática inversa pide giros
    rápidos para poco recorrido.
    """
    origin = planner.tool_point(q, config)
    limit = NO_RAMP_SPEED * SEGMENT_MS / 1000

    def move(fraction):
        """La configuración y su motor más rápido por segmento, o None fuera del alcance."""
        point = list(origin[:2])
        point[2 - command.axis] += command.direction * distance * fraction  # eje 1: Y; eje 2: X
        try:
            q1, q2 = arm_angles(*point, elbow, config)
        except ValueError:
            return None, math.inf
        j1 = q1 * planner.SCALE[0]
        # J1 continuo: de las vueltas posibles, la más cercana.
        j1 += 36000 * round((q[0] - j1) / 36000)
        j2 = q2 * planner.SCALE[1]
        after = (j1, j2, sum(q[:3]) - j1 - j2, q[3])
        delta = [b - a for a, b in zip(q, after)]
        return after, max(abs(d) for d in delta + list(planner.motor_travel(delta)))

    after, fastest = move(1.0)
    if fastest <= limit + 1e-9:
        return after
    # Junto al brazo estirado, J2 crece como la raíz del avance: se busca
    # por bisección el paso más largo que respeta la velocidad y el alcance.
    low, high, best = 0.0, 1.0, (None, 0.0)
    for _ in range(30):
        middle = (low + high) / 2
        after, fastest = move(middle)
        if fastest <= limit + 1e-9:
            low, best = middle, (after, fastest)
        else:
            high = middle
    # Si lo que acorta el paso es el alcance y no la velocidad, el robot está
    # en el borde: por ejemplo, de costado con el brazo estirado.
    if best[0] is None or best[1] < limit / 2:
        raise Blocked(_edge())
    return best[0]


def _edge():
    return "llegó al borde del alcance: el jog cartesiano no estira el brazo ni cambia la configuración del codo"


def _check_travel(q, after, travel):
    """Frena antes de pasar el recorrido; desde afuera, solo deja volver."""
    for name, before, value, (low, high) in zip(planner.NAMES, q, after, travel):
        outside = max(low - value, value - high, 0)
        if outside > max(low - before, before - high, 0) + 1e-9:
            bound, unit = (high if value > high else low) / 100, " mm" if name == "J4" else "°"
            raise Blocked(f"{name} llegó al límite de su recorrido ({bound:g}{unit})")


def _check_obstacles(q, after, config, checker):
    """Dentro de la zona de margen de un obstáculo, solo deja alejarse (D70)."""
    here = checker.clearance(planner.inside_range(q, config))
    ahead = planner.inside_range(after, config)
    if checker.clearance(ahead) < min(here, checker.margin):
        conflict = checker.first_conflict(ahead, ahead)
        where = f"{conflict['instance']} tocaría {conflict['obstacle']}" if conflict else "habría un choque"
        raise Blocked(f"{where} (envolventes y margen de {checker.margin * 1000:g} mm)")


def rounded(q):
    """La configuración para el SEG, redondeada a la centésima."""
    return tuple(math.floor(v + 0.5) for v in q)
