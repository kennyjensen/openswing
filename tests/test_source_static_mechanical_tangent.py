"""Exact source load columns in steady assembly, with full-residual controls."""
import numpy as np
import pytest

from openswing.mechanical_tangent import MechanicalDerivativeUnavailable
from openswing.source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
from openswing.source_dynamics import SourceDynamicNetwork
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_airflow import SourceAirflowNetwork
from openswing.structured_static import jacobian
from test_source_joints import model, trial
from test_source_coupled import condition
from test_source_fuselage import model as body_model


def fixture(kind):
    cls = dict(zero=SourceDiscreteNetwork, section=SourceSectionNetwork,
        dynamic=SourceDynamicNetwork, coupled=SourceCoupledNetwork,
        airflow=SourceAirflowNetwork, fuselage=SourceSectionNetwork)[kind]
    source = body_model() if kind == 'fuselage' else model(offsets=kind != 'zero', mass=kind != 'zero')
    n = cls(source, 4, condition() if kind in ('coupled', 'airflow') else None, [1., -2., -10.], [])
    return n, trial(n)


@pytest.mark.parametrize('kind', ['zero', 'section', 'dynamic', 'coupled', 'airflow', 'fuselage'])
def test_source_steady_columns_match_full_residuals_and_reduce_evaluations(kind):
    n, x = fixture(kind)
    before = n.residual(x, .6).copy()
    actual, report = jacobian(n, x, .6, direct_circulation=False)
    original, old_report = jacobian(n, x, .6, direct_circulation=False, direct_mechanics=False)
    assert report['mechanical_derivative']['method'].startswith('direct source endpoint-average')
    assert report['mechanical_derivative_fallback'] is None
    assert report['evaluations'] < old_report['evaluations']-5
    a, b = actual.toarray(), original.toarray()
    assert np.max(abs(a-b)/(1+abs(b))) < 2e-6
    # Every internal load and reaction column, including the sprung joint,
    # is checked against the complete current physical residual.
    for column in range(6*n.nn, n.gamma_start):
        h = 3e-6*max(1., abs(x[column]))
        p, m = x.copy(), x.copy()
        p[column] += h
        m[column] -= h
        expected = (n.residual(p, .6)-n.residual(m, .6))/(2*h)
        assert np.max(abs(a[:, column]-expected)/(1+abs(expected))) < 2e-8
    np.testing.assert_array_equal(n.residual(x, .6), before)
    assert n.iteration_fields is None and n.tangent_influences is None
    assert n.analytic_mechanics is False


def test_source_unavailable_derivative_keeps_original_complete_matrix(monkeypatch):
    import openswing.mechanical_tangent as mechanical
    n, x = fixture('section')
    expected, _ = jacobian(n, x, 1., direct_mechanics=False)
    def unavailable(*args, **kwargs):
        raise MechanicalDerivativeUnavailable('deliberate unsupported source state')
    monkeypatch.setattr(mechanical, 'source_network_mechanical_columns', unavailable)
    actual, report = jacobian(n, x, 1.)
    assert report['mechanical_derivative_fallback'] == 'deliberate unsupported source state'
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())
    assert n.iteration_fields is None and n.tangent_influences is None


def test_unknown_source_constitutive_override_uses_full_residual_fallback():
    n, x = fixture('section')
    original = n.constitutive_response
    n.constitutive_response = lambda force, moment: original(force, moment)
    expected, _ = jacobian(n, x, 1., direct_mechanics=False)
    actual, report = jacobian(n, x, 1.)
    assert report['mechanical_derivative_fallback'] == 'Unknown source constitutive load law.'
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())
    assert n.iteration_fields is None and n.tangent_influences is None
