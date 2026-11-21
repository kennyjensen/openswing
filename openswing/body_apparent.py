"""Circular-body acceleration reaction, steady Eq.86 / unsteady Eq.45.

The printed ASWING coefficient is twice the classical cylinder pressure
integral. The caller must preserve the selected convention in state identity.
"""
from numbers import Real
import numpy as np
from .aero import AnalysisError


def coefficient(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or value not in (1., 2.):
        raise AnalysisError('Body apparent-mass coefficient must be 1 (cylinder) or 2 (printed ASWING).')
    return float(value)


def acceleration_force(span, radius, density, acceleration, factor=1.):
    """Force per material length about the circular section's center axis."""
    factor = coefficient(factor)
    radius, span, acceleration = map(np.asarray, (radius, span, acceleration))
    if (not np.all(np.isfinite(radius)) or np.any(radius < 0)
            or not np.isfinite(density) or density < 0):
        raise AnalysisError('Body apparent inertia requires finite nonnegative radius and density.')
    transverse = acceleration-np.sum(acceleration*span, axis=-1)[..., None]*span
    return -(factor*density*np.pi*radius**2)[..., None]*transverse


def source_rigid_response(pa, pb, ra, rb, radius_a, radius_b, length, density, reference, factor):
    """Rigid projection of completed endpoint forces and source box transfer."""
    midpoint = (pa+pb)/2
    columns = []
    for unit in np.eye(6):
        aa = unit[:3]+np.cross(unit[3:], pa-reference)
        ab = unit[:3]+np.cross(unit[3:], pb-reference)
        force = length[:, None]/2*(acceleration_force(ra[..., 1], radius_a, density, aa, factor)
            +acceleration_force(rb[..., 1], radius_b, density, ab, factor))
        columns.append(-np.c_[force, np.cross(midpoint-reference, force)])
    return np.stack(columns, axis=-1)
