"""Independent complex section-output references; no ASWING/aircraft parity claim."""
from pathlib import Path
from dataclasses import replace
import hashlib
import json
import platform
import runpy
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem, output_perturbation, solve_modes
from openswing.frequency_response import solve_frequency_response

SOURCE = runpy.run_path(str(ROOT/'scripts/verify-section-outputs.py'))['source']
KEYS = ('cm','f_aero','f_reac','da_eff')
RHO, G, SOUND = 1.225, 9.80665, 340.294

def z(v): return np.asarray(v['real'])+1j*np.asarray(v['imag'])
def packed(v): return dict(real=np.asarray(v).real.tolist(),imag=np.asarray(v).imag.tolist())
def values(output): return np.array([[z(s[k]) for k in KEYS] for s in output['strips']])

def checked(actual, expected, scope):
    actual,expected=np.asarray(actual),np.asarray(expected)
    error=float(np.max(abs(actual-expected)/np.maximum(1,abs(expected))))
    assert error < 2e-7,(scope,error,actual,expected)
    return dict(scope=scope,computed=packed(actual),reference=packed(expected),maximum_scaled_error=error,
                complex_values_compared=actual.size)

def loaded_tangent(spec):
    """Prescribed stretch and rotation about y; differentiate closed scalar laws.

    This is an output tangent at a nonequilibrium state. It is not an eigenmode.
    V=(32,1,3), Omega=(0,.4,0), a_ref=(0,0,.5), Gamma=0, c=1 m.
    Distributed real mass is 2.5 kg/m of jig span with summed normal first
    moment .135 kg. Current span is stretched by lambda. A separate 10 kg
    point mass must not contribute to this distributed output.
    """
    units=spec.get('units',[1.,1.,1.]);L,T,F=units
    count=spec.get('panels',4);theta=np.deg2rad(spec['angle']);stretch=spec.get('stretch',1.2)
    lag=spec.get('lag',True);frozen=spec.get('frozen',False)
    c=FlightCondition(speed=30*T/L,alpha=0,mach=0,controls={1:3.},rates=[0,.4*T,0],
        acceleration=[0,0,.5*T*T/L],gust=dict(type='uniform',velocity=(np.array([2,1,3])*T/L).tolist()),
        aero_lag=lag,freeze_influences=frozen)
    net=StaticNetwork(parse_asw(SOURCE(spec)),count,c,None,[])
    base=np.zeros(net.size);shape=base[:6*net.nn].reshape(net.nn,6)
    shape[:,1]=(stretch-1)*net.rj[:,1]/net.L;shape[:,4]=theta
    system=DynamicSystem(net,base)
    v=np.zeros(system.size,complex);rate=v.copy()
    eta=.7+.2j;chi=.11-.08j;gamma=.3+.4j;gdot=.9-.6j;control=.4-.7j
    acceleration=np.array([.2+.1j,0,-.5+.3j])
    shape=v[:6*net.nn].reshape(net.nn,6);shape[:,1]=chi*net.rj[:,1]/net.L;shape[:,4]=eta
    sine=np.sin((np.arange(count)+.5)*np.pi/count)
    v[net.gamma_start:net.operating_start]=gamma*sine*T/L**2/net.gamma_scale
    rate[net.gamma_start:net.operating_start]=gdot*T*T/L**2/net.gamma_scale
    rate[system.velocity_start:system.velocity_start+3*net.nn]=np.tile(acceleration*T*T/L/system.V,net.nn)
    def forcing(part,increment):
        def apply(state,options):
            options['condition_override']=replace(options['condition_override'],controls={1:3+increment*(control.real if part==0 else control.imag)})
            return options
        return apply
    output=output_perturbation(system,v,rate,spec.get('step',1e-5),forcing=forcing)
    actual=values(output);actual[:,1:3]*=F/L
    s,co=np.sin(theta),np.cos(theta);speed=np.hypot(32,3);norm=np.sqrt(32**2+1+3**2)
    # Closed Glauert identity at a straight bound line; K/F retains jig span.
    dw=-count*np.sin(np.pi/(2*count))/(2*np.pi*(1 if frozen else stretch))*gamma
    beta=np.sqrt(1-(speed/SOUND)**2)
    dcm=.005*control/beta+(-.025)*3*dw/(SOUND**2*beta**3)
    fa=RHO*(32*co-3*s)*(gamma*sine+(gdot/speed if lag else 0))
    mass=2.5;ma=RHO*np.pi/4;normal_acceleration=s*acceleration[0]+co*acceleration[2]
    real=(mass*(-G-.5)*co+.4**2*(2*.08+.5*(-.05)))/stretch
    fr=(mass*(G+.5)*s*eta-mass*normal_acceleration)/stretch-real*chi/stretch
    fr+=ma*((-1.2*co-12.3*s)*eta-.4*s*dw-normal_acceleration)
    incidence=(32*co-3*s)*eta/norm+((co-1)/norm-(32*s+3*(co-1))*3/norm**3)*dw
    expected=np.column_stack([np.full(count,dcm),fa,np.full(count,fr),np.full(count,incidence)])
    return checked(actual,expected,'Prescribed loaded-state tangent against differentiated analytical force/geometry formulas')

def flow_matrix(count):
    """Independent straight horseshoe integrals at half-chord control points."""
    edge=-np.cos(np.linspace(0,np.pi,count+1));y=-np.cos((np.arange(count)+.5)*np.pi/count)
    a=y[:,None]-edge[:-1];b=y[:,None]-edge[1:];dx=.5
    ra=np.sqrt(dx*dx+a*a);rb=np.sqrt(dx*dx+b*b)
    return -(a/ra-b/rb)/(4*np.pi*dx)+((1+dx/rb)/b-(1+dx/ra)/a)/(4*np.pi)

