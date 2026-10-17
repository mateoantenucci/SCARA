#!/usr/bin/env python3
"""Convert local SolidWorks parts and validate geometry before publishing STL.

Requires the separately downloaded, reviewed sldprt2step revision documented in
docs/EVALUACION_CONVERSION_CAD.md, plus tools/requirements-cad.txt. No network,
assembly placement, automatic repairs, material assignments or source edits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import runpy
import shutil
import struct
import subprocess
import sys
import tempfile
import time

REVISION = "fa954124f4f126e0c465c8f96454978ac80b812e"
UPSTREAM_TREE_SHA256 = "5abed6e10f5eea683f2b208c848c7f3f165cb22c6d414035fd00e41ac8481104"
ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools/patches/ole_ministreams.py"
GEOMETRY_PATCH = ROOT / "tools/patches/intersection_precision.py"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mesh_metrics(path):
    """Read binary STL, measuring its actual float32 geometry and triangle count."""
    raw = Path(path).read_bytes()
    count = struct.unpack_from("<I", raw, 80)[0]
    if len(raw) != 84 + 50 * count or not count:
        raise ValueError("STL is not a nonempty, complete binary STL")
    low, high = [math.inf] * 3, [-math.inf] * 3
    volume = 0.0
    edges = Counter()
    for i in range(count):
        v = struct.unpack_from("<9f", raw, 84 + 50 * i + 12)
        a, b, c = v[:3], v[3:6], v[6:]
        if not all(math.isfinite(x) for x in v):
            raise ValueError("STL contains nonfinite coordinates")
        for p in (a, b, c):
            for k in range(3):
                low[k], high[k] = min(low[k], p[k]), max(high[k], p[k])
        volume += (a[0] * (b[1]*c[2]-b[2]*c[1])
                   - a[1] * (b[0]*c[2]-b[2]*c[0])
                   + a[2] * (b[0]*c[1]-b[1]*c[0])) / 6
        for p, q in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((p, q)))] += 1
    return {"triangles": count, "bbox_m": [low, high],
            "signed_volume_m3": volume,
            "boundary_edges": sum(n == 1 for n in edges.values()),
            "nonmanifold_edges": sum(n > 2 for n in edges.values()),
            "webots_r2025a_shadow_triangle_limit": 21845,
            "within_shadow_limit": count <= 21845}


def kernel_worker(step, stl, result, linear_mm, angular):
    """Run in a bounded subprocess; never invoke ShapeFix or another repair."""
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.StlAPI import StlAPI_Writer
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_IN, TopAbs_OUT
    from OCP.TopExp import TopExp_Explorer
    from OCP.gp import gp_Pnt, gp_Trsf

    reader = STEPControl_Reader()
    if reader.ReadFile(str(step)) != IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError("OCCT could not read/transfer STEP")
    shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError("OCCT returned a null shape")
    valid = bool(BRepCheck_Analyzer(shape, True).IsValid())
    solid_volumes, solid_validity = [], []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = explorer.Current()
        solid_validity.append(bool(BRepCheck_Analyzer(solid, True).IsValid()))
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid, props)
        solid_volumes.append(props.Mass())
        explorer.Next()
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    faces = 0
    while explorer.More():
        faces += 1
        explorer.Next()
    bounds = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, bounds, False, False)
    minimum, maximum = bounds.CornerMin(), bounds.CornerMax()
    bbox = [minimum.X(), minimum.Y(), minimum.Z(), maximum.X(), maximum.Y(), maximum.Z()]
    spans = [bbox[i + 3] - bbox[i] for i in range(3)]
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    center = props.CentreOfMass()
    info = {"valid": valid, "solids": len(solid_volumes), "faces": faces,
            "solid_volumes_mm3": solid_volumes, "solid_validity": solid_validity,
            "volume_mm3": props.Mass(),
            "bbox_mm": [bbox[:3], bbox[3:]], "dimensions_mm": spans,
            "volume_centroid_mm": [center.X(), center.Y(), center.Z()],
            "explicit_repair": False, "step_importer": "OCCT STEPControl_Reader",
            "input_unit": "mm (declared in generated STEP)",
            "stl_unit": "m", "scale_mm_to_m": 0.001,
            "linear_tessellation_mm": linear_mm,
            "angular_tessellation_rad": angular, "mass_kg": None}
    errors = []
    if not valid:
        errors.append("BRepCheck_Analyzer.IsValid() is false")
    if not all(solid_validity):
        errors.append("an individual solid failed BRepCheck_Analyzer")
    if not solid_volumes or any(v <= 0 or not math.isfinite(v) for v in solid_volumes):
        errors.append("missing solid or nonpositive/nonfinite solid volume")
    if any(v <= 0 or not math.isfinite(v) for v in spans):
        errors.append("nonpositive/nonfinite bounding box")
    if step.stem == "A-Brazo":
        # Probe a section midway along the tube, away from both joint holes.
        axis = max(range(3), key=spans.__getitem__)
        transverse = [i for i in range(3) if i != axis]
        midpoint = [(bbox[i] + bbox[i + 3]) / 2 for i in range(3)]
        wall = midpoint.copy()
        wall[transverse[0]] = bbox[transverse[0]] + 0.6
        def state(point):
            classifier = BRepClass3d_SolidClassifier(shape, gp_Pnt(*point), 1e-6)
            return classifier.State()
        checks = {"dimensions_300_50_50_mm": all(
                      abs(a-b) < 0.01 for a, b in zip(sorted(spans), [50, 50, 300])),
                  "tube_center_is_void": state(midpoint) == TopAbs_OUT,
                  "wall_at_0_6_mm_is_solid": state(wall) == TopAbs_IN,
                  "volume_below_unperforated_1_2_mm_tube": 0 < props.Mass() < 70272,
                  "probe_center_mm": midpoint, "probe_wall_mm": wall}
        info["reference_checks"] = checks
        if not all(v for v in checks.values() if isinstance(v, bool)):
            errors.append("A-Brazo reference dimension/tube check failed")
    if not errors:
        transform = gp_Trsf()
        transform.SetScale(gp_Pnt(0, 0, 0), 0.001)
        meters = BRepBuilderAPI_Transform(shape, transform, True).Shape()
        mesher = BRepMesh_IncrementalMesh(meters, linear_mm * 0.001, False, angular, False)
        mesher.Perform()
        if not mesher.IsDone():
            errors.append("OCCT tessellation failed")
        else:
            writer = StlAPI_Writer()
            writer.ASCIIMode = False
            if not writer.Write(meters, str(stl)):
                errors.append("OCCT STL export failed")
            else:
                info["mesh"] = mesh_metrics(stl)
                mesh_volume = info["mesh"]["signed_volume_m3"]
                error = abs(mesh_volume / (props.Mass() * 1e-9) - 1)
                info["mesh"]["relative_volume_error"] = error
                mesh_bbox = info["mesh"]["bbox_m"][0] + info["mesh"]["bbox_m"][1]
                bbox_error = max(abs(a - b * 0.001) for a, b in zip(mesh_bbox, bbox))
                info["mesh"]["max_bbox_error_m"] = bbox_error
                if error > 0.01:
                    errors.append("STL volume differs from BREP by more than 1%")
                if bbox_error > linear_mm * 0.001 + 1e-7:
                    errors.append("STL bounding box differs from BREP beyond tessellation tolerance")
                if info["mesh"]["boundary_edges"] or info["mesh"]["nonmanifold_edges"]:
                    errors.append("STL is not a closed manifold after float32 export")
    info["errors"] = errors
    result.write_text(json.dumps(info, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter-root", type=Path)
    parser.add_argument("--source", type=Path, default=ROOT / "Modelos3D")
    parser.add_argument("--output", type=Path, default=ROOT / "cad/derivados")
    parser.add_argument("--parts", nargs="+", help="Names, with or without .SLDPRT; default: all")
    parser.add_argument("--merge", action="store_true", help="Retain unselected entries from an existing report")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--linear-mm", type=float, default=0.05)
    parser.add_argument("--angular-rad", type=float, default=0.3)
    parser.add_argument("--_worker", nargs=3, metavar=("STEP", "STL", "JSON"), help=argparse.SUPPRESS)
    parser.add_argument("--_convert-worker", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._worker:
        kernel_worker(*(Path(p) for p in args._worker), args.linear_mm, args.angular_rad)
        return 0
    if args._convert_worker:
        original, step, converter_root = args._convert_worker
        sys.path.insert(0, str(Path(converter_root).resolve()))
        runpy.run_path(str(PATCH))["install"]()
        runpy.run_path(str(GEOMETRY_PATCH))["install"]()
        from sldprt2step import run_conversion
        result = run_conversion(original, step)
        print(json.dumps(result))
        return (2 if result.get("warnings") else 0) if result.get("ok") else 1
    if args.timeout <= 0 or args.linear_mm <= 0 or args.angular_rad <= 0:
        parser.error("Timeout and tessellation tolerances must be positive")
    if not args.converter_root or not (args.converter_root / "sldprt2step.py").is_file():
        parser.error("--converter-root must point to the reviewed sldprt2step source directory")
    source = args.source.resolve()
    parts = sorted(source.glob("*.SLDPRT"))
    if args.parts:
        requested = {Path(name).stem for name in args.parts}
        parts = [p for p in parts if p.stem in requested]
        if requested != {p.stem for p in parts}:
            parser.error("Some requested parts do not exist in --source")
    if not parts:
        parser.error("No .SLDPRT parts found")
    out = args.output.resolve()
    if args.merge and (not args.parts or not (out / "informe.json").is_file()):
        parser.error("--merge requires --parts and an existing output report")
    (out / "step").mkdir(parents=True, exist_ok=True)
    (out / "stl").mkdir(exist_ok=True)
    code_hashes = {p.relative_to(args.converter_root).as_posix(): sha256(p)
                   for p in sorted(args.converter_root.rglob("*.py"))}
    tree_hash = hashlib.sha256(json.dumps(code_hashes, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    if tree_hash != UPSTREAM_TREE_SHA256:
        parser.error("Converter Python tree differs from the reviewed pinned revision")
    patch_hash = sha256(PATCH)
    geometry_patch_hash = sha256(GEOMETRY_PATCH)
    effective_hash = hashlib.sha256((tree_hash + ":" + patch_hash + ":" + geometry_patch_hash).encode()).hexdigest()
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "converter_repository": "https://github.com/BlinkingSun/sldprt2step",
                "converter_revision_declared": REVISION,
                "converter_revision_verified": True,
                "converter_source_sha256": code_hashes,
                "converter_original_tree_sha256": tree_hash,
                "converter_patch": {"id": "SCARA-CFB-MiniFAT-1", "path": str(PATCH.relative_to(ROOT)),
                                    "sha256": patch_hash, "upstream_files_modified": False},
                "converter_effective_source_sha256": effective_hash,
                "converter_geometry_patch": {"id": "SCARA-XT-Intersection-1", "path": str(GEOMETRY_PATCH.relative_to(ROOT)),
                                             "sha256": geometry_patch_hash, "intersection_target_m": 1e-9,
                                             "explicit_brep_repair": False},
                "pipeline_sha256": sha256(__file__), "python": sys.version,
                "kernel_distribution": {name: importlib.metadata.version(name) for name in
                     ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
                "assembly_placement": False, "part_count": len(parts), "parts": []}
    previous = {}
    report = out / "informe.json"
    if report.exists():
        history = out / "history"
        history.mkdir(exist_ok=True)
        archived = history / (datetime.now(timezone.utc).strftime("informe-%Y%m%dT%H%M%S%fZ-")
                              + sha256(report)[:12] + ".json")
        shutil.copyfile(report, archived)
        manifest["previous_report"] = {"path": str(archived.relative_to(out)), "sha256": sha256(archived)}
        previous = {Path(p["source"]).stem: p for p in json.loads(archived.read_text())["parts"]}
    if args.merge:
        selected = {p.stem for p in parts}
        retained = [p for name, p in previous.items() if name not in selected]
        for entry in retained:
            artifacts = [(ROOT / entry["source"], entry["source_sha256"])]
            artifacts += [(out / entry[key]["path"], entry[key]["sha256"])
                          for key in ("step", "stl") if key in entry]
            if any(sha256(path) != digest for path, digest in artifacts):
                parser.error("Retained source/artifact differs from previous report: " + entry["source"])
        manifest["parts"] = retained
        manifest["retained_from_previous_report"] = [p["source"] for p in retained]
        manifest["part_count"] = len(retained) + len(parts)
    for index, part in enumerate(parts, 1):
        start = time.monotonic()
        entry = {"source": str(part.relative_to(ROOT)) if part.is_relative_to(ROOT) else str(part),
                 "source_sha256": sha256(part), "status": "failed", "warnings": []}
        entry["converter_effective_source_sha256"] = effective_hash
        entry["pipeline_sha256"] = manifest["pipeline_sha256"]
        if part.stem in previous:
            prior = previous[part.stem]
            entry["previous_outcome"] = {"status": prior["status"], "error": prior.get("error")}
        final_step, final_stl = out / "step" / (part.stem + ".step"), out / "stl" / (part.stem + ".stl")
        try:
            with tempfile.TemporaryDirectory(prefix="conversion-", dir=out) as tmp:
                tmp = Path(tmp)
                step, stl, validation = (tmp / (part.stem + ext) for ext in (".step", ".stl", ".json"))
                conversion = subprocess.run(
                    [sys.executable, "-B", str(Path(__file__).resolve()), "--_convert-worker",
                     str(part), str(step), str(args.converter_root)], capture_output=True, text=True,
                    timeout=args.timeout, check=False)
                res = json.loads(conversion.stdout)
                entry["conversion"] = res
                entry["warnings"].extend(res.get("warnings", []))
                if conversion.returncode not in (0, 2) or not res.get("ok"):
                    raise ValueError("Source converter failed: " + str(res))
                # Generated STEP explicitly declares millimetres. Refuse unknown units.
                if "SI_UNIT(.MILLI.,.METRE.)" not in step.read_text():
                    raise ValueError("Generated STEP does not explicitly declare millimetres")
                command = [sys.executable, "-B", str(Path(__file__).resolve()), "--_worker",
                           str(step), str(stl), str(validation), "--linear-mm", str(args.linear_mm),
                           "--angular-rad", str(args.angular_rad)]
                kernel = subprocess.run(command, capture_output=True, text=True,
                                        timeout=args.timeout, check=False)
                if kernel.returncode or not validation.exists():
                    raise ValueError("Kernel worker failed: " + kernel.stderr[-3000:])
                entry["geometry"] = json.loads(validation.read_text())
                step.replace(final_step)
                entry["step"] = {"path": str(final_step.relative_to(out)), "sha256": sha256(final_step)}
                if entry["geometry"]["errors"]:
                    raise ValueError("; ".join(entry["geometry"]["errors"]))
                if entry["geometry"]["solids"] != res["solids"]:
                    raise ValueError("OCCT and converter solid counts differ")
                stl.replace(final_stl)
                entry["stl"] = {"path": str(final_stl.relative_to(out)), "sha256": sha256(final_stl)}
                entry["status"] = "kernel_validated"
                if entry["geometry"]["faces"] != res["faces"]:
                    entry["warnings"].append("OCCT and converter report different face counts")
                if not entry["geometry"]["mesh"]["within_shadow_limit"]:
                    entry["warnings"].append("STL exceeds Webots R2025a per-Mesh shadow limit")
        except subprocess.TimeoutExpired:
            entry["error"] = f"Per-stage timeout after {args.timeout}s; no STL accepted"
        except Exception as exc:
            entry["error"] = str(exc)
        entry["source_unchanged"] = sha256(part) == entry["source_sha256"]
        if not entry["source_unchanged"]:
            entry["status"] = "failed"
            entry["error"] = "Source SHA changed during conversion; no STL accepted"
        if entry["status"] != "kernel_validated":
            # Never leave an older accepted-looking STL after a failed rerun.
            final_stl.unlink(missing_ok=True)
            entry.pop("stl", None)
        entry["elapsed_seconds"] = round(time.monotonic() - start, 3)
        manifest["parts"].append(entry)
        manifest["parts"].sort(key=lambda p: p["source"])
        manifest["summary"] = dict(Counter(p["status"] for p in manifest["parts"]))
        (out / "informe.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(f"{index}/{len(parts)} {part.name}: {entry['status']} {entry.get('error', '')}", flush=True)
    return 0 if all(p["status"] == "kernel_validated" and p["source_unchanged"]
                    for p in manifest["parts"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
