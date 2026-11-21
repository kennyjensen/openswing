"""Run the raw-history audit in serial, capped chunks and then combine metrics."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from isae_ua2_incidence_periodic import windows
from isae_ua2_periodic_records import records

ROOT=Path(__file__).resolve().parents[1]
BASE=Path(os.environ.get('OPENSWING_UA2_PERIODIC_BASE', ROOT/'artifacts/isae/ua2-incidence-periodic-20261101')).resolve()


def main():
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_jobs']==sum(len(records(BASE,n)) for n in (320,640))
    jobs=[(f'audit-n{n}-chunk{i:02d}', ['chunk','--steps',str(n),'--index',str(i)])
          for n in (320,640) for i in range((len(records(BASE,n))+3)//4)]
    jobs.append(('audit',['combine']))
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    for name,args in jobs:
        receipt_path=BASE/(name+'-execution.json');output=BASE/(name+'.json')
        if receipt_path.exists():
            receipt=json.loads(receipt_path.read_text())
            assert receipt['exit_code']==0 and receipt['report_sha256']==sha256(output.read_bytes()).hexdigest()
            continue
        if output.exists() or (BASE/(name+'.log')).exists():
            raise RuntimeError('Inspect retained unfinished or failed audit before recovery: '+name)
        command=['timeout','45s',sys.executable,str(ROOT/'scripts/audit-isae-ua2-incidence-periodic-chunks.py'),*args]
        started=time.monotonic()
        print(json.dumps(dict(starting=name)),flush=True)
        with (BASE/(name+'.log')).open('x') as stream:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
            live=dict(job=name,runner_pid=os.getpid(),child_pid=process.pid,command=command,status='running',start_time_unix=time.time())
            (BASE/'live-audit.json').write_text(json.dumps(live,indent=2)+'\n')
            code=process.wait()
        receipt=dict(**live,exit_code=code,wall_seconds=time.monotonic()-started)
        receipt['status']='terminal'
        if output.exists():receipt['report_sha256']=sha256(output.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        (BASE/'live-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(dict(completed=name,exit_code=code,seconds=receipt['wall_seconds'])),flush=True)
        if code:raise SystemExit(code if code>0 else 1)


if __name__=='__main__':main()
