from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, finite_vortex, semi_infinite_vortex, AnalysisError
from openswing.geometry import mesh_beam, surface_frame

EXAMPLE = Path("examples/rectangular.asw").read_text()


def test_finite_vortex_matches_biot_savart_at_segment_midpoint():
    val = finite_vortex([1, 0, 0], [0, -1, 0], [0, 1, 0])
    np.testing.assert_allclose(val, [0, 0, -np.sqrt(2) / (4 * np.pi)], atol=1e-14)


def test_semi_infinite_vortex_known_solution():
    val = semi_infinite_vortex([0, 1, 0], [0, 0, 0], [1, 0, 0])
    np.testing.assert_allclose(val, [0, 0, 1 / (4 * np.pi)], atol=1e-14)


def test_regularized_integral_matches_numerical_quadrature():
    from scipy.integrate import quad_vec
    p, a, b, eps = np.array([.3, 1.2, .7]), np.array([-.2, 0., 0.]), np.array([.8, .5, .1]), .3
    expected = quad_vec(lambda t: np.cross(b-a, p-a-t*(b-a)) / (np.linalg.norm(p-a-t*(b-a))**2+eps**2)**1.5, 0, 1)[0] / (4*np.pi)
    np.testing.assert_allclose(finite_vortex(p, a, b, eps), expected, atol=1e-13)


def test_frame_is_right_handed_and_twist_convention():
    b = parse_asw(EXAMPLE.replace("t Cdf", "t twist\n0 10\n6 10\nt Cdf")).beams[0]
    r = surface_frame(b, 2)
    np.testing.assert_allclose(r.T @ r, np.eye(3), atol=1e-14)
    assert np.linalg.det(r) == pytest.approx(1)
    assert r[2, 0] == pytest.approx(-np.sin(np.deg2rad(10)))


def test_arbitrary_parameter_does_not_change_mesh():
    first = parse_asw(EXAMPLE).beams[0]
    # Scale every station parameter (including controls), not spatial coordinates.
    text = EXAMPLE
    lines = text.splitlines()
    within = False
    for i, line in enumerate(lines):
        if line.startswith("Beam"):
            within = True
        if within and line and (line[0].isdigit() or line[0] == "-"):
            tokens = line.split(); tokens[0] = str(float(tokens[0]) * 10); lines[i] = " ".join(tokens)
    second = parse_asw("\n".join(lines)).beams[0]
    np.testing.assert_allclose(mesh_beam(first).rm, mesh_beam(second).rm, atol=1e-12)


def test_zero_alpha_and_mirror_symmetry():
    m = parse_asw(EXAMPLE)
    r = solve_rigid(m, FlightCondition(alpha=0, mach=0))
    assert abs(r["CL"]) < 1e-12
    assert r["CDp"] == pytest.approx(.008, rel=.002)
    assert abs(r["Cl"]) < 1e-12
    r = solve_rigid(m, FlightCondition(alpha=4, mach=0))
    cls = np.array([p["cl"] for p in r["strips"]])
    np.testing.assert_allclose(cls, cls[::-1], atol=1e-12)
    assert r["CL"] > 0 and r["CDi"] > 0
    assert abs(r["CY"]) < 1e-12 and abs(r["Cl"]) < 1e-12
    assert r["residual"] < 1e-9


def test_elliptic_wing_lift_slope_drag_and_mesh_convergence():
    # Classical lifting line: CL_alpha=a0/(1+a0/(pi AR)), e=1. This is
    # an asymptotic high-AR validation, not an exact finite-chord identity.
    span, root_chord = 40., 1.
    ts = np.linspace(-span/2, span/2, 101)
    chords = np.maximum(np.sqrt(1-(2*ts/span)**2), 1e-5)
    text = f"Name\nElliptic verification\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n{np.pi*span*root_chord/4} 1 {span}\nEnd\nBeam 1\nWing\nt y chord Xax\n"
    text += "\n".join(f"{t:.12g} {t:.12g} {c:.12g} .25" for t,c in zip(ts,chords)) + "\nEnd\n"
    model = parse_asw(text)
    expected_slope = 2*np.pi/(1+2/(span**2/model.reference[0,0]))
    a = solve_rigid(model, FlightCondition(alpha=.5, mach=0, stall=False), panels=48)
    b = solve_rigid(model, FlightCondition(alpha=.5, mach=0, stall=False), panels=96)
    assert b["CL"]/np.deg2rad(.5) == pytest.approx(expected_slope, rel=.015)
    assert b["efficiency"] == pytest.approx(1., abs=.04)
    assert abs(b["CL"]-a["CL"])/b["CL"] < .005


def test_controls_have_correct_roll_sign_and_zero_net_lift_increment():
    m = parse_asw(EXAMPLE)
    pos = solve_rigid(m, FlightCondition(alpha=0, controls={1: 5}, mach=0))
    neg = solve_rigid(m, FlightCondition(alpha=0, controls={1: -5}, mach=0))
    assert abs(pos["CL"]) < 1e-10
    assert pos["Cl"] < 0
    assert pos["Cl"] == pytest.approx(-neg["Cl"], rel=1e-9)


@pytest.mark.parametrize('frozen', [True, False], ids=['frozen', 'current'])
@pytest.mark.parametrize('alpha', [25, 35])
def test_stall_reduces_slope_and_adds_pressure_drag(frozen, alpha):
    m = parse_asw(EXAMPLE)
    attached = solve_rigid(m, FlightCondition(alpha=alpha, stall=False, mach=0, freeze_influences=frozen))
    stalled = solve_rigid(m, FlightCondition(alpha=alpha, stall=True, mach=0, freeze_influences=frozen))
    assert stalled["CL"] < attached["CL"] * .7
    assert stalled["CDp"] > .05
    # The smooth stall law acts before crossing the example's +/-1.2 limits.
    # This flag reports the crossing, not every nonzero soft-stall contribution.
    assert all(s['stalled'] == (abs(s['cl']) > 1.2) for s in stalled['strips'])
    if alpha == 35:
        assert any(s['stalled'] for s in stalled['strips'])


def test_compressibility_increases_lift():
    m = parse_asw(EXAMPLE)
    low = solve_rigid(m, FlightCondition(alpha=2, mach=0))
    high = solve_rigid(m, FlightCondition(alpha=2, mach=.6))
    assert 1.1 < high["CL"] / low["CL"] < 1.3


def test_speed_scaling_preserves_coefficients():
    m = parse_asw(EXAMPLE)
    a = solve_rigid(m, FlightCondition(speed=20, alpha=3, mach=0))
    b = solve_rigid(m, FlightCondition(speed=40, alpha=3, mach=0))
    assert a["CL"] == pytest.approx(b["CL"], rel=1e-10)
    np.testing.assert_allclose(np.array(b["force"]), 4*np.array(a["force"]), atol=1e-9)


def test_invalid_volume_is_reported_not_silently_omitted():
    m = parse_asw(EXAMPLE + "\nWeight\n1 0 0 0 0 1 0 -1\nEnd\n")
    with pytest.raises(AnalysisError, match="nonnegative"):
        solve_rigid(m, FlightCondition())
