"""Reproducible simultaneous controller/trim mechanics and aerodynamic checks."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib,json,platform
import numpy as np
import scipy
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.linear_dynamics import solve_modes
from openswing.frequency_response import solve_frequency_response


def mechanical(panels,ki):
    source=Path('examples/instrumented-oscillator.asw').read_text()
    terms=[dict(input='RY[2]',gain=-200),dict(input='UY[2]',gain=-20)]
    if ki:terms.append(dict(input='RY[2]',gain=-ki,mode='integral'))
    controller=dict(outputs=[dict(actuator='E1',terms=terms)])
    constraints=[dict(variable='command.RY[2]',quantity='force.y',target=5)]
    c=FlightCondition(speed=10,alpha=0,mach=0,gravity_magnitude=0)
    result=solve_static(parse_asw(source),c,panels,controller=controller,operating_constraints=constraints,tolerance=1e-11)
    f=result['feedback']
    actual=np.array([result['sensors'][1]['displacement_body'][1],f['actuators']['E1'],f['commands']['RY[2]'],f['integrals'].get('RY[2]',0)])
    exact=np.array([.01,5,2.01 if ki else 2.035,-5/ki if ki else 0])
    assert max(abs(actual-exact))<1e-8
    modes=solve_modes(parse_asw(source),c,panels,controller=controller,operating_constraints=constraints,count=3 if ki else 2,tolerance=1e-11)
    poles=np.array([complex(*m['eigenvalue']) for m in modes['modes']])
    expected=np.roots([2,30,700,ki] if ki else [2,30,700])
    cost=abs(poles[:,None]-expected);i,j=linear_sum_assignment(cost)
    pole_error=float(max(cost[i,j]));assert pole_error<1e-6
    response=solve_frequency_response(parse_asw(source),c,panels,controller=controller,operating_constraints=constraints,
        frequencies=[0,3,10,30],inputs=['power.1','command.RY[2]'],tolerance=1e-11)
    transfers=[];errors=[]
    for sample in response['samples']:
        s=1j*sample['omega'];den=2*s*s+30*s+700
        exact_transfer=np.array([s/(s*den+ki),(200*s+ki)/(s*den+ki)] if ki else [1/den,200/den])
        actual_transfer=np.array([complex(r['output']['sensors'][1]['displacement_body']['real'][1],
            r['output']['sensors'][1]['displacement_body']['imag'][1]) for r in sample['responses']])
        errors.extend(abs(actual_transfer-exact_transfer))
        transfers.append(dict(omega=sample['omega'],actual=[[v.real,v.imag] for v in actual_transfer],
            reference=[[v.real,v.imag] for v in exact_transfer]))
    assert max(errors)<1e-7
    return dict(kind='original spring-mass trim and released dynamics',source=source,panels=panels,
        condition=dict(speed=10,alpha=0,mach=0,gravity_magnitude=0),controller=controller,operating_constraints=constraints,
        actual=actual.tolist(),reference=exact.tolist(),coordinate_order=['displacement_y','actuator','command_RY','integral_RY'],
        equilibrium=result['controller_equilibrium'],maximum_pole_error=pole_error,
        maximum_transfer_error=float(max(errors)),transfers=transfers)


def aerodynamic(panels):
    source=Path('examples/rectangular.asw').read_text().split('t dCLdF1')[0]+'t Cm dCMdF1\n0 -.04 -.012\n6 -.04 -.012\nEnd\n'
    c=FlightCondition(alpha=1,mach=0)
    common=dict(variable='alpha',quantity='lift',target=2000)
    open_loop=solve_static(parse_asw(source),c,panels,operating_constraints=[common,dict(variable='control.1',quantity='moment.y',target=0)],tolerance=1e-10)
    controller=dict(commands={'A':1},outputs=[dict(actuator='F1',terms=[dict(input='A',gain=-2)])])
    constraints=[common,dict(variable='command.F1',quantity='moment.y',target=0)]
    result=solve_static(parse_asw(source),c,panels,controller=controller,operating_constraints=constraints,tolerance=1e-10)
    alpha=result['operating_values']['alpha'];f=result['feedback']
    expected_command=-.04/.012+2*(alpha-1)
    assert abs(f['actuators']['F1']+.04/.012)<1e-8
    assert abs(f['commands']['F1']-expected_command)<1e-8
    assert abs(alpha-open_loop['operating_values']['alpha'])<1e-7
    assert abs(result['operating_constraints'][0]['actual']-2000)<1e-6
    assert abs(result['applied_moment'][1])<1e-6
    return dict(kind='aerodynamic lift and pitch trim',source=source,panels=panels,
        condition=dict(alpha=1,mach=0),controller=controller,operating_constraints=constraints,
        alpha=alpha,open_loop_alpha=open_loop['operating_values']['alpha'],actuator=f['actuators']['F1'],
        analytic_actuator=-.04/.012,command=f['commands']['F1'],analytic_command=expected_command,
        lift=result['operating_constraints'][0]['actual'],pitch_moment=result['applied_moment'][1],equilibrium=result['controller_equilibrium'])


if __name__=='__main__':
    cases=[mechanical(panels,ki) for panels in (4,8) for ki in (0,100)]
    cases += [aerodynamic(panels) for panels in (4,8,12)]
    files=[Path(__file__).resolve(),Path('examples/instrumented-oscillator.asw').resolve(),Path('examples/rectangular.asw').resolve(),*sorted(Path('openswing').resolve().glob('*.py'))]
    report=dict(description='Independent mechanical controller trim and analytical aerodynamic moment checks, with open-loop lift-trim comparison.',
        references=['https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf','https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt'],
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},cases=cases,
        equations=['2 yddot + 10 ydot + 500 y = actuator','actuator = bias - 200 (y-reference) - 20 ydot - Ki I','Idot = y-reference',
            'Cm + dCMdF1 * F1 = 0; commanded F1 = F1 + 2 (alpha-1)'],
        limitations=['Mechanical equations and zero section pitch moment are independent references; aerodynamic lift comparison uses the same lifting-line kernel.',
            'This is not ASWING executable or experimental aircraft validation.',
            'Open-loop seed is the loaded structure at prescribed operating values, so an equilibrium seed is still required.'])
    Path('docs/validation/control-trim.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Mechanical maximum pole errors:',[c['maximum_pole_error'] for c in cases[:4]])
    print('Mechanical maximum transfer errors:',[c['maximum_transfer_error'] for c in cases[:4]])
    print('Aerodynamic alpha (4/8/12 panels):',[c['alpha'] for c in cases[4:]])
    print('Aerodynamic target residuals:',[c['equilibrium']['residual'] for c in cases[4:]])
