"""Reproducción de trayectorias por los endpoints HTTP (seam 2 de la spec #2).

Una UCI falsa confirma cada SEG apenas llega, como un firmware con la cola
siempre libre, y anota lo que recibe. La prueba decide qué informa el estado
S: dónde está el robot y hasta qué segmento terminó.
"""

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from scara.kinematics import load_config
from tests.test_urc import FakeUci, wait_for
from urc import planner, validation
from urc.app import handler_for
from urc.playback import Player
from urc.session import Session
from urc.trajectories import TrajectoryManager


REST = (0, 0, 0, 12000)
# Tres puntos cercanos, con el codo negativo: tramos cortos para que las pruebas vayan rápido.
P1, P2, P3 = (3000, -6000, 1000, 6000), (2000, -5000, 1000, 6000), (2000, -5000, 1000, 3000)
CONFIG = load_config()


def degrees(units):
    return [value / 100 for value in units]


def lin(start, target, speed):
    return validation.check_lin(start, target, speed, config=CONFIG).segments


def ptp(start, target, speed):
    return planner.plan_ptp(start, target, speed).segments


class Robot:
    """UCI falsa que confirma cada SEG al recibirlo y anota todo lo que llega."""

    def __init__(self, port):
        self.uci = FakeUci(port)
        assert self.uci.receive() == "HELLO"
        self.uci.sock.settimeout(None)
        self.lock = threading.Lock()
        self.segments, self.orders = [], []
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        try:
            while True:
                line = self.uci.receive()
                fields = line.split()
                with self.lock:
                    if fields[0] == "SEG":
                        self.segments.append((int(fields[1]), int(fields[2]), tuple(int(v) for v in fields[3:])))
                    else:
                        self.orders.append(line)
                if fields[0] == "SEG":
                    self.uci.send(f"OK {fields[1]}")
        except OSError:
            pass

    def received(self, count):
        """Espera a que lleguen `count` SEG y los devuelve como (ms, J1–J4)."""
        wait_for(lambda: len(self.segments) >= count)
        with self.lock:
            return [(ms, units) for _, ms, units in self.segments]

    def close(self):
        self.uci.close()


class PlaybackHttpTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.manager = TrajectoryManager(self.session, self.folder)
        self.player = Player(self.session, self.manager)
        self.addCleanup(self.player.close)
        handler = handler_for(self.session, manager=self.manager, player=self.player)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    # --- Ayudas -----------------------------------------------------------

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        self.addCleanup(connection.close)
        data = None if body is None else json.dumps(body).encode()
        connection.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def post(self, path, body=None, expect=202):
        status, data = self.request("POST", path, body if body is not None else {})
        self.assertEqual(status, expect, data)
        return data

    def play(self, body=None, expect=202):
        return self.post("/api/reproduccion/reproducir", {"speed": 100, **(body or {})}, expect)

    def state(self):
        status, data = self.request("GET", "/api/reproduccion")
        self.assertEqual(status, 200)
        return data

    def until(self, state):
        return wait_for(lambda: (data := self.state())["state"] == state and data, timeout=5)

    def points(self, *points, **tramo):
        """Agrega los puntos; tramo[i] = cambios en cómo se llega al punto i (desde 0)."""
        for units in points:
            self.post("/api/trayectoria/punto", {"joints": degrees(units)}, expect=200)
        for index, fields in tramo.items():
            self.post("/api/trayectoria/editar", {"index": int(index[1:]), **fields}, expect=200)

    def robot(self, position=REST, homed=15):
        robot = Robot(self.session.port)
        self.addCleanup(robot.close)
        self.report(robot, "IDLE", position, homed=homed)
        return robot

    def report(self, robot, mode, position, last=0, homed=15):
        robot.uci.send(f"S {mode} {homed} {' '.join(map(str, position))} 0 16 {last}")
        wait_for(lambda: (s := self.session.snapshot()["status"]) and s["position"] == list(position)
                 and s["mode"] == mode and s["last"] == last)

    def numbers(self, robot):
        with robot.lock:
            return [number for number, _, _ in robot.segments]

    # --- Antes de arrancar --------------------------------------------------

    def test_without_reference_playback_is_blocked_with_a_clear_message(self):
        self.points(P1, P2)
        self.assertIn("UCI", self.play(expect=409)["error"])
        robot = self.robot(homed=0)
        error = self.play(expect=400)["error"]
        self.assertIn("referenciado", error)
        self.assertIn("homing", error)
        # Una referencia dudosa (EV LOST, D65) también bloquea: conviene hacer homing.
        self.report(robot, "IDLE", REST)
        robot.uci.send("EV LOST 2 -4")
        wait_for(lambda: self.session.snapshot()["doubtful"])
        self.assertIn("dudosa", self.play(expect=400)["error"])
        self.assertEqual(robot.segments, [])
        self.assertEqual(self.state()["state"], "inactiva")

    def test_needs_points_a_still_robot_and_a_valid_request(self):
        robot = self.robot()
        self.assertIn("puntos", self.play(expect=400)["error"])
        self.points(P1, P2)
        for body in ({"speed": 9}, {"speed": 101}, {"speed": 50.5}, {"loops": 0}, {"start": 2}, {"start": "1"}):
            self.play(body, expect=400)
        self.report(robot, "JOG", REST)
        self.assertIn("moviendo", self.play(expect=400)["error"])
        self.assertEqual(robot.segments, [])

    def test_the_whole_trajectory_is_validated_before_moving(self):
        robot = self.robot(P1)
        # El punto 3 cambia de codo: la recta es imposible y se sugiere PTP (D14).
        self.points(P1, P2, (2000, 5000, 1000, 3000))
        error = self.play(expect=400)["error"]
        self.assertIn("Tramo 3 (LIN), cambio de codo", error)
        self.assertIn("Usá un tramo PTP", error)
        self.assertEqual(robot.segments, [])
        self.post("/api/trayectoria/editar", {"index": 2, "kind": "PTP"}, expect=200)
        self.assertEqual(self.play()["state"], "reproduciendo")

    def test_the_loop_back_is_validated_too(self):
        self.robot(P1)
        # Del punto 3 al 1 la recta cambia de codo: con loop se valida la vuelta.
        self.points(P1, P2, (2000, 5000, 1000, 3000), p2={"kind": "PTP"})
        self.assertIn("Tramo de vuelta (LIN), cambio de codo", self.play({"loops": 2}, expect=400)["error"])

    # --- Reproducción -------------------------------------------------------

    def test_plays_the_approach_and_every_tramo_as_planned(self):
        robot = self.robot()
        self.points(P1, P2, P3, p1={"speed": 100}, p2={"kind": "PTP", "speed": 50, "wait": 0.5})
        state = self.play()
        # Tramo 0: PTP al 25 % desde donde está el robot (D32, D33), con su duración.
        approach = ptp(REST, P1, 0.25)
        self.assertEqual(state["approach"], {"skipped": False, "duration_s": round(len(approach) * 0.02, 2), "point": 0})
        self.assertEqual([(t["label"], t["kind"], t["speed"]) for t in state["tramos"]],
                         [("2", "LIN", 100), ("3", "PTP", 50)])
        self.assertEqual(state["tramos"][1]["wait_s"], 0.5)
        expected = approach + lin(P1, P2, 1.0) + ptp(P2, P3, 0.5) + [(500, P3)]
        self.assertEqual(state["duration_s"], round(sum(ms for ms, _ in expected) / 1000, 2))
        self.assertEqual(robot.received(len(expected)), expected)
        self.assertEqual(self.numbers(robot), list(range(1, len(expected) + 1)))
        self.assertEqual(self.state()["state"], "reproduciendo")
        self.report(robot, "IDLE", P3, len(expected))
        state = self.until("terminada")
        self.assertIn("terminada", state["message"])
        self.assertEqual(len(robot.segments), len(expected))

    def test_the_global_speed_scales_every_tramo_and_is_not_saved(self):
        robot = self.robot()
        self.points(P1, P2, p1={"speed": 80})
        state = self.play({"speed": 50})
        self.assertEqual(state["speed"], 50)
        expected = ptp(REST, P1, 0.125) + lin(P1, P2, 0.4)
        self.assertEqual(robot.received(len(expected)), expected)
        self.post("/api/trayectoria/guardar", {"name": "Prueba"}, expect=200)
        document = json.loads((self.folder / "prueba.json").read_text(encoding="utf-8"))
        self.assertNotIn("speed", {key for key in document} - {"points"})
        self.assertEqual([point["speed"] for point in document["points"]], [50, 80])

    def test_the_approach_is_skipped_if_the_robot_is_already_at_point_1(self):
        # Menos de un paso por articulación (D33): el primer tramo parte del punto 1 grabado.
        robot = self.robot((3004, -6006, 997, 6001))
        self.points(P1, P2)
        state = self.play()
        self.assertEqual(state["approach"], {"skipped": True, "duration_s": 0, "point": 0})
        expected = lin(P1, P2, 0.5)
        self.assertEqual(robot.received(len(expected)), expected)

    def test_a_step_away_from_point_1_the_approach_is_planned(self):
        robot = self.robot((3007, -6000, 1000, 6000))
        self.points(P1, P2)
        self.assertFalse(self.play()["approach"]["skipped"])
        expected = ptp((3007, -6000, 1000, 6000), P1, 0.25) + lin(P1, P2, 0.5)
        self.assertEqual(robot.received(len(expected)), expected)

    def test_plays_from_the_selected_point(self):
        robot = self.robot()
        self.points(P1, P2, P3)
        state = self.play({"start": 1})
        self.assertEqual(state["approach"]["point"], 1)
        self.assertEqual([t["label"] for t in state["tramos"]], ["3"])
        expected = ptp(REST, P2, 0.25) + lin(P2, P3, 0.5)
        self.assertEqual(robot.received(len(expected)), expected)

    def test_the_running_tramo_follows_the_status_of_the_uci(self):
        robot = self.robot()
        self.points(P1, P2, P3, p2={"kind": "PTP", "wait": 1})
        self.play()
        approach, first, second = len(ptp(REST, P1, 0.25)), len(lin(P1, P2, 0.5)), len(ptp(P2, P3, 0.5))
        robot.received(approach + first + second + 1)
        current = lambda: self.state()["current"]  # noqa: E731
        self.assertEqual(current(), {"point": 0, "label": "0", "kind": "PTP", "approach": True, "waiting": False,
                                     "cycle": 1})
        self.report(robot, "RUN", P1, approach + 3)
        wait_for(lambda: current()["label"] == "2")
        self.assertEqual(current(), {"point": 1, "label": "2", "kind": "LIN", "approach": False, "waiting": False,
                                     "cycle": 1})
        self.report(robot, "RUN", P3, approach + first + second)
        wait_for(lambda: current()["waiting"])
        self.assertEqual(current()["point"], 2)

    # --- Pausa, reanudación y stop -----------------------------------------

    def test_pause_ramps_and_resume_keeps_the_line(self):
        robot = self.robot(P1)
        self.points(P1, P2, P3)
        self.play()
        plan = lin(P1, P2, 0.5)
        robot.received(len(plan))
        self.assertEqual(self.post("/api/reproduccion/pausa")["state"], "pausando")
        wait_for(lambda: "STOP" in robot.orders)
        self.assertEqual(self.state()["state"], "pausando")
        # El firmware frenó con rampa a mitad de la recta (D52), en el segmento 41.
        stopped = plan[40][1]
        self.report(robot, "IDLE", stopped, 40)
        self.until("pausada")
        sent = len(robot.segments)
        state = self.post("/api/reproduccion/reanudar")
        self.assertEqual(state["state"], "reproduciendo")
        # Recalcula desde la pose actual hasta el final del tramo, sobre la misma recta.
        rest = lin(stopped, P2, 0.5)
        expected = rest + lin(P2, P3, 0.5)
        resumed = robot.received(sent + len(expected))[sent:]
        self.assertEqual(resumed, expected)
        origin, end = planner.tool_point(P1, CONFIG), planner.tool_point(P2, CONFIG)
        worst = max(planner.distance_to_line(planner.tool_point(units, CONFIG), origin, end) for _, units in rest)
        self.assertLess(worst * 1000, planner.lin_tolerance(CONFIG))

    def test_pause_during_a_wait_resumes_the_rest_of_the_wait(self):
        robot = self.robot(P1)
        self.points(P1, P2, P3, p1={"wait": 2.5})
        self.play()
        first = len(lin(P1, P2, 0.5))
        robot.received(first + 3)
        self.post("/api/reproduccion/pausa")
        # Terminó el tramo y el primer segundo de la espera.
        self.report(robot, "IDLE", P2, first + 1)
        self.until("pausada")
        sent = len(robot.segments)
        self.post("/api/reproduccion/reanudar")
        self.assertEqual(robot.received(sent + 3)[sent:sent + 3], [(1000, P2), (500, P2), lin(P2, P3, 0.5)[0]])

    def test_resume_needs_the_robot_where_it_paused_and_the_same_trajectory(self):
        robot = self.robot(P1)
        self.points(P1, P2)
        self.play()
        robot.received(10)
        self.post("/api/reproduccion/pausa")
        self.report(robot, "IDLE", (2900, -5900, 1000, 6000), 5)
        self.until("pausada")
        self.report(robot, "IDLE", (2800, -5900, 1000, 6000), 5)
        self.assertIn("se movió", self.post("/api/reproduccion/reanudar", expect=400)["error"])
        self.report(robot, "IDLE", (2900, -5900, 1000, 6000), 5)
        self.post("/api/trayectoria/editar", {"index": 1, "speed": 20}, expect=200)
        self.assertIn("cambió", self.post("/api/reproduccion/reanudar", expect=400)["error"])
        self.assertEqual(self.state()["state"], "pausada")

    def test_stop_brakes_and_discards_what_is_pending(self):
        robot = self.robot()
        self.points(P1, P2)
        self.play()
        robot.received(5)
        state = self.post("/api/reproduccion/stop")
        self.assertEqual(state["state"], "detenida")
        wait_for(lambda: "STOP" in robot.orders)
        sent = len(robot.segments)
        self.report(robot, "IDLE", (100, -100, 0, 11900), 3)
        self.assertEqual(self.session.snapshot()["segments"]["pending"], 0)
        self.assertEqual(len(robot.segments), sent)
        self.assertIn("reanudar", self.post("/api/reproduccion/reanudar", expect=400)["error"])
        # Se puede volver a reproducir desde donde quedó.
        self.assertEqual(self.play()["state"], "reproduciendo")

    def test_escape_stops_the_playback_even_while_paused(self):
        robot = self.robot()
        self.points(P1, P2)
        self.play()
        robot.received(5)
        self.post("/api/stop")
        self.assertEqual(self.until("detenida")["state"], "detenida")
        self.report(robot, "IDLE", (100, -100, 0, 11900), 3)
        self.play()
        self.post("/api/reproduccion/pausa")
        self.report(robot, "IDLE", (200, -200, 0, 11800), 6)
        self.until("pausada")
        self.post("/api/stop")
        self.until("detenida")

    def test_stop_while_validating_cancels_the_start(self):
        robot = self.robot()
        self.points(P1, P2)
        prepare = self.player._prepare

        def stopped_halfway(*args):
            plan = prepare(*args)
            self.post("/api/stop")
            return plan
        self.player._prepare = stopped_halfway
        self.assertIn("cancelada", self.play(expect=400)["error"])
        self.assertEqual(self.state()["state"], "detenida")
        self.assertEqual(robot.segments, [])

    def test_a_pause_at_the_very_end_resumes_into_the_end(self):
        robot = self.robot(P1)
        self.points(P1, P2)
        self.play()
        count = len(lin(P1, P2, 0.5))
        robot.received(count)
        self.post("/api/reproduccion/pausa")
        self.report(robot, "IDLE", P2, count)
        self.until("pausada")
        self.assertEqual(self.post("/api/reproduccion/reanudar")["state"], "terminada")
        self.assertEqual(len(robot.segments), count)

    def test_an_err_from_the_uci_stops_the_playback(self):
        robot = self.robot()
        self.points(P1, P2)
        self.play()
        robot.received(5)
        robot.uci.send("ERR 8 velocidad")
        state = self.until("detenida")
        self.assertIn("ERR 8", state["message"])

    def test_lost_steps_during_playback_stop_it(self):
        robot = self.robot()
        self.points(P1, P2)
        self.play()
        robot.received(5)
        robot.uci.send("EV LOST 1 4")
        state = self.until("detenida")
        self.assertIn("dudosa", state["message"])
        wait_for(lambda: "STOP" in robot.orders)

    def test_only_one_playback_at_a_time(self):
        robot = self.robot()
        self.points(P1, P2)
        self.play()
        robot.received(5)
        self.assertIn("Stop", self.play(expect=400)["error"])
        self.assertIn("pausa", self.post("/api/reproduccion/reanudar", expect=400)["error"])

    # --- Loop -----------------------------------------------------------------

    def test_the_loop_repeats_n_times_and_comes_back_with_point_1_parameters(self):
        robot = self.robot(P1)
        self.points(P1, P2, P3, p0={"kind": "PTP", "speed": 80, "wait": 0.2})
        state = self.play({"loops": 2})
        self.assertEqual([t["label"] for t in state["tramos"]], ["2", "3", "vuelta"])
        cycle = lin(P1, P2, 0.5) + lin(P2, P3, 0.5)
        back = ptp(P3, P1, 0.8) + [(200, P1)]
        expected = cycle + back + cycle
        self.assertEqual(robot.received(len(expected)), expected)
        self.report(robot, "RUN", P1, len(cycle) + 5)
        wait_for(lambda: self.state()["current"]["label"] == "vuelta")
        self.assertEqual(self.state()["current"]["point"], 0)
        self.report(robot, "RUN", P2, len(cycle + back) + 5)
        wait_for(lambda: self.state()["current"]["cycle"] == 2)
        self.report(robot, "IDLE", P3, len(expected))
        self.until("terminada")
        self.assertEqual(len(robot.segments), len(expected))

    def test_an_endless_loop_goes_on_until_stop(self):
        robot = self.robot(P1)
        self.points(P1, P2)
        state = self.play({"loops": None})
        self.assertIsNone(state["loops"])
        cycle = lin(P1, P2, 0.5) + lin(P2, P1, 0.5)
        robot.received(4 * len(cycle))
        self.assertEqual(self.state()["state"], "reproduciendo")
        self.post("/api/reproduccion/stop")
        wait_for(lambda: "STOP" in robot.orders)


if __name__ == "__main__":
    unittest.main()
