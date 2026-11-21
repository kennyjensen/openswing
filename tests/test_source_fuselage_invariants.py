"""Noncommuting Euler histories and independent rigid-body rank checks."""
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.aero import AnalysisError
from openswing.source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_quiescent import SourceQuiescentNetwork
from openswing.source_time import SourceTimeChart
from test_source_fuselage import BODY_SOURCE, PANELS, model, product
from test_source_rigid_tree_rank import certificate, oracle_matrix, finite_difference_matrix, assert_well_resolved


@pytest.mark.parametrize('order', [1, 2])
def test_body_multiaxis_unequal_step_bdf_matches_rotation_product(order):
    jig = np.array([product(q, np.zeros(3))[0] for q in [[.1, .2, -1.5], [-.2, .1, -1.3]]])
    chart = SourceTimeChart(SimpleNamespace(nn=2, a=np.array([0]), b=np.array([1]),
        R0a=jig[:1], R0b=jig[1:], source_fuselage=np.array([True])))
    q0 = np.array([[.2, -.3, -1.4], [-.3, .2, -1.6]])
    q1 = np.array([[.4, -.5, .8], [-.2, .7, -.5]])
    q2 = np.array([[.3, -.2, .4], [.1, .3, -.2]]) if order == 2 else np.zeros((2, 3))
    samples = []
    times = [0., .12, .31]
    for t in times:
        values = [product(q, dq) for q, dq in zip(q0+t*q1+t*t*q2, q1+2*t*q2)]
        state = SimpleNamespace(Q=np.array([v[0] for v in values])@jig.transpose(0, 2, 1),
            w=np.array([v[1] for v in values]), orientation=np.eye(3), Omega=np.zeros(3))
        chart.bind(state, samples[-1] if samples else None)
        samples.append(state)
    h, hp = times[2]-times[1], times[1]-times[0]
    coefficients = [1/h, -1/h, 0.] if order == 1 else [
        (2*h+hp)/(h*(h+hp)), -(h+hp)/(h*hp), h/(hp*(h+hp))]
    local, frame = chart.rates(samples[2], samples[1], samples[0] if order == 2 else None, coefficients)
    np.testing.assert_allclose(local, 0., atol=8e-15)
    np.testing.assert_allclose(frame, 0., atol=8e-15)


@pytest.mark.parametrize('cls', [SourceDiscreteNetwork, SourceSectionNetwork, SourceCoupledNetwork])
def test_axial_body_rank_certificate_agrees_with_independent_balance_operator(cls):
    rigid = model(BODY_SOURCE.replace('200 0 0 0 0 0', '0 0 0 0 0 0'))
    net = cls(rigid, PANELS, None, [0, 0, 0], [])
    # The proof intentionally requires exact orthonormality. Trigonometric
    # jig construction has a tiny off-diagonal residue and uses the ordinary
    # numerical rank fallback. Exercise the algebraic proof on its exact
    # signed-permutation frame without widening the production proof scope.
    original = certificate(net)
    assert not original['certified'] and 'exact orthonormal' in original['reason']
    frame = np.array([[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]])
    np.testing.assert_allclose(net.R0a, np.broadcast_to(frame, net.R0a.shape), atol=1e-15)
    net.R0a[:] = frame
    net.R0b[:] = frame
    report = certificate(net)
    assert report['certified'] and report['source_scope']['source_chart_smooth']
    expected = oracle_matrix(net)
    assert_well_resolved(expected)
    np.testing.assert_allclose(finite_difference_matrix(net), expected, rtol=3e-8, atol=3e-9)


def test_still_air_body_has_no_axial_added_mass():
    net=SourceQuiescentNetwork(model(), PANELS, None, [0, 0, 0], [], quiescent_density=1.2)
    matrix=np.array(net.rigid_acceleration_report()['matrix'])
    np.testing.assert_allclose(matrix[:,0],0.,atol=2e-15)
    assert matrix[1,1]>0 and matrix[2,2]>0
