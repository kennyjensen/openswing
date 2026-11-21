"""Check a saved descriptor mode against directional nonlinear residuals.

ASWING's sign convention is A=R_z and M=-R_zdot. Real centered probes
are applied separately to the real and imaginary parts of each direction;
the physical residual is never evaluated at a complex aircraft state.
The left-projected pole correction is first-order diagnostic evidence, not
a replacement eigensolution or a finite-amplitude mode trajectory.
"""
import numpy as np


def actions(residual, direction, step):
    direction = np.asarray(direction, dtype=complex)
    if (direction.ndim != 1 or not np.all(np.isfinite(direction))
            or not np.isfinite(step) or step <= 0):
        raise ValueError('Directional probes require a finite vector and positive step.')
    zero = np.zeros(len(direction))
    aa = np.zeros(len(direction), dtype=complex)
    mm = np.zeros_like(aa)
    for part, factor in [(direction.real, 1.), (direction.imag, 1j)]:
        if not np.any(part):
            continue
        dz = step*part
        aa += factor*(residual(dz, zero)-residual(-dz, zero))/(2*step)
        mm -= factor*(residual(zero, dz)-residual(zero, -dz))/(2*step)
    if not np.all(np.isfinite(aa)) or not np.all(np.isfinite(mm)):
        raise ValueError('Nonlinear mode probes returned nonfinite directional actions.')
    return aa, mm


def projected_correction(left, mass_action, defect):
    # Only vectors are promoted, avoiding a full extended-precision matrix.
    left, mass_action, defect = [np.asarray(v, dtype=np.clongdouble)
                                for v in (left, mass_action, defect)]
    den = np.vdot(left, mass_action)
    if not np.isfinite(den) or abs(den) == 0:
        raise ValueError('This mode has no finite nonzero left/right mass pairing.')
    return complex(np.vdot(left, defect)/den)
