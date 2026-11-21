"""Explicit origin derivatives preserve rigid reference-point translations."""
from copy import deepcopy
from dataclasses import replace
import numpy as np
import pytest

from openswing.aero import FlightCondition, solve_rigid
from openswing.rigid_derivatives import rigid_control_derivatives, rigid_state_derivatives
from test_rigid_control_derivatives import controlled_model


@pytest.mark.parametrize('scope', ['state', 'control'])
@pytest.mark.parametrize('body', [False, True])
def test_origin_columns_are_reference_invariant_and_match_physical_perturbations(scope, body):
    model = controlled_model(body)
    model.reference[1] = 0.
    condition = FlightCondition(speed=30., alpha=7., beta=3., mach=.1,
                                controls={1: 1.3, 2: -.7})
    solve = rigid_state_derivatives if scope == 'state' else rigid_control_derivatives
    original = solve(model, condition, 6)
    moved_model = deepcopy(model)
    shift = np.array([.37, -.21, .13])
    moved_model.reference[1] = shift
    moved = solve(moved_model, condition, 6)

    for key in ('distributed_aero_wrench', 'coefficients', 'base_coefficients'):
        np.testing.assert_array_equal(original[key+'_origin'], original[key])
        np.testing.assert_allclose(moved[key+'_origin'], original[key], rtol=2e-13, atol=2e-12)
    np.testing.assert_array_equal(moved['circulation'], original['circulation'])
    assert moved['physical_evaluations'] == moved['factorizations'] == 1
    assert moved['moment_definitions']['reference'] == shift.tolist()
    assert moved['moment_definitions']['coefficient_axes'] == 'base stability'
    assert moved['moment_definitions']['wrench_axes'] == 'body'
    assert np.max(abs(np.array(moved['coefficients'])[3:]-np.array(original['coefficients'])[3:])) > .01

    # Check one whole six-output column against fresh nonlinear origin loads.
    # The unchanged analytic derivatives already have full multi-step tests;
    # here the translated outputs must recover the same physical origin wrench.
    h = 1e-5
    pair = []
    for sign in (1, -1):
        perturbed = (replace(condition, rates=[0., sign*h*2*condition.speed/model.reference[0, 1], 0.])
                     if scope == 'state' else
                     replace(condition, controls={**condition.controls, 1: condition.controls[1]+sign*h}))
        result = solve_rigid(moved_model, perturbed, 6)
        pair.append(np.r_[result['distributed_aero_force'], result['distributed_aero_moment_origin']])
    expected_wrench = (pair[0]-pair[1])/(2*h)
    column = moved['parameters'].index('q') if scope == 'state' else moved['controls'].index(1)
    np.testing.assert_allclose(np.asarray(moved['distributed_aero_wrench_origin'])[:, column],
                               expected_wrench, rtol=5e-6, atol=3e-6)
    a = np.deg2rad(condition.alpha)
    rotation = np.array([[-np.cos(a), 0., -np.sin(a)], [0., 1., 0.], [np.sin(a), 0., -np.cos(a)]])
    scale = .5*result['atmosphere']['density']*condition.speed**2*model.reference[0, 0]
    force = rotation@expected_wrench[:3]/scale
    force[2] *= -1
    moment = (rotation@expected_wrench[3:])/scale/model.reference[0, [2, 1, 2]]
    np.testing.assert_allclose(np.asarray(moved['coefficients_origin'])[:, column],
                               np.r_[force, moment], rtol=5e-6, atol=3e-8)
