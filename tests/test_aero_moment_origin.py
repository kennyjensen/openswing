"""Origin coefficients and reference-point constraints are distinct outputs."""
from copy import deepcopy
import numpy as np
import pytest

from openswing.aero import FlightCondition, solve_rigid
from openswing.rom_outputs import output_catalog
from openswing.output_derivatives import aerodynamic_moments
from test_profile_drag_moments import fixture_model, zero_circulation_evaluation, exact_wrench, flight


@pytest.mark.parametrize('kind', ['dihedral', 'cantilever'])
def test_origin_profile_moment_matches_exact_continuous_first_moment(kind):
    model = fixture_model(kind)
    _, result = zero_circulation_evaluation(model, 4)
    force, expected = exact_wrench(kind, reference=np.zeros(3))
    np.testing.assert_allclose(result['moment_origin'], expected, rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(result['distributed_aero_moment_origin'], expected, rtol=2e-14, atol=2e-14)
    qsc = .5 * flight().density * flight().speed**2 * np.prod(model.reference[0, :2])
    assert result['Cm_origin'] == pytest.approx(expected[1] / qsc, rel=2e-14, abs=2e-14)


def test_lifting_wrench_origin_is_invariant_to_moment_reference():
    model = fixture_model('dihedral')
    condition = FlightCondition(speed=13., alpha=6., beta=2., density=1.1, mach=0.)
    original = solve_rigid(model, condition, panels=12)
    moved = deepcopy(model)
    shift = np.array([1.7, -.6, .9])
    moved.reference[1] += shift
    result = solve_rigid(moved, condition, panels=12)
    for key in ('force', 'moment_origin', 'distributed_aero_moment_origin', 'Cm_origin', 'CL', 'CD', 'CDi'):
        np.testing.assert_allclose(result[key], original[key], rtol=2e-14, atol=3e-14)
    np.testing.assert_array_equal([s['circulation'] for s in result['strips']],
                                  [s['circulation'] for s in original['strips']])
    np.testing.assert_allclose(result['moment'], np.array(original['moment']) - np.cross(shift, result['force']),
                               rtol=2e-14, atol=3e-14)
    assert abs(result['Cm'] - original['Cm']) > .1
    catalog = output_catalog(result)
    assert {'moment_origin', 'distributed_aero_moment_origin', 'Cm_origin'} <= set(catalog['global_available'])
    assert result['moment_definitions']['reference'] == moved.reference[1].tolist()


def test_moving_load_origin_derivative_includes_force_and_arm_changes():
    # F(s)=(2+s,0,5+3s), r(s)=(1+2s,0,4-s), intrinsic My=7s.
    # dMy(origin)/ds at zero = 7 + (-2+4) - (10+3) = -4.
    # A reference (.3,0,-.2) adds .2*dFx+.3*dFz = 1.1.
    step = 1e-4
    snapshots = []
    for s in (step, -step, 0., 0.):
        snapshots.append(dict(moment=[0., 0., 0.], strips=[dict(
            position=[1+2*s, 0., 4-s], force=[2+s, 0., 5+3*s], moment=[0., 7*s, 0.],
            apparent_force=[0., 0., 0.], apparent_moment=[0., 0., 0.])],
            body_shoulders=[], engines=[], point_forces=[]))
    result = aerodynamic_moments(snapshots, [[], [], [], []], np.array([.3, 0., -.2]), step)
    np.testing.assert_allclose(result['moment'], [0., -2.9, 0.], rtol=0, atol=2e-11)
    for key in ('moment_origin', 'distributed_aero_moment_origin'):
        np.testing.assert_allclose(result[key], [0., -4., 0.], rtol=0, atol=2e-11)
