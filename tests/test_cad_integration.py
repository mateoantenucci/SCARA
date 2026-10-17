import math
import random
import unittest
import json
from pathlib import Path

from scara.frames import chain_frames, multiply, rigid_inverse, transform_point
from scara.kinematics import forward, load_config
from tools.integrate_cad import derive


class CADIntegrationTests(unittest.TestCase):
    def test_wrist_pulley_uses_shoulder_and_rotates_with_the_bushing(self):
        cad = derive()
        parts = {p['instance_name']: p for p in cad['instances']}
        pulley = parts['2GT_80Teet_40Bore-registro-R']
        bushing = parts['Z-BujeExterior-1']
        self.assertEqual(pulley['group'], 'wrist')
        self.assertTrue(pulley['meshes'])
        # Escalón medido en el buje: Z=31 mm. La pose B invade ese escalón.
        relative = multiply(rigid_inverse(bushing['body_from_piece']), pulley['body_from_piece'])
        self.assertLess(math.dist(transform_point(relative, [0, 0, 0]), [0, 0, .031]), 1e-10)
        for angle in (-math.pi/2, 0, math.pi/2):
            q = list(cad['saved_joint_reference'])
            q[2] = angle
            frames = chain_frames(q, load_config())
            placed = multiply(frames['wrist'], pulley['body_from_piece'])
            support = multiply(frames['wrist'], bushing['body_from_piece'])
            self.assertLess(math.dist(transform_point(placed, [0, 0, 0]),
                                      transform_point(support, [0, 0, .031])), 1e-10)

    def test_output_pulleys_follow_the_driven_link(self):
        cad = derive()
        parts = {p['instance_name']: p for p in cad['instances']}
        # Lado de salida sustentado por ejes, aprietes y transmisión del maestro.
        # Unirlas a base/brazo respectivamente dejaría inmóvil la polea de salida.
        for name, group in (('2GT_80Teet_16Bore-registro-1', 'arm'),
                            ('2GT_60Teet_8Bore-registro-1', 'forearm')):
            part = parts[name]
            self.assertEqual(part['group'], group)
            self.assertTrue(part['meshes'])
            self.assertTrue(part['registration_evidence'])
            self.assertIsNone(part['placement_correction'])

    def test_wrist_cap_and_bearings_use_the_coherent_housing_assembly(self):
        cad = derive()
        parts = {p['instance_name']: p for p in cad['instances']}
        root = Path(__file__).resolve().parents[1]
        source = json.loads((root/'cad/ensambles/informe.json').read_text())
        rotation = next(a for a in source['assemblies']
                        if Path(a['source']).stem == 'R-EnsambleRotacion')
        source_parts = {p['instance_name']:p for p in rotation['configurations'][0]['instances']}
        anchor = parts['R-Bancada-1']['saved_object_to_assembly']
        expected = multiply(anchor, multiply(
            rigid_inverse(source_parts['R-Bancada-1']['transform_object_to_assembly_m']),
            source_parts['R-ContraBancada-1']['transform_object_to_assembly_m']))
        actual = parts['R-ContraBancada-1']['saved_object_to_assembly']
        self.assertLess(max(abs(a-b) for ar,br in zip(actual,expected)
                            for a,b in zip(ar,br)), 1e-10)
        for name in ('Z-6907-2RS-registro-1', 'Z-6907-2RS-registro-2'):
            self.assertEqual(parts[name]['group'], 'forearm')
            self.assertTrue(parts[name]['meshes'])

    def test_saved_assembly_and_joint_lines_survive_articulation(self):
        config = load_config()
        cad = derive(config)
        parts = {entry['instance_name']: entry for entry in cad['instances']}
        frames = chain_frames(cad['saved_joint_reference'], config)
        for entry in cad['instances']:
            reconstructed = multiply(frames[entry['group']], entry['body_from_piece'])
            self.assertLess(max(abs(a-b) for ar,br in zip(reconstructed,entry['canonical_object_pose'])
                                for a,b in zip(ar,br)), 1e-10)
        rng = random.Random(42)
        for _ in range(30):
            q = [rng.uniform(low+.01,high-.01) for low,high in config['limits']]
            frames = chain_frames(q, config)
            def point(name, local):
                entry = parts[name]
                return transform_point(multiply(frames[entry['group']],entry['body_from_piece']),local)
            # Centros de agujeros independientes obtenidos de las superficies CAD.
            shoulder = point('A-Brazo-1',[0,0,.03])
            elbow_arm = point('A-Brazo-1',[0,0,.28])
            elbow_forearm = point('B-Antebrazo-1',[0,0,.22])
            wrist = point('Z-BujeExterior-1',[0,0,.028])
            tcp = point('Z-SoporteEfector-1',[0,0,0])
            self.assertLess(math.dist(shoulder[:2],[0,0]),1e-10)
            self.assertLess(math.dist(elbow_arm[:2],elbow_forearm[:2]),1e-10)
            self.assertAlmostEqual(math.dist(shoulder[:2],elbow_arm[:2]),.25,places=10)
            self.assertAlmostEqual(math.dist(elbow_forearm[:2],wrist[:2]),.25,places=10)
            self.assertLess(math.dist(tcp,forward(q,config)[:3]),1e-10)
