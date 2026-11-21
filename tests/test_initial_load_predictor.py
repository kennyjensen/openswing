"""No-equilibrium checks for the optional first-load rotation predictor.

The fixtures are synthetic. Load derivatives are checked against full physical
residual stencils, while fallback tests deliberately inject failed queries or
linear solves. No aircraft, equilibrium solve, or relaxed rotation gate is used.
"""
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.sparse import csc_matrix, eye
from scipy.spatial.transform import Rotation

from openswing.aero import AnalysisError
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_dynamics import SourceMovingNetwork
from openswing.source_airflow import SourceAirflowNetwork
from openswing.inertia import Motion
from openswing.source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
import openswing.structured_static as static
from test_source_joints import source, mounted_condition


CLASSES = [StaticNetwork, SourceDiscreteNetwork, SourceSectionNetwork,
           SourceCoupledNetwork, SourceMovingNetwork, SourceAirflowNetwork]
CURVE = '-5 -4\n0 1\n5 9'
LIMIT = np.deg2rad(5.)


@pytest.fixture(autouse=True)
def forbid_equilibrium(monkeypatch):
    """A predictor may inspect equations and solve one linear system only."""
    import openswing.network as network
    def forbidden(*args, **kwargs):
        pytest.fail('This suite must not run an equilibrium solve.')
    monkeypatch.setattr(static, 'equilibrate', forbidden)
    monkeypatch.setattr(network, '_equilibrate_full', forbidden)


def network(cls=SourceSectionNetwork, *, joint_t=3., curve=CURVE):
    general = cls is not SourceDiscreteNetwork
    model = parse_asw(source(offsets=general, mass=general, joint_t=joint_t,
                             curve=curve), beam_interpolation='drela-segspl-v1')
    flight = mounted_condition() if cls in (StaticNetwork, SourceCoupledNetwork, SourceAirflowNetwork) else None
    options = {}
    if cls is SourceMovingNetwork:
        options['motion'] = Motion([.3, -.2, .4], [.2, -.1, .3], [-.1, .3, .2])
    elif cls is SourceAirflowNetwork:
        flight.rates, flight.acceleration, flight.angular_acceleration = [.3, -.2, .4], [.2, -.1, .3], [-.1, .3, .2]
    loads = [dict(beam=2, t=3., force=[.3, -.2, .5], moment=[.1, .2, -.3])]
    return cls(model, 4, flight, [1., -2., -10.], loads, **options)


def random_state_at_known_hinge_moment(net, moment=2.5):
    rng = np.random.default_rng(61421)
    x = rng.normal(0., .004, net.size)
    pose = x[:6*net.nn].reshape(net.nn, 6)
    pose[:, 3:] = rng.normal(0., .12, (net.nn, 3))
    r = net.rj+net.L*pose[:, :3]
    q = Rotation.from_rotvec(pose[:, 3:]).as_matrix()
    wrench = x[6*net.nn:6*(net.nn+net.ne)].reshape(net.ne, 6)
    wrench[:, :3] = rng.normal(0., 2., (net.ne, 3))/net.F
    wrench[:, 3:] = rng.normal(0., 3., (net.ne, 3))/(net.F*net.L)
    c = next(c for c in net.constraints if c['type'] == 3)
    e = c['element']; sign = -1 if c['end'] else 1
    axis = q[c['a']]@np.array([2., 1., 3.])/np.sqrt(14.)
    # The fixture has no stepped beam axis. At lambda=0 the endpoint trace is
    # M +/- (r_b-r_a) cross N / 2, independently of distributed end couples.
    force = wrench[e, :3]*net.F
    body_moment = moment*axis-sign*np.cross(r[net.b[e]]-r[net.a[e]], force)/2
    wrench[e, 3:] = body_moment/(net.F*net.L)
    if net.ng:
        x[net.gamma_start:net.operating_start] = .04*np.sin(np.linspace(.3, 2.8, net.ng))
    return x, c, r, q


