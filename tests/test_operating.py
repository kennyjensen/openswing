from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from openswing.inertia import Motion
from openswing.network import solve_static
from openswing.operating import OperatingConstraint, free_flight_constraints
from test_inertia import rod


def accelerations(result):
    return np.array([result["operating_values"][f"{name}.{a}"] for name in ("acceleration", "angular_acceleration") for a in "xyz"])


def test_six_free_flight_constraints_match_rigid_body_newton_euler_with_spin():
    mass, g = 3., 9.80665
    cg, spin = np.array([.2, .7, .1]), np.array([.2, .1, -.15])
    inertia = np.array([[.5, .04, -.02], [.04, .7, .03], [-.02, .03, .9]])
    row = [1, 0, *cg, mass*g, 0, 0, *(spin*g), *(np.r_[np.diag(inertia), -inertia[0, 1], -inertia[0, 2], -inertia[1, 2]]*g)]
    model = rod(weight="Weight\n"+" ".join(map(str, row))+"\nEnd\n")
    rates = np.array([.3, -.2, .4]); force = np.array([2., -1., 4.]); torque = np.array([.4, .3, -.2])
    alpha = np.linalg.solve(inertia, torque+np.cross(np.array([0, 2, 0])-cg, force)-np.cross(rates, inertia@rates+spin))
    a_cg = np.array([0, 0, -g])+force/mass
    a_ref = a_cg-np.cross(alpha, cg)-np.cross(rates, np.cross(rates, cg))
    result = solve_static(model, panels=4, motion=Motion(rates=rates), operating_constraints=free_flight_constraints(),
                          loads=[dict(beam=1, t=2, force=force, moment=torque)])
    np.testing.assert_allclose(accelerations(result), np.r_[a_ref, alpha], atol=1e-8)
    np.testing.assert_allclose(result["support_force"], 0, atol=1e-8)
    np.testing.assert_allclose(result["support_moment"], 0, atol=1e-8)
    assert result["analysis"] == "constrained_static"
    assert all(abs(c["normalized_residual"]) < 1e-8 for c in result["operating_constraints"])


def test_free_flight_aerodynamic_acceleration_includes_full_added_mass_matrix():
    source = Path("examples/rectangular.asw").read_text()
    g = 9.80665
    source += f"\nWeight\n1 0 .1 0 0 {100*g} 0 0 0 0 0 {500*g} {100*g} {550*g}\nEnd\n"
    model, condition = parse_asw(source), FlightCondition(alpha=5, mach=0)
    rigid = solve_rigid(model, condition, panels=8)
    real, apparent = rigid["mass_properties"], rigid["apparent_mass"]
    matrix = np.array(real["spatial_matrix"])+apparent["spatial_matrix"]
    weight = np.array([0, 0, -g*real["mass"]])
    load = np.r_[np.array(rigid["force"])+weight, np.array(rigid["moment"])+np.cross(real["cg"], weight)]
    expected = np.linalg.solve(matrix, load)
    result = solve_static(model, condition, panels=8, operating_constraints=free_flight_constraints())
    np.testing.assert_allclose(accelerations(result), expected, atol=1e-8)
    np.testing.assert_allclose(result["support_force"], 0, atol=1e-7)
    np.testing.assert_allclose(result["support_moment"], 0, atol=1e-7)
    assert np.linalg.norm(result["apparent_force"]) > .1


def test_prescribed_lift_and_pitch_moment_solve_alpha_and_flap():
    source = Path("examples/rectangular.asw").read_text().split("t dCLdF1")[0]
    source += "t Cm dCMdF1\n0 -.04 -.012\n6 -.04 -.012\nEnd\n"
    model = parse_asw(source)
    constraints = [OperatingConstraint("alpha", "lift", 2000), OperatingConstraint("control.1", "moment.y", 0)]
    result = solve_static(model, FlightCondition(alpha=1, mach=0), panels=8, operating_constraints=constraints)
    assert 2 < result["operating_values"]["alpha"] < 5
    assert result["operating_values"]["control.1"] == pytest.approx(-.04/.012, abs=1e-8)
    assert result["operating_constraints"][0]["actual"] == pytest.approx(2000, abs=1e-6)
    assert abs(result["applied_moment"][1]) < 1e-6


def test_inverse_constraints_recover_a_finite_deformation_operating_point():
    source = Path("examples/flexible.asw").read_text().rstrip()
    source = source[:-3]+"t dCLdF2 dCMdF2\n0 .02 -.007\n8 .02 -.007\nEnd\n"
    model = parse_asw(source)
    forward = solve_static(model, FlightCondition(alpha=5, mach=0, controls={2:2}), panels=8)
    ez = FlightCondition(alpha=5).vectors()[2]
    target_lift = np.array(forward["force"])@ez
    inverse = solve_static(model, FlightCondition(alpha=3, mach=0), panels=8,
                           operating_constraints=[OperatingConstraint("alpha", "lift", target_lift),
                                                  OperatingConstraint("control.2", "moment.y", forward["applied_moment"][1])])
    assert forward["max_displacement"] > 1
    assert inverse["operating_values"]["alpha"] == pytest.approx(5, abs=1e-7)
    assert inverse["operating_values"]["control.2"] == pytest.approx(2, abs=1e-7)
    np.testing.assert_allclose([n["position"] for n in inverse["nodes"]], [n["position"] for n in forward["nodes"]], atol=1e-7)


def test_speed_can_be_solved_from_lift_without_negative_speed_trials():
    model = parse_asw(Path("examples/rectangular.asw").read_text())
    condition = FlightCondition(speed=20, alpha=4, mach=0, stall=False)
    reference = solve_rigid(model, condition, panels=8)
    target = np.array(reference["force"])@condition.vectors()[2]*4
    result = solve_static(model, condition, panels=8, operating_constraints=[OperatingConstraint("speed", "lift", target)])
    assert result["operating_values"]["speed"] == pytest.approx(40, rel=1e-8)


@pytest.mark.parametrize("constraints,match", [
    ([OperatingConstraint("alpha", "lift"), OperatingConstraint("alpha", "moment.y")], "more than once"),
    ([OperatingConstraint("control.90", "moment.y")], "Unsupported operating"),
    ([OperatingConstraint("alpha", "lift", np.nan)], "finite target"),
    ([OperatingConstraint("acceleration.x", "force.z"), OperatingConstraint("acceleration.y", "force.z")], "operating targets"),
])
def test_invalid_and_dependent_operating_constraints_fail_explicitly(constraints, match):
    model = parse_asw(Path("examples/rectangular.asw").read_text())
    with pytest.raises(ValueError, match=match):
        solve_static(model, FlightCondition(mach=0), panels=4, operating_constraints=constraints)
