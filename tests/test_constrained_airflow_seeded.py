"""Full-system parity for acceleration/net-load constrained warm correction."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from openswing.equilibrium_state import restore
from openswing.operating import OperatingConstraint, free_flight_constraints
from openswing.source_airflow import SourceAirflowNetwork, solve_source_airflow_steady
import openswing.seeded_corrector as seeded
from test_source_coupled import model, condition


def setup(frozen, mass, axes):
    m = model(mass=mass)
    c = condition(freeze_influences=frozen, rates=[.1, -.05, .07],
                  acceleration=[.3, -.2, .1], angular_acceleration=[.4, -.1, .2])
    gravity = [1., -2., -10.]
    prescribed = solve_source_airflow_steady(m, c, 4, gravity=gravity, tolerance=1e-10)
    constraints = (free_flight_constraints() if axes == 'all' else
                   [OperatingConstraint('angular_acceleration.x', 'moment.x')])
    # Independently computed loads give a well-conditioned initial branch.
    # Targets are physical loads, not values fitted to an archived comparison.
    for row in constraints:
        quantity, axis = row.quantity.split('.')
        row.target = prescribed['applied_' + quantity]['xyz'.index(axis)]
    first = solve_source_airflow_steady(m, c, 4, gravity=gravity,
                operating_constraints=constraints, tolerance=1e-10)
    targets = [replace(row, target=row.target + .003 * (i + 1))
               for i, row in enumerate(constraints)]
    return m, c, gravity, first['equilibrium_state'], targets


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('mass,axes', [(False, 'roll'), (True, 'roll'), (True, 'all')])
def test_constrained_sparse_warm_matches_dense_cold_and_full_equations(frozen, mass, axes, monkeypatch):
    m, c, gravity, seed, targets = setup(frozen, mass, axes)
    original = deepcopy(seed)
    target = replace(c, beta=c.beta + .02, controls={1: .16})
    options = dict(gravity=gravity, operating_constraints=targets, tolerance=1e-10)
    warm = solve_source_airflow_steady(m, target, 4, initial_state=seed, **options)
    diagnostics = warm['equilibrium_initialization']
    report = diagnostics['seeded_corrector']
    assert report['enabled'] and report['builder_detached']
    assert report['builds'] and all(row['status'] == 'BUILT' for row in report['builds'])
    assert report['dense_tangent_builds'] == 0
    assert report['factor_wrappers_alive_before_final_tangent'] == 0
    assert report['complete_residual_acceptance_unchanged'] and report['rank_acceptance_threshold_unchanged']
    cold = solve_source_airflow_steady(m, target, 4, **options)

    @contextmanager
    def original_dense(*args, **kwargs):
        yield None

    monkeypatch.setattr(seeded, 'attach', original_dense)
    dense = solve_source_airflow_steady(m, target, 4, initial_state=seed, **options)
    assert seed == original
    for reference in (cold, dense):
        for key in ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions', 'circulation'):
            np.testing.assert_allclose(warm['equilibrium_state'][key], reference['equilibrium_state'][key],
                                       rtol=2e-7, atol=2e-9)
        for key, value in warm['equilibrium_state']['operating_values'].items():
            np.testing.assert_allclose(value, reference['equilibrium_state']['operating_values'][key],
                                       rtol=2e-7, atol=2e-9)
        for key in ('distributed_aero_force', 'distributed_aero_moment', 'applied_force', 'applied_moment'):
            np.testing.assert_allclose(warm[key], reference[key], rtol=2e-7, atol=2e-9)

    net = SourceAirflowNetwork(m, 4, target, gravity, (), operating_constraints=targets, steady_trim=True)
    x = restore(net, warm['equilibrium_state'])
    assert np.max(abs(net.residual(x))) < 1e-10
    for row in targets:
        quantity, axis = row.quantity.split('.')
        assert abs(warm['applied_' + quantity]['xyz'.index(axis)] - row.target) < 1e-8
    sparse = net.jacobian(x, 1., _sparse=True, _direct_geometry=False)
    dense = net.jacobian(x, 1., _direct_geometry=False)
    np.testing.assert_allclose(sparse.toarray(), dense, rtol=2e-10, atol=2e-10)
    # Include every structural, circulation and acceleration unknown. Check
    # the full physical residual action independently of either matrix form.
    direction = np.random.default_rng(1729).normal(size=net.size)
    direction /= np.linalg.norm(direction)
    estimates = [(net.residual(x+h*direction)-net.residual(x-h*direction))/(2*h)
                 for h in (1e-5, 5e-6)]
    np.testing.assert_allclose(estimates[0], estimates[1], rtol=2e-5, atol=2e-7)
    np.testing.assert_allclose(sparse @ direction, estimates[1], rtol=2e-5, atol=2e-7)
    assert net.iteration_fields is None and net.tangent_influences is None and net._tangent_loads is None


@pytest.mark.parametrize('kind', ['wrong_pair', 'control', 'time_row', 'count', 'custom', 'minimum'])
def test_noncanonical_constraints_still_decline_without_numerical_work(kind):
    from openswing.operating import TimeHistoryConstraint
    net = SourceAirflowNetwork(model(), 4, condition(), [0., 0., 0.], (), steady_trim=True,
                              operating_constraints=[OperatingConstraint('angular_acceleration.x', 'moment.x')])
    if kind == 'wrong_pair': net.operating.constraints[0].quantity = 'moment.y'
    if kind == 'control': net.operating.constraints[0].variable = 'control.1'
    if kind == 'time_row': net.operating.constraints[0] = TimeHistoryConstraint('angular_acceleration.x', 'moment.x')
    if kind == 'count': net.operating.count += 1
    if kind == 'custom': net.operating.custom = {'target': object()}
    if kind == 'minimum': net.operating.minimum_indices = [0]
    function = lambda x: x
    before = net.nfev
    report = {}
    with seeded.attach(net, function, {}, {}, final_tangent=None, report=report) as builder:
        assert builder is None and not report['enabled'] and report['decline_reasons']
    assert net.nfev == before and not hasattr(function, 'factorization_builder')


def test_constrained_factor_failure_recovers_with_complete_dense_equations(monkeypatch):
    m, c, gravity, seed, targets = setup(True, True, 'all')
    def unavailable(*args, **kwargs):
        raise RuntimeError('Injected sparse factor failure')
    monkeypatch.setattr(seeded, 'NewtonBeamFactor', unavailable)
    options = dict(gravity=gravity, operating_constraints=targets, tolerance=1e-10)
    recovered = solve_source_airflow_steady(m, c, 4, initial_state=seed, **options)
    report = recovered['equilibrium_initialization']['seeded_corrector']
    assert report['enabled'] and report['builds'][0]['status'] == 'BUILD_EXCEPTION'
    assert report['dense_tangent_builds'] >= 1
    net = SourceAirflowNetwork(m, 4, c, gravity, (), operating_constraints=targets, steady_trim=True)
    x = restore(net, recovered['equilibrium_state'])
    assert np.max(abs(net.residual(x))) < 1e-10
    assert net.iteration_fields is None and net.tangent_influences is None and net._tangent_loads is None
