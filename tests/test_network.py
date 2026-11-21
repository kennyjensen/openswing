from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from openswing.network import solve_static
from openswing.structure import Section, solve_cantilever


def beam(index=1, start=0, end=2, z=0, stiffness="100 100 100 1000 1000 1000"):
    return f"""Beam {index}
Beam {index}
t x y z EIcc EInn GJ EA GKc GKn
0 0 {start} {z} {stiffness}
2 0 {end} {z} {stiffness}
End
"""


def model(beams=None, attachments="Ground\n1 0 0\nEnd\n"):
    return parse_asw("Name\nNetwork verification\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\n" + attachments + (beams or beam()))


def tip(result, beam=1):
    return np.array([n["position"] for n in result["nodes"] if n["beam"] == beam][-1])


def balanced(result, atol=1e-7):
    np.testing.assert_allclose(result["force_balance"], 0, atol=atol)
    np.testing.assert_allclose(result["moment_balance"], 0, atol=atol)
    assert result["residual"] < 1e-8


@pytest.mark.parametrize("angle", [np.pi/2, np.pi])
def test_large_rotation_bending_converges_to_exact_arc(angle):
    m = model(beam(stiffness="100 0 0 0 0 0"))
    expected = [0, 2*np.sin(angle)/angle, 2*(1-np.cos(angle))/angle]
    errors = []
    for panels in (12, 24):
        r = solve_static(m, panels=panels, gravity=[0, 0, 0], loads=[dict(beam=1, t=2, moment=[50*angle, 0, 0])])
        errors.append(np.linalg.norm(tip(r)-expected))
        balanced(r)
        for node in r["nodes"]:
            rotation = np.array(node["rotation"])
            np.testing.assert_allclose(rotation.T@rotation, np.eye(3), atol=1e-14)
    assert errors[1] < errors[0]*.26
    assert errors[1] < .003


def test_finite_extension_and_shear_are_exact():
    r = solve_static(model(beam(stiffness="0 0 0 1000 0 100")), panels=6,
                     loads=[dict(beam=1, t=2, force=[0, 10, 2])])
    np.testing.assert_allclose(tip(r), [0, 2.02, .04], atol=1e-10)
    balanced(r)


def test_combined_spatial_loading_matches_independent_collocation():
    m = model(beam(stiffness="80 100 60 500 900 700"))
    force, moment = [1., .5, 2.], [2., 1., .3]
    reference = solve_cantilever(2, Section(EIcc=80, EInn=100, GJ=60, EA=500, GKc=900, GKn=700),
                                tip_force=force, tip_moment=moment)
    r = solve_static(m, panels=24, loads=[dict(beam=1, t=2, force=force, moment=moment)])
    np.testing.assert_allclose(tip(r), reference.position[-1], atol=1e-4)
    np.testing.assert_allclose(r["nodes"][-1]["rotation"], reference.rotation[-1], atol=2e-5)
    balanced(r)


def test_mass_centroid_and_point_pylon_gravity_reactions():
    b = beam(stiffness="0 0 0 0 0 0").replace("End", "t mg Ccg Dmg DCcg\n0 10 .2 5 -.1\n2 10 .2 5 -.1\nEnd")
    m = model(b, "Ground\n1 0 0\nEnd\nWeight\n1 1 .4 1 .3 20\nEnd\n")
    r = solve_static(m, panels=8)
    np.testing.assert_allclose(r["support_force"], [0, 0, 50], atol=1e-9)
    np.testing.assert_allclose(r["support_moment"], [50, -11, 0], atol=1e-9)
    balanced(r)


def test_rigid_offset_joint_transmits_force_and_moment_conservatively():
    b = beam(stiffness="0 0 0 0 0 0") + beam(2, start=3, end=5, z=1, stiffness="0 0 0 0 0 0")
    m = model(b, "Ground\n1 0 0\nEnd\nJoint\n1 2 2 0 0\nEnd\n")
    r = solve_static(m, panels=4, loads=[dict(beam=2, t=2, force=[2, 3, 4])])
    np.testing.assert_allclose(r["support_force"], [-2, -3, -4], atol=1e-10)
    np.testing.assert_allclose(r["support_moment"], -np.cross([0, 5, 1], [2, 3, 4]), atol=1e-10)
    assert r["max_displacement"] < 1e-10
    balanced(r)


def test_connected_flexible_beams_match_one_continuous_beam():
    joined = model(beam()+beam(2, start=2, end=4), "Ground\n1 0 0\nEnd\nJoint\n1 2 2 0 0\nEnd\n")
    r = solve_static(joined, panels=12, loads=[dict(beam=2, t=2, force=[0, 0, 2])])
    reference = solve_cantilever(4, Section(EIcc=100, EInn=100, GJ=100, EA=1000, GKc=1000, GKn=1000), tip_force=[0, 0, 2])
    np.testing.assert_allclose(tip(r, 2), reference.position[-1], atol=7e-4)
    balanced(r)


