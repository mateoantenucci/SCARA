#!/usr/bin/env python3
"""Audita once poses CAD y un recorrido frente al pedestal y suelo de ensayo.

Usar el Python OCP de tools/requirements-cad.txt. No conecta con Webots ni
mueve el robot. Las intersecciones BREP son evidencia de esas poses; la
comprobación continua del recorrido usa las cajas conservadoras del control.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.collisions import CollisionChecker, piece_boxes
from scara.frames import chain_frames, multiply
from scara.kinematics import forward, load_config, validate_joints
from tools.calcular_propiedades_cad import read_part


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calculate():
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.gp import gp_Pnt, gp_Trsf

    config = load_config()
    cad_path = ROOT/"cad/ensambles/integracion_articulada.json"
    properties_path = ROOT/"cad/propiedades/propiedades_geometricas.json"
    cad, properties = (json.loads(p.read_text()) for p in (cad_path, properties_path))
    checker = CollisionChecker(config)
    parts = {p["name"]: p for p in properties["parts"]}
    dependencies = ["config/scara.json", "config/cad_integration.json", "scara/collisions.py",
        "scara/frames.py", "scara/kinematics.py", "scara/runtime.py", "client/app.py",
        "tools/check_collisions.py", "tools/calcular_propiedades_cad.py",
        "tools/requirements-cad.txt", "tools/generate_world.py", "webots/protos/SCARA.proto",
        "webots/worlds/scara.wbt", "cad/ensambles/integracion_articulada.json",
        "cad/propiedades/propiedades_geometricas.json", "cad/derivados/informe.json"]
    expected = dict(cad["sources"])
    expected[cad["source_assembly"]] = cad["source_sha256"]
    for entry in cad["instances"]:
        expected[entry["source"]] = entry["source_sha256"]
        part = parts[Path(entry["source"]).stem]
        if part["source_sha256"] != entry["source_sha256"]:
            raise ValueError("Revisiones distintas en propiedades e integración: " + entry["source"])
        expected[part["step"]] = part["step_sha256"]
        expected.update({mesh["path"]: mesh["sha256"] for mesh in entry["meshes"]})
    for name, digest in expected.items():
        if sha256(ROOT/name) != digest:
            raise ValueError("Entrada distinta del manifiesto: " + name)
    sources = {name: sha256(ROOT/name) for name in sorted(set(dependencies) | expected.keys())}

    def box(bounds):
        lower, upper = ([v*1000 for v in bounds[offset:offset+3]] for offset in (0, 3))
        return BRepPrimAPI_MakeBox(gp_Pnt(*lower), gp_Pnt(*upper)).Shape()

    def placed(shape, matrix):
        transform = gp_Trsf()
        transform.SetValues(*(v for row in matrix[:3] for v in row[:3]+[row[3]*1000]))
        return BRepBuilderAPI_Transform(shape, transform, True).Shape()

    def bounds(shape):
        result = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, result, False, False)
        return [v/1000 for point in (result.CornerMin(), result.CornerMax())
                for v in (point.X(), point.Y(), point.Z())]

    def overlap(a, b):
        return all(a[i] <= b[i+3] and a[i+3] >= b[i] for i in range(3))

    obstacles = []
    for obstacle in config["environment"]:
        limits = ([c-s/2 for c,s in zip(obstacle["center"], obstacle["size"])]
                  + [c+s/2 for c,s in zip(obstacle["center"], obstacle["size"])])
        obstacles.append(dict(name=obstacle["name"], bounds=limits, shape=box(limits)))

    def contacts(shape, bbox):
        result = []
        for obstacle in obstacles:
            distance = BRepExtrema_DistShapeShape(shape, obstacle["shape"])
            distance.Perform()
            if not distance.IsDone():
                raise ValueError("No se pudo calcular distancia a " + obstacle["name"])
            volume = 0.0
            if overlap(bbox, obstacle["bounds"]):
                common = BRepAlgoAPI_Common(shape, obstacle["shape"])
                common.Build()
                if not common.IsDone():
                    raise ValueError("Falló intersección BREP con " + obstacle["name"])
                if not common.Shape().IsNull():
                    props = GProp_GProps()
                    BRepGProp.VolumeProperties_s(common.Shape(), props, True, True, False)
                    volume = props.Mass()*1e-9
                if volume < -1e-15 or not math.isfinite(volume):
                    raise ValueError("Volumen de intersección inválido")
            result.append(dict(obstacle=obstacle["name"], distance_m=distance.Value()/1000,
                intersection_volume_m3=max(0, volume), intersection_volume_cm3=max(0, volume)*1e6))
        return result

    shapes, exclusions = {}, []
    moving = [entry for entry in cad["instances"] if entry["group"] != "base"]
    for entry in moving:
        part = parts[Path(entry["source"]).stem]
        if part["status"] != "computed":
            exclusions.append(dict(instance=entry["instance_name"], group=entry["group"],
                                   source=entry["source"], reasons=part["errors"]))
            continue
        if part["name"] in shapes:
            continue
        step = ROOT/part["step"]
        measured = read_part(step)  # Validez BREP, sólidos/shells cerrados, sin caras sueltas.
        if abs(measured["volume_m3"]/part["properties"]["volume_m3"]-1) > 1e-8:
            raise ValueError("Volumen distinto del precálculo: " + part["name"])
        reader = STEPControl_Reader()
        if reader.ReadFile(str(step)) != IFSelect_RetDone:
            raise ValueError("No se pudo leer STEP: " + str(step))
        reader.SetSystemLengthUnit(1.0)
        if not reader.TransferRoots():
            raise ValueError("No se pudo transferir STEP: " + str(step))
        shapes[part["name"]] = reader.OneShape()

    poses = dict(initial=config["initial_positions"],
        initial_J4min=[0, math.pi/2, -math.pi/2, 0],
        initial_J4max=[0, math.pi/2, -math.pi/2, .12],
        folded_x135_J4max=[0, 3*math.pi/4, -3*math.pi/4, .12],
        folded_diag_J4max=[math.pi/8, 3*math.pi/4, -3*math.pi/4, .12],
        folded_diag_J4initial=[math.pi/8, 3*math.pi/4, -3*math.pi/4, .06],
        folded_negative_J4max=[0, -3*math.pi/4, 3*math.pi/4, .12],
        saved=cad["saved_joint_reference"],
        swept_start=[-math.pi/3, 2*math.pi/3, 0, .12],
        swept_middle=[-math.pi/12, 2*math.pi/3, 0, .12],
        swept_end=[math.pi/6, 2*math.pi/3, 0, .12])
    boxes = [entry for entry in piece_boxes(cad) if entry["group"] != "base"]
    pose_results = []
    for name, q in poses.items():
        q = validate_joints(q, config)
        frames = chain_frames(q, config)
        rows, envelopes, legacy = [], [], []
        for entry in moving:
            part = parts[Path(entry["source"]).stem]
            if part["name"] not in shapes:
                continue
            shape = placed(shapes[part["name"]], multiply(frames[entry["group"]], entry["body_from_piece"]))
            bbox = bounds(shape)
            rows.append(dict(instance=entry["instance_name"], group=entry["group"],
                source=entry["source"], bbox_m=bbox, contacts=contacts(shape, bbox)))
        for entry in boxes:
            limits = ([c-s/2 for c,s in zip(entry["center"], entry["size"])]
                      + [c+s/2 for c,s in zip(entry["center"], entry["size"])])
            shape = placed(box(limits), multiply(frames[entry["group"]], entry["pose"]))
            bbox = bounds(shape)
            envelopes.append(dict(instance=entry["name"], group=entry["group"],
                disposition=entry["disposition"], bbox_m=bbox, contacts=contacts(shape, bbox)))
        for group, entry in cad["body_boxes"].items():
            if group == "base":
                continue
            shape = placed(box(entry["bounds"]), frames[group])
            bbox = bounds(shape)
            legacy.append(dict(group=group, bbox_m=bbox, contacts=contacts(shape, bbox)))
        pose_results.append(dict(name=name, joints=q, tcp_pose=forward(q, config),
            guard_conflict=checker.first_conflict(q, q), cad_parts=rows,
            piece_envelopes=envelopes, previous_group_envelopes=legacy))
        print("CAD:", name, len(rows), "piezas válidas", flush=True)

    path_conflict = checker.first_conflict(poses["swept_start"], poses["swept_end"])
    observed = {p["name"]: p for p in pose_results}
    intrusions = [dict(pose=p["name"], instance=row["instance"], **contact)
        for p in pose_results for row in p["cad_parts"] for contact in row["contacts"]
        if contact["intersection_volume_m3"] > 1e-12]
    checks = [dict(name="guard_rejects_confirmed_CAD_intrusions", passed=all(
        observed[row["pose"]]["guard_conflict"] is not None for row in intrusions)),
        dict(name="initial_and_J4_extremes_clear", passed=all(
            observed[name]["guard_conflict"] is None for name in
            ("initial", "initial_J4min", "initial_J4max"))),
        dict(name="clear_endpoints_do_not_make_swept_path_safe", passed=(
            observed["swept_start"]["guard_conflict"] is None
            and observed["swept_end"]["guard_conflict"] is None
            and observed["swept_middle"]["guard_conflict"] is not None
            and path_conflict is not None)),
        dict(name="protected_inputs_unchanged", passed=all(
            sha256(ROOT/name) == digest for name,digest in sources.items()))]
    return dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
        status="passed" if all(c["passed"] for c in checks) else "failed",
        python=sys.version, kernel_distribution={name: importlib.metadata.version(name) for name in
            ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
        method="OCCT STEP in mm; rigid BREP placement; DistShapeShape and boolean Common; closed exact BREP volume",
        units=dict(length="m", volume="m^3", display_volume="cm^3", joints="rad,rad,rad,m"),
        scope="Movable pieces versus configured pedestal/floor at eleven poses; one nominal joint segment bounded continuously by guard",
        limitations=["No self-collision, unrepresented parts, transmission, tool or cable validation",
            "Fixed base support contact excluded from moving-piece audit",
            "Excluded BREP pieces keep conservative envelopes but have no certified CAD intersection volume",
            "BREP poses are finite samples, not a continuous CAD sweep or complete workspace proof",
            "Envelope guard bounds nominal reference only, not physical following, solver penetration or fault motion",
            "No Webots connection or native simulation was made by this tool"],
        collision_policy=config["collision_check"], environment=config["environment"],
        sources_sha256=sources, checks=checks,
        summary=dict(poses=len(poses), movable_instances=len(moving),
            valid_movable_instances=len(moving)-len(exclusions), excluded_movable_instances=len(exclusions),
            confirmed_intersections=len(intrusions)), exclusions=exclusions,
        confirmed_intersections=intrusions, poses=pose_results,
        swept_path=dict(start=poses["swept_start"], target=poses["swept_end"],
            parameterization="q(s)=start+s*(target-start), 0<=s<=1; same monotone quintic scalar for every joint",
            guard_conflict=path_conflict))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"validation/collisions.json")
    args = parser.parse_args()
    report = calculate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(dict(status=report["status"], **report["summary"]), ensure_ascii=False))
    print("Informe:", args.output)
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
