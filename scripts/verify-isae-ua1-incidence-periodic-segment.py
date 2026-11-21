"""Advance 40 steps of one continuous eight-cycle inclined UA-1 trajectory."""
import argparse
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np
from isae_suite_unsteady import model_text
from isae_ua_artifacts import write_trajectory
from isae_ua_incidence_periodic import full_request, GATES, PERIOD, CYCLES

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua1-incidence-periodic-20261101'


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps',type=int,choices=(80,160),required=True)
    parser.add_argument('--part',type=int,required=True)
    args = parser.parse_args()
    if args.part not in range(CYCLES*args.steps//40):
        parser.error('Part outside the continuous eight-cycle history')
    name = f'n{args.steps}-part{args.part:02d}'
    folder = BASE/name
    if folder.exists():
        parser.error('Preserve completed or interrupted evidence')
    sys.path.insert(0,str(ROOT))
    paths = [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        *[ROOT/'scripts'/n for n in ('isae_suite_unsteady.py','isae_ua_artifacts.py','isae_ua_incidence_reference.py','isae_ua_incidence_periodic.py')],
        ROOT/'artifacts/isae/ua1-incidence-20261101/source-review.json',
        BASE/'reference.json', ROOT/'tests/test_isae_ua_incidence_periodic.py',
        ROOT/'.reference/asw_uns_theory.txt',ROOT/'.reference/asw_theory.txt']
    pins = {str(p.relative_to(ROOT)):digest(p) for p in paths}
    for p in paths:
        frozen = BASE/'frozen-code'/p.relative_to(ROOT)
        frozen.parent.mkdir(parents=True,exist_ok=True)
        if frozen.exists(): assert digest(frozen)==pins[str(p.relative_to(ROOT))],p
        else: shutil.copyfile(p,frozen)
    full = full_request(args.steps)
    period = PERIOD
    end = 40*(args.part+1)*period/args.steps
    request = {**full,'time':{**full['time'],'duration':end}}
    parent_inputs = {}
    previous = None
    if args.part:
        from openswing.time_state import checkpoint
        parent = BASE/f'n{args.steps}-part{args.part-1:02d}'
        receipt_path = BASE/(parent.name+'-execution.json')
        assert json.loads(receipt_path.read_text())['exit_code']==0
        parent_plan = json.loads((parent/'plan.json').read_text())
        parent_report = json.loads((parent/'report.json').read_text())
        assert parent_plan['source_sha256']==pins and parent_plan['full_request']==full
        assert parent_report['converged'] and parent_report['accepted_steps']==40
        for p in (parent/'trajectory.json.gz',parent/'plan.json',parent/'report.json',receipt_path):
            parent_inputs[str(p.relative_to(ROOT))]=digest(p)
        with gzip.open(parent/'trajectory.json.gz','rt') as stream:
            raw_parent = json.load(stream)
        previous = raw_parent['snapshots'][-1]
        saved = checkpoint(raw_parent)
        assert saved['older'] is not None
        request = {key:value for key,value in full.items() if key not in ('condition','time')}
        request.update(action='resume_time',checkpoint=saved,
            time=dict(duration=end-saved['state']['time'],max_steps=4*CYCLES*args.steps))
    folder.mkdir(parents=True)
    plan = dict(steps=args.steps,part=args.part,alpha_deg=9.,k=.94,amplitude_ratio=.5,
        full_request=full,source_sha256=pins,parent_sha256=parent_inputs,gates=GATES,
        native_ASWING_comparison=False,scope='Eight continuous cycles from the production steady initial state; full forcing present from startup.',
        registered_rows_before=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started = time.monotonic()
    def progress(*values):
        if len(values)==2 and isinstance(values[0],(int,float)):
            (folder/'progress.json').write_text(json.dumps(dict(time=values[0],steps=values[1],seconds=time.monotonic()-started))+'\n')
    from openswing.bridge import dispatch
    raw = dispatch(request,progress=progress)
    solver_seconds = time.monotonic()-started
    assert raw['converged'] and raw['accepted_steps']==40 and raw['rejected_steps']==0
    samples = raw['snapshots']
    assert abs(samples[-1]['time']-end)<1e-12
    if previous is not None:
        for key in ('force','circulation_rate','frame'):
            assert previous[key]==samples[0][key],key
        assert [r['circulation'] for r in previous['strips']]==[r['circulation'] for r in samples[0]['strips']]
    write_trajectory(folder/'trajectory.json.gz',raw)
    reference_data=json.loads((BASE/'reference.json').read_text())
    assert reference_data['passed']
    source_rows=reference_data['reference']['cold_rows']
    reference_rows=[]
    for s in samples:
        index=round(s['time']/PERIOD*160)
        assert abs(source_rows[index]['time']-s['time'])<1e-12
        reference_rows.append(source_rows[index])
    reference=dict(rows=reference_rows)
    alpha = math.radians(9.)
    direction = np.array([-math.sin(alpha),0.,math.cos(alpha)])
    wind = np.array([math.cos(alpha),0.,math.sin(alpha)])
    qs = .5*1.225*100*200000
    rows = []
    for s,ref in zip(samples,reference['rows']):
        frame = s['frame']
        assert max(abs(x) for x in frame['attitude']+frame['rates_body'])<1e-12
        v = np.array(frame['velocity_origin_body'])
        a = np.array(frame['acceleration_reference_body'])
        p = np.array(frame['position_earth'])
        rows.append(dict(time=s['time'],reference=ref,CL=float(np.array(s['force'])@direction/qs),
            CL_instantaneous=s['CL'],force_coefficient=(np.array(s['force'])/qs).tolist(),
            circulation=[r['circulation'] for r in s['strips']],circulation_rate=s['circulation_rate'],
            heave_velocity=float(v@direction),heave_position=float(p@direction),heave_acceleration=float(a@direction),
            mean_flow_velocity=float(v@wind),residual=s['residual'],order=s['order']))
    assert max(r['residual'] for r in rows)<1e-10
    assert max(abs(r['mean_flow_velocity']+10) for r in rows)<1e-10
    assert max(abs(r['heave_acceleration']-r['reference']['acceleration']) for r in rows)<1e-10
    unchanged = all(digest(ROOT/n)==h for n,h in {**pins,**parent_inputs}.items())
    report = dict(converged=True,accepted_steps=40,rejected_steps=0,solver_seconds=solver_seconds,
        checkpoint_join_exact=True,rows=rows,maximum_residual=max(r['residual'] for r in rows),
        source_unchanged=unchanged,native_ASWING_comparison=False)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(job=name,solver_seconds=solver_seconds,accepted_steps=40,
        end_time=samples[-1]['time'],maximum_residual=report['maximum_residual'],source_unchanged=unchanged)),flush=True)
    if not unchanged: raise SystemExit(1)


if __name__=='__main__':
    main()
