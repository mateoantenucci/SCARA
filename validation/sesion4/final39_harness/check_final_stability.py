"""Observación de cierre del banco propio; no modifica el ensayo."""
from pathlib import Path
import json
from tools.check_simulation import Bench,load_config
report={'requests':[],'events':[]}
bench=Bench('127.0.0.1',19141,report)
try:
    bench.connect(); samples=bench.observe(1.5); initial=load_config()['initial_positions']
    assert len({s['trial_id'] for s in samples})==1
    assert all(s['mode']=='STOPPED' and s['payload_mass']==0 and s['reference_valid'] and not s['faults'] and s['commanded']==initial and s['estimated']==initial for s in samples)
    errors=[[abs(a-b) for a,b in zip(s['simulated'],initial)] for s in samples]
    assert all(max(e[:3])<.005 and e[3]<.0005 for e in errors)
    report.update(status='passed',samples=len(samples),simulated_duration=samples[-1]['time']-samples[0]['time'],final_state=samples[-1],max_joint_errors=[max(e[i] for e in errors) for i in range(4)])
    Path('/private/tmp/scara-sesion4-final-20261017/evidence/final39_stability.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('PASS: STOPPED, payload0, reference_valid, one trial, stable samples',len(samples))
finally:
    bench.close()
