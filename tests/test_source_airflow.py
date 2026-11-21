"""Source airflow balances against stationary and analytical motion limits."""
import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.local_motion import NetworkMotion
from openswing.source_airflow import SourceAirflowNetwork
from openswing.source_airflow import AIRFLOW_POLICY
from openswing.source_coupled import SourceCoupledNetwork
from test_source_coupled import model as tapered_model, condition as tapered_condition, trial


UNIFORM = '''Name
Source airflow strip limits
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
10 1.2 340
End
Reference
1.6 .8 2
0 0 0
End
Ground
1 1 0
End
Beam 1
Uniform lifting strip
t x y z chord Xax Cdf Cdp Cm dCLda
1 0 0 0 .8 .13 0 0 0 6.283185307179586
3 0 2 0 .8 .13 0 0 0 6.283185307179586
End
'''

PANELS = {'default': 4, 'beams': {'1': {'count': 4, 'spacing': 'uniform'}}}


def uniform_network():
    model = parse_asw(UNIFORM, beam_interpolation='drela-segspl-v1')
    c = FlightCondition(speed=23., density=1.2, mach=0., alpha=0., beta=0.)
    return SourceAirflowNetwork(model, PANELS, c, [0.,0.,0.], [])


def evaluate(n, *, pitch=0., pitch_acceleration=0., heave_acceleration=0., gamma_rate=None):
    r, q, *_, gamma = n.unpack(np.zeros(n.size))
    zero = np.zeros_like(r)
    rates = zero.copy(); rates[:,1] = pitch
    acceleration = zero.copy(); acceleration[:,2] = heave_acceleration
    alpha = zero.copy(); alpha[:,1] = pitch_acceleration
    local = NetworkMotion(n, r, q, zero, rates, acceleration, alpha)
    meshes = n.deformed_meshes(r, q, n.geometry(r,q))
    values = n.external(r, q, meshes, gamma, n.condition, n.condition.motion(), (),
                        local_motion=local, circulation_rate=gamma_rate)
    force, couple, aero, _, ends_m, ends_f = values
    total_moment = (couple+np.cross(r,force)).sum(axis=0)
    return force.sum(axis=0), total_moment, values


@pytest.mark.parametrize('rigid', [False, True])
@pytest.mark.parametrize('mass', [False, True])
def test_zero_local_motion_matches_existing_source_coupled_balance(rigid, mass):
    model = tapered_model(rigid=rigid, mass=mass)
    condition = tapered_condition()
    steady = SourceCoupledNetwork(model, 4, condition, [1.,-2.,-10.])
    dynamic = SourceAirflowNetwork(model, 4, condition, [1.,-2.,-10.], [])
    state = trial(steady)
    zero = np.zeros_like(dynamic.rj)
    expected = steady.residual(state)
    actual = dynamic.residual(state, elastic_motion=(zero,zero,zero,zero),
                              circulation_rate=np.zeros(dynamic.circulation_basis.panels))
    np.testing.assert_allclose(actual, expected, rtol=3e-13, atol=3e-14)


@pytest.mark.parametrize('pitch,pitch_acceleration,heave_acceleration',
                         [(.7,0.,0.),(0.,-.4,0.),(0.,0.,1.8),(.7,-.4,1.8)])
def test_full_network_apparent_force_and_moment_match_thin_strip_limit(
        pitch, pitch_acceleration, heave_acceleration):
    n = uniform_network()
    force, moment, values = evaluate(n, pitch=pitch, pitch_acceleration=pitch_acceleration,
                                     heave_acceleration=heave_acceleration)
    chord, span, rho, speed, xax = .8, 2., 1.2, 23., .13
    mu = rho*np.pi*chord**2/4
    arm = (.5-xax)*chord
    lift = mu*(speed*pitch-heave_acceleration+arm*pitch_acceleration)
    couple = -arm*lift-mu*(chord*speed*pitch/4+chord**2*pitch_acceleration/32)
    # The deliberately prescribed zero circulation is not a flow-tangent
    # solution during pitching. Include the published tangency-drag term.
    velocity = np.array([speed,0.,pitch*(.25-xax)*chord])
    tangency = pitch*(.75-xax)*chord
    profile = 2*rho*chord*tangency**2*velocity/np.linalg.norm(velocity)
    expected_f = span*(profile+[0.,0.,lift])
    expected_m = [span**2/2*(lift+profile[2]),span*couple,-span**2/2*profile[0]]
    np.testing.assert_allclose(force, expected_f, rtol=3e-14, atol=3e-14)
    np.testing.assert_allclose(moment, expected_m, rtol=3e-14, atol=3e-14)
    np.testing.assert_allclose(values[2]['surface_apparent_force'],[0.,0.,span*lift],rtol=3e-14,atol=3e-14)
    # No real mass exists in this model: the real-inertia reporting cache must
    # remain exactly zero, including endpoint couples and forces.
    for index in (0,1,3,4):
        np.testing.assert_array_equal(n.mass_cached[index], 0.)
    # The source mixed-resultant rule requires equal endpoint applied wrenches.
    np.testing.assert_array_equal(values[4][:,0], values[4][:,1])
    np.testing.assert_array_equal(values[5][:,0], values[5][:,1])


