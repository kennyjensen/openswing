"""Explicit model comparisons, independent cut balances and Schur tangents."""
import numpy as np
import pytest

from scripts.isae_ffwt4_rigid_extension_v2 import (
    fixture, balanced_state, compare_loads, compare_tangent, physical_loads,
)


@pytest.mark.parametrize('upper', [False, True])
@pytest.mark.parametrize('panels', [4, 6])
@pytest.mark.parametrize('tilted,local', [(False, False), (True, False), (True, True)])
def test_all_retained_endpoint_loads_match_independent_moving_point_oracle(upper, panels, tilted, local):
    compare_loads(upper=upper, panels=panels, tilted=tilted, local=local)


@pytest.mark.parametrize('upper', [False, True])
def test_static_jig_load_balance_closes_complete_source_equations(upper):
    report = compare_loads(upper=upper, moving=False)
    assert max(report['complete_residuals']) < 2e-13


@pytest.mark.parametrize('upper', [False, True])
@pytest.mark.parametrize('tilted', [False, True])
def test_production_pose_and_load_matrix_matches_after_eliminating_extension(upper, tilted):
    compare_tangent(upper=upper, tilted=tilted)


def test_interior_reanchor_changes_section_loads_despite_same_total_wrench():
    correct = fixture(extended=False)
    wrong = fixture(extended=False, anchor=1.5)
    _, a, *_ = balanced_state(correct, tilted=True, local=True)
    _, b, *_ = balanced_state(wrong, tilted=True, local=True)
    for data in (a, b):
        data['global_wrench'] = np.r_[data['force'].sum(axis=0),
            (data['moment']+np.cross(data['r'], data['force'])).sum(axis=0)]
    np.testing.assert_allclose(a['global_wrench'], b['global_wrench'], rtol=2e-14, atol=2e-14)
    assert np.max(abs(physical_loads(correct, a)-physical_loads(wrong, b))) > 1


def test_finite_extension_compliance_cannot_use_rigid_condensation():
    f = fixture(extended=True, flexible_extension=True)
    with pytest.raises(ValueError, match='not exactly rigid'):
        balanced_state(f)
