"""Escenarios de la campaña de validación (issue #18) que no cubría ningún ensayo anterior.

La sesión real de la URC (scara/1, puerto 9120), su gestor de trayectorias y
su reproducción, con el canal de instrumentación (scara-sim/1, puerto 9121),
contra el controlador scara_uci compilado, en un Webots minimizado y sin vista.
El mundo arranca como lo ve el operador: cerca del reposo, con el desvío al
azar por defecto (hasta ±10° en J1–J3) y sin referencia.
  1. F3 con el Hall de J1 trabado inactivo: el homing referencia J4, no
     encuentra el Hall de J1 y aborta con ERR 11, sin declarar referencia;
  2. con el Hall libre, el homing se repite y termina en la pose de reposo;
  3. teach & play: tres puntos capturados con jog (Espacio), guardados,
     cargados del archivo y reproducidos con tramos LIN y PTP;
  4. cada trayectoria de demostración de trayectorias/ se carga y se
     reproduce sin errores; al terminar, la posición estimada está en su
     último punto y la física simulada coincide con ella;
  5. F5 en plena reproducción: la URC detecta el BOOT, la reproducción se
     detiene, el robot queda sin referencia y reproducir queda bloqueado.

Uso, desde la raíz del repo y con el controlador compilado (docs/UCI_WEBOTS.md):
    python validation/campana/ensayo_webots.py validation/campana/registros/campana.log
La variable WEBOTS puede apuntar al ejecutable de Webots.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from urc.instrumentation import Instrumentation  # noqa: E402
from urc.playback import AT_POINT, Player  # noqa: E402
from urc.session import Session  # noqa: E402
from urc.trajectories import DEFAULT_FOLDER, TrajectoryManager  # noqa: E402

PORT, SIM_PORT = 9120, 9121
WEBOTS = os.environ.get("WEBOTS", r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
WORLD = ROOT / "webots" / "worlds" / "_ensayo_campana.wbt"
LOG = open(sys.argv[1], "w", encoding="utf-8", newline="\n")
REST = [0, 0, 0, 12000]
# Física contra estimada con el robot quieto: menos de un paso completo de cada
# motor (D64: el rotor sostiene la carga con una fracción de paso de atraso).
# Un paso completo es 0,45° de J1 y J3 y 0,04 mm de J4; J2 suma los de M1 y M2.
STILL = (45, 90, 45, 4)


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
    return (state["status"]["mode"] == "IDLE" and state["segments"]["pending"] == 0
            and state["segments"]["in_flight"] is None
            and (tramo is None or tramo["done"] == tramo["segments"] or tramo["cancelled"])) and state


def homing(session):
    session.home()
    state = wait(lambda: (s := session.snapshot())["homing"]["state"] != "en curso" and s, "fin del homing", 240)
    if state["homing"]["state"] == "terminado":
        wait(lambda: still(session) and session.snapshot()["status"]["position"] == REST, "vuelta al reposo", 120)
    return state


def agree(session, bench):
    """Física simulada contra estimada, con el robot quieto: la diferencia por articulación."""
    time.sleep(1)
    estimated, simulated = session.snapshot()["status"]["position"], bench.snapshot()["simulated"]
    difference = [round(s - e, 1) for s, e in zip(simulated, estimated)]
    assert all(abs(d) <= limit for d, limit in zip(difference, STILL)), (estimated, simulated)
    return estimated, difference


def play(player, request, what):
    """Reproduce hasta el final: la duración planificada y la medida con el reloj de la PC, validación incluida."""
    began = time.monotonic()
    state = player.play(request)
    planned = state["duration_s"]
    state = wait(lambda: (s := player.snapshot())["state"] in ("terminada", "detenida") and s, what, planned + 60)
    assert state["state"] == "terminada", state
    return planned, time.monotonic() - began


def jog(session, order, seconds):
    session.order(order)
    time.sleep(seconds)
    session.order("JOG STOP")
    wait(lambda: still(session), "jog frenado", 10)
    time.sleep(0.3)


world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
world = world.replace('controller "scara_uci"', 'controller "scara_uci"\n  controllerArgs ["--port", "{}", "--sim-port", '
                      '"{}"]'.format(PORT, SIM_PORT))
WORLD.write_text(world, encoding="utf-8")
folder = tempfile.TemporaryDirectory()
session, bench = Session(port=PORT), Instrumentation(port=SIM_PORT)
taught = TrajectoryManager(session, folder.name)
demos = TrajectoryManager(session, DEFAULT_FOLDER)
webots = subprocess.Popen([WEBOTS, "--batch", "--minimize", "--no-rendering", "--mode=realtime",
                           "--stdout", "--stderr", str(WORLD)], stdout=LOG, stderr=LOG)
player = None
try:
    wait(lambda: session.snapshot()["status"] and bench.snapshot()["simulated"], "los dos canales", 180)
    session.enable()
    wait(lambda: session.snapshot()["status"]["mode"] == "IDLE", "drivers con corriente")
    log(f"0 arranque con desvío: simulado {bench.snapshot()['simulated']}, sin referencia")

    # 1. F3: Hall de J1 trabado inactivo; el homing aborta sin referencia.
    bench.order({"falla": "F3", "articulacion": 1, "estado": "inactivo"})
    wait(lambda: bench.snapshot()["faults"]["F3"][0] == "inactivo", "Hall de J1 trabado")
    state = homing(session)
    log(f"1 F3, Hall de J1 trabado inactivo: homing {state['homing']['state']}; ejes referenciados "
        f"{state['homing']['axes']}; máscara {state['status']['homed']:04b}; referenciado {state['referenced']}")
    assert "ERR 11" in state["homing"]["state"] and state["homing"]["axes"] == [4] and not state["referenced"]
    bench.order({"falla": "F3", "articulacion": 1, "estado": "libre"})
    wait(lambda: bench.snapshot()["faults"]["F3"][0] == "libre", "Hall de J1 libre")

    # 2. Homing de nuevo, con el Hall libre.
    state = homing(session)
    assert state["homing"]["state"] == "terminado" and state["homing"]["axes"] == [4, 1, 2, 3], state["homing"]
    estimated, difference = agree(session, bench)
    log(f"2 homing con el Hall libre: ejes {state['homing']['axes']}; reposo, estimada {estimated}, "
        f"simulado − estimado {difference}")

    # 3. Teach & play: jog, captura, guardar, cargar y reproducir.
    player = Player(session, taught)
    jog(session, "JOG 1 + 1000", 2.5)
    jog(session, "JOG 2 - 1000", 4)
    jog(session, "JOG 4 - 1000", 4)
    taught.capture({})
    jog(session, "JOG 4 + 1000", 3)
    taught.capture({})
    jog(session, "JOG 1 - 1000", 5)
    jog(session, "JOG 3 + 1000", 3)
    taught.capture({})
    taught.edit({"index": 0, "kind": "PTP"})
    taught.edit({"index": 2, "kind": "PTP", "wait": 1})
    saved = taught.save({"name": "Ensayo teach"})
    taught.new({})
    loaded = taught.load({"file": saved["file"]})
    log("3 teach: " + "; ".join(f"punto {i + 1} {p['joints']} {p['kind']} {p['speed']} % espera {p['wait']} s"
                                for i, p in enumerate(loaded["points"])) + f"; guardado y cargado de {saved['file']}")
    assert [p["joints"] for p in loaded["points"]] == [p["joints"] for p in saved["points"]]
    planned, measured = play(player, {"speed": 100}, "reproducción de lo capturado")
    estimated, difference = agree(session, bench)
    log(f"  play desde el reposo: tramo 0 PTP, tramo 2 LIN, tramo 3 PTP; terminada en {measured:.1f} s de reloj "
        f"de la PC con la validación (planificado {planned} s); estimada {estimated}, simulado − estimado "
        f"{difference}")
    assert all(abs(e - q) <= limit for e, q, limit in zip(estimated, loaded["points"][-1]["joints"], AT_POINT))
    player.close()

    # 4. Trayectorias de demostración.
    player = Player(session, demos)
    for file in demos.files()["files"]:
        if not file.startswith("demo-"):
            continue
        loaded = demos.load({"file": file, "discard": True})
        errors = session.snapshot()["errors"]
        kinds = "".join(p["kind"][0] for p in loaded["points"])
        planned, measured = play(player, {"speed": 100}, f"reproducción de {file}")
        estimated, difference = agree(session, bench)
        state = session.snapshot()
        # La sesión guarda los últimos 10 ERR y EV LOST: si la lista cambió, hubo uno nuevo.
        new_errors = state["errors"] != errors
        log(f"4 {file} «{loaded['name']}»: {len(loaded['points'])} puntos ({kinds}); terminada en {measured:.1f} s "
            f"de reloj de la PC con la validación (planificado {planned} s); estimada {estimated}, simulado − "
            f"estimado {difference}; ERR o EV LOST nuevos: {state['errors'][-1:] if new_errors else 'ninguno'}; "
            f"referencia dudosa: {state['doubtful'] or 'no'}")
        assert all(abs(e - q) <= limit for e, q, limit in zip(estimated, loaded["points"][-1]["joints"], AT_POINT))
        assert not state["doubtful"] and not new_errors

    # 5. F5 en plena reproducción.
    demos.load({"file": "demo-pick-and-place.json", "discard": True})
    player.play({"speed": 100, "loops": None})
    wait(lambda: player.snapshot()["state"] == "reproduciendo" and session.snapshot()["status"]["mode"] == "RUN",
         "reproducción en marcha")
    time.sleep(6)
    boots, before = session.snapshot()["boots"], bench.snapshot()["simulated"]
    bench.order({"falla": "F5"})
    state = wait(lambda: (s := player.snapshot())["state"] != "reproduciendo" and s, "la reproducción se detiene", 10)
    session_state = wait(lambda: (s := session.snapshot())["boots"] == boots + 1 and s["status"] and s, "BOOT")
    time.sleep(1)
    after = bench.snapshot()["simulated"]
    log(f"5 F5 en plena reproducción sin fin: {state['state']} («{state['message']}»); URC: "
        f"«{session_state['message']}»; referenciado {session_state['referenced']}; simulado {before} → {after}")
    assert state["state"] == "detenida" and not session_state["referenced"]
    assert "BOOT inesperado" in session_state["message"]
    try:
        player.play({"speed": 100})
        raise AssertionError("reprodujo sin referencia")
    except ValueError as exc:
        log(f"  play otra vez: «{exc}»")
        assert "referenciado" in str(exc)
    log("ENSAYO OK")
finally:
    webots.kill()
    webots.wait()
    if player is not None:
        player.close()
    session.close()
    bench.close()
    folder.cleanup()
    WORLD.unlink()
