"""Real-pole certification must not erase small physical oscillations."""
from copy import deepcopy

import numpy as np
import pytest

from scripts.isae_modal_classification import classify_modes


def mode(root, right, left=None):
    def split(v):
        v = np.asarray(v, dtype=complex)
        return dict(real=v.real.tolist(), imag=v.imag.tolist())
    return dict(eigenvalue=root, right=split(right), left=split(right if left is None else left))


def classify(modes, a, m=None, shift=(0., 200.), rate=1.):
    return classify_modes(modes, a, np.eye(len(a)) if m is None else m,
                          shift=shift, characteristic_rate=rate)


@pytest.mark.parametrize('noise', [-2e-12, 0., 2e-12])
def test_phase_rotated_real_mode_has_both_independent_pencil_certificates(noise):
    a = np.array([[-23., 7.], [0., -37.]])
    original = mode([-23., noise], np.array([1., 0.])*np.exp(.4j),
                    np.array([1., .5])*np.exp(-.7j))
    saved = deepcopy(original)
    result = classify([original], a)[0]
    assert result['classification'] == 'certified_real'
    assert result['right']['passed'] and result['left']['passed']
    assert result['projected_mass_pairing'] > 0
    assert original == saved  # neither root nor vector is rounded in place


@pytest.mark.parametrize('omega', [1e-12, 1e-5, 10.])
def test_true_complex_pair_is_not_certified_real_even_inside_roundoff_window(omega):
    a = np.array([[-2., -omega], [omega, -2.]])
    modes = [mode([-2., omega], [1., -1j]), mode([-2., -omega], [1., 1j])]
    result = classify(modes, a)
    assert all(r['classification'] != 'certified_real' for r in result)
    if omega == 1e-12:
        assert all(r['classification'] == 'unresolved_near_real' for r in result)
        assert all(not r['right']['passed'] for r in result)
    else:
        assert [r['classification'] for r in result] == ['positive_frequency', 'negative_frequency']


@pytest.mark.parametrize('side', ['right', 'left'])
def test_small_imaginary_part_does_not_replace_a_valid_real_pencil_equation(side):
    original = mode([-2., 1e-12], [1., 0.])
    original[side]['real'] = [0., 1.]
    result = classify([original], np.diag([-2., -3.]))[0]
    assert result['classification'] == 'unresolved_near_real'
    assert not result[side]['passed']


def test_zero_mass_nullspace_is_not_a_certified_finite_pole():
    result = classify([mode([0., 0.], [1., 0.])], np.diag([0., 1.]), np.diag([0., 1.]))[0]
    assert result['classification'] == 'unresolved_near_real'
    assert result['projected_mass_pairing'] == 0


@pytest.mark.parametrize('scale', [1e-6, 1., 1e6])
def test_changing_time_units_preserves_real_pole_classification(scale):
    result = classify([mode([-23.*scale, 2e-12*scale], [1., 0.])],
                      np.diag([-23., -37.])*scale, shift=(0., 200.*scale), rate=scale)[0]
    assert result['classification'] == 'certified_real'


@pytest.mark.parametrize('bad', [np.array([[complex(1., 1e-20)]]), np.array([[np.nan]]), np.ones((2, 1))])
def test_invalid_or_complex_matrix_cannot_certify_a_real_pole(bad):
    with pytest.raises(ValueError, match='pencil matrices'):
        classify([mode([1., 0.], [1.])], bad)


def test_nonfinite_or_incomplete_vectors_are_rejected():
    with pytest.raises(ValueError, match='Complete finite'):
        classify([mode([-2., 1e-12], [1.])], np.diag([-2., -3.]))
    with pytest.raises(ValueError, match='Complete finite'):
        classify([mode([-2., 1e-12], [np.nan, 0.])], np.diag([-2., -3.]))
