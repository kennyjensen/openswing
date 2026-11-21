"""Independent section references for the documented ASWING K/L option."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.linalg import eigvals
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.frequency_response import solve_frequency_response
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.time_integration import solve_time
from openswing.reduced_model import solve_reduced_model


def wing_source(units=(1.,1.,1.)):
    L,T,F=units
    return f'''! Original infinite-span-limit verification wing, not an aircraft.
Name
Aerodynamic lag section limit
End
Unit
L {L} m
T {T} s
F {F} N
End
Constant
{9.80665*T*T/L} {1.225*L**4/(F*T*T)} {340.294*T/L}
End
Reference
{200000/L**2} {1/L} {200000/L}
End
Ground
1 0 0
End
Beam 1
Rigid symmetric lifting line
t y chord Xax Cdf dCLda CLmax CLmin
0 0 {1/L} .25 0 {2*np.pi} 100 -100
1 {100000/L} {1/L} .25 0 {2*np.pi} 100 -100
End
'''


def section_poles(speed,lag):
    """Independent heave/pitch equations per unit span, chord 1 metre.

    M qddot = K q + D qdot + [1,-a] rho U Gamma.
    With lag disabled, substitute Gamma=pi*(U theta-hdot+(a+.5) thetadot).
    The retained added-mass acceleration and pitch-rate terms form M and D.
    """
    rho=1.225;ma=rho*np.pi/4;m=20*ma;j=.06*m;e=.1;d=.1;a=-.15
    mass=np.array([[m+ma,-m*e-ma*d],[-m*e-ma*d,j+ma*(d*d+1/32)]])
    stiffness=np.diag([-m*20**2,-j*50**2])
    damping=np.array([[0,ma*speed],[0,-ma*(d+.25)*speed]])
    lift=rho*speed*np.array([1.,-a]);rate=rho*np.array([1.,-a])
    gq=np.array([0.,np.pi*speed]);gv=np.array([-np.pi,np.pi*(a+.5)])
    if not lag:
        stiffness+=np.outer(lift,gq);damping+=np.outer(lift,gv)
        generator=np.block([[np.zeros((2,2)),np.eye(2)],
                            [np.linalg.solve(mass,stiffness),np.linalg.solve(mass,damping)]])
        return eigvals(generator)
    A=np.zeros((5,5));M=np.zeros((5,5));M[:2,:2]=np.eye(2);A[:2,2:4]=np.eye(2)
    M[2:4,2:4]=mass;M[2:4,4]=-rate
    A[2:4,:2]=stiffness;A[2:4,2:4]=damping;A[2:4,4]=lift
    M[4,4]=2/speed;A[4,:2]=gq;A[4,2:4]=gv;A[4,4]=-1
    return eigvals(A,M)


def finite_wing_poles(span,panels,speed,lag,modes=0,frequencies=None):
    """Closed planar horseshoe integrals plus two mechanical coordinates.

    No production vortex, geometry, circulation-basis or descriptor routine is
    used. The rigid wing leaves only heave, pitch and the circulation unknowns.
    Cosine nodes and Glauert midpoints define the independently assembled grid.
    For disabled lag, optional frequencies return heave/velocity/acceleration
    and pitch-angle transfers plus direct acceleration feedthrough.
    """
    edge=-span/2*np.cos(np.linspace(0,np.pi,panels+1));theta=(np.arange(panels)+.5)*np.pi/panels
    y=-span/2*np.cos(theta);ds=np.diff(edge);dx=.5
    da=y[:,None]-edge[:-1];db=y[:,None]-edge[1:]
    ra=np.sqrt(dx*dx+da*da);rb=np.sqrt(dx*dx+db*db)
    bound=-(da/ra-db/rb)/(4*np.pi*dx)
    wake=((1+dx/rb)/db-(1+dx/ra)/da)/(4*np.pi)
    w=bound+wake
    basis=np.sin((np.pi-theta)[:,None]*np.arange(1,modes+1)) if modes else np.eye(panels)
    weight=ds@basis/span;flow=basis.T@w@basis;uniform=basis.T@np.ones(panels)
    rho=1.225;ma=rho*np.pi/4;m=20*ma;j=.06*m;e=.1;d=.1;a=-.15
    mass=np.array([[m+ma,-m*e-ma*d],[-m*e-ma*d,j+ma*(d*d+1/32)]])
    stiffness=np.diag([-m*20**2,-j*50**2]);damping=np.array([[0,ma*speed],[0,-ma*(d+.25)*speed]])
    lift=rho*speed*np.array([1.,-a]);rate=rho*np.array([1.,-a])
    gq=np.array([0.,speed]);gv=np.array([-1.,a+.5])
    if not lag:
        gain=-weight@np.linalg.solve(flow,uniform)
        stiffness+=gain*np.outer(lift,gq);damping+=gain*np.outer(lift,gv)
        generator=np.block([[np.zeros((2,2)),np.eye(2)],
            [np.linalg.solve(mass,stiffness),np.linalg.solve(mass,damping)]])
        if frequencies is not None:
            forcing=np.r_[np.zeros(2),np.linalg.solve(mass,lift*gain)]
            response=[]
            for omega in frequencies:
                state=np.linalg.solve(1j*omega*np.eye(4)-generator,forcing)
                response.append([state[0],1j*omega*state[0],-omega**2*state[0],180/np.pi*state[1]])
            return np.array(response),forcing[2]
        return eigvals(generator)
    count=basis.shape[1];A=np.zeros((4+count,4+count));M=np.zeros_like(A)
    M[:2,:2]=np.eye(2);A[:2,2:4]=np.eye(2);M[2:4,2:4]=mass
    M[2:4,4:]=-np.outer(rate,weight);A[2:4,:2]=stiffness;A[2:4,2:4]=damping
    A[2:4,4:]=np.outer(lift,weight);M[4:,4:]=2/(np.pi*speed)*(basis.T@basis)
    A[4:,:2]=np.outer(uniform,gq);A[4:,2:4]=np.outer(uniform,gv);A[4:,4:]=flow
    return eigvals(A,M)


def compute(spec):
    kind=spec['kind'];lag=spec['lag'];units=spec.get('units',[1.,1.,1.]);L,T,F=units
    c=FlightCondition(speed=30*T/L,alpha=0,mach=0,stall=False,aero_lag=lag,
                      circulation_modes={1:spec.get('modes',0)})
    if kind=='frequency':
        result=solve_frequency_response(parse_asw(wing_source(units)),c,spec['panels'],gravity=[0,0,0],
            frequencies=np.array([0.,1.,3.,30.,100.,300.])*T,inputs=[dict(kind='gust',wave='uniform')])
        actual=[];expected=[]
        for sample in result['samples']:
            assert sample['converged']
            omega=sample['omega']/T;v=sample['responses'][0]['output']['global']['CL']
            actual.append(complex(v['real'],v['imag'])*T/L)
            expected.append(2*np.pi/30*((1+1j*omega/30)/(1+2j*omega/30) if lag else 1))
        error=float(np.max(abs(np.array(actual)-expected)/abs(np.array(expected))))
        assert error<2e-4,error
        return dict(kind=kind,omega=[s['omega']/T for s in result['samples']],
            response=[[z.real,z.imag] for z in actual],expected=[[z.real,z.imag] for z in expected],
            maximum_relative_error=error,lag=result['base']['aerodynamic_lag'])
    if kind=='time':
        c.gust=dict(type='expression',components=['0','0',f'{.001*T*T/L:.17g}*t'])
        result=solve_time(parse_asw(wing_source(units)),c,spec['panels'],gravity=[0,0,0],
            duration=.1/T,dt=spec['step']/T,tolerance=1e-10)
        time=np.array([s['time']*T for s in result['snapshots']]);cl=np.array([s['CL'] for s in result['snapshots']])
        tau=2/30
        gamma=np.pi*.001*(time-tau*(1-np.exp(-time/tau))) if lag else np.pi*.001*time
        rate=np.pi*.001*(1-np.exp(-time/tau)) if lag else np.zeros_like(time)
        expected=2*(gamma+rate/30)/30
        error=float(np.max(abs(cl-expected)))
        if not lag:assert error<2e-9,error
        return dict(kind=kind,time=time.tolist(),CL=cl.tolist(),expected=expected.tolist(),maximum_error=error,
            circulation_rate_force_z=[s['circulation_rate_force'][2]*F for s in result['snapshots']],
            lag=result['snapshots'][-1]['aerodynamic_lag'])
    if kind=='modes':
        helper=runpy.run_path('scripts/modal-benchmark.py');model=helper['configuration'](spec['span'])
        c=FlightCondition(speed=spec['speed'],alpha=0,mach=0,stall=False,aero_lag=lag,
                          circulation_modes={2:spec.get('modes',0)})
        system,_=make_system(model,c,spec['panels'],gravity=[0,0,0])
        step=spec.get('difference_step',1e-6);method=spec.get('method','dense')
        rank=spec.get('rank_tolerance',1e-9);shift=spec.get('shift',[-.1,20.])
        a,m=linearize(system,step=step)
        count=4+(system.network.ng if lag else 0)
        modes,meta=eigensystem(a,m,time_scale=system.W,count=count,rank_tolerance=rank,method=method,shift=shift)
        values=np.array([complex(*v['eigenvalue']) for v in modes]);n=system.network
        assert len(values)==count
        assert meta['finite_dimension']==(None if method=='full_shift_invert' else count)
        if not lag:assert np.max(abs(m[:,n.gamma_start:n.operating_start]))==0
        expected=section_poles(spec['speed'],lag)
        if lag:expected=np.r_[expected,np.full(n.ng-1,-spec['speed']/2)]
        rows,cols=linear_sum_assignment(abs(values[:,None]-expected[None,:]))
        ordered=values[rows[np.argsort(cols)]]
        error=float(np.max(abs(ordered-expected)/np.maximum(1,abs(expected))))
        finite=finite_wing_poles(spec['span'],spec['panels'],spec['speed'],lag,spec.get('modes',0))
        fr,fc=linear_sum_assignment(abs(ordered[:,None]-finite[None,:]))
        finite=finite[fc[np.argsort(fr)]]
        finite_error=float(np.max(abs(ordered-finite)/np.maximum(1,abs(finite))))
        assert finite_error<2e-6,finite_error
        residual=max(v['right_backward_error'] for v in modes);assert residual<1e-9
        if spec['span']>=4000:assert error<.01,error
        return dict(kind=kind,poles=[[v.real,v.imag] for v in ordered],
            expected=[[v.real,v.imag] for v in expected],maximum_relative_error=error,
            finite_reference=[[v.real,v.imag] for v in finite],finite_reference_relative_error=finite_error,
            returned_modes=len(values),finite_dimension=meta['finite_dimension'],method=meta['method'],
            difference_step=step,rank_tolerance=meta['rank_tolerance'],shift=shift,maximum_backward_error=residual)
    if kind=='rom':
        assert not lag
        helper=runpy.run_path('scripts/modal-benchmark.py')
        model=parse_asw(helper['configuration'](spec['span']).dumps()+'\nSensor\n1 2 0 0 0 1\nEnd\n')
        c=FlightCondition(speed=spec['speed'],alpha=0,mach=0,stall=False,aero_lag=False)
        omega=[0.,1.,15.,25.,35.,50.,300.]
        result=solve_reduced_model(model,c,spec['panels'],gravity=[0,0,0],count=4,step=1e-6,
            inputs=[dict(kind='gust',wave='uniform')],outputs=['rz[1]','uz[1]','Az[1]','Ey[1]'],frequencies=omega)
        assert result['spectrum']['finite_dimension']==result['diagnostics']['dimension']==4
        assert all(s['converged'] for s in result['samples'])
        expected,direct=finite_wing_poles(spec['span'],spec['panels'],spec['speed'],False,frequencies=omega)
        def unpack(key):return np.array([np.array(s[key]['real'])[:,0]+1j*np.array(s[key]['imag'])[:,0] for s in result['samples']])
        reduced,full=unpack('reduced'),unpack('full')
        scale=np.maximum(1e-10,np.max(abs(expected),axis=0))
        error=float(np.max(abs(reduced-expected)/scale));full_error=float(np.max(abs(reduced-full)/scale))
        assert error<2e-6 and full_error<2e-6,(error,full_error)
        actual_direct=result['matrices']['D'][2][0]
        assert abs(actual_direct-direct)<2e-6*abs(direct),(actual_direct,direct)
        assert np.max(np.abs(result['matrices']['D_rate']))<1e-8
        return dict(kind=kind,omega=omega,response=np.stack([reduced.real,reduced.imag],axis=-1).tolist(),
            expected=np.stack([expected.real,expected.imag],axis=-1).tolist(),maximum_relative_error=error,
            maximum_full_reduced_error=full_error,acceleration_feedthrough=actual_direct,expected_feedthrough=direct,
            dimension=result['diagnostics']['dimension'],lag=result['base']['aerodynamic_lag'])
    raise ValueError(kind)


def physical(result):
    key={'frequency':'response','time':'CL','modes':'poles','rom':'response'}[result['kind']]
    values=np.asarray(result[key]).ravel()
    return np.r_[values,result['acceleration_feedthrough']] if result['kind']=='rom' else values


def main():
    sources=sorted(Path('openswing').glob('*.py'))+[Path(p) for p in ['scripts/verify-aero-lag.py','scripts/modal-benchmark.py','tests/test_aero_lag.py']]
    source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    cases=[]
    def add(name,**spec):
        print('Starting '+name,flush=True)
        result=compute(spec);cases.append(dict(name=name,specification=spec,result=result));print(name,flush=True)
    for lag in [False,True]:
        for modes in [0,3]:add(f'frequency/lag={lag}/modes={modes}',kind='frequency',lag=lag,modes=modes,panels=8)
    for units in [[1.,1.,1.],[.3048,.1,4.4482216152605],[1000.,60.,1000.]]:
        add(f'time/algebraic/{units}',kind='time',lag=False,panels=4,step=.02,units=units)
    for step in [.02,.01,.005]:add(f'time/lagged/{step}',kind='time',lag=True,panels=4,step=step)
    errors=[c['result']['maximum_error'] for c in cases if c['specification']['kind']=='time' and c['specification']['lag']]
    assert all(a/b>2.5 for a,b in zip(errors,errors[1:])),errors
    for lag in [False,True]:
        for span in [40.,400.,4000.]:add(f'modes/lag={lag}/span={span}',kind='modes',lag=lag,panels=4,span=span,speed=50.,
            rank_tolerance=1e-11 if span==400 else 1e-9,method='full_shift_invert' if span==4000 else 'dense')
        errors=[c['result']['maximum_relative_error'] for c in cases if c['specification']['kind']=='modes' and c['specification']['lag']==lag]
        assert errors[2]<errors[1]<errors[0],errors
    for panels in [8,12]:add(f'modes/algebraic/panels={panels}',kind='modes',lag=False,panels=panels,modes=3,span=400.,speed=50.,method='full_shift_invert')
    for lag in [False,True]:
        for step,shift in [(1e-6,[10.,40.]),(2e-6,[-.1,20.])]:
            add(f'modes/refinement/lag={lag}/step={step}/shift={shift}',kind='modes',lag=lag,panels=4,span=4000.,speed=50.,
                method='full_shift_invert',difference_step=step,shift=shift)
    add('rom/algebraic/gust',kind='rom',lag=False,panels=4,span=40.,speed=50.)
    assert source_hashes=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'Study source changed during execution.'
    report=dict(scope='Documented K/L option: rate-load removal, algebraic circulation, independent section frequency/time/pole limits, finite-wing ROM transfers and consistent units. Not ASWING executable or aircraft/experimental parity.',
        source_sha256=source_hashes,cases=cases)
    Path('docs/validation/aero-lag.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Aerodynamic-lag study passed: {len(cases)} cases.',flush=True)


if __name__=='__main__':main()
