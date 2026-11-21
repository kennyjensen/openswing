"""Independent loaded, variable-section, three-branch spatial rod reference.

No openswing import. Fixed spatial nodal dead loads, inextensible unshearable
Kirchhoff rods, exact massless offset connector, and distributed real inertia.
The literal tables and physical loads are input data, not residual operators.
"""
from pathlib import Path
import argparse
import hashlib
import json
import time
import traceback
import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import CubicSpline
from scipy.linalg import lu_factor, lu_solve, get_lapack_funcs
from scipy.optimize import root


def hat(v):
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def pin(path):
    b = Path(path).read_bytes()
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


class Tables:
    def __init__(self, data):
        self.parts = {}
        self.knots = set()
        for name, value in data.items():
            if not isinstance(value, dict):
                self.parts[name] = value
                continue
            s, y = np.array(value['t']), np.array(value['values'])
            self.knots.update(s)
            cuts = [0, *list(np.flatnonzero(np.diff(s) == 0)+1), len(s)]
            parts = []
            for lo, hi in zip(cuts[:-1], cuts[1:]):
                x, v = s[lo:hi], y[lo:hi]
                assert len(x) >= 2 and np.all(np.diff(x) > 0)
                parts.append((x[0], x[-1], CubicSpline(x, v, bc_type='natural')))
            self.parts[name] = parts

    def at(self, name, s, midpoint):
        parts = self.parts[name]
        if not isinstance(parts, list):
            return parts
        available = [p for p in parts if p[0] <= midpoint <= p[1]]
        assert len(available) == 1, (name, s, midpoint)
        return float(available[0][2](s))


