"""Verify the ST-4 static divergence condition without repeated modal solves."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run(args):
    plan_path=Path(args.plan);plan=json.loads(plan_path.read_text())
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    pins={str(plan_path.resolve()):sha(plan_path),str(Path(__file__)):sha(Path(__file__)),
          str(ROOT/'scripts/static_divergence.py'):sha(ROOT/'scripts/static_divergence.py')}
    pins.update({str(ROOT/p):value for p,value in plan['kernel_pins'].items()})
    pins.update({str(ROOT/p):value for p,value in plan['reference_pins'].items()})
    for path,value in pins.items():assert sha(path)==value,path
    started=time.monotonic();report=dict(status='RUNNING',kind=args.kind,case=args.case,
        native_ASWING_validation=False,goal_complete=False)
    try:
        import numpy as np
        from scipy.sparse import load_npz
        from static_divergence import first_divergence
        gates=plan['gates']
        if args.kind=='public':
            folder=ROOT/plan['public_cases'][args.case]
            for name in ('request.json','result.json','A.npz'):
                pins[str(folder/name)]=sha(folder/name)
            request=json.loads((folder/'request.json').read_text())
            result=json.loads((folder/'result.json').read_text())
            layout=result['diagnostics']['state_layout'];saved=result['base']['equilibrium_state']
            del result
            speed=request['condition']['speed']
            split,size=layout['circulation']['start'],layout['network_size']
            full=load_npz(folder/'A.npz')[:size,:size].tocsc()
            a,b,c,d=full[:split,:split],full[:split,split:],full[split:,:split],full[split:,split:]
            del full
            candidate=first_divergence(a,b,c,d,speed)
            count=layout['node_coordinates']['width']
            normalization=candidate['right'][np.argmax(abs(candidate['right'][:count]))]
            vector=candidate['right']/normalization
            derivative=candidate['speed_action']/normalization
            left=candidate['left']
            assert np.max(abs(vector.imag))<1e-8*max(1.,np.max(abs(vector.real)))
            vector=vector.real
            derivative=np.real(derivative)
            from openswing.asw import parse_asw
            from openswing.aero import FlightCondition
            from openswing.source_airflow import SourceAirflowNetwork
            from openswing.equilibrium_state import restore,warm_start_recipe
            from openswing.linear_dynamics import DynamicSystem
            model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
            def make_system(velocity):
                condition=FlightCondition(**dict(request['condition'],speed=velocity))
                n=SourceAirflowNetwork(model,request['panels'],condition,None,[],
                    mesh_recipe=warm_start_recipe(model,request['panels'],saved))
                x=restore(n,saved)
                assert n.nfev==0 and n.size==size and n.gamma_start==split
                assert n.F==layout['internal_loads']['force_scale']
                assert n.L==layout['node_coordinates']['translation_scale']
                assert abs(n.gamma_scale/layout['circulation']['scale']-velocity/speed)<1e-14
                system=DynamicSystem(n,x,frame='fixed')
                return system
            critical=candidate['speed']
            system=make_system(critical)
            zero=np.zeros(system.size)
            base_error=float(np.max(abs(system.residual(zero,zero))))
            assert base_error<=gates['base_residual']
            direction=np.r_[vector,np.zeros(system.size-size)]
            den=np.vdot(left.astype(np.clongdouble),derivative.astype(np.clongdouble))
            assert np.isfinite(den) and abs(den)>0
            probes=[];actions=[]
            for h in plan['probe_steps']:
                action=(system.residual(h*direction,zero)-system.residual(-h*direction,zero))/(2*h)
                correction=-np.vdot(left.astype(np.clongdouble),action[:size].astype(np.clongdouble))/den
                backward=float(np.max(abs(action))/(candidate['matrix_norm']*np.max(abs(vector))))
                sample=dict(step=h,full_zero_mode_backward_error=backward,
                    first_order_speed_correction=[float(correction.real),float(correction.imag)],
                    relative_speed_correction=float(abs(correction)/critical))
                probes.append(sample);actions.append(action)
                print(json.dumps(dict(case=args.case,probe=sample)),flush=True)
            final=[p for p in probes if p['step']<=1e-5]
            assert all(p['full_zero_mode_backward_error']<=gates['pencil_backward'] and
                       p['relative_speed_correction']<=gates['relative_speed_correction'] for p in final)
            # Independent smooth geometry and circulation probes check the
            # pressure scaling, rather than just testing the candidate vector.
            geometry=np.zeros(size);nodes=layout['nodes'];s=np.linspace(0.,1.,nodes)
            k=geometry[:6*nodes].reshape(nodes,6)
            k[:,0]=np.sin(np.pi*s);k[:,1]=s*s
            k[:,3]=.2*np.sin(2*np.pi*s);k[:,5]=.3*s
            circulation=np.zeros(size)
            circulation[split:]=np.sin(np.pi*(np.arange(size-split)+.5)/(size-split))
            directions=dict(critical=vector,geometry=geometry,circulation=circulation)
            scales=[];bracket=[];evaluations=system.network.nfev
            for offset in (-plan['speed_bracket_relative'],0.,plan['speed_bracket_relative']):
                velocity=critical*(1+offset);current=make_system(velocity)
                z=np.zeros(current.size)
                error=float(np.max(abs(current.residual(z,z))))
                assert error<=gates['base_residual']
                q=(velocity/speed)**2;h=plan['scaling_probe_step']
                for name,v in directions.items():
                    extended=np.r_[v,np.zeros(current.size-size)]
                    measured=(current.residual(h*extended,z)-current.residual(-h*extended,z))/(2*h)
                    expected=np.r_[a@v[:split]+q*(b@v[split:]),c@v[:split]+d@v[split:],np.zeros(current.size-size)]
                    action_error=float(np.max(abs(measured-expected))/max(1.,np.max(abs(expected))))
                    assert action_error<=gates['directional_action'],(velocity,name,action_error)
                    scales.append(dict(speed=velocity,direction=name,relative_action_error=action_error,base_residual=error))
                    if name=='critical':
                        equivalent=np.vdot(left.astype(np.clongdouble),measured[:size].astype(np.clongdouble))/den
                        predicted=(velocity**2-critical**2)/(2*critical)
                        assert abs(equivalent-predicted)<=gates['relative_speed_correction']*critical
                        bracket.append(dict(speed=velocity,equivalent_speed_residual=float(equivalent.real),
                            predicted_speed_residual=float(predicted)))
                evaluations+=current.network.nfev
            assert bracket[0]['equivalent_speed_residual']<0<bracket[2]['equivalent_speed_residual']
            np.savez_compressed(out/'physical-probes.npz',right=vector,left=left,speed_action=derivative,
                                probe_steps=plan['probe_steps'],actions=np.asarray(actions))
            report.update(base_residual=base_error,probes=probes,speed_scaling=scales,
                sign_bracket=bracket,residual_evaluations=evaluations,
                structural_intervals=layout['elements'],circulation_unknowns=size-split,
                requested_panels=request['panels'],saved_source=str(folder))
        else:
            from isae_st4_flow_reference import matrices
            intervals,structure=plan['reference_cases'][args.case]
            speed=139.5
            aa,mm,parts=matrices(intervals=intervals,structure_intervals=structure,speed=speed)
            del aa,mm
            # eta=Gamma/U: divide the flow equation by U. The static equations
            # become -K q - rho U^2 L eta = 0, H q + W eta = 0.
            a=-parts['stiffness'];b=-parts['density']*speed**2*parts['lift']
            c=parts['flow_twist'];d=parts['influence']
            candidate=first_divergence(a,b,c,d,speed)
            np.savez_compressed(out/'reference-mode.npz',right=candidate['right'],left=candidate['left'],
                speed_action=candidate['speed_action'],nodes=parts['nodes'],aero_nodes=parts['aero_nodes'])
            report.update(structural_intervals=len(parts['nodes'])-1,
                aerodynamic_intervals=len(parts['aero_nodes'])-1,reference_grid=[intervals,structure])
            del parts
        assert candidate['right_backward_error']<=gates['pencil_backward']
        assert candidate['left_backward_error']<=gates['pencil_backward']
        report.update({k:v for k,v in candidate.items() if k not in ('right','left','speed_action')})
        for path,value in pins.items():assert sha(path)==value,path
        report['status']='PASS_STATIC_DIVERGENCE_CHECK'
    except BaseException as error:
        report.update(status='FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        report.update(seconds=time.monotonic()-started,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(out/'pins.json',pins);write(out/'report.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('traceback','probes','speed_scaling','sign_bracket')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan');parser.add_argument('output')
    parser.add_argument('--kind',choices=['public','reference'],required=True)
    parser.add_argument('--case',required=True)
    run(parser.parse_args())
