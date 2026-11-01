"""Regresiones del pedestal: límites, barrido nominal y carga de ensayo.

Las poses invasivas también se contrastaron con BREP; los tests no requieren OCP.
El muestreo final complementa la cota continua, no la reemplaza.
"""

import copy
import itertools
import json
import math
from pathlib import Path
import random
import unittest

from scara.collisions import CollisionChecker
from scara.frames import chain_frames, multiply, transform_point
from scara.kinematics import forward, load_config


ROOT = Path(__file__).resolve().parents[1]


def pose(j1=0, j2=135, j3=-135, j4=.12):
    return [math.radians(j1), math.radians(j2), math.radians(j3), j4]


class CollisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.checker = CollisionChecker(cls.config)
        cls.cad = json.loads((ROOT/'cad/ensambles/integracion_articulada.json').read_text())

    def test_nominal_demonstration_routes_remain_available(self):
        initial = self.config['initial_positions']
        routes = [(initial, [.2, 1, -1, .08]),
                  (initial, self.cad['saved_joint_reference']),
                  (initial, pose(0, 90, -90, 0)),
                  (initial, pose(0, 90, -90, .12))]
        q = list(initial)
        for axis, delta in enumerate((.12, -.12, .12, .015)):
            target = list(q)
            target[axis] += delta
            routes.append((q, target))
            q = target
        for start, target in routes:
            with self.subTest(start=start, target=target):
                self.assertIsNone(self.checker.first_conflict(start, target))

    def test_folded_piston_and_missing_effector_envelopes_are_preserved(self):
        # BREP del pistón: 0.543954881 cm³ dentro del pedestal a J4=120 mm.
        for j2 in (-135, 135):
            q = pose(j2=j2, j3=-j2)
            conflict = self.checker.first_conflict(q, q)
            self.assertEqual(conflict['instance'], 'Z-Piston-1')
            self.assertEqual(conflict['obstacle'], 'pedestal_de_ensayo')
        # A 100 mm el pistón todavía está arriba; falta el BREP del soporte.
        q = pose(j4=.1)
        conflict = self.checker.first_conflict(q, q)
        self.assertEqual(conflict['instance'], 'Z-SoporteEfector-1')

    def test_clear_endpoints_do_not_allow_an_invasive_middle(self):
        start, middle, target = pose(-60, 120, 0), pose(-15, 120, 0), pose(30, 120, 0)
        self.assertIsNone(self.checker.first_conflict(start, start))
        self.assertIsNone(self.checker.first_conflict(target, target))
        self.assertEqual(self.checker.first_conflict(middle, middle)['instance'], 'Z-Piston-1')
        for a, b in ((start, target), (target, start)):
            conflict = self.checker.first_conflict(a, b)
            self.assertEqual(conflict['obstacle'], 'pedestal_de_ensayo')
            self.assertGreater(conflict['path_interval'][0], 0)
            self.assertLess(conflict['path_interval'][1], 1)
            self.assertLessEqual(conflict['displacement_bound_m'],
                                 self.config['collision_check']['interval_bound_m'])

    def test_one_millimeter_margin_applies_before_geometric_contact(self):
        # Lejos de la torre: aislar el margen frente al pedestal.
        clear, near = pose(-15, 120, -105, .093), pose(-15, 120, -105, .094)
        self.assertIsNone(self.checker.first_conflict(clear, clear))
        self.assertEqual(self.checker.first_conflict(near, near)['instance'],
                         'Z-SoporteEfector-1')
        no_margin = copy.deepcopy(self.config)
        no_margin['collision_check']['margin_m'] = 0
        self.assertIsNone(CollisionChecker(no_margin).first_conflict(near, near))

    def test_clearance_is_the_static_measure_of_the_margin(self):
        clear, near = pose(-15, 120, -105, .093), pose(-15, 120, -105, .094)
        self.assertGreater(self.checker.clearance(clear), self.checker.margin)
        self.assertLess(self.checker.clearance(near), self.checker.margin)
        self.assertGreater(self.checker.clearance(near), 0)

    def test_a_path_can_leave_the_margin_zone_but_not_go_deeper(self):
        # QA R3: con pasos chicos el PTP llegó a J2 = 107,33°, a menos de
        # 0,5 mm de la zona de margen del pedestal. Desde ahí no se demuestra
        # la separación al arrancar, y todo camino se rechazaba.
        inside = pose(0, 107.33, 0)
        self.assertIsNotNone(self.checker.first_conflict(inside, pose(0, 100, 0)))
        for away in (pose(0, 100, 0), pose(0, 30, 0), pose(0, 100, 0, .05)):
            self.assertIsNone(self.checker.first_conflict_leaving(inside, away), away)
        for deeper in (pose(0, 108, 0), pose(0, 107.4, 0)):
            self.assertIsNotNone(self.checker.first_conflict_leaving(inside, deeper), deeper)
        # Si después de salir el camino choca igual, se rechaza.
        self.assertIsNotNone(self.checker.first_conflict_leaving(inside, pose(0, 135, -135)))

    def test_folded_tool_cannot_enter_the_fixed_tower(self):
        # Cuatro invasiones verificadas con los sólidos CAD, sin tocar pedestal.
        for shoulder, elbow in ((0, 135), (0, -135), (45, 135), (-45, -135)):
            q = pose(shoulder, elbow, -elbow, .06)
            with self.subTest(shoulder=shoulder, elbow=elbow):
                conflict = self.checker.first_conflict(q, q)
                self.assertIsNotNone(conflict)
                self.assertIn(conflict['obstacle'],
                              [p['instance_name'] for p in self.cad['instances']
                               if p['group'] == 'base'])

    def test_free_endpoints_do_not_allow_crossing_the_tower(self):
        start, target = pose(-90, 135, -135, .06), pose(90, 135, -135, .06)
        for q in (start, target):
            self.assertIsNone(self.checker.first_conflict(q, q))
        for a, b in ((start, target), (target, start)):
            conflict = self.checker.first_conflict(a, b)
            self.assertEqual(conflict['obstacle'], '0-Torre-1')
            self.assertGreater(conflict['path_interval'][0], 0)
            self.assertLess(conflict['path_interval'][1], 1)

    def test_impractical_resolution_rejects_instead_of_blocking_the_controller(self):
        config = copy.deepcopy(self.config)
        config['collision_check']['interval_bound_m'] = 1e-300
        conflict = CollisionChecker(config).first_conflict(pose(-60,120,0),pose(30,120,0))
        self.assertIsNotNone(conflict)
        self.assertIn('agotad',conflict['reason'])

    def test_payload_cube_can_block_a_route_with_clear_tool(self):
        start, target = pose(-15, 120, -105, .06), pose(-15, 120, -105, .08)
        self.assertIsNone(self.checker.first_conflict(start, target))
        self.assertIsNone(self.checker.first_conflict(start, start, payload=.1))
        conflict = self.checker.first_conflict(start, target, payload=.1)
        self.assertEqual(conflict['instance'], 'carga_cubica_de_ensayo')
        self.assertEqual(conflict['obstacle'], 'pedestal_de_ensayo')

    def test_accepted_paths_are_clear_in_independent_sampled_placements(self):
        rng = random.Random(81)
        accepted = 0
        for _ in range(16):
            start, target = [[rng.uniform(lo, hi) for lo, hi in self.config['limits']]
                             for _ in range(2)]
            if self.checker.first_conflict(start, target):
                continue
            accepted += 1
            for step in range(41):
                fraction = step/40
                q = [a+fraction*(b-a) for a, b in zip(start, target)]
                frames = chain_frames(q, self.config)
                for part in self.cad['instances']:
                    if part['group'] == 'base':
                        continue
                    # Colocar desde la caja original, sin usar vértices del checker.
                    bounds = part['bbox_local_m']
                    matrix = multiply(frames[part['group']], part['body_from_piece'])
                    points = [transform_point(matrix, p) for p in itertools.product(
                        *[(bounds[i], bounds[i+3]) for i in range(3)])]
                    low = [min(p[i] for p in points) for i in range(3)]
                    high = [max(p[i] for p in points) for i in range(3)]
                    for obstacle in self.config['environment']:
                        margin = self.config['collision_check']['margin_m']
                        separation = any(high[i] < obstacle['center'][i]-obstacle['size'][i]/2-margin
                                         or low[i] > obstacle['center'][i]+obstacle['size'][i]/2+margin
                                         for i in range(3))
                        self.assertTrue(separation, (start, target, step, part['instance_name'],
                                                     obstacle['name']))
        self.assertGreaterEqual(accepted, 4)


if __name__ == '__main__':
    unittest.main()
