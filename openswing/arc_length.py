"""Physical material arc of a piecewise cubic beam axis.

Integration cells split every axis spline knot and reflected knot, independently
of the physical mesh. Rigid position jumps contain no material arc. Vectorized
Gauss rules integrate analytic axis derivatives; no chord table or per-panel
``scipy.quad`` call is used. The inverse is bracketed within retained cells.
"""
import hashlib
import numpy as np


_RULES = {n: np.polynomial.legendre.leggauss(n) for n in (8, 16)}
_EPS = np.finfo(float).eps
_RTOL = 2e-13


def _signature(beam):
    """Include mutable inputs actually used by Beam.position(derivative=1)."""
    h = hashlib.sha256(repr((beam.domain, beam.lifting)).encode())
    for name in ('x', 'y', 'z'):
        d = beam.distributions.get(name)
        h.update(name.encode())
        if d is None:
            continue
        h.update(d.name.encode())
        for array in (d.t, d.values):
            h.update(np.asarray(array).tobytes())
        for lo, hi, spline in d._segments:
            h.update(repr((lo, hi, spline.extrapolate, spline.axis)).encode())
            for array in (spline.x, spline.c):
                h.update(repr((array.shape, array.dtype.str)).encode())
                h.update(array.tobytes())
    return h.digest()


def _axis_knots(beam):
    lo, hi = beam.domain
    points = [lo, hi]
    for name in ('x', 'y', 'z'):
        d = beam.distributions.get(name)
        if d is None:
            continue
        knots = np.unique(np.r_[d.t, *[spline.x for _, _, spline in d._segments],
                                [v for a, b, _ in d._segments for v in (a, b)]])
        points.extend(knots)
        if beam.lifting and d.t[0] == 0:
            points.extend(-knots)
            points.append(0.)
    return np.array(sorted({float(t) for t in points if lo <= t <= hi}))


