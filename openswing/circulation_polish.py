"""Bounded terminal Newton correction of the unchanged physical equations.

This improves an already computed local root; it does not select a root,
continue a branch, regularize the equations or replace caller-supplied states.
"""
import numpy as np


def polish_circulation(residual, derivative, gamma, initial_residual, *, scale,
                       tolerance=1e-12, maximum_steps=4):
    gamma = np.asarray(gamma, dtype=float).copy()
    value = np.asarray(initial_residual, dtype=float).copy()
    report = dict(target=tolerance, evaluations=0, jacobians=0, accepted_steps=0,
                  status='ALREADY_RESOLVED', corrections=[])
    if (gamma.ndim != 1 or value.shape != gamma.shape or
            not np.all(np.isfinite(gamma)) or not np.all(np.isfinite(value)) or
            not np.isfinite(scale) or scale <= 0 or
            not np.isfinite(tolerance) or tolerance <= 0):
        raise ValueError('Circulation polishing requires finite matching vectors and positive scales.')
    error = float(np.max(abs(value), initial=0.))
    report['initial_residual'] = error
    origin = gamma.copy()
    # A terminal correction must remain close to the root already selected.
    # The common Gamma scale transforms as L²/T under changes of input units.
    # This numerical neighborhood does not prove identity of a physical branch.
    radius = 1e-8 * max(scale, float(np.max(abs(origin), initial=0.)))
    report['maximum_total_gamma_change'] = radius
    for index in range(maximum_steps):
        if error <= tolerance:
            break
        row = dict(index=index, before_residual=error, accepted=False, trials=[])
        report['corrections'].append(row)
        report['jacobians'] += 1
        try:
            matrix = np.asarray(derivative(gamma), dtype=float)
        except (ValueError, FloatingPointError, OverflowError) as exc:
            report['status'] = 'JACOBIAN_DOMAIN_FAILURE_RETAINED'
            row.update(status=report['status'], exception=type(exc).__name__, error=str(exc))
            break
        if matrix.shape != (len(gamma), len(gamma)) or not np.all(np.isfinite(matrix)):
            report['status'] = 'INVALID_JACOBIAN_RETAINED'
            row['status'] = report['status']
            break
        try:
            delta = np.linalg.solve(matrix, -value)
        except np.linalg.LinAlgError as exc:
            report['status'] = 'SINGULAR_JACOBIAN_RETAINED'
            row.update(status=report['status'], error=str(exc))
            break
        row['proposed_max_step'] = float(np.max(abs(delta), initial=0.)) if np.isfinite(delta).all() else None
        if not np.all(np.isfinite(delta)) or np.max(abs(delta), initial=0.) > radius:
            report['status'] = 'NONLOCAL_CORRECTION_RETAINED'
            row['status'] = report['status']
            break
        row['linear_defect'] = float(np.max(abs(matrix @ delta + value), initial=0.))
        accepted = False
        for half in range(7):
            factor = 2. ** (-half)
            candidate = gamma + factor * delta
            trial_record = dict(factor=factor, status='STARTED')
            row['trials'].append(trial_record)
            if (not np.all(np.isfinite(candidate)) or
                    np.max(abs(candidate - origin), initial=0.) > radius):
                trial_record['status'] = 'NONLOCAL_OR_NONFINITE_TRIAL_RETAINED'
                continue
            report['evaluations'] += 1
            try:
                trial = np.asarray(residual(candidate), dtype=float)
            except (ValueError, FloatingPointError, OverflowError) as exc:
                trial_record.update(status='RESIDUAL_DOMAIN_FAILURE_RETAINED',
                                    exception=type(exc).__name__, error=str(exc))
                continue
            if trial.shape != value.shape or not np.all(np.isfinite(trial)):
                trial_record['status'] = 'INVALID_RESIDUAL_RETAINED'
                continue
            trial_error = float(np.max(abs(trial), initial=0.))
            trial_record.update(status='NONIMPROVING_RETAINED', residual=trial_error)
            if trial_error < error:
                trial_record['status'] = 'ACCEPTED'
                row.update(factor=factor, after_residual=trial_error,
                           realized_max_step=float(np.max(abs(candidate-gamma), initial=0.)))
                gamma, value, error = candidate, trial, trial_error
                report['accepted_steps'] += 1
                report['status'] = 'IMPROVED'
                accepted = True
                break
        row['accepted'] = accepted
        row['status'] = 'IMPROVED' if accepted else 'NONIMPROVING_CORRECTION_RETAINED'
        if not accepted:
            report['status'] = 'NONIMPROVING_CORRECTION_RETAINED'
            break
    report['final_residual'] = error
    report['target_met'] = error <= tolerance
    if report['accepted_steps'] and report['target_met']:
        report['status'] = 'TARGET_RECOVERED'
    report['total_gamma_change'] = float(np.max(abs(gamma-origin), initial=0.))
    return gamma, value, report
