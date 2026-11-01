"""Ensayos destructivos SOLO del banco provisional abierto en Webots.

Usa instrumentación simulada para verificar; no representa sensores del robot.
Recarga el mundo entre escenarios y lo deja detenido al terminar.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.dynamics import box_with_payload
from scara.kinematics import forward, inverse, load_config


class Bench:
    def __init__(self, host, port, report):
        self.address = (host, port)
        self.report = report
        self.sock = None
        self.buffer = bytearray()
        self.sequence = 0
        self.last = None

    def connect(self):
        self.close()
        deadline = time.monotonic() + 20
        while True:
            try:
                self.sock = socket.create_connection(self.address, timeout=1)
                self.sock.settimeout(1)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise TimeoutError("No conecta al banco: abrir Webots y ejecutar la simulación")
                time.sleep(0.1)
        return self.wait(lambda e: e.get("event") == "state")["state"]

    def close(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.buffer.clear()

    def send(self, command, **values):
        self.sequence += 1
        request = dict(values, id=f"smoke-{self.sequence}", command=command)
        frame = json.dumps(request, allow_nan=False).encode() + b"\n"
        self.sock.sendall(frame)
        # Conservar exactamente lo transmitido, aunque el llamador luego cambie una lista.
        self.report["requests"].append(json.loads(frame))
        return request["id"]

    def wait(self, predicate, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if b"\n" not in self.buffer:
                try:
                    chunk = self.sock.recv(16384)
                except socket.timeout:
                    continue
                if not chunk:
                    raise ConnectionError("El banco cerró la conexión")
                self.buffer.extend(chunk)
                if len(self.buffer) > 1024 * 1024:
                    raise ValueError("Buffer de ensayo excedido")
                continue
            frame, _, self.buffer = self.buffer.partition(b"\n")
            event = json.loads(frame)
            self.report["events"].append(event)
            if event.get("event") == "state":
                self.last = event["state"]
            if predicate(event):
                return event
        raise TimeoutError("Sin resultado: comprobar reproducción de Webots y que no haya otro cliente ocupando TCP")

    def command(self, command, expected="accepted", **values):
        request_id = self.send(command, **values)
        result = self.wait(lambda e: e.get("id") == request_id and e.get("event") in ("accepted", "rejected"))
        assert result["event"] == expected, result
        return request_id

    def state(self, predicate=lambda s: True):
        return self.wait(lambda e: e.get("event") == "state" and predicate(e["state"]))["state"]

    def observe(self, seconds):
        start = self.state()["time"]
        samples = []
        while not samples or samples[-1]["time"] < start + seconds:
            samples.append(self.state())
        return samples

    def reset(self):
        previous_trial = (self.last or {}).get("trial_id")
        # Esperar el acuse antes de cerrar: se descartan órdenes de sesiones perdidas.
        self.command("reset_trial")
        self.close()
        time.sleep(0.1)
        state = self.connect()
        if previous_trial is not None and state.get("trial_id") == previous_trial:
            state = self.state(lambda s: s.get("trial_id") != previous_trial)
        assert state.get("trial_id") and state["mode"] == "STOPPED" and not state["faults"], state
        assert state["reference_valid"] and state["payload_mass"] == 0, state
        assert state["commanded"] == load_config()["initial_positions"], state
        self.observe(0.5)
        return self.last


def angle_error(a, b):
    return abs(math.atan2(math.sin(a-b), math.cos(a-b)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--output", type=Path, default=ROOT / "validation/simulation.json")
    parser.add_argument("--webots-version", default="no registrada; completar al ejecutar")
    args = parser.parse_args()
    config = load_config()
    report = {"status": "running", "started_utc": datetime.now(timezone.utc).isoformat(),
              "protocol": "scara-dev/1", "webots_version": args.webots_version,
              "platform": platform.platform(), "python": sys.version,
              "note": config["model_status"] + ". Instrumentación interna, no sensores físicos.",
              "tolerances": {"joint_rad": 0.005, "slider_m": 0.0005, "tcp_m": 0.001, "yaw_rad": 0.02},
              "sources": {}, "checks": [], "requests": [], "events": []}
    for name in ("config/scara.json", "tools/check_simulation.py", "tools/generate_world.py", "scara/runtime.py",
                 "scara/kinematics.py", "scara/dynamics.py", "scara/transport.py", "webots/protos/SCARA.proto",
                 "webots/worlds/scara.wbt", "webots/controllers/scara_bridge/scara_bridge.py",
                 "config/cad_integration.json", "scara/frames.py", "tools/integrate_cad.py",
                 "cad/ensambles/integracion_articulada.json", "scara/collisions.py"):
        report["sources"][name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    bench = Bench(args.host, args.port, report)

    def passed(name, **evidence):
        report["checks"].append(dict(name=name, status="passed", **evidence))
        print("PASS:", name, flush=True)

    def pose_check(state, target):
        errors = [abs(a-b) for a,b in zip(state["simulated"], target)]
        assert max(errors[:3]) < 0.005 and errors[3] < 0.0005, errors
        tcp_error = math.dist(state["tcp_world"], forward(target, config)[:3])
        fk_error = math.dist(state["tcp_world"], state["simulated_pose"][:3])
        assert tcp_error < 0.001 and fk_error < 0.001, (tcp_error, fk_error)
        assert angle_error(state["tcp_world_yaw"], forward(target, config)[3]) < 0.02
        return dict(joint_error=errors, tcp_error_m=tcp_error, fk_error_m=fk_error)

    try:
        bench.connect()
        initial = bench.reset()
        passed("initial_pose", **pose_check(initial, config["initial_positions"]))
        bench.command("rearm")
        target = inverse(0.30, 0.20, 0.05, current=initial["estimated"], config=config)
        request_id = bench.command("move_joints", positions=target, speed=0.7)
        bench.wait(lambda e: e.get("event") == "completed" and e.get("id") == request_id)
        samples = bench.observe(0.7)
        result = pose_check(samples[-1], target)
        nominal_states = [e["state"] for e in report["events"] if e.get("event") == "state"]
        max_yaw = max(angle_error(s["tcp_world_yaw"], initial["tcp_world_yaw"]) for s in nominal_states)
        assert max_yaw < 0.02, max_yaw
        passed("nominal_xyz_and_heading", max_yaw_error_rad=max_yaw, **result)
        bench.command("move_joints", expected="rejected", positions=[10, 0, 0, 0])
        sample = bench.state()
        assert sample["mode"] == "IDLE" and sample["commanded"] == target
        passed("reject_before_motion")

        bench.command("fault", kind="hall_stuck", axis=1, factor=1)
        sample = bench.state(lambda s: s["mode"] == "FAULT")
        assert sample["hall"][0] and not sample["hall_nominal"][0]
        bench.command("rearm", expected="rejected")
        bench.command("clear_faults")
        sample = bench.state(lambda s: s["mode"] == "STOPPED")
        assert not sample["faults"] and sample["reference_valid"]
        bench.command("rearm")
        passed("hall_fault_and_explicit_rearm")

        bench.reset()
        bench.command("payload", mass=0.25)
        # Supervisor aplica los cambios de campos en el siguiente paso físico.
        sample = bench.state(lambda s: s["payload_mass"] == 0.25 and abs(s["tool_physics"]["mass"] - 0.4) < 1e-9)
        mass, center, inertia = box_with_payload(config["body_properties"][-1], 0.25)
        applied = sample["tool_physics"]
        assert abs(applied["mass"]-mass) < 1e-9
        assert math.dist(applied["center"], center) < 1e-9 and math.dist(applied["inertia"], inertia) < 1e-9
        loaded = bench.observe(0.8)[-1]
        pose_check(loaded, config["initial_positions"])
        force = abs(loaded["effort_feedback"][3])
        assert abs(force - mass*9.81) < 0.2, force
        passed("payload_physics_and_static_force", applied=applied, holding_force_N=force)

        bench.command("fault", kind="effort_loss", axis=4, factor=0)
        samples = bench.observe(1.2)
        fallen = samples[-1]
        drop = loaded["tcp_world"][2] - fallen["tcp_world"][2]
        assert fallen["effort_available"][3] == 0 and not fallen["reference_valid"]
        assert drop > 0.03 and fallen["simulated"][3] <= config["limits"][3][1] + 0.002, drop
        bench.command("clear_faults")
        bench.command("rearm", expected="rejected")
        sample = bench.state(lambda s: s["mode"] == "STOPPED")
        assert sample["effort_available"][3] == 0 and not sample["reference_valid"]
        passed("effort_loss_causes_gravity_drop_and_latches_reference", drop_m=drop)

        bench.reset()
        bench.command("payload", mass=1.0)
        samples = bench.observe(1.2)
        overload = samples[-1]
        overload_drop = forward(config["initial_positions"], config)[2] - overload["tcp_world"][2]
        assert overload["effort_available"][3] == 8 and overload_drop > 0.03, overload
        assert overload["simulated"][3] <= config["limits"][3][1] + 0.002
        assert overload["mode"] == "FAULT" and not overload["reference_valid"]
        bench.command("payload", expected="rejected", mass=0)
        bench.command("clear_faults")
        bench.command("rearm", expected="rejected")
        passed("overload_changes_physics", drop_m=overload_drop, effort_available_N=8,
               note="Aviso por carga conocida que supera esfuerzo estático; no hay detector por encoder")

        bench.reset()
        bench.command("rearm")
        bench.command("move_joints", positions=[0.4, 0.9, -1.3, 0.09], speed=0.5)
        bench.observe(0.5)
        bench.close()
        sample = bench.connect()
        if sample["mode"] != "STOPPED":
            sample = bench.state(lambda s: s["mode"] == "STOPPED")
        stopped = list(sample["estimated"])
        samples = bench.observe(1.5)
        assert all(s["mode"] == "STOPPED" and s["estimated"] == stopped for s in samples)
        bench.command("move_joints", expected="rejected", positions=config["initial_positions"])
        passed("disconnect_cancels_without_replay_or_automatic_rearm", stopped_reference=stopped)
        final = bench.reset()
        passed("reset_restores_stopped_initial_trial", **pose_check(final, config["initial_positions"]))
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        if bench.sock is not None:
            try:
                bench.send("stop")
            except OSError:
                pass
        raise
    finally:
        bench.close()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        print("Informe:", args.output, flush=True)


if __name__ == "__main__":
    main()
