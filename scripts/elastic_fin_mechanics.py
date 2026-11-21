"""Source-only candidate: loaded three-branch continuum nodal compliance.

No production imports, finite elements, aerodynamic law, or base solve here.
An accepted independent rod_reference.Reference is supplied explicitly.
All rotations in the response are spatial infinitesimal vectors, not Euler
angles or logarithms of the material frame.  Phasors use exp(+i*omega*time).
"""
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import lu_factor, lu_solve, get_lapack_funcs

from boom_fin_reference import hat


class ElasticCompliance:
    """Retain the reference's preload, material tables and real line inertia."""

    def __init__(self, reference):
        if reference.base is None:
            raise ValueError('An explicitly accepted loaded continuum base is required')
        self.ref = reference
        self.scale = reference.scale.copy()
        self.names = reference.names
        self.Q = reference.rotation_to_physical.copy()
        self.T = reference.rotation_to_gauge.copy()
        self.ops = dict(transfer_integrations=0, transfer_rhs=0,
                        boundary_factorizations=0, boundary_solves=0,
                        density_calls=0)

    def _node(self, node):
        branch, s = node['branch'], float(node['s'])
        if not np.isfinite(s):
            raise ValueError('Nonfinite material station')
        if branch == 'joint':
            if s != 0.:
                raise ValueError('The shared fin root is joint at s=0')
            return dict(branch=branch, s=s)
        if branch not in self.names:
            raise ValueError('Unknown branch')
        grid = self.ref.branches[branch]['stations']
        if not min(grid) <= s <= max(grid):
            raise ValueError('Station outside branch')
        if branch in ('lower', 'upper') and s == 0.:
            return dict(branch='joint', s=0.)
        return dict(branch=branch, s=s)

    def mesh_nodes(self, subdivisions=1):
        """Fin ascending (shared root once), then boom ascending; preserve knots.

        The independent rod material stations are the old fixed-load stations.
        Subdivide EVERY original interval equally; do not create a cosine grid.
        Beam 3 fin and beam 4 boom retain distinct offset connector nodes.
        """
        if not isinstance(subdivisions, int) or subdivisions < 1:
            raise ValueError('subdivisions must be a positive integer')
        grids = {}
        for name in self.names:
            old = self.ref.branches[name]['stations']
            grids[name] = [float(a+(b-a)*j/subdivisions)
                          for a, b in zip(old[:-1], old[1:])
                          for j in range(subdivisions)] + [float(old[-1])]
        fin = sorted(set(grids['lower']+grids['upper']))
        return [dict(branch='lower' if s < 0 else 'upper' if s > 0 else 'joint', s=s)
                for s in fin] + [dict(branch='boom', s=s) for s in grids['boom']]

    def _base_state(self, node, side='toward_root'):
        node = self._node(node)
        name = 'upper' if node['branch'] == 'joint' else node['branch']
        s = node['s']
        if side not in ('toward_root', 'toward_tip'):
            raise ValueError('Specify the material trace toward_root or toward_tip')
        branch = self.ref.base[name]
        if s == self.ref.branches[name]['stations'][0]:
            return branch['nodes'][0, :18].copy()
        if side == 'toward_tip':
            for j, station in enumerate(self.ref.branches[name]['stations']):
                if s == station:
                    return branch['nodes'][j, :18].copy()
        parts = [p for p in branch['intervals']
                 if min(p['lo'], p['hi']) <= s <= max(p['lo'], p['hi'])]
        part = parts[0] if side == 'toward_root' else parts[-1]
        return part['base'](s)[:18].copy()

    def sample_nodes(self, nodes, side='toward_root'):
        """Finite loaded geometry. R is FULL material triad, not deformation Q.

        At a point load, r/R are continuous and N/M are one-sided traces.
        The joint sample uses the upper material-positive root trace; both
        root traces are returned separately by solve().
        """
        normalized = [self._node(n) for n in nodes]
        y = np.array([self._base_state(n, side) for n in normalized])
        r, R = y[:, :3], y[:, 3:12].reshape(-1, 3, 3)
        cut = self.ref.fixture['gauge']['cut']
        physical_r = (r-np.array(cut['jig_position']))@self.Q.T + np.array(cut['position'])
        return dict(nodes=normalized, trace_side=side,
                    r_gauge=r, material_R_gauge=R,
                    r_physical=physical_r, material_R_physical=np.einsum('ij,njk->nik', self.Q, R),
                    N_gauge=y[:, 12:15], M_gauge=y[:, 15:18],
                    N_physical=y[:, 12:15]@self.Q.T,
                    M_physical=y[:, 15:18]@self.Q.T)

    def point_load_basis(self, nodes, include_tip_inputs=True):
        """Six force/couple columns per unique node, optionally upper-tip Fy/Mz.

        These are physical-axis unit loads unless solve(gauge_loads=True).
        Every couple is ABOUT ITS NODE, never about an external origin.
        """
        nodes = [self._node(n) for n in nodes]
        identities = [(n['branch'], n['s']) for n in nodes]
        if len(set(identities)) != len(nodes):
            raise ValueError('Repeated nodes, including shared fin root')
        nrhs = 6*len(nodes)+(2 if include_tip_inputs else 0)
        points, labels = [], []
        for j, node in enumerate(nodes):
            wrench = np.zeros((6, nrhs))
            wrench[:, 6*j:6*j+6] = np.eye(6)
            points.append(dict(node=node, wrench=wrench))
            labels.extend([dict(node=node.copy(), component=c)
                           for c in ('Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz')])
        if include_tip_inputs:
            tip = dict(branch='upper', s=float(self.ref.branches['upper']['stations'][-1]))
            wrench = np.zeros((6, nrhs))
            wrench[1, -2], wrench[5, -1] = 1., 1.
            points.append(dict(node=tip, wrench=wrench))
            labels.extend([dict(node=tip.copy(), component='Fy'), dict(node=tip.copy(), component='Mz')])
        return dict(points=points, nrhs=nrhs, labels=labels)

    def _wrench(self, value, nrhs, gauge_loads):
        value = np.asarray(value, dtype=complex)
        if value.shape != (6, nrhs) or not np.isfinite(value).all():
            raise ValueError('Load basis must be finite shape (6,nrhs)')
        if gauge_loads:
            return value.copy()
        return np.concatenate((self.T@value[:3], self.T@value[3:]))

    def _propagate(self, name, initial, loads, frequency, nrhs,
                   density, density_breaks, gauge_loads):
        """One 12x12 fundamental per segment; point-load RHS propagate algebraically.

        Optional continuous density requires an additional 12xnrhs particular
        map. Nodal-only aero does not enlarge the integrated ODE with its RHS.
        """
        transfer_width = 12+(nrhs if density is not None else 0)
        state = initial.copy()
        records, at_points = [], {}
        sign = np.sign(self.ref.branches[name]['stations'][-1]-self.ref.branches[name]['stations'][0])
        root = float(self.ref.branches[name]['stations'][0])
        at_points[root] = dict(before=state.copy(), after=state.copy())
        for part in self.ref.base[name]['intervals']:
            lo, hi = part['lo'], part['hi']
            mid = (lo+hi)/2
            breaks = set(s for s in loads if min(lo, hi) < s < max(lo, hi))
            breaks.update(s for s in density_breaks.get(name, ()) if min(lo, hi) < s < max(lo, hi))
            grid = [lo, *sorted(breaks, reverse=hi < lo), hi]
            for a, b in zip(grid[:-1], grid[1:]):
                def ode(s, flat):
                    self.ops['transfer_rhs'] += 1
                    A, B, _, _ = self.ref.coefficients(part['base'](s), s, mid, part['table'], True)
                    operator = (A-(2*np.pi*frequency)**2*B)*self.scale[None, :]/self.scale[:, None]
                    result = operator@flat.reshape(12, transfer_width)
                    if density is not None:
                        self.ops['density_calls'] += 1
                        w = self._wrench(density(name, s), nrhs, gauge_loads)
                        result[6:, 12:] -= w/self.scale[6:, None]
                    return result.ravel()

                identity = np.zeros((12, transfer_width), complex)
                identity[:, :12] = np.eye(12)
                self.ops['transfer_integrations'] += 1
                sol = solve_ivp(ode, (a, b), identity.ravel(), method='DOP853',
                                rtol=self.ref.rtol, atol=self.ref.rtol*.01, dense_output=True)
                if not sol.success:
                    raise RuntimeError(sol.message)
                transfer = sol.y[:, -1].reshape(12, transfer_width).copy()
                records.append(dict(lo=a, hi=b, solution=sol.sol,
                                    initial_map=state.copy(), transfer=transfer,
                                    transfer_width=transfer_width, nfev=sol.nfev))
                state = transfer[:, :12]@state
                if density is not None:
                    state[:, 18:] += transfer[:, 12:]
                before = state.copy()
                if b in loads:
                    state[6:, 18:] -= sign*loads[b]/self.scale[6:, None]
                at_points[float(b)] = dict(before=before, after=state.copy())
        return dict(initial=initial.copy(), end=state, dense=records, at_points=at_points)

    def solve(self, frequency_Hz, points, samples, nrhs, *, gauge_loads=False,
              density=None, density_breaks=None):
        """One 18x18 boundary factorization with all prescribed load RHS.

        points: [{'node': {'branch', 's'}, 'wrench': array(6,nrhs)}, ...].
        density(branch,s): optional physical force/couple per unit material
        length, array(6,nrhs). It is an additive prescribed RHS, NOT a follower
        law; aero feedback is assembled by the caller from this compliance.
        No poles are moved; unavailable responses retain raw boundary data.
        """
        frequency = float(frequency_Hz)
        if not np.isfinite(frequency) or frequency < 0 or not isinstance(nrhs, int) or nrhs < 1:
            raise ValueError('Finite nonnegative Hz and positive integer nrhs required')
        samples = [self._node(n) for n in samples]
        loads = {name: {} for name in self.names}
        joint = np.zeros((6, nrhs), complex)
        clamp = np.zeros((6, nrhs), complex)
        for point in points:
            node = self._node(point['node'])
            w = self._wrench(point['wrench'], nrhs, gauge_loads)
            if node['branch'] == 'joint':
                joint += w
            elif node['branch'] == 'boom' and node['s'] == self.ref.branches['boom']['stations'][0]:
                clamp += w
            else:
                rows = loads[node['branch']]
                rows[node['s']] = rows.get(node['s'], np.zeros_like(w))+w
        density_breaks = {} if density_breaks is None else density_breaks
        width = 18+nrhs
        initial = np.zeros((12, width), complex)
        initial[6:, :6] = np.eye(6)
        records = dict(boom=self._propagate('boom', initial, loads['boom'], frequency, nrhs,
                                           density, density_breaks, gauge_loads))
        endboom = records['boom']['end']
        d = self.ref.base['boom']['end'][3:12].reshape(3, 3)@self.ref.offset
        # q ordering = [translation/20, spatial rotation].
        kinematic = np.eye(6)
        kinematic[:3, 3:] = -hat(d)/self.scale[0]
        for name, columns in (('upper', slice(6, 12)), ('lower', slice(12, 18))):
            initial = np.zeros((12, width), complex)
            initial[:6] = kinematic@endboom[:6]
            initial[6:, columns] = np.eye(6)
            records[name] = self._propagate(name, initial, loads[name], frequency, nrhs,
                                             density, density_breaks, gauge_loads)
        u0, l0 = records['upper']['initial'], records['lower']['initial']
        junction = endboom[6:]-u0[6:]+l0[6:]
        junction[3:] -= hat(d)@(u0[6:9]-l0[6:9])/self.scale[9]
        # delta(d)xF_connector,0, including the entire loaded fin root action.
        junction[3:] -= hat(self.ref.ffin)@hat(d)@endboom[3:6]/self.scale[9]
        junction[:, 18:] -= joint/self.scale[6:, None]
        junction[3:, 18:] -= hat(d)@joint[:3]/self.scale[9]
        boundary = np.concatenate((records['upper']['end'][6:],
                                   records['lower']['end'][6:], junction))
        matrix, rhs = boundary[:, :18], -boundary[:, 18:]
        row_scale = np.max(abs(matrix), axis=1)
        if not np.all(row_scale > 0):
            raise ValueError('Empty boundary equation')
        scaled = matrix/row_scale[:, None]
        col_scale = np.max(abs(scaled), axis=0)
        if not np.all(col_scale > 0):
            raise ValueError('Empty boundary unknown')
        scaled = scaled/col_scale[None, :]
        forcing = rhs/row_scale[:, None]
        self.ops['boundary_factorizations'] += 1
        lu, piv = lu_factor(scaled)
        rcond, info = get_lapack_funcs('gecon', (scaled,))(lu, np.linalg.norm(scaled, 1))
        if info != 0:
            raise RuntimeError('Boundary condition estimate failed')
        self.ops['boundary_solves'] += 1
        solution_scaled = lu_solve((lu, piv), forcing)
        roots = solution_scaled/col_scale[:, None]
        residual = matrix@roots-rhs
        relative = np.max(abs(residual)/row_scale[:, None], axis=0)/np.maximum(1., np.max(abs(forcing), axis=0))
        denominator = np.linalg.norm(matrix)*np.linalg.norm(roots, axis=0)+np.linalg.norm(rhs, axis=0)
        backward = np.divide(np.linalg.norm(residual, axis=0), denominator,
                             out=np.zeros(nrhs), where=denominator != 0)
        diagnostics = dict(frequency_Hz=frequency, reciprocal_condition=float(rcond),
                           scaled_residuals=relative.tolist(), backward_errors=backward.tolist(),
                           available=bool(rcond >= 1e-12 and np.max(relative) <= 1e-7
                                          and np.max(backward) <= 1e-9 and np.isfinite(roots).all()))
        data = dict(boundary_matrix=matrix, boundary_rhs=rhs, boundary_residual=residual,
                    boundary_scaled_matrix=scaled, boundary_scaled_rhs=forcing,
                    boundary_row_scale=row_scale, boundary_column_scale=col_scale,
                    boundary_lu=lu, boundary_pivots=piv, root_wrenches_scaled=roots,
                    joint_input_wrenches_gauge=joint, clamp_input_wrenches_gauge=clamp,
                    joint_offset_gauge=d, operations=self.ops.copy(), diagnostics=diagnostics)
        # Preserve every endpoint transfer and its complete incoming affine map
        # for later saved-only audits, without serializing SciPy interpolants.
        data['segment_maps'] = {name: [dict(lo=p['lo'], hi=p['hi'],
                                           transfer=p['transfer'], initial_map=p['initial_map'],
                                           nfev=p['nfev']) for p in rec['dense']]
                                for name, rec in records.items()}
        if not diagnostics['available']:
            return data

        def recover(mapping):
            return self.scale[:, None]*(mapping[:, :18]@roots+mapping[:, 18:])

        def sample(node, side):
            name = 'upper' if node['branch'] == 'joint' else node['branch']
            record, s = records[name], node['s']
            if s in record['at_points']:
                return recover(record['at_points'][s]['before' if side == 'toward_root' else 'after'])
            part = next(p for p in record['dense'] if min(p['lo'], p['hi']) < s < max(p['lo'], p['hi']))
            transfer = part['solution'](s).reshape(12, part['transfer_width'])
            mapping = transfer[:, :12]@part['initial_map']
            if density is not None:
                mapping[:, 18:] += transfer[:, 12:]
            return recover(mapping)

        gauge = np.array([sample(n, 'toward_root') for n in samples])
        after = np.array([sample(n, 'toward_tip') for n in samples])
        physical = np.einsum('ij,nkjt->nkit', self.Q,
                             gauge.reshape(len(samples), 4, 3, nrhs)).reshape(len(samples), 12, nrhs)
        omega = 2*np.pi*frequency
        initial_states = {name: recover(r['initial']) for name, r in records.items()}
        end_states = {name: recover(r['end']) for name, r in records.items()}
        # Fin-root joint action excludes separately applied joint input.
        # Upper/lower traces are material-positive; force on fin = -Nu+Nl-FJ.
        fin_reaction = -initial_states['upper'][6:]+initial_states['lower'][6:]-joint
        clamp_reaction = -initial_states['boom'][6:]-clamp
        data.update(samples=samples, base=self.sample_nodes(samples),
                    states_gauge=gauge, states_gauge_toward_tip=after,
                    states_physical=physical, motion_gauge=gauge[:, :6],
                    motion_physical=physical[:, :6],
                    velocity_gauge=1j*omega*gauge[:, :6],
                    acceleration_gauge=-omega**2*gauge[:, :6],
                    velocity_physical=1j*omega*physical[:, :6],
                    acceleration_physical=-omega**2*physical[:, :6],
                    root_states_gauge=initial_states, tip_states_gauge=end_states,
                    clamp_reaction_gauge=clamp_reaction,
                    boom_joint_reaction_gauge=end_states['boom'][6:],
                    fin_joint_reaction_gauge=fin_reaction,
                    clamp_reaction_physical=np.concatenate((self.Q@clamp_reaction[:3], self.Q@clamp_reaction[3:])),
                    fin_joint_reaction_physical=np.concatenate((self.Q@fin_reaction[:3], self.Q@fin_reaction[3:])))
        return data
