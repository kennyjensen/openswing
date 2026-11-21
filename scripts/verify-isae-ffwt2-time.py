"""Bounded serial FFWT2 pilot; retain source and checkpoints for later segments.

Initial operating defaults and mesh remain declared, not historically recovered.
No original shell program is executed and no sensor/stiffness input is repaired.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
REVISION='f62943df20e9e4d7d9f50e070477b22426b5f865'
PREFIX='4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/FFWT-2-D - Effect of FFWT on Rolling Performance'


def pin(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def write(path,data):
    Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def prepare(folder,nominal,duration):
    cache=ROOT/'.reference/isae-validation'/REVISION
    source=cache/PREFIX/'FFWT10/FFWT_REMOVED_V15_DF21.asw'
    driver=source.with_name('FFWT_REMOVED_V15_ROLL_DF21.sh')
    output=source.with_suffix('.txt')
    manifest=json.loads((cache.parent/'manifest.json').read_text())
    sources=[pin(p) for p in (source,driver,output)]
    for record in sources:
        expected=manifest['files'][Path(record['path']).relative_to(cache).as_posix()]
        assert all(record[k]==expected[k] for k in ('bytes','sha256'))
    commands=[s.strip().lower() for s in driver.read_text().splitlines() if s.strip()]
    assert commands[commands.index('oper')+1:commands.index('p')]==['!v 15','!f1 21','%','4 23','c','d','x','0.01 200','x','0.01 800']
    native=[]
    for line,raw in enumerate(output.read_text().splitlines(),1):
        if not raw.strip() or raw.startswith('#'):continue
        words=raw.split();assert len(words)==7
        native.append(dict(line=line,tokens=words))
    assert len(native)==801 and float(native[0]['tokens'][1])==2 and float(native[-1]['tokens'][1])==10
    request=dict(action='time',mode='time',source=source.read_text(),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=nominal,beams={str(i):dict(count=nominal if i==1 else nominal//2,spacing='cosine') for i in (1,2,3)}),
        condition=dict(speed=15.,alpha=0.,beta=0.,density=1.2256,mach=0.,gravity_magnitude=9.81,
            controls={'1':21.},position_earth=[0.,0.,0.],attitude=[0.,0.,0.],rates=[0.,0.,0.],
            acceleration=[0.,0.,0.],angular_acceleration=[0.,0.,0.],ground_effect=0,
            freeze_influences=False,aero_lag=True,circulation_modes={str(i):0 for i in (1,2,3)},
            wake_core_ratio=.25,stall=True,stall_factor=40.,stall_width=.05),
        time=dict(frame='mixed',load_targets={'moment.x':0.},duration=duration,dt=.01,order=2,
            tolerance=1e-8,continuation_steps=4,max_steps=1000))
    plan=dict(family='FFWT-2',configuration='FFWT10 V15 DF21',source_pins=sources,
        kernel_pins=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))],helper=pin(__file__),
        native_rows=native,native_scalar_slots=4005,native_time_range=[2.,10.],
        declared_initial_time=0.,nominal=nominal,duration=duration,
        qualifications=['Original time history starts after two seconds of warm-up; shorter segments cannot match it.',
            'Mixed frame with free roll and other accelerations prescribed zero represents the reported rolling rig.',
            'Default alpha/beta/pose, cold zero-local-rate equilibrium, aerodynamic flags and node arrays are not authenticated historical startup.',
            'No initial state is inferred from native outputs. All literal source sensors and hinge laws are preserved.',
            'Full history, temporal/mesh refinement and all five native channels remain required.'],
        native_comparisons=0,full_family_validated=False)
    write(folder/'plan.json',plan);write(folder/'request.json',request)
    return request,plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--nominal',type=int,choices=(8,16,32),default=16)
    parser.add_argument('--duration',type=float,default=.02)
    seed=parser.add_mutually_exclusive_group()
    seed.add_argument('--resume-from',type=Path)
    seed.add_argument('--equilibrium-from',type=Path,
        help='Launch from a separately completed, same-kernel mixed-frame matrix probe.')
    args=parser.parse_args()
    folder=args.output_dir;folder.mkdir(parents=True,exist_ok=True)
    assert not (folder/'started.json').exists(),'Retain prior evidence; choose a new output directory'
    if args.resume_from:
        checkpoint=json.loads((args.resume_from/'checkpoint.json').read_text())
        plan=json.loads((args.resume_from/'plan.json').read_text())
        request=dict(action='resume_time',source=Path(plan['source_pins'][0]['path']).read_text(),
                     numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
                     checkpoint=checkpoint,time=dict(duration=args.duration))
        plan=dict(plan,parent_checkpoint=pin(args.resume_from/'checkpoint.json'),duration=args.duration)
        write(folder/'plan.json',plan);write(folder/'request.json',request)
    else:
        request,plan=prepare(folder,args.nominal,args.duration)
        if args.equilibrium_from:
            prior=json.loads((args.equilibrium_from/'plan.json').read_text())
            assert prior['args']['frame']=='mixed'
            assert prior['request']['source']==request['source']
            assert prior['request']['panels']==request['panels']
            assert prior['kernel']=={p['path']:p['sha256'] for p in plan['kernel_pins']}
            saved=json.loads((args.equilibrium_from/'equilibrium.json').read_text())
            request=dict(action='launch_time',source=request['source'],numerics=request['numerics'],
                equilibrium_state=saved,time=dict(frame='mixed',load_targets={'moment.x':0.},
                    duration=args.duration,dt=.01,order=2,tolerance=1e-8,max_steps=1000))
            plan['parent_equilibrium']=pin(args.equilibrium_from/'equilibrium.json')
            write(folder/'plan.json',plan);write(folder/'request.json',request)
    assert all(pin(p['path'])==p for p in plan['source_pins']+plan['kernel_pins']+[plan['helper']])
    write(folder/'started.json',dict(request=pin(folder/'request.json'),wall_time=time.time()))
    sys.path.insert(0,str(ROOT))
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint as save_checkpoint
    start=time.monotonic()
    print('Starting bounded FFWT2 segment.',flush=True)
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*args):
            stream.write(json.dumps(dict(seconds=time.monotonic()-start,event=args))+'\n');stream.flush()
        result=dispatch(request,progress=progress)
    seconds=time.monotonic()-start
    write(folder/'result.json',result)
    assert result['converged']
    saved=save_checkpoint(result,-1)
    write(folder/'checkpoint.json',saved)
    assert all(pin(p['path'])==p for p in plan['source_pins']+plan['kernel_pins']+[plan['helper']])
    report=dict(status='SEGMENT_COMPUTED',seconds=seconds,snapshots=len(result['snapshots']),
        times=[s['time'] for s in result['snapshots']],result=pin(folder/'result.json'),checkpoint=pin(folder/'checkpoint.json'),
        native_comparisons=0,full_family_validated=False)
    write(folder/'report.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
