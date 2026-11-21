"""Independent rigid-link solutions and spatial invariance of sprung hinges."""
import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation
from openswing.asw import AswError
from openswing.joints import hinge_laws
from openswing.network import solve_static
from test_network import beam, model, tip, balanced


def linked(curve="-100 -100\n100 100", axis="1 0 0", reverse=False, offset=False, extra=""):
    b1 = beam(start=2 if reverse else 0, end=0 if reverse else 2, stiffness="0 0 0 0 0 0")
    b2 = beam(2, start=3 if offset else 2, end=5 if offset else 4, z=1 if offset else 0, stiffness="0 0 0 0 0 0")
    return model(b1+b2, f"Ground\n1 {2 if reverse else 0} 0\nEnd\nJoint\n1 2 {0 if reverse else 2} 0 3\nEnd\nJangle\n1 {axis}\n{curve}\nEnd\n{extra}")


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("angle", [-75., 45., 150.])
def test_exact_rigid_links_under_tip_couple_and_reversed_beam(reverse, angle):
    sign = -1 if reverse else 1
    m = linked(curve=f"-100 {-100*sign}\n100 {100*sign}", reverse=reverse)
    r = solve_static(m, panels=4, loads=[dict(beam=2, t=2, moment=[angle, 0, 0])])
    theta = np.deg2rad(angle)
    np.testing.assert_allclose(tip(r, 2), [0, 2+2*np.cos(theta), 2*np.sin(theta)], atol=1e-9)
    h = r["hinges"][0]
    assert h["angle_deg"] == pytest.approx(angle)
    assert h["structural_moment"] == pytest.approx(sign*angle)
    assert h["moment_trace"] == ("right" if reverse else "left")
    assert h["extrapolated"] == (abs(angle) > 100)
    balanced(r)


def test_dead_tip_force_matches_independent_pendulum_spring_equation():
    # Moment = 2 F cos(theta). Spring stiffness 180/pi N m / rad.
    r = solve_static(linked(), panels=4, loads=[dict(beam=2, t=2, force=[0, 0, 15])])
    theta = brentq(lambda a: a-np.deg2rad(30*np.cos(a)), 0, np.pi/2)
    np.testing.assert_allclose(tip(r, 2), [0, 2+2*np.cos(theta), 2*np.sin(theta)], atol=1e-9)
    assert r["hinges"][0]["angle_deg"] == pytest.approx(np.rad2deg(theta))
    balanced(r)


def test_offset_joint_uses_structural_moment_including_pylon_lever_arm():
    r = solve_static(linked(offset=True), panels=4, loads=[dict(beam=2, t=2, force=[0, 0, 15])])
    theta = brentq(lambda a: a-np.deg2rad(15*(1+2*np.cos(a))), 0, np.pi/2)
    np.testing.assert_allclose(tip(r, 2), [0, 3+2*np.cos(theta), 1+2*np.sin(theta)], atol=1e-9)
    reaction = r["reactions"][-1]
    assert r["hinges"][0]["structural_moment"] == pytest.approx(reaction["moment"][0])
    assert abs(reaction["moment"][0]+reaction["other_moment"][0]) == pytest.approx(15.)
    balanced(r)


def test_cubic_law_slope_breaks_extrapolation_and_nonzero_unloaded_angle():
    curve = "-10 -30\n-5 -5\n-5 -5\n0 0\n5 5\n5 5\n10 30"
    m = linked(curve)
    law = hinge_laws(m.records)[1]
    # Natural cubic interior segment is the straight central branch; end
    # segments are linear. Check both one-sided slopes and exact extrapolation.
    assert law.spline.evaluate(5, side="left", derivative=1) == pytest.approx(1)
    assert law.spline.evaluate(5, side="right", derivative=1) == pytest.approx(5)
    assert np.rad2deg(law.angle(12)) == pytest.approx(40)
    r = solve_static(m, panels=4, loads=[dict(beam=2, t=2, moment=[12, 0, 0])])
    assert r["hinges"][0]["angle_deg"] == pytest.approx(40)
    balanced(r)
    # Independent natural-cubic value: nodal second derivatives (0, .18, 0).
    r = solve_static(linked("-5 -4\n0 1\n5 9"), panels=4,
                     loads=[dict(beam=2, t=2, moment=[2.5, 0, 0])])
    assert r["hinges"][0]["angle_deg"] == pytest.approx(4.71875)
    balanced(r)
    # An unloaded angle is continued without removing the spring's tangent.
    r = solve_static(linked("-100 -75\n100 125"), panels=4)
    assert r["hinges"][0]["angle_deg"] == pytest.approx(25)
    np.testing.assert_allclose(r["support_moment"], 0, atol=1e-10)
    balanced(r)


