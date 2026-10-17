"""Ensayo nativo de llegada y sostén en límites de J4; recarga y mueve el mundo.

Solo banco Webots aislado. Guarda muestras incluso ante una llegada inestable.
No usa sensores simulados como realimentación de control ni modifica topes.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from check_simulation import Bench


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=19011)
    parser.add_argument('--snapshot-root',type=Path,required=True)
    parser.add_argument('--webots-version',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--targets',type=float,nargs='+',default=[.12,.119,0])
    parser.add_argument('--pose',choices=('folded','initial'),default='folded')
    parser.add_argument('--payload',type=float,default=0)
    args = parser.parse_args()
    paths = ('config/scara.json','scara/runtime.py','scara/dynamics.py','scara/collisions.py',
             'scara/kinematics.py','scara/frames.py','scara/transport.py',
             'cad/ensambles/integracion_articulada.json','webots/protos/SCARA.proto',
             'webots/worlds/scara.wbt','webots/controllers/scara_bridge/scara_bridge.py')
    sources = {p:hashlib.sha256((args.snapshot_root/p).read_bytes()).hexdigest() for p in paths}
    report = dict(started_utc=datetime.now(timezone.utc).isoformat(),status='running',
        webots_version=args.webots_version,snapshot_root=str(args.snapshot_root),
        executed_sources_sha256=sources,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        bench_sha256=hashlib.sha256((ROOT/'tools/check_simulation.py').read_bytes()).hexdigest(),
        tolerance_m=.0005,settling_s=1.0,observation_s=2.0,checks=[],requests=[],events=[])
    bench = Bench('127.0.0.1',args.port,report)
    try:
        bench.connect()
        for target in args.targets:
            bench.reset()
            if args.payload:
                bench.command('payload',mass=args.payload)
            bench.command('rearm')
            if args.pose == 'folded':
                q = [-math.pi/3,2*math.pi/3,0,.06]
                request = bench.command('move_joints',positions=q,speed=1)
                bench.wait(lambda e:e.get('id') == request and e.get('event') == 'completed')
                bench.observe(.6)
            else:
                q = [0,math.pi/2,-math.pi/2,.06]
            q[3] = target
            request = bench.command('move_joints',positions=q,speed=1)
            bench.wait(lambda e:e.get('id') == request and e.get('event') == 'completed')
            bench.observe(report['settling_s'])
            first_event = len(report['events'])
            request = bench.command('inspect_j4_window',seconds=report['observation_s'])
            window = bench.wait(lambda e:e.get('id') == request and e.get('event') == 'j4_window')
            samples = [e['state'] for e in report['events'][first_event:] if e.get('event') == 'state'
                       and window['start_time'] <= e['state']['time'] <= window['end_time']]
            request = bench.command('inspect_contacts')
            contact = bench.wait(lambda e:e.get('id') == request and e.get('event') == 'contact_snapshot')
            error = window['max_error_m']
            amplitude = window['maximum_m']-window['minimum_m']
            assert not window['command_changed'] and window['samples'] > 0 and window['invalid_samples'] == 0
            assert window['samples'] >= int(report['observation_s']*1000/window['basic_time_step_ms'])
            assert samples and all(s['trial_id'] == window['trial_id'] for s in samples)
            assert abs(window['target_m']-target) < 1e-12
            ok = error < report['tolerance_m'] and amplitude < report['tolerance_m']
            report['checks'].append(dict(target=q,payload_kg=args.payload,pose=args.pose,
                status='passed' if ok else 'failed',max_error_m=error,range_m=[window['minimum_m'],window['maximum_m']],
                amplitude_m=amplitude,contact_snapshot=contact,per_physics_step_window=window,samples=samples))
            print(f"{'PASS' if ok else 'FAIL'}: J4={target:g} m; error={error*1000:.6f} mm; "
                  f"amplitud={amplitude*1000:.6f} mm; contactos={contact['total_contacts']}",flush=True)
        report['status'] = 'passed' if all(p['status'] == 'passed' for p in report['checks']) else 'failed'
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        if bench.sock:
            try:
                bench.reset()
                report['restored_initial_trial'] = True
            except Exception as error:
                report['cleanup_error'] = str(error)
                report['status'] = 'failed'
        bench.close()
        report['executed_inputs_unchanged'] = all(
            hashlib.sha256((args.snapshot_root/p).read_bytes()).hexdigest() == digest for p,digest in sources.items())
        if not report['executed_inputs_unchanged']:
            report['status'] = 'failed'
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
