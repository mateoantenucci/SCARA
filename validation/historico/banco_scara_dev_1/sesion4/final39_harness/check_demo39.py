"""Caso de demostración solicitado por sesión6; TCP nativo, sin interfaz visual."""
from datetime import datetime,timezone
import hashlib,json,math,platform,sys
from pathlib import Path
from tools.check_simulation import Bench,load_config
from scara.collisions import CollisionChecker
from scara.kinematics import inverse
ROOT=Path('/private/tmp/scara-sesion4-final-20261017/SCARA minima39')
OUTPUT=Path('/private/tmp/scara-sesion4-final-20261017/evidence/final39_demo_collision.json')
report=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),platform=platform.platform(),python=sys.version,
            note='Rechazo preventivo real en Runtime Webots; sin choque físico provocado ni observación visual de UI',checks=[],requests=[],events=[],
            inputs={'nominal_mm':[240,250,35],'nominal_yaw_deg':None,'rejected_mm':[73.2233,176.7767,34.6669],'rejected_yaw_deg':0,'speed':.3},
            tolerances={'joint_rad':.005,'slider_m':.0005},source_imports={name:str(sys.modules[name].__file__) for name in ('scara.kinematics','scara.collisions','scara.dynamics')})
report['sources']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('scara/runtime.py','scara/kinematics.py','scara/collisions.py','config/scara.json','webots/protos/SCARA.proto','webots/worlds/scara.wbt','cad/ensambles/integracion_articulada.json')}
bench=Bench('127.0.0.1',19141,report)
try:
    bench.connect();initial=bench.reset();assert initial['payload_mass']==0
    bench.command('rearm');config=load_config()
    nominal=inverse(.240,.250,.035,yaw=None,current=initial['estimated'],config=config)
    CollisionChecker(config).validate_path(initial['estimated'],nominal,0)
    ident=bench.command('move_joints',positions=nominal,speed=.3)
    bench.wait(lambda e:e.get('id')==ident and e.get('event')=='completed');before=bench.observe(.7)[-1]
    errors=[abs(a-b) for a,b in zip(before['simulated'],nominal)]
    assert max(errors[:3])<.005 and errors[3]<.0005,errors
    rejected=inverse(.0732233,.1767767,.0346669,yaw=0,current=before['estimated'],config=config)
    try:
        CollisionChecker(config).validate_path(before['estimated'],rejected,0)
    except ValueError as exc:
        client_guard=str(exc)
    else:
        raise AssertionError('La guardia del cliente debería rechazar el choque')
    assert 'puede tocar' in client_guard and '0-Torre-1' in client_guard,client_guard
    ident=bench.send('move_joints',positions=rejected,speed=.3)
    event=bench.wait(lambda e:e.get('id')==ident and e.get('event') in ('accepted','rejected'))
    assert event['event']=='rejected' and 'puede tocar' in event['message'] and '0-Torre-1' in event['message'],event
    samples=bench.observe(.7)
    assert all(s['mode']=='IDLE' and s['estimated']==before['estimated'] and s['commanded']==before['commanded'] for s in samples)
    assert all(max(abs(a-b) for a,b in zip(s['simulated'][:3],before['simulated'][:3]))<.005 and abs(s['simulated'][3]-before['simulated'][3])<.0005 for s in samples)
    final=bench.reset();assert final['mode']=='STOPPED' and final['reference_valid'] and final['payload_mass']==0
    report['checks'].append(dict(name='professor_demo_collision_rejected_before_motion',status='passed',nominal_joints=nominal,rejected_joints=rejected,
        nominal_final_joint_errors=errors,client_guard_message=client_guard,native_event=event,unchanged_samples=len(samples),final_state=final))
    report['status']='passed';print('PASS: professor_demo_collision_rejected_before_motion',event['message'],flush=True)
except Exception as exc:
    report.update(status='failed',error=f'{type(exc).__name__}: {exc}');raise
finally:
    bench.close();OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
