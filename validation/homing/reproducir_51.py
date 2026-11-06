"""Reproducción y validación empírica de #51.

«El homing aborta con ERR 4 watchdog cuando Webots corre más rápido que el tiempo real».

Compara sistemáticamente el comportamiento del homing y del watchdog de scara/1:
  1. A 1× (--mode=realtime): homing completo y exitoso de los cuatro ejes.
  2. A 3× con fluctuación de 85 ms (carga URC / sondeo HTTP): aborta con ERR 4 watchdog.
  3. A 1× con la MISMA fluctuación de 85 ms: no le afecta y termina exitosamente.
  4. A >4×: aborto garantizado por watchdog incluso sin ninguna fluctuación (S * 0.25 >= 1.0 s).

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
            except Exception:
                pass
            time.sleep(0.005)

    def current_speed(self):
        if len(self.samples) < 5:
            return 1.0
        r_start, s_start = self.samples[-min(20, len(self.samples))]
        r_end, s_end = self.samples[-1]
        dt_real = r_end - r_start
        dt_sim = s_end - s_start
        return (dt_sim / dt_real) if dt_real > 0.001 else 1.0

    def total_speed(self):
        if len(self.samples) < 2:
            return 1.0
        r_start, s_start = self.samples[0]
        r_end, s_end = self.samples[-1]
        dt_real = r_end - r_start
        dt_sim = s_end - s_start
        return (dt_sim / dt_real) if dt_real > 0.001 else 1.0

    def stop(self):
        self.running = False


class JitterSession(Session):
    """Sesión de URC que puede silenciar el envío durante un lapso deliberado."""
    def __init__(self, *args, inject_delay=0.0, inject_after_axis=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.inject_delay = inject_delay
        self.inject_after_axis = inject_after_axis
        self.pause_until = None
        self.injected = False

    def _send_pending(self, client, now):
        if not self.injected and self.inject_delay > 0 and self.inject_after_axis is not None:
            if self.homing and self.inject_after_axis in self.homing.get("axes", []):
                if self.pause_until is None:
                    self.pause_until = now + self.inject_delay
                    log(f"   [JITTER] Silenciando envíos durante {self.inject_delay*1000:.0f} ms reales tras EV HOMED {self.inject_after_axis}")
                    return
        if self.pause_until is not None:
            if now < self.pause_until:
                return
            self.pause_until = None
            self.injected = True
        super()._send_pending(client, now)


def run_scenario(name, mode_args, basic_time_step=2, inject_delay=0.0, inject_after_axis=None, timeout=120):
    log("\n" + "=" * 70)
    log(f"ESCENARIO: {name}")
    log(f"  Parámetros Webots: {' '.join(mode_args)}, basicTimeStep={basic_time_step}")
    if inject_delay > 0:
        log(f"  Fluctuación URC: {inject_delay*1000:.0f} ms tras referenciar J{inject_after_axis}")
    log("=" * 70)

    temp_dir = Path(tempfile.mkdtemp())
    sample_file = temp_dir / "speed.json"
    OBSERVER_DIR.mkdir(parents=True, exist_ok=True)

    obs_code = f"""import json, os, sys
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
        json.dump({{"t": robot.getTime()}}, f)
    os.replace(tmp, out)