def test_hinge_axis_follows_finite_beam_one_rotation():
    # Combined bending/torsion and an oblique hinge axis exercise
    # noncommuting spatial rotations.
    m = linked(axis="2 1 3")
    for key in ("EIcc", "EInn", "GJ"):
        m.beams[0].distributions[key].values[:] = 100
        m.beams[0].distributions[key].__post_init__()
    r = solve_static(m, panels=8, loads=[dict(beam=2, t=2, moment=[40, 15, 20])])
    q1 = np.array([n["rotation"] for n in r["nodes"] if n["beam"] == 1][-1])
    q2 = np.array([n["rotation"] for n in r["nodes"] if n["beam"] == 2][0])
    axis = np.array([2, 1, 3])/np.sqrt(14)
    h = r["hinges"][0]
    np.testing.assert_allclose(h["axis"], q1@axis, atol=1e-11)
    assert h["structural_moment"] == pytest.approx(np.dot([40, 15, 20], q1@axis))
    expected = q1@Rotation.from_rotvec(np.deg2rad(h["angle_deg"])*axis).as_matrix()
    np.testing.assert_allclose(q2, expected, atol=1e-9)
    assert np.linalg.norm(np.array(h["axis"])-axis) > .1
    balanced(r)


def test_distributed_load_endpoint_trace_excludes_lumped_half_panel_couple():
    m = linked(extra="Weight\n2 2 0 4 0 10\nEnd\n")
    # Beam 1 has distributed gravity and an offset centroid. Its own weight
    # must not create an artificial hinge angle dependent on the end cell size.
    from openswing.asw import parse_asw
    source = m.dumps()
    source = source.replace("2 0 2 0 0 0 0 0 0 0\nEnd", "2 0 2 0 0 0 0 0 0 0\nt mg Ccg\n0 10 .4\n2 10 .4\nEnd", 1)
    m = parse_asw(source)
    assert m.beams[0].value("mg", 1) == 10
    theta = brentq(lambda a: a+np.deg2rad(20*np.cos(a)), -np.pi/2, 0)
    for panels in (4, 8):
        r = solve_static(m, panels=panels)
        assert r["hinges"][0]["angle_deg"] == pytest.approx(np.rad2deg(theta), abs=1e-9)
        balanced(r)


def test_interior_joint_reports_left_trace_including_outboard_beam_one_load():
    from openswing.asw import parse_asw
    m = parse_asw(linked().dumps().replace("1 2 2 0 3", "1 2 1 0 3"))
    r = solve_static(m, panels=4, loads=[dict(beam=1, t=2, moment=[5, 0, 0]),
                                       dict(beam=2, t=2, moment=[10, 0, 0])])
    assert r["hinges"][0]["structural_moment"] == pytest.approx(15)
    assert r["hinges"][0]["angle_deg"] == pytest.approx(15)
    balanced(r)


