"""Campaña de validación en Webots (issue #18, seam 3 de la spec #2).

Corre, uno detrás de otro, los ensayos en Webots del camino nuevo y deja la
evidencia de la campaña en validation/campana/campana.json: qué versión se
ensayó (commit, y el SHA-256 del controlador compilado, del mundo, del proto
y de las trayectorias de demostración), y para cada escenario su condición
inicial, el resultado esperado, la tolerancia, el ensayo que lo ejecuta, su
registro y si pasó. Cada ensayo es el de su issue, sin copiarlo: su registro
de la campaña va a validation/campana/registros/, así que el del issue queda
como estaba.

Antes de correr, compila el controlador (make no hace nada si está al día),
para que el binario ensayado salga del commit registrado.

Uso, desde la raíz del repo, con el árbol sin cambios sin commitear:
    python validation/campana/campana.py              # todos los ensayos, ~25 min
    python validation/campana/campana.py homing       # solo los nombrados, con registros en un temporal
La variable WEBOTS puede apuntar al ejecutable de Webots y WEBOTS_HOME a su carpeta.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULT = HERE / "campana.json"
LOGS = HERE / "registros"
WEBOTS_HOME = Path(os.environ.get("WEBOTS_HOME", r"C:\Program Files\Webots" if os.name == "nt"
                                  else "/Applications/Webots.app"))
CONTROLLER = ROOT / "webots" / "controllers" / "scara_uci" / ("scara_uci.exe" if os.name == "nt" else "scara_uci")
# Lo que, además del commit, identifica lo ensayado (D73).
ARTIFACTS = [CONTROLLER, ROOT / "webots" / "worlds" / "scara_uci.wbt", ROOT / "webots" / "protos" / "SCARA.proto",
             *sorted((ROOT / "trayectorias").glob("demo-*.json"))]

# Ensayo: script, puertos que usa y cuánto puede tardar (s).
ENSAYOS = {
    "protocolo": ("validation/protocolo/ensayo_webots.py", (9100,), 300),
    "transmision": ("validation/transmision/ensayo_webots.py", (9101,), 300),
    "segmentos": ("validation/segmentos/ensayo_webots.py", (9102,), 300),
    "homing": ("validation/homing/ensayo_webots.py", (9103,), 600),
    "instrumentacion": ("validation/instrumentacion/ensayo_webots.py", (9104, 9105), 300),
    "perdida_pasos": ("validation/perdida_pasos/ensayo_webots.py", (9110, 9111), 900),
    "reproduccion": ("validation/reproduccion/ensayo_webots.py", (9114, 9115), 600),
    "campana": ("validation/campana/ensayo_webots.py", (9120, 9121), 900),
}

# Escenarios de la campaña: id, nombre, condición inicial, resultado esperado,
# tolerancia y dónde se ejecuta (ensayos y pasos de sus registros). Un
# escenario pasa si pasan todos sus ensayos.
ESCENARIOS = [
    {"id": "H1", "nombre": "Homing desde el reposo",
     "inicial": "Mundo en la pose de reposo (--desvio 0), drivers con corriente, sin referencia",
     "esperado": "Sin referencia, el jog de J4 va a 5 mm/s y lo frena su Hall; el homing referencia J4, J1, J2 y "
                 "J3 en ese orden, en el flanco de cada Hall, y la URC vuelve sola al reposo; todo el camino "
                 "físico, sin choques",
     "tolerancia": "Física en el flanco a ≤ 3 pasos (0,17°; 0,15 mm en J4); reposo final a ≤ 3 pasos; jog a "
                   "5 ± 0,25 mm/s",
     "ensayos": ["homing"], "pasos": "corrida A"},
    {"id": "H2", "nombre": "Homing con desvío",
     "inicial": "Mundo con el desvío al azar por defecto (hasta ±10° en J1–J3), sin referencia",
     "esperado": "El homing termina igual: los cuatro ejes en el mismo orden y el robot en el reposo; repetido "
                 "después de un homing abortado (F3)",
     "tolerancia": "Reposo final a ≤ 3 pasos (homing); física contra estimada, quieto, a menos de un paso "
                   "completo por motor (campana)",
     "ensayos": ["homing", "campana"], "pasos": "corrida B; también campana, paso 2"},
    {"id": "T1", "nombre": "Teach & play: capturar con jog y reproducir LIN y PTP",
     "inicial": "Robot referenciado en el reposo",
     "esperado": "Tres puntos capturados con jog se guardan, se cargan del archivo sin cambios y se reproducen "
                 "(tramo 0 PTP, LIN, PTP con espera); termina en el último punto",
     "tolerancia": "Estimada en el último punto a < 1 paso (6 centésimas de grado; 1 de mm en J4); física contra "
                   "estimada a menos de un paso completo por motor (0,45° en J1 y J3; 0,04 mm en J4)",
     "ensayos": ["campana"], "pasos": "paso 3 (el jog, con órdenes JOG de scara/1)"},
    {"id": "T2", "nombre": "Reproducción LIN y PTP con loop, pausa y stop",
     "inicial": "Robot referenciado en el reposo; trayectoria mixta de 4 puntos con espera",
     "esperado": "Loop de 2 vueltas: cada tramo dura lo planificado y los LIN siguen la recta; la pausa frena "
                 "sobre la recta y reanudar la conserva; stop frena y descarta lo pendiente",
     "tolerancia": "Tiempo por tramo ± 0,12 s; recta ≤ 0,32 mm la estimada (0,069 mm del plan más medio paso "
                   "de M1 y M2) y ≤ 0,40 mm la física (más el atraso del rotor de N2)",
     "ensayos": ["reproduccion"], "pasos": "pasos 1 a 3"},
    {"id": "T3", "nombre": "Trayectorias de demostración",
     "inicial": "Robot referenciado; cada archivo demo-*.json de trayectorias/",
     "esperado": "Cada una se carga y se reproduce sin errores, sin EV LOST, y termina en su último punto",
     "tolerancia": "Estimada en el último punto a < 1 paso; física contra estimada a menos de un paso completo "
                   "por motor; ningún ERR ni EV LOST",
     "ensayos": ["campana"], "pasos": "paso 4; sin Webots, tests/test_demos.py (loop de 2 vueltas)"},
    {"id": "F1", "nombre": "Pérdida de pasos por carga y por aceleración",
     "inicial": "Robot referenciado; 5 kg en la herramienta; driver de M4 al 50 % (carga) o de M1 al 20 % "
                "(aceleración)",
     "esperado": "Con la corriente nominal, ningún paso perdido; con la falla, la planta pierde pasos de a 4 y "
                 "el firmware lo informa con EV LOST al entrar en un imán; la URC marca la referencia dudosa; "
                 "un homing la limpia",
     "tolerancia": "EV LOST con los pasos que perdió la planta ± 1 paso completo (lectura del Hall en movimiento); "
                   "sin falla, simulado − estimado < 1 paso completo",
     "ensayos": ["perdida_pasos"], "pasos": "pasos 0 a 4"},
    {"id": "F2", "nombre": "Driver de M4 sin corriente",
     "inicial": "Robot referenciado con J4 en 60 mm y 500 g",
     "esperado": "J4 simulado cae hasta abajo y la estimada no cambia; al volver la corriente, el motor retiene "
                 "J4 donde quedó",
     "tolerancia": "J4 simulado > 118 mm; estimada en 60 mm ± 0,01 mm",
     "ensayos": ["instrumentacion"], "pasos": "paso 2"},
    {"id": "F3a", "nombre": "Hall de J4 trabado activo",
     "inicial": "Robot sin referencia, Hall de J4 trabado activo a mitad de carrera",
     "esperado": "El homing aborta con ERR 12 trabado, sin declarar referencia",
     "tolerancia": "Máscara de referencia 0000",
     "ensayos": ["instrumentacion"], "pasos": "paso 3"},
    {"id": "F3b", "nombre": "Hall de J1 trabado inactivo",
     "inicial": "Mundo con desvío, sin referencia, Hall de J1 trabado inactivo",
     "esperado": "El homing referencia J4, no encuentra el Hall de J1 y aborta con ERR 11 ausente, sin declarar "
                 "referencia; con el Hall libre, el homing se repite y termina",
     "tolerancia": "Solo J4 en los ejes encontrados; robot sin referencia",
     "ensayos": ["campana"], "pasos": "pasos 1 y 2"},
    {"id": "F4", "nombre": "Enlace scara/1 cortado (watchdog)",
     "inicial": "Jog de J1 en marcha",
     "esperado": "El estado S deja de llegar y el firmware frena solo; al volver el enlace, el robot está quieto; "
                 "con la URC cortada, la UCI se reconecta sin BOOT y conserva la referencia",
     "tolerancia": "Watchdog de 1 s: J1 simulado quieto (≤ 1 paso) 2,5 s después del corte",
     "ensayos": ["instrumentacion", "protocolo"], "pasos": "paso 4; también protocolo, paso 5"},
    {"id": "F5", "nombre": "Reinicio de la UCI",
     "inicial": "Robot referenciado, quieto o en plena reproducción sin fin",
     "esperado": "La URC avisa BOOT inesperado y marca el robot sin referencia; la UCI arranca sin corriente y "
                 "J4 cae; una reproducción en curso se detiene y no se puede volver a dar play",
     "tolerancia": "Exactamente un BOOT más; reproducción «detenida»",
     "ensayos": ["instrumentacion", "campana", "reproduccion"], "pasos": "paso 5; también campana, paso 5, y reproduccion, paso 4"},
    {"id": "P1", "nombre": "Protocolo scara/1 con la UCI de Webots",
     "inicial": "Mundo en el reposo, sin corriente",
     "esperado": "Corriente, referencia manual, STOP y HALT en pleno jog, watchdog, DISABLE y reinicio de Webots, "
                 "como dice el protocolo",
     "tolerancia": "Estados y mensajes exactos",
     "ensayos": ["protocolo"], "pasos": "pasos 1 a 7"},
    {"id": "P2", "nombre": "Transmisión N1: acople M1/M2 y resolución",
     "inicial": "Robot referenciado en el reposo",
     "esperado": "El jog articular mueve una sola articulación; el jog de M1 cambia J1 y J2 y no el rumbo; J3 "
                 "avanza en escalones de un paso",
     "tolerancia": "Física contra estimada a ≤ 1 paso; escalón de 0,05625°",
     "ensayos": ["transmision"], "pasos": "pasos 1 a 6"},
    {"id": "P3", "nombre": "Segmentos temporizados y tramo PTP",
     "inicial": "Robot referenciado en el reposo",
     "esperado": "Las cuatro articulaciones llegan juntas en el tiempo planificado; la cola absorbe 200 ms sin "
                 "segmentos; STOP frena con rampa y conserva la referencia",
     "tolerancia": "Las del ensayo de segmentos (su INFORME)",
     "ensayos": ["segmentos"], "pasos": "pasos 1 a 4"},
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def compile_controller():
    """make del controlador: con el bash de Webots en Windows, con el del sistema en macOS y Linux."""
    folder = "webots/controllers/scara_uci"
    if os.name == "nt":
        bash = WEBOTS_HOME / "msys64" / "usr" / "bin" / "bash.exe"
        command = [str(bash), "-lc", f"cd '{ROOT.as_posix()}' && export PATH=/mingw64/bin:/mingw64/bin/cpp:/usr/bin "
                                     f"WEBOTS_HOME='{WEBOTS_HOME.as_posix()}'; make -C {folder}"]
    else:
        command = ["make", "-C", folder]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors="replace",
                            env=dict(os.environ, WEBOTS_HOME=str(WEBOTS_HOME)))
    if result.returncode:
        raise SystemExit(f"No compila el controlador:\n{result.stdout}{result.stderr}")


def free(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def version():
    webots = WEBOTS_HOME / "resources" / "version.txt"
    return {
        "commit": git("rev-parse", "HEAD"),
        "fecha_commit": git("log", "-1", "--format=%cI"),
        "sha256": {str(path.relative_to(ROOT).as_posix()): sha256(path) for path in ARTIFACTS},
        "webots": webots.read_text(encoding="utf-8").strip() if webots.exists() else None,
        "python": platform.python_version(),
        "sistema": platform.platform(),
    }


def kill_tree(child):
    """Corta el ensayo con el Webots que lanzó, que si no queda con los puertos, y borra su mundo temporal."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(child.pid)], capture_output=True)
    else:
        os.killpg(child.pid, signal.SIGKILL)
    child.wait()
    for leftover in [*(ROOT / "webots" / "worlds").glob("_ensayo_*.wbt"),
                     *(ROOT / "webots" / "controllers").glob("_observador_*")]:
        shutil.rmtree(leftover) if leftover.is_dir() else leftover.unlink()


