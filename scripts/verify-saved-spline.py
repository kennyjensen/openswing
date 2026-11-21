"""Independent 2 kg / 500 N m^-1 translating-frame spring references.

No production modules are imported. Natural-spline polynomials are derived
from the three data points and zero endpoint second derivatives. The Radau
matrix is integrated from the Lagrange basis, not copied from the kernel.
"""
import math
import numpy as np
from numpy.polynomial import Polynomial as P

KNOT=.04
MASS=2.
STIFFNESS=500.
OMEGA2=STIFFNESS/MASS
INITIAL=np.array([-.0016,0.])


def segment(t):
    return (0.,P([0.,.596,0.,2.5])) if t<=KNOT else (KNOT,P([.024,.608,.3,-5/48]))


def velocity(t):
    origin,p=segment(t)
    return float(p(t-origin))


def acceleration(t):
    origin,p=segment(t)
    return float(p.deriv()(t-origin))


def position(t):
    if t<=KNOT:return float(P([0.,.596,0.,2.5]).integ()(t))
    return position(KNOT)+float(P([.024,.608,.3,-5/48]).integ()(t-KNOT))


def continuous(t):
    """Exact oscillator response to piecewise quadratic frame acceleration."""
    y=INITIAL.copy();start=0.;omega=math.sqrt(OMEGA2)
    for end in ([KNOT,t] if t>KNOT else [t]):
        origin,g=segment((start+end)/2)
        a=g.deriv();particular=-a/OMEGA2+a.deriv(2)/OMEGA2**2
        c=y[0]-particular(start-origin)
        d=(y[1]-particular.deriv()(start-origin))/omega
        h=end-start
        y=np.array([particular(end-origin)+c*math.cos(omega*h)+d*math.sin(omega*h),
            particular.deriv()(end-origin)+omega*(-c*math.sin(omega*h)+d*math.cos(omega*h))])
        start=end
    return y


def radau_step(y,time,end,forcing_acceleration=acceleration):
    h=end-time;c=np.array([(4-math.sqrt(6))/10,(4+math.sqrt(6))/10,1.])
    basis=[]
    for j in range(3):
        p=P([1.])
        for k in range(3):
            if k!=j:p*=P([-c[k],1.])/(c[j]-c[k])
        basis.append(p.integ())
    a=np.array([[p(ci)-p(0.) for p in basis] for ci in c])
    b=np.array([p(1.)-p(0.) for p in basis])
    matrix=np.array([[0.,1.],[-OMEGA2,0.]])
    load=np.array([[0.,-forcing_acceleration(time+ci*h)] for ci in c])
    rates=np.linalg.solve(np.eye(6)-h*np.kron(a,matrix),(np.tile(matrix@y,(3,1))+load).ravel()).reshape(3,2)
    return y+h*b@rates


def bdf_step(history,time,order):
    previous=history[-1];h=time-previous['time']
    if order==1:coefficients=[1/h,-1/h]
    else:
        k=previous['time']-history[-2]['time']
        coefficients=[(2*h+k)/(h*(h+k)),-(h+k)/(h*k),h/(k*(h+k))]
    predecessors=list(reversed(history[-(len(coefficients)-1):]))
    c0=coefficients[0]
    sq=sum(c*p['y'][0] for c,p in zip(coefficients[1:],predecessors))
    sv=sum(c*p['y'][1] for c,p in zip(coefficients[1:],predecessors))
    frame_a=c0*velocity(time)+sum(c*velocity(p['time']) for c,p in zip(coefficients[1:],predecessors))
    q=(-c0*sq-sv-frame_a)/(c0*c0+OMEGA2)
    return np.array([q,c0*q+sq]),frame_a


