"""Source modal load columns against complete moving physical residuals."""
from dataclasses import replace
import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.inertia import Motion
from openswing.linear_dynamics import DynamicSystem, linearize
from openswing.mechanical_tangent import mechanical_columns, MechanicalDerivativeUnavailable
from openswing.source_airflow import SourceAirflowNetwork
from openswing.source_dynamics import SourceDynamicNetwork, SourceMovingNetwork
from openswing.source_quiescent import SourceQuiescentNetwork
from test_source_coupled import condition
from test_source_joints import source, trial
from test_source_fuselage import model as body_model
from test_source_dynamic_tangents import system as stationary_system


def fixture(kind, frame='fixed'):
    text = source(offsets=True, mass=True)
    text = text.replace('3 1.2 .04 .02 .3 .01 -.015\nEnd\n',
        '3 1.2 .04 .02 .3 .01 -.015\nt tdeps tdgam\n1 .03 .01\n3 .02 .04\nEnd\n')
    model = body_model() if kind == 'fuselage' else parse_asw(text, beam_interpolation='drela-segspl-v1')
    cls = dict(vacuum=SourceDynamicNetwork, moving=SourceMovingNetwork,
        still_air=SourceQuiescentNetwork, airflow=SourceAirflowNetwork,
        fuselage=SourceDynamicNetwork)[kind]
    options = dict(quiescent_density=1.2) if kind == 'still_air' else {}
    flow = None
    if kind == 'moving':
        options['motion'] = Motion(rates=[.02, -.01, .03], acceleration=[.1, .2, -.1])
    if kind == 'airflow':
        flow = replace(condition(), rates=[.02, -.01, .03], acceleration=[.1, .2, -.1])
    n = cls(model, 4, flow, [1., -2., -10.], [], **options)
    return DynamicSystem(n, trial(n), frame=frame)


@pytest.mark.parametrize('kind,frame', [('vacuum','fixed'), ('still_air','fixed'),
    ('moving','prescribed'), ('moving','free'), ('airflow','fixed'),
    ('airflow','free'), ('fuselage','fixed')])
def test_all_load_and_reaction_columns_match_two_full_dynamic_stencils(kind, frame):
    s = fixture(kind, frame); n = s.network
    z = np.zeros(s.size)
    zdot = np.random.default_rng(12).normal(0, 1e-4, s.size)
    before, state, options = s.residual(z, zdot, detail=True)
    _, data = n.residual(state.x, detail=True, **options)
    scales = np.r_[np.maximum(1., abs(s.base)), np.ones(s.size-n.size)]
    evaluations = n.nfev
    matrix, report = mechanical_columns(s, data, scales, 1e-5)
    assert n.nfev == evaluations
    assert report['method'].startswith('direct source endpoint-average')
    assert matrix.shape == (s.size, n.gamma_start-6*n.nn)
    for width in (1e-5, 3e-6):
        for k, column in enumerate(range(6*n.nn, n.gamma_start)):
            h = width*scales[column]; direction = z.copy(); direction[column] = h
            expected = (s.residual(direction, zdot)-s.residual(-direction, zdot))/(2*h)
            actual = matrix[:, k].toarray().ravel()
            assert np.max(abs(actual-expected)/(1+abs(expected))) < 2e-8
    np.testing.assert_array_equal(s.residual(z, zdot), before)
    assert n.analytic_mechanics is False


def test_unknown_rate_law_keeps_full_source_linearization():
    s = stationary_system(); n = s.network
    n.constitutive_motion = lambda strain, curvature, data, motion: (1.25*strain, curvature)
    h = 1e-5; z = np.zeros(s.size)
    expected = []
    for column in range(n.size):
        direction = z.copy(); direction[column] = h
        values = [s.residual(k*direction, z) for k in (1., -1., 2., -2.)]
        expected.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*h))
    actual = linearize(s, sparse=True, _stationary=True).toarray()
    np.testing.assert_allclose(actual, np.column_stack(expected), rtol=2e-10, atol=2e-10)
    assert s.state_derivative_diagnostics['mechanical_fallback'] == 'Unknown source rate-dependent constitutive law.'


def test_controller_keeps_complete_residual_derivatives():
    s = stationary_system(); s.feedback = object()
    with pytest.raises(MechanicalDerivativeUnavailable, match='Controller/custom'):
        mechanical_columns(s, {}, np.ones(s.size), 1e-5)
