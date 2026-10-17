#!/usr/bin/env python3
"""Precalcula propiedades volumétricas BREP sin asignar materiales ni tocar Webots.

Usar el Python OCP de tools/requirements-cad.txt. Salidas: JSON trazable y CSV
explorable. Jc = integral((r.r) identidad - r r^T) dV, en m^5; I = rho Jc.
Las sumas son aditivas, sin unión booleana ni validación de interferencias.
"""

import argparse
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.frames import transform_point
from tools.convertir_cad import sha256
from tools.integrate_cad import derive


def properties(volume, center, inertia):
    values = [volume, *center, *(v for row in inertia for v in row)]
    if not all(math.isfinite(v) for v in values) or volume <= 0:
        raise ValueError("Propiedades no finitas o volumen no positivo")
    scale = max(abs(v) for row in inertia for v in row)
    if scale <= 0 or any(abs(inertia[i][j]-inertia[j][i]) > scale*1e-9
                         for i in range(3) for j in range(3)):
        raise ValueError("Tensor nulo o no simétrico")
    # Sylvester en escala normalizada: inercia y segundo momento positivos.
    for matrix in (inertia, [[(sum(inertia[k][k] for k in range(3))/2 if i == j else 0)
                              - inertia[i][j] for j in range(3)] for i in range(3)]):
        a = [[v/scale for v in row] for row in matrix]
        det = (a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
               - a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
               + a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
        if min(a[0][0], a[0][0]*a[1][1]-a[0][1]*a[1][0], det) <= 0:
            raise ValueError("Tensor incompatible con un volumen tridimensional positivo")
    return dict(volume_m3=volume, centroid_m=center, inertia_per_density_m5=inertia)


def combine(items):
    """Suma a densidad común: centro volumétrico y tensor central, no unión."""
    volume = math.fsum(p["volume_m3"] for p in items)
    if volume <= 0:
        raise ValueError("No hay volumen para agregar")
    center = [math.fsum(p["volume_m3"]*p["centroid_m"][i] for p in items)/volume for i in range(3)]
    inertia = [[0.0]*3 for _ in range(3)]
    for p in items:
        d = [p["centroid_m"][i]-center[i] for i in range(3)]
        norm2 = sum(v*v for v in d)
        for i in range(3):
            for j in range(3):
                inertia[i][j] += p["inertia_per_density_m5"][i][j] + p["volume_m3"] * (
                    (norm2 if i == j else 0)-d[i]*d[j])
    return properties(volume, center, inertia)


def placed(p, transform):
    rotation = [row[:3] for row in transform[:3]]
    if (len(transform) != 4 or transform[3] != [0, 0, 0, 1]
            or any(abs(sum(rotation[k][i]*rotation[k][j] for k in range(3))-(i == j)) > 1e-8
                   for i in range(3) for j in range(3))):
        raise ValueError("Colocación no rígida")
    inertia = [[sum(rotation[i][a]*p["inertia_per_density_m5"][a][b]*rotation[j][b]
                    for a in range(3) for b in range(3)) for j in range(3)] for i in range(3)]
    return properties(p["volume_m3"], transform_point(transform, p["centroid_m"]), inertia)


def solid_properties(shape):
    from OCP.BRep import BRep_Tool
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer

    if not BRepCheck_Analyzer(shape, True).IsValid():
        raise ValueError("BREP inválido")
    shells = TopExp_Explorer(shape, TopAbs_SHELL)
    count = 0
    while shells.More():
        if not BRep_Tool.IsClosed_s(shells.Current()):
            raise ValueError("Shell no cerrado")
        count += 1
        shells.Next()
    if not count:
        raise ValueError("Sólido sin shell cerrado")
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, True, True, False)
    c, matrix = props.CentreOfMass(), props.MatrixOfInertia()
    # mm^3 -> m^3; mm -> m; mm^5 -> m^5. No es una masa en kg.
    return properties(props.Mass()*1e-9, [c.X()*1e-3, c.Y()*1e-3, c.Z()*1e-3],
                      [[matrix.Value(i+1, j+1)*1e-15 for j in range(3)] for i in range(3)])


