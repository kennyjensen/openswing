"""Opt-in static beam equations from ASWING steady theory, Eqs. 48/54–56.

The original policy retains zero section/CG offsets and rigid shear. The
separate section policy adds finite shear and section/centroid offsets with
coupled bending/torsion. Both support static distributed gravity, concentrated
loads and rotating point-weight pylons. Neither changes the browser default.
Ground types 0/1/2 and Joint types 0/1/2/3 use the common conservative joint
equations. Surface and fuselage beams use their respective Euler charts.
Airflow and moving-frame dynamics use the corresponding subclasses; stepped
axes remain unsupported.

Eqs. 49–51 average endpoint matrices and body resultants. Eq. 54 inverts the
averaged stiffness. Axial strain uses inverse averaged EA; the unsubscripted
length in Eqs. 54–56 is taken as unloaded arc length. Those last two choices
are explicit interpretations, not proven historical executable conventions.
"""
from dataclasses import fields
import numpy as np

from .aero import AnalysisError
from .network import StaticNetwork, equilibrate, network_result
from .structure import Section, stiffness_inverse
from .equilibrium_state import capture, warm_start_recipe


STRUCTURAL_POLICY = 'drela-steady-zero-offset-v1'
SECTION_POLICY = 'drela-steady-section-v1'
COUPLED_POLICY = 'drela-steady-coupled-v1'
SOURCE_INTERVAL_MEASURE = 'drela-eq48-average-strain-norm-v1'


