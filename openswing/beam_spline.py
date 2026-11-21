"""Explicit cubic policies for beam tables, independent of mesh construction.

The opt-in Drela policy implements the documented SEGSPL/SPLIND (-999, -999)
equations: C2 interior continuity and zero third derivative on the end
intervals. It is not not-a-knot for more than three points. The primary
routine's use by a particular historical ASWING executable is unverified.
Joint laws and time tables continue to use the natural default.
"""
import numpy as np
from scipy.interpolate import CubicHermiteSpline, CubicSpline


NATURAL = 'natural-v1'
DRELA_SEGSPL = 'drela-segspl-v1'


def checked_interpolation(policy):
    if not isinstance(policy, str) or policy not in (NATURAL, DRELA_SEGSPL):
        raise ValueError(f'Unknown beam interpolation policy {policy!r}.')
    return policy


def segment_spline(t, values, policy=NATURAL):
    """Compile one strictly increasing segment; callers retain jump sidedness.

    Intervals are extrapolated with their endpoint polynomial, as for the
    existing natural policy. Two knots give a line under both policies.
    """
    checked_interpolation(policy)
    if policy == NATURAL:
        # Keep historical SciPy construction and arithmetic unchanged.
        return CubicSpline(t, values, bc_type='natural')
    t = np.asarray(t, dtype=float)
    values = np.asarray(values, dtype=float)
    if t.ndim != 1 or values.shape != t.shape or len(t) < 2:
        raise ValueError('A spline segment requires at least two matching station/value pairs.')
    widths = np.diff(t)
    if (not np.all(np.isfinite(t)) or not np.all(np.isfinite(values))
            or not np.all(np.isfinite(widths)) or np.any(widths <= 0)):
        raise ValueError('Spline stations must be finite and strictly increasing.')
    secants = np.diff(values)/widths
    if len(t) == 2:
        slopes = np.repeat(secants, 2)
    else:
        # Unknowns are knot first derivatives. Interior C2 equations are
        # h_right*m_left + 2*(h_left+h_right)*m + h_left*m_right
        # = 3*(h_right*secant_left + h_left*secant_right).
        # Zero third derivatives give m0+m1=2*secant0 at each end.
        lower = np.r_[0., widths[1:], 1.]
        upper = np.r_[1., widths[:-1], 0.]
        diagonal = np.r_[1., 2*(widths[:-1]+widths[1:]), 1.]
        rhs = np.r_[2*secants[0],
                    3*(widths[1:]*secants[:-1]+widths[:-1]*secants[1:]),
                    2*secants[-1]]
        for i in range(1, len(t)):
            factor = lower[i]/diagonal[i-1]
            diagonal[i] -= factor*upper[i-1]
            rhs[i] -= factor*rhs[i-1]
        slopes = np.empty_like(t)
        slopes[-1] = rhs[-1]/diagonal[-1]
        for i in range(len(t)-2, -1, -1):
            slopes[i] = (rhs[i]-upper[i]*slopes[i+1])/diagonal[i]
    if not np.all(np.isfinite(slopes)):
        raise ValueError('Spline segment derivatives are not finite; revise its scale or station spacing.')
    return CubicHermiteSpline(t, values, slopes)
