"""Independent loaded spatial-rod dynamic transfer, with distributed real inertia.

No production import. The state is [displacement, spatial rotation, force,
moment] and the time convention is exp(lambda*t). Frozen nodal spatial loads
set the base state; their variations are zero. There is no fluid or damping.
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import solve
from loaded_wing_reference import hat, continuum, projected_mass


class Rod:
    def __init__(self, s, S, force, torque, r0, R0, initial_moment, common, table,
                 *, rtol=1e-10):
        self.s, self.S = np.asarray(s), S
        self.common, self.table, self.rtol = common, table, rtol
        self.static = continuum(s, S, force, torque, r0, R0, initial_moment, rtol=rtol)
        y = np.r_[r0, R0.ravel(), self.static['root_force'], self.static['root_moment']]
        self.base = []

        def ode(_, state):
            R = state[3:12].reshape(3, 3)
            N, M = state[12:15], state[15:18]
            strain = S@np.r_[R.T@N, R.T@M]
            rp = R@(strain[:3]+[0., 1., 0.])
            return np.r_[rp, (R@hat(strain[3:])).ravel(), np.zeros(3), -np.cross(rp, N)]

        for j, (lo, hi) in enumerate(zip(s[:-1], s[1:]), 1):
            result = solve_ivp(ode, (lo, hi), y, method='DOP853', rtol=rtol,
                               atol=rtol*.01, dense_output=True)
            assert result.success, result.message
            self.base.append(result.sol)
            y = result.y[:, -1].copy()
            y[12:15] -= force[j]; y[15:18] -= torque[j]
        assert np.max(abs(y[12:])) < 1e-8

    def coefficients(self, j, position):
        y = self.base[j](position)
        R, N, M = y[3:12].reshape(3, 3), y[12:15], y[15:18]
        rp = R@((self.S@np.r_[R.T@N, R.T@M])[:3]+[0., 1., 0.])
        variation = np.zeros((6, 12))
        variation[:3, 3:6], variation[3:, 3:6] = R.T@hat(N), R.T@hat(M)
        variation[:3, 6:9], variation[3:, 9:] = R.T, R.T
        strain = self.S@variation
        A = np.zeros((12, 12))
        A[:3] = R@strain[:3]; A[:3, 3:6] -= hat(rp)
        A[3:6] = R@strain[3:]
        A[9:] = hat(N)@A[:3]; A[9:, 6:9] -= hat(rp)
        breaks = np.cumsum(self.common['segment_lengths_m'])
        mid = (self.s[j]+self.s[j+1])/2
        k = min(np.searchsorted(breaks, mid), len(breaks)-1)
        mg, ccg, ncg, mgcc, mgnn = self.table['inertia'][k]
        mass, icc, inn = np.array([mg, mgcc, mgnn])/self.common['gravity_m_s2']
        arm = hat(R@np.array([ccg, 0., ncg]))
        inertia = R@np.diag([icc, icc+inn, inn])@R.T
        B = np.zeros((12, 12))
        B[6:9, :3] = mass*np.eye(3); B[6:9, 3:6] = -mass*arm
        B[9:, :3] = mass*arm; B[9:, 3:6] = inertia-mass*arm@arm
        return A, B

    def transfers(self, rate):
        dtype = complex if np.iscomplexobj(rate) else float
        transfers = []
        evaluations = 0
        for j, (lo, hi) in enumerate(zip(self.s[:-1], self.s[1:])):
            def ode(s, value):
                A, B = self.coefficients(j, s)
                return ((A+rate**2*B)@value.reshape(12, 12)).ravel()
            result = solve_ivp(ode, (lo, hi), np.eye(12, dtype=dtype).ravel(),
                               method='DOP853', rtol=self.rtol, atol=self.rtol*.01)
            assert result.success, result.message
            transfers.append(result.y[:, -1].reshape(12, 12))
            evaluations += result.nfev
        return np.array(transfers), evaluations

    def response(self, rate):
        """All nodal load inputs and outputs, retaining the clamped root.

        Each node's force/moment is a physical spatial wrench. Transfer states
        are immediately after each dead-load jump. The final wrench is zero.
        Multiple shooting avoids dividing by singular local compliance blocks.
        """
        transfers, evaluations = self.transfers(rate)
        nn = len(self.s)
        A = np.zeros((12*nn, 12*nn), dtype=transfers.dtype)
        D = np.zeros((12*nn, 6*nn), dtype=transfers.dtype)
        A[:6, :6] = np.eye(6)
        for j, T in enumerate(transfers):
            rows = slice(6+12*j, 18+12*j)
            A[rows, 12*j:12*j+12] = T
            A[rows, 12*j+12:12*j+24] = -np.eye(12)
            D[12+12*j:18+12*j, 6*j+6:6*j+12] = np.eye(6)
        A[-6:, -6:] = np.eye(6)
        value = solve(A, D)
        output = value.reshape(nn, 12, 6*nn)[:, :6].reshape(6*nn, 6*nn)
        backward = np.linalg.norm(A@value-D, np.inf)/max(1., np.linalg.norm(A, np.inf)*np.linalg.norm(value, np.inf))
        return dict(response=output, transfers=transfers, states=value,
                    backward_error=float(backward), evaluations=evaluations)

    def characteristic(self, omega):
        transfers, _ = self.transfers(1j*omega)
        T = np.eye(12, dtype=complex)
        for part in transfers:
            T = part@T
        # With pure imaginary lambda all coefficients are real. Column scaling
        # is positive and cannot move determinant zeros or change their signs.
        end = T[6:, 6:].real
        return float(np.linalg.det(end/np.maximum(np.linalg.norm(end, axis=0), 1e-30)))

    def mode(self, omega):
        transfers, _ = self.transfers(1j*omega)
        states = [np.r_[np.zeros((6, 6)), np.eye(6)]]
        for part in transfers:
            states.append(part@states[-1])
        _, _, vh = np.linalg.svd(states[-1][6:])
        root_wrench = vh[-1].conj()
        values = np.array(states)@root_wrench
        scale = max(np.max(abs(values[:, :3]))/self.common['length_m'], np.max(abs(values[:, 3:6])))
        values /= scale
        return dict(shape=values[:, :6], states=values,
                    boundary_relative=float(np.linalg.norm(values[-1, 6:])/np.linalg.norm(values[:, 6:])))


def full_mass(s, positions, rotations, common, table, *, step=3e-6, quadrature=12):
    """All nodal kinetic-energy coefficients, assembled from twelve local fields."""
    matrix = np.zeros((6*len(s), 6*len(s)))
    for j in range(len(s)-1):
        local = projected_mass(s[j:j+2], positions[j:j+2], rotations[j:j+2],
                               np.eye(12).reshape(2, 6, 12), common, table,
                               step=step, quadrature=quadrature)
        matrix[6*j:6*j+12, 6*j:6*j+12] += local
    return matrix