class Reference:
    names = ('boom', 'upper', 'lower')

    def __init__(self, fixture, rtol):
        self.fixture, self.rtol = fixture, rtol
        self.tables = {name: Tables(p) for name, p in fixture['properties'].items()}
        self.branches = fixture['branches']
        self.scale = np.r_[np.repeat(20., 3), np.ones(6), np.repeat(20., 3)]
        self.ops = dict(base_integrations=0, base_rhs=0, transfer_integrations=0,
                        transfer_rhs=0, boundary_solves=0)
        self.fjoint = np.array(fixture['joint_dead_force_fin_root'])
        self.mjoint = np.array(fixture['joint_dead_moment_fin_root'])
        self.fupper = np.sum(self.branches['upper']['dead_force'][1:], axis=0)
        self.flower = np.sum(self.branches['lower']['dead_force'][1:], axis=0)
        self.ffin = self.fjoint+self.fupper+self.flower
        self.forces = dict(boom=np.sum(self.branches['boom']['dead_force'][1:], axis=0)+self.ffin,
                           upper=self.fupper, lower=-self.flower)
        self.offset = np.array(fixture['jointoffset_material'])
        self.relative_rotation = np.array(fixture['joint_rotation_material'])
        self.cache = None
        self.base = None
        self.rotation_to_physical = np.array(fixture['gauge']['cut']['rotation'])
        self.rotation_to_gauge = np.array(fixture['gauge']['physical_to_gauge_rotation'])
        for table in self.tables.values():
            assert all(table.parts[k] == 'rigid' for k in ('EA', 'GKc', 'GKn'))
            assert all(table.parts[k] == 0 for k in ('EIcn', 'EIcs', 'EIsn',
                       'Cea', 'Nea', 'Cta', 'Nta', 'tdeps', 'tdgam', 'Dmg',
                       'Dmgcc', 'Dmgnn', 'DCcg', 'DNcg'))

    def intervals(self, name):
        b = self.branches[name]
        table = self.tables['boom' if name == 'boom' else 'fin']
        for j, (lo, hi) in enumerate(zip(b['stations'][:-1], b['stations'][1:]), 1):
            knots = sorted(k for k in table.knots if min(lo, hi) < k < max(lo, hi))
            if hi < lo:
                knots.reverse()
            grid = [lo, *knots, hi]
            for a, z in zip(grid[:-1], grid[1:]):
                yield a, z, j if z == hi else None, table

    def coefficients(self, y, s, midpoint, table, dynamic):
        R, N, M = y[3:12].reshape(3, 3), y[12:15], y[15:18]
        tangent = R[:, 1]
        stiffness = np.array([table.at(k, s, midpoint) for k in ('EIcc', 'GJ', 'EInn')])
        assert np.all(stiffness > 0)
        C = (R/stiffness)@R.T
        A = np.zeros((12, 12))
        A[:3, 3:6] = -hat(tangent)
        A[3:6, 3:6] = C@hat(M)
        A[3:6, 9:] = C
        A[9:, :6] = hat(N)@A[:3, :6]
        A[9:, 6:9] = -hat(tangent)
        B = np.zeros_like(A)
        if dynamic:
            mass = table.at('mg', s, midpoint)/self.fixture['gravity']
            arm = hat(R@np.array([table.at('Ccg', s, midpoint), 0., table.at('Ncg', s, midpoint)]))
            icc = table.at('mgcc', s, midpoint)/self.fixture['gravity']
            inn = table.at('mgnn', s, midpoint)/self.fixture['gravity']
            J = R@np.diag([icc, icc+inn, inn])@R.T
            B[6:9, :3] = mass*np.eye(3)
            B[6:9, 3:6] = -mass*arm
            B[9:, :3] = mass*arm
            B[9:, 3:6] = J-mass*arm@arm
        return A, B, tangent, stiffness

    def branch_base(self, name, r, R, N, M, derivative):
        y = np.r_[r, R.ravel(), N, M, derivative.ravel()]
        nodes = [y.copy()]
        intervals = []
        for lo, hi, node, table in self.intervals(name):
            mid = (lo+hi)/2

            def ode(s, state):
                Q = state[3:12].reshape(3, 3)
                A, _, tangent, stiffness = self.coefficients(state, s, mid, table, False)
                rotation = Q@hat((Q.T@state[15:18])/stiffness)
                dy = np.r_[tangent, rotation.ravel(), np.zeros(3), -np.cross(tangent, state[12:15])]
                return np.r_[dy, (A@state[18:].reshape(12, 9)).ravel()]

            sol = solve_ivp(ode, (lo, hi), y, method='DOP853', rtol=self.rtol,
                            atol=self.rtol*.01, dense_output=True)
            self.ops['base_integrations'] += 1
            self.ops['base_rhs'] += sol.nfev
            assert sol.success, sol.message
            y = sol.y[:, -1].copy()
            intervals.append(dict(lo=lo, hi=hi, table=table, base=sol.sol))
            if node is not None:
                sign = np.sign(hi-lo)
                y[12:15] -= sign*np.array(self.branches[name]['dead_force'][node])
                y[15:18] -= sign*np.array(self.branches[name]['dead_moment'][node])
                nodes.append(y.copy())
        return dict(end=y, nodes=np.array(nodes), intervals=intervals)

    def evaluate_base(self, guess):
        if self.cache is not None and np.array_equal(guess, self.cache[0]):
            return self.cache[1:]
        derivative = np.zeros((12, 9))
        derivative[9:, :3] = np.eye(3)
        boom = self.branch_base('boom', np.array(self.fixture['rootposition']),
                                np.array(self.fixture['rootmaterialrotation']),
                                self.forces['boom'], guess[:3], derivative)
        tip = boom['end']
        Rb = tip[3:12].reshape(3, 3)
        d = Rb@self.offset
        Rfin = Rb@self.relative_rotation
        db = tip[18:].reshape(12, 9)
        branches = dict(boom=boom)
        for name, columns in (('upper', slice(3, 6)), ('lower', slice(6, 9))):
            derivative = np.zeros((12, 9))
            derivative[:3] = db[:3]-hat(d)@db[3:6]
            derivative[3:6] = db[3:6]
            derivative[9:, columns] = np.eye(3)
            branches[name] = self.branch_base(name, tip[:3]+d, Rfin,
                                              self.forces[name], guess[columns], derivative)
        residual = np.r_[branches['upper']['end'][15:18], branches['lower']['end'][15:18],
                          tip[15:18]-guess[3:6]+guess[6:9]-self.mjoint-np.cross(d, self.ffin)]
        jac = np.r_[branches['upper']['end'][18:].reshape(12, 9)[9:],
                    branches['lower']['end'][18:].reshape(12, 9)[9:],
                    db[9:]-hat(self.ffin)@hat(d)@db[3:6]]
        jac[6:, 3:6] -= np.eye(3)
        jac[6:, 6:9] += np.eye(3)
        self.cache = (guess.copy(), residual, jac, branches)
        return residual, jac, branches

    def solve_base(self):
        guess = np.concatenate([self.fixture['initial_root_trace_details'][name]['spatial_gauge']
                                for name in self.names])
        sol = root(lambda x: self.evaluate_base(x)[0], guess,
                   jac=lambda x: self.evaluate_base(x)[1],
                   method='hybr', options=dict(xtol=1e-10, maxfev=24))
        residual, jac, self.base = self.evaluate_base(sol.x)
        orthogonal = max(np.max(abs(n[3:12].reshape(3, 3).T@n[3:12].reshape(3, 3)-np.eye(3)))
                         for b in self.base.values() for n in b['nodes'])
        force_error = max(np.max(abs(self.base['upper']['end'][12:15])),
                          np.max(abs(self.base['lower']['end'][12:15])),
                          np.max(abs(self.base['boom']['end'][12:15]-self.ffin)))
        report = dict(success=bool(sol.success), message=str(sol.message),
                      evaluations=int(sol.nfev), root_moments_spatial=sol.x.tolist(),
                      maximum_moment_residual=float(np.max(abs(residual))),
                      maximum_force_residual=float(force_error),
                      maximum_rotation_orthogonality_error=float(orthogonal),
                      moment_residual=residual.tolist(), root_jacobian=jac.tolist())
        assert np.max(abs(residual)) <= 1e-8, report
        assert force_error <= 1e-10 and orthogonal <= 1e-8, report
        return report

    def transfers(self, name, frequency):
        cumulative = [np.eye(12)]
        dense = []
        for part in self.base[name]['intervals']:
            lo, hi, table = part['lo'], part['hi'], part['table']
            mid = (lo+hi)/2

            def ode(s, value):
                A, B, _, _ = self.coefficients(part['base'](s), s, mid, table, True)
                operator = (A-(2*np.pi*frequency)**2*B)*self.scale[None, :]/self.scale[:, None]
                return (operator@value.reshape(12, 12)).ravel()

            sol = solve_ivp(ode, (lo, hi), np.eye(12).ravel(), method='DOP853',
                            rtol=self.rtol, atol=self.rtol*.01, dense_output=True)
            self.ops['transfer_integrations'] += 1
            self.ops['transfer_rhs'] += sol.nfev
            assert sol.success, sol.message
            dense.append(sol.sol)
            cumulative.append(sol.y[:, -1].reshape(12, 12)@cumulative[-1])
        return np.array(cumulative), dense

    def solve_response(self, frequency):
        matrices = {name: self.transfers(name, frequency) for name in self.names}
        initial = dict(boom=np.zeros((12, 18)))
        initial['boom'][6:, :6] = np.eye(6)
        endboom = matrices['boom'][0][-1]@initial['boom']
        d = self.base['boom']['end'][3:12].reshape(3, 3)@self.offset
        kinematic = np.eye(6)
        kinematic[:3, 3:] = -hat(d)/20.
        for name, columns in (('upper', slice(6, 12)), ('lower', slice(12, 18))):
            initial[name] = np.zeros((12, 18))
            initial[name][:6] = kinematic@endboom[:6]
            initial[name][6:, columns] = np.eye(6)
        upper = matrices['upper'][0][-1]@initial['upper']
        lower = matrices['lower'][0][-1]@initial['lower']
        junction = endboom[6:]-initial['upper'][6:]+initial['lower'][6:]
        junction[3:] -= hat(d)@(initial['upper'][6:9]-initial['lower'][6:9])/20.
        junction[3:] -= hat(self.ffin)@hat(d)@endboom[3:6]/20.
        matrix = np.r_[upper[6:], lower[6:], junction]
        rhs = np.zeros((18, 2))
        rhs[:3, 0] = self.rotation_to_gauge@np.array([0., 1., 0.])
        rhs[3:6, 1] = (self.rotation_to_gauge@np.array([0., 0., 1.]))/20.
        rows = np.max(abs(matrix), axis=1)
        assert np.all(rows > 0)
        scaled = matrix/rows[:, None]
        cols = np.max(abs(scaled), axis=0)
        assert np.all(cols > 0)
        scaled /= cols[None, :]
        forcing = rhs/rows[:, None]
        lu, piv = lu_factor(scaled)
        rcond, info = get_lapack_funcs('gecon', (scaled,))(lu, np.linalg.norm(scaled, 1))
        assert info == 0
        value = lu_solve((lu, piv), forcing)
        self.ops['boundary_solves'] += 1
        internal_residual = scaled@value-forcing
        internal_relative = np.max(abs(internal_residual), axis=0)/np.max(abs(forcing), axis=0)
        value /= cols[:, None]
        residual = matrix@value-rhs
        relative = np.max(abs(residual)/rows[:, None], axis=0)/np.maximum(1., np.max(abs(forcing), axis=0))
        backward = np.linalg.norm(residual, axis=0)/(np.linalg.norm(matrix)*
                   np.linalg.norm(value, axis=0)+np.linalg.norm(rhs, axis=0)+1e-30)
        diagnostics = dict(reciprocal_condition=float(rcond), scaled_residuals=relative.tolist(),
                           backward_errors=backward.tolist(), frequency_Hz=frequency,
                           internal_relative_residuals=internal_relative.tolist(),
                           available=bool(rcond >= 1e-12 and np.max(relative) <= 1e-7
                                          and np.max(backward) <= 1e-9 and np.isfinite(value).all()))
        if not diagnostics['available']:
            return diagnostics, {}
        data = {}
        for name in self.names:
            branch = self.branches[name]
            points = [s for lo, hi in zip(branch['stations'][:-1], branch['stations'][1:])
                      for s in np.linspace(lo, hi, 5)[:-1]]+[branch['stations'][-1]]
            records, base = [], []
            cumulative, dense = matrices[name]
            rootstate = initial[name]@value
            for station in points:
                j = next(j for j, part in enumerate(self.base[name]['intervals'])
                         if min(part['lo'], part['hi'])-1e-13 <= station <= max(part['lo'], part['hi'])+1e-13)
                state = dense[j](station).reshape(12, 12)@cumulative[j]@rootstate
                records.append(self.scale[:, None]*state)
                base.append(self.base[name]['intervals'][j]['base'](station)[:18])
            records = np.array(records)
            physical = np.einsum('ij,nkjt->nkit', self.rotation_to_physical,
                                 records.reshape(len(points), 4, 3, 2)).reshape(len(points), 12, 2)
            data[name+'_stations'] = np.array(points)
            data[name+'_states_gauge'] = records
            data[name+'_states_physical'] = physical
            data[name+'_base'] = np.array(base)
        data['junction_offset'] = d
        data['boundary_matrix'] = matrix
        data['boundary_rhs'] = rhs
        data['initial_wrenches_scaled'] = value
        return diagnostics, data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--rtol', type=float, required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='STARTED', rtol=args.rtol, source=pin(__file__), fixture=pin(args.fixture),
                  frequencies_Hz=[0., .7, 1., 1.3], production_imports=False)
    started = time.monotonic()
    reference = None
    try:
        reference = Reference(json.loads(Path(args.fixture).read_text()), args.rtol)
        report['base'] = reference.solve_base()
        np.savez(output/'base.npz', **{name: branch['nodes'][:, :18] for name, branch in reference.base.items()})
        report['responses'] = []
        for i, frequency in enumerate(report['frequencies_Hz']):
            diagnostics, data = reference.solve_response(frequency)
            report['responses'].append(diagnostics)
            if data:
                np.savez(output/f'response-{i}.npz', **data)
            (output/'progress.json').write_text(json.dumps(report, indent=2)+'\n')
        report['status'] = 'PASS_CONTINUUM_EXECUTION' if all(r['available'] for r in report['responses']) else 'POLE_GAPS_RETAINED'
    except BaseException as exc:
        report.update(status='FAILURE_RETAINED', error=str(exc), traceback=traceback.format_exc())
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic()-started
        report['operations'] = {} if reference is None else reference.ops
        (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
