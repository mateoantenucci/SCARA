"""Campaña de validación en Webots (issue #18): los escenarios y su registro.

No corre Webots: verifica que cada escenario dice lo que exige la spec
(condición inicial, resultado esperado, tolerancia y ensayo que lo ejecuta),
que están todos los de la spec y que el registro de la última campaña los
trae a todos, aprobados y con la versión ensayada.
"""

import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "validation" / "campana"
_spec = importlib.util.spec_from_file_location("campana", FOLDER / "campana.py")
campana = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(campana)


class ScenarioTests(unittest.TestCase):
    def test_every_scenario_is_complete_and_runs_in_an_existing_ensayo(self):
        ids = [e["id"] for e in campana.ESCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        for scenario in campana.ESCENARIOS:
            with self.subTest(scenario["id"]):
                for key in ("nombre", "inicial", "esperado", "tolerancia", "pasos"):
                    self.assertTrue(scenario[key].strip(), key)
                self.assertTrue((ROOT / campana.ENSAYOS[scenario["ensayo"]][0]).is_file())

    def test_the_spec_scenarios_are_all_there(self):
        ids = {e["id"] for e in campana.ESCENARIOS}
        # Seam 3: homing desde el reposo, teach & play LIN y PTP, fallas F1–F5.
        self.assertLessEqual({"H1", "H2", "T1", "T2", "T3", "F1", "F2", "F3a", "F3b", "F4", "F5"}, ids)

    def test_ensayos_use_distinct_ports_away_from_the_operator(self):
        ports = [port for _, used, _ in campana.ENSAYOS.values() for port in used]
        self.assertEqual(len(ports), len(set(ports)))
        self.assertFalse({9000, 9001} & set(ports))


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((FOLDER / "campana.json").read_text(encoding="utf-8"))

    def test_the_last_campaign_passed_every_scenario(self):
        self.assertEqual([e["id"] for e in self.record["escenarios"]], [e["id"] for e in campana.ESCENARIOS])
        for scenario in self.record["escenarios"]:
            with self.subTest(scenario["id"]):
                self.assertEqual(scenario["resultado"], "OK")
                self.assertTrue((ROOT / scenario["registro"]).is_file())
                self.assertIn("ENSAYO OK", (ROOT / scenario["registro"]).read_text(encoding="utf-8", errors="replace"))

    def test_the_version_is_identified(self):
        version = self.record["version"]
        self.assertRegex(version["commit"], r"^[0-9a-f]{40}$")
        hashes = version["sha256"]
        # El controlador compilado: scara_uci.exe en Windows, scara_uci en macOS.
        self.assertTrue(any(path.startswith("webots/controllers/scara_uci/scara_uci") for path in hashes))
        self.assertTrue(any(re.fullmatch(r"trayectorias/demo-.*\.json", path) for path in hashes))
        for digest in hashes.values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
