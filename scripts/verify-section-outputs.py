"""Independent analytical checks of the documented derived section outputs.

Prescribed moving-section cases verify instantaneous fields and loads, not
converged equilibria. Rigid and stationary-history cases are solved states.
"""
from pathlib import Path
import hashlib
import json
import platform
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import StaticNetwork, network_result, solve_static
from openswing.time_initialization import launch_time

G, RHO, SOUND = 9.80665, 1.225, 340.294


def source(spec):
    L, T, F = spec.get('units', [1., 1., 1.])
    return ('! Original derived-output verification: two distributed masses and a separate 10 kg point mass.\n'
        'Name\nNormal section loads\nEnd\nUnit\n'
        f'L {L:.17g} m\nT {T:.17g} s\nF {F:.17g} N\nEnd\nConstant\n'
        f'{G*T*T/L:.17g} {RHO*L**4/(F*T*T):.17g} {SOUND*T/L:.17g}\nEnd\n'
        f'Reference\n{2/L**2:.17g} {1/L:.17g} {2/L:.17g}\nEnd\nGround\n1 0 0\nEnd\nWeight\n'
        f'1 0 0 0 0 {10*G/F:.17g} 0 0 0 0 0 0 0 0\nEnd\nBeam 1\nRigid reference wing\n'
        't x y z chord Xax Cdf Cm dCMdF1 mg Ccg Ncg Dmg DCcg DNcg\n'+
        ''.join(f'{t} 0 {t/L:.17g} 0 {1/L:.17g} .25 .02 -.04 .005 '
                f'{2*G*L/F:.17g} {.1/L:.17g} {.08/L:.17g} {.5*G*L/F:.17g} '
                f'{-.2/L:.17g} {-.05/L:.17g}\n' for t in [-1, 1])+'End\n')


def values(result, units):
    L, T, F = units
    return np.array([[s['cm'], s['f_aero']*F/L, s['f_reac']*F/L,
                      np.nan if s['da_eff'] is None else s['da_eff']] for s in result['strips']])


