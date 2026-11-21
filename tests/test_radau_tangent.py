"""Scoped Radau dispatch and independent nonlinear stage derivative controls."""
from types import SimpleNamespace
import numpy as np
from openswing.nonlinear_initial import InitialSystem
from openswing.radau_tangent import stage_jacobian, supported_rate_columns
from openswing.radau_time import INVERSE, collocate
from openswing import time_integration


class _Subclass(InitialSystem):
    pass


def _scope_chart(kind):
    # Minimal exact-type metadata tests dispatch, not excluded-path dynamics.
    cls = _Subclass if kind == 'subclass' else InitialSystem
    chart = cls.__new__(cls)
    chart.dynamic_indices = np.array([0])
    chart.system = SimpleNamespace(
        feedback=object() if kind == 'controller' else None,
        position_lift=object() if kind == 'position_history' else None,
        network=SimpleNamespace(operating=SimpleNamespace(
            count=1 if kind == 'operating' else 0, custom=kind == 'custom')))
    return chart


def test_radau_stage_tangent_scope_preserves_full_difference_fallback(monkeypatch):
    original_newton = time_integration.newton
    dispatch = []

    def newton(function, *args, **kwargs):
        dispatch.append(hasattr(function, 'factorization_builder'))
        return original_newton(function, *args, **kwargs)

    monkeypatch.setattr(time_integration, 'newton', newton)
    endpoints = []
    for kind in ('ordinary', 'controller', 'operating', 'custom', 'position_history', 'subclass'):
        columns = supported_rate_columns(_scope_chart(kind))
        result = collocate(lambda y, d, t: d+y, np.array([1.]), np.array([-1.]),
                           0., .01, 1e-10, stage_rate_columns=columns)
        assert dispatch[-1] == (kind == 'ordinary')
        assert (columns is not None) == (kind == 'ordinary')
        endpoints.append(float(result[0][0]))
    assert max(endpoints)-min(endpoints) < 1e-14


def test_radau_nonlinear_time_dependent_stage_blocks_match_analytic_derivative():
    initial = np.array([.2, -.3])
    flat = np.array([.1, .2, .15, -.1, -.2, .4])
    times = np.array([.03, .08, .1])
    step = .1

    def residual(y, d, t):
        return np.array([y[0]**2+(2+t+y[1])*d[0], 3*y[1]+(1+2*t)*d[1]])

    matrix, _ = stage_jacobian(residual, initial, flat, times, step, INVERSE, np.arange(2))
    exact = np.empty((6, 6))
    states = initial+flat.reshape(3, 2)
    rates = INVERSE@flat.reshape(3, 2)/step
    for i, (y, d, t) in enumerate(zip(states, rates, times)):
        fy = np.array([[2*y[0], d[0]], [0., 3.]])
        fd = np.diag([2+t+y[1], 1+2*t])
        for j in range(3):
            exact[2*i:2*i+2, 2*j:2*j+2] = (INVERSE[i, j]/step)*fd+(fy if i == j else 0.)
    # The independently differentiated quadratic has a forward-difference
    # truncation defect near 1e-6; stages differ in state, rate and time.
    assert float(np.max(abs(matrix-exact))) < 2e-6


def test_radau_invalid_explicit_rate_columns_use_existing_newton_fallback():
    def ode(y, d, t):
        return d+y

    generic = collocate(ode, np.array([1.]), np.array([-1.]), 0., .05, 1e-10)
    fallback = collocate(ode, np.array([1.]), np.array([-1.]), 0., .05, 1e-10,
                         stage_rate_columns=np.array([3]))
    assert np.max(abs(generic[0]-fallback[0])) < 1e-13
