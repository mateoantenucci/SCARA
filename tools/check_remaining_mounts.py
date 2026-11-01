#!/usr/bin/env python3
"""Contrasta las poses retenidas y M3; no reconstruye mates ni cambia el CAD.

Requiere el Python de tools/requirements-cad.txt. El STEP inválido del extensor
solo permite comparar superficies diagnósticas, nunca aceptar su volumen/malla.
"""

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scara.frames import multiply, rigid_inverse, transform_point
from tools.check_collisions import sha256
from tools.check_self_collisions import kernel, self_check


def calculate():
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    dependencies = ('tools/check_remaining_mounts.py', 'tools/check_self_collisions.py',
        'tools/check_collisions.py', 'scara/frames.py', 'config/scara.json',
        'config/cad_integration.json', 'tools/integrate_cad.py', 'tools/registrar_subensambles.py',
        'cad/derivados/informe.json', 'cad/ensambles/informe.json',
        'cad/ensambles/registro_subensambles.json', 'cad/ensambles/integracion_articulada.json',
        'webots/protos/SCARA.proto', 'webots/worlds/scara_uci.wbt', 'tools/requirements-cad.txt',
        'Modelos3D/B-ExtensorM3.PDF', 'Modelos3D/A-Eje.PDF', 'Modelos3D/A-EjeInterior.PDF')
    sources = {n: sha256(ROOT/n) for n in dependencies}

    def verify(path, expected):
        if sha256(ROOT/path) != expected:
            raise ValueError('Fuente distinta del informe: ' + path)
        sources[path] = expected

    raw = json.loads((ROOT/'cad/ensambles/informe.json').read_text())
    registry = json.loads((ROOT/'cad/ensambles/registro_subensambles.json').read_text())
    conversion = json.loads((ROOT/'cad/derivados/informe.json').read_text())
    manifest = json.loads((ROOT/'cad/ensambles/integracion_articulada.json').read_text())
    if (registry['assembly_report_sha256'] != sources['cad/ensambles/informe.json']
            or registry['script_sha256'] != sources['tools/registrar_subensambles.py']
            or raw['geometry_report_sha256'] != sources['cad/derivados/informe.json']
            or not registry['protected_inputs_unchanged']):
        raise ValueError('Registro de subensambles o geometría desactualizado')
    for path, expected in manifest['sources'].items():
        verify(path, expected)
    assemblies = {}
    for a in raw['assemblies']:
        verify(a['source'], a['source_sha256'])
        assemblies[Path(a['source']).stem] = {p['instance_name']: p
            for p in a['configurations'][0]['instances'] if p['xml_attributes']['swSuppressed'] == 'NO'}
    parts = {p['instance_name']: p for p in manifest['instances']}
    native = {Path(p['source']).stem: p for p in conversion['parts']}
    box, placed, bounds, intersection = kernel()
    shapes, surfaces = {}, {}

    def read(name, diagnostic=False):
        p = native[name]
        if p['status'] != 'kernel_validated' and not diagnostic:
            raise ValueError('Geometría no aceptada: ' + name)
        if name not in shapes:
            path = 'cad/derivados/' + p['step']['path']
            verify(p['source'], p['source_sha256'])
            verify(path, p['step']['sha256'])
            reader = STEPControl_Reader()
            if reader.ReadFile(str(ROOT/path)) != IFSelect_RetDone:
                raise ValueError('STEP ilegible: ' + name)
            reader.SetSystemLengthUnit(1.0)
            if not reader.TransferRoots():
                raise ValueError('STEP sin raíz: ' + name)
            shapes[name] = reader.OneShape()
            cylinders = surfaces[name] = []
            it = TopExp_Explorer(shapes[name], TopAbs_FACE)
            while it.More():
                s = BRepAdaptor_Surface(TopoDS.Face(it.Current()), True)
                if s.GetType() == GeomAbs_Cylinder:
                    c = s.Cylinder()
                    o, a = c.Location(), c.Axis().Direction()
                    cylinders.append(dict(radius_mm=c.Radius(),
                        origin_mm=[o.Coord(k) for k in (1, 2, 3)],
                        axis=[a.Coord(k) for k in (1, 2, 3)],
                        ends_mm=[[o.Coord(k)+a.Coord(k)*v for k in (1, 2, 3)]
                                 for v in (s.FirstVParameter(), s.LastVParameter())]))
                it.Next()
        return shapes[name]

    def cylinder(name, radius, diagnostic=False):
        read(name, diagnostic)
        return next(c for c in surfaces[name] if abs(c['radius_mm']-radius) < 1e-6
                    and math.hypot(*c['origin_mm'][:2]) < 1e-6
                    and abs(abs(c['axis'][2])-1) < 1e-8)

    def point(matrix, p):
        return [v*1000 for v in transform_point(matrix, [v/1000 for v in p])]

    def span(matrix, c):
        ends = [point(matrix, p) for p in c['ends_mm']]
        if math.dist(ends[0][:2], ends[1][:2]) > 1e-6:
            raise ValueError('El eje no es paralelo al Z de referencia')
        return sorted(p[2] for p in ends)

    def overlap(a, b):
        return max(0, min(a[1], b[1])-max(a[0], b[0]))

    retained = []
    for a in registry['ambiguous_additions_withheld']:
        rows = []
        for c in a['candidates']:
            name = Path(c['basename']).stem
            rows.append(dict(assembly=c['source_assembly'], instance=c['source_instance'],
                cache_stamp=c['source_cache_stamp'], current_bbox_agrees=c['current_bbox_agrees_with_cached'],
                saved_global_bbox_mm=bounds(placed(read(name), c['transform_part_to_global_m'])),
                transform_part_to_saved_global=c['transform_part_to_global_m']))
        retained.append(dict(part=Path(a['basename']).stem, reason=a['reason'], candidates=rows))

    pulley = next(a for a in registry['ambiguous_additions_withheld']
                  if a['basename'] == '2GT_80Teet_40Bore.SLDPRT')
    support = parts['Z-BujeExterior-1']
    wrist = []
    for c in pulley['candidates']:
        relative = multiply(rigid_inverse(support['saved_object_to_assembly']), c['transform_part_to_global_m'])
        contacts = []
        for name in ('Z-BujeExterior-1', 'Z-Cuerpo-1', 'R-Bancada-1', 'R-ContraBancada-1',
                     'Z-6907-2RS-registro-1', 'Z-6907-2RS-registro-2'):
            p = parts[name]
            rel = multiply(rigid_inverse(p['saved_object_to_assembly']), c['transform_part_to_global_m'])
            contacts.append(dict(part=name, intersection_volume_mm3=intersection(
                read(Path(p['source']).stem), placed(read('2GT_80Teet_40Bore'), rel))))
        bore = span(relative, cylinder('2GT_80Teet_40Bore', 20))
        seat = span([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                    cylinder('Z-BujeExterior', 20))
        wrist.append(dict(source_assembly=c['source_assembly'], axis_gap_mm=math.hypot(*point(relative, [0, 0, 0])[:2]),
            pulley_bore_diameter_mm=40, bushing_seat_diameter_mm=40,
            bore_on_bushing_Z_mm=bore, seat_on_bushing_Z_mm=seat,
            shoulder_offset_mm=bore[0]-seat[0], engagement_mm=overlap(bore, seat),
            contacts=contacts))

    b = assemblies['B-EnsambleAntebrazo']
    motor = b['NEMA17-1']['transform_object_to_assembly_m']
    pinion = multiply(rigid_inverse(motor), b['2GT_20Teet_5Bore-1']['transform_object_to_assembly_m'])
    ext = multiply(rigid_inverse(motor), b['B-ExtensorM3-1']['transform_object_to_assembly_m'])
    identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    shaft_span = span(identity, cylinder('NEMA17', 2.5))
    pinion_span = span(pinion, cylinder('2GT_20Teet_5Bore', 2.5))
    ext_bore = span(ext, cylinder('B-ExtensorM3', 2.5, True))
    ext_shaft = span(ext, cylinder('B-ExtensorM3', 4, True))
    m3 = dict(reference='NEMA17 local Z in B-EnsambleAntebrazo; current STEP geometry',
        motor_shaft_span_mm=shaft_span, pinion_bore_span_mm=pinion_span,
        direct_motor_pinion_engagement_mm=overlap(shaft_span, pinion_span),
        extension_input_bore_span_mm=ext_bore, motor_extension_engagement_mm=overlap(shaft_span, ext_bore),
        extension_output_span_mm=ext_shaft, extension_output_diameter_mm=8, pinion_bore_diameter_mm=5,
        mismatched_axial_overlap_mm=overlap(ext_shaft, pinion_span),
        extension_status=native['B-ExtensorM3']['status'],
        limitation='Extensor STEP inválido: superficies solo diagnósticas. El plano original también indica salida Ø8 y entrada Ø5. No se calcula su intersección/masa.')

    vertical = []
    global_parts = assemblies['0-EnsambleColision']
    for name in ('Z-EnsambleEfector', 'Z-EnsambleM4'):
        common = []
        for p in assemblies[name].values():
            matches = [g for g in global_parts.values() if p['basename'] == g['basename']]
            for g in matches:
                common.append(dict(part=p['basename'], source_instance=p['instance_name'], global_instance=g['instance_name'],
                    source_cache_stamp=p['model_attributes']['swLastModifiedStamp'],
                    global_cache_stamp=g['model_attributes']['swLastModifiedStamp']))
        vertical.append(dict(assembly=name, valid_registration_candidates_to_global=len(
            registry['registrations'][name+' -> 0-EnsambleColision']), shared_revisions=common))
    accepted = next(p for p in wrist if p['source_assembly'] == 'R-EnsambleRotacion')
    rejected = next(p for p in wrist if p['source_assembly'] == 'B-EnsambleAntebrazo')
    chosen = parts.get('2GT_80Teet_40Bore-registro-R')
    checks = self_check(box, bounds, intersection) + [
        dict(name='five_retained_part_types_measured', passed=len(retained) == 5),
        dict(name='wrist_R_seated_on_shoulder_full_12mm_engagement', passed=(accepted['axis_gap_mm'] < 1e-6
            and abs(accepted['shoulder_offset_mm']) < 1e-6 and abs(accepted['engagement_mm']-12) < 1e-6)),
        dict(name='wrist_R_no_positive_volume_against_six_neighbors', passed=all(
            p['intersection_volume_mm3'] < .001 for p in accepted['contacts'])),
        dict(name='wrist_B_rejected_by_bushing_shoulder_interference', passed=any(
            p['part'] == 'Z-BujeExterior-1' and p['intersection_volume_mm3'] > 400 for p in rejected['contacts'])),
        dict(name='selected_wrist_pulley_follows_wrist', passed=chosen is not None and chosen['group'] == 'wrist'),
        dict(name='M3_extension_and_pinion_diameters_incompatible', passed=(m3['extension_output_diameter_mm'] >
            m3['pinion_bore_diameter_mm'] and m3['mismatched_axial_overlap_mm'] > 16)),
        dict(name='vertical_has_no_identity_preserving_global_registration', passed=all(
            p['valid_registration_candidates_to_global'] == 0 for p in vertical)),
        dict(name='protected_inputs_unchanged', passed=all(sha256(ROOT/n) == d for n, d in sources.items()))]
    return dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
        status='remaining_mounts_reviewed_with_explicit_wrist_choice', active_instances=len(parts),
        environment=dict(platform=platform.platform(), python=sys.version,
            kernel=importlib.metadata.version('cadquery-ocp-novtk')),
        method='STEP mm, saved transforms m; exact cylindrical spans and BREP Common. No physical hardware trial.',
        checks=checks, sources_sha256=sources, retained_candidates=retained,
        wrist_pulley_comparison=wrist, M3=m3, vertical=vertical,
        drawing_contrasts=[dict(part='A-Eje', drawing_length_mm=110, STEP_length_mm=140,
                drawing='Modelos3D/A-Eje.PDF', page=1),
            dict(part='A-EjeInterior', drawing_length_mm=160, STEP_length_mm=190,
                drawing='Modelos3D/A-EjeInterior.PDF', page=1),
            dict(part='B-ExtensorM3', drawing_input_diameter_mm=5, drawing_output_diameter_mm=8,
                drawing='Modelos3D/B-ExtensorM3.PDF', page=1)],
        limitations=['Saved angular phase and mechanical fastening are provisional; diameter fit is not torque transmission.',
            'Three motor pinions and inner transmission require separate rotor coordinates; no belt path or sign assumed.',
            'No new mass/inertia, motor properties, homing or full workspace collision claim.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'validation/remaining_mounts.json')
    args = parser.parse_args()
    report = calculate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(output=str(args.output), instances=report['active_instances'], checks=report['checks'])))
    if not all(c['passed'] for c in report['checks']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