def compute(spec):
    units = spec.get('units', [1., 1., 1.]); L, T, F = units
    model = parse_asw(source(spec)); n = spec.get('panels', 8)
    condition = FlightCondition(speed=30*T/L, alpha=0., mach=0., controls={1:3.},
        freeze_influences=spec.get('frozen', False), aero_lag=spec.get('lag', True))
    kind = spec['kind']
    if kind == 'rigid':
        condition.acceleration = [0., 0., 1.2*T*T/L]
        condition.attitude = [17., 8., 23.]
        result = solve_rigid(model, condition, n)
        expected = [(-.04+.005*3)/np.sqrt(1-(30/SOUND)**2), 0.,
                    2.5*(-G*np.cos(np.deg2rad(17))*np.cos(np.deg2rad(8))-1.2)-RHO*np.pi/4*1.2, 0.]
        status = 'solved rigid operating point'
    elif kind == 'elliptic_load':
        net = StaticNetwork(model, n, condition, None, [])
        x = np.zeros(net.size)
        gamma = np.sin((np.arange(n)+.5)*np.pi/n)
        x[net.gamma_start:net.operating_start] = gamma*T/L**2/net.gamma_scale
        result = network_result(net, x, circulation_rate=np.full(net.ng, .7*T*T/L**2))
        # Independent Glauert midpoint identity for a straight unswept line
        # with prescribed Gamma = sin(theta) m^2/s and projected semispan 1 m.
        downwash = -n*np.sin(np.pi/(2*n))/(2*np.pi)
        speed = np.hypot(30., downwash)
        rate_lift = RHO*.7*30/speed if condition.aero_lag else 0.
        expected = np.column_stack([np.full(n,(-.04+.005*3)/np.sqrt(1-(speed/SOUND)**2)),
                                    RHO*30*gamma+rate_lift,np.full(n,-2.5*G),np.zeros(n)])
        status = 'prescribed elliptic circulation and rate; not a solved operating point'
    elif kind == 'moving':
        angle = np.deg2rad(spec['angle']); stretch = spec.get('stretch', 1.)
        condition.rates = [0., .4*T, 0.]
        condition.acceleration = [0., 0., .5*T*T/L]
        condition.gust = dict(type='uniform', velocity=(np.array([2.,1.,3.])*T/L).tolist())
        net = StaticNetwork(model, n, condition, None, [])
        x = np.zeros(net.size); kinematic = x[:6*net.nn].reshape(net.nn, 6)
        kinematic[:, 1] = (stretch-1)*net.rj[:, 1]/net.L
        kinematic[:, 4] = angle
        zero = np.zeros_like(net.rj)
        velocity = np.tile(np.array([1.,0.,-2.])*T/L, (net.nn,1))
        acceleration = np.tile(np.array([0.,0.,.9])*T*T/L, (net.nn,1))
        result = network_result(net, x, elastic_motion=(velocity, zero, acceleration, zero),
                                circulation_rate=np.full(net.ng, .7*T*T/L**2))
        # Straight span remains along y. These expressions use a prescribed
        # y rotation and physical kinematics, with no production field/frame API.
        sine, cosine = np.sin(angle), np.cos(angle)
        speed = np.hypot(31., 5.)
        da = (31*sine+5*(cosine-1))/np.sqrt(31**2+1+5**2)
        aerodynamic = RHO*.7*(31*cosine-5*sine)/speed if condition.aero_lag else 0.
        # a_axis = a_ref + 2 Omega x u + du/dt = (-1.6,0,.6).
        # Offset centripetal acceleration projects to -Omega^2 * Ncg.
        real = (2.5*(1.6*sine+(-G-.6)*cosine)+.4**2*(2*.08+.5*(-.05)))/stretch
        apparent = RHO*np.pi/4*(-.4*sine+11.8*cosine)
        expected = [(-.04+.005*3)/np.sqrt(1-(speed/SOUND)**2), aerodynamic, real+apparent, da]
        status = 'prescribed nonequilibrium instantaneous state; not a solved operating point'
    elif kind == 'stationary_history':
        steady = solve_static(model, condition, n)
        history = launch_time(model, steady['equilibrium_state'], duration=.02/T, dt=.01/T)
        expected = [(-.04+.005*3)/np.sqrt(1-(30/SOUND)**2), 0., -2.5*G, 0.]
        result = steady
        for state in [steady, *history['snapshots']]:
            np.testing.assert_allclose(values(state, units), np.tile(expected,(len(state['strips']),1)), atol=2e-8, rtol=2e-8)
            assert abs(state['support_force'][2]*F-15*G) < 2e-7
        status = 'solved steady state and three stationary physical time snapshots'
    else:
        raise ValueError(kind)
    actual = values(result, units)
    error = float(np.max(abs(actual-expected)))
    assert error < 2e-8, (spec, error, actual, expected)
    return dict(status=status, reference=np.asarray(expected).tolist(), samples=actual.tolist(), maximum_absolute_error=error,
                physical_values_compared=actual.size*(4 if kind=='stationary_history' else 1),
                snapshots=3 if kind=='stationary_history' else 0)


def physical(result):
    return np.array(result['samples']).ravel()


def main():
    specs = [dict(kind='rigid',panels=n) for n in [4,8,16]]
    specs += [dict(kind='elliptic_load',panels=n,lag=lag) for n,lag in [(4,True),(16,True),(32,False)]]
    specs += [dict(kind='moving',angle=a,stretch=s,panels=8,frozen=f,lag=lag)
              for a,s,f,lag in [(-35.,1.,False,True),(35.,1.,False,True),(70.,1.25,False,True),
                                (35.,1.2,True,True),(35.,1.2,True,False)]]
    specs += [dict(kind='moving',angle=-35.,stretch=1.15,units=u,panels=8)
              for u in [[.3048,2.,4.4482216152605],[100.,.25,.01]]]
    specs += [dict(kind='stationary_history',panels=4)]
    cases=[]
    for spec in specs:
        result=compute(spec);cases.append(dict(specification=spec,result=result))
        print(spec, result['maximum_absolute_error'],flush=True)
    sources=[Path(__file__),*sorted((ROOT/'openswing').glob('*.py'))]
    data=dict(description=__doc__,cases=cases,
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        limitations=['Moving cases prescribe geometry, circulation and motion; they do not validate equilibrium convergence.',
                     'f_reac uses interval-average distributed inertia. Original ASWING midpoint/nodal-output parity remains unverified.',
                     'These analytical checks do not establish aircraft or experimental validity.'])
    (ROOT/'docs/validation/section-outputs.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