def source_output_metadata(network=None):
    """Fresh reporting metadata shared by direct snapshots and solved output."""
    general = network is not None and isinstance(network, SourceSectionNetwork)
    coupled = network is not None and network.structural_operator == COUPLED_POLICY
    flowing = getattr(network, 'source_airflow', False)
    result = dict(structural_operator=network.structural_operator if network is not None else STRUCTURAL_POLICY,
        output_scope=dict(
            authoritative='Nodes, reactions, source constitutive element estimates, one-sided endpoint resultants/section recovery and sensor-anchor sections.',
            material_charts='Surface steady Eqs.4/9 and fuselage Eqs.11/12. Vertical fuselage spans and x-directed surface spans are chart poles; spatial Euler branch cuts remain unsupported.',
            element_coordinates='t locates the interval on plots; interval strains use the source averaged law. endpoint_traces contain actual sided point samples.',
            deformed_interval_measure=(SOURCE_INTERVAL_MEASURE+': constant-average-strain arc measure '
                '||solve((Ra+Rb)/2, rb-ra)|| from Eq.48 physical endpoint frames. Material arc/theta stay fixed. '
                'The quadrature for nonuniform endpoint strains is not established historical executable behavior.')),
        limitations=[
            'Opt-in static source equations with zero section/CG offsets, rigid shear and rigid joints; no airflow, motion, engines or dynamics.',
            'The averaged transform is generally not a rotation. Element local components use transform_average; the physical midpoint frame is for geometric display only.',
            'Eq. 54 uses inverse averaged stiffness. EA is averaged before inversion; ds is set to unloaded spline arc. Historical executable conventions for those latter choices remain unproven.',
            'Element constitutive estimates use averaged shell properties. Endpoint traces and sensor strains use their one-sided section properties; exact ASWING output sampling remains unverified.',
            'Mass properties are static bookkeeping for the endpoint load rule, not a validated dynamic inertia model.'
        ])
    if general:
        result['output_scope']['strain_components'] = ('source_discrete_elements.axial_strain is reference-axis epsilon_s; '
            'elements.axial_strain_tension is Fs/EA. Closed-shell shear uses the translated elastic-axis torque.')
        result['limitations'][0] = ('Static source equations with coupled sections, finite axial/shear stiffness, '
            'section and distributed-CG offsets, and rigid joints; no stepped axes, airflow, motion, engines or dynamics.')
        result['limitations'][2] = ('Eq. 54 uses inverse averaged bending/torsion stiffness. EA, GK and offsets are averaged '
            'before applying Eqs. 18–19; ds is unloaded arc. These property/length interpretations are not proven historical executable conventions.')
        result['limitations'][-1] = ('Mass and first moment follow the static endpoint-averaged gravity rule. '
            'Dynamic inertia and spin are unavailable for this operator.')
    if coupled:
        result['limitations'][0] = ('Mounted steady source structural equations with surface/body sections and rigid joints; '
            'prescribed zero frame rates/accelerations only. Ordinary steady targets solve flow, pose, flap or engine settings in the full coupled residual. '
            'Steady engines use their rotated attachment pylons. Custom sensor equations and weighted control allocation share the full coupled residual. No stepped axes or dynamics.')
        result['limitations'].append('Aerodynamic loads retain physical Glauert-midpoint section frames and the existing interval circulation quadrature and the declared source interval arc measure. '
            'Their integrated wrench is transferred symmetrically about the structural midpoint. Historical ASWING load-sampling equivalence is unverified.')
        result['output_scope']['aerodynamic_load_transfer'] = 'Equal endpoint forces and equal couples preserve each aerodynamic strip total force and global moment; mixed N/M remain physical endpoint means.'
    if getattr(network, 'source_dynamic', False):
        result['limitations'][0] = ('Source structural equations with fixed-frame vacuum inertia. '
            'Material strain-rate damping uses local source kinematics. No airflow, moving frames, stepped axes or engines.')
        result['limitations'][-1] = ('Distributed loads average completed endpoint products and transfer each interval wrench symmetrically. '
            'Section rotary inertia includes steady Eq.80 exactly once, using unloaded interval length. '
            'For varying properties this finite-difference mass operator need not be symmetric; it is not a finite-element kinetic-energy mass matrix. '
            'Historical executable discretization and modal reference agreement remain unverified.')
        if getattr(network, 'source_moving', False):
            result['limitations'][0] = ('Source structural equations with moving-frame real inertia and local material damping. '
                'No airflow, stepped axes or engines.')
            result['limitations'].append('Angular inertia includes Omega cross omega from inertial differentiation of angular momentum; '
                'printed unsteady Eqs.40/47 omit this term. Global loads use the same symmetric interval transfer as local equilibrium (Eq.266). '
                'This explicitly declared interpretation is not established historical ASWING executable parity.')
        if getattr(network, 'source_quiescent', False):
            result['limitations'][0] = ('Source structural equations with fixed-frame real and still-air apparent inertia. '
                'Material strain-rate damping uses local source kinematics. No mean flow, moving frames, stepped axes or engines.')
            result['limitations'][-1] += ' The finite-segment Eq.80 correction applies only to real mass, never to fluid apparent inertia.'
        if np.any(network.damping_times):
            result['output_scope']['authoritative'] = ('Nodes, reactions, interval mechanical strains from the damped source law, '
                'and one-sided endpoint loads. Endpoint mechanical strains are unavailable; sensors report a sided interval strain estimate.')
            result['limitations'][3] = ('Damped interval mechanical strains subtract material-rate contributions from the averaged load law. '
                'Damped endpoint strains are unavailable; sensor strains are sided interval estimates. '
                'Endpoint loads and total-torque shell shear stress retain one-sided properties.')
            result['limitations'].append('Damping follows unsteady Eqs.57/58/60 and full Eq.62. The anisotropic translation law is transformed in local csn axes; '
                'the bare body-axis diagonal printed in Eq.61 is inconsistent with Eq.57 under rotation. '
                'Endpoint damping times are averaged; exact historical sampling is unverified.')
    if flowing:
        result['limitations'][0] = ('Source structural equations with moving-frame real inertia, material damping and unsteady airflow. '
            'Engine types 0, 1 and 2 use moving attachment velocities and rates; engine mass and rotor angular momentum are separate Weight records. '
            'Stepped axes and inverse actuator/history targets remain unsupported.')
        result['output_scope']['aerodynamic_load_transfer'] = ('Glauert aerodynamic section wrenches are transferred symmetrically about the structural midpoint; '
            'real inertia retains source endpoint averaging. No second apparent-mass matrix is added.')
    if network is not None and network.struts:
        result['output_scope']['strut_load_transfer'] = (
            'Current-pylon axial force and its arm couple are applied once at the attachment; '
            'the body-fixed anchor reaction cancels the net aircraft wrench. No added mass or degrees of freedom. '
            'Declared engineering-strain law with bilateral compression or explicit tension-only wire mode; '
            'historical ASWING compression and large-strain conventions remain unverified.')
    if (coupled or flowing) and network.engines:
        result['output_scope']['engine_load_transfer'] = ('Concentrated engine forces and intrinsic couples act at the rotated engine position; '
            'the engine-to-node arm is added once at its attachment and is excluded from distributed strip and real-mass loads.')
    if network is not None and any(c['type'] != 0 for c in network.constraints):
        # An accepted-input extension, not a different equation policy: keep
        # all previous rigid-only reports and saved-state identities intact.
        result['limitations'][0] = result['limitations'][0].replace(
            'rigid joints', 'rigid, pinned, roller and sprung joints')
        result['joint_constraints'] = dict(
            ground_types=[0, 1, 2], joint_types=[0, 1, 2, 3],
            position='The joint pylon follows beam 1; the beam-2 attachment is free to rotate for type 1 and free to translate for type 2.',
            moment='Type 3 uses the beam-1 inward endpoint or left interior structural moment, including distributed endpoint couples; it is not generally the free-end reaction couple.',
            interpolation='Jangle retains the existing natural cubic interpolation, sided slope breaks and extrapolation. Historical spline-endpoint and interior-trace conventions remain unverified.',
            rotations='Hinge winding uses version-2 equilibrium charts. Each source beam must still remain inside its nonsingular, uncut Euler chart.',
            stability='A converged equilibrium does not establish stability or passivity of an offset or interior sprung joint.')
    return result


