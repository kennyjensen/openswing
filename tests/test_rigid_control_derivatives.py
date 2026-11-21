"""Analytic rigid tangents versus independently re-solved physical states."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from openswing.geometry import model_meshes
from openswing.rigid_derivatives import rigid_control_derivatives
from openswing.circulation_tangent import CirculationDerivativeUnavailable
import openswing.rigid_derivatives as helper


def controlled_model(body=False):
    if body:
        text = Path('examples/wing-body.asw').read_text().replace(
            '0 0 0 -.2 .3', '0 0 0 -.2 .25\n0 0 0 -.2 .3')
        text = text.replace('t Cdf\n0 .008\n6 .008',
            't Cdf Cdp dCLdF1 dCMdF1 dCDdF1 dCLdF2 dCMdF2 dCDdF2\n'
            '0 .008 .02 .05 -.012 .002 -.03 .02 -.001\n'
            '6 .008 .02 .07 -.008 .003 -.02 .01 -.001')
    else:
        text = Path('tests/data/derivative-quiet-wing.asw').read_text().replace(
            't dCLdF1 dCMdF1\n0 .05 -.012\n6 .05 -.012',
            't Cdp dCLdF1 dCMdF1 dCDdF1 dCLdF2 dCMdF2 dCDdF2\n'
            '0 .02 .05 -.012 .002 -.03 .02 -.001\n'
            '6 .02 .07 -.008 .003 -.02 .01 -.001')
    return parse_asw(text)


def wrench(result):
    return np.r_[result['distributed_aero_force'], result['distributed_aero_moment']]


@pytest.mark.parametrize('alpha,stall,modes,frozen,body', [
    (5, False, {}, False, False),
    (17, True, {}, False, False),
    (17, True, {1: 4}, False, False),
    (5, False, {}, True, False),
    (8, True, {}, False, True),
])
def test_control_response_matches_two_refined_resolved_circulation_stencils(alpha, stall, modes, frozen, body):
    model = controlled_model(body)
    condition = FlightCondition(speed=30, alpha=alpha, beta=2, mach=.15,
        controls={1: 1.3, 2: -.7}, rates=[.02, -.03, .01], stall=stall,
        circulation_modes=modes, freeze_influences=frozen)
    audit = {}
    actual = rigid_control_derivatives(model, condition, 12, controls=[2, 1], _audit=audit.update)
    assert actual['physical_evaluations'] == actual['factorizations'] == 1
    assert actual['base_residual'] < 1e-8 and max(actual['linear_residuals']) < 1e-12
    if body:
        assert audit['base']['body_shoulders']
    meshes = model_meshes(model, 12)
    for column, control in enumerate([2, 1]):
        previous = None
        for h in (.002, .001):
            pair = [evaluate_aerodynamics(model, replace(condition,
                controls={**condition.controls, control: condition.controls[control]+sign*h}), meshes)
                for sign in (1, -1)]
            assert all(p['residual'] < 1e-8 for p in pair)
            expected_wrench = (wrench(pair[0])-wrench(pair[1]))/(2*h)
            expected_gamma = (np.array([s['circulation'] for s in pair[0]['strips'] if s['lifting']])
                              -np.array([s['circulation'] for s in pair[1]['strips'] if s['lifting']]))/(2*h)
            np.testing.assert_allclose(np.asarray(actual['distributed_aero_wrench'])[:, column],
                                       expected_wrench, rtol=3e-6, atol=2e-6)
            np.testing.assert_allclose(np.asarray(actual['circulation'])[:, column], expected_gamma,
                                       rtol=3e-6, atol=2e-8)
            np.testing.assert_allclose(np.asarray(actual['coefficients'])[:, column],
                                       audit['coefficient_transform']@expected_wrench, rtol=3e-6, atol=2e-9)
            if previous is not None:
                np.testing.assert_allclose(expected_wrench, previous, rtol=3e-6, atol=2e-6)
            previous = expected_wrench


def test_direct_control_load_contains_separation_drag_before_circulation_response():
    text = Path('tests/data/derivative-quiet-wing.asw').read_text().replace('-.012', '0')
    model = parse_asw(text)
    condition = FlightCondition(alpha=19, mach=0, controls={1: 8})
    audit = {}
    rigid_control_derivatives(model, condition, 10, controls=[1], _audit=audit.update)
    data = audit['fields'].circulation_aero; p = data['p']; gamma = data['gamma']
    assert np.linalg.norm(audit['wrench_direct']) > 1.
    v = data['velocity']; vp = v-(v*p['s']).sum(axis=1)[:, None]*p['s']
    speed = np.linalg.norm(vp, axis=1)
    # Independent physical normal/force calculation, with no tangent helper.
    slope = np.array([model.beams[0].value('dCLdF1', t) for t in p['t']])/p['slope']
    dn = slope[:, None]*((p['normal']*p['section_normal']).sum(axis=1)[:, None]*p['c']
                        -(p['normal']*p['c']).sum(axis=1)[:, None]*p['section_normal'])
    tau_f = (data['cp_velocity']*dn).sum(axis=1)
    df = 4*data['rho']*vp/speed[:, None]*(p['chord']*p['ds']*data['tangency']*tau_f)[:, None]
    dm = np.cross(p['rm']+p['profile_arm']-model.reference[1], df)
    np.testing.assert_allclose(audit['wrench_direct'][:, 0], np.r_[df.sum(axis=0), dm.sum(axis=0)], atol=2e-12)
    meshes = model_meshes(model, 10)
    for h in (.002, .001):
        pair = [evaluate_aerodynamics(model, replace(condition, controls={1: 8+sign*h}), meshes,
                                     circulation=gamma) for sign in (1, -1)]
        np.testing.assert_allclose((wrench(pair[0])-wrench(pair[1]))/(2*h),
                                   audit['wrench_direct'][:, 0], rtol=2e-8, atol=2e-7)


def test_multiple_controls_share_one_factorization_and_do_not_perturb_condition(monkeypatch):
    model = controlled_model(); condition = FlightCondition(alpha=4, mach=0, controls={1: 2, 2: 1})
    evaluations, factorizations = [], []
    physical, factor = helper.evaluate_aerodynamics, helper.lu_factor
    def observed(m, c, *args, **kwargs):
        assert c is condition
        evaluations.append(c)
        return physical(m, c, *args, **kwargs)
    def observed_factor(matrix):
        factorizations.append(matrix.shape)
        return factor(matrix)
    monkeypatch.setattr(helper, 'evaluate_aerodynamics', observed)
    monkeypatch.setattr(helper, 'lu_factor', observed_factor)
    result = rigid_control_derivatives(model, condition, 8)
    assert len(evaluations) == len(factorizations) == 1
    assert np.shape(result['coefficients']) == (6, 2)


def test_supplied_circulation_reproduces_tangent_and_unconverged_state_is_rejected():
    model = controlled_model(); condition = FlightCondition(alpha=8, mach=0, controls={1: 1})
    audit = {}
    first = rigid_control_derivatives(model, condition, 8, _audit=audit.update)
    gamma = audit['fields'].circulation_aero['gamma']
    again = rigid_control_derivatives(model, condition, 8, circulation=gamma)
    np.testing.assert_array_equal(first['coefficients'], again['coefficients'])
    with pytest.raises(AnalysisError, match='converged base'):
        rigid_control_derivatives(model, condition, 8, circulation=gamma+.1)


@pytest.mark.parametrize('controls', [[], [1, 1], [999], [True]])
def test_bad_control_selection_is_rejected(controls):
    with pytest.raises(CirculationDerivativeUnavailable, match='distinct declared'):
        rigid_control_derivatives(controlled_model(), FlightCondition(alpha=3, mach=0), 4, controls=controls)


def test_engine_and_one_sided_drag_boundaries_are_explicit():
    model = parse_asw(Path('examples/powered.asw').read_text())
    with pytest.raises(AnalysisError, match='engine-inflow'):
        rigid_control_derivatives(model, FlightCondition(), 4)
    text = Path('tests/data/derivative-quiet-wing.asw').read_text().replace(
        't dCLdF1 dCMdF1\n0 .05 -.012\n6 .05 -.012',
        't dCLdF1 dCMdF1 dCDdF1\n0 .05 -.012 .01\n6 .05 -.012 .01')
    with pytest.raises(AnalysisError, match='profile-drag boundary'):
        rigid_control_derivatives(parse_asw(text), FlightCondition(alpha=0, mach=0), 4)
