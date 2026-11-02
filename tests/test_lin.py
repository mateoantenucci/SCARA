"""Tramo LIN y validación previa como módulos puros (seam 2 de la spec #2)."""

import math
import unittest

from scara.collisions import CollisionChecker
from scara.kinematics import forward, load_config
from urc import planner, validation
from urc.planner import SEGMENT_MS, plan_lin
from urc.validation import Rejection, check_lin, check_ptp, check_tramo


CONFIG = load_config()
LIMITS = planner.default_limits(CONFIG)
CHECKER = CollisionChecker(CONFIG)


def pose(radius, angle, z, heading, elbow=-1):
    """Configuración para un punto de herramienta en coordenadas polares (mm y grados)."""
    a = math.radians(angle)
    return planner.joints_from_pose(radius * math.cos(a), radius * math.sin(a), z, heading, elbow, CONFIG)


def tool(units):
    return [v * 1000 for v in forward(planner.units_to_si(units), CONFIG)[:3]]


def off_line(point, origin, end):
    """Distancia en mm de un punto a la recta origin–end, calculada aparte del planificador."""
    path = [b - a for a, b in zip(origin, end)]
    s = sum((p - a) * d for p, a, d in zip(point, origin, path)) / sum(d * d for d in path)
    return math.dist(point, [a + d * s for a, d in zip(origin, path)])


START = pose(350, -16, 50, 0)
TARGET = pose(360, 23, 20, 30)


