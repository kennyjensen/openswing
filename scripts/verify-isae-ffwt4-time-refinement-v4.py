"""Full FFWT-4 spatial/time histories on authenticated meshes, in at most ten-step jobs."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
NATIVE_DT=Decimal('.0149')


from isae_ffwt4_evidence import KernelArchive, pin, read, write


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    parent=ap.add_mutually_exclusive_group(required=True)
    parent.add_argument('--initial-from',type=Path)
    parent.add_argument('--resume-from',type=Path)
    ap.add_argument('--divisor',type=int,choices=(2,4,8,16))
    ap.add_argument('--steps',type=int,default=10)
    ap.add_argument('--kernel-archive',type=Path)
    args=ap.parse_args();assert 1<=args.steps<=10
    folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=False)
    if args.initial_from:
        parent=args.initial_from.resolve();base=read(parent/'plan.json')
        request=read(parent/'request.json');report=read(parent/'report.json')
        assert report['status']=='INITIAL_COMPARISON_COMPUTED' and report['residual']<=1e-8
        assert pin(parent/'result.json')==report['result']
        if args.kernel_archive is None:ap.error('--kernel-archive is required for a new history')
        archive=KernelArchive(args.kernel_archive.resolve(),base['kernel_pins'])
        divisor=args.divisor or 8;dt=NATIVE_DT/divisor
        request.update(action='time',mode='time')
        request.pop('tolerance');request.pop('continuation_steps')
        request['condition']['gust']=dict(type='cosine',amplitude=[0.,0.,.6978],
            origin=[-10.9366,0.,0.],normal=[-1.,0.,0.],length=10.9366,speed=0.)
        request['time']=dict(frame='prescribed',duration=float(dt*args.steps),dt=float(dt),
            order=2,tolerance=1e-8,continuation_steps=4,max_steps=args.steps)
        plan=dict(schema='isae-ffwt4-fixed1-refinement-v3',source_pins=base['source_pins'],
            kernel_pins=base['kernel_pins'],nominal=base['nominal'],helper=pin(__file__),
            kernel_archive=archive.manifest_pin,runtime_kernel_pins=archive.runtime_pins,
            evidence_helper=pin(ROOT/'scripts/isae_ffwt4_evidence.py'),
            initial_plan=pin(parent/'plan.json'),initial_request=pin(parent/'request.json'),
            initial_result=report['result'],initial_report=pin(parent/'report.json'),
            initial_helper=base['helper'],initial_moment=report['predicted'],
            divisor=divisor,dt=str(dt),native_dt=str(NATIVE_DT),
            accuracy_gate=dict(relative=.001,normalization='Maximum fine-grid magnitude over all 200 common native ticks, separately for root moment and its increment from t=0.'),
            qualifications=[
                'Literal FFWT_Fixed.asw, original first gust, speed22/alpha6 and left root sensor trace are retained.',
                'Historical node positions and complete operating defaults remain unrecovered; declared cosine meshes retain mandatory stations.',
                f"Independent cold equilibrium and full BDF startup at nominal{base['nominal']}; no state transfer between meshes.",
                'BDF2 uses BDF1 only at the first physical step; continuation checkpoints retain predecessor history.',
                'Both spatial and temporal accuracy need complete histories on controlled comparison grids.',
                'Native comparisons use exact common ticks, without interpolation or fitted phase/amplitude.',
                'The eight fixed histories retain 1600 required scalar values; this study computes Fixed-1 only.',
                'The full 138-file kernel archive is unchanged from the earlier time and initial spatial studies.',
                'Full snapshots are retained with lossless gzip compression; partial prefixes cannot certify full-history accuracy.'],
            start_step=0,end_step=args.steps,native_slots=200,fixed_history_slots=1600,
            full_family_validated=False)
    else:
        parent=args.resume_from.resolve();plan=read(parent/'plan.json');report=read(parent/'report.json')
        assert plan['schema']=='isae-ffwt4-fixed1-refinement-v3'
        assert args.divisor is None or args.divisor==plan['divisor']
        if args.kernel_archive is not None:assert str(args.kernel_archive.resolve())==plan['kernel_archive']['path']
        archive=KernelArchive(plan['kernel_archive']['path'],plan['kernel_pins'])
        assert archive.manifest_pin==plan['kernel_archive'] and archive.runtime_pins==plan['runtime_kernel_pins']
        assert pin(ROOT/'scripts/isae_ffwt4_evidence.py')==plan['evidence_helper']
        divisor=plan['divisor'];dt=Decimal(plan['dt']);assert dt*divisor==NATIVE_DT
        assert report['status']=='SEGMENT_COMPUTED' and report['rejected_steps']==0
        assert pin(parent/'checkpoint.json')==report['checkpoint'] and pin(parent/'result.json.gz')==report['result']
        assert pin(plan['helper']['path'])==plan['helper']
        plan.update(parent_time_helper=plan['helper'],helper=pin(__file__))
        saved=read(parent/'checkpoint.json');start=plan['end_step']
        assert abs(saved['state']['time']-float(start*dt))<1e-10
        plan.update(start_step=start,end_step=start+args.steps,parent_plan=pin(parent/'plan.json'),
                    parent_report=pin(parent/'report.json'),parent_checkpoint=report['checkpoint'])
        request=dict(action='resume_time',source=Path(plan['source_pins'][0]['path']).read_text(),
            numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
            checkpoint=saved,time=dict(duration=float(dt*args.steps),dt=float(dt),order=2))
    assert plan['end_step']<=199*divisor
    pins=plan['source_pins']+plan['runtime_kernel_pins']+[plan['kernel_archive'],plan['evidence_helper']]+[plan[k] for k in
        ('helper','initial_helper','initial_plan','initial_request','initial_result','initial_report')]
    if 'parent_time_helper' in plan:pins.append(plan['parent_time_helper'])
    for p in pins:assert pin(p['path'])==p
    write(folder/'plan.json',plan);write(folder/'request.json',request)
    archive.activate()
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    started=time.monotonic()
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*event):
            stream.write(json.dumps(dict(seconds=time.monotonic()-started,event=event))+'\n');stream.flush()
        result=dispatch(request,progress=progress)
    write(folder/'result.json.gz',result)
    assert result['converged'] and result['rejected_steps']==0 and result['accepted_steps']==args.steps
    assert len(result['snapshots'])==args.steps+1
    for i,snapshot in enumerate(result['snapshots']):
        tick=plan['start_step']+i
        assert abs(snapshot['time']-float(tick*dt))<1e-10
        assert snapshot['converged'] and snapshot['residual']<=1e-8
        if i:assert snapshot['restart']['accepted_method']['effective_order']==(1 if tick==1 else 2)
        sensors=[v for v in snapshot['sensors'] if v['index']==1]
        assert len(sensors)==1 and sensors[0]['load_trace']=='left'
    if args.initial_from:
        root=next(v for v in result['snapshots'][0]['sensors'] if v['index']==1)
        assert abs(root['moment_local'][0]-plan['initial_moment'])<1e-8
    else:assert result['checkpoint_validation']['discrete_replayed']
    write(folder/'checkpoint.json',checkpoint(result,-1))
    for p in pins:assert pin(p['path'])==p
    report=dict(status='SEGMENT_COMPUTED',seconds=time.monotonic()-started,
        nominal=plan['nominal'],start_step=plan['start_step'],end_step=plan['end_step'],dt=str(dt),
        accepted_steps=result['accepted_steps'],rejected_steps=result['rejected_steps'],
        maximum_residual=max(s['residual'] for s in result['snapshots']),
        request=pin(folder/'request.json'),result=pin(folder/'result.json.gz'),checkpoint=pin(folder/'checkpoint.json'),
        kernel_archive=archive.manifest_pin,loaded_kernel_modules=archive.loaded_modules(),
        source_pins_unchanged=True,kernel_pins_unchanged=True,full_family_validated=False)
    write(folder/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('loaded_kernel_modules','request','result','checkpoint','kernel_archive')}),flush=True)


if __name__=='__main__':main()

