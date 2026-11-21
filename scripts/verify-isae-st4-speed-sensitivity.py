"""Measure local speed sensitivity from fresh full residual actions, without solves.

For A v = lambda M v, lambda_U = w^H (A_U-lambda M_U) v / (w^H M v).
The coordinate scales may vary with speed: their derivative contributions cancel
in this projection at an exact left/right pair. Saved-matrix and base checks
verify the anchor chart. These derivatives diagnose discrepancies; they never
replace computed poles or alter comparison scores.
"""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    folder=ROOT/'artifacts/isae/st4-critical-refinement-20261104/public139p5_n160'
    files=[folder/name for name in ('request.json','result.json','A.npz','M.npz')]
    files += [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),ROOT/'scripts/modal_directional_check.py']
    pins={str(p.relative_to(ROOT)):sha(p) for p in files}
    widths=[.03,.01,.003];state_step=1e-5;check_step=3e-6;selected=[4,1]
    gates=dict(base=1e-9,pencil=1e-8,anchor_action=1e-6,slope_relative=1e-4,slope_absolute=1e-7)
    write(out/'plan.json',dict(scope=__doc__,pins=pins,speed_steps=widths,state_step=state_step,
        check_step=check_step,selected_modes=selected,gates=gates,native_ASWING_validation=False))
    began=time.monotonic();report=dict(status='RUNNING',native_ASWING_validation=False,goal_complete=False)
    try:
        import numpy as np
        from scipy.sparse import load_npz
        from openswing.asw import parse_asw
        from openswing.aero import FlightCondition
        from openswing.source_airflow import SourceAirflowNetwork
        from openswing.equilibrium_state import restore,warm_start_recipe
        from openswing.linear_dynamics import DynamicSystem
        from modal_directional_check import actions,projected_correction
        request,result=[json.loads((folder/name).read_text()) for name in ('request.json','result.json')]
        layout=result['diagnostics']['state_layout'];saved=result['base']['equilibrium_state']
        speed=request['condition']['speed'];assert speed==139.5
        model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
        aa,mm=[load_npz(folder/name) for name in ('A.npz','M.npz')]
        modes=[]
        for index in selected:
            original=result['modes'][index];value=complex(*original['eigenvalue'])
            v=np.asarray(original['right']['real'])+1j*np.asarray(original['right']['imag'])
            w=np.asarray(original['left']['real'])+1j*np.asarray(original['left']['imag'])
            v/=v[np.argmax(abs(v[:6*layout['nodes']]))];w/=np.max(abs(w))
            av,mv=aa@v,mm@v;wa,wm=aa.T@w,mm.T@w
            er=float(np.linalg.norm(av-value*mv)/(np.linalg.norm(av)+abs(value)*np.linalg.norm(mv)))
            el=float(np.linalg.norm(wa-value.conjugate()*wm)/(np.linalg.norm(wa)+abs(value)*np.linalg.norm(wm)))
            assert max(er,el)<=gates['pencil'],(index,er,el)
            modes.append(dict(index=index,value=value,v=v,w=w,av=av,mv=mv))
        del result,aa,mm
        def make(velocity):
            condition=FlightCondition(**dict(request['condition'],speed=velocity))
            n=SourceAirflowNetwork(model,request['panels'],condition,None,[],
                mesh_recipe=warm_start_recipe(model,request['panels'],saved))
            x=restore(n,saved);assert n.nfev==0
            assert n.size==layout['network_size'] and n.nn==layout['nodes']
            assert n.F==layout['internal_loads']['force_scale'] and n.L==layout['node_coordinates']['translation_scale']
            assert abs(n.gamma_scale/layout['circulation']['scale']-velocity/speed)<1e-14
            system=DynamicSystem(n,x,frame=request['modes']['frame'])
            z=np.zeros(system.size);error=float(np.max(abs(system.residual(z,z))))
            assert error<=gates['base'],(velocity,error)
            return system,error
        system,base=make(speed);anchor=[];evaluations=0
        for mode in modes:
            av,mv=actions(system.residual,mode['v'],state_step)
            errors=[float(np.linalg.norm(x-y)/np.linalg.norm(y)) for x,y in ((av,mode['av']),(mv,mode['mv']))]
            assert max(errors)<=gates['anchor_action'],errors
            anchor.append(dict(index=mode['index'],A_relative_error=errors[0],M_relative_error=errors[1]))
        evaluations+=system.network.nfev;del system;gc.collect()
        rows=[];saved_actions={};projections={}
        for hu in widths:
            for sign in (-1,1):
                current,error=make(speed+sign*hu)
                for h in ([state_step,check_step] if hu==widths[-1] else [state_step]):
                    for mode in modes:
                        av,mv=actions(current.residual,mode['v'],h)
                        projection=projected_correction(mode['w'],mode['mv'],av-mode['value']*mv)
                        key=(hu,sign,h,mode['index']);projections[key]=projection
                        saved_actions[f'U{sign*hu}_h{h}_mode{mode["index"]}_A']=av
                        saved_actions[f'U{sign*hu}_h{h}_mode{mode["index"]}_M']=mv
                        rows.append(dict(speed=speed+sign*hu,speed_step=hu,state_step=h,index=mode['index'],
                            base_residual=error,projected_pole_defect=[projection.real,projection.imag]))
                evaluations+=current.network.nfev;del current;gc.collect()
                print(json.dumps(dict(speed=speed+sign*hu,status='PROBED',evaluations=evaluations)),flush=True)
        slopes=[]
        def close(a,b):
            changes=[abs(a.real-b.real),abs(a.imag-b.imag)]
            limits=[gates['slope_absolute']+gates['slope_relative']*abs(x) for x in (b.real,b.imag)]
            assert all(x<=y for x,y in zip(changes,limits)),(a,b,changes,limits)
        for mode in modes:
            index=mode['index'];samples=[]
            for hu in widths:
                for h in ([state_step,check_step] if hu==widths[-1] else [state_step]):
                    derivative=(projections[hu,1,h,index]-projections[hu,-1,h,index])/(2*hu)
                    samples.append(dict(speed_step=hu,state_step=h,derivative=[derivative.real,derivative.imag]))
            close(complex(*samples[-3]['derivative']),complex(*samples[-2]['derivative']))
            close(complex(*samples[-2]['derivative']),complex(*samples[-1]['derivative']))
            slopes.append(dict(index=index,eigenvalue=[mode['value'].real,mode['value'].imag],samples=samples))
        np.savez_compressed(out/'actions.npz',**saved_actions)
        assert all(sha(ROOT/p)==value for p,value in pins.items())
        report.update(status='PASS_LOCAL_SPEED_DERIVATIVE_CHECK',speed=speed,base_residual=base,
            anchor_checks=anchor,slopes=slopes,probes=rows,residual_evaluations=evaluations)
    except BaseException as error:
        report.update(status='FAILURE_RETAINED',error=repr(error),traceback=traceback.format_exc());raise
    finally:
        report.update(seconds=time.monotonic()-began,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(out/'report.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('probes','traceback')},allow_nan=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output')
    run(parser.parse_args())
