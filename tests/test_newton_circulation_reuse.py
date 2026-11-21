"""Share only the current Newton base fields; retain full physical accuracy."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from test_direct_circulation import model_for, state_for


CASES = [
    ('wing-body', {'ground_effect': 1}, .37, 'free', .3),
    ('stepped-wing-body', {'ground_effect': -1}, 1., 'fixed', .3),
    ('torsion-joint', {}, .6, 'fixed', .3),
    ('flexible', {'circulation_modes': {1: 3}}, .4, 'free', .3),
    ('rectangular', {}, 0., 'fixed', 1.2),
    ('jet-2', {'powers': {1: 50000.}}, .6, 'free', .3),
    ('dae', {}, .25, 'fixed', .08),
]


def fixture(example, extra, factor, frame, circulation):
    net = StaticNetwork(model_for(example), 4,
        FlightCondition(speed=30, alpha=7, beta=3, mach=.2,
            rates=[.03, -.04, .02], position_earth=[0, 0, 30], **extra), None, [],
        operating_constraints=time_load_constraints('prescribed' if frame == 'fixed' else frame))
    net._frequency_local_geometry = True
    return net, state_for(net, circulation)


@pytest.mark.parametrize('example,extra,factor,frame,circulation', CASES)
def test_shared_capture_replaces_probes_and_matches_complete_physical_columns(example, extra, factor, frame, circulation):
    net, x = fixture(example, extra, factor, frame, circulation)
    base = net.residual(x, factor).copy()
    start = net.nfev
    actual = net.jacobian(x, factor)
    calls = net.nfev-start
    assert net.circulation_derivative_diagnostics['method'] == 'direct fixed-geometry blocks'
    start = net.nfev
    previous = net.jacobian(x, factor, _direct_circulation=False)
    assert net.nfev-start-calls == net.ng
    keep = np.r_[np.arange(net.gamma_start), np.arange(net.operating_start, net.size)]
    np.testing.assert_array_equal(actual[:, keep], previous[:, keep])
    # Independent complete residual references at two widths: no captured or
    # lagged fields, including operating, hinge, engine and transferred loads.
    for step in [1e-5, 3e-6]:
        for j in range(net.gamma_start, net.operating_start):
            h = step*max(1., abs(x[j])); d = np.zeros(net.size); d[j] = h
            v = [net.residual(x+k*d, factor) for k in [1, -1, 2, -2]]
            expected = (8*(v[0]-v[1])-(v[2]-v[3]))/(12*h)
            error = np.max(abs(actual[:, j]-expected)/(1+abs(expected)))
            assert error < 2e-7, (example, step, j, error)
    np.testing.assert_array_equal(net.residual(x, factor), base)
    assert net.iteration_fields is None and net.tangent_influences is None


def test_changed_state_and_continuation_factor_get_fresh_capture():
    net, x = fixture(*CASES[0])
    a = net.jacobian(x, .2)
    y = x.copy(); y[:6*net.nn] *= 1.4; y[net.gamma_start:net.operating_start] *= 1.7
    b = net.jacobian(y, .8)
    fresh, _ = fixture(*CASES[0])
    # The existing forward-difference operating columns vary by ~7e-12
    # between warm and fresh owners, also in the unchanged baseline. Require
    # exact identity for all reused/structural columns; retain that separate
    # roundoff observation in the study instead of weakening a physical gate.
    np.testing.assert_array_equal(b[:, :net.operating_start],
        fresh.jacobian(y, .8)[:, :net.operating_start])
    np.testing.assert_array_equal(a, net.jacobian(x, .2))
    assert np.max(abs(a[:, net.gamma_start:net.operating_start]-b[:, net.gamma_start:net.operating_start])) > 1e-4


def test_unavailable_circulation_retains_original_columns_and_restores_context(monkeypatch):
    import openswing.circulation_tangent as module
    net, x = fixture(*CASES[0]); previous = net.jacobian(x, .37, _direct_circulation=False)
    def unavailable(*args, **kwargs):
        raise module.CirculationDerivativeUnavailable('deliberate circulation storage limit')
    monkeypatch.setattr(module, 'circulation_columns', unavailable)
    actual = net.jacobian(x, .37)
    np.testing.assert_array_equal(actual, previous)
    assert net.circulation_derivative_diagnostics == dict(method='forward differences', fallback='deliberate circulation storage limit')
    assert net.iteration_fields is None and net.tangent_influences is None


@pytest.mark.parametrize('case', ['geometry-fallback', 'residual-options', 'disabled-geometry'])
def test_ineligible_geometry_capture_keeps_original_complete_matrix(case, monkeypatch):
    import openswing.geometry_tangent as geometry
    import openswing.circulation_tangent as circulation
    net, x = fixture('rectangular', {}, .6, 'fixed', .3)
    def unavailable(*args, **kwargs):
        raise geometry.GeometryDerivativeUnavailable('deliberate unavailable geometry')
    if case == 'geometry-fallback':monkeypatch.setattr(geometry, 'geometry_columns', unavailable)
    if case == 'disabled-geometry':net._frequency_local_geometry = False
    options = dict(gravity_override=net.gravity) if case == 'residual-options' else {}
    previous = net.jacobian(x, .6, _direct_circulation=False, **options)
    def unexpected(*args, **kwargs):raise AssertionError('No eligible base capture')
    monkeypatch.setattr(circulation, 'circulation_columns', unexpected)
    np.testing.assert_array_equal(net.jacobian(x, .6, **options), previous)
    assert net.circulation_derivative_diagnostics['method'] == 'forward differences'
    assert net.iteration_fields is None and net.tangent_influences is None
