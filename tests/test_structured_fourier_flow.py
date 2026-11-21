"""Local strip differentiation preserves the complete Fourier Newton matrix."""
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.operating import free_flight_constraints
from openswing.source_airflow import SourceAirflowNetwork
from openswing.structured_static import jacobian
from test_source_coupled import model, condition, trial


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('factor', [0., .6])
@pytest.mark.parametrize('direct_mechanics', [False, True])
def test_local_fourier_columns_equal_individual_physical_stencils(frozen, factor, direct_mechanics):
    net = SourceAirflowNetwork(model(), 8,
        condition(circulation_modes={1: 3}, freeze_influences=frozen),
        [1., -2., -10.], (), operating_constraints=free_flight_constraints(), steady_trim=True)
    x = trial(net)
    # Nonzero elastic deformation, six frame accelerations and strong
    # circulation exercise the local kinematics and nonlinear stall leakage.
    x[net.gamma_start:net.operating_start] *= 5
    x[net.operating_start:] = np.linspace(-.003, .004, net.operating.count)
    before = net.residual(x, factor).copy()
    actual, counts = jacobian(net, x, factor, direct_mechanics=direct_mechanics)
    expected, control = jacobian(net, x, factor, grouped=False, direct_mechanics=direct_mechanics)
    np.testing.assert_array_equal(actual.toarray()[:net.operating_start],
                                  expected.toarray()[:net.operating_start])
    # The established frame-load grouping differences nodal wrenches before
    # summing; the ungrouped reference differences their global sum. Retain
    # the existing test_structured_initial_frames roundoff gate for these rows.
    np.testing.assert_allclose(actual.toarray()[net.operating_start:],
                               expected.toarray()[net.operating_start:], atol=2e-8, rtol=1e-9)
    assert counts['local_flow_before_projection'] and not control['local_flow_before_projection']
    assert counts['groups'] < control['groups']/2
    assert counts['evaluations'] < control['evaluations']/2
    assert net.iteration_fields is None and net.tangent_influences is None
    np.testing.assert_array_equal(net.residual(x, factor), before)


@pytest.mark.parametrize('example', ['dae', 'wing-body', 'powered'])
def test_mixed_beams_preserve_global_projection_and_other_rows(example):
    m = parse_asw(Path(f'examples/{example}.asw').read_text())
    beam = next(b.index for b in m.beams if b.lifting)
    net = StaticNetwork(m, 4, FlightCondition(mach=.2, beta=2,
        rates=[.01, -.02, .03], circulation_modes={beam: 3},
        ground_effect=1, position_earth=[0, 0, 30],
        powers={1: 50.} if example == 'powered' else {}), None, [])
    rng = np.random.default_rng(112211)
    x = rng.normal(0., .0001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    before = net.residual(x, .6).copy()
    actual, counts = jacobian(net, x, .6, direct_circulation=False, direct_mechanics=False)
    expected, control = jacobian(net, x, .6, grouped=False, direct_circulation=False, direct_mechanics=False)
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())
    assert counts['groups'] < control['groups']
    np.testing.assert_array_equal(net.residual(x, .6), before)


def test_pointwise_then_fourier_networks_keep_separate_patterns():
    for modes in (0, 3):
        net = SourceAirflowNetwork(model(), 6, condition(circulation_modes={1: modes}),
                                  [0., 0., -10.], (), steady_trim=True)
        x = trial(net)
        first, record = jacobian(net, x, .4)
        expected, _ = jacobian(net, x, .4, grouped=False)
        repeated, _ = jacobian(net, x, .4)
        np.testing.assert_array_equal(first.toarray(), expected.toarray())
        np.testing.assert_array_equal(repeated.toarray(), first.toarray())
        assert record['local_flow_before_projection'] == bool(modes)
