"""Fuselage material chart: steady Eqs.10--12 and unsteady Eq.4.

Angles are [phi, theta, psi] in radians. Frames map local csn components
to body xyz. The fuselage chart is singular at a vertical span, while the
surface chart is singular at an x-directed span. Neither pole is regularized.
"""
import numpy as np
from .aero import AnalysisError


def frame_from_angles(angles):
    phi, theta, psi = np.moveaxis(np.asarray(angles), -1, 0)
    cp, sp, ct, st, cs, ss = (np.cos(phi), np.sin(phi), np.cos(theta),
                             np.sin(theta), np.cos(psi), np.sin(psi))
    c0 = np.stack([cs, ss, np.zeros_like(phi)], axis=-1)
    n0 = np.stack([ss*sp, -cs*sp, cp], axis=-1)
    span = np.stack([-ss*cp, cs*cp, sp], axis=-1)
    return np.stack([c0*ct[..., None]-n0*st[..., None], span,
                     c0*st[..., None]+n0*ct[..., None]], axis=-1)


def angles_from_frame(frame):
    r = np.asarray(frame)
    span = r[..., :, 1]
    horizontal = np.hypot(span[..., 0], span[..., 1])
    if np.any(horizontal < 1e-8):
        raise AnalysisError('Source fuselage Euler chart is singular for a vertical beam orientation.')
    phi = np.arctan2(span[..., 2], horizontal)
    psi = np.arctan2(-span[..., 0], span[..., 1])
    c0 = np.stack([np.cos(psi), np.sin(psi), np.zeros_like(phi)], axis=-1)
    n0 = np.stack([np.sin(psi)*np.sin(phi), -np.cos(psi)*np.sin(phi), np.cos(phi)], axis=-1)
    theta = np.arctan2(-np.sum(r[..., :, 0]*n0, axis=-1), np.sum(r[..., :, 0]*c0, axis=-1))
    return np.stack([phi, theta, psi], axis=-1)


def angle_matrix(angles):
    q = np.asarray(angles)
    phi, theta = q[..., 0], q[..., 1]
    cp, sp, ct, st = np.cos(phi), np.sin(phi), np.cos(theta), np.sin(theta)
    out = np.zeros(q.shape[:-1]+(3, 3), dtype=np.result_type(q, float))
    out[..., 0, 0], out[..., 0, 2] = ct, -cp*st
    out[..., 1, 1], out[..., 1, 2] = 1., sp
    out[..., 2, 0], out[..., 2, 2] = st, cp*ct
    return out


def angle_matrix_rate(angles, rates):
    q, dq = np.asarray(angles), np.asarray(rates)
    phi, theta, pd, td = q[..., 0], q[..., 1], dq[..., 0], dq[..., 1]
    cp, sp, ct, st = np.cos(phi), np.sin(phi), np.cos(theta), np.sin(theta)
    out = np.zeros(q.shape[:-1]+(3, 3), dtype=np.result_type(q, dq, float))
    out[..., 0, 0] = -st*td
    out[..., 0, 2] = sp*st*pd-cp*ct*td
    out[..., 1, 2] = cp*pd
    out[..., 2, 0] = ct*td
    out[..., 2, 2] = -sp*ct*pd-cp*st*td
    return out


def euler_rates(angles, angular_velocity):
    """Unsteady Eq.4: angular velocity uses body xyz components."""
    q, w = np.asarray(angles), np.asarray(angular_velocity)
    phi, psi = q[..., 0], q[..., 2]
    along = -np.sin(psi)*w[..., 0]+np.cos(psi)*w[..., 1]
    return np.stack([np.cos(psi)*w[..., 0]+np.sin(psi)*w[..., 1],
                     along/np.cos(phi), w[..., 2]-np.tan(phi)*along], axis=-1)
