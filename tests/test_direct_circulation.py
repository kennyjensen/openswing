"""Complete direct circulation blocks versus the full physical residual."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.structured_static import jacobian, linearization


def model_for(name):
    example = 'wing-body' if name == 'stepped-wing-body' else 'powered' if name.startswith('jet-') else 'articulated' if name == 'torsion-joint' else name
    source = Path(f'examples/{example}.asw').read_text()
    if name == 'stepped-wing-body':
        start = source.index('t x y z radius'); end = source.index('t EIcc', start)
        source = source[:start]+'t x y z\n-2 -2 0 -.2\n2 2 0 -.2\nt radius\n-2 0\n-1 0\n-1 .2\n1 .2\n1 0\n2 0\n'+source[end:]
    if name == 'torsion-joint':
        source = source.replace('1 .25 .008', '1 .4 .008').replace('1 1 0 0\n-8000', '1 .2 1 .1\n-8000').replace('2 1 0 0\n-8000', '2 .2 1 .1\n-8000')
    model = parse_asw(source)
    if name.startswith('jet-'):
        typ = int(name[-1])
        for i, row in enumerate(model.records['engine']):
            row[1] = typ; row[4:7] = [-1.5, (-1)**i*.25, -.2]
            row[7:10] = [-1., .07, .12]; row[10:13] = [.01, -.0001, 2.]
            row[15:25] = [.6, 5.8, .45, .13, .2, .07, .08, .04, .04, .02]
    return model


def state_for(net, circulation=.08):
    x = np.random.default_rng(729).normal(0., .002, net.size)
    x[net.gamma_start:] += circulation
    return x


def centered_columns(net, x, factor, step):
    columns = []
    for j in range(net.gamma_start, net.size):
        h = step*max(1., abs(x[j])); plus = x.copy(); minus = x.copy()
        plus[j] += h; minus[j] -= h
        columns.append((net.residual(plus, factor)-net.residual(minus, factor))/(2*h))
    return np.array(columns).T if columns else np.empty((net.size, 0))


@pytest.mark.parametrize('example,extra,circulation', [
    ('rectangular', {}, .08), ('flexible', {}, .08), ('wing-body', {}, .08),
    ('stepped-wing-body', {}, .08), ('torsion-joint', {}, .3), ('dae', {}, .08),
    ('flexible', {'circulation_modes': {1: 3}}, .3),
    ('wing-body', {'freeze_influences': True}, .3),
    ('rectangular', {}, 1.2), ('rectangular', {'stall': False}, 1.2),
    ('jet-0', {'powers': {1: 50000.}}, .3),
    ('jet-1', {'powers': {1: 50000.}}, .3),
    ('jet-2', {'powers': {1: 50000.}}, .3),
])
def test_complete_circulation_columns_match_refined_physical_differences(example, extra, circulation):
    net = StaticNetwork(model_for(example), 4,
        FlightCondition(mach=.2, alpha=7, beta=3, rates=[.03, -.04, .02],
                        ground_effect=1, position_earth=[0, 0, 30], **extra), None, [])
    x = state_for(net, circulation); base = net.residual(x, .6).copy()
    direct, counts = jacobian(net, x, .6, direct_circulation=True)
    assert counts['circulation_derivative'] == 'direct fixed-geometry blocks', counts
    assert counts['evaluations'] == counts['groups']+1
    columns = np.r_[direct.force_circulation, direct.circulation]
    for step in [1e-5, 3e-6]:
        expected = centered_columns(net, x, .6, step)
        # Entrywise bounds also cover small moment, joint and point-load rows.
        error = np.max(abs(columns-expected)/(1+abs(expected)), initial=0.)
        assert error < 2e-7, (example, step, error)
    np.testing.assert_array_equal(net.residual(x, .6), base)
    assert net.iteration_fields is None and net.tangent_influences is None
    old, _ = jacobian(net, x, .6, direct_circulation=False)
    np.testing.assert_array_equal(direct.mechanical.toarray(), old.mechanical.toarray())
    np.testing.assert_array_equal(direct.flow_geometry.toarray(), old.flow_geometry.toarray())
    if example == 'torsion-joint':
        start = 6*(net.ne+net.nn)
        assert np.max(abs(columns[start:net.gamma_start])) > 1e-6


@pytest.mark.parametrize('factor', [0., .4])
def test_zero_load_and_no_circulation_retain_their_exact_zero_blocks(factor):
    for example in ['stepped-body', 'wing-body']:
        net = StaticNetwork(model_for(example), 4, FlightCondition(mach=.1), None, [])
        x = state_for(net); direct, _ = jacobian(net, x, factor, direct_circulation=True)
        if factor == 0 or not net.ng: assert not np.any(direct.force_circulation)
        expected = centered_columns(net, x, factor, 3e-6)
        np.testing.assert_allclose(np.r_[direct.force_circulation, direct.circulation], expected, rtol=2e-7, atol=2e-7)


def test_frozen_circulation_columns_keep_direct_derivative_under_storage_limit(monkeypatch):
    from openswing import circulation_tangent
    net = StaticNetwork(model_for('stepped-wing-body'), 8,
                        FlightCondition(alpha=5, freeze_influences=True), None, [])
    x = state_for(net)
    with linearization(net, x, .6, capture_circulation=True) as (fields, _):
        expected = circulation_tangent.circulation_columns(net, fields, .6)
        bytes_per_column = 8*(net.size + 18*fields.vortex_receiver_count())
        budget = expected.nbytes + 2*bytes_per_column
        assert budget < net.ng*bytes_per_column
        monkeypatch.setattr(circulation_tangent, '_COLUMN_BUDGET', budget)
        actual = circulation_tangent.circulation_columns(net, fields, .6)
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-14)


def test_engine_jet_feedback_is_observable_and_not_frozen(monkeypatch):
    from openswing.circulation_tangent import EngineDerivative
    net = StaticNetwork(model_for('jet-2'), 8, FlightCondition(mach=.1, alpha=7, beta=3, powers={1:50000.}), None, [])
    x = state_for(net, .3)
    actual, counts = jacobian(net, x, .7, direct_circulation=True)
    assert counts['circulation_derivative'] == 'direct fixed-geometry blocks'
    monkeypatch.setattr(EngineDerivative, 'jet', lambda self, points: np.zeros(points.shape+(net.ng,)))
    missing, _ = jacobian(net, x, .7, direct_circulation=True)
    a, b = np.r_[actual.force_circulation, actual.circulation], np.r_[missing.force_circulation, missing.circulation]
    assert np.max(abs(a-b)/(1+abs(a))) > 1e-5


def test_hinge_slope_break_keeps_the_original_circulation_columns():
    source = Path('examples/articulated.asw').read_text().replace('1 .25 .008', '1 .4 .008')
    source = source.replace('1 1 0 0\n-8000', '1 0 1 0\n-8000').replace('2 1 0 0\n-8000', '2 0 1 0\n-8000')
    source = source.replace('0 0\n4000', '0 0\n0 0\n4000')
    net = StaticNetwork(parse_asw(source), 4, FlightCondition(alpha=0, beta=0, mach=0), None, [])
    x = np.zeros(net.size)
    actual, counts = jacobian(net, x, .6, direct_circulation=True)
    assert counts['circulation_derivative'] == 'forward differences'
    assert 'slope break' in counts['circulation_derivative_fallback']
    expected, _ = jacobian(net, x, .6, direct_circulation=False)
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())


def test_unresolved_engine_branch_keeps_the_original_circulation_columns():
    from openswing.propulsion import actuator_disk
    model = model_for('jet-1')
    model.records['engine'] = model.records['engine'][:1]
    model.records['engine'][0][12] *= -1  # No jet; isolate the clipped disk branch.
    condition = FlightCondition(mach=0, alpha=7, beta=3, powers={1:0.})
    net = StaticNetwork(model, 4, condition, None, []); x = state_for(net)
    with linearization(net, x, .6, capture_circulation=True) as (fields, _):
        engine = fields.circulation_aero['engines'][0]
        row = model.records['engine'][0]
        state = actuator_disk(0., fields.circulation_aero['rho'], engine['axial_velocity'], row[12], row[13], row[14])
    condition.powers[1] = state['minimum_power']+state['viscous_power']
    net = StaticNetwork(model, 4, condition, None, [])
    actual, counts = jacobian(net, x, .6, direct_circulation=True)
    assert counts['circulation_derivative'] == 'forward differences'
    assert 'clipping' in counts['circulation_derivative_fallback']
    expected, _ = jacobian(net, x, .6, direct_circulation=False)
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())


def test_unavailable_direct_derivative_restores_numerical_columns(monkeypatch):
    import openswing.circulation_tangent as module
    net = StaticNetwork(model_for('wing-body'), 4, FlightCondition(), None, []); x = state_for(net)
    expected, _ = jacobian(net, x, .6, direct_circulation=False)
    def unavailable(*args):raise module.CirculationDerivativeUnavailable('deliberate storage limit')
    monkeypatch.setattr(module, 'circulation_columns', unavailable)
    actual, counts = jacobian(net, x, .6, direct_circulation=True)
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())
    assert counts['circulation_derivative_fallback'] == 'deliberate storage limit'
    assert net.iteration_fields is None and net.tangent_influences is None
