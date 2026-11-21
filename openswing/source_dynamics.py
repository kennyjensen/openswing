"""Vacuum inertia and damping for the source structural discretization.

Steady Eqs.50/55/56 average completed nodal loads. Unsteady Eqs.37--40
provide the local inertial wrench; steady Eq.80 adds the finite-segment
rotary correction. This is an endpoint finite-difference operator, not the
default Gauss/virtual-power mass operator. Material damping uses unsteady
Eqs.57/58/60 and the full Eq.62 Euler curvature derivative. Unloaded ds is an explicit policy
interpretation, as in the corresponding source static equations.
The original fixed-frame policy is retained. The moving-frame subclass adds
absolute acceleration and angular-momentum transport at those same endpoints.
"""
import numpy as np

from .aero import AnalysisError
from .inertia import inertial_wrench
from .source_discrete import SourceSectionNetwork, angles_from_frame, angle_matrix, _increments


DYNAMIC_POLICY = 'drela-fixed-vacuum-v1'
MOVING_POLICY = 'drela-moving-vacuum-v1'


def check_frame_constraints(constraints, label='Source moving vacuum dynamics'):
    """Only the six published force/moment-to-frame-acceleration pairs."""
    from .operating import OperatingConstraint, time_load_constraints
    if not constraints:
        return
    constraints = [OperatingConstraint(**c) if isinstance(c, dict) else c for c in constraints]
    if any(not isinstance(c, OperatingConstraint) for c in constraints):
        raise AnalysisError(f'{label} requires canonical frame constraints.')
    targets = {c.quantity: c.target for c in constraints}
    expected = time_load_constraints('mixed', targets)
    if len(constraints) != len(expected) or any(c not in expected for c in constraints):
        raise AnalysisError(f'{label} supports only canonical frame force/moment constraints.')


def angle_matrix_rate(angles, rates, fuselage=False):
    """Exact derivative of the selected surface/fuselage curvature matrix."""
    theta, psi = angles[..., 1], angles[..., 2]
    td, pd = rates[..., 1], rates[..., 2]
    ct, st, cp, sp = np.cos(theta), np.sin(theta), np.cos(psi), np.sin(psi)
    out = np.zeros(angles.shape[:-1]+(3, 3))
    out[..., 0, 0] = -sp*ct*pd-cp*st*td
    out[..., 0, 2] = -ct*td
    out[..., 1, 0] = -cp*pd
    out[..., 2, 0] = -sp*st*pd+cp*ct*td
    out[..., 2, 2] = -st*td
    if np.any(fuselage):
        from .source_fuselage import angle_matrix_rate as body_rate
        mask = np.broadcast_to(fuselage, angles.shape[:-1])
        out[mask] = body_rate(angles[mask], rates[mask])
    return out


def source_strain_rates(pa, pb, ra, rb, va, vb, wa, wb, lengths, fuselage=False):
    """Local Eq.60 strain rates and full Eq.62 curvature rates.

    Eq.60 is the published endpoint-average approximation, not the exact
    derivative of the nonorthogonal averaged transform. For curvature retain
    the derivative of BOTH endpoint K matrices, including their distinct
    Euler rates; no midpoint rotation logarithm or averaged-rate shortcut.
    Lengths are the fixed unloaded lengths used by the source static policy.
    """
    qa, qb = angles_from_frame(ra, fuselage), angles_from_frame(rb, fuselage)
    ka, kb = angle_matrix(qa, fuselage), angle_matrix(qb, fuselage)
    ta, tb = ra.transpose(0, 2, 1), rb.transpose(0, 2, 1)
    qda = np.linalg.solve(ka, np.einsum('nij,nj->ni', ta, wa)[..., None])[..., 0]
    qdb = np.linalg.solve(kb, np.einsum('nij,nj->ni', tb, wb)[..., None])[..., 0]
    velocity = vb-va-np.cross((wa+wb)/2, pb-pa)
    translation = np.einsum('nij,nj->ni', (ta+tb)/2, velocity)
    curvature = (np.einsum('nij,nj->ni', (ka+kb)/2, qdb-qda)
        +np.einsum('nij,nj->ni', (angle_matrix_rate(qa, qda, fuselage)+angle_matrix_rate(qb, qdb, fuselage))/2,
                  _increments(qa, qb)))
    return np.c_[translation, curvature]/np.asarray(lengths)[:, None]


