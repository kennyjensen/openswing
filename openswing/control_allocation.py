"""Weighted control trim with hard coupled equilibrium/operating equations.

ASWING v5.86 documents a least-squares option for redundant controls, but does
not publish its weight normalization. Here J=1/2 sum w_i (u_i-u_preferred_i)^2
over every solved flap/engine variable. Numerical scaling does not change J's
minimizer. Physical equations are equality constraints, never soft penalties.
"""
from copy import copy
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import null_space
from .aero import AnalysisError


def allocate(residual, initial, operating, start, *, tolerance, continuation_steps, warm=False):
    slots=operating.minimum_indices
    if not slots:raise AnalysisError('Control allocation needs at least one minimum-control slot.')
    selected=[(i,c) for i,c in enumerate(operating.constraints) if c.variable.startswith(('control.','power.'))]
    indices=np.array([start+i for i,c in selected]);weights=np.array([c.weight for i,c in selected])
    preferred=np.array([c.preferred for i,c in selected]);base=np.array([operating.base[c.variable] for i,c in selected])
    scales=np.array([operating.scale[c.variable] for i,c in selected])
    # Unit Hessian in weighted actuator coordinates. Common weight scaling
    # leaves the optimizer invariant; the report retains the physical weights.
    root=np.sqrt(weights/np.max(weights));mapping=np.ones(len(initial));mapping[indices]=1/(root*scales)
    if not np.all(np.isfinite(mapping)):raise AnalysisError('Control weights are too ill-conditioned for allocation.')
    y=initial/mapping;offset=root*(base-preferred)
    keep=np.ones(len(initial),dtype=bool);keep[start+np.array(slots)]=False
    def objective(v):return .5*float(np.sum((v[indices]+offset)**2))
    def gradient(v):
        g=np.zeros(len(v));g[indices]=v[indices]+offset;return g
    evaluations=0
    def equations(v,factor=1.):
        nonlocal evaluations
        evaluations+=1
        out=np.asarray(residual(v*mapping,factor))[keep]
        if not np.all(np.isfinite(out)):raise AnalysisError('Nonfinite physical residual during control allocation.')
        return out
    def tangent(v,factor=1.):
        columns=[]
        for j in range(len(v)):
            h=2e-6*max(1.,abs(v[j]));a=v.copy();b=v.copy();a[j]+=h;b[j]-=h
            columns.append((equations(a,factor)-equations(b,factor))/(2*h))
        return np.column_stack(columns)
    # Record target continuation origins before the first trial changes them.
    equations(y)
    reached,step,steps,iterations=0.,1. if warm else 1./continuation_steps,0,0
    while reached<1-1e-12:
        fraction=min(1.,reached+step)
        result=minimize(objective,y,jac=gradient,method='SLSQP',
            constraints=[dict(type='eq',fun=lambda v:equations(v,fraction),jac=lambda v:tangent(v,fraction))],
            options=dict(ftol=min(1e-11,tolerance*.01),maxiter=100))
        error=float(np.max(abs(equations(result.x,fraction))))
        if not result.success or error>tolerance or not np.all(np.isfinite(result.x)):
            step*=.5
            if step<1/256:
                raise AnalysisError(f'Weighted control trim failed at target fraction {fraction:.4f}: {result.message}; physical residual {error:.3g}.')
            continue
        y=result.x;reached=fraction;steps+=1;iterations+=int(result.nit)
        step=min(1. if warm else 1./continuation_steps,step*1.5)
    jac=tangent(y);norms=np.linalg.norm(jac,axis=0)
    singular=np.linalg.svd(jac/np.maximum(norms,1e-30),compute_uv=False)
    reciprocal=float(singular[-1]/singular[0])
    if reciprocal<1e-10:raise AnalysisError('Weighted trim equality constraints are dependent or leave an unrestrained mechanism.')
    basis=null_space(jac,rcond=1e-10)
    if basis.shape[1]!=len(slots):raise AnalysisError('Weighted trim tangent has unresolved numerical rank.')
    _,control_singular,control_right=np.linalg.svd(basis[indices],full_matrices=False)
    if control_singular[-1]<1e-10*max(control_singular[0],1e-30):
        raise AnalysisError('Weighted trim leaves a free direction that control effort cannot determine.')
    # Normalize feasible directions by their weighted control motion, rather
    # than by an arbitrary mixture of structural state and actuator scales.
    basis=(basis@control_right.T)/control_singular
    grad=gradient(y);multipliers=np.linalg.lstsq(jac.T,-grad,rcond=1e-12)[0]
    stationarity=float(np.max(abs(basis.T@grad),initial=0.)/max(1.,np.linalg.norm(grad)))
    if stationarity>max(2e-6,20*tolerance):raise AnalysisError(f'Weighted trim did not reach a stationary control allocation: {stationarity:.3g}.')
    # Reduced Lagrangian Hessian, including nonlinear equilibrium curvature.
    # A positive objective Hessian alone would not certify a constrained minimum.
    zero=equations(y)
    increments=2e-4/np.max(abs(basis)/np.maximum(1.,abs(y))[:,None],axis=0)
    hessian=np.empty((len(slots),len(slots)))
    for i in range(len(slots)):
        hi=increments[i];a=hi*basis[:,i]
        hessian[i,i]=np.sum(basis[indices,i]**2)+float(multipliers@(equations(y+a)-2*zero+equations(y-a)))/hi**2
        for j in range(i):
            hj=increments[j];b=hj*basis[:,j]
            hessian[i,j]=hessian[j,i]=float(basis[indices,i]@basis[indices,j])+float(multipliers@(equations(y+a+b)-equations(y+a-b)-equations(y-a+b)+equations(y-a-b)))/(4*hi*hj)
    curvature=np.linalg.eigvalsh(hessian);curvature_scale=max(1.,float(np.max(abs(curvature))))
    if curvature[0]<-2e-5*curvature_scale:raise AnalysisError('Weighted trim stationary point is not a local control-effort minimum.')
    if curvature[0]<=2e-7*curvature_scale:raise AnalysisError('Weighted trim minimum is not numerically isolated; change constraints or control weights.')
    physical=base+scales*(y*mapping)[indices]
    return y*mapping,steps,dict(objective=.5*float(np.sum(weights*(physical-preferred)**2)),
        definition='Minimize 1/2 sum(weight * (setting - preferred)^2) over every solved flap/engine, subject to all physical equilibrium and hard operating equations.',
        controls=[dict(variable=c.variable,weight=float(c.weight),preferred=float(c.preferred),actual=float(value)) for (i,c),value in zip(selected,physical)],
        free_directions=len(slots),normalized_stationarity=stationarity,
        equality_residual=float(np.max(abs(equations(y)))),equality_reciprocal_condition=reciprocal,
        reduced_curvatures=curvature.tolist(),curvature_coordinates='Unit weighted control motion in the feasible tangent; weights normalized by their maximum.',iterations=iterations,residual_evaluations=evaluations,
        scope='Steady control allocation; trim constraints are released for dynamic and derivative responses.',
        limitations=['A checked local minimum on the selected nonlinear branch, not proof of a unique global optimum or aircraft stability.',
                     'Weights multiply squared file control settings; exact ASWING least-squares weight conventions are unverified.',
                     'Actuator bounds and saturation are not imposed.'])


