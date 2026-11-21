"""Source mechanical columns against complete residuals, not midpoint targets."""
from copy import deepcopy

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.ground import body_to_earth
from openswing.hinge_history import at_network
from openswing.mechanical_tangent import source_network_mechanical_columns, MechanicalDerivativeUnavailable
from openswing.source_airflow import SourceAirflowNetwork
from openswing.source_coupled import SourceCoupledNetwork
from openswing.structured_time import jacobian
from openswing.time_integration import TimeState, TimeSystem, bdf_coefficients
from test_source_coupled import source, condition, trial
from test_source_joints import model as joint_model, trial as joint_trial


@pytest.mark.parametrize('joint', [False, True])
def test_source_load_columns_match_two_full_residual_stencils(joint):
    model = joint_model(offsets=True, mass=True) if joint else parse_asw(source(), beam_interpolation='drela-segspl-v1')
    n = SourceCoupledNetwork(model, 4, condition(), [1., -2., -10.], [])
    x = joint_trial(n) if joint else trial(n)
    data = {}
    before = n.residual(x, _mechanical_data=data)
    direct, report = source_network_mechanical_columns(n, data, np.maximum(1.,abs(x)), 1e-6)
    assert report['method'].startswith('direct source endpoint-average')
    for step in (1e-5, 3e-6):
        for j, column in enumerate(range(6*n.nn, n.gamma_start)):
            h = step*max(1.,abs(x[column])); plus=x.copy(); minus=x.copy()
            plus[column]+=h; minus[column]-=h
            expected=(n.residual(plus)-n.residual(minus))/(2*h)
            observed=direct[:,j].toarray().ravel()
            assert np.max(abs(observed-expected)/(1+abs(expected))) < 2e-8
    np.testing.assert_array_equal(n.residual(x), before)


def setup(previous_step=.013):
    text = source().rsplit('End\n',1)[0]+'t tdeps tdgam\n1 .02 .03\n3 .04 .01\nEnd\n'
    model = parse_asw(text, beam_interpolation='drela-segspl-v1')
    c = condition()
    n = SourceAirflowNetwork(model, 4, c, [0.,0.,0.], [])
    system = TimeSystem(n)
    x = trial(n)
    r, q, *_, gamma = n.unpack(x)
    rng = np.random.default_rng(501)
    previous = TimeState(0., x, r, q, rng.normal(0,.02,r.shape), rng.normal(0,.01,r.shape),
        -c.speed*c.vectors()[0], np.array([.02,-.03,.01]), np.zeros(3), body_to_earth(c.attitude), gamma,
        hinge_charts=at_network(n,q))
    system.source_time.bind(previous)
    older = None if previous_step is None else deepcopy(previous)
    if older is not None:
        older.time=-previous_step
    values = system.guess(previous,.017)+rng.normal(0,1e-5,system.size)
    coefficients = bdf_coefficients(.017,previous_step)
    function = lambda v:system.residual(v,previous,older,.017,coefficients)
    return system, function, values, coefficients[0]


@pytest.mark.parametrize('previous_step', [None, .013])
def test_bdf_assembly_preserves_full_columns_and_reduces_residual_evaluations(previous_step):
    system, function, x, rate = setup(previous_step)
    before = function(x).copy()
    direct, permutation, report = jacobian(system,function,x,circulation_rate_factor=rate)
    old, old_p, old_report = jacobian(system,function,x,circulation_rate_factor=rate,direct_mechanics=False)
    assert report['mechanical_derivative'] is not None and report['mechanical_derivative_fallback'] is None
    assert report['evaluations'] < old_report['evaluations']-5
    np.testing.assert_array_equal(permutation,old_p)
    a,b=direct.toarray(),old.toarray()
    assert np.max(abs(a-b)/(1+abs(b))) < 2e-6
    inverse=np.argsort(permutation)
    n=system.network
    for column in range(6*n.nn,n.gamma_start):
        h=3e-6*max(1.,abs(x[column]));plus=x.copy();minus=x.copy()
        plus[column]+=h;minus[column]-=h
        expected=(function(plus)-function(minus))[permutation]/(2*h)
        assert np.max(abs(a[:,inverse[column]]-expected)/(1+abs(expected))) < 2e-8
    np.testing.assert_array_equal(function(x),before)
    assert n.iteration_fields is None and n.tangent_influences is None


def test_unavailable_source_derivative_keeps_original_matrix(monkeypatch):
    import openswing.mechanical_tangent as module
    system,function,x,rate=setup()
    expected,p,_=jacobian(system,function,x,circulation_rate_factor=rate,direct_mechanics=False)
    def unavailable(*args,**kwargs):
        raise MechanicalDerivativeUnavailable('deliberate source branch')
    monkeypatch.setattr(module,'source_network_mechanical_columns',unavailable)
    actual,ap,report=jacobian(system,function,x,circulation_rate_factor=rate)
    assert report['mechanical_derivative_fallback']=='deliberate source branch'
    np.testing.assert_array_equal(ap,p)
    np.testing.assert_array_equal(actual.toarray(),expected.toarray())
    assert system.network.iteration_fields is None


def test_other_residual_callers_without_mechanical_capture_keep_original_matrix():
    system,function,x,rate=setup()
    expected,p,_=jacobian(system,function,x,circulation_rate_factor=rate,direct_mechanics=False)
    def without_capture(v):
        result=function(v)
        fields=system.network.iteration_fields
        if fields is not None:
            fields.mechanical_data.clear()
        return result
    actual,ap,report=jacobian(system,without_capture,x,circulation_rate_factor=rate)
    assert 'not captured' in report['mechanical_derivative_fallback']
    np.testing.assert_array_equal(ap,p)
    np.testing.assert_array_equal(actual.toarray(),expected.toarray())
