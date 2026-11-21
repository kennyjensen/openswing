"""Nonlinear initial mechanics, time refinement and physical checkpoint checks."""
import hashlib,inspect,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.integrate import solve_ivp
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork,solve_static
from openswing.equilibrium_state import capture
from openswing.operating import free_flight_constraints
from openswing.ground import body_to_earth
from openswing.local_motion import rotation_matrix
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint,resume_time

PENDULUM='''Name
Suspended rigid pendulum verification
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
2 1 2
End
Ground
1 0 1
End
Weight
1 2 0 0 -2 19.6133 0 0 0 0 0 2.941995 2.941995 2.941995
End
Beam 1
Rigid pendulum
t z
0 0
2 -2
End
'''
RIGID=PENDULUM.replace('Suspended rigid pendulum verification','Torque-free rigid body verification').replace('1 0 1','1 0 0').replace('1 2 0 0 -2 19.6133 0 0 0 0 0 2.941995 2.941995 2.941995','1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266')


def cases():
    source=(ROOT/'examples/instrumented-oscillator.asw').read_text();profile=json.loads((ROOT/'examples/initial-nonlinear-spring.json').read_text())['state'];rows=[]
    law=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',expression="-20*tanh(5*error('RY[2]'))")])
    for name,unit,panels in [('spring',1.,4),('spring-milliseconds',.001,4),('spring-mesh-8',1.,8),('controller-states',1.,4)]:
        text=source;state=json.loads(json.dumps(profile));control=law
        if unit!=1:
            text=text.replace('T 1 s','T .001 s').replace('9.80665 1.225 340.294','0.00000980665 1225000 .340294').replace('1000 .02','1000 20')
            state['beam_fields'][0]['velocity'][-1][2]*=unit
        if name=='controller-states':
            control=dict(commands={'RY[2]':2,'UY[2]':0},outputs=[dict(actuator='E1',expression="state('lag')-100*integral('RY[2]')")],
                states=[dict(name='lag',initial=0,scale=10,unit='input F',rate="(-200*error('RY[2]')-20*error('UY[2]')-state('lag'))/.05")])
            state['feedback']=dict(integrals={'RY[2]':.003},states={'lag':.1})
        seed=solve_static(parse_asw(text),FlightCondition(speed=10*unit,alpha=0,mach=0),panels,gravity=[0,0,0],controller=control)['equilibrium_state']
        rows.append(dict(name=name,unit=unit,source=text,seed=seed,time=dict(duration=.12/unit,dt=.02/unit,order=5,disturbance=state)))
    # The freely pinned pendulum has a neutral steady spin coordinate. Construct
    # its known vertical equilibrium by solving only the linear internal loads
    # and reaction balance; do not route it through a static mechanism rejection.
    m=parse_asw(PENDULUM);n=StaticNetwork(m,4,None,None,[]);x=np.zeros(n.size);ai=np.arange(6*n.nn,n.size)
    x[ai]=np.linalg.lstsq(n.jacobian(x,1.)[:,ai],-n.residual(x),rcond=1e-12)[0]
    error=float(np.max(abs(n.residual(x))));assert error<1e-8
    angle,omega=1.1,1.3;r=rotation_matrix(np.array([angle,0,0]))@np.array([0,0,-2.]);v=np.cross([omega,0,0],r)
    state=dict(beam_fields=[dict(beam=1,displacement=[[0,0,0,0],[2,*(r-[0,0,-2])]],rotation=[[0,angle,0,0],[2,angle,0,0]],velocity=[[0,0,0,0],[2,*v]],rates=[[0,omega,0,0],[2,omega,0,0]])])
    rows.append(dict(name='pendulum',unit=1.,source=PENDULUM,seed=capture(n,x,residual=error),time=dict(duration=.12,dt=.02,order=5,disturbance=state)))
    m=parse_asw(RIGID);seed=solve_static(m,panels=4,gravity=[0,0,0],operating_constraints=free_flight_constraints())['equilibrium_state']
    state=dict(frame=dict(rates_body=[.8,1.2,.6],attitude_rad=[.3,np.pi/2,-.4],velocity_origin_body=[.2,-.3,.4],position_earth=[1,2,3]))
    rows.append(dict(name='free-body-pitch-pole',unit=1.,source=RIGID,seed=seed,time=dict(duration=.24,dt=.12,order=5,frame='free',disturbance=state)))
    return rows