@pytest.mark.parametrize('cls', CLASSES)
@pytest.mark.parametrize('joint_t', [1., 3.])
def test_explicit_load_derivative_matches_centered_full_equations(cls, joint_t):
    net = network(cls, joint_t=joint_t)
    x, c, r, q = random_state_at_known_hinge_moment(net)
    saved = x.copy(); chart = c.get('angle_chart', 0.)
    _, data = net.residual(x, 0., detail=True)
    assert data['hinges'][0]['structural_moment'] == pytest.approx(2.5, abs=2e-14)
    actual = static.load_fraction_derivative(net, data)
    expected = np.zeros(net.size)
    start = 6*net.ne
    expected[start:start+3*net.nn] = (data['force']/net.F).ravel()
    start += 3*net.nn
    expected[start:start+3*net.nn] = (data['moment']/(net.F*net.L)).ravel()
    e, end = c['element'], int(c['end'])
    sign = -1 if end else 1
    axis0 = np.array([2., 1., 3.])/np.sqrt(14.)
    moment_rate = sign*data['element_moments'][e, end]@(q[c['a']]@axis0)
    # For the literal natural cubic [-5,-4; 0,1; 5,9], the middle second
    # derivative is .18, theta'(2.5)=131/80 deg/Nm, and theta(0)=1 degree.
    start = 6*(net.ne+net.nn)+c['sl'].start+3
    expected[start:start+3] = -axis0*np.deg2rad((131/80)*moment_rate+1.)
    np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=3e-15)
    np.testing.assert_array_equal(actual[:6*net.ne], 0.)
    np.testing.assert_array_equal(actual[net.gamma_start:], 0.)
    for h in (2e-4, 5e-5):
        stencil = (net.residual(x, h)-net.residual(x, -h))/(2*h)
        np.testing.assert_allclose(actual, stencil, rtol=2e-7, atol=2e-9)
    if cls in (SourceSectionNetwork, SourceCoupledNetwork):
        # Recover the source endpoint couple independently from the literal
        # dual CG arms, actual node rotations, and any saved aerodynamic strip.
        ds = np.linalg.norm(net.rj[net.b[e]]-net.rj[net.a[e]])
        couple = np.zeros(3)
        for weight, arm in [(1.2, [.04, 0., .02]), (.3, [.01, 0., -.015])]:
            couple += weight*ds/40*(np.cross(q[net.a[e]]@arm, net.gravity)
                                      +np.cross(q[net.b[e]]@arm, net.gravity))
        if cls is SourceCoupledNetwork:
            strip = data['aero']['strips'][e]
            couple += (np.asarray(strip['moment'])+np.cross(
                np.asarray(strip['position'])-(r[net.a[e]]+r[net.b[e]])/2,
                strip['force']))/2
        np.testing.assert_allclose(data['element_moments'][e, end], couple,
                                   rtol=3e-13, atol=3e-14)
        assert abs(moment_rate) > 1e-6
    np.testing.assert_array_equal(x, saved)
    assert c.get('angle_chart', 0.) == chart
    assert net.iteration_fields is None and net.tangent_influences is None


@pytest.mark.parametrize('moment', [0., -5e-9, 5e-9])
def test_doubled_moment_slope_break_keeps_existing_continuation(moment):
    net = network(curve='-5 -4\n0 1\n0 1\n5 9')
    x, _, _, _ = random_state_at_known_hinge_moment(net, moment)
    _, data = net.residual(x, 0., detail=True)
    with pytest.raises(static.StructuredTangentUnavailable, match='slope break'):
        static.load_fraction_derivative(net, data)


def test_rotation_rate_is_physical_and_includes_relative_hinge_travel():
    net = SimpleNamespace(nn=3, constraints=[dict(type=3, a=0, b=1)])
    rng = np.random.default_rng(1951)
    state = rng.normal(0., .7, 18)
    delta = rng.normal(0., .3, 18)
    w = state.reshape(3, 6)[:, 3:]; dw = delta.reshape(3, 6)[:, 3:]
    h = 2e-6
    plus = Rotation.from_rotvec(w+h*dw).as_matrix()
    minus = Rotation.from_rotvec(w-h*dw).as_matrix()
    physical = Rotation.from_matrix(plus@minus.transpose(0, 2, 1)).as_rotvec()/(2*h)
    expected = max(*np.linalg.norm(physical, axis=1), np.linalg.norm(physical[1]-physical[0]))
    assert static.rotation_increment(net, state, delta) == pytest.approx(expected, rel=3e-9, abs=2e-11)
    state[:] = 0.; delta[:] = 0.
    delta[3], delta[9] = 1., -1.
    assert static.rotation_increment(net, state, delta) == 2.


