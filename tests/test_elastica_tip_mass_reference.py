"""Independent controls of large-rotation equilibrium and its tip tangent."""
from pathlib import Path
import importlib.util
import numpy as np
import pytest

path = Path(__file__).resolve().parents[1] / 'scripts/elastica_tip_mass_reference.py'
spec = importlib.util.spec_from_file_location('elastica_reference', path)
reference = importlib.util.module_from_spec(spec); spec.loader.exec_module(reference)
PCR = np.pi ** 2 * 100 / (4 * 2 ** 2)


@pytest.mark.parametrize('ratio', [.5, 1.5])
def test_nonlinear_force_derivative_matches_analytic_tangent(ratio):
    p = ratio * PCR; q = .02 * p; h = 1e-4
    base = reference.solve(p, q)
    for column in (0, 1):
        plus = reference.solve(p - (h if column == 0 else 0), q + (h if column == 1 else 0))
        minus = reference.solve(p + (h if column == 0 else 0), q - (h if column == 1 else 0))
        measured = (np.array(plus['positions']) - np.array(minus['positions'])) / (2 * h)
        expected = np.array(base['force_sensitivities'])[:, :2, column]
        np.testing.assert_allclose(measured[:, 1:], expected, rtol=2e-5, atol=2e-9)
        measured_angle = (np.array(plus['angles']) - np.array(minus['angles'])) / (2 * h)
        np.testing.assert_allclose(measured_angle, np.array(base['force_sensitivities'])[:, 2, column], rtol=2e-5, atol=2e-9)
    assert base['reciprocity_error'] < 1e-10
    assert base['energy_first_integral_error'] / p < 1e-10


def test_mirrored_loads_mirror_shape_and_preserve_frequencies():
    positive = reference.solve(1.5 * PCR, .03 * PCR)
    negative = reference.solve(1.5 * PCR, -.03 * PCR)
    np.testing.assert_allclose(np.array(positive['positions']) * [1., 1., -1.], negative['positions'], rtol=0., atol=1e-12)
    np.testing.assert_allclose(np.array(positive['angles']), -np.array(negative['angles']), rtol=0., atol=1e-12)
    np.testing.assert_allclose(positive['angular_frequencies'], negative['angular_frequencies'], rtol=2e-12)
    assert max(positive['angles']) > np.pi / 2


def test_small_transverse_load_recovers_linear_cantilever():
    q = .25; result = reference.solve(0., q)
    expected = q * 2 ** 3 / (3 * 100)
    assert abs(result['positions'][-1][2] / expected - 1) < 2e-5
    assert abs(result['root_moment'] / (2 * q) - 1) < 2e-5


def test_elastica_obeys_length_stiffness_mass_scaling():
    a = reference.solve(1.5 * PCR, .03 * PCR)
    # Double length, quadruple EI, same force: identical angles, doubled
    # compliance, and 1/sqrt(6) frequencies when tip mass is tripled.
    b = reference.solve(1.5 * PCR, .03 * PCR, length=4., ei=400., mass=3.)
    np.testing.assert_allclose(b['positions'], 2 * np.array(a['positions']), rtol=2e-11, atol=2e-12)
    np.testing.assert_allclose(b['angles'], a['angles'], rtol=2e-11, atol=2e-12)
    np.testing.assert_allclose(b['compliance'], 2 * np.array(a['compliance']), rtol=2e-11, atol=2e-12)
    np.testing.assert_allclose(b['angular_frequencies'], np.array(a['angular_frequencies']) / np.sqrt(6), rtol=2e-11)


@pytest.mark.parametrize('p,q', [(-1., 1.), (1., 0.), (np.nan, 1.)])
def test_invalid_force_branch_rejected(p, q):
    with pytest.raises(ValueError, match='compression'):
        reference.solve(p, q)
