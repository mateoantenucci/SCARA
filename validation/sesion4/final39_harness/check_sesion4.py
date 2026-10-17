"""Adenda de sesión4: usa el Bench existente y solo el contrato scara-dev/1."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from tools.check_simulation import Bench, load_config

ROOT = Path('/private/tmp/scara-sesion4-final-20261017/SCARA minima39')
HARNESS = Path('/private/tmp/scara-sesion4-final-20261017/harness')
OUTPUT = Path('/private/tmp/scara-sesion4-final-20261017/evidence/final39_supplement.json')
report = dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),
              platform=platform.platform(),python=sys.version,protocol='scara-dev/1',
              tolerances={'joint_rad':.005,'slider_m':.0005},checks=[],requests=[],events=[])
report['sources'] = {p:hashlib.sha256((ROOT/p if (ROOT/p).is_file() else HARNESS/p).read_bytes()).hexdigest() for p in (
    'scara/runtime.py','scara/transport.py','webots/controllers/scara_bridge/scara_bridge.py',
    'webots/protos/SCARA.proto','webots/worlds/scara.wbt','config/scara.json',
    'cad/ensambles/integracion_articulada.json','tools/check_simulation.py','check_sesion4.py')}
bench = Bench('127.0.0.1',19141,report)
def passed(name,**values):
    report['checks'].append(dict(name=name,status='passed',**values))
    print('PASS:',name,flush=True)
def raw(frame):
    report.setdefault('raw_chunks',[]).append(frame.decode('utf-8'))
    bench.sock.sendall(frame)
try:
    bench.connect(); initial=bench.reset()
    raw(b'{"command":"status","id":"fragment')
    start=len(report['events']);bench.observe(.3)
    assert not any(e.get('id')=='fragmented' for e in report['events'][start:])
    raw(b'ed"}\n{"command":"status","id":"concat-a"}\n{"command":"status","id":"concat-b"}\n')
    for ident in ('fragmented','concat-a','concat-b'):
        bench.wait(lambda e,ident=ident:e.get('id')==ident and e.get('event')=='accepted')
    passed('real_tcp_fragmentation_and_concatenation')
    raw(b'{"command":"rearm","id":"abandoned"')
    bench.close(); sample=bench.connect()
    assert sample['mode']=='STOPPED'
    raw(b'}\n')
    bench.wait(lambda e:e.get('event')=='rejected' and e.get('message')=='JSON invalido')
    bench.command('status');sample=bench.state()
    assert sample['mode']=='STOPPED'
    assert not any(e.get('id')=='abandoned' and e.get('event')=='accepted' for e in report['events'])
    passed('truncated_frame_discarded_between_connections')
    bench.command('rearm')
    request_id=bench.command('move_joints',positions=[.4,.9,-1.3,.09],speed=.5)
    moving=bench.observe(.5)[-1];assert moving['mode']=='MOVING'
    bench.command('stop');stopped=bench.state(lambda s:s['mode']=='STOPPED')
    start=len(report['events']);samples=bench.observe(1.5)
    assert all(s['estimated']==stopped['estimated'] and s['commanded']==stopped['commanded'] and s['mode']=='STOPPED' for s in samples)
    assert not any(e.get('id')==request_id and e.get('event')=='completed' for e in report['events'][start:])
    errors=[abs(a-b) for a,b in zip(samples[-1]['simulated'],stopped['commanded'])]
    assert max(errors[:3])<.005 and errors[3]<.0005,errors
    bench.command('move_joints',expected='rejected',positions=initial['estimated'])
    bench.command('rearm')
    request_id=bench.command('move_joints',positions=initial['estimated'],speed=.5)
    bench.wait(lambda e:e.get('id')==request_id and e.get('event')=='completed')
    passed('explicit_stop_cancels_and_new_motion_requires_rearm',stopped_reference=stopped['estimated'],settled_error=errors,
           note='Error de asentamiento observado; no máximo continuo ni detención instantánea')
    initial=bench.reset();bench.command('rearm')
    target=list(initial['estimated']);target[3]=0
    request_id=bench.command('move_joints',positions=target,speed=.5)
    bench.wait(lambda e:e.get('id')==request_id and e.get('event')=='completed');bench.observe(.7)
    sample=bench.state(lambda s:s['hall_nominal'][3])
    bench.command('fault',kind='hall_stuck',axis=4,factor=0)
    sample=bench.state(lambda s:s['mode']=='FAULT')
    assert sample['hall_nominal'][3] and not sample['hall'][3]
    bench.command('rearm',expected='rejected');bench.command('clear_faults')
    sample=bench.state(lambda s:s['mode']=='STOPPED')
    assert sample['hall_nominal'][3] and sample['hall'][3]
    passed('hall_stuck_inactive_against_active_nominal',axis=4,
           note='Región Hall lógica provisional del banco, no calibración de sensor físico')
    initial=bench.reset();bench.command('fault',kind='effort_loss',axis=4,factor=.5)
    sample=bench.state(lambda s:s['mode']=='FAULT')
    assert sample['effort_available'][3]==4 and not sample['reference_valid']
    bench.command('clear_faults');sample=bench.state(lambda s:s['mode']=='STOPPED')
    assert sample['effort_available'][3]==4 and not sample['reference_valid']
    bench.command('rearm',expected='rejected')
    passed('half_effort_persists_after_stop_and_clear',available_force_N=4,
           note='No exige caída: la reducción no garantiza fallo bajo toda carga')
    final=bench.reset()
    passed('final_restored',trial_id=final['trial_id'],mode=final['mode'])
    report['status']='passed'
except Exception as exc:
    report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    raise
finally:
    bench.close()
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
