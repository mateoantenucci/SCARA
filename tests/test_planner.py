"""Planificador PTP de la URC como módulo puro (seam 2 de la spec #2)."""

import math
from pathlib import Path
import re
import unittest

from scara.kinematics import forward, load_config
from urc import planner
from urc.planner import SEGMENT_MS, plan_ptp


ROOT = Path(__file__).resolve().parents[1]
START = (0, 0, 0, 12000)


def speeds(start, segments):
    """Velocidad media de cada segmento, en centésimas por segundo, por articulación."""
    result, previous = [], start
    for ms, units in segments:
        result.append([(b - a) * 1000 / ms for a, b in zip(previous, units)])
        previous = units
    return result


def motor(values):
    """Recorrido de cada motor en las unidades de su articulación: M2 sigue a J1 + J2."""
    return [values[0], values[0] + values[1], values[2], values[3]]


class PtpTests(unittest.TestCase):
    def setUp(self):
        self.limits = planner.default_limits()

    def check_within_limits(self, start, plan, speed=1.0):
        """Cada segmento respeta la velocidad y la aceleración de cada articulación y de cada motor.

        Las posiciones van redondeadas a la centésima: una centésima de más
        por articulación (dos para M2, que suma dos) en cada segmento.
        """
        rounding = 1000 / SEGMENT_MS
        previous = [0.0] * 4
        for index, velocity in enumerate(speeds(start, plan.segments) + [[0.0] * 4]):
            for joint in range(4):
                self.assertLessEqual(abs(velocity[joint]), self.limits.joint_speed[joint] * speed + rounding,
                                     (index, joint))
                acceleration = (velocity[joint] - previous[joint]) * 1000 / SEGMENT_MS
                self.assertLessEqual(abs(acceleration), self.limits.joint_acceleration[joint] + 2 * rounding ** 2,
                                     (index, joint))
            for axis, (now, before) in enumerate(zip(motor(velocity), motor(previous))):
                tolerance = 2 * rounding if axis == 1 else rounding
                self.assertLessEqual(abs(now), self.limits.motor_speed[axis] * speed + tolerance, (index, axis))
                acceleration = (now - before) * 1000 / SEGMENT_MS
                self.assertLessEqual(abs(acceleration), self.limits.motor_acceleration[axis] + 2 * tolerance * rounding,
                                     (index, axis))
            previous = velocity

    def test_all_joints_arrive_together(self):
        target = (4500, -3000, 6000, 8000)
        plan = plan_ptp(START, target)
        self.assertEqual(plan.segments[-1][1], target)
        self.assertTrue(all(ms == SEGMENT_MS for ms, _ in plan.segments))
        # Todas recorren la misma fracción de su camino en cada instante:
        # empiezan, aceleran, frenan y llegan juntas.
        for _, units in plan.segments:
            fractions = [(q - a) / (b - a) for q, a, b in zip(units, START, target)]
            self.assertLess(max(fractions) - min(fractions), 0.002, fractions)
        self.check_within_limits(START, plan)

    def test_the_most_demanding_axis_sets_the_time(self):
        # J4 recorre 120 mm con 40 mm/s y 120 mm/s²: trapecio de 0,33 s de
        # rampa y 3,33 s en total. J1 y J3 llegarían antes y no limitan.
        plan = plan_ptp(START, (3000, -3000, 6000, 0))
        self.assertAlmostEqual(plan.duration, 12000 / 4000 + 4000 / 12000, places=3)
        self.assertEqual(len(plan.segments), math.ceil(plan.duration * 1000 / SEGMENT_MS))
        peak = max(abs(v[3]) for v in speeds(START, plan.segments))
        self.assertAlmostEqual(peak, 4000, delta=60)

    def test_m2_follows_j1_plus_j2(self):
        # Con J1 y J2 en el mismo sentido, M2 recorre la suma: el tramo tarda
        # más que con cada articulación sola (D45).
        alone = plan_ptp(START, (9000, 0, 0, 12000))
        together = plan_ptp(START, (9000, 9000, 0, 12000))
        opposed = plan_ptp(START, (9000, -9000, 0, 12000))
        self.assertGreater(together.duration, alone.duration * 1.5)
        self.assertAlmostEqual(opposed.duration, alone.duration, places=6)
        self.check_within_limits(START, together)

    def test_j2_can_go_twice_as_fast_as_j1(self):
        # M1 deja a J1 en 90 °/s y M2, a J1 + J2. Con J1 en sentido contrario,
        # J2 llega a 180 °/s, dentro de los 3,5 rad/s del modelo (D76).
        start = (4500, -9000, 0, 12000)
        plan = plan_ptp(start, (-4500, 9000, 0, 12000))
        self.check_within_limits(start, plan)
        peak = max(abs(v[1]) for v in speeds(start, plan.segments))
        self.assertAlmostEqual(peak, 18000, delta=300)
        self.assertLess(peak, self.limits.joint_speed[1])

    def test_short_move_has_a_triangular_profile(self):
        plan = plan_ptp(START, (100, 0, 0, 12000))
        # 1° de J1 con 140 °/s²: sin llegar a velocidad máxima, 2·√(d/a).
        self.assertAlmostEqual(plan.duration, 2 * math.sqrt(100 / 14000), places=4)
        self.check_within_limits(START, plan)

    def test_starts_and_ends_at_rest(self):
        plan = plan_ptp(START, (4500, -3000, 6000, 8000))
        velocity = speeds(START, plan.segments)
        for joint in range(4):
            peak = max(abs(v[joint]) for v in velocity)
            self.assertLess(abs(velocity[0][joint]), 0.1 * peak)
            self.assertLess(abs(velocity[-1][joint]), 0.1 * peak)

    def test_speed_scales_the_maximum_speed(self):
        # La fracción baja la velocidad máxima; la aceleración queda (D53).
        full = plan_ptp(START, (9000, 0, 0, 12000))
        quarter = plan_ptp(START, (9000, 0, 0, 12000), speed=0.25)
        self.assertAlmostEqual(full.duration, 9000 / 9000 + 9000 / 14000, places=3)
        self.assertAlmostEqual(quarter.duration, 9000 / 2250 + 2250 / 14000, places=3)
        self.check_within_limits(START, quarter, speed=0.25)
        peak = max(abs(v[0]) for v in speeds(START, quarter.segments))
        self.assertAlmostEqual(peak, 2250, delta=30)

    def test_no_motion_needs_no_segments(self):
        plan = plan_ptp(START, START)
        self.assertEqual(plan.segments, [])
        self.assertEqual(plan.duration, 0)

    def test_segments_respect_the_firmware_check(self):
        # El firmware rechaza con ERR 8 un segmento que supera la velocidad de
        # un motor por más de 2 centésimas (transmission.h); el plan nunca.
        for target in ((13500, -13500, 15000, 0), (-13500, 13500, -15000, 0), (9000, 9000, 0, 12000)):
            plan = plan_ptp((-13500, 13500, -15000, 12000) if target[0] > 0 else START, target)
            previous = (-13500, 13500, -15000, 12000) if target[0] > 0 else START
            for ms, units in plan.segments:
                travel = motor([b - a for a, b in zip(previous, units)])
                for axis in range(4):
                    allowed = self.limits.motor_speed[axis] * ms / 1000 + 2
                    self.assertLessEqual(abs(travel[axis]), allowed, (target, axis))
                previous = units

    def test_rejects_bad_arguments(self):
        for start, target, speed in ((START, (0, 0, 0), 1), (START, (0, 0, 0, 1.5), 1), (START, START, 0),
                                     (START, START, 1.5), (START, (0, 0, 0, 100000), 1)):
            with self.subTest(target=target, speed=speed), self.assertRaises(ValueError):
                plan_ptp(start, target, speed)

    def test_motor_limits_match_the_firmware(self):
        # Los límites de D45 viven en firmware/config.h, por motor y en grados
        # de su eje; el planificador los usa en las unidades de cada
        # articulación: θM/4 en M1–M3 y 8 mm por vuelta en M4.
        text = (ROOT / "firmware" / "config.h").read_text(encoding="utf-8")

        def array(name):
            match = re.search(name + r"\[MOTOR_COUNT\] = \{([^}]*)\}", text)
            return [int(value) for value in match.group(1).split(",")]

        per_degree = (100 / 4, 100 / 4, 100 / 4, 80000 / 360 / 100)  # centésimas por grado de motor
        for axis in range(4):
            self.assertAlmostEqual(planner.MOTOR_SPEED[axis], array("MOTOR_MAX_SPEED")[axis] * per_degree[axis])
            self.assertAlmostEqual(planner.MOTOR_ACCELERATION[axis],
                                   array("MOTOR_MAX_ACCELERATION")[axis] * per_degree[axis])


