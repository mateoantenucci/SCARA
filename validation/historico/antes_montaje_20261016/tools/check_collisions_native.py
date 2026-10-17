"""Comprueba rechazo de consignas y contacto por gravedad SOLO en Webots.

Recarga el mundo y provoca pérdida de esfuerzo. Usar una sesión de ensayo,
sin cliente UI. No contra hardware. Al terminar deja STOPPED inicial.
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
from scara.kinematics import load_config
from check_simulation import Bench


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=9000)
    parser.add_argument('--webots-version',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'validation/collisions_native.json')
    parser.add_argument('--snapshot-root',type=Path,help='Copia aislada de ejecución, para comprobar sus hashes')
    args = parser.parse_args()
    c = load_config()
    report = dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),
        webots_version=args.webots_version,checks=[],requests=[],events=[],sources={})
    for name in ('config/scara.json','scara/collisions.py','scara/runtime.py','client/app.py',
                 'tools/generate_world.py','tools/check_collisions_native.py','tools/check_simulation.py',
                 'scara/frames.py','scara/kinematics.py','cad/ensambles/integracion_articulada.json',
                 'webots/controllers/scara_bridge/scara_bridge.py','webots/protos/SCARA.proto','webots/worlds/scara.wbt'):
        report['sources'][name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    if args.snapshot_root:
        executed = ('config/scara.json','scara/collisions.py','scara/runtime.py','scara/frames.py',
                    'scara/kinematics.py','webots/controllers/scara_bridge/scara_bridge.py',
                    'webots/protos/SCARA.proto','cad/ensambles/integracion_articulada.json')
        for name in executed:
            assert (args.snapshot_root/name).read_bytes() == (ROOT/name).read_bytes(), name
        world = args.snapshot_root/'webots/worlds/scara.wbt'
        expected = (ROOT/'webots/worlds/scara.wbt').read_text().replace(
            'DEF SCARA SCARA { }',f'DEF SCARA SCARA {{ controllerArgs [ "--port" "{args.port}" ] }}')
        assert world.read_text() == expected,'El mundo de ensayo difiere más allá del puerto'
        report['isolated_execution'] = dict(root=str(args.snapshot_root),tcp_port=args.port,
            source_files_match=executed, world_sha256=hashlib.sha256(world.read_bytes()).hexdigest(),
            world_change='Solo controllerArgs --port; geometría y parámetros iguales a la plantilla')
    bench = Bench('127.0.0.1',args.port,report)

    def passed(name,**data):
        report['checks'].append(dict(name=name,status='passed',**data))
        print('PASS:',name,flush=True)

    def contacts():
        request_id = bench.command('inspect_contacts')
        return bench.wait(lambda e:e.get('id') == request_id and e.get('event') == 'contact_snapshot')

    def move(q):
        request_id = bench.command('move_joints',positions=q,speed=1)
        bench.wait(lambda e:e.get('id') == request_id and e.get('event') == 'completed',timeout=60)
        state = bench.observe(.6)[-1]
        assert max(abs(a-b) for a,b in zip(q[:3],state['simulated'][:3])) < .005
        assert abs(q[3]-state['simulated'][3]) < .0005,(q,state['simulated'])
        return state

    def rejected_without_motion(q):
        before = bench.state()
        request_id = bench.command('move_joints',expected='rejected',positions=q,speed=1)
        after = bench.observe(.3)[-1]
        assert after['commanded'] == before['commanded'] and after['mode'] == 'IDLE'
        assert max(abs(a-b) for a,b in zip(after['simulated'],before['simulated'])) < .001
        return dict(request_id=request_id,before=before['simulated'],after=after['simulated'])

    try:
        bench.connect();bench.reset()
        snapshot = contacts()
        assert snapshot['collision_box_counts'] == dict(base=8,arm=6,forearm=8,wrist=6,tool=2)
        passed('native_boxes_per_instance',counts=snapshot['collision_box_counts'])
        bench.command('rearm')
        invasion = [0,math.radians(135),math.radians(-135),.12]
        passed('reject_pedestal_target_before_motion',**rejected_without_motion(invasion))
        qa = [math.radians(-60),math.radians(120),0,.06]
        # El ensayo vuelve a cubrir el tope exacto tras ajustar la integración.
        move(qa);qa[3]=.12;move(qa)
        qb = [math.radians(30),math.radians(120),0,.12]
        passed('reject_free_endpoints_with_interior_collision',**rejected_without_motion(qb))
        bench.reset();bench.command('rearm')
        high = [0,math.radians(135),math.radians(-135),.08]
        before = move(high)
        assert not contacts()['total_contacts']
        bench.command('fault',kind='effort_loss',axis=4,factor=0)
        after = bench.observe(1.2)[-1]
        snapshot = contacts()
        # Los Solid internos del PROTO pueden devolver id=-1. Solo TOOL llega
        # a Z=0 en esta pose; identificamos el contacto por posición mundial.
        tool_contacts = [p for p in snapshot['contacts'] if abs(p['point'][2]) < .001
                         and max(abs(v) for v in p['point'][:2]) <= .201]
        assert tool_contacts, snapshot
        assert all(abs(p['point'][2]) < .001 for p in tool_contacts)
        assert -.001 < after['tcp_world'][2] < .001,after['tcp_world']
        assert high[3]+.005 < after['simulated'][3] < .104
        assert not after['reference_valid'] and after['effort_available'][3] == 0
        passed('gravity_contact_on_pedestal_not_lower_joint_stop',before=before['simulated'],
               after=after['simulated'],tcp=after['tcp_world'],contacts=tool_contacts,
               note='Contacto del soporte efector aproximado por caja; materiales aún provisionales')
        bench.command('clear_faults');bench.command('rearm',expected='rejected')
        bench.reset()
        passed('reset_restores_stopped_trial')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed',error=f'{type(error).__name__}: {error}')
        if bench.sock:
            try: bench.send('stop')
            except OSError: pass
        raise
    finally:
        bench.close();args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
