"""Velocity-reference covariance (steady eqs. 181–184, 218–219).

ASWING 5.85 fixed rate derivatives missing the induced change of origin
velocity when the air-data reference is displaced. Verify that transformation
independently of the implementation's direct kinematic differentiation.
"""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from openswing.aero import FlightCondition, solve_rigid
from openswing.rigid_derivatives import rigid_state_derivatives
from test_rigid_control_derivatives import controlled_model


@pytest.mark.parametrize('modes', [{}, {1: 4}], ids=['pointwise', 'fourier'])
def test_velocity_reference_transports_rates_and_preserves_physical_flow(modes):
    # Frozen influence geometry, prescribed PG Mach and no volume sources:
    # this isolates reference kinematics from changes of the assumed wake or
    # uniform-flow volume model when the air-data angles/speed are changed.
    model = controlled_model()
    model.reference[3] = 0.
    shifted = deepcopy(model)
    displacement = np.array([1.7, -.9, .6])
    shifted.reference[3] = displacement
    condition = FlightCondition(speed=30., alpha=17., beta=3., mach=0.,
        controls={1: 1.3, 2: -.7}, freeze_influences=True,
        circulation_modes=modes)
    original = rigid_state_derivatives(model, condition, 6)
    moved = rigid_state_derivatives(shifted, condition, 6)
    assert original['parameters'] == moved['parameters'] == ['u', 'alpha', 'beta', 'p', 'q', 'r']

    a, b = np.deg2rad([condition.alpha, condition.beta])
    ca, sa, cb, sb = np.cos(a), np.sin(a), np.cos(b), np.sin(b)
    # d(V_ref)/d(u, alpha, beta), with u the fractional speed change.
    velocity_basis = condition.speed*np.array([
        [ca*cb, -sa*cb, -ca*sb],
        [-sb,   0.,    -cb],
        [sa*cb, ca*cb, -sa*sb],
    ])
    stability_axes = np.array([[-ca, 0., -sa], [0., 1., 0.], [sa, 0., -ca]])
    lengths = model.reference[0, [2, 1, 2]]
    rate_vectors = stability_axes*(2*condition.speed/lengths)[:, None]
    # Holding V_ref fixed at its new location adds Omega x displacement
    # to the origin airflow. Thus each rate column gains uniform-flow columns.
    additional_flow = np.cross(rate_vectors, displacement).T
    transport = np.linalg.solve(velocity_basis, additional_flow)
    for key in ('distributed_aero_wrench', 'distributed_aero_wrench_origin',
                'coefficients', 'coefficients_origin', 'circulation'):
        base = np.asarray(original[key])
        expected = base.copy()
        expected[:, 3:] += base[:, :3]@transport
        np.testing.assert_allclose(moved[key], expected, rtol=2e-11, atol=2e-10)
    for result in (original, moved):
        assert result['physical_evaluations'] == result['factorizations'] == 1
        assert result['base_residual'] < 1e-8
        assert max(result['linear_residuals']) < 1e-12
    assert np.max(abs(np.asarray(moved['coefficients'])[:, 3:]
                         -np.asarray(original['coefficients'])[:, 3:])) > .1

    # Independently retain the same physical velocity field at finite rates:
    # V_new = V_old - Omega x displacement. The dimensional loads and Gamma
    # must agree although air-data speed, angles and normalization change.
    rotating = replace(condition, rates=[.07, -.13, .11])
    old_airflow = condition.speed*np.array([ca*cb, -sb, sa*cb])
    new_airflow = old_airflow-np.cross(rotating.rates, displacement)
    new_speed = np.linalg.norm(new_airflow)
    new_alpha = np.rad2deg(np.arctan2(new_airflow[2], new_airflow[0]))
    new_beta = np.rad2deg(np.arctan2(-new_airflow[1], np.hypot(new_airflow[0], new_airflow[2])))
    represented = replace(rotating, speed=new_speed, alpha=new_alpha, beta=new_beta)
    before = solve_rigid(model, rotating, 6)
    after = solve_rigid(shifted, represented, 6)
    assert before['residual'] < 1e-8 and after['residual'] < 1e-8
    for key in ('distributed_aero_force', 'distributed_aero_moment', 'distributed_aero_moment_origin'):
        np.testing.assert_allclose(after[key], before[key], rtol=2e-11, atol=2e-10)
    gamma = lambda result: [s['circulation'] for s in result['strips'] if s['lifting']]
    np.testing.assert_allclose(gamma(after), gamma(before), rtol=2e-11, atol=2e-10)