class PoseTests(unittest.TestCase):
    def test_units_round_trip(self):
        units = (4500, -3000, 6000, 8000)
        self.assertEqual(planner.si_to_units(planner.units_to_si(units)), units)
        self.assertAlmostEqual(planner.units_to_si(units)[0], math.radians(45))
        self.assertAlmostEqual(planner.units_to_si(units)[3], 0.08)

    def test_pose_by_xyz_and_heading_uses_the_preferred_elbow(self):
        config = load_config()
        q = planner.units_to_si((3000, -6000, 1000, 6000))
        x, y, z, heading = forward(q, config)
        mm = (x * 1000, y * 1000, z * 1000)
        preferred = planner.joints_from_pose(*mm, math.degrees(heading), config=config)
        self.assertEqual(preferred, (3000, -6000, 1000, 6000))
        # Con el otro codo, el mismo punto con J2 positivo.
        other = planner.joints_from_pose(*mm, math.degrees(heading), elbow=1, config=config)
        self.assertGreater(other[1], 0)
        self.assertAlmostEqual(sum(other[:3]), sum(preferred[:3]), delta=2)

    def test_unreachable_pose_is_rejected(self):
        with self.assertRaises(ValueError):
            planner.joints_from_pose(900, 0, 100, 0)

    def test_check_target_rejects_limits_and_collisions(self):
        planner.check_target((0, 0, 0, 12000), (3000, -6000, 1000, 6000))
        with self.assertRaisesRegex(ValueError, "J1"):
            planner.check_target((0, 0, 0, 12000), (14000, 0, 0, 12000))
        with self.assertRaisesRegex(ValueError, "J4"):
            planner.check_target((0, 0, 0, 12000), (0, 0, 0, 12500))
        # Desde fuera del recorrido (un jog o el redondeo a pasos junto al
        # límite), un PTP lo trae de vuelta.
        planner.check_target((13503, 0, 0, 12000), (0, 0, 0, 12000))
        planner.check_target((14000, 0, 0, 12000), (9000, 0, 0, 12000))
        # Codo plegado del todo: el antebrazo toca la torre (D30).
        with self.assertRaisesRegex(ValueError, "Recorrido rechazado"):
            planner.check_target((0, 0, 0, 12000), (0, 13500, 0, 12000))


if __name__ == "__main__":
    unittest.main()
