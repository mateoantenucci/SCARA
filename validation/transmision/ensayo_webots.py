"""Ensayo de la transmisión N1 (issue #7) en Webots.

La sesión real de la URC, en el puerto 9101, contra el controlador scara_uci
compilado, en un Webots minimizado y sin vista. Un supervisor aparte
(observador.py) mide la posición física simulada sin tocar al robot, y el
ensayo la compara con la posición estimada por pasos que informa el firmware:
  1-4. jog articular de J1–J4: cada articulación se mueve sola, también J1
       (el firmware compensa el acople moviendo M1 y M2 juntos);
  5.   jog por motor de M1: cambian J1 y J2, y el rumbo de la herramienta no;
  6.   resolución: un jog lento de J3 avanza en escalones de un paso
       (0,05625° con 1/8: 360° / 1600 / 4).

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/transmision/ensayo_webots.py validation/transmision/ensayo_webots.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.session import Session  # noqa: E402

PORT = 9101
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_transmision.wbt"
OBSERVER = ROOT / "webots" / "controllers" / "_observador_transmision"
LOG = open(sys.argv[1], "w", encoding="utf-8")
# El microstepping de firmware/config.h (D44), el mismo con que se compiló el controlador.
MICROSTEPS = int(re.search(r"#define SCARA_MICROSTEPS (\d+)", (ROOT / "firmware" / "config.h").read_text()).group(1))
STEP = 36000 / (200 * MICROSTEPS * 4)  # centésimas de grado por paso en J1–J3: 5,625 con 1/8
NAMES = ("J1", "J2", "J3", "J4")


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


def physical(path):
    """Última muestra del observador: J1–J4 físicas y rumbo, en unidades de scara/1."""
    for _ in range(100):
        try:
            sample = json.loads(path.read_text(encoding="utf-8"))
            return sample["joints"], sample["heading"]
        except (OSError, ValueError):
            time.sleep(0.02)  # el observador la está reemplazando
    raise AssertionError("el observador no escribe")


def estimated(session):
    return session.snapshot()["status"]["position"]


def settle(session, path):
    """Espera que el firmware frene y que la física simulada deje de moverse.

    Webots lleva cada articulación a la posición que ordena la planta con un
    control de posición de velocidad, aceleración y par limitados: el brazo,
    con más inercia, tarda más de medio segundo en asentarse.
    """
    wait(session, lambda s: s["status"]["mode"] == "IDLE")
    previous, _ = physical(path)
    for _ in range(50):
        time.sleep(0.2)
        joints, _ = physical(path)
        # J4 vibra alrededor de un centésimo de mm sosteniendo su peso.
        if all(abs(a - b) < limit for a, b, limit in zip(previous, joints, (0.2, 0.2, 0.2, 3))):
            return
        previous = joints
    raise AssertionError(f"la física simulada no se asienta: {previous} → {joints}")


def jog(session, order, seconds, path):
    """Envía un JOG y lo frena después de `seconds`."""
    session.order(order)
    time.sleep(seconds)
    session.order("JOG STOP")
    settle(session, path)


def rounded(values):
    return [round(value, 1) for value in values]


def check_joint_jog(session, sample, joint):
    before, _ = physical(sample)
    # J4 arranca abajo, en su tope: sube (J4 es positivo hacia abajo).
    jog(session, f"JOG {joint + 1} {'-' if joint == 3 else '+'} 500", 1.5, sample)
    after, _ = physical(sample)
    est = estimated(session)
    moved = [b - a for a, b in zip(before, after)]
    log(f"{joint + 1} jog articular de {NAMES[joint]}: estimada {est}, física {rounded(after)}, "
        f"cambio físico {rounded(moved)}")
    # J1–J3: un paso, 5,6 centésimas de grado. J4: el deslizador de Webots
    # sostiene el peso con control de posición y fuerza limitada, y cede unas
    # décimas de mm cuando el brazo gira; no es la transmisión (ver el informe).
    tolerance = [STEP, STEP, STEP, 30]
    for other in range(4):
        assert abs(after[other] - est[other]) <= tolerance[other], (NAMES[other], after[other], est[other])
        if other != joint:
            assert abs(moved[other]) <= tolerance[other], (NAMES[other], "se movió", moved[other])
    assert abs(moved[joint]) > 300, (NAMES[joint], "no se movió")


def staircase(session, sample):
    """Muestrea J3 física durante un jog lento: tiene que quedar en múltiplos de un paso."""
    start, _ = physical(sample)
    session.order("JOG 3 + 10")  # 0,1 °/s: un paso cada 0,56 s
    levels, samples, off = set(), 0, 0
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        joints, _ = physical(sample)
        steps = (joints[2] - start[2]) / STEP
        samples += 1
        if abs(steps - round(steps)) > 0.1:
            off += 1  # el control de posición de Webots tarda ~0,2 s en asentar cada paso
        else:
            levels.add(round(steps))
        time.sleep(0.05)
    session.order("JOG STOP")
    settle(session, sample)
    end, _ = physical(sample)
    return sorted(levels), samples, off, (end[2] - start[2]) / STEP


# El mismo mundo, con el controlador apuntando al puerto del ensayo y el observador.
OBSERVER.mkdir()
shutil.copy(Path(__file__).with_name("observador.py"), OBSERVER / "_observador_transmision.py")
sample_file = Path(tempfile.mkdtemp()) / "fisica.json"
world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', f'controller "scara_uci"\n  controllerArgs ["--port", "{PORT}", "--sim-port", "0", "--desvio", "0"]')
world += ('Robot {\n  name "observador"\n  controller "_observador_transmision"\n'
          f'  controllerArgs ["{sample_file.as_posix()}"]\n  supervisor TRUE\n}}\n')
WORLD.write_text(world, encoding="utf-8")
session = Session(port=PORT)
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
try:
    wait(session, lambda s: s["status"] is not None)
    session.enable()
    session.zero()
    wait(session, lambda s: s["referenced"])
    rest, heading = physical(sample_file)
    log("0 en reposo y referenciada: estimada", estimated(session), "física", rounded(rest), "rumbo", round(heading, 1))
    for joint in range(4):
        check_joint_jog(session, sample_file, joint)
    before, heading_before = physical(sample_file)
    jog(session, "JOG M1 + 500", 1.5, sample_file)
    after, heading_after = physical(sample_file)
    moved = [b - a for a, b in zip(before, after)]
    log("5 jog por motor de M1: estimada", estimated(session), "física", rounded(after), "cambio físico",
        rounded(moved), "rumbo antes", round(heading_before, 1), "después", round(heading_after, 1))
    assert moved[0] > 300 and abs(moved[0] + moved[1]) <= STEP, "M1 solo: J2 tiene que cambiar al revés que J1"
    assert abs(moved[2]) <= STEP and abs(heading_after - heading_before) <= STEP, "M1 solo: el rumbo no cambia"
    levels, samples, off, moved = staircase(session, sample_file)
    log(f"6 resolución: jog de J3 a 0,1 °/s durante 6 s; {samples} muestras de la física, {off} en transición; "
        f"escalones vistos (en pasos de {STEP} centésimas de grado): {levels}; al frenar, {moved:.3f} pasos")
    assert len(levels) >= 5 and levels == list(range(levels[0], levels[-1] + 1)), "J3 no avanza de a un paso"
    assert abs(moved - round(moved)) < 0.02 and round(moved) == levels[-1], "J3 no se detiene en un paso entero"
    log("ENSAYO OK")
finally:
    webots.kill()
    webots.wait()
    session.close()
    WORLD.unlink()
    # Los controladores tardan un momento en soltar sus archivos.
    for attempt in range(50):
        try:
            shutil.rmtree(OBSERVER)
            break
        except PermissionError:
            time.sleep(0.1)
    shutil.rmtree(sample_file.parent, ignore_errors=True)
