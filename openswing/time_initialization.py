"""Launch the time equations from a portable, validated steady operating point.

The saved setup is authoritative. Steady trim targets are released, controller
commands are retained, and new time inputs apply after the initial snapshot.
Optional physical disturbances complete the nonlinear constrained initial rates.
A guarded inverse Earth-velocity/position history branch instead completes the held
physical state at the explicit right limit and retains the before-input record.
Neither path recomputes the saved equilibrium.
"""
from copy import deepcopy
import numpy as np
from .aero import AnalysisError
from .equilibrium_state import restore,restore_feedback,finite_array,recipe_from_identity
from .feedback import FeedbackSystem
from .forcing import TimeForcing
from .ground import body_to_earth
from .inertia import Motion,vector
from .network import StaticNetwork
from .operating import time_operating_constraints, time_constraint_data
from .time_integration import TimeState,TimeSystem,integrate,validate_time_settings
from .time_state import read_condition,condition_data,motion_data,portable


def launch_time(model,saved,*,duration,dt,order=2,frame='prescribed',tolerance=1e-8,
                max_steps=10000,forcing='',loads=None,load_targets=None,actuator_constraints=None,progress=None,
                disturbance=None,initial_difference_step=.01,initial_rank_tolerance=1e-7,accuracy=None):
    """Use a saved steady state, optionally with a compatible physical disturbance.

    Default loads hold the saved body-axis wrenches; an explicit list replaces
    them after snapshot zero. New attachment stations must not change the mesh.
    The saved state must satisfy the selected frame load targets. A support
    release with inconsistent initial derivatives is rejected, not projected.
    Forcing times are absolute and must start no later than the saved time.
    Specified values become zero after the table ends on the ordinary path.
    A single nonrotating Earth-velocity or Earth-position history has a guarded
    held-state right-limit path with unchanged loads and compatible table
    transitions. It retains the old snapshot under ``launch_transition``;
    snapshot zero and its checkpoint contain the completed right state.
    ``disturbance`` uses the physical initial-response state schema. All omitted
    dynamic increments are zero. A nonlinear derivative array holds these values
    fixed and solves the algebraic state and initial rates before new time inputs.
    """
    validate_time_settings(duration,dt,order,frame,max_steps,tolerance)
    from .time_accuracy import settings
    accuracy=settings(accuracy)
    if not isinstance(saved,dict) or not isinstance(saved.get('launch'),dict) or saved['launch'].get('version')!=1:
        raise AnalysisError('Saved equilibrium lacks time-launch setup; recompute and export it with the current application.')
    if saved['launch'].get('quiescent_density') is not None or saved.get('identity', {}).get('quiescent_density') is not None:
        raise AnalysisError('Quiescent modal equilibria cannot launch time response; that fluid model is currently supported for fixed-frame modes only.')
    launch=deepcopy(saved['launch'])
    try:
        c=read_condition(launch['condition']);motion=Motion(**launch['motion'])
        active_loads=deepcopy(launch['loads'] if loads is None else list(loads))
        mesh_loads=launch['loads']+active_loads
        constraints=time_operating_constraints(frame,load_targets,actuator_constraints)
        from .time_network import time_network_class
        network_class=time_network_class(model,c,frame=frame,identity=saved.get('identity'),
            controller=launch['controller'],actuator_constraints=actuator_constraints,
            strut_mode=launch['strut_mode'])
        from .time_cold_initial import cold_history_targets
        if cold_history_targets(constraints):
            from .time_saved_history import launch_history
            return launch_history(model,saved,launch,c,motion,active_loads,mesh_loads,constraints,
                duration=duration,dt=dt,order=order,frame=frame,tolerance=tolerance,max_steps=max_steps,
                forcing=forcing,load_targets=load_targets,actuator_constraints=actuator_constraints,
                progress=progress,disturbance=disturbance,initial_difference_step=initial_difference_step,
                initial_rank_tolerance=initial_rank_tolerance,accuracy=accuracy)
        n=network_class(model,launch['panels'],c,launch['gravity'],mesh_loads,
            motion if c is None else None,constraints,launch['strut_mode'],
            mesh_recipe=recipe_from_identity(saved.get('identity')))
        n.loads=launch['loads']
        x=restore(n,saved)
        pose=launch['frame'];g=pose['gravity_magnitude']
        if c is None:
            position,attitude,velocity=(vector(pose[key],'Saved '+key) for key in ('position','attitude','velocity'))
            time=0.
        else:
            position,attitude=np.asarray(c.position_earth),np.asarray(c.attitude)
            velocity=-c.speed*c.vectors()[0]-np.cross(n.motion.rates,model.reference[3]);time=c.time
        r,Q,*_,gamma=n.unpack(x);zero=np.zeros_like(r)
        state=TimeState(time,x,r,Q,zero.copy(),zero.copy(),velocity,n.motion.rates.copy(),position,body_to_earth(attitude),gamma)
        from .hinge_history import at_network
        state.hinge_charts=at_network(n,Q)
        feedback=None if launch['controller'] is None else FeedbackSystem(n,launch['controller'])
        if feedback is None and saved.get('feedback') is not None:
            raise AnalysisError('Saved controller state requires its matching time-launch definition.')
        system=TimeSystem(n,controller=feedback,gravity_magnitude=g)
        if system.source_time is not None:
            state.source_attitude=np.deg2rad(attitude).copy()
            system.source_time.bind(state)
        if feedback is not None:
            state.feedback=finite_array(saved.get('feedback',{}),'values',(feedback.size,))
            options=system.options(state,zero,zero,np.zeros(n.circulation_basis.panels),apply_forcing=False)
            _,data=n.residual(x,detail=True,**options)
            feedback.initialize(state,data)
            restore_feedback(n,feedback,state,saved,preserve_commands=True)
        histories=TimeForcing(forcing,model,c,n.motion,time+duration,frame,feedback,start_time=time,load_targets=load_targets,actuator_constraints=actuator_constraints)
        if feedback is not None:histories.bind_commands({**feedback.commands,**feedback.bias})
        system.forcing=histories
        state.commands={channel['name']:channel['initial'] for channel in histories.channels}
        options=system.options(state,zero,zero,np.zeros(n.circulation_basis.panels),apply_forcing=False)
        residual,data=n.residual(x,detail=True,**options)
        if feedback is not None:residual=np.r_[residual,feedback.evaluate(state,data,np.zeros(feedback.size))[0]]
        error=float(np.max(abs(residual)))
        if not np.isfinite(error) or error>tolerance:
            hint=' The saved net loads must satisfy the selected frame targets, and the state must satisfy any actuator targets; compute a matching equilibrium or trim first.' if constraints else ''
            raise AnalysisError(f'Saved equilibrium is inconsistent with the time equations (residual {error:.3g}).'+hint)
        if system.has_actuator_constraints:
            from .time_integration import regular_tangent
            # The unchanged saved zero-local-rate state must determine its new
            # algebraic actuators, just as a cold initial equilibrium does.
            regular_tangent(lambda value:n.residual(value,**options),x)
        initial_report=None
        if disturbance is not None:
            from .nonlinear_initial import InitialSystem,consistent_initial
            chart=InitialSystem(system,state,frame);requested=chart.profile(disturbance)
            completed,rate,initial_report=consistent_initial(chart.residual,requested,chart.dynamic_indices,
                chart.rate_guess(requested),time=state.time,time_scale=chart.W,tolerance=tolerance,
                difference_step=initial_difference_step,rank_tolerance=initial_rank_tolerance,progress=progress)
            residual,state,options=chart.residual(completed,rate,state.time,detail=True)
            error=float(np.max(abs(residual)))
            if error>tolerance:raise AnalysisError('Completed physical initial disturbance fails the full time residual.')
        setup=dict(panels=n.panels,condition=condition_data(c),motion=motion_data(n.motion),gravity=launch['gravity'],
            gravity_magnitude=g,mesh_loads=mesh_loads,loads=active_loads,strut_mode=launch['strut_mode'],frame=frame,
            controller=launch['controller'],forcing=forcing,**time_constraint_data(constraints))
        if getattr(n, 'source_moving', False):setup['structural_operator']=n.structural_operator
    except AnalysisError:
        raise
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        raise AnalysisError(f'Invalid saved equilibrium time-launch setup: {exc}') from exc
    result=integrate(system,state,None,options,portable(setup),duration=duration,dt=dt,order=order,tolerance=tolerance,
        max_steps=max_steps,continuation=0,progress=progress,initial_error=error,accuracy=accuracy,
        initial_phase='saved_equilibrium_before_time_inputs' if disturbance is None else 'saved_equilibrium_disturbance_before_time_inputs')
    result['initialization']=dict(source='saved steady equilibrium',equilibrium_recomputed=False,residual=error,
        operating_values=deepcopy(saved['operating_values']),released_constraints=launch.get('released_constraints',[]),
        local_rates='zero' if disturbance is None else 'specified physical disturbance',inputs_apply='after initial snapshot')
    if initial_report is not None:
        result['initialization'].update(disturbance=deepcopy(disturbance),consistency=initial_report)
    return result
