"""Optional temporal refinement checks of the existing implicit time methods.

Compare one full step with two half steps of the same method. Accept the
refined endpoint without extrapolation, and retain its actual BDF predecessor.
The discrepancy is a local resolution indicator, not a global error bound or
an ASWING adaptive-step convention. Algebraic loads and physical rates take
part in the check; their convergence order need not equal the ODE order.
"""
from copy import deepcopy
import numpy as np
from .aero import AnalysisError
from .local_motion import rotation_vector as log
from .operating import time_constraint_data


def settings(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value)-{'rtol', 'atol', 'minimum_step'}:
        raise AnalysisError('Time accuracy must be null or an object with rtol, atol and optional minimum_step.')
    out=dict(rtol=value.get('rtol',1e-3),atol=value.get('atol',1e-6))
    for key,number in out.items():
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not np.isfinite(number) or not (0<=number<=.1 if key=='rtol' else 0<number<=.1):
            raise AnalysisError('Time accuracy needs 0 <= rtol <= 0.1 and 0 < atol <= 0.1 in scaled physical variables.')
        out[key]=float(number)
    if 'minimum_step' in value:
        number=value['minimum_step']
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not np.isfinite(number) or number<=0:
            raise AnalysisError('Minimum accuracy-check step must be finite and positive in input time units.')
        out['minimum_step']=float(number)
    return out


def compare(system,previous,coarse,fine,coarse_options,fine_options,accuracy):
    """Maximum weighted vector/scalar discrepancy in physical quantities.

    Euclidean vector norms and relative rotations preserve coordinate covariance.
    Earth positions are relative to the common beginning of this trial; a large
    arbitrary Earth origin must not hide a trajectory error.
    """
    n=system.network;L,V,W,F=n.L,system.V,system.W,n.F
    def fields(state,options):
        _,_,force,moment,reaction,_=n.unpack(state.x)
        _,motion,operating=n.operating.apply(state.x[n.operating_start:],condition_override=options['condition_override'],motion_override=options['motion_override'])
        result={
            'node_displacement':(state.r-n.rj)/L,'node_velocity':state.u/V,'node_rotation_rate':state.w/W,
            'section_force':force/F,'section_moment':moment/(F*L),'constraint_reaction':reaction.reshape(-1,3),
            'circulation':state.gamma[:,None]/n.gamma_scale,
            'earth_position':((state.position-previous.position)/L)[None,:],
            'earth_velocity':(state.orientation@state.U/V)[None,:],
            'earth_rotation_rate':(state.orientation@state.Omega/W)[None,:],
            'local_acceleration':options['elastic_motion'][2]/system.A,
            'local_angular_acceleration':options['elastic_motion'][3]/W**2,
            'circulation_rate':options['circulation_rate'][:,None]/(n.gamma_scale*W),
            'reference_acceleration':(motion.acceleration/system.A)[None,:],
            'frame_angular_acceleration':(motion.angular_acceleration/W**2)[None,:],
        }
        if n.hinges:
            result['hinge_angle']=(np.asarray(state.hinge_charts)-np.asarray(previous.hinge_charts))[:,None]
        if system.feedback is not None:
            result['controller']= (state.feedback/system.feedback.scales)[:,None]
        if system.has_actuator_constraints:
            result['actuator_settings']=np.array([operating[c.variable]/n.operating.scale[c.variable]
                for c in n.operating.constraints if c.variable.startswith(('control.', 'power.'))])[:,None]
        return result
    a,b=fields(coarse,coarse_options),fields(fine,fine_options)
    a['node_rotation']=log(coarse.Q@np.swapaxes(previous.Q,-1,-2))
    b['node_rotation']=log(fine.Q@np.swapaxes(previous.Q,-1,-2))
    a['frame_orientation']=log(coarse.orientation@previous.orientation.T)[None,:]
    b['frame_orientation']=log(fine.orientation@previous.orientation.T)[None,:]
    rotation_error={'node_rotation':log(fine.Q@np.swapaxes(coarse.Q,-1,-2)),
                    'frame_orientation':log(fine.orientation@coarse.orientation.T)[None,:]}
    groups={}
    for key in a:
        if not a[key].size:
            continue
        delta=np.linalg.norm(rotation_error.get(key,b[key]-a[key]),axis=1)
        magnitude=np.maximum(np.linalg.norm(a[key],axis=1),np.linalg.norm(b[key],axis=1))
        ratios=delta/(accuracy['atol']+accuracy['rtol']*magnitude)
        if not np.all(np.isfinite(ratios)):
            raise AnalysisError('Nonfinite temporal refinement discrepancy for '+key+'.')
        groups[key]=float(np.max(ratios))
    worst=max(groups,key=groups.get)
    return dict(maximum_ratio=groups[worst],limiting_quantity=worst,group_ratios=groups)