def angle_matrix(angles, fuselage=False):
    """Surface Eq.9 or fuselage Eq.12: Euler increments to local curvature."""
    q = np.asarray(angles)
    theta, psi = q[..., 1], q[..., 2]
    ct, st, cs, ss = np.cos(theta), np.sin(theta), np.cos(psi), np.sin(psi)
    out = np.zeros(q.shape[:-1]+(3, 3), dtype=np.result_type(q, float))
    out[..., 0, 0], out[..., 0, 2] = cs*ct, -st
    out[..., 1, 0], out[..., 1, 1] = -ss, 1.
    out[..., 2, 0], out[..., 2, 2] = cs*st, ct
    if np.any(fuselage):
        from .source_fuselage import angle_matrix as body_matrix
        mask = np.broadcast_to(fuselage, q.shape[:-1])
        out[mask] = body_matrix(q[mask])
    return out


def angles_from_frame(frame, fuselage=False):
    """Recover the principal surface/fuselage chart, local-to-body input."""
    r = np.asarray(frame)
    if np.any(fuselage):
        from .source_fuselage import angles_from_frame as body_angles
        mask = np.broadcast_to(fuselage, r.shape[:-2])
        if np.all(mask):
            return body_angles(r)
        result = np.empty(r.shape[:-2]+(3,))
        result[mask] = body_angles(r[mask])
        result[~mask] = angles_from_frame(r[~mask])
        return result
    s = r[..., :, 1]
    phi = np.arctan2(s[..., 2], s[..., 1])
    psi = -np.arcsin(np.clip(s[..., 0], -1., 1.))
    if np.any(abs(np.cos(psi)) < 1e-8):
        raise AnalysisError('Source-discrete Euler chart is singular for this beam orientation.')
    c0 = np.stack([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)], axis=-1)
    n0 = np.stack([np.zeros_like(phi), -np.sin(phi), np.cos(phi)], axis=-1)
    theta = np.arctan2(-np.sum(r[..., :, 0]*n0, axis=-1), np.sum(r[..., :, 0]*c0, axis=-1))
    return np.stack([phi, theta, psi], axis=-1)


def _increments(a, b):
    delta = b-a
    if np.any(abs(delta) >= np.pi):
        raise AnalysisError('Source-discrete Euler chart crosses a branch cut; this orientation needs a lifted-angle formulation.')
    return delta


