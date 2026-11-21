import numpy as np
import pytest
from pathlib import Path
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.geometry import mesh_beam, surface_frame
from openswing.inertia import (Motion, InertiaModel, inertial_wrench, parallel_axis,
                               point_tensor, mass_summary, surface_apparent_loads)
from openswing.network import solve_static
from openswing.aero import FlightCondition, solve_rigid


PREFIX = "Name\nInertia verification\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\n"


def rod(extra="", weight="", flexible=False):
    stiffness = "t EIcc EInn GJ EA\n0 2000 2400 1800 10000\n2 2000 2400 1800 10000\n" if flexible else ""
    return parse_asw(PREFIX+weight+"Beam 1\nRod\nt y\n0 0\n2 2\n"+stiffness+extra+"End\n")


def test_absolute_acceleration_reference_change_preserves_field():
    motion = Motion([.3, -.4, .2], [.1, .7, -.2], [.2, .1, -.3])
    old, new = np.array([1., 2., -1.]), np.array([-2., .5, 1.])
    points = np.array([[.2, .3, .1], [3., -1., 2.], [0, 0, 0]])
    shifted = Motion(motion.rates, motion.at(new, old), motion.angular_acceleration)
    np.testing.assert_allclose(motion.at(points, old), shifted.at(points, new), atol=1e-14)


def test_inclined_fuselage_inertia_uses_its_documented_frame_sequence():
    phi, psi, theta = np.deg2rad([20, -70, 15])
    expected = (Rotation.from_rotvec([0, 0, psi])*Rotation.from_rotvec([phi, 0, 0])*Rotation.from_rotvec([0, theta, 0])).as_matrix()
    endpoint = 2*expected[:, 1]
    text = PREFIX+f"Beam 1\nInclined body\nt x y z twist mg mgcc mgnn\n0 0 0 0 15 9.80665 1.96133 2.941995\n2 {endpoint[0]} {endpoint[1]} {endpoint[2]} 15 9.80665 1.96133 2.941995\nEnd\n"
    model = parse_asw(text)
    np.testing.assert_allclose(surface_frame(model.beams[0], 1), expected, atol=1e-14)
    meshes = [mesh_beam(model.beams[0], 4)]
    mass = InertiaModel(model, meshes)
    props = mass.summary(mass.elements(meshes))
    local = np.diag([2/3+.4, 1., 2/3+.6])
    np.testing.assert_allclose(props["inertia_cg"], expected@local@expected.T, atol=1e-12)


def test_asw_products_have_negative_tensor_sign_and_weight_units():
    row = np.zeros(17); row[11:] = np.array([4, 5, 6, 1, -.3, .7])*9.80665
    np.testing.assert_allclose(point_tensor(row, 9.80665), [[4, -1, .3], [-1, 5, -.7], [.3, -.7, 6]], atol=1e-14)
    row[11] = -1
    with pytest.raises(ValueError, match="positive semidefinite"):
        point_tensor(row, 9.80665)


def test_straight_distributed_rod_and_additional_mass_exact_inertia_on_coarse_grid():
    m = rod("t mg Ccg Ncg mgcc mgnn Dmg DCcg DNcg Dmgcc Dmgnn\n0 19.6133 .2 .1 .980665 1.96133 9.80665 -.3 -.2 .4903325 .392266\n2 19.6133 .2 .1 .980665 1.96133 9.80665 -.3 -.2 .4903325 .392266\n")
    meshes = [mesh_beam(m.beams[0], 4)]
    mass = InertiaModel(m, meshes)
    props = mass.summary(mass.elements(meshes))
    assert props["mass"] == pytest.approx(6)
    centers = np.array([[.2, 1, .1], [-.3, 1, -.2]])
    masses = np.array([4., 2.])
    expected_cg = np.average(centers, axis=0, weights=masses)
    own = np.array([np.diag([4/3+.2, .6, 4/3+.4]), np.diag([2/3+.1, .18, 2/3+.08])])
    expected = (own+parallel_axis(masses, centers)).sum(axis=0)
    np.testing.assert_allclose(props["cg"], expected_cg, atol=1e-13)
    np.testing.assert_allclose(props["inertia_reference"], expected, atol=1e-12)
    np.testing.assert_allclose(props["inertia_cg"], expected-parallel_axis(6, expected_cg), atol=1e-12)


