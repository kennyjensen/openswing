"""Constraint-consistent nonlinear initial states in the physical time chart.

The residual and its first two time derivatives enforce hidden velocity and
acceleration constraints. Higher Taylor coefficients are auxiliary unknowns;
only the initial state and its physical dynamic rates must be unique.
"""
import numpy as np
from .vector_ops import cross3
from collections.abc import Mapping
from numbers import Real
from scipy.linalg import svd
from .aero import AnalysisError
from .local_motion import left_jacobian,mv,rotation_vector


def consistent_initial(residual,initial,dynamic_indices,rate,*,time=0.,time_scale=1.,
                       difference_step=.01,tolerance=1e-8,rank_tolerance=1e-7,progress=None,
                       fixed_state_indices=None,fixed_rates=None,accepted_initial_diagnostic=None):
    """Hold every prescribed physical coordinate fixed and complete the DAE.

``residual(x,xdot,t)`` uses physical input time. Its state coordinates must be
scaled. A cubic local trajectory supplies the derivative array R,R',R'';
sixth-order symmetric stencils are repeated at half spacing. A rank-aware
Gauss-Newton solve leaves auxiliary undetermined derivatives free, and checks
that their nullspace cannot change the required state or dynamic rates.

``dynamic_indices`` always identifies the differential coordinates, including
their cubic Taylor support. By default all their initial values are held fixed.
``fixed_state_indices`` may select a subset to hold; every other initial state
component is solved. ``fixed_rates`` maps differential indices to prescribed
initial physical ``xdot`` values (per input time). These values fix only the
first Taylor coefficients at the anchor, never the higher derivatives. All
free initial states and free physical differential rates must be unique.
The caller owns this selection, including feedback state initial conditions.
An optional accepted-initial diagnostic can inspect the complete parameter
chart after the existing checks. Its proposals must preserve this ownership;
it cannot change the accepted state or the original residual tolerance.
"""
    x0=np.asarray(initial,dtype=float).copy();rate=np.asarray(rate,dtype=float)
    n=len(x0);dynamic=np.asarray(dynamic_indices,dtype=int);algebraic=np.setdiff1d(np.arange(n),dynamic);na=len(algebraic)
    if x0.ndim!=1 or rate.shape!=x0.shape or not np.all(np.isfinite(x0)) or not np.all(np.isfinite(rate)):
        raise AnalysisError('Nonlinear initialization needs finite state and rate guesses.')
    if len(set(dynamic))!=len(dynamic) or np.any(dynamic<0) or np.any(dynamic>=n):
        raise AnalysisError('Nonlinear initial dynamic coordinates are invalid.')
    if not np.isfinite(time_scale) or time_scale<=0 or not np.isfinite(time):
        raise AnalysisError('Nonlinear initial time and time scale must be finite, with positive scale.')
    if not np.isfinite(difference_step) or not .001<=difference_step<=.03:
        raise AnalysisError('Initial derivative spacing must be between .001 and .03 in scaled time.')
    if not np.isfinite(tolerance) or not 1e-10<=tolerance<=1e-6:
        raise AnalysisError('Initial consistency tolerance must be between 1e-10 and 1e-6.')
    if not np.isfinite(rank_tolerance) or not 1e-9<=rank_tolerance<=1e-5:
        raise AnalysisError('Initial derivative-array rank tolerance must be between 1e-9 and 1e-5.')
    generalized=fixed_state_indices is not None or fixed_rates is not None
    held=dynamic;free_state=algebraic;free_rate=np.arange(n);prescribed_rates={}
    if generalized:
        if fixed_state_indices is not None:
            raw=np.asarray(fixed_state_indices,dtype=object)
            if raw.ndim!=1 or any(isinstance(i,(bool,np.bool_)) or not isinstance(i,(int,np.integer)) for i in raw):
                raise AnalysisError('Fixed initial state indices must be a one-dimensional sequence of integers.')
            if len(set(raw))!=len(raw) or not set(raw).issubset(set(dynamic)):
                raise AnalysisError('Fixed initial state indices must be a unique subset of dynamic coordinates.')
            held=np.asarray(raw,dtype=int)
        if fixed_rates is not None:
            if not isinstance(fixed_rates,Mapping):
                raise AnalysisError('Fixed initial rates must map dynamic coordinate indices to finite physical rates.')
            for index,value in fixed_rates.items():
                if isinstance(index,(bool,np.bool_)) or not isinstance(index,(int,np.integer)) or index not in dynamic:
                    raise AnalysisError('Fixed initial rate indices must be dynamic coordinate integers.')
                if isinstance(value,(bool,np.bool_)) or not isinstance(value,Real) or not np.isfinite(value):
                    raise AnalysisError('Fixed initial rates must be finite numeric physical rates.')
                prescribed_rates[int(index)]=float(value)
        free_state=np.setdiff1d(np.arange(n),held);na=len(free_state)
        free_rate=np.setdiff1d(np.arange(n),list(prescribed_rates))
        p=np.r_[x0[free_state],rate[free_rate]/time_scale,np.zeros(n),np.zeros(len(dynamic))]
        targets=np.r_[np.arange(na),na+np.flatnonzero(np.isin(free_rate,dynamic))]
    else:
        # Keep the established default parameter indexing and numerical path.
        p=np.r_[x0[algebraic],rate/time_scale,np.zeros(n),np.zeros(len(dynamic))]
        targets=np.r_[np.arange(na),na+dynamic]
    nr=len(free_rate);history=[];previous=None;evaluations=0;diagnostic_scales=[]

    def unpack(p):
        x=x0.copy();x[free_state]=p[:na]
        if generalized:
            first=np.zeros(n);first[free_rate]=p[na:na+nr]
            for index,value in prescribed_rates.items():first[index]=value/time_scale
        else:first=p[na:na+n]
        second=p[na+nr:na+nr+n];third=np.zeros(n);third[dynamic]=p[na+nr+n:]
        return x,first,second,third

    for refinement,h in enumerate((difference_step,difference_step/2)):
        def path(p,tau):
            nonlocal evaluations
            x,first,second,third=unpack(p)
            evaluations+=1
            value=np.asarray(residual(x+tau*first+.5*tau*tau*second+tau**3/6*third,
                time_scale*(first+tau*second+.5*tau*tau*third),time+tau/time_scale))
            if value.shape!=(n,) or not np.all(np.isfinite(value)):
                raise AnalysisError('Nonfinite or malformed nonlinear initial trajectory residual.')
            return value

        def array_at(p,spacing):
            zero=path(p,0);plus,minus,plus2,minus2,plus3,minus3=(path(p,k*spacing) for k in (1,-1,2,-2,3,-3))
            return np.r_[zero,(45*(plus-minus)-9*(plus2-minus2)+(plus3-minus3))/(60*spacing),
                         (270*(plus+minus)-27*(plus2+minus2)+2*(plus3+minus3)-490*zero)/(180*spacing*spacing)]

        def array(p):return array_at(p,h)

        def factor(p):
            jac=np.empty((3*n,len(p)))
            for j in range(len(p)):
                delta=np.zeros(len(p));dh=1e-4*max(1.,abs(p[j]));delta[j]=dh
                jac[:,j]=(array(p+delta)-array(p-delta))/(2*dh)
                if progress is not None:progress('initializing',j+1,len(p))
            rows=np.ones(len(jac));columns=np.ones(len(p))
            for _ in range(6):
                norms=np.linalg.norm(jac/rows[:,None]*columns,axis=1)
                # Prescribed holonomic constraints have zero tangents. Never
                # amplify their floating-point residual into the merit function.
                rows*=np.where(norms>1e-12,norms,1.)
                norms=np.linalg.norm(jac/rows[:,None]*columns,axis=0)
                columns/=np.where(norms>1e-12,norms,1.)
                columns=np.clip(columns,1e-4,1e4)
            u,singular,vh=svd(jac/rows[:,None]*columns,full_matrices=False)
            rank=int(np.sum(singular>rank_tolerance*singular[0]))
            return rows,columns,u,singular,vh,rank,jac

        factors=None;age=0;iterations=0;builds=0
        def measure(value,rows):
            return float(max(np.max(abs(value[:n])),np.max(abs(value[n:]/rows[n:]))))
        for iteration in range(12):
            value=array(p);error=float(np.max(abs(value)))
            if not np.isfinite(error):raise AnalysisError('Nonfinite nonlinear initial derivative array.')
            if error<=tolerance:break
            if factors is None:
                factors=factor(p);builds+=1;age=0
            rows,columns,u,singular,vh,rank,_=factors
            error=measure(value,rows)
            if error<=tolerance:break
            update=-columns*((vh[:rank].T/singular[:rank])@(u[:,:rank].T@(value/rows)))
            norm=np.linalg.norm(value/rows);accepted=False
            for power in range(10):
                trial=p+update/2**power
                try:trial_value=array(trial)
                except (AnalysisError,ValueError,FloatingPointError):continue
                if np.all(np.isfinite(trial_value)) and np.linalg.norm(trial_value/rows)<norm:
                    p=trial;accepted=True;age+=1;iterations+=1
                    if measure(trial_value,rows)>.2*error or age>=4:factors=None
                    break
            if not accepted:
                if age:factors=None;continue
                break
        # Certify the required variables at the accepted solution, independently
        # of any tangent reused during the nonlinear iterations.
        if factors is not None and age==0:
            rows,columns,u,singular,vh,rank,jac=factors
        else:
            rows,columns,u,singular,vh,rank,jac=factor(p);builds+=1
        value=array(p);error=measure(value,rows)
        if error>tolerance:
            raise AnalysisError(f'Physical initial profile does not resolve the nonlinear state/velocity/acceleration constraints (scaled derivative residual {error:.3g}). Refine the derivative spacing or supply compatible physical fields; no profile is projected silently.')
        # Certify in the original scaled coordinates, independently of column
        # balancing used for the Newton update. Scaling near-zero auxiliary
        # columns can otherwise corrupt a transformed nullspace basis.
        # Freeing initial states can make this Jacobian wide. Thin SVD then
        # omits exact right-nullspace vectors and can falsely certify uniqueness.
        _,singular,vh=svd(jac/np.maximum(np.linalg.norm(jac,axis=1),1.)[:,None],
            full_matrices=generalized and len(p)>3*n)
        rank=int(np.sum(singular>rank_tolerance*singular[0]))
        defect=float(np.linalg.norm(vh[rank:,targets],2)) if rank<len(p) and len(targets) else 0.
        if rank==0 and (not generalized or len(targets)):
            raise AnalysisError('Nonlinear initial state and dynamic rates are not uniquely resolved by the derivative array.')
        gap=float(singular[rank-1]/max(singular[rank],np.finfo(float).tiny)) if rank<len(singular) else None
        if rank==0:gap=None
        if defect>1e-6 or (gap is not None and gap<100):
            raise AnalysisError(f'Nonlinear initial state or dynamic rates are not uniquely resolved by the derivative array (null defect {defect:.3g}, rank {rank}/{len(p)}, singular-value gap {gap}). Refine rank/spacing or inspect higher-index, weak-inertia or nonsmooth constraints.')
        change=None if previous is None else float(np.max(abs(p[targets]-previous)/np.maximum(1.,abs(p[targets])),initial=0.))
        if change is not None and change>max(20*tolerance,2e-6):
            raise AnalysisError(f'Nonlinear initialization does not converge with derivative spacing (scaled state/rate change {change:.3g}). Refine the spacing; this initial state is not accepted.')
        # A centered array can average different left/right constraint branches.
        # Check both derivatives on the same composite physical trajectory.
        points=np.arange(7,dtype=float)
        weights=np.linalg.solve(points[None,:]**points[:,None],np.eye(7)[:,1:3]*np.array([1.,2.]))
        side_error=0.
        for side in (-1,1):
            values=np.array([path(p,side*k*h/4) for k in points])
            derivatives=weights.T@values/np.array([side*h/4,(h/4)**2])[:,None]
            side_error=max(side_error,float(np.max(abs(derivatives.ravel()-value[n:])/rows[n:])))
        if side_error>max(50*tolerance,1e-6):
            raise AnalysisError(f'Initial derivative array has inconsistent one-sided derivatives ({side_error:.3g}). Move away from a switching boundary or refine the spacing.')
        previous=p[targets].copy()
        history.append(dict(scaled_time_spacing=h,derivative_residual=error,unbalanced_derivative_residual=float(np.max(abs(value[n:]))),original_residual=float(np.max(abs(value[:n]))),
            one_sided_derivative_defect=side_error,
            iterations=iterations,jacobian_builds=builds,rank=rank,unknowns=len(p),required_nullspace_defect=defect,
            singular_value_gap=gap,smallest_resolved_singular_value=float(singular[rank-1]) if rank else None,
            largest_discarded_singular_value=float(singular[rank]) if rank<len(singular) else 0.,refinement_change=change))
        if accepted_initial_diagnostic is not None:diagnostic_scales.append((h,rows.copy()))
    diagnostic_report=None
    if accepted_initial_diagnostic is not None:
        def physical_values(parameters):
            state,first,*_=unpack(parameters);physical_rate=first*time_scale
            for index,value in prescribed_rates.items():physical_rate[index]=value
            return state,physical_rate

        def restore(parameters,physical_residual):
            path(parameters,0)
            state,physical_rate=physical_values(parameters)
            if not np.all(np.isfinite(state)) or not np.all(np.isfinite(physical_rate)):
                raise AnalysisError('Nonfinite diagnostic initial state or physical rate.')
            physical_residual(state,physical_rate,time)

        def inspect(parameters,physical_residual):
            parameters=np.asarray(parameters,dtype=float)
            if parameters.shape!=p.shape or not np.all(np.isfinite(parameters)):
                raise AnalysisError('Nonfinite or malformed diagnostic initial parameters.')
            state,physical_rate=physical_values(parameters)
            if not np.all(np.isfinite(state)) or not np.all(np.isfinite(physical_rate)):
                raise AnalysisError('Nonfinite diagnostic initial state or physical rate.')
            if not np.array_equal(state[held],x0[held]) or any(physical_rate[i]!=v for i,v in prescribed_rates.items()):
                raise ValueError('Initial diagnostic changed a prescribed coordinate or physical rate.')
            anchor=path(parameters,0).copy()
            physical=np.asarray(physical_residual(state,physical_rate,time)).copy()
            if physical.shape!=(n,) or not np.all(np.isfinite(physical)):
                raise AnalysisError('Nonfinite or malformed diagnostic physical anchor residual.')
            trial=dict(accepted=False,state=state.copy(),physical_rate=physical_rate.copy(),
                required_values=parameters[targets].copy(),original_anchor_residual=anchor,
                physical_anchor_residual=physical,held_coordinates_unchanged=True,prescribed_rates_unchanged=True,
                refinements=[])
            if max(np.max(abs(anchor)),np.max(abs(physical)))>tolerance:return trial
            profiles=[]
            for spacing,accepted_rows in diagnostic_scales:
                values=array_at(parameters,spacing).copy()
                if not np.all(np.isfinite(values)):
                    raise AnalysisError('Nonfinite diagnostic initial derivative array.')
                error=measure(values,accepted_rows)
                if not np.isfinite(error):
                    raise AnalysisError('Nonfinite diagnostic initial derivative error.')
                if error>tolerance:return trial
                side_error=0.;sides=[]
                for side in (-1,1):
                    samples=np.array([path(parameters,side*k*spacing/4) for k in points])
                    derivatives=weights.T@samples/np.array([side*spacing/4,(spacing/4)**2])[:,None]
                    if not np.all(np.isfinite(derivatives)):
                        raise AnalysisError('Nonfinite diagnostic one-sided initial derivatives.')
                    defect=float(np.max(abs(derivatives.ravel()-values[n:])/accepted_rows[n:]))
                    if not np.isfinite(defect):
                        raise AnalysisError('Nonfinite diagnostic one-sided initial error.')
                    side_error=max(side_error,defect)
                    sides.append(dict(side=side,sampled_residuals=samples.copy(),derivatives=derivatives.copy()))
                if side_error>max(50*tolerance,1e-6):return trial
                trial['refinements'].append(dict(scaled_time_spacing=spacing,derivative_residual=error,
                    one_sided_derivative_defect=side_error,full_array=values,accepted_row_scales=accepted_rows.copy(),sides=sides))
                profile=np.r_[values[:n],values[n:]/accepted_rows[n:]]
                if not np.all(np.isfinite(profile)):
                    raise AnalysisError('Nonfinite scaled diagnostic initial profile.')
                profiles.append(profile)
            trial.update(accepted=True,scaled_array_profile=np.concatenate(profiles))
            return trial

        diagnostic_report=accepted_initial_diagnostic(parameters=p.copy(),jacobian=jac.copy(),
            required_indices=targets.copy(),free_state_indices=free_state.copy(),inspect=inspect,
            restore=restore,measure=measure,scales=rows.copy(),size=n,rank_tolerance=rank_tolerance)
    state,first,*_=unpack(p)
    physical_rate=first*time_scale
    for index,value in prescribed_rates.items():physical_rate[index]=value
    report=dict(method='nonlinear derivative array through second time derivative',
        difference_step=difference_step,difference_order=6,jacobian_step=1e-4,
        newton_column_scale_bounds=[1e-4,1e4],rank_tolerance=rank_tolerance,tolerance=tolerance,refinements=history,
        residual_evaluations=evaluations,prescribed_coordinate_error=float(np.max(abs(state[held]-x0[held]),initial=0.)),
        interpretation='Every prescribed dynamic coordinate is held fixed in scaled coordinates. The original residual uses the time tolerance; differentiated residuals use tangent row scaling. Algebraic state and physical dynamic rates pass local uniqueness, one-sided and spacing-refinement checks. Auxiliary higher derivatives need not be unique. Finite differences give local numerical evidence, not a proof for arbitrary higher-index or nonsmooth systems.')
    if generalized:
        report.update(fixed_state_indices=held.tolist(),fixed_rates=prescribed_rates.copy(),
            free_state_indices=free_state.tolist(),free_dynamic_rate_indices=[int(i) for i in free_rate if i in dynamic],
            prescribed_rate_error=float(max((abs(physical_rate[i]-v) for i,v in prescribed_rates.items()),default=0.)),
            interpretation='Only selected initial dynamic coordinates and physical rates are held fixed. All free initial state components and free physical dynamic rates pass the original residual, complete right-nullspace, one-sided and spacing-refinement checks. Higher Taylor derivatives retain their original support and need not be unique. Finite differences give local numerical evidence, not a proof for arbitrary higher-index or nonsmooth systems.')
    if diagnostic_report is not None:report['accepted_initial_diagnostic']=diagnostic_report
    return state,physical_rate,report