def take_step(system,previous,older,time,order,frame,side,tolerance,*,acceptance_setup=None,selection=None):
    from .time_integration import bdf_coefficients,bdf_nonlinear_gate,newton
    progress=getattr(system,'progress',None)
    if progress is not None:progress('time_step',previous.time,time)
    h=time-previous.time
    if h<=0 or previous.time+h/2==previous.time:
        raise AnalysisError('Time refinement is below floating-point resolution.')
    if order==5:
        from .radau_time import step
        solved=step(system,previous,time,frame,side,tolerance,capture=acceptance_setup is not None)
        state,options,_,iterations,builds,error,stage_tolerance=solved[:7]
        detail=dict(stages=3,maximum_stage_residual=error,stage_tolerance=stage_tolerance)
    else:
        coefficients=bdf_coefficients(h,None if older is None or order==1 else previous.time-older.time)
        nonlinear_tolerance,nonlinear_policy=bdf_nonlinear_gate(system,coefficients,tolerance)
        function=lambda values:system.residual(values,previous,older if order==2 else None,time,coefficients,side=side)
        function.progress=progress
        from .structured_time import attach
        attach(system,function,progress)
        from .time_tangent import attach_mechanical_columns
        attach_mechanical_columns(system, function, lambda values, data: system.residual(
            values, previous, older if order == 2 else None, time, coefficients,
            side=side, _mechanical_data=data[0]))
        if system.feedback is not None:
            function.accepted_root_diagnostic=system.feedback.root_diagnostic(
                range(system.feedback_start,system.feedback_start+system.feedback.count),nonlinear_tolerance)
        values,_,iterations,builds=newton(function,system.guess(previous,h),nonlinear_tolerance,check_rank=system.requires_unique_time_solution)
        residual,state,options=system.residual(values,previous,older if order==2 else None,time,coefficients,side=side,detail=True)
        error=float(np.max(abs(residual)));detail=None
    stats=dict(iterations=iterations,builds=builds,residual=error,collocation=detail)
    if acceptance_setup is not None:
        from .time_acceptance import capture_bdf,capture_radau
        if order==5:
            stats['accepted_method']=capture_radau(system,previous,state,options,acceptance_setup,
                stage_data=solved[7],side=side,tolerance=tolerance,selection=selection)
        else:
            stats['accepted_method']=capture_bdf(system,previous,older if order==2 else None,state,options,acceptance_setup,
                values=values,time=time,coefficients=coefficients,side=side,tolerance=tolerance,selection=selection,
                nonlinear_tolerance=nonlinear_tolerance,nonlinear_policy=nonlinear_policy)
    return state,options,stats


