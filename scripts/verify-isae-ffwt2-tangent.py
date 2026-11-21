"""Versioned continuation of FFWT2 across the complete-tangent optimization.

The frozen preceding kernel and exact checkpoint stay binding evidence. The
ordinary resume API replays the saved discrete equations before advancing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'artifacts/isae/ffwt2-pilot-20261105/frozen/manifest.json'


def pin(p):
    p=Path(p).resolve();b=p.read_bytes()
    return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--resume-from',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--duration',type=float,default=.02)
    args=ap.parse_args();parent=args.resume_from.resolve();folder=args.output_dir.resolve()
    folder.mkdir(parents=True,exist_ok=False)
    plan=json.loads((parent/'plan.json').read_text())
    report=json.loads((parent/'report.json').read_text())
    assert report['status']=='SEGMENT_COMPUTED'
    assert pin(parent/'checkpoint.json')==report['checkpoint']
    assert pin(parent/'result.json')==report['result']
    for p in plan['source_pins']:assert pin(p['path'])==p
    prior=json.loads((parent/'checkpoint.json').read_text())
    current=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    old={p['path']:p for p in plan['kernel_pins']}
    assert set(old)=={p['path'] for p in current}
    changed=[Path(p['path']).name for p in current if p!=old[p['path']]]
    if plan.get('continuation_version')==1:
        assert not changed and pin(plan['helper']['path'])==plan['helper']
        plan['parent_checkpoint']=pin(parent/'checkpoint.json')
    else:
        assert changed==['time_integration.py'],changed
        frozen=json.loads(FROZEN.read_text())
        frozen={r['original']['path']:r for r in frozen}
        for p in plan['kernel_pins']+[plan['helper']]:
            row=frozen[p['path']];assert row['original']==p
            actual=pin(row['frozen_path'])
            assert all(actual[k]==p[k] for k in ('bytes','sha256'))
        for key in ('parent_checkpoint','parent_equilibrium'):plan.pop(key,None)
        plan.update(continuation_version=1,declared_segment_start=prior['state']['time'],
            prefix_checkpoint=pin(parent/'checkpoint.json'),prefix_report=pin(parent/'report.json'),
            frozen_prefix_manifest=pin(FROZEN),kernel_upgrade=dict(changed_modules=changed,
                before=old[str(ROOT/'openswing/time_integration.py')],
                after=pin(ROOT/'openswing/time_integration.py'),
                scope='Use existing analytical source load/reaction derivatives in full Newton matrices; physical equations and gates unchanged.'))
        plan['qualifications']=plan['qualifications']+[
            'This segment continues a frozen prefix; the ordinary checkpoint API checks its saved physical and discrete equations.',
            'Snapshot accounting here covers the versioned continuation, not the separately retained warm-up prefix.']
    plan.update(kernel_pins=current,helper=pin(__file__),duration=args.duration)
    request=dict(action='resume_time',source=Path(plan['source_pins'][0]['path']).read_text(),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        checkpoint=prior,time=dict(duration=args.duration))
    write(folder/'plan.json',plan);write(folder/'request.json',request)
    write(folder/'started.json',dict(request=pin(folder/'request.json'),wall_time=time.time()))
    sys.path.insert(0,str(ROOT))
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    start=time.monotonic()
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*args):
            stream.write(json.dumps(dict(seconds=time.monotonic()-start,event=args))+'\n');stream.flush()
        result=dispatch(request,progress=progress)
    elapsed=time.monotonic()-start
    assert result['converged'] and result['checkpoint_validation']['discrete_replayed']
    write(folder/'result.json',result);write(folder/'checkpoint.json',checkpoint(result,-1))
    for p in plan['source_pins']+plan['kernel_pins']+[plan['helper']]:assert pin(p['path'])==p
    record=dict(status='SEGMENT_COMPUTED',seconds=elapsed,snapshots=len(result['snapshots']),
        times=[s['time'] for s in result['snapshots']],result=pin(folder/'result.json'),
        checkpoint=pin(folder/'checkpoint.json'),native_comparisons=0,full_family_validated=False,
        checkpoint_validation=result['checkpoint_validation'])
    write(folder/'report.json',record);print(json.dumps(record),flush=True)


if __name__=='__main__':main()
