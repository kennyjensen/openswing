"""Resume the immutable AE-1 plan after explicitly verified saved finalizations.

This supplements the original supervisor; it never rewrites its plan or failed
terminal receipts. New numerical jobs still use the original bounded worker.
"""
import argparse
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.isae_ae1_sweep import read,sha,save
from scripts.finalize_isae_ae1_saved import verify_completed,require


def prepare(out):
    original=read(out/'plan.json')
    for path,digest in original['pins'].items():require(sha(path)==digest,'original code/source changed')
    reviewed={}
    for entry in original['entries']:
        folder=Path(entry['folder'])
        if not entry['reused'] and (folder/'terminal.json').exists() and read(folder/'terminal.json')['returncode']!=0:
            require(verify_completed(folder),'unfinished failure');path=folder/'finalization/verification.json'
            reviewed[entry['id']]=dict(path=str(path),sha256=sha(path))
    require(bool(reviewed),'no reviewed finalization to authorize this continuation')
    number=len(list(out.glob('continuation-plan-*.json')))+1
    save(out/f'continuation-plan-{number:04d}.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        original_plan_sha256=sha(out/'plan.json'),reviewed_finalizations=reviewed,
        pins={str(p):sha(p) for p in (Path(__file__),ROOT/'scripts/finalize_isae_ae1_saved.py')},
        max_batch_jobs=2,physical_jobs_retried=0,scope_changed=False))
    (out/'continuation-batches').mkdir(exist_ok=True)
    print(f'Prepared continuation-plan-{number:04d}.json; original plan and terminations retained.')


def batch(out,plan_name):
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        continuation=read(out/plan_name)
        require(sha(out/'plan.json')==continuation['original_plan_sha256'],'original plan changed')
        original=read(out/'plan.json')
        for path,digest in {**original['pins'],**continuation['pins']}.items():
            require(sha(path)==digest,'pinned source changed: '+path)
        pending=[]
        for entry in original['entries']:
            folder=Path(entry['folder']);require(sha(folder/'job.json')==entry['job_sha256'],'job changed')
            if entry['reused']:continue
            if (folder/'terminal.json').exists():
                if read(folder/'terminal.json')['returncode']!=0:
                    evidence=continuation['reviewed_finalizations'].get(entry['id'])
                    require(evidence is not None and sha(evidence['path'])==evidence['sha256'],'unreviewed failed attempt')
                    require(verify_completed(folder),'invalid finalization')
                require((folder/'strict-result.json').exists(),'completed record lacks result')
            else:
                require(not (folder/'raw').exists(),'unreviewed interrupted worker; no retry')
                pending.append(entry)
        outcomes=[];began=time.monotonic()
        for entry in pending[:continuation['max_batch_jobs']]:
            folder=Path(entry['folder']);started=datetime.now(timezone.utc).isoformat()
            with (folder/'stdout.log').open('x') as stdout,(folder/'stderr.log').open('x') as stderr:
                try:
                    process=subprocess.run([sys.executable,str(ROOT/'scripts/replay_isae_ae1_bounded.py'),str(folder)],
                        stdout=stdout,stderr=stderr,cwd=ROOT,timeout=30)
                    terminal=dict(returncode=process.returncode,status='REAPED')
                except subprocess.TimeoutExpired:
                    terminal=dict(returncode=None,status='SUPERVISOR_TIMEOUT_REAPED')
            terminal.update(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat())
            save(folder/'terminal.json',terminal)
            receipt=read(folder/'receipt.json') if (folder/'receipt.json').exists() else {}
            outcomes.append(dict(id=entry['id'],terminal=terminal,receipt=receipt))
            if terminal['returncode']!=0:break
        number=len(list((out/'continuation-batches').glob('*.json')))+1
        save(out/'continuation-batches'/f'{number:04d}.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            continuation_plan=plan_name,seconds=time.monotonic()-began,outcomes=outcomes,remaining_before=len(pending)))
        failed=[o['id'] for o in outcomes if o['terminal']['returncode']!=0]
        print(dict(batch=number,finished=len(outcomes),remaining=len(pending)-len(outcomes),
            passed=sum(o['receipt'].get('passed',0) for o in outcomes),required=6*len(outcomes),failures=failed),flush=True)
        return int(bool(failed))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','batch'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--plan',default='continuation-plan-0001.json')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:raise SystemExit(batch(a.output.resolve(),a.plan))