class SourceDiscreteNetwork(StaticNetwork):
    """Explicit static policy; all default StaticNetwork behavior is retained."""
    analytic_mechanics = False
    structural_operator = STRUCTURAL_POLICY
    deformed_interval_measure = SOURCE_INTERVAL_MEASURE

    @staticmethod
    def _check_section_scope(beam):
        # Whole tables are checked so an interior property cannot be ignored
        # merely because the current mesh does not sample it.
        for name in ('Cea', 'Nea', 'Cta', 'Nta', 'Ccg', 'Ncg', 'DCcg', 'DNcg'):
            d = beam.distributions.get(name)
            if d is not None and np.any(d.values != 0):
                raise AnalysisError(f'Source-discrete static analysis requires zero {name}.')
        for name in ('GKc', 'GKn'):
            d = beam.distributions.get(name)
            if d is not None and np.any((d.values != 0) & ~np.isposinf(d.values)):
                raise AnalysisError('Source-discrete static analysis currently requires rigid shear stiffness.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._check_analysis_scope()
        self._check_motion(self.motion)
        # Joint kinematics and conservative nodal wrenches are independent of
        # the beam constitutive discretization. Its symmetric distributed
        # transfer also gives the common type-3 law the actual endpoint M.
        # StaticNetwork validates the allowed Ground/Joint types and Jangle;
        # the solve's rank check remains responsible for free mechanisms.
        if np.any(self.offa) or np.any(self.offb):
            raise AnalysisError('Source-discrete static analysis does not yet support stepped beam axes.')
        self.source_sections, self.source_endpoint_sections = [], []
        self.source_fuselage = np.concatenate([
            np.full(len(mesh.length), not mesh.beam.lifting, dtype=bool) for mesh in self.meshes])
        self.source_fuselage.setflags(write=False)
        compliance, axial, weights = [], [], []
        for mesh in self.meshes:
            beam = mesh.beam
            self._check_section_scope(beam)

            def average(name):
                return (beam.value(name, mesh.t0, side='right')+beam.value(name, mesh.t1, side='left'))/2

            ends = [{f.name: beam.value(f.name, t, side=side) for f in fields(Section)}
                    for t, side in ((mesh.t0, 'right'), (mesh.t1, 'left'))]
            for i in range(len(mesh.length)):
                # Validate both endpoints as well as their average, including
                # the full symmetric bend/twist matrix and infinite directions.
                endpoint_sections = [Section(**{key: float(v[i]) for key, v in values.items()}) for values in ends]
                for endpoint in endpoint_sections:
                    endpoint.compliance()
                self.source_endpoint_sections.append(endpoint_sections)
                sec = Section(**{key: float((ends[0][key][i]+ends[1][key][i])/2) for key in ends[0]})
                sec.compliance()
                e = [[sec.EIcc, sec.EIcs, sec.EIcn], [sec.EIcs, sec.GJ, sec.EIsn], [sec.EIcn, sec.EIsn, sec.EInn]]
                self.source_sections.append(sec)
                compliance.append(stiffness_inverse(e))
                axial.append(1/sec.EA)
            weights.extend((average('mg')+average('Dmg'))*mesh.length)
            entries = []
            for prefix, entry in zip(('', 'D'), self.inertia_model.data[beam.index]):
                mass = average(prefix+'mg')*mesh.length/self.model.constants[0]
                if np.any(mass < 0) and not kwargs.get('allow_signed_distributed_weights', False):
                    raise AnalysisError('Source-discrete endpoint weights must be nonnegative unless signed static loading is enabled.')
                entries.append((mass, *entry[1:]))
            self.inertia_model.data[beam.index] = entries
        self.source_compliance = np.array(compliance)
        self.source_axial_compliance = np.array(axial)
        self.source_weights = np.array(weights)
        qa, qb = (angles_from_frame(r, self.source_fuselage) for r in (self.R0a, self.R0b))
        self.source_jig_curvature = np.einsum('nij,nj->ni',
            (angle_matrix(qa, self.source_fuselage)+angle_matrix(qb, self.source_fuselage))/2, _increments(qa, qb))

    def deformed_meshes(self, r, Q, geometry):
        """Source interval measure from the Eq.48 average-strain vector.

        With R_a=(R_i+R_i+1)/2, Eq.48 gives delta_r=R_a q_a ds0,
        q_a=[gamma_c,1+epsilon_s,gamma_n]_a. Hence the constant-average-
        strain arc measure is ||solve(R_a,delta_r)||. R_a is not a rotation:
        neither its transpose nor a normalized midpoint frame is its inverse.
        This metric preserves ds0 under zero-strain bending and includes
        uniform axial/shear stretch. It does not claim a unique quadrature
        for nonuniform endpoint strains in the historical executable.
        """
        pa, pb, Ra, Rb, *_ = geometry
        if not all(np.all(np.isfinite(value)) for value in (pa, pb, Ra, Rb)):
            raise AnalysisError('Source interval arc measure requires finite endpoint positions and frames.')
        average = .5*Ra+.5*Rb
        with np.errstate(over='ignore', invalid='ignore'):
            delta = pb-pa
        if not np.all(np.isfinite(delta)):
            raise AnalysisError('Source interval arc measure requires finite endpoint displacement.')
        try:
            singular = np.linalg.svd(average, compute_uv=False)
        except np.linalg.LinAlgError as exc:
            raise AnalysisError('Source interval arc measure could not resolve the averaged endpoint transform.') from exc
        # Same relative numerical-rank floor used by the network, saved-state
        # and circulation checks. This is not a physical bending-angle limit.
        cutoff = 1e-10
        invalid = (~np.all(np.isfinite(singular), axis=1)
                   | (singular[:, 0] <= 0)
                   | (singular[:, -1] <= cutoff*singular[:, 0]))
        if np.any(invalid):
            index = int(np.flatnonzero(invalid)[0])
            raise AnalysisError(
                f'Source interval {index} has a singular or ill-conditioned averaged endpoint transform; refine the spatial discretization.',
                details=dict(kind='source_interval_arc_measure', interval=index,
                             singular_values=singular[index].tolist(), relative_cutoff=cutoff))
        try:
            local_delta = np.linalg.solve(average, delta[..., None])[..., 0]
        except np.linalg.LinAlgError as exc:
            raise AnalysisError('Source interval arc measure could not invert the averaged endpoint transform.') from exc
        with np.errstate(over='ignore', invalid='ignore'):
            length = np.linalg.norm(local_delta, axis=1)
        if np.any(~np.isfinite(length)) or np.any(length <= 0):
            raise AnalysisError('Source interval arc measure must be finite and positive.')
        meshes = super().deformed_meshes(r, Q, geometry)
        for mesh in meshes:
            mesh.length = length[self.beam_elements[mesh.beam.index]]
        return meshes

    def deformed_interval_length_columns(self, geometry, da, db, dRa, dRb):
        """Differentiate the same Eq.48 interval measure used by the residual.

        Rbar u = rb-ra gives du = solve(Rbar, d(rb-ra)-dRbar u).
        This matters for external-receiver vortex cores, whose lower bound is
        the current interval length. A straight endpoint-chord derivative does
        not include the source averaged-frame contribution during bending.
        Geometry was validated by deformed_meshes before this tangent is used.
        """
        pa, pb, Ra, Rb, *_ = geometry
        average = .5*Ra+.5*Rb
        local = np.linalg.solve(average, (pb-pa)[..., None])[..., 0]
        rhs = db-da-np.einsum('nijk,nj->nik', .5*dRa+.5*dRb, local)
        derivative = np.linalg.solve(average, rhs)
        return np.einsum('ni,nik->nk', local, derivative)/np.linalg.norm(local, axis=1)[:, None]

    def _check_analysis_scope(self):
        if (self.condition is not None or self.ng or self.operating.count
                or self.engines or self.quiescent_density is not None):
            raise AnalysisError('Source-discrete static analysis requires no airflow, operating constraints, engines or quiescent fluid.')

    @staticmethod
    def _check_motion(motion):
        if any(np.any(getattr(motion, k)) for k in ('rates', 'acceleration', 'angular_acceleration')):
            raise AnalysisError('Source-discrete static analysis requires zero motion; dynamics are not implemented for this policy.')

    def constitutive_response(self, force, moment):
        """The original zero-offset law, preserving its operation order."""
        strain = np.zeros_like(force)
        strain[:, 1] = force[:, 1]*self.source_axial_compliance
        curvature = np.einsum('nij,nj->ni', self.source_compliance, moment)
        return strain, curvature

    def constitutive_motion(self, strain, curvature, data, elastic_motion):
        """Static policies retain their load-only constitutive response."""
        return strain, curvature

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, *, local_motion=None,
                 circulation_rate=None, gravity=None, _loads_only=False):
        self._check_motion(motion)
        if condition is not None or len(gamma) or circulation_rate is not None:
            raise AnalysisError('Source-discrete static analysis does not support aerodynamic or unsteady loads.')
        gravity = self.gravity if gravity is None else np.asarray(gravity)
        element = self.source_weights[:, None]*gravity[None, :]/self.model.constants[0]
        ends = np.repeat((element/2)[:, None, :], 2, axis=1)
        couples = np.zeros_like(ends)
        force, moment = np.zeros_like(r), np.zeros_like(r)
        np.add.at(force, self.a, ends[:, 0])
        np.add.at(force, self.b, ends[:, 1])
        point_positions = self.point_positions(r, Q)
        for row, position in zip(self.weights, point_positions):
            i = self.node(*row[:2])
            f = row[5]/self.model.constants[0]*gravity
            force[i] += f
            moment[i] += np.cross(position-r[i], f)
        for load in self.loads:
            i = self.node(load['beam'], load['t'])
            force[i] += load.get('force', [0., 0., 0.])
            moment[i] += load.get('moment', [0., 0., 0.])
        masses = self.inertia_model.elements(meshes, point_positions, [Q[self.node(*row[:2])] for row in self.weights])
        self.mass_cached = (force, moment, masses, couples, ends)
        return force, moment, None, masses, couples, ends

    def _check_local_motion(self, kwargs):
        if kwargs.get('elastic_motion') is not None or kwargs.get('circulation_rate') is not None:
            raise AnalysisError('Source-discrete static states cannot initialize dynamics.')

    def source_section_data(self, data, elastic_motion=None, *, frames=None):
        """One source constitutive law for residuals, sensors and user rows."""
        Ra, Rb = self.geometry(data['r'], data['Q'])[2:4] if frames is None else frames
        Ta = (Ra.transpose(0, 2, 1)+Rb.transpose(0, 2, 1))/2
        force = np.einsum('nij,nj->ni', Ta, data['N'])
        moment = np.einsum('nij,nj->ni', Ta, data['M'])
        strain, curvature = self.constitutive_response(force, moment)
        strain, curvature = self.constitutive_motion(strain, curvature, data, elastic_motion)
        return dict(transform_average=Ta, force_local=force, moment_local=moment,
                    axial_strain=strain[:, 1], curvature_change=curvature,
                    **({'translation_strain': strain} if isinstance(self, SourceSectionNetwork) else {}))

    def custom_operating_values(self, data, values, force, moment, *, elastic_motion=None):
        # The parent residual evaluates OPER before its source compatibility
        # replacement. Recover source sections here too: otherwise a custom
        # target silently uses midpoint strains instead of the reported anchor
        # trace (or declared damped interval estimate).
        data['source_discrete'] = self.source_section_data(data, elastic_motion)
        return super().custom_operating_values(data, values, force, moment,
                                               elastic_motion=elastic_motion)

    def residual(self, x, factor=1., detail=False, **kwargs):
        self._check_local_motion(kwargs)
        if not detail and getattr(self, 'compact_source_evaluation', False):
            data = {}
            residual = super().residual(x, factor, _constitutive_data=data, **kwargs)
        else:
            residual, data = super().residual(x, factor, detail=True, **kwargs)
        pa, pb, Ra, Rb, *_ = self.geometry(data['r'], data['Q'])
        qa, qb = angles_from_frame(Ra, self.source_fuselage), angles_from_frame(Rb, self.source_fuselage)
        source = self.source_section_data(data, kwargs.get('elastic_motion'), frames=(Ra, Rb))
        Ta = source['transform_average']
        Ka = (angle_matrix(qa, self.source_fuselage)+angle_matrix(qb, self.source_fuselage))/2
        # Symmetric distributed forces/couples have no end-difference correction.
        # Concentrated nodal loads remain jumps between adjacent elements.
        strain = source.get('translation_strain')
        if strain is None:
            strain = np.zeros_like(data['N']); strain[:, 1] = source['axial_strain']
        curvature = source['curvature_change']
        # Evaluate Eq.48 in displacement coordinates. Reconstructing the
        # absolute endpoints first can erase sub-ULP translations, leaving a
        # staircase residual which repeated Newton steps turn into false BDF
        # velocities/accelerations. Source networks have no stepped-axis
        # offsets, so this is algebraically the same endpoint difference.
        # Keep strain separate from the unit span vector for the same reason.
        displacement = x[:6*self.nn].reshape(self.nn, 6)[:, :3]
        reference_defect = (self.rj[self.b]-self.rj[self.a]
                            -Ta[:, 1, :]*self.ds[:, None])
        translation = (reference_defect
                       +self.L*(displacement[self.b]-displacement[self.a])
                       -np.einsum('nji,nj->ni', Ta, strain)*self.ds[:, None])
        rotation = np.einsum('nij,nj->ni', Ka, _increments(qa, qb))-self.source_jig_curvature-curvature*self.ds[:, None]
        residual[:6*self.ne] = np.c_[translation/self.L, rotation].ravel()
        if detail:
            data['source_discrete'] = dict(source, translation_defect=translation, rotation_defect=rotation)
            return residual, data
        return residual