def compute(case,progress=None):
    m=parse_asw(case['source']);out=launch_time(m,case['seed'],**case['time'],progress=progress)
    cp=checkpoint(out,0);fine=resume_time(m,cp,duration=case['time']['duration'],dt=case['time']['dt']/2)
    middle=len(out['snapshots'])//2;cp=checkpoint(out,middle)
    resumed=resume_time(m,cp,duration=out['end_time']-cp['state']['time'])
    return dict(trajectory=out,refined=fine,restarted=resumed,restart_index=middle)


def physical(case,snapshot):
    unit=case['unit'];s=snapshot
    if case['name'].startswith('spring') or case['name']=='controller-states':
        values=[s['nodes'][-1]['position'][1]-2,s['local_velocity'][-1][1]/unit,s['local_acceleration'][-1][1]/unit**2,s['feedback']['actuators']['E1']]
        if case['name']=='controller-states':values.extend([s['feedback']['integrals']['RY[2]'],s['feedback']['states']['lag'],s['feedback']['state_rates']['lag']])
        return np.array(values)
    if case['name']=='pendulum':return np.r_[s['nodes'][-1]['position'],s['local_velocity'][-1],s['local_acceleration'][-1],s['local_rates'][-1],s['local_rate_derivative'][-1],s['support_force'],s['support_moment']]
    f=s['frame'];return np.r_[np.array(f['body_to_earth']).ravel(),f['position_earth'],f['velocity_origin_body'],f['rates_body'],f['acceleration_reference_body'],f['angular_acceleration_body']]


def reference(case,times):
    name=case['name'];times=np.asarray(times)*case['unit']
    if name.startswith('spring') or name=='controller-states':
        def rhs(t,y):
            q,v=y[:2]
            if name=='controller-states':
                integral,lag=y[2:];actuator=lag-100*integral
                return [v,(-500*q-10*v+actuator)/2,q,(-200*q-20*v-lag)/.05]
            return [v,(-500*q-10*v-20*np.tanh(5*q))/2]
        initial=[.2,.1,.003,.1] if name=='controller-states' else [.2,.1]
        solution=solve_ivp(rhs,(0,max(times.max(),.001)),initial,rtol=2e-12,atol=2e-14,method='DOP853',dense_output=True)
        result=[]
        for t,y in zip(times,solution.sol(times).T):
            d=rhs(t,y);a=y[3]-100*y[2] if name=='controller-states' else -20*np.tanh(5*y[0])
            result.append([y[0],y[1],d[1],a]+([y[2],y[3],d[3]] if name=='controller-states' else []))
        return np.array(result)
    if name=='pendulum':
        def rhs(t,y):return [y[1],-2*9.80665*2*np.sin(y[0])/8.3]
        solution=solve_ivp(rhs,(0,max(times.max(),.001)),[1.1,1.3],rtol=2e-12,atol=2e-14,method='DOP853',dense_output=True);result=[]
        for t,(angle,omega) in zip(times,solution.sol(times).T):
            alpha=rhs(t,[angle,omega])[1];r=np.array([0,2*np.sin(angle),-2*np.cos(angle)]);w=np.array([omega,0,0]);wd=np.array([alpha,0,0]);v=np.cross(w,r);a=np.cross(wd,r)+np.cross(w,np.cross(w,r))
            result.append(np.r_[r,v,a,w,wd,2*(a+[0,0,9.80665]),np.zeros(3)])
        return np.array(result)
    inertia=np.array([2,3,4]);R=body_to_earth(np.rad2deg([.3,np.pi/2,-.4]));U=np.array([.2,-.3,.4]);earth_velocity=R@U
    def rhs(t,y):
        r=y[:9].reshape(3,3);w=y[9:];a,b,c=w;skew=np.array([[0,-c,b],[c,0,-a],[-b,a,0]])
        return np.r_[(r@skew).ravel(),-np.cross(w,inertia*w)/inertia]
    solution=solve_ivp(rhs,(0,max(times.max(),.001)),np.r_[R.ravel(),[.8,1.2,.6]],rtol=2e-12,atol=2e-14,method='DOP853',dense_output=True)
    return np.array([np.r_[y[:9],[1,2,3]+t*earth_velocity,y[:9].reshape(3,3).T@earth_velocity,y[9:],np.zeros(3),rhs(t,y)[9:]] for t,y in zip(times,solution.sol(times).T)])


