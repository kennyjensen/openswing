"""Memory-bounded FFWT-4 Fixed-1 continuation; stream JSON instead of copying it."""
import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('ffwt4_initial',ROOT/'scripts/verify-isae-ffwt4-initial.py')
initial=importlib.util.module_from_spec(spec);spec.loader.exec_module(initial)
pin=initial.pin


def write(path,value):
    # Avoid materializing a second, indented copy of an entire history.
    temporary=path.with_name(path.name+'.partial')
    with temporary.open('w') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')
    temporary.replace(path)
DT=Decimal('.0149')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--initial-from',type=Path)
    ap.add_argument('--resume-from',type=Path)
    ap.add_argument('--steps',type=int,default=20)
    args=ap.parse_args()
    assert bool(args.initial_from)!=bool(args.resume_from) and 1<=args.steps<=30
    folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=False)
    if args.initial_from:
        parent=args.initial_from.resolve()
        base=json.loads((parent/'plan.json').read_text())
        request=json.loads((parent/'request.json').read_text())
        report=json.loads((parent/'report.json').read_text())
        assert report['status']=='INITIAL_COMPARISON_COMPUTED' and report['residual']<=1e-8
        assert pin(parent/'result.json')==report['result']
        # A fresh equilibrium includes the gust in its condition identity.
        # It is exactly zero on the wing at startup; no saved state is edited.
        request.update(action='time',mode='time')
        request.pop('tolerance');request.pop('continuation_steps')
        request['condition']['gust']=dict(type='cosine',amplitude=[0.,0.,.6978],
            origin=[-10.9366,0.,0.],normal=[-1.,0.,0.],length=10.9366,speed=0.)
        request['time']=dict(frame='prescribed',duration=float(DT*args.steps),dt=float(DT),
            order=2,tolerance=1e-8,continuation_steps=4,max_steps=args.steps)
        plan=dict(schema='isae-ffwt4-fixed1-time-v1',source_pins=base['source_pins'],
            kernel_pins=base['kernel_pins'],nominal=base['nominal'],helper=pin(__file__),
            initial_plan=pin(parent/'plan.json'),initial_result=report['result'],initial_report=pin(parent/'report.json'),
            initial_helper=base['helper'],initial_moment=report['predicted'],
            qualifications=base['qualifications']+[
                'Gust parameters remain the literal first GMOD values; H is onset-to-peak length.',
                'BDF2 with BDF1 startup, dt=.0149, prescribed zero frame accelerations; segment resumes preserve history.',
                'The first archive contains 200 rows including t=0, ending at step199. Other seven fixed histories remain unrun.',
                'Pointwise circulation and nominal mesh remain declared; native spacing/mode defaults are not authenticated.'],
            start_step=0,end_step=args.steps,native_slots=200,fixed_history_slots=base['fixed_history_slots'],
            full_family_validated=False)
    else:
        parent=args.resume_from.resolve()
        plan=json.loads((parent/'plan.json').read_text())
        report=json.loads((parent/'report.json').read_text())
        assert report['status']=='SEGMENT_COMPUTED' and report['rejected_steps']==0
        assert pin(parent/'checkpoint.json')==report['checkpoint'] and pin(parent/'result.json')==report['result']
        saved=json.loads((parent/'checkpoint.json').read_text())
        start=plan['end_step'];assert abs(saved['state']['time']-float(start*DT))<1e-10
        plan.update(start_step=start,end_step=start+args.steps,parent_plan=pin(parent/'plan.json'),
                    parent_report=pin(parent/'report.json'),parent_checkpoint=report['checkpoint'])
        request=dict(action='resume_time',source=Path(plan['source_pins'][0]['path']).read_text(),
            numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
            checkpoint=saved,time=dict(duration=float(DT*args.steps),dt=float(DT),order=2))
    assert plan['end_step']<=199
    previous_helper=plan['helper']
    assert pin(previous_helper['path'])==previous_helper
    plan.update(parent_time_helper=previous_helper,helper=pin(__file__),continuation_writer_version=2)
    for p in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['initial_helper']]:assert pin(p['path'])==p
    write(folder/'plan.json',plan);write(folder/'request.json',request)
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    started=time.monotonic()
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*event):
            stream.write(json.dumps(dict(seconds=time.monotonic()-started,event=event))+'\n');stream.flush()
        result=dispatch(request,progress=progress)
    write(folder/'result.json',result)
    assert result['converged'] and result['rejected_steps']==0 and result['accepted_steps']==args.steps
    assert len(result['snapshots'])==args.steps+1
    for i,s in enumerate(result['snapshots']):
        assert abs(s['time']-float((plan['start_step']+i)*DT))<1e-10
        assert s['converged'] and s['residual']<=1e-8
        if i:
            expected_order=1 if plan['start_step']+i==1 else 2
            assert s['restart']['accepted_method']['effective_order']==expected_order
        assert next(v for v in s['sensors'] if v['index']==1)['load_trace']=='left'
    if args.initial_from:
        root=next(v for v in result['snapshots'][0]['sensors'] if v['index']==1)
        assert abs(root['moment_local'][0]-plan['initial_moment'])<1e-8
    else:assert result['checkpoint_validation']['discrete_replayed']
    write(folder/'checkpoint.json',checkpoint(result,-1))
    for p in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['initial_helper']]:assert pin(p['path'])==p
    report=dict(status='SEGMENT_COMPUTED',seconds=time.monotonic()-started,
        start_step=plan['start_step'],end_step=plan['end_step'],accepted_steps=result['accepted_steps'],
        rejected_steps=result['rejected_steps'],maximum_residual=max(s['residual'] for s in result['snapshots']),
        result=pin(folder/'result.json'),checkpoint=pin(folder/'checkpoint.json'),
        source_pins_unchanged=True,kernel_pins_unchanged=True,full_family_validated=False)
    write(folder/'report.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
