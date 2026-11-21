"""One short segment of an eight-cycle UA-2 cold-start trajectory."""
import argparse
import gzip
from hashlib import sha256
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

import numpy as np
from isae_ua_artifacts import write_trajectory
from isae_ua_wing_periodic import cycle_grid

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('ua_time',ROOT/'scripts/verify-isae-ua-time.py')
UA=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(UA)


def full_request(steps,panels):
    full=UA.make_request(steps=steps,amplitude_ratio=.5,k=.95,aspect_ratio=10.,panels=panels)
    period=full['time']['duration'];grid=cycle_grid(period,steps)
    full['time']['duration']=8*period
    full['time']['forcing']='time Az\n'+'\n'.join(
        f'{t:.17g} {-.25*19**2*math.cos(19*t):.17g}' for t in grid)+'\n'
    return full


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--steps',type=int,choices=(80,160),required=True)
    parser.add_argument('--segment',type=int,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--parent',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if args.output_dir.exists() or args.segment<0 or (args.segment>0)!=(args.parent is not None):
        parser.error('Fresh output and preceding segment required for continuation')
    reference=json.loads(args.reference.read_text());rplan=reference['plan']
    assert reference['numerical_passed'] and rplan['panels']==args.panels
    amplitude,k=rplan['amplitude_ratio'],rplan['k']
    assert amplitude in (.05,.1,.3,.5) and k in (.475,.95)
    assert rplan['span']==10. and rplan['chord']==1. and rplan['speed']==10.
    grid=reference['grids'][str(args.steps)]
    start_index=args.segment*32;end_index=min(start_index+32,len(grid)-1)
    if start_index>=len(grid)-1:parser.error('Segment outside declared grid')
    assert rplan['cycles']==8 and amplitude==.5 and k==.95
    full=full_request(args.steps,args.panels)
    actual_grid=[float(line.split()[0]) for line in full['time']['forcing'].splitlines()[1:]]
    assert actual_grid==grid
    source_paths=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__).resolve(),
        ROOT/'scripts/verify-isae-ua-time.py',ROOT/'scripts/isae_suite_unsteady.py',ROOT/'scripts/isae_ua_artifacts.py']
    pins=dict(rplan['source_sha256'])
    pins.update({str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in source_paths})
    pins[str(args.reference.resolve().relative_to(ROOT))]=sha256(args.reference.read_bytes()).hexdigest()
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    sys.path.insert(0,str(ROOT));parent_last=None;parent_hashes={}
    request=dict(full,time=dict(full['time'],duration=grid[end_index]))
    if args.parent is not None:
        from openswing.time_state import checkpoint
        previous_plan=json.loads((args.parent/'plan.json').read_text())
        previous_report=json.loads((args.parent/'report.json').read_text())
        assert previous_plan['segment']==args.segment-1 and previous_plan['source_sha256']==pins
        assert previous_plan['steps']==args.steps and previous_plan['panels']==args.panels
        assert previous_report['converged'] and previous_report['rejected_steps']==0
        with gzip.open(args.parent/'trajectory.json.gz','rt') as stream:parent=json.load(stream)
        saved=checkpoint(parent);parent_last=parent['snapshots'][-1]
        assert saved['older'] is not None and abs(saved['state']['time']-grid[start_index])<1e-13
        request={key:value for key,value in full.items() if key not in ('time','condition')}
        request.update(action='resume_time',checkpoint=saved,time=dict(duration=grid[end_index]-saved['state']['time'],max_steps=640))
        parent_hashes={n:sha256((args.parent/n).read_bytes()).hexdigest() for n in ('plan.json','report.json','trajectory.json.gz')}
    args.output_dir.mkdir(parents=True)
    plan=dict(panels=args.panels,steps=args.steps,segment=args.segment,amplitude_ratio=amplitude,k=k,cycles=8,
        grid=grid,start_index=start_index,end_index=end_index,source_sha256=pins,
        reference=str(args.reference.resolve()),parent=None if args.parent is None else str(args.parent.resolve()),
        parent_sha256=parent_hashes,full_request=full,
        request_without_checkpoint={k:v for k,v in request.items() if k!='checkpoint'},
        native_ASWING_comparison=False,independent_spatial_reference=True)
    (args.output_dir/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started=time.monotonic()
    def progress(*values):
        if len(values)==2 and isinstance(values[0],(int,float)):
            (args.output_dir/'progress.json').write_text(json.dumps(dict(time=values[0],accepted_steps=values[1],seconds=time.monotonic()-started))+'\n')
    try:
        from openswing.bridge import dispatch
        result=dispatch(request,progress=progress);seconds=time.monotonic()-started
        assert result['converged'] and result['rejected_steps']==0 and result['accepted_steps']==end_index-start_index
        samples=result['snapshots'];assert abs(samples[-1]['time']-grid[end_index])<1e-13
        assert all(s['order']==2 for s in samples[(2 if args.segment==0 else 1):])
        join=0.
        if parent_last is not None:
            join=max(float(np.max(np.abs(np.asarray(parent_last[n])-np.asarray(samples[0][n])))) for n in ('force','circulation_rate'))
            assert join<1e-12 and [r['circulation'] for r in parent_last['strips']]==[r['circulation'] for r in samples[0]['strips']]
        before=time.monotonic();write_trajectory(args.output_dir/'trajectory.json.gz',result);persistence=time.monotonic()-before
        ref_rows=reference['reference']['DOP853']['cold']['rows'];ref_times=np.asarray([r['time'] for r in ref_rows])
        errors=[]
        for sample in samples:
            index=int(np.argmin(abs(ref_times-sample['time'])))
            assert abs(ref_times[index]-sample['time'])<1e-12
            errors.append(sample['force'][2]/(.5*1.225*100*10)-ref_rows[index]['CL'])
        scale=max(abs(r['CL']) for r in ref_rows)
        report=dict(status='computed_segment',converged=True,seconds=seconds,persistence_seconds=persistence,
            accepted_steps=result['accepted_steps'],rejected_steps=result['rejected_steps'],jacobian_builds=result['jacobian_builds'],
            maximum_residual=max(s['residual'] for s in samples),checkpoint_boundary_jump=join,
            segment_lift_error_fraction_of_full_history_peak=max(map(abs,errors))/scale,
            structural_operator=result['structural_operator'],temporal_policy=result['temporal_policy'],
            source_unchanged=all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items()))
        assert report['maximum_residual']<1e-10 and report['source_unchanged']
        (args.output_dir/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps(report),flush=True)
    except Exception as error:
        (args.output_dir/'failure.json').write_text(json.dumps(dict(error=str(error),traceback=traceback.format_exc()),indent=2)+'\n')
        raise


if __name__=='__main__':main()
