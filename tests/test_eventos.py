"""Registro de eventos de la URC (D78) y confirmación de las órdenes del banco (D79).

La página muestra el registro como historial y saca de él los avisos
emergentes; estas pruebas lo miran por sus tres fuentes: la sesión con una UCI
falsa, el servidor HTTP y el canal de instrumentación con un controlador falso.
"""

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from tests.test_instrumentation import FakeBench
from tests.test_urc import FakeUci, wait_for
from urc import instrumentation
from urc.app import handler_for
from urc.events import REPEAT, EventLog
from urc.instrumentation import Instrumentation
from urc.session import Session


def texts(log, version=0):
    return [event["text"] for event in log.since(version)["events"]]


class EventLogTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.log = EventLog(clock=lambda: self.now)

    def test_numbers_and_times_each_event(self):
        self.assertEqual(self.log.add("error", "UCI", "ERR 4 watchdog: el robot frenó solo"), 1)
        self.now += 5
        self.assertEqual(self.log.add("info", "Operador", "Homing"), 2)
        events = self.log.since()["events"]
        self.assertEqual([(e["n"], e["time"], e["level"], e["source"]) for e in events],
                         [(1, 1000.0, "error", "UCI"), (2, 1005.0, "info", "Operador")])
        with self.assertRaises(ValueError):
            self.log.add("grave", "UCI", "?")

    def test_the_same_event_soon_after_is_a_repetition(self):
        # El jog que se renueva contra un límite: un evento, con sus repeticiones.
        for _ in range(3):
            self.log.add("aviso", "Jog", "Jog frenado: J1 llegó al límite", rejected=True)
            self.now += REPEAT / 2
        event, = self.log.since()["events"]
        self.assertEqual((event["n"], event["repeats"], event["time"], event["last"]), (1, 3, 1000.0, 1000.0 + REPEAT))
        # Lo mismo un rato después es otro evento, con su número y su hora.
        self.now += REPEAT * 2
        self.assertEqual(self.log.add("aviso", "Jog", "Jog frenado: J1 llegó al límite"), 2)

    def test_since_gives_only_what_changed(self):
        self.log.add("info", "URC", "UCI conectada")
        version = self.log.since()["version"]
        self.log.add("info", "URC", "Homing en curso")
        self.assertEqual(texts(self.log, version), ["Homing en curso"])
        version = self.log.since()["version"]
        self.log.add("info", "URC", "Homing en curso")  # una repetición también es un cambio
        self.assertEqual([e["repeats"] for e in self.log.since(version)["events"]], [2])


class SessionEventTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.uci = FakeUci(self.session.port)
        self.addCleanup(self.uci.close)
        self.assertEqual(self.uci.receive(), "HELLO")

    def events(self):
        return self.session.events.since()["events"]

    def wait_event(self, text):
        return wait_for(lambda: next((e for e in self.events() if text in e["text"]), None))

    def test_what_the_uci_reports_goes_to_the_log(self):
        self.uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        self.uci.send("ERR 4 watchdog")
        self.uci.send("EV LOST 4 -36")
        self.uci.send("EV HOMED 4")
        self.uci.send("RUIDO")
        self.assertEqual(self.wait_event("ERR 4 watchdog")["level"], "error")
        lost = self.wait_event("Pérdida de pasos en J4")
        self.assertEqual((lost["level"], lost["source"]), ("error", "URC"))
        self.assertEqual(self.wait_event("EV HOMED 4")["level"], "info")
        self.assertEqual(self.wait_event("no respeta scara/1")["level"], "aviso")
        # Los números siguen el orden de llegada.
        numbers = [e["n"] for e in self.events()]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(self.session.snapshot()["events_version"], self.session.events.version)

    def test_an_unexpected_boot_is_an_error(self):
        self.uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        self.uci.send("BOOT scara/1 1")
        self.assertEqual(self.wait_event("BOOT inesperado")["level"], "error")

    def test_the_link_going_quiet_and_coming_back(self):
        # F4: la conexión sigue abierta, pero el estado S deja de llegar.
        self.uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        late = wait_for(lambda: next((e for e in self.events() if "Sin estado de la UCI" in e["text"]), None), timeout=3)
        self.assertEqual(late["level"], "error")
        self.uci.send("S IDLE 15 0 0 0 12000 8 16 0")
        self.assertEqual(self.wait_event("Volvió a llegar el estado")["level"], "ok")


class HttpEventTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.session))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.port = server.server_port

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        self.addCleanup(connection.close)
        data = None if body is None else json.dumps(body).encode()
        connection.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def connect(self, status="S OFF 0 0 0 0 12000 8 16 0"):
        uci = FakeUci(self.session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        uci.send(status)
        wait_for(lambda: self.session.snapshot()["status"])
        return uci

    def test_a_rejected_order_is_logged_with_its_name(self):
        self.connect()
        status, body = self.request("POST", "/api/home", {})
        self.assertEqual(status, 400)
        status, log = self.request("GET", "/api/eventos")
        self.assertEqual(status, 200)
        order, rejection = log["events"][-2:]
        self.assertEqual((order["source"], order["text"], order["rejected"]), ("Operador", "Homing", False))
        self.assertEqual((rejection["source"], rejection["text"], rejection["level"], rejection["rejected"]),
                         ("Homing", body["error"], "aviso", True))
        self.assertIn("habilitalos", rejection["text"])

    def test_the_order_goes_before_what_the_urc_does_with_it(self):
        uci = self.connect("S IDLE 0 0 0 0 12000 8 16 0")
        self.assertEqual(self.request("POST", "/api/home", {})[0], 202)
        self.assertEqual(uci.receive(), "HOME")
        version = self.request("GET", "/api/eventos")[1]["version"]
        self.assertEqual(texts(self.session.events)[-2:], ["Homing", "Homing en curso: J4, J1, J2 y J3"])
        # Solo lo nuevo, y nada mientras no cambie.
        self.assertEqual(self.request("GET", f"/api/eventos?desde={version}")[1]["events"], [])

    def test_the_jog_and_questions_are_not_logged_as_orders(self):
        uci = self.connect("S IDLE 0 0 0 0 12000 8 16 0")
        before = self.session.events.version
        self.assertEqual(self.request("POST", "/api/jog", {"joint": 1, "direction": "+"})[0], 202)
        self.assertEqual(uci.receive(), "JOG 1 + 500")
        self.assertEqual(self.request("POST", "/api/trayectoria/punto", {"joints": [0, -30, 0, 120]})[0], 200)
        # Nueva con cambios sin guardar es una pregunta (409), no un rechazo.
        self.assertEqual(self.request("POST", "/api/trayectoria/nueva", {})[0], 409)
        self.assertEqual(texts(self.session.events, before), [])


class BenchConfirmationTests(unittest.TestCase):
    """Las órdenes del banco se confirman con el estado SIM (D79)."""

    LINE = "SIM 0 0 0 12000 8 15 0 ---- 0 150 100 100 100 {current} 0 0 0 0"

    def setUp(self):
        self.bench = Instrumentation(port=0)
        self.addCleanup(self.bench.close)
        self.sim = FakeBench(self.bench.port)
        self.addCleanup(self.sim.close)
        self.sim.send("SIM HELLO scara-sim/1")
        self.sim.send(self.LINE.format(current=100))
        wait_for(lambda: self.bench.snapshot()["simulated"])

    def test_an_applied_order_is_confirmed(self):
        self.assertEqual(texts(self.bench.events), ["Canal de instrumentación conectado: carga 150 g, sin fallas"])
        self.assertEqual(self.bench.order({"falla": "F1", "motor": 4, "corriente": 50}),
                         "F1 · corriente del driver de M4: 50 %")
        self.assertEqual(self.sim.receive(), "F1 4 50")
        self.assertEqual(self.bench.snapshot()["pending"], [{"key": "F1 4", "value": 50}])
        self.sim.send(self.LINE.format(current=50))
        wait_for(lambda: not self.bench.snapshot()["pending"])
        event = self.bench.events.since()["events"][-1]
        self.assertEqual((event["level"], event["text"]), ("ok", "F1 · corriente del driver de M4: 100 % → 50 %"))

    def test_the_page_takes_the_load_limit_from_the_urc(self):
        self.assertEqual(self.bench.snapshot()["load_max"], instrumentation.LOAD_MAX)

    def test_an_order_already_in_force_is_confirmed_too(self):
        self.bench.order({"carga": 150})
        self.sim.send(self.LINE.format(current=100))
        wait_for(lambda: not self.bench.snapshot()["pending"])
        self.assertEqual(texts(self.bench.events)[-1], "Carga en la herramienta: 150 g, ya regía")

    def test_an_order_the_simulator_does_not_apply_is_reported(self):
        with mock.patch.object(instrumentation, "CONFIRM", 0.2):
            self.bench.order({"carga": 0})
        event = wait_for(lambda: next((e for e in self.bench.events.since()["events"] if e["level"] == "aviso"), None))
        self.assertEqual(event["text"], "No se aplicó Carga en la herramienta: se pidió 0 g y el simulador sigue en 150 g")
        self.assertEqual(self.bench.snapshot()["pending"], [])

    def test_changes_nobody_asked_for_are_logged_as_information(self):
        # F5 o recargar el mundo vuelven las fallas a su estado nominal.
        self.sim.send(self.LINE.format(current=40))
        event = wait_for(lambda: next((e for e in self.bench.events.since()["events"] if "→" in e["text"]), None))
        self.assertEqual((event["level"], event["text"]), ("info", "F1 · corriente del driver de M4: 100 % → 40 %"))


if __name__ == "__main__":
    unittest.main()
