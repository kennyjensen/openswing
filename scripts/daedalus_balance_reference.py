"""Independent loaded-Daedalus equilibrium assembly and frame kinematics.

This module imports no production code and evaluates no aerodynamic or mass
law. External force/couple arrays are explicit inputs about the current nodes.
It supports complex perturbations about the saved stationary configuration.
The selected residual rows exclude beam compatibility and circulation, which
have separate independent checks. Actual rigid-attachment geometry is included.

Conventions: spatial body-frame resultants N/M act positively at element a;
joint reaction F/T is on its first node, with T specified about the second.
The six free-flight rows sum external loads before internal/support assembly.
Primary identities: Drela unsteady Eqs. 12--21 and 263--267.
"""
import numpy as np
from elastic_fin_kinematics import logarithm


def cross_matrix(v):
    """Matrix [v] such that [v]w=v cross w, without conjugation."""
    v = np.asarray(v)
    out = np.zeros(v.shape[:-1] + (3, 3), dtype=v.dtype)
    out[..., 0, 1], out[..., 0, 2] = -v[..., 2], v[..., 1]
    out[..., 1, 0], out[..., 1, 2] = v[..., 2], -v[..., 0]
    out[..., 2, 0], out[..., 2, 1] = -v[..., 1], v[..., 0]
    return out


def _rotation_coefficients(v):
    t2 = np.sum(np.asarray(v)**2, axis=-1)
    small = np.abs(t2) < 1e-8
    a, b, c = [np.empty_like(t2) for _ in range(3)]
    q = t2[small]
    a[small] = 1 - q/6 + q*q/120 - q*q*q/5040
    b[small] = .5 - q/24 + q*q/720 - q*q*q/40320
    c[small] = 1/6 - q/120 + q*q/5040 - q*q*q/362880
    q = t2[~small]
    t = np.sqrt(q)
    a[~small], b[~small], c[~small] = np.sin(t)/t, (1-np.cos(t))/q, (t-np.sin(t))/(q*t)
    return a, b, c


def rotation(v):
    v = np.asarray(v)
    a, b, _ = _rotation_coefficients(v)
    h = cross_matrix(v)
    return np.eye(3) + a[..., None, None]*h + b[..., None, None]*(h@h)


def left_jacobian(v):
    v = np.asarray(v)
    _, b, c = _rotation_coefficients(v)
    h = cross_matrix(v)
    return np.eye(3) + b[..., None, None]*h + c[..., None, None]*(h@h)


def euler_kinematics(angles):
    """Radians: Earth-from-body rotation and ASW Euler-rate-to-body-rate map.

    The three elementary rotations have angles (-bank,+elevation,-heading).
    E is unsteady Eq. 12; it is not the usual aerospace yaw/pitch/roll map.
    """
    phi, theta, psi = angles
    cp, ct, cy = np.cos(angles)
    sp, st, sy = np.sin(angles)
    r = np.array([[cy*ct, -cy*st*sp+sy*cp, cy*st*cp+sy*sp],
                  [-sy*ct, sy*st*sp+cy*cp, -sy*st*cp+cy*sp],
                  [-st, -ct*sp, ct*cp]])
    e = np.array([[-1., 0., st], [0., cp, sp*ct], [0., sp, -cp*ct]])
    return r, e


def _inverse_euler_rate(angles, omega):
    phi, theta, _ = angles
    lateral = np.sin(phi)*omega[1] - np.cos(phi)*omega[2]
    return np.array([-omega[0] + np.tan(theta)*lateral,
                     np.cos(phi)*omega[1] + np.sin(phi)*omega[2],
                     lateral/np.cos(theta)])


