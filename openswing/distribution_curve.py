"""Property symmetry and local cubic grafts stored as ordinary ASW stations.

ASW has no documented endpoint-derivative fields. A clamped graft is therefore
resampled until the reloaded spline under the distribution's explicit policy meets both value and slope
tolerances over every polynomial interval, including the unchanged exterior.
This is an explicit approximation, not an assertion about ASWING's editor.
"""
import numpy as np
from scipy.interpolate import CubicSpline
from .asw import AswError, Distribution
from .beam_spline import NATURAL, segment_spline


def symmetry(d, mode, lifting):
    if mode not in ('keep', 'independent', 'positive'):
        raise AswError('Symmetry must be keep, independent, or positive.')
    if mode == 'keep':
        return d
    if d.constant_rigid:
        raise AswError('Automatic symmetry cannot rewrite a constant rigid singleton. Supply an explicit multi-point replacement first.')
    if not lifting:
        raise AswError('Automatic property symmetry requires a lifting surface.')
    if mode == 'independent':
        if d.t[0] != 0:
            return d
        # Two center stations retain the separate half splines, including a
        # center slope corner. Reversing the negative half reverses jump sides.
        values = 2*d.values[0]-d.values[::-1] if d.name == 'y' else d.values[::-1]
        return Distribution(d.name, np.r_[-d.t[::-1], d.t], np.r_[values, d.values], 0,
                            interpolation=d.interpolation)
    if d.t[0] == 0:
        return d
    if d.t[-1] <= 0:
        raise AswError('Mirroring the positive half requires a positive station.')
    positive = d.t > 0
    # Existing positive stations survive. If zero was not a station, add its
    # current value; the new half spline is shown in the ordinary preview.
    return Distribution(d.name, np.r_[0., d.t[positive]],
                        np.r_[d.evaluate(0., side='right'), d.values[positive]], 0,
                        interpolation=d.interpolation)


def _extrema(coefficients):
    """Real stationary locations on the unit interval, including endpoints."""
    c = np.polynomial.polynomial.polytrim(np.asarray(coefficients, dtype=float))
    candidates = [0., 1.]
    if len(c) > 1:
        roots = np.polynomial.polynomial.polyroots(np.arange(1, len(c))*c[1:])
        candidates.extend(float(z.real) for z in roots
                          if abs(z.imag) < 1e-10 and 0 < z.real < 1)
    return np.asarray(candidates)


def _coefficients(spline, left, width):
    # Power coefficients in u=(t-left)/width avoid large station offsets.
    return np.array([spline(left, nu=k)*width**k/f
                     for k, f in enumerate((1, 1, 2, 6))])


def _errors(fitted, regions, knots, length):
    errors = []
    for left, right in zip(knots, knots[1:]):
        width = right-left
        target = next(s for a, b, s in regions if a <= (left+right)/2 <= b)
        delta = _coefficients(fitted, left, width)-_coefficients(target, left, width)
        value = max(abs(np.polynomial.polynomial.polyval(_extrema(delta), delta)))
        slope_coefficients = np.arange(1, 4)*delta[1:]*length/width
        slope = max(abs(np.polynomial.polynomial.polyval(_extrema(slope_coefficients), slope_coefficients)))
        errors.append((float(value), float(slope)))
    return np.asarray(errors)


