"""URC por su borde hacia el robot: una UCI falsa se conecta por TCP y habla scara/1."""

import http.client
import json
import socket
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

from urc.app import handler_for
from urc.session import Session


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.01)
    raise AssertionError("No se cumplió la condición esperada")


class FakeUci:
    """Extremo UCI: se conecta a la URC como lo hace Webots o socat."""

    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.buffer = b""

    def send(self, line):
        self.sock.sendall(line.encode() + b"\n")

    def receive(self, ignore=("PING",)):
        while True:
            while b"\n" not in self.buffer:
                chunk = self.sock.recv(1024)
                if not chunk:
                    raise ConnectionError("La URC cerró la conexión")
                self.buffer += chunk
            line, self.buffer = self.buffer.split(b"\n", 1)
            text = line.decode()
            if text not in ignore:
                return text

    def close(self):
        self.sock.close()


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0, jog_hold=0.3)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)

    def test_greets_and_reads_boot_hi_and_status(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("BOOT scara/1 1")
        self.uci.send("HI scara/1 1")
        self.uci.send("S IDLE 15 450 -900 0 12000 0 16 0")
        state = wait_for(lambda: (s := self.session.snapshot())["status"] and s)
        self.assertTrue(state["connected"])
        self.assertEqual(state["firmware"], {"protocol": "scara/1", "version": 1})
        self.assertEqual(state["boots"], 1)
        self.assertEqual(state["status"]["mode"], "IDLE")
        self.assertEqual(state["status"]["homed"], 15)
        self.assertEqual(state["status"]["position"], [450, -900, 0, 12000])
        self.assertIn({"direction": "<", "line": "BOOT scara/1 1"}, state["traffic"])

    def test_pings_keep_the_watchdog_alive(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.assertEqual(self.uci.receive(ignore=()), "PING")
        self.assertEqual(self.uci.receive(ignore=()), "PING")

    def test_jog_is_sent_once_and_stops_when_not_refreshed(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        wait_for(lambda: self.session.snapshot()["connected"])
        self.session.jog(1, "+")
        self.assertEqual(self.uci.receive(), "JOG 1 + 500")
        self.session.jog(1, "+")
        # Sin renovar, el jog vence y la URC lo frena.
        self.assertEqual(self.uci.receive(), "JOG STOP")
        self.session.jog(1, "-")
        self.assertEqual(self.uci.receive(), "JOG 1 - 500")
        self.session.jog_stop()
        self.assertEqual(self.uci.receive(), "JOG STOP")
        self.session.zero()
        self.assertEqual(self.uci.receive(), "ZERO")

    def test_rejects_invalid_jog_and_orders_without_robot(self):
        with self.assertRaises(ValueError):
            self.session.jog(5, "+")
        with self.assertRaises(ValueError):
            self.session.jog(1, "x")
        self.uci.close()
        wait_for(lambda: not self.session.snapshot()["connected"])
        with self.assertRaises(ConnectionError):
            self.session.jog(1, "+")

    def test_reconnection_greets_again_and_discards_bad_lines(self):
        self.assertEqual(self.uci.receive(), "HELLO")
        self.uci.send("S IDLE 0 1 2")
        self.uci.send("ERR 1 comando")
        wait_for(lambda: self.session.snapshot()["errors"])
        self.assertIsNone(self.session.snapshot()["status"])
        self.uci.close()
        second = FakeUci(self.session.port)
        self.addCleanup(second.close)
        self.assertEqual(second.receive(), "HELLO")
        second.send("S JOG 0 1 2 3 4 0 16 0")
        state = wait_for(lambda: (s := self.session.snapshot())["status"] and s)
        self.assertEqual(state["status"]["position"], [1, 2, 3, 4])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.session))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        self.addCleanup(connection.close)
        data = None if body is None else json.dumps(body).encode()
        headers = dict({"Content-Type": "application/json"} if data else {}, **(headers or {}))
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()

    def test_page_and_state(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"scara/1", page)
        status, body = self.request("GET", "/api/estado")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["connected"])

    def test_orders_need_a_robot_and_a_local_origin(self):
        status, body = self.request("POST", "/api/jog", {"joint": 1, "direction": "+"})
        self.assertEqual(status, 409, body)
        status, _ = self.request("POST", "/api/jog", {"joint": 1, "direction": "+"},
                                 {"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/jog", {"joint": 9, "direction": "+"})
        self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/nada", {})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
