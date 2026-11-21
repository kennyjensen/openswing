"""Portable physical time checkpoints, including the BDF predecessor.

This is an OpenSwing format, not an ASWING .pnt/.set interchange format.
The setup and original forcing offsets belong to the saved trajectory.
"""
from copy import deepcopy
from dataclasses import asdict,replace
import numpy as np
from .aero import AnalysisError,FlightCondition
from .inertia import Motion
from .equilibrium_state import identity,matching_identity,capture,restore,finite_array,feedback_layout

FIELDS=('positions','rotations','internal_force','internal_moment','reactions','circulation','operating_values')


def portable(value):
    if isinstance(value,np.ndarray):return portable(value.tolist())
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:portable(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [portable(v) for v in value]
    return value


def condition_data(c):
    return None if c is None else portable(asdict(c))


def read_condition(data, *, saved=True):
    if data is None:return None
    if not isinstance(data,dict):raise AnalysisError('Invalid checkpoint flight condition.')
    data=deepcopy(data)
    # Missing fields in old saved states predate the ASWING-compatible default.
    # Fresh requests use FlightCondition defaults; explicit choices always win.
    if saved:data.setdefault('freeze_influences',False)
    for key in ('controls','powers'):data[key]={int(k):float(v) for k,v in data.get(key,{}).items()}
    return FlightCondition(**data)


def motion_data(m):
    return {name:getattr(m,name).tolist() for name in ('rates','acceleration','angular_acceleration')}


def position_chart(n,x):
    """Retain small translations before adding the much larger jig position.

    Absolute positions remain the portable physical view. This optional chart
    preserves their low-order displacement information for BDF continuation;
    it has an explicit physical origin and length scale, not an opaque vector.
    """
    return dict(scheme='jig-relative-translation-v1',origin=n.rj.tolist(),scale=float(n.L),
        coordinates=x[:6*n.nn].reshape(n.nn,6)[:,:3].tolist())


def restore_position_chart(n,data,x):
    """Validate the optional precision extension; old checkpoints stay valid."""
    if 'position_chart' not in data:return
    chart=data['position_chart']
    if (not isinstance(chart,dict) or set(chart)!={'scheme','origin','scale','coordinates'}
            or chart['scheme']!='jig-relative-translation-v1'):
        raise AnalysisError('Invalid checkpoint position chart.')
    scale=scalar(chart['scale'],'position chart scale',positive=True)
    origin=finite_array(chart,'origin',(n.nn,3))
    coordinates=finite_array(chart,'coordinates',(n.nn,3))
    positions=finite_array(data['network'],'positions',(n.nn,3))
    with np.errstate(over='ignore',invalid='ignore'):
        represented=origin+scale*coordinates
    if not np.all(np.isfinite(represented)) or not np.array_equal(represented,positions):
        raise AnalysisError('Checkpoint position chart disagrees with physical positions.')
    # Keep the exact coordinates on the same mesh. If an identity-compatible
    # reconstruction differs at roundoff, translate origins before scaling;
    # never subtract two large reconstructed absolute positions again.
    if scale==n.L and np.array_equal(origin,n.rj):
        restored=coordinates
    else:
        with np.errstate(over='ignore',invalid='ignore'):
            restored=((origin-n.rj)+scale*coordinates)/n.L
        if not np.all(np.isfinite(restored)):
            raise AnalysisError('Checkpoint position chart cannot be represented on this mesh.')
    x[:6*n.nn].reshape(n.nn,6)[:,:3]=restored


def pack_state(n,state):
    physical=capture(n,state.x,include_launch=False,hinge_charts_override=state.hinge_charts)
    result=dict(time=float(state.time),network={k:physical[k] for k in FIELDS},
        local_velocity=state.u.tolist(),local_rates=state.w.tolist(),velocity_origin_body=state.U.tolist(),
        rates_body=state.Omega.tolist(),position_earth=state.position.tolist(),body_to_earth=state.orientation.tolist(),
        feedback=state.feedback.tolist(),commands=deepcopy(state.commands),
        position_chart=position_chart(n,state.x))
    if n.hinges:result['network'].update(version=2,hinge_charts=physical['hinge_charts'])
    if state.position_history is not None:
        from .position_history_checkpoint import pack_sample
        result['position_history']=portable(pack_sample(state.position_history))
    from .time_network import source_time_chart
    chart=source_time_chart(n)
    if chart is not None:result.update(chart.pack(state))
    return result


def scalar(value,name,positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value) or (positive and value<=0):
        raise AnalysisError(f'Invalid checkpoint {name}.')
    return float(value)


def finite_map(data,keys,name,positive=False):
    if not isinstance(data,dict) or set(data)!=set(keys):raise AnalysisError(f'Invalid checkpoint {name} channels.')
    return {k:scalar(v,name,positive) for k,v in data.items()}


def unpack_state(n,data,feedback):
    from .time_integration import TimeState
    if not isinstance(data,dict) or not isinstance(data.get('network'),dict):raise AnalysisError('Invalid checkpoint physical state.')
    physical=dict(data['network']);physical.setdefault('version',1)
    physical.update(format='openswing-equilibrium',identity=identity(n))
    x=restore(n,physical,install_hinge_charts=False)
    restore_position_chart(n,data,x)
    from .equilibrium_state import checked_hinge_charts
    centers=tuple(checked_hinge_charts(n,physical,x)) if n.hinges else ()
    r,Q,*_,gamma=n.unpack(x)
    time=scalar(data.get('time'),'time')
    if time<0:raise AnalysisError('Checkpoint time must be nonnegative.')
    orientation=finite_array(data,'body_to_earth',(3,3))
    if np.linalg.norm(orientation.T@orientation-np.eye(3))>1e-8 or abs(np.linalg.det(orientation)-1)>1e-8:
        raise AnalysisError('Checkpoint frame orientation must be a proper rotation matrix.')
    commands=data.get('commands')
    if not isinstance(commands,dict):raise AnalysisError('Invalid checkpoint commands.')
    commands={k:scalar(v,'command') for k,v in commands.items()}
    state=TimeState(time,x,r,Q,finite_array(data,'local_velocity',(n.nn,3)),finite_array(data,'local_rates',(n.nn,3)),
        finite_array(data,'velocity_origin_body',(3,)),finite_array(data,'rates_body',(3,)),
        finite_array(data,'position_earth',(3,)),orientation,gamma,
        finite_array(data,'feedback',(0 if feedback is None else feedback.size,)),commands,hinge_charts=centers)
    if 'position_history' in data:
        from .position_history_checkpoint import unpack_sample
        state.position_history=unpack_sample(data['position_history'])
    from .time_network import source_time_chart
    chart=source_time_chart(n)
    if chart is not None:chart.unpack(state,data)
    return state


def feedback_data(f):
    if f is None:return None
    return dict(layout=feedback_layout(f),commands=deepcopy(f.commands),bias=deepcopy(f.bias),
        signal_scales=deepcopy(f.signal_scales),scales=f.scales.tolist(),rate_scales=f.rate_scales.tolist(),
        time_scale=float(f.time_scale))


def restore_feedback(f,data,state):
    if f is None:
        if data is not None:raise AnalysisError('Checkpoint controller definition is missing.')
        return
    if not isinstance(data,dict) or data.get('layout')!=feedback_layout(f):raise AnalysisError('Checkpoint controller layout does not match.')
    f.commands=finite_map(data.get('commands'),f.signals,'controller commands')
    f.bias=finite_map(data.get('bias'),[o['actuator'] for o in f.outputs],'controller biases')
    f.signal_scales=finite_map(data.get('signal_scales'),f.signals,'signal scales',True)
    f.scales=finite_array(data,'scales',(f.size,));f.rate_scales=finite_array(data,'rate_scales',(f.size-f.count,))
    if np.any(f.scales<=0) or np.any(f.rate_scales<=0):raise AnalysisError('Checkpoint controller scales must be positive.')
    f.time_scale=scalar(data.get('time_scale'),'controller time scale',True)
    f.base=state.feedback.copy()


def pack_options(options):
    return dict(condition=condition_data(options['condition_override']),motion=motion_data(options['motion_override']),
        local_acceleration=options['elastic_motion'][2].tolist(),local_rate_derivative=options['elastic_motion'][3].tolist(),
        circulation_rate=options['circulation_rate'].tolist(),gravity=options['gravity_override'].tolist(),
        operating_targets=portable(options.get('operating_targets',{})),
        **({'hinge_charts':list(options['hinge_charts'])} if 'hinge_charts' in options else {}))


def unpack_options(n,state,data):
    from .hinge_history import checked
    charts={'hinge_charts':checked(n,data.get('hinge_charts'))} if n.hinges else {}
    return dict(condition_override=read_condition(data['condition']),motion_override=Motion(**data['motion']),
        elastic_motion=(state.u,state.w,finite_array(data,'local_acceleration',(n.nn,3)),finite_array(data,'local_rate_derivative',(n.nn,3))),
        circulation_rate=finite_array(data,'circulation_rate',(n.circulation_basis.panels,)),gravity_override=finite_array(data,'gravity',(3,)),
        operating_targets=data.get('operating_targets',{}),**charts)


def checkpoint_frame_options(n,state,options,gravity_magnitude=None):
    """Require the cached residual inputs to describe the saved physical frame.

    New forcing must not be applied here: a saved launch or changed-input
    checkpoint can intentionally precede its next commands. Preserve cached
    actuator, acceleration and target values, but recover redundant kinematic
    fields from the physical state before validating its common residual.
    """
    from .time_integration import TimeSystem
    from .ground import body_to_earth
    system=TimeSystem(n,gravity_magnitude=gravity_magnitude)
    physical,_=system.condition(state)
    cached=options['condition_override'];cached_motion=options['motion_override']
    defects={
        'angular velocity':float(np.linalg.norm(cached_motion.rates-state.Omega)/system.W),
        'gravity':float(np.linalg.norm(options['gravity_override']-system.gravity(state))/system.A),
    }
    if (physical is None)!=(cached is None):
        raise AnalysisError('Checkpoint frame condition does not match its physical setup.')
    if cached is not None:
        for name in ('speed','alpha','beta','time'):
            scalar(getattr(cached,name),'frame cached '+name,positive=name=='speed')
        for name in ('rates','position_earth','attitude'):
            try:value=np.asarray(getattr(cached,name))
            except (ValueError,TypeError) as exc:
                raise AnalysisError(f'Checkpoint frame cached {name} must be a finite xyz vector.') from exc
            if value.shape!=(3,) or value.dtype.kind not in 'iuf' or not np.all(np.isfinite(value)):
                raise AnalysisError(f'Checkpoint frame cached {name} must be a finite xyz vector.')
        origin=-cached.speed*cached.vectors()[0]-np.cross(np.asarray(cached.rates),n.model.reference[3])
        defects.update({
            'origin velocity':float(np.linalg.norm(origin-state.U)/system.V),
            'condition angular velocity':float(np.linalg.norm(np.asarray(cached.rates)-state.Omega)/system.W),
            'position':float(np.linalg.norm(np.asarray(cached.position_earth)-state.position)/n.L),
            'orientation':float(np.linalg.norm(body_to_earth(cached.attitude)-state.orientation)),
            'time':float(abs(cached.time-state.time)*system.W),
        })
    for name,error in defects.items():
        if not np.isfinite(error) or error>1e-8:
            raise AnalysisError(f'Checkpoint frame {name} disagrees with its cached residual inputs (scaled difference {error:.3g}).')
    if n.hinges:
        from .hinge_history import checked,lifted
        owned=checked(n,state.hinge_charts)
        represented=lifted(n,state.Q,options.get('hinge_charts'))
        branch_error=max((abs(a-b) for a,b in zip(owned,represented)),default=0.)
        if branch_error>1e-8:
            raise AnalysisError('Checkpoint hinge history disagrees with its cached residual branch.')
    rebuilt=dict(options)
    if cached is not None:
        rebuilt['condition_override']=replace(cached,speed=physical.speed,alpha=physical.alpha,beta=physical.beta,
            rates=physical.rates,position_earth=physical.position_earth,attitude=physical.attitude,time=physical.time)
    rebuilt['motion_override']=Motion(state.Omega,cached_motion.acceleration,cached_motion.angular_acceleration)
    rebuilt['gravity_override']=system.gravity(state)
    return rebuilt


def context(system,setup,order,dt,tolerance,accuracy=None):
    result=dict(identity=identity(system.network),setup=portable(deepcopy(setup)),feedback=feedback_data(system.feedback),
        forcing_offsets={c['name']:c['initial'] for c in system.forcing.channels},
        method=dict(order=order,maximum_step=dt,tolerance=tolerance,**({} if accuracy is None else {'accuracy':deepcopy(accuracy)})))
    from .position_history_checkpoint import method_metadata
    metadata=method_metadata(system,order)
    if metadata is not None:result['method']['position_history']=portable(metadata)
    return result


def record(system,state,older,options,next_step,side,*,accepted_method=None):
    result=dict(state=pack_state(system.network,state),older=None if older is None else pack_state(system.network,older),
        options=pack_options(options),next_step=float(next_step),forcing_side=side,
        validation_loads=portable(deepcopy(system.network.loads)))
    if system.network.hinges:result['version']=2
    if accepted_method is not None:result['accepted_method']=deepcopy(accepted_method)
    return result


def checkpoint(result,index=-1):
    """Make an owned standalone checkpoint at a computed result snapshot."""
    try:
        record=deepcopy(result['snapshots'][index]['restart'])
        version=record.pop('version',1)
        return deepcopy(dict(format='openswing-time-checkpoint',version=version,context=result['snapshots'][index].get('restart_context',result['restart_context']),**record))
    except (KeyError,IndexError,TypeError) as exc:raise AnalysisError('This result has no checkpoint at the selected snapshot.') from exc


def restore_checkpoint(model,saved):
    """Validate a physical checkpoint without advancing or changing its inputs."""
    from .network import StaticNetwork
    from .equilibrium_state import recipe_from_identity
    from .feedback import FeedbackSystem
    from .operating import time_operating_constraints
    if not isinstance(saved,dict) or saved.get('format')!='openswing-time-checkpoint' or type(saved.get('version')) is not int or saved.get('version') not in (1,2):
        raise AnalysisError('Expected a version-1 or version-2 OpenSwing time checkpoint.')
    try:
        saved=deepcopy(saved);ctx=saved['context'];setup=ctx['setup']
        c=read_condition(setup['condition']);motion=Motion(**setup['motion'])
        from .time_network import time_network_class
        network_class=time_network_class(model,c,frame=setup['frame'],
            structural_operator=setup.get('structural_operator'),identity=ctx.get('identity'),
            controller=setup['controller'],actuator_constraints=setup.get('actuator_constraints'),
            strut_mode=setup['strut_mode'],require_saved_operator=True)
        n=network_class(model,setup['panels'],c,setup['gravity'],setup['mesh_loads'],None if c is not None else motion,
            time_operating_constraints(setup['frame'],setup.get('load_targets'),setup.get('actuator_constraints')),setup['strut_mode'],
            mesh_recipe=recipe_from_identity(ctx.get('identity')))
        if not matching_identity(ctx['identity'],identity(n)):raise AnalysisError('Checkpoint aircraft, mesh or constraints do not match.')
        if getattr(n,'source_moving',False) and 'accepted_method' not in saved:
            raise AnalysisError('Source time checkpoint requires its accepted method and Euler-angle history.')
        if saved['version']!=(2 if n.hinges else 1):
            raise AnalysisError('Hinged time histories require version-2 checkpoints with owned continuous angles; non-hinge histories use version 1.')
        f=None if setup['controller'] is None else FeedbackSystem(n,setup['controller'])
        state=unpack_state(n,saved['state'],f)
        older=None if saved['older'] is None else unpack_state(n,saved['older'],f)
        if older is not None and older.time>=state.time:raise AnalysisError('Checkpoint BDF predecessor must be earlier than its current state.')
        restore_feedback(f,ctx['feedback'],state)
        from .position_history_checkpoint import validate_checkpoint,validate_acceleration
        accepted_system=validate_checkpoint(n,f,state,older,saved)
        options=checkpoint_frame_options(n,state,unpack_options(n,state,saved['options']),setup.get('gravity_magnitude'))
        validate_acceleration(accepted_system,state,options)
        n.loads=saved['validation_loads']
        residual,data=n.residual(state.x,detail=True,**options)
        error=float(np.max(abs(residual)))
        if f is not None:error=max(error,float(np.max(abs(f.evaluate(state,data)[0]))))
        old_tolerance=scalar(ctx['method']['tolerance'],'saved tolerance',True)
        if not np.isfinite(error) or error>max(10*old_tolerance,1e-8):
            raise AnalysisError(f'Checkpoint physical/algebraic residual is inconsistent ({error:.3g}).')
        from .time_acceptance_validation import validate_accepted_method
        # A recorded method is binding. Re-evaluate its original discrete
        # equations at fixed values; do not solve or continuously reinitialize
        # a valid finite-step state. Old and initial records retain their
        # explicitly limited physical-only validation scope.
        saved['acceptance_validation']=validate_accepted_method(model,saved)
        return n,f,state,older,options,data,error,saved
    except (KeyError,TypeError,IndexError) as exc:
        raise AnalysisError(f'Incomplete or malformed time checkpoint: {exc}') from exc


def resume_time(model,saved,*,duration,dt=None,order=None,tolerance=None,forcing=None,max_steps=10000,progress=None,accuracy='saved'):
    """Advance by an additional duration from an exact saved physical state.

    Unchanged forcing retains BDF history and original +channel offsets.
    Replacing the table is an explicit input change and restarts BDF with BDF1;
    Radau IIA needs no predecessor for either kind of continuation.
    """
    from .forcing import TimeForcing
    from .time_integration import TimeSystem,integrate,validate_time_settings
    if not isinstance(saved,dict) or saved.get('format')!='openswing-time-checkpoint' or type(saved.get('version')) is not int or saved.get('version') not in (1,2):
        raise AnalysisError('Expected a version-1 or version-2 OpenSwing time checkpoint.')
    try:
        saved=deepcopy(saved);ctx=saved['context'];setup=ctx['setup'];method=ctx['method']
        dt=method['maximum_step'] if dt is None else dt
        order=method['order'] if order is None else order
        tolerance=method['tolerance'] if tolerance is None else tolerance
        from .time_accuracy import settings
        accuracy=settings(method.get('accuracy') if accuracy=='saved' else accuracy)
        frame=setup['frame'];validate_time_settings(duration,dt,order,frame,max_steps,tolerance)
        n,f,state,older,options,_,error,saved=restore_checkpoint(model,saved)
        ctx=saved['context'];setup=ctx['setup'];c=n.condition
        end=state.time+duration
        source=setup['forcing'] if forcing is None else forcing
        from .position_history_checkpoint import validate_checkpoint,require_smooth_continuation
        accepted_system=validate_checkpoint(n,f,state,older,saved)
        if accepted_system is not None:
            require_smooth_continuation(accepted_system,source,setup['forcing'],state,order,end_time=end)
        histories=TimeForcing(source,model,c,n.motion,end,frame,f,start_time=state.time,load_targets=setup.get('load_targets'),actuator_constraints=setup.get('actuator_constraints'))
        if 'saved_history_scope' in setup:
            from .time_saved_history import require_continuation
            require_continuation(setup,histories,state.time,duration)
        for channel in histories.channels:
            if channel['name'] in ctx['forcing_offsets']:channel['initial']=scalar(ctx['forcing_offsets'][channel['name']],'forcing offset')
        if source!=setup['forcing'] or state.time in histories.breaks:older=None
        system=TimeSystem(n,histories,f,gravity_magnitude=setup.get('gravity_magnitude'))
        if system.position_lift is not None:
            system.position_lift.tolerance=max(tolerance,1e-8)
        step=min(dt,scalar(saved['next_step'],'next step',True))
        from .time_cold_initial import cold_history_targets
        transition=None
        if source!=setup['forcing'] and cold_history_targets(n.operating.constraints):
            transition=dict(before_context=deepcopy(ctx),before_record=deepcopy({key:saved[key]
                for key in ('state','older','options','next_step','forcing_side','validation_loads','accepted_method')
                if key in saved}))
        setup['forcing']=source
        result=integrate(system,state,older,options,setup,duration=duration,dt=dt,order=order,tolerance=tolerance,
            max_steps=max_steps,continuation=0,progress=progress,initial_step=step,side=saved['forcing_side'],
            initial_phase='checkpoint_before_next_inputs',initial_error=error,accuracy=accuracy,
            initial_acceptance=saved.get('accepted_method'),initial_transition=transition)
        result['checkpoint_validation']=deepcopy(saved['acceptance_validation'])
        return result
    except (KeyError,TypeError,IndexError) as exc:
        raise AnalysisError(f'Incomplete or malformed time checkpoint: {exc}') from exc
