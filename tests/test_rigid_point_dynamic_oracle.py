"""Independent energy and vector-wrench checks of the dynamic comparison oracle."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
SPEC = importlib.util.spec_from_file_location('rigid_dynamic_check', ROOT/'scripts/verify-isae-ffwt4-rigid-dynamic.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def data(seed):
    rng = np.random.default_rng(seed)
    basis = rng.normal(size=(3, 3))
    inertia = basis@basis.T+np.diag([.2, .3, .4])
    return rng, .1+rng.random(), inertia, rng.normal(size=3), rng.normal(size=3), rng.normal(size=3)


def vector_wrench(mass, inertia, spin, arm, frame, velocity, rate, acceleration, angular_acceleration):
    """Direct cross-product equations; no block-matrix or skew helper."""
    point_acceleration = (acceleration+np.cross(angular_acceleration, arm)
        +np.cross(rate, np.cross(rate, arm))
        +2*np.cross(frame, velocity+np.cross(rate, arm)))
    force = -mass*point_acceleration
    absolute_rate = frame+rate
    couple = (-inertia@(angular_acceleration+np.cross(frame, rate))
              -np.cross(absolute_rate, inertia@absolute_rate+spin))
    return np.r_[force, couple+np.cross(arm, force)]


@pytest.mark.parametrize('seed', range(8))
def test_spatial_inertia_preserves_point_kinetic_energy_and_positive_mass(seed):
    rng, mass, inertia, spin, arm, frame = data(seed)
    negative_mass, _ = CHECK.rigid_point_coefficients(mass, inertia, spin, arm, frame)
    np.testing.assert_allclose(negative_mass, negative_mass.T, rtol=0, atol=2e-14)
    assert np.linalg.eigvalsh(-negative_mass).min() > 0
    for _ in range(5):
        velocity, rate = rng.normal(size=(2, 3))
        point_velocity = velocity+np.cross(rate, arm)
        energy = .5*mass*(point_velocity@point_velocity)+.5*rate@inertia@rate
        z = np.r_[velocity, rate]
        assert abs(-.5*z@negative_mass@z-energy)/(1+abs(energy)) < 2e-14


@pytest.mark.parametrize('seed', range(8))
@pytest.mark.parametrize('rotating', [False, True])
def test_matrix_coefficients_match_complex_step_of_full_vector_wrench(seed, rotating):
    _, mass, inertia, spin, arm, frame = data(seed)
    if not rotating:
        frame = np.zeros(3)
    negative_mass, damping = CHECK.rigid_point_coefficients(mass, inertia, spin, arm, frame)
    zero, h = np.zeros(3), 1e-30
    for column in range(6):
        delta = np.zeros(6, dtype=complex); delta[column] = 1j*h
        rate_column = vector_wrench(mass, inertia, spin, arm, frame,
            delta[:3], delta[3:], zero, zero).imag/h
        acceleration_column = vector_wrench(mass, inertia, spin, arm, frame,
            zero, zero, delta[:3], delta[3:]).imag/h
        assert np.max(abs(rate_column-damping[:, column])/(1+abs(rate_column))) < 2e-14
        assert np.max(abs(acceleration_column-negative_mass[:, column])/(1+abs(acceleration_column))) < 2e-14
