"""Contraste de informes 38/39 y muñeca por compuesto BREP independiente.

Ejecutar desde la copia proyecto con el Python OCP existente. No importa ni
invoca combine/placed/read_part del productor; no modifica fuentes.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import sys

from OCP.BRep import BRep_Builder
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Trsf

args = argparse.ArgumentParser(description=__doc__)
args.add_argument('--root', type=Path, default=Path.cwd())
args.add_argument('--new', type=Path)
args.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
args = args.parse_args()
ROOT = args.root.resolve()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
OLD = ROOT / 'cad/propiedades/propiedades_geometricas.json'
NEW = args.new or ROOT / 'cad/propiedades/propiedades_geometricas_39.json'
BASE = Path(__file__).resolve().parent / 'baseline_rondaA.json'
old, new = (json.loads(p.read_text()) for p in (OLD, NEW))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
TOL = dict(volume_relative=1e-9, centroid_m=1e-10, tensor_max_relative=1e-9)


def compare(actual, expected):
    scale = max(abs(x) for row in expected['inertia_per_density_m5'] for x in row)
    error = dict(volume_relative=abs(actual['volume_m3']/expected['volume_m3']-1),
                 centroid_m=math.dist(actual['centroid_m'], expected['centroid_m']),
                 tensor_max_relative=max(abs(a-b) for ar, br in zip(actual['inertia_per_density_m5'], expected['inertia_per_density_m5']) for a, b in zip(ar, br))/scale)
    assert all(math.isfinite(v) and v <= TOL[k] for k, v in error.items()), error
    return dict(error, passed=True)


def equal_metadata(actual, expected):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(equal_metadata(actual[k], expected[k]) for k in actual)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(equal_metadata(a, b) for a, b in zip(actual, expected))
    return actual == expected


def independent_wrist(instances):
    compound, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(compound)
    part_map = {p['source']: p for p in new['parts']}
    for inst in instances:
        reader = STEPControl_Reader()
        assert reader.ReadFile(str(ROOT / part_map[inst['source']]['step'])) == IFSelect_RetDone
        reader.SetSystemLengthUnit(1.0)
        assert reader.TransferRoots()
        shape = reader.OneShape()
        assert not shape.IsNull() and BRepCheck_Analyzer(shape, True).IsValid()
        pose = inst['body_from_piece']
        trsf = gp_Trsf()
        trsf.SetValues(*(pose[i][j]*(1000 if j == 3 else 1) for i in range(3) for j in range(4)))
        builder.Add(compound, BRepBuilderAPI_Transform(shape, trsf, True).Shape())
    assert BRepCheck_Analyzer(compound, True).IsValid()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(compound, props, True, True, False)
    c, matrix = props.CentreOfMass(), props.MatrixOfInertia()
    return dict(volume_m3=props.Mass()*1e-9,
                centroid_m=[c.X()*1e-3, c.Y()*1e-3, c.Z()*1e-3],
                inertia_per_density_m5=[[matrix.Value(i+1, j+1)*1e-15 for j in range(3)] for i in range(3)])


assert old['summary'] == dict(parts=50, computed_parts=49, computed_solids=51, excluded_parts=['B-ExtensorM3'], instances=38, computed_instances=38)
assert new['summary'] == dict(old['summary'], instances=39, computed_instances=39)
old_parts, new_parts = ({p['name']: p for p in r['parts']} for r in (old, new))
assert old_parts.keys() == new_parts.keys()
part_checks = []
for name, before in old_parts.items():
    after = new_parts[name]
    assert equal_metadata({k: v for k, v in after.items() if k != 'properties'}, {k: v for k, v in before.items() if k != 'properties'}), name
    if before['status'] == 'computed':
        solid_checks = [compare(a, b) for a, b in zip(after['properties']['solids'], before['properties']['solids'])]
        assert len(after['properties']['solids']) == len(before['properties']['solids'])
        part_checks.append(dict(name=name, **compare(after['properties'], before['properties']), solids=solid_checks))
    else:
        assert name == 'B-ExtensorM3' and after['errors'] == before['errors']

old_inst, new_inst = ({p['instance_name']: p for p in r['instances']} for r in (old, new))
added = sorted(new_inst.keys()-old_inst.keys())
assert not old_inst.keys()-new_inst.keys()
assert added == ['2GT_80Teet_40Bore-registro-R']
assert len(new_inst) == len(new['instances']) == 39
instance_checks = []
for name, before in old_inst.items():
    after = new_inst[name]
    assert equal_metadata({k: v for k, v in after.items() if k != 'properties'}, {k: v for k, v in before.items() if k != 'properties'}), name
    instance_checks.append(dict(name=name, **compare(after['properties'], before['properties'])))
pulley = new_inst[added[0]]
assert pulley['group'] == 'wrist' and pulley['status'] == 'computed'
assert pulley['source'] == 'Modelos3D/2GT_80Teet_40Bore.SLDPRT'
old_body, new_body = ({b['group']: b for b in r['bodies']} for r in (old, new))
body_checks = []
for group, before in old_body.items():
    if group != 'wrist':
        assert before['included_instances'] == new_body[group]['included_instances']
        body_checks.append(dict(group=group, **compare(new_body[group]['properties'], before['properties'])))
assert new_body['wrist']['included_instances'] == old_body['wrist']['included_instances']+added
assert all(not b['missing_instances'] for b in new['bodies'])
assert all(b['reference_only'] and not b['overlaps_checked'] and not b['complete_robot_body'] and b['mass_kg'] is None for b in new['bodies'])
assert all(p['mass_kg'] is None and p['density_kg_m3'] is None for p in new['parts'])

independent = []
for label, report, members in [('historical38', old, list(old_inst.values())), ('current39', new, list(new_inst.values()))]:
    wrist = [i for i in members if i['group'] == 'wrist']
    result = independent_wrist(wrist)
    expected = next(b['properties'] for b in report['bodies'] if b['group'] == 'wrist')
    independent.append(dict(version=label, instances=[i['instance_name'] for i in wrist], properties=result, **compare(result, expected)))

# El incremento de volumen es exactamente el de la instancia nueva; los tensores
# centrales no se restan como si compartieran centro. El compuesto comprueba
# también el traslado de centroide y los ejes paralelos de cada versión.
delta = new_body['wrist']['properties']['volume_m3']-old_body['wrist']['properties']['volume_m3']
assert math.isclose(delta, pulley['properties']['volume_m3'], rel_tol=TOL['volume_relative'])
csv_rows = list(csv.DictReader(NEW.with_suffix('.csv').open()))
assert len([r for r in csv_rows if r['kind'] == 'instance']) == 39
assert len([r for r in csv_rows if r['kind'] == 'instance' and r['name'] == added[0]]) == 1
assert [r['name'] for r in csv_rows if r['kind'] == 'part' and r['status'] == 'excluded'] == ['B-ExtensorM3']
assert all(r['volume_m3'] == '' for r in csv_rows if r['status'] == 'excluded')

baseline = json.loads(BASE.read_text())['files_sha256']
differences = [p for p, digest in baseline.items() if not (ROOT/p).is_file() or sha(ROOT/p) != digest]
protected = new['protected_inputs_sha256']
protected_differences = [p for p, digest in protected.items() if sha(ROOT/p) != digest]
assert not differences and not protected_differences and new['protected_inputs_unchanged']
assert sha(OLD) == baseline[str(OLD.relative_to(ROOT))]
assert sha(OLD.with_suffix('.csv')) == baseline[str(OLD.with_suffix('.csv').relative_to(ROOT))]
report = dict(created_utc=datetime.now(timezone.utc).isoformat(), passed=True,
              environment=dict(python=sys.version, executable=sys.executable, platform=platform.platform(), kernel_distribution={n: importlib.metadata.version(n) for n in ('cadquery-ocp-novtk', 'cadquery-ocp-proxy')}),
              tolerance_source='validation/cad_properties.json: independent_body_check (v=1e-9, centroid=1e-10 m, tensor=1e-9); metadata docs/PROPIEDADES_GEOMETRICAS_CAD.md step1 (abs/rel=1e-12)',
              tolerances=TOL, historical_sha256=sha(OLD), current_sha256=sha(NEW),
              historical_summary=old['summary'], current_summary=new['summary'],
              parts_and_solids_unchanged=part_checks, previous_instances_unchanged=instance_checks,
              unaffected_bodies=body_checks, added_instances=added, removed_instances=[],
              affected_group='wrist', affected_group_before=old_body['wrist'], affected_group_after=new_body['wrist'],
              unique_new_instance=pulley, volume_delta_m3=delta,
              independent_method='Releer STEP, transferir mm, transformar cada BREP con gp_Trsf (traslaciones convertidas m→mm), construir compuesto de copias y volver a integrar por BRepGProp.VolumeProperties(OnlyClosed=True, SkipShared=True, UseTriangulation=False). Sin importar calculador/productor ni usar combine/placed/read_part; misma librería CAD y mismos STEP, no equivalencia independiente con SolidWorks.',
              independent_affected_group=independent,
              exclusions=[dict(name=p['name'], errors=p['errors']) for p in new['parts'] if p['status'] == 'excluded'],
              unchanged=dict(baseline_files=len(baseline), baseline_differences=differences, protected_files=len(protected), protected_differences=protected_differences, historical_json_and_csv=True, modelos3d_files=sum(p.startswith('Modelos3D/') for p in baseline), active_physics=True, proto=True, world=True, zip=True),
              limits=new['assumptions'], suite_reexecuted=False, webots_reexecuted=False)
(OUT/'contraste.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
print(json.dumps(dict(passed=True, added=added, volume_delta_m3=delta, independent_checks=[{k:v for k,v in r.items() if k not in ('instances','properties')} for r in independent], baseline_files=len(baseline)), indent=2))
