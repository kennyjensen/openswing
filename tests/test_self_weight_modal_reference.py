"""Analytical and invariance controls for the distributed column reference."""
from pathlib import Path
import importlib.util
import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.sparse.linalg import eigsh


def load(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reference = load('self_weight_modal_reference')
airy = load('self_weight_column_reference')


def test_four_unloaded_frequencies_match_cantilever_characteristic():
    roots = [brentq(lambda x: np.cosh(x) * np.cos(x) + 1., a, b)
             for a, b in [(1., 2.), (4., 5.), (7., 8.), (10., 11.5)]]
    expected = 100 * np.array(roots) ** 4
    result = reference.modes(96)
    np.testing.assert_allclose(result['squared_frequencies_rad2_s2'], expected, rtol=3e-6, atol=0.)


def test_energy_instability_threshold_matches_independent_airy_determinant():
    _, k, m = reference.matrices(64)
    _, loaded, _ = reference.matrices(64, 500.)
    geometric = (k - loaded) / 500.
    value = eigsh(k, M=geometric, k=1, sigma=0., which='LM', tol=1e-12,
                  v0=np.linspace(1., 2., k.shape[0]))[0][0]
    assert abs(value / airy.critical() - 1) < 2e-6


@pytest.mark.parametrize('ratio', [.5, 1.5])
def test_loaded_modes_obey_physical_scaling_and_stability(ratio):
    g = ratio * airy.critical()
    original = reference.modes(48, g)
    # L -> 2L, EI -> 8EI and mu -> mu leaves gcr unchanged and omega² -> omega²/2.
    scaled = reference.modes(48, g, ei=800., length=2.)
    np.testing.assert_allclose(scaled['squared_frequencies_rad2_s2'],
                               .5 * np.array(original['squared_frequencies_rad2_s2']), rtol=2e-8, atol=0.)
    assert original['unstable_modes'] == (1 if ratio > 1 else 0)
    assert scaled['unstable_modes'] == original['unstable_modes']


def test_integrated_kinetic_energy_matches_a_known_cubic_field():
    nodes, _, mass = reference.matrices(17, mass_per_length=2., length=3.)
    # w=s², theta=2s satisfies the essential root conditions exactly.
    field = np.column_stack([nodes ** 2, 2 * nodes]).ravel()[2:]
    np.testing.assert_allclose(field @ mass @ field, 2 * 3 ** 5 / 5, rtol=2e-14)


@pytest.mark.parametrize('parameters', [dict(length=0.), dict(ei=-1.), dict(mass_per_length=np.nan)])
def test_invalid_beam_parameters_rejected(parameters):
    with pytest.raises(ValueError, match='parameters'):
        reference.matrices(4, **parameters)
