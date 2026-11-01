"""Camino serie de punta a punta (issue #16): la URC real opera el firmware
por un puerto serie virtual y socat, como operará al UNO por USB.

    Session (URC) ◄─TCP─ socat ─PTY─ uci_serie (núcleo + capa de hardware serie)

firmware/pc/uci_serie hace de UNO: crea el PTY y espera a que lo abran. socat
lo abre con la misma receta que el USB del UNO y se conecta a la URC, que no
sabe nada del serie.

Necesita socat y un compilador de C++ POSIX. En Windows, los dos del mismo
MSYS2 (C:\\msys64, o SOCAT apuntando a su socat.exe): solo los programas del
runtime de MSYS2 ven sus PTY. Sin ellos, se omite. Receta en docs/ARDUINO_UNO.md.
"""

import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from tests.test_firmware import COMPILER, FLAGS
from tests.test_urc import wait_for
from urc.session import Session


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware"
ALL_HOMED = 0x0F


def find_tools():
    """(socat, compilador POSIX) o (None, None)."""
    socat = os.environ.get("SOCAT") or shutil.which("socat")
    if sys.platform != "win32":
        return (socat, COMPILER) if socat and COMPILER else (None, None)
    if socat is None and Path(r"C:\msys64\usr\bin\socat.exe").exists():
        socat = r"C:\msys64\usr\bin\socat.exe"
    compiler = Path(socat).parent / "g++.exe" if socat else None
    return (socat, str(compiler)) if compiler and compiler.exists() else (None, None)


SOCAT, POSIX_COMPILER = find_tools()


@unittest.skipIf(SOCAT is None, "Sin socat y un compilador POSIX (en Windows, los de MSYS2)")
class SerialSocatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        tools = str(Path(POSIX_COMPILER).parent)
        cls.env = dict(os.environ, PATH=os.pathsep.join([tools, os.environ.get("PATH", "")]))
        cls.program = Path(cls.build.name) / "uci_serie"
        result = subprocess.run(
            # Con barras normales: el gcc de MSYS2 no resuelve los include relativos con «\».
            [POSIX_COMPILER, *FLAGS, (FIRMWARE / "pc" / "uci_serie.cpp").as_posix(),
             (FIRMWARE / "firmware.cpp").as_posix(), "-o", cls.program.as_posix()],
            capture_output=True, text=True, env=cls.env)
        if result.returncode != 0:
            cls.build.cleanup()
            raise AssertionError("No compila:\n" + result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.session = Session(port=0)
        self.addCleanup(self.session.close)
        self.uci = self.start([str(self.program)])
        self.open_port()

    def open_port(self):
        """La receta del UNO (docs/ARDUINO_UNO.md), con el PTY en lugar del USB."""
        port = self.wait_line(self.uci, re.compile(r"puerto serie en (\S+)")).group(1)
        self.socat = self.start([SOCAT, f"{port},b115200,rawer", f"TCP:127.0.0.1:{self.session.port}"])

    def start(self, command):
        process = subprocess.Popen(command, stderr=subprocess.PIPE, text=True, env=self.env)
        self.addCleanup(self.stop, process)
        process.lines = queue.Queue()
        process.reader = threading.Thread(target=lambda: [process.lines.put(line) for line in process.stderr],
                                          daemon=True)
        process.reader.start()
        return process

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
        # Con el proceso terminado, el lector llega al fin del pipe y lo suelta.
        process.reader.join(timeout=5)
        process.stderr.close()

    def wait_line(self, process, pattern, timeout=10):
        seen = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = process.lines.get(timeout=0.1)
            except queue.Empty:
                continue
            seen.append(line)
            match = pattern.search(line)
            if match:
                return match
        raise AssertionError("No apareció " + pattern.pattern + ":\n" + "".join(seen))

    def status(self, predicate, timeout=3):
        return wait_for(lambda: (lambda s: s if s and predicate(s) else None)(self.session.snapshot()["status"]),
                        timeout)

    def test_urc_operates_the_firmware_over_serial(self):
        session = self.session
        # Abrir el puerto reinicia la UCI: BOOT y estado periódico, sin corriente
        # (D40). El HELLO de la URC se pierde en el reinicio; BOOT ya identifica.
        self.status(lambda s: s["mode"] == "OFF", timeout=10)
        snapshot = session.snapshot()
        self.assertEqual(snapshot["firmware"], {"protocol": "scara/1", "version": 1})
        self.assertEqual(snapshot["boots"], 1)
        self.assertIn({"direction": "<", "line": "BOOT scara/1 1"}, snapshot["traffic"])

        session.enable()
        self.status(lambda s: s["mode"] == "IDLE")
        session.zero()
        self.status(lambda s: s["homed"] == ALL_HOMED)

        # Jog de J1 como lo pide la página: renovado cada 150 ms durante 1 s.
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            session.jog(1, "+")
            time.sleep(0.15)
        self.status(lambda s: s["mode"] == "JOG")
        session.jog_stop()
        stopped = self.status(lambda s: s["mode"] == "IDLE")
        j1, j2 = stopped["position"][:2]
        self.assertGreater(j1, 600, "J1 avanzó a 10 °/s (con referencia, D68) durante ~1 s")
        self.assertLess(j1, 1600)
        self.assertEqual(j2, 0, "el acople M1/M2 mantiene J2")
        self.assertEqual(stopped["homed"], ALL_HOMED)

        session.disable()
        self.status(lambda s: s["mode"] == "OFF" and s["homed"] == 0)
        snapshot = session.snapshot()
        self.assertEqual(snapshot["errors"], [])
        self.assertEqual(snapshot["rejected"], [])
        self.assertEqual(snapshot["boots"], 1)

    def test_closing_socat_disconnects_and_reopening_boots_again(self):
        self.status(lambda s: s["mode"] == "OFF", timeout=10)
        self.session.enable()
        self.status(lambda s: s["mode"] == "IDLE")
        # Cortar socat cierra el puerto: la UCI se apaga y la URC espera.
        self.socat.terminate()
        self.socat.wait(timeout=5)
        self.wait_line(self.uci, re.compile("puerto cerrado"))
        wait_for(lambda: not self.session.snapshot()["connected"])
        # Volver a abrirlo reinicia la UCI: BOOT, sin corriente (D43).
        self.open_port()
        self.status(lambda s: s["mode"] == "OFF", timeout=10)
        self.assertEqual(self.session.snapshot()["boots"], 2)


if __name__ == "__main__":
    unittest.main()
