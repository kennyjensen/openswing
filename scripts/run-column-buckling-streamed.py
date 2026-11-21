"""Retry unsaved column output with streaming JSON, preserving all physics.

The pinned original verifier is changed only at its JSON writer. Successful
earlier cases are never repeated. The failed full-matrix formatting attempt
remains in the original directory and receipts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/isae/st6-column-supplement-20261103'
BASE=OLD/'streamed'
VERIFIER=ROOT/'scripts/verify-source-column-buckling.py'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
write=lambda p,v:Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def transformed():
    text=VERIFIER.read_text()
    before="    write=lambda name,v:(out/name).write_text(json.dumps(v,indent=2,allow_nan=False)+'\\n')"
    after="    def write(name,value):\n        with (out/name).open('w') as stream:\n            json.dump(value,stream,indent=2,allow_nan=False)\n            stream.write('\\n')"
    assert text.count(before)==1
    return text.replace(before,after)


def prepare():
    assert not BASE.exists();original=read(OLD/'plan.json')
    for name,value in original['pins'].items():assert sha(ROOT/name)==value
    failure=read(OLD/'n64-over/report.json')
    assert failure['status']=='FAILURE_RETAINED' and failure['error']=='MemoryError()'
    assert "write('result.json',result)" in failure['traceback']
    assert not (OLD/'n64-over/result.json').exists()
    BASE.mkdir();(BASE/'verifier-at-execution.py').write_text(transformed())
    jobs={name:row for name,row in original['jobs'].items() if name.startswith('n64-')}
    assert len(jobs)==3
    # Existing completed smaller jobs retain the exact original source pins.
    for name in original['jobs']:
        if name not in jobs:assert read(OLD/name/'report.json')['status']=='PASS'
    pins={**original['pins'],str(Path(__file__).relative_to(ROOT)):sha(__file__),
          str((BASE/'verifier-at-execution.py').relative_to(ROOT)):sha(BASE/'verifier-at-execution.py'),
          str((OLD/'plan.json').relative_to(ROOT)):sha(OLD/'plan.json'),
          str((OLD/'n64-over/report.json').relative_to(ROOT)):sha(OLD/'n64-over/report.json')}
    write(BASE/'plan.json',dict(jobs=jobs,pins=pins,retained_successful_jobs=16,
        expected_new_successful_solves=3,identical_unsaved_retry='n64-over',
        physical_and_numerical_expressions_unchanged=True,only_change='json.dump to file instead of json.dumps + write_text',
        timeout_seconds=180,child_memory_bytes=512*1024**2,workers=1,blas_threads=1))
    print(json.dumps(dict(prepared=True,retained_successes=16,new_jobs=3,memory_cap_unchanged=True)))


def work(name):
    plan=read(BASE/'plan.json')
    for key,value in plan['pins'].items():assert sha(ROOT/key)==value,key
    assert transformed()==(BASE/'verifier-at-execution.py').read_text()
    args=plan['jobs'][name]
    namespace={'__name__':'_streamed_column_verifier','__file__':str(VERIFIER)}
    exec(compile(transformed(),str(BASE/'verifier-at-execution.py'),'exec'),namespace)
    namespace['run'](argparse.Namespace(output=str(BASE/name),**args))


def run(name):
    assert not (BASE/name).exists();plan=read(BASE/'plan.json');assert name in plan['jobs']
    began=time.monotonic();timed_out=False
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
    with (BASE/(name+'.log')).open('xb') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__)),'worker','--case',name],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write(BASE/(name+'-process.json'),dict(pid=child.pid,started_unix=time.time()))
        try:code=child.wait(timeout=plan['timeout_seconds'])
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
    receipt=dict(case=name,exit_code=code,timed_out=timed_out,process_reaped=True,elapsed_seconds=time.monotonic()-began,
        report_sha256=sha(BASE/name/'report.json') if (BASE/name/'report.json').exists() else None)
    write(BASE/(name+'-execution.json'),receipt);print(json.dumps(receipt),flush=True)
    if code!=0:raise SystemExit(code)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run','worker'));parser.add_argument('--case')
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.action=='worker':work(args.case)
    else:run(args.case)
