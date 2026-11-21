"""Replay the UA-2 checkpoint boundary that exposed endpoint event filtering."""
import argparse
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/isae/ua2-incidence-periodic-20261101'
BASE=ROOT/'artifacts/isae/ua2-time-endpoint-fix-20261101'
sys.path.insert(0,str(ROOT))
from openswing.bridge import dispatch
from openswing.time_state import checkpoint
from isae_ua2_incidence_periodic import grid,windows
from isae_ua_artifacts import write_trajectory


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('boundary','continuation'))
    args=parser.parse_args();folder=BASE/args.action
    assert not folder.exists();folder.mkdir(parents=True)
    part=12 if args.action=='boundary' else 13
    parent=OLD/'n640-part11' if part==12 else BASE/'boundary'
    input_path=parent/'trajectory.json.gz'
    with gzip.open(input_path,'rt') as stream:previous=json.load(stream)
    source_plan=OLD/f'n640-part{part:02d}'/'plan.json'
    full=json.loads(source_plan.read_text())['full_request']
    start,end=windows(640)[part];target=grid(640)[end]
    saved=checkpoint(previous)
    request={key:value for key,value in full.items() if key not in ('condition','time')}
    request.update(action='resume_time',checkpoint=saved,time=dict(duration=target-saved['state']['time'],max_steps=4096))
    paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
           ROOT/'scripts/isae_ua2_incidence_periodic.py',ROOT/'scripts/isae_ua_artifacts.py',input_path,source_plan]
    pins={str(p.relative_to(ROOT)):digest(p) for p in paths}
    plan=dict(action=args.action,part=part,steps=end-start,target_time=target,source_sha256=pins,
              native_ASWING_comparison=False,scope='Exact failed checkpoint boundary, same physical equations and tolerances.')
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started=time.monotonic()
    raw=dispatch(request)
    elapsed=time.monotonic()-started
    assert raw['converged'] and raw['accepted_steps']==end-start and raw['rejected_steps']==0
    assert raw['snapshots'][-1]['time']==target
    assert min(r['step'] for r in raw['snapshots'][1:])>1e-5
    assert max(r['residual'] for r in raw['snapshots'])<1e-10
    np.testing.assert_allclose([r['time'] for r in raw['snapshots']],grid(640)[start:end+1],rtol=0,atol=1e-15)
    for key in ('frame','force','circulation_rate'):assert raw['snapshots'][0][key]==previous['snapshots'][-1][key]
    errors=None
    if part==12:
        old_path=OLD/'n640-part12/trajectory.json.gz';pins[str(old_path.relative_to(ROOT))]=digest(old_path)
        with gzip.open(old_path,'rt') as stream:old=json.load(stream)
        assert len(old['snapshots'])==len(raw['snapshots'])
        errors={}
        for key in ('force','circulation_rate','local_velocity','local_acceleration'):
            a=np.array([r[key] for r in raw['snapshots']]);b=np.array([r[key] for r in old['snapshots']])
            errors[key]=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
        assert max(errors.values())<2e-9,errors
    write_trajectory(folder/'trajectory.json.gz',raw)
    assert all(digest(ROOT/n)==h for n,h in pins.items())
    report=dict(passed=True,solver_seconds=elapsed,accepted_steps=raw['accepted_steps'],rejected_steps=raw['rejected_steps'],
                start_time=raw['snapshots'][0]['time'],end_time=raw['snapshots'][-1]['time'],
                minimum_step=min(r['step'] for r in raw['snapshots'][1:]),maximum_residual=max(r['residual'] for r in raw['snapshots']),
                boundary_replay_errors=errors,source_sha256=pins,native_ASWING_comparison=False)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'}))


if __name__=='__main__':main()
