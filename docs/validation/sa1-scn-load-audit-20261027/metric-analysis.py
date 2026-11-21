#!/usr/bin/env python3
"""Conditional CASEI geometry diagnostic, stdlib only; no aerodynamic solve."""
from bisect import bisect_right
from decimal import Decimal as D
from hashlib import sha256
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT/'.reference/sa1-public-history-20261027/scn-study'


def pin(p):
    b = p.read_bytes()
    return {'path': str(p.relative_to(ROOT)), 'bytes': len(b), 'sha256': sha256(b).hexdigest()}


def spline(grid, values):
    """Natural cubic second derivatives: tridiagonal solve, explicit endpoints."""
    n = len(grid)
    h = [grid[i+1]-grid[i] for i in range(n-1)]
    lower = [0.0]*n
    diagonal = [1.0]*n
    upper = [0.0]*n
    rhs = [0.0]*n
    for i in range(1, n-1):
        lower[i], diagonal[i], upper[i] = h[i-1], 2*(h[i-1]+h[i]), h[i]
        rhs[i] = 6*((values[i+1]-values[i])/h[i]-(values[i]-values[i-1])/h[i-1])
    for i in range(1, n):
        factor = lower[i]/diagonal[i-1]
        diagonal[i] -= factor*upper[i-1]
        rhs[i] -= factor*rhs[i-1]
    second = [0.0]*n
    second[-1] = rhs[-1]/diagonal[-1]
    for i in reversed(range(n-1)):
        second[i] = (rhs[i]-upper[i]*second[i+1])/diagonal[i]

    def derivative(t):
        i = max(0, min(n-2, bisect_right(grid, t)-1))
        width = h[i]
        a, b = (grid[i+1]-t)/width, (t-grid[i])/width
        return ((values[i+1]-values[i])/width
                + width*((1-3*a*a)*second[i]+(3*b*b-1)*second[i+1])/6)
    return derivative


def integrate(f, a, b, tolerance=1e-13):
    def rec(a, b, fa, fm, fb, whole, tol, depth):
        mid = (a+b)/2
        fl, fr = f((a+mid)/2), f((mid+b)/2)
        left, right = (mid-a)*(fa+4*fl+fm)/6, (b-mid)*(fm+4*fr+fb)/6
        error = left+right-whole
        if abs(error) <= 15*tol or depth == 0:
            return left+right+error/15
        return (rec(a, mid, fa, fl, fm, left, tol/2, depth-1)
                + rec(mid, b, fm, fr, fb, right, tol/2, depth-1))
    if a == b:
        return 0.0
    fa, fm, fb = f(a), f((a+b)/2), f(b)
    return rec(a, b, fa, fm, fb, (b-a)*(fa+4*fm+fb)/6, tolerance, 24)


def bounds(token):
    x = D(token)
    h = D(5).scaleb(x.as_tuple().exponent-1)
    return x-h, x+h


