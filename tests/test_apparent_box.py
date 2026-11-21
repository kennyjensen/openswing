"""Independent acceleration/box oracles; no equilibrium or aerodynamic solve."""
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.apparent_box import endpoint_acceleration_wrench, rigid_acceleration_response


def rotation(vector):
    return Rotation.from_rotvec(vector).as_matrix()


def endpoint_oracle(frame, chord, xax, rho, a, alpha):
    """Direct physical projections, without the production helper/matrix."""
    c, s, n = frame.T
    d = (.5-xax)*chord*c
    mu = rho*np.pi*chord**2/4
    force = -mu*np.dot(n, a+np.cross(alpha, d))*n
    moment = np.cross(d, force)-rho*np.pi*chord**4/128*np.dot(s, alpha)*s
    return force, moment


def box_oracle(r0, r1, frame0, frame1, c0, c1, x0, x1, h, rho, ref, a, alpha):
    endpoint = [endpoint_oracle(frame, chord, xax, rho, a+np.cross(alpha, r-ref), alpha)
                for r, frame, chord, xax in [(r0, frame0, c0, x0), (r1, frame1, c1, x1)]]
    f = h/2*(endpoint[0][0]+endpoint[1][0])
    m = h/2*(endpoint[0][1]+endpoint[1][1])+np.cross((r0+r1)/2-ref, f)
    return np.r_[f, m]


def varying_case():
    return (np.array([.2, -.8, .4]), np.array([.6, 1.3, -.2]),
            rotation([.2, -.3, .1]), rotation([-.1, .4, .2]),
            .37, .81, -.2, .73, 2.7, 1.17, np.array([-.4, .3, .6]))


def test_endpoint_reaction_has_physical_midchord_arm_and_pitch_inertia():
    frame = rotation([.3, -.1, .7]); a = np.array([.7, -.2, .4]); alpha = np.array([-.3, .9, .2])
    actual = endpoint_acceleration_wrench(frame, .63, -.17, 1.2, a, alpha)
    expected = endpoint_oracle(frame, .63, -.17, 1.2, a, alpha)
    np.testing.assert_allclose(actual, expected, rtol=2e-15, atol=2e-16)


def test_endpoint_broadcasts_density_sections_and_acceleration_columns():
    frames = rotation([[.2, .1, -.3], [-.1, .4, .2]])
    chords = np.array([.2, .7]); xax = np.array([.1, .6]); rho = np.array([1.2, .8])
    values = np.arange(18, dtype=float).reshape(3, 6)/11-.4
    f, m = endpoint_acceleration_wrench(frames[:, None], chords[:, None], xax[:, None],
                                       rho[:, None], values[None, :, :3], values[None, :, 3:])
    assert f.shape == m.shape == (2, 3, 3)
    for i in range(2):
        for j in range(3):
            expected = endpoint_oracle(frames[i], chords[i], xax[i], rho[i], values[j, :3], values[j, 3:])
            np.testing.assert_allclose([f[i, j], m[i, j]], expected, rtol=3e-15, atol=2e-16)


def test_constant_strip_reduces_to_independent_midpoint_energy_matrix():
    frame = rotation([.35, -.12, .22]); c, s, n = frame.T
    r0 = np.array([.4, -.9, .2]); r1 = r0+2.3*s
    ref = np.array([-.2, .7, .5]); chord, xax, h, rho = .6, .13, 2.3, 1.19
    actual = rigid_acceleration_response(r0, r1, frame, frame, chord, chord, xax, xax, h, rho, ref)
    midchord = (r0+r1)/2+(.5-xax)*chord*c-ref
    # The scalar normal midchord speed is [n, r_midchord cross n] dot [v,w].
    covector = np.r_[n, np.cross(midchord, n)]
    pitch = np.r_[np.zeros(3), s]
    expected = rho*np.pi*chord**2*h/4*np.outer(covector, covector)
    expected += rho*np.pi*chord**4*h/128*np.outer(pitch, pitch)
    np.testing.assert_allclose(actual, expected, atol=3e-16, rtol=2e-15)
    np.testing.assert_allclose(actual, actual.T, atol=2e-16)
    v = np.array([.2, -.4, .7, .3, .1, -.2])
    energy = rho*np.pi*chord**2*h/8*(covector@v)**2+rho*np.pi*chord**4*h/256*(pitch@v)**2
    assert .5*v@actual@v == pytest.approx(energy, rel=2e-15, abs=1e-16)


def test_centered_uniform_strip_has_no_unrequested_span_segment_inertia():
    r0, r1 = np.array([0., -2., 0.]), np.array([0., 2., 0.])
    response = rigid_acceleration_response(r0, r1, np.eye(3), np.eye(3), .5, .5, .5, .5, 4., 1.2, np.zeros(3))
    # About the beam midpoint, box-averaged alpha_x forces cancel exactly.
    assert response[3, 3] == 0.
    assert response[2, 2] == pytest.approx(1.2*np.pi*.5**2*4/4)
    assert response[4, 4] == pytest.approx(1.2*np.pi*.5**4*4/128)