def test_hinge_equilibrium_is_covariant_under_global_rigid_rotation():
    from openswing.asw import Distribution
    rotation = Rotation.from_rotvec([.4, -.3, .7]).as_matrix()
    m = linked(axis="1 2 3", offset=True)
    load = dict(beam=2, t=2, force=[2, 1, 5], moment=[3, -2, 7])
    first = solve_static(m, panels=4, loads=[load], gravity=[0, 0, 0])
    for b in m.beams:
        ts = np.array(b.domain)
        points = b.position(ts)@rotation.T
        for k, name in enumerate(("x", "y", "z")):
            b.distributions[name] = Distribution(name, ts, points[:, k], 0)
    m.records["jangle"][0]["header"][1:] = rotation@m.records["jangle"][0]["header"][1:]
    rotated = solve_static(m, panels=4, loads=[dict(beam=2, t=2, force=rotation@load["force"],
                                                 moment=rotation@load["moment"])], gravity=[0, 0, 0])
    for one, two in zip(first["nodes"], rotated["nodes"]):
        np.testing.assert_allclose(two["position"], rotation@one["position"], atol=2e-9)
        np.testing.assert_allclose(two["rotation"], rotation@one["rotation"]@rotation.T, atol=2e-9)
    assert rotated["hinges"][0]["angle_deg"] == pytest.approx(first["hinges"][0]["angle_deg"])
    balanced(rotated)


def test_articulated_wing_couples_spring_angles_and_circulation_symmetrically():
    from pathlib import Path
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, solve_rigid
    m = parse_asw(Path("examples/articulated.asw").read_text())
    condition = FlightCondition(alpha=5, mach=0)
    rigid = solve_rigid(m, condition, panels=4)
    r = solve_static(m, condition, panels=4)
    right, left = r["hinges"]
    assert right["angle_deg"] == pytest.approx(-left["angle_deg"], abs=1e-8)
    assert 4 < right["angle_deg"] < 7
    assert .35 < r["max_displacement"] < .55
    assert rigid["CL"]-r["CL"] > .001
    for one, two in zip([n for n in r["nodes"] if n["beam"] == 2],
                        [n for n in r["nodes"] if n["beam"] == 3][::-1]):
        np.testing.assert_allclose(one["position"], np.array(two["position"])*[1, -1, 1], atol=1e-8)
    assert len([a for a in r["attachments"] if a["kind"] == "hinge"]) == 2
    balanced(r, atol=1e-6)


def test_rigid_limit_and_table_scaling():
    r = solve_static(linked("-1 0\n1 0"), panels=4, loads=[dict(beam=2, t=2, moment=[90, 0, 0])])
    np.testing.assert_allclose(tip(r, 2), [0, 4, 0], atol=1e-10)
    assert r["hinges"][0]["angle_deg"] == 0
    m = linked("* 10 2\n+ 1 3\n-1 -2\n1 2")
    law = hinge_laws(m.records)[1]
    assert np.rad2deg(law.angle(1)) == pytest.approx(3)
    assert np.rad2deg(law.angle(6)) == pytest.approx(5)


@pytest.mark.parametrize("curve,axis,match", [
    ("1 1\n-1 -1\n0 0", "1 0 0", "moments must increase"),
    ("-1 -1\n1 1", "0 0 0", "axis must be nonzero"),
    ("-1 -1\n0 0\n0 1\n1 2", "1 0 0", "equal angles"),
    ("-1 -1\n0 0\n0 0\n0 0\n1 1", "1 0 0", "two points"),
])
def test_invalid_hinge_laws_fail_during_import(curve, axis, match):
    with pytest.raises(AswError, match=match):
        linked(curve, axis)


def test_laws_bind_to_joint_row_and_require_exactly_one_block():
    from openswing.asw import parse_asw
    source = linked().dumps()
    with pytest.raises(AswError, match="requires a Jangle"):
        parse_asw(source.replace("1 2 2 0 3", "1 2 2 0 3\n1 2 1 1 3"))
    with pytest.raises(AswError, match="more than one"):
        parse_asw(source+"Jangle\n1 1 0 0\n-1 -1\n1 1\nEnd\n")
    with pytest.raises(AswError, match="type 3 Joint row"):
        parse_asw(source.replace("Jangle\n1", "Jangle\n2"))
