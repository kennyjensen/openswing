import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.structure import Section, solve_cantilever


@pytest.mark.parametrize("angle", [0.1, np.pi/2, np.pi])
def test_large_rotation_pure_bending_is_exact_circular_arc(angle):
    length, ei = 2., 100.
    sol = solve_cantilever(length, Section(EIcc=ei), tip_moment=[ei*angle/length, 0, 0])
    k = angle/length
    expected = np.column_stack([0*sol.s, np.sin(k*sol.s)/k, (1-np.cos(k*sol.s))/k])
    np.testing.assert_allclose(sol.position, expected, atol=2e-7)
    assert sol.orthogonality_error < 1e-6
    assert np.linalg.norm(sol.position[-1]-sol.position[0]) <= length


def test_small_deflection_tip_load_matches_euler_bernoulli():
    length, ei, f = 3., 2e6, 5.
    sol = solve_cantilever(length, Section(EIcc=ei), tip_force=[0, 0, f])
    assert sol.position[-1, 2] == pytest.approx(f*length**3/(3*ei), rel=1e-6)
    assert sol.moment[0, 0] == pytest.approx(f*length, rel=1e-7)


def test_shear_and_axial_compliance():
    sol = solve_cantilever(2, Section(GKn=100, EA=1000), tip_force=[0, 10, 2])
    np.testing.assert_allclose(sol.position[-1], [0, 2.02, .04], atol=1e-9)


def test_torsion():
    sol = solve_cantilever(3, Section(GJ=10), tip_moment=[0, 2, 0])
    expected = Rotation.from_rotvec([0, .6, 0]).as_matrix()
    np.testing.assert_allclose(sol.rotation[-1], expected, atol=1e-8)
    np.testing.assert_allclose(sol.position[-1], [0, 3, 0], atol=1e-10)


def test_uniform_load_small_deflection_and_force_balance():
    length, ei, w = 3., 2e6, 5.
    sol = solve_cantilever(length, Section(EIcc=ei), loads=lambda s, p, r: ([0, 0, w], [0, 0, 0]))
    assert sol.position[-1, 2] == pytest.approx(w*length**4/(8*ei), rel=1e-6)
    np.testing.assert_allclose(sol.force[0], [0, 0, w*length], atol=1e-9)
    assert sol.moment[0, 0] == pytest.approx(w*length**2/2, rel=1e-7)


def test_rigid_body_rotation_covariance():
    f, m = np.array([1., 0., 2.]), np.array([2., 1., 0.])
    sec = Section(EIcc=80, EInn=100, GJ=60, EA=500)
    a = solve_cantilever(2, sec, tip_force=f, tip_moment=m)
    rotation = Rotation.from_rotvec([.4, -.8, 1.2]).as_matrix()
    offset = np.array([5., 2., -3.])
    b = solve_cantilever(2, sec, tip_force=rotation@f, tip_moment=rotation@m, root_rotation=rotation, root_position=offset)
    np.testing.assert_allclose(b.position, a.position@rotation.T+offset, atol=2e-7)
    np.testing.assert_allclose(b.force, a.force@rotation.T, atol=2e-7)


def test_constitutive_energy_is_positive_and_reciprocal_with_axis_offsets():
    s = Section(EIcc=20, GJ=10, EInn=30, EIcn=3, EIcs=2, EIsn=1, EA=100, GKc=200, GKn=300, Cea=.1, Nea=.2, Cta=.3, Nta=.4).compliance()
    np.testing.assert_allclose(s, s.T, atol=1e-15)
    assert min(np.linalg.eigvalsh(s)) > 0


def test_rigid_limit_has_exactly_zero_compliance():
    np.testing.assert_array_equal(Section().compliance(), np.zeros((6, 6)))


def test_invalid_stiffness_rejected():
    with pytest.raises(ValueError, match="positive definite"):
        Section(EIcc=1, EInn=1, EIcn=2).compliance()
