"""Independent continuum, impulse, wake-energy and invariance checks."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid
from openswing.asw import parse_asw
from openswing.geometry import mesh_beam
from openswing.ground import GroundPlane
from openswing.trefftz import wake_forces, wake_velocity, WakeIntersection


def elliptic(n=64, modes=(10.,), span=8.):
    theta = np.linspace(0, np.pi, n+1)
    middle = (theta[:-1]+theta[1:])/2
    nodes = np.c_[np.zeros(n+1), -span/2*np.cos(theta), np.zeros(n+1)]
    points = np.c_[np.zeros(n), -span/2*np.cos(middle), np.zeros(n)]
    gamma = sum(value*np.sin((i+1)*middle) for i, value in enumerate(modes))
    return nodes[:-1], nodes[1:], points, gamma


def report(a, b, p, gamma, *, wind=(1, 0, 0), side=(0, 1, 0), lift=(0, 0, 1),
           speed=20., density=1.2, reference=None, ground=None):
    if reference is None:reference = np.array([[8., 1., 8.], [0., 0., 0.]])
    return wake_forces(a, b, p, gamma, wind, side, lift, speed, density, reference, ground)


def test_elliptic_lift_downwash_drag_and_efficiency_converge_to_continuum():
    errors = []
    for n in (16, 32, 64):
        a, b, p, gamma = elliptic(n)
        r = report(a, b, p, gamma)
        assert r['available']
        # L=rho V Gamma0 pi b/4, D=rho pi Gamma0^2/8, w_T=-Gamma0/b.
        exact_lift = 1.2*20*10*np.pi*8/4
        exact_drag = 1.2*np.pi*100/8
        errors.append(abs(r['induced_drag']/exact_drag-1))
        assert r['force_transverse_body'][2] == pytest.approx(exact_lift, rel=.002)
        np.testing.assert_allclose(np.array(r['velocity_body'])[:, 2], -10/8, rtol=.002)
        assert r['efficiency'] == pytest.approx(1., abs=1e-12)
        assert r['rolling_moment_wind'] == pytest.approx(0., abs=1e-11)
    assert errors[1] < .26*errors[0] and errors[2] < .26*errors[1]
    assert errors[-1] < .00021


@pytest.mark.parametrize('modes', [(10., 0., 2.), (0., 10.), (8., -2., 1., .5)])
def test_fourier_loads_match_independent_induced_drag_and_roll(modes):
    a, b, p, gamma = elliptic(192, modes)
    r = report(a, b, p, gamma)
    exact_drag = 1.2*np.pi/8*sum((i+1)*v*v for i, v in enumerate(modes))
    exact_lift = 1.2*20*np.pi*8/4*modes[0]
    # With y=-b cos(theta)/2, only sin(2 theta) contributes to the roll impulse.
    exact_roll = -1.2*20*np.pi*8**2/16*(modes[1] if len(modes)>1 else 0.)
    assert r['induced_drag'] == pytest.approx(exact_drag, rel=.0005)
    assert r['force_transverse_body'][2] == pytest.approx(exact_lift, rel=.0001, abs=1e-11)
    assert r['rolling_moment_wind'] == pytest.approx(exact_roll, rel=.0003, abs=1e-11)
    if modes[0] == 0:assert r['efficiency'] < 1e-25


def test_rotation_translation_and_chordwise_stagger_preserve_wake_energy():
    a, b, p, gamma = elliptic(32, (10., 1., 2.))
    original = report(a, b, p, gamma)
    # Two coincident wake sheets with half the circulation reproduce one sheet,
    # even after moving each lifting surface arbitrarily along the wind.
    a, b, p = [np.concatenate((v+[7, 0, 0], v+[-13, 0, 0])) for v in (a, b, p)]
    gamma = np.r_[gamma/2, gamma/2]
    q = Rotation.from_rotvec([.8, -.6, .3]).as_matrix(); offset = [13., 17., -9.]
    rotated = report(a@q.T+offset, b@q.T+offset, p@q.T+offset, gamma,
        wind=q[:, 0], side=q[:, 1], lift=q[:, 2], reference=np.array([[8, 1, 8], offset]))
    for key in ('CLi', 'CYi', 'CDi', 'efficiency', 'rolling_moment_wind'):
        assert rotated[key] == pytest.approx(original[key], rel=1e-12, abs=1e-12)
    # Rotating only the lifting trace about the wind transfers lift to sideforce.
    q = Rotation.from_rotvec([np.pi/2, 0, 0]).as_matrix()
    vertical = report(a@q.T, b@q.T, p@q.T, gamma)
    assert vertical['CLi'] == pytest.approx(0., abs=1e-14)
    assert vertical['CYi'] == pytest.approx(-original['CLi'], rel=1e-12)
    assert vertical['efficiency'] == pytest.approx(original['efficiency'], rel=1e-12)


@pytest.mark.parametrize('flag', [1, -1])
def test_ground_image_downwash_matches_elliptic_center_formula(flag):
    # Odd count puts y=0 at the theta midpoint used by the force quadrature,
    # rather than at a cancelled pair of discrete filament endpoints.
    a, b, _, gamma = elliptic(511)
    for height in (.3, 1., 4.):
        ground = GroundPlane(flag, [0, 0, height])
        w = wake_velocity([[0., 0., 0.]], np.r_[a, ground.reflect_points(a)],
                          np.r_[b, ground.reflect_points(b)], np.r_[gamma, -flag*gamma], [1., 0., 0.])[0, 2]
        # Solid-wall center downwash = free value * k/sqrt(1+k^2), k=2h/(b/2).
        k = 2*height/4
        factor = k/np.sqrt(1+k*k)
        expected = -10/8*(factor if flag == 1 else 2-factor)
        assert w == pytest.approx(expected, rel=3e-5)


def test_unresolved_filament_is_reported_but_coincident_cancellation_is_exact():
    a = np.array([[0., -1., 0.]]); b = np.array([[0., 1., 0.]])
    with pytest.raises(WakeIntersection):wake_velocity(a, a, b, [1.], [1., 0., 0.])
    result = report(a, b, a, [1.])
    assert not result['available'] and result['CDi'] is None
    assert 'filament' in result['reason']
    np.testing.assert_array_equal(wake_velocity(a, np.r_[a, a], np.r_[b, b], [1., -1.], [1., 0., 0.]), 0.)
    solid = report(a, b, [[0, 0, 0]], [1.], ground=GroundPlane(1, [0, 0, 0]))
    assert solid['available'] and solid['induced_drag'] == 0 and solid['efficiency'] is None


@pytest.mark.parametrize('sign', [1., -1.])
def test_exactly_zero_circulation_uses_native_zero_efficiency_convention(sign):
    a, b, p, gamma = elliptic(8)
    r = report(a, b, p, sign*np.zeros_like(gamma))
    assert r['available']
    assert r['CLi'] == r['CYi'] == r['CDi'] == r['efficiency'] == 0.
    np.testing.assert_array_equal(r['force_transverse_body'], 0.)
    np.testing.assert_array_equal(r['velocity_body'], 0.)


@pytest.mark.parametrize('scale', [1e-12, 1e-80])
def test_nonzero_circulation_has_no_efficiency_reporting_threshold(scale):
    a, b, p, gamma = elliptic(8)
    original = report(a, b, p, gamma)
    small = report(a, b, p, scale*gamma)
    assert small['available'] and small['CDi'] > 0.
    assert small['efficiency'] == pytest.approx(original['efficiency'], rel=1e-12)


def test_zero_efficiency_convention_excludes_empty_degenerate_and_invalid_geometry():
    empty = np.empty((0, 3))
    assert report(empty, empty, empty, [])['efficiency'] is None
    a = np.array([[0., -1., 0.]])
    assert report(a, a, a, [0.])['efficiency'] is None
    assert report(a, a+[1., 0., 0.], a, [0.])['efficiency'] is None
    b = np.array([[0., 1., 0.]])
    with pytest.raises(ValueError, match='finite'):
        report(a, b, [[0., np.nan, 0.]], [0.])
    with pytest.raises(ValueError, match='finite'):
        report(a, b, [[0., 0., 0.]], [np.nan])
    assert report(a, b, [[0., 0., 0.]], [0.],
                  reference=np.array([[np.inf, 1., 8.], [0., 0., 0.]]))['efficiency'] is None


def test_opposite_nonzero_sheets_do_not_use_unloaded_efficiency_convention():
    a = np.array([[0., -1., 0.]])
    b = np.array([[0., 1., 0.]])
    r = report(np.r_[a, a], np.r_[b, b], np.zeros((2, 3)), [1., -1.])
    assert r['available'] and r['CLi'] == r['CYi'] == r['CDi'] == 0.
    assert r['efficiency'] is None


def test_oblique_image_trace_is_unavailable_without_corrupting_near_field_loads():
    model = parse_asw(Path('examples/rectangular.asw').read_text())
    r = solve_rigid(model, FlightCondition(alpha=5., ground_effect=1, position_earth=(0, 0, 4)), panels=8)
    assert r['converged'] and np.isfinite(r['CD']) and np.isfinite(r['CDi_near'])
    assert r['CDi'] is None and r['efficiency'] is None
    assert 'parallel' in r['trefftz']['reason']


def test_force_drag_ledger_and_trefftz_reference_quantities_are_distinct():
    model = parse_asw(Path('examples/rectangular.asw').read_text())
    c = FlightCondition(alpha=12., beta=7., mach=0., stall=False)
    r = solve_rigid(model, c, panels=16)
    assert r['CD'] == pytest.approx(sum(r[k] for k in ('CDi_near', 'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate')), abs=1e-14)
    assert abs(r['CDi']-r['CDi_near']) > 1e-5
    gamma = [s['circulation'] for s in r['strips']]
    # Holding circulation fixed isolates the geometric Trefftz evaluation from
    # the Mach-dependent lifting-line solution.
    meshes = [mesh_beam(b, 16) for b in model.beams]
    compressible = evaluate_aerodynamics(model, replace(c, mach=.6), meshes, circulation=gamma)
    for key in ('CLi', 'CYi', 'CDi', 'efficiency'):
        assert compressible[key] == pytest.approx(r[key], rel=1e-12, abs=1e-12)


@pytest.mark.parametrize('images', [False, True])
def test_complex_output_obeys_wake_homogeneity_and_preserves_unavailable_drag(images):
    from openswing.linear_dynamics import make_system, output_perturbation
    model = parse_asw(Path('examples/rectangular.asw').read_text())
    condition = FlightCondition(alpha=5., mach=0., ground_effect=int(images), position_earth=(0, 0, 4))
    system, _ = make_system(model, condition, 4, frame='fixed', gravity=[0, 0, 0])
    base = system.base_report(); n = system.network
    vector = np.zeros(system.size, dtype=complex)
    factor = 1.+.4j
    vector[n.gamma_start:n.operating_start] = factor*system.gamma0/n.gamma_scale
    result = output_perturbation(system, vector, np.zeros_like(vector))['global']
    def value(key):return complex(result[key]['real'], result[key]['imag'])
    # Impulse is linear in Gamma; fixed-geometry wake drag is quadratic.
    assert value('CLi') == pytest.approx(factor*base['CLi'], rel=1e-8)
    assert np.isfinite(value('CDi_near'))
    if images:
        assert result['CDi'] is None
    else:
        assert value('CDi') == pytest.approx(2*factor*base['CDi'], rel=1e-8)
