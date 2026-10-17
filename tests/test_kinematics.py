import math
import random
import unittest

from scara.dynamics import box_with_payload
from scara.kinematics import forward, inverse, interpolate, load_config, trajectory_duration, validate_joints


class KinematicsTests(unittest.TestCase):
    def test_inverse_reconstructs_poses_and_preserves_heading(self):
        rng = random.Random(7)
        config = load_config()
        for _ in range(100):
            q = [rng.uniform(low + 1e-4, high - 1e-4) for low, high in config["limits"]]
            x, y, z, yaw = forward(q, config)
            recovered = inverse(x, y, z, yaw=yaw, current=q, config=config)
            actual = forward(recovered, config)
            for a, b in zip(actual[:3], (x, y, z)):
                self.assertAlmostEqual(a, b, places=10)
            self.assertAlmostEqual(math.sin(actual[3] - yaw), 0, places=10)
        current = config["initial_positions"]
        target = inverse(0.3, 0.2, forward(current)[2], current=current)
        self.assertAlmostEqual(forward(target)[3], forward(current)[3], places=10)
        pose = forward(current)
        for heading in (0, 2*math.tau, -2*math.tau):
            recovered = inverse(*pose[:3], yaw=heading, current=current)
            self.assertAlmostEqual(forward(recovered)[3], 0, places=10)

    def test_unreachable_nonfinite_and_limits_are_rejected(self):
        for xyz in ((1, 0, 0.03), (0.2, 0.2, 1), (0, 0, 0.03), (math.nan, 0, 0.03)):
            with self.assertRaises(ValueError):
                inverse(*xyz)
        for q in ([0, 0, 0, 0.2], [0, 0, math.inf, 0], [True, 0, 0, 0], [0, 0, 0]):
            with self.assertRaises(ValueError):
                validate_joints(q)

    def test_omitted_orientation_does_not_allow_a_full_turn_during_motion(self):
        current = [2, 1, 2, 0.06]
        target_pose = forward([-2, -1, 8-math.tau, 0.06])
        with self.assertRaises(ValueError):
            inverse(*target_pose[:3], current=current)
        start = load_config()["initial_positions"]
        target = inverse(0.3, 0.2, forward(start)[2], current=start)
        for i in range(101):
            self.assertAlmostEqual(sum(interpolate(start, target, i/100, 1)[:3]), sum(start[:3]), places=10)

    def test_quintic_respects_velocity_acceleration_and_endpoints(self):
        config = load_config()
        start = config["initial_positions"]
        target = [0.7, -0.7, 0.5, 0.1]
        duration = trajectory_duration(start, target, 0.6, config)
        steps = 2000
        dt = duration / steps
        samples = [interpolate(start, target, i*dt, duration) for i in range(steps+1)]
        self.assertEqual(samples[0], start)
        self.assertEqual(samples[-1], target)
        for axis in range(4):
            velocities = [(b[axis]-a[axis])/dt for a,b in zip(samples,samples[1:])]
            accelerations = [(b-a)/dt for a,b in zip(velocities,velocities[1:])]
            self.assertLessEqual(max(map(abs, velocities)), config["max_velocity"][axis]*0.6 + 1e-7)
            self.assertLessEqual(max(map(abs, accelerations)), config["max_acceleration"][axis]*0.6 + 1e-7)

    def test_payload_changes_mass_center_and_inertia(self):
        body = load_config()["body_properties"][-1]
        mass, center, inertia = box_with_payload(body, 0.5)
        self.assertAlmostEqual(mass, 0.65)
        self.assertLess(center[2], body["center"][2])
        self.assertTrue(all(v > 0 for v in inertia[:3]))
        for value in inertia[3:]:
            self.assertAlmostEqual(value, 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
