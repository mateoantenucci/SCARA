"""Pruebas del firmware C++ en la PC: compila el núcleo con la capa de hardware
falsa y corre cada conversación de firmware/test/conversaciones.

Necesita un compilador de C++. Busca CXX, luego c++, g++ o clang++ en el PATH
y, en Windows, el g++ que trae Webots (msys64). Sin compilador, se omite.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware"
CONVERSATIONS = sorted((FIRMWARE / "test" / "conversaciones").glob("*.txt"))
FLAGS = ["-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic"]
# Lo que el Arduino UNO no tiene: el núcleo se compila sin ellos.
CORE_FLAGS = ["-fno-exceptions", "-fno-rtti"]
DYNAMIC_MEMORY = ("malloc", "calloc", "realloc", "free", "_Znwm", "_Znwj", "_Znam", "_Znaj")


def find_compiler():
    candidates = [os.environ.get("CXX"), "c++", "g++", "clang++"]
    found = [shutil.which(name) for name in candidates if name]
    if sys.platform == "win32":
        webots = Path(os.environ.get("WEBOTS_HOME", r"C:\Program Files\Webots"))
        bundled = webots / "msys64" / "mingw64" / "bin" / "g++.exe"
        found.append(str(bundled) if bundled.exists() else None)
    return next((path for path in found if path), None)


COMPILER = find_compiler()


@unittest.skipIf(COMPILER is None, "Sin compilador de C++: instalar uno o definir CXX")
class FirmwareConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        build = Path(cls.build.name)
        # En Windows, el ejecutable necesita las DLL de la misma instalación;
        # Webots guarda las de C++ en mingw64/bin/cpp.
        compiler_dir = Path(COMPILER).parent
        dll_dirs = [str(path) for path in (compiler_dir, compiler_dir / "cpp") if path.is_dir()]
        cls.env = dict(os.environ, PATH=os.pathsep.join(dll_dirs + [os.environ.get("PATH", "")]))
        cls.core = build / "firmware.o"
        cls.program = build / "conversacion"
        cls.compile(["-c", str(FIRMWARE / "firmware.cpp"), *CORE_FLAGS, "-o", str(cls.core)])
        cls.compile([str(FIRMWARE / "test" / "conversacion.cpp"), str(cls.core), "-o", str(cls.program)])

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    @classmethod
    def compile(cls, arguments):
        result = subprocess.run([COMPILER, *FLAGS, *arguments], capture_output=True, text=True, env=cls.env)
        if result.returncode != 0:
            cls.build.cleanup()
            raise AssertionError("No compila:\n" + result.stdout + result.stderr)

    def test_conversations(self):
        self.assertTrue(CONVERSATIONS, "No hay conversaciones de ejemplo")
        for path in CONVERSATIONS:
            with self.subTest(conversacion=path.name):
                result = subprocess.run([str(self.program), str(path)], capture_output=True, text=True,
                                        env=self.env, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_core_has_no_dynamic_memory(self):
        nm = shutil.which("nm", path=self.env["PATH"]) or shutil.which("gcc-nm", path=self.env["PATH"])
        if nm is None:
            self.skipTest("Sin nm para inspeccionar el objeto")
        result = subprocess.run([nm, "-u", str(self.core)], capture_output=True, text=True, env=self.env, check=True)
        undefined = {line.split()[-1].lstrip("_") for line in result.stdout.splitlines() if line.strip()}
        used = sorted(name for name in DYNAMIC_MEMORY if name.lstrip("_") in undefined)
        self.assertEqual(used, [], "El núcleo no debe usar memoria dinámica")


if __name__ == "__main__":
    unittest.main()
