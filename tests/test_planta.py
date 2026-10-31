"""Pruebas del modelo de motor de la planta de Webots (N2, D64), en la PC.

Compila webots/controllers/scara_uci/test/stepper.cpp con el mismo
compilador que las pruebas del firmware: no necesita Webots.
"""

from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.test_firmware import COMPILER, FIRMWARE, FLAGS, ROOT, compiler_env


CONTROLLER = ROOT / "webots" / "controllers" / "scara_uci"


@unittest.skipIf(COMPILER is None, "Sin compilador de C++: instalar uno o definir CXX")
class StepperModelTests(unittest.TestCase):
    def test_torque_model(self):
        with tempfile.TemporaryDirectory() as build:
            program = Path(build) / "stepper"
            env = compiler_env()
            result = subprocess.run([COMPILER, *FLAGS, f"-I{FIRMWARE}", str(CONTROLLER / "test" / "stepper.cpp"),
                                     "-o", str(program)], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, "No compila:\n" + result.stdout + result.stderr)
            result = subprocess.run([str(program)], capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
