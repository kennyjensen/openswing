"""Dimensionless arclength continuation for unchanged circulation equations.

H(z, lambda) = lambda R(z) - (1-lambda) D z connects z=0 to R(z)=0.
The auxiliary regularizer is exactly absent in every returned solution. This
selects a numerical continuation branch; it does not establish uniqueness or
physical stability of a stalled flow.
"""
import numpy as np
import warnings
from scipy.linalg import solve, LinAlgWarning
from scipy.optimize import root


class CirculationContinuationError(ValueError):
    pass


def jacobian(function, point):
    """Centered derivatives in dimensionless circulation coordinates."""
    point = np.asarray(point, dtype=float)
    step = np.cbrt(np.finfo(float).eps)*np.maximum(1., abs(point))
    out = np.empty((len(point), len(point)))
    for j, h in enumerate(step):
        left, right = point.copy(), point.copy()
        left[j] -= h; right[j] += h
        out[:, j] = (function(right)-function(left))/(2*h)
    return out


def _newton_corrector(function, derivative, predicted, tolerance):
    """Bounded Newton correction with LU solves and residual backtracking.

    Continuation predictions are already near the solution. Dense MINPACK QR
    factorizations at every step are unnecessarily expensive in this regime.
    Return None on an unresolved correction so the original hybrid corrector
    can retry from the original prediction. The caller still applies every
    arclength, branch-neighborhood and physical-endpoint acceptance check.
    """
    trial = predicted.copy()
    value = function(trial)
    for iteration in range(9):
        error = float(np.max(abs(value)))
        if not np.isfinite(error):
            return None
        if error <= tolerance:
            return trial
        if iteration == 8:
            return None
        matrix = derivative(trial)
        if not np.all(np.isfinite(matrix)):
            return None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', LinAlgWarning)
                update = solve(matrix, -value, assume_a='gen', check_finite=False)
        except (np.linalg.LinAlgError, LinAlgWarning):
            return None
        if not np.all(np.isfinite(update)):
            return None
        for fraction in (1., .5, .25, .125, .0625, .03125, .015625):
            candidate = trial + fraction*update
            candidate_value = function(candidate)
            if np.all(np.isfinite(candidate_value)) and np.max(abs(candidate_value)) < error:
                trial, value = candidate, candidate_value
                break
        else:
            return None
    return None


