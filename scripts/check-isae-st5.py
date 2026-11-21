"""Numerical gates for ST-5; these do not gate experimental agreement."""
from pathlib import Path
import importlib.util
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('isae_st5',ROOT/'scripts/verify-isae-st5.py')
study=importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
path=ROOT/'docs/validation/isae-st5.json'
report=json.loads(path.read_text())
modules={p.name:study.sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
assert report['provenance']['modules']==modules
assert report['provenance']['script_sha256']==study.sha(Path(spec.origin))
case=report['cases'][0]
model=study.parse_asw((study.CACHE/case['input_path']).read_text())
expected=next(r for r in case['runs'] if r['specification']['panels']==16)['result']
actual=study.run_model(model,16,'dense')['result']
maximum=0.;checked=0
fields={None:['max_displacement','max_rotation_deg','force_balance','moment_balance','applied_force','applied_moment','support_force','support_moment'],
        'nodes':['t','position','jig_position','rotation'],
        'elements':['t','t0','t1','length','position','frame','force','moment','force_local','moment_local','strain','curvature_change']}
for collection,keys in fields.items():
    left=[actual] if collection is None else actual[collection]
    right=[expected] if collection is None else expected[collection]
    assert len(left)==len(right)
    for a,b in zip(left,right):
        for key in keys:
            av,bv=np.asarray(a[key]),np.asarray(b[key])
            assert av.shape==bv.shape
            maximum=max(maximum,float(np.max(abs(av-bv))));checked+=av.size
assert maximum<2e-7,maximum
refinement=[]
for case in report['cases'][:3]:
    runs=case['runs']
    assert all(r['status']=='computed' for r in runs)
    forces=np.array([[b['upward_force_lb'] for b in r['load_checks']] for r in runs])
    spread=float(np.max(np.ptp(forces,axis=0)))
    assert spread<1e-10
    errors=[r['load_checks'][0]['jig_moment_error_lbft'] for r in runs]
    assert all(b<a for a,b in zip(errors[:-1],errors[1:]))
    assert errors[-1]<.0003
    refinement.append(dict(case=case['name'],total_load_spread_lb=spread,forward_jig_moment_errors_lbft=errors))
assert all(r['status']=='rejected' and 'Attachment station is outside' in r['error'] for r in report['cases'][-1]['runs'])
output=dict(status='PASS_NUMERICAL_GATES_ONLY',full_suite_validated=False,modules=modules,
            study_sha256=study.sha(path),script_sha256=study.sha(Path(__file__)),
            dense_vs_structured=dict(case=report['cases'][0]['name'],panels=16,maximum_physical_difference=maximum,values=checked),
            load_refinement=refinement)
(ROOT/'docs/validation/isae-st5-checks.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:v for k,v in output.items() if k!='modules'},indent=2))
