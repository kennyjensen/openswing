"""Physical initial conditions and free evolution, unsteady theory §13.3.3.

Initial coordinates use the left mass-dual projection, q0 = W^T M x0.
The complete finite pencil supplies the constraint completion, reference
history and convergence bound. A truncated ROM never replaces those checks.
"""
from copy import deepcopy
import warnings
import numpy as np
from scipy.linalg import expm
from .aero import AnalysisError
from .initial_response import ConsistentSubspace, InitialInput
from .linear_dynamics import complex_data
from .frequency_response import harmonic_solve, HarmonicPole


def time_grid(values):
    try: times=np.asarray(values,dtype=float)
    except (TypeError,ValueError) as exc:raise AnalysisError('Initial response times must be real numbers in input T.') from exc
    if times.ndim!=1 or not len(times) or not np.all(np.isfinite(times)) or np.any(times<0) or np.any(np.diff(times)<=0):
        raise AnalysisError('Initial response times must be finite, nonnegative and strictly increasing in input T.')
    return times


def projected_response(space, ar, lift, dual, cr, cf, requested, times, frequencies, shift):
    """Compare a mass-projected initial condition with the complete finite ODE.

cf maps full finite coordinates to physical outputs, including their state
derivatives: cf=C Z+Q Z G. This automatically retains the initial-value boundary
term in acceleration spectra; C X+Q sX alone would be incorrect.
"""
    initial,rate,checks=space.complete(requested)
    full0=space.lift.T@initial
    modal0=dual@space.m@initial
    represented=lift@modal0;omitted=initial-represented
    known=initial[space.indices];lost=omitted[space.indices]
    amplitude=float(np.max(abs(known)))
    report=dict(converged=True,consistency=checks,resolved_state=initial.tolist(),resolved_rate=rate.tolist(),
        reduced_initial_state=modal0.tolist(),represented_state=represented.tolist(),omitted_state=omitted.tolist(),
        projection=dict(relative_dynamic_norm=float(np.linalg.norm(lost/amplitude)/np.linalg.norm(known/amplitude)),
            maximum_scaled_dynamic_error=float(np.max(abs(lost))),
            full_initial_output=(cf@full0).tolist(),reduced_initial_output=(cr@modal0).tolist(),
            interpretation='Mass-dual mode truncation of a constraint-consistent physical state. Error uses scaled dynamic coordinates, not physical energy.'),
        time_samples=[],samples=[])
    for t in times:
        row=dict(time=float(t))
        try:
            with warnings.catch_warnings(),np.errstate(over='raise',invalid='raise',divide='raise'):
                warnings.simplefilter('error',RuntimeWarning)
                fq=expm(space.generator*t)@full0;rq=expm(ar*t)@modal0
                full,reduced=cf@fq,cr@rq
                if not all(np.all(np.isfinite(x)) for x in (fq,rq,full,reduced)):
                    raise FloatingPointError('nonfinite response')
            row.update(converged=True,full=full.tolist(),reduced=reduced.tolist(),
                absolute_error=abs(full-reduced).tolist(),reduced_state=rq.tolist())
        except (FloatingPointError,RuntimeWarning):
            row.update(converged=False,error='Initial response overflows at this time; shorten the range or inspect unstable modes.')
        report['time_samples'].append(row)
    try: shift=space.transform_shift(shift)
    except AnalysisError as exc:
        report['spectrum_error']=str(exc)
        return report
    report['laplace_shift']=shift
    for w in frequencies:
        row=dict(omega=float(w),shift=shift)
        try:
            fq,diagnostic=harmonic_solve(space.generator,np.eye(len(full0)),full0,w,shift=shift)
            rq,_=harmonic_solve(ar,np.eye(len(modal0)),modal0,w,shift=shift)
            state=space.lift@fq;state_rate=(shift+1j*w)*state-initial
            residual=(space.m@state_rate-space.a@state)/space.rows
            scale=max(np.max(abs(space.m@state_rate/space.rows)),np.max(abs(space.a@state/space.rows)),np.max(abs(initial)),1e-30)
            error=float(np.max(abs(residual))/scale)
            if error>1e-7:raise AnalysisError('Initial transform fails the original full descriptor equations.')
            full,reduced=cf@fq,cr@rq
            row.update(converged=True,full=complex_data(full),reduced=complex_data(reduced),
                absolute_error=abs(full-reduced).tolist(),full_equation_scaled_residual=error,
                full_diagnostics=diagnostic)
        except (HarmonicPole,AnalysisError) as exc:row.update(converged=False,error=str(exc))
        report['samples'].append(row)
    return report


def initial_comparisons(system,a,m,ar,lift,dual,cr,measured,specifications,times,frequencies,shift,step,tolerance,progress=None):
    """Prepare physical profiles and expose each invalid profile independently."""
    if not isinstance(specifications,(list,tuple)):
        raise AnalysisError('ROM initial_inputs must be a list of physical initial profiles.')
    if not specifications:return [],None
    times=time_grid(times)
    space=ConsistentSubspace(a,m,system.dynamic_indices,system.W,tolerance)
    cf=np.column_stack([measured.tangent(space.lift[:,j],space.lift@space.generator[:,j],step)
                        for j in range(space.lift.shape[1])])
    rows=[];names=set()
    for i,spec in enumerate(specifications):
        row=dict(name=spec.get('name',f'initial_{i+1}') if isinstance(spec,dict) else f'initial_{i+1}',converged=False)
        try:
            if not isinstance(spec,dict) or spec.get('kind')!='initial':
                raise AnalysisError('ROM initial profiles require kind=initial, name and a physical state.')
            profile=InitialInput(system,spec,i)
            if profile.report['name'] in names:raise AnalysisError('ROM initial profile names must be distinct.')
            names.add(profile.report['name']);row.update(deepcopy(profile.report))
            row.update(projected_response(space,ar,lift,dual,cr,cf,profile.requested,times,frequencies,shift))
        except AnalysisError as exc:row['error']=str(exc)
        rows.append(row)
        if progress is not None:progress('initial response',i+1,len(specifications))
    return rows,space.report
