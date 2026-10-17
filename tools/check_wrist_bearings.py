#!/usr/bin/env python3
"""Compara los asientos de muñeca guardados; no modifica el modelo móvil.

Requiere tools/requirements-cad.txt. La alternativa usa la pose de la Contra
de R-EnsambleRotacion, registrada únicamente por R-Bancada; no traslada 3 mm.
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
from scara.frames import multiply, rigid_inverse, transform_point
from tools.check_collisions import sha256
from tools.check_self_collisions import kernel
from tools.registrar_subensambles import registration_candidates

TOL_MM = 1e-6
VOLUME_TOL_MM3 = 0.001
NAMES = ("R-Bancada", "R-ContraBancada", "Z-6907-2RS", "Z-BujeExterior")
BASELINE = "validation/historico/antes_montaje_20261016/config/scara.json"


def measure():
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Fuse
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    _, placed, bounds, intersection = kernel()
    dependencies = ("tools/check_wrist_bearings.py", "tools/check_self_collisions.py",
        "tools/check_collisions.py", "tools/registrar_subensambles.py", "tools/requirements-cad.txt",
        "scara/frames.py", "config/scara.json", BASELINE,
        "cad/ensambles/informe.json", "cad/ensambles/registro_subensambles.json",
        "cad/derivados/informe.json")
    sources = {p: sha256(ROOT/p) for p in dependencies}
    report = json.loads((ROOT/"cad/ensambles/informe.json").read_text())
    registry = json.loads((ROOT/"cad/ensambles/registro_subensambles.json").read_text())
    if (registry["assembly_report_sha256"] != sources["cad/ensambles/informe.json"]
            or registry["script_sha256"] != sources["tools/registrar_subensambles.py"]):
        raise ValueError("Registro de subensambles desactualizado")
    conversion = json.loads((ROOT/"cad/derivados/informe.json").read_text())
    config = json.loads((ROOT/"config/scara.json").read_text())
    baseline = json.loads((ROOT/BASELINE).read_text())
    assemblies, revisions = {}, {n: [] for n in NAMES}
    for assembly in report["assemblies"]:
        rows = assembly["configurations"][0]["instances"]
        relevant = [r for r in rows if Path(r["basename"]).stem in NAMES]
        if not relevant:
            continue
        sources[assembly["source"]] = assembly["source_sha256"]
        key = Path(assembly["source"]).stem
        assemblies[key] = {r["instance_name"]: r for r in rows}
        for r in relevant:
            sources[r["local_source"]] = r["local_sha256"]
            revisions[Path(r["basename"]).stem].append(dict(assembly=key,
                instance=r["instance_name"], configuration=r["model_attributes"].get("swConfigurationName"),
                stamp=r["model_attributes"].get("swLastModifiedStamp"),
                creation_time=r["file_attributes"].get("swCreationTime"),
                current_bbox_agrees_with_cache=r["current_brep_cached_bbox_agree_0_05mm"]))
    shapes, cylinders, contact_faces = {}, {}, {}
    bearing_symmetry = dict(cylinders=0, planes=0, coaxial_full_cylinders=True, normal_planes=True)
    for name in NAMES:
        part = next(p for p in conversion["parts"] if Path(p["source"]).stem == name)
        if part["status"] != "kernel_validated":
            raise ValueError("STEP no validado: " + name)
        path = "cad/derivados/" + part["step"]["path"]
        sources[path] = part["step"]["sha256"]
        sources[part["source"]] = part["source_sha256"]
        reader = STEPControl_Reader()
        if reader.ReadFile(str(ROOT/path)) != IFSelect_RetDone:
            raise ValueError("No se pudo leer STEP: " + path)
        reader.SetSystemLengthUnit(1.0)
        if not reader.TransferRoots():
            raise ValueError("No se pudo transferir STEP: " + path)
        shape = shapes[name] = reader.OneShape()
        cylinders[name], contact_faces[name] = [], []
        explorer, index = TopExp_Explorer(shape, TopAbs_FACE), 0
        while explorer.More():
            face = TopoDS.Face(explorer.Current())
            surface = BRepAdaptor_Surface(face, True)
            if surface.GetType() == GeomAbs_Cylinder:
                c = surface.Cylinder()
                o, axis = c.Location(), c.Axis().Direction()
                ends = [[o.Coord(i)+axis.Coord(i)*v for i in range(1, 4)]
                        for v in (surface.FirstVParameter(), surface.LastVParameter())]
                cylinders[name].append(dict(face=index, radius_mm=c.Radius(), ends_mm=ends,
                    axis=[axis.X(), axis.Y(), axis.Z()]))
                if name == "Z-6907-2RS":
                    bearing_symmetry["cylinders"] += 1
                    bearing_symmetry["coaxial_full_cylinders"] &= (math.hypot(o.X(), o.Y()) < TOL_MM
                        and abs(abs(axis.Z())-1) < 1e-8
                        and abs(surface.LastUParameter()-surface.FirstUParameter()-2*math.pi) < 1e-8)
            elif surface.GetType() == GeomAbs_Plane:
                p = surface.Plane()
                o, axis = p.Location(), p.Axis().Direction()
                if name == "Z-6907-2RS":
                    bearing_symmetry["planes"] += 1
                    bearing_symmetry["normal_planes"] &= abs(abs(axis.Z())-1) < 1e-8
                if ((name == "R-Bancada" and abs(abs(axis.Z())-1) < 1e-8 and abs(o.Z()+20) < TOL_MM)
                    or (name == "R-ContraBancada" and abs(abs(axis.Y())-1) < 1e-8 and abs(o.Y()) < TOL_MM)):
                    contact_faces[name].append(face)
            elif name == "Z-6907-2RS":
                raise ValueError("Superficie de rodamiento no axialmente simétrica")
            explorer.Next()
            index += 1
    if any(sha256(ROOT/p) != digest for p, digest in sources.items()):
        raise ValueError("Fuente distinta del informe o modificación durante la lectura")

    def is_radius(c, radius):
        return abs(c["radius_mm"]-radius) < TOL_MM

    def point_mm(matrix, point):
        return [v*1000 for v in transform_point(matrix, [p/1000 for p in point])]

    def seats(name, relative):
        result = []
        for c in cylinders[name]:
            if is_radius(c, 27.5):
                ends = [point_mm(relative, p) for p in c["ends_mm"]]
                result.append(dict(face=c["face"], interval_on_Bancada_Y_mm=sorted(p[1] for p in ends),
                    max_axis_offset_mm=max(math.hypot(p[0], p[2]+20) for p in ends)))
        return sorted(result, key=lambda x: x["interval_on_Bancada_Y_mm"])

    identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    bank_seats = seats("R-Bancada", identity)
    bank_holes = [c for c in cylinders["R-Bancada"]
                  if is_radius(c, 2.5) and abs(abs(c["axis"][2])-1) < 1e-8]

    def area(shape):
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(shape, props)
        return props.Mass()

    def volume(shape):
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props, True, True, False)
        return props.Mass()

    def assess(bank, counter, bearings, bushing):
        relative = multiply(rigid_inverse(bank), counter)
        counter_seats = seats("R-ContraBancada", relative)
        holes = []
        for c in cylinders["R-ContraBancada"]:
            if is_radius(c, 2.5) and abs(abs(c["axis"][1])-1) < 1e-8:
                p = point_mm(relative, c["ends_mm"][0])
                direction = [sum(relative[i][j]*c["axis"][j] for j in range(3)) for i in range(3)]
                holes.append(dict(face=c["face"], axis_point_in_Bancada_mm=p,
                    nearest_Bancada_axis_offset_mm=min(math.dist(p[:2], h["ends_mm"][0][:2]) for h in bank_holes),
                    parallel_to_Bancada_holes=abs(abs(direction[2])-1) < 1e-8))
        contact_area = 0
        for a, b in itertools.product(contact_faces["R-Bancada"], contact_faces["R-ContraBancada"]):
            op = BRepAlgoAPI_Common(a, placed(b, relative))
            op.Build()
            if not op.IsDone():
                raise ValueError("Falló la comparación de las caras de unión")
            contact_area += area(op.Shape())
        # La cara local Y=0 de la Contra debe caer en Z=-20 de Bancada.
        contact = [point_mm(relative, p) for p in ([0, 0, 0], [1, 0, 0], [0, 0, 1])]
        bearing_rows = []
        for name, pose in bearings.items():
            bearing = placed(shapes["Z-6907-2RS"], pose)
            local = multiply(rigid_inverse(bank), pose)
            ends = [point_mm(local, p) for p in ([0, 0, 0], [0, 0, 10])]
            bearing_rows.append(dict(instance=name, pose=pose,
                interval_on_Bancada_Y_mm=sorted(p[1] for p in ends),
                max_axis_offset_mm=max(math.hypot(p[0], p[2]+20) for p in ends),
                intersection_mm3={n: intersection(bearing, placed(shapes[n], matrix)) for n, matrix in
                    (("R-Bancada", bank), ("R-ContraBancada", counter), ("Z-BujeExterior", bushing))}))
        return dict(Bancada_from_Contra=relative, counter_seats=counter_seats,
            seat_displacements_mm=[[b-a for a, b in zip(x["interval_on_Bancada_Y_mm"], y["interval_on_Bancada_Y_mm"])]
                for x, y in zip(bank_seats, counter_seats)], holes=holes,
            contact_plane_max_gap_mm=max(abs(p[2]+20) for p in contact),
            contact_area_mm2=contact_area, bearings=bearing_rows)

    global_rows, rotation = assemblies["0-EnsambleColision"], assemblies["R-EnsambleRotacion"]
    pose = lambda rows, name: rows[name+"-1"]["transform_object_to_assembly_m"]
    bank, original_counter = pose(global_rows, "R-Bancada"), pose(global_rows, "R-ContraBancada")
    registration = multiply(bank, rigid_inverse(pose(rotation, "R-Bancada")))
    candidate_counter = multiply(registration, pose(rotation, "R-ContraBancada"))
    original_bearings = {p["proposed_occurrence"]: p["transform_part_to_global_m"]
                        for p in registry["proposed_additions"] if p["basename"] == "Z-6907-2RS.SLDPRT"}
    source_bearings = {n: r["transform_object_to_assembly_m"] for n, r in rotation.items()
                       if r["basename"] == "Z-6907-2RS.SLDPRT"}
    original = assess(bank, original_counter, original_bearings, pose(global_rows, "Z-BujeExterior"))
    candidate = assess(bank, candidate_counter, original_bearings, pose(global_rows, "Z-BujeExterior"))
    source = assess(pose(rotation, "R-Bancada"), pose(rotation, "R-ContraBancada"),
                    source_bearings, pose(rotation, "Z-BujeExterior"))
    candidates = registration_candidates(list(rotation.values()), list(global_rows.values()))
    anchor = next(c for c in candidates if c["anchor_source_instance"] == "R-Bancada-1")
    delta = multiply(rigid_inverse(original_counter), candidate_counter)
    expected_delta = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, .0476], [0, 0, 0, 1]]
    # Rellenar el canal central permite comprobar la simetría de exterior y fijaciones.
    counter_shape = shapes["R-ContraBancada"]
    fuse = BRepAlgoAPI_Fuse(counter_shape, BRepPrimAPI_MakeCylinder(35, 47.6).Shape())
    fuse.Build()
    if not fuse.IsDone():
        raise ValueError("Falló la comprobación de simetría exterior")
    filled = fuse.Shape()
    exterior_difference = max(0, 2*(volume(filled)-intersection(filled, placed(filled, expected_delta))))
    full_difference = max(0, 2*(volume(counter_shape)-intersection(counter_shape, placed(counter_shape, expected_delta))))
    physical_keys = ("geometry", "limits", "initial_positions", "max_velocity", "max_acceleration",
                     "max_effort", "body_properties", "environment", "simulation")
    all_zero = lambda data: all(v <= VOLUME_TOL_MM3 for b in data["bearings"] for v in b["intersection_mm3"].values())
    seat_error = lambda data: max(abs(v) for row in data["seat_displacements_mm"] for v in row)
    checks = dict(same_mount_and_bearing_cached_revisions=all(len({(r["configuration"], r["stamp"], r["creation_time"])
        for r in revisions[name]}) == 1 for name in NAMES[:3]),
        expected_two_seats_and_two_bearings=len(bank_seats) == len(candidate["counter_seats"])
            == len(original_bearings) == len(source_bearings) == 2,
        original_seat_displacement_is_3mm=all(abs(v+3) < TOL_MM for row in original["seat_displacements_mm"] for v in row),
        source_seats_aligned=seat_error(source) < TOL_MM, candidate_seats_aligned=seat_error(candidate) < TOL_MM,
        candidate_bearing_axes_coincident=all(b["max_axis_offset_mm"] < TOL_MM for b in candidate["bearings"]),
        candidate_four_holes_aligned=len(candidate["holes"]) == 4 and all(h["nearest_Bancada_axis_offset_mm"] < TOL_MM
            and h["parallel_to_Bancada_holes"] for h in candidate["holes"]),
        candidate_contact_plane_preserved=candidate["contact_plane_max_gap_mm"] < TOL_MM,
        candidate_full_contact_area=abs(candidate["contact_area_mm2"]-sum(area(f) for f in contact_faces["R-ContraBancada"])) < TOL_MM,
        original_bearing_interference_reproduced=any(v > VOLUME_TOL_MM3 for b in original["bearings"] for v in b["intersection_mm3"].values()),
        source_bearings_clear=all_zero(source), candidate_bearings_clear=all_zero(candidate),
        bearing_shape_axisymmetric=bearing_symmetry["cylinders"] == bearing_symmetry["planes"] == 6
            and bearing_symmetry["coaxial_full_cylinders"] and bearing_symmetry["normal_planes"],
        exact_180_degree_local_Y_inversion=max(abs(a-b) for ar, br in zip(delta, expected_delta) for a, b in zip(ar, br)) < 1e-10,
        exterior_and_fastening_pattern_symmetric=exterior_difference <= VOLUME_TOL_MM3,
        numerical_physics_unchanged=all(config[k] == baseline[k] for k in physical_keys),
        protected_inputs_unchanged=all(sha256(ROOT/p) == digest for p, digest in sources.items()))
    return dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
        status="source_pose_diagnosis_only", active_model_modified=False, checks=checks,
        sources_sha256=sources, units=dict(length="mm; pose translations in m", volume="mm3", area="mm2"),
        tolerance_mm=TOL_MM, volume_tolerance_mm3=VOLUME_TOL_MM3,
        kernel_distribution={n: importlib.metadata.version(n) for n in ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
        revisions=revisions, revision_check_scope=list(NAMES[:3]),
        local_cylinders=cylinders, Bancada_seats=bank_seats,
        saved_rotation_assembly=source, original_global_with_hypothetical_bearings=original,
        candidate_global_with_registered_bearings=candidate,
        candidate_transform=dict(formula="T_global_Bancada * inverse(T_Rrot_Bancada) * T_Rrot_Contra",
            source_to_global=registration, global_from_Contra=candidate_counter,
            original_Contra_from_candidate_Contra=delta, registration_evidence=anchor,
            independent_shared_part_anchors=0,
            phase="Only R-Bancada is the shared anchor. Contra orientation is copied exactly from R-EnsambleRotacion; no added phase or 3 mm translation.",
            bearing_phase="Existing registry bearing poses are retained; their geometry is axially symmetric, with no separate race motion represented."),
        symmetry=dict(bearing=bearing_symmetry, full_solid_symmetric_difference_mm3=full_difference,
            symmetric_difference_after_filling_central_R35_channel_mm3=exterior_difference,
            interpretation="Exterior and fastening pattern are symmetric; the stepped internal channel is not."),
        limitations=["Saved placements and current STEP geometry; no mate solver or official revision certification",
            "Single shared-part anchor, supplemented by seat, axis, four-hole and contact-face measurements",
            "Original global has no bearings: its bearing intersections use hypothetical registry placements",
            "No edits to integration, world or configuration; no claim about active-model validation"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"validation/wrist_bearing_diagnosis.json")
    args = parser.parse_args()
    report = measure()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), checks=report["checks"]), ensure_ascii=False))
    if not all(report["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
