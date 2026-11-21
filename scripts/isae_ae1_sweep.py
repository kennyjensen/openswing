"""Complete the literal AE-1 frozen sweep in small foreground serial batches.

Reuse only exactly matching, pinned current-code records. Each new worker has
its own process limits; interrupted/failed attempts are retained, never retried.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_ae1 as adapter


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')


def prepare(out, previous):
    out.mkdir()
    context = adapter._context(ROOT)
    jobs = list(adapter._jobs(*context, frozen=True))
    assert len(jobs) == 200 and sum(j['execution_route'] == 'worker' for j in jobs) == 196
    prior = read(previous/'plan.json')['selected'] + read(previous/'interior-plan.json')['selected']
    pins = {str(previous/'summary.json'):sha(previous/'summary.json')}
    entries = []
    for job in jobs:
        reused = job['id'] in prior
        folder = previous/job['id'] if reused else out/job['id']
        if reused:
            assert read(folder/'job.json') == job, 'Current job differs from retained state'
            result = read(folder/'strict-result.json')
            adapter.validate_result_contract(job, result)
            for name in ('job.json', 'strict-result.json', 'receipt.json'):
                pins[str(folder/name)] = sha(folder/name)
        else:
            folder.mkdir();save(folder/'job.json', job)
        entries.append(dict(id=job['id'], folder=str(folder), reused=reused, required=6,
                            job_sha256=sha(folder/'job.json')))
    for name in ('scripts/isae_ae1_sweep.py', 'scripts/replay_isae_ae1_bounded.py',
                 'scripts/run-isae-suite.py', 'scripts/isae_suite_ae1.py',
                 'scripts/isae_suite_ap1.py', 'scripts/isae_acceptance.py'):
        pins[str(ROOT/name)] = sha(ROOT/name)
        dest=out/'frozen-code'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dest)
    for p in jobs[0]['kernel_pins'] + jobs[0]['source_pins']:
        pins[p['path']] = p['sha256']
    for name in ('docs/validation/aswing-authoritative-references.md',
                 'reference/aswing-authoritative-20261108/isae-part-4.json',
                 'reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf'):
        pins[str(ROOT/name)] = sha(ROOT/name)
    source=read(ROOT/'reference/aswing-authoritative-20261108/isae-part-4.json')
    assert sha(ROOT/'reference/aswing-authoritative-20261108/isae-part-4-aeroelasticity.pdf')==source['expected_sha256']
    save(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_turn='progress: twelve current states and six operating points verified',
        scope='All100 original rows, six absolute channels, nominal40/80 meshes, frozen influences',
        required=1200, positive_states=196, unknown_start_records=4, new_states=184,
        reused_states=12, reused_unknown_records=4, relative_tolerance=.05,
        physical_gates_unchanged=True, historical_settings_recovered=False,
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25,supervisor_seconds=30),
        pins=pins, entries=entries))
    (out/'batches').mkdir()
    print(json.dumps(dict(status='FULL_SCOPE_PREPARED',required=1200,new_states=184,reused_records=len(prior))))


def batch(out, count):
    if not 1 <= count <= 8:
        raise ValueError('Use one to eight serial worker processes per foreground batch')
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan=read(out/'plan.json')
        for path, checksum in plan['pins'].items():
            assert sha(path)==checksum, path
        pending=[]
        for entry in plan['entries']:
            if entry['reused']:continue
            folder=Path(entry['folder'])
            assert sha(folder/'job.json')==entry['job_sha256']
            if (folder/'terminal.json').exists():
                assert read(folder/'terminal.json')['returncode']==0, 'Prior failure needs inspection; no retry'
                assert (folder/'strict-result.json').exists()
            else:
                assert not (folder/'raw').exists(), 'Interrupted worker needs inspection; no retry'
                pending.append(entry)
        selected=pending[:count]
        outcomes=[];began=time.monotonic()
        for entry in selected:
            folder=Path(entry['folder']);started=datetime.now(timezone.utc).isoformat()
            with (folder/'stdout.log').open('x') as stdout, (folder/'stderr.log').open('x') as stderr:
                try:
                    process=subprocess.run([sys.executable,str(ROOT/'scripts/replay_isae_ae1_bounded.py'),str(folder)],
                        stdout=stdout,stderr=stderr,timeout=30,cwd=ROOT)
                    terminal=dict(returncode=process.returncode,status='REAPED')
                except subprocess.TimeoutExpired:
                    terminal=dict(returncode=None,status='SUPERVISOR_TIMEOUT_REAPED')
            terminal.update(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat())
            save(folder/'terminal.json',terminal)
            receipt=read(folder/'receipt.json') if (folder/'receipt.json').exists() else {}
            outcomes.append(dict(id=entry['id'],terminal=terminal,receipt=receipt))
            if terminal['returncode']!=0:break
        number=len(list((out/'batches').glob('*.json')))+1
        save(out/'batches'/f'{number:04d}.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
            seconds=time.monotonic()-began,outcomes=outcomes,remaining_before=len(pending)))
        print(json.dumps(dict(batch=number,finished=len(outcomes),remaining=len(pending)-len(outcomes),
            passed=sum(o['receipt'].get('passed',0) for o in outcomes),required=6*len(outcomes),
            seconds=time.monotonic()-began,failures=[o['id'] for o in outcomes if o['terminal']['returncode']!=0])),flush=True)
        return int(any(o['terminal']['returncode']!=0 for o in outcomes))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','batch']);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--previous',type=Path);parser.add_argument('--count',type=int,default=4)
    args=parser.parse_args();out=args.output.resolve()
    if args.action=='prepare':prepare(out,args.previous.resolve())
    else:raise SystemExit(batch(out,args.count))