def verify(case,result):
    out=result['trajectory'];fine=result['refined'];report=out['initialization']['consistency'];assert report['prescribed_coordinate_error']==0
    assert all(result[key]['method']=='Radau IIA (3 stages)' for key in ('trajectory','refined','restarted'))
    assert len(report['refinements'])==2
    assert all(v['derivative_residual']<=report['tolerance'] and v['original_residual']<=report['tolerance'] and v['required_nullspace_defect']<=1e-6 for v in report['refinements'])
    start=physical(case,out['snapshots'][0]);expected=reference(case,[0])[0];initial_error=float(np.max(abs(start-expected)/np.maximum(1.,abs(expected))));assert initial_error<2e-7,(case['name'],initial_error,start,expected)
    errors=[];values=0
    for trajectory in (out,fine):
        times=[s['time'] for s in trajectory['snapshots']];actual=np.array([physical(case,s) for s in trajectory['snapshots']]);exact=reference(case,times);errors.append(np.max(abs(actual-exact),axis=0));values+=actual.size
        assert max(s['residual'] for s in trajectory['snapshots'])<=1e-8
    error_ratio=float(np.linalg.norm(errors[1])/np.linalg.norm(errors[0]));assert error_ratio<.4,(case['name'],error_ratio,errors)
    resumed=result['restarted']['snapshots'];remaining=out['snapshots'][result['restart_index']:]
    assert len(resumed)==len(remaining)
    np.testing.assert_allclose([s['time'] for s in resumed],[s['time'] for s in remaining],rtol=0,atol=1e-13*max(1.,out['end_time']))
    restart=max(float(np.max(abs(physical(case,a)-physical(case,b))/np.maximum(1.,abs(physical(case,b))))) for a,b in zip(resumed,remaining))
    assert restart<2e-7,(case['name'],restart)
    return dict(maximum_scaled_initial_reference_error=initial_error,maximum_history_errors=np.array(errors).tolist(),refined_error_norm_ratio=error_ratio,maximum_scaled_restart_physical_difference=restart,physical_reference_values_checked=values)


def main():
    files=[Path(__file__),ROOT/'examples/instrumented-oscillator.asw',ROOT/'examples/initial-nonlinear-spring.json',*sorted((ROOT/'openswing').glob('*.py'))]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    computation=dict(hashes={k:v for k,v in hashes.items() if k!=str(Path(__file__).relative_to(ROOT))},versions=versions,case_builder=inspect.getsource(cases),runner=inspect.getsource(compute),models=[PENDULUM,RIGID])
    key=hashlib.sha256(json.dumps(computation,sort_keys=True).encode()).hexdigest();cache=ROOT/'.reference/nonlinear-initial'/key;cache.mkdir(parents=True,exist_ok=True)
    (cache/'computation.json').write_text(json.dumps(computation,indent=2)+'\n')
    file=cache/'cases.json'
    if file.exists():specs=json.loads(file.read_text())
    else:specs=cases();file.write_text(json.dumps(specs)+'\n')
    rows=[]
    for case in specs:
        start=time.monotonic();file=cache/(case['name']+'.json')
        def progress(*args):
            if args[0]=='initializing' and args[1] in (1,args[2]):print(case['name'],args,round(time.monotonic()-start,1),flush=True)
        if file.exists():result=json.loads(file.read_text())
        else:result=compute(case,progress);file.write_text(json.dumps(result,allow_nan=False)+'\n')
        checks=verify(case,result);rows.append(dict(specification=case,result=result,checks=checks));print(case['name'],checks,flush=True)
    (ROOT/'docs/validation/nonlinear-initial.json').write_text(json.dumps(dict(description='Nonlinear derivative-array initial states, independent spring/controller/pendulum/Newton-Euler mechanics, Radau temporal refinement and checkpoint continuation. The pinned pendulum uses an analytically constrained static seed because its neutral spin is a static mechanism.',source_sha256=hashes,versions=versions,cases=rows),indent=2,allow_nan=False)+'\n')
    print('Wrote nonlinear-initial.json',flush=True)

if __name__=='__main__':main()