class SourceDynamicNetwork(SourceSectionNetwork):
    structural_operator = DYNAMIC_POLICY
    source_dynamic = True

    def __init__(self, *args, **kwargs):
        if kwargs.get('allow_signed_point_weights') or kwargs.get('allow_signed_distributed_weights'):
            raise AnalysisError('Source dynamics requires physical nonnegative masses; signed static loading is unavailable.')
        super().__init__(*args, **kwargs)
        self.source_rotary_samples = []
        times = []
        for mesh in self.meshes:
            beam = mesh.beam
            # Check entire input tables, not just the sampled midpoint.
            for name in ('tdeps', 'tdgam'):
                d = beam.distributions.get(name)
                if d is not None and (np.any(d.values < 0) or not np.all(np.isfinite(d.values))):
                    raise AnalysisError('Material damping times must be finite and nonnegative.')
            averaged = {}
            for name in ('tdeps', 'tdgam'):
                ends = [beam.value(name, t, side=side) for t, side in ((mesh.t0, 'right'), (mesh.t1, 'left'))]
                if any(np.any(v < 0) or not np.all(np.isfinite(v)) for v in ends):
                    raise AnalysisError('Source endpoint damping times must be finite and nonnegative.')
                averaged[name] = (ends[0]+ends[1])/2
            times.append(np.stack([averaged[k] for k in ('tdgam', 'tdeps', 'tdgam', 'tdeps', 'tdgam', 'tdeps')], axis=1))
            for prefix in ('', 'D'):
                for name in (prefix+'mgcc', prefix+'mgnn'):
                    d = beam.distributions.get(name)
                    if d is not None and (np.any(d.values < 0) or not np.all(np.isfinite(d.values))):
                        raise AnalysisError('Source section inertias must be finite and nonnegative.')
                for t, side in ((mesh.t0, 'right'), (mesh.t1, 'left')):
                    scale = mesh.length/(2*self.model.constants[0])
                    icc = beam.value(prefix+'mgcc', t, side=side)*scale
                    inn = beam.value(prefix+'mgnn', t, side=side)*scale
                    if np.any(icc < 0) or np.any(inn < 0) or not np.all(np.isfinite([icc, inn])):
                        raise AnalysisError('Source endpoint section inertias must be finite and nonnegative.')
                    self.source_rotary_samples.append(np.stack([icc, icc+inn, inn], axis=-1))
        self.damping_times = np.concatenate(times)
        self.source_material_compliance = np.array([s.compliance() for s in self.source_sections])

    def material_strain_rate(self, local_motion):
        local = local_motion
        return source_strain_rates(local.pa, local.pb, local.ra, local.rb, local.va, local.vb,
                                   local.rates[self.a], local.rates[self.b], self.ds, self.source_fuselage)

    def damping_report(self):
        return super().damping_report(compliance=self.source_material_compliance)

    def constitutive_motion(self, strain, curvature, data, elastic_motion):
        if elastic_motion is None or not np.any(self.damping_times):
            return strain, curvature
        # Eq.57 acts in local csn axes. The parent compatibility maps this
        # damped strain through Ta.T. Eq.61's bare body-axis diagonal would
        # give orientation-dependent material properties for unequal times.
        rates = data['strain_rate']
        strain = strain-self.damping_times[:, :3]*rates[:, :3]
        curvature = curvature-self.damping_times[:, 3:]*rates[:, 3:]
        data['source_material_rates'] = rates
        data['mechanical_strain'] = np.c_[strain, curvature]
        return strain, curvature

    @staticmethod
    def _check_motion(motion):
        if any(np.any(getattr(motion, key)) for key in ('rates', 'acceleration', 'angular_acceleration')):
            raise AnalysisError('Source vacuum dynamics requires a stationary fixed frame.')

    @staticmethod
    def _check_local_motion(kwargs):
        rate = kwargs.get('circulation_rate')
        if rate is not None and np.size(rate):
            raise AnalysisError('Source vacuum dynamics has no circulation states.')

    def endpoint_inertial_wrench(self, local, sl, end, nodes, mass, offset, inertia, motion):
        """Original fixed-frame arithmetic, retained by its existing policy."""
        omega, alpha = local.rates[nodes], local.rate_derivative[nodes]
        acceleration = (local.aa if end == 0 else local.ab)[sl]
        acceleration = acceleration+np.cross(alpha, offset)+np.cross(omega, np.cross(omega, offset))
        f = -mass[:, None]*acceleration
        m = (np.cross(offset, f)-np.einsum('nij,nj->ni', inertia, alpha)
             -np.cross(omega, np.einsum('nij,nj->ni', inertia, omega)))
        return f, m

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, *,
                 local_motion=None, circulation_rate=None, gravity=None, _loads_only=False):
        self._check_local_motion(dict(circulation_rate=circulation_rate))
        # Retain exactly the accepted static gravity and point-load arithmetic.
        force, moment, aero, _, couples, ends = super().external(
            r, Q, meshes, gamma, condition, motion, operating_key, gravity=gravity)
        if local_motion is None:
            from .local_motion import NetworkMotion
            zero = np.zeros_like(r)
            local_motion = NetworkMotion(self, r, Q, zero, zero, zero, zero)
        local = local_motion
        midpoint = (local.pa+local.pb)/2
        interval_force, interval_moment = np.zeros((self.ne, 3)), np.zeros((self.ne, 3))
        records = []
        for sample, section_inertia in zip(self.source_mass_samples, self.source_rotary_samples):
            beam, sl, end, mass, arm = sample
            nodes = (self.a if end == 0 else self.b)[sl]
            rotation = (local.ra if end == 0 else local.rb)[sl]
            offset = np.einsum('nij,nj->ni', rotation, arm)
            diagonal = section_inertia+mass[:, None]*self.ds[sl, None]**2/12*np.array([1., 0., 1.])
            inertia = (rotation*diagonal[:, None, :])@rotation.transpose(0, 2, 1)
            f, m = self.endpoint_inertial_wrench(local, sl, end, nodes, mass, offset, inertia, motion)
            interval_force[sl] += f
            interval_moment[sl] += m
            records.append(dict(beam=beam, point=None, mass=mass,
                position=midpoint[sl]+offset, inertia=inertia, spin=np.zeros_like(offset)))
        ends = ends+interval_force[:, None, :]/2
        couples = couples+interval_moment[:, None, :]/2
        for ids in (self.a, self.b):
            np.add.at(force, ids, interval_force/2)
            np.add.at(moment, ids, interval_moment/2)
        positions = self.point_positions(r, Q)
        for record in self.inertia_model.point_elements(positions, [Q[self.node(*row[:2])] for row in self.weights]):
            index = record['point']
            i = self.node(*self.weights[index][:2])
            f, m = inertial_wrench(*(record[key] for key in ('mass', 'position', 'inertia', 'spin')),
                motion, np.zeros(3), self.model.reference[2], local_motion=local.point('weight', index))
            force[i] += f[0]
            moment[i] += m[0]+np.cross(positions[index]-r[i], f[0])
            records.append(record)
        self.mass_cached = (force, moment, records, couples, ends)
        return force, moment, aero, records, couples, ends


