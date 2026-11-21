"""Original reduced/full/reference comparisons with resumable source provenance."""
import hashlib
import json
from pathlib import Path
import platform
import runpy
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from scipy.linalg import expm
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.reduced_model import solve_reduced_model

benchmark=runpy.run_path(str(Path(__file__).with_name('modal-benchmark.py')))
files=[Path(__file__).resolve(),Path('scripts/modal-benchmark.py').resolve(),
       Path('examples/instrumented-oscillator.asw').resolve(),*sorted(Path('openswing').resolve().glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
checkpoint=Path('.reference/rom-verification-checkpoint.json')
saved=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
cache=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def z(v):return np.array(v['real'])+1j*np.array(v['imag'])
def packed(v):return dict(real=np.asarray(v).real.tolist(),imag=np.asarray(v).imag.tolist())


def record(key,compute):
    if key in cache:
        print('Resumed '+key,flush=True);return cache[key]
    out=compute();cache[key]=out
    temporary=checkpoint.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(provenance=provenance,cases=cache),allow_nan=False))
    temporary.replace(checkpoint)
    print(key+': '+json.dumps(out['errors']),flush=True);return out


def oscillator(panels,step):
    source=Path('examples/instrumented-oscillator.asw').read_text()
    frequencies=[0.,1.,10.,np.sqrt(250),50.]
    rom=solve_reduced_model(parse_asw(source),FlightCondition(speed=10,alpha=0,mach=0),panels,
        gravity=[0,0,0],count=2,selected=[0],outputs=['RY[2]','UY[2]','Ay[2]'],step=step,frequencies=frequencies)
    exact=np.array([np.array([1,1j*w,-w*w])/(500+10j*w-2*w*w) for w in frequencies])[:,:,None]
    actual=np.array([z(s['reduced']) for s in rom['samples']])
    errors=np.max(abs(actual-exact),axis=0)/np.max(abs(exact),axis=0)
    assert errors.max()<2e-6,errors
    a,b,c,d=(np.array(rom['matrices'][key]) for key in ('A','B','C','D'))
    reference_a=np.array([[0.,1.],[-250.,-5.]])
    reference_b=np.array([[0.],[.5]]);reference_c=np.array([[1.,0.],[0.,1.],[-250.,-5.]])
    reference_d=np.array([[0.],[0.],[.5]])
    times=np.linspace(0,.5,51)
    histories=np.array([c@np.linalg.solve(a,(expm(a*t)-np.eye(2))@b)+d for t in times])
    reference=np.array([reference_c@np.linalg.solve(reference_a,(expm(reference_a*t)-np.eye(2))@reference_b)+reference_d for t in times])
    time_errors=np.max(abs(histories-reference),axis=0)/np.max(abs(reference),axis=0)
    assert time_errors.max()<2e-6,time_errors
    return dict(kind='spring-mass exact harmonic and force-step response',source=source,panels=panels,step=step,
        result=rom,independent=packed(exact),times=times.tolist(),step_response=histories.tolist(),
        independent_step_response=reference.tolist(),errors=dict(transfer=errors.tolist(),force_step=time_errors.tolist()))


def section_reference(speed,omega):
    # Independent per-span force and moment balances: [h,theta,v,q,Gamma].
    rho=1.225;ma=rho*np.pi/4;m=20*ma;j=.06*m
    a,d,e=-.15,.1,.1
    A=np.zeros((5,5));M=np.zeros((5,5));B=np.zeros((5,2))
    M[0,0]=M[1,1]=1.;A[0,2]=A[1,3]=1.
    M[2,2:]=[m+ma,-m*e-ma*d,-rho]
    M[3,2:]=[-m*e-ma*d,j+ma*(d*d+1/32),a*rho]
    A[2,[0,3,4]]=[-400*m,ma*speed,rho*speed]
    A[3,[1,3,4]]=[-2500*j,-ma*(d+.25)*speed,-a*rho*speed]
    M[4,4]=2/speed;A[4,[1,2,3,4]]=[np.pi*speed,-np.pi,np.pi*(a+.5),-1.]
    B[2,0]=1.;B[4,1]=np.pi
    x=np.linalg.solve(1j*omega*M-A,B)
    return np.array([x[0],1j*omega*x[0],-omega**2*x[0],180/np.pi*x[1]])


def section(span,count,tolerance):
    source=benchmark['configuration'](span).dumps()+f'\nEngine\n1 0 2 0 0 0 1 0 0 1 {span} 0 -1 0 0\nEnd\nSensor\n1 2 0 0 0 1\nEnd\n'
    frequencies=[1.,15.,25.,35.,50.];speed=40.
    rom=solve_reduced_model(parse_asw(source),FlightCondition(speed=speed,alpha=0,mach=0,stall=False),4,
        gravity=[0,0,0],count=count,step=1e-6,rank_tolerance=tolerance,inputs=['power.1',dict(kind='gust',wave='uniform')],
        outputs=['rz[1]','uz[1]','Az[1]','Ey[1]'],frequencies=frequencies)
    exact=np.array([section_reference(speed,w) for w in frequencies])
    full=np.array([z(s['full']) for s in rom['samples']]);reduced=np.array([z(s['reduced']) for s in rom['samples']])
    reference_error=np.max(abs(full-exact),axis=0)/np.max(abs(exact),axis=0)
    reduced_error=np.max(abs(reduced-full),axis=0)/np.max(abs(full),axis=0)
    if count>=8:assert reduced_error.max()<2e-5,reduced_error
    return dict(kind='heave-pitch-circulation with engine and uniform gust inputs',source=source,span=span,
        speed=speed,panels=4,requested_count=count,rank_tolerance=tolerance,result=rom,
        independent=packed(exact),errors=dict(full_vs_2d=reference_error.tolist(),rom_vs_full=reduced_error.tolist()))


if __name__=='__main__':
    cases=[record('oscillator-4',lambda:oscillator(4,1e-5)),record('oscillator-6',lambda:oscillator(6,2e-6))]
    for span,count,tolerance in [(80,8,1e-10),(160,8,1e-11),(2000,5,1e-12),(2000,8,1e-12)]:
        cases.append(record(f'section-{span}-{count}',lambda s=span,c=count,t=tolerance:section(s,c,t)))
    norms=[np.max(case['errors']['full_vs_2d']) for case in cases[2:4]+cases[-1:]]
    assert norms[1]<norms[0] and norms[2]<norms[1] and norms[2]<.01,norms
    assert np.max(cases[-2]['errors']['rom_vs_full'])>.5
    artifact=dict(description='Original modal ROM mechanical, constraint, acceleration and coupled aeroelastic verification; not an ASWING executable comparison.',
        **provenance,cases=cases,reference_equations=[
            '2 yddot+10 ydot+500 y=u; measured outputs [y,ydot,yddot]. Force-step reference is an independent 2-state matrix exponential.',
            'Coupled section uses independent heave/pitch force-moment balances plus the implemented empirical circulation lag. Source matrices are in section_reference().',
            'Full 3D beam-model response approaches the independent 2D section as span increases. The selected-mode ROM is separately compared with that same 3D full descriptor.'
        ],limitations=['Finite-span and empirical-lag models are not experimental or published ASWING validation.',
            'The deliberately truncated 6-state model omits the fast pitch pair; its response error is recorded rather than hidden.',
            'Large span weakens dimensionless inertia; each requested rank tolerance is explicit, and no failed tangent is accepted.'])
    Path('docs/validation/reduced-model.json').write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n')
    print('Completed six ROM reference cases; finite-span reference errors '+str(norms),flush=True)
