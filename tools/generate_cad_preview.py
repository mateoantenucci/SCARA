#!/usr/bin/env python3
"""Build a static CAD inspection world from saved, verified instance transforms.

Blue: current BREP bounding box agrees with assembly cache within 0.05 mm.
Amber: a saved/current bounding box mismatch. Magenta wire boxes: unavailable
accepted STL, drawn only as cached bounds. No motors, Physics, collision objects
or inferred masses. The dynamic scara_uci.wbt is never touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def axis_angle(matrix):
    cosine = max(-1.0, min(1.0, (sum(matrix[i][i] for i in range(3)) - 1) / 2))
    angle = math.acos(cosine)
    if angle < 1e-10:
        return [0.0, 0.0, 1.0, 0.0]
    if math.pi - angle < 1e-7:
        # Near pi, skew terms vanish. Recover an axis from the strongest column
        # of R+I; its sign is immaterial at an exact half-turn.
        k = max(range(3), key=lambda i: matrix[i][i])
        axis = [matrix[i][k] + (1 if i == k else 0) for i in range(3)]
    else:
        axis = [matrix[2][1] - matrix[1][2], matrix[0][2] - matrix[2][0],
                matrix[1][0] - matrix[0][1]]
    norm = math.sqrt(sum(v*v for v in axis))
    return [v / norm for v in axis] + [angle]


def numbers(values):
    return " ".join(f"{value:.15g}" for value in values)


def camera_orientation(eye, target):
    def unit(vector):
        norm = math.sqrt(sum(v*v for v in vector))
        return [v / norm for v in vector]
    forward = unit([b-a for a, b in zip(eye, target)])
    left = unit([-forward[1], forward[0], 0])
    up = [forward[1]*left[2]-forward[2]*left[1],
          forward[2]*left[0]-forward[0]*left[2],
          forward[0]*left[1]-forward[1]*left[0]]
    # Webots Viewpoint looks along local +X; local +Z is up.
    return axis_angle([[forward[i], left[i], up[i]] for i in range(3)])


def wire_box(bbox):
    points = [[bbox[3] if i & 1 else bbox[0], bbox[4] if i & 2 else bbox[1],
               bbox[5] if i & 4 else bbox[2]] for i in range(8)]
    edges = [(i, i ^ bit) for i in range(8) for bit in (1, 2, 4) if i < (i ^ bit)]
    return ("Shape { appearance Appearance { material Material { emissiveColor 0.85 0.1 0.5 } }\n"
            "geometry IndexedLineSet { coord Coordinate { point [\n" +
            "\n".join(numbers(p) + "," for p in points) + "\n] } coordIndex [\n" +
            "\n".join(f"{a}, {b}, -1," for a, b in edges) + "\n] } }")


def tower_body_meshes(instance):
    """Accept the separately reported three bodies, never the rejected union."""
    from convertir_cad import mesh_metrics

    report_path = ROOT / "cad/derivados/torre_por_cuerpos/informe.json"
    report = json.loads(report_path.read_text())
    assert report["source"]["sha256"] == instance["local_sha256"] == digest(ROOT / report["source"]["path"])
    assert digest(ROOT / report["step"]["path"]) == report["step"]["sha256"]
    assert digest(ROOT / "cad/derivados/informe.json") == report["batch_report_sha256_before"]
    assert digest(ROOT / "tools/exportar_torre_cuerpos.py") == report["script_sha256"]
    assert report["all_individual_meshes_validated"] and report["protected_inputs_unchanged"]
    assert report["scale_mm_to_m"] == .001 and not report["origin_or_orientation_changed"]
    assert not report["explicit_brep_repair"] and not report["global_mesh_manifold_validated"]
    assert len(report["bodies"]) == 3
    meshes = []
    for body in report["bodies"]:
        assert body["status"] == "individual_mesh_validated" and body["brep_valid"] and not body["errors"]
        filtering, mesh = body["zero_area_filter"], body["derived_stl"]
        assert filtering["removed_positive_area_triangles"] == filtering["vertices_moved_or_welded"] == filtering["triangles_added"] == 0
        assert filtering["retained_triangle_records_byte_identical"] and filtering["bbox_float32_identical"]
        assert filtering["geometric_oriented_volume_exactly_preserved"]
        assert digest(report_path.parent / body["raw_stl"]["path"]) == body["raw_stl"]["sha256"]
        path = report_path.parent / mesh["path"]
        assert digest(path) == mesh["sha256"]
        actual = mesh_metrics(path)
        assert all(actual[key] == value for key, value in mesh["metrics"].items() if key in actual)
        assert actual["boundary_edges"] == actual["nonmanifold_edges"] == 0
        assert mesh["metrics"]["relative_volume_error_to_brep"] < .01
        assert mesh["metrics"]["max_bbox_error_m"] < .0000501
        meshes.append({"path": str(path.relative_to(ROOT)), "sha256": mesh["sha256"],
                       "individual_gate_status": body["status"],
                       "zero_area_triangles_removed": filtering["removed_triangles"]})
    return meshes, {"path": str(report_path.relative_to(ROOT)), "sha256": digest(report_path),
                    "global_mesh_manifold_validated": False}


def self_check():
    from extraer_ensamble import matrix_from_xml
    for raw in ["0 1 0 0 -1 0 0 0 0 0 1 0 .1 .2 .3 1",
                "1 0 0 0 0 -1 0 0 0 0 -1 0 0 0 0 1"]:
        matrix, _, _ = matrix_from_xml(raw)
        x, y, z, a = axis_angle(matrix)
        c, s, t = math.cos(a), math.sin(a), 1-math.cos(a)
        rebuilt = [[t*x*x+c, t*x*y-s*z, t*x*z+s*y],
                   [t*x*y+s*z, t*y*y+c, t*y*z-s*x],
                   [t*x*z-s*y, t*y*z+s*x, t*z*z+c]]
        assert max(abs(rebuilt[i][j]-matrix[i][j]) for i in range(3) for j in range(3)) < 1e-8
    x, y, z, a = camera_orientation([2, -3, 4], [0, 0, 0])
    c, s, t = math.cos(a), math.sin(a), 1-math.cos(a)
    camera = [[t*x*x+c, t*x*y-s*z, t*x*z+s*y],
              [t*x*y+s*z, t*y*y+c, t*y*z-s*x],
              [t*x*z-s*y, t*y*z+s*x, t*z*z+c]]
    forward = [-2 / math.sqrt(29), 3 / math.sqrt(29), -4 / math.sqrt(29)]
    assert max(abs(camera[i][0]-forward[i]) for i in range(3)) < 1e-10
    assert camera[2][2] > 0
    assert abs(sum(camera[i][0]*camera[i][2] for i in range(3))) < 1e-10
    print("PASS: rotations and Webots camera +X-forward/+Z-up orientation")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--assembly", default="0-EnsambleColision.SLDASM")
    cli.add_argument("--output", type=Path, default=ROOT / "webots/worlds/scara_cad_inspeccion.wbt")
    cli.add_argument("--self-check", action="store_true")
    args = cli.parse_args()
    if args.self_check:
        self_check()
        return
    source = ROOT / "cad/ensambles/informe.json"
    report = json.loads(source.read_text())
    candidates = [a for a in report["assemblies"] if Path(a["source"]).name == args.assembly]
    if len(candidates) != 1 or len(candidates[0]["configurations"]) != 1:
        cli.error("Assembly/configuration must resolve unambiguously")
    assembly = candidates[0]
    if digest(ROOT / assembly["source"]) != assembly["source_sha256"]:
        cli.error("SLDASM differs from the extracted report")
    config = assembly["configurations"][0]
    bbox = config["cached_assembly_bbox_m"]
    center = [(bbox[i] + bbox[i+3])/2 for i in range(3)]
    span = max(bbox[i+3]-bbox[i] for i in range(3))
    eye = [center[i] + v*span*1.35 for i, v in enumerate([1.25, -1.4, .95])]
    output = args.output.resolve()
    if output == ROOT / "webots/worlds/scara_uci.wbt":
        cli.error("Refusing to overwrite the dynamic scara_uci.wbt")
    entries, shapes, body_report = [], [], None
    for instance in config["instances"]:
        attrs = instance["xml_attributes"]
        if attrs["swSuppressed"] != "NO":
            continue
        matrix = instance["transform_object_to_assembly_m"]
        mesh = instance.get("accepted_stl")
        bodies = []
        mismatch = not instance.get("current_brep_cached_bbox_agree_0_05mm", False)
        disposition = "accepted_mesh_cache_bbox_differs" if mismatch else "accepted_mesh_cache_bbox_agrees"
        if instance["basename"] == "0-Torre.SLDPRT":
            bodies, body_report = tower_body_meshes(instance)
            disposition = "body_meshes_validated_zero_area_cleanup"
            geometry = "\n".join(
                "Shape { appearance PBRAppearance { baseColor 0.36 0.58 0.75 roughness 0.65 metalness 0.15 } "
                "geometry Mesh { url [ " + json.dumps(os.path.relpath(ROOT / body["path"], output.parent).replace(os.sep, "/")) +
                " ] } castShadows FALSE }" for body in bodies)
        elif mesh:
            mesh_path = ROOT / mesh["path"]
            if (not instance["local_matches_geometry_report_source"] or
                    digest(ROOT / instance["local_source"]) != instance["local_sha256"] or
                    digest(mesh_path) != mesh["sha256"]):
                cli.error("Part/STL changed since validation: " + instance["instance_name"])
            url = os.path.relpath(mesh_path, output.parent).replace(os.sep, "/")
            color = "0.85 0.49 0.12" if mismatch else "0.36 0.58 0.75"
            geometry = ("Shape { appearance PBRAppearance { baseColor " + color +
                        " roughness 0.65 metalness 0.15 } geometry Mesh { url [ " +
                        json.dumps(url) + " ] } castShadows FALSE }")
        else:
            disposition = "cached_wire_bbox_only_rejected_or_missing_mesh"
            geometry = wire_box(instance["cached_local_bbox_m"])
        label = instance["instance_name"] + " | " + disposition
        shapes.append("# " + label + "\nSolid { name " + json.dumps(label) +
                      " translation " + numbers([matrix[i][3] for i in range(3)]) +
                      " rotation " + numbers(axis_angle(matrix)) + "\nchildren [\n" + geometry + "\n] }\n")
        entries.append({"instance_name": instance["instance_name"], "basename": instance["basename"],
                        "disposition": disposition, "mesh_gate_status": instance["mesh_gate_status"],
                        "cache_bbox_difference_m": instance.get("current_brep_vs_cached_bbox_max_delta_m"),
                        "accepted_stl": mesh, "individual_body_meshes": bodies})
    world = ("#VRML_SIM R2025a utf8\n# Generated by tools/generate_cad_preview.py. Saved CAD pose, no dynamics.\n"
             "WorldInfo { info [\n\"CAD saved instances: blue=current bbox agrees; amber=cache differs; magenta=wire bounds only\"\n"
             "\"0-Torre: 3 individually validated body meshes; 8 exact-zero-area triangles removed; union not validated\"\n"
             "\"No Physics, motors or collision geometry. Saved CAD frame is not a calibrated robot zero.\"\n] coordinateSystem \"ENU\" }\n"
             "Viewpoint { orientation " + numbers(camera_orientation(eye, center)) + " position " + numbers(eye) +
             " fieldOfView 0.785398 near 0.001 }\nBackground { skyColor [ 0.94 0.96 0.98 ] }\n"
             "DirectionalLight { direction -1 -1 -2 intensity 0.8 }\n"
             "DirectionalLight { direction 1 1 -0.5 intensity 0.5 }\n" + "\n".join(shapes))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(world)
    summary = {"world": str(output.relative_to(ROOT)), "world_sha256": digest(output),
               "generator_sha256": digest(__file__), "assembly_report_sha256": digest(source),
               "assembly_source": assembly["source"], "assembly_sha256": assembly["source_sha256"],
               "saved_configuration": config["xml_attributes"]["swName"],
               "dynamic_robot_modified": False, "physics_or_motors": False,
               "preserves_saved_cad_frame": True, "instances": entries}
    if body_report:
        summary["tower_individual_bodies_report"] = body_report
    (ROOT / "cad/ensambles/inspeccion_webots.json").write_text(json.dumps(summary, indent=2) + "\n")
    counts = {}
    for entry in entries:
        counts[entry["disposition"]] = counts.get(entry["disposition"], 0) + 1
    print(json.dumps({"world": str(output), "dispositions": counts}))


if __name__ == "__main__":
    main()
