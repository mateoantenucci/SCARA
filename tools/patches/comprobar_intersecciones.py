#!/usr/bin/env python3
"""Reproduce the three upstream CAD failures and check the precision patch.

Run with the CAD Python and --converter-root pointing to the reviewed revision.
All intermediate STEP/STL files live in a discarded temporary directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.convertir_cad import REVISION, UPSTREAM_TREE_SHA256, sha256

PARTS = ("B-CarretelInf", "B-CarretelSup", "Z-SoporteEfector")
BASELINE = """import json,runpy,sys
sys.path.insert(0,sys.argv[3])
runpy.run_path(sys.argv[4])['install']()
from sldprt2step import run_conversion
result=run_conversion(sys.argv[1],sys.argv[2])
print(json.dumps(result))
sys.exit((2 if result.get('warnings') else 0) if result.get('ok') else 1)
"""


def run(command, accepted=(0,)):
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if result.returncode not in accepted:
        raise RuntimeError(f"worker exited {result.returncode}: {result.stderr[-2000:]}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter-root", required=True, type=Path)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/cad_recovery_regression.json")
    args = parser.parse_args()
    converter = args.converter_root.resolve()
    code_hashes = {p.relative_to(converter).as_posix(): sha256(p)
                   for p in sorted(converter.rglob("*.py"))}
    tree_hash = hashlib.sha256(json.dumps(code_hashes, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    if tree_hash != UPSTREAM_TREE_SHA256:
        parser.error("Converter Python tree differs from the reviewed pinned revision")
    pipeline = ROOT / "tools/convertir_cad.py"
    mini = ROOT / "tools/patches/ole_ministreams.py"
    precision = ROOT / "tools/patches/intersection_precision.py"
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "converter_revision": REVISION,
        "converter_original_tree_sha256": tree_hash,
        "converter_source_sha256": code_hashes,
        "pipeline_sha256": sha256(pipeline),
        "patch_sha256": {p.name: sha256(p) for p in (mini, precision)},
        "python": sys.version,
        "kernel_distribution": {name: importlib.metadata.version(name) for name in
                                ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
        "timeout_seconds_per_worker": 90,
        "intermediate_files_retained": False,
        "parts": [],
    }
    with tempfile.TemporaryDirectory(prefix="scara-intersection-regression-") as temp:
        for name in PARTS:
            source = ROOT / "Modelos3D" / (name + ".SLDPRT")
            entry = {"source": str(source.relative_to(ROOT)),
                     "source_sha256": sha256(source)}
            for mode in ("baseline", "candidate"):
                step = Path(temp) / (name + "-" + mode + ".step")
                stl, result = step.with_suffix(".stl"), step.with_suffix(".json")
                if mode == "baseline":
                    command = [sys.executable, "-c", BASELINE, str(source), str(step),
                               str(converter), str(mini)]
                else:
                    command = [sys.executable, str(pipeline), "--_convert-worker",
                               str(source), str(step), str(converter)]
                conversion = run(command, (0, 2))
                kernel_command = [sys.executable, str(pipeline), "--_worker",
                                  str(step), str(stl), str(result)]
                kernel = run(kernel_command)
                entry[mode] = {
                    "conversion_command": command,
                    "conversion_returncode": conversion.returncode,
                    "conversion": json.loads(conversion.stdout),
                    "kernel_command": kernel_command,
                    "kernel_returncode": kernel.returncode,
                    "geometry": json.loads(result.read_text()),
                    "step_sha256": sha256(step),
                    "stl_sha256": sha256(stl) if stl.exists() else None,
                }
            old = entry["baseline"]["geometry"]
            new = entry["candidate"]["geometry"]
            bbox_error = max(abs(a - b) for old_row, new_row in
                             zip(old["bbox_mm"], new["bbox_mm"])
                             for a, b in zip(old_row, new_row))
            entry["max_bbox_change_mm"] = bbox_error
            entry["checks"] = {
                "baseline_reproduces_failure": bool(old["errors"]) and
                    (old["solids"] == 0 if name.startswith("B-") else not old["valid"]),
                "candidate_passes_original_gate": not new["errors"],
                "candidate_one_valid_solid": new["valid"] and new["solids"] == 1
                    and new["solid_validity"] == [True],
                "bbox_preserved_within_1e_6_mm": bbox_error <= 1e-6,
                "source_unchanged": sha256(source) == entry["source_sha256"],
            }
            report["parts"].append(entry)
    report["passed"] = all(all(p["checks"].values()) for p in report["parts"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(args.output),
                      "checks": {p["source"]: p["checks"] for p in report["parts"]}},
                     indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
