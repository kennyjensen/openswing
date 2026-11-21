"""Scoped analytic circulation block for equilibrium response derivatives.

This validation prototype retains every checked centered probe in the caller.
It changes only the Gamma block; it does not approximate geometry derivatives
or reuse an equilibrium solver's final Newton matrix.
"""
import numpy as np
from .circulation_tangent import circulation_columns, CirculationDerivativeUnavailable
from .structured_static import IterationFields, StructuredTangentUnavailable


def capture_circulation_columns(network, state, checked, baseline, *, response,
                                feedback, step, report):
    """Return a complete analytic Gamma block, or None for centered fallback.

    Call before acquiring the derivative-probe cache. Physical evaluation and
    branch failures propagate; only explicit derivative/storage unavailability
    permits fallback. The network is the derivative API's shallow trial copy.
    """
    reasons = []
    if response != 'fixed_acceleration': reasons.append('response is not fixed_acceleration')
    if feedback is not None: reasons.append('feedback is active')
    if not network.ng: reasons.append('no circulation unknowns')
    if network.model.records.get('engine', []): reasons.append('engine records require centered derivatives')
    if any(c['type'] == 3 for c in network.constraints): reasons.append('type-3 hinges require centered derivatives')
    for name in ('iteration_fields', 'tangent_influences', '_tangent_loads'):
        if getattr(network, name) is not None: reasons.append(name+' already has an owner')
    report.update(eligible=not reasons, enabled=False, fallback_reasons=reasons,
                  checked_centered_gamma_probes_retained=True,
                  capture_phase='capture', lagged_geometry=False,
                  factor=1., circulation_rate_factor=0.)
    if reasons:
        return None
    fields = IterationFields()
    fields.capture_circulation = True
    old_fields = network.iteration_fields
    old_pairs, old_loads = network.tangent_influences, network._tangent_loads
    before = network.nfev
    network.iteration_fields = fields
    network.aero_key = network.aero_cached = None
    try:
        # This always evaluates the full base residual. No geometry phase is
        # entered, and the caller's physical branch checks remain active.
        captured = checked(state)
        if not np.array_equal(captured, baseline):
            raise CirculationDerivativeUnavailable('Fresh capture differs from the original base residual.')
        data = fields.circulation_aero
        if data is None:
            raise CirculationDerivativeUnavailable('Missing aerodynamic circulation capture.')
        velocity, span = data['velocity'], data['p']['s']
        perpendicular = velocity-np.sum(velocity*span, axis=-1)[:, None]*span
        speed = np.linalg.norm(perpendicular, axis=-1)
        floor = data['condition'].speed*1e-12
        # A conservative smooth-flow exclusion. The existing checked probes
        # remain intact; this guard only declines the analytic replacement.
        minimum = max(100*floor, 10*step*data['condition'].speed)
        report.update(minimum_transverse_speed=float(np.min(speed, initial=np.inf)),
                      smooth_flow_minimum=minimum)
        if np.any(~np.isfinite(speed)) or np.any(speed <= minimum):
            raise CirculationDerivativeUnavailable('Transverse flow is too close to the speed floor.')
        direct = circulation_columns(network, fields, 1., circulation_rate_factor=0.)
        if (not isinstance(direct, np.ndarray) or direct.shape != (network.size, network.ng)
                or direct.dtype.kind != 'f'):
            raise CirculationDerivativeUnavailable('Invalid analytic circulation block shape.')
        if not np.all(np.isfinite(direct)):
            raise CirculationDerivativeUnavailable('Nonfinite analytic circulation block.')
        # Without engines the fixed-geometry velocity is affine in Gamma.
        # The reverse triangle inequality bounds every retained centered
        # Gamma stencil away from the speed floor, including its interior.
        velocity_columns = fields.values['vortex', 'hv'].apply_columns(
            network.gamma_scale*data['basis'].sample)
        transverse_columns = velocity_columns-span[:, :, None]*np.einsum(
            'ni,nij->nj', span, velocity_columns)[:, None, :]
        steps = step*np.maximum(1., abs(state[network.gamma_start:network.operating_start]))
        excursions = np.linalg.norm(transverse_columns, axis=1)*steps[None, :]
        clearance = speed[:, None]-floor-excursions
        if not np.all(np.isfinite(clearance)) or np.any(clearance <= 16*np.finfo(float).eps*data['condition'].speed):
            raise CirculationDerivativeUnavailable('Gamma stencil cannot be bounded away from the speed floor.')
        report['minimum_stencil_speed_floor_clearance'] = float(np.min(clearance))
        report.update(enabled=True, columns=network.ng,
                      field_storage_bytes=fields.bytes, fixed_storage_bytes=fields.fixed_bytes)
        return direct
    except (CirculationDerivativeUnavailable, StructuredTangentUnavailable, MemoryError) as exc:
        report['fallback_reasons'].append(type(exc).__name__+': '+str(exc))
        return None
    finally:
        network.iteration_fields = old_fields
        network.aero_key = network.aero_cached = None
        report.update(capture_evaluations=network.nfev-before,
                      owner_restored=network.iteration_fields is old_fields,
                      tangent_owner_unchanged=network.tangent_influences is old_pairs,
                      tangent_load_owner_unchanged=network._tangent_loads is old_loads,
                      aero_cache_invalidated=network.aero_key is None and network.aero_cached is None)
