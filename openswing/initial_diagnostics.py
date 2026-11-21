"""Finite alternative-state witnesses for nonlinear cold initialization.

This is a bounded discovery diagnostic, not a nonsmooth uniqueness theorem.
The original derivative array and physical residual decide whether a proposed
alternative is admissible. Auxiliary Taylor freedom alone is never a witness.
"""
import numpy as np
from scipy.linalg import svd
from .aero import AnalysisError


class UnresolvedInitialControllerAuthority(AnalysisError):
    """Several resolved physical initial completions satisfy the original checks."""


def controller_initial_alternatives(rows, state_indices, physical_residual, tolerance):
    """Own controller output rows/states and an ordinary physical anchor lookup.

    Row omission generates proposals only; every original row is enforced for
    their acceptance. ``physical_residual`` must use the caller's original
    forcing and IC ownership, not a replacement input or projected state.
    """
    rows=tuple(rows);state_indices=tuple(state_indices);tolerance=float(tolerance)
    for indices in (rows,state_indices):
        if not indices or len(set(indices))!=len(indices) or any(isinstance(i,bool) or not isinstance(i,(int,np.integer)) or i<0 for i in indices):
            raise ValueError('Initial controller indices must be distinct nonnegative integers.')
    if len(rows)!=len(state_indices) or not callable(physical_residual):
        raise ValueError('Initial controller output rows, states and physical residual must be owned explicitly.')
    if not np.isfinite(tolerance) or tolerance<=0:
        raise ValueError('The original initial residual tolerance must be positive.')

    def diagnose(*,parameters,jacobian,required_indices,free_state_indices,
                 inspect,restore,measure,scales,size,rank_tolerance):
        p=np.asarray(parameters).copy();jac=np.asarray(jacobian)
        required=np.asarray(required_indices,dtype=int);free=np.asarray(free_state_indices,dtype=int)
        if jac.shape!=(3*size,len(p)) or max(rows)>=size or any(np.count_nonzero(free==i)!=1 for i in state_indices):
            raise ValueError('Initial controller ownership does not match the derivative-array parameter chart.')
        report=dict(method='finite original-residual initial alternatives',directions=0,
            tested_profiles=0,domain_skips=0,trial_checks=0,direction_limit=8,
            probe_step=2.5e-5,probe_ratios=[1.,2.,4.],witness=False,
            limitation='No witness is not a uniqueness certificate; finite straight probes may miss narrow, curved or other branches.')
        if not len(required):return report
        parameter_scale=np.maximum(1.,abs(p[required]))
        omitted=np.concatenate([np.asarray(rows)+k*size for k in range(3)])
        retained=np.delete(jac,omitted,axis=0)
        retained=retained/np.maximum(1.,np.linalg.norm(retained,axis=1))[:,None]
        _,singular,vh=svd(retained,full_matrices=retained.shape[0]<retained.shape[1])
        rank=int(np.sum(singular>rank_tolerance*singular[0])) if len(singular) and singular[0]>0 else 0
        null=vh[rank:].T
        if not null.shape[1]:return report
        physical=null[required]/parameter_scale[:,None]
        _,resolved,modes=svd(physical,full_matrices=False)
        proposals=[null@null[int(np.flatnonzero(free==index)[0])] for index in state_indices]
        if len(resolved) and resolved[0]>0:
            proposals.extend(null@mode for value,mode in zip(resolved,modes) if value>rank_tolerance*resolved[0])
        directions=[];physical_directions=[]
        for proposal in proposals:
            if not np.all(np.isfinite(proposal)):continue
            projection=proposal[required]/parameter_scale
            magnitude=float(np.max(abs(projection)))
            if not np.isfinite(magnitude) or magnitude<=1e-10:continue
            direction=proposal/magnitude;projection=projection/magnitude
            if not np.all(np.isfinite(direction)) or not np.all(np.isfinite(projection)):continue
            unit=projection/np.linalg.norm(projection)
            if not np.all(np.isfinite(unit)):continue
            if any(abs(float(unit@previous))>1-1e-8 for previous in physical_directions):continue
            directions.append(direction);physical_directions.append(unit)
            if len(directions)==report['direction_limit']:break
        report['directions']=len(directions)
        report['row_relaxed_rank']=rank;report['proposal_nullity']=null.shape[1]
        try:
            for direction in directions:
                predicted=measure(jac@direction,scales);h=report['probe_step']
                if not np.isfinite(predicted) or predicted*h<=32*tolerance:continue
                for sign in (-1.,1.):
                    report['tested_profiles']+=1
                    steps=sign*h*np.array(report['probe_ratios']);trials=[]
                    try:
                        for step in steps:
                            report['trial_checks']+=1
                            trial=inspect(p+step*direction,physical_residual)
                            if not trial['accepted']:break
                            trials.append(trial)
                    except (AnalysisError,ValueError,FloatingPointError):
                        report['domain_skips']+=1
                        continue
                    if len(trials)!=3:continue
                    profiles=[trial['scaled_array_profile'] for trial in trials]
                    if any(not np.all(np.isfinite(profile)) for profile in profiles):continue
                    slopes=[float(np.max(abs((b-a)/(v-u)))) for a,b,u,v in zip(profiles,profiles[1:],steps,steps[1:])]
                    if not np.all(np.isfinite(slopes)):continue
                    if max(slopes)>1e-6*predicted:continue
                    separations=[float(np.max(abs((trial['required_values']-p[required])/parameter_scale))) for trial in trials]
                    if not np.all(np.isfinite(separations)):continue
                    if any(distance<.9*abs(step) for distance,step in zip(separations,steps)):continue
                    witness=dict(kind='nearby_accepted_initial_completions',steps=steps.tolist(),
                        required_indices=required.tolist(),controller_rows=list(rows),controller_state_indices=list(state_indices),
                        base_parameters=p.tolist(),parameter_direction=direction.tolist(),
                        required_separations=separations,centered_first_change=predicted*h,
                        centered_slope=predicted,profile_slopes=slopes,tolerance=tolerance,
                        alternatives=trials,
                        limitation='Finite original-equation witnesses at the recorded probe scale; not proof of a continuum or a general nonsmooth uniqueness certificate.')
                    error=UnresolvedInitialControllerAuthority('Nonsmooth controller has unresolved nearby accepted initial states in the original continuous residual; cold actuator authority is not certified.')
                    error.accepted_initial_witness=witness
                    raise error
        finally:
            # Trial residuals own mutable mechanics/controller caches. Both the
            # stencil and ordinary physical anchor must finish at the accepted p.
            restore(p,physical_residual)
        return report
    return diagnose
