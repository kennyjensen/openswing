"""Finite force-point velocities when a panel approaches its own filament."""
from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad_vec

from openswing.aero import FlightCondition, evaluate_aerodynamics, horseshoe_velocity
from openswing.asw import parse_asw
from openswing.geometry import mesh_beam
from openswing.ground import GroundPlane


@pytest.mark.parametrize('ground_flag', [0, 1, -1])
def test_excluded_bound_retains_wakes_and_complete_ground_image(ground_flag):
    # Non-axis-aligned geometry and a PG transform expose cancellation between
    # broadcast and vector evaluations of the same nearly singular filament.
    a = np.array([.1, -1., .2]); b = np.array([.8, 1., .3])
    point = .4*a+.6*b+np.array([1e-10, 0., 0.])
    e = np.array([1., .1, -.05]); e /= np.linalg.norm(e)
    pg = np.eye(3)+(1/np.sqrt(1-.63**2)-1)*np.outer(e, e)
    ground = GroundPlane(ground_flag, [0, 0, 2])
    target = point@pg.T

    def integral(start, end, direction, include_bound):
        start, end, direction = start@pg.T, end@pg.T, direction@pg.T
        direction /= np.linalg.norm(direction)
        def leg(origin):
            return quad_vec(lambda t: np.cross(direction, target-origin-t*direction)
                            /np.linalg.norm(target-origin-t*direction)**3,
                            0, np.inf, epsabs=1e-12)[0]
        bound = 0.
        if include_bound:
            d = end-start
            bound = quad_vec(lambda t: np.cross(d, target-start-t*d)
                             /np.linalg.norm(target-start-t*d)**3,
                             0, 1, epsabs=1e-12)[0]
        return (bound+leg(end)-leg(start))@pg/(4*np.pi)

    expected = integral(a, b, e, False)
    if ground_flag:
        expected -= ground_flag*integral(ground.reflect_points(a), ground.reflect_points(b),
                                          ground.reflect_vectors(e), True)
    actual = horseshoe_velocity(point, a, b, e, pg, ground=ground, exclude_bound=True)
    np.testing.assert_allclose(actual, expected, atol=2e-13)


@pytest.mark.parametrize('beta', [-.0006, 0., .0006])
def test_aerodynamic_loads_are_continuous_near_own_bound_segment(beta):
    model = parse_asw(Path('examples/rectangular.asw').read_text())
    condition = FlightCondition(alpha=3., beta=beta, mach=.37)
    meshes = [mesh_beam(beam, 8) for beam in model.beams]
    base = evaluate_aerodynamics(model, condition, meshes)
    # Move the theta force points a vanishing distance off their own bound
    # filaments. The omitted self field must not leave a numerical remainder.
    for mesh in meshes:
        mesh.rm += np.array([2e-10, 0., -1e-10])
    moved = evaluate_aerodynamics(model, condition, meshes)
    for key in ('CL', 'CD', 'Cm'):
        assert moved[key] == pytest.approx(base[key], abs=2e-9)