def continue_circulation(residual, regularizer, *, derivative=None, tolerance=1e-11, max_step=.04,
                         progress=None):
    """Pseudo-arclength predictor/corrector, rollback and exact endpoint solve.

    The metric uses the mean square of dimensionless circulation coordinates
    plus lambda squared. Lambda may turn at a fold inside [0,1]. A path that
    leaves this interval or exhausts the bounded step search is unresolved;
    an intermediate homotopy state is never returned as a physical solution.
    """
    d = np.asarray(regularizer, dtype=float)
    if d.ndim != 2 or d.shape[0] != d.shape[1] or not np.all(np.isfinite(d)):
        raise ValueError('Circulation regularizer must be a finite square matrix.')
    if not np.isfinite(max_step) or max_step <= 0 or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Circulation continuation step and tolerance must be positive and finite.')
    n = len(d)
    if not n:
        return np.empty(0), dict(method='continuation', path='pseudo-arclength', steps=0,
            attempts=0, evaluations=0, trace=[], final_regularization=0., physical_residual=0.)
    attempt_limit = 600
    if progress is not None:
        progress('static_circulation_continuation', 0, attempt_limit)
    singular = np.linalg.svd(d, compute_uv=False)
    if singular[-1] <= 1e-12*singular[0]:
        raise CirculationContinuationError('Circulation continuation has an unresolved coordinate scaling.')
    evaluations = 0
    def r(z):
        nonlocal evaluations
        evaluations += 1
        value = np.asarray(residual(z), dtype=float)
        if value.shape != (n,) or not np.all(np.isfinite(value)):
            raise CirculationContinuationError('Circulation continuation encountered a nonfinite residual.')
        return value
    def physical_jacobian(z):
        return derivative(z) if derivative is not None else jacobian(r, z)
    def h(y):
        z, parameter = y[:-1], y[-1]
        return parameter*r(z)-(1-parameter)*(d@z)
    def h_jacobian(y):
        z, parameter = y[:-1], y[-1]
        return np.column_stack((parameter*physical_jacobian(z)-(1-parameter)*d, r(z)+d@z))
    metric = np.r_[np.full(n, 1/n), 1.]
    def norm(y):
        return float(np.sqrt(np.dot(metric*y, y)))
    y = np.zeros(n+1)
    tangent = np.r_[np.zeros(n), 1.]
    step = min(.04, max_step)
    trace = []
    correctors = dict(newton=0, hybrid=0)
    reason = 'step search exhausted'
    for attempt in range(attempt_limit):
        if progress is not None:
            progress('static_circulation_continuation', attempt+1, attempt_limit)
        # A fixed 1e-7 floor can stop before closely spaced stall corners,
        # even when the unchanged predictor/corrector checks resolve them.
        # Bound refinement by floating-point resolution in the same metric;
        # the attempt budget and physical/branch acceptance guards remain.
        if step < 64*np.finfo(float).eps*max(1., norm(y)):
            reason = 'arclength step became too small'
            break
        # The bordered system remains regular at a simple lambda fold. Its
        # last row orients the new tangent along the previously accepted path.
        try:
            direction = np.linalg.solve(np.vstack((h_jacobian(y), metric*tangent)), np.r_[np.zeros(n), 1.])
        except np.linalg.LinAlgError:
            reason = 'arclength tangent is singular'
            break
        tangent = direction/norm(direction)
        predicted = y+step*tangent
        limit = .5*max(1., float(np.max(abs(y[:-1]))))
        if np.max(abs(predicted[:-1]-y[:-1])) > limit:
            step *= .5
            continue
        def corrector(trial):
            return np.r_[h(trial), np.dot(metric*tangent, trial-predicted)]
        def corrector_jacobian(trial):
            return np.vstack((h_jacobian(trial), metric*tangent))
        try:
            candidate = None
            if derivative is not None:
                candidate = _newton_corrector(corrector, corrector_jacobian, predicted, .1*tolerance)
            if candidate is None:
                correctors['hybrid'] += 1
                solution = root(corrector, predicted, jac=corrector_jacobian,
                    method='hybr', options={'xtol': 1e-11})
                candidate = solution.x
            else:
                correctors['newton'] += 1
            error = float(np.max(abs(corrector(candidate))))
            correction = norm(candidate-predicted)
        except CirculationContinuationError:
            step *= .5
            continue
        if (error > tolerance or correction > .5*step or norm(candidate-y) > 1.5*step
                or np.max(abs(candidate-predicted)) > .25*np.max(abs(predicted-y))
                or np.max(abs(candidate[:-1]-y[:-1])) > limit):
            step *= .5
            continue
        if candidate[-1] < 0:
            reason = 'path left the admissible regularization interval'
            break
        if y[-1] < 1 <= candidate[-1]:
            # Locate lambda=1 on the accepted path, then solve R=0 exactly.
            fraction = (1-y[-1])/(candidate[-1]-y[-1])
            guess = y[:-1]+fraction*(candidate[:-1]-y[:-1])
            endpoint = root(r, guess, jac=physical_jacobian, method='hybr', options={'xtol': 1e-11})
            error = float(np.max(abs(r(endpoint.x))))
            if error > tolerance or norm(np.r_[endpoint.x-guess, 0.]) > .5*step:
                step *= .5
                continue
            trace.append(dict(parameter=1., residual=error, physical_residual=error,
                              step=float(step*fraction), predictor_correction=norm(np.r_[endpoint.x-guess, 0.]),
                              parameter_tangent=float(tangent[-1])))
            return endpoint.x, dict(method='continuation', path='pseudo-arclength', steps=len(trace),
                attempts=attempt+1, evaluations=evaluations, trace=trace, maximum_step=max_step, final_regularization=0.,
                correctors=correctors,
                physical_residual=error,
                scope='A continuation branch of the unchanged circulation equations; uniqueness and aircraft stability are not established.')
        y = candidate.copy()
        trace.append(dict(parameter=float(y[-1]), residual=error,
                          physical_residual=float(np.max(abs(r(y[:-1])))),
                          step=float(step), predictor_correction=correction, parameter_tangent=float(tangent[-1])))
        step = min(max_step, step*1.4 if correction < .1*step else step)
    raise CirculationContinuationError(
        f'Circulation continuation stopped at lambda={y[-1]:.9g}: {reason}; '
        'no full physical solution was returned. Refine the mesh/basis or use operating-point continuation; a fold or competing branch may be present.')
