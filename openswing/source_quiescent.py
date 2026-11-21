"""Stationary fixed-frame source modes with surface/body apparent inertia.

This is the acceleration-linear part of unsteady Eqs.41--45 at zero mean
flow and zero base rates. Quadratic velocity/rate terms have zero tangent
there; no nonlinear fluid/time solver or circulatory model is implied.
"""
import numpy as np

from .aero import AnalysisError
from .source_dynamics import SourceDynamicNetwork
from .apparent_box import endpoint_acceleration_wrench as source_apparent_wrench
from .apparent_box import rigid_acceleration_response
from .geometry import surface_frame


FLUID_POLICY = 'drela-fixed-still-air-v1'


class SourceQuiescentNetwork(SourceDynamicNetwork):
    structural_operator = FLUID_POLICY
    source_quiescent = True

    def __init__(self, *args, quiescent_density=None, **kwargs):
        from .quiescent import density_value
        density_value(quiescent_density)
        super().__init__(*args, quiescent_density=quiescent_density, **kwargs)
        self.source_fluid_samples = []
        self.source_body_fluid_samples = []
        for mesh in self.meshes:
            beam = mesh.beam
            if not beam.lifting:
                d = beam.distributions.get('radius')
                if d is not None and (not np.all(np.isfinite(d.values)) or np.any(d.values < 0)):
                    raise AnalysisError('Source body apparent inertia requires finite nonnegative radius.')
                for end, (t, side) in enumerate(((mesh.t0, 'right'), (mesh.t1, 'left'))):
                    radius = beam.value('radius', t, side=side)
                    if not np.all(np.isfinite(radius)) or np.any(radius < 0):
                        raise AnalysisError('Source body apparent inertia requires finite nonnegative endpoint radius.')
                    self.source_body_fluid_samples.append((beam.index, self.beam_elements[beam.index], end, radius))
                continue
            for name in ('chord', 'Xax'):
                d = beam.distributions.get(name)
                if d is not None and (not np.all(np.isfinite(d.values)) or name == 'chord' and np.any(d.values < 0)):
                    raise AnalysisError('Source apparent inertia requires finite Xax and nonnegative finite chord.')
            for end, (t, side) in enumerate(((mesh.t0, 'right'), (mesh.t1, 'left'))):
                chord, xax = beam.value('chord', t, side=side), beam.value('Xax', t, side=side)
                if np.any(chord < 0) or not np.all(np.isfinite([chord, xax])):
                    raise AnalysisError('Source apparent inertia requires finite Xax and nonnegative finite endpoint chord.')
                self.source_fluid_samples.append((beam.index, self.beam_elements[beam.index], end, chord, xax))

    def _check_analysis_scope(self):
        if (self.condition is not None or self.ng or self.operating.count
                or self.engines or self.quiescent_density is None):
            raise AnalysisError('Source still-air modes require explicit density without airflow, operating constraints or engines.')

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, *,
                 local_motion=None, circulation_rate=None, gravity=None, _loads_only=False):
        result = super().external(r, Q, meshes, gamma, condition, motion, operating_key,
            local_motion=local_motion, circulation_rate=circulation_rate, gravity=gravity, _loads_only=_loads_only)
        force, moment, aero, records, couples, ends = result
        if local_motion is None:
            return result
        # Preserve the real-mass cache used by f_reac reporting.
        force, moment = force.copy(), moment.copy()
        local = local_motion
        interval_force, interval_moment = np.zeros((self.ne, 3)), np.zeros((self.ne, 3))
        for beam, sl, end, chord, xax in self.source_fluid_samples:
            nodes = (self.a if end == 0 else self.b)[sl]
            frame = (local.ra if end == 0 else local.rb)[sl]
            acceleration = (local.aa if end == 0 else local.ab)[sl]
            f, m = source_apparent_wrench(frame, chord, xax, self.quiescent_density,
                                         acceleration, local.rate_derivative[nodes])
            interval_force[sl] += self.ds[sl, None]*f/2
            interval_moment[sl] += self.ds[sl, None]*m/2
        from .body_apparent import acceleration_force
        for beam, sl, end, radius in self.source_body_fluid_samples:
            frame = (local.ra if end == 0 else local.rb)[sl]
            acceleration = (local.aa if end == 0 else local.ab)[sl]
            f = acceleration_force(frame[..., 1], radius, self.quiescent_density,
                acceleration, self.quiescent_body_added_mass_factor)
            interval_force[sl] += self.ds[sl, None]*f/2
        ends = ends+interval_force[:, None, :]/2
        couples = couples+interval_moment[:, None, :]/2
        for ids in (self.a, self.b):
            np.add.at(force, ids, interval_force/2)
            np.add.at(moment, ids, interval_moment/2)
        return force, moment, aero, records, couples, ends

    def rigid_acceleration_report(self, meshes=None, reference=None):
        """Rigid projection of the actual endpoint-load operator.

        This is an acceleration-response Jacobian, not an energy-based mass
        tensor. Endpoint-varying sections can make it nonsymmetric. Use the
        current endpoint geometry with the source policy's unloaded lengths.
        """
        geometry = 'undeformed' if meshes is None else 'provided endpoint geometry'
        meshes = self.meshes if meshes is None else meshes
        reference = np.asarray(self.model.reference[1] if reference is None else reference, dtype=float)
        coefficients = {(beam, end): (chord, xax)
                        for beam, _, end, chord, xax in self.source_fluid_samples}
        body_coefficients = {(beam, end): radius for beam, _, end, radius in self.source_body_fluid_samples}
        matrix = np.zeros((6, 6))
        for mesh in meshes:
            beam = mesh.beam
            frame0 = surface_frame(beam, mesh.t0, 'right') if mesh.frame0 is None else mesh.frame0
            frame1 = surface_frame(beam, mesh.t1, 'left') if mesh.frame1 is None else mesh.frame1
            if beam.lifting:
                chord0, xax0 = coefficients[beam.index, 0]
                chord1, xax1 = coefficients[beam.index, 1]
                matrix += rigid_acceleration_response(mesh.r0, mesh.r1, frame0, frame1,
                    chord0, chord1, xax0, xax1, self.ds[self.beam_elements[beam.index]],
                    self.quiescent_density, reference).sum(axis=0)
            else:
                from .body_apparent import source_rigid_response
                matrix += source_rigid_response(mesh.r0, mesh.r1, frame0, frame1,
                    body_coefficients[beam.index, 0], body_coefficients[beam.index, 1],
                    self.ds[self.beam_elements[beam.index]], self.quiescent_density, reference,
                    self.quiescent_body_added_mass_factor).sum(axis=0)
        return dict(matrix=matrix.tolist(), reference=reference.tolist(), geometry=geometry,
            definition='[force, moment_about_reference] = -matrix @ [reference_acceleration, angular_acceleration]',
            input_axes=['ax', 'ay', 'az', 'alphax', 'alphay', 'alphaz'],
            output_axes=['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz'],
            structural_operator=self.structural_operator,
            length_policy='unloaded source beam intervals',
            maximum_antisymmetric_entry=float(np.max(abs(matrix-matrix.T))),
            scope='Rigid projection of completed endpoint acceleration loads and arithmetic box transfer. '
                  'Not a symmetric spatial mass tensor, not an apparent CG, and not a historical ASWING exporter match.')

    def fluid_report(self, meshes=None):
        samples = []
        for beam, sl, end, chord, xax in self.source_fluid_samples:
            mu = self.quiescent_density*np.pi*chord**2/4
            samples.append(dict(beam=beam, end=end, element_indices=list(range(sl.start, sl.stop)),
                normal_mass_per_length=mu.tolist(), midchord_arm=((.5-xax)*chord).tolist(),
                span_pitch_inertia_per_length=(mu*chord**2/32).tolist()))
        for beam, sl, end, radius in self.source_body_fluid_samples:
            mu = self.quiescent_body_added_mass_factor*self.quiescent_density*np.pi*radius**2
            samples.append(dict(beam=beam, end=end, element_indices=list(range(sl.start, sl.stop)),
                kind='circular_body', transverse_mass_per_length=mu.tolist(),
                axial_mass_per_length=np.zeros_like(mu).tolist(),
                section_rotary_inertia_per_length=np.zeros_like(mu).tolist()))
        return dict(kind='quiescent', density=self.quiescent_density, density_units='input M/L^3',
            body_added_mass_factor=self.quiescent_body_added_mass_factor,
            mean_velocity_body=[0., 0., 0.], circulatory=False, wind_direction=None,
            structural_operator=self.structural_operator, supported_analyses=['fixed_frame_modes', 'fixed_frame_frequency_response'],
            rigid_acceleration_response=self.rigid_acceleration_report(meshes),
            apparent_properties=dict(spatial_matrix=None, mass_tensor=None, inertia_reference=None,
                scope='Endpoint coefficients in physical local c/s/n axes; completed loads are averaged before symmetric endpoint transfer.',
                endpoint_coefficients=samples),
            limitations=[
                'Stationary fixed-frame modes and frequency response: thin-strip apparent mass and midchord/pitch coupling from Eqs.41–44; circular-body transverse inertia from Eq.45. Body factor 1 is cylinder potential flow; 2 is the printed ASWING coefficient. No fluid stiffness, damping, buoyancy or circulation is added.',
                'Input chord is the local airfoil-plane chord. There is no wind projection or real-mass finite-segment correction in fluid inertia.',
                'The completed endpoint-product rule can yield a nonsymmetric global descriptor mass for varying properties. No single symmetric aggregate apparent-inertia tensor is asserted.',
                'Quadratic fluid velocity/rate terms vanish at the stationary base and are outside this modal operator; nonlinear fluid response and moving frames are unsupported.',
                'Finite-span fluid interaction, viscosity, surface thickness, compressibility, wall effects and point-object aerodynamic volumes are unsupported. Historical ASWING sampling and modal reference agreement remain unverified.'])
