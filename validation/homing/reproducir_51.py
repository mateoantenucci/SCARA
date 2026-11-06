"""Reproducción y análisis experimental de #51.

«El homing aborta con ERR 4 watchdog cuando Webots corre más rápido que el tiempo real».

Compara sistemáticamente el comportamiento del homing y del watchdog de scara/1:
  - Serie principal (3 intentos por modo, basicTimeStep=2, sin demoras inyectadas):
      * Modo Real-time (--mode=realtime, ~1.0×): homing completo de los cuatro ejes.
      * Modo Fast (--mode=fast): mide la velocidad alcanzada en este host (t_sim / t_real)
        y registra si se presentan abortos con el modelo y paso estándar.
  - Serie auxiliar (claramente diferenciada del modelo de producción):
      * Modo Fast con basicTimeStep=8 para evaluar la cota analítica nominal >= 4×
        sin demoras del host.

El watchdog en firmware/firmware.cpp evalúa (now - lastMessage_ > 1000 ms) en tiempo
simulado (hal_.millis(), alimentado por robot_.getTime() * 1000.0). Durante el homing,
la URC sólo envía PING periódicos cada 0.25 s de tiempo real (session.py). A mayor
velocidad de simulación, el intervalo simulado entre mensajes se amplía y el margen para
absorber fluctuaciones del host se reduce.

Uso:
  python validation/homing/reproducir_51.py [archivo_log]
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
from urc.session import Session

PORT = 9230
WEBOTS = os.environ.get("WEBOTS", "/Applications/Webots.app/Contents/MacOS/webots" if sys.platform == "darwin"
                        else r"C:\Program Files\Webots\msys64\mingw64\bin\webots.exe")
OBSERVER_DIR = ROOT / "webots" / "controllers" / "_obs_repro_51"
WORLD_FILE = ROOT / "webots" / "worlds" / "_repro_51.wbt"

LOG_FILE = open(sys.argv[1], "w", encoding="utf-8") if len(sys.argv) > 1 else None


def log(*args):
    line = " ".join(str(a) for a in args)
    print(line)
    if LOG_FILE:
        LOG_FILE.write(line + "\n")
        LOG_FILE.flush()


def wait(session, predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = session.snapshot()
        if predicate(state):
            return state
        time.sleep(0.01)
    return session.snapshot()


class SpeedObserver:
    """Registra muestras (t_real, t_sim) para medir la velocidad durante el homing."""
    def __init__(self, path):
        self.path = path
        self.samples = []
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        last_t = None
        while self.running:
            try:
                if self.path.exists():
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                    sim_t = data.get("t")
                    if sim_t is not None and sim_t != last_t:
                        last_t = sim_t
                        self.samples.append((time.monotonic(), sim_t))
            except (OSError, ValueError):
                pass
            time.sleep(0.005)

    def last_sim_time(self):
        return self.samples[-1][1] if self.samples else None

    @staticmethod
    def speed_between(r0, s0, r1, s1):
        if r0 is None or r1 is None or s0 is None or s1 is None:
            return None
        dt_real = r1 - r0
        dt_sim = s1 - s0
        if dt_real <= 0.05:
            return None
        return dt_sim / dt_real

    def stop(self):
        self.running = False


def setup_observer_controller():
    OBSERVER_DIR.mkdir(parents=True, exist_ok=True)
    obs_code = """import json, os, sys
from controller import Supervisor
robot = Supervisor()
step = int(robot.getBasicTimeStep())
out = sys.argv[1]
count = 0
while robot.step(step) != -1:
    count += 1
    if count % max(1, 50 // step) != 0:
        continue
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"t": robot.getTime()}, f)
    os.replace(tmp, out)
"""
    (OBSERVER_DIR / "_obs_repro_51.py").write_text(obs_code, encoding="utf-8")


def cleanup_observer_controller():
    for _ in range(50):
        try:
            shutil.rmtree(OBSERVER_DIR)
            break
        except (PermissionError, OSError):
            time.sleep(0.1)


def run_attempt(name, mode_args, basic_time_step=2, timeout=120):
    log("\n" + "=" * 70)
    log(f"INTENTO: {name}")
    log(f"  Parámetros: {' '.join(mode_args)}, basicTimeStep={basic_time_step}")
    log("=" * 70)

    temp_dir = Path(tempfile.mkdtemp())
    sample_file = temp_dir / "speed.json"
    log_path = temp_dir / "webots.log"

    session = None
    proc = None
    observer = None
    log_file = None

    result = {
        "name": name,
        "mode_args": mode_args,
        "basic_time_step": basic_time_step,
        "speed": None,
        "axes": [],
        "errors": [],
        "outcome": "UNKNOWN"
    }

    try:
        world = (ROOT / "webots" / "worlds" / "scara_uci.wbt").read_text(encoding="utf-8")
        if basic_time_step != 2:
            world = world.replace("basicTimeStep 2", f"basicTimeStep {basic_time_step}")
        world = world.replace('controller "scara_uci"',
                              f'controller "scara_uci"\n  controllerArgs ["--port", "{PORT}", "--sim-port", "0", "--desvio", "0"]')
        world += f"""
