"""Prescribed-circulation audit of curved bound-line section velocities.

This is an isolated mechanism control, not a new ASWING force model or a
reproduction of Li et al.'s solved wings. Uses production zero-core kernels,
independent line integration, and analytic straight-wing/curvature limits.
Run as one small foreground job with one BLAS thread; never solves Gamma.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import finite_vortex, semi_infinite_vortex


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [portable(v) for v in value]
    return value


def write(path, value):
    path.write_text(json.dumps(portable(value), indent=2, allow_nan=False) + '\n')


def total(array):
    return np.array([math.fsum(array[:, k]) for k in range(3)])


def bound_integral(point, a, b, *, omit=None):
    """Independent direct quadrature of dl cross r / (4 pi r^3)."""
    if omit is not None:
        keep = np.arange(len(a)) != omit
        a, b = a[keep], b[keep]
    u, w = np.polynomial.legendre.leggauss(80)
    u, w = (u + 1.) / 2., w / 2.
    d = b - a
    r = point - a[:, None, :] - u[None, :, None] * d[:, None, :]
    value = np.cross(d[:, None, :], r) / np.linalg.norm(r, axis=2)[:, :, None]**3
    return total(np.einsum('q,eqk->ek', w, value)) / (4 * np.pi)


def run_case(kind, count, radius, half_angle, chord, gamma, ambient, density):
    # Odd N places one central straight panel across the symmetry plane.
    # Its arithmetic midpoint is also its Glauert-angle midpoint. The local
    # beam span there is +y for each of these exactly symmetric controls.
    theta = np.linspace(-half_angle, half_angle, count + 1)
    xyz = np.zeros((count + 1, 3))
    if kind == 'straight':
        xyz[:, 1] = radius * theta
    else:
        xyz[:, 1] = radius * np.sin(theta)
        xyz[:, 0 if kind == 'sweep' else 2] = radius * (1 - np.cos(theta))
    a, b = xyz[:-1], xyz[1:]
    middle = count // 2
    hv = (a[middle] + b[middle]) / 2
    cp = hv + np.array([chord / 2, 0., 0.])
    direction = np.array([1., 0., 0.])
    tangent = np.array([0., 1., 0.])
    assert np.linalg.norm(np.cross(hv - a[middle], b[middle] - a[middle])) < 1e-15
    assert np.linalg.norm(np.cross(tangent, b[middle] - a[middle])) < 1e-15
    # Own straight bound segment has zero self-field, omitted before summation.
    keep = np.arange(count) != middle
    bound_hv = gamma * total(finite_vortex(hv, a[keep], b[keep]))
    bound_cp = gamma * total(finite_vortex(cp, a, b))
    delta = cp - hv
    perpendicular = delta - (delta @ tangent) * tangent
    infinite_2d = gamma / (2*np.pi) * np.cross(tangent, perpendicular) / (perpendicular @ perpendicular)
    corrected_bound = bound_cp - infinite_2d
    wakes = []
    wake_errors = []
    for point in (hv, cp):
        discrete = gamma * total(semi_infinite_vortex(point, b, direction)
                                 - semi_infinite_vortex(point, a, direction))
        # With constant Gamma all interior rays cancel exactly as vortex
        # sources: an independent endpoint expression isolates the bound field.
        ends = gamma * (semi_infinite_vortex(point, b[-1], direction)
                        - semi_infinite_vortex(point, a[0], direction))
        wake_errors.append(float(np.max(abs(discrete - ends))))
        np.testing.assert_allclose(discrete, ends, atol=2e-13, rtol=1e-12)
        wakes.append(ends)
    reference_hv = gamma * bound_integral(hv, a, b, omit=middle)
    reference_cp = gamma * bound_integral(cp, a, b)
    quadrature_error = max(float(np.max(abs(bound_hv-reference_hv))),
                           float(np.max(abs(bound_cp-reference_cp))))
    np.testing.assert_allclose(bound_hv, reference_hv, atol=2e-11, rtol=1e-10)
    np.testing.assert_allclose(bound_cp, reference_cp, atol=2e-11, rtol=1e-10)
    raw_velocity = ambient + wakes[0] + bound_hv
    corrected_velocity = ambient + wakes[0] + corrected_bound
    raw_force = density * gamma * np.cross(raw_velocity, tangent)
    corrected_force = density * gamma * np.cross(corrected_velocity, tangent)
    # Component calculation independently checks the common local force rule.
    component_error = 0.
    for v, f in ((raw_velocity, raw_force), (corrected_velocity, corrected_force)):
        expected = density * gamma * np.array([-v[2], 0., v[0]])
        component_error = max(component_error, float(np.max(abs(f-expected))))
        np.testing.assert_allclose(f, expected, atol=1e-14, rtol=1e-14)
    straight_error = None
    if kind == 'straight':
        length, h = radius * half_angle, chord / 2
        exact_bound = np.array([0., 0., -gamma/(2*np.pi*h)*length/np.hypot(length, h)])
        straight_error = float(np.max(abs(bound_cp-exact_bound)))
        np.testing.assert_allclose(bound_cp, exact_bound, atol=2e-13, rtol=1e-12)
        np.testing.assert_array_equal(bound_hv, np.zeros(3))
    return dict(kind=kind, panels=count, force_point=hv, control_point=cp,
                bound_at_force_point=bound_hv, bound_at_control_point=bound_cp,
                infinite_2d_at_control_point=infinite_2d,
                corrected_bound=corrected_bound, wake_at_force_point=wakes[0],
                wake_at_control_point=wakes[1], raw_force_velocity=raw_velocity,
                corrected_force_velocity=corrected_velocity,
                raw_force_per_length=raw_force,
                corrected_force_per_length=corrected_force,
                control_point_velocity=ambient+bound_cp+wakes[1],
                inner_control_point_velocity=ambient+corrected_bound+wakes[1],
                quadrature_max_error=quadrature_error,
                wake_telescoping_max_error=max(wake_errors),
                force_component_max_error=component_error,
                straight_analytic_max_error=straight_error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory.')
    args.output.mkdir(parents=True)
    counts = [15, 31, 63, 127, 255, 511]
    radius, half_angle, chord, gamma, density = 10., np.pi/6, 1., 1., 1.225
    ambient = 10 * np.array([np.cos(np.deg2rad(5)), 0., np.sin(np.deg2rad(5))])
    paths = sorted(ROOT.glob('openswing/**/*.py')) + [ROOT/'docs/validation/ISAE_STATUS.md',
                    ROOT/'docs/validation/isae-progress-scopes.json']
    pins = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    plan = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        previous_turn='progress: primary literature and fixed-Gamma force-integral singularities established',
        unchanged_pins=pins, driver_sha256=sha(Path(__file__)), panels=counts,
        geometries=['straight', 'sweep', 'dihedral'], radius=radius,
        half_angle=half_angle, chord=chord, constant_circulation=gamma,
        ambient_velocity=ambient, density=density, core=0., mach=0.,
        influence_wind=[1.,0.,0.], new_circulation_solves=0,
        scope='Central section field/force only. Constant Gamma is a mechanism control, not a solved wing or tip loading.',
        force_rule='rho Gamma V cross section_span, per length; Gamma held fixed for both velocities.',
        corrected_bound_rule='B3D(cp)-Gamma/(2 pi) s cross r_perp / |r_perp|^2; cp=hv+c/2 xhat.',
        correction_scope='Li et al. 2020 steady bound correction only; not a full MIRAS or ASWING implementation.',
        source_documents={name: sha(ROOT/name) for name in
            ['.reference/asw_theory.txt', '.reference/aswing_doc.txt']},
        gates=dict(independent_bound_integration_atol=2e-11,
                   independent_bound_integration_rtol=1e-10,
                   final_curved_log_increment_relative_error=.005,
                   final_corrected_increment_over_raw_increment=.02))
    write(args.output/'plan.json', plan)
    shutil.copyfile(__file__, args.output/'driver-used.py')
    start = time.monotonic()
    rows = []
    try:
        for kind in plan['geometries']:
            for count in counts:
                rows.append(run_case(kind, count, radius, half_angle, chord, gamma, ambient, density))
        increments = []
        for kind in ('sweep', 'dihedral'):
            selected = [r for r in rows if r['kind'] == kind]
            curvature = np.array([1., 0., 0.]) if kind == 'sweep' else np.array([0., 0., 1.])
            coefficient = gamma/(4*np.pi*radius) * np.cross([0., 1., 0.], curvature)
            for first, second in zip(selected[:-1], selected[1:]):
                actual = second['bound_at_force_point'] - first['bound_at_force_point']
                expected = coefficient * np.log(second['panels']/first['panels'])
                corrected = second['corrected_bound'] - first['corrected_bound']
                error = np.linalg.norm(actual-expected)/np.linalg.norm(expected)
                ratio = np.linalg.norm(corrected)/np.linalg.norm(actual)
                increments.append(dict(kind=kind, first=first['panels'], second=second['panels'],
                    analytic_log_coefficient=coefficient, predicted_increment=expected,
                    raw_increment=actual, corrected_increment=corrected,
                    log_increment_relative_error=error, corrected_over_raw_increment=ratio))
                if second['panels'] == counts[-1]:
                    assert error < plan['gates']['final_curved_log_increment_relative_error']
                    assert ratio < plan['gates']['final_corrected_increment_over_raw_increment']
        limits = []
        for semispan in (10., 100., 1000.):
            h = chord/2
            point = np.array([h, 0., 0.])
            finite = gamma * finite_vortex(point, np.array([0.,-semispan,0.]), np.array([0.,semispan,0.]))
            infinite = np.array([0.,0.,-gamma/(2*np.pi*h)])
            # Rationalized analytic finite/infinite difference, no cancellation.
            radius_to_end = np.hypot(semispan, h)
            expected = gamma/(2*np.pi*h) * h*h/(radius_to_end*(radius_to_end+semispan))
            np.testing.assert_allclose(finite-infinite, [0.,0.,expected], atol=2e-16, rtol=1e-8)
            limits.append(dict(semispan=semispan, correction=finite-infinite,
                               analytic_correction=expected))
        for name, digest in pins.items():
            assert sha(ROOT/name) == digest, name
        result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), rows=rows,
                      mesh_increments=increments, infinite_span_limits=limits,
                      wall_seconds=time.monotonic()-start,
                      maximum_independent_quadrature_error=max(r['quadrature_max_error'] for r in rows),
                      maximum_wake_telescoping_error=max(r['wake_telescoping_max_error'] for r in rows),
                      new_circulation_solves=0, unchanged_pin_count=len(pins),
                      production_change=False, isae_fraction_change=False)
        write(args.output/'results.json', result)
        write(args.output/'verification.json', dict(completed_utc=datetime.now(timezone.utc).isoformat(),
            status='verified', unchanged_pin_count=len(pins),
            artifacts={p.name: sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}))
        print(json.dumps(portable(dict(status='verified', cases=len(rows),
            seconds=result['wall_seconds'], max_integral_error=result['maximum_independent_quadrature_error'],
            final_increments=[r for r in increments if r['second']==counts[-1]]))))
    except Exception as exc:
        write(args.output/'failure.json', dict(error_type=type(exc).__name__, error=str(exc),
                                             observed_utc=datetime.now(timezone.utc).isoformat(), rows=rows))
        raise


if __name__ == '__main__':
    main()
