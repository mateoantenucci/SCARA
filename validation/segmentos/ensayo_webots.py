"""Ensayo de los segmentos temporizados y el tramo PTP (issue #9) en Webots.

La sesión real de la URC, en el puerto 9102, contra el controlador scara_uci
compilado, en un Webots minimizado y sin vista. El observador del ensayo de
transmisión (validation/transmision/observador.py) mide la posición física
simulada con el tiempo simulado, que es el reloj del firmware (D26):
  1. PTP con las cuatro articulaciones: empiezan y llegan juntas, en el tiempo
     planificado, sin pasar los límites de velocidad del modelo ni de los motores;
  2. en pleno tramo, la URC deja de enviar segmentos durante 200 ms (una demora
     del enlace o de la URC): la cola la absorbe, el robot no se entera y el
     tramo dura lo mismo;
  3. lo mismo durante 600 ms, casi el doble de lo que dura la cola (16 × 20 ms):
     la cola se vacía, el robot se detiene y arranca de golpe; es el límite del
     punto 2;
  4. STOP en plena marcha: frena con rampa, vacía la cola, conserva la
     referencia y la física coincide con la estimada.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/segmentos/ensayo_webots.py validation/segmentos/ensayo_webots.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc import planner  # noqa: E402
from urc.session import Session  # noqa: E402

PORT = 9102
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_segmentos.wbt"
OBSERVER = ROOT / "webots" / "controllers" / "_observador_segmentos"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
STEP = 5.625      # centésimas de grado por paso de J1–J3 con 1/8
NAMES = planner.NAMES
LIMITS = planner.default_limits()


def log(*parts):
    print(*parts, file=LOG, flush=True)


def wait(session, predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = session.snapshot()
        if predicate(state):
            return state
        time.sleep(0.02)
    raise AssertionError(f"no se cumplió; estado: {session.snapshot()}")


class Recorder:
    """Muestras del observador (tiempo simulado y J1–J4 físicas) y de S, en un hilo aparte."""

    def __init__(self, path, session):
        self.path, self.session = path, session
        self.samples, self.free = [], []
        self.running = True
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
            status = self.session.snapshot()["status"]
            if status:
                self.free.append((sample["t"], status["free"], status["mode"]))
            time.sleep(0.005)

    def now(self):
        return self.samples[-1][0]

    def between(self, start, end):
        return [(t, q) for t, q in self.samples if start <= t <= end]

    def physical(self):
        return self.samples[-1][1]


def settle(session, recorder):
    """Espera que el firmware termine y que la física simulada deje de moverse."""
    wait(session, lambda s: s["status"]["mode"] == "IDLE" and not s["segments"]["pending"]
         and s["segments"]["in_flight"] is None)
    # Quieta y donde el firmware cree que está: en el pico de un sobrepaso la
    # física también está quieta un instante.
    estimated = session.snapshot()["status"]["position"]
    previous = recorder.physical()
    for _ in range(50):
        time.sleep(0.2)
        joints = recorder.physical()
        if (all(abs(a - b) < limit for a, b, limit in zip(previous, joints, (0.3, 0.3, 0.3, 3)))
                and all(abs(a - b) <= limit for a, b, limit in zip(joints, estimated, (STEP, STEP, STEP, 10)))):
            return
        previous = joints
    raise AssertionError(f"la física simulada no se asienta: {previous}, estimada {estimated}")


def motion(samples, start, target):
    """Inicio y llegada de cada articulación: cuándo se aparta un paso del inicio y cuándo queda a un paso del destino."""
    result = []
    for joint in range(4):
        if start[joint] == target[joint]:
            continue
        tolerance = STEP if joint < 3 else 10
        begin = next(t for t, q in samples if abs(q[joint] - start[joint]) > tolerance)
        arrive = next(t for t, q in samples if t > begin and all(
            abs(q2[joint] - target[joint]) <= tolerance for t2, q2 in samples if t2 >= t))
        result.append((NAMES[joint], begin, arrive))
    return result


def peak_speeds(samples, window=0.06):
    """Velocidad física máxima de cada articulación y de cada motor (M2: J1 + J2), en centésimas por segundo."""
    joints, motors = [0.0] * 4, [0.0] * 4
    index = 0
    for t1, q1 in samples:
        while samples[index][0] < t1 - window:
            index += 1
        t0, q0 = samples[index]
        if t1 - t0 < window / 2:
            continue
        velocity = [(b - a) / (t1 - t0) for a, b in zip(q0, q1)]
        joints = [max(m, abs(v)) for m, v in zip(joints, velocity)]
        motors = [max(m, abs(v)) for m, v in zip(motors, planner.motor_travel(velocity))]
    return joints, motors


def ptp(session, recorder, target, delay=None):
    """Ejecuta un PTP a velocidad máxima.

    delay = (a los s, durante s): la URC no envía segmentos, como si esperara
    un OK que no llega (un número que no existe). PING y el estado siguen
    pasando, así el watchdog no salta y se ve cómo baja la cola.
    """
    start = session.snapshot()["status"]["position"]
    plan = session.move_ptp(target, speed=1)
    begin = recorder.now()
    if delay:
        time.sleep(delay[0])
        with session.lock:
            session.in_flight = -1
        time.sleep(delay[1])
        with session.lock:
            session.in_flight = None
    settle(session, recorder)
    samples = recorder.between(begin - 0.1, recorder.now())
    state = session.snapshot()
    assert state["tramo"]["cancelled"] is None and state["tramo"]["done"] == plan["segments"], (
        state["tramo"], state["errors"], state["status"])
    return start, plan, samples


def report_ptp(label, start, target, plan, samples):
    moves = motion(samples, start, target)
    begins, arrivals = [b for _, b, _ in moves], [a for _, _, a in moves]
    duration = max(arrivals) - min(begins)
    joints, motors = peak_speeds(samples)
    final = samples[-1][1]
    log(f"{label}: de {start} a {list(target)}: {plan['segments']} segmentos, {plan['duration_s']:.2f} s planificados")
    for name, begin, arrive in moves:
        log(f"   {name}: arranca a los {begin - min(begins):.3f} s y llega a los {arrive - min(begins):.3f} s")
    # En un PTP todas recorren la misma fracción de su camino en cada instante.
    moving = [joint for joint in range(4) if start[joint] != target[joint]]
    fractions = [[(q[j] - start[j]) / (target[j] - start[j]) for j in moving] for _, q in samples]
    sync = max(max(f) - min(f) for f in fractions)
    log(f"   duración física {duration:.3f} s; dispersión de arranques {max(begins) - min(begins):.3f} s, "
        f"de llegadas {max(arrivals) - min(arrivals):.3f} s; mayor diferencia de avance entre "
        f"articulaciones en una muestra: {100 * sync:.1f} % del camino")
    log(f"   velocidad física máxima J1–J4 {[round(v) for v in joints]} (límites {[round(v) for v in LIMITS.joint_speed]}); "
        f"M1–M4 {[round(v) for v in motors]} (límites {list(LIMITS.motor_speed)})")
    log(f"   física final {[round(v, 1) for v in final]}")
    return duration, sync, joints, motors, final


def queue_while_running(recorder, samples):
    """(t, libres, modo) del estado S desde el primer RUN hasta el último del tramo."""
    states = [s for s in recorder.free if samples[0][0] <= s[0] <= samples[-1][0]]
    runs = [i for i, (_, _, mode) in enumerate(states) if mode == "RUN"]
    return states[runs[0]:runs[-1] + 1]


def idle_inside(states):
    """Tiempo en IDLE en medio de un tramo: la cola se vació y el robot se detuvo."""
    return sum(t1 - t0 for (t0, _, mode), (t1, _, _) in zip(states, states[1:]) if mode == "IDLE")


def check_limits(joints, motors):
    # Muestras cada 10 ms de un movimiento en pasos: el margen cubre el
    # escalón de un paso en la ventana de 60 ms.
    for value, limit in zip(joints + motors, list(LIMITS.joint_speed) + list(LIMITS.motor_speed)):
        assert value <= limit * 1.1 + STEP / 0.06, (value, limit)


# El mismo mundo, con el controlador apuntando al puerto del ensayo y el observador.
OBSERVER.mkdir()
shutil.copy(ROOT / "validation" / "transmision" / "observador.py", OBSERVER / "_observador_segmentos.py")
sample_file = Path(tempfile.mkdtemp()) / "fisica.json"
world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', f'controller "scara_uci"\n  controllerArgs ["--port", "{PORT}"]')
world += ('Robot {\n  name "observador"\n  controller "_observador_segmentos"\n'
          f'  controllerArgs ["{sample_file.as_posix()}"]\n  supervisor TRUE\n}}\n')
WORLD.write_text(world, encoding="utf-8")
session = Session(port=PORT)
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
recorder = None
try:
    wait(session, lambda s: s["status"] is not None)
    session.enable()
    session.zero()
    wait(session, lambda s: s["referenced"])
    recorder = Recorder(sample_file, session)
    wait(session, lambda s: len(recorder.samples) > 10)
    log("0 en reposo y referenciada: estimada", session.snapshot()["status"]["position"])

    # 1. PTP con las cuatro articulaciones.
    target = (3000, -6000, 2000, 8000)
    start, plan, samples = ptp(session, recorder, target)
    duration, sync, joints, motors, final = report_ptp("1 PTP", start, target, plan, samples)
    assert sync <= 0.05, "las articulaciones no van juntas"
    assert abs(duration - plan["duration_s"]) <= 0.15, "el tramo no dura lo planificado"
    check_limits(joints, motors)
    estimated = session.snapshot()["status"]["position"]
    assert all(abs(a - b) <= STEP for a, b in zip(final[:3], estimated[:3])), (final, estimated)
    # El firmware llega al paso más cercano de cada motor; J2 es la diferencia
    # de dos motores redondeados y puede quedar a un paso.
    assert all(abs(a - b) <= STEP for a, b in zip(estimated[:3], target[:3])), estimated

    # 2. 200 ms sin enviar segmentos en pleno tramo: la cola alcanza.
    target = (-3000, -3000, -2000, 10000)
    start, plan, samples = ptp(session, recorder, target, delay=(1.0, 0.2))
    duration, *_ = report_ptp("2 PTP con 200 ms sin enviar segmentos", start, target, plan, samples)
    running = queue_while_running(recorder, samples)
    most_free = max(free for _, free, _ in running[:-10])  # el final del tramo vacía la cola
    stopped = idle_inside(running)
    in_run = running[-1][0] - running[0][0]
    log(f"   durante la demora la cola bajó a {16 - most_free} segmentos de 16, sin vaciarse; el firmware estuvo "
        f"{in_run:.2f} s en RUN (planificado {plan['duration_s']:.2f} s), sin detenerse ({stopped:.2f} s en IDLE)")
    assert most_free > 8 and stopped == 0 and abs(in_run - plan["duration_s"]) <= 0.1, "la demora se notó"

    # 3. 600 ms sin enviar segmentos: más que la cola. El robot se detiene y
    # arranca de golpe.
    target = (3000, -6000, 2000, 8000)
    start, plan, samples = ptp(session, recorder, target, delay=(1.0, 0.6))
    duration, *_ = report_ptp("3 PTP con 600 ms sin enviar segmentos", start, target, plan, samples)
    running = queue_while_running(recorder, samples)
    stopped = idle_inside(running)
    log(f"   la cola se vació: el firmware quedó quieto {stopped:.2f} s en IDLE en medio del tramo y estuvo "
        f"{running[-1][0] - running[0][0]:.2f} s entre el primer y el último RUN (planificado "
        f"{plan['duration_s']:.2f} s). Al volver los segmentos arrancó de golpe a velocidad de crucero.")
    assert stopped > 0.15, "una demora más larga que la cola tendría que notarse"

    # 4. STOP en plena marcha: rampa, cola vacía y referencia conservada.
    target = (-9000, -3000, 2000, 8000)
    start = session.snapshot()["status"]["position"]
    plan = session.move_ptp(target, speed=1)
    begin = recorder.now()
    time.sleep(2.5)
    stopped_at = recorder.now()
    session.stop()
    settle(session, recorder)
    samples = recorder.between(begin, recorder.now())
    # Velocidad física de J1 en ventanas de 60 ms. El frenado empieza cuando
    # baja del 95 % de la de crucero, después de que la URC envió STOP.
    velocity = []
    for (t0, q0), (t1, q1) in zip(samples, samples[6:]):
        velocity.append(((t0 + t1) / 2, (q1[0] - q0[0]) / (t1 - t0), q0[0]))
    cruise = [v for t, v, _ in velocity if t < stopped_at]
    speed = abs(sum(cruise[-10:]) / 10)
    braking = next((t, q) for t, v, q in velocity if t > stopped_at and abs(v) < 0.95 * speed)
    final = recorder.physical()
    halt_time = next(t for t, q in samples if t > braking[0] and all(
        abs(q2[0] - final[0]) <= STEP for t2, q2 in samples if t2 >= t))
    state = session.snapshot()
    travel = abs(final[0] - braking[1])
    expected = speed * speed / (2 * LIMITS.motor_acceleration[0])
    log(f"4 STOP a los 2,5 s de un PTP de J1 de {start[0]} a {target[0]}: J1 iba a {speed / 100:.1f} °/s; "
        f"empezó a frenar {braking[0] - stopped_at:.2f} s después de enviar STOP y se detuvo en "
        f"{halt_time - braking[0]:.2f} s y {travel / 100:.2f}° (v/a y v²/2a con 34 °/s²: "
        f"{speed / LIMITS.motor_acceleration[0]:.2f} s y {expected / 100:.2f}°)")
    log(f"   estimada {state['status']['position']}, física {[round(v, 1) for v in final]}, "
        f"modo {state['status']['mode']}, cola libre {state['status']['free']}, referenciada {state['referenced']}, "
        f"tramo: {state['tramo']['cancelled']}")
    assert state["status"]["free"] == 16 and state["referenced"] and state["status"]["mode"] == "IDLE"
    assert state["status"]["position"] != list(target), "no frenó"
    assert abs(travel - expected) <= 0.3 * expected + 2 * STEP, "la rampa no frena con la aceleración de D45"
    assert all(abs(a - b) <= STEP for a, b in zip(final[:3], state["status"]["position"][:3]))
    log("ENSAYO OK")
finally:
    if recorder:
        recorder.running = False
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
