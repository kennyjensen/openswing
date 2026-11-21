import numpy as np
import pytest
from scipy.linalg import block_diag
from openswing.linear_dynamics import eigensystem


def constrained_pencil():
    # Two constrained masses: 5 x'' + 1.2 x' + 28 x = 0. Add a weak
    # inertia, three remote finite poles and three exact position integrators.
    a = np.array([[0, 0, 1, 0, 0], [0, 0, 0, 1, 0],
                  [-18, 7, -.4, 0, 1], [7, -24, 0, -.8, -1], [1, -1, 0, 0, 0]], dtype=float)
    m = np.diag([1., 1., 2., 3., 0.])
    return (block_diag(a, -np.eye(1), -np.diag([20., 30., 40.]), np.zeros((3, 3))),
            block_diag(m, np.array([[1e-11]]), np.eye(3), np.eye(3)))


def test_reduction_rejects_resolved_weak_inertia_far_below_requested_cutoff():
    # Previously only the top two decades below the requested cutoff were
    # guarded. A real weak inertia farther below it could silently disappear.
    a, m = constrained_pencil()
    with pytest.raises(ValueError, match='weak inertia'):
        eigensystem(a, m, rank_tolerance=1e-9)


@pytest.mark.parametrize('time_scale', [.001, 1., 1000.])
def test_full_descriptor_search_retains_constraints_and_left_right_vectors(time_scale):
    a, m = constrained_pencil()
    # Re-express physical seconds in different input time units.
    m = m/time_scale
    expected = np.roots([5., 1.2, 28.])*time_scale
    modes, meta = eigensystem(a, m, time_scale=time_scale, count=2,
                              shift=(-.12*time_scale, 2.4*time_scale), method='full_shift_invert')
    # The positive root is closest; a numerical zero can fill the second slot.
    nearest = modes[0]; value = complex(*nearest['eigenvalue'])
    assert min(abs(value-expected)) < 1e-9*time_scale
    assert meta['finite_dimension'] is None and meta['eliminated_dimension'] is None
    assert meta['rank_tolerance'] is None and meta['right_reduction'] == []
    assert meta['integrator_deflation']['count'] == 0
    assert meta['arnoldi']['retained_dimension'] == len(a)
    for mode in modes:
        value = complex(*mode['eigenvalue']); v, w = mode['right'], mode['left']
        np.testing.assert_allclose(a@v, value*m@v, atol=1e-9)
        np.testing.assert_allclose(w.conj()@a, value*(w.conj()@m), atol=1e-9*time_scale)
        assert max(mode['right_backward_error'], mode['left_backward_error']) < 1e-10
        assert not mode['exact_integrator']
        assert v[0] == pytest.approx(v[1], abs=1e-10)
        assert np.vdot(w, m@v) == pytest.approx(1, abs=1e-10)


def test_full_descriptor_search_rejects_singular_shift_and_excess_count():
    a = -np.diag(np.arange(1., 9)); m = np.eye(8)
    with pytest.raises(ValueError, match='shift is on'):
        eigensystem(a, m, method='full_shift_invert', count=2, shift=(-4., 0.))
    with pytest.raises(ValueError, match='reduce count'):
        eigensystem(a, m, method='full_shift_invert', count=7)
    with pytest.raises(ValueError, match='shift is on'):
        eigensystem(np.diag([1.]*7+[0.]), np.diag([1.]*7+[0.]), method='full_shift_invert', count=2)
