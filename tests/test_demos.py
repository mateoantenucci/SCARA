"""Trayectorias de demostración de la defensa (issue #18): se cargan y se reproducen sin errores.

Cada archivo de trayectorias/ se carga con el gestor y se reproduce en loop de
2 vueltas, como en la defensa, por los endpoints HTTP: así se validan todos
sus tramos, la vuelta del último punto al primero y el tramo de aproximación
desde el reposo (D68). La UCI falsa de las pruebas de la reproducción
confirma cada SEG; al final, la prueba informa el último segmento terminado
y la reproducción termina.
"""

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from tests.test_playback import REST, Robot
from tests.test_urc import wait_for
from urc.app import handler_for
from urc.playback import Player
from urc.session import Session
from urc.trajectories import DEFAULT_FOLDER, TrajectoryManager


DEMOS = sorted(DEFAULT_FOLDER.glob("demo-*.json"))


class DemoTrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        # La carpeta de la URC por defecto, la misma que abre `python -m urc.app`: cargar no escribe nada.
        self.manager = TrajectoryManager(self.session, DEFAULT_FOLDER)
        self.player = Player(self.session, self.manager)
        self.addCleanup(self.player.close)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                          handler_for(self.session, manager=self.manager, player=self.player))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def post(self, path, body, expect):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=60)
        self.addCleanup(connection.close)
        connection.request("POST", path, body=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        data = json.loads(response.read())
        self.assertEqual(response.status, expect, data)
        return data

    def all_sent(self):
        with self.player.lock:
            if self.player.pending or self.player.cycles_left != 0:
                return False
        segments = self.session.snapshot()["segments"]
        return segments["pending"] == 0 and segments["in_flight"] is None

    def test_there_are_demos_for_lin_ptp_and_waits(self):
        kinds, waits = set(), False
        for path in DEMOS:
            points = json.loads(path.read_text(encoding="utf-8"))["points"]
            kinds |= {point["kind"] for point in points}
            waits |= any(point["wait"] > 0 for point in points)
        self.assertGreaterEqual(len(DEMOS), 3)
        self.assertEqual(kinds, {"LIN", "PTP"})
        self.assertTrue(waits)

    def test_every_demo_loads_and_plays_twice_from_rest(self):
        robot = Robot(self.session.port)
        self.addCleanup(robot.close)
        last_number = 0
        for path in DEMOS:
            with self.subTest(path.name):
                # Si una demo falla a mitad, Stop la corta: la siguiente arranca igual.
                self.addCleanup(self.player.stop)
                # Cada demo arranca en el reposo, referenciado, como después del homing.
                robot.uci.send(f"S IDLE 15 {' '.join(map(str, REST))} 0 16 {last_number}")
                wait_for(lambda: (s := self.session.snapshot()["status"]) and s["position"] == list(REST))
                loaded = self.post("/api/trayectoria/cargar", {"file": path.name, "discard": True}, 200)
                self.assertFalse(loaded["dirty"])
                state = self.post("/api/reproduccion/reproducir", {"speed": 100, "loops": 2}, 202)
                self.assertEqual(state["state"], "reproduciendo", state)
                self.assertFalse(state["approach"]["skipped"])
                # Encoladas las dos vueltas, la UCI falsa recibió y confirmó cada segmento.
                wait_for(lambda: self.all_sent(), timeout=60)
                with robot.lock:
                    last_number, _, last = robot.segments[-1]
                self.assertEqual(last_number, len(robot.segments))
                self.assertEqual(list(last), loaded["points"][-1]["joints"])
                robot.uci.send(f"S IDLE 15 {' '.join(map(str, last))} 0 16 {last_number}")
                state = wait_for(lambda: (s := self.player.snapshot())["state"] != "reproduciendo" and s)
                self.assertEqual(state["state"], "terminada", state)
                self.assertIn("2 vueltas", state["message"])

if __name__ == "__main__":
    unittest.main()
