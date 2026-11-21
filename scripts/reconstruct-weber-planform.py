"""Reconstruct the published Weber/Brebner planform without an aerodynamic fit.

ARC R&M 2882, Part II, Table 1 (printed p.42 / PDF p.43) gives the tip
coordinates. Figure 1 (printed p.75 / PDF p.76) supplies their origin and
the three finite spans. No ASWING solver, spline or mesh code is used here.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.integrate import quad
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/validation/weber-planform'
F = Fraction
TIP_Y = '0 .80 1.43 2.00 2.40 2.78 3.08 3.35 3.60 3.80 4.00 4.12 4.28 4.40 4.50 4.60 4.68 4.75 4.80 4.86 4.92 4.95 4.98 5.00 5.00 5.00'.split()
TIP = [(F(x), F(y)) for x, y in enumerate(TIP_Y)]
INCH = F('0.0254')


def integrate_linear(span):
    """Exact rational integration of straight segments between printed points."""
    start = F(span, 2) - 5
    # Constant 20-inch streamwise chord between apex and tip-curve origin.
    area = 20 * start
    quarter_moment = 10 * start**2 + 100 * start
    centroid_moment = 10 * start**2 + 200 * start
    for (x0, y0), (x1, y1) in zip(TIP, TIP[1:]):
        # Simpson integration is exact for the quadratic chord*position product.
        weights = (F(1, 6), F(4, 6), F(1, 6))
        for t, weight in zip((F(0), F(1, 2), F(1)), weights):
            x, y = x0 + t*(x1-x0), y0 + t*(y1-y0)
            chord = 20 + y - x
            dy = weight * (y1-y0)
            assert chord >= 0
            area += chord * dy
            quarter_moment += (start + x + chord/4) * chord * dy
            centroid_moment += (start + x + chord/2) * chord * dy
    return area, quarter_moment/area, centroid_moment/area


def polygon_check(span):
    """Independent shoelace area and centroid of the entire half-wing outline."""
    start = F(span, 2) - 5
    vertices = [(F(0), F(0)), *[(start+x, start+y) for x, y in TIP], (F(20), F(0))]
    pairs = list(zip(vertices, vertices[1:] + vertices[:1]))
    cross = [x0*y1-x1*y0 for (x0, y0), (x1, y1) in pairs]
    twice_area = sum(cross)
    centroid = sum((a[0]+b[0])*c for (a, b), c in zip(pairs, cross))/(3*twice_area)
    return abs(twice_area)/2, centroid, vertices


def integrate_smooth(span, curve):
    """Separate monotone interpolation sensitivity, retaining every printed point."""
    start = span/2-5
    derivative = curve.derivative()
    moments = [20*start, 10*start**2+100*start]
    errors = [0., 0.]
    for x0 in range(25):
        def integrand(x, order):
            y = float(curve(x))
            chord = 20+y-x
            return chord*float(derivative(x))*(1 if order == 0 else start+x+chord/4)
        for order in [0, 1]:
            value, error = quad(integrand, x0, x0+1, args=(order,), epsabs=1e-10, epsrel=1e-12)
            moments[order] += value
            errors[order] += error
    return moments[0], moments[1]/moments[0], errors


def main():
    manifest_path = ROOT/'docs/validation/sa2-sources.json'
    manifest = json.loads(manifest_path.read_text())
    pdf_path = ROOT/'.reference/isae-sa2/arc-rm-2882.pdf'
    specification = manifest['files']['arc-rm-2882.pdf']
    pdf = pdf_path.read_bytes()
    digest = lambda data: hashlib.sha256(data).hexdigest()
    assert len(pdf) == specification['bytes']
    assert digest(pdf) == specification['sha256']
    tip = np.array(TIP, dtype=float)
    curve = PchipInterpolator(tip[:, 0], tip[:, 1])
    samples = np.linspace(0, 25, 1001)
    assert np.all(curve.derivative()(samples) >= -1e-14)
    assert np.max(abs(curve(tip[:, 0])-tip[:, 1])) < 1e-14
    cases = []
    for span, nominal_ar, published_quarter in [(98, 5, '29.30'), (59, 3.04, '19.70'), (38, 2, '14.60')]:
        area, quarter, centroid = integrate_linear(span)
        polygon_area, polygon_centroid, vertices = polygon_check(span)
        assert area == polygon_area and centroid == polygon_centroid
        smooth_area, smooth_quarter, error = integrate_smooth(span, curve)
        # Green's theorem supplies a third, exact area calculation from y(x).
        smooth_green_area = 20*(span/2-5) + float(curve.integrate(0, 25)) - 12.5
        assert abs(smooth_area-smooth_green_area) < 1e-10
        cases.append(dict(
            span_in=span, figure_aspect_ratio=nominal_ar,
            straight_le_end_and_tip_origin_in=[span/2-5]*2,
            half_outline_xy_in=np.array(vertices, dtype=float).tolist(),
            piecewise_linear=dict(area_in2=float(2*area), area_m2=float(2*area*INCH**2),
                                  area_exact_in2=str(2*area), aspect_ratio=float(F(span**2)/(2*area)),
                                  mean_streamwise_chord_in=float(2*area/span),
                                  area_weighted_quarter_chord_x_in=float(quarter),
                                  area_centroid_x_in=float(centroid)),
            monotone_cubic=dict(area_in2=2*smooth_area, aspect_ratio=span**2/(2*smooth_area),
                                area_weighted_quarter_chord_x_in=smooth_quarter,
                                quadrature_error_estimates=error),
            interpolation_area_change_in2=2*(smooth_area-float(area)),
            published_moment_reference_x_in=float(published_quarter),
            quarter_chord_reference_difference_in=float(quarter-F(published_quarter)),
            exact_polygon_area_and_centroid_agree=True))
    result = dict(
        description=__doc__, source=dict(**specification, alternative_url='https://reports.aerade.cranfield.ac.uk/bitstream/handle/1826.2/3441/arc-rm-2882.pdf?isAllowed=y&sequence=1'),
        locations=dict(tip_table=dict(printed=42, pdf=43), coordinate_figure=dict(printed=75, pdf=76),
                       section_and_moment_notes=dict(printed=43, pdf=44)),
        source_sha256={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in [Path(__file__), manifest_path]},
        versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        tip_coordinates_local_xy_in=tip.tolist(),
        interpretation='x points aft, y points outboard, origin at the start of the curved leading edge; the straight trailing edge is x=y+20 in global coordinates. Final repeated y=5 entries are a constant-span edge, not extra span stations. Pressure-tube fairings are excluded.',
        cases=cases,
        archived_SA2_reference_area_m2=1.549,
        archived_reference_area_excess_fraction=1.549/cases[0]['piecewise_linear']['area_m2']-1,
        scope='Independent planform reconstruction and geometry integration only; no aerodynamic calculation, ASWING input conversion or experimental validation claim.',
        limitations=[
            'Straight segments and monotone cubic interpolation are declared reconstructions of rounded table values, not exact recovery of the manufactured curve.',
            'Printed aspect ratios and moment reference locations are retained independently, not used to tune the outline or normalize discrepancies away.',
            'The model used RAE 101 sections along wind. The report records thickness/asymmetry differences and zero-incidence pressure subtraction; a thin ideal section is not an exact experimental reconstruction.',
            'Pressure-tube fairings and their omission for the additional y/c=2.20 measurements need separate treatment.',
            'Normal-section ASWING axis/chord conversion, tunnel correction and sectional aerodynamic parameters remain to be established before a matched solve.'
        ])
    OUTPUT.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    plt.rcParams.update({'font.size': 10, 'svg.hashsalt': 'openswing-weber-planform'})
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 6), gridspec_kw={'width_ratios': [2.2, 1]}, layout='constrained')
    for case, color in zip(cases, ['#176985', '#c27627', '#724b92']):
        vertices = np.array(case['half_outline_xy_in'])
        for sign in [-1, 1]:
            xy = np.column_stack([sign*vertices[:, 1], vertices[:, 0]])
            axes[0].add_patch(Polygon(xy, closed=True, facecolor=color, edgecolor=color, alpha=.18))
            axes[0].plot(xy[:, 0], xy[:, 1], color=color, lw=1,
                         label=f"{case['span_in']} in span · area {case['piecewise_linear']['area_in2']:.2f} in²" if sign == 1 else None)
    axes[0].set(xlabel='Span coordinate y (in)', ylabel='Aft coordinate x (in)',
                xlim=(-53, 53), ylim=(73, -3), title='Primary-table outline, fairings excluded')
    axes[0].set_aspect('equal'); axes[0].legend(loc='lower center', fontsize=8)
    axes[1].plot(curve(samples), samples, label='Monotone cubic', color='#c27627', lw=1.6)
    axes[1].plot(tip[:, 1], tip[:, 0], 'o-', label='Printed points / straight segments',
                 color='#176985', markersize=3, lw=.8)
    axes[1].plot([0, 5], [20, 25], '--', color='#666666', label='Straight trailing edge')
    axes[1].set(xlabel='Local outboard y (in)', ylabel='Local aft x (in)',
                xlim=(-.3, 5.5), ylim=(26, -1), title='Tip coordinates · Part II, Table 1')
    axes[1].legend(loc='upper left', bbox_to_anchor=(-.14, -.12), fontsize=8)
    for ax in axes: ax.grid(alpha=.2)
    fig.suptitle('Weber–Brebner planform reconstruction\nGeometry evidence only; no aerodynamic validation', fontsize=13)
    for suffix in ['.svg', '.pdf', '.png']:
        fig.savefig(OUTPUT.with_suffix(suffix), dpi=160)
    plt.close(fig)
    print(json.dumps(dict(cases=cases, archived_reference_area_excess_fraction=result['archived_reference_area_excess_fraction']), indent=2))


if __name__ == '__main__':
    main()
