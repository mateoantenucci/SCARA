"""Planificador del jog verificado como módulo puro (D28, D75)."""

import math
import unittest

from scara.collisions import CollisionChecker
from scara.kinematics import load_config
from urc import jog, planner
from urc.jog import Blocked, Command


REST = (0.0, 0.0, 0.0, 12000.0)


def motor_rates(before, after):
    """Velocidad de cada articulación y de cada motor en un segmento, en centésimas por segundo."""
    delta = [b - a for a, b in zip(before, after)]
    seconds = jog.SEGMENT_MS / 1000
    return [abs(d) / seconds for d in delta + list(planner.motor_travel(delta))]


class JogStepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.checker = CollisionChecker(cls.config)
        cls.travel = planner.travel(cls.config)

    def step(self, q, mode, axis, direction, slow=False, elbow=None):
        command = Command(mode, axis, direction, slow)
        return jog.step(q, command, jog.elbow_of(q) if elbow is None else elbow,
                        self.config, self.checker, self.travel)

    def run_until_blocked(self, q, mode, axis, direction, limit=2000):
        """Pasos hasta que el jog frena; devuelve los visitados y el motivo."""
        visited, elbow = [q], jog.elbow_of(q)
        for _ in range(limit):
            try:
                visited.append(self.step(visited[-1], mode, axis, direction, elbow=elbow))
            except Blocked as exc:
                return visited, str(exc)
        self.fail("El jog no frenó")

    def test_joint_jog_moves_one_joint_at_its_speed(self):
        q = (1000.0, -2000.0, 0.0, 6000.0)
        for axis in range(1, 5):
            with self.subTest(axis=axis):
                fast = self.step(q, "articular", axis, -1)
                slow = self.step(q, "articular", axis, -1, slow=True)
                expected = [0.0] * 4
                expected[axis - 1] = -jog.JOINT_SPEED[0] * jog.SEGMENT_MS / 1000
                self.assertEqual([b - a for a, b in zip(q, fast)], expected)
                expected[axis - 1] = -jog.JOINT_SPEED[1] * jog.SEGMENT_MS / 1000
                self.assertEqual([b - a for a, b in zip(q, slow)], expected)

    def test_cartesian_jog_moves_the_tool_point_along_one_axis(self):
        q = (3000.0, -6000.0, 1000.0, 6000.0)
        x, y, z = planner.tool_point(q, self.config)
        heading = sum(q[:3])
        for axis, moved in ((2, 0), (1, 1)):  # W/S mueven X; A/D, Y
            with self.subTest(axis=axis):
                after = self.step(q, "cartesiano", axis, 1)
                point = planner.tool_point(after, self.config)
                # Solo cambia esa coordenada, hasta lo que avanza en 20 ms (o
                # menos, si un motor llegaría a la velocidad sin rampa).
                advance = point[moved] - (x, y, z)[moved]
                self.assertGreater(advance, 0)
                self.assertLessEqual(advance, jog.TOOL_SPEED[0] / 1000 * jog.SEGMENT_MS / 1000 + 1e-12)
                for index, (got, want) in enumerate(zip(point, (x, y, z))):
                    if index != moved:
                        self.assertAlmostEqual(got, want, places=9)
                self.assertAlmostEqual(sum(after[:3]), heading, places=6)
                self.assertEqual(after[3], q[3])
                self.assertLess(after[1], 0)
        # R/F: solo J4 (R sube, J4 baja de valor); Q/E: solo J3, el rumbo.
        up = self.step(q, "cartesiano", 4, -1)
        self.assertEqual(up, q[:3] + (q[3] - jog.JOINT_SPEED[0] * jog.SEGMENT_MS / 1000,))
        turn = self.step(q, "cartesiano", 3, 1, slow=True)
        self.assertEqual(turn, (q[0], q[1], q[2] + jog.JOINT_SPEED[1] * jog.SEGMENT_MS / 1000, q[3]))

    def test_no_motor_goes_faster_than_the_jog_without_ramp(self):
        # Cerca del brazo estirado y cerca de la torre, la cinemática inversa
        # pide giros rápidos: el paso se acorta.
        for q in ((0.0, -900.0, 0.0, 6000.0), (0.0, -13000.0, 0.0, 6000.0), (2000.0, 9000.0, -3000.0, 6000.0)):
            for axis in (1, 2):
                for direction in (-1, 1):
                    with self.subTest(q=q, axis=axis, direction=direction):
                        try:
                            after = self.step(q, "cartesiano", axis, direction)
                        except Blocked:
                            continue
                        self.assertLessEqual(max(motor_rates(q, after)), jog.NO_RAMP_SPEED + 1e-6)

    def test_cartesian_jog_never_changes_the_elbow(self):
        # Hacia afuera, el brazo se estira: frena antes, con J2 del mismo signo.
        for elbow in (-1, 1):
            with self.subTest(elbow=elbow):
                visited, reason = self.run_until_blocked((0.0, elbow * 3000.0, 0.0, 6000.0), "cartesiano", 2, 1)
                self.assertIn("borde del alcance", reason)
                self.assertTrue(all(q[1] * elbow >= jog.ELBOW_MIN for q in visited))

    def test_from_the_stretched_arm_it_takes_the_preferred_elbow(self):
        self.assertEqual(jog.elbow_of(REST), -1)
        self.assertEqual(jog.elbow_of((0, 1, 0, 0)), 1)
        with self.assertRaisesRegex(Blocked, "borde del alcance"):
            self.step(REST, "cartesiano", 2, 1)
        with self.assertRaisesRegex(Blocked, "borde del alcance"):
            self.step(REST, "cartesiano", 1, 1)
        inward = self.step(REST, "cartesiano", 2, -1)
        self.assertLess(inward[1], 0)
        # Hacia adentro sigue aunque todavía esté casi estirado.
        self.assertLess(self.step(inward, "cartesiano", 2, -1)[1], inward[1])

    def test_jog_stops_before_the_end_of_travel(self):
        with self.assertRaisesRegex(Blocked, r"J4 llegó al límite de su recorrido \(120 mm\)"):
            self.step(REST, "articular", 4, 1)
        with self.assertRaisesRegex(Blocked, r"J4 llegó al límite de su recorrido \(120 mm\)"):
            self.step(REST, "cartesiano", 4, 1)
        with self.assertRaisesRegex(Blocked, r"J1 llegó al límite de su recorrido \(135°\)"):
            self.step((13490.0, 0.0, 0.0, 6000.0), "articular", 1, 1)
        # Desde afuera (el redondeo a pasos) puede volver, no seguir.
        self.assertEqual(self.step((0.0, 0.0, 0.0, 12050.0), "articular", 4, -1)[3], 12030.0)
        with self.assertRaises(Blocked):
            self.step((0.0, 0.0, 0.0, 12050.0), "articular", 4, 1)
        # En el jog cartesiano frena la articulación que llega primero.
        visited, reason = self.run_until_blocked((0.0, -9000.0, 12000.0, 6000.0), "cartesiano", 2, -1)
        self.assertIn("J3 llegó al límite", reason)
        self.assertTrue(all(planner.out_of_range([round(v) for v in q], self.config) is None for q in visited))

    def test_jog_stops_before_the_margin_of_an_obstacle(self):
        # Con J4 abajo, el soporte Z llega a la zona de margen del pedestal
        # desde J2 ≈ 107,4°.
        visited, reason = self.run_until_blocked((0.0, 10000.0, 0.0, 12000.0), "articular", 2, 1)
        self.assertIn("Z-SoporteEfector-1 tocaría pedestal_de_ensayo", reason)
        last = planner.inside_range(visited[-1], self.config)
        self.assertGreaterEqual(self.checker.clearance(last), self.checker.margin)
        # Desde dentro de la zona puede salir.
        inside = (0.0, 10760.0, 0.0, 12000.0)
        self.assertLess(self.checker.clearance(planner.inside_range(inside, self.config)), self.checker.margin)
        self.assertLess(self.step(inside, "articular", 2, -1)[1], inside[1])
        with self.assertRaises(Blocked):
            self.step(inside, "articular", 2, 1)


if __name__ == "__main__":
    unittest.main()
