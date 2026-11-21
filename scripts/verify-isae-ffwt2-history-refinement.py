"""Refine the complete FFWT2 declared jig startup, in small serial segments.

No equilibrium is inserted before the first BDF1 step. The uncomputed jig
snapshot is retained separately, with its actual residual. Only completed
discrete states at t>=dt enter the comparison chain. This is a startup
diagnostic motivated by the original script, not authenticated ASWING defaults.
"""
import argparse
from copy import deepcopy
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('ffwt2_original',ROOT/'scripts/verify-isae-ffwt2-time.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
pin,write=original.pin,original.write


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--resume-from',type=Path)
    ap.add_argument('--duration',type=float,default=.02)
    ap.add_argument('--dt',type=float,choices=(.01,.005,.0025),default=.005)
    ap.add_argument('--command-restart',action='store_true')
    args=ap.parse_args();folder=args.output_dir.resolve()
    folder.mkdir(parents=True,exist_ok=False)
    if args.resume_from:
        parent=args.resume_from.resolve()
        plan=json.loads((parent/'plan.json').read_text())
        report=json.loads((parent/'report.json').read_text())
        assert report['status']=='SEGMENT_COMPUTED' and plan['continuation_version']==3
        assert plan['time_step']==args.dt
        assert pin(parent/'checkpoint.json')==report['checkpoint']
        assert pin(parent/'result.json')==report['result']
        saved=json.loads((parent/'checkpoint.json').read_text())
        start_time=saved['state']['time']
        if args.command_restart:
            assert abs(start_time-2.)<1e-12 and args.duration==args.dt
            assert not plan.get('command_restarts')
            plan['command_restarts']=[2.]
        else:
            assert start_time<2.-1e-12 or plan.get('command_restarts')==[2.]
            if start_time<2.-1e-12:assert start_time+args.duration<=2.+1e-12
        assert start_time+args.duration<=2.04+1e-12
        plan.update(parent_checkpoint=pin(parent/'checkpoint.json'),duration=args.duration)
        write(folder/'plan.json',plan)
    else:
        assert args.duration>args.dt and args.duration<=2. and not args.command_restart
        request,plan=original.prepare(folder,16,args.duration)
        request['time']['dt']=args.dt
        plan.update(continuation_version=3,declared_segment_start=args.dt,time_step=args.dt,
            accuracy_gate=dict(relative=.001,normalization='maximum fine-grid magnitude per channel over common 2.00--2.04 s rows'),
            startup='jig-zero-motion-zero-circulation',helper=pin(__file__),
            preparation_helper=pin(ROOT/'scripts/verify-isae-ffwt2-time.py'))
        plan['qualifications']=[
            'Declared jig geometry, zero local/frame rates, zero circulation; no initial equilibrium solve.',
            'Original script executes time marching without an explicit preceding steady solve; actual historical initial point and C preset remain unverified.',
            'Uncomputed t=0 algebraic loads/rates are not certified or scored; the first complete BDF1 state is at the declared dt.',
            'Only dt is refined from .01; literal physical inputs, nominal16 mesh, equations, tolerance1e-8 and reference tolerance.05 remain fixed.',
            'The second command restarts with BDF1 at t=2+dt, then continues with BDF2; ordinary segment boundaries retain history.',
            'No initialization parameter, phase shift or model field is fitted to native output.',
            'Full history, time/mesh refinement, other models and authenticated historical startup remain required.']
        write(folder/'plan.json',plan)
    for p in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['preparation_helper']]:assert pin(p['path'])==p
    write(folder/'started.json',dict(wall_time=time.time()))
    start=time.monotonic()
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*event):
            stream.write(json.dumps(dict(seconds=time.monotonic()-start,event=event))+'\n');stream.flush()
        if not args.resume_from:
            import numpy as np
            from openswing.asw import parse_asw
            from openswing.aero import FlightCondition
            from openswing.source_airflow import SourceAirflowNetwork
            from openswing.operating import time_operating_constraints,time_constraint_data
            from openswing.forcing import TimeForcing
            from openswing.time_integration import TimeState,TimeSystem,integrate
            from openswing.time_state import portable
            from openswing.hinge_history import at_network
            cdata=deepcopy(request['condition'])
            for key in ('controls','powers','circulation_modes'):
                cdata[key]={int(k):v for k,v in cdata.get(key,{}).items()}
            c=FlightCondition(**cdata)
            model=parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
            targets={'moment.x':0.}
            constraints=time_operating_constraints('mixed',targets)
            n=SourceAirflowNetwork(model,request['panels'],c,None,[],operating_constraints=constraints)
            forcing=TimeForcing('',model,c,n.motion,args.duration,'mixed',None,load_targets=targets)
            system=TimeSystem(n,forcing)
            x=np.zeros(n.size);r,Q,*_,gamma=n.unpack(x);zero=np.zeros_like(r)
            seed=TimeState(0.,x,r,Q,zero.copy(),zero.copy(),-c.speed*c.vectors()[0],
                np.zeros(3),np.zeros(3),np.eye(3),gamma,hinge_charts=at_network(n,Q))
            system.source_time.bind(seed)
            options=system.options(seed,zero,zero,np.zeros(n.circulation_basis.panels))
            setup=portable(dict(panels=request['panels'],condition=asdict(c),
                motion={k:getattr(n.motion,k).tolist() for k in ('rates','acceleration','angular_acceleration')},
                gravity=None,mesh_loads=[],loads=[],strut_mode='bilateral',frame='mixed',
                controller=None,forcing='',structural_operator=n.structural_operator,
                **time_constraint_data(constraints)))
            first=integrate(system,seed,None,options,setup,duration=args.dt,dt=args.dt,order=2,
                tolerance=1e-8,max_steps=1,continuation=0,progress=progress,
                initial_phase='declared_uncomputed_jig_seed')
            assert len(first['snapshots'])==2 and first['accepted_steps']==1 and first['rejected_steps']==0
            assert first['snapshots'][-1]['converged'] and first['snapshots'][-1]['residual']<=1e-8
            write(folder/'first-step.json',first)
            saved=checkpoint(first,-1);write(folder/'first-checkpoint.json',saved)
            plan.update(first_step_result=pin(folder/'first-step.json'),
                first_checkpoint=pin(folder/'first-checkpoint.json'),
                seed_residual=first['snapshots'][0]['residual'])
            write(folder/'plan.json',plan)
        request=dict(action='resume_time',source=Path(plan['source_pins'][0]['path']).read_text(),
            numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
            checkpoint=saved,time=dict(duration=args.duration if args.resume_from else args.duration-args.dt,
                dt=args.dt,order=1 if args.command_restart else 2))
        write(folder/'request.json',request)
        result=dispatch(request,progress=progress)
    assert result['converged'] and result['rejected_steps']==0 and result['checkpoint_validation']['discrete_replayed']
    assert result['maximum_step']==args.dt
    assert all(s['converged'] and s['residual']<=1e-8 for s in result['snapshots'])
    assert all(s['restart']['accepted_method']['effective_order']==(1 if args.command_restart else 2)
        for s in result['snapshots'][1:])
    write(folder/'result.json',result);write(folder/'checkpoint.json',checkpoint(result,-1))
    for p in plan['source_pins']+plan['kernel_pins']+[plan['helper'],plan['preparation_helper']]:assert pin(p['path'])==p
    report=dict(status='SEGMENT_COMPUTED',seconds=time.monotonic()-start,
        times=[s['time'] for s in result['snapshots']],snapshots=len(result['snapshots']),
        result=pin(folder/'result.json'),checkpoint=pin(folder/'checkpoint.json'),
        checkpoint_validation=result['checkpoint_validation'],native_comparisons_assessed=False,
        full_family_validated=False)
    write(folder/'report.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
