"""Interprete del banco PROVISIONAL scara-dev/1; no es el protocolo de la catedra."""

from pathlib import Path
import sys
import math
import json
from uuid import uuid4
import argparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from controller import Supervisor
from scara.dynamics import box_with_payload
from scara.kinematics import forward, load_config
from scara.runtime import Runtime
from scara.transport import Server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=9000)
    args = parser.parse_args()
    robot = Supervisor()
    config = load_config()
    runtime = Runtime(config)
    trial_id = str(uuid4())
    timestep = int(robot.getBasicTimeStep())
    motors = [robot.getDevice(f"j{i}_motor") for i in range(1, 5)]
    sensors = [robot.getDevice(f"j{i}_sensor") for i in range(1, 5)]
    for sensor in sensors:
        sensor.enable(timestep)
    for axis, motor in enumerate(motors):
        motor.setPosition(runtime.commanded[axis])
        motor.setVelocity(config["max_velocity"][axis])
        motor.setAcceleration(config["max_acceleration"][axis])
        if axis == 3:
            motor.enableForceFeedback(timestep)
        elif axis > 0:
            motor.enableTorqueFeedback(timestep)
    instance = robot.getFromDef("SCARA")
    tool = instance.getFromProtoDef("TOOL") if instance else None
    physics = tool.getField("physics").getSFNode() if tool else None
    cad_path = ROOT / "cad/ensambles/integracion_articulada.json"
    cad = json.loads(cad_path.read_text()) if cad_path.exists() else None
    cad_nodes = {entry["def_name"]: instance.getFromProtoDef(entry["def_name"])
                 for entry in cad["instances"]} if cad else {}
    server = Server(port=args.port)
    print(f"SCARA: banco provisional scara-dev/1 en TCP 127.0.0.1:{args.port}; habilitar desde la interfaz", flush=True)
    if tool is None:
        print("SCARA: instrumentacion TOOL no disponible; carga ajustable desactivada", flush=True)
    last_payload = 0.0
    last_state = -1.0
    joint_probe = None
    try:
        while robot.step(timestep) != -1:
            now = robot.getTime()
            for event in runtime.advance(now):
                server.send(event)
            if joint_probe is not None:
                value = sensors[3].getValue()
                joint_probe['samples'] += 1
                if not math.isfinite(value):
                    joint_probe['invalid_samples'] += 1
                else:
                    joint_probe['minimum_m'] = min(joint_probe['minimum_m'],value)
                    joint_probe['maximum_m'] = max(joint_probe['maximum_m'],value)
                    joint_probe['max_error_m'] = max(joint_probe['max_error_m'],abs(value-joint_probe['target_m']))
                joint_probe['command_changed'] |= runtime.commanded[3] != joint_probe['target_m']
                if now-joint_probe['start_time'] >= joint_probe['duration_s']:
                    server.send(dict(event='j4_window',end_time=now,**joint_probe))
                    joint_probe = None
            requests = server.poll()
            if server.lost:
                runtime.stop()
                server.lost = False
            for request in requests:
                if isinstance(request,dict) and request.get('command') == 'inspect_j4_window':
                    # Resumen a cada paso físico; instrumentación sin realimentación.
                    event = runtime.handle({'command':'status','id':request.get('id')},now)
                    seconds = request.get('seconds',2.0)
                    if (joint_probe is not None or isinstance(seconds,bool)
                            or not isinstance(seconds,(int,float)) or not .1 <= seconds <= 5):
                        event = dict(event='rejected',id=event.get('id'),message='Ventana ocupada o duración fuera de 0.1–5 s')
                    if event['event'] == 'accepted':
                        value = sensors[3].getValue()
                        invalid = not math.isfinite(value)
                        if invalid:
                            value = 0.0  # La ventana fallará por invalid_samples; JSON finito.
                        joint_probe = dict(id=request.get('id'),start_time=now,duration_s=seconds,
                            target_m=runtime.commanded[3],samples=0,minimum_m=value,maximum_m=value,
                            max_error_m=abs(value-runtime.commanded[3]),command_changed=False,
                            basic_time_step_ms=timestep,invalid_samples=int(invalid),trial_id=trial_id)
                    server.send(event)
                    continue
                if isinstance(request, dict) and request.get("command") == "inspect_contacts":
                    # Instrumentación de ensayo: solo lectura, sin intervenir en el control.
                    event = runtime.handle({"command": "status", "id": request.get("id")}, now)
                    server.send(event)
                    if event['event'] == 'accepted':
                        points = instance.getContactPoints(True)
                        counts = {}
                        for group,def_name in cad['body_defs'].items():
                            body = instance if group == 'base' else instance.getFromProtoDef(def_name)
                            field = (body.getBaseNodeField('boundingObject') if group == 'base'
                                     else body.getField('boundingObject'))
                            bounding = field.getSFNode()
                            counts[group] = bounding.getField('children').getCount()
                        server.send(dict(event='contact_snapshot',id=request.get('id'),time=now,
                            total_contacts=len(points), tool_node_id=tool.getId(), collision_box_counts=counts,
                            contacts=[dict(point=list(p.point),node_id=p.node_id) for p in points[:16]]))
                    continue
                if isinstance(request, dict) and request.get("command") == "inspect_cad":
                    # Instrumentación de ensayo, nunca fuente de realimentación del control.
                    event = runtime.handle({"command": "status", "id": request.get("id")}, now)
                    if not cad or any(node is None for node in cad_nodes.values()):
                        event = {"event": "rejected", "id": event.get("id"),
                                 "message": "Manifest CAD y nodos no coinciden; regenerar mundo"}
                    server.send(event)
                    if event["event"] == "accepted":
                        actual = [sensor.getValue() for sensor in sensors]
                        for group, def_name in cad["body_defs"].items():
                            body = instance if group == "base" else instance.getFromProtoDef(def_name)
                            body_physics = body.getField("physics").getSFNode() if group != "base" else None
                            server.send({"event": "cad_snapshot", "id": request.get("id"),
                                "time": now, "group": group, "simulated": actual,
                                "body_position": body.getPosition(), "body_orientation": body.getOrientation(),
                                "body_mass": body_physics.getField("mass").getSFFloat() if body_physics else None,
                                "parts": [{"name": entry["def_name"],
                                           "position": cad_nodes[entry["def_name"]].getPosition(),
                                           "orientation": cad_nodes[entry["def_name"]].getOrientation()}
                                          for entry in cad["instances"] if entry["group"] == group]})
                        server.send({"event": "cad_snapshot_complete", "id": request.get("id")})
                    continue
                if isinstance(request, dict) and request.get("command") == "reset_trial":
                    event = runtime.handle({"command": "status", "id": request.get("id")}, now)
                    if event["event"] == "rejected":
                        server.send(event)
                        continue
                    runtime.stop()
                    server.send({"event": "accepted", "id": request.get("id"),
                                 "message": "Recarga del ensayo; no es homing del robot fisico"})
                    server.poll()  # Enviar acuse si el socket sigue abierto; descartar otras ordenes.
                    robot.worldReload()
                    return
                if isinstance(request, dict) and request.get("command") == "payload" and physics is None:
                    event = {"event": "rejected", "id": request.get("id"), "message": "Fisica de carga no disponible"}
                else:
                    event = runtime.handle(request, now)
                server.send(event)
                last_state = -1.0
            if runtime.payload_mass != last_payload:
                mass, center, inertia = box_with_payload(config["body_properties"][-1], runtime.payload_mass)
                # Los campos internos del PROTO son de solo lectura para Supervisor.
                instance.getField("toolMass").setSFFloat(mass)
                instance.getField("toolCenterOfMass").setMFVec3f(0, center)
                instance.getField("toolInertiaMatrix").setMFVec3f(0, inertia[:3])
                instance.getField("toolInertiaMatrix").setMFVec3f(1, inertia[3:])
                last_payload = runtime.payload_mass
            for i, (motor, factor) in enumerate(zip(motors, runtime.effort_factors())):
                if i == 3:
                    motor.setAvailableForce(config["max_effort"][i] * factor)
                else:
                    motor.setAvailableTorque(config["max_effort"][i] * factor)
                motor.setPosition(runtime.commanded[i])
            if server.client is not None and now - last_state >= 0.128:
                actual = [sensor.getValue() for sensor in sensors]
                if not all(math.isfinite(v) for v in actual):
                    continue
                nominal = [abs(value-bounds[0]) < (0.0005 if i == 3 else 0.01)
                           for i, (value, bounds) in enumerate(zip(actual, config["limits"]))]
                end_hall = [abs(value-bounds[1]) < (0.0005 if i == 3 else 0.01)
                            for i, (value, bounds) in enumerate(zip(actual, config["limits"]))]
                feedback = [None]
                for i, motor in enumerate(motors[1:], 1):
                    value = motor.getForceFeedback() if i == 3 else motor.getTorqueFeedback()
                    feedback.append(value if math.isfinite(value) else None)
                orientation = tool.getOrientation() if tool else None
                state = {
                    "time": now, "trial_id": trial_id, "mode": runtime.mode,
                    "commanded": runtime.commanded, "estimated": runtime.estimated, "simulated": actual,
                    "estimated_pose": forward(runtime.estimated, config), "simulated_pose": forward(actual, config),
                    "hall": runtime.hall_output(nominal), "hall_nominal": nominal, "end_hall": end_hall,
                    "faults": runtime.faults, "payload_mass": runtime.payload_mass,
                    "reference_valid": runtime.reference_valid,
                    "effort_available": [a*b for a,b in zip(config["max_effort"], runtime.effort_factors())],
                    "effort_feedback": feedback,
                    "effort_feedback_note": "J1 no disponible con base estatica; los otros valores son aproximaciones de Webots",
                    "tcp_world": tool.getPosition() if tool else None,
                    "tcp_world_yaw": math.atan2(orientation[3], orientation[0]) if orientation else None,
                    "tool_physics": {
                        "mass": physics.getField("mass").getSFFloat(),
                        "center": physics.getField("centerOfMass").getMFVec3f(0),
                        "inertia": (physics.getField("inertiaMatrix").getMFVec3f(0) +
                                    physics.getField("inertiaMatrix").getMFVec3f(1)),
                    } if physics else None,
                    "model_status": config["model_status"], "protocol": "scara-dev/1",
                }
                server.send({"event": "state", "state": state})
                last_state = now
    finally:
        server.close()


if __name__ == "__main__":
    main()
