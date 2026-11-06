"""C4: movimiento a mano, pérdida de referencia y recuperación, issue #49.

La sesión, el reproductor y la instrumentación reales contra la UCI de
Webots. El mundo parte del reposo sin desvío, para declarar inicialmente
la referencia manual. Uso: python validation/movido_mano/ensayo_webots.py registro.log
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.instrumentation import Instrumentation  # noqa: E402
from urc.playback import Player  # noqa: E402
from urc.session import Session  # noqa: E402
from urc.trajectories import TrajectoryManager  # noqa: E402

PORT, SIM_PORT = 9132, 9133
WEBOTS = os.environ.get("WEBOTS", "/Applications/Webots.app/Contents/MacOS/webots" if sys.platform == "darwin"
                        else r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_movido_mano.wbt"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
REST = [0, 0, 0, 12000]
# Menos de un paso completo de cada motor; J2 suma el acople M1/M2 (D64).
STILL = (45, 90, 45, 4)
OFFSET = 1000  # 10° de J1: lejos de los Hall durante esta trayectoria.


def log(*parts):
    print(*parts, file=LOG, flush=True)


def wait(predicate, what, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(f"no se cumplió: {what}")


def still():
    state = session.snapshot()
    tramo = state["tramo"]
    return (state["status"]["mode"] == "IDLE" and state["segments"]["pending"] == 0
            and state["segments"]["in_flight"] is None
            and (tramo is None or tramo["done"] == tramo["segments"] or tramo["cancelled"])) and state


def difference():
    time.sleep(1)
    estimated = session.snapshot()["status"]["position"]
    simulated = bench.snapshot()["simulated"]
    return [s - e for s, e in zip(simulated, estimated)]


def play():
    state = player.play({"speed": 50})
    end = wait(lambda: (s := player.snapshot())["state"] in ("terminada", "detenida") and s,
               "fin de reproducción", 2 * state["duration_s"] + 60)
    assert end["state"] == "terminada", end
    return difference()


def hand_cycle():
    session.disable()
    wait(lambda: bench.snapshot()["power"] == 0 and not session.snapshot()["referenced"],
         "DISABLE sin corriente ni referencia")
    before = session.snapshot()["status"]["position"]
    bench.order({"mano": {"articulacion": 1, "posicion": OFFSET}})
    wait(lambda: not bench.snapshot()["pending"] and abs(bench.snapshot()["simulated"][0] - OFFSET) <= STILL[0],
         "J1 colocado a mano")
    assert session.snapshot()["status"]["position"] == before
    session.enable()
    wait(lambda: bench.snapshot()["power"] == 15 and session.snapshot()["status"]["mode"] == "IDLE",
         "drivers con corriente")
    assert not session.snapshot()["referenced"]
    log("  DISABLE, MANO J1 10°, ENABLE: estimada", before, "física", bench.snapshot()["simulated"],
        "referenciado", session.snapshot()["referenced"])
    try:
        player.play({"speed": 50})
    except ValueError as exc:
        assert "referenciado" in str(exc), exc
        log("  play bloqueado:", str(exc))
    else:
        raise AssertionError("reprodujo sin referencia después de DISABLE")


world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs '
                      f'["--port", "{PORT}", "--sim-port", "{SIM_PORT}", "--desvio", "0"]')
WORLD.write_text(world, encoding="utf-8")
folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
trajectory = TrajectoryManager(session, folder.name)
player = Player(session, trajectory)
webots = None
try:
    for joints in ([10, -20, 10, 100], [20, -30, 10, 90]):
        state = trajectory.add({"joints": joints})
        trajectory.edit({"index": len(state["points"]) - 1, "kind": "PTP", "speed": 50})
    # Webots R2025a se bloquea al arrancar minimizado en macOS 27.
    minimize = [] if sys.platform == "darwin" else ["--minimize"]
    webots = subprocess.Popen([WEBOTS, "--batch", *minimize, "--no-rendering", "--mode=realtime",
                               "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"], "los dos canales", 180)
    session.enable()
    wait(lambda: bench.snapshot()["power"] == 15, "drivers con corriente")
    session.zero()
    wait(lambda: session.snapshot()["referenced"], "referencia manual inicial en el reposo")
    baseline = difference()
    assert all(abs(d) <= limit for d, limit in zip(baseline, STILL)), baseline

    # La URC impide la orden; la planta también, aunque se saltee esa validación.
    log("C4.1 referencia inicial; diferencia física − estimada", baseline)
    try:
        bench.order({"mano": {"articulacion": 1, "posicion": OFFSET}})
    except ValueError as exc:
        assert "sin corriente" in str(exc), exc
        log("  MANO con corriente rechazado por la URC:", str(exc))
    else:
        raise AssertionError("la URC aceptó MANO con corriente")
    with bench.lock:
        bench.client.sendall(f"MANO 1 {OFFSET}\n".encode())
    wait(lambda: "SIM ERR corriente" in bench.snapshot()["rejected"], "rechazo de la planta con corriente")
    assert abs(bench.snapshot()["simulated"][0]) <= STILL[0]
    log("  MANO directo con corriente rechazado por la planta: SIM ERR corriente")

    # DISABLE invalida la referencia; ENABLE retiene donde se colocó el eje.
    log("C4.2 recuperación por homing")
    hand_cycle()
    session.home()
    state = wait(lambda: (s := session.snapshot())["homing"]["state"] != "en curso" and s,
                 "fin del homing", 240)
    assert state["homing"]["state"] == "terminado", state["homing"]
    wait(lambda: still() and session.snapshot()["status"]["position"] == REST, "vuelta al reposo", 120)
    recovered = difference()
    assert all(abs(d) <= limit for d, limit in zip(recovered, STILL)), recovered
    after_play = play()
    assert all(abs(d) <= limit for d, limit in zip(after_play, STILL)), after_play
    log("  homing: diferencia en reposo", recovered, "; trayectoria terminada, diferencia", after_play)

    # Un origen declarado fuera de las marcas acepta una trayectoria corrida.
    session.park()
    wait(lambda: still() and session.snapshot()["status"]["position"] == REST, "reposo antes del segundo ciclo", 120)
    log("C4.3 referencia manual fuera del reposo")
    hand_cycle()
    session.zero()
    wait(lambda: session.snapshot()["referenced"], "referencia manual fuera de las marcas")
    errors = session.snapshot()["errors"]
    shifted = play()
    state = session.snapshot()
    assert abs(shifted[0] - OFFSET) <= STILL[0], shifted
    assert all(abs(d) <= limit for d, limit in zip(shifted[1:], STILL[1:])), shifted
    assert state["errors"] == errors and not state["doubtful"], state
    log("  ZERO fuera del reposo: trayectoria terminada; física − estimada", shifted,
        "; sin ERR/EV LOST nuevos; referencia dudosa", state["doubtful"])
    log("ENSAYO OK")
finally:
    if webots is not None:
        webots.kill()
        webots.wait()
    player.close()
    session.close()
    bench.close()
    folder.cleanup()
    WORLD.unlink(missing_ok=True)
