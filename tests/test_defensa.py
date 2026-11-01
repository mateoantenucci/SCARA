"""El guion de la defensa (issue #20) cita cosas que existen.

docs/DEFENSA.md se sigue en vivo frente al profesor: un archivo movido, un
botón renombrado o una decisión renumerada lo dejarían desactualizado sin que
nada falle. Esta prueba verifica que:
- cada D-número citado esté en el registro de decisiones, y cada ADR en docs/adr;
- cada decisión del registro tenga al menos una pregunta que la cite: una
  decisión nueva necesita su respuesta antes de la defensa;
- los enlaces relativos y las rutas del repo citadas existan;
- los comandos `python -m …` y `python <script>` apunten a módulos y scripts
  que existen, con opciones que la URC acepta;
- lo que la demostración cita de la página («…») esté en la URC, y el rechazo
  del LIN que se muestra sea el que da la validación;
- los tiempos por bloque sumen el total.
"""

import importlib.util
import json
import re
import unittest
from pathlib import Path

from urc import validation
from urc.trajectories import DEFAULT_FOLDER

ROOT = Path(__file__).resolve().parents[1]
GUION = ROOT / "docs" / "DEFENSA.md"
TEXT = GUION.read_text(encoding="utf-8")
REGISTRO = (ROOT / "docs" / "REGISTRO_DE_DECISIONES.md").read_text(encoding="utf-8")
URC_TEXT = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "urc").iterdir())
                     if path.suffix in {".py", ".js", ".html"})
CARPETAS = ("docs", "firmware", "urc", "webots", "validation", "trayectorias", "tools", "tests", "config")


def section(number):
    """Texto de la sección `## number.` hasta la siguiente."""
    match = re.search(rf"^## {number}\. .*?(?=^## \d+\. |\Z)", TEXT, re.S | re.M)
    assert match, f"falta la sección {number}"
    return match.group(0)


class DefenseScriptTests(unittest.TestCase):
    def test_cada_decision_citada_esta_en_el_registro(self):
        cited = {int(number) for number in re.findall(r"\bD(\d+)\b", TEXT)}
        recorded = {int(number) for number in re.findall(r"^\*\*D(\d+) ·", REGISTRO, re.M)}
        self.assertTrue(cited)
        self.assertEqual(cited - recorded, set())

    def test_cada_decision_del_registro_tiene_su_pregunta(self):
        recorded = {int(number) for number in re.findall(r"^\*\*D(\d+) ·", REGISTRO, re.M)}
        answered = {int(number) for number in re.findall(r"\bD(\d+)\b", section(4))}
        self.assertEqual(recorded - answered, set())

    def test_cada_adr_citado_existe(self):
        cited = set(re.findall(r"ADR (\d{4})", TEXT))
        existing = {path.name[:4] for path in (ROOT / "docs" / "adr").glob("*.md")}
        self.assertTrue(cited)
        self.assertEqual(cited - existing, set())

    def test_enlaces_relativos_existen(self):
        for target in re.findall(r"\]\(([^)\s]+)\)", TEXT):
            if re.match(r"[a-z]+:", target):
                continue
            path = target.split("#", 1)[0]
            with self.subTest(target=target):
                self.assertTrue((GUION.parent / path).exists())

    def test_rutas_citadas_existen(self):
        for code in re.findall(r"`([^`\n]+)`", TEXT):
            for token in code.split():
                token = token.strip("'\";,")
                if token.startswith(tuple(f"{folder}/" for folder in CARPETAS)):
                    with self.subTest(path=token):
                        self.assertTrue((ROOT / token).exists())
                elif re.fullmatch(r"demo-[\w-]+\.json", token):
                    with self.subTest(demo=token):
                        self.assertTrue((DEFAULT_FOLDER / token).exists())

    def test_comandos_de_python_existen(self):
        commands = re.findall(r"^\s*python (.+)$", TEXT, re.M)
        self.assertTrue(commands)
        for command in commands:
            words = command.split()
            with self.subTest(command=command):
                if words[0] == "-m":
                    self.assertIsNotNone(importlib.util.find_spec(words[1]))
                else:
                    self.assertTrue((ROOT / words[0]).exists())
        app = (ROOT / "urc" / "app.py").read_text(encoding="utf-8")
        for flag in re.findall(r"python -m urc\.app[^\n`]*?(--[\w-]+)", TEXT):
            self.assertIn(f'"{flag}"', app)

    def test_lo_que_cita_la_demostracion_esta_en_la_urc(self):
        rejection = self.rejection()
        quoted = re.findall(r"«([^»]+)»", section(2))
        self.assertIn(rejection, quoted)
        for text in quoted:
            if text != rejection:
                with self.subTest(text=text):
                    self.assertIn(text, URC_TEXT)

    def rejection(self):
        """El rechazo del LIN del punto 3 de la demo del barrido, como lo da la validación (D55)."""
        points = json.loads((DEFAULT_FOLDER / "demo-barrido-ptp.json").read_text(encoding="utf-8"))["points"]
        with self.assertRaises(validation.Rejection) as caught:
            validation.check_tramo("LIN", tuple(points[1]["joints"]), tuple(points[2]["joints"]), 1.0, 3)
        self.assertEqual(caught.exception.reason, "codo")
        return str(caught.exception)

    def test_los_bloques_suman_el_total(self):
        rows = [row.split("|") for row in section(3).splitlines() if row.startswith("| ")]
        minutes = [cells[4].strip() for cells in rows if re.fullmatch(r"\*{0,2}\d+\*{0,2}", cells[4].strip())]
        *blocks, total = minutes
        self.assertTrue(blocks)
        self.assertEqual(sum(int(value) for value in blocks), int(total.strip("*")))


if __name__ == "__main__":
    unittest.main()
