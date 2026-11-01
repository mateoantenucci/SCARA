"""Ensayo de la reproducción de trayectorias (issue #13) en Webots.

La sesión real de la URC (scara/1, puerto 9114), el gestor de trayectorias y
la reproducción, con el canal de instrumentación (scara-sim/1, puerto 9115)
para ver la posición física simulada, contra el controlador scara_uci
compilado, en un Webots minimizado y sin vista. El observador del ensayo de
transmisión (validation/transmision/observador.py) da el tiempo simulado, que
es el reloj del firmware (D26): Webots puede correr más lento que el reloj de
la PC, y los tiempos se miden con el de la simulación:
  0. homing y vuelta al reposo;
  1. una trayectoria mixta LIN/PTP con espera, en loop de 2 vueltas desde el
     reposo: tramo 0 de aproximación, los tramos de la trayectoria y la vuelta
     con los parámetros del punto 1. Cada tramo dura lo planificado, y en los
     LIN el punto de herramienta, estimado y simulado, sigue la recta;
  2. pausa a mitad de un LIN y reanudación: la pose de la pausa y el resto
     del tramo siguen sobre la misma recta;
  3. stop a mitad de un tramo: frena con rampa y no se envía nada más;
  4. sin referencia (F5 reinicia la UCI), reproducir queda bloqueado.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/reproduccion/ensayo_webots.py validation/reproduccion/ensayo_webots.log
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
from urc.instrumentation import Instrumentation  # noqa: E402
from urc.playback import Player  # noqa: E402
from urc.session import Session  # noqa: E402
from urc.trajectories import TrajectoryManager  # noqa: E402

PORT, SIM_PORT = 9114, 9115
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_reproduccion.wbt"
OBSERVER = ROOT / "webots" / "controllers" / "_observador_reproduccion"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
REST = (0, 0, 0, 12000)
# Trayectoria mixta: cómo se llega a cada punto (el 1 rige la vuelta del loop).
POINTS = [
    ((30, -60, 10, 60), {"kind": "LIN", "speed": 50}),
    ((-20, -40, 5, 30), {"kind": "LIN", "speed": 100}),
    ((20, -80, 0, 90), {"kind": "PTP", "speed": 50}),
    ((20, -80, 0, 50), {"kind": "LIN", "speed": 50, "wait": 1}),
]
# Lo más que el punto de herramienta puede apartarse de la recta (D54): la
# tolerancia del plan, 0,069 mm, más medio paso de M1 y de M2, 0,25 mm.
LINE_TOLERANCE = 0.32        # mm
TIME_TOLERANCE = 0.12        # s: el estado S llega cada 50 ms y el observador escribe cada 10 ms


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


def still(session):
    state = session.snapshot()
    tramo = state["tramo"]
    return (state["status"] and state["status"]["mode"] == "IDLE" and state["segments"]["pending"] == 0
            and state["segments"]["in_flight"] is None
            and (tramo is None or tramo["done"] == tramo["segments"] or tramo["cancelled"]))


class Recorder:
    """Anota cada estado S que llega, con el tiempo simulado y la posición simulada, y los tramos encolados."""

    def __init__(self, session, bench, player, clock):
        self.session, self.bench, self.player, self.clock = session, bench, player, clock
        self.samples, self.tramos = [], {}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        seen = None
        while not self.stop.is_set():
            state = self.session.snapshot()
            status = state["status"]
            if status is not None and state["received"] != seen:
                seen = state["received"]
                self.samples.append((simulated_time(self.clock), status["last"], status["mode"],
                                     tuple(status["position"]), tuple(self.bench.snapshot()["simulated"] or ())))
            with self.player.lock:
                for t in self.player.queued:
                    self.tramos[t.first] = t
            time.sleep(0.005)

    def close(self):
        self.stop.set()
        self.thread.join()


def simulated_time(path):
    """Tiempo de la simulación que informa el observador; reintenta mientras reemplaza el archivo."""
    while True:
        try:
            return json.loads(path.read_text(encoding="utf-8"))["t"]
        except (OSError, ValueError):
            time.sleep(0.002)


def finished(samples, number):
    """Momento del primer estado que muestra terminado el segmento `number`."""
    return next(t for t, last, *_ in samples if last >= number)


def started(samples, tramo, previous):
    if previous is not None and previous.last == tramo.first - 1:
        return finished(samples, previous.last)
    # Primer tramo de un movimiento: arranca al pasar a RUN.
    return next(t for t, last, mode, *_ in samples if mode == "RUN" and last >= tramo.first - 1)


def line_deviation(samples, tramo, origin, end, config):
    """Lo más que se apartan de la recta, en mm, la pose estimada y la simulada mientras se mueve el tramo."""
    a, b = planner.tool_point(origin, config), planner.tool_point(end, config)
    inside = [s for s in samples if tramo.first - 1 <= s[1] < tramo.first + len(tramo.motion) - 1]
    worst = [0.0, 0.0]
    for _, _, _, estimated, simulated in inside:
        for i, units in enumerate((estimated, simulated)):
            worst[i] = max(worst[i], planner.distance_to_line(planner.tool_point(units, config), a, b) * 1000)
    return worst, len(inside)


world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs ["--port", "{}", "--sim-port", '
                      '"{}", "--desvio", "0"]'.format(PORT, SIM_PORT))
# El observador puede tener abierto su archivo al cerrar: que no impida borrar el resto.
folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
clock = Path(folder.name) / "fisica.json"
OBSERVER.mkdir()
shutil.copy(ROOT / "validation" / "transmision" / "observador.py", OBSERVER / "_observador_reproduccion.py")
world += ('Robot {\n  name "observador"\n  controller "_observador_reproduccion"\n'
          f'  controllerArgs ["{clock.as_posix()}"]\n  supervisor TRUE\n}}\n')
WORLD.write_text(world, encoding="utf-8")
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
manager = TrajectoryManager(session, folder.name)
player = Player(session, manager)
config = session.config
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
recorder = None
try:
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"], "los dos canales", 180)
    session.enable()
    wait(lambda: session.snapshot()["status"]["mode"] == "IDLE", "drivers con corriente")

    # 0. Homing y vuelta al reposo.
    session.home()
    wait(lambda: session.snapshot()["homing"]["state"] == "terminado", "homing", 180)
    wait(lambda: still(session) and session.snapshot()["status"]["position"] == list(REST), "vuelta al reposo", 120)
    time.sleep(1)
    log(f"0 homing y reposo: estimada {session.snapshot()['status']['position']}")

    for joints, tramo in POINTS:
        manager.add({"joints": list(joints)})
        manager.edit({"index": len(manager.points) - 1, **tramo})
    joints = [p["joints"] for p in manager.points]
    log("  trayectoria: " + "; ".join(f"punto {i + 1} {list(q)} {p['kind']} {p['speed']} % espera {p['wait']} s"
                                     for i, (q, p) in enumerate(zip(joints, manager.points))))
    recorder = Recorder(session, bench, player, clock)
    wall = (time.monotonic(), simulated_time(clock))

    # 1. Trayectoria mixta en loop de 2 vueltas, desde el reposo.
    began = time.monotonic()
    state = player.play({"speed": 100, "loops": 2})
    log(f"1 play en loop de 2 vueltas: validación y arranque en {time.monotonic() - began:.2f} s; tramo 0 "
        f"{state['approach']}; duración planificada {state['duration_s']} s")
    state = wait(lambda: (s := player.snapshot())["state"] in ("terminada", "detenida") and s, "fin del loop",
                 # El tiempo es de la PC: Webots puede ir a menos de 1× (0,82× con otro Webots abierto).
                 2 * state["duration_s"] + 30)
    log(f"  {state['state']}: {state['message']}")
    assert state["state"] == "terminada", state
    time.sleep(0.5)
    tramos = sorted(recorder.tramos.values(), key=lambda t: t.first)
    assert [(t.label, t.cycle) for t in tramos] == [("0", 1), ("2", 1), ("3", 1), ("4", 1), ("vuelta", 2), ("2", 2),
                                                   ("3", 2), ("4", 2)], [(t.label, t.cycle) for t in tramos]
    previous, total_planned = None, 0.0
    starts = {"0": REST, "2": joints[0], "3": joints[1], "4": joints[2], "vuelta": joints[3]}
    for tramo in tramos:
        planned = sum(ms for ms, _ in tramo.segments()) / 1000
        measured = finished(recorder.samples, tramo.last) - started(recorder.samples, tramo, previous)
        line = ""
        if tramo.kind == "LIN":
            (estimated, simulated), count = line_deviation(recorder.samples, tramo, starts[tramo.label],
                                                           tramo.target, config)
            line = f"; recta: estimada a {estimated:.3f} mm, simulada a {simulated:.3f} mm ({count} estados)"
            assert estimated <= LINE_TOLERANCE and simulated <= LINE_TOLERANCE, (tramo.label, estimated, simulated)
        log(f"  vuelta {tramo.cycle} tramo {tramo.label} ({tramo.kind}, espera {tramo.wait_ms / 1000:g} s): "
            f"planificado {planned:.2f} s, medido {measured:.2f} s{line}")
        assert abs(measured - planned) <= TIME_TOLERANCE, (tramo.label, planned, measured)
        total_planned += planned
        previous = tramo
    total = finished(recorder.samples, tramos[-1].last) - started(recorder.samples, tramos[0], None)
    rate = (simulated_time(clock) - wall[1]) / (time.monotonic() - wall[0])
    log(f"  total: planificado {total_planned:.2f} s, medido {total:.2f} s de simulación; Webots corrió a "
        f"{rate:.2f}× del reloj de la PC")
    assert abs(total - total_planned) <= TIME_TOLERANCE and abs(total_planned - state["duration_s"]) < 0.01

    # 2. Pausa a mitad del tramo 2 (LIN) y reanudación.
    recorder.tramos.clear()
    state = player.play({"speed": 100})
    log(f"2 play desde el principio: tramo 0 {state['approach']}")
    lin = wait(lambda: next((t for t in recorder.tramos.values() if t.label == "2"), None), "tramo 2 encolado", 60)
    middle = lin.first + len(lin.motion) // 2
    wait(lambda: session.snapshot()["status"]["last"] >= middle, "mitad del tramo 2", 60)
    player.pause({})
    state = wait(lambda: (s := player.snapshot())["state"] == "pausada" and s, "pausa", 10)
    time.sleep(1)
    status, simulated = session.snapshot()["status"], bench.snapshot()["simulated"]
    a, b = planner.tool_point(joints[0], config), planner.tool_point(joints[1], config)
    paused = [planner.distance_to_line(planner.tool_point(q, config), a, b) * 1000
              for q in (status["position"], simulated)]
    log(f"  pausa en el segmento {status['last'] + 1 - lin.first} de {len(lin.motion)} del tramo 2: estimada "
        f"{status['position']} a {paused[0]:.3f} mm de la recta, simulada a {paused[1]:.3f} mm; {state['message']}")
    assert all(d <= LINE_TOLERANCE for d in paused), paused
    player.resume({})
    state = wait(lambda: (s := player.snapshot())["state"] in ("terminada", "detenida") and s, "fin", 60)
    assert state["state"] == "terminada", state
    parts = sorted((t for t in recorder.tramos.values() if t.label == "2"), key=lambda t: t.first)
    worst = [0.0, 0.0]
    for part, origin in zip(parts, (joints[0], status["position"])):
        (estimated, simulated), _ = line_deviation(recorder.samples, part, origin, joints[1], config)
        # Contra la recta original del punto 1 al 2, no contra la del resto.
        inside = [s for s in recorder.samples if part.first - 1 <= s[1] < part.first + len(part.motion) - 1]
        for _, _, _, est, sim in inside:
            for i, units in enumerate((est, sim)):
                worst[i] = max(worst[i], planner.distance_to_line(planner.tool_point(units, config), a, b) * 1000)
    log(f"  reanudado: {len(parts[1].motion)} segmentos más hasta el punto 2; en todo el tramo 2, con la rampa, "
        f"estimada a {worst[0]:.3f} mm y simulada a {worst[1]:.3f} mm de la recta original")
    assert len(parts) == 2 and all(d <= LINE_TOLERANCE for d in worst), worst

    # 3. Stop a mitad de un tramo: frena con rampa y descarta lo pendiente.
    recorder.tramos.clear()
    player.play({"speed": 100})
    lin = wait(lambda: next((t for t in recorder.tramos.values() if t.label == "2"), None), "tramo 2 encolado", 60)
    wait(lambda: session.snapshot()["status"]["last"] >= lin.first + len(lin.motion) // 3, "un tercio del tramo 2", 60)
    at_stop = session.snapshot()["status"]["position"]
    player.stop()
    wait(lambda: still(session), "robot quieto", 10)
    time.sleep(1)
    state = session.snapshot()
    log(f"3 stop en el tramo 2: {player.snapshot()['message']}; tramo de la sesión cancelado "
        f"({state['tramo']['cancelled']}) en el segmento {state['status']['last']} de {state['tramo']['last']}; "
        f"de {at_stop} frenó en {state['status']['position']}; por enviar {state['segments']['pending']}")
    assert player.snapshot()["state"] == "detenida" and state["segments"]["pending"] == 0
    assert state["status"]["last"] < state["tramo"]["last"]

    # 4. Sin referencia, reproducir queda bloqueado.
    bench.order({"falla": "F5"})
    wait(lambda: session.snapshot()["boots"] >= 2 and session.snapshot()["status"], "BOOT de la UCI", 10)
    try:
        player.play({"speed": 100})
        raise AssertionError("reprodujo sin referencia")
    except ValueError as exc:
        log(f"4 F5, sin referencia: «{exc}»")
        assert "referenciado" in str(exc)
    log("ENSAYO OK")
finally:
    if recorder is not None:
        recorder.close()
    webots.kill()
    webots.wait()
    player.close()
    session.close()
    bench.close()
    folder.cleanup()
    WORLD.unlink()
    shutil.rmtree(OBSERVER)