def integrate(system,previous,older,options,setup,*,duration,dt,order,tolerance,max_steps,continuation,
              accuracy,progress=None,initial_step=None,side='right',initial_phase='before_load_switch',initial_error=None,
              initial_acceptance=None,initial_transition=None):
    from .time_integration import time_snapshot,UnresolvedControllerAuthority
    from .time_state import context,record
    from .time_acceptance import capture_initial
    from .gust import gust_field
    system.progress=progress
    n=system.network;histories=system.forcing;start=previous.time;end=start+duration
    if not np.isfinite(end) or end<=start:
        raise AnalysisError('Time interval is below floating-point resolution or nonfinite.')
    minimum=accuracy.get('minimum_step',min(dt,duration)/65536)
    if minimum>dt:
        raise AnalysisError('Minimum accuracy-check step exceeds the maximum step.')
    # Store the resolved limit, so a shorter resumed segment does not silently
    # choose a different rejection policy.
    accuracy=dict(accuracy,minimum_step=minimum)
    restart_context=context(system,setup,order,dt,tolerance,accuracy)
    error=float(np.max(abs(n.residual(previous.x,**options)))) if initial_error is None else initial_error
    from .time_snapshot_storage import snapshot_history
    snapshots=snapshot_history(time_snapshot(system,previous,options,error,0,0.,side))
    snapshots[0]['initial_phase']=initial_phase
    if initial_phase.startswith(('checkpoint','saved_equilibrium')):
        snapshots[0]['forcing_values']=previous.commands.copy()
    step=min(dt,duration) if initial_step is None else min(initial_step,dt,duration)
    accepted_initial=initial_acceptance if initial_acceptance is not None else capture_initial(
        system,previous,options,setup,phase=initial_phase,side=side,tolerance=tolerance)
    snapshots[0]['restart']=record(system,previous,older,options,step,side,accepted_method=accepted_initial)
    if initial_transition is not None:
        snapshots[0]['restart_context']=initial_transition['before_context']
        snapshots[0]['restart']=initial_transition['before_record']
    n.loads=setup['loads'];gust=gust_field(None if n.condition is None else n.condition.gust)
    rejected=nonlinear_retries=accuracy_retries=gust_retries=builds=iterations=0
    maximum_ratio=0.;attempts=0;accepted_steps=0
    if progress is not None:progress(start,0)
    while previous.time<end:
        if accepted_steps>=max_steps:
            raise AnalysisError('Time integration exceeded the maximum accepted step count.')
        from .time_input_transition import needed,complete
        if needed(system,previous,side,changed=initial_transition is not None):
            reason='replacement forcing' if initial_transition is not None else 'forcing cutoff' if previous.time==histories.end_time else 'forcing break'
            previous,options,right=complete(system,previous,setup,tolerance=tolerance,progress=progress,
                step=step,reason=reason,before_snapshot=snapshots[-1])
            snapshots.append(right);older=None;side='right'
        initial_transition=None
        upcoming=histories.events[histories.events>previous.time]
        event=float(upcoming[0]) if len(upcoming) else end
        time=min(previous.time+step,event,end)
        if event-time<=8*np.finfo(float).eps*max(abs(event),abs(time),dt):time=event
        h=time-previous.time;mid=previous.time+h/2
        if mid==previous.time or mid==time:
            raise AnalysisError('Time refinement is below floating-point resolution.')
        at_break=time in histories.breaks;target_side='left' if at_break else 'right'
        # Start/restart both refined substeps with BDF1, matching the coarse
        # trial's order. Subsequent BDF2 trials retain the actual half-step history.
        effective=1 if order==2 and older is None else order
        attempts+=1;phase=0.;failure=None;ratio=None
        try:
            coarse,coarse_options,coarse_stats=take_step(system,previous,older,time,effective,setup['frame'],target_side,tolerance)
            builds+=coarse_stats['builds'];iterations+=coarse_stats['iterations']
            half,half_options,half_stats=take_step(system,previous,older,mid,effective,setup['frame'],'right',tolerance)
            builds+=half_stats['builds'];iterations+=half_stats['iterations']
            if gust.kind!='none':half_positions=deepcopy(n.aero_cached['gust']['sample_positions_earth'])
            state,new_options,stats=take_step(system,half,previous if effective==2 else None,time,effective,setup['frame'],target_side,tolerance,
                acceptance_setup=setup,selection=dict(mode='two_half_steps',macro_start_time=float(previous.time),
                    midpoint_time=float(mid),macro_end_time=float(time),accepted_substep=2))
            builds+=stats['builds'];iterations+=stats['iterations']
            if gust.kind!='none':
                before=snapshots[-1]['gust']['sample_positions_earth'];after=n.aero_cached['gust']['sample_positions_earth']
                phase=max(gust.phase_change(before,half_positions,mid-previous.time),gust.phase_change(half_positions,after,time-mid))
                if phase>np.pi/8*(1+1e-9):
                    gust_retries+=1;failure='Gust phase travel exceeds pi/8 in a refined substep.'
            comparison=compare(system,previous,coarse,state,coarse_options,new_options,accuracy)
            ratio=comparison['maximum_ratio']
            if failure is None and ratio>1:
                accuracy_retries+=1;failure=f"Temporal refinement ratio {ratio:.6g} exceeds one for {comparison['limiting_quantity']}."
        except UnresolvedControllerAuthority:
            raise
        except (AnalysisError,ValueError,FloatingPointError) as exc:
            nonlinear_retries+=1;failure=str(exc)
        if failure is not None:
            rejected+=1
            factor=.5 if ratio is None else min(.5,max(.1,.8/np.sqrt(max(ratio,1e-30))))
            step=h*factor
            if progress is not None:progress('time_retry',previous.time,step)
            if step<minimum:
                raise AnalysisError(f'Time accuracy check failed after t={previous.time:.9g} at minimum step {minimum:.9g}: {failure}')
            continue
        # Retain the accepted branch through nonlinear or accuracy retries.
        side=target_side
        options=new_options;maximum_ratio=max(maximum_ratio,ratio)
        snapshot=time_snapshot(system,state,options,stats['residual'],effective,time-mid,side)
        snapshot['accuracy']=dict(comparison,trial_step=h,internal_steps=2,midpoint_time=mid,
                                  comparison_order=effective,accepted='two half steps; no extrapolation')
        if stats['collocation'] is not None:snapshot['collocation']=stats['collocation']
        snapshots.append(snapshot)
        accepted_steps+=1
        # Local algebraic loads may converge more slowly than ODE states. A
        # conservative square-root controller avoids assuming fifth-order DAE
        # accuracy; no Richardson factor divides away the observed discrepancy.
        step=min(dt,h*min(1.5,max(.5,.8/np.sqrt(max(ratio,1e-30)))))
        if phase>0:step=min(step,.99*h*np.pi/8/phase)
        older=None if order==5 or at_break else half
        previous=state
        snapshot['restart']=record(system,previous,older,options,step,side,accepted_method=stats['accepted_method'])
        if progress is not None:progress(state.time,accepted_steps)
    return dict(analysis='time_response',converged=True,frame_mode=setup['frame'],
        method='Radau IIA (3 stages)' if order==5 else f'BDF{order}',
        frame_load_targets=time_constraint_data(n.operating.constraints)['load_targets'],
        actuator_constraints=time_constraint_data(n.operating.constraints)['actuator_constraints'],
        duration=duration,start_time=start,end_time=end,restart_context=restart_context,maximum_step=dt,
        accepted_steps=accepted_steps,internal_steps=2*accepted_steps,rejected_steps=rejected,
        jacobian_builds=builds,newton_iterations=iterations,gust_resolution_retries=gust_retries,
        continuation_steps=continuation,evaluations=n.nfev,snapshots=snapshots,forcing=histories.report(),
        controller=None if system.feedback is None else system.feedback.report(),
        accuracy=dict(accuracy,method='one full step versus two half steps',minimum_step=minimum,
            attempts=attempts,rejected_accuracy_steps=accuracy_retries,rejected_nonlinear_steps=nonlinear_retries,
            maximum_accepted_ratio=maximum_ratio,scales=dict(length=n.L,velocity=system.V,rate=system.W,force=n.F,circulation=n.gamma_scale),
            norm='Maximum weighted physical vector/scalar discrepancy, including algebraic loads and endpoint rates; rotations use relative SO(3) angles.'),
        limitations=[
            'Optional OpenSwing temporal refinement check, not an ASWING adaptive-step convention or a global error bound. Refine tolerances, maximum step and spatial mesh independently.',
            'Each reported endpoint follows two accepted half steps. Snapshot step is the final internal step; accuracy.trial_step is the interval between reported snapshots. BDF checkpoints retain the unreported midpoint predecessor.',
            'The check includes motion, circulation, local/frame rates and accelerations, section forces/moments, support/joint reactions and controller states. It does not bound every derived output or capture arbitrary unsampled forcing features.',
            'Constrained variables can have lower order than ODE states. BDF startup reactions can fail to converge for curved constraints with nonzero initial speed; use Radau and verify refinement.',
            'Forcing knots and left/right event semantics are retained. Specified table values become zero beyond the last sample. Compatible inverse-history input changes complete separate right states. Atmospheric altitude remains prescribed; impulse events and legacy companion-file parity remain unimplemented.'])
