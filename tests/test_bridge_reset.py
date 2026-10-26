import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from scara.runtime import Runtime


class ResetTrialTests(unittest.TestCase):
    def test_reset_validates_id_before_stopping_and_reloading(self):
        path = Path(__file__).resolve().parents[1] / 'webots/controllers/scara_bridge/scara_bridge.py'
        spec = importlib.util.spec_from_file_location('scara_bridge_test', path)
        bridge = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'controller': types.SimpleNamespace(Supervisor=MagicMock())}):
            spec.loader.exec_module(bridge)

        for request_id, valid in [(None, True), ('x' * 80, True), (42, False),
                                  (True, False), ([], False), ('x' * 81, False)]:
            with self.subTest(id=request_id):
                robot = MagicMock()
                robot.step.side_effect = [0, -1]
                robot.getBasicTimeStep.return_value = 32
                robot.getTime.return_value = 0
                server = MagicMock()
                server.client = None
                server.lost = False
                server.poll.side_effect = [[{'command': 'reset_trial', 'id': request_id}], []]
                runtime = Runtime()
                runtime.stop = MagicMock(wraps=runtime.stop)
                with patch.object(bridge, 'Supervisor', return_value=robot), \
                     patch.object(bridge, 'Server', return_value=server), \
                     patch.object(bridge, 'Runtime', return_value=runtime), \
                     patch.object(sys, 'argv', ['scara_bridge']):
                    bridge.main()
                event = server.send.call_args_list[0].args[0]
                if valid:
                    self.assertEqual(event['event'], 'accepted')
                    self.assertEqual(event['id'], request_id)
                    runtime.stop.assert_called_once()
                    robot.worldReload.assert_called_once()
                    self.assertEqual(server.poll.call_count, 2)
                else:
                    self.assertEqual(event['event'], 'rejected')
                    self.assertIsNone(event['id'])
                    runtime.stop.assert_not_called()
                    robot.worldReload.assert_not_called()
                    self.assertEqual(server.poll.call_count, 1)


if __name__ == '__main__':
    unittest.main()