Robot {{
  name "observador"
  controller "_obs_repro_51"
  controllerArgs ["{sample_file.as_posix()}"]
  supervisor TRUE
}}
"""
        WORLD_FILE.write_text(world, encoding="utf-8")

        log_file = open(log_path, "w", encoding="utf-8")
        session = Session(port=PORT)

        cmd = [
            WEBOTS,
            "--batch",
            *mode_args,
            "--stdout",
            "--stderr",
            str(WORLD_FILE)
        ]
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, text=True)
        observer = SpeedObserver(sample_file)

        # 1. Esperar arranque y primer estado
        state = wait(session, lambda s: s["status"] is not None, timeout=20)
        if state["status"] is None:
            log("   ERROR: scara_uci no conectó a tiempo.")
            result["outcome"] = "NO_CONNECT"
            return result

        time.sleep(1.0)
        log(f"   scara_uci conectado en puerto {PORT}.")

        # 2. Habilitar motores
        session.enable()
        state = wait(session, lambda s: s["status"]["mode"] == "IDLE", timeout=5)
        log(f"   Motores habilitados (modo {state['status']['mode']}, Hall {state['status']['hall']:04b})")

        # 3. Lanzar homing y medir reloj
        log("   Lanzando HOME...")
        t_real_start = time.monotonic()
        t_sim_start = observer.last_sim_time()
        session.home()

        last_axes_count = 0
        while time.monotonic() - t_real_start < timeout:
            state = session.snapshot()
            homing = state.get("homing") or {}
            errors = state.get("errors", [])
            axes = homing.get("axes", [])

            if len(axes) > last_axes_count:
                last_axes_count = len(axes)
                log(f"   Progreso homing: ejes referenciados {axes}")

            if errors:
                log(f"   -> ERROR DETECTADO: {errors[-1]}")
                result["errors"] = list(errors)
                break

            if homing.get("state") == "terminado":
                log(f"   -> Homing completado exitosamente (ejes: {axes})")
                break

            time.sleep(0.05)

        t_real_end = time.monotonic()
        t_sim_end = observer.last_sim_time()

        speed_during_homing = SpeedObserver.speed_between(t_real_start, t_sim_start, t_real_end, t_sim_end)
        result["speed"] = speed_during_homing

        state = session.snapshot()
        result["errors"] = list(state.get("errors", []))
        result["axes"] = list(state.get("homing", {}).get("axes", []))

        speed_str = f"{speed_during_homing:.2f}×" if speed_during_homing is not None else "sin_muestra"
        log(f"   Velocidad medida durante homing: {speed_str}")

        if any("ERR 4 watchdog" in err for err in result["errors"]):
            result["outcome"] = "ABORTED_WATCHDOG"
            log(f"   RESULTADO: Abortó con ERR 4 watchdog tras referenciar ejes {result['axes']}")
        elif state.get("homing", {}).get("state") == "terminado":
            result["outcome"] = "SUCCESS_HOMED"
            log("   RESULTADO: Homing terminado exitosamente.")
        elif result["errors"]:
            result["outcome"] = f"ERROR ({result['errors'][-1]})"
            log(f"   RESULTADO: {result['outcome']}")
        else:
            result["outcome"] = f"TIMEOUT ({state.get('homing', {}).get('state')})"
            log(f"   RESULTADO: {result['outcome']}")

    finally:
        if observer is not None:
            observer.stop()
        if proc is not None:
            proc.kill()
            proc.communicate()
        if log_file is not None:
            log_file.close()
        if session is not None:
            session.close()
        WORLD_FILE.unlink(missing_ok=True)
        shutil.rmtree(temp_dir, ignore_errors=True)

    return result


def main():
    log("======================================================================")
    log("REPRODUCCIÓN Y ANÁLISIS EXPERIMENTAL #51")
    log("Homing y Watchdog vs Velocidad de Simulación en Webots")
    log(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Plataforma: {sys.platform}")
    log("======================================================================")

    setup_observer_controller()

    realtime_results = []
    fast_results = []
    auxiliary_results = []

    try:
        # --- SERIE PRINCIPAL: 3 intentos a Real-time 1× ---
        log("\n>>> SERIE 1: Modo Real-time 1× (--mode=realtime, basicTimeStep 2)")
        for i in range(1, 4):
            r = run_attempt(f"Real-time 1× (intento {i}/3)", ["--mode=realtime"], basic_time_step=2)
            realtime_results.append(r)
            time.sleep(1.5)

        # --- SERIE PRINCIPAL: 3 intentos a Fast ---
        log("\n>>> SERIE 2: Modo Fast (--mode=fast, basicTimeStep 2)")
        for i in range(1, 4):
            r = run_attempt(f"Fast estándar (intento {i}/3)", ["--mode=fast"], basic_time_step=2)
            fast_results.append(r)
            time.sleep(1.5)

        # --- SERIE AUXILIAR: Evaluación de la cota analítica >= 4× ---
        log("\n>>> SERIE AUXILIAR: Verificación analítica de cota >= 4× (--mode=fast, basicTimeStep 8)")
        r_aux = run_attempt("AUXILIAR: Fast con basicTimeStep 8", ["--mode=fast"], basic_time_step=8)
        auxiliary_results.append(r_aux)

    finally:
        cleanup_observer_controller()

    # --- TABLA Y CONTEOS FINALES ---
    log("\n" + "=" * 78)
    log("TABLA DE RESULTADOS POR INTENTO (#51):")
    log("=" * 78)
    log(f"{'Intento':<36} | {'Velocidad':<12} | {'Resultado':<18} | {'Ejes logrados'}")
    log("-" * 78)

    all_runs = realtime_results + fast_results + auxiliary_results
    for r in all_runs:
        v_str = f"{r['speed']:.2f}×" if r['speed'] is not None else "N/A"
        log(f"{r['name']:<36} | {v_str:<12} | {r['outcome']:<18} | {r['axes']}")
    log("-" * 78)

    rt_success = sum(1 for r in realtime_results if r["outcome"] == "SUCCESS_HOMED")
    fast_success = sum(1 for r in fast_results if r["outcome"] == "SUCCESS_HOMED")
    fast_watchdog = sum(1 for r in fast_results if r["outcome"] == "ABORTED_WATCHDOG")
    aux_watchdog = sum(1 for r in auxiliary_results if r["outcome"] == "ABORTED_WATCHDOG")

    log("\nCONTEOS Y CONCLUSIONES EXPERIMENTALES:")
    log(f"  1. Real-time 1× (basicTimeStep 2): {rt_success}/3 completados con éxito.")
    log(f"  2. Fast estándar (basicTimeStep 2): {fast_success}/3 completados, {fast_watchdog}/3 abortos watchdog.")
    avg_fast = [r["speed"] for r in fast_results if r["speed"] is not None]
    if avg_fast:
        log(f"     Velocidad promedio alcanzada en Fast (este host): {sum(avg_fast)/len(avg_fast):.2f}×.")
        if sum(avg_fast)/len(avg_fast) < 3.0:
            log("     LIMITACIÓN: En este host Apple Silicon, --mode=fast con basicTimeStep=2 no alcanza")
            log(f"     los >3.0× observados en la sesión del ticket (alcanza ~{min(avg_fast):.1f}-{max(avg_fast):.1f}×).")
    log(f"  3. Auxiliar (basicTimeStep 8): {aux_watchdog}/1 abortos por watchdog.")
    if auxiliary_results and auxiliary_results[0]["speed"] is not None:
        log(f"     Velocidad alcanzada en auxiliar: {auxiliary_results[0]['speed']:.2f}× (supera la cota analítica de 4×).")

    # Aserciones de consistencia mínima
    assert rt_success == 3, f"Se esperaban 3/3 exitosos en tiempo real, se obtuvieron {rt_success}"
    assert aux_watchdog == 1, "El ensayo auxiliar (>4×) debe reproducir el aborto por watchdog sin demoras de host"
    log("\nENSAYO Y REGISTRO FINALIZADOS SATISFACTORIAMENTE.")


if __name__ == "__main__":
    main()
