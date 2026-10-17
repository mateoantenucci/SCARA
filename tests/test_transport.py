from collections import deque
import unittest

from scara.runtime import Runtime
from scara.transport import Server


class FakeSocket:
    def __init__(self, chunks, fail_send=False):
        self.chunks = deque(chunks)
        self.fail_send = fail_send

    def recv(self, _size):
        if not self.chunks:
            raise BlockingIOError()
        return self.chunks.popleft()

    def send(self, data):
        if self.fail_send:
            raise ConnectionResetError()
        return len(data)

    def close(self):
        pass


def server_for(chunks, fail_send=False):
    server = object.__new__(Server)
    server.client = FakeSocket(chunks, fail_send)
    server.received = bytearray()
    server.outgoing = bytearray()
    server.lost = False
    return server


class TransportTests(unittest.TestCase):
    def test_stream_fragmentation_and_multiple_frames(self):
        server = server_for([b'{"command":"sta'])
        self.assertEqual(server.poll(), [])
        server.client.chunks.extend([b'tus"}\n{"command":"stop"}\n'])
        self.assertEqual(server.poll(), [{"command": "status"}, {"command": "stop"}])

    def test_send_failure_discards_commands_from_lost_connection(self):
        server = server_for([b'{"command":"rearm"}\n'], fail_send=True)
        server.outgoing.extend(b"state\n")
        requests = server.poll()
        runtime = Runtime()
        if server.lost:
            runtime.stop()
        for request in requests:
            runtime.handle(request, 0)
        self.assertEqual(requests, [])
        self.assertEqual(runtime.mode, "STOPPED")
        self.assertIsNone(server.client)

    def test_invalid_json_and_oversized_frame_do_not_reach_runtime(self):
        server = server_for([b'{"command":"payload","mass":1e999}\n'])
        self.assertEqual(server.poll(), [])
        server = server_for([b"x"*4096]*5)
        self.assertEqual(server.poll(), [])
        self.assertTrue(server.lost)
        self.assertIsNone(server.client)


if __name__ == "__main__":
    unittest.main()
