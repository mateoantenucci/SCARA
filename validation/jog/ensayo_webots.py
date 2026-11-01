"""Ensayo del jog cartesiano y del jog verificado (issue #11) en Webots.

La sesión real de la URC (scara/1, puerto 9116) contra el controlador
scara_uci compilado, en un Webots minimizado y sin vista, con el canal de
instrumentación (scara-sim/1, puerto 9117). El observador del ensayo de
transmisión (validation/transmision/observador.py) da, cada 10 ms, el tiempo
simulado, que es el reloj del firmware (D26), y la posición física simulada.
Cada jog se mantiene como lo hace la página: renovado cada 150 ms.
  0. referencia manual en la pose de reposo;
  1. jog articular de J1, normal y lento: la velocidad, y cuánto tarda en
     frenar al soltar la tecla;
  2. jog cartesiano: desde el brazo estirado, hacia adentro toma el codo
     preferido; en Y, el punto de herramienta sigue la recta con el rumbo
     fijo; hacia afuera, frena antes del brazo estirado sin cambiar el codo;
  3. J4 hacia abajo frena antes del límite de su recorrido;
  4. J2 hacia la torre, con J4 abajo, frena antes de la zona de margen del
     pedestal: el camino físico no toca nada;
  5. sin referencia (después de deshabilitar), el jog cartesiano se rechaza y
     el articular va lento.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/jog/ensayo_webots.py validation/jog/ensayo_webots.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import json
import math
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
from urc import jog, planner  # noqa: E402
from urc.instrumentation import Instrumentation  # noqa: E402
from urc.session import Session  # noqa: E402

PORT, SIM_PORT = 9116, 9117
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_jog.wbt"
OBSERVER = ROOT / "webots" / "controllers" / "_observador_jog"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
REFRESH = 0.15               # s, como la página
# El criterio del issue es frenar en unos 100 ms. Con otro Webots corriendo
# en la PC, la simulación se traba de a ratos y el observador puede escribir
# tarde: cada medida se acepta hasta 150 ms, y la mediana hasta 100.
RELEASE_LIMIT = 0.15         # s de simulación
RELEASE_MEDIAN = 0.1         # s de simulación
# Quieto: a menos de un paso del motor de la posición final (5,625 centésimas
# de grado en J1–J3 y 0,5 de mm en J4, con 1/8).
STILL = (6, 6, 6, 1)


def log(*parts):
    print(*parts, file=LOG, flush=True)


def wait(predicate, what, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(f"no se cumplió: {what}")


def observed(path):
    """Última muestra del observador; reintenta mientras reemplaza el archivo."""
    while True:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.002)


class Recorder:
    """Cada muestra del observador (10 ms simulados), con la posición estimada del último S."""

    def __init__(self, session, clock):
        self.session, self.clock, self.samples, self.modes = session, clock, [], []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        seen = None
        while not self.stop.is_set():
            sample = observed(self.clock)
            if sample["t"] != seen:
                seen = sample["t"]
                status = self.session.snapshot()["status"]
                self.samples.append((sample["t"], sample["joints"], status and tuple(status["position"])))
                self.modes.append(status and status["mode"])
            time.sleep(0.004)

    def since(self, t):
        return [s for s in list(self.samples) if s[0] >= t]

    def close(self):
        self.stop.set()
        self.thread.join()


def still(session):
    state = session.snapshot()
    return state["status"]["mode"] == "IDLE" and state["jog"] is None and state["segments"]["in_flight"] is None


def hold(session, clock, seconds, joint, direction, **options):
    """Mantiene un jog `seconds` (reloj de la PC) y lo suelta.

    Devuelve el tiempo simulado del primer pedido y de soltar, y el motivo
    si la URC lo frenó antes.
    """
    before = session.snapshot()
    began, reason, message, errors = observed(clock)["t"], None, before["message"], len(before["errors"])
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            session.jog(joint, direction, **options)
        except ValueError as exc:
            reason = str(exc)
            break
        time.sleep(REFRESH)
    released = observed(clock)["t"]
    session.jog_stop()
    if session.jog_last is not None:
        # El último S puede tener hasta 50 ms: dos segmentos y medio más de los que quedan.
        queued = session.jog_last - session.snapshot()["status"]["last"]
        log(f"  al soltar: {queued} segmentos sin terminar según el último S; ritmo de la UCI "
            f"{session._uci_rate():.2f}")
    modes = [m for (t, *_), m in zip(list(recorder.samples), list(recorder.modes)) if began <= t <= released]
    running = modes[modes.index("RUN"):] if "RUN" in modes else []
    gaps = sum(1 for a, b in zip(running, running[1:]) if a == "RUN" and b == "IDLE")
    if gaps:
        log(f"  la cola se vació {gaps} veces durante el jog")
    for error in session.snapshot()["errors"][errors:]:
        log(f"  la UCI informó: {error}")
    try:
        wait(lambda: still(session), "robot quieto", 10)
    except AssertionError:
        state = session.snapshot()
        log(f"  sin frenar: {state['status']} jog {state['jog']} SEG {state['segments']} {state['message']} "
            f"{state['errors'][-3:]} {state['traffic'][-6:]}")
        raise
    time.sleep(0.4)
    # La URC frenó el jog entre dos pedidos: lo dice el mensaje.
    after = session.snapshot()["message"]
    return began, released, reason or (after if after != message and "frenado" in after else None)


def stop_time(samples, released):
    """Desde soltar hasta que la posición física queda a menos de un paso de la final, en s simulados."""
    final = samples[-1][1]
    moving = [t for t, q, _ in samples if any(abs(a - b) > tol for a, b, tol in zip(q, final, STILL))]
    return max(moving[-1] if moving else released, released) - released


def estimated_stop(samples, released):
    """Lo mismo con la posición estimada por pasos que informa S, cada 50 ms."""
    final = samples[-1][2]
    moving = [t for t, _, q in samples if q != final]
    return max(moving[-1] if moving else released, released) - released


def speed(samples, joint, began, released):
    """Velocidad física media de una articulación en el tramo constante del jog, por segundo simulado."""
    inside = [(t, q[joint]) for t, q, _ in samples if began + 0.2 <= t <= released]
    assert len(inside) > 1, (began, released, len(samples), samples[:3])
    (t0, a), (t1, b) = inside[0], inside[-1]
    return (b - a) / (t1 - t0)


world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs ["--port", "{}", "--sim-port", '
                      '"{}", "--desvio", "0"]'.format(PORT, SIM_PORT))
folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
clock = Path(folder.name) / "fisica.json"
OBSERVER.mkdir()
shutil.copy(ROOT / "validation" / "transmision" / "observador.py", OBSERVER / "_observador_jog.py")
world += ('Robot {\n  name "observador"\n  controller "_observador_jog"\n'
          f'  controllerArgs ["{clock.as_posix()}"]\n  supervisor TRUE\n}}\n')
WORLD.write_text(world, encoding="utf-8", newline="\n")
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
config, checker = session.config, session.checker
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
recorder = None
try:
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"] and clock.exists(),
         "los dos canales y el observador", 180)
    session.enable()
    wait(lambda: session.snapshot()["status"]["mode"] == "IDLE", "drivers con corriente")
    recorder = Recorder(session, clock)
    wall = (time.monotonic(), observed(clock)["t"])

    # 0. Referencia manual: el mundo arranca justo en la pose de reposo.
    session.zero()
    wait(lambda: session.snapshot()["referenced"], "referencia")
    log(f"0 referencia manual en {session.snapshot()['status']['position']}")
    releases = []

    # 1. Jog articular de J1, normal y lento.
    for slow, nominal in ((False, jog.JOINT_SPEED[0]), (True, jog.JOINT_SPEED[1])):
        began, released, reason = hold(session, clock, 1.2, 1, "+" if not slow else "-", slow=slow)
        samples = recorder.since(began)
        measured, latency = abs(speed(samples, 0, began, released)), stop_time(samples, released)
        releases.append(latency)
        log(f"1 jog articular J1 {'lento' if slow else 'normal'}: {measured / 100:.2f} °/s simulados "
            f"(nominal {nominal / 100:g}); frenó {latency * 1000:.0f} ms después de soltar "
            f"(la estimada, con S cada 50 ms: {estimated_stop(samples, released) * 1000:.0f} ms); "
            f"J2 físico {samples[-1][1][1]:.1f} centésimas")
        assert reason is None and abs(measured - nominal) < 0.1 * nominal, (reason, measured)
        assert latency < RELEASE_LIMIT and abs(samples[-1][1][1]) < STILL[1], latency

    # 2. Jog cartesiano.
    start = session.snapshot()
    log(f"2 cartesiano desde {start['status']['position']}: codo {start['elbow']}, punto {start['tool']}")
    began, released, reason = hold(session, clock, 1.5, 2, "-", mode="cartesiano")
    state = session.snapshot()
    latency = stop_time(recorder.since(began), released)
    releases.append(latency)
    if os.environ.get("JOG_DEBUG"):
        Path(os.environ["JOG_DEBUG"]).write_text(chr(10).join(f"{t:.3f} {q} {e} {m}" for (t, q, e), m in zip(
            recorder.samples, recorder.modes) if t >= released - 0.3), encoding="utf-8")
        log(f"  estimada frenó {estimated_stop(recorder.since(began), released) * 1000:.0f} ms")
    log(f"  S (X −) 1,5 s: codo {state['elbow']}, J2 {state['status']['position'][1]}, punto {state['tool']}; "
        f"frenó {latency * 1000:.0f} ms después de soltar")
    assert reason is None and state["elbow"] == "negativo" and latency < RELEASE_LIMIT, (reason, state["elbow"], latency)
    origin, heading = state["tool"], state["tool"]["heading"]
    began, released, reason = hold(session, clock, 1.5, 1, "-", mode="cartesiano")
    samples, state = recorder.since(began), session.snapshot()
    latency = stop_time(samples, released)
    releases.append(latency)
    a = [origin[k] / 1000 for k in "xyz"]
    b = [state["tool"][k] / 1000 for k in "xyz"]
    deviation = [max(planner.distance_to_line(planner.tool_point(q, config), a, b) * 1000 for q in column)
                 for column in ([q for _, _, q in samples if q], [q for _, q, _ in samples])]
    turned = max(abs(sum(q[:3]) - heading) for _, q, _ in samples)
    log(f"  A (Y −) 1,5 s: de {origin} a {state['tool']}; de la recta: estimada a {deviation[0]:.3f} mm, "
        f"simulada a {deviation[1]:.3f} mm; rumbo físico a {turned:.1f} centésimas del inicial; "
        f"frenó {latency * 1000:.0f} ms después de soltar")
    assert reason is None and state["tool"]["y"] < origin["y"] - 20 and latency < RELEASE_LIMIT, (reason, state["tool"], latency)
    assert deviation[0] < 0.1 and deviation[1] < 0.5 and turned < 20, (deviation, turned)
    began, released, reason = hold(session, clock, 8, 2, "+", mode="cartesiano")
    samples, state = recorder.since(began), session.snapshot()
    elbow = max(q[1] for _, _, q in samples if q)
    log(f"  W (X +) hasta frenar: «{reason}»; J2 estimada nunca pasó de {elbow / 100:.2f}°, "
        f"física al final {samples[-1][1][1] / 100:.2f}°; codo {state['elbow']}")
    assert reason and "borde del alcance" in reason and elbow <= -jog.ELBOW_MIN + STILL[1] and state["elbow"] == "negativo", (reason, elbow)

    # 3. J4 hacia abajo frena antes del límite de su recorrido.
    log(f"3 Hall antes de subir J4: {session.snapshot()['status']['hall']:04b} (J4…J1)")
    hold(session, clock, 1.0, 4, "-")
    up = session.snapshot()["status"]["position"][3]
    began, released, reason = hold(session, clock, 3, 4, "+")
    samples, state = recorder.since(began), session.snapshot()
    deepest = max(q[3] for _, q, _ in samples)
    log(f"  R 1 s llevó J4 a {up / 100:.2f} mm; F hasta frenar: «{reason}»; J4 estimada "
        f"{state['status']['position'][3] / 100:.2f} mm, física como mucho {deepest / 100:.2f} mm")
    assert reason and "J4 llegó al límite" in reason and state["status"]["position"][3] <= 12000, (reason, state["status"])
    assert deepest <= 12000 + STILL[3], deepest

    # 4. J2 hacia la torre, con J4 abajo.
    plan = session.move_ptp((0, 9500, 0, 12000), speed=1.0)
    # El firmware redondea a pasos: J2 = M2 − M1 puede quedar a una centésima.
    wait(lambda: still(session) and session.snapshot()["tramo"]["done"] == plan["segments"], "PTP", 30)
    began, released, reason = hold(session, clock, 4, 2, "+")
    samples, state = recorder.since(began), session.snapshot()
    closest = min(checker.clearance(planner.inside_range(q, config)) for _, q, _ in samples) * 1000
    log(f"4 PTP a J2 = 95° en {plan['duration_s']:.2f} s; W hasta frenar: «{reason}»; J2 estimada "
        f"{state['status']['position'][1] / 100:.2f}°; separación física mínima {closest:.2f} mm")
    assert reason and "tocaría" in reason and closest > 0, (reason, closest)
    began, released, reason = hold(session, clock, 1, 2, "-")
    log(f"  S para salir: J2 {session.snapshot()['status']['position'][1] / 100:.2f}°, sin frenar ({reason})")
    assert reason is None, reason

    # 5. Sin referencia.
    session.disable()
    wait(lambda: not session.snapshot()["referenced"], "sin referencia")
    session.enable()
    wait(lambda: session.snapshot()["status"]["mode"] == "IDLE", "drivers con corriente")
    try:
        session.jog(2, "-", mode="cartesiano")
        raise AssertionError("jog cartesiano sin referencia")
    except ValueError as exc:
        log(f"5 sin referencia, jog cartesiano: «{exc}»")
    began, released, reason = hold(session, clock, 1.2, 1, "-")
    samples = recorder.since(began)
    measured = abs(speed(samples, 0, began, released))
    log(f"  jog articular J1: {measured / 100:.2f} °/s simulados (el firmware, sin referencia, 5 °/s)")
    assert abs(measured - 500) < 50, measured
    rate = (observed(clock)["t"] - wall[1]) / (time.monotonic() - wall[0])
    median = sorted(releases)[len(releases) // 2]
    log(f"frenado al soltar: mediana {median * 1000:.0f} ms y como mucho {max(releases) * 1000:.0f} ms simulados, "
        f"en {len(releases)} jogs; Webots corrió a {rate:.2f}× del reloj de la PC")
    assert median <= RELEASE_MEDIAN, releases
    log("ENSAYO OK")
finally:
    if recorder is not None:
        recorder.close()
    webots.kill()
    webots.wait()
    session.close()
    bench.close()
    folder.cleanup()
    WORLD.unlink()
    shutil.rmtree(OBSERVER)
