"""Cuenta dientes dibujados en STEP; una superficie lisa no permite contarlos.

Solo inspecciona los derivados validados. No modifica montaje ni transmisión.
Requiere el Python CAD de tools/requirements-cad.txt.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.generate_cad_preview import digest


def inspect(path):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError("No se pudo leer " + str(path))
    reader.SetSystemLengthUnit(1.0)
    if not reader.TransferRoots():
        raise ValueError("No se pudo transferir " + str(path))
    explorer = TopExp_Explorer(reader.OneShape(), TopAbs_FACE)
    surfaces, concentric, cuts = Counter(), Counter(), defaultdict(list)
    while explorer.More():
        surface = BRepAdaptor_Surface(TopoDS.Face(explorer.Current()), True)
        surfaces[str(surface.GetType()).split(".")[-1]] += 1
        if surface.GetType() == GeomAbs_Cylinder:
            cylinder = surface.Cylinder()
            point, axis = cylinder.Location(), cylinder.Axis().Direction()
            if abs(abs(axis.Z()) - 1) < 1e-8:
                radius = round(cylinder.Radius(), 6)
                width = round(surface.LastVParameter() - surface.FirstVParameter(), 6)
                offset = math.hypot(point.X(), point.Y())
                if offset < 1e-6:
                    concentric[(radius, width)] += 1
                else:
                    cuts[(radius, round(offset, 6), width)].append(
                        math.degrees(math.atan2(point.Y(), point.X())) % 360)
        explorer.Next()
    patterns = []
    for (radius, offset, width), angles in cuts.items():
        angles.sort()
        gaps = [(angles[(i+1) % len(angles)] - angle) % 360
                for i, angle in enumerate(angles)]
        if len(angles) >= 8 and max(gaps) - min(gaps) < 1e-6:
            patterns.append(dict(cuts=len(angles), cut_radius_mm=radius,
                centers_radius_mm=offset, width_mm=width,
                angular_gap_range_deg=[min(gaps), max(gaps)]))
    return dict(surfaces=dict(surfaces), periodic_cut_patterns=patterns,
        geometry_tooth_count=patterns[0]["cuts"] if len(patterns) == 1 else None,
        concentric_surfaces=[dict(radius_mm=r, width_mm=w, faces=n)
                             for (r, w), n in sorted(concentric.items())])


def calculate():
    report_path = ROOT / "cad/derivados/informe.json"
    conversion = json.loads(report_path.read_text())
    sources = {"tools/check_pulley_geometry.py": digest(__file__),
               "cad/derivados/informe.json": digest(report_path)}
    parts = []
    for part in conversion["parts"]:
        if not Path(part["source"]).stem.startswith("2GT_"):
            continue
        if part["status"] != "kernel_validated":
            raise ValueError("Polea sin conversión validada: " + part["source"])
        step = (report_path.parent / part["step"]["path"]).relative_to(ROOT)
        for name, expected in ((part["source"], part["source_sha256"]),
                               (str(step), part["step"]["sha256"])):
            if digest(ROOT / name) != expected:
                raise ValueError("Fuente modificada: " + name)
            sources[name] = expected
        measured = inspect(ROOT / step)
        parts.append(dict(part=Path(part["source"]).stem, step=str(step),
            **measured, limitation=(None if measured["geometry_tooth_count"] else
                "Sin ranuras periódicas contables; no se deducen dientes del nombre ni del diámetro.")))
    wrist = next(p for p in parts if p["part"] == "2GT_80Teet_40Bore")
    pattern = wrist["periodic_cut_patterns"]
    arcs = [s for s in wrist["concentric_surfaces"]
            if s["radius_mm"] == 25.2 and s["width_mm"] == 10]
    checks = dict(
        eight_pulley_types_inspected=len(parts) == 8,
        wrist_has_80_periodic_cuts=wrist["geometry_tooth_count"] == 80,
        wrist_cuts_every_4_5_degrees=(len(pattern) == 1 and all(
            abs(g - 4.5) < 1e-6 for g in pattern[0]["angular_gap_range_deg"])),
        wrist_has_80_matching_exterior_arcs=len(arcs) == 1 and arcs[0]["faces"] == 80,
        seven_other_types_do_not_model_countable_teeth=sum(
            p["geometry_tooth_count"] is None for p in parts) == 7,
        protected_inputs_unchanged=all(digest(ROOT / n) == h for n, h in sources.items()))
    return dict(created_utc=datetime.now(timezone.utc).isoformat(),
        status="geometry_inspected_only", active_model_modified=False,
        method="Count equally spaced axial cylindrical cuts, cross-check exterior arcs; STEP lengths in mm.",
        limitation="No acredita correas, fijaciones, fases, signos ni revisión mecánica oficial.",
        checks=checks, sources_sha256=sources, parts=parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "validation/pulley_geometry.json")
    args = parser.parse_args()
    report = calculate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(checks=report["checks"], parts=[
        dict(part=p["part"], teeth=p["geometry_tooth_count"]) for p in report["parts"]])))
    if not all(report["checks"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
