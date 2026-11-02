"""Canal de instrumentación (ADR 0004): la verdad del simulador, aparte de scara/1.

Un controlador falso se conecta por TCP como lo hace Webots en el puerto 9001.
La URC lo muestra en el banco de ensayo y nunca lo usa para capturar ni
planificar.
"""

import ast
import http.client
import json
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer

from tests.test_urc import FakeUci, wait_for
from urc.app import handler_for
from urc.instrumentation import Instrumentation
from urc.session import Session


ROOT = Path(__file__).resolve().parents[1]


class FakeBench(FakeUci):
    """El lado del controlador de Webots en el canal de instrumentación."""


class InstrumentationTests(unittest.TestCase):
    def setUp(self):
        self.bench = Instrumentation(port=0)
        self.addCleanup(self.bench.close)

    def connect(self):
        client = FakeBench(self.bench.port)
        self.addCleanup(client.close)
        client.send("SIM HELLO scara-sim/1")
        wait_for(lambda: self.bench.snapshot()["connected"])
        return client

    def test_without_the_channel_there_is_no_bench(self):
        state = self.bench.snapshot()
        self.assertFalse(state["connected"])
        self.assertIsNone(state["simulated"])
        with self.assertRaises(ConnectionError):
            self.bench.order({"falla": "F5"})

    def test_reads_the_simulator_truth(self):
        client = self.connect()
        client.send("SIM 3001 -5995 2003 8001 8 15 0 -A-- 0 150 100 100 100 40 0 0 0 -12")
        state = wait_for(lambda: (s := self.bench.snapshot())["simulated"] and s)
        self.assertEqual(state["simulated"], [3001, -5995, 2003, 8001])
        self.assertEqual(state["hall"], 8)
        self.assertEqual(state["power"], 15)
        self.assertEqual(state["faults"], {"F2": False, "F3": ["libre", "activo", "libre", "libre"], "F4": False})
        self.assertEqual(state["load_g"], 150)
        self.assertEqual(state["current_pct"], [100, 100, 100, 40])
        self.assertEqual(state["lost_steps"], [0, 0, 0, -12])

    def test_orders_reach_the_controller(self):
        client = self.connect()
        for request, line in (({"falla": "F1", "motor": 4, "corriente": 40}, "F1 4 40"),
                              ({"falla": "F2", "activa": True}, "F2 1"),
                              ({"falla": "F2", "activa": False}, "F2 0"),
                              ({"falla": "F3", "articulacion": 2, "estado": "inactivo"}, "F3 2 inactivo"),
                              ({"falla": "F4", "activa": True}, "F4 1"),
                              ({"falla": "F5"}, "F5"),
                              ({"carga": 500}, "CARGA 500"),
                              # Sin carga: queda la herramienta sola (D85).
                              ({"carga": 0}, "CARGA 0"),
                              ({"carga": 4850}, "CARGA 4850"),
                              ({"recarga": True}, "RECARGA")):
            with self.subTest(request=request):
                self.bench.order(request)
                self.assertEqual(client.receive(), line)

    def test_rejects_bad_orders_and_lines(self):
        client = self.connect()
        for request in ({"falla": "F1"}, {"falla": "F1", "motor": 5, "corriente": 50},
                        {"falla": "F1", "motor": 1, "corriente": 5}, {"falla": "F1", "motor": 1, "corriente": 101},
                        {"falla": "F1", "motor": 1, "corriente": 50.5}, {"falla": "F2", "activa": 1}, {"falla": "F3", "articulacion": 5,
                        "estado": "activo"}, {"falla": "F3", "articulacion": 1, "estado": "roto"},
                        {"carga": -1}, {"carga": 4851}, {"carga": True}, {}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.bench.order(request)
        client.send("SIM 1 2 3")
        client.send("SIM 3001 -5995 2003 8001 8 15 0 -A-- 0 150")  # sin corrientes ni pasos perdidos
        client.send("RUIDO")
        wait_for(lambda: len(self.bench.snapshot()["rejected"]) == 3)
        self.assertIsNone(self.bench.snapshot()["simulated"])


class IsolationTests(unittest.TestCase):
    """Capturar y planificar nunca usan datos del canal de instrumentación (ADR 0004)."""

    def test_no_robot_module_imports_the_channel(self):
        for name in ("session.py", "planner.py", "validation.py", "protocol.py"):
            tree = ast.parse((ROOT / "urc" / name).read_text(encoding="utf-8"))
            imported = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                        for alias in node.names} | {node.module for node in ast.walk(tree)
                                                     if isinstance(node, ast.ImportFrom) and node.module}
            with self.subTest(module=name):
                self.assertFalse(any("instrumentation" in module for module in imported), imported)

    def test_planning_uses_the_estimated_position(self):
        session = Session(port=0)
        self.addCleanup(session.close)
        bench = Instrumentation(port=0)
        self.addCleanup(bench.close)
        uci, sim = FakeUci(session.port), FakeBench(bench.port)
        self.addCleanup(uci.close)
        self.addCleanup(sim.close)
        self.assertEqual(uci.receive(), "HELLO")
        uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        # La física dice otra cosa (por ejemplo, J4 cayó sin corriente).
        sim.send("SIM HELLO scara-sim/1")
        sim.send("SIM 1000 0 0 6000 0 7 1 ---- 0 150 100 100 100 100 0 0 0 0")
        wait_for(lambda: session.snapshot()["referenced"] and bench.snapshot()["simulated"])
        plan = session.move_ptp((900, 0, 0, 12000), dry_run=True)
        self.assertEqual(plan["start"], [0, 0, 0, 12000])
        self.assertFalse(any(isinstance(value, Instrumentation) for value in vars(session).values()))


class HttpTests(unittest.TestCase):
    def serve(self, bench):
        session = Session(port=0)
        self.addCleanup(session.close)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(session, bench))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_port

    def request(self, port, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        self.addCleanup(connection.close)
        data = None if body is None else json.dumps(body).encode()
        connection.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
        response = connection.getresponse()
        return response.status, response.read()

    def test_the_page_hides_the_bench_without_the_channel(self):
        # Con el robot real no hay canal: la URC funciona igual.
        port = self.serve(None)
        status, body = self.request(port, "GET", "/api/banco")
        self.assertEqual((status, json.loads(body)["connected"]), (200, False))
        status, _ = self.request(port, "POST", "/api/banco", {"falla": "F5"})
        self.assertEqual(status, 409)
        status, script = self.request(port, "GET", "/banco.js")
        self.assertEqual(status, 200)
        self.assertIn(b"Banco de ensayo", script)

    def test_orders_go_through_the_channel(self):
        bench = Instrumentation(port=0)
        self.addCleanup(bench.close)
        port = self.serve(bench)
        sim = FakeBench(bench.port)
        self.addCleanup(sim.close)
        sim.send("SIM HELLO scara-sim/1")
        wait_for(lambda: bench.snapshot()["connected"])
        status, body = self.request(port, "POST", "/api/banco", {"falla": "F4", "activa": True})
        self.assertEqual(status, 202, body)
        self.assertEqual(sim.receive(), "F4 1")
        status, _ = self.request(port, "POST", "/api/banco", {"falla": "F9"})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
