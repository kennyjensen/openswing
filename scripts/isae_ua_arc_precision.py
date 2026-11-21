"""Bounded current-source UA replay/startup checks after arc quadrature repair.

These short histories establish neither full-period nor native-ASWING parity.
The enlarged comparison includes nodal kinematics and structural resultants.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isae_ua1_stall_browser import read,write,pins,verify,digest,flatten
from isae_ua_artifacts import write_trajectory

BASE=ROOT/'artifacts/isae/ua-arc-precision-20261102'
OLD=ROOT/'artifacts/isae/ua-time-refinement-20261102'
LOCAL_FIELDS=('local_velocity','local_rates','local_acceleration','local_rate_derivative')


def prepare():
    assert not (BASE/'plan.json').exists()
    previous=read(OLD/'plan.json')
    kernel=pins(sorted((ROOT/'openswing').glob('*.py')))
    changed={k:dict(old=previous['source_sha256'][k],new=v) for k,v in kernel.items() if previous['source_sha256'][k]!=v}
    assert len(kernel)==136 and set(changed)=={'openswing/arc_length.py'}
    assert digest(BASE/'arc_length-before.py')==changed['openswing/arc_length.py']['old']
    for name,value in kernel.items():
        for directory in ('public/kernel','dist/kernel'):
            assert digest(ROOT/directory/Path(name).name)==value
    cases=[];inputs=[]
    for name,tolerance in [('replay-requested',1e-10),('replay-tight',1e-12)]:
        path=OLD/('requested' if name=='replay-requested' else 'tight')/'request.json'
        request=read(path);inputs.append(path)
        cases.append(dict(name=name,cold=False,area=200000.,panels=4,tolerance=tolerance,request=request))
    for label,folder,area in [('UA1','ua1-stall-periodic-browser-20261102',200000.),
                             ('UA2','ua2-incidence-periodic-browser-20261101',10.)]:
        path=ROOT/'artifacts/isae'/folder/'plan.json';saved=read(path);inputs.append(path)
        request=saved['full_request'];request['time']['duration']=saved['times'][8]
        request['time']['max_steps']=32
        cases.append(dict(name='cold-'+label,cold=True,area=area,panels=request['panels'],
            tolerance=request['time']['tolerance'],request=request))
    for case in cases:
        case['span']=case['area']  # Rectangular unit-chord fixtures.
        folder=BASE/case['name'];folder.mkdir()
        write(folder/'request.json',case.pop('request'))
        case['request_sha256']=digest(folder/'request.json')
    sources=[Path(__file__).resolve(),ROOT/'scripts/test-ua-arc-precision-browser.mjs',
        ROOT/'scripts/isae_time_browser_compare.mjs',ROOT/'scripts/isae_ua1_stall_browser.py',
        ROOT/'scripts/isae_ua_artifacts.py',ROOT/'web/saved-state-data.js',
        ROOT/'tests/test_arc_constant_precision.py',ROOT/'tests/test_arc_length.py',
        ROOT/'dist/kernel/manifest.json',*sorted((ROOT/'dist/assets').glob('*')),
        *sorted(p for p in (ROOT/'dist/runtime').rglob('*') if p.is_file())]
    plan=dict(cases=cases,physical_steps_per_case=8,runtime_scaled_difference=2e-8,
        independent_rigid_local_motion_limit=2e-8,local_fields=list(LOCAL_FIELDS),
        force_scale='0.5*rho*Vref^2*Sref',moment_scale='force_scale*span (the structural moment scale); unit chord, span=area in these fixtures',
        other_field_scale='max(1,abs(expected)) for each scalar in its displayed physical units',
        comparison_scope='Aerodynamic/frame fields plus all nodal kinematics, nodal positions/rotations, internal forces/moments and reactions; not all possible app outputs.',
        worker_request_timeout_seconds=45,source_sha256={**kernel,**pins(sources)},input_sha256=pins(inputs),
        changed_modules=changed,previous_goal_turn='progress',
        full_periodic_validation=False,native_ASWING_comparison=False,registered_case_pass_count_change=0)
    write(BASE/'plan.json',plan)
    for name in plan['source_sha256']:
        if name.startswith('dist/runtime/'):continue
        target=BASE/'frozen-code'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    print(json.dumps(dict(prepared=True,cases=[c['name'] for c in cases],changed_modules=changed)),flush=True)


def run(index):
    from openswing.bridge import dispatch
    plan=read(BASE/'plan.json');verify(plan['source_sha256']);verify(plan['input_sha256'])
    case=plan['cases'][index];folder=BASE/case['name'];request=read(folder/'request.json')
    assert digest(folder/'request.json')==case['request_sha256']
    start=time.monotonic();raw=dispatch(request);seconds=time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert raw['converged'] and raw['accepted_steps']==8 and raw['rejected_steps']==0
    assert len(raw['snapshots'])==9
    for i,s in enumerate(raw['snapshots']):
        assert len(s['strips'])==case['panels']
        if i:assert s['residual']<=case['tolerance'] and s['order']==(1 if case['cold'] and i==1 else 2)
    maxima={key:max(abs(v) for s in raw['snapshots'] for v in flatten(s[key])) for key in LOCAL_FIELDS}
    report=dict(case=case,seconds=seconds,accepted_steps=8,rejected_steps=0,
        maximum_new_step_residual=max(s['residual'] for s in raw['snapshots'][1:]),
        local_motion_maxima=maxima,independent_rigid_motion_passed=None if not case['cold'] else max(maxima.values())<=plan['independent_rigid_local_motion_limit'])
    write(folder/'report.json',report)
    write(folder/'completed.json',dict(output_sha256=pins([folder/'request.json',folder/'trajectory.json.gz',folder/'report.json'])))
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--case',type=int,choices=range(4))
    args=parser.parse_args()
    prepare() if args.action=='prepare' else run(args.case)