def equilibrate_allocation(n,tolerance,continuation_steps,initial_state,options):
    from .operating import OperatingSystem
    from .network import equilibrate
    if initial_state is None:
        seed=copy(n);seed.operating=OperatingSystem(n.model,n.condition,n.motion,(),n.L,n.F);seed.size=n.operating_start
        x,seed_steps=equilibrate(seed,tolerance,continuation_steps,**options)
        initial=np.r_[x,np.zeros(n.operating.count)]
    else:
        from .equilibrium_state import restore
        initial=restore(n,initial_state);seed_steps=0
    def residual(x,factor):return n.residual(x,operating_factor=factor,**options)
    x,steps,report=allocate(residual,initial,n.operating,n.operating_start,tolerance=tolerance,
        continuation_steps=continuation_steps,warm=initial_state is not None)
    n.control_allocation=report
    if n.operating.custom:
        from .custom_constraints import check_custom_tangent
        n.custom_trim=check_custom_tangent(n.operating,lambda v:residual(v,1.),x,n.operating_start,rank=False)
    n.equilibrium_diagnostics=dict(initialization='saved physical equilibrium' if initial_state is not None else 'prescribed-control equilibrium and weighted trim',
        seed_continuation_steps=seed_steps,target_continuation_steps=steps,control_allocation=report)
    return x,steps
