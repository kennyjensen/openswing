"""Exact zero-flow surface/body apparent inertia for stationary fixed-frame modes.

There is no circulation, wake direction, flow coefficient, or epsilon velocity.
This candidate supports linear modes only; it is not a nonlinear fluid solver.
"""
from numbers import Real
import numpy as np
from .aero import AnalysisError
from .inertia import Motion, surface_apparent_loads, apparent_properties


def density_value(value):
    if (isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
            or not np.isfinite(value) or value <= 0):
        raise AnalysisError('Quiescent density must be a positive finite number in input M/L^3 units; use vacuum for zero density.')
    return float(value)


def stationary(motion):
    if not isinstance(motion, Motion) or any(np.any(getattr(motion, key))
            for key in ('rates', 'acceleration', 'angular_acceleration')):
        raise AnalysisError('Quiescent modes require zero prescribed rates and accelerations.')


def validate_model(model):
    if model.records.get('engine'):
        raise AnalysisError('Quiescent modes do not support Engine blocks.')
    if any(np.any(row[6:8]) for row in model.records.get('weight', [])):
        raise AnalysisError('Quiescent modes do not support point-object aerodynamic drag areas or volumes; mechanical Weight entries are supported.')


def prepare(model, condition, density, *, frame, motion, velocity, position, attitude,
            gravity_magnitude, controller, operating_constraints, load_targets):
    density = density_value(density)
    validate_model(model)
    if frame != 'fixed':
        raise AnalysisError('Quiescent modes currently require frame="fixed".')
    if controller is not None or operating_constraints or load_targets:
        raise AnalysisError('Quiescent modes do not support controllers, operating constraints or frame load targets.')
    velocity = np.asarray(velocity, dtype=float)
    if velocity.shape != (3,) or not np.all(np.isfinite(velocity)) or np.any(velocity):
        raise AnalysisError('Quiescent modes require exactly zero base velocity.')
    stationary(Motion() if motion is None else motion)
    if condition is not None:
        if condition.speed != 0 or not np.isfinite(condition.speed):
            raise AnalysisError('An explicit quiescent medium requires condition.speed exactly zero.')
        stationary(condition.motion())
        if condition.density is not None and condition.density != density:
            raise AnalysisError('FlightCondition density conflicts with explicit quiescent_density.')
        if (condition.gust is not None or condition.ground_effect or condition.circulation_modes
                or condition.freeze_influences or condition.mach not in (None, 0)):
            raise AnalysisError('Quiescent modes do not support gusts, ground images, circulation settings or nonzero Mach.')
        if any(value != 0 for value in [*condition.controls.values(), *condition.powers.values()]):
            raise AnalysisError('Quiescent modes do not support nonzero control or power settings.')
        # Zero flow has no wind angles. In particular do not call vectors().
        position, attitude = condition.position_earth, condition.attitude
        if condition.gravity_magnitude is not None:
            gravity_magnitude = condition.gravity_magnitude
    return density, position, attitude, gravity_magnitude


def add_loads(network, r, meshes, motion, local_motion, force, moment, element_forces, element_moments):
    """Add dimensional fluid reaction with the existing power-conjugate transfer."""
    stationary(motion)
    if local_motion is None:
        # The stationary frame and no elastic kinematics imply exactly zero load.
        return
    for mesh in meshes:
        beam = mesh.beam
        fractions = network.fractions[beam.index]
        if beam.lifting:
            field, _, _ = local_motion.sample(beam.index, fractions)
            fs, ms = surface_apparent_loads(mesh.rm, mesh.frames,
                beam.value('chord', mesh.tm), beam.value('Xax', mesh.tm), mesh.length,
                network.quiescent_density, -field.velocity_at(mesh.rm), motion,
                network.model.reference[2], local_motion=field)
        else:
            from .volume import body_quadrature
            from .body_apparent import acceleration_force
            t, positions, radius, weights = body_quadrature(mesh)
            fractions = (t-mesh.t0[:, None])/(mesh.t1-mesh.t0)[:, None]
            field, _, _ = local_motion.sample(beam.index, fractions)
            acceleration = field.absolute_acceleration(positions, motion, network.model.reference[2])
            fs = weights[..., None]*acceleration_force(mesh.frames[:, None, :, 1], radius,
                network.quiescent_density, acceleration, network.quiescent_body_added_mass_factor)
            ms = np.zeros_like(fs)
        sl = network.beam_elements[beam.index]
        for end, (ids, f, m) in enumerate(local_motion.nodal_wrenches(beam.index, fractions, fs, ms)):
            np.add.at(force, ids, f)
            np.add.at(moment, ids, m)
            element_forces[sl, end] += f
            element_moments[sl, end] += m


def report(network, meshes):
    if getattr(network, 'source_quiescent', False):
        return network.fluid_report(meshes)
    return dict(kind='quiescent', density=network.quiescent_density, density_units='input M/L^3',
        mean_velocity_body=[0., 0., 0.], circulatory=False, wind_direction=None,
        body_added_mass_factor=network.quiescent_body_added_mass_factor,
        apparent_properties=apparent_properties(meshes, network.quiescent_density, network.model.reference[1], network.quiescent_body_added_mass_factor),
        supported_analyses=['fixed_frame_modes'],
        limitations=['Incompressible thin-surface added mass with midchord/pitch coupling, and circular-body transverse added mass. Body factor 1 is classical cylinder flow; factor 2 is printed ASWING Eq.45.',
            'Finite-span fluid coupling, viscosity, fluid damping, surface thickness, compressibility and wall corrections are omitted.',
            'Density is explicit; zero-speed test density is not inferred from flutter conditions.',
            'No ASWING executable parity or measured ST4 modal validation is claimed.'])
