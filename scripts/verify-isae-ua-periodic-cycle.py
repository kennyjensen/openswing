"""Advance one UA-1 heave cycle, keeping the original forcing and BDF history."""
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
from isae_ua_periodic import periodic_reference, fourier, phase_difference
from isae_ua_section_reference import section_load

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ua_time_request', ROOT/'scripts/verify-isae-ua-time.py')
UA = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(UA)


def full_request(steps, amplitude_ratio, k=.95, cycles=8):
    request = UA.make_request(steps=steps, amplitude_ratio=amplitude_ratio, k=k)
    period = request['time']['duration']
    knots = [period*i/steps for i in range(steps*cycles+1)]
    request['time']['forcing'] = 'time Az\n'+'\n'.join(
        f'{t:.17g} {-amplitude_ratio/2*(20*k)**2*math.cos(20*k*t):.17g}' for t in knots)+'\n'
    return request


def resume_request(request, saved, end_time):
    resumed = {key:value for key,value in request.items() if key not in ('time','condition')}
    resumed.update(action='resume_time', checkpoint=saved,
        time=dict(duration=end_time-saved['state']['time'], max_steps=request['time']['max_steps']))
    return resumed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=int, choices=(80,160), required=True)
    parser.add_argument('--amplitude-ratio', type=float, choices=(.05,.1,.3,.5), required=True)
    parser.add_argument('--cycle', type=int, choices=range(1,9), required=True)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() or (args.cycle>1)!=(args.parent is not None):
        parser.error('Use a fresh output directory and the preceding cycle for resume')
    full = full_request(args.steps, args.amplitude_ratio)
    period = full['time']['duration']; end_time = period*args.cycle
    source_paths = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__).resolve(),
        *[ROOT/'scripts'/name for name in ('verify-isae-ua-time.py','isae_suite_unsteady.py',
            'isae_ua_artifacts.py','isae_ua_periodic.py','isae_ua_section_reference.py')],
        ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    pins = {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in source_paths}
    sys.path.insert(0,str(ROOT))
    request = full; parent_rows = None; parent_hashes = {}
    if args.parent is not None:
        from openswing.time_state import checkpoint
        parent_plan = json.loads((args.parent/'plan.json').read_text())
        parent_report = json.loads((args.parent/'report.json').read_text())
        assert parent_plan['cycle']==args.cycle-1 and parent_plan['steps']==args.steps
        assert parent_plan['amplitude_ratio']==args.amplitude_ratio
        assert parent_plan['source_sha256']==pins
        assert parent_report['converged'] and parent_report['rejected_steps']==0
        with gzip.open(args.parent/'trajectory.json.gz','rt') as stream:
            parent = json.load(stream)
        parent_rows = parent['snapshots']; saved = checkpoint(parent)
        assert saved['older'] is not None
        request = resume_request(full, saved, end_time)
        parent_hashes = {name:sha256((args.parent/name).read_bytes()).hexdigest()
                         for name in ('plan.json','report.json','trajectory.json.gz')}
    args.output_dir.mkdir(parents=True)
    plan = dict(cycle=args.cycle, total_cycles=8, steps=args.steps, amplitude_ratio=args.amplitude_ratio,
        k=.95, aspect_ratio=200000., panels=4, period=period, end_time=end_time,
        parent=None if args.parent is None else str(args.parent), parent_sha256=parent_hashes,
        full_request=full, request_without_checkpoint={k:v for k,v in request.items() if k!='checkpoint'},
        source_sha256=pins, native_ASWING_comparison=False,
        source='Same published nonlinear attached-flow section equations; zero-circulation cold start, eight continuous cycles.',
        qualifications=['Infinite-span reconstruction; not a native ASWING deck.',
                        'No forcing replacement, state correction or restart-history reset between cycles.'])
    (args.output_dir/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started = time.monotonic()
    def progress(*values):
        if len(values)==2 and isinstance(values[0],(int,float)):
            row=dict(time=values[0], accepted_steps=values[1],seconds=time.monotonic()-started)
            (args.output_dir/'progress.json').write_text(json.dumps(row)+'\n')
    try:
        from openswing.bridge import dispatch
        raw = dispatch(request,progress=progress)
        seconds=time.monotonic()-started
        assert raw['converged'] and raw['rejected_steps']==0
        assert raw['accepted_steps']==args.steps
        snapshots=raw['snapshots']
        assert abs(snapshots[-1]['time']-end_time)<1e-12
        assert all(s['order']==2 for s in snapshots[(2 if args.cycle==1 else 1):])
        join=0.
        if parent_rows is not None:
            join=max(float(np.max(np.abs(np.asarray(parent_rows[-1][key])-np.asarray(snapshots[0][key]))))
                     for key in ('force','circulation_rate'))
            assert join<1e-12
            assert [r['circulation'] for r in parent_rows[-1]['strips']]==[r['circulation'] for r in snapshots[0]['strips']]
        write_start=time.monotonic()
        write_trajectory(args.output_dir/'trajectory.json.gz',raw)
        persistence=time.monotonic()-write_start
        local_times=np.asarray([s['time']-(args.cycle-1)*period for s in snapshots])
        expected=periodic_reference(local_times,amplitude_ratio=args.amplitude_ratio,k=.95)
        periodic=np.asarray([r['CL'] for r in expected['rows']])
        cold=[]
        for s,row in zip(snapshots,expected['rows']):
            gamma=row['circulation']-expected['initial_circulation']*math.exp(-5*s['time'])
            cold.append(section_load(gamma,row['velocity'],row['acceleration'],speed=10.)['CL'])
        actual=np.asarray([s['force'][2]/(.5*1.225*100*200000) for s in snapshots])
        norm=float(np.max(np.abs(periodic)))
        measured=fourier(local_times,actual,period); reference=fourier(local_times,periodic,period)
        a,b=measured['harmonics'][0],reference['harmonics'][0]
        change=None if parent_rows is None else float(np.max(np.abs(actual-np.asarray([
            s['force'][2]/(.5*1.225*100*200000) for s in parent_rows])))/norm)
        report=dict(status='computed_cycle',converged=True,cycle=args.cycle,seconds=seconds,
            persistence_seconds=persistence,accepted_steps=raw['accepted_steps'],rejected_steps=raw['rejected_steps'],
            jacobian_builds=raw['jacobian_builds'],maximum_residual=max(s['residual'] for s in snapshots),
            checkpoint_boundary_jump=join, previous_cycle_waveform_change_fraction=change,
            cold_waveform_error_fraction=float(np.max(np.abs(actual-cold))/norm),
            periodic_waveform_error_fraction=float(np.max(np.abs(actual-periodic))/norm),
            amplitude_error_fraction=a['amplitude']/b['amplitude']-1,
            phase_error_deg=phase_difference(a['phase_deg'],b['phase_deg']),
            mean_error_peak_fraction=(measured['mean']-reference['mean'])/norm,
            measured=measured,reference=reference,reference_peak=norm,
            source_unchanged=all(sha256((ROOT/name).read_bytes()).hexdigest()==h for name,h in pins.items()),
            structural_operator=raw['structural_operator'],temporal_policy=raw['temporal_policy'])
        assert report['source_unchanged'] and report['maximum_residual']<1e-10
        (args.output_dir/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('measured','reference')}),flush=True)
    except Exception as error:
        (args.output_dir/'failure.json').write_text(json.dumps(dict(error=str(error),traceback=traceback.format_exc()),indent=2)+'\n')
        raise


if __name__=='__main__':
    main()
