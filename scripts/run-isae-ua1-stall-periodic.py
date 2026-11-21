"""Four-cycle stall comparison, using small serial jobs and complete histories."""
import argparse
from dataclasses import asdict
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
from isae_ua_stall_reference import Section, trajectory
from isae_ua1_stall_periodic import GATES, KEYS, request, summarize, checks
from isae_ua_artifacts import write_trajectory
from isae_ua1_periodic_boundary import check_boundary
from isae_ua2_browser_cutoff import validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve()
sys.path.insert(0,str(ROOT))


def read(path): return json.loads(path.read_text())
def write(path,value):
    with path.open('x') as stream: stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
def digest(path):
    h=sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1048576),b''): h.update(b)
    return h.hexdigest()
def verify(pins):
    for name,value in pins.items(): assert digest(ROOT/name)==value,name
def name_for(steps,part): return f'n{steps}-part{part:03d}'
def completed(base,name):
    receipt=read(base/(name+'-execution.json'))
    assert receipt['exit_code']==0,name
    verify(receipt['output_sha256'])
    return receipt


def prepare(base):
    base.mkdir(parents=True)
    section=Section()
    names=['isae_ua1_stall_periodic.py','isae_ua_stall_reference.py','isae_ua_stall_production.py',
        'isae_ua_artifacts.py','isae_suite_unsteady.py','isae_ua1_periodic_study.py',
        'isae_ua1_periodic_boundary.py','isae_ua2_browser_cutoff.py',
        'isae_ua_incidence_reference.py','isae_ua_incidence_periodic.py',
        'isae_ua_periodic.py','isae_ua_section_reference.py']
    paths=[*sorted((ROOT/'openswing').glob('*.py')),SCRIPT,*[ROOT/'scripts'/name for name in names],
        ROOT/'tests/test_isae_ua1_stall_periodic.py',ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    plan=dict(section=asdict(section),grids=[320,640],cycles=4,reference_cycles=8,
        reference_steps=640,segment_steps=40,gates=GATES,source_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths},
        serial=True,threads=1,subprocess_timeout_seconds=45,production_changed=False,
        native_ASWING_comparison=False,browser_validation=False,full_forcing_before_startup=True,
        scope='Supplemental nonlinear 2D stall leakage and lag, four cold-start heave cycles. Not recovered native UA-1 settings.',
        normalization='Cold CL/Gamma: peak departure from independent pre-motion steady. Periodic CL/Gamma: peak departure from independent periodic mean. Rate/pressure: own reference peak. Every strip participates.',
        registered_rows=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
    write(base/'plan.json',plan)
    shutil.copyfile(ROOT/'docs/validation/ISAE_STATUS.md',base/'status-before.md')
    for path in paths:
        target=base/'frozen-code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
    for steps in plan['grids']: write(base/f'request-n{steps}.json',request(section,steps,plan['cycles']))
    print(json.dumps(dict(prepared=True,jobs=sum(plan['cycles']*n//plan['segment_steps'] for n in plan['grids']))),flush=True)


def reference(base,plan,method):
    section=Section(**plan['section'])
    times=[section.period*i/plan['reference_steps'] for i in range(plan['reference_cycles']*plan['reference_steps']+1)]
    start=time.monotonic()
    result=trajectory(section,times,method)
    write(base/f'reference-{method}.json',result)
    print(json.dumps(dict(method=method,seconds=time.monotonic()-start,samples=len(result['rows']))),flush=True)


def reference_check(base,plan):
    paths=[base/f'reference-{method}.json' for method in ('DOP853','Radau')]
    for method in ('DOP853','Radau'): completed(base,'reference-'+method)
    a,b=[read(p) for p in paths]
    errors={key:float(np.max(abs(np.array([r[key] for r in a['rows']])-np.array([r[key] for r in b['rows']])))/max(abs(r[key]) for r in b['rows'])) for key in KEYS}
    n=plan['reference_steps'];changes={}
    for key in KEYS:
        values=np.array([r[key] for r in b['rows'][-n-1:]])
        previous=np.array([r[key] for r in b['rows'][-2*n-1:-n]])
        scale=np.max(abs(values-(np.mean(values[:-1]) if key in ('CL','circulation') else 0.)))
        changes[key]=float(np.max(abs(values-previous))/scale)
    passed=max(errors.values()) < GATES['reference_fraction'] and max(changes.values()) < GATES['reference_settling_fraction']
    result=dict(passed=bool(passed),error_fractions=errors,settling_fractions=changes,input_sha256={str(p.relative_to(ROOT)):digest(p) for p in paths})
    write(base/'reference-check.json',result)
    print(json.dumps(result),flush=True)
    assert passed


def audit_raw(section,raw,steps,part,size,targets):
    rows=[]
    for local,sample in enumerate(raw['snapshots']):
        index=part*size+local
        target=targets[index]
        assert abs(sample['time']-target['time']) < 1e-12
        if part and local==0: continue
        if index: assert sample['order']==(1 if index==1 else 2)
        frame=sample['frame']
        assert max(abs(x) for x in frame['attitude']+frame['rates_body']) < 1e-12
        v=np.asarray(frame['velocity_origin_body']);a=np.asarray(frame['acceleration_reference_body'])
        assert abs(v@section.wind+section.speed) < 1e-10
        assert abs(a@section.heave-target['acceleration']) < 1e-10
        rows.append(dict(time=sample['time'],CL=float(np.asarray(sample['force'])@section.heave/(.5*1.225*section.speed**2*200000)),
            CDp_fixed=sample['CDp']*(sample['operating_values']['speed']/section.speed)**2,
            circulation=[s['circulation'] for s in sample['strips']],circulation_rate=sample['circulation_rate'],
            section_cl=[s['cl'] for s in sample['strips']],residual=sample['residual'],
            velocity=float(v@section.heave),position=float(np.asarray(frame['position_earth'])@section.heave)))
    return rows


def segment(base,plan,steps,part):
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    section=Section(**plan['section']);size=plan['segment_steps'];cycles=plan['cycles']
    assert steps in plan['grids'] and 0 <= part < cycles*steps//size
    full=read(base/f'request-n{steps}.json')
    assert full==request(section,steps,cycles)
    completed(base,'reference-check')
    refs=read(base/'reference-check.json');assert refs['passed'];verify(refs['input_sha256'])
    folder=base/name_for(steps,part);folder.mkdir()
    end=section.period*(size*(part+1))/steps
    calculation={**full,'time':{**full['time'],'duration':end}}
    prior=None
    if part:
        name=name_for(steps,part-1);completed(base,name)
        prior=read(base/name/'checkpoint.json')
        calculation={k:v for k,v in full.items() if k not in ('condition','time')}
        calculation.update(action='resume_time',checkpoint=prior,time=dict(duration=end-prior['state']['time'],max_steps=4*steps))
    write(folder/'request.json',calculation)
    start=time.monotonic();raw=dispatch(calculation);seconds=time.monotonic()-start
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert raw['converged'] and raw['accepted_steps']==size and raw['rejected_steps']==0
    samples=raw['snapshots'];assert len(samples)==size+1 and abs(samples[-1]['time']-end)<1e-12
    cutoff=validate_checkpoint(raw,final=(part==cycles*steps//size-1),expected_end=samples[-1]['time'])
    rounding=check_boundary(prior,samples) if prior else []
    write(folder/'checkpoint.json',checkpoint(raw))
    target=read(base/'reference-DOP853.json')['rows'][::plan['reference_steps']//steps]
    rows=audit_raw(section,raw,steps,part,size,target)
    write(folder/'audit.json',dict(rows=rows,boundary_checks=int(part>0),restart_rounding=rounding,cutoff=cutoff))
    write(folder/'report.json',dict(seconds=seconds,maximum_residual=max(r['residual'] for r in samples),accepted_steps=size,rejected_steps=0))
    verify(plan['source_sha256'])
    print(json.dumps(dict(job=folder.name,seconds=seconds,audited=len(rows))),flush=True)


def combine(base,plan,steps=None):
    results={};inputs={};section=Section(**plan['section']);boundaries=0
    grids=[steps] if steps else plan['grids']
    for grid in grids:
        assert grid in plan['grids'];rows=[]
        for part in range(plan['cycles']*grid//plan['segment_steps']):
            name=name_for(grid,part);inputs.update(completed(base,name)['output_sha256'])
            audit=read(base/name/'audit.json');rows.extend(audit['rows']);boundaries+=audit['boundary_checks']
        results[str(grid)]=summarize(section,grid,plan['cycles'],rows,read(base/'reference-DOP853.json'),plan['reference_steps'])
    reference=read(base/'reference-check.json');inputs.update(reference['input_sha256'])
    gates,ratios=checks(results,reference['passed'],section) if steps is None else ({},{})
    output=dict(passed=all(gates.values()) if gates else None,checks=gates,refinement_ratios=ratios,results=results,
        audited_unique_states=sum(r['samples'] for r in results.values()),boundary_checks=boundaries,
        source_sha256=plan['source_sha256'],input_sha256=inputs,
        production_changed=False,native_ASWING_comparison=False,browser_validation=False)
    verify({**plan['source_sha256'],**inputs})
    write(base/(f'grid-n{steps}.json' if steps else 'audit.json'),output)
    print(json.dumps({k:v for k,v in output.items() if k not in ('source_sha256','input_sha256')}),flush=True)
    if steps is None: assert output['passed'],'Preserve failed gates; do not relax them'


def run(base,plan,phase,max_jobs):
    if phase=='reference':
        jobs=[('reference-'+m,['reference','--method',m],[base/f'reference-{m}.json']) for m in ('DOP853','Radau')]
        jobs.append(('reference-check',['reference-check'],[base/'reference-check.json']))
    else:
        completed(base,'reference-check')
        jobs=[]
        for n in plan['grids']:
            for p in range(plan['cycles']*n//plan['segment_steps']):
                name=name_for(n,p)
                jobs.append((name,['segment','--steps',str(n),'--part',str(p)],
                    [base/name/f for f in ('request.json','trajectory.json.gz','checkpoint.json','audit.json','report.json')]))
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    count=0
    for name,args,outputs in jobs:
        if (base/(name+'-execution.json')).exists():completed(base,name);continue
        assert not (base/name).exists() and all(not p.exists() for p in outputs),'Inspect unreceipted work before resuming'
        command=['timeout','45s',sys.executable,str(SCRIPT),*args,'--base',str(base)]
        start=time.monotonic();print(json.dumps(dict(starting=name)),flush=True)
        with (base/(name+'.log')).open('x') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            live=dict(status='running',runner_pid=os.getpid(),child_pid=child.pid,command=command)
            (base/'live-job.json').write_text(json.dumps(live)+'\n')
            code=child.wait()
        receipt=dict(**live,exit_code=code,seconds=time.monotonic()-start);receipt['status']='terminal'
        if code==0:receipt['output_sha256']={str(p.relative_to(ROOT)):digest(p) for p in outputs}
        write(base/(name+'-execution.json'),receipt);(base/'live-job.json').write_text(json.dumps(receipt)+'\n')
        print(json.dumps(dict(job=name,exit_code=code,seconds=receipt['seconds'])),flush=True)
        if code!=0:raise SystemExit(code if code>0 else 1)
        count+=1
        if max_jobs and count>=max_jobs:break


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','reference','reference-check','segment','combine','run'])
    p.add_argument('--base',type=Path,default=ROOT/'artifacts/isae/ua1-stall-periodic-20261102')
    p.add_argument('--method',choices=['DOP853','Radau']);p.add_argument('--steps',type=int);p.add_argument('--part',type=int)
    p.add_argument('--phase',choices=['reference','production']);p.add_argument('--max-jobs',type=int)
    args=p.parse_args();base=args.base.resolve();assert base.is_relative_to(ROOT/'artifacts/isae')
    if args.action=='prepare':prepare(base);return
    plan=read(base/'plan.json');assert plan['gates']==GATES;verify(plan['source_sha256'])
    if args.action=='reference':reference(base,plan,args.method)
    elif args.action=='reference-check':reference_check(base,plan)
    elif args.action=='segment':segment(base,plan,args.steps,args.part)
    elif args.action=='combine':combine(base,plan,args.steps)
    else:run(base,plan,args.phase,args.max_jobs)


if __name__=='__main__':main()
