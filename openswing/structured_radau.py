"""Sparse modified Newton for the original three-stage Radau equations.

State and rate partials share the final stage's current chart. The state
partial uses the same lagged nonlocal fields as structured BDF; the rate
partial differentiates the continuous residual at fixed state. This is a
Newton approximation only. All three original stage residuals still decide
acceptance, and the ordinary full collocation tangent remains the fallback.

Only the constant 3-by-3 stage matrix is diagonalized. No aircraft modes or
mass inverse enter the two full-size shifted beam/frame factorizations.
"""
import numpy as np

from .structured_static import StructuredMatrix
from . import structured_time


def eligible(chart):
    from .nonlinear_initial import InitialSystem
    return type(chart) is InitialSystem and structured_time.eligible(chart.system)


def shifted(state, rate, shift):
    return StructuredMatrix(
        state.mechanical + shift * rate.mechanical,
        state.force_circulation + shift * rate.force_circulation,
        state.flow_geometry + shift * rate.flow_geometry,
        state.circulation + shift * rate.circulation)


def product(matrix, values):
    """Multiply already-permuted columns without a global dense matrix."""
    split = matrix.mechanical.shape[0]
    return np.concatenate([
        matrix.mechanical @ values[:split] + matrix.force_circulation @ values[split:],
        matrix.flow_geometry @ values[:split] + matrix.circulation @ values[split:]])


class Factorization:
    def __init__(self, state, rate, permutation, inverse, step):
        self.state, self.rate = state, rate
        self.permutation = np.asarray(permutation)
        self.inverse = np.asarray(inverse, dtype=float)
        self.step = float(step)
        self.size = len(self.permutation)
        if (self.inverse.shape != (3, 3) or not np.isfinite(self.step)
                or self.step <= 0 or not np.all(np.isfinite(self.inverse))
                or not np.array_equal(np.sort(self.permutation), np.arange(self.size))):
            raise ValueError('Invalid structured Radau coordinates.')
        eigenvalues, vectors = np.linalg.eig(self.inverse)
        real = np.flatnonzero(abs(eigenvalues.imag) < 1e-12)
        positive = np.flatnonzero(eigenvalues.imag > 1e-12)
        if len(real) != 1 or len(positive) != 1:
            raise ValueError('Unsupported Radau stage spectrum.')
        ir, ic = real[0], positive[0]
        v0, v1 = vectors[:, ir].real.copy(), vectors[:, ic].copy()
        v0 /= v0[np.argmax(abs(v0))]
        v1 /= v1[np.argmax(abs(v1))]
        self.transform = np.column_stack([v0, v1, v1.conj()])
        self.reverse = np.linalg.inv(self.transform)
        mu = np.array([eigenvalues[ir].real, eigenvalues[ic], eigenvalues[ic].conjugate()])
        recovered = self.transform @ np.diag(mu) @ self.reverse
        if np.max(abs(recovered-self.inverse)) > 1e-12 * max(1., np.max(abs(self.inverse))):
            raise ValueError('Radau stage transformation failed its identity check.')
        self.real = structured_time.Factorization(
            shifted(state, rate, mu[0].real/self.step), self.permutation)
        self.complex = structured_time.Factorization(
            shifted(state, rate, mu[1]/self.step), self.permutation)

    def solve(self, rhs):
        rhs = np.asarray(rhs)
        if rhs.shape != (3*self.size,) or np.iscomplexobj(rhs) or not np.all(np.isfinite(rhs)):
            raise ValueError('Invalid structured Radau right-hand side.')
        stages = rhs.reshape(3, self.size)
        transformed = self.reverse @ stages
        real = self.real.solve(transformed[0].real)
        complex_ = self.complex.solve(transformed[1])
        values = (self.transform[:, 0, None].real * real[None]
                  + 2*np.real(self.transform[:, 1, None] * complex_[None]))
        # Verify the original approximate three-stage operator, including the
        # transformation and conjugate reconstruction, before Newton uses it.
        ordered = values[:, self.permutation].T
        applied = product(self.state, ordered)
        applied += product(self.rate, ordered @ self.inverse.T/self.step)
        residual = applied.T - stages[:, self.permutation]
        if not np.all(np.isfinite(values)) or np.max(abs(residual)) > 1e-8*max(1., np.max(abs(rhs))):
            raise ValueError('Structured Radau solve failed its original-stage residual check.')
        return values.ravel()


def build(chart, residual, initial, flat, times, step, inverse, progress=None):
    if not eligible(chart):
        raise ValueError('Unsupported structured Radau chart.')
    initial, flat, times = (np.asarray(x, dtype=float) for x in (initial, flat, times))
    n = chart.size
    if (initial.shape != (n,) or flat.shape != (3*n,) or times.shape != (3,)
            or not all(np.all(np.isfinite(x)) for x in (initial, flat, times))
            or not np.isfinite(step) or step <= 0):
        raise ValueError('Invalid structured Radau stage anchor.')
    increments = flat.reshape(3, n)
    anchor = initial + increments[-1]
    rate = (inverse @ increments/step)[-1]
    time = times[-1]
    # Each pass captures its own identical physical stage. Rate differences
    # must not use direct Gamma columns: Gamma itself is fixed in that pass.
    state_matrix, permutation, state_counts = structured_time.jacobian(
        chart.system, lambda z: residual(z, rate, time), anchor,
        progress=progress, circulation_rate_factor=0.)
    rate_matrix, rate_permutation, rate_counts = structured_time.jacobian(
        chart.system, lambda d: residual(anchor, d, time), rate,
        progress=progress, circulation_rate_factor=None)
    if not np.array_equal(permutation, rate_permutation):
        raise ValueError('Inconsistent structured Radau partial layouts.')
    factor = Factorization(state_matrix, rate_matrix, permutation, inverse, step)
    factor.diagnostics = dict(state=state_counts, rate=rate_counts,
        shifted_factorizations=2, stage_size=n,
        partial_storage_bytes=state_matrix.storage_bytes+rate_matrix.storage_bytes)
    return factor


def attach(function, chart, residual, initial, times, step, inverse, progress=None):
    if not eligible(chart):
        return False
    def builder(flat):
        factor = build(chart, residual, initial, flat, times, step, inverse, progress)
        function.stage_tangent_diagnostics = factor.diagnostics
        return factor
    function.factorization_builder = builder
    return True
