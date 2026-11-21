"""Source time partials against independent full-residual stencils."""
from copy import deepcopy
import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.feedback import FeedbackSystem
from openswing.ground import body_to_earth
from openswing.hinge_history import at_network
from openswing.nonlinear_initial import InitialSystem
from openswing.radau_time import INVERSE, NODES
from openswing.source_airflow import SourceAirflowNetwork
from openswing.time_integration import TimeState, TimeSystem, bdf_coefficients
from openswing.time_tangent import attach_mechanical_columns
from test_source_coupled import source, condition, trial


def setup(signal='rx[1]'):
    text = source().rsplit('End\n', 1)[0] + 't tdeps tdgam\n1 .02 .03\n3 .04 .01\nEnd\n'
    n = SourceAirflowNetwork(parse_asw(text, beam_interpolation='drela-segspl-v1'),
                            4, condition(), [1., -2., -9.], [])
    controller = FeedbackSystem(n, dict(outputs=[dict(actuator='F1',
        terms=[dict(input=signal, gain=-.01)])]))
    system = TimeSystem(n, controller=controller)
    x = trial(n);r,q,*_,gamma = n.unpack(x)
    rng = np.random.default_rng(901)
    state = TimeState(0., x, r, q, rng.normal(0,.02,r.shape), rng.normal(0,.01,r.shape),
        -n.condition.speed*n.condition.vectors()[0], np.array([.02,-.03,.01]),
        np.array([.1,.2,.3]), body_to_earth([4.,-3.,2.]), gamma,
        hinge_charts=at_network(n,q))
    _, data = n.residual(x, detail=True)
    controller.initialize(state, data)
    system.source_time.bind(state)
    return system, state


def compare_columns(function, x, indices, matrix):
    actual = matrix.toarray()
    for width in (1e-5, 3e-6):
        for k,j in enumerate(indices):
            delta = np.zeros_like(x);delta[j] = width*max(1.,abs(x[j]))
            expected = (function(x+delta)-function(x-delta))/(2*delta[j])
            assert np.max(abs(actual[:,k]-expected)/(1+abs(expected))) < 2e-8


@pytest.mark.parametrize('previous_step', [None, .013])
def test_bdf_source_columns_keep_loaded_motion_damping_and_feedback(previous_step):
    system, previous = setup()
    older = None if previous_step is None else deepcopy(previous)
    if older is not None:older.time = -previous_step
    coefficients = bdf_coefficients(.017, previous_step)
    values = system.guess(previous, .017)
    values += np.random.default_rng(902).normal(0.,1e-5,len(values))
    function = lambda v:system.residual(v, previous, older, .017, coefficients)
    before = function(values).copy()
    attach_mechanical_columns(system, function, lambda v, data:system.residual(
        v, previous, older, .017, coefficients, _mechanical_data=data[0]))
    indices, matrix = function.direct_mechanical_columns(values)
    compare_columns(function, values, indices, matrix)
    assert matrix[system.network.size:].nnz == 0
    np.testing.assert_array_equal(function(values), before)


def test_radau_source_columns_keep_all_stage_couplings():
    system, previous = setup('Cr[1]')
    chart = InitialSystem(system, previous, 'prescribed', apply_forcing=True)
    h = .017;size = chart.size;times = NODES*h
    values = np.random.default_rng(903).normal(0., 1e-5, 3*size)
    def function(flat, data=None):
        increments = flat.reshape(3,size);rates = INVERSE@increments/h
        return np.concatenate([chart.residual(z,d,t,
            **({} if data is None else dict(_mechanical_data=data[k])))
            for k,(z,d,t) in enumerate(zip(increments,rates,times))])
    before = function(values).copy()
    attach_mechanical_columns(system, function, lambda v,data:function(v,data), stages=3)
    indices, matrix = function.direct_mechanical_columns(values)
    compare_columns(function, values, indices, matrix)
    np.testing.assert_array_equal(function(values), before)


@pytest.mark.parametrize('signal', ['Fc[1]', 'Ms[1]'])
def test_load_measurement_feedback_keeps_its_nonzero_mechanical_coupling(signal):
    system, previous = setup(signal)
    coefficients = bdf_coefficients(.017)
    values = system.guess(previous, .017)
    function = lambda v:system.residual(v, previous, None, .017, coefficients)
    def forbidden(*args):
        pytest.fail('Force/moment feedback must retain its full residual stencil')
    attach_mechanical_columns(system, function, forbidden)
    assert not hasattr(function, 'direct_mechanical_columns')
    sensitivity = []
    for j in range(6*system.network.nn, system.network.gamma_start):
        delta = np.zeros_like(values);delta[j] = 1e-5
        sensitivity.append((function(values+delta)[-1]-function(values-delta)[-1])/2e-5)
    assert max(abs(np.asarray(sensitivity))) > 1e-8


def test_unavailable_source_derivative_retains_the_complete_rank_matrix(monkeypatch):
    from openswing.time_integration import regular_tangent
    from openswing.mechanical_tangent import MechanicalDerivativeUnavailable
    import openswing.time_tangent as tangent
    system, previous = setup()
    coefficients = bdf_coefficients(.017)
    values = system.guess(previous, .017)
    function = lambda v:system.residual(v, previous, None, .017, coefficients)
    matrices = []
    function.accepted_root_diagnostic = lambda f,x,j:matrices.append(j.copy())
    regular_tangent(function, values)
    attach_mechanical_columns(system, function, lambda v,data:system.residual(
        v, previous, None, .017, coefficients, _mechanical_data=data[0]))
    def unavailable(*args, **kwargs):
        raise MechanicalDerivativeUnavailable('deliberate unsupported constitutive branch')
    monkeypatch.setattr(tangent, 'source_network_mechanical_columns', unavailable)
    regular_tangent(function, values)
    assert len(matrices) == 2
    np.testing.assert_array_equal(matrices[1], matrices[0])