class SourceSectionNetwork(SourceDiscreteNetwork):
    """Eqs. 18–20/48/54 with section offsets and static centroid gravity.

    Average primitive section properties, then form H, D and inverse(E).
    Symmetric transfer of the averaged body load density keeps the mixed N/M
    unknowns equal to the actual endpoint-resultant averages in Eq. 51.
    """
    structural_operator = SECTION_POLICY

    @staticmethod
    def _check_section_scope(beam):
        for name in ('Cea', 'Nea', 'Cta', 'Nta', 'Ccg', 'Ncg', 'DCcg', 'DNcg'):
            value = beam.distributions.get(name)
            if value is not None and not np.all(np.isfinite(value.values)):
                raise AnalysisError(f'Source section offsets must be finite: {name}.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_h = np.array([[[0, s.Nta, 0], [-s.Nea, 0, s.Cea], [0, -s.Cta, 0]]
                                  for s in self.source_sections])
        self.source_direct_compliance = np.array([[1/s.GKc, 1/s.EA, 1/s.GKn] for s in self.source_sections])
        self.source_mass_samples = []
        for mesh in self.meshes:
            beam, sl = mesh.beam, self.beam_elements[mesh.beam.index]
            for prefix in ('', 'D'):
                for end, (t, side) in enumerate(((mesh.t0, 'right'), (mesh.t1, 'left'))):
                    mass = beam.value(prefix+'mg', t, side=side)*mesh.length/(2*self.model.constants[0])
                    if np.any(mass < 0) and not kwargs.get('allow_signed_distributed_weights', False):
                        raise AnalysisError('Signed endpoint weights require signed static loading to be enabled.')
                    if np.any(mass < 0):
                        record = dict(beam=beam.index, field=prefix+'mg')
                        if record not in self.inertia_model.signed_distributed_weights:
                            self.inertia_model.signed_distributed_weights.append(record)
                    arm = np.c_[beam.value(prefix+'Ccg', t, side=side), np.zeros(len(t)),
                                beam.value(prefix+'Ncg', t, side=side)]
                    self.source_mass_samples.append((beam.index, sl, end, mass, arm))

    def constitutive_response(self, force, moment):
        translated = moment+np.einsum('nij,nj->ni', self.source_h, force)
        curvature = np.einsum('nij,nj->ni', self.source_compliance, translated)
        strain = self.source_direct_compliance*force+np.einsum('nji,nj->ni', self.source_h, curvature)
        return strain, curvature

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, **kwargs):
        force, moment, aero, _, couples, ends = super().external(r, Q, meshes, gamma, condition, motion, operating_key, **kwargs)
        gravity = self.gravity if kwargs.get('gravity') is None else np.asarray(kwargs['gravity'])
        pa, pb, ra, rb, *_ = self.geometry(r, Q)
        midpoint = (pa+pb)/2
        total_couple = np.zeros((self.ne, 3))
        masses = []
        for beam, sl, end, mass, arm in self.source_mass_samples:
            offset = np.einsum('nij,nj->ni', (ra if end == 0 else rb)[sl], arm)
            total_couple[sl] += np.cross(offset, mass[:, None]*gravity)
            # These records reproduce the symmetric static force transfer's
            # exact first moment; they do not define a dynamic inertia.
            masses.append(dict(beam=beam, point=None, mass=mass, position=midpoint[sl]+offset,
                               inertia=np.zeros((len(mass), 3, 3)), spin=np.zeros((len(mass), 3))))
        couples += total_couple[:, None, :]/2
        np.add.at(moment, self.a, total_couple/2)
        np.add.at(moment, self.b, total_couple/2)
        positions = self.point_positions(r, Q)
        masses.extend(self.inertia_model.point_elements(positions, [Q[self.node(*row[:2])] for row in self.weights]))
        self.mass_cached = (force, moment, masses, couples, ends)
        return force, moment, aero, masses, couples, ends