def main():
    model = SOURCE/'CASEI.asw'
    lines = model.read_text().splitlines()
    geometry = []
    for line in lines[40:121]:
        geometry.append(list(map(float, line.split())))
    grid, x = [r[0] for r in geometry], [r[1] for r in geometry]
    assert len(geometry) == 81 and all(r[0] == r[2] and r[3] == 0 for r in geometry)
    dx = spline(grid, x)
    # Source geometry has y=t, z=0. No model-dependent aerodynamic field is made.
    speed = lambda t: math.hypot(dx(t), 1.0)
    sy = lambda t: 1/speed(t)
    sx = lambda t: dx(t)/speed(t)
    def arc(a, b, tolerance=1e-13):
        knots = [a]+[t for t in grid if a < t < b]+[b]
        return math.fsum(integrate(speed, u, v, tolerance) for u, v in zip(knots, knots[1:]))

    sanity = {
        'linear_derivative_error': max(abs(spline([0.,1.,2.], [1.,3.,5.])(t)-2.) for t in [0.,.3,1.,1.7,2.]),
        'quadratic_integral_error': abs(integrate(lambda t: t*t, 0., 1.)-1/3),
        'unit_tangent_max_error': max(abs(sx(t)**2+sy(t)**2-1) for t in grid)}
    assert max(sanity.values()) < 1e-14
    arc_refinement = abs(arc(0, grid[-1], 1e-11)-arc(0, grid[-1], 1e-13))
    assert arc_refinement < 1e-10
    results = []
    for n in (6, 12, 96):
        path = SOURCE/f'SCN/ellip_A8_N{n}.txt'
        text = path.read_text()
        rows = []
        for line_number, line in enumerate(text.splitlines(), 1):
            tok = line.split()
            if len(tok) != 10:
                continue
            try:
                vals = list(map(float, tok))
            except ValueError:
                continue
            rows.append({'line': line_number, 'tokens': tok, 'v': vals})
        positive = [r for r in rows if r['v'][0] > 0]
        center = [r for r in rows if r['v'][0] == 0][-1]
        half = [center]+positive
        xx, yy = x[0], 0.0
        checks = []
        total_normal, total_wind_projected = 0.0, 0.0
        for a, b in zip(half, half[1:]):
            u, v = a['v'][0], b['v'][0]
            ds = arc(u, v)
            xx += (sx(u)+sx(v))*ds/2
            yy += (sy(u)+sy(v))*ds/2
            fa = a['v'][8]
            total_normal += fa*ds*2
            total_wind_projected += fa*ds*math.cos(math.radians(8))*2
            fnlo, fnhi = bounds(a['tokens'][6]); bnlo, bnhi = bounds(b['tokens'][6])
            flo, fhi = 10*(fnlo-bnhi), 10*(fnhi-bnlo)
            falo, fahi = bounds(a['tokens'][8])
            aylo, ayhi = bounds(a['tokens'][1]); bylo, byhi = bounds(b['tokens'][1])
            minimum_dy = max(D(0), bylo-ayhi)
            effective_length = (flo/fahi, fhi/falo)
            checks.append({'lines': [a['line'], b['line']], 't': v,
                'native_y_token': b['tokens'][1], 'box_y_natural_spline': yy,
                'box_y_minus_native_y': yy-b['v'][1], 'within_y_print_half_unit_central_t_only': abs(yy-b['v'][1]) <= 5e-5,
                'box_x_natural_spline_unobserved': xx, 'natural_spline_arc_interval': ds,
                'printed_delta_t': v-u, 'printed_delta_y': b['v'][1]-a['v'][1],
                'Fn_decrement': 10*(a['v'][6]-b['v'][6]), 'f_aero': fa,
                'Fn_decrement_over_f_aero_print_interval': list(map(str, effective_length)),
                'minimum_delta_y_from_print_bounds': str(minimum_dy),
                'normal_density_single_product_impossible_for_any_arc': effective_length[1] < minimum_dy})
        fz = float(re.search(r'sum Fz\s*:\s*([^ ]+)', text).group(1))
        fx = float(re.search(r'sum Fx\s*:\s*([^ ]+)', text).group(1))
        lift = float(re.search(r'Lift\s*:\s*([^ ]+)', text).group(1))
        results.append({'source': pin(path), 'N': n, 'positive_half_intervals': len(checks),
            'maximum_printed_cl': max(r['v'][7] for r in rows),
            'native_Lift': lift, 'body_force_projected_to_Lift': fz*math.cos(math.radians(8))-fx*math.sin(math.radians(8)),
            'natural_spline_half_arc': arc(0, grid[-1]),
            'max_abs_box_y_minus_native': max(abs(c['box_y_minus_native_y']) for c in checks),
            'y_checks_within_print_half_unit_central_t_only': sum(c['within_y_print_half_unit_central_t_only'] for c in checks),
            'normal_density_single_product_impossible_count_positive_half': sum(c['normal_density_single_product_impossible_for_any_arc'] for c in checks),
            'sum_f_aero_times_natural_arc': total_normal,
            'sum_f_aero_times_natural_arc_cos_freestream_alpha': total_wind_projected,
            'native_sum_Fz': fz, 'intervals': checks})
    out = {
        'format': 'openswing.isae.scn-conditional-metric-audit', 'version': 1,
        'pins': [pin(Path(__file__).resolve()), pin(model), pin(SOURCE/'SCN_ellip.sh'),
                 pin(ROOT/'.reference/aswing_doc.txt'), pin(ROOT/'.reference/asw_theory.txt')],
        'qualifications': [
            'CASEI-to-output pairing remains conditional; matching names/headers and retained driver are not an execution receipt.',
            'Natural spline boundary conditions are declared for this diagnostic; historical boundary conditions and exact unprinted node t values are unknown.',
            'The box geometry uses literal x(t), y=t, z=0 and integrates Eq48/50 with endpoint unit tangents and spline arc length. No aerodynamic or structural equilibrium solve is run.',
            'Central printed t values are used. A within-half-unit y result is a diagnostic agreement, not rigorous propagation of all node-t rounding.',
            'The cos(8deg) alternative treats f_aero as a freestream-normal lift magnitude only to test that particular interpretation; the manual instead calls it wing-normal lift. No projection is chosen by numerical closeness.',
            'The model excludes prescribed profile drag and mass loads. All shown cl are well below the stall limits. Tiny smooth-stall leakage and unsaved fields are not asserted identically zero.',
            'The effective-length lower-bound rejection is independent of spline boundary conditions, conditioned only on Fn being z force, f_aero being the complete normal density, and a single interval product.'],
        'source_facts': {'geometry_lines': [40,121], 'geometry_count': len(geometry),
            'max_abs_x_plus_chord_over_4': max(abs(r[1]+r[4]/4) for r in geometry),
            'zero_mass_blocks_start_lines': [544,628], 'zero_rigidity_means_infinity_manual_lines': [1200,1204],
            'zero_twist_alpha_Cm_lines': [712,714], 'zero_Cdf_Cdp_and_stall_limits_lines': [717,719],
            'theory_true_arc_definition_lines': [2257,2261]},
        'scalar_sanity_checks': sanity, 'arc_quadrature_refinement_abs_1e11_vs_1e13': arc_refinement,
        'files': results}
    (HERE/'metric-report.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps({'sanity': sanity, 'files': [{k:v for k,v in r.items() if k not in ('intervals','source')} for r in results], 'report': pin(HERE/'metric-report.json')}, indent=2))


if __name__ == '__main__':
    main()