def rigid_frequency(spec):
    count=spec.get('panels',4);lag=spec.get('lag',True)
    units=spec.get('units',[1.,1.,1.]);L,T,F=units
    inputs=['control.1',dict(kind='gust',wave='uniform')]
    initial=.2*np.sin((np.arange(count)+.5)*np.pi/count)
    if lag:inputs.append(dict(kind='initial',name='elliptic circulation',state=dict(circulation=(initial*T/L**2).tolist())))
    frequencies=np.array([0.,3.,25.])
    result=solve_frequency_response(parse_asw(SOURCE(spec)),FlightCondition(speed=30*T/L,alpha=0,mach=0,
        controls={1:3.},aero_lag=lag),count,gravity=[0,0,0],inputs=inputs,frequencies=frequencies*T,step=spec.get('step',1e-5))
    assert result['converged']
    actual=[];expected=[];W=flow_matrix(count);mass=2/(np.pi*30)*np.eye(count) if lag else np.zeros_like(W)
    for sample,omega in zip(result['samples'],frequencies):
        for i,response in enumerate(sample['responses']):
            out=values(response['output']);out[:,1:3]*=F/L
            out*=1 if i==0 else T/L if i==1 else T
            actual.append(out)
            ref=np.zeros((count,4),complex)
            if i==0:ref[:,0]=.005/np.sqrt(1-(30/SOUND)**2)
            else:
                gamma=np.linalg.solve(1j*omega*mass-W,np.ones(count) if i==1 else mass@initial)
                gdot=1j*omega*gamma-(initial if i==2 else 0)
                ref[:,1]=RHO*(30*gamma+(gdot if lag else 0))
            expected.append(ref)
    return checked(actual,expected,'Solved rigid-wing control/gust transfers and initial spectra against independent horseshoe equations')

def coupled_modes(spec):
    count=spec.get('panels',4);speed=40.;lag=spec.get('lag',True)
    result=solve_modes(parse_asw((ROOT/'examples/heave-pitch.asw').read_text()),
        FlightCondition(speed=speed,alpha=0,mach=0,stall=False,aero_lag=lag),count,
        gravity=[0,0,0],count=count+4,step=spec.get('step',1e-5))
    root=next(n['index'] for n in result['base']['nodes'] if n['beam']==2 and n['t']==0)
    actual=[];expected=[]
    for mode in result['modes']:
        lam=complex(*mode['eigenvalue']);out=mode['output'];h=z(out['nodes'][root]['displacement'])[2];theta=z(out['nodes'][root]['rotation'])[1]
        strips=[s for s in out['strips'] if s['beam']==2]
        gamma=np.array([z(s['circulation']) for s in strips])
        # All real mass is a separate Weight. Only apparent mass contributes
        # to f_reac. Its midchord lies .1 m aft of the elastic axis.
        ref=np.column_stack([np.zeros(len(gamma)),RHO*(speed+(lam if lag else 0))*gamma,
            np.full(len(gamma),RHO*np.pi/4*(-lam**2*h+.1*lam**2*theta+speed*lam*theta)),np.full(len(gamma),theta)])
        actual.append(values(dict(strips=strips)));expected.append(ref)
    report=checked(actual,expected,'Computed eigenmode outputs against independent heave/pitch load identities; not independent eigenvalue validation')
    report['eigenvalues']=[mode['eigenvalue'] for mode in result['modes']]
    return report

def compute(spec):
    return {'loaded':loaded_tangent,'frequency':rigid_frequency,'modes':coupled_modes}[spec['kind']](spec)

def physical(result):
    a=z(result['computed']);return np.r_[a.real.ravel(),a.imag.ravel()]

def main():
    specs=[dict(kind='loaded',angle=theta,stretch=stretch,panels=n,step=h,frozen=frozen,lag=lag)
        for theta,stretch,n,h,frozen,lag in [(-35,1.15,4,1e-5,False,True),(35,1.2,8,1e-5,False,True),
            (70,1.25,4,3e-6,False,True),(35,1.2,4,1e-5,True,False)]]
    specs += [dict(kind='loaded',angle=35,units=u) for u in [[.3048,2.,4.4482216152605],[100.,.25,.01]]]
    specs += [dict(kind='frequency',panels=n,lag=lag) for n,lag in [(4,True),(8,True),(4,False)]]
    specs += [dict(kind='frequency',units=[.3048,2.,4.4482216152605])]
    specs += [dict(kind='modes',panels=n,lag=lag,step=h) for n,lag,h in [(4,True,1e-5),(8,True,1e-5),(4,False,3e-6)]]
    cases=[]
    for spec in specs:
        result=compute(spec);cases.append(dict(specification=spec,result=result));print(spec,result['maximum_scaled_error'],flush=True)
    files=[Path(__file__),ROOT/'scripts/verify-section-outputs.py',ROOT/'examples/heave-pitch.asw',*sorted((ROOT/'openswing').glob('*.py'))]
    data=dict(description=__doc__,cases=cases,
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        limitations=['Loaded tangent cases are prescribed nonequilibrium fields.',
            'Modal load identities verify output recovery, not eigenvalue accuracy.',
            'Original ASWING sampling/interoperability and aircraft/experimental validation remain open.'])
    (ROOT/'docs/validation/dynamic-section-outputs.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()
