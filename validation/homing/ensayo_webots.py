"""Ensayo de los sensores Hall y el homing (issue #8) en Webots.

La sesión real de la URC, en el puerto 9103, contra el controlador scara_uci
compilado, en un Webots minimizado y sin vista. Los Hall son imanes (Emitter
de radio) y KY-003 (Receiver) del SCARA.proto: se activan por geometría. El
observador del ensayo de transmisión (validation/transmision/observador.py),
en modo absoluto, mide la posición física simulada.

Dos corridas:
  A. Arranque justo en la pose de reposo (--desvio 0):
     1. sin referencia, un jog de J4 hacia arriba pedido a 10 mm/s va a 5 mm/s,
        sale del imán de abajo y frena solo al activarse el de arriba (ERR 10);
        de vuelta hacia abajo, frena en el de abajo;
     2. homing: J4, J1, J2 y J3 referenciados en ese orden, cada uno en el
        flanco de su Hall; la URC vuelve sola a la pose de reposo;
     3. todo el camino físico, desde el arranque, pasa el chequeo de
        colisiones del repositorio: no toca la torre.
  B. Arranque con un desvío al azar de hasta ±10° en J1–J3 (el valor por
     defecto del mundo): el homing termina igual en la pose de reposo.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/homing/ensayo_webots.py validation/homing/ensayo_webots.log
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
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scara.collisions import CollisionChecker  # noqa: E402
from scara.kinematics import load_config  # noqa: E402
from urc import planner  # noqa: E402
from urc.session import Session  # noqa: E402

PORT = 9103
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_homing.wbt"
OBSERVER = ROOT / "webots" / "controllers" / "_observador_homing"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
STEP = 5.625      # centésimas de grado por paso de J1–J3 con 1/8
EDGES = [int(v) for v in re.search(r"HALL_EDGE\[MOTOR_COUNT\] = \{([^}]*)\}",
                                   (ROOT / "firmware" / "config.h").read_text(encoding="utf-8")).group(1).split(",")]
REST = (0, 0, 0, 12000)
LAG = (3 * STEP, 3 * STEP, 3 * STEP, 15)  # atraso de la física de Webots al referenciar


def log(*parts):
    print(*parts, file=LOG, flush=True)


def wait(session, predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = session.snapshot()
        if predicate(state):
            return state
        time.sleep(0.02)
    raise AssertionError(f"no se cumplió; estado: {session.snapshot()}")


class Recorder:
    """Muestras del observador: tiempo simulado y J1–J4 físicas, en unidades de scara/1."""

    def __init__(self, path):
        self.path, self.samples, self.running = path, [], True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        last = None
        while self.running:
            try:
                sample = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                time.sleep(0.005)  # el observador la está reemplazando
                continue
            if sample["t"] != last:
                last = sample["t"]
                self.samples.append((sample["t"], sample["joints"]))
            time.sleep(0.005)

    def physical(self):
        return self.samples[-1][1]


def rounded(values):
    return [round(v, 1) for v in values]


def settled(recorder, estimated=None):
    """Espera que la física quede quieta y, con referencia, donde el firmware cree que está.

    Sin referencia, la estimada cuenta desde el arranque: no se compara.
    """
    previous = recorder.physical()
    for _ in range(100):
        time.sleep(0.2)
        joints = recorder.physical()
        still = all(abs(a - b) < limit for a, b, limit in zip(previous, joints, (0.3, 0.3, 0.3, 3)))
        if still and (estimated is None or all(abs(a - b) <= limit for a, b, limit in
                                                  zip(joints, estimated, LAG))):
            return joints
        previous = joints
    raise AssertionError(f"la física no se asienta: {previous}, estimada {estimated}")


def jog_until_hall(session, recorder, order, errors):
    """Jog sin referencia hasta que el firmware lo frena con ERR 10; devuelve la física y la velocidad."""
    session.order(order)
    time.sleep(1)  # ya en marcha: sin el arranque ni la demora de la URC
    start_t, start_q = recorder.samples[-1]
    time.sleep(2)
    t1, q1 = recorder.samples[-1]
    speed = abs(q1[3] - start_q[3]) / (t1 - start_t)
    state = wait(session, lambda s: len(s["errors"]) == errors, timeout=60)
    assert state["errors"][-1].startswith("ERR 10 fin"), state["errors"]
    joints = settled(recorder)
    return joints, speed, state


def path_conflicts(samples, checker, config):
    """Choques en el camino físico: cada par de muestras cada 50 ms, con el chequeo del repositorio."""
    poses = [planner.units_to_si(tuple(round(v) for v in q)) for _, q in samples[::5]]
    limits = config["limits"]
    poses = [[min(max(v, low), high) for v, (low, high) in zip(q, limits)] for q in poses]
    for a, b in zip(poses, poses[1:]):
        conflict = checker.first_conflict(a, b)
        if conflict:
            return conflict
    return None


def run(label, deviation, jog_test):
    OBSERVER.mkdir(exist_ok=True)
    shutil.copy(ROOT / "validation" / "transmision" / "observador.py", OBSERVER / "_observador_homing.py")
    sample_file = Path(tempfile.mkdtemp()) / "fisica.json"
    world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
    world = world.replace('controller "scara_uci"', f'controller "scara_uci"\n  controllerArgs ["--port", "{PORT}", '
                                                     f'"--sim-port", "0", "--desvio", "{deviation}"]')
    world += ('Robot {\n  name "observador"\n  controller "_observador_homing"\n'
              f'  controllerArgs ["{sample_file.as_posix()}", "absoluto"]\n  supervisor TRUE\n}}\n')
    WORLD.write_text(world, encoding="utf-8")
    session = Session(port=PORT)
    webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                               "--stdout", "--stderr", str(WORLD)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace")
    recorder = None
    try:
        wait(session, lambda s: s["status"] is not None)
        recorder = Recorder(sample_file)
        wait(session, lambda s: len(recorder.samples) > 10)
        session.enable()
        state = wait(session, lambda s: s["status"]["mode"] == "IDLE")
        start = recorder.physical()
        log(f"{label}: arranque con desvío de hasta {deviation}°: física {rounded(start)}, "
            f"Hall {state['status']['hall']:04b} (bit 0 = J1), sin referencia")
        assert state["status"]["hall"] == 0b1000, "desde el reposo, solo J4 (abajo) está sobre un imán"
        if jog_test:
            joints, speed, state = jog_until_hall(session, recorder, "JOG 4 - 1000", 1)
            log(f"   jog de J4 hacia arriba pedido a 10 mm/s: fue a {speed / 100:.2f} mm/s, salió del imán de abajo "
                f"y frenó solo con ERR 10 fin en J4 = {joints[3] / 100:.2f} mm (flanco del Hall: {EDGES[3] / 100} mm)")
            # El pistón de Webots sigue a los pasos con unas décimas de segundo
            # de atraso: cuando el Hall se activa, los pasos ya van un poco más
            # allá, y la física termina ahí.
            assert abs(speed - 500) < 25 and abs(joints[3] - EDGES[3]) <= 80
            joints, speed, state = jog_until_hall(session, recorder, "JOG 4 + 1000", 2)
            log(f"   de vuelta hacia abajo: frenó en J4 = {joints[3] / 100:.2f} mm (flanco del imán de fin: 117 mm)")
            assert abs(joints[3] - 11700) <= 80
        session.home()
        state = wait(session, lambda s: s["homing"]["state"] != "en curso", timeout=180)
        assert state["homing"]["state"] == "terminado", state["homing"]
        wait(session, lambda s: s["status"]["mode"] == "IDLE" and s["status"]["homed"] == 15)
        edges = recorder.physical()
        log(f"   homing: ejes en orden {state['homing']['axes']}; en los flancos, física {rounded(edges)} "
            f"y estimada {state['status']['position']}")
        assert state["homing"]["axes"] == [4, 1, 2, 3]
        # Webots sigue a los pasos con atraso: cuando el Hall se activa en la
        # física, los pasos van unos dos más allá, y la referencia queda corrida
        # en esa cantidad. Con motores paso a paso reales no pasa.
        for joint in range(4):
            assert abs(edges[joint] - EDGES[joint]) <= LAG[joint], (joint, edges, EDGES)
        state = wait(session, lambda s: s["tramo"] is not None and s["tramo"]["done"] == s["tramo"]["segments"]
                     and s["status"]["mode"] == "IDLE", timeout=120)
        final = settled(recorder, list(REST))
        log(f"   vuelta al reposo (PTP de {state['tramo']['segments'] * 20 / 1000:.1f} s al 50 %): física "
            f"{rounded(final)}, estimada {state['status']['position']}, referenciado {state['referenced']}, "
            f"Hall {state['status']['hall']:04b}")
        assert state["referenced"] and state["status"]["hall"] == 0b1000
        assert all(abs(a - b) <= limit for a, b, limit in zip(final, REST, LAG))
        config = load_config()
        conflict = path_conflicts(recorder.samples, CollisionChecker(config), config)
        log(f"   camino físico completo ({len(recorder.samples)} muestras, cada 50 ms al chequear): "
            f"{'sin choques' if conflict is None else conflict}")
        assert conflict is None
    finally:
        if recorder:
            recorder.running = False
        webots.kill()
        output = webots.communicate()[0]
        for line in output.splitlines():
            if "arranca a" in line:
                log("   Webots:", line.strip())
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


run("A", 0, jog_test=True)
run("B", 10, jog_test=False)
log("ENSAYO OK")