class InitialSystem:
    """Continuous common residual in the time integrator's SO(3) charts."""
    def __init__(self,system,seed,frame,*,apply_forcing=False,history_context=None):
        self.system=system;self.network=system.network;self.seed=seed;self.frame=frame;self.feedback=system.feedback
        self.history_context=history_context
        self.apply_forcing=apply_forcing
        n=self.network;self.L,self.V,self.W=n.L,system.V,system.W
        self.velocity_start=n.size;self.frame_start=system.frame_start;self.feedback_start=system.feedback_start;self.size=system.size
        x=seed.x.copy();x[:6*n.nn].reshape(n.nn,6)[:,3:]=0.
        self.base=np.r_[x,(seed.u/self.V).ravel(),(seed.w/self.W).ravel(),seed.U/self.V,seed.Omega/self.W,
            seed.position/n.L,np.zeros(3),[] if self.feedback is None else seed.feedback/self.feedback.scales]
        self.dynamic_indices=np.r_[np.arange(6*n.nn),np.arange(n.gamma_start,n.operating_start),
            np.arange(self.velocity_start,self.feedback_start),[] if self.feedback is None else np.arange(self.feedback_start+self.feedback.count,self.size)].astype(int)

    def residual(self,z,rate,time,*,detail=False,side='right',_mechanical_data=None):
        n=self.network;system=self.system;f=self.feedback
        state=system.unpack(self.base+z,self.seed,time)
        udot,wdot=rate[self.velocity_start:self.frame_start].reshape(2,n.nn,3)
        options=system.options(state,self.V*udot,self.W*wdot,
            n.circulation_basis.decode(rate[n.gamma_start:n.operating_start]*n.gamma_scale),side,apply_forcing=self.apply_forcing,history_context=self.history_context)
        if n.hinges:options['hinge_charts']=self.seed.hinge_charts
        if not self.apply_forcing:state.commands=self.seed.commands.copy()
        if f is None:base=n.residual(state.x,**options,_mechanical_data=_mechanical_data)
        else:base,data=n.residual(state.x,detail=True,**options,_mechanical_data=_mechanical_data)
        _,motion,_=n.operating.apply(state.x[n.operating_start:],condition_override=options['condition_override'],motion_override=options['motion_override'])
        dot=rate[:6*n.nn].reshape(n.nn,6);angles=z[:6*n.nn].reshape(n.nn,6)[:,3:]
        Ud,Od,pd,rd=rate[self.frame_start:self.feedback_start].reshape(4,3)
        result=np.r_[base,((n.L*dot[:,:3]-state.u)/self.V).ravel(),
            ((mv(left_jacobian(angles),dot[:,3:])-state.w)/self.W).ravel(),
            (self.V*Ud+cross3(state.Omega,state.U)-motion.at(np.zeros(3),n.model.reference[2]))/system.A,
            (self.W*Od-motion.angular_acceleration)/self.W**2,(n.L*pd-state.orientation@state.U)/self.V,
            (left_jacobian(-z[self.frame_start+9:self.feedback_start])@rd-state.Omega)/self.W]
        if f is not None:
            control,state.feedback_report=f.evaluate(state,data,rate[self.feedback_start:]*f.scales)
            result=np.r_[result,control]
        return (result,state,options) if detail else result

    def profile(self,specification):
        from .initial_response import dynamic_state
        from .ground import body_to_earth
        from .time_integration import attitude_angles
        z=dynamic_state(self,specification)
        if 'attitude_rad' in specification.get('frame',{}):
            desired=body_to_earth(attitude_angles(self.seed.orientation)+np.rad2deg(specification['frame']['attitude_rad']))
            z[self.frame_start+9:self.feedback_start]=rotation_vector(self.seed.orientation.T@desired)
        return z

    def rate_guess(self,z):
        _,state,options=self.residual(z,np.zeros(self.size),self.seed.time,detail=True)
        n=self.network;rate=np.zeros(self.size);kin=rate[:6*n.nn].reshape(n.nn,6)
        kin[:,:3]=state.u/n.L
        kin[:,3:]=np.linalg.solve(left_jacobian(z[:6*n.nn].reshape(n.nn,6)[:,3:]),state.w[...,None])[...,0]
        _,motion,_=n.operating.apply(state.x[n.operating_start:],condition_override=options['condition_override'],motion_override=options['motion_override'])
        rate[self.frame_start:self.feedback_start]=np.r_[(motion.at(np.zeros(3),n.model.reference[2])-cross3(state.Omega,state.U))/self.V,
            motion.angular_acceleration/self.W,state.orientation@state.U/n.L,
            np.linalg.solve(left_jacobian(-z[self.frame_start+9:self.feedback_start]),state.Omega)]
        return rate
