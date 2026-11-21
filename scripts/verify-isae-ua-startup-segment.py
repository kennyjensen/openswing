"""Two short, checkpoint-connected parts of one graded-grid UA-2 trajectory."""
import argparse
import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

from isae_ua_artifacts import write_trajectory
from isae_ua_startup import heave_grid

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ua_time_request',ROOT/'scripts/verify-isae-ua-time.py')
UA = importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(UA)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--k',type=float,choices=(.475,.95),required=True)
    parser.add_argument('--part',choices=('start','finish'),required=True)
    parser.add_argument('--parent',type=Path)
    parser.add_argument('--parent-driver',type=Path,
        help='Preserved producer driver if its validation-only code changed; production/helper hashes must still match.')
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or (args.part=='finish') != (args.parent is not None):
        parser.error('Use a fresh output directory and supply a parent only for the finish part')
    reference_path = ROOT/f'artifacts/isae/ua2-time-20261101/reference-n{args.panels}.json'
    reference = json.loads(reference_path.read_text())
    assert reference['numerical_passed'] and reference['unchanged_code']
    for name,digest in reference['source_sha256'].items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    full_request = UA.make_request(steps=160,amplitude_ratio=.001,k=args.k,
        aspect_ratio=10.,panels=args.panels,startup_subdivisions=256,startup_growth=1.125)
    period = full_request['time']['duration']
    grid = heave_grid(period,160,256,1.125)
    cut = 32
    request = dict(full_request,time=dict(full_request['time']))
    pins = dict(reference['source_sha256'])
    for path in (Path(__file__).resolve(),ROOT/'scripts/verify-isae-ua-time.py',
            ROOT/'scripts/isae_ua_startup.py',ROOT/'scripts/isae_ua_artifacts.py',reference_path):
        pins[str(path.relative_to(ROOT))] = sha256(path.read_bytes()).hexdigest()
    sys.path.insert(0,str(ROOT))
    if args.part == 'start':
        request['time']['duration'] = grid[cut]
        start_time,end_time,expected_steps = 0.,grid[cut],cut
    else:
        from openswing.time_state import checkpoint
        parent_plan = json.loads((args.parent/'plan.json').read_text())
        parent_report = json.loads((args.parent/'report.json').read_text())
        assert parent_plan['part']=='start' and parent_plan['k']==args.k
        assert parent_plan['panels']==args.panels and parent_report['converged']
        assert parent_report['accepted_steps']==cut and parent_report['rejected_steps']==0
        for name,digest in parent_plan['source_sha256'].items():
            path=ROOT/name
            if name==str(Path(__file__).resolve().relative_to(ROOT)) and args.parent_driver is not None:
                path=args.parent_driver.resolve()
                pins[str(path.relative_to(ROOT))]=sha256(path.read_bytes()).hexdigest()
            assert sha256(path.read_bytes()).hexdigest()==digest,name
        with gzip.open(args.parent/'trajectory.json.gz','rt') as stream:
            parent = json.load(stream)
        saved = checkpoint(parent)
        assert saved['older'] is not None and saved['state']['time']==grid[cut]
        del parent
        request.update(action='resume_time',checkpoint=saved,
            time=dict(duration=period-grid[cut],max_steps=640))
        request.pop('condition')  # The checkpoint owns its physical operating condition.
        start_time,end_time,expected_steps = grid[cut],period,len(grid)-1-cut
        for name in ('plan.json','report.json','trajectory.json.gz'):
            path = (args.parent/name).resolve()
            pins[str(path.relative_to(ROOT))] = sha256(path.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True)
    # The checkpoint itself is retained in the parent trajectory; keep the
    # request manifest compact while recording that exact parent's hashes.
    plan = dict(part=args.part,parent=None if args.parent is None else str(args.parent),
        k=args.k,panels=args.panels,full_period=period,amplitude_ratio=.001,
        grid=grid,cut_index=cut,start_time=start_time,end_time=end_time,expected_steps=expected_steps,
        full_request=full_request,request_without_checkpoint={k:v for k,v in request.items() if k!='checkpoint'},
        source_sha256=pins,maximum_growth=1.125,first_step_subdivisions=256,
        native_ASWING_comparison=False,independent_spatial_physics_reference=False,
        gate='Combined full trajectory: lift error <0.1%; per-strip peak-normalized rate error <0.1%; first-step relative rate error <1%.',
        source='Unsteady Eqs123-125; source Euler/BDF history retained across the split; no replacement forcing.')
    (args.output_dir/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started = time.monotonic()
    def progress(*values):
        if len(values)==2 and isinstance(values[0],(float,int)):
            status=dict(time=values[0],accepted_steps=values[1],seconds=time.monotonic()-started)
            (args.output_dir/'progress.json').write_text(json.dumps(status)+'\n')
            if values[1]%10==0:print(json.dumps(status),flush=True)
    try:
        from openswing.bridge import dispatch
        result = dispatch(request,progress=progress)
        elapsed = time.monotonic()-started
        assert result['converged'] and result['rejected_steps']==0
        assert result['accepted_steps']==expected_steps
        assert abs(result['snapshots'][-1]['time']-end_time)<1e-13
        if args.part=='finish':
            assert all(s['order']==2 for s in result['snapshots'][1:]),'Checkpoint lost BDF2 history'
        persistence_start=time.monotonic()
        write_trajectory(args.output_dir/'trajectory.json.gz',result)
        persistence_seconds=time.monotonic()-persistence_start
        stable=all(sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in pins.items())
        report=dict(status='computed_segment',converged=True,part=args.part,seconds=elapsed,
            persistence_seconds=persistence_seconds,start_time=start_time,end_time=end_time,
            accepted_steps=result['accepted_steps'],rejected_steps=result['rejected_steps'],
            jacobian_builds=result['jacobian_builds'],maximum_residual=max(s['residual'] for s in result['snapshots']),
            source_unchanged=stable,checkpoint_history_retained=args.part=='start' or result['snapshots'][1]['order']==2,
            structural_operator=result['structural_operator'],temporal_policy=result['temporal_policy'],
            reference_comparison='Pending combined full-trajectory audit')
        (args.output_dir/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
        if not stable:raise SystemExit(1)
    except Exception as error:
        (args.output_dir/'failure.json').write_text(json.dumps(dict(error=str(error),traceback=traceback.format_exc()),indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