def run(name, logs):
    script, ports, timeout = ENSAYOS[name]
    busy = [port for port in ports if not free(port)]
    if busy:
        raise SystemExit(f"{name}: los puertos {busy} están ocupados (¿otro ensayo en curso?)")
    log = logs / f"{name}.log"
    began = time.monotonic()
    child = subprocess.Popen([sys.executable, script, str(log)], cwd=ROOT, start_new_session=os.name != "nt")
    try:
        code = child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(child)
        code = "tiempo agotado"
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    ok = code == 0 and "ENSAYO OK" in text
    print(f"{name}: {'OK' if ok else 'FALLA'} en {time.monotonic() - began:.0f} s", flush=True)
    return {"script": script, "registro": log.relative_to(ROOT).as_posix() if log.is_relative_to(ROOT) else str(log),
            "resultado": "OK" if ok else "FALLA",
            "salida": code, "duracion_s": round(time.monotonic() - began)}


def main(names):
    unknown = set(names) - ENSAYOS.keys()
    if unknown:
        raise SystemExit(f"Ensayos desconocidos: {sorted(unknown)}; hay {sorted(ENSAYOS)}")
    full = not names
    # También los archivos sin seguimiento: una demo nueva sin commitear se ensayaría (D73).
    if full and git("status", "--porcelain", "--", ".", ":!validation/campana/registros",
                    ":!validation/campana/campana.json"):
        raise SystemExit("Hay cambios sin commitear: la campaña tiene que ensayar un commit")
    compile_controller()
    # Una corrida parcial no toca los registros de la última campaña completa.
    logs = LOGS if full else Path(tempfile.mkdtemp(prefix="scara-campana-"))
    logs.mkdir(exist_ok=True)
    started = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    identity = version()
    ensayos = {name: run(name, logs) for name in (names or ENSAYOS)}
    if not full:
        print(f"Registros en {logs}")
        return all(e["resultado"] == "OK" for e in ensayos.values())
    if version() != identity:
        raise SystemExit("La versión cambió durante la campaña: no se registra")
    escenarios = [dict(e, resultado="OK" if all(ensayos[n]["resultado"] == "OK" for n in e["ensayos"]) else "FALLA",
                       registros=[ensayos[n]["registro"] for n in e["ensayos"]]) for e in ESCENARIOS]
    document = {"campana": "scara/1 en Webots (issue #18)", "inicio": started,
                "fin": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "version": identity, "ensayos": ensayos, "escenarios": escenarios}
    RESULT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return all(e["resultado"] == "OK" for e in escenarios)


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1:]) else 1)