"""
    (OBSERVER_DIR / "_obs_repro_51.py").write_text(obs_code, encoding="utf-8")

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

    cmd = [
        WEBOTS,
        "--batch",
        *mode_args,
        "--stdout",
        "--stderr",
        str(WORLD_FILE)
    ]

    log_path = temp_dir / "webots_stdout.log"
    log_file = open(log_path, "w", encoding="utf-8")

    session = JitterSession(port=PORT, inject_delay=inject_delay, inject_after_axis=inject_after_axis)
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, text=True)
    observer = SpeedObserver(sample_file)

    result = {
        "name": name,
        "mode_args": mode_args,
        "basic_time_step": basic_time_step,
        "speed": 0.0,
        "axes": [],
        "errors": [],
        "outcome": "UNKNOWN"
    }

    try:
        # Esperar conexión
        state = wait(session, lambda s: s["status"] is not None, timeout=20)
        if state["status"] is None:
            log("ERROR: scara_uci no conectó a tiempo")
            result["outcome"] = "NO_CONNECT"
            return result

        time.sleep(1.0)
        speed_init = observer.current_speed()
        log(f"   scara_uci conectado. Velocidad simulación observada: {speed_init:.2f}×")

        # Habilitar
        session.enable()
        state = wait(session, lambda s: s["status"]["mode"] == "IDLE", timeout=5)
        log(f"   Motores habilitados (modo {state['status']['mode']}, Hall {state['status']['hall']:04b})")

        # Homing
        log("   Lanzando HOME...")
        t_start = time.monotonic()
        session.home()

        last_axes_count = 0
        while time.monotonic() - t_start < timeout:
            state = session.snapshot()
            homing = state.get("homing") or {}
            errors = state.get("errors", [])
            axes = homing.get("axes", [])

            if len(axes) > last_axes_count:
                last_axes_count = len(axes)
                speed_now = observer.current_speed()
                log(f"   Progreso homing: ejes referenciados {axes} (velocidad: {speed_now:.2f}×)")

            if errors:
                log(f"   -> ERROR DETECTADO: {errors[-1]}")
                result["errors"] = list(errors)
                break

            if homing.get("state") == "terminado":
                log(f"   -> Homing completado exitosamente (ejes: {axes})")
                break

            time.sleep(0.05)

        total_speed = observer.total_speed()
        state = session.snapshot()
        result["speed"] = total_speed
        result["errors"] = list(state.get("errors", []))
        result["axes"] = list(state.get("homing", {}).get("axes", []))

        if any("ERR 4 watchdog" in err for err in result["errors"]):
            result["outcome"] = "ABORTED_WATCHDOG"
            log(f"   RESULTADO: Abortó con ERR 4 watchdog tras referenciar ejes {result['axes']}")
        elif state.get("homing", {}).get("state") == "terminado":
            result["outcome"] = "SUCCESS_HOMED"
            log("   RESULTADO: Homing terminado exitosamente.")
        else:
            result["outcome"] = f"TIMEOUT ({state.get('homing', {}).get('state')})"
            log(f"   RESULTADO: {result['outcome']}")

    finally:
        observer.stop()
        proc.kill()
        proc.communicate()
        log_file.close()
        session.close()
        WORLD_FILE.unlink(missing_ok=True)
        shutil.rmtree(OBSERVER_DIR, ignore_errors=True)
        shutil.rmtree(temp_dir, ignore_errors=True)

    return result


def main():
    log("======================================================================")
    log("REPRODUCCIÓN Y EVIDENCIA EXPERIMENTAL #51")
    log("Watchdog de scara/1 vs Velocidad de Simulación en Webots")
    log(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("======================================================================")

    res = []

    # 1. Corrida 1x normal (sin fluctuación)
    r1 = run_scenario("1. Real-time 1× (control)", ["--mode=realtime"])
    res.append(r1)

    time.sleep(2)

    # 2. Corrida >4x (sin fluctuación adicional, falla por pura velocidad)
    r2 = run_scenario("2. Fast >4× (basicTimeStep 8)", ["--mode=fast"], basic_time_step=8)
    res.append(r2)

    time.sleep(2)

    # 3. Corrida 1x con pausa de silencio URC de 450 ms (debe tolerarla: 450 ms < 1000 ms)
    r3 = run_scenario("3. Real-time 1× con silencio URC de 450 ms", ["--mode=realtime"],
                      inject_delay=0.450, inject_after_axis=1)
    res.append(r3)

    time.sleep(2)

    # 4. Corrida fast ~2.3× con silencio URC de 450 ms (450 ms * 2.3x = 1035 ms > 1000 ms -> watchdog aborta)
    r4 = run_scenario("4. Fast ~2.3× con silencio URC de 450 ms", ["--mode=fast"], basic_time_step=2,
                      inject_delay=0.450, inject_after_axis=1)
    res.append(r4)

    log("\n" + "=" * 70)
    log("TABLA COMPARATIVA FINAL DE RESULTADOS #51:")
    log("=" * 70)
    log(f"{'Escenario':<42} | {'Velocidad':<10} | {'Resultado':<18} | {'Ejes logrados'}")
    log("-" * 80)
    for r in res:
        err_str = "ERR 4 watchdog" if "ERR 4 watchdog" in str(r["errors"]) else "OK"
        log(f"{r['name']:<42} | {r['speed']:.2f}×       | {err_str:<18} | {r['axes']}")
    log("-" * 80)

    # Verificación de asertos fundamentales de la hipótesis
    assert res[0]["outcome"] == "SUCCESS_HOMED", "El homing a 1× debe pasar siempre"
    assert res[1]["outcome"] == "ABORTED_WATCHDOG", "El homing a >4× debe abortar por watchdog"
    assert res[2]["outcome"] == "SUCCESS_HOMED", "A 1× el silencio de 450 ms debe ser tolerado (450 ms < 1000 ms)"
    assert res[3]["outcome"] == "ABORTED_WATCHDOG", "A ~2.3× el silencio de 450 ms debe romper el watchdog (1035 ms > 1000 ms)"
    log("EVIDENCIA CONFIRMADA Y ASISTIDA POR ASERCIONES.")


if __name__ == "__main__":
    main()
