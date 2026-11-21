"""Continuous rigid-pylon identities must not imply exact finite-BDF parity."""
import pytest

from scripts.isae_ffwt4_rigid_bdf import probe, refinement


@pytest.mark.parametrize('order', [1, 2])
def test_source_kinematic_history_leaves_anchor_dependent_finite_step_error(order):
    result = refinement(order)
    assert all(row['velocity_difference'] > 0 and row['acceleration_difference'] > 0 for row in result['rows'])
    assert not result['exact_finite_step_equivalence']


@pytest.mark.parametrize('order', [1, 2])
def test_stationary_rigid_pose_has_no_pylon_representation_difference(order):
    result = probe(order, .01, omega=0.)
    assert result['velocity_difference'] == result['acceleration_difference'] == 0
