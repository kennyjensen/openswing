"""Serial, bounded jobs for the independent Euler-column verification."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/st6-column-supplement-20261103'
VERIFIER=ROOT/'scripts/verify-source-column-buckling.py'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,v:Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def prepare():
    assert not (BASE/'plan.json').exists()
    pilot=read(BASE/'n8-half/report.json');assert pilot['status']=='PASS'
    old=read(BASE/'n8-half/plan.json')
    for path,value in old['source_pins'].items():assert sha(ROOT/path)==value
    jobs={}
    for n in (8,16,32):
        for name,ratio,grid in [('zero',0.,False),('half',.5,False),('over',1.5,False),
                                ('below-critical',.9999,True),('above-critical',1.0001,True)]:
            jobs[f'n{n}-{name}']=dict(intervals=n,ratio=ratio,grid_critical=grid,method='full_shift_invert')
    jobs['n4-half-dense']=dict(intervals=4,ratio=.5,grid_critical=False,method='dense')
    for name,ratio,grid in [('over',1.5,False),('below-critical',.9999,True),('above-critical',1.0001,True)]:
        jobs[f'n64-{name}']=dict(intervals=64,ratio=ratio,grid_critical=grid,method='full_shift_invert')
    pins={**old['source_pins'],str(Path(__file__).relative_to(ROOT)):sha(__file__),
          str((BASE/'n8-half/plan.json').relative_to(ROOT)):sha(BASE/'n8-half/plan.json'),
          str((BASE/'n8-half/report.json').relative_to(ROOT)):sha(BASE/'n8-half/report.json'),
          str((BASE/'n8-half/result.json').relative_to(ROOT)):sha(BASE/'n8-half/result.json')}
    write(BASE/'plan.json',dict(jobs=jobs,pins=pins,retained_jobs=['n8-half'],workers=1,
        cold_solves_total=19,new_cold_solves=18,fresh_residuals_total=19,
        timeout_seconds=180,child_memory_bytes=512*1024**2,blas_threads=1,
        gates=dict(fine_continuum_relative=.001,fine_mesh_relative=.001,
                   critical_continuum_relative=.001,critical_bracket_relative_width=.00021),
        refinement_reason='Independent formulas predict a 0.157% 16/32 growth-rate change at 1.5 Pcr and a 0.1206% critical-load change. Declare the needed 64-interval extension before running the batch; preserve failed coarse pairs.',
        scope='Synthetic cantilever/point mass. Independent Euler/discrete references only, not original ISAE or native ASWING results.'))
    print(json.dumps(dict(prepared=True,total_jobs=19,new_jobs=18,retained=1)))


def run(name):
    plan=read(BASE/'plan.json')
    for path,value in plan['pins'].items():assert sha(ROOT/path)==value,path
    assert name in plan['jobs'] and name not in plan['retained_jobs']
    stage=BASE/name;assert not stage.exists(), 'Never overwrite or rerun a completed attempt.'
    args=plan['jobs'][name]
    command=[sys.executable,str(VERIFIER),str(stage),'--intervals',str(args['intervals']),
             '--ratio',str(args['ratio']),'--method',args['method']]
    if args['grid_critical']:command.append('--grid-critical')
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
    began=time.monotonic();timed_out=False
    with (BASE/(name+'.log')).open('xb') as log:
        child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write(BASE/(name+'-process.json'),dict(pid=child.pid,started_unix=time.time(),command=command))
        try:code=child.wait(timeout=plan['timeout_seconds'])
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
    receipt=dict(name=name,exit_code=code,timed_out=timed_out,process_reaped=True,
                 elapsed_seconds=time.monotonic()-began,
                 report_sha256=sha(stage/'report.json') if (stage/'report.json').exists() else None)
    write(BASE/(name+'-execution.json'),receipt);print(json.dumps(receipt),flush=True)
    if code!=0:raise SystemExit(code or 1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('--case')
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:run(args.case)
