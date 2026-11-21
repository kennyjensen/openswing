"""Standard state derivatives against complete independent physical re-solves."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from openswing.geometry import model_meshes
from openswing.rigid_derivatives import rigid_state_derivatives
from test_rigid_control_derivatives import controlled_model
import openswing.rigid_derivatives as helper


NAMES = ['u', 'alpha', 'beta', 'p', 'q', 'r']


def physical_change(condition, model, name, delta):
    # Eq.219: input rate increments use the unperturbed stability axes and V.
    if name == 'u':
        return replace(condition, speed=condition.speed*(1+delta))
    if name in ('alpha', 'beta'):
        return replace(condition, **{name: getattr(condition, name)+delta*180/np.pi})
    a = condition.alpha*np.pi/180
    axes = np.array([[-np.cos(a), 0, -np.sin(a)], [0, 1, 0], [np.sin(a), 0, -np.cos(a)]])
    column = 'pqr'.index(name)
    length = model.reference[0, 1 if name == 'q' else 2]
    rates = np.asarray(condition.rates)+axes[column]*2*condition.speed/length*delta
    return replace(condition, rates=rates.tolist())


def body_wrench(result):
    return np.r_[result['distributed_aero_force'], result['distributed_aero_moment']]


def base_coefficients(condition, model, density, wrench):
    a = condition.alpha*np.pi/180
    rotation = np.array([[-np.cos(a), 0, -np.sin(a)], [0, 1, 0], [np.sin(a), 0, -np.cos(a)]])
    scale = .5*density*condition.speed**2*model.reference[0, 0]
    force = rotation@wrench[:3]/scale
    force[2] *= -1
    moment = (rotation@wrench[3:])/scale/model.reference[0, [2, 1, 2]]
    return np.r_[force, moment]


@pytest.mark.parametrize('alpha,mach,modes,frozen,body,ground', [
    (6., .2, {}, False, False, 0),
    (17., None, {1: 4}, False, False, 0),
    (5., .2, {}, False, True, 1),
    (5., .2, {}, False, True, -1),
    (8., None, {}, True, True, 0),
])
def test_all_state_columns_match_two_steps_of_fresh_nonlinear_solves(alpha, mach, modes, frozen, body, ground):
    model = controlled_model(body)
    model.reference[3] = [.2, -.3, .1]
    condition = FlightCondition(speed=30, alpha=alpha, beta=2, mach=mach,
        controls={1: 1.3, 2: -.7}, rates=[.02, -.03, .01],
        circulation_modes=modes, freeze_influences=frozen,
        ground_effect=ground, position_earth=[0, 0, 10])
    audit = {}
    result = rigid_state_derivatives(model, condition, 8, _audit=audit.update)
    assert result['parameters'] == NAMES
    assert result['physical_evaluations'] == result['factorizations'] == 1
    assert max(result['linear_residuals']) < 1e-12
    assert result['base_residual'] < 1e-8
    if body:
        assert audit['base']['body_shoulders']
    meshes = model_meshes(model, 8)
    density = audit['base']['atmosphere']['density']
    for j, name in enumerate(NAMES):
        for step in (2e-5, 1e-5):
            pair = [evaluate_aerodynamics(model, physical_change(condition, model, name, sign*step), meshes)
                    for sign in (1, -1)]
            assert all(row['residual'] < 1e-8 for row in pair)
            expected = (body_wrench(pair[0])-body_wrench(pair[1]))/(2*step)
            gamma = [np.array([s['circulation'] for s in row['strips'] if s['lifting']]) for row in pair]
            np.testing.assert_allclose(np.asarray(result['distributed_aero_wrench'])[:, j], expected,
                                       rtol=5e-6, atol=3e-5)
            np.testing.assert_allclose(np.asarray(result['coefficients'])[:, j],
                base_coefficients(condition, model, density, expected), rtol=5e-6, atol=3e-8)
            np.testing.assert_allclose(np.asarray(result['circulation'])[:, j],
                                       (gamma[0]-gamma[1])/(2*step), rtol=5e-6, atol=2e-6)


def test_speed_uses_fixed_base_dynamic_pressure_and_angles_use_fixed_output_axes():
    model = parse_asw(Path('tests/data/derivative-quiet-wing.asw').read_text())
    condition = FlightCondition(speed=20, alpha=7, mach=0, stall=False)
    audit = {}
    result = rigid_state_derivatives(model, condition, 8, _audit=audit.update)
    # With constant specified PG Mach and zero Cm, all distributed loads are
    # homogeneous of degree two in speed. Renormalizing each perturbed state
    # would incorrectly erase the whole speed column.
    np.testing.assert_allclose(np.asarray(result['coefficients'])[:, 0],
                               2*np.asarray(result['base_coefficients']), rtol=1e-10, atol=1e-12)
    assert abs(result['coefficients'][2][0]) > .1
    step = 1e-5
    meshes = model_meshes(model, 8)
    pair = [evaluate_aerodynamics(model, replace(condition, alpha=7+sign*step*180/np.pi), meshes)
            for sign in (1, -1)]
    moving_axes = (base_coefficients(replace(condition, alpha=7+step*180/np.pi), model,
                    audit['base']['atmosphere']['density'], body_wrench(pair[0]))
                  -base_coefficients(replace(condition, alpha=7-step*180/np.pi), model,
                    audit['base']['atmosphere']['density'], body_wrench(pair[1])))/(2*step)
    assert np.max(abs(moving_axes-np.asarray(result['coefficients'])[:, 1])) > .1


def test_state_columns_share_one_physical_call_and_one_factorization(monkeypatch):
    model = controlled_model()
    condition = FlightCondition(alpha=5, mach=0)
    count = [0, 0]
    physical, factor = helper.evaluate_aerodynamics, helper.lu_factor
    def observed(m, c, *args, **kwargs):
        assert c is condition
        count[0] += 1
        return physical(m, c, *args, **kwargs)
    def observed_factor(matrix):
        count[1] += 1
        return factor(matrix)
    monkeypatch.setattr(helper, 'evaluate_aerodynamics', observed)
    monkeypatch.setattr(helper, 'lu_factor', observed_factor)
    result = rigid_state_derivatives(model, condition, 6, parameters=['r', 'u', 'alpha'])
    assert count == [1, 1] and result['parameters'] == ['r', 'u', 'alpha']
    assert np.shape(result['coefficients']) == (6, 3)


@pytest.mark.parametrize('parameters', [[], ['u', 'u'], ['speed'], [True], 'u'])
def test_invalid_state_coordinates_are_rejected(parameters):
    with pytest.raises(AnalysisError, match='distinct names'):
        rigid_state_derivatives(controlled_model(), FlightCondition(mach=0), 4, parameters=parameters)


def test_spatial_gust_sampling_moves_with_the_wind_defined_force_points():
    model = controlled_model()
    condition = FlightCondition(alpha=8, beta=2, mach=.1, gust=dict(type='sum', fields=[
        dict(type='sinusoid', amplitude=[.2, .1, .5], wavevector=[.2, .1, .05], phase=.7),
        dict(type='cosine', amplitude=[.1, 0, .3], normal=[1, 0, 0], origin=[-2, 0, 0], length=4)]))
    result = rigid_state_derivatives(model, condition, 8, parameters=['alpha', 'beta'])
    meshes = model_meshes(model, 8)
    for j, name in enumerate(['alpha', 'beta']):
        for step in (2e-5, 1e-5):
            pair = [evaluate_aerodynamics(model, physical_change(condition, model, name, sign*step), meshes)
                    for sign in (1, -1)]
            expected = (body_wrench(pair[0])-body_wrench(pair[1]))/(2*step)
            np.testing.assert_allclose(np.asarray(result['distributed_aero_wrench'])[:, j], expected,
                                       rtol=5e-6, atol=3e-5)


def test_unimplemented_expression_gust_gradient_is_explicit():
    condition = FlightCondition(alpha=4, mach=0, gust=dict(type='expression', components=['0', '0', '.1*x']))
    with pytest.raises(AnalysisError, match='expression-gust'):
        rigid_state_derivatives(controlled_model(), condition, 4)


def test_swept_tapered_nonplanar_two_surface_state_chain():
    source = Path('tests/data/derivative-quiet-wing.asw').read_text()
    source = source.replace('0 0 0 0 1 .25\n6 0 6 0 1 .25',
                            '0 0 0 0 1 .1\n6 2 6 1 .7 .4')
    second = source[source.index('Beam 1'):].replace('Beam 1', 'Beam 2').replace(
        '0 0 0 0 1 .1\n6 2 6 1 .7 .4', '0 3 0 -.6 .8 .2\n6 4 6 -.2 .5 .35')
    model = parse_asw(source+second)
    condition = FlightCondition(speed=25, alpha=5, beta=3, mach=.3, rates=[.01, .02, -.01])
    actual = rigid_state_derivatives(model, condition, 8, parameters=['alpha', 'beta', 'r'])
    meshes = model_meshes(model, 8)
    for j, name in enumerate(['alpha', 'beta', 'r']):
        for step in (2e-5, 1e-5):
            pair = [evaluate_aerodynamics(model, physical_change(condition, model, name, sign*step), meshes)
                    for sign in (1, -1)]
            np.testing.assert_allclose(np.asarray(actual['distributed_aero_wrench'])[:, j],
                (body_wrench(pair[0])-body_wrench(pair[1]))/(2*step), rtol=5e-6, atol=3e-5)


def test_direct_state_residual_partial_includes_off_equilibrium_speed_normalization():
    from openswing.structured_static import IterationFields
    from openswing.state_tangent import StateFlow
    from openswing.rigid_derivatives import distributed_wrench_columns
    model = controlled_model()
    condition = FlightCondition(speed=20, alpha=17, beta=2, mach=None)
    meshes = model_meshes(model, 6)
    fields = IterationFields(); fields.capture_circulation = True
    gamma = np.full(sum(len(m.tm) for m in meshes if m.beam.lifting), 2.)
    baseline = evaluate_aerodynamics(model, condition, meshes, circulation=gamma, _iteration_fields=fields)
    assert np.max(np.abs(baseline['circulation_residual'])) > .01
    flow = StateFlow(model, meshes, fields, ['u', 'alpha'])
    actual_wrench, actual_residual = distributed_wrench_columns(model, fields.circulation_aero, flow)
    for j, name in enumerate(['u', 'alpha']):
        for step in (2e-5, 1e-5):
            pair = [evaluate_aerodynamics(model, physical_change(condition, model, name, sign*step),
                                         meshes, circulation=gamma) for sign in (1, -1)]
            expected = (np.asarray(pair[0]['circulation_residual'])-pair[1]['circulation_residual'])/(2*step)
            np.testing.assert_allclose(actual_residual[:, j], expected, rtol=3e-7, atol=1e-9)
            np.testing.assert_allclose(actual_wrench[:, j],
                (body_wrench(pair[0])-body_wrench(pair[1]))/(2*step), rtol=3e-7, atol=2e-6)
