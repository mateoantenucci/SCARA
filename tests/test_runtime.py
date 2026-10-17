import unittest

from scara.runtime import Runtime


class RuntimeTests(unittest.TestCase):
    def test_motion_rejection_does_not_replace_accepted_motion(self):
        r = Runtime()
        self.assertEqual(r.handle({"command": "rearm"}, 0)["event"], "accepted")
        self.assertEqual(r.handle({"command": "move_joints", "id": "1", "positions": [0.2, 1, -1, 0.08]}, 0)["event"], "accepted")
        motion = r.motion
        self.assertEqual(r.handle({"command": "move_joints", "positions": [10, 1, 1, 0]}, 0.1)["event"], "rejected")
        self.assertIs(r.motion, motion)
        self.assertEqual(r.advance(100)[0]["event"], "completed")
        self.assertEqual(r.estimated, [0.2, 1, -1, 0.08])

    def test_effort_loss_persists_when_stopped_and_rearm_is_explicit(self):
        r = Runtime()
        r.handle({"command": "fault", "kind": "effort_loss", "axis": 4, "factor": 0}, 0)
        r.stop()
        self.assertEqual(r.effort_factors(), [1, 1, 1, 0])
        self.assertEqual(r.handle({"command": "rearm"}, 0)["event"], "rejected")
        r.handle({"command": "clear_faults"}, 0)
        self.assertEqual(r.mode, "STOPPED")
        self.assertEqual(r.effort_factors(), [1, 1, 1, 0])
        self.assertFalse(r.reference_valid)
        self.assertEqual(r.handle({"command": "rearm"}, 0)["event"], "rejected")
        self.assertEqual(r.mode, "STOPPED")

    def test_hall_injection_does_not_change_physical_reference(self):
        r = Runtime()
        start = list(r.commanded)
        r.handle({"command": "fault", "kind": "hall_stuck", "axis": 1, "factor": 1}, 0)
        self.assertEqual(r.hall_output([False]*4), [True, False, False, False])
        self.assertEqual(r.commanded, start)

    def test_known_overload_latches_reference_and_cannot_be_removed_to_restart_motion(self):
        r = Runtime()
        r.handle({"command": "rearm"}, 0)
        self.assertEqual(r.handle({"command": "payload", "mass": 1}, 0)["event"], "accepted")
        self.assertEqual(r.mode, "FAULT")
        self.assertIn("overload:J4", r.faults)
        self.assertFalse(r.reference_valid)
        self.assertEqual(r.effort_factors(), [1]*4)
        r.handle({"command": "clear_faults"}, 0)
        self.assertEqual(r.handle({"command": "payload", "mass": 0}, 0)["event"], "rejected")
        self.assertEqual(r.payload_mass, 1)
        self.assertEqual(r.handle({"command": "rearm"}, 0)["event"], "rejected")

    def test_disconnect_cancels_trajectory_without_advancing_estimate(self):
        r = Runtime()
        r.handle({"command": "rearm"}, 0)
        r.handle({"command": "move_joints", "positions": [0.2, 1, -1, 0.08]}, 0)
        r.advance(0.5)
        position = list(r.estimated)
        r.stop()
        r.advance(100)
        self.assertEqual(r.estimated, position)
        self.assertEqual(r.mode, "STOPPED")


if __name__ == "__main__":
    unittest.main()
