"""Independent closed-loop mechanical spectra/transfers and PI time refinement."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib,json,platform
import numpy as np
import scipy
from scipy.linalg import expm
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response
from openswing.time_integration import solve_time

SOURCE=Path('examples/instrumented-oscillator.asw').read_text()
C=FlightCondition(speed=10,alpha=0,mach=0)

def law(ki=0.,ka=0.):
    terms=[dict(input='RY[2]',gain=-200),dict(input='UY[2]',gain=-20)]
    if ki:terms.append(dict(input='RY[2]',gain=-ki,mode='integral'))
    if ka:terms.append(dict(input='Ay[2]',gain=-ka))
    return dict(outputs=[dict(actuator='E1',terms=terms)])

def complex_array(value):
    return np.asarray(value['real'])+1j*np.asarray(value['imag'])

def modal_frequency(ki,ka):
    control=law(ki,ka)
    modes=solve_modes(parse_asw(SOURCE),C,4,count=3 if ki else 2,controller=control,gravity=[0,0,0])
    expected=np.roots([2+ka,30,700,ki] if ki else [2+ka,30,700])
    actual=np.array([complex(*m['eigenvalue']) for m in modes['modes']])
    cost=abs(actual[:,None]-expected);i,j=linear_sum_assignment(cost)
    pole_error=float(max(cost[i,j]));assert pole_error<1e-6
    response=solve_frequency_response(parse_asw(SOURCE),C,4,frequencies=[0,.3,3,10,30,100],
        inputs=['power.1','command.RY[2]'],controller=control,gravity=[0,0,0])
    samples=[];errors=[]
    for sample in response['samples']:
        s=1j*sample['omega'];den=(2+ka)*s*s+30*s+700
        expected=[s/(s*den+ki),(200*s+ki)/(s*den+ki)] if ki else [1/den,200/den]
        actual=[complex_array(r['output']['sensors'][1]['displacement_body'])[1] for r in sample['responses']]
        errors.extend(abs(np.array(actual)-expected))
        samples.append(dict(omega=sample['omega'],actual=[[v.real,v.imag] for v in actual],
            reference=[[v.real,v.imag] for v in expected],diagnostics=sample['diagnostics']))
    assert max(errors)<1e-7
    return dict(kind='closed-loop poles and transfers',controller=control,panels=4,integral_gain=ki,acceleration_gain=ka,
        poles=[[v.real,v.imag] for v in actual_poles(modes)],reference_poles=[[v.real,v.imag] for v in np.roots([2+ka,30,700,ki] if ki else [2+ka,30,700])],
        maximum_pole_error=pole_error,maximum_transfer_error=float(max(errors)),samples=samples)

def actual_poles(modes):
    return [complex(*m['eigenvalue']) for m in modes['modes']]

def transient(dt):
    control=law(100);control['commands']={'RY[2]':2.}
    load=dict(beam=1,t=2,force=[0,1,0])
    out=solve_time(parse_asw(SOURCE),C,4,duration=.2,dt=dt,controller=control,gravity=[0,0,0],initial_loads=[load])
    a=np.array([[0,1,0],[-350,-15,-50],[1,0,0.]])
    initial=np.array([1/700,0,0]);samples=[];errors=[]
    for s in out['snapshots']:
        sensor=s['sensors'][1]
        actual=np.array([sensor['displacement_body'][1],sensor['anchor_velocity_body'][1],s['feedback']['integrals']['RY[2]']])
        exact=expm(a*s['time'])@initial
        errors.append(np.linalg.norm((actual-exact)*[1,.05,20]))
        samples.append(dict(time=s['time'],actual=actual.tolist(),reference=exact.tolist(),actuator=s['feedback']['actuators']['E1']))
    return dict(kind='PI load release',controller=control,step=dt,duration=.2,initial_load=load,panels=4,
        reference_matrix=a.tolist(),reference_initial=initial.tolist(),error_weights=[1,.05,20],
        maximum_weighted_error=float(max(errors)),samples=samples)

if __name__=='__main__':
    cases=[modal_frequency(*parameters) for parameters in [(0,0),(100,0),(0,3)]]
    cases += [transient(dt) for dt in (.02,.01,.005)]
    errors=[c['maximum_weighted_error'] for c in cases[3:]]
    assert errors[1]<.4*errors[0] and errors[2]<.4*errors[1],errors
    files=[Path(__file__).resolve(),Path('examples/instrumented-oscillator.asw').resolve(),*sorted(Path('openswing').resolve().glob('*.py'))]
    report=dict(description='Original independent feedback benchmarks; not ASWING executable or experimental parity.',
        references=['https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf'],
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        source=SOURCE,condition=dict(speed=10,alpha=0,mach=0,gravity=[0,0,0]),cases=cases,
        equations=['2 yddot + 10 ydot + 500 y = actuator',
            'actuator = command - 200 (y-reference) - 20 ydot - Ki I - Ka yddot',
            'Idot = y-reference'],
        limitations=['The time error norm weights velocity and integral coordinates explicitly; it is not an adaptive solver tolerance.',
            'The mechanical example has no wing aerodynamics; separate flexible-aircraft and experimental closed-loop validation remains.',
            'Gain-table index/unit bindings are explicit; this study does not establish default INDEXC compatibility.'])
    Path('docs/validation/feedback.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Maximum pole errors:',[c['maximum_pole_error'] for c in cases[:3]])
    print('Maximum transfer errors:',[c['maximum_transfer_error'] for c in cases[:3]])
    print('PI weighted time errors:',errors)
