"""Scoped analytic control inputs for equilibrium response derivatives.

Only fixed-state residual input partials are replaced. The caller retains its
checked centered input probes, state Jacobian and directional output recovery.
"""
import numpy as np

from .control_tangent import control_columns
from .circulation_tangent import CirculationDerivativeUnavailable
from .structured_static import IterationFields, StructuredTangentUnavailable


def capture_control_columns(network, state, checked, baseline, *, controls,
                            response, feedback, step, report):
    """Return residual columns per literal file control unit, or None.

    Capture on the caller's shallow trial network before acquiring a probe
    cache. Physical failures propagate; only explicit derivative/storage
    unavailability retains the complete centered input columns.
    """
    reasons = []
    valid_controls = (isinstance(controls, (list, tuple)) and bool(controls)
                      and all(isinstance(k, int) and not isinstance(k, bool) for k in controls)
                      and len(set(controls)) == len(controls))
    if not valid_controls:
        reasons.append('no distinct integer control parameters')
    elif any(k not in network.model.controls for k in controls):
        reasons.append('control parameter is not declared by the model')
    if response != 'fixed_acceleration': reasons.append('response is not fixed_acceleration')
    if feedback is not None: reasons.append('feedback is active')
    if not network.ng: reasons.append('no circulation unknowns')
    if network.model.records.get('engine', []): reasons.append('engine records require centered derivatives')
    if any(c['type'] == 3 for c in network.constraints): reasons.append('type-3 hinges require centered derivatives')
    for name in ('iteration_fields', 'tangent_influences', '_tangent_loads'):
        if getattr(network, name) is not None: reasons.append(name+' already has an owner')
    report.update(eligible=not reasons, enabled=False, fallback_reasons=reasons,
                  controls=list(controls) if valid_controls else [],
                  units='literal file control setting',
                  checked_centered_control_probes_retained=True,
                  capture_phase='capture', fixed_geometry=True,
                  output_recovery='centered directional derivatives',
                  factor=1., step=step)
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
        captured = checked(state)
        if not np.array_equal(captured, baseline):
            raise CirculationDerivativeUnavailable('Fresh control capture differs from the original base residual.')
        if fields.circulation_aero is None or fields.circulation_mechanics is None:
            raise CirculationDerivativeUnavailable('Missing fixed-geometry control capture.')
        direct = control_columns(network, fields, list(controls))
        if (not isinstance(direct, np.ndarray) or direct.shape != (network.size, len(controls))
                or direct.dtype.kind != 'f'):
            raise CirculationDerivativeUnavailable('Invalid analytic control block shape.')
        if not np.all(np.isfinite(direct)):
            raise CirculationDerivativeUnavailable('Nonfinite analytic control block.')
        report.update(enabled=True, columns=len(controls),
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
