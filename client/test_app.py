"""Prueba del enlace real, sin instalar Webots: python3 -m unittest client.test_app."""

import json
import socket
import threading
import time
import unittest

from client.app import Bridge, MAX_FRAME, finite_json


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("No llegó el estado esperado del enlace TCP")


class LinkTest(unittest.TestCase):
    def test_fragmented_state_and_reconnect_do_not_replay_reset_trial(self):
        received, errors = [], []
        close_first, second_ready = threading.Event(), threading.Event()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(3)

            def webots_fake():
                try:
                    with listener.accept()[0] as first:
                        first.settimeout(3)
                        frame = json.dumps({"event": "state", "state": {"time": 12, "mode": "disabled", "estimated": [0, 0, 0, 0]}}).encode() + b"\n"
                        first.sendall(frame[:9])
                        time.sleep(0.02)
                        first.sendall(frame[9:])
                        raw = b""
                        while b"\n" not in raw:
                            raw += first.recv(1024)
                        received.append(json.loads(raw.split(b"\n")[0]))
                        first.sendall(json.dumps({"event": "accepted", "id": received[0]["id"]}).encode() + b"\n")
                        close_first.wait(3)
                    with listener.accept()[0] as second:
                        second.settimeout(0.35)
                        second_ready.set()
                        try:
                            received.append(second.recv(1024))
                        except socket.timeout:
                            pass
                except Exception as exc:
                    errors.append(exc)

            worker = threading.Thread(target=webots_fake, daemon=True)
            worker.start()
            bridge = Bridge(port=listener.getsockname()[1], retry_delay=0.03)
            try:
                wait_for(lambda: (bridge.snapshot()["state"] or {}).get("time") == 12)
                reply = bridge.command({"command": "reset_trial"})
                wait_for(lambda: len(bridge.snapshot()["responses"]) == 1)
                self.assertEqual(bridge.snapshot()["responses"][0]["id"], reply["id"])
                close_first.set()
                self.assertTrue(second_ready.wait(3), "El cliente debe reconectar")
                worker.join(timeout=1)
                self.assertFalse(errors)
                self.assertEqual(len(received), 1, "La conexión nueva no debe recibir órdenes anteriores")
                self.assertEqual(received[0], {"id": reply["id"], "command": "reset_trial"})
                bridge.connection(False)
                with self.assertRaises(ConnectionError):
                    bridge.command({"command": "stop"})
                self.assertTrue(bridge.pending.empty(), "No guardar órdenes para una futura reconexión")
            finally:
                close_first.set()
                bridge.close()
                worker.join(timeout=1)

    def test_reject_nonfinite_json_and_oversize_frames(self):
        for raw in ('{"value": NaN}', '{"value": 1e999}', '{"value": Infinity}'):
            with self.assertRaises(ValueError):
                finite_json(raw)
        # El parser del enlace aplica el límite aun con JSON válido.
        bridge = Bridge.__new__(Bridge)
        with self.assertRaises(ValueError):
            bridge._receive(b" " * (MAX_FRAME + 1))


if __name__ == "__main__":
    unittest.main()