def test_mass_tensor_energy_and_rotation_translation_covariance():
    points = np.array([[.2, .7, .5], [-.6, .3, 1.], [.5, -.7, .4]])
    mass = np.array([2., 1., 3.])
    inertia = np.array([np.diag(v) for v in [[.3, .4, .5], [.2, .3, .4], [.1, .2, .25]]])
    spins = np.array([[.3, .2, .1], [.1, .2, .3], [-.2, .4, .1]])
    reference = np.array([.4, -.2, .5])
    original = mass_summary(mass, points, inertia, spins, reference)
    v, omega = np.array([.3, -.4, .2]), np.array([.6, .1, -.2])
    vel = v+np.cross(omega, points-reference)
    expected_energy = .5*np.sum(mass*np.sum(vel**2, axis=1))+.5*np.einsum("i,nij,j->", omega, inertia, omega)
    generalized = np.r_[v, omega]
    matrix = np.array(original["spatial_matrix"])
    assert .5*generalized@matrix@generalized == pytest.approx(expected_energy, abs=1e-13)
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-14)
    q = Rotation.from_rotvec([.3, -.7, 1.1]).as_matrix(); d = np.array([3., -2., 5.])
    transformed = mass_summary(mass, points@q.T+d, q@inertia@q.T, spins@q.T, q@reference+d)
    np.testing.assert_allclose(transformed["cg"], q@original["cg"]+d, atol=1e-14)
    np.testing.assert_allclose(transformed["inertia_reference"], q@original["inertia_reference"]@q.T, atol=1e-13)
    np.testing.assert_allclose(transformed["spin_angular_momentum"], q@original["spin_angular_momentum"], atol=1e-14)


def test_cloud_of_masses_and_equivalent_full_tensor_produce_same_deformed_solution():
    points = np.array([[.2, 1, .3], [-.4, 1.2, .1], [.1, .8, -.2], [.3, 1.4, .4]])
    masses = np.array([1., 2., .7, 1.5])
    cg = np.average(points, axis=0, weights=masses)
    tensor = parallel_axis(masses, points-cg).sum(axis=0)
    # Every pylon attaches at the same beam node, as required by the 5.99
    # equivalence statement. Their offsets/rotations must remain identical.
    rows = [[1, 1, *p, mass*9.80665] for mass, p in zip(masses, points)]
    lumped = [[1, 1, *cg, sum(masses)*9.80665, 0, 0, 0, 0, 0,
               *(np.r_[np.diag(tensor), -tensor[0, 1], -tensor[0, 2], -tensor[1, 2]]*9.80665)]]
    def weight(rows):
        return "Weight\n"+"\n".join(" ".join(map(str, row)) for row in rows)+"\nEnd\n"
    motion = Motion([.4, -.3, .2], [.3, -.2, .5], [.1, .2, .15])
    solutions = [solve_static(rod(weight=weight(rows), flexible=True), panels=8, motion=motion) for rows in (rows, lumped)]
    a, b = solutions
    assert a["max_displacement"] > .002
    np.testing.assert_allclose([n["position"] for n in a["nodes"]], [n["position"] for n in b["nodes"]], atol=2e-9)
    for key in ("support_force", "support_moment"):
        np.testing.assert_allclose(a[key], b[key], atol=2e-8)
    for key in ("inertia_reference", "inertia_cg", "cg"):
        np.testing.assert_allclose(a["mass_properties"][key], b["mass_properties"][key], atol=1e-8)


def test_angular_acceleration_of_uniform_rod_has_exact_root_torque():
    m = rod("t mg\n0 19.6133\n2 19.6133\n")
    r = solve_static(m, panels=4, gravity=[0, 0, 0], motion=Motion(angular_acceleration=[3, 0, 0]))
    # For density 2 kg/m, length 2 m: I_root=mu L³/3; torque=I_root alpha.
    np.testing.assert_allclose(r["support_force"], [0, 0, 12], atol=1e-9)
    np.testing.assert_allclose(r["support_moment"], [16, 0, 0], atol=1e-9)
    np.testing.assert_allclose(r["moment_balance"], 0, atol=1e-9)


def test_rotating_rod_centrifugal_force_and_point_gyroscopic_torque():
    m = rod("t mg\n0 19.6133\n2 19.6133\n", "Weight\n1 0 0 0 0 0 0 0 9.80665 19.6133 29.41995\nEnd\n")
    r = solve_static(m, panels=4, gravity=[0, 0, 0], motion=Motion(rates=[0, 0, 2]))
    np.testing.assert_allclose(r["support_force"], [0, -16, 0], atol=1e-9)
    np.testing.assert_allclose(r["support_moment"], np.cross([0, 0, 2], [1, 2, 3]), atol=1e-9)


