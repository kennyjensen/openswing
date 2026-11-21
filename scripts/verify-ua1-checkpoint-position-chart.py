"""Serial physical replays of the production checkpoint precision correction."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from isae_ua1_stall_browser import read,write,pins,verify,digest,flatten
from isae_ua_artifacts import write_trajectory

BASE = ROOT/'artifacts/isae/ua1-checkpoint-chart-20261103'
DIAGNOSTIC = ROOT/'artifacts/isae/ua1-checkpoint-displacement-20261103'


def prepare():
    assert not BASE.exists()
    prior=read(DIAGNOSTIC/'plan.json')
    modules=pins(sorted((ROOT/'openswing').glob('*.py')))
    changed={k:dict(old=prior['source_sha256'][k],new=v) for k,v in modules.items()
             if prior['source_sha256'][k]!=v}
    assert set(changed)=={'openswing/time_state.py'} and len(modules)==136
    for name,entry in changed.items():
        assert digest(DIAGNOSTIC/'frozen-code'/name)==entry['old']
    sources=[Path(__file__).resolve(),ROOT/'scripts/test-ua1-checkpoint-chart-browser.mjs',
        ROOT/'scripts/isae_time_browser_compare.mjs',ROOT/'web/saved-state-data.js',
        ROOT/'scripts/isae_ua1_stall_browser.py',ROOT/'scripts/isae_ua_artifacts.py',
        ROOT/'tests/test_time_checkpoint_position_chart.py',
        ROOT/'dist/kernel/manifest.json',*sorted((ROOT/'dist/assets').glob('*')),
        *sorted(p for p in (ROOT/'dist/runtime').rglob('*') if p.is_file())]
    inputs=[DIAGNOSTIC/'capture/request.json',DIAGNOSTIC/'ordinary/request.json',
        ROOT/'artifacts/isae/ua-arc-precision-20261102/cold-UA1/request.json',
        DIAGNOSTIC/'diagnostic-summary.json']
    BASE.mkdir()
    cases=[]
    for name,path,steps,cold,previous in (
        ('seed',inputs[0],20,False,None),('continue',inputs[1],8,False,'seed'),
        ('cold-UA1',inputs[2],8,True,None)):
        folder=BASE/name;folder.mkdir()
        request=read(path)
        if previous:request.pop('checkpoint')
        write(folder/'request-template.json',request)
        cases.append(dict(name=name,steps=steps,cold=cold,previous=previous,area=200000.,span=200000.,panels=4,
            tolerance=1e-10,template_sha256=digest(folder/'request-template.json')))
    plan=dict(cases=cases,source_sha256={**modules,**pins(sources)},input_sha256=pins(inputs),
        changed_modules=changed,local_fields=['local_velocity','local_rates','local_acceleration','local_rate_derivative'],
        independent_rigid_local_motion_limit=2e-8,runtime_scaled_difference=2e-8,
        worker_request_timeout_seconds=45,serial=True,threads=1,
        full_periodic_validation=False,native_ASWING_comparison=False,registered_case_pass_count_change=0,
        scope='Legacy 20-step seed, its own new-format 8-step continuation, independent 8-step cold start; not a full periodic case.')
    write(BASE/'plan.json',plan)
    for name in plan['source_sha256']:
        if name.startswith('dist/runtime/'):continue
        dest=BASE/'frozen-code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    print(json.dumps(dict(prepared=True,cases=cases,changed_modules=changed)),flush=True)


def run(index):
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    plan=read(BASE/'plan.json');verify(plan['source_sha256']);verify(plan['input_sha256'])
    entry=plan['cases'][index];folder=BASE/entry['name']
    assert digest(folder/'request-template.json')==entry['template_sha256']
    request=read(folder/'request-template.json')
    if entry['previous']:
        prior=BASE/entry['previous'];verify(read(prior/'completed.json')['output_sha256'])
        request['checkpoint']=read(prior/'checkpoint.json')
    write(folder/'request.json',request)
    start=time.monotonic();raw=dispatch(request);seconds=time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert raw['converged'] and raw['accepted_steps']==entry['steps'] and raw['rejected_steps']==0
    assert len(raw['snapshots'])==entry['steps']+1
    saved=checkpoint(raw);write(folder/'checkpoint.json',saved)
    assert saved['state']==saved['accepted_method']['endpoint']['state']
    assert saved['accepted_method']['previous']==raw['snapshots'][-2]['restart']['state']
    assert saved['accepted_method']['previous2']==raw['snapshots'][-3]['restart']['state']
    for s in raw['snapshots']:
        assert 'position_chart' in s['restart']['state']
    maxima={key:max(abs(v) for s in raw['snapshots'] for v in flatten(s[key])) for key in plan['local_fields']}
    report=dict(case=entry,seconds=seconds,accepted_steps=entry['steps'],rejected_steps=0,
        maximum_new_step_residual=max(s['residual'] for s in raw['snapshots'][1:]),
        first_acceleration=raw['snapshots'][1]['local_acceleration'],local_motion_maxima=maxima,
        rigid_motion_passed=max(maxima.values())<=plan['independent_rigid_local_motion_limit'])
    write(folder/'report.json',report)
    assert report['rigid_motion_passed'] and report['maximum_new_step_residual']<=entry['tolerance']
    write(folder/'completed.json',dict(exit_code=0,output_sha256=pins([folder/name for name in
        ('request.json','trajectory.json.gz','checkpoint.json','report.json')])))
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','run']);p.add_argument('--case',type=int,choices=range(3))
    args=p.parse_args();prepare() if args.action=='prepare' else run(args.case)