class LinTests(unittest.TestCase):
    def test_the_tool_stays_on_the_line(self):
        plan = plan_lin(START, TARGET, 0.5, LIMITS, CONFIG)
        self.assertEqual(plan.segments[-1][1], TARGET)
        origin, end = tool(START), tool(TARGET)
        tolerance = planner.lin_tolerance(CONFIG, LIMITS)
        # Lo que ejecuta el firmware: interpolación lineal en articulaciones
        # entre los destinos redondeados de cada segmento.
        worst, previous = 0.0, START
        for _, units in plan.segments:
            for u in (0.1, 0.3, 0.5, 0.7, 0.9, 1.0):
                q = [a + (b - a) * u for a, b in zip(previous, units)]
                worst = max(worst, off_line(tool(q), origin, end))
            previous = units
        self.assertLessEqual(worst, tolerance)
        self.assertLessEqual(plan.deviation, tolerance)
        self.assertAlmostEqual(plan.deviation, worst, delta=0.01)

    def test_tolerance_is_rounding_plus_chord(self):
        # Media centésima en J1 y J2 (una entera en el antebrazo): 0,0654 mm
        # en el plano, con J4, 0,0656. Cuerda con M1 y M2 a 90 °/s en 20 ms:
        # 1,8° por segmento, (250 + 250)·(1,8°)²/8 = 0,0617 mm.
        self.assertAlmostEqual(planner.lin_tolerance(CONFIG, LIMITS), 0.0656 + 0.0617, delta=0.0002)

    def test_the_heading_goes_along_with_the_tool(self):
        plan = plan_lin(START, TARGET, 1.0, LIMITS, CONFIG)
        origin, end = tool(START), tool(TARGET)
        length = math.dist(origin, end)
        for q in plan.samples:
            along = math.dist(origin, tool(q)) / length
            heading = (sum(q[:3]) - sum(START[:3])) / (sum(TARGET[:3]) - sum(START[:3]))
            self.assertAlmostEqual(along, heading, delta=0.001)

    def test_the_tool_moves_at_the_speed_of_the_tramo(self):
        # 50 % de 150 mm/s, con 150 mm/s² de rampa: trapecio en la recta.
        plan = plan_lin(START, TARGET, 0.5, LIMITS, CONFIG)
        length = math.dist(tool(START), tool(TARGET))
        self.assertAlmostEqual(plan.duration, length / 75 + 75 / 150, places=6)
        # Sin redondear: en 1,5 mm por segmento, el redondeo a la centésima
        # (hasta 0,066 mm) se notaría como velocidad.
        speeds, previous = [], tool(START)
        for units in plan.samples:
            point = tool(units)
            speeds.append(math.dist(previous, point) * 1000 / SEGMENT_MS)
            previous = point
        self.assertLessEqual(max(speeds), 75 + 0.2)
        # Los segmentos se estiran hasta entrar justos (D53): algo más lento.
        self.assertAlmostEqual(speeds[len(speeds) // 2], 75, delta=0.5)

    def test_a_vertical_line_goes_at_the_speed_of_j4(self):
        # La recta pediría 150 mm/s, pero solo mueve J4: 40 mm/s y 120 mm/s²
        # de M4, también escalados por la fracción (D76).
        start, target = pose(350, 0, 0, 0), pose(350, 0, 90, 0)
        for fraction in (1.0, 0.5):
            plan = plan_lin(start, target, fraction, LIMITS, CONFIG)
            speed, acceleration = 40 * fraction, 120 * fraction
            self.assertAlmostEqual(plan.duration, 90 / speed + speed / acceleration, places=6)

    def test_turning_in_place_keeps_the_tool_still(self):
        start, target = pose(350, 0, 30, -40), pose(350, 0, 30, 40)
        plan = plan_lin(start, target, 1.0, LIMITS, CONFIG)
        # Solo gira el rumbo: 80° a 90 °/s con 140 °/s².
        self.assertAlmostEqual(plan.duration, 80 / 90 + 90 / 140, places=6)
        self.assertLessEqual(plan.deviation, planner.lin_tolerance(CONFIG, LIMITS))
        self.assertTrue(all(q[:2] == start[:2] for _, q in plan.segments))

    def test_the_elbow_stays_on_its_side(self):
        start, target = pose(350, -30, 30, 0, elbow=1), pose(300, 40, 30, 0, elbow=1)
        plan = plan_lin(start, target, 1.0, LIMITS, CONFIG)
        self.assertEqual(plan.elbow, 1)
        self.assertTrue(all(q[1] > 0 for _, q in plan.segments))

    def test_from_the_stretched_arm_the_elbow_follows_the_other_end(self):
        stretched = (0, 0, 0, 6467)
        for elbow in (-1, 1):
            target = pose(400, 20 * elbow, 30, 0, elbow)
            plan = plan_lin(stretched, target, 1.0, LIMITS, CONFIG)
            self.assertEqual(plan.elbow, elbow)
            self.assertTrue(all(q[1] * elbow >= 0 for _, q in plan.segments))
        # Los dos extremos estirados: el codo preferido, J2 negativo (D31).
        plan = plan_lin(stretched, (2000, 0, 0, 6467), 1.0, LIMITS, CONFIG)
        self.assertEqual(plan.elbow, -1)
        self.assertTrue(all(q[1] <= 0 for _, q in plan.segments))

    def test_rejects_an_elbow_change_and_bad_arguments(self):
        with self.assertRaises(ValueError):
            plan_lin((3000, -6000, 1000, 6000), (3000, 6000, 1000, 6000), 1.0, LIMITS, CONFIG)
        for speed in (0, 1.5, True):
            with self.assertRaises(ValueError):
                plan_lin(START, TARGET, speed, LIMITS, CONFIG)

    def test_no_motion_needs_no_segments(self):
        plan = plan_lin(START, START, 1.0, LIMITS, CONFIG)
        self.assertEqual((plan.segments, plan.duration), ([], 0.0))


class ValidationTests(unittest.TestCase):
    def reject(self, start, target, speed=1.0, kind="LIN"):
        with self.assertRaises(Rejection) as caught:
            check_tramo(kind, start, target, speed, 3, LIMITS, CONFIG, CHECKER)
        rejection = caught.exception
        self.assertIn(f"Tramo 3 ({kind})", str(rejection))
        # Un LIN imposible sugiere PTP (D14), en el mensaje o, si primero
        # conviene bajar la velocidad, en el porqué.
        if kind == "LIN" and rejection.hint != "destino":
            self.assertIn("PTP", f"{rejection} {rejection.detail}")
        return rejection

    def test_a_valid_line_returns_its_plan(self):
        plan = check_lin(START, TARGET, 0.5, None, LIMITS, CONFIG, CHECKER)
        self.assertEqual(plan.segments[-1][1], TARGET)
        # El firmware rechaza con ERR 8 un segmento que supera la velocidad
        # de un motor por más de 2 centésimas (D51); el plan nunca.
        previous = START
        for ms, units in plan.segments:
            travel = planner.motor_travel([b - a for a, b in zip(previous, units)])
            for axis in range(4):
                self.assertLessEqual(abs(travel[axis]), LIMITS.motor_speed[axis] * ms / 1000 + 2)
            previous = units

    def test_out_of_reach_near_the_tower_axis(self):
        # La recta pasa a 103 mm del eje de J1; con J2 hasta ±135° el
        # extremo no llega a menos de 191 mm.
        rejection = self.reject(pose(300, -60, 30, 0), pose(300, 80, 30, 0))
        self.assertEqual(rejection.reason, "alcance")
        self.assertIn("103 mm", rejection.detail)
        self.assertIn("191 mm", rejection.detail)

    def test_elbow_change(self):
        rejection = self.reject((3000, -6000, 1000, 6000), (3000, 6000, 1000, 6000))
        self.assertEqual(rejection.reason, "codo")

    def test_joint_limit_along_the_way(self):
        # Por detrás del robot: los dos extremos están en su recorrido, pero
        # el camino lleva J1 o J3 más allá.
        rejection = self.reject(pose(480, 145, 30, 161, 1), pose(480, -115, 30, -115, 1))
        self.assertEqual(rejection.reason, "limite")
        # Un extremo fuera del recorrido, también.
        rejection = self.reject(START, (14000, -6000, 0, 6000))
        self.assertEqual(rejection.reason, "limite")
        self.assertIn("J1", str(rejection))

    def test_excessive_speed_near_the_stretched_arm(self):
        # Hacia el brazo estirado, el brazo y el antebrazo tienen que girar
        # cada vez más rápido para el mismo avance: al 100 % y al 50 % la
        # aceleración pasa la de M1; al 25 %, no.
        start, target = pose(470, 0, 30, 0), pose(498, 0, 30, 0)
        for fraction in (1.0, 0.5):
            rejection = self.reject(start, target, fraction)
            self.assertEqual(rejection.reason, "velocidad")
            self.assertIn("M1", str(rejection))
            self.assertIn("Bajá la velocidad", str(rejection))
        check_lin(start, target, 0.25, None, LIMITS, CONFIG, CHECKER)
        # Saliendo del brazo estirado no alcanza con ir más lento: es la singularidad.
        rejection = self.reject((0, 0, 0, 6467), pose(400, 0, 30, 0), 0.1)
        self.assertEqual(rejection.reason, "velocidad")
        self.assertIn("casi estirado", rejection.detail)
        self.assertIn("bajar la velocidad puede no alcanzar", rejection.detail)

    def test_collision_with_the_tower(self):
        # Los dos extremos están libres, pero la recta acerca el soporte del
        # efector a la torre.
        rejection = self.reject(pose(230, 20, 30, -40), pose(230, 60, 30, 0))
        self.assertEqual(rejection.reason, "colision")
        self.assertIn("Torre", str(rejection))

    def test_ptp_tramos_are_validated_too(self):
        plan = check_tramo("PTP", START, TARGET, 0.5, 1, LIMITS, CONFIG, CHECKER)
        self.assertEqual(plan.segments[-1][1], TARGET)
        # Codo plegado del todo: el antebrazo toca la torre (D30).
        rejection = self.reject((0, 0, 0, 12000), (0, 13500, 0, 12000), kind="PTP")
        self.assertEqual(rejection.reason, "colision")
        self.assertIn("puede chocar con", str(rejection))
        self.assertIn("Agregá un punto intermedio antes del destino", rejection.suggestion)
        self.assertEqual(self.reject(START, (14000, 0, 0, 6000), kind="PTP").reason, "limite")
        with self.assertRaises(ValueError):
            check_tramo("CIRC", START, TARGET, 0.5, 1, LIMITS, CONFIG, CHECKER)

    def test_a_ptp_brings_back_a_pose_outside_the_travel(self):
        # Desde fuera del recorrido (un jog o el redondeo a pasos junto al
        # límite), un PTP lo trae de vuelta.
        check_ptp((13503, 0, 0, 12000), (0, 0, 0, 12000), 1.0, None, LIMITS, CONFIG, CHECKER)
        check_ptp((14000, 0, 0, 12000), (9000, 0, 0, 12000), 1.0, None, LIMITS, CONFIG, CHECKER)
        rejection = self.reject((0, 0, 0, 12000), (0, 0, 0, 12500), kind="PTP")
        self.assertIn("J4 fuera de su recorrido en el destino", str(rejection))
        self.assertEqual(rejection.detail, "En el destino, J4 = 125 mm, y su recorrido va de 0 mm a 120 mm.")

    def test_a_rejection_is_a_short_message_and_a_detail(self):
        rejection = Rejection("codo", "el codo cambia de lado", "J2 cambia de signo.", tramo=2, hint="negativo")
        self.assertIsInstance(rejection, ValueError)
        self.assertEqual(str(rejection), "Tramo 2 (LIN): el codo cambia de lado. Usá un tramo PTP.")
        self.assertEqual(rejection.detail, "J2 cambia de signo. También podés grabar el destino con J2 negativo, "
                                           "del mismo lado que el inicio.")
        self.assertEqual(set(validation.REASONS), {"alcance", "codo", "limite", "velocidad", "colision"})

    def test_a_rejection_names_the_points_and_what_to_change(self):
        # La vuelta del loop usa el tipo y la velocidad del punto 1 (D32): el
        # mensaje dice de qué punto a qué punto y que hay que cambiar el 1.
        place = validation.Place("de vuelta", "punto 4", "punto 1", 1)
        rejection = self.reject_at((3000, -6000, 1000, 6000), (3000, 6000, 1000, 6000), place)
        self.assertEqual(str(rejection), "Tramo de vuelta del loop (punto 4 → punto 1, LIN): el codo cambia de lado. "
                                         "Cambiá el punto 1 a PTP.")
        self.assertTrue(rejection.detail.startswith("En el punto 4, J2 = -60°, y en el punto 1, J2 = 60°"))
        self.assertIn("También podés grabar el punto 1 con J2 negativo, del mismo lado que el punto 4.",
                      rejection.detail)
        self.assertIn("La vuelta del loop usa el tipo y la velocidad del punto 1.", rejection.detail)
        place = validation.Place(3, "punto 2", "punto 3", 3)
        rejection = self.reject_at(pose(470, 0, 30, 0), pose(498, 0, 30, 0), place)
        self.assertEqual(str(rejection), "Tramo 3 (punto 2 → punto 3, LIN): M1 (J1) no da la aceleración que pide "
                                         "la recta. Bajá la velocidad del punto 3 o la global.")
        self.assertIn("Si no alcanza, cambiá el punto 3 a PTP.", rejection.detail)
        place = validation.Place(0, "pose actual", "punto 1", 1)
        rejection = self.reject_at((0, 0, 0, 12000), (0, 13500, 0, 12000), place, "PTP")
        self.assertTrue(str(rejection).startswith("Tramo 0 (pose actual → punto 1, PTP de aproximación): "))
        self.assertTrue(str(rejection).endswith("Llevá el robot con jog a una pose más despejada."))
        place = validation.Place(None, "pose actual", "punto 2")
        rejection = self.reject_at(START, (14000, 0, 0, 6000), place, "PTP")
        self.assertEqual(str(rejection), "Movimiento PTP (pose actual → punto 2): J1 fuera de su recorrido en el "
                                         "punto 2. Corregí el punto 2.")
        self.assertEqual(rejection.detail, "En el punto 2, J1 = 140°, y su recorrido va de -135° a 135°.")

    def reject_at(self, start, target, place, kind="LIN"):
        with self.assertRaises(Rejection) as caught:
            check_tramo(kind, start, target, 1.0, place, LIMITS, CONFIG, CHECKER)
        return caught.exception


if __name__ == "__main__":
    unittest.main()
