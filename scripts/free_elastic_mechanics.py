"""Independent continuous elastic branches on a six-coordinate free carrier.

No production imports. Importing this module performs no calculation. The
declared base has constant material triads and tensile resultants, with finite
axial and shear compliance. Its axial extension is exact; neither a nonlinear
equilibrium solve nor a fitted displacement field is used here.

Coordinates are physical Galilean/Earth perturbations with exp(+i*omega*t).
The carrier is xi=[translation, spatial rotation]. Branch nodes use ABSOLUTE
motion e=[translation, spatial rotation], not motion relative to the carrier.
Continuous material mass occurs once in the rod equation A-omega**2*B; the
separate carrier mass contains only the explicit carrier point body.

Sources: Drela steady Eqs.16--20 and spatial force/moment balance; unsteady
Eqs.16--27,37--40. See the source-only contract in the study reference-review.
This module does not evaluate aerodynamics or claim historical discrete parity.
"""
from copy import deepcopy

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import get_lapack_funcs, lu_factor, lu_solve


def hat(value):
    x, y, z = np.asarray(value)
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]],
                    dtype=np.result_type(value, float))


def _finite(value, shape, name):
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ValueError(name + ' has invalid shape or nonfinite entries')
    return result.copy()


def spatial_mass(mass, offset, centroid_inertia):
    """Real kinetic-energy matrix about an axis/origin, in spatial axes.

    v_cg=v_axis-hat(offset)*omega. Centroid inertia must not already contain
    the parallel-axis contribution. All measures are original material length
    for a section and ordinary physical mass for the carrier point body.
    """
    S = hat(offset)
    return np.block([[mass*np.eye(3), -mass*S],
                     [mass*S, centroid_inertia-mass*(S@S)]])


def transport(arm):
    """Map [force,couple about application point] to an origin wrench."""
    result = np.eye(6)
    result[3:, :3] = hat(arm)
    return result


def body_fixed_derivative(wrench):
    """d(Rcarrier*wrench)/d[x,phi] at the identity carrier attitude."""
    result = np.zeros((6, 6))
    result[:3, 3:] = -hat(wrench[:3])
    result[3:, 3:] = -hat(wrench[3:])
    return result