def graft(d, specification, domain):
    if d.constant_rigid:
        raise AswError('A graft cannot rewrite a constant rigid singleton. Supply an explicit multi-point replacement first.')
    if not isinstance(specification, dict) or set(specification)-{'points', 'tangent', 'tolerance'}:
        raise AswError('A graft accepts points, tangent, and tolerance only.')
    try:
        points = np.asarray(specification.get('points'), dtype=float)
        tolerance = float(specification.get('tolerance', 1e-5))
    except (TypeError, ValueError) as exc:
        raise AswError('Graft points and tolerance must be finite numbers.') from exc
    tangent = specification.get('tangent', True)
    if not isinstance(tangent, bool):
        raise AswError('Graft tangent must be true or false.')
    if not np.isfinite(tolerance) or not 1e-9 <= tolerance <= 1e-2:
        raise AswError('Graft relative tolerance must be between 1e-9 and 0.01.')
    if points.ndim != 2 or points.shape[1] != 2 or not 2 <= len(points) <= 200:
        raise AswError('A graft requires 2 to 200 (station, value) points.')
    if not np.all(np.isfinite(points)):
        raise AswError('Graft points must be finite.')
    points = points[np.argsort(points[:, 0], kind='stable')].copy()
    if np.any(np.diff(points[:, 0]) <= 0):
        raise AswError('Graft stations must be distinct; use doubled table stations to edit a corner.')
    lo = min(float(d.t[0]), float(domain[0]))
    hi = max(float(d.t[-1]), float(domain[1]))
    left, right = points[[0, -1], 0]
    if left < lo or right > hi:
        raise AswError('Graft points must lie within the displayed property domain. Make the halves independent to edit negative stations.')
    if tangent:
        # Joining position and tangent is explicit: the end clicks choose
        # stations; their ordinates snap to the existing exterior curve.
        points[0, 1] = d.evaluate(left, side='left')
        points[-1, 1] = d.evaluate(right, side='right')
        bc = ((1, float(d.evaluate(left, side='left', derivative=1))),
              (1, float(d.evaluate(right, side='right', derivative=1))))
        replacement = CubicSpline(points[:, 0], points[:, 1], bc_type=bc)
    else:
        replacement = segment_spline(points[:, 0], points[:, 1], d.interpolation)
    regions = []
    for i, (a, b, spline) in enumerate(d._segments):
        a = lo if i == 0 else a
        b = hi if i == len(d._segments)-1 else b
        if a < left:
            regions.append((a, min(b, left), spline))
    regions.append((left, right, replacement))
    for i, (a, b, spline) in enumerate(d._segments):
        a = lo if i == 0 else a
        b = hi if i == len(d._segments)-1 else b
        if b > right:
            regions.append((max(a, right), b, spline))
    breaks = {float(t) for t in d.breaks if t < left or t > right}
    if not tangent:
        breaks.update(t for t in (left, right) if lo < t < hi)
    bounds = sorted({lo, hi, *breaks})
    # Magnitude comes from polynomial extrema, not just control points; narrow
    # overshoots cannot be hidden from the error normalization.
    minimum, maximum_value = np.inf, -np.inf
    for a, b, spline in regions:
        sub = sorted({a, b, *[float(t) for t in spline.x if a < t < b]})
        for x, y in zip(sub, sub[1:]):
            c = _coefficients(spline, x, y-x)
            extrema = np.polynomial.polynomial.polyval(_extrema(c), c)
            minimum = min(minimum, float(min(extrema)))
            maximum_value = max(maximum_value, float(max(extrema)))
    scale = maximum_value-minimum or abs(maximum_value) or 1.
    if not np.isfinite(scale) or not np.isfinite(hi-lo):
        raise AswError('Graft range is too large for finite spline arithmetic.')
    output = []
    maximum = np.zeros(2)
    for a, b in zip(bounds, bounds[1:]):
        pieces = [(max(a, x), min(b, y), s) for x, y, s in regions if x < b and y > a]
        knots = np.array(sorted({a, b, *[v for x, y, s in pieces for v in (x, y)],
                               *[float(t) for x, y, s in pieces for t in s.x if x < t < y]}))
        for iteration in range(49):
            if len(output)+len(knots)>4096:
                raise AswError('Graft would exceed 4096 stations. Simplify the distribution first.')
            values = np.array([next(s for x, y, s in pieces if x <= t <= y)(t) for t in knots])
            fitted = segment_spline(knots, values, d.interpolation)
            error = _errors(fitted, pieces, knots, hi-lo)
            if not np.all(np.isfinite(error)):
                raise AswError('Graft cannot resolve finite value and slope errors; revise its scale or station spacing.')
            bad = np.any(error > tolerance*scale, axis=1)
            if not np.any(bad):
                maximum = np.maximum(maximum, np.max(error, axis=0)/scale)
                output.extend(zip(knots.tolist(), values.tolist()))
                break
            if iteration == 48 or len(output)+len(knots)+np.count_nonzero(bad) > 4096:
                raise AswError('Graft cannot meet its value/slope tolerance within 4096 stations. Relax the tolerance or revise the points.')
            midpoints = (knots[:-1][bad]+knots[1:][bad])/2
            updated = np.unique(np.r_[knots, midpoints])
            if len(updated) == len(knots):
                raise AswError('Graft stations are too close to resolve at this tolerance.')
            knots = updated
    data = np.asarray(output)
    result = Distribution(d.name, data[:, 0], data[:, 1], 0, interpolation=d.interpolation)
    report = dict(operation='graft', tangent=tangent, tolerance=tolerance,
                  maximum_relative_value_error=float(maximum[0]),
                  maximum_relative_slope_error=float(maximum[1]),
                  value_scale=scale, slope_length_scale=hi-lo, domain=[lo, hi],
                  stations=len(data), points=points.tolist(),
                  limitation=('Natural-spline station approximation; ASWING endpoint and editor conventions remain unverified.'
                              if d.interpolation == NATURAL else
                              'drela-segspl-v1 station approximation; historical ASWING caller and editor conventions remain unverified.'))
    return result, report