def read_part(path):
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError("No se pudo leer STEP")
    reader.SetSystemLengthUnit(1.0)  # OCCT: transferencia explícita a milímetros.
    if not reader.TransferRoots():
        raise ValueError("No se pudo transferir STEP")
    shape = reader.OneShape()
    if shape.IsNull() or not BRepCheck_Analyzer(shape, True).IsValid():
        raise ValueError("BREP global nulo o inválido")
    explorer, solids, solid_faces = TopExp_Explorer(shape, TopAbs_SOLID), [], 0
    while explorer.More():
        solid = explorer.Current()
        solids.append(dict(index=len(solids)+1, **solid_properties(solid)))
        faces = TopExp_Explorer(solid, TopAbs_FACE)
        while faces.More():
            solid_faces += 1
            faces.Next()
        explorer.Next()
    if not solids:
        raise ValueError("Cero sólidos: las caras sueltas no definen volumen admisible")
    faces, total_faces = TopExp_Explorer(shape, TopAbs_FACE), 0
    while faces.More():
        total_faces += 1
        faces.Next()
    if total_faces != solid_faces:
        raise ValueError("Hay caras fuera de los sólidos; no se omiten silenciosamente")
    return dict(solids=solids, **combine(solids))


def write_csv(report, path):
    columns = ["kind", "name", "group", "status", "volume_m3", "cx_m", "cy_m", "cz_m",
               "Jxx_m5", "Jyy_m5", "Jzz_m5", "Jxy_m5", "Jxz_m5", "Jyz_m5", "notes"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        rows = [("part", p["name"], "", p) for p in report["parts"]]
        rows += [("solid", p["name"]+f"/solid-{s['index']}", "", dict(s, status="computed"))
                 for p in report["parts"] for s in p.get("properties", {}).get("solids", [])]
        rows += [("instance", p["instance_name"], p["group"], p) for p in report["instances"]]
        rows += [("body", p["group"], p["group"], dict(p, status="partial_additive_reference"))
                 for p in report["bodies"]]
        for kind, name, group, item in rows:
            p = item.get("properties", item if kind == "solid" else {})
            row = dict(kind=kind, name=name, group=group, status=item["status"],
                       notes="; ".join(item.get("errors", []) + item.get("missing_instances", [])))
            if p:
                row.update(volume_m3=p["volume_m3"], **dict(zip(columns[5:8], p["centroid_m"])))
                inertia = p["inertia_per_density_m5"]
                row.update(zip(columns[8:14], [inertia[i][j] for i,j in
                                               ((0,0),(1,1),(2,2),(0,1),(0,2),(1,2))]))
            writer.writerow(row)


def calculate():
    batch_path = ROOT/"cad/derivados/informe.json"
    integration_path = ROOT/"cad/ensambles/integracion_articulada.json"
    batch, integration = json.loads(batch_path.read_text()), json.loads(integration_path.read_text())
    def agrees(a, b):
        # Python 3.9/3.12 difieren en el último bit de algunos sumatorios.
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(agrees(a[k], b[k]) for k in a)
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(agrees(x, y) for x,y in zip(a,b))
        return a == b
    if not agrees(derive(), integration):
        raise ValueError("Integración CAD desactualizada; revisar antes de calcular propiedades")
    protected_paths = [ROOT/"config/scara.json", ROOT/"webots/protos/SCARA.proto",
                       ROOT/"webots/worlds/scara.wbt", batch_path, integration_path,
                       Path(__file__), ROOT/"tools/requirements-cad.txt",
                       ROOT/"scara/frames.py", ROOT/"tools/convertir_cad.py"]
    protected_paths += [ROOT/p for p in integration["sources"]]
    protected_paths += list((ROOT/"Modelos3D").iterdir())
    protected_paths += [ROOT/"cad/derivados"/p["step"]["path"] for p in batch["parts"]]
    protected = {str(p.relative_to(ROOT)): sha256(p) for p in set(protected_paths) if p.is_file()}
    parts = []
    for source in batch["parts"]:
        step = ROOT/"cad/derivados"/source["step"]["path"]
        if (sha256(ROOT/source["source"]) != source["source_sha256"]
                or sha256(step) != source["step"]["sha256"]):
            raise ValueError("Original/STEP distinto del lote: " + source["source"])
        part = dict(name=Path(source["source"]).stem, source=source["source"],
                    source_sha256=source["source_sha256"], step=str(step.relative_to(ROOT)),
                    step_sha256=source["step"]["sha256"], batch_mesh_status=source["status"],
                    conversion_warnings=source["warnings"], density_kg_m3=None, mass_kg=None,
                    material_unspecified_label_utf16le_present=(
                        "Material <sin especificar>".encode("utf-16-le") in (ROOT/source["source"]).read_bytes()),
                    status="excluded", errors=[])
        try:
            p = read_part(step)
        except ValueError as error:
            part["errors"].append(str(error))
        else:
            # Contraste con el cálculo volumétrico previo, independiente del STL.
            previous = source["geometry"]
            if (abs(p["volume_m3"]/(previous["volume_mm3"]*1e-9)-1) > 1e-6
                    or math.dist(p["centroid_m"], [v*1e-3 for v in previous["volume_centroid_mm"]]) > 1e-8):
                raise ValueError("Propiedades difieren del informe BREP previo: " + part["name"])
            part.update(status="computed", properties=p)
        parts.append(part)
        print(part["name"] + ": " + part["status"], flush=True)
    by_name, instances = {p["name"]: p for p in parts}, []
    for source in integration["instances"]:
        part = by_name[Path(source["source"]).stem]
        entry = {k: source[k] for k in ("instance_name", "source", "source_sha256", "group",
                 "body_from_piece", "disposition", "attachment_status")}
        entry.update(status=part["status"], errors=part["errors"])
        if part["status"] == "computed":
            entry["properties"] = placed(part["properties"], source["body_from_piece"])
        instances.append(entry)
    bodies = []
    for group in integration["body_defs"]:
        members = [p for p in instances if p["group"] == group]
        represented = [p for p in members if "properties" in p]
        bodies.append(dict(group=group, included_instances=[p["instance_name"] for p in represented],
            missing_instances=[p["instance_name"] for p in members if "properties" not in p],
            properties=combine([p["properties"] for p in represented]),
            reference_only=True, uniform_common_density_required=True,
            overlaps_checked=False, complete_robot_body=False, mass_kg=None))
    unchanged = all(sha256(ROOT/p) == digest for p,digest in protected.items())
    if not unchanged:
        raise ValueError("Un archivo protegido cambió durante el cálculo")
    return dict(created_utc=datetime.now(timezone.utc).isoformat(), schema_version=1,
        status="geometric_precalculation_not_applied_to_physics", python=sys.version,
        kernel_distribution={name: importlib.metadata.version(name) for name in
                             ("cadquery-ocp-novtk", "cadquery-ocp-proxy")},
        method="OCCT BRepGProp.VolumeProperties: OnlyClosed=True, SkipShared=True, UseTriangulation=False; per-solid addition",
        units=dict(step_transfer="mm", volume="m^3", centroid="m", inertia_per_density="m^5",
                   density_when_known="kg/m^3", resulting_inertia="kg*m^2"),
        tensor_convention="central; axes parallel to stated frame; off-diagonal = -integral(x_i*x_j dV)",
        frames=dict(parts="piece local", solids="piece local", instances="body local", bodies="body local"),
        assumptions=["No material or density assigned", "Additive volumes, not boolean unions",
                     "No overlap correction or complete assembly claim",
                     "Commercial internals and printed infill not inferred from envelope",
                     "Converted BREP validity does not certify equivalence to SolidWorks"],
        summary=dict(parts=len(parts), computed_parts=sum(p["status"] == "computed" for p in parts),
                     computed_solids=sum(len(p.get("properties", {}).get("solids", [])) for p in parts),
                     excluded_parts=[p["name"] for p in parts if p["status"] == "excluded"],
                     instances=len(instances), computed_instances=sum("properties" in p for p in instances)),
        protected_inputs_sha256=dict(sorted(protected.items())), protected_inputs_unchanged=unchanged,
        parts=parts, instances=instances, bodies=bodies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"cad/propiedades")
    args = parser.parse_args()
    report = calculate()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/"propiedades_geometricas.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    write_csv(report, args.output/"propiedades_geometricas.csv")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
