"""Geometrically exact spatial beam equilibrium, independent of aero coupling.

Constitutive equations: Drela steady formulation (18–20). Spatial force and
moment balance and SO(3) kinematics are integrated using adaptive collocation.
This independent clamped/free driver validates the mixed network discretization
in network.py; both share this section constitutive law.
"""
from dataclasses import dataclass
from collections.abc import Callable
import numpy as np


def skew(v):
    v = np.asarray(v)
    out = np.zeros(v.shape[:-1] + (3, 3))
    out[..., 0, 1], out[..., 0, 2] = -v[..., 2], v[..., 1]
    out[..., 1, 0], out[..., 1, 2] = v[..., 2], -v[..., 0]
    out[..., 2, 0], out[..., 2, 1] = -v[..., 1], v[..., 0]
    return out


def stiffness_inverse(matrix):
    """Take the exact rigid limit, eliminating infinite-stiffness directions."""
    e = np.asarray(matrix, dtype=float)
    if e.shape != (3, 3) or np.any(np.isnan(e)) or not np.allclose(e, e.T):
        raise ValueError("Bending/torsion stiffness must be symmetric 3×3.")
    if np.any(np.diag(e) <= 0):
        raise ValueError("Stiffness must be positive or infinite.")
    finite = np.isfinite(np.diag(e))
    sub = e[np.ix_(finite, finite)]
    inv = np.zeros((3, 3))
    if sub.size:
        if not np.all(np.isfinite(sub)) or np.min(np.linalg.eigvalsh(sub)) <= 0:
            raise ValueError("Finite bending/torsion stiffness must be positive definite.")
        inv[np.ix_(finite, finite)] = np.linalg.inv(sub)
    return inv


@dataclass
class Section:
    EIcc: float = np.inf
    GJ: float = np.inf
    EInn: float = np.inf
    EIcs: float = 0.
    EIcn: float = 0.
    EIsn: float = 0.
    EA: float = np.inf
    GKc: float = np.inf
    GKn: float = np.inf
    Cea: float = 0.
    Nea: float = 0.
    Cta: float = 0.
    Nta: float = 0.

    def compliance(self):
        e = np.array([[self.EIcc, self.EIcs, self.EIcn],
                      [self.EIcs, self.GJ, self.EIsn],
                      [self.EIcn, self.EIsn, self.EInn]])
        f = np.array([self.GKc, self.EA, self.GKn])
        if np.any(np.isnan(f)) or np.any(f <= 0):
            raise ValueError("Axial/shear stiffness must be positive or infinite.")
        h = np.array([[0, self.Nta, 0], [-self.Nea, 0, self.Cea], [0, -self.Cta, 0]])
        b = stiffness_inverse(e)
        # [strain, curvature] = S [force, moment] in local c,s,n axes.
        return np.block([[np.diag(1 / f) + h.T @ b @ h, h.T @ b], [b @ h, b]])


@dataclass
class BeamSolution:
    s: np.ndarray
    position: np.ndarray
    rotation: np.ndarray
    force: np.ndarray
    moment: np.ndarray
    residual: float
    orthogonality_error: float
    nodes: int


