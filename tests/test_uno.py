"""Pruebas de la capa de hardware del Arduino UNO (firmware/arduino).

- El generador de pulsos, que es C++ portable, se compila y se prueba en la PC
  con el mismo compilador que las conversaciones del firmware.
- El sketch se compila para el UNO con arduino-cli, si está (en el PATH o en
  ARDUINO_CLI, con el core arduino:avr instalado), y se verifica el uso de
  flash y RAM contra el presupuesto de la placa.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests.test_firmware import COMPILER, FLAGS


ROOT = Path(__file__).resolve().parents[1]
ARDUINO = ROOT / "firmware" / "arduino"
SKETCH = ARDUINO / "scara_uci"
FLASH_MAX = 32256        # bytes: 32 KB menos el bootloader del UNO
RAM_MAX = 2048           # bytes
# Arduino avisa «poca memoria» pasado el 75 %: el resto es la pila.
RAM_GLOBALS_MAX = RAM_MAX * 3 // 4


def dll_env(compiler):
    """En Windows, el ejecutable necesita las DLL de la misma instalación."""
    compiler_dir = Path(compiler).parent
    dll_dirs = [str(path) for path in (compiler_dir, compiler_dir / "cpp") if path.is_dir()]
    return dict(os.environ, PATH=os.pathsep.join(dll_dirs + [os.environ.get("PATH", "")]))


@unittest.skipIf(COMPILER is None, "Sin compilador de C++: instalar uno o definir CXX")
class StepPulserTests(unittest.TestCase):
    def test_pulser(self):
        env = dll_env(COMPILER)
        with tempfile.TemporaryDirectory() as build:
            program = Path(build) / "pulsos"
            sources = [str(ARDUINO / "test" / "pulsos.cpp"), str(SKETCH / "pulsos.cpp")]
            result = subprocess.run([COMPILER, *FLAGS, "-I", str(ROOT / "firmware"), *sources, "-o", str(program)],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, "No compila:\n" + result.stdout + result.stderr)
            result = subprocess.run([str(program)], capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)


def find_arduino_cli():
    return os.environ.get("ARDUINO_CLI") or shutil.which("arduino-cli")


ARDUINO_CLI = find_arduino_cli()


def compile_for_uno(arduino_cli, build):
    """Compila el sketch con el núcleo como biblioteca; devuelve (flash, ram)."""
    command = [arduino_cli, "compile", "--fqbn", "arduino:avr:uno", "--warnings", "all",
               "--library", str(ROOT / "firmware"), "--build-path", str(build), str(SKETCH)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise AssertionError("No compila para el UNO:\n" + result.stdout + result.stderr)
    flash = re.search(r"Sketch uses (\d+) bytes", result.stdout)
    ram = re.search(r"Global variables use (\d+) bytes", result.stdout)
    if not flash or not ram:
        raise AssertionError("arduino-cli no informó el uso de memoria:\n" + result.stdout)
    return int(flash.group(1)), int(ram.group(1)), result.stdout + result.stderr


@unittest.skipIf(ARDUINO_CLI is None, "Sin arduino-cli: instalarlo o definir ARDUINO_CLI")
class UnoBuildTests(unittest.TestCase):
    def test_fits_in_the_uno(self):
        with tempfile.TemporaryDirectory() as build:
            flash, ram, output = compile_for_uno(ARDUINO_CLI, build)
        print(f"\nUNO: flash {flash} de {FLASH_MAX} bytes, RAM global {ram} de {RAM_MAX} bytes")
        self.assertLessEqual(flash, FLASH_MAX)
        self.assertLessEqual(ram, RAM_GLOBALS_MAX, "La pila del UNO necesita al menos un 25 % de la RAM")
        # Sin avisos del compilador en nuestro código (los del core de Arduino no cuentan).
        ours = [line for line in output.splitlines()
                if "warning:" in line and ("firmware" in line.replace("\\", "/"))]
        self.assertEqual(ours, [], "\n".join(ours))


if __name__ == "__main__":
    unittest.main()