@pytest.mark.parametrize('column', range(6))
def test_varying_endpoints_match_completed_endpoint_loads_for_every_acceleration(column):
    args = varying_case(); response = rigid_acceleration_response(*args)
    acceleration = np.eye(6)[column]
    expected = box_oracle(*args, acceleration[:3], acceleration[3:])
    np.testing.assert_allclose(-response@acceleration, expected, rtol=3e-15, atol=3e-16)


def test_varying_properties_preserve_nonsymmetry_instead_of_projecting_to_mass_tensor():
    r0, r1 = np.array([0., -1., 0.]), np.array([0., 1., 0.])
    rho, h, c0, c1 = 1.2, 2., .2, .6
    result = rigid_acceleration_response(r0, r1, np.eye(3), np.eye(3), c0, c1, .5, .5, h, rho, np.zeros(3))
    expected_coupling = h/2*(rho*np.pi*c1**2/4-rho*np.pi*c0**2/4)
    assert result[2, 3] == pytest.approx(expected_coupling, rel=2e-15)
    assert result[3, 2] == 0.
    assert abs(result[2, 3]-result[3, 2]) > .1
    # The reference is the box midpoint: endpoint r cross F averaging would
    # introduce an alpha_x inertia that this source operator does not contain.
    assert result[3, 3] == 0.


def test_response_is_covariant_under_rigid_rotation_and_translation():
    args = list(varying_case()); response = rigid_acceleration_response(*args)
    q = rotation([.4, -.7, .1]); shift = np.array([3., -2., .6])
    moved = args.copy()
    for i in (0, 1, 10):
        moved[i] = q@args[i]+shift
    for i in (2, 3):
        moved[i] = q@args[i]
    block = np.zeros((6, 6)); block[:3, :3] = block[3:, 3:] = q
    actual = rigid_acceleration_response(*moved)
    np.testing.assert_allclose(actual, block@response@block.T, rtol=4e-15, atol=4e-16)


def test_reference_shift_preserves_physical_wrench_and_acceleration_field():
    args = list(varying_case()); old = args[-1].copy(); new = old+np.array([.7, -.4, .8])
    a, alpha = np.array([.3, -.2, .7]), np.array([-.1, .6, .4])
    original = -rigid_acceleration_response(*args)@np.r_[a, alpha]
    args[-1] = new
    shifted_a = a+np.cross(alpha, new-old)
    shifted = -rigid_acceleration_response(*args)@np.r_[shifted_a, alpha]
    expected = np.r_[original[:3], original[3:]+np.cross(old-new, original[:3])]
    np.testing.assert_allclose(shifted, expected, atol=3e-16, rtol=4e-15)


def test_response_broadcasts_two_dimensional_batches_and_declared_length():
    args = varying_case()
    r0 = np.stack([args[0], args[0]+[.2, .3, -.1]])[:, None, :]
    chord1 = np.array([[.3, .5, .8]])
    lengths = np.array([[.9], [3.2]])
    density = np.array([[.9, 1.1, 1.3]])
    actual = rigid_acceleration_response(r0, args[1], args[2], args[3], args[4], chord1,
                                         args[6], args[7], lengths, density, args[-1])
    assert actual.shape == (2, 3, 6, 6)
    for i in range(2):
        for j in range(3):
            local = (r0[i, 0], args[1], args[2], args[3], args[4], chord1[0, j],
                     args[6], args[7], lengths[i, 0], density[0, j], args[-1])
            expected = -np.column_stack([box_oracle(*local, e[:3], e[3:]) for e in np.eye(6)])
            np.testing.assert_allclose(actual[i, j], expected, rtol=4e-15, atol=3e-16)


@pytest.mark.parametrize('index', [4, 5, 8, 9])
def test_zero_chord_length_or_density_is_retained_without_division(index):
    args = list(varying_case())
    if index in (4, 5):
        args[4] = args[5] = 0.
    else:
        args[index] = 0.
    np.testing.assert_array_equal(rigid_acceleration_response(*args), np.zeros((6, 6)))


@pytest.mark.parametrize('index', [4, 5, 8, 9])
def test_negative_physical_measures_are_rejected(index):
    args = list(varying_case()); args[index] = -.1
    with pytest.raises(ValueError, match='nonnegative'):
        rigid_acceleration_response(*args)


@pytest.mark.parametrize('index', [0, 2, 6, 10])
def test_nonfinite_inputs_are_rejected(index):
    args = list(varying_case()); args[index] = np.full_like(args[index], np.nan, dtype=float)
    with pytest.raises(ValueError, match='finite'):
        rigid_acceleration_response(*args)


def test_endpoint_rejects_invalid_vector_shape():
    with pytest.raises(ValueError, match='trailing shape'):
        endpoint_acceleration_wrench(np.eye(3), 1., .5, 1., [0., 0.], np.zeros(3))