def solve_cantilever(length: float, section: Section | Callable[[float], Section], *,
                     tip_force=(0., 0., 0.), tip_moment=(0., 0., 0.),
                     root_position=(0., 0., 0.), root_rotation=None,
                     loads=None, rest_curvature=None, samples=101,
                     tolerance=1e-7, continuation_steps=4) -> BeamSolution:
    """Solve a clamped/free beam with dead tip loads in global xyz axes.

    `loads(s, position, rotation)` supplies distributed global forces/moments
    per undeformed length, with batch shapes (N,), (N,3), (N,3,3).
    A callable section or rest curvature supports nonuniform/curved beams.
    The local undeformed tangent is +s, the second frame column.
    """
    from scipy.integrate import solve_bvp, solve_ivp

    if not np.isfinite(length) or length <= 0 or tolerance <= 0:
        raise ValueError("Positive finite length and positive tolerance required.")
    if continuation_steps < 1 or samples < 2:
        raise ValueError("At least one continuation step and two samples required.")
    origin, ftip, mtip = map(lambda x: np.asarray(x, dtype=float), (root_position, tip_force, tip_moment))
    r0 = np.eye(3) if root_rotation is None else np.asarray(root_rotation, dtype=float)
    if r0.shape != (3, 3) or not np.allclose(r0.T @ r0, np.eye(3), atol=1e-10) or not np.isclose(np.linalg.det(r0), 1):
        raise ValueError("Root rotation must be a proper orthonormal rotation.")
    if any(x.shape != (3,) or not np.all(np.isfinite(x)) for x in (origin, ftip, mtip)):
        raise ValueError("Tip loads and root position must be finite xyz vectors.")
    scale_f = max(np.linalg.norm(ftip), np.linalg.norm(mtip) / length, 1.)
    # Dimensionless positions, loads and coordinate keep mixed-unit residuals
    # from obscuring the equilibrium tolerance.
    sec_constant = section.compliance() if isinstance(section, Section) else None

    def compliances(s):
        if sec_constant is not None:
            return np.broadcast_to(sec_constant, (len(s), 6, 6))
        return np.array([section(float(v)).compliance() for v in s])

    def curvature(s):
        if rest_curvature is None:
            return np.zeros((len(s), 3))
        return np.broadcast_to(np.asarray(rest_curvature(s)), (len(s), 3))

    def rest_ode(u, y):
        rotation = y[3:12].reshape(3, 3)
        k = curvature(np.array([u * length]))[0]
        return np.r_[rotation[:, 1], (length * rotation @ skew(k)).ravel()]

    mesh = np.linspace(0, 1, 33)
    rest = solve_ivp(rest_ode, (0, 1), np.r_[np.zeros(3), r0.ravel()], t_eval=mesh, rtol=1e-10, atol=1e-12)
    y = np.vstack([rest.y, np.zeros((6, len(mesh)))])
    solver = None
    for factor in np.linspace(1 / continuation_steps, 1, continuation_steps):
        def rhs(u, state):
            s = u * length
            xyz = state[:3].T * length + origin
            rot = state[3:12].T.reshape(-1, 3, 3)
            force = state[12:15].T * scale_f
            moment = state[15:18].T * scale_f * length
            local = np.concatenate([np.einsum("nji,nj->ni", rot, force),
                                    np.einsum("nji,nj->ni", rot, moment)], axis=1)
            strain = np.einsum("nij,nj->ni", compliances(s), local)
            tangent = strain[:, :3] + np.array([0., 1., 0.])
            dr = np.einsum("nij,nj->ni", rot, tangent)
            drot = length * rot @ skew(curvature(s) + strain[:, 3:])
            f = np.zeros_like(xyz)
            m = np.zeros_like(xyz)
            if loads is not None:
                f, m = (np.broadcast_to(np.asarray(v), xyz.shape) * factor for v in loads(s, xyz, rot))
            return np.vstack([dr.T, drot.reshape(-1, 9).T, (-length * f / scale_f).T,
                              ((-np.cross(dr, force) - m) / scale_f).T])

        def boundary(a, b):
            return np.r_[a[:3], a[3:12] - r0.ravel(),
                         b[12:15] - factor * ftip / scale_f,
                         b[15:18] - factor * mtip / (scale_f * length)]

        solver = solve_bvp(rhs, boundary, mesh, y, tol=tolerance, max_nodes=4000)
        if not solver.success:
            raise RuntimeError(f"Nonlinear beam equilibrium did not converge: {solver.message}")
        mesh, y = solver.x, solver.y
    s = np.linspace(0, length, samples)
    out = solver.sol(s / length)
    rotations = out[3:12].T.reshape(-1, 3, 3)
    ortho = float(np.max(np.abs(rotations.transpose(0, 2, 1) @ rotations - np.eye(3))))
    if ortho > max(20 * tolerance, 1e-6):
        raise RuntimeError(f"Beam rotation integration drifted from SO(3): {ortho:.3g}")
    return BeamSolution(s, origin + out[:3].T * length, rotations, out[12:15].T * scale_f,
                        out[15:18].T * scale_f * length, float(max(solver.rms_residuals)), ortho, len(mesh))
