"""Gestor de trayectorias de la URC por sus endpoints HTTP (seam 2 de la spec #2)."""

import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from tests.test_urc import FakeUci, wait_for
from urc.app import handler_for
from urc.session import Session
from urc.trajectories import TrajectoryManager


REST = "S IDLE 15 0 0 0 12000 0 16 0"


class TrajectoryHttpTests(unittest.TestCase):
    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.manager = TrajectoryManager(self.session, self.folder)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.session, manager=self.manager))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    # --- Ayudas -----------------------------------------------------------

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        self.addCleanup(connection.close)
        data = None if body is None else json.dumps(body).encode()
        connection.request(method, path, body=data, headers={"Content-Type": "application/json"} if data else {})
        response = connection.getresponse()
        return response.status, json.loads(response.read())

    def post(self, path, body=None, expect=200):
        status, data = self.request("POST", "/api/trayectoria/" + path, body if body is not None else {})
        self.assertEqual(status, expect, data)
        return data

    def robot(self, status=REST):
        """Una UCI conectada y referenciada, quieta en `status`."""
        uci = FakeUci(self.session.port)
        self.addCleanup(uci.close)
        self.assertEqual(uci.receive(), "HELLO")
        self.move(uci, status)
        return uci

    def move(self, uci, status):
        uci.send(status)
        position = [int(v) for v in status.split()[3:7]]
        wait_for(lambda: (s := self.session.snapshot()["status"]) and s["position"] == position
                 and s["mode"] == status.split()[1])

    def joints(self, trajectory):
        return [point["joints"] for point in trajectory["points"]]

    def write(self, name, document):
        (self.folder / name).write_text(document if isinstance(document, str) else json.dumps(document),
                                        encoding="utf-8")

    # --- Captura -------------------------------------------------------------

    def test_full_cycle_capture_name_save_close_and_load(self):
        uci = self.robot()
        self.post("capturar")
        self.move(uci, "S IDLE 15 3000 -6000 1000 6000 0 16 0")
        self.post("capturar", {"after": 0})
        self.move(uci, "S IDLE 15 -2000 -4000 500 3000 0 16 0")
        trajectory = self.post("capturar", {"after": 1})
        self.assertEqual(self.joints(trajectory), [[0, 0, 0, 12000], [3000, -6000, 1000, 6000],
                                                   [-2000, -4000, 500, 3000]])
        self.assertTrue(trajectory["dirty"])
        # Cada tramo nace LIN, al 50 % y sin espera (D22), y muestra XYZ, rumbo y codo.
        second = trajectory["points"][1]
        self.assertEqual((second["kind"], second["speed"], second["wait"]), ("LIN", 50, 0))
        self.assertEqual(second["tool"], {"x": 433.01, "y": 0.0, "z": 34.67, "heading": -20.0})
        self.assertEqual([p["elbow"] for p in trajectory["points"]], [0, -1, -1])
        # Enter: el operador le pone nombre y la guarda.
        saved = self.post("guardar", {"name": "Demostración 1"})
        self.assertEqual((saved["name"], saved["file"], saved["dirty"]), ("Demostración 1", "demostracion-1.json", False))
        document = json.loads((self.folder / "demostracion-1.json").read_text(encoding="utf-8"))
        self.assertEqual((document["format"], document["version"], document["name"]),
                         ("scara-trayectoria", 1, "Demostración 1"))
        self.assertIn("saved", document)
        self.assertIn("joints", document["units"])
        self.assertEqual(document["points"][1]["joints"], [3000, -6000, 1000, 6000])
        # Cerrar (nueva) y volver a cargar: la misma trayectoria.
        empty = self.post("nueva")
        self.assertEqual((empty["points"], empty["name"], empty["file"]), ([], None, None))
        status, files = self.request("GET", "/api/trayectorias")
        self.assertEqual(status, 200)
        self.assertEqual(files["files"], ["demostracion-1.json"])
        loaded = self.post("cargar", {"file": "demostracion-1.json"})
        self.assertEqual(loaded["points"], trajectory["points"])
        self.assertEqual((loaded["name"], loaded["dirty"]), ("Demostración 1", False))
        status, current = self.request("GET", "/api/trayectoria")
        self.assertEqual((status, current), (200, loaded))

    def test_capture_inserts_after_the_selected_point(self):
        uci = self.robot()
        self.post("capturar")
        self.move(uci, "S IDLE 15 3000 -6000 1000 6000 0 16 0")
        self.post("capturar")
        self.move(uci, "S IDLE 15 1000 -2000 0 6000 0 16 0")
        trajectory = self.post("capturar", {"after": 0})
        self.assertEqual([p[0] for p in self.joints(trajectory)], [0, 1000, 3000])
        self.assertEqual(trajectory["selected"], 1)
        trajectory = self.post("capturar", {"after": -1})
        self.assertEqual(trajectory["selected"], 0)
        self.post("capturar", {"after": 4}, expect=400)

    def test_capture_needs_a_referenced_robot_at_rest(self):
        self.assertIn("UCI", self.post("capturar", expect=409)["error"])
        uci = self.robot("S IDLE 0 0 0 0 12000 0 16 0")
        self.assertIn("referenciado", self.post("capturar", expect=400)["error"])
        self.move(uci, "S JOG 15 0 0 0 12000 0 16 0")
        self.assertIn("moviendo", self.post("capturar", expect=400)["error"])
        self.move(uci, REST)
        self.post("capturar")

    def test_capture_needs_a_fresh_status(self):
        self.robot()
        time.sleep(1.1)
        self.assertIn("al día", self.post("capturar", expect=400)["error"])

    def test_a_captured_pose_out_of_range_is_rejected(self):
        # Un jog puede dejar el robot apenas fuera del recorrido (D53).
        self.robot("S IDLE 15 13501 0 0 12000 0 16 0")
        self.assertIn("J1 fuera de su recorrido", self.post("capturar", expect=400)["error"])

    # --- Puntos escritos a mano ------------------------------------------

    def test_a_point_written_in_xyz_uses_the_preferred_elbow(self):
        trajectory = self.post("punto", {"pose": {"x": 433.0, "y": 0.0, "z": 34.7, "heading": -20}})
        for got, want in zip(trajectory["points"][0]["joints"], (3000, -6000, 1000, 6000)):
            self.assertAlmostEqual(got, want, delta=5)
        trajectory = self.post("punto", {"pose": {"x": 433.0, "y": 0.0, "z": 34.7, "heading": -20, "elbow": 1},
                                         "after": 0})
        self.assertEqual(trajectory["points"][1]["elbow"], 1)
        self.assertGreater(trajectory["points"][1]["joints"][1], 0)
        trajectory = self.post("punto", {"joints": [10, -20, 30, 40], "after": 1})
        self.assertEqual(trajectory["points"][2]["joints"], [1000, -2000, 3000, 4000])
        self.assertEqual(trajectory["selected"], 2)

    def test_an_edited_point_keeps_its_elbow(self):
        self.post("punto", {"joints": [-30, 60, -50, 60]})
        trajectory = self.post("editar", {"index": 0, "pose": {"x": 420.0, "y": 50.0, "z": 34.7, "heading": -20}})
        point = trajectory["points"][0]
        self.assertEqual(point["elbow"], 1)
        self.assertAlmostEqual(point["tool"]["x"], 420.0, delta=0.1)
        self.assertAlmostEqual(point["tool"]["y"], 50.0, delta=0.1)
        # Por articulaciones se puede cambiar todo, también el codo.
        trajectory = self.post("editar", {"index": 0, "joints": [30, -60, 10, 60]})
        self.assertEqual(trajectory["points"][0]["elbow"], -1)

    def test_written_points_are_validated(self):
        cases = (
            ({"pose": {"x": 900, "y": 0, "z": 0, "heading": 0}}, "alcance"),
            ({"joints": [0, 140, 0, 120]}, "J2 fuera de su recorrido"),
            ({"joints": [0, 135, 0, 0]}, "colisión"),
            ({"joints": [0, 0, 0]}, "J1–J4"),
            ({"pose": {"x": 433, "y": 0, "z": 34.7, "heading": -20, "elbow": 0}}, "codo"),
            ({}, "joints"),
        )
        for request, message in cases:
            with self.subTest(request=request):
                self.assertIn(message, self.post("punto", request, expect=400)["error"])
        self.post("punto", {"joints": [0, 0, 0, 120]})
        self.assertIn("Punto 1", self.post("editar", {"index": 0, "joints": [0, 135, 0, 0]}, expect=400)["error"])
        status, trajectory = self.request("GET", "/api/trayectoria")
        self.assertEqual(self.joints(trajectory), [[0, 0, 0, 12000]])

    # --- Edición de la lista ---------------------------------------------

    def test_tramo_parameters_are_edited_per_point(self):
        self.post("punto", {"joints": [0, 0, 0, 120]})
        trajectory = self.post("editar", {"index": 0, "kind": "PTP", "speed": 80, "wait": 1.5})
        self.assertEqual({k: trajectory["points"][0][k] for k in ("kind", "speed", "wait")},
                         {"kind": "PTP", "speed": 80, "wait": 1.5})
        for request in ({"kind": "CIRC"}, {"speed": 0}, {"speed": 101}, {"speed": 50.5}, {"wait": -1},
                        {"wait": "1"}, {"wait": 1e9}, {"index": 1, "speed": 10}, {"index": True, "speed": 10}):
            with self.subTest(request=request):
                self.post("editar", dict({"index": 0}, **request), expect=400)

    def test_reorder_delete_and_overwrite_with_the_current_pose(self):
        uci = self.robot()
        for joints in ([0, 0, 0, 120], [10, -20, 0, 60], [20, -40, 0, 30]):
            self.post("punto", {"joints": joints})
        trajectory = self.post("mover", {"index": 2, "to": 0})
        self.assertEqual([p[0] for p in self.joints(trajectory)], [2000, 0, 1000])
        self.assertEqual(trajectory["selected"], 0)
        self.post("mover", {"index": 0, "to": 3}, expect=400)
        trajectory = self.post("borrar", {"index": 1})
        self.assertEqual([p[0] for p in self.joints(trajectory)], [2000, 1000])
        self.assertEqual(trajectory["selected"], 0)
        self.post("editar", {"index": 1, "kind": "PTP"})
        self.move(uci, "S IDLE 15 3000 -6000 1000 6000 0 16 0")
        trajectory = self.post("sobrescribir", {"index": 1})
        self.assertEqual(self.joints(trajectory)[1], [3000, -6000, 1000, 6000])
        self.assertEqual(trajectory["points"][1]["kind"], "PTP")  # cómo se llega no cambia
        self.post("borrar", {"index": 5}, expect=400)

    # --- Ir al punto -------------------------------------------------------

    def test_go_to_a_point_plans_first_and_moves_after_confirming(self):
        uci = self.robot()
        self.post("punto", {"joints": [30, -60, 10, 60]})
        plan = self.post("ir", {"index": 0})
        self.assertEqual(plan["target"], [3000, -6000, 1000, 6000])
        self.assertEqual(plan["speed"], 0.25)
        self.assertGreater(plan["duration_s"], 1)
        self.assertTrue(uci.silent(0.1))
        # La confirmación trae el destino que vio el operador.
        self.post("editar", {"index": 0, "joints": [20, -60, 10, 60]})
        self.assertIn("cambió", self.post("ir", {"index": 0, "confirm": True, "target": plan["target"]},
                                          expect=400)["error"])
        self.assertTrue(uci.silent(0.1))
        target = self.post("ir", {"index": 0})["target"]
        self.post("ir", {"index": 0, "confirm": True, "target": target}, expect=202)
        self.assertTrue(uci.receive().startswith("SEG 1 20 "))
        # Con el tramo en cola, el estado S todavía dice IDLE: no se captura.
        self.assertIn("moviendo", self.post("capturar", expect=400)["error"])
        self.post("ir", {"index": 3}, expect=400)

    # --- Archivo -----------------------------------------------------------

    def test_unsaved_changes_are_not_discarded_without_asking(self):
        self.post("punto", {"joints": [0, 0, 0, 120]})
        self.assertIn("sin guardar", self.post("nueva", expect=409)["error"])
        self.post("guardar", {"name": "uno"})
        self.post("punto", {"joints": [10, -20, 0, 60]})
        self.assertIn("sin guardar", self.post("cargar", {"file": "uno.json"}, expect=409)["error"])
        self.assertEqual(len(self.post("cargar", {"file": "uno.json", "discard": True})["points"]), 1)
        self.post("punto", {"joints": [10, -20, 0, 60]})
        self.assertEqual(self.post("nueva", {"discard": True})["points"], [])

    def test_save_writes_its_file_and_save_as_asks_before_overwriting(self):
        self.assertIn("puntos", self.post("guardar", {"name": "vacía"}, expect=400)["error"])
        self.post("punto", {"joints": [0, 0, 0, 120]})
        self.assertIn("nombre", self.post("guardar", expect=400)["error"])
        self.post("guardar", {"name": "Pick & place"})
        self.post("punto", {"joints": [10, -20, 0, 60]})
        trajectory = self.post("guardar")
        self.assertEqual((trajectory["file"], trajectory["dirty"]), ("pick-place.json", False))
        stored = json.loads((self.folder / "pick-place.json").read_text(encoding="utf-8"))
        self.assertEqual(len(stored["points"]), 2)
        # Guardar como: otro archivo; si ya existe, pregunta.
        self.post("guardar", {"name": "Copia"})
        self.assertIn("Ya existe", self.post("guardar", {"name": "pick place"}, expect=409)["error"])
        trajectory = self.post("guardar", {"name": "pick place", "overwrite": True})
        self.assertEqual((trajectory["name"], trajectory["file"]), ("pick place", "pick-place.json"))
        for name in ("", "   ", "../", 7, "x" * 61, "Con", "COM1"):
            with self.subTest(name=name):
                self.post("guardar", {"name": name}, expect=400)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["copia.json", "pick-place.json"])

    def test_loading_rejects_bad_files_saying_which_point_and_why(self):
        self.post("punto", {"joints": [0, 0, 0, 120]})
        self.post("guardar", {"name": "buena"})
        good = json.loads((self.folder / "buena.json").read_text(encoding="utf-8"))
        point = good["points"][0]
        bare = {key: value for key, value in point.items() if key != "tool"}

        def variant(points=None, **fields):
            return dict(good, points=points if points is not None else good["points"], **fields)

        cases = {
            "roto.json": ("{", "JSON"),
            "lista.json": ("[]", "objeto"),
            "formato.json": (variant(format="otra-cosa"), "formato"),
            "version.json": (variant(version=2), "versión 2"),
            "unidades.json": (variant(units={"joints": "grados"}), "unidades"),
            "sin-puntos.json": (variant(points=[]), "puntos"),
            "limite.json": (variant(points=[point, dict(bare, joints=[0, 14000, 0, 12000])]),
                            "Punto 2: J2 fuera de su recorrido"),
            "choque.json": (variant(points=[point, point, dict(bare, joints=[0, 13500, 0, 0])]),
                            "Punto 3: colisión"),
            "tipo.json": (variant(points=[dict(point, kind="lin")]), "Punto 1"),
            "falta.json": (variant(points=[{k: v for k, v in point.items() if k != "speed"}]), "Punto 1"),
            "sobra.json": (variant(points=[dict(point, velocidad=50)]), "velocidad"),
            "xyz.json": (variant(points=[dict(point, tool=dict(point["tool"], x=100.0))]),
                         "Punto 1: X, Y, Z y rumbo no coinciden"),
            "nombre.json": (variant(name=""), "nombre"),
        }
        for file, (document, message) in cases.items():
            self.write(file, document)
            with self.subTest(file=file):
                self.assertIn(message, self.post("cargar", {"file": file}, expect=400)["error"])
        # El rechazo no toca la trayectoria abierta.
        status, trajectory = self.request("GET", "/api/trayectoria")
        self.assertEqual((trajectory["name"], len(trajectory["points"])), ("buena", 1))
        # Sin XYZ derivados se aceptan: mandan las articulaciones (D13).
        self.write("sin-xyz.json", variant(points=[bare]))
        self.assertEqual(self.post("cargar", {"file": "sin-xyz.json"})["points"], trajectory["points"])

    def test_only_trajectory_files_of_its_folder_can_be_loaded(self):
        for file in ("../buena.json", "no-existe.json", "a/b.json", "c:x.json", ".json", 3):
            with self.subTest(file=file):
                self.post("cargar", {"file": file}, expect=400)
        self.write("grande.json", " " * (2 * 1024 * 1024))
        self.assertIn("grande", self.post("cargar", {"file": "grande.json"}, expect=400)["error"])

    def test_a_file_error_is_answered(self):
        self.post("punto", {"joints": [0, 0, 0, 120]})
        self.manager.folder = self.folder / "archivo"
        self.manager.folder.write_text("no es una carpeta", encoding="utf-8")
        self.assertIn("Error de archivo", self.post("guardar", {"name": "uno"}, expect=500)["error"])
        self.assertTrue(self.request("GET", "/api/trayectoria")[1]["dirty"])

    def test_unknown_routes(self):
        self.post("nada", expect=404)


if __name__ == "__main__":
    unittest.main()
