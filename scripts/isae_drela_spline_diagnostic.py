"""Experimental beam-table interpolation for the ST-5 reference diagnostic.

This is not a production interpolation policy. The slopes satisfy C2 continuity
and zero third derivatives on the two end intervals, as specified by Drela's
published SEGSPL/SPLIND equations. Two points give a straight line. Natural
interpolation remains the production default; joint and time tables are not
changed. No model values or derivatives are fitted to archived outputs.
"""
import hashlib
import json
import numpy as np
from scipy.interpolate import CubicHermiteSpline

POLICY = 'diagnostic-drela-segspl-zero-third-v1'


def slopes(t, values):
    """Solve the C2 slope equations with m0+m1=2*first_secant at each end."""
    t, values = np.asarray(t, dtype=float), np.asarray(values, dtype=float)
    if t.ndim != 1 or values.shape != t.shape or len(t) < 2:
        raise ValueError('Expected at least two matching station/value pairs.')
    h = np.diff(t)
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(values)) or np.any(h <= 0):
        raise ValueError('Finite increasing stations and finite values required.')
    secants = np.diff(values)/h
    if len(t) == 2:
        return np.repeat(secants, 2)
    # Derive each interior row by equating the adjacent Hermite second
    # derivatives. A zero cubic term on an end interval gives the end rows.
    lower = np.r_[0., h[1:], 1.]
    upper = np.r_[1., h[:-1], 0.]
    diagonal = np.r_[1., 2*(h[:-1]+h[1:]), 1.]
    rhs = np.r_[2*secants[0], 3*(h[1:]*secants[:-1]+h[:-1]*secants[1:]), 2*secants[-1]]
    for i in range(1, len(t)):
        factor = lower[i]/diagonal[i-1]
        diagonal[i] -= factor*upper[i-1]
        rhs[i] -= factor*rhs[i-1]
    result = np.empty_like(t)
    result[-1] = rhs[-1]/diagonal[-1]
    for i in range(len(t)-2, -1, -1):
        result[i] = (rhs[i]-upper[i]*result[i+1])/diagonal[i]
    return result


def coefficient_signature(model):
    h = hashlib.sha256()
    for beam in model.beams:
        h.update(str(beam.index).encode())
        for name, distribution in sorted(beam.distributions.items()):
            h.update(name.encode())
            for lo, hi, spline in distribution._segments:
                h.update(np.asarray([lo, hi], dtype=float).tobytes())
                h.update(spline.x.tobytes())
                h.update(spline.c.tobytes())
    return h.hexdigest()


def adapt_beam_tables(model):
    """Change compiled beam splines only, before any mesh/network is built.

    The returned object's ordinary equilibrium identity cannot express this
    experimental policy. Callers must not publish its states as app inputs.
    """
    source = model.dumps()
    before = {(b.index, k): (d.t.copy(), d.values.copy())
              for b in model.beams for k, d in b.distributions.items()}
    old_signature = coefficient_signature(model)
    segments = 0
    for beam in model.beams:
        for d in beam.distributions.values():
            compiled = []
            for ids in np.split(np.arange(len(d.t)), np.flatnonzero(np.diff(d.t) == 0)+1):
                t, y = d.t[ids], d.values[ids]
                compiled.append((t[0], t[-1], CubicHermiteSpline(t, y, slopes(t, y))))
                segments += 1
            d._segments = compiled
    for beam in model.beams:
        for key, d in beam.distributions.items():
            t, y = before[(beam.index, key)]
            assert np.array_equal(d.t, t) and np.array_equal(d.values, y)
    assert model.dumps() == source
    model._diagnostic_spline = dict(policy=POLICY, segments=segments,
        source_sha256=hashlib.sha256(source.encode()).hexdigest(),
        natural_coefficients_sha256=old_signature,
        candidate_coefficients_sha256=coefficient_signature(model),
        changes='Compiled beam-table interpolation only; no table, source, joint-law or time-forcing edits.',
        limitation='Generic Drela source routine and archived observables support this candidate; the unavailable ASWING caller is not proven.')
    return model


def seal_diagnostic_result(result):
    """Prevent an experimental state with an unversioned policy from app reuse."""
    state = result.get('equilibrium_state')
    if state is not None:
        state['format'] = 'openswing-diagnostic-only-equilibrium'
        state['diagnostic_interpolation'] = POLICY
        note = 'Not an app restart: this experimental beam interpolation is absent from the production saved-state identity.'
        if note not in state.setdefault('limitations', []):
            state['limitations'].append(note)
    result['diagnostic_only'] = True
    result['diagnostic_interpolation'] = POLICY
    return result


def verify_algebra():
    """Small independent polynomial and continuity invariants; no aircraft solve."""
    checks = []
    grids = [np.array([0., 2.]), np.array([0., .3, 2.]), np.array([-2., -.7, 0., .2, 3.])]
    for t in grids:
        for degree in range(3 if len(t) > 2 else 2):
            polynomial = np.polynomial.Polynomial([.17, -.31, .29][:degree+1])
            y = polynomial(t)
            spline = CubicHermiteSpline(t, y, slopes(t, y))
            samples = np.linspace(t[0], t[-1], 37)
            for derivative in (0, 1, 2):
                error = float(np.max(abs(spline(samples, derivative)-polynomial.deriv(derivative)(samples))))
                checks.append(dict(name=f'n{len(t)}-degree{degree}-derivative{derivative}', error=error, passed=error < 2e-12))
    t = np.array([0., .17, .8, 1.3, 4.])
    y = np.array([1., -.3, .6, .4, -.7])
    s = CubicHermiteSpline(t, y, slopes(t, y))
    h = np.diff(t)
    left_second = 6*s.c[0, :-1]*h[:-1]+2*s.c[1, :-1]
    right_second = 2*s.c[1, 1:]
    errors = dict(interior_C2=float(np.max(abs(left_second-right_second))),
        first_third_derivative=float(abs(6*s.c[0, 0])), last_third_derivative=float(abs(6*s.c[0, -1])),
        interpolation=float(np.max(abs(s(t)-y))))
    checks.extend(dict(name=k, error=v, passed=v < 2e-11) for k, v in errors.items())
    assert all(r['passed'] for r in checks)
    return dict(status='PASS_ALGEBRA_ONLY', checks=checks, physical_solves=0)


if __name__ == '__main__':
    print(json.dumps(verify_algebra(), indent=2))
