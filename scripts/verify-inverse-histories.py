"""Public inverse-history checks shared by native and packaged WASM runners.

The rigid-body oracle differentiates the prescribed cubic with the actual BDF
stencil. The saved spring oracle is an independently reduced two-kilogram,
500 N/m oscillator and the exact first Radau IIA step, not a continuous-time
value substituted for the discrete method.
"""
from copy import deepcopy
from fractions import Fraction as Q
import json
import numpy as np


def curved_request(source):
    return dict(action='time', source=source, panels=4, gravity=[0., 0., 0.],
        condition=dict(speed=10., alpha=0., mach=0., gravity_magnitude=0.),
        time=dict(duration=.04, dt=.02, order=2, frame='free', tolerance=1e-8,
            actuator_constraints=[dict(variable='power.1', quantity='velocity_earth.x', target=-10.)],
            forcing='time velocity_earth.x\n-1 -10.2\n0 -10\n1 -9.4'))


def close(actual, expected, tolerance):
    error=float(np.max(np.abs(np.asarray(actual)-np.asarray(expected)), initial=0.))
    assert np.isfinite(error) and error <= tolerance, (actual, expected, error, tolerance)
    return error


def check_curved(snapshots):
    times=[]; velocities=[]; positions=[]; errors=[]
    for i, s in enumerate(snapshots):
        t=Q(str(s['time'])); velocity=-10+Q(2,5)*t+Q(3,10)*t*t-Q(1,10)*t**3
        if not i:
            acceleration=Q(2,5); position=Q(0)
            assert s['initial_phase']=='cold_inverse_history'
        else:
            h=t-times[-1]
            if i==1:
                coefficients=[1/h,-1/h]
            else:
                k=times[-1]-times[-2]
                coefficients=[(2*h+k)/(h*(h+k)),-(h+k)/(h*k),h/(k*(h+k))]
            acceleration=coefficients[0]*velocity+sum(c*v for c,v in zip(coefficients[1:],reversed(velocities)))
            position=(velocity-sum(c*p for c,p in zip(coefficients[1:],reversed(positions))))/coefficients[0]
            accepted=s['restart']['accepted_method']
            assert accepted['scheme']=='openswing-so3-bdf-v2'
            assert 0 < accepted['nonlinear_tolerance'] < accepted['tolerance']
        frame=s['frame']
        errors.append(dict(force=close(s['operating_values']['power.1'],float(acceleration),1e-7),
            acceleration=close(frame['acceleration_reference_body'],[float(acceleration),0,0],1e-7),
            velocity=close(frame['velocity_origin_body'],[float(velocity),0,0],1e-9),
            position=close(frame['position_earth'],[float(position),0,0],1e-8)))
        close(s['applied_force'],[0,0,0],1e-8)
        close(frame['body_to_earth'],np.eye(3),1e-10)
        for name in ('local_velocity','local_rates','local_acceleration','local_rate_derivative'):
            close(s[name],np.zeros_like(s[name]),1e-10)
        assert s['converged'] and s['residual'] <= 1e-8
        times.append(t); velocities.append(velocity); positions.append(position)
    return dict(snapshots=len(snapshots), maximum_errors={k:max(row[k] for row in errors) for k in errors[0]})


def run_curved(source, progress=None):
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint, restore_checkpoint
    from openswing.asw import parse_asw
    request=curved_request(source)
    result=dispatch(request,progress)
    assert result['accepted_steps']==2 and result['rejected_steps']==0
    saved=checkpoint(result,2); before=deepcopy(saved)
    replay=restore_checkpoint(parse_asw(source),saved)[7]['acceptance_validation']
    assert replay['level']=='recorded_discrete_equations'
    resumed=dispatch(dict(action='resume_time',source=source,checkpoint=saved,
        time=dict(duration=.04,dt=.02,order=2)),progress)
    assert saved==before and resumed['accepted_steps']==2 and resumed['rejected_steps']==0
    metrics=check_curved(result['snapshots']+resumed['snapshots'][1:])
    return dict(request=request,result=result,resumed=resumed,metrics=metrics,checkpoint_validation=replay)


def run_saved(source, saved, progress=None):
    from openswing.bridge import dispatch
    from openswing.asw import parse_asw
    from openswing.time_state import checkpoint, restore_checkpoint
    before=deepcopy(saved)
    request=dict(action='launch_time',source=source,equilibrium_state=saved,
        time=dict(duration=.02,dt=.02,order=5,frame='mixed',load_targets={'force.y':0.},
            actuator_constraints=[dict(variable='power.1',quantity='velocity_earth.y',target=0.)],
            forcing='time velocity_earth.y\n0 0\n1 .6'))
    result=dispatch(request,progress)
    assert saved==before and result['accepted_steps']==1 and result['rejected_steps']==0
    transition=result['launch_transition']; left=transition['before_input']['snapshot']
    initial,endpoint=result['snapshots']
    assert initial['initial_phase']=='history_transition_right_limit'
    close(left['frame']['acceleration_reference_body'],[0,.4,0],1e-8)
    close(initial['frame']['acceleration_reference_body'],[0,.6,0],1e-8)
    close(initial['local_acceleration'][-1],[0,-.2,0],1e-8)
    close(initial['operating_values']['power.1'],.8,1e-8)
    assert all(v==0. for v in transition['held_state_max_error'].values())
    q=float(Q(-7422963,4527113750)); force=float(Q(14845926,18108455))
    jig=np.asarray(saved['identity']['nodes']); expected=jig.copy(); expected[:,1]+=q*jig[:,1]/2
    metrics=dict(shape=close([n['position'] for n in endpoint['nodes']],expected,1e-10),
        force=close(endpoint['operating_values']['power.1'],force,1e-6),
        local_velocity=close(endpoint['local_velocity'][-1],[0,float(Q(-356163,90542275)),0],1e-8))
    validations=[]
    for i in (0,1):
        cp=checkpoint(result,i); original=deepcopy(cp)
        validation=restore_checkpoint(parse_asw(source),cp)[7]['acceptance_validation']
        assert cp==original
        assert validation['level']==('initial_physical_only' if i==0 else 'recorded_discrete_equations')
        validations.append(validation)
    return dict(request=request,result=result,metrics=metrics,checkpoint_validations=validations)


if __name__=='__main__':
    import argparse, hashlib, sys, time, traceback
    from pathlib import Path
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=['curved','saved'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(repo))
    start=time.monotonic()
    pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (repo/'openswing').glob('*.py')}
    def progress(*values):
        with (args.output/'progress.jsonl').open('a') as f:f.write(json.dumps(values)+'\n')
    status=dict(status='RUNNING',case=args.case,source_sha256=pins)
    (args.output/'status.json').write_text(json.dumps(status,indent=2)+'\n')
    try:
        if args.case=='curved':
            result=run_curved((repo/'tests/fixtures/inverse-history-curved.asw').read_text(),progress)
        else:
            inputs=repo/'tests/inverse_history/saved/inputs'
            result=run_saved((inputs/'both-root.asw').read_text(),json.loads((inputs/'saved-equilibrium.json').read_text()),progress)
        (args.output/'output.json').write_text(json.dumps(result,allow_nan=False)+'\n')
        assert pins=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (repo/'openswing').glob('*.py')}
        status.update(status='PASS',metrics=result['metrics'])
    except BaseException:
        status.update(status='FAIL',traceback=traceback.format_exc())
        raise
    finally:
        status['seconds']=time.monotonic()-start
        (args.output/'status.json').write_text(json.dumps(status,indent=2)+'\n')
        print(json.dumps(status,indent=2),flush=True)