class BalanceReference:
    """Prepared material topology; no native target or physics helper is read.

    ``evaluate(inputs,z,zdot,external_force,external_moment)`` accepts the
    captured physical-input schema and returns selected normalized rows plus
    physical contribution arrays. ``inputs`` needs only r/Q: all descriptor
    kinematics and frame pose are independently decoded from raw z/zdot.
    External moments are about each node, not about the global moment origin.
    """

    def __init__(self, fixture, base_inputs):
        self.fixture = fixture
        layout = fixture['layout']
        self.nn, self.ne = int(layout['nodes']), int(layout['elements'])
        self.ns = int(layout['network_size'])
        self.size = int(layout['frame']['start'] + layout['frame']['width'])
        if (self.nn, self.ne, self.ns, self.size) != (108, 103, 1384, 2044):
            raise ValueError('This reference is frozen to the corrected C16 topology')
        self.L, self.F, self.V, self.W = [fixture['scales'][k] for k in ('L', 'F', 'V', 'W')]
        self.FL = self.F*self.L
        self.ends = np.asarray(fixture['ends'], dtype=int)
        self.a, self.b = self.ends.T
        self.rj = np.empty((self.nn, 3))
        self.offa, self.offb = np.empty((self.ne, 3)), np.empty((self.ne, 3))
        self.stations = {}
        for beam in fixture['beams']:
            ids, elements = np.asarray(beam['node_ids'], int), np.asarray(beam['element_ids'], int)
            self.rj[ids] = beam['jig_nodes']
            self.offa[elements], self.offb[elements] = beam['offa'], beam['offb']
            self.stations[int(beam['index'])] = (np.asarray(beam['stations']), ids)
        self.base = fixture['loaded_base']
        self.base_x = np.asarray(self.base['x'])
        self.origin = np.asarray(fixture['reference'])[1]
        self.acceleration_origin = np.asarray(fixture['reference'])[2]
        self.load_start = int(layout['internal_loads']['start'])
        self.reaction_start = int(layout['reactions']['start'])
        self.circulation_start = int(layout['circulation']['start'])
        self.operating_start = int(layout['operating']['start'])
        self.velocity_start = int(layout['local_velocity']['start'])
        self.frame_start = int(layout['frame']['start'])
        expected_variables = [p+'.'+a for p in ('acceleration', 'angular_acceleration') for a in 'xyz']
        if layout['operating']['variables'] != expected_variables:
            raise ValueError('Expected canonical six free-flight load equations')
        self.operating_scales = np.asarray(layout['operating']['scales'])
        self.base_acceleration = np.asarray(base_inputs['motion']['acceleration'])
        self.base_alpha = np.asarray(base_inputs['motion']['angular_acceleration'])
        self.base_angles = np.asarray(self.base['attitude_deg'])*np.pi/180
        self.base_U, self.base_Omega = np.asarray(self.base['U']), np.asarray(self.base['Omega'])
        r0, _ = euler_kinematics(self.base_angles)
        self.base_Udot = self._acceleration_at_origin(self.base_acceleration, self.base_alpha,
                                                     self.base_Omega) - np.cross(self.base_Omega, self.base_U)
        self.base_pdot = r0@self.base_U
        self.base_angle_dot = _inverse_euler_rate(self.base_angles, self.base_Omega)
        self.constraints = []
        offset = 0
        for kind in ('ground', 'joint'):
            for row in fixture['records'][kind]:
                if int(row[-1]) != 0:
                    raise ValueError('This fixture must contain only rigid constraints')
                i = self.node(row[0], row[1] if kind == 'ground' else row[2])
                j = None if kind == 'ground' else self.node(row[1], row[3])
                self.constraints.append((kind, i, j, offset))
                offset += 6
        self.struts = np.asarray(fixture['records']['strut'])
        if len(self.constraints) != 5 or offset != 30 or self.struts.shape != (2, 10):
            raise ValueError('Expected one gauge, four joints, and two bilateral braces')
        if sum(c[0] == 'ground' for c in self.constraints) != 1:
            raise ValueError('Expected one ground gauge')
        self.row_indices = np.r_[np.arange(6*self.ne, self.circulation_start),
                                 np.arange(self.operating_start, self.size)]

    def node(self, beam, station):
        ts, ids = self.stations[int(beam)]
        matches = np.flatnonzero(np.abs(ts-station) <= 1e-10*max(1., abs(station)))
        if len(matches) != 1:
            raise ValueError('Attachment must have one exact physical station')
        return int(ids[matches[0]])

    def _acceleration_at_origin(self, acceleration, alpha, omega):
        arm = -self.acceleration_origin
        return acceleration + np.cross(alpha, arm) + np.cross(omega, np.cross(omega, arm))

    def physical_from_raw(self, z, zdot):
        """Independent input chart, including nonzero base trajectory drift."""
        z, zdot = np.asarray(z), np.asarray(zdot)
        if z.shape != (self.size,) or zdot.shape != z.shape:
            raise ValueError('Expected complete 2044-state vectors')
        q, qdot = z[:6*self.nn].reshape(self.nn, 6), zdot[:6*self.nn].reshape(self.nn, 6)
        local = z[self.velocity_start:self.frame_start].reshape(2, self.nn, 3)
        local_dot = zdot[self.velocity_start:self.frame_start].reshape(2, self.nn, 3)
        frame = z[self.frame_start:].reshape(4, 3)
        frame_dot = zdot[self.frame_start:].reshape(4, 3)
        angles = self.base_angles + frame[3]
        orientation, e = euler_kinematics(angles)
        op = z[self.operating_start:self.ns]*self.operating_scales
        return dict(r=np.asarray(self.base['r'])+self.L*q[:, :3],
                    Q=rotation(q[:, 3:])@np.asarray(self.base['Q']),
                    u=self.V*local[0], w=self.W*local[1],
                    udot=self.V*local_dot[0], wdot=self.W*local_dot[1],
                    U=self.base_U+self.V*frame[0], Omega=self.base_Omega+self.W*frame[1],
                    position=np.asarray(self.base['position'])+self.L*frame[2],
                    attitude_deg=angles*180/np.pi, orientation=orientation, euler_matrix=e,
                    acceleration=self.base_acceleration+op[:3], alpha=self.base_alpha+op[3:],
                    Udot=self.base_Udot+self.V*frame_dot[0],
                    Omegadot=self.base_alpha+self.W*frame_dot[1],
                    pdot=self.base_pdot+self.L*frame_dot[2],
                    angle_dot=self.base_angle_dot+frame_dot[3],
                    q_angle=q[:, 3:], qdot=qdot)

    def kinematics(self, z, zdot):
        p = self.physical_from_raw(z, zdot)
        rows = dict(
            node_translation=(self.L*p['qdot'][:, :3]-p['u'])/self.V,
            node_rotation=(np.einsum('nij,nj->ni', left_jacobian(p['q_angle']), p['qdot'][:, 3:])-p['w'])/self.W,
            frame_velocity=(p['Udot']+np.cross(p['Omega'], p['U'])-
                            self._acceleration_at_origin(p['acceleration'], p['alpha'], p['Omega']))/(self.V*self.W),
            frame_rate=(p['Omegadot']-p['alpha'])/self.W**2,
            frame_position=(p['pdot']-p['orientation']@p['U'])/self.V,
            frame_angles=(p['euler_matrix']@p['angle_dot']-p['Omega'])/self.W)
        return np.concatenate([v.ravel() for v in rows.values()]), rows, p

    def evaluate(self, inputs, z, zdot, external_force, external_moment):
        """Assemble supplied external loads; all returned moments are explicit.

        The internal/constraint/brace components are physical node wrenches.
        ``global_external`` excludes every such support/internal component.
        ``component_globals`` are diagnostics about the fixed moment origin.
        """
        z, zdot = np.asarray(z), np.asarray(zdot)
        r, q = np.asarray(inputs['r']), np.asarray(inputs['Q'])
        fext, mext = np.asarray(external_force), np.asarray(external_moment)
        if r.shape != (self.nn, 3) or q.shape != (self.nn, 3, 3) or fext.shape != r.shape or mext.shape != r.shape:
            raise ValueError('Expected 108 physical node poses and node wrenches')
        dtype = np.result_type(z, zdot, r, q, fext, mext)
        x = self.base_x + z[:self.ns]
        resultants = x[self.load_start:self.reaction_start].reshape(self.ne, 6)
        n, m = resultants[:, :3]*self.F, resultants[:, 3:]*self.FL
        oa = np.einsum('nij,nj->ni', q[self.a], self.offa)
        ob = np.einsum('nij,nj->ni', q[self.b], self.offb)
        chord = r[self.b]+ob-r[self.a]-oa
        # Each element conserves global force and moment; the dr cross N term
        # carries the complete loaded-resultant geometric tangent.
        ef = np.stack((n, -n), axis=1)
        em = np.stack((m+np.cross(.5*chord+oa, n),
                       -m+np.cross(.5*chord-ob, n)), axis=1)
        components = {name:np.zeros((self.nn, 6), dtype=dtype)
                      for name in ('element', 'joint', 'ground', 'brace')}
        for end, ids in enumerate((self.a, self.b)):
            np.add.at(components['element'][:, :3], ids, ef[:, end])
            np.add.at(components['element'][:, 3:], ids, em[:, end])
        reaction_rows = x[self.reaction_start:self.circulation_start]
        reactions, constraint_geometry = [], []
        for kind, i, j, start in self.constraints:
            force, torque = reaction_rows[start:start+3]*self.F, reaction_rows[start+3:start+6]*self.FL
            component = components[kind]
            first_moment = torque if j is None else torque+np.cross(r[j]-r[i], force)
            component[i, :3] += force
            component[i, 3:] += first_moment
            if j is not None:
                component[j, :3] -= force
                component[j, 3:] -= torque
                constraint_geometry.extend(((r[j]-r[i]-q[i]@(self.rj[j]-self.rj[i]))/self.L,
                                            logarithm(q[i].T@q[j])))
            else:
                constraint_geometry.extend(((r[i]-self.rj[i])/self.L, logarithm(q[i])))
            reactions.append(np.r_[force, first_moment])
        brace_rows = []
        for row in self.struts:
            node = self.node(row[0], row[1])
            arm = q[node]@(row[2:5]-self.rj[node])
            position, anchor = r[node]+arm, row[5:8]
            rest_length = np.sqrt(np.sum((anchor-row[2:5])**2))+row[8]
            delta = anchor-position
            length = np.sqrt(np.sum(delta*delta))
            tension = row[9]*(length-rest_length)/rest_length
            force = tension*delta/length
            couple = np.cross(arm, force)
            components['brace'][node, :3] += force
            components['brace'][node, 3:] += couple
            brace_rows.append(dict(node=node, position=position, arm=arm, anchor=anchor,
                                   length=length, rest_length=rest_length, tension=tension,
                                   force=force, moment=couple))
        total = np.c_[fext, mext] + sum(components.values())
        global_external = np.r_[np.sum(fext, axis=0),
                                np.sum(mext+np.cross(r-self.origin, fext), axis=0)]
        nodal_rows = np.r_[(total[:, :3]/self.F).ravel(), (total[:, 3:]/self.FL).ravel()]
        global_rows = global_external / np.array([self.F]*3+[self.FL]*3)
        constraint_rows = np.concatenate(constraint_geometry)
        kinematic_rows, kinematic_groups, decoded = self.kinematics(z, zdot)
        component_globals = {key:np.r_[v[:, :3].sum(axis=0),
            np.sum(v[:, 3:]+np.cross(r-self.origin, v[:, :3]), axis=0)] for key,v in components.items()}
        return dict(row_indices=self.row_indices, selected_residual=np.r_[nodal_rows, constraint_rows, global_rows, kinematic_rows],
                    nodal_residual=nodal_rows, constraint_residual=constraint_rows,
                    global_residual=global_rows, kinematic_residual=kinematic_rows,
                    nodal_force=total[:, :3], nodal_moment=total[:, 3:], global_external=global_external,
                    components=components, component_globals=component_globals,
                    element_force=ef, element_moment=em, element_N=n, element_M=m,
                    element_dr=chord, element_oa=oa, element_ob=ob,
                    reactions=np.asarray(reactions), braces=brace_rows,
                    kinematic_groups=kinematic_groups, decoded=decoded)
