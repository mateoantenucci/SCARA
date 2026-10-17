import math
import random
import unittest

from scara.frames import chain_frames, multiply, transform_point
from scara.kinematics import forward, load_config
from tools.integrate_cad import derive


class CADIntegrationTests(unittest.TestCase):
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
