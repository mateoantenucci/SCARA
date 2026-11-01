#!/usr/bin/env python3
"""Revisa interferencias internas del CAD; no certifica recorridos CAD continuos.

Requiere el Python OCP de tools/requirements-cad.txt. No mueve Webots.
Una interferencia encontrada es un resultado de auditoría, no un fallo del cálculo.
"""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import itertools
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.collisions import CollisionChecker
from scara.frames import chain_frames, multiply
from scara.kinematics import load_config, validate_joints
from tools.calcular_propiedades_cad import read_part
from tools.check_collisions import sha256

# 0.001 mm³: distingue volumen positivo de residuos numéricos; no es una holgura.
VOLUME_THRESHOLD_MM3 = 0.001


def kernel():
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.gp import gp_Pnt, gp_Trsf

    def box(bounds):
        return BRepPrimAPI_MakeBox(gp_Pnt(*bounds[:3]), gp_Pnt(*bounds[3:])).Shape()

    def placed(shape, matrix):
        transform = gp_Trsf()
        transform.SetValues(*(v for row in matrix[:3] for v in row[:3]+[row[3]*1000]))
        return BRepBuilderAPI_Transform(shape, transform, True).Shape()

    def bounds(shape):
        result = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, result, False, False)
        return [v for p in (result.CornerMin(), result.CornerMax()) for v in (p.X(), p.Y(), p.Z())]

    def intersection(a, b):
        common = BRepAlgoAPI_Common(a, b)
        common.Build()
        if not common.IsDone():
            raise ValueError("Falló una intersección BREP")
        props = GProp_GProps()
        if not common.Shape().IsNull():
            BRepGProp.VolumeProperties_s(common.Shape(), props, True, True, False)
        volume = props.Mass()
        if not math.isfinite(volume) or volume < -VOLUME_THRESHOLD_MM3:
            raise ValueError("Volumen de intersección inválido")
        return max(0, volume)

    return box, placed, bounds, intersection


def overlap(a, b):
    return all(a[i] <= b[i+3] and a[i+3] >= b[i] for i in range(3))


def self_check(box, bounds, intersection):
    a, b, separate = (box(v) for v in ([0, 0, 0, 10, 10, 10],
        [5, 5, 5, 15, 15, 15], [20, 0, 0, 30, 10, 10]))
    return [dict(name="known_box_intersection_125_mm3", passed=(
        overlap(bounds(a), bounds(b)) and abs(intersection(a, b)-125) < 1e-7)),
        dict(name="separated_boxes_zero_volume", passed=(
            not overlap(bounds(a), bounds(separate)) and intersection(a, separate) < 1e-7))]


def paths(config):
    def q(j1, j2, j3, j4):
        return [math.radians(j1), math.radians(j2), math.radians(j3), j4]

    return {
        "tower_positive": (q(-90, 135, -135, .06), q(90, 135, -135, .06)),
        "tower_negative": (q(-90, -135, 135, .06), q(90, -135, 135, .06)),
        "pedestal": (q(-60, 120, 0, .12), q(30, 120, 0, .12)),
        "wrist_full_range": (q(0, 90, -150, .06), q(0, 90, 150, .06)),
        "vertical_full_range": (q(0, 90, -90, 0), q(0, 90, -90, .12)),
        "elbow_unfold": (q(0, -90, 90, .06), q(0, 90, -90, .06)),
    }


def scenarios(config, cad, extended=False):
    poses = dict(initial=config["initial_positions"], saved=cad["saved_joint_reference"],
        initial_J4min=[0, math.pi/2, -math.pi/2, 0], initial_J4max=[0, math.pi/2, -math.pi/2, .12],
        straight=[0, 0, 0, .06], folded_positive=[0, 3*math.pi/4, -3*math.pi/4, .06],
        folded_negative=[0, -3*math.pi/4, 3*math.pi/4, .06],
        folded_positive_J4max=[0, 3*math.pi/4, -3*math.pi/4, .12],
        folded_negative_J4max=[0, -3*math.pi/4, 3*math.pi/4, .12],
        wrist_positive=[0, math.pi/2, 5*math.pi/6, .06], wrist_negative=[0, math.pi/2, -5*math.pi/6, .06],
        shoulder_positive=[3*math.pi/4, math.pi/2, -math.pi/2, .06],
        shoulder_negative=[-3*math.pi/4, math.pi/2, -math.pi/2, .06],
        straight_J4min=[0, 0, 0, 0], straight_J4max=[0, 0, 0, .12])
    seen = {tuple(round(v, 12) for v in q) for q in poses.values()}
    for j1, j2, j4 in itertools.product((0, math.pi/4, -math.pi/4, math.pi/2, -math.pi/2),
                                     (3*math.pi/4, -3*math.pi/4), (0, .06, .12)):
        q = [j1, j2, -j2, j4]
        key = tuple(round(v, 12) for v in q)
        if key not in seen:
            poses[f"folded_J1_{round(math.degrees(j1))}_J2_{round(math.degrees(j2))}_J4_{round(j4*1000)}"] = q
            seen.add(key)
    if extended:
        for name, (start, target) in paths(config).items():
            for step in range(9):
                poses[f"path_{name}_{step}_of_8"] = [
                    a+step/8*(b-a) for a, b in zip(start, target)]
    return poses