def solve_source_discrete(model, panels=24, *, gravity=None, loads=(), tolerance=1e-8,
                          continuation_steps=4, initial_state=None, progress=None,
                          allow_signed_point_weights=False, allow_signed_distributed_weights=False,
                          structural_operator=STRUCTURAL_POLICY, strut_mode='bilateral'):
    """Solve the bounded source policy; explicit opt-in, no default change.

    Warm starts require both this structural policy and the same interpolation
    policy. No dynamic launch is exported. Original ASW source stays unchanged.
    """
    classes = {STRUCTURAL_POLICY: SourceDiscreteNetwork, SECTION_POLICY: SourceSectionNetwork}
    if structural_operator not in classes:
        raise AnalysisError('Unknown source static structural operator.')
    net = classes[structural_operator](model, panels, None, gravity, loads, strut_mode=strut_mode,
        allow_signed_point_weights=allow_signed_point_weights,
        allow_signed_distributed_weights=allow_signed_distributed_weights,
        mesh_recipe=warm_start_recipe(model, panels, initial_state))
    return _solve_source_network(net, tolerance, continuation_steps, initial_state, progress)


def source_network_result(net, x, **options):
    """Report the source section state using the actual applied operating state."""
    result = network_result(net, x, **options)
    _, data = net.residual(x, detail=True, **options)
    source = data['source_discrete']
    result['source_discrete_elements'] = [dict(beam=mesh.beam.index, t0=float(mesh.t0[i]), t1=float(mesh.t1[i]),
        force_local=source['force_local'][j].tolist(), moment_local=source['moment_local'][j].tolist(),
        axial_strain=float(source['axial_strain'][j]), curvature_change=source['curvature_change'][j].tolist(),
        transform_average=source['transform_average'][j].tolist())
        for mesh in net.meshes for i, j in enumerate(range(net.beam_elements[mesh.beam.index].start, net.beam_elements[mesh.beam.index].stop))]
    if isinstance(net, SourceSectionNetwork):
        for i, element in enumerate(result['source_discrete_elements']):
            element['translation_strain'] = source['translation_strain'][i].tolist()
    return result


def _solve_source_network(net, tolerance, continuation_steps, initial_state, progress, *, derivatives=None):
    """Shared solve/report path; each network owns its exact numerical identity."""
    x, steps = equilibrate(net, tolerance, continuation_steps, initial_state=initial_state, progress=progress)
    result = source_network_result(net, x)
    result.update(continuation_steps=steps,
        equilibrium_state=capture(net, x, residual=result['residual'], include_launch=getattr(net, 'source_airflow', False)),
        equilibrium_initialization=getattr(net, 'equilibrium_diagnostics', dict(initialization='undeformed load continuation')))
    if not getattr(net, 'source_airflow', False):
        result['equilibrium_state']['limitations'].append('Static source-discrete policy only; cannot initialize physical dynamics or a different structural operator.')
    if derivatives is not None:
        from .derivatives import linearize_equilibrium
        result['derivatives'] = linearize_equilibrium(net, x, **derivatives)
    return result
