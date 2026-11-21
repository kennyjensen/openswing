"""Independent actuator-lag and nonlinear anti-windup verification records."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib,json,platform
import numpy as np
import scipy
from scipy.linalg import expm
from scipy.integrate import solve_ivp
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response
from openswing.time_integration import solve_time

SOURCE=Path('examples/instrumented-oscillator.asw').read_text()
C=FlightCondition(speed=10,alpha=0,mach=0,gravity_magnitude=0)
LAG=json.loads(Path('examples/actuator-lag-controller.json').read_text())
ANTI=json.loads(Path('examples/antiwindup-controller.json').read_text())


def spectrum(kind):
    controller=json.loads(json.dumps(LAG if kind=='lag' else ANTI))
    if kind=='antiwindup':controller['commands']={'RY[2]':2.02}
    roots=np.roots([.1,2.5,55,700]) if kind=='lag' else np.r_[np.roots([2,10,500]),-10]
    modes=solve_modes(parse_asw(SOURCE),C,4,controller=controller,count=3,tolerance=1e-11)
    actual=np.array([complex(*m['eigenvalue']) for m in modes['modes']])
    cost=abs(actual[:,None]-roots);i,j=linear_sum_assignment(cost);pole_error=float(max(cost[i,j]))
    assert pole_error<2e-6
    response=solve_frequency_response(parse_asw(SOURCE),C,4,controller=controller,frequencies=[0,3,10,30],
        inputs=['command.RY[2]'],tolerance=1e-11)
    samples=[];errors=[]
    for sample in response['samples']:
        output=sample['responses'][0]['output'];s=1j*sample['omega']
        def value(key):
            data=output['feedback'][key];return complex(data['real'],data['imag'])
        displacement=complex(output['sensors'][1]['displacement_body']['real'][1],output['sensors'][1]['displacement_body']['imag'][1])
        plant=2*s*s+10*s+500
        reference_y=200/((1+.05*s)*plant+200+20*s) if kind=='lag' else 0j
        state_name='lag' if kind=='lag' else 'I'
        reference_state=plant*reference_y if kind=='lag' else 19/(s+10)
        observed=[displacement,value('states_'+state_name),value('state_rates_'+state_name)]
        expected=[reference_y,reference_state,s*reference_state]
        errors.extend(abs(np.array(observed)-expected))
        samples.append(dict(omega=sample['omega'],actual=[[v.real,v.imag] for v in observed],reference=[[v.real,v.imag] for v in expected]))
    assert max(errors)<3e-6
    return dict(kind=kind+' steady spectrum and reference command response',controller=controller,panels=4,
        base=modes['base']['feedback'],maximum_pole_error=pole_error,maximum_transfer_error=float(max(errors)),
        poles=[[v.real,v.imag] for v in actual],reference_poles=[[v.real,v.imag] for v in roots],samples=samples,
        response_order=['displacement_y','custom_state','custom_state_rate'])


def lag_transient(dt):
    controller={**LAG,'commands':{'RY[2]':2.}}
    matrix=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20]])
    initial=np.array([.002,0,0]);weights=np.array([1,.05,.002])
    load=dict(beam=1,t=2,force=[0,1,0])
    out=solve_time(parse_asw(SOURCE),C,4,duration=.12,dt=dt,controller=controller,initial_loads=[load])
    samples=[];errors=[]
    for snapshot in out['snapshots']:
        sensor=snapshot['sensors'][1]
        actual=np.array([sensor['displacement_body'][1],sensor['anchor_velocity_body'][1],snapshot['feedback']['states']['lag']])
        exact=expm(matrix*snapshot['time'])@initial
        errors.append(np.linalg.norm((actual-exact)*weights))
        samples.append(dict(time=snapshot['time'],actual=actual.tolist(),reference=exact.tolist()))
    return dict(kind='actuator-lag load release',controller=controller,panels=4,step=dt,duration=.12,initial_load=load,
        reference_matrix=matrix.tolist(),reference_initial=initial.tolist(),weights=weights.tolist(),
        maximum_weighted_error=float(max(errors)),samples=samples)


def anti_transient(dt):
    initial=np.zeros(3);references=[]
    for start,end,command in [(0,.02,0),(.02,.12,.05),(.12,.2,0)]:
        def rate(t,q):
            y,v,I=q;e=y-command;desired=-200*e-100*I;actual=np.clip(desired,-5,5)
            return [v,(actual-10*v-500*y)/2,e-.1*(actual-desired)]
        solution=solve_ivp(rate,(start,end),initial,rtol=2e-12,atol=2e-14,dense_output=True,max_step=.001)
        assert solution.success
        references.append((end,solution));initial=solution.y[:,-1]
    forcing='time +RY[2]\n0 0\n.02 0\n.02 .05\n.12 .05\n.12 0\n.2 0'
    out=solve_time(parse_asw(SOURCE),C,4,duration=.2,dt=dt,controller=ANTI,forcing=forcing)
    samples=[];errors=[];weights=np.array([1,.05,2])
    for snapshot in out['snapshots']:
        sensor=snapshot['sensors'][1]
        actual=np.array([sensor['displacement_body'][1],sensor['anchor_velocity_body'][1],snapshot['feedback']['states']['I']])
        exact=next(s for end,s in references if snapshot['time']<=end+1e-12).sol(snapshot['time'])
        errors.append(np.linalg.norm((actual-exact)*weights))
        setting=snapshot['feedback']['actuators']['E1'];assert abs(setting)<=5+1e-8
        samples.append(dict(time=snapshot['time'],actual=actual.tolist(),reference=exact.tolist(),actuator=setting))
    return dict(kind='saturated anti-windup command/release',controller=ANTI,panels=4,step=dt,duration=.2,forcing=forcing,
        reference_solver=dict(method='RK45',rtol=2e-12,atol=2e-14,max_step=.001),weights=weights.tolist(),
        maximum_weighted_error=float(max(errors)),samples=samples)


if __name__=='__main__':
    cases=[spectrum(kind) for kind in ('lag','antiwindup')]
    cases += [lag_transient(dt) for dt in (.02,.01,.005)]
    cases += [anti_transient(dt) for dt in (.02,.01,.005)]
    for subset,bound in [(cases[2:5],.5),(cases[5:8],.65)]:
        errors=[c['maximum_weighted_error'] for c in subset]
        assert errors[1]<bound*errors[0] and errors[2]<bound*errors[1],errors
    files=[Path(__file__).resolve(),*[Path('examples',name).resolve() for name in
        ('instrumented-oscillator.asw','actuator-lag-controller.json','antiwindup-controller.json')],*sorted(Path('openswing').resolve().glob('*.py'))]
    report=dict(description='Independent custom controller mechanics and piecewise nonlinear ODE comparisons; not ASWING executable parity.',
        references=['https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf'],source=SOURCE,
        condition=dict(speed=10,alpha=0,mach=0,gravity_magnitude=0),cases=cases,
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        equations=['2 yddot + 10 ydot + 500 y = actuator','Lag: .05 actuator_dot = u - 200 error - 20 velocity - actuator',
            'Anti-windup: desired = u - 200 error - 100 I; actuator = clip(desired,-5,5); Idot = error - .1 (actuator-desired)'],
        limitations=['Weights give an explicit error norm, not an adaptive-step error estimate.',
            'Switching laws need time refinement; modal/harmonic linearization is local to a smooth branch.',
            'Aircraft and experimental custom-controller validation and arbitrary legacy subroutine compatibility remain.'])
    Path('docs/validation/custom-control.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Pole and transfer errors:',[(c['maximum_pole_error'],c['maximum_transfer_error']) for c in cases[:2]])
    print('Lag transient errors:',[c['maximum_weighted_error'] for c in cases[2:5]])
    print('Anti-windup transient errors:',[c['maximum_weighted_error'] for c in cases[5:8]])
