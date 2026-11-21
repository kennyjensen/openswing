"""Two independently integrated references on the complete startup-refined grids."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time
import numpy as np
from isae_ua_wing_incidence_refined import AccurateInclinedWing
from isae_ua2_incidence_nested import grid,full_request,GATES

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-nested-20261101'


def main():
    BASE.mkdir(parents=True,exist_ok=True)
    assert not (BASE/'reference-plan.json').exists()
    paths=[Path(__file__).resolve(),*[ROOT/'scripts'/n for n in ('isae_ua_wing_incidence_refined.py',
        'isae_ua_wing_incidence.py','isae_ua_wing_nonlinear.py','isae_ua2_incidence_nested.py','isae_ua2_incidence_startup.py',
        'isae_ua2_incidence_time.py','isae_ua_startup.py','isae_suite_unsteady.py')],
        ROOT/'tests/test_isae_ua_wing_incidence.py',ROOT/'.reference/asw_uns_theory.txt',ROOT/'.reference/asw_theory.txt']
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    grids={str(n):grid(n) for n in (160,320)}
    for n,times in grids.items():
        actual=[float(r.split()[0]) for r in full_request(int(n))['time']['forcing'].splitlines()[1:]]
        assert actual==times
    times=sorted(set(t for values in grids.values() for t in values))
    plan=dict(gates=GATES,grids=grids,source_sha256=pins,reference_agreement_fraction=1e-8,
        first_step_subdivisions=256,maximum_step_growth=1.125,alpha_deg=9,k=.95,panels=20,
        span=10.,amplitude_ratio=.5,native_ASWING_comparison=False)
    (BASE/'reference-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for p in paths:
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    wing=AccurateInclinedWing(20,alpha_deg=9.);results={};seconds={}
    for method in ('DOP853','Radau'):
        started=time.monotonic();results[method]=dict(cold=wing.integrate(times,amplitude_ratio=.5,k=.95,method=method));seconds[method]=time.monotonic()-started
    errors={}
    for key in ('CL','circulation','circulation_rate'):
        x,y=(np.array([r[key] for r in results[m]['cold']['rows']]) for m in ('DOP853','Radau'))
        errors[key]=float(np.max(abs(x-y)/np.max(abs(y),axis=0)))
    output=dict(passed=max(errors.values())<plan['reference_agreement_fraction'],reference=results,
        method_differences=errors,grids=grids,method_seconds=seconds)
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    (BASE/'reference.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=output['passed'],differences=errors,grid_lengths={n:len(v) for n,v in grids.items()},seconds=seconds)))
    if not output['passed']:raise SystemExit(1)


if __name__=='__main__':main()