def test_pinned_joint_allows_relative_rotation_and_transmits_no_couple():
    m = model(beam()+beam(2, start=2, end=4), "Ground\n1 0 0\n2 0 2\nEnd\nJoint\n1 2 2 0 1\nEnd\n")
    r = solve_static(m, panels=8, loads=[dict(beam=2, t=2, force=[0, 0, 2])])
    nodes1, nodes2 = [[n for n in r["nodes"] if n["beam"] == k] for k in (1, 2)]
    np.testing.assert_allclose(nodes1[-1]["position"], nodes2[0]["position"], atol=1e-9)
    assert np.linalg.norm(np.array(nodes1[-1]["rotation"])-nodes2[0]["rotation"]) > .02
    np.testing.assert_allclose(r["reactions"][-1]["moment"], 0, atol=1e-12)
    balanced(r)


def test_roller_joint_matches_rotations_but_leaves_translation_free():
    m = model(beam()+beam(2, start=3, end=5), "Ground\n1 0 0\n2 0 1\nEnd\nJoint\n1 2 2 0 2\nEnd\n")
    r = solve_static(m, panels=8, loads=[dict(beam=2, t=2, moment=[4, 0, 0])])
    nodes1, nodes2 = [[n for n in r["nodes"] if n["beam"] == k] for k in (1, 2)]
    np.testing.assert_allclose(nodes1[-1]["rotation"], nodes2[0]["rotation"], atol=1e-8)
    np.testing.assert_allclose(nodes2[0]["position"], [0, 3, 0], atol=1e-9)
    assert nodes1[-1]["position"][2] > .03
    np.testing.assert_allclose(r["reactions"][-1]["force"], 0, atol=1e-12)
    balanced(r)


def test_doubled_station_rigid_offset_is_not_material_length():
    b = "Beam 1\nStepped axis\nt y z\n0 0 0\n1 1 0\n1 1 1\n2 2 1\nEnd\n"
    m = model(b)
    from openswing.geometry import mesh_beam
    assert sum(mesh_beam(m.beams[0], 8).length) == pytest.approx(2.)
    r = solve_static(m, panels=8, loads=[dict(beam=1, t=2, force=[2, 3, 4])])
    np.testing.assert_allclose(tip(r), [0, 2, 1], atol=1e-10)
    np.testing.assert_allclose(r["support_moment"], -np.cross([0, 2, 1], [2, 3, 4]), atol=1e-9)
    balanced(r)


@pytest.mark.parametrize("attachments,beams", [
    ("Ground\n1 0 1\nEnd\n", beam()),
    ("Ground\n1 0 0\n1 0 0\nEnd\n", beam()),
    ("Ground\n1 0 0\nEnd\n", beam()+beam(2)),
])
def test_mechanisms_and_redundant_constraints_are_rejected_at_zero_load(attachments, beams):
    with pytest.raises(AnalysisError, match="mechanism or redundant"):
        solve_static(model(beams, attachments), panels=4, gravity=[0, 0, 0])


def test_coupled_rigid_limit_matches_separate_aero_and_balances_reactions():
    m = parse_asw(Path("examples/rectangular.asw").read_text())
    c = FlightCondition(alpha=5, mach=0)
    rigid = solve_rigid(m, c, panels=8)
    coupled = solve_static(m, c, panels=8)
    for key in ("CL", "CD", "Cm", "force", "moment"):
        np.testing.assert_allclose(coupled[key], rigid[key], atol=1e-8)
    assert coupled["max_displacement"] < 1e-10
    balanced(coupled)


def test_circulation_responds_to_finite_elastic_deformation_and_refines():
    m = parse_asw(Path("examples/flexible.asw").read_text())
    c = FlightCondition(alpha=5, mach=0)
    rigid = solve_rigid(m, c, panels=24)
    coarse = solve_static(m, c, panels=12)
    fine = solve_static(m, c, panels=24)
    assert fine["max_displacement"] > 1
    assert abs(fine["CL"]-rigid["CL"]) > .03
    assert abs(fine["CL"]-coarse["CL"])/fine["CL"] < .025
    assert abs(fine["max_displacement"]-coarse["max_displacement"])/fine["max_displacement"] < .025
    assert fine["CL"] > 0
    balanced(fine, atol=1e-6)
    nodes = np.array([n["position"] for n in fine["nodes"]])
    np.testing.assert_allclose(nodes[:, [0, 2]], nodes[::-1, [0, 2]], atol=1e-7)
    np.testing.assert_allclose(nodes[:, 1], -nodes[::-1, 1], atol=1e-7)


def test_missing_mount_and_invalid_motion_are_explicit_errors():
    with pytest.raises(AnalysisError, match="requires Ground"):
        solve_static(model(attachments=""), panels=4)
    m = parse_asw(Path("examples/rectangular.asw").read_text())
    with pytest.raises(ValueError, match="finite xyz"):
        solve_static(m, FlightCondition(rates=(0, 1)), panels=4)