def calculate(extended=False):
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    box, placed, bounds, intersection = kernel()
    dependencies = ("config/scara.json", "scara/collisions.py", "scara/frames.py", "scara/kinematics.py",
        "tools/check_self_collisions.py", "tools/check_collisions.py", "tools/calcular_propiedades_cad.py",
        "tools/requirements-cad.txt", "cad/ensambles/integracion_articulada.json",
        "cad/propiedades/propiedades_geometricas.json", "webots/protos/SCARA.proto", "webots/worlds/scara_uci.wbt")
    sources = {name: sha256(ROOT/name) for name in dependencies}
    config = load_config()
    cad = json.loads((ROOT/"cad/ensambles/integracion_articulada.json").read_text())
    properties = json.loads((ROOT/"cad/propiedades/propiedades_geometricas.json").read_text())
    parts = {p["name"]: p for p in properties["parts"]}
    expected = dict(cad["sources"])
    expected[cad["source_assembly"]] = cad["source_sha256"]
    shapes = {}
    for entry in cad["instances"]:
        part = parts[Path(entry["source"]).stem]
        if part["status"] != "computed" or part["source_sha256"] != entry["source_sha256"]:
            raise ValueError("Pieza no validada o revisión distinta: " + entry["instance_name"])
        expected.update({entry["source"]: entry["source_sha256"], part["step"]: part["step_sha256"]})
        expected.update({m["path"]: m["sha256"] for m in entry["meshes"]})
        if part["name"] in shapes:
            continue
        step = ROOT/part["step"]
        measured = read_part(step)
        if abs(measured["volume_m3"]/part["properties"]["volume_m3"]-1) > 1e-8:
            raise ValueError("Volumen distinto del precálculo: " + part["name"])
        reader = STEPControl_Reader()
        if reader.ReadFile(str(step)) != IFSelect_RetDone:
            raise ValueError("No se pudo leer STEP: " + str(step))
        reader.SetSystemLengthUnit(1.0)
        if not reader.TransferRoots():
            raise ValueError("No se pudo transferir STEP: " + str(step))
        shapes[part["name"]] = reader.OneShape()
    if any(sha256(ROOT/name) != digest for name, digest in expected.items()):
        raise ValueError("Entrada distinta del manifiesto CAD")
    sources.update(expected)
    checker, results, intrusions, false_boxes = CollisionChecker(config), [], [], []
    distance_pairs = {("R-Bancada-1", "Z-BujeExterior-1"), ("Z-Cuerpo-1", "Z-Piston-1")}
    pairs = {(a["instance_name"], b["instance_name"]): dict(
        a=a["instance_name"], b=b["instance_name"], groups=[a["group"], b["group"]],
        excluded_same_rigid_body=a["group"] == b["group"], bbox_candidates=0,
        positive_intersections=0)
        for a, b in itertools.combinations(cad["instances"], 2)}
    for name, q in scenarios(config, cad, extended).items():
        q = validate_joints(q, config)
        frames, rows = chain_frames(q, config), []
        for entry in cad["instances"]:
            matrix = multiply(frames[entry["group"]], entry["body_from_piece"])
            shape = placed(shapes[Path(entry["source"]).stem], matrix)
            rows.append((entry, shape, bounds(shape), matrix))
        candidates, hits = 0, []
        for (a, sa, ba, ma), (b, sb, bb, mb) in itertools.combinations(rows, 2):
            if a["group"] == b["group"] or not overlap(ba, bb):
                continue
            candidates += 1
            coverage = pairs[(a["instance_name"], b["instance_name"])]
            coverage["bbox_candidates"] += 1
            volume = intersection(sa, sb)
            pair = dict(a=a["instance_name"], b=b["instance_name"], groups=[a["group"], b["group"]],
                intersection_volume_mm3=volume, intersection_volume_cm3=volume/1000)
            if volume > VOLUME_THRESHOLD_MM3:
                coverage["positive_intersections"] += 1
                hits.append(pair)
                intrusions.append(dict(pose=name, joints=q, **pair))
            elif name == "initial":
                boxes = [placed(box([v*1000 for v in e["bbox_local_m"]]), m) for e, m in ((a, ma), (b, mb))]
                box_volume = intersection(*boxes)
                if box_volume > VOLUME_THRESHOLD_MM3:
                    item = dict(**pair, envelope_intersection_cm3=box_volume/1000)
                    if (pair["a"], pair["b"]) in distance_pairs:
                        distance = BRepExtrema_DistShapeShape(sa, sb)
                        distance.Perform()
                        if not distance.IsDone():
                            raise ValueError("Falló distancia CAD inicial")
                        item["cad_distance_mm"] = distance.Value()
                    false_boxes.append(item)
        results.append(dict(name=name, joints=q, bbox_candidates=candidates,
            positive_intersections=hits, guard_conflict=checker.first_conflict(q, q)))
        print("CAD interno:", name, len(hits), "interferencias", flush=True)
    path_results = []
    if extended:
        indexed = {p["name"]: p for p in results}
        for name, (start, target) in paths(config).items():
            samples = [indexed[f"path_{name}_{step}_of_8"] for step in range(9)]
            path_results.append(dict(name=name, start=start, target=target,
                sample_names=[p["name"] for p in samples],
                sample_fractions=[step/8 for step in range(9)],
                sampled_internal_intersections=sum(len(p["positive_intersections"]) for p in samples),
                endpoint_guard_conflicts=[checker.first_conflict(q, q) for q in (start, target)],
                continuous_envelope_guard_forward=checker.first_conflict(start, target),
                continuous_envelope_guard_reverse=checker.first_conflict(target, start),
                payload_variants=[dict(payload_kg=mass,
                    continuous_envelope_guard=checker.first_conflict(start, target, mass))
                    for mass in (0, .25)]))
    baseline = {"initial", "saved", "initial_J4min", "initial_J4max"}
    known = {"folded_positive", "folded_negative", "folded_J1_45_J2_135_J4_60", "folded_J1_-45_J2_-135_J4_60"}
    checks = self_check(box, bounds, intersection) + [
        dict(name="initial_saved_and_initial_J4_extremes_without_positive_volume", passed=all(
            not p["positive_intersections"] for p in results if p["name"] in baseline)),
        dict(name="four_known_tower_support_interferences_reproduced", passed=known <= {
            p["pose"] for p in intrusions if p["a"] == "0-Torre-1" and p["b"] == "Z-SoporteEfector-1"}),
        dict(name="guard_rejects_detected_interferences", passed=all(
            p["guard_conflict"] is not None for p in results if p["positive_intersections"])),
        dict(name="protected_inputs_unchanged", passed=all(sha256(ROOT/n) == d for n, d in sources.items()))]
    return dict(schema_version=2, created_utc=datetime.now(timezone.utc).isoformat(), audit_complete=True,
        status="interferences_found" if intrusions else "no_interference_in_sampled_poses",
        checks=checks, sources_sha256=sources, volume_threshold_mm3=VOLUME_THRESHOLD_MM3,
        kernel_distribution={n: importlib.metadata.version(n) for n in ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
        method="Closed validated STEP solids in mm; current body frames; AABB broadphase; boolean Common volume",
        units=dict(joints="rad,rad,rad,m", length="mm", volume="mm3 and cm3"),
        guard_policy=config["collision_check"],
        limitations=["Finite poses only; no continuous sweep or complete workspace proof",
            "No pairs within the same rigid body; omitted parts, tool, cables and transmissions not checked",
            "Guard conflict is a separate envelope check; no physical following or native selfCollision validation"],
        summary=dict(instances=len(cad["instances"]), poses=len(results),
            distinct_poses=len({tuple(round(v, 12) for v in p["joints"]) for p in results}),
            sampled_paths=len(path_results),
            bbox_candidates=sum(p["bbox_candidates"] for p in results), confirmed_intersections=len(intrusions),
            initial_envelope_overlaps_without_CAD_volume=len(false_boxes)),
        pair_coverage=list(pairs.values()), sampled_paths=path_results,
        confirmed_intersections=intrusions, initial_envelope_overlaps_without_CAD_volume=false_boxes, poses=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"validation/self_collisions.json")
    parser.add_argument("--self-check", action="store_true", help="Comprueba el cálculo con dos cajas y cajas separadas")
    parser.add_argument("--extended", action="store_true", help="Añade seis recorridos CAD muestreados, pares y variantes de carga del guard")
    args = parser.parse_args()
    if args.self_check:
        box, _, bounds, intersection = kernel()
        checks = self_check(box, bounds, intersection)
        print(json.dumps(checks))
    else:
        report = calculate(args.extended)
        checks = report["checks"]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
        print(json.dumps(dict(audit_complete=True, status=report["status"], **report["summary"])))
        print("Informe:", args.output)
    if not all(c["passed"] for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
