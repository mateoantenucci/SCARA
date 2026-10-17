#!/usr/bin/env python3
"""Comprueba ajustes de dos salidas visuales y mide tres piñones retenidos.

Usa los STEP actuales en mm y matrices guardadas, sin resolver mates, definir
fase de motor ni modificar el modelo. Requiere tools/requirements-cad.txt.
"""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.frames import multiply, rigid_inverse, transform_point
from tools.check_collisions import sha256


def calculate():
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    dependencies = ("tools/check_pulley_mounts.py", "tools/check_collisions.py", "tools/requirements-cad.txt",
        "scara/frames.py", "tools/registrar_subensambles.py", "cad/ensambles/informe.json",
        "cad/ensambles/registro_subensambles.json", "cad/ensambles/integracion_articulada.json",
        "cad/derivados/informe.json")
    sources = {p: sha256(ROOT/p) for p in dependencies}

    def verify(path, expected):
        if sha256(ROOT/path) != expected:
            raise ValueError("Fuente distinta del informe: " + path)
        sources[path] = expected

    registry = json.loads((ROOT/"cad/ensambles/registro_subensambles.json").read_text())
    if (registry["assembly_report_sha256"] != sources["cad/ensambles/informe.json"]
            or registry["script_sha256"] != sources["tools/registrar_subensambles.py"]
            or not registry["protected_inputs_unchanged"]):
        raise ValueError("Registro de subensambles desactualizado")
    raw = json.loads((ROOT/"cad/ensambles/informe.json").read_text())
    cad = json.loads((ROOT/"cad/ensambles/integracion_articulada.json").read_text())
    parts = {p["instance_name"]: p for p in cad["instances"]}
    assemblies = {Path(a["source"]).stem: a for a in raw["assemblies"]}
    routes = {r["source_assembly"]: r for r in registry["selected_partial_routes"]}
    additions = {p["proposed_occurrence"]: p for p in registry["proposed_additions"]}
    conversion = {Path(p["source"]).stem: p for p in
                  json.loads((ROOT/"cad/derivados/informe.json").read_text())["parts"]}
    geometry = {}

    def cylinders(name):
        if name in geometry:
            return geometry[name]
        part = conversion[name]
        if part["status"] != "kernel_validated":
            raise ValueError("Geometría no validada: " + name)
        verify(part["source"], part["source_sha256"])
        path = "cad/derivados/" + part["step"]["path"]
        verify(path, part["step"]["sha256"])
        reader = STEPControl_Reader()
        if reader.ReadFile(str(ROOT/path)) != IFSelect_RetDone:
            raise ValueError("No se pudo leer STEP: " + path)
        reader.SetSystemLengthUnit(1.0)
        if not reader.TransferRoots():
            raise ValueError("No se pudo transferir STEP: " + path)
        explorer = TopExp_Explorer(reader.OneShape(), TopAbs_FACE)
        rows = geometry[name] = []
        while explorer.More():
            surface = BRepAdaptor_Surface(TopoDS.Face(explorer.Current()), True)
            if surface.GetType() == GeomAbs_Cylinder:
                c = surface.Cylinder()
                o, axis = c.Location(), c.Axis().Direction()
                rows.append(dict(radius=c.Radius(), origin=[o.X(), o.Y(), o.Z()],
                    axis=[axis.X(), axis.Y(), axis.Z()],
                    ends=[[o.Coord(k)+axis.Coord(k)*v for k in (1, 2, 3)]
                          for v in (surface.FirstVParameter(), surface.LastVParameter())]))
            explorer.Next()
        return rows

    def matches(c, radius):
        return (abs(c["radius"]-radius) < 1e-6 and abs(abs(c["axis"][2])-1) < 1e-8
                and math.hypot(*c["origin"][:2]) < 1e-6)

    def piece(name, radius):
        return next(c for c in cylinders(name) if matches(c, radius))

    def point(matrix, p):
        return [v*1000 for v in transform_point(matrix, [v/1000 for v in p])]

    def span(matrix, c):
        return sorted(point(matrix, p)[2] for p in c["ends"])

    def gap(a, b):
        return math.dist(a[:2], b[:2])

    def engagement(a, b):
        return max(0, min(a[1], b[1])-max(a[0], b[0]))

    def parallel_to_saved_z(matrix, c):
        direction = [sum(matrix[i][j]*c["axis"][j] for j in range(3)) for i in range(3)]
        return math.hypot(*direction[:2]) < 1e-8 and abs(abs(direction[2])-1) < 1e-8

    def registered(name):
        candidate = additions[name]
        for evidence in candidate["evidence"]:
            assembly = assemblies[evidence["source_assembly"]]
            verify(assembly["source"], assembly["source_sha256"])
        return candidate

    def active(name):
        p = parts[name]
        native = conversion[Path(p["source"]).stem]
        if p["source_sha256"] != native["source_sha256"]:
            raise ValueError("Revisión activa distinta: " + name)
        return p

    outputs = []
    for occurrence, group, support, shaft, radius, origins in (
        ("2GT_80Teet_16Bore-registro-1", "arm", "A-BridaEje-1", "A-Eje", 8,
            ("0-EnsambleBase", "A-EnsambleBrazo")),
        ("2GT_60Teet_8Bore-registro-1", "forearm", "B-SoporteEjeFijo-registro-1", "B-Eje", 4,
            ("A-EnsambleBrazo", "B-EnsambleAntebrazo"))):
        candidate, model, fixed = registered(occurrence), active(occurrence), active(support)
        name, matrix = Path(candidate["basename"]).stem, candidate["transform_part_to_global_m"]
        bore = piece(name, radius)
        bore_span, bore_axis = span(matrix, bore), point(matrix, bore["origin"])
        support_name = Path(fixed["source"]).stem
        support_cylinder = next(c for c in cylinders(support_name) if abs(c["radius"]-radius) < 1e-6)
        support_axis = point(fixed["saved_object_to_assembly"], support_cylinder["origin"])
        screw = next(c for c in cylinders(name) if abs(c["axis"][2]) < 1e-8 and abs(c["radius"]-2) < 1e-6)
        screw_point = point(matrix, [0, 0, screw["origin"][2]])
        shafts = []
        for origin in origins:
            assembly = assemblies[origin]
            verify(assembly["source"], assembly["source_sha256"])
            row = next(p for p in assembly["configurations"][0]["instances"] if p["instance_name"] == shaft+"-1")
            native = conversion[shaft]
            if row["local_sha256"] != native["source_sha256"]:
                raise ValueError("Revisión del eje distinta: " + origin)
            sm = multiply(routes[origin]["transform_source_to_global_m"], row["transform_object_to_assembly_m"])
            sections = []
            for c in cylinders(shaft):
                if matches(c, radius):
                    interval = span(sm, c)
                    sections.append(dict(shaft_span_saved_Z_mm=interval,
                        engagement_mm=engagement(interval, bore_span),
                        axis_gap_mm=gap(point(sm, c["origin"]), bore_axis),
                        axis_parallel_to_saved_Z=parallel_to_saved_z(sm, c),
                        set_screw_on_shaft=interval[0]-1e-6 <= screw_point[2] <= interval[1]+1e-6))
            shafts.append(dict(assembly=origin, stamp=row["model_attributes"].get("swLastModifiedStamp"),
                cached_bbox_matches_current_geometry=row["current_brep_cached_bbox_agree_0_05mm"],
                shaft_to_saved_global=sm, sections=sections))
        outputs.append(dict(occurrence=occurrence, expected_group=group, active_group=model["group"],
            support=support, measured_bore_diameter_mm=2*bore["radius"],
            axis_gap_to_support_mm=gap(bore_axis, support_axis), bore_span_saved_Z_mm=bore_span,
            pulley_and_support_axes_parallel_to_saved_Z=parallel_to_saved_z(matrix, bore)
                and parallel_to_saved_z(fixed["saved_object_to_assembly"], support_cylinder),
            set_screw_axis_crossing_saved_mm=screw_point, pulley_to_saved_global=matrix,
            support_from_pulley=multiply(rigid_inverse(fixed["saved_object_to_assembly"]), matrix),
            active_saved_pose_max_error=max(abs(a-b) for ar, br in zip(matrix, model["saved_object_to_assembly"])
                for a, b in zip(ar, br)), shaft_placements=shafts))
    pinions = []
    for occurrence, motor, radius in (
        ("2GT_20Teet_635Bore-registro-1", "NEMA23-registro-2", 3.175),
        ("2GT_20Teet_635Bore-registro-2", "NEMA23-registro-1", 3.175),
        ("2GT_20Teet_5Bore-registro-1", "NEMA17-1", 2.5)):
        candidate, mp = registered(occurrence), active(motor)
        pc, mc = piece(Path(candidate["basename"]).stem, radius), piece(Path(mp["source"]).stem, radius)
        pm, mm = candidate["transform_part_to_global_m"], mp["saved_object_to_assembly"]
        pi, mi = span(pm, pc), span(mm, mc)
        pinions.append(dict(occurrence=occurrence, motor=motor,
            axis_gap_mm=gap(point(pm, pc["origin"]), point(mm, mc["origin"])),
            bore_span_saved_Z_mm=pi, motor_shaft_span_saved_Z_mm=mi, engagement_mm=engagement(pi, mi),
            status="held: requires its own rotor coordinate and phase"))
    inner_output = dict(occurrence="2GT_80Teet_10Bore-registro-1",
        measured_bore_diameter_mm=2*piece("2GT_80Teet_10Bore", 4.75)["radius"],
        measured_inner_shaft_diameter_mm=2*piece("A-EjeInterior", 4.75)["radius"],
        reason="Axis remains at J1; elbow transmission rotation needs an auxiliary rotor, not forearm parenting")
    checks = dict(output_axes_coincident=all(p["axis_gap_to_support_mm"] < 1e-6
        and p["pulley_and_support_axes_parallel_to_saved_Z"] for p in outputs),
        shaft_cached_revisions_match=all(s["cached_bbox_matches_current_geometry"] for p in outputs for s in p["shaft_placements"]),
        all_shaft_placements_engage_at_set_screw=all(any(c["engagement_mm"] > 0 and c["axis_gap_mm"] < 1e-6
            and c["set_screw_on_shaft"] and c["axis_parallel_to_saved_Z"] for c in s["sections"])
            for p in outputs for s in p["shaft_placements"]),
        active_groups_match=all(p["active_group"] == p["expected_group"] for p in outputs),
        active_saved_poses_preserved=all(p["active_saved_pose_max_error"] < 1e-10 for p in outputs),
        protected_inputs_unchanged=all(sha256(ROOT/p) == digest for p, digest in sources.items()))
    return dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
        status="visual_output_membership_check", checks=checks, sources_sha256=sources,
        units=dict(length="mm", matrix_translation="m"), outputs=outputs, held_pinions=pinions,
        held_inner_output=inner_output,
        limitations=["Visual grouping only; no additional mass, motor law, angular zero or certified mate",
            "Saved angular phases retained; radial set screws on round shafts do not establish an indexed phase",
            "NEMA17 cached geometry differs by 3 mm; its retained pinion position is not corrected here"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"validation/pulley_mounts.json")
    args = parser.parse_args()
    report = calculate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), checks=report["checks"]), ensure_ascii=False))
    if not all(report["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
