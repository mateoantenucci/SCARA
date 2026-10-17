"""Verifica en Webots cada Pose CAD durante los cuatro movimientos articulares.

Necesita scara.wbt en reproducción, sin client.app conectado. Recarga el ensayo.
Usa instrumentación interna; no agrega sensores al diseño físico.
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
from scara.frames import chain_frames, multiply
from scara.kinematics import load_config
from check_simulation import Bench


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'validation/cad_motion.json')
    parser.add_argument('--webots-version',default='no registrada')
    parser.add_argument('--port',type=int,default=9000)
    args=parser.parse_args()
    config=load_config()
    cad=json.loads((ROOT/'cad/ensambles/integracion_articulada.json').read_text())
    report=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),
                webots_version=args.webots_version,model_status=config['model_status'],
                tolerances=dict(position_m=.001,rotation_matrix_entry=.01),
                sources={},checks=[],arrivals=[],requests=[],events=[])
    paths=['config/scara.json','config/cad_integration.json','scara/frames.py','tools/check_cad_motion.py',
           'tools/check_simulation.py','tools/generate_world.py','tools/integrate_cad.py',
           'cad/ensambles/integracion_articulada.json','webots/protos/SCARA.proto','webots/worlds/scara.wbt',
           'webots/controllers/scara_bridge/scara_bridge.py']
    paths += ['scara/collisions.py','scara/runtime.py']
    paths+=list(cad['sources'])
    paths += [mesh['path'] for entry in cad['instances'] for mesh in entry['meshes']]
    for name in paths:
        report['sources'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    bench=Bench('127.0.0.1',args.port,report)
    entries={entry['def_name']:entry for entry in cad['instances']}

    def snapshot(name,saved_pose=False):
        request_id=bench.command('inspect_cad')
        groups={}
        while True:
            event=bench.wait(lambda e:e.get('id')==request_id and e.get('event') in ('cad_snapshot','cad_snapshot_complete'))
            if event['event']=='cad_snapshot_complete':break
            assert event['group'] not in groups
            groups[event['group']]=event
        assert set(groups)==set(cad['body_defs'])
        observed=set();max_position=max_rotation=0.0
        for group,event in groups.items():
            frame=chain_frames(event['simulated'],config)[group]
            assert math.dist(event['body_position'],[frame[i][3] for i in range(3)])<.001
            expected_mass=None if group=='base' else config['body_properties'][['arm','forearm','wrist','tool'].index(group)]['mass']
            assert event['body_mass']==expected_mass
            for part in event['parts']:
                assert part['name'] not in observed
                observed.add(part['name'])
                entry=entries[part['name']]
                assert entry['group']==group
                expected=entry['canonical_object_pose'] if saved_pose else multiply(frame,entry['body_from_piece'])
                error=math.dist(part['position'],[expected[i][3] for i in range(3)])
                rotation_error=max(abs(part['orientation'][3*i+j]-expected[i][j]) for i in range(3) for j in range(3))
                max_position=max(max_position,error);max_rotation=max(max_rotation,rotation_error)
                assert error<.001 and rotation_error<.01,(part['name'],error,rotation_error)
        assert observed==set(entries)
        result=dict(name=name,status='passed',instances_checked=len(observed),
                    max_position_error_m=max_position,max_rotation_entry_error=max_rotation)
        report['checks'].append(result);print('PASS:',name,len(observed),'poses CAD',flush=True)
        return groups

    def move(q):
        q=list(q)
        request_id=bench.command('move_joints',positions=q,speed=1)
        bench.wait(lambda e:e.get('event')=='completed' and e.get('id')==request_id,timeout=60)
        actual=bench.observe(.6)[-1]['simulated']
        errors=[abs(a-b) for a,b in zip(actual,q)]
        assert max(errors[:3])<.005 and errors[3]<.0005,errors
        report['arrivals'].append(dict(target=q,simulated=actual,joint_errors=errors))

    try:
        bench.connect();bench.reset()
        snapshot('initial_CAD_frames')
        bench.command('rearm');move(cad['saved_joint_reference'])
        snapshot('saved_assembly_reconstructed_in_Webots',saved_pose=True)
        move(config['initial_positions'])
        q=list(config['initial_positions'])
        for axis,delta in enumerate((.12,-.12,.12,.015)):
            before=snapshot(f'before_J{axis+1}')
            q[axis]+=delta;move(q)
            after=snapshot(f'after_J{axis+1}')
            fixed=['base','arm','forearm','wrist'][:axis+1]
            moving=['arm','forearm','wrist','tool'][axis:]
            for group in fixed:
                assert math.dist(before[group]['body_position'],after[group]['body_position'])<.001
                assert max(abs(a-b) for a,b in zip(before[group]['body_orientation'],after[group]['body_orientation']))<.01
            for group in moving:
                changed_position=math.dist(before[group]['body_position'],after[group]['body_position'])
                changed_rotation=max(abs(a-b) for a,b in zip(before[group]['body_orientation'],after[group]['body_orientation']))
                assert changed_position>.005 or changed_rotation>.02,(axis,group)
        bench.reset();snapshot('restored_initial_CAD')
        report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['error']=f'{type(exc).__name__}: {exc}'
        if bench.sock is not None:
            try:bench.send('stop')
            except OSError:pass
        raise
    finally:
        bench.close();args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        print('Informe:',args.output,flush=True)


if __name__=='__main__':
    main()