def test_circulation_rate_force_has_quarter_chord_moment_and_cache_invalidation():
    n = uniform_network()
    rate = .37
    force, moment, _ = evaluate(n, gamma_rate=np.full(n.circulation_basis.panels, rate))
    lift = 1.2*rate*.8
    arm = (.25-.13)*.8
    profile = 2*1.2*.8*(2*rate/(np.pi*23))**2
    np.testing.assert_allclose(force, [2*profile,0.,2*lift], rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(moment, [2*lift,-2*arm*lift,-2*profile], rtol=2e-14, atol=2e-14)
    zero_force, zero_moment, _ = evaluate(n, gamma_rate=np.zeros(n.circulation_basis.panels))
    np.testing.assert_array_equal([zero_force,zero_moment], np.zeros((2,3)))
    # A new local rate must also invalidate the cached aerodynamic result.
    pitched, _, _ = evaluate(n, pitch=.2)
    assert pitched[2] > 1.
    zero_force, zero_moment, _ = evaluate(n)
    np.testing.assert_array_equal([zero_force,zero_moment], np.zeros((2,3)))


def test_source_airflow_does_not_silently_drop_its_condition():
    n = uniform_network()
    r,q,*_,gamma = n.unpack(np.zeros(n.size))
    with pytest.raises(AnalysisError, match='FlightCondition'):
        n.external(r,q,n.meshes,gamma,None,n.motion,())


def controlled_uniform():
    text = UNIFORM.rsplit('End\n',1)[0]+'t dCLdF1 dCMdF1\n1 1 0\n3 1 0\nEnd\n'
    return parse_asw(text, beam_interpolation='drela-segspl-v1')


@pytest.mark.parametrize('lag', [False, True])
def test_control_response_matches_analytic_bound_and_wake_integrals(lag):
    from openswing.frequency_response import solve_frequency_response
    speed, chord, semispan = 23., .8, 1.
    condition = FlightCondition(speed=speed, density=1.2, mach=0., alpha=0.,
                                stall=False, aero_lag=lag)
    result = solve_frequency_response(controlled_uniform(), condition, PANELS,
        frequencies=[.2,3.,20.,100.], inputs=['control.1'], frame='fixed',
        gravity=[0.,0.,0.], structural_operator=AIRFLOW_POLICY, matrices=True)
    assert result['converged'] and result['vacuum'] is False
    assert result['structural_operator'] == AIRFLOW_POLICY
    # Analytic integration of finite bound segments and trailing rays at the
    # 3/4-chord Glauert receivers. No production geometry or vortex functions.
    h = chord/2
    edges = np.linspace(-semispan,semispan,5)
    theta = np.arccos(edges/semispan)
    receivers = semispan*np.cos((theta[:-1]+theta[1:])/2)
    ya,yb = receivers[:,None]-edges[None,:-1],receivers[:,None]-edges[None,1:]
    ra,rb = np.sqrt(h*h+ya*ya),np.sqrt(h*h+yb*yb)
    a = -(ya/ra-yb/rb)/(4*np.pi*h)+((1+h/rb)/yb-(1+h/ra)/ya)/(4*np.pi)
    d = 2/(np.pi*speed) if lag else 0.
    aa, mm = (np.array(result['matrices'][key]) for key in ('A','M'))
    for sample in result['samples']:
        s = 1j*sample['omega']
        gamma = np.linalg.solve(-a+d*s*np.eye(4),np.full(4,speed/(2*np.pi)))
        cl = 2*(speed+(chord*s if lag else 0.))*np.dot(gamma,np.diff(edges))/(speed*speed*2*semispan*chord)
        response = sample['responses'][0]
        output = response['output']['global']
        z = lambda value: np.asarray(value['real'])+1j*np.asarray(value['imag'])
        assert z(output['CL']) == pytest.approx(cl, rel=3e-8, abs=2e-10)
        assert z(output['Cm']) == pytest.approx(-(.25-.13)*cl, rel=3e-8, abs=2e-10)
        np.testing.assert_allclose((s*mm-aa)@z(response['state']),z(sample['B'])[:,0],
                                   rtol=2e-9,atol=2e-10)
    assert ('differential' if lag else 'algebraic') == result['base']['aerodynamic_lag']['circulation']


@pytest.fixture(scope='module')
def flowing_pencil():
    from openswing.linear_dynamics import make_system, linearize
    from test_source_moving_system import beam_source
    model = parse_asw(beam_source(),beam_interpolation='drela-segspl-v1')
    condition = FlightCondition(speed=12.,alpha=2.,beta=1.,density=1.2,mach=0.,
        rates=(.17,-.13,.11),acceleration=(.25,-.18,.12),angular_acceleration=(.04,-.03,.02))
    system,_ = make_system(model,condition,4,frame='prescribed',gravity=[0.,0.,0.],
                          structural_operator=AIRFLOW_POLICY,tolerance=1e-10)
    zero = np.zeros(system.size)
    assert np.max(abs(system.residual(zero,zero))) < 1e-9
    dense = linearize(system,step=1e-5)
    sparse = tuple(a.toarray() for a in linearize(system,step=1e-5,sparse=True))
    return system,dense,sparse


def test_flowing_dense_and_sparse_pencils_match_complete_residual_actions(flowing_pencil):
    from test_source_moving_system import directional
    system,(a,m),(sa,sm) = flowing_pencil
    np.testing.assert_allclose(sa,a,rtol=3e-8,atol=3e-9)
    np.testing.assert_allclose(sm,m,rtol=3e-10,atol=3e-11)
    zero = np.zeros(system.size)
    rng = np.random.default_rng(93172)
    for _ in range(3):
        q = rng.normal(size=system.size);q /= np.linalg.norm(q)
        rate = np.zeros(system.size)
        rate[system.dynamic_indices] = rng.normal(size=len(system.dynamic_indices))
        rate /= np.linalg.norm(rate)
        expected_a = directional(lambda v: system.residual(v,zero),q)
        expected_m = -directional(lambda v: system.residual(zero,v),rate,h=.1)
        for aa,mm in ((a,m),(sa,sm)):
            np.testing.assert_allclose(aa@q,expected_a,rtol=3e-7,atol=3e-8)
            np.testing.assert_allclose(mm@rate,expected_m,rtol=3e-9,atol=3e-10)
