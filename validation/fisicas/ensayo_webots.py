"""C1, C2 y C3: ensayos físicos de contacto y perturbación (spec #45, issues #46, #47 y #48).

- C1 (#46): maceta fija en medio del barrido largo de J1 (demo-barrido-ptp.json
  a 25 y 100 % de velocidad y aceleración).
- C2 (#47): mesa fija bajo el pistón (X=500, Y=0, altura=40 mm) que bloquea el
  descenso de J4, hace perder pasos a M4 y registra la fuerza axial real (~73,7 N).
- C3 (#48): empujón horizontal en la punta con motores energizados: por debajo
  del par de retención (5 N) cede y vuelve sin perder pasos; por encima (12 N)
  salta ciclos eléctricos y queda corrido sin aviso hasta hacer homing.
"""
import json
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.instrumentation import Instrumentation
from urc.planner import tool_point
from urc.playback import AT_POINT
from urc.session import Session
from urc.trajectories import TrajectoryManager

PORT, SIM_PORT = 9130, 9131
WEBOTS = os.environ.get("WEBOTS", "/Applications/Webots.app/Contents/MacOS/webots" if sys.platform == "darwin"
                        else r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots/worlds/_ensayo_fisicas.wbt"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
REST = [0, 0, 0, 12000]
STILL = (45, 90, 45, 4)


def log(*parts):
    print(*parts, file=LOG, flush=True)


def wait(predicate, what, timeout=60):
    deadline = time.monotonic() + timeout
    diagnostic = time.monotonic() + 10
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        if time.monotonic() > diagnostic:
            log("esperando", what, "UCI", session.snapshot()["status"], "física", bench.snapshot()["simulated"])
            diagnostic += 10
        time.sleep(0.02)
    raise AssertionError(f"no se cumplió: {what}; UCI {session.snapshot()}; banco {bench.snapshot()}")


def still():
    state = session.snapshot()
    tramo = state["tramo"]
    return (state["status"] and state["status"]["mode"] == "IDLE"
            and not state["segments"]["pending"] and state["segments"]["in_flight"] is None
            and (tramo is None or tramo["done"] == tramo["segments"] or tramo["cancelled"]))


def move(target, speed=0.25):
    plan = session.move_ptp(target, speed=speed)
    wait(lambda: still() and all(abs(a - b) <= limit for a, b, limit in
         zip(session.snapshot()["status"]["position"], target, AT_POINT)),
         f"PTP a {target}", 60 + 3 * plan["duration_s"])
    time.sleep(0.5)


def home():
    log("HOME inicio", session.snapshot()["status"], bench.snapshot()["simulated"])
    session.home()
    state = wait(lambda: (s := session.snapshot())["homing"]["state"] != "en curso" and s,
                 "homing", 300)
    assert state["homing"]["state"] == "terminado", state
    wait(lambda: still() and session.snapshot()["status"]["position"] == REST, "reposo", 120)
    time.sleep(1)
    difference = [s - e for s, e in zip(bench.snapshot()["simulated"], REST)]
    assert all(abs(d) <= limit for d, limit in zip(difference, STILL)), difference
    assert not session.snapshot()["doubtful"]
    return difference


def obstacle(kind, **position):
    bench.order({"obstaculo": {"tipo": kind, **position}})
    wait(lambda: bench.snapshot().get("obstacle", {}).get("tipo") == kind
         and not any(p["key"] == "obstaculo" for p in bench.snapshot()["pending"]), "obstáculo aplicado")


world = (ROOT / "webots/worlds/scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs '
                      f'["--port", "{PORT}", "--sim-port", "{SIM_PORT}", "--desvio", "0"]')
WORLD.write_text(world, encoding="utf-8")
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
webots = subprocess.Popen([WEBOTS, "--batch", *([] if sys.platform == "darwin" else ["--minimize"]), "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
try:
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"], "ambos canales", 180)
    session.enable()
    wait(lambda: bench.snapshot()["power"] == 15, "corriente")
    home()
    manager = TrajectoryManager(session, ROOT / "trayectorias")
    demo = manager.load({"file": "demo-barrido-ptp.json"})
    start, target = [p["joints"] for p in demo["points"][:2]]
    middle = [(a + b) / 2 for a, b in zip(start, target)]
    x, y, _ = tool_point(middle)
    position = {"x": round(x * 1000), "y": round(y * 1000)}
    nominal_limits = session.limits
    results = []
    for speed in (0.25, 1.0):
        log("C1 inicio", speed, start, target, position)
        move(start)
        obstacle("maceta", **position)
        # El porcentaje de velocidad de la URC conserva aceleraciones (D53).
        # Para este ensayo se reducen también, explícitamente, los límites D76.
        with session.lock:
            session.limits = replace(nominal_limits,
                joint_acceleration=tuple(a * speed for a in nominal_limits.joint_acceleration),
                motor_acceleration=tuple(a * speed for a in nominal_limits.motor_acceleration))
        session.move_ptp(target, speed=speed)
        touch = wait(lambda: (s := bench.snapshot()).get("contact") and s, "contacto con maceta", 60)
        wait(lambda: any(bench.snapshot()["lost_steps"]), "pérdida de pasos", 60)
        # El estator completa su tramo con el obstáculo aún puesto.
        wait(lambda: still(), "fin del tramo contra maceta", 90)
        before = bench.snapshot()
        drift = [s - e for s, e in zip(before["simulated"], target)]
        assert any(abs(d) > 100 for d in drift[:3]), before
        lost = list(before["lost_steps"])
        obstacle("ninguno")
        # Sin pulsos nuevos no puede recuperar el tramo que perdió.
        time.sleep(1)
        after = bench.snapshot()
        release = [a - b for a, b in zip(after["simulated"], before["simulated"])]
        assert all(abs(d) < 2 * limit for d, limit in zip(release, STILL)), release
        assert all(v > 0 for v in before["peak_effort"]), before
        assert after["lost_steps"] == lost, (lost, after["lost_steps"])
        result = {"speed_pct": round(speed * 100), "acceleration_pct": round(speed * 100), "contact": touch["contact"],
                  "obstacle_mm": position, "estimated": session.snapshot()["status"]["position"],
                  "physical": before["simulated"], "lost_steps": lost,
                  "peak_effort": before["peak_effort"], "effort_limit": before["effort_limit"],
                  "release_motion": release}
        log("C1", json.dumps(result, ensure_ascii=False))
        # Seguir con pulsos nuevos conserva el corrimiento.
        continued = list(target)
        continued[0] -= 1000
        offset = [s - e for s, e in zip(after["simulated"], target)]
        move(continued)
        next_offset = [s - e for s, e in zip(bench.snapshot()["simulated"], continued)]
        assert all(abs(a - b) < 2 * limit for a, b, limit in zip(next_offset, offset, STILL)), (offset, next_offset)
        with session.lock:
            session.limits = nominal_limits
        # Buscar un Hall sin homing para observar EV LOST con referencia dudosa.
        axis = max(range(3), key=lambda j: abs(drift[j]) / STILL[j]) + 1
        # El contacto puede bloquear M2/M3 mientras J1 termina su barrido.
        # Se cruza el Hall del eje corrido; el robot sigue sin saber del objeto.
        direction = "-" if bench.snapshot()["simulated"][axis - 1] < 0 else "+"
        session.order(f"JOG {axis} {direction} 1000")
        wait(lambda: any(e["joint"] == axis for e in session.snapshot()["doubtful"]),
             f"EV LOST al cruzar Hall J{axis}", 90)
        session.order("JOG STOP")
        wait(still, "jog detenido")
        log("C1 EV LOST", session.snapshot()["doubtful"])
        log("C1 homing recupera", home())
        results.append(result)
    log("C1 comparación 25 % / 100 %", json.dumps(results, ensure_ascii=False))

    # --- C2: J4 contra la mesa (issue #47) ---
    log("C2 inicio")
    move([0, 0, 0, 1000], speed=0.5)
    obstacle("mesa", x=500, y=0, altura=40)
    session.move_ptp([0, 0, 0, 11000], speed=0.5)
    touch_c2 = wait(lambda: (s := bench.snapshot()).get("contact") == "TOOL" and s, "contacto de J4 con mesa", 60)
    wait(lambda: bench.snapshot()["lost_steps"][3] != 0, "pérdida de pasos en M4 contra la mesa", 60)
    wait(still, "fin del descenso de J4 contra la mesa", 60)
    before_c2 = bench.snapshot()
    assert before_c2["simulated"][3] < 6000, before_c2
    assert before_c2["lost_steps"][3] < 0 and before_c2["lost_steps"][3] % 4 == 0, before_c2
    assert before_c2["peak_effort"][3] > before_c2["effort_limit"][3], before_c2
    lost_c2 = list(before_c2["lost_steps"])
    obstacle("ninguno")
    time.sleep(1)
    after_c2 = bench.snapshot()
    release_c2 = [a - b for a, b in zip(after_c2["simulated"], before_c2["simulated"])]
    assert all(abs(d) <= 2 * limit for d, limit in zip(release_c2, STILL)), release_c2
    assert after_c2["lost_steps"] == lost_c2, (lost_c2, after_c2["lost_steps"])
    offset_c2 = after_c2["simulated"][3] - 11000
    move([0, 0, 0, 9000], speed=0.5)
    next_offset_c2 = bench.snapshot()["simulated"][3] - 9000
    assert abs(next_offset_c2 - offset_c2) <= 2 * STILL[3], (offset_c2, next_offset_c2)
    c2_result = {
        "contact": touch_c2["contact"],
        "obstacle_mm": {"tipo": "mesa", "x": 500, "y": 0, "altura": 40},
        "estimated_after_block": [0, 0, 0, 11000],
        "physical_after_block": before_c2["simulated"],
        "lost_steps": lost_c2,
        "peak_effort": before_c2["peak_effort"],
        "effort_limit": before_c2["effort_limit"],
        "release_motion": release_c2,
        "offset_after_up_mm": round(next_offset_c2 / 100, 2),
    }
    log("C2", json.dumps(c2_result, ensure_ascii=False))
    log("C2 homing recupera", home())

    # --- C3: Empujón en la punta (issue #48) ---
    def wait_physical_still(timeout=15):
        prev = bench.snapshot()["simulated"]
        def settled():
            nonlocal prev
            time.sleep(0.25)
            curr = bench.snapshot()["simulated"]
            ok = all(abs(a - b) <= 2 for a, b in zip(curr, prev))
            prev = curr
            return curr if ok else None
        return wait(settled, "planta físicamente quieta", timeout)

    log("C3 inicio")
    move([0, 0, 0, 6000], speed=0.5)
    bench.order({"empujon": {"fuerza_n": 5, "direccion": 90, "duracion_ms": 500}})
    wait(lambda: (p := bench.snapshot().get("push")) and p["fuerza_n"] == 5.0
         and not any(item["key"] == "empujon" for item in bench.snapshot()["pending"]),
         "confirmación empujón 5 N", 10)
    time.sleep(1.2)
    wait_physical_still()
    gentle_c3 = bench.snapshot()
    assert gentle_c3["lost_steps"] == [0, 0, 0, 0], gentle_c3
    assert all(abs(a - b) <= limit for a, b, limit in zip(gentle_c3["simulated"], [0, 0, 0, 6000], STILL)), gentle_c3
    assert not session.snapshot()["doubtful"], session.snapshot()

    bench.order({"empujon": {"fuerza_n": 12, "direccion": 90, "duracion_ms": 500}})
    wait(lambda: (p := bench.snapshot().get("push")) and p["fuerza_n"] == 12.0
         and any(bench.snapshot()["lost_steps"][:2]),
         "empujón 12 N vence retención", 10)
    time.sleep(1.5)
    wait_physical_still()
    strong_c3 = bench.snapshot()
    assert any(strong_c3["lost_steps"][:2]), strong_c3
    assert all(steps % 4 == 0 for steps in strong_c3["lost_steps"]), strong_c3
    drift_c3 = [s - e for s, e in zip(strong_c3["simulated"], [0, 0, 0, 6000])]
    assert any(abs(d) > 100 for d in drift_c3[:2]), strong_c3
    assert session.snapshot()["status"]["position"] == [0, 0, 0, 6000], session.snapshot()
    assert not session.snapshot()["doubtful"], session.snapshot()
    move([1000, -1000, 0, 6000], speed=0.5)
    wait_physical_still()
    drift_after_move = [s - e for s, e in zip(bench.snapshot()["simulated"], [1000, -1000, 0, 6000])]
    assert all(abs(a - b) <= 2 * limit for a, b, limit in zip(drift_after_move, drift_c3, STILL)), (drift_c3, drift_after_move)
    assert not session.snapshot()["doubtful"], session.snapshot()
    c3_result = {
        "gentle_5N": {
            "simulated": gentle_c3["simulated"],
            "lost_steps": gentle_c3["lost_steps"],
            "peak_effort": gentle_c3.get("peak_effort"),
        },
        "strong_12N": {
            "estimated": [0, 0, 0, 6000],
            "physical": strong_c3["simulated"],
            "drift": drift_c3,
            "lost_steps": strong_c3["lost_steps"],
            "peak_effort": strong_c3.get("peak_effort"),
            "drift_after_ptp": drift_after_move,
            "doubtful": session.snapshot()["doubtful"],
        },
    }
    log("C3", json.dumps(c3_result, ensure_ascii=False))
    log("C3 homing recupera", home())
    log("ENSAYO OK")
finally:
    session.close()
    bench.close()
    webots.terminate()
    try:
        webots.wait(timeout=10)
    except subprocess.TimeoutExpired:
        webots.kill()
        webots.wait()
    WORLD.unlink(missing_ok=True)
    (WORLD.parent / f".{WORLD.stem}.wbproj").unlink(missing_ok=True)
    LOG.close()
