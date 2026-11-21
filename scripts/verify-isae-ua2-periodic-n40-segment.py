"""Advance 16 steps of the continuous 40-strip, eight-cycle UA-2 history."""
import argparse
import gzip
import gc
import resource
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
from isae_ua2_incidence_periodic_n40 import full_request, GATES, PERIOD, CYCLES, grid, windows, STEPS

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua2-incidence-periodic-n40-20261101'


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--part',type=int,required=True)
    args=parser.parse_args();args.steps=STEPS
    if args.part not in range(len(windows())):parser.error('Part outside the full eight-cycle history')
    name=f'part{args.part:03d}';folder=BASE/'production'/name
    if folder.exists():parser.error('Preserve completed or interrupted evidence')
    sys.path.insert(0,str(ROOT))
    batch_path=BASE/'production-plan.json';batch=json.loads(batch_path.read_text())
    pins=dict(batch['source_sha256']);pins[str(batch_path.relative_to(ROOT))]=digest(batch_path)
    for n,h in pins.items():assert digest(ROOT/n)==h,n
    reference_index=json.loads((BASE/'reference-verified.json').read_text());assert reference_index['passed']
    target=reference_index['reference_parts'][str(args.part)]
    target_path=BASE/target['path'];assert digest(target_path)==target['sha256']
    full=full_request();times=grid();period=PERIOD
    start_index,end_index=windows()[args.part];expected_steps=end_index-start_index;end=times[end_index]
    assert full==batch['full_request'] and batch['gates']==GATES
    request={**full,'time':{**full['time'],'duration':end}}
    parent_inputs = {str(target_path.relative_to(ROOT)):target['sha256']}
    previous = None
    if args.part:
        from openswing.time_state import checkpoint
        parent=BASE/'production'/f'part{args.part-1:03d}'
        receipt_path=BASE/'production'/(parent.name+'-execution.json')
        assert json.loads(receipt_path.read_text())['exit_code']==0
        parent_plan = json.loads((parent/'plan.json').read_text())
        parent_report = json.loads((parent/'report.json').read_text())
        assert parent_plan['source_sha256']==pins and parent_plan['full_request']==full
        assert parent_report['converged'] and parent_report['accepted_steps']==16 and parent_report['rejected_steps']==0
        assert digest(parent/'report.json')==json.loads(receipt_path.read_text())['report_sha256']
        for p in (parent/'trajectory.json.gz',parent/'plan.json',parent/'report.json',receipt_path):
            parent_inputs[str(p.relative_to(ROOT))]=digest(p)
        with gzip.open(parent/'trajectory.json.gz','rt') as stream:
            raw_parent = json.load(stream)
        previous = raw_parent['snapshots'][-1]
        saved = checkpoint(raw_parent)
        assert saved['older'] is not None
        assert saved['state']['time']==times[start_index]
        del raw_parent
        gc.collect()
        request = {key:value for key,value in full.items() if key not in ('condition','time')}
        request.update(action='resume_time',checkpoint=saved,
            time=dict(duration=end-saved['state']['time'],max_steps=4*CYCLES*args.steps))
    folder.mkdir(parents=True)
    plan = dict(steps=args.steps,part=args.part,alpha_deg=9.,k=.95,amplitude_ratio=.5,
        full_request=full,source_sha256=pins,parent_sha256=parent_inputs,gates=GATES,
        native_ASWING_comparison=False,scope='Eight continuous cycles from production steady equilibrium at40 strips; unchanged fine temporal grid and complete forcing from startup.',
        registered_rows_before=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started = time.monotonic()
    def progress(*values):
        if len(values)==2 and isinstance(values[0],(int,float)):
            (folder/'progress.json').write_text(json.dumps(dict(time=values[0],steps=values[1],seconds=time.monotonic()-started))+'\n')
    from openswing.bridge import dispatch
    raw = dispatch(request,progress=progress)
    solver_seconds = time.monotonic()-started
    assert raw['converged'] and raw['accepted_steps']==expected_steps and raw['rejected_steps']==0
    samples = raw['snapshots']
    assert samples[-1]['time']==end
    assert all(len(s['strips'])==40 for s in samples)
    if previous is not None:
        for key in ('force','circulation_rate','frame'):
            assert previous[key]==samples[0][key],key
        assert [r['circulation'] for r in previous['strips']]==[r['circulation'] for r in samples[0]['strips']]
    write_trajectory(folder/'trajectory.json.gz',raw)
    target_data=json.loads(target_path.read_text())
    assert target_data['job']==dict(part=args.part,start_index=start_index,end_index=end_index)
    reference=dict(rows=target_data['rows'])
    assert len(samples)==len(reference['rows'])
    np.testing.assert_allclose([s['time'] for s in samples],[r['time'] for r in reference['rows']],rtol=0,atol=1e-12)
    alpha = math.radians(9.)
    direction = np.array([-math.sin(alpha),0.,math.cos(alpha)])
    wind = np.array([math.cos(alpha),0.,math.sin(alpha)])
    qs = .5*1.225*100*10
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
    report = dict(converged=True,accepted_steps=expected_steps,rejected_steps=0,solver_seconds=solver_seconds,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        checkpoint_join_exact=True,rows=rows,maximum_residual=max(r['residual'] for r in rows),
        source_unchanged=unchanged,native_ASWING_comparison=False)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(job=name,solver_seconds=solver_seconds,accepted_steps=expected_steps,
        end_time=samples[-1]['time'],maximum_residual=report['maximum_residual'],source_unchanged=unchanged)),flush=True)
    if not unchanged: raise SystemExit(1)


if __name__=='__main__':
    main()
