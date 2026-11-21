"""Independent checks of the three-coordinate FFWT2 mechanics reference."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest


PATH = Path(__file__).resolve().parents[1]/'scripts/verify-isae-ffwt2-mechanics.py'
SPEC = importlib.util.spec_from_file_location('ffwt2_mechanics', PATH)
REF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REF)


def earth_positions(q):
    frame = REF.rotation(REF.EX, q[0])
    cloud = REF.point_cloud(q[1:])
    return np.array([m for m, _, _ in cloud]), np.array([frame@r for _, r, _ in cloud])


def test_uniform_rod_integrals_equal_the_closed_form_mass_matrix():
    report = REF.check_oracle()
    assert report['total_mass'] == pytest.approx(.8729872, abs=1e-15)
    assert report['analytical_flat_matrix_verified']


@pytest.mark.parametrize('q', [[.2, .3, -.7], [-2., -1.2, .8], [4.8, 2.4, -2.]])
def test_mass_and_bias_match_independently_differentiated_particle_motion(q):
    q = np.array(q)
    velocity = np.array([3.1, .4, -2.])
    acceleration = np.array([.8, -1.3, 2.4])
    step = 1e-4
    mass, center = earth_positions(q)
    _, plus = earth_positions(q+step*velocity+.5*step**2*acceleration)
    _, minus = earth_positions(q-step*velocity+.5*step**2*acceleration)
    particle_acceleration = (plus-2*center+minus)/step**2
    columns = []
    for direction in np.eye(3):
        _, p = earth_positions(q+1e-5*direction)
        _, m = earth_positions(q-1e-5*direction)
        columns.append((p-m)/2e-5)
    jacobian = np.stack(columns, axis=-1)
    expected = np.einsum('n,nij,ni->j', mass, jacobian, particle_acceleration)
    matrix, bias = REF.mass_and_bias(q[1:], velocity)
    np.testing.assert_allclose(matrix@acceleration+bias, expected, atol=3e-9, rtol=2e-7)


@pytest.mark.parametrize('angles', [[.3, -.7], [-1.2, .8], [2.4, -2.]])
def test_coriolis_power_matches_rate_of_kinetic_energy(angles):
    angles = np.array(angles); velocity = np.array([3.1, .4, -2.])
    _, bias = REF.mass_and_bias(angles, velocity)
    step = 1e-5
    plus, _ = REF.mass_and_bias(angles+step*velocity[1:], velocity)
    minus, _ = REF.mass_and_bias(angles-step*velocity[1:], velocity)
    matrix_rate = (plus-minus)/(2*step)
    assert velocity@bias == pytest.approx(.5*velocity@matrix_rate@velocity, abs=3e-11, rel=1e-8)
