#!/usr/bin/env python3
"""Exporta los tres sólidos de 0-Torre por separado; no cambia el lote CAD.

Usar el entorno OCP de tools/requirements-cad.txt. Conserva cada STL crudo y
otro que descarta exclusivamente triángulos de área exactamente cero en las
coordenadas float32 exportadas. No repara BREP, suelda, mueve ni añade vértices.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import importlib.metadata
import json
import math
from pathlib import Path
import struct
import sys

from convertir_cad import mesh_metrics, sha256


ROOT = Path(__file__).resolve().parents[1]


def zero_area(vertices):
    """Comparación racional exacta de valores float32, sin tolerancia geométrica."""
    a, b, c = (tuple(Fraction(value) for value in vertices[i:i+3]) for i in (0, 3, 6))
    u, v = [y-x for x, y in zip(a, b)], [y-x for x, y in zip(a, c)]
    return all(u[i]*v[j] == u[j]*v[i] for i, j in ((0, 1), (1, 2), (2, 0)))


def remove_zero_area(raw_path, destination):
    raw = raw_path.read_bytes()
    count = struct.unpack_from("<I", raw, 80)[0]
    if len(raw) != 84 + 50*count:
        raise ValueError("STL binario incompleto")
    kept, removed = [], []
    for index in range(count):
        record = raw[84 + 50*index:134 + 50*index]
        vertices = struct.unpack_from("<9f", record, 12)
        if not all(math.isfinite(value) for value in vertices):
            raise ValueError("Coordenadas STL no finitas")
        if zero_area(vertices):
            removed.append(index)
        else:
            kept.append(record)
    # Los registros conservados (incluidos normales/vértices) son idénticos byte a byte.
    destination.write_bytes(raw[:80] + struct.pack("<I", len(kept)) + b"".join(kept))
    return {"method": "exact_rational_cross_product_of_exported_float32_vertices",
            "removed_triangle_indices_zero_based": removed,
            "removed_triangles": len(removed), "removed_positive_area_triangles": 0,
            "retained_triangle_records_byte_identical": True,
            "geometric_oriented_volume_exactly_preserved": True,
            "vertices_moved_or_welded": 0, "triangles_added": 0}


def export(step, source, batch_report, output, linear_mm, angular):
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.Bnd import Bnd_Box
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.StlAPI import StlAPI_Writer
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.gp import gp_Pnt, gp_Trsf

    protected = {path: sha256(path) for path in (step, source, batch_report)}
    batch = json.loads(batch_report.read_text())
    parent_entry = next(entry for entry in batch["parts"]
                        if Path(entry["source"]).stem == "0-Torre")
    if (parent_entry["source_sha256"] != protected[source]
            or parent_entry["step"]["sha256"] != protected[step]):
        raise ValueError("Original o STEP no coincide con el informe del lote")
    if "SI_UNIT(.MILLI.,.METRE.)" not in step.read_text():
        raise ValueError("STEP sin declaración de milímetros")
    reader = STEPControl_Reader()
    if reader.ReadFile(str(step)) != IFSelect_RetDone or not reader.TransferRoots():
        raise ValueError("OCCT no pudo leer/transferir STEP")
    shape = reader.OneShape()
    if shape.IsNull() or not BRepCheck_Analyzer(shape, True).IsValid():
        raise ValueError("BREP global nulo o inválido")
    solids = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids.append(explorer.Current())
        explorer.Next()
    if len(solids) != 3:
        raise ValueError(f"Se esperaban tres sólidos, se obtuvieron {len(solids)}")
    for directory in (output / "crudos", output / "stl"):
        directory.mkdir(parents=True, exist_ok=True)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(),
              "purpose": "visualizacion de tres cuerpos de 0-Torre en su marco de pieza",
              "source": {"path": str(source.relative_to(ROOT)), "sha256": protected[source]},
              "step": {"path": str(step.relative_to(ROOT)), "sha256": protected[step]},
              "batch_report_sha256_before": protected[batch_report],
              "batch_result_unchanged": batch["summary"],
              "converter_revision": "fa954124f4f126e0c465c8f96454978ac80b812e",
              "source_conversion_warnings": parent_entry["warnings"],
              "script_sha256": sha256(__file__), "python": sys.version,
              "kernel_distribution": {name: importlib.metadata.version(name) for name in
                   ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
              "scale_mm_to_m": 0.001, "origin_or_orientation_changed": False,
              "explicit_brep_repair": False, "linear_tessellation_mm": linear_mm,
              "angular_tessellation_rad": angular, "mass_kg": None,
              "assembly_placement": False, "global_mesh_manifold_validated": False,
              "equivalence_to_original_solidworks_independently_verified": False,
              "bodies": []}
    for index, solid in enumerate(solids, 1):
        props, bounds = GProp_GProps(), Bnd_Box()
        BRepGProp.VolumeProperties_s(solid, props)
        BRepBndLib.AddOptimal_s(solid, bounds, False, False)
        lo, hi, center = bounds.CornerMin(), bounds.CornerMax(), props.CentreOfMass()
        bbox = [[lo.X(), lo.Y(), lo.Z()], [hi.X(), hi.Y(), hi.Z()]]
        valid, volume = bool(BRepCheck_Analyzer(solid, True).IsValid()), props.Mass()
        if not valid or not math.isfinite(volume) or volume <= 0:
            raise ValueError(f"Sólido {index} inválido o sin volumen positivo")
        transform = gp_Trsf()
        transform.SetScale(gp_Pnt(0, 0, 0), 0.001)
        meters = BRepBuilderAPI_Transform(solid, transform, True).Shape()
        mesher = BRepMesh_IncrementalMesh(meters, linear_mm*0.001, False, angular, False)
        mesher.Perform()
        if not mesher.IsDone():
            raise ValueError(f"Falló teselación del sólido {index}")
        raw = output / "crudos" / f"0-Torre-cuerpo-{index:02}.stl"
        cleaned = output / "stl" / raw.name
        writer = StlAPI_Writer()
        writer.ASCIIMode = False
        if not writer.Write(meters, str(raw)):
            raise ValueError(f"Falló exportación del sólido {index}")
        raw_metrics = mesh_metrics(raw)
        filtering = remove_zero_area(raw, cleaned)
        metrics = mesh_metrics(cleaned)
        filtering["bbox_float32_identical"] = raw_metrics["bbox_m"] == metrics["bbox_m"]
        filtering["signed_volume_float64_identical"] = (
            raw_metrics["signed_volume_m3"] == metrics["signed_volume_m3"])
        filtering["signed_volume_float64_difference_m3"] = (
            metrics["signed_volume_m3"] - raw_metrics["signed_volume_m3"])
        metrics["relative_volume_error_to_brep"] = abs(metrics["signed_volume_m3"]/(volume*1e-9)-1)
        metrics["max_bbox_error_m"] = max(abs(a-b*0.001)
            for mesh_side, cad_side in zip(metrics["bbox_m"], bbox)
            for a, b in zip(mesh_side, cad_side))
        errors = []
        if metrics["boundary_edges"] or metrics["nonmanifold_edges"]:
            errors.append("STL individual no cerrado/manifold")
        if metrics["relative_volume_error_to_brep"] > 0.01:
            errors.append("Volumen STL difiere más del 1% del sólido BREP")
        if metrics["max_bbox_error_m"] > linear_mm*0.001 + 1e-7:
            errors.append("Bounding box STL excede tolerancia de teselación")
        if not filtering["bbox_float32_identical"]:
            errors.append("El filtrado cambió bounding box")
        report["bodies"].append({"index": index, "brep_valid": valid,
            "volume_mm3": volume, "bbox_mm": bbox,
            "volume_centroid_mm": [center.X(), center.Y(), center.Z()],
            "raw_stl": {"path": str(raw.relative_to(output)), "sha256": sha256(raw),
                        "metrics": raw_metrics},
            "zero_area_filter": filtering,
            "derived_stl": {"path": str(cleaned.relative_to(output)), "sha256": sha256(cleaned),
                            "metrics": metrics},
            "status": "individual_mesh_validated" if not errors else "rejected", "errors": errors})
    report["protected_inputs_unchanged"] = all(sha256(path) == digest for path, digest in protected.items())
    report["all_individual_meshes_validated"] = all(not body["errors"] for body in report["bodies"])
    (output / "informe.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "individual_meshes_validated": report["all_individual_meshes_validated"],
                      "removed_triangles": [body["zero_area_filter"]["removed_triangles"] for body in report["bodies"]]}))
    return 0 if report["protected_inputs_unchanged"] and report["all_individual_meshes_validated"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "cad/derivados/torre_por_cuerpos")
    parser.add_argument("--linear-mm", type=float, default=0.05)
    parser.add_argument("--angular-rad", type=float, default=0.3)
    args = parser.parse_args()
    if not all(math.isfinite(value) and value > 0 for value in (args.linear_mm, args.angular_rad)):
        parser.error("Tolerancias positivas y finitas requeridas")
    output = args.output.resolve()
    if output == ROOT / "cad/derivados" or output == ROOT / "cad/derivados/stl":
        parser.error("Usar salida aislada del lote principal")
    return export(ROOT / "cad/derivados/step/0-Torre.step", ROOT / "Modelos3D/0-Torre.SLDPRT",
                  ROOT / "cad/derivados/informe.json", output, args.linear_mm, args.angular_rad)


if __name__ == "__main__":
    raise SystemExit(main())
