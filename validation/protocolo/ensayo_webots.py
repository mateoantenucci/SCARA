"""Ensayo de punta a punta del protocolo scara/1 (issue #6) en Webots.

La sesión real de la URC, en el puerto 9100 para no chocar con una URC o un
Webots abiertos, contra el controlador scara_uci compilado, en un Webots
minimizado y sin vista. Recorre: arranque sin corriente, ENABLE, ZERO, jog,
STOP, HALT, corte de la URC (F4), DISABLE y reinicio de la UCI (F5).

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/protocolo/ensayo_webots.py validation/protocolo/ensayo_webots.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.session import Session  # noqa: E402

WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_9100.wbt"
LOG = open(sys.argv[1], "w", encoding="utf-8")


def log(*parts):
    print(*parts, file=LOG, flush=True)


def wait(session, predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = session.snapshot()
        if predicate(state):
            return state
        time.sleep(0.05)
    raise AssertionError(f"no se cumplió; estado: {session.snapshot()}")


def status(session):
    s = session.snapshot()["status"]
    return None if s is None else (s["mode"], s["homed"], s["position"])


def launch():
    return subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                             "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)


# El mismo mundo, con el controlador apuntando al puerto 9100.
world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
WORLD.write_text(world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs ["--port", "9100", "--sim-port", "0", "--desvio", "0"]'),
                 encoding="utf-8")
session = Session(port=9100)
webots = launch()
try:
    state = wait(session, lambda s: s["boots"] == 1 and s["status"] is not None)
    log("1 conectada:", state["message"], status(session))
    assert state["status"]["mode"] == "OFF"
    session.jog(1, "+")
    wait(session, lambda s: any("deshabilitado" in e for e in s["errors"]))
    session.jog_stop()
    log("2 jog sin corriente rechazado:", session.snapshot()["errors"][-1])
    session.enable()
    wait(session, lambda s: s["status"]["mode"] == "IDLE")
    session.zero()
    wait(session, lambda s: s["referenced"])
    log("3 habilitada y referenciada:", status(session))
    session.order("JOG 1 + 500")
    time.sleep(2)
    session.stop()
    time.sleep(0.3)
    a = status(session)
    time.sleep(1)
    b = status(session)
    log("4 STOP tras 2 s de jog:", a, "1 s después:", b)
    assert a == b and a[0] == "IDLE" and a[1] == 15 and 800 <= a[2][0] <= 1100
    session.order("JOG 1 - 500")
    time.sleep(1)
    session.halt()
    time.sleep(0.3)
    log("5 HALT en movimiento:", status(session))
    assert status(session)[1] == 0
    session.zero()
    wait(session, lambda s: s["referenced"])
    session.order("JOG 1 + 500")
    time.sleep(1)
    # F4: la URC deja de hablar (se cierra la sesión) y el firmware frena solo.
    session.close()
    time.sleep(3)
    session = Session(port=9100)
    state = wait(session, lambda s: s["status"] is not None)
    a = status(session)
    time.sleep(1)
    b = status(session)
    log("6 tras cortar la URC 3 s y reconectar:", a, b, "boots:", state["boots"], "errores:", state["errors"])
    assert a == b and a[0] == "IDLE" and a[1] == 15 and state["boots"] == 0
    session.disable()
    wait(session, lambda s: s["status"]["mode"] == "OFF")
    log("7 DISABLE:", status(session))
    assert status(session)[1] == 0
    # F5: la UCI se reinicia (Webots de nuevo).
    session.enable()
    session.zero()
    wait(session, lambda s: s["referenced"])
    webots.kill()
    webots.wait()
    webots = launch()
    state = wait(session, lambda s: s["boots"] == 1 and s["status"] is not None)
    log("8 reinicio de la UCI:", state["message"], "referenciado:", state["referenced"], status(session))
    assert not state["referenced"]
    log("ENSAYO OK")
finally:
    webots.kill()
    session.close()
    WORLD.unlink()
