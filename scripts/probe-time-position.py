"""Paired runtime replay after cancellation-free nodal BDF differentiation.

This is a diagnostic of a retained eight-step segment, not a cold-start case.
The original UA-1 failed result and its comparison limits remain unchanged.
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import time

from isae_ua1_stall_browser import ROOT, BASE as OLD, read, write, digest, pins, verify, physical_row, difference, FIELDS
from isae_ua_artifacts import write_trajectory

BASE=ROOT/'artifacts/isae/ua-time-position-20261102'


def prepare():
    assert not BASE.exists()
    original=read(OLD/'plan.json')
    kernel=pins(sorted((ROOT/'openswing').glob('*.py')))
    changed={k:dict(old=original['source_sha256'][k],new=v) for k,v in kernel.items() if original['source_sha256'][k]!=v}
    assert set(changed)=={'openswing/time_integration.py'} and len(kernel)==136
    for name,value in kernel.items():
        for directory in ('public/kernel','dist/kernel'):
            assert digest(ROOT/directory/Path(name).name)==value
    paths=[Path(__file__).resolve(), ROOT/'scripts/test-time-position-browser.mjs',
        ROOT/'scripts/isae_ua1_stall_browser.py',ROOT/'scripts/isae_time_browser_compare.mjs',
        ROOT/'scripts/isae_ua_artifacts.py',ROOT/'web/saved-state-data.js',
        ROOT/'tests/test_time_position_derivative.py',ROOT/'dist/kernel/manifest.json',
        *sorted((ROOT/'dist/assets').glob('*')),
        *sorted(p for p in (ROOT/'dist/runtime').rglob('*') if p.is_file())]
    source=OLD/'production/part220/request.json'
    inputs=[source,OLD/'plan.json',OLD/'production/part220/trajectory.json.gz',OLD/'production/part220/receipt.json',OLD/'targets/part220.json']
    BASE.mkdir()
    cases=[]
    for label,tolerance in [('requested',1e-10),('tight',1e-12)]:
        folder=BASE/label;folder.mkdir()
        request=read(source);request['time']['tolerance']=tolerance
        write(folder/'request.json',request)
        cases.append(dict(name=label,tolerance=tolerance,request_sha256=digest(folder/'request.json')))
    plan=dict(cases=cases,section=original['section'],physical_steps_per_case=8,
        CPython_scaled_difference=2e-8,worker_request_timeout_seconds=45,
        source_sha256={**kernel,**pins(paths)},input_sha256=pins(inputs),changed_modules=changed,
        scope='Paired CPython/browser replays of the failed UA-1 part220, from its retained browser checkpoint. No new full-case validation count.',
        production_equations_changed=False,default_tolerance_changed=False,explicit_diagnostic_tolerances=[1e-10,1e-12],
        native_ASWING_comparison=False,full_periodic_case_passed=False)
    write(BASE/'plan.json',plan)
    for name in plan['source_sha256']:
        if name.startswith('dist/runtime/'):
            continue
        dest=BASE/'frozen-code'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    print(json.dumps(dict(prepared=True,changed_modules=changed,cases=cases)),flush=True)


def run(index):
    from openswing.bridge import dispatch
    plan=read(BASE/'plan.json');verify(plan['source_sha256']);verify(plan['input_sha256'])
    case=plan['cases'][index];folder=BASE/case['name'];request=read(folder/'request.json')
    assert digest(folder/'request.json')==case['request_sha256']
    start=time.monotonic();raw=dispatch(request);seconds=time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert raw['converged'] and raw['accepted_steps']==8 and raw['rejected_steps']==0 and len(raw['snapshots'])==9
    target=read(OLD/'targets/part220.json')['rows'];rows=[]
    for i,s in enumerate(raw['snapshots']):
        row=physical_row(s,plan['section']);assert abs(row['time']-target[i]['time'])<1e-12
        if i:assert s['residual']<=case['tolerance'] and s['order']==2
        rows.append(dict(**row,difference_from_old_Python={k:difference(row[k],target[i][k]) for k in FIELDS}))
    write(folder/'report.json',dict(diagnostic_only=True,case=case,seconds=seconds,rows=rows,
        accepted_steps=8,rejected_steps=0,maximum_new_step_residual=max(r['residual'] for r in rows[1:]),
        plan_sha256=digest(BASE/'plan.json'),source_sha256=plan['source_sha256']))
    write(folder/'completed.json',dict(output_sha256=pins([folder/'request.json',folder/'trajectory.json.gz',folder/'report.json'])))
    print(json.dumps(dict(case=case,seconds=seconds,max_residual=max(r['residual'] for r in rows[1:]),
        max_old_Python_force_difference=max(r['difference_from_old_Python']['force_coefficient'] for r in rows))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--case',type=int,choices=[0,1])
    args=parser.parse_args()
    prepare() if args.action=='prepare' else run(args.case)