@pytest.mark.parametrize('cls',[SourceDiscreteNetwork, SourceMovingNetwork])
def test_retained_rank_matrix_proposes_analytic_rigid_hinge_step_without_solving(monkeypatch,cls):
    model = parse_asw(source(rigid=True, distant=False, axis='1 0 0',
        curve='-100 -100\n100 100'), beam_interpolation='drela-segspl-v1')
    net = cls(model, 4, None, [0., 0., 0.],
        [dict(beam=2, t=3., moment=[30., 0., 0.])])
    state = np.zeros(net.size)
    report, matrix = static.check_initial_rank(net, state, retain_matrix=True)
    assert isinstance(report, dict) and isinstance(matrix, static.StructuredMatrix)
    saved_matrix = matrix.toarray().copy()
    assert not np.any(matrix.force_circulation)
    before = net.nfev
    candidate, diagnostic = static.initial_load_step(net, state, matrix, .25, 1e-12, LIMIT)
    # The rigid second link rotates 30 degrees per unit load. 90% of the
    # unchanged five-degree limit therefore gives lambda=.15, below .25.
    assert candidate == pytest.approx(.15, abs=3e-9)
    assert diagnostic['rotation_rate_rad'] == pytest.approx(np.pi/6, abs=1e-8)
    assert diagnostic['applied'] and diagnostic['evaluations'] == net.nfev-before == 1
    assert diagnostic['zero_load_residual'] <= 1e-12
    assert candidate*diagnostic['rotation_rate_rad'] == pytest.approx(.9*LIMIT, abs=1e-15)
    np.testing.assert_array_equal(state, 0.)
    np.testing.assert_array_equal(matrix.toarray(), saved_matrix)
    assert net.aero_key is None and net.iteration_fields is None and net.tangent_influences is None
    # Optional retention must not alter the legacy dictionary return type.
    calls = []
    def retained(*args, **kwargs):
        calls.append(True)
        return matrix, {'evaluations': 0}
    monkeypatch.setattr(static, 'jacobian', retained)
    default = static.check_initial_rank(net, state)
    assert isinstance(default, dict) and default['method'] == report['method']
    assert len(calls) == 1


def control_fixture(monkeypatch):
    """Exact allowed class, with only the expensive physical query replaced."""
    net = StaticNetwork.__new__(StaticNetwork)
    net.nn, net.ne, net.size, net.gamma_start = 2, 1, 19, 18
    net.hinges = {1: object()}
    net.constraints = [dict(type=3, a=0, b=1, angle_chart=.37)]
    net.operating = SimpleNamespace(count=0)
    net.struts = []
    net.iteration_fields = net.tangent_influences = None
    net.aero_key = 'prior-query'; net.nfev = 0
    matrix = static.StructuredMatrix(eye(18, format='csc'), np.zeros((18, 1)),
                                     csc_matrix((1, 18)), np.eye(1))
    state = np.zeros(19)
    calls = []
    def residual(x, factor, detail=False):
        assert x is state and factor == 0. and detail is True
        calls.append(True); net.nfev += 1; net.aero_key = 'detailed-query'
        return np.zeros(net.size), {'sentinel': True}
    monkeypatch.setattr(net, 'residual', residual)
    def derivative(n, data):
        assert n is net and data == {'sentinel': True}
        return np.zeros(net.size)
    monkeypatch.setattr(static, 'load_fraction_derivative', derivative)
    return net, state, matrix, calls


@pytest.mark.parametrize('guard', ['subclass', 'no_hinges', 'operating', 'struts',
                                   'iteration_fields', 'tangent_influences', 'nonzero_B'])
