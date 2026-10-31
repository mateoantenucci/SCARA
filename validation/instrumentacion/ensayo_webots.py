"""Ensayo del canal de instrumentación y las fallas F2–F5 (issue #14) en Webots.

La sesión real de la URC (scara/1, puerto 9104) y el canal de instrumentación
real (scara-sim/1, puerto 9105) contra el controlador scara_uci compilado,
en un Webots minimizado y sin vista. El ensayo mira lo mismo que el banco de
ensayo de la página: la posición física simulada que manda el canal junto a
la estimada por pasos que informa el firmware.
  0. el canal se conecta solo; con el robot quieto, simulado y estimado coinciden;
  1. carga: la herramienta pasa a 500 g;
  2. F2, driver de M4 sin corriente: J4 cae hasta abajo y el firmware no se
     entera; al volver la corriente, el motor lo retiene donde quedó;
  3. F3, Hall de J4 trabado activo: el firmware lo ve activo a mitad de
     carrera y el homing aborta con ERR 12;
  4. F4, enlace cortado en pleno jog: el estado S deja de llegar y el firmware
     frena solo por el watchdog; al volver el enlace, el robot está quieto;
  5. F5, reinicio de la UCI: BOOT inesperado, sin referencia; la UCI arranca sin
     corriente (D40), así que J1–J3 quedan donde estaban y J4 cae;
  6. recarga del mundo: el controlador vuelve a conectarse a los dos canales.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/instrumentacion/ensayo_webots.py validation/instrumentacion/ensayo_webots.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.instrumentation import Instrumentation  # noqa: E402
from urc.session import Session  # noqa: E402

PORT, SIM_PORT = 9104, 9105
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_instrumentacion.wbt"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
STEP = 5.625      # centésimas de grado por paso de J1–J3 con 1/8


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


def both(session, bench):
    return session.snapshot(), bench.snapshot()


world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs ["--port", "{}", "--sim-port", '
                      '"{}", "--desvio", "0"]'.format(PORT, SIM_PORT))
WORLD.write_text(world, encoding="utf-8")
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
try:
    # 0. El canal se conecta solo y trae la verdad del simulador.
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"], "los dos canales")
    session.enable()
    session.zero()
    wait(lambda: session.snapshot()["referenced"], "referencia manual")
    time.sleep(0.5)
    state, sim = both(session, bench)
    log(f"0 canal conectado ({sim['protocol']}): estimada {state['status']['position']}, simulado {sim['simulated']}, "
        f"motores con corriente {sim['power']:04b}, carga {sim['load_g']} g")
    # J4 sostiene su peso con el control de posición de Webots y cede unas
    # décimas de mm (ensayo de transmisión, #7).
    assert all(abs(a - b) <= limit for a, b, limit in zip(state["status"]["position"], sim["simulated"],
                                                         (STEP, STEP, STEP, 30)))
    assert sim["power"] == 0b1111

    # 1. Carga.
    bench.order({"carga": 500})
    sim = wait(lambda: (s := bench.snapshot())["load_g"] == 500 and s, "carga de 500 g")
    log(f"1 carga: la herramienta pasa a {sim['load_g']} g (toolMass del SCARA.proto)")

    # 2. F2: J4 sube a 60 mm; sin corriente en M4, cae.
    plan = session.move_ptp((0, 0, 0, 6000), speed=1)
    wait(lambda: (s := session.snapshot())["tramo"]["done"] == plan["segments"] and s["status"]["mode"] == "IDLE",
         "J4 arriba")
    time.sleep(1)
    before = bench.snapshot()["simulated"][3]
    bench.order({"falla": "F2", "activa": True})
    time.sleep(2)
    state, sim = both(session, bench)
    log(f"2 F2 con J4 en {before / 100:.2f} mm: M4 sin corriente ({sim['power']:04b}); J4 simulado cae a "
        f"{sim['simulated'][3] / 100:.2f} mm y el estimado sigue en {state['status']['position'][3] / 100:.2f} mm "
        f"(diferencia {(sim['simulated'][3] - state['status']['position'][3]) / 100:.2f} mm)")
    assert sim["faults"]["F2"] and sim["power"] == 0b0111
    assert sim["simulated"][3] > 11800 and abs(state["status"]["position"][3] - 6000) <= 1
    bench.order({"falla": "F2", "activa": False})
    time.sleep(1)
    held = bench.snapshot()["simulated"][3]
    log(f"   F2 apagada: el motor retiene J4 donde quedó ({held / 100:.2f} mm); la posición estimada ya no vale")
    assert held > 11800

    # 3. F3: Hall de J4 trabado activo.
    bench.order({"falla": "F3", "articulacion": 4, "estado": "activo"})
    wait(lambda: (session.snapshot()["status"]["hall"] & 8) and bench.snapshot()["faults"]["F3"][3] == "activo",
         "Hall de J4 trabado")
    session.home()
    state = wait(lambda: (s := session.snapshot())["homing"]["state"] != "en curso" and s, "homing abortado", 60)
    log(f"3 F3, Hall de J4 trabado activo: el homing aborta ({state['homing']['state']}); referencia "
        f"{state['status']['homed']}")
    assert "ERR 12" in state["homing"]["state"] and state["status"]["homed"] == 0
    bench.order({"falla": "F3", "articulacion": 4, "estado": "libre"})

    # 4. F4: enlace cortado en pleno jog.
    session.order("JOG 1 + 300")
    time.sleep(1)
    bench.order({"falla": "F4", "activa": True})
    time.sleep(2.5)
    state, sim = both(session, bench)
    frozen = sim["simulated"][0]
    time.sleep(1)
    later = bench.snapshot()["simulated"][0]
    log(f"4 F4 en pleno jog de J1: el último S tiene {state['status']['age_s']:.1f} s; J1 simulado quieto "
        f"({frozen} → {later}): frenó solo")
    assert state["status"]["age_s"] > 1.5 and abs(later - frozen) <= STEP
    bench.order({"falla": "F4", "activa": False})
    state = wait(lambda: (s := session.snapshot())["status"]["age_s"] < 0.2 and s, "enlace de vuelta")
    session.order("JOG STOP")
    # El ERR 4 salió con el enlace cortado y se perdió, como con un cable
    # desenchufado: lo que se ve al volver es el robot quieto.
    log(f"   F4 apagada: vuelve el estado S, con el robot en {state['status']['mode']} (el ERR 4 del watchdog "
        f"salió con el enlace cortado y se perdió)")
    assert state["status"]["mode"] == "IDLE"

    # 5. F5: reinicio de la UCI.
    boots, before = session.snapshot()["boots"], bench.snapshot()["simulated"]
    bench.order({"falla": "F5"})
    state = wait(lambda: (s := session.snapshot())["boots"] == boots + 1 and s, "BOOT")
    time.sleep(0.5)
    after = bench.snapshot()["simulated"]
    log(f"5 F5: {state['message']}; referenciado {state['referenced']}; simulado {before} → {after}")
    assert "BOOT inesperado" in state["message"] and not state["referenced"]

    # 6. Recarga del mundo.
    bench.order({"recarga": True})
    wait(lambda: not bench.snapshot()["connected"], "el canal se corta con la recarga", 30)
    sim = wait(lambda: (s := bench.snapshot())["simulated"] and s, "el canal vuelve", 60)
    state = wait(lambda: (s := session.snapshot())["status"] and s, "la UCI vuelve", 60)
    log(f"6 recarga: los dos canales vuelven; UCI {state['message']}; simulado {sim['simulated']}, carga "
        f"{sim['load_g']} g")
    assert not state["referenced"] and abs(sim["simulated"][3] - 12000) <= 30
    log("ENSAYO OK")
finally:
    webots.kill()
    webots.wait()
    session.close()
    bench.close()
    WORLD.unlink()