class MaterialArc:
    """A monotone material coordinate, with error-checked local quadrature."""
    def __init__(self, beam):
        self.beam = beam
        self.knots = _axis_knots(beam)
        lo, hi = beam.domain
        if not np.isfinite(hi-lo) or hi <= lo:
            raise ValueError(f'Beam {beam.index} has an empty parameter range.')
        first = self._quadrature(self.knots[:-1], self.knots[1:], 16)
        self.mean_speed = float(np.sum(first)/(hi-lo))
        left, right, lengths, _, errors = self._refine(self.knots[:-1], self.knots[1:])
        order = np.argsort(left)
        left, right, lengths = left[order], right[order], lengths[order]
        self.t = np.r_[left, right[-1]]
        self.s = np.r_[0., np.cumsum(lengths)]
        self.lengths = lengths
        self.total = float(self.s[-1])
        self.estimated_error = float(np.sum(errors))
        if (not np.isfinite(self.total) or self.total <= 1e-12
                or np.any(lengths <= 0) or np.any(np.diff(self.s) <= 0)):
            raise ValueError(f'Beam {beam.index} has zero-length geometry.')

    def _quadrature(self, left, right, order):
        x, w = _RULES[order]
        width = right-left
        t = left[:, None]+width[:, None]*((x+1)/2)
        velocity = self.beam.position(t, derivative=1)
        speed = np.linalg.norm(velocity, axis=-1)
        if not np.all(np.isfinite(speed)):
            raise ValueError(f'Beam {self.beam.index}: nonfinite axis derivative.')
        # The Gauss rule integrates a constant exactly. Factoring out that
        # constant avoids a batch/BLAS-dependent sum of its repeated samples,
        # which otherwise adds spurious strain to a straight rigid beam.
        # The minimum keeps the remaining samples nonnegative, so this also
        # avoids cancellation when the derivative norm varies strongly.
        baseline=np.min(speed,axis=1)
        return width*(baseline+((speed-baseline[:,None])@w)/2)

    def _refine(self, left, right):
        """One batched adaptive calculation; retain parent query indices."""
        left, right = np.asarray(left).ravel(), np.asarray(right).ravel()
        ids = np.arange(len(left))
        pieces = []
        for _ in range(48):
            fine = self._quadrature(left, right, 16)
            coarse = self._quadrature(left, right, 8)
            error = abs(fine-coarse)
            # Relative integral error plus a roundoff budget distributed by
            # parameter width. The latter also permits isolated zero speed.
            tolerance = _RTOL*abs(fine)+32*_EPS*self.mean_speed*(right-left)
            accept = error <= tolerance
            if np.any(accept):
                pieces.append((left[accept], right[accept], fine[accept], ids[accept], error[accept]))
            if np.all(accept):
                return tuple(np.concatenate([p[i] for p in pieces]) for i in range(5))
            left, right, ids = left[~accept], right[~accept], ids[~accept]
            middle = left+(right-left)/2
            if np.any((middle == left) | (middle == right)) or len(left) > 65536:
                break
            left, right, ids = (np.r_[left, middle], np.r_[middle, right], np.r_[ids, ids])
        raise ValueError(f'Beam {self.beam.index}: material arc quadrature did not converge.')

    def _integral(self, left, right):
        shape = np.shape(left)
        left, right = np.asarray(left).ravel(), np.asarray(right).ravel()
        if not len(left):
            return np.empty(shape)
        _, _, value, ids, _ = self._refine(left, right)
        return np.bincount(ids, weights=value, minlength=len(left)).reshape(shape)

    def _checked(self, values, upper, lower=0.):
        values = np.asarray(values, dtype=float)
        if not np.all(np.isfinite(values)) or np.any(values < lower) or np.any(values > upper):
            raise ValueError('Material arc query lies outside the beam domain.')
        return values

    def at(self, t):
        """Arc from the domain start; a position jump contributes exactly zero."""
        t = self._checked(t, self.t[-1], self.t[0])
        ids = np.clip(np.searchsorted(self.t, t, side='right')-1, 0, len(self.lengths)-1)
        result = self.s[ids]+self._integral(self.t[ids], t)
        return np.where(t == self.t[-1], self.total, result)

    def between(self, start, end):
        """Direct short-interval lengths avoid subtracting two large arcs."""
        start, end = np.broadcast_arrays(self._checked(start, self.t[-1], self.t[0]),
                                         self._checked(end, self.t[-1], self.t[0]))
        if np.any(end < start):
            raise ValueError('Material arc interval is reversed.')
        a = np.clip(np.searchsorted(self.t, start, side='right')-1, 0, len(self.lengths)-1)
        b = np.clip(np.searchsorted(self.t, end, side='left')-1, 0, len(self.lengths)-1)
        same = a >= b
        # Same-cell queries need only one integration, including zero width.
        result = self._integral(start, np.where(same, end, self.t[a+1]))
        different = ~same
        if np.any(different):
            result = np.asarray(result).copy()
            # Sum retained cell lengths directly: a short interval may cross
            # several knots far from the arc origin. Prefix subtraction would
            # discard its relative accuracy even when quadrature is exact.
            middle = np.array([np.sum(self.lengths[i+1:j])
                               for i, j in zip(a[different], b[different])])
            result[different] += middle+self._integral(self.t[b[different]], end[different])
        return result

    def inverse(self, s):
        """Bracketed Newton inversion of the integrated, positive speed."""
        s = self._checked(s, self.total)
        shape = s.shape
        s = s.ravel()
        ids = np.clip(np.searchsorted(self.s, s, side='right')-1, 0, len(self.lengths)-1)
        left, right = self.t[ids].copy(), self.t[ids+1].copy()
        target = s-self.s[ids]
        t = left+(right-left)*(target/self.lengths[ids])
        done = (s == 0) | (s == self.total) | (target == 0)
        t[s == 0], t[s == self.total] = self.t[0], self.t[-1]
        for _ in range(96):
            active = np.flatnonzero(~done)
            if not len(active):
                return t.reshape(shape)
            q = t[active]
            error = self._integral(self.t[ids[active]], q)-target[active]
            left[active] = np.where(error < 0, q, left[active])
            right[active] = np.where(error > 0, q, right[active])
            speed = np.linalg.norm(self.beam.position(q, derivative=1), axis=-1)
            correction = np.divide(error, speed, out=np.full_like(error, np.inf), where=speed > 0)
            trial = q-correction
            bounded = (trial > left[active]) & (trial < right[active]) & np.isfinite(trial)
            trial = np.where(bounded, trial, left[active]+(right[active]-left[active])/2)
            # Scale by requested local arc, not the entire cell: near a zero
            # endpoint speed, a tiny positive target still needs inversion.
            converged = (abs(error) <= 8*_EPS*abs(target[active])) | (q-correction == q)
            adjacent = np.nextafter(left[active], right[active]) >= right[active]
            if np.any(adjacent):
                # Once the bracket contains no other representable parameter,
                # return its best endpoint even if its arc rounds differently.
                close = active[adjacent]
                eleft = abs(self._integral(self.t[ids[close]], left[close])-target[close])
                eright = abs(self._integral(self.t[ids[close]], right[close])-target[close])
                t[close] = np.where(eleft <= eright, left[close], right[close])
                converged |= adjacent
            done[active[converged]] = True
            t[active[~converged]] = trial[~converged]
        raise ValueError(f'Beam {self.beam.index}: material arc inversion did not converge.')


def material_arc(beam):
    """Reuse the map only while the actual axis evaluation inputs match."""
    signature = _signature(beam)
    cached = getattr(beam, '_material_arc_cache', None)
    if cached is None or cached[0] != signature:
        cached = (signature, MaterialArc(beam))
        beam._material_arc_cache = cached
    return cached[1]