def test_freefall_cancels_gravity_on_structural_masses():
    m = rod("t mg Ccg\n0 19.6133 .2\n2 19.6133 .2\n", flexible=True)
    r = solve_static(m, panels=4, motion=Motion(acceleration=[0, 0, -9.80665]))
    np.testing.assert_allclose(r["support_force"], 0, atol=1e-12)
    assert r["max_displacement"] < 1e-12


def test_normal_acceleration_gives_flat_plate_added_mass_and_correct_arm():
    source = Path("examples/rectangular.asw").read_text().replace(".008", "0")
    m = parse_asw(source)
    result = solve_rigid(m, FlightCondition(alpha=0, mach=0, acceleration=[0, 0, 2]), panels=12)
    added_mass = 1.225*np.pi/4*12
    np.testing.assert_allclose(result["force"], [0, 0, -2*added_mass], atol=1e-10)
    # Axis is at quarter chord; acceleration load acts at midchord.
    np.testing.assert_allclose(result["moment"], [0, .5*added_mass, 0], atol=1e-10)
    np.testing.assert_allclose(result["apparent_mass"]["mass_tensor"], np.diag([0, 0, added_mass]), atol=1e-12)
    assert result["CD"] == pytest.approx(result["CDi_near"]+result["CDp"]+result["CDam"], abs=1e-12)


def test_apparent_spatial_tensor_matches_general_acceleration_load_and_is_positive():
    source = Path("examples/rectangular.asw").read_text().replace(".008", "0")
    m = parse_asw(source)
    acceleration, alpha = [.3, -.2, .7], [.4, -.3, .2]
    result = solve_rigid(m, FlightCondition(alpha=0, mach=0, acceleration=acceleration, angular_acceleration=alpha), panels=12)
    matrix = np.array(result["apparent_mass"]["spatial_matrix"])
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-13)
    assert np.min(np.linalg.eigvalsh(matrix)) > -1e-12
    np.testing.assert_allclose(np.r_[result["force"], result["moment"]], -matrix@np.r_[acceleration, alpha], atol=1e-11)


def test_two_dimensional_pitch_rate_and_acceleration_apparent_loads():
    chord, rho, rate, speed, angular_acceleration = 2., 1.2, .3, 10., .4
    mass = rho*np.pi*(chord/2)**2
    force, moment = surface_apparent_loads(np.zeros((1, 3)), np.eye(3)[None], np.array([chord]), np.array([.5]),
                                          np.ones(1), rho, np.array([[speed, 0, 0]]),
                                          Motion(rates=[0, rate, 0], angular_acceleration=[0, angular_acceleration, 0]), np.zeros(3))
    np.testing.assert_allclose(force[0], [0, 0, mass*speed*rate], atol=1e-12)
    # Thin-airfoil noncirculatory pitch-rate torque and plate added inertia.
    expected = -np.pi*rho*chord**3/16*speed*rate-np.pi*rho*chord**4/128*angular_acceleration
    np.testing.assert_allclose(moment[0], [0, expected, 0], atol=1e-12)


def test_point_inertial_wrench_is_objective_including_spin():
    mass, position = np.array([2.]), np.array([[.4, .3, -.2]])
    inertia, spin = np.array([[[3., .2, .1], [.2, 4., -.3], [.1, -.3, 5.]]]), np.array([[.2, .4, -.3]])
    motion = Motion([.3, -.4, .1], [.7, .2, -.3], [.1, .2, .3])
    gravity, ref = np.array([0, 0, -9.81]), np.array([.4, -.2, .5])
    f, t = inertial_wrench(mass, position, inertia, spin, motion, gravity, ref)
    q = Rotation.from_rotvec([.4, -.3, .7]).as_matrix(); d = np.array([3, 2, -1])
    moved = Motion(q@motion.rates, q@motion.acceleration, q@motion.angular_acceleration)
    fq, tq = inertial_wrench(mass, position@q.T+d, q@inertia@q.T, spin@q.T, moved, q@gravity, q@ref+d)
    np.testing.assert_allclose(fq, f@q.T, atol=1e-13)
    np.testing.assert_allclose(tq, t@q.T, atol=1e-13)
