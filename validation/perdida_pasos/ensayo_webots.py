"""Ensayo de la pérdida de pasos (N2) y de F1 con EV LOST (issue #15) en Webots.

La sesión real de la URC (scara/1, puerto 9110) y el canal de instrumentación
real (scara-sim/1, puerto 9111) contra el controlador scara_uci compilado, en
un Webots minimizado y sin vista. Cada paso compara la posición física
simulada con la estimada por pasos, y los pasos que la planta dice que perdió
cada motor con lo que informa el firmware al cruzar un Hall:
  0. homing y vuelta al reposo: cruzar los Hall sin pasos perdidos no da
     ningún EV LOST, y lo simulado coincide con lo estimado;
  1. 5 kg en la herramienta, con la corriente nominal: J4 sube y baja a su
     velocidad máxima sin perder pasos (los límites de D45 dejan margen, D66);
  2. F1 por carga: con J4 a media altura y el driver de M4 al 50 %, los 5 kg
     se sostienen pero no suben; lo simulado se aparta de lo estimado en pasos
     completos y, al volver al reposo, el Hall de abajo lo detecta: EV LOST 4 y
     la referencia queda dudosa;
  3. F1 por aceleración: con el driver de M1 al 20 %, el jog de J1, que arranca
     sin rampa, pierde pasos; al llegar a su imán, EV LOST 1 con los mismos pasos
     que perdió la planta;
  4. un homing limpia la referencia dudosa.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/perdida_pasos/ensayo_webots.py validation/perdida_pasos/ensayo_webots.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.instrumentation import Instrumentation  # noqa: E402
from urc.session import Session  # noqa: E402

PORT, SIM_PORT = 9110, 9111
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_perdida_pasos.wbt"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
# Un paso completo de cada motor en unidades de su articulación, con 1/8:
# 8 pulsos de 5,625 centésimas de grado en J1–J3 y de 0,5 centésimas de mm en J4.
FULL_STEP = (45.0, 45.0, 45.0, 4.0)
REST = (0, 0, 0, 12000)


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


def still(session):
    state = session.snapshot()
    tramo = state["tramo"]
    return (state["status"] and state["status"]["mode"] == "IDLE" and state["segments"]["pending"] == 0
            and state["segments"]["in_flight"] is None and (tramo is None or tramo["done"] == tramo["segments"]
                                                             or tramo["cancelled"]))


def move(session, target, speed=1.0):
    plan = session.move_ptp(target, speed=speed)
    wait(lambda: still(session) and session.snapshot()["status"]["last"] >= session.snapshot()["tramo"]["last"],
         f"tramo a {target}", 30 + plan["duration_s"] * 2)
    time.sleep(0.5)


def gap(session, bench):
    """Simulado menos estimado por articulación, en pasos completos de su motor."""
    state, sim = session.snapshot(), bench.snapshot()
    return [(s - e) / step for s, e, step in zip(sim["simulated"], state["status"]["position"], FULL_STEP)], sim


def home(session, what):
    session.home()
    state = wait(lambda: (s := session.snapshot())["homing"]["state"] == "terminado" and s, what, 180)
    wait(lambda: still(session) and session.snapshot()["status"]["position"] == list(REST), "vuelta al reposo", 120)
    time.sleep(1)
    return state


world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs ["--port", "{}", "--sim-port", '
                      '"{}", "--desvio", "0"]'.format(PORT, SIM_PORT))
WORLD.write_text(world, encoding="utf-8")
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
try:
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"], "los dos canales", 180)
    session.enable()
    wait(lambda: session.snapshot()["status"]["mode"] == "IDLE", "drivers con corriente")

    # 0. Homing y vuelta al reposo, sin pasos perdidos.
    started = time.monotonic()
    home(session, "homing")
    state = session.snapshot()
    steps, sim = gap(session, bench)
    log(f"0 homing y reposo en {time.monotonic() - started:.0f} s: estimada {state['status']['position']}, simulado "
        f"{sim['simulated']}, diferencia {[round(s, 2) for s in steps]} pasos completos; pasos perdidos "
        f"{sim['lost_steps']}; EV LOST {state['doubtful']}")
    assert state["doubtful"] == [] and sim["lost_steps"] == [0, 0, 0, 0]
    assert all(abs(s) < 1 for s in steps), steps

    # 1. 5 kg con la corriente nominal: J4 sube y baja a 40 mm/s sin perder pasos.
    bench.order({"carga": 5000})
    wait(lambda: bench.snapshot()["load_g"] == 5000, "carga de 5 kg")
    time.sleep(1)
    move(session, (0, 0, 0, 1000))
    steps, sim = gap(session, bench)
    log(f"1 con 5 kg y la corriente nominal, J4 sube a 10 mm: diferencia {[round(s, 2) for s in steps]} pasos "
        f"completos, pasos perdidos {sim['lost_steps']}")
    assert sim["lost_steps"] == [0, 0, 0, 0] and all(abs(s) < 1 for s in steps), steps
    move(session, REST)
    state = session.snapshot()
    steps, sim = gap(session, bench)
    log(f"  y vuelve al reposo, cruzando el Hall de abajo: pasos perdidos {sim['lost_steps']}, EV LOST "
        f"{state['doubtful']}")
    assert state["doubtful"] == [] and sim["lost_steps"] == [0, 0, 0, 0]

    # 2. F1 por carga: con M4 al 50 %, 5 kg se sostienen pero no suben.
    move(session, (0, 0, 0, 6000))
    bench.order({"falla": "F1", "motor": 4, "corriente": 50})
    wait(lambda: bench.snapshot()["current_pct"][3] == 50, "M4 al 50 %")
    move(session, (0, 0, 0, 1000))
    steps, sim = gap(session, bench)
    lost = sim["lost_steps"][3]
    log(f"2 F1, M4 al 50 % con 5 kg, de 60 a 10 mm: J4 estimado {session.snapshot()['status']['position'][3] / 100:.2f} mm, "
        f"simulado {sim['simulated'][3] / 100:.2f} mm; diferencia {steps[3]:.2f} pasos completos, la planta "
        f"perdió {lost}")
    assert lost > 0 and lost % 4 == 0 and abs(steps[3] - lost) < 1, (steps, lost)
    bench.order({"falla": "F1", "motor": 4, "corriente": 100})
    wait(lambda: bench.snapshot()["current_pct"][3] == 100, "M4 al 100 %")
    move(session, REST)
    state = wait(lambda: (s := session.snapshot())["doubtful"] and s, "EV LOST de J4", 5)
    log(f"  M4 al 100 % y de vuelta al reposo: el Hall de abajo da {state['doubtful']}; mensaje: {state['message']}")
    # El Hall se lee una vez por paso de Webots (2 ms): a 40 mm/s, 0,08 mm o
    # 2 pasos completos de M4 (D76).
    assert state["doubtful"][0]["joint"] == 4 and abs(state["doubtful"][0]["steps"] - lost) <= 2
    assert state["referenced"]

    # 3. F1 por aceleración: M1 al 20 % con 5 kg; el jog arranca sin rampa.
    bench.order({"falla": "F1", "motor": 1, "corriente": 20})
    wait(lambda: bench.snapshot()["current_pct"][0] == 20, "M1 al 20 %")
    session.order("JOG 1 - 1000")
    time.sleep(1)
    lost = bench.snapshot()["lost_steps"][0]
    state = wait(lambda: (s := session.snapshot())["errors"] and "fin" in s["errors"][-1] and s, "J1 en su imán", 30)
    time.sleep(0.5)
    steps, sim = gap(session, bench)
    log(f"3 F1, M1 al 20 % con 5 kg: al arrancar el jog de J1 la planta perdió {lost} pasos completos "
        f"(diferencia {steps[0]:.2f}); al llegar al imán: {state['doubtful']}")
    lost_j1 = [item for item in state["doubtful"] if item["joint"] == 1]
    assert lost != 0 and lost % 4 == 0 and lost_j1 and abs(lost_j1[0]["steps"] - lost) <= 1, (lost, state["doubtful"])
    assert all(math.isfinite(value) for value in sim["simulated"])

    # 4. Un homing limpia la duda (con la corriente nominal y la herramienta sola).
    bench.order({"falla": "F1", "motor": 1, "corriente": 100})
    bench.order({"carga": 150})
    wait(lambda: bench.snapshot()["current_pct"][0] == 100 and bench.snapshot()["load_g"] == 150, "nominal")
    session.order("JOG 1 + 500")
    time.sleep(2)
    session.order("JOG STOP")
    time.sleep(0.5)
    state = home(session, "homing de nuevo")
    steps, sim = gap(session, bench)
    log(f"4 homing de nuevo: EV LOST {state['doubtful']}; diferencia {[round(s, 2) for s in steps]} pasos completos")
    assert state["doubtful"] == [] and all(abs(s) < 1 for s in steps), steps
    log("ENSAYO OK")
finally:
    webots.kill()
    webots.wait()
    session.close()
    bench.close()
    WORLD.unlink()
