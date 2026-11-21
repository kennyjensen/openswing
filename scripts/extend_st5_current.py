"""Extend current ST-5 snapshots one cold, resource-bounded grid at a time.

Only JSON whitespace changes in the inherited verifier. All physical recovery,
source data, equation checks and 0.1% convergence gates remain unchanged.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

import verify_st5_current as common

ROOT,read,write,pin=common.ROOT,common.read,common.write,common.pin
PARENT=ROOT/'artifacts/isae/st5-family-current-20261109'


def prepare(out,case):
    folder=out/case
    assert not folder.exists(), 'Preserve every earlier attempt.'
    parent=read(PARENT/'plan.json')
    row=next(r for r in parent['cases'] if r['case']==case)
    old=Path(row['directory']);study=read(old/'study.json')
    common.unchanged(study['pins']);common.unchanged(study['source_pins'])
    original=read(old/'plan.json')
    retained=[];paths=[Path(__file__),Path(common.__file__),PARENT/'plan.json',
                     old/'plan.json',old/'study.json',old/'verifier.py',old/'assessment.json']
    for level in (0,1):
        receipt=read(old/f'run-{level}/execution.json')
        assert receipt['exit_code']==0 and receipt['reaped'] and not receipt['timed_out']
        common.unchanged(receipt['outputs'])
        retained.append(str(old/f'run-{level}/level{level}/comparison.json'))
        for name in ('result.json','comparison.json'):
            path=old/f'run-{level}/level{level}'/name
            value=read(path);compact=json.dumps(value,separators=(',',':'),allow_nan=False)
            assert json.dumps(json.loads(compact),sort_keys=True)==json.dumps(value,sort_keys=True)
            paths.append(path)
        paths.append(old/f'run-{level}/execution.json')
    text=(old/'verifier.py').read_text()
    before="json.dumps(value, indent=2, allow_nan=False)"
    after="json.dumps(value, separators=(',', ':'), allow_nan=False)"
    assert text.count(before)==1
    text=text.replace(before,after)
    folder.mkdir(parents=True)
    (folder/'verifier.py').write_text(text)
    write(folder/'patches.json',dict(before=before,after=after,
        parent_verifier_sha256=pin(old/'verifier.py')['sha256'],
        justification='Whitespace only; full retained-result and comparison JSON round trips checked.'))
    nodes={k:v['nodes'] for k,v in original['meshes'][1]['panels']['beams'].items()}
    meshes=[]
    for level in (2,3,4):
        nodes={k:sorted(v+[(a+b)/2 for a,b in zip(v[:-1],v[1:])]) for k,v in nodes.items()}
        counts={k:len(v)-1 for k,v in nodes.items()}
        assert max(counts.values())<=1024
        mesh=dict(level=level,intervals_by_beam=counts,
                  panels=dict(default=max(counts.values()),beams={k:dict(nodes=v) for k,v in nodes.items()}))
        meshes.append(mesh)
        child=folder/f'run-{level}';child.mkdir()
        plan=deepcopy(original)
        plan.update(script_sha256=pin(folder/'verifier.py')['sha256'],meshes=[mesh],
            retained_comparisons=retained+[str(folder/f'run-{j}/level{j}/comparison.json') for j in range(2,level)],
            cold_solves=1,fresh_residuals=1,original_required_pair=[0,1],extension_pair=[level-1,level])
        write(child/'plan.json',plan);paths.append(child/'plan.json')
    paths.extend([folder/'verifier.py',folder/'patches.json'])
    # The supervisor checks all original sources and retained evidence before
    # and after each child. The verifier checks kernel/source/target identities
    # inside the child as well; unrelated PDF hashing is outside its CPU budget.
    pins={p['path']:p for p in study['pins']+study['source_pins']}
    pins.update({pin(p)['path']:pin(p) for p in paths})
    write(folder/'study.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),case=case,
        inherited_study=str(old/'study.json'),pins=list(pins.values()),limits=study['limits'],
        meshes=meshes,retained_current_states=2,new_states=3,
        required_rows=row['rows'],distinct_structural_targets=row['structural_targets'],
        reference_allowance=study['comparison'],numerical_gates=original['numerical_gates'],
        physics_changes=False,primary_passes_added=0))
    print(json.dumps(dict(case=case,prepared=[m['intervals_by_beam'] for m in meshes])),flush=True)


def worker(folder,level):
    assert all(os.environ.get(k)=='1' for k in common.helper.THREADS)
    study=read(folder/'study.json');limits=study['limits']
    resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu_seconds'],)*2);signal.alarm(limits['wall_seconds'])
    start=time.monotonic();cpu=time.process_time()
    module=common.load_module(folder/'verifier.py','st5_extension_worker')
    assert pin(folder/'verifier.py')['sha256']==read(folder/f'run-{level}/plan.json')['script_sha256']
    original_write=module.write;timings=[]
    def timed_write(path,value):
        began=time.monotonic();original_write(path,value)
        timings.append(dict(file=str(path.relative_to(folder)),seconds=time.monotonic()-began))
    module.write=timed_write
    module.run(folder/f'run-{level}')
    write(folder/f'run-{level}/timing.json',dict(wall_seconds=time.monotonic()-start,
        cpu_seconds=time.process_time()-cpu,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        json_writes=timings))


def run(out,case,level):
    folder=out/case;study=read(folder/'study.json');common.unchanged(study['pins'])
    childdir=folder/f'run-{level}'
    assert not (childdir/'execution.json').exists() and not (childdir/'run.log').exists()
    preceding=[]
    for j in range(2,level):
        r=read(folder/f'run-{j}/execution.json')
        assert r['exit_code']==0 and r['reaped'] and not r['timed_out']
        common.unchanged(r['outputs'])
        preceding.append(pin(folder/f'run-{j}/level{j}/comparison.json'))
    command=[sys.executable,str(Path(__file__).resolve()),'worker','--output',str(out),'--case',case,'--level',str(level)]
    start=time.monotonic()
    receipt=dict(observed_utc=datetime.now(timezone.utc).isoformat(),case=case,level=level,
        command=command,study=pin(folder/'study.json'),preceding=preceding,timed_out=False)
    with (childdir/'run.log').open('x') as log:
        child=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ,**common.helper.THREADS),
                               stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        receipt.update(pid=child.pid,reaped=False);write(childdir/'execution.json',receipt)
        try:child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            receipt['timed_out']=True;os.killpg(child.pid,signal.SIGKILL);child.wait()
        except BaseException:
            os.killpg(child.pid,signal.SIGKILL);child.wait();raise
        finally:
            receipt.update(exit_code=child.returncode,reaped=child.returncode is not None,
                elapsed_seconds=time.monotonic()-start,
                outputs=[pin(p) for p in sorted(childdir.rglob('*')) if p.is_file() and p.name!='execution.json'])
            write(childdir/'execution.json',receipt)
    common.unchanged(study['pins']);common.unchanged(preceding)
    print(json.dumps({k:receipt[k] for k in ('case','level','exit_code','reaped','elapsed_seconds')}),flush=True)
    assert child.returncode==0 and not receipt['timed_out'], 'Failed attempt retained; stop before dependent grid.'
    summary=read(childdir/'summary.json')
    assert summary['all_numerical_gates_pass']
    change=summary['mesh_changes'][-1]
    print(json.dumps(dict(mesh_checks_passed=sum(v['passes'] for v in change['measures'].values()),
        mesh_checks_required=14,maximum_relative_change=max(v['relative_change'] for v in change['measures'].values()),
        timing=read(childdir/'timing.json'))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','worker'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--case',required=True)
    p.add_argument('--level',type=int,choices=[2,3,4]);a=p.parse_args();out=a.output.resolve()
    if a.action=='prepare':prepare(out,a.case)
    else:
        assert a.level is not None
        if a.action=='run':run(out,a.case,a.level)
        else:worker(out/a.case,a.level)
