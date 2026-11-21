"""Continuous wake energy, invariance, cancellation and explicit diagnostic scope."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.spatial.transform import Rotation
from openswing.aero import FlightCondition, solve_rigid, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.circulation import CirculationBasis
from openswing.fourier_wake import fourier_wake_forces, fourier_wake_for_meshes
from openswing.geometry import model_meshes


def trace(coefficients=(3.,), span=4., center=(0., 0., 0.)):
    center = np.asarray(center)
    return dict(start=center+[0, -span/2, 0], end=center+[0, span/2, 0], coefficients=np.asarray(coefficients))


def report(traces, **kwargs):
    settings = dict(wind=[1., 0., 0.], side=[0., 1., 0.], lift=[0., 0., 1.],
                    speed=20., density=1.2, reference=[[4., 1., 4.], [0., 0., 0.]])
    return fourier_wake_forces(traces, **(settings | kwargs))


def test_fourier_modal_energy_impulse_and_roll_are_exact():
    coefficients = np.array([3., -.4, .2, .07])
    r = report([trace(coefficients, center=(9., .3, -.8))])
    assert r['available']
    exact_lift = 1.2*20*np.pi*4*coefficients[0]/4
    assert r['force_transverse_body'] == pytest.approx([0, 0, exact_lift], abs=1e-12)
    assert r['induced_drag'] == pytest.approx(1.2*np.pi/8*np.sum(np.arange(1, 5)*coefficients**2), rel=2e-15)
    assert r['rolling_moment_wind'] == pytest.approx(.3*exact_lift+1.2*20*np.pi*4**2*coefficients[1]/16, rel=2e-15)
    assert report([trace()])['efficiency'] == pytest.approx(1., abs=1e-14)


def test_independent_line_integral_at_nearly_coincident_unequal_spans():
    # A one-mode source has analytic normal velocity. Integrate it with an
    # independent adaptive real quadrature, avoiding the production partition.
    height = .002025068888026535
    first, second = trace((3.,), 1.32), trace((2.,), 1.83, (5., 0., height))
    r = report([first, second])
    assert r['available'], r
    def directed(target_span, target_gamma, source_span, source_gamma):
        a, b = target_span/2, source_span/2
        def integrand(theta):
            y = a*np.cos(theta)
            z = complex(y, height)
            root = np.sqrt(z-b)*np.sqrt(z+b)
            vz = source_gamma/(2*b)*np.real(z/root-1)
            return -.5*1.2*a*target_gamma*np.sin(theta)**2*vz
        points = [np.arccos(np.clip(v/a, -1, 1)) for v in (-b, b) if abs(v) < a]
        return quad(integrand, 0, np.pi, points=points, epsabs=1e-11, epsrel=1e-11, limit=250)[0]
    d12 = directed(1.32, 3., 1.83, 2.)
    d21 = directed(1.83, 2., 1.32, 3.)
    assert d12 == pytest.approx(d21, rel=1e-11)
    np.testing.assert_allclose(r['drag_matrix'], [[1.2*np.pi/8*9, d12], [d21, 1.2*np.pi/8*4]], rtol=2e-10)
    assert r['induced_drag'] > 0


@pytest.mark.parametrize('height', [0., 1e-5, .01, 1.])
def test_opposite_unequal_wakes_keep_nonnegative_energy_through_alignment(height):
    r = report([trace((1., .02, -.03), 4.), trace((-.9, -.01), 3., (10., .1, height))])
    assert r['available'], r
    assert r['induced_drag'] > 0
    assert np.asarray(r['drag_matrix'])[0, 1] == pytest.approx(np.asarray(r['drag_matrix'])[1, 0], rel=2e-10)


def test_coplanar_elliptic_mutual_energy_matches_constant_inner_downwash():
    # The smaller wake lies entirely inside the longer elliptic wake, whose
    # principal-value downwash is constant. Reciprocity supplies the reverse
    # integral, including the shorter wake's tip singularities.
    r = report([trace((1.,), 4.), trace((-.9,), 3., (11., .1, 0.))])
    assert r['available'], r
    cross = 1.2*np.pi/8*(1.*-.9)*(3./4.)
    np.testing.assert_allclose(r['drag_matrix'],
        [[1.2*np.pi/8, cross], [cross, 1.2*np.pi/8*.9**2]], rtol=2e-10)
    assert r['induced_drag'] == pytest.approx(1.2*np.pi/8*(1+.9**2-2*.9*3/4), rel=2e-10)


def test_coincident_cancellation_orientation_and_translation_are_preserved():
    original = trace((3., .2, -.3), center=(9., .1, .7))
    reversed_trace = dict(start=original['end']+[-21, 0, 0], end=original['start']+[-21, 0, 0],
                          coefficients=original['coefficients']*(-1.)**np.arange(1, 4))
    single = report([original])
    same = report([reversed_trace])
    for name in ('CLi', 'CYi', 'CDi', 'efficiency', 'rolling_moment_wind'):
        assert same[name] == pytest.approx(single[name], rel=2e-14, abs=2e-14)
    opposite = dict(reversed_trace, coefficients=-reversed_trace['coefficients'])
    canceled = report([original, opposite])
    assert canceled['available'] and canceled['induced_drag'] == canceled['CLi'] == canceled['CYi'] == 0
    assert canceled['efficiency'] is None
    q = Rotation.from_rotvec([.7, -.3, .5]).as_matrix()
    shift = np.array([19., -13., 7.])
    transformed = dict(start=q@original['start']+shift, end=q@original['end']+shift, coefficients=original['coefficients'])
    rotated = report([transformed], wind=q[:, 0], side=q[:, 1], lift=q[:, 2], reference=[[4., 1., 4.], shift])
    for name in ('CLi', 'CYi', 'CDi', 'efficiency', 'rolling_moment_wind'):
        assert rotated[name] == pytest.approx(single[name], rel=2e-14, abs=2e-14)


@pytest.mark.parametrize('factor', [0., 1e-12, 1e-80])
def test_small_nonzero_circulation_is_not_clipped(factor):
    original = report([trace((3., .2))])
    small = report([trace(np.array([3., .2])*factor)])
    assert small['available']
    if factor:
        assert small['CDi'] > 0
        assert small['CDi']/original['CDi'] == pytest.approx(factor**2, rel=1e-14, abs=0)
        assert small['efficiency'] == pytest.approx(original['efficiency'], rel=1e-14)
    else:
        assert small['CDi'] == small['efficiency'] == 0


def test_unsupported_geometry_and_unresolved_quadrature_are_explicit():
    parallel_to_wind = dict(start=[-2., 0., 0.], end=[2., 0., 0.], coefficients=[1.])
    assert not report([parallel_to_wind])['available']
    unresolved = report([trace((1., .2)), trace((-.8, .3), 3., (0, .2, .002))],
                        relative_tolerance=1e-30, max_order=32)
    assert not unresolved['available'] and 'converge' in unresolved['reason']
    with pytest.raises(ValueError, match='finite'):
        report([trace((np.nan,))])
    with pytest.raises(ValueError, match='right-handed'):
        report([trace()], lift=[0, 0, -1])


def test_diagnostic_uses_selected_coefficients_and_leaves_solver_outputs_unchanged():
    model = parse_asw(Path('examples/rectangular.asw').read_text())
    condition = FlightCondition(alpha=6., mach=0., circulation_modes={1: 3})
    baseline = solve_rigid(model, condition, 12)
    mesh = model_meshes(model, 12)
    gamma = [s['circulation'] for s in baseline['strips']]
    diagnostic = evaluate_aerodynamics(model, condition, mesh, circulation=gamma, fourier_wake_diagnostic=True)
    continuous = diagnostic['trefftz']['continuous_fourier']
    assert continuous['available']
    for key in ('CL', 'CD', 'CDi', 'efficiency', 'force', 'moment', 'circulation_residual'):
        np.testing.assert_array_equal(diagnostic[key], baseline[key])
    assert 'continuous_fourier' not in baseline['trefftz']
    coefficients = np.array(baseline['circulation_discretization']['coefficients'])
    assert continuous['induced_drag'] == pytest.approx(.125*model.constants[1]*np.pi*np.sum(np.arange(1, 4)*coefficients**2), rel=1e-12)
    # No silent Fourier fit for a pointwise solve, and no use of a deformed
    # curved trace as though it were its straight endpoint chord.
    point = solve_rigid(model, replace(condition, circulation_modes={}), 6, fourier_wake_diagnostic=True)
    assert not point['trefftz']['continuous_fourier']['available']
    basis = CirculationBasis(mesh, condition.circulation_modes)
    mesh[0].rm = mesh[0].rm.copy()
    mesh[0].rm[2, 2] += .01
    invalid = fourier_wake_for_meshes(model, condition, mesh, gamma, basis, model.constants[1], None)
    assert not invalid['available'] and 'curved' in invalid['reason']
    from openswing.ground import GroundPlane
    image = fourier_wake_for_meshes(model, condition, mesh, gamma, basis, model.constants[1], GroundPlane(1, [0, 0, 4]))
    assert not image['available'] and 'images' in image['reason']