class FreeElasticMechanics:
    """Two independent distributed rods joined to a massive rigid carrier.

    base_nodes(n) supplies wing-root-to-tip, then fin-root-to-tip receivers;
    coincident joint nodes remain distinct. green(...) returns rows
    [carrier xi6, absolute node e6] and columns
    [six physical force/couple inputs per receiving node, six carrier inputs].
    The final six columns are Fx,Fy,Fz,Mx,My,Mz about carrier O. Moments at
    receiving nodes are intrinsic couples about those nodes, not global moments.
    """

    names = ('wing', 'fin')

    def __init__(self, fixture, rtol=1e-11):
        self.fixture = deepcopy(fixture)
        self.rtol = float(rtol)
        if not np.isfinite(self.rtol) or not 0 < self.rtol <= 1e-6:
            raise ValueError('A fixed positive integration tolerance <=1e-6 is required')
        if fixture.get('schema') != 'openswing-free-elastic-fixture-v1':
            raise ValueError('Unsupported independent fixture schema')
        if set(fixture['branches']) != set(self.names):
            raise ValueError('The declared wing and fin branches are required')
        self.origin = _finite(fixture['carrier']['origin'], (3,), 'carrier origin')
        self.V0 = np.array([-float(fixture['speed']), 0., 0.])
        if not np.array_equal(fixture['gravity_override'], np.zeros(3)):
            raise ValueError('This reference requires zero physical gravity')
        for key in ('attitude', 'rates', 'acceleration', 'angular_acceleration'):
            if not np.array_equal(fixture['condition'][key], np.zeros(3)):
                raise ValueError('The reference tangent is about zero carrier attitude/rates/accelerations')
        self.branches = {}
        for name in self.names:
            raw = fixture['branches'][name]
            root = _finite(raw['root'], (3,), name + ' root')
            c = _finite(raw['chord_direction'], (3,), name + ' chord direction')
            s = _finite(raw['span_direction'], (3,), name + ' span direction')
            R = np.column_stack((c, s, np.cross(c, s)))
            if np.max(abs(R.T@R-np.eye(3))) > 2e-13 or np.linalg.det(R) <= 0:
                raise ValueError('Full material frame must be orthonormal and right handed')
            stiffness = {key: float(raw['stiffness'][key])
                         for key in ('EA', 'GKc', 'GKn', 'EIcc', 'GJ', 'EInn')}
            if not all(np.isfinite(v) and v > 0 for v in stiffness.values()):
                raise ValueError('All six declared stiffnesses must be finite and positive')
            length, tension, mass = map(float, (raw['length'], raw['tension'], raw['mass_per_length']))
            if not all(np.isfinite(v) and v > 0 for v in (length, tension, mass)):
                raise ValueError('Positive length, tensile preload and real line mass are required')
            D = R@np.diag([1/stiffness['GKc'], 1/stiffness['EA'], 1/stiffness['GKn']])@R.T
            C = R@np.diag([1/stiffness['EIcc'], 1/stiffness['GJ'], 1/stiffness['EInn']])@R.T
            N = tension*s
            tangent = s+D@N
            d = R@_finite(raw['cg_material'], (3,), name + ' material CG offset')
            intrinsic = np.asarray(raw['inertia_per_length'], dtype=float)
            intrinsic = np.diag(intrinsic) if intrinsic.shape == (3,) else intrinsic
            intrinsic = _finite(intrinsic, (3, 3), name + ' material centroid inertia')
            if np.max(abs(intrinsic-intrinsic.T)) > 2e-14 or np.min(np.linalg.eigvalsh(intrinsic)) <= 0:
                raise ValueError('Positive definite symmetric intrinsic section inertia is required')
            inertia = R@intrinsic@R.T
            B6 = spatial_mass(mass, d, inertia)
            A = np.zeros((12, 12))
            # Differentiate r'=s_hat+D*N, including rotation of D and loaded N.
            A[:3, 3:6] = -hat(tangent)+D@hat(N)
            A[:3, 6:9] = D
            A[3:6, 9:12] = C       # M0=0 for this exact tensile base.
            A[9:12] = hat(N)@A[:3]
            A[9:12, 6:9] -= hat(tangent)
            B = np.zeros((12, 12))
            B[6:12, :6] = B6
            self.branches[name] = dict(root=root, root_arm=root-self.origin,
                frame=R, span=s, tangent=tangent, length=length, tension=tension,
                N=N, M=np.zeros(3), mass_per_length=mass, cg_offset=d,
                centroid_inertia_per_length=inertia, mass_block=B6,
                force_compliance=D, moment_compliance=C, A=A, B=B)
        carrier = fixture['carrier']
        mass = float(carrier['mass'])
        d = _finite(carrier['cg'], (3,), 'carrier CG offset')
        inertia = _finite(carrier['inertia'], (3, 3), 'carrier centroid inertia')
        if not np.isfinite(mass) or mass <= 0 or np.max(abs(inertia-inertia.T)) > 2e-14 or np.min(np.linalg.eigvalsh(inertia)) <= 0:
            raise ValueError('Carrier mass and centroid tensor must be positive')
        self.carrier_mass = spatial_mass(mass, d, inertia)
        self.length_scale = float(fixture['normalization']['motion_length'])
        self.force_scale = max(1., sum(b['tension'] for b in self.branches.values()))
        if not np.isfinite(self.length_scale) or self.length_scale <= 0:
            raise ValueError('Positive declared motion length scale required')
        L, F = self.length_scale, self.force_scale
        self.state_scale = np.array([L]*3+[1.]*3+[F]*3+[F*L]*3)
        self.motion_scale = self.state_scale[:6]
        self.wrench_scale = self.state_scale[6:]
        self.operations = dict(green_calls=0, transfer_integrations=0,
            transfer_rhs=0, boundary_factorizations=0, boundary_solves=0,
            nonlinear_equilibrium_solves=0, production_evaluations=0,
            algebraic_diagnostic_calls=0)

    def coefficients(self, branch):
        """Unscaled physical A/B and kinetic-energy section data, copies only."""
        b = self.branches[branch]
        return {key: b[key].copy() for key in
                ('A', 'B', 'mass_block', 'force_compliance', 'moment_compliance')}

    def static_invariants(self):
        """Algebraic checks, with no integration, solve or physical evaluation.

        A constant absolute translation has zero static rod residual. A common
        rotation of geometry AND tensile loads has only the expected rigid
        position derivative. This is a mechanical coordinate identity, not an
        assertion that rotating an aircraft in a fixed wind leaves aero fixed.
        The rigid-configuration real mass integral is an exact quadratic
        polynomial here, so the three-point Simpson rule is an algebraic
        identity for this affine base, not a quadrature convergence claim.
        """
        self.operations['algebraic_diagnostic_calls'] += 1
        rows = {}
        preload = np.zeros(6)
        rigid_mass = self.carrier_mass.copy()
        translations = np.zeros((12, 3))
        translations[:3] = np.eye(3)
        for name, b in self.branches.items():
            sample_rows = []
            for station in (0., b['length']/2, b['length']):
                arm = b['root_arm']+station*b['tangent']
                rotations = np.zeros((12, 3))
                rotations[:3] = -hat(arm)
                rotations[3:6] = np.eye(3)
                rotations[6:9] = -hat(b['N'])
                expected = np.zeros((12, 3))
                expected[:3] = -hat(b['tangent'])
                sample_rows.append(b['A']@rotations-expected)
            d = b['cg_offset']
            Jv = np.column_stack((np.eye(3), -hat(d)))
            Jw = np.column_stack((np.zeros((3, 3)), np.eye(3)))
            gram = b['mass_per_length']*(Jv.T@Jv)+Jw.T@b['centroid_inertia_per_length']@Jw
            integration = np.zeros((6, 6))
            for station, weight in ((0., 1.), (b['length']/2, 4.), (b['length'], 1.)):
                arm = b['root_arm']+station*b['tangent']
                rigid = np.eye(6)
                rigid[:3, 3:] = -hat(arm)
                integration += weight*(rigid.T@b['mass_block']@rigid)*b['length']/6
            rigid_mass += integration
            tip_arm = b['root_arm']+b['length']*b['tangent']
            preload += transport(tip_arm)@np.r_[b['N'], b['M']]
            rows[name] = dict(static_translation_residual=b['A']@translations,
                static_rigid_rotation_residual=np.asarray(sample_rows),
                section_kinetic_gram=gram,
                section_kinetic_gram_difference=b['mass_block']-gram,
                rigid_real_mass_integral=integration)
        balancer = np.r_[self.fixture['base']['carrier_balancer_force'],
                         self.fixture['base']['carrier_balancer_moment']]
        return dict(branches=rows, tensile_preload_wrench=preload,
            carrier_balancer=balancer, base_rigid_load_balance=preload+balancer,
            rigid_real_mass=rigid_mass,
            rigid_real_mass_symmetry=rigid_mass-rigid_mass.T,
            physical_gravity=np.zeros(3),
            interpretation='Exact-base mechanical invariants; not aerodynamic rotation invariance or a coupled-response result.')

    def base_nodes(self, n):
        """Exact stretched geometry and immutable material sampling convention."""
        if type(n) is not int or n not in self.fixture['mesh']['lifting_intervals']:
            raise ValueError('Use a predeclared lifting interval count')
        nodes, positions, frames, ends, fractions, owners, node_owners = [], [], [], [], [], [], []
        s0, s1, sm, branch_slices = [], [], [], {}
        for index, name in enumerate(self.names):
            b = self.branches[name]
            grid = b['length']*(1-np.cos(np.pi*np.arange(n+1)/n))/2
            grid[0], grid[-1] = 0., b['length']
            mid = b['length']*(1-np.cos(np.pi*(np.arange(n)+.5)/n))/2
            first = len(nodes)
            branch_slices[name] = [first, first+n+1]
            for station in grid:
                nodes.append(dict(branch=name, s=float(station), t=float(station-b['length']/2)))
                positions.append(b['root']+station*b['tangent'])
                frames.append(b['frame'])
                node_owners.append(index)
            ends.extend(zip(np.arange(first, first+n), np.arange(first+1, first+n+1)))
            fractions.extend((mid-grid[:-1])/np.diff(grid))
            s0.extend(grid[:-1]); s1.extend(grid[1:]); sm.extend(mid)
            owners.extend([index]*n)
        return dict(n=n, nodes=nodes, positions=np.asarray(positions),
            material_frames=np.asarray(frames), endpoints=np.asarray(ends, dtype=int),
            fractions=np.asarray(fractions), panel_branch=np.asarray(owners, dtype=int),
            node_branch=np.asarray(node_owners, dtype=int),
            panel_s0=np.asarray(s0), panel_s1=np.asarray(s1), panel_sm=np.asarray(sm),
            branch_node_slices=branch_slices, carrier_origin=self.origin.copy(),
            material_measure='Original branch length; aero length uses stretched nodal geometry.')

    def _segment(self, name, lo, hi, omega):
        """Continuous fundamental plus integrated real-inertia wrench map.

        Only a 12-column fundamental is integrated. Its six additional output
        rows accumulate inertia about carrier O; they do not modify the rod.
        All receiving-node and carrier RHS use the same transfer afterwards.
        """
        b = self.branches[name]
        scale, ws = self.state_scale, self.wrench_scale
        operator = (b['A']-omega**2*b['B'])*scale[None, :]/scale[:, None]
        inertia = omega**2*b['mass_block']*self.motion_scale[None, :]

        def rhs(station, values):
            self.operations['transfer_rhs'] += 1
            fundamental = values.reshape(18, 12)[:12]
            arm = b['root_arm']+station*b['tangent']
            mass_rows = (transport(arm)@inertia@fundamental[:6])/ws[:, None]
            return np.concatenate((operator@fundamental, mass_rows)).ravel()

        initial = np.zeros((18, 12))
        initial[:12] = np.eye(12)
        self.operations['transfer_integrations'] += 1
        result = solve_ivp(rhs, (float(lo), float(hi)), initial.ravel(),
            method='DOP853', rtol=self.rtol, atol=self.rtol*.01, dense_output=False)
        raw = dict(branch=name, lo=float(lo), hi=float(hi), success=bool(result.success),
                   message=str(result.message), nfev=result.nfev,
                   transfer=result.y[:,-1].reshape(18, 12).copy())
        if not result.success:
            error = RuntimeError('Continuous branch transfer failed: '+result.message)
            error.saved_segment = raw
            raise error
        return raw

    def green(self, frequency_Hz, n, body_fixed_nodal_loads, carrier_balancer):
        """One full moving-root boundary solve, with all nodal/carrier RHS.

        body_fixed_nodal_loads is (nn,6) in base body/Earth axes: Q32 aero
        counterloads PLUS the positive tensile tip loads, each couple about its
        node. carrier_balancer is a six-wrench about O. All are constant in
        BODY axes; their Earth derivatives rotate with carrier phi, never with
        local elastic theta. The base aero cancels its counterloads nodewise.

        The Green map is mechanical only. The caller supplies incremental
        aerodynamic nodal wrenches and closes circulation feedback separately.
        No additional apparent or frame-coupling mass belongs outside this map.
        The physical_global_balance diagnostic uses the COUPLED steady base:
        aerodynamic loads and their fixed counterloads cancel nodewise, so
        only the tensile tip loads contribute displaced steady-force arms.
        It is not a standalone balance about a base containing counterloads
        without their equal steady aerodynamic loads.
        """
        self.operations['green_calls'] += 1
        frequency = float(frequency_Hz)
        if not np.isfinite(frequency) or frequency <= 0:
            raise ValueError('A fixed positive frequency is required for the free system')
        omega = 2*np.pi*frequency
        base = self.base_nodes(n)
        nn, nrhs = len(base['nodes']), 6*len(base['nodes'])+6
        fixed = _finite(body_fixed_nodal_loads, (nn, 6), 'body-fixed nodal loads')
        balancer = _finite(carrier_balancer, (6,), 'carrier balancer')
        width = 18+nrhs
        scale, ws, es = self.state_scale, self.wrench_scale, self.motion_scale
        physical_carrier = np.zeros((6, width))
        physical_carrier[:, 12:18] = np.diag(es)

        def node_load(index):
            value = np.zeros((6, width))
            value[:, 12:18] = body_fixed_derivative(fixed[index])*es[None, :]
            value[:, 18+6*index:18+6*index+6] = np.eye(6)
            return value

        node_maps = [None]*nn
        initial_maps, end_maps, mass_maps, segments, root_external = [], [], [], [], []
        carrier_equation = np.zeros((6, width))
        for bi, name in enumerate(self.names):
            b = self.branches[name]
            first, end = base['branch_node_slices'][name]
            mapping = np.zeros((12, width))
            root_kinematics = np.eye(6)
            root_kinematics[:3, 3:] = -hat(b['root_arm'])
            mapping[:6, 12:18] = root_kinematics*es[None, :]/es[:, None]
            mapping[6:, 6*bi:6*bi+6] = np.eye(6)
            initial_maps.append(mapping.copy())
            node_maps[first] = mapping.copy()
            mass = np.zeros((6, width))
            grid = [base['nodes'][i]['s'] for i in range(first, end)]
            for local, (lo, hi) in enumerate(zip(grid[:-1], grid[1:]), 1):
                record = self._segment(name, lo, hi, omega)
                transfer = record['transfer']
                record['initial_map'] = mapping.copy()
                mass += ws[:, None]*(transfer[12:]@mapping)
                mapping = transfer[:12]@mapping
                index = first+local
                # A receiving-node load jumps force/couple only. Geometry and
                # spatial rotation remain continuous across the point.
                node_maps[index] = mapping.copy()  # trace toward the root
                mapping[6:] -= node_load(index)/ws[:, None]
                record['after_map'] = mapping.copy()
                segments.append(record)
            end_maps.append(mapping.copy())       # after tip applied load
            mass_maps.append(mass)
            root_load = node_load(first)
            root_external.append(root_load)
            root_traction = ws[:, None]*initial_maps[-1][6:]
            carrier_equation += transport(b['root_arm'])@(root_traction+root_load)
            # Differentiate the moving rigid-root arm against its TOTAL
            # steady reaction N0. Base aero/counterloads cancel nodewise.
            carrier_equation[3:, 15:18] += hat(b['N'])@hat(b['root_arm'])
        carrier_inertia = omega**2*self.carrier_mass@physical_carrier
        balancer_increment = body_fixed_derivative(balancer)@physical_carrier
        carrier_equation += carrier_inertia+balancer_increment
        carrier_equation[:, 18+6*nn:] += np.eye(6)
        boundary = np.concatenate((end_maps[0][6:], end_maps[1][6:],
                                    carrier_equation/ws[:, None]))
        matrix, rhs = boundary[:, :18], -boundary[:, 18:]
        rows = np.max(abs(matrix), axis=1)
        if np.any(rows <= 0) or not np.isfinite(matrix).all():
            raise ValueError('Empty or nonfinite independent mechanical boundary row')
        row_scaled = matrix/rows[:, None]
        columns = np.max(abs(row_scaled), axis=0)
        if np.any(columns <= 0):
            raise ValueError('Empty independent mechanical boundary column')
        scaled = row_scaled/columns[None, :]
        forcing = rhs/rows[:, None]
        self.operations['boundary_factorizations'] += 1
        lu, pivots = lu_factor(scaled)
        rcond, info = get_lapack_funcs('gecon', (scaled,))(lu, np.linalg.norm(scaled, 1))
        if info:
            raise RuntimeError('Independent boundary condition estimator failed')
        self.operations['boundary_solves'] += 1
        solution = lu_solve((lu, pivots), forcing)/columns[:, None]
        residual = matrix@solution-rhs
        relative = np.max(abs(residual)/rows[:, None], axis=0)/np.maximum(1., np.max(abs(forcing), axis=0))
        denominator = np.linalg.norm(matrix)*np.linalg.norm(solution, axis=0)+np.linalg.norm(rhs, axis=0)
        backward = np.divide(np.linalg.norm(residual, axis=0), denominator,
                             out=np.zeros(nrhs), where=denominator != 0)
        diagnostics = dict(frequency_Hz=frequency, reciprocal_condition=float(rcond),
            scaled_residuals=relative.tolist(), backward_errors=backward.tolist(),
            available=bool(rcond >= 1e-12 and np.max(relative) <= 1e-7
                           and np.max(backward) <= 1e-9 and np.isfinite(solution).all()))
        output = dict(base=base, frequency_Hz=frequency, n=n, nrhs=nrhs,
            row_order='carrier xi6, then absolute receiving-node [u,theta]',
            column_order='six physical force/couple inputs per receiving node, then carrier Fx,Fy,Fz,Mx,My,Mz',
            body_fixed_nodal_loads=fixed, carrier_balancer=balancer,
            state_scale=scale.copy(), boundary_matrix=matrix, boundary_rhs=rhs,
            boundary_residual=residual, boundary_scaled_matrix=scaled,
            boundary_scaled_rhs=forcing, boundary_row_scale=rows,
            boundary_column_scale=columns, boundary_solution_scaled=solution,
            boundary_lu=lu, boundary_pivots=pivots, diagnostics=diagnostics,
            segment_maps=segments, operations=self.operations.copy())
        if not diagnostics['available']:
            return output

        def recover(mapping):
            return mapping[:, :18]@solution+mapping[:, 18:]

        carrier_motion = recover(physical_carrier)
        states = np.array([scale[:, None]*recover(mapping) for mapping in node_maps])
        roots = np.array([ws[:, None]*recover(mapping[6:]) for mapping in initial_maps])
        root_applied = np.array([recover(mapping) for mapping in root_external])
        carrier_on_branch = -(roots+root_applied)
        on_carrier = []
        for bi, name in enumerate(self.names):
            b = self.branches[name]
            value = transport(b['root_arm'])@(roots[bi]+root_applied[bi])
            value[3:] += hat(b['N'])@hat(b['root_arm'])@carrier_motion[3:]
            on_carrier.append(value)
        inertial = np.array([recover(carrier_inertia),
                             recover(mass_maps[0]), recover(mass_maps[1])])
        # Independent physical global balance from all applied node loads,
        # displaced preload arms and separately integrated distributed inertia.
        applied = recover(balancer_increment)
        applied[:, 6*nn:] += np.eye(6)
        for i, node in enumerate(base['nodes']):
            applied += transport(base['positions'][i]-self.origin)@recover(node_load(i))
            b = self.branches[node['branch']]
            if node['s'] == b['length']:
                applied[3:] += -hat(b['N'])@(states[i, :3]-carrier_motion[:3])
        global_balance = applied+inertial.sum(axis=0)
        lambda_ = 1j*omega
        velocity_body = lambda_*carrier_motion[:3]+hat(self.V0)@carrier_motion[3:]
        output.update(carrier_motion=carrier_motion, node_states=states,
            node_motion=states[:, :6],
            motion_map=np.concatenate((carrier_motion, states[:, :6].reshape(6*nn, nrhs))),
            carrier_velocity_body=velocity_body,
            carrier_rates_body=lambda_*carrier_motion[3:],
            carrier_acceleration_body=-omega**2*carrier_motion[:3],
            carrier_angular_acceleration_body=-omega**2*carrier_motion[3:],
            root_tractions=roots, root_applied_wrenches=root_applied,
            carrier_on_branch=carrier_on_branch,
            branch_on_carrier_origin=np.asarray(on_carrier),
            inertia_wrenches_origin=inertial,
            carrier_balance=recover(carrier_equation),
            physical_global_balance=global_balance,
            physical_global_applied_wrench=applied,
            tip_boundary_residual=np.array([ws[:, None]*recover(m[6:]) for m in end_maps]),
            real_mass_blocks=dict(carrier=self.carrier_mass.copy(),
                **{name: b['mass_block'].copy() for name, b in self.branches.items()}))
        return output
