"""Independent checks of the gravity-loaded continuous Pazy reference."""
from pathlib import Path
import importlib.util
import numpy as np
import pytest
from scipy.sparse.linalg import splu
from scipy.spatial.transform import Rotation


def load(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reference = load('isae_st2_loaded_reference')
energy = load('isae_st2_modal_reference')


def test_upright_compression_matches_exact_axial_solution():
    frame = Rotation.from_rotvec([np.pi / 2, 0., 0.]).as_matrix()
    base = reference.equilibrium(root_frame=frame)
    s = np.linspace(0., reference.LENGTH, 31)
    states = base['sample'](s)
    expected = s - reference.MASS * 9.81 / reference.EA * (reference.LENGTH * s - s ** 2 / 2)
    np.testing.assert_allclose(states['positions'][:, 2], expected, rtol=0., atol=2e-13)
    np.testing.assert_allclose(states['positions'][:, :2], 0., rtol=0., atol=2e-13)
    np.testing.assert_allclose(states['moments'], 0., rtol=0., atol=2e-13)
    assert states['quaternion_norm_error'] < 1e-12


@pytest.mark.parametrize('density', [0., 1.23])
def test_section_inertia_matches_direct_kinetic_energy(density):
    rng = np.random.default_rng(831)
    for s in (0., .3, .535, .55):
        rotation = Rotation.from_rotvec(rng.normal(size=3)).as_matrix()
        velocity, omega = rng.normal(size=(2, 3))
        matrix = reference.section_inertia(s, rotation, density)
        inn = reference.INN + max(0., (s - .52) / .03) * (.0041 - reference.INN)
        local_omega = rotation.T @ omega
        real = reference.MASS * (velocity @ velocity) + np.sum(
            np.array([reference.ICC, reference.ICC + inn, inn]) * local_omega ** 2)
        midchord_velocity = velocity + np.cross(omega, .005 * rotation[:, 0])
        fluid = density * np.pi * .1 ** 2 / 4 * ((midchord_velocity @ rotation[:, 2]) ** 2
                    + .1 ** 2 / 32 * (omega @ rotation[:, 1]) ** 2)
        state = np.r_[velocity, omega]
        np.testing.assert_allclose(state @ matrix @ state, real + fluid, rtol=2e-14, atol=1e-15)
        np.testing.assert_allclose(matrix, matrix.T, rtol=0., atol=1e-17)
        assert np.min(np.linalg.eigvalsh(matrix)) > 0


def test_loaded_static_tangent_matches_nonlinear_gravity_perturbation():
    gravity = np.array([0., 0., -9.81])
    direction = np.array([.3, .4, -.7])
    step = 1e-3
    base = reference.equilibrium(gravity)
    plus = reference.equilibrium(gravity + step * direction)
    minus = reference.equilibrium(gravity - step * direction)
    errors = []
    for elements in (96, 192):
        assembled = reference.pencil(elements, gravity, base=base)
        nodes = assembled['nodes']
        rhs = np.zeros(12 * len(nodes))
        for e, length in enumerate(np.diff(nodes)):
            rhs[6 + 12 * e + 6:6 + 12 * e + 9] = length * reference.MASS * direction
        perturbation = (assembled['column_scale'] * splu(assembled['A']).solve(
            assembled['row_scale'] * rhs)).reshape(-1, 12)
        p, m = plus['sample'](nodes), minus['sample'](nodes)
        displacement = (p['positions'] - m['positions']) / (2 * step)
        rotation = Rotation.from_matrix(p['rotations'] @ np.transpose(m['rotations'], (0, 2, 1))).as_rotvec() / (2 * step)
        error = max(np.max(abs(perturbation[:, :3] - displacement)) / np.max(abs(displacement)),
                    np.max(abs(perturbation[:, 3:6] - rotation)) / np.max(abs(rotation)))
        errors.append(error)
    assert errors[1] < 1e-4, errors
    assert errors[1] < .3 * errors[0], errors


@pytest.mark.parametrize('density', [0., 1.23])
def test_unloaded_modes_match_independent_hermite_energy(density):
    mixed = reference.modes(192, (0., 0., 0.), count=7, density=density)
    hermite = energy.modes(192, 0., count=7, density=density)
    np.testing.assert_allclose(mixed['frequencies_Hz'], hermite['frequencies_Hz'], rtol=1e-3, atol=0.)


def test_loaded_modes_are_covariant_under_global_rotation():
    rotation = Rotation.from_rotvec([.3, -.4, .7]).as_matrix()
    original = reference.modes(24, count=7, density=1.23)
    transformed = reference.modes(24, rotation @ [0., 0., -9.81], count=7,
                                   density=1.23, root_frame=rotation)
    np.testing.assert_allclose(transformed['frequencies_Hz'], original['frequencies_Hz'], rtol=3e-9, atol=0.)
    np.testing.assert_allclose(np.array(transformed['base']['positions']),
                               np.array(original['base']['positions']) @ rotation.T, rtol=0., atol=2e-12)


@pytest.mark.parametrize('density', [-1., np.nan, np.inf])
def test_invalid_density_rejected(density):
    with pytest.raises(ValueError, match='density'):
        reference.pencil(4, density=density)