class SourceMovingNetwork(SourceDynamicNetwork):
    """Source endpoint real-mass operator with full moving-frame transport.

    Unsteady Eqs.23/27 give the absolute CG acceleration. Differentiating
    angular momentum in Earth axes requires alpha_abs=alpha_o+wdot+Omega×w.
    This explicitly resolves the omission of Omega×w in printed Eqs.40/47;
    it is not a claim about an unavailable historical executable. Global
    balance uses the same transferred wrenches as the local equations
    (Eq.266), without a second aggregate mass or endpoint r×f quadrature.
    """
    structural_operator = MOVING_POLICY
    source_moving = True

    def _check_analysis_scope(self):
        if (self.condition is not None or self.ng or self.engines
                or self.quiescent_density is not None):
            raise AnalysisError('Source moving vacuum dynamics requires no airflow, engines or quiescent fluid.')
        check_frame_constraints(self.operating.constraints)

    @staticmethod
    def _check_motion(motion):
        # Motion validates all three finite xyz vectors at construction.
        from .inertia import Motion
        if not isinstance(motion, Motion):
            raise AnalysisError('Source moving vacuum dynamics requires a Motion object.')

    def endpoint_inertial_wrench(self, local, sl, end, nodes, mass, offset, inertia, motion):
        if not any(np.any(getattr(motion, key)) for key in ('rates', 'acceleration', 'angular_acceleration')):
            # Exact compatibility with the accepted stationary operator.
            return super().endpoint_inertial_wrench(local, sl, end, nodes, mass, offset, inertia, motion)
        from .local_motion import LocalMotion
        origin = (local.pa if end == 0 else local.pb)[sl]
        field = LocalMotion(origin, (local.va if end == 0 else local.vb)[sl],
            local.rates[nodes], (local.aa if end == 0 else local.ab)[sl], local.rate_derivative[nodes])
        f, m = inertial_wrench(mass, origin+offset, inertia, np.zeros_like(offset),
            motion, np.zeros(3), self.model.reference[2], local_motion=field)
        return f, np.cross(offset, f)+m