def test_unsupported_prediction_does_not_enter_or_disturb_field_context(monkeypatch, guard):
    net, state, matrix, calls = control_fixture(monkeypatch)
    if guard == 'subclass':
        class UnknownNetwork(StaticNetwork):
            pass
        net.__class__ = UnknownNetwork
    elif guard == 'no_hinges': net.hinges = {}
    elif guard == 'operating': net.operating.count = 1
    elif guard == 'struts': net.struts = [object()]
    elif guard == 'nonzero_B': matrix.force_circulation[0, 0] = 1e-30
    else: setattr(net, guard, object())
    fields, pairs, key = net.iteration_fields, net.tangent_influences, net.aero_key
    candidate, report = static.initial_load_step(net, state, matrix, .25, 1e-12, LIMIT)
    assert candidate == .25 and not report['applied'] and calls == []
    assert net.iteration_fields is fields and net.tangent_influences is pairs and net.aero_key == key
    assert net.constraints[0]['angle_chart'] == .37


@pytest.mark.parametrize('value', [2e-12, np.nan, np.inf])
def test_predictor_checks_whole_fresh_zero_load_residual(monkeypatch, value):
    net, state, matrix, calls = control_fixture(monkeypatch)
    original = net.residual
    def residual(*args, **kwargs):
        result, data = original(*args, **kwargs)
        result[-1] = value  # A circulation row, beyond all mechanical rows.
        return result, data
    monkeypatch.setattr(net, 'residual', residual)
    def forbidden(*args, **kwargs):
        pytest.fail('An unconverged zero-load state must not reach the linear solve.')
    monkeypatch.setattr(static, 'block_solve', forbidden)
    candidate, report = static.initial_load_step(net, state, matrix, .25, 1e-12, LIMIT)
    assert candidate == .25 and not report['applied']
    assert report['reason'] == 'zero-load state is not converged'
    assert report['evaluations'] == len(calls) == 1 and net.aero_key is None


@pytest.mark.parametrize('failure', ['physical', 'derivative', 'singular', 'nonfinite_matrix',
                                    'nonfinite_direction', 'nonfinite_rate', 'resolution'])
def test_failed_prediction_returns_original_step_and_cleans_query_cache(monkeypatch, failure):
    net, state, matrix, calls = control_fixture(monkeypatch)
    if failure == 'physical':
        original = net.residual
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise AnalysisError('deliberate physical query failure')
        monkeypatch.setattr(net, 'residual', broken)
    elif failure == 'derivative':
        def broken(*args, **kwargs):
            raise static.StructuredTangentUnavailable('deliberate slope break')
        monkeypatch.setattr(static, 'load_fraction_derivative', broken)
    elif failure == 'singular': matrix.mechanical = csc_matrix((18, 18))
    elif failure == 'nonfinite_matrix': matrix.circulation[0, 0] = np.nan
    elif failure == 'nonfinite_direction':
        def broken(*args, **kwargs):
            direction = np.zeros(net.size); direction[0] = np.nan
            return direction
        monkeypatch.setattr(static, 'block_solve', broken)
    elif failure == 'nonfinite_rate':
        monkeypatch.setattr(static, 'rotation_increment', lambda *args: np.inf)
    elif failure == 'resolution':
        monkeypatch.setattr(static, 'rotation_increment', lambda *args: 1e20)
    saved = state.copy(); charts = deepcopy(net.constraints)
    candidate, report = static.initial_load_step(net, state, matrix, .25, 1e-12, LIMIT)
    assert candidate == report['proposed_increment'] == .25 and not report['applied']
    assert report['reason'] != 'original target retained'
    assert report['evaluations'] == len(calls) == 1
    assert net.aero_key is None and net.iteration_fields is None and net.tangent_influences is None
    assert net.constraints == charts
    np.testing.assert_array_equal(state, saved)


@pytest.mark.parametrize('rate', [0., .01, 1.])
def test_candidate_never_enlarges_original_increment(monkeypatch, rate):
    net, state, matrix, calls = control_fixture(monkeypatch)
    monkeypatch.setattr(static, 'rotation_increment', lambda *args: rate)
    candidate, report = static.initial_load_step(net, state, matrix, .25, 1e-12, LIMIT)
    expected = min(.25, .9*LIMIT/rate) if rate else .25
    assert candidate == expected and report['proposed_increment'] == expected
    assert report['applied'] is bool(expected < .25)
    assert report['evaluations'] == len(calls) == 1
    assert net.aero_key is None