def verify(snapshots):
    expected=INITIAL.copy();past=[];errors=[];trajectory=[]
    for i,s in enumerate(snapshots):
        t=s['time'];order=s['order']
        if i:
            if order==5:expected=radau_step(expected,past[-1]['time'],t);frame_a=acceleration(t)
            else:expected,frame_a=bdf_step(past,t,order)
        else:
            assert s['initial_phase']=='history_transition_right_limit'
            frame_a=acceleration(t)
        q,qd=expected
        # The public snapshot's saved physical chart owns nodal positions.
        nodes=s['restart']['state']['network']['positions']
        actual_q=float(nodes[-1][1])-2.
        actual_v=float(s['local_velocity'][-1][1])
        row=dict(position=abs(actual_q-q),velocity=abs(actual_v-qd),
            root_force=abs(s['operating_values']['power.1']+STIFFNESS*q),
            frame_velocity=abs(s['frame']['velocity_origin_body'][1]-velocity(t)),
            frame_acceleration=abs(s['frame']['acceleration_reference_body'][1]-frame_a),
            relative_acceleration=abs(s['local_acceleration'][-1][1]-(-OMEGA2*q-frame_a)))
        limits=dict(position=1e-9,velocity=1e-8,root_force=1e-7,frame_velocity=1e-9,
            frame_acceleration=1e-7,relative_acceleration=1e-7)
        for key,error in row.items():assert np.isfinite(error) and error<=limits[key],(t,key,error,limits[key])
        assert s['converged'] and s['residual']<=1e-8
        assert np.max(np.abs(s['applied_force']))<=1e-7
        errors.append(row);past.append(dict(time=t,y=expected.copy()))
        exact=continuous(t)
        trajectory.append(dict(time=t,actual=[actual_q,actual_v],discrete=expected.tolist(),
            continuous=exact.tolist(),temporal_error=np.abs(expected-exact).tolist()))
    return dict(status='PASS',snapshots=len(snapshots),maximum_discrete_errors={key:max(row[key] for row in errors) for key in errors[0]},trajectory=trajectory)


def verify_transition(result):
    """Check the physical launch state and separately owned left/right records."""
    transition=result['launch_transition']
    before=transition['before_input']['snapshot'];right=result['snapshots'][0]
    assert before['initial_phase']=='saved_equilibrium_before_history_transition'
    assert right['initial_phase']=='history_transition_right_limit'
    assert transition['right_limit_snapshot_index']==0
    assert all(value==0. for value in transition['held_state_max_error'].values())
    assert abs(before['frame']['acceleration_reference_body'][1]-.4)<1e-8
    assert abs(right['frame']['acceleration_reference_body'][1]-.596)<1e-8
    assert abs(right['local_acceleration'][-1][1]+.196)<1e-8
    assert abs(right['operating_values']['power.1']-.8)<1e-8
    marker=right['restart']['accepted_method']['accepted_inputs']['setup']['saved_history_scope']
    assert marker['version'] in (2,3)
    assert marker['kind']=={2:'single-nonrotating-earth-velocity-spline-v2',3:'single-nonrotating-earth-velocity-transitions-v3'}[marker['version']]
    return verify(result['snapshots'])


def run(source,saved,progress=None):
    """Actual public launch and checkpoint continuation, with original inputs owned."""
    from copy import deepcopy
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint,restore_checkpoint
    original=deepcopy(saved)
    request=dict(action='launch_time',source=source,equilibrium_state=saved,
        time=dict(duration=.06,dt=.02,order=5,frame='mixed',load_targets={'force.y':0.},
            actuator_constraints=[dict(variable='power.1',quantity='velocity_earth.y',target=0.)],
            forcing='time velocity_earth.y\n0 0\n.04 .024\n1 .792'))
    result=dispatch(request,progress)
    assert saved==original and result['accepted_steps']==3 and result['rejected_steps']==0
    metrics=verify_transition(result)
    validations=[restore_checkpoint(parse_asw(source),checkpoint(result,i))[7]['acceptance_validation']
        for i in range(len(result['snapshots']))]
    cp=checkpoint(result,1);before=deepcopy(cp)
    resumed=dispatch(dict(action='resume_time',source=source,checkpoint=cp,
        time=dict(duration=.04,dt=.02,order=5)),progress)
    assert cp==before and resumed['accepted_steps']==2 and resumed['rejected_steps']==0
    resumed_metrics=verify(result['snapshots'][:2]+resumed['snapshots'][1:])
    return dict(request=request,result=result,metrics=metrics,resumed=resumed,
        resumed_metrics=resumed_metrics,checkpoint_validations=validations)


if __name__=='__main__':
    import argparse,json,sys
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--result',type=Path,help='Check an exported complete trajectory without importing the solver')
    group.add_argument('--run',action='store_true',help='Execute the public launch and continuation')
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    if args.result:
        result=json.loads(args.result.read_text())
        report=verify_transition(result) if 'launch_transition' in result else verify(result['snapshots'])
    else:
        root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
        inputs=root/'tests/inverse_history/saved/inputs'
        report=run((inputs/'both-root.asw').read_text(),json.loads((inputs/'saved-equilibrium.json').read_text()),
            lambda *v:print(json.dumps(v),flush=True))
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
