"""Los Hall de Webots se activan por geometría y coinciden con lo que supone el firmware.

Lee el SCARA.proto generado: cada KY-003 es un Receiver en la pieza fija y
cada imán un Emitter, con su alcance, en la que se mueve. Con la articulación
en J, calcula la distancia entre los dos y dice si el imán está dentro del
alcance, la misma regla que aplica la planta de Webots (D57). Los flancos que salen de esa geometría tienen que ser los
de HALL_EDGE y HALL_FAR_EDGE (firmware/config.h) y los de la planta falsa de las
conversaciones (firmware/test/conversacion.cpp).
"""

from functools import lru_cache
import math
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROTO = (ROOT / "webots" / "protos" / "SCARA.proto").read_text(encoding="utf-8")
NUMBER = r"(-?[0-9.e+-]+)"


def vector(text):
    return [float(value) for value in text.split()]


@lru_cache(maxsize=None)
def device(kind, name):
    match = re.search(kind + r' \{ translation ([^n]+) name "' + name + r'"\s+type "radio"(?: range ' + NUMBER +
                      r')?', PROTO)
    if not match:
        raise AssertionError(f"Falta {kind} {name} en SCARA.proto")
    return vector(match.group(1)), (float(match.group(2)) if match.group(2) else None)


def config_array(name):
    text = (ROOT / "firmware" / "config.h").read_text(encoding="utf-8")
    match = re.search(name + r"\[MOTOR_COUNT\] = \{([^}]*)\}", text)
    return [int(value) for value in match.group(1).split(",")]


ANCHORS = [vector(text) for text in re.findall(r"HingeJointParameters \{ axis 0 0 1 anchor ([^p]+) position", PROTO)]
TOOL_Z = float(re.search(r'Receiver \{ translation [^ ]+ [^ ]+ ' + NUMBER + ' name "hall4"', PROTO).group(1))


def active(joint, position):
    """¿El Hall de Jjoint+1 se activa con la articulación en `position` (rad o m)?"""
    sensor, _ = device("Receiver", f"hall{joint + 1}")
    for name in ("inicio", "fin"):
        magnet, reach = device("Emitter", f"iman{joint + 1}_{name}")
        if joint == 3:
            # El pistón baja cuando J4 crece: su origen está a TOOL_Z − J4 del cuerpo Z.
            offset = [magnet[0] - sensor[0], magnet[1] - sensor[1], TOOL_Z - position + magnet[2] - sensor[2]]
        else:
            # El imán gira con la pieza alrededor del eje; el sensor está fijo.
            anchor = ANCHORS[joint]
            c, s = math.cos(position), math.sin(position)
            turned = [c * magnet[0] - s * magnet[1], s * magnet[0] + c * magnet[1], magnet[2]]
            relative = [sensor[i] - anchor[i] for i in range(3)]
            offset = [turned[i] - relative[i] for i in range(3)]
        if math.dist(offset, [0, 0, 0]) <= reach:
            return True
    return False


def edge(joint, start, step):
    """Primera posición, desde `start` y en pasos de `step`, en la que el Hall se activa."""
    position = start
    for _ in range(40000):  # más que todo el recorrido: si no aparece, el imán no está
        if active(joint, position):
            return position
        position += step
    raise AssertionError(f"El Hall de J{joint + 1} no se activa en todo el recorrido")


UNITS = (100 * 180 / math.pi,) * 3 + (100000,)


class HallGeometryTests(unittest.TestCase):
    def test_edges_match_the_firmware(self):
        edges = config_array("HALL_EDGE")
        for joint in range(4):
            with self.subTest(joint=f"J{joint + 1}"):
                rest = 0.12 if joint == 3 else 0.0
                # Hacia la referencia: J1–J3 negativos, J4 hacia arriba (J4 decrece).
                found = edge(joint, rest - 0.02 if joint == 3 else rest, -1e-5 if joint == 3 else -1e-4)
                self.assertAlmostEqual(found * UNITS[joint], edges[joint], delta=2)

    def test_both_extremes_have_a_magnet(self):
        # La planta falsa de las conversaciones usa los mismos flancos.
        harness = (ROOT / "firmware" / "test" / "conversacion.cpp").read_text(encoding="utf-8")
        low = [int(v) for v in re.search(r"MAGNET_LOW\[scara::MOTOR_COUNT\] = \{([^}]*)\}", harness).group(1).split(",")]
        high = [int(v) for v in re.search(r"MAGNET_HIGH\[scara::MOTOR_COUNT\] = \{([^}]*)\}", harness).group(1).split(",")]
        self.assertEqual(low, config_array("HALL_EDGE"))
        # El firmware compara con los dos flancos al buscar pasos perdidos (D65).
        self.assertEqual(high, config_array("HALL_FAR_EDGE"))
        for joint in range(4):
            with self.subTest(joint=f"J{joint + 1}"):
                start, step = (0.0, 1e-4) if joint < 3 else (0.06, 1e-5)
                self.assertAlmostEqual(edge(joint, start, step) * UNITS[joint], high[joint], delta=2)

    def test_the_rest_pose_only_activates_j4(self):
        # Desde el reposo, solo J4 (abajo) está sobre un imán: el de fin.
        self.assertEqual([active(joint, 0.12 if joint == 3 else 0.0) for joint in range(4)],
                         [False, False, False, True])

    def test_the_width_matches_the_firmware(self):
        # Del flanco al tope, la zona activa mide HALL_WIDTH.
        widths = config_array("HALL_WIDTH")
        limits = (13500, 13500, 15000, 0)
        edges = config_array("HALL_EDGE")
        for joint in range(4):
            with self.subTest(joint=f"J{joint + 1}"):
                self.assertEqual(abs(limits[joint] - abs(edges[joint])), widths[joint])


if __name__ == "__main__":
    unittest.main()
