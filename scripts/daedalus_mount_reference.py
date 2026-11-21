"""Independent continuous spatial rod for the literal 0..2.5 ft boom span.

No OpenSwing imports. Direct literal stiffness/weight formulae, fixed spatial
dead loads at the original interior station, and fixed fairing-end pose.
The wing-end wrench is prescribed. Section shear/extension and offsets are
zero, as verified by the capture adapter. The spatial ODE retains preload.
"""
import numpy as np
from scipy.integrate import solve_ivp


def hat(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def properties(t):
    bending = 5000 * (10 + 10 * (t + 6.5) / 10.5)
    return np.array([bending, 25000., bending]), .15


class Mount:
    def __init__(self, fixture, rtol=1e-10):
        self.f = fixture
        self.rtol = rtol
        self.stations = np.array(fixture['stations'])
        self.force = np.array(fixture['dead_force'])
        self.moment = np.array(fixture['dead_moment'])
        self.counts = dict(base_rhs=0, dynamic_rhs=0)

    @staticmethod
    def operator(state, t):
        q = state[3:12].reshape(3, 3)
        N, M = state[12:15], state[15:18]
        k, _ = properties(t)
        tangent = q[:, 1]
        compliance = (q / k) @ q.T
        a = np.zeros((12, 12))
        a[:3, 3:6] = -hat(tangent)
        a[3:6, 3:6] = compliance @ hat(M)
        a[3:6, 9:12] = compliance
        a[9:12, :6] = hat(N) @ a[:3, :6]
        a[9:12, 6:9] = -hat(tangent)
        return a, tangent, k

    def base(self, right_wrench):
        y = np.r_[self.f['positions'][-1], np.array(self.f['frames'][-1]).ravel(),
                  right_wrench, np.r_[np.zeros((6, 6)), np.eye(6)].ravel()]
        values = {len(self.stations)-1: y.copy()}
        segments = []
        for j in range(len(self.stations)-2, -1, -1):
            lo, hi = self.stations[j:j+2]
            def ode(t, state):
                a, tangent, k = self.operator(state, t)
                q = state[3:12].reshape(3, 3)
                dq = q @ hat((q.T @ state[15:18]) / k)
                return np.r_[tangent, dq.ravel(), np.zeros(3),
                    -np.cross(tangent, state[12:15]),
                    (a @ state[18:].reshape(12, 6)).ravel()]
            sol = solve_ivp(ode, (hi, lo), y, method='DOP853', rtol=self.rtol,
                            atol=.01*self.rtol, dense_output=True)
            assert sol.success, sol.message
            self.counts['base_rhs'] += sol.nfev
            y = sol.y[:, -1].copy()
            segments.append(dict(lo=lo, hi=hi, node=j, dense=sol.sol))
            values[j] = y.copy()
            if j:
                y[12:15] += self.force[j]
                y[15:18] += self.moment[j]
        return dict(left=y, values=np.array([values[j] for j in range(len(values))]),
                    segments=segments)

    def equilibrium(self):
        wrench = np.array(self.f['right_wrench'])
        target = np.array(self.f['left_wrench'])
        scale = np.array([100.]*3 + [250.]*3)
        history = []
        for iteration in range(5):
            base = self.base(wrench)
            defect = base['left'][12:18] - target
            residual = float(max(abs(defect/scale)))
            history.append(residual)
            if residual < 2e-12:
                return base, wrench, history
            matrix = base['left'][18:].reshape(12, 6)[6:]
            scaled = matrix*scale[None, :]/scale[:, None]
            assert np.linalg.cond(scaled) < 1e8
            wrench -= np.linalg.solve(scaled, defect/scale)*scale
        raise AssertionError(('continuum equilibrium did not converge', history))

    def response(self, base, s):
        y = np.eye(12, dtype=complex).ravel()
        values = {len(self.stations)-1: y.reshape(12, 12).copy()}
        for segment in base['segments']:
            def ode(t, value):
                a, _, _ = self.operator(segment['dense'](t), t)
                b = np.zeros((12, 12))
                b[6:9, :3] = properties(t)[1]/self.f['gravity_constant']*np.eye(3)
                return ((a+s*s*b) @ value.reshape(12, 12)).ravel()
            sol = solve_ivp(ode, (segment['hi'], segment['lo']), y,
                method='DOP853', rtol=self.rtol, atol=.01*self.rtol)
            assert sol.success, sol.message
            self.counts['dynamic_rhs'] += sol.nfev
            y = sol.y[:, -1].copy()
            values[segment['node']] = y.reshape(12, 12).copy()
        matrix = values[0][6:, 6:]
        rhs = np.c_[np.eye(6), -values[0][6:, :6]]
        row = np.max(abs(matrix), axis=1)
        col = np.max(abs(matrix/row[:, None]), axis=0)
        scaled = matrix/row[:, None]/col
        assert np.linalg.cond(scaled) < 1e10
        wrench = np.linalg.solve(scaled, rhs/row[:, None])/col[:, None]
        residual = float(np.max(abs((matrix@wrench-rhs)/row[:, None])))
        assert residual < 2e-10, residual
        right = np.r_[np.c_[np.zeros((6, 6)), np.eye(6)], wrench]
        states = np.array([values[j]@right for j in range(len(values))])
        return states, residual, float(1/np.linalg.cond(scaled))
