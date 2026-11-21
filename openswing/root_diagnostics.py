"""Bounded accepted-root probes for explicit nonsmooth controller residuals.

A witness shows numerically accepted alternatives at a resolved probe scale.
Absence of a witness is not a nonsmooth uniqueness certificate: narrow, curved,
and other branch families are outside this diagnostic. It does not change the
original residual or replace the centered accepted-root rank test.
"""
import numpy as np
from .aero import AnalysisError


def controller_alternatives(rows, tolerance):
    """Build an explicit callback for selected algebraic controller rows.

    The caller owns full residual row indices, its original tolerance and all
    history/side context. This square-root callback is not a derivative-array
    initializer: auxiliary Taylor directions require different ownership.
    """
    rows=tuple(rows);tolerance=float(tolerance)
    if not np.isfinite(tolerance) or tolerance<=0:
        raise ValueError('The original residual tolerance must be positive.')
    if not rows or any(isinstance(i,bool) or not isinstance(i,(int,np.integer)) or i<0 for i in rows) or len(set(rows))!=len(rows):
        raise ValueError('Controller rows must be distinct nonnegative integers.')

    def diagnose(function, values, jacobian):
        from .time_integration import UnresolvedControllerAuthority
        x=np.asarray(values);jac=np.asarray(jacobian)
        if jac.shape!=(len(x),len(x)) or max(rows)>=len(x):
            raise ValueError('Controller row ownership does not match the square residual.')
        basis=np.zeros((len(x),len(rows)))
        basis[list(rows),np.arange(len(rows))]=1.
        scale=np.maximum(1.,abs(x));h=2.5e-5
        try:
            base=np.asarray(function(x)).copy()
            try:
                directions=np.linalg.solve(jac,basis)
            except np.linalg.LinAlgError:
                # The existing balanced rank gate already passed. Failure of
                # this optional raw solve supplies no alternative-state witness.
                return
            for row,direction in zip(rows,directions.T):
                magnitude=float(np.max(abs(direction)/scale))
                if not np.isfinite(magnitude) or magnitude==0:continue
                direction=direction/magnitude
                predicted=float(np.max(abs(jac@direction)))
                signal=predicted*h
                if not np.isfinite(signal) or signal<=32*tolerance:continue
                for sign in (-1.,1.):
                    steps=sign*h*np.array([1.,2.,4.])
                    trials=[x+step*direction for step in steps]
                    try:
                        residuals=[np.asarray(function(trial)).copy() for trial in trials]
                    except (AnalysisError,ValueError,FloatingPointError):
                        # Same domain/finite-value exceptions as Newton's line
                        # search: an inadmissible diagnostic is not a witness.
                        continue
                    if any(not np.all(np.isfinite(r)) or np.max(abs(r))>tolerance for r in residuals):continue
                    slopes=[float(np.max(abs((b-a)/(v-u)))) for a,b,u,v in zip(residuals,residuals[1:],steps,steps[1:])]
                    if max(slopes)>1e-6*predicted:continue
                    witness=dict(kind='resolved_nearby_accepted_alternatives',controller_row=int(row),
                        tolerance=tolerance,steps=steps.tolist(),centered_predicted_first_change=signal,
                        profile_slopes=slopes,centered_slope=predicted,base=x.tolist(),
                        base_residual=base.tolist(),trials=[a.tolist() for a in trials],
                        residuals=[a.tolist() for a in residuals],
                        limitation='Finite diagnostic witness; not a proof of a root continuum or a general nonsmooth uniqueness certificate.')
                    error=UnresolvedControllerAuthority('Nonsmooth controller has unresolved nearby accepted alternatives in the original full residual; control authority is not certified.')
                    error.accepted_root_witness=witness
                    raise error
        finally:
            # The original residual owns mutable physical caches. Restore its
            # accepted state after successful probes and diagnostic rejection.
            function(x)
    return diagnose
