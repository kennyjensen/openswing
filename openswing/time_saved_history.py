"""Guarded saved-state launch of one Earth-velocity or Earth-position history.

This branch holds the saved physical state and completes its right-side
algebraic settings and rates. Versions 3 (velocity) and 4 (position) permit
explicit compatible transitions; legacy scopes retain their original contract.
Broader saved histories use separate validation before they can be supported.
"""
from copy import deepcopy
import numpy as np
from .aero import AnalysisError
from .equilibrium_state import restore,recipe_from_identity
from .forcing import TimeForcing
from .ground import body_to_earth
from .gust import gust_field
from .network import StaticNetwork
from .operating import TimeHistoryConstraint, time_constraint_data, time_operating_constraints
from .time_integration import TimeState, TimeSystem, integrate, time_snapshot
from .time_state import condition_data, motion_data, pack_state, pack_options, portable, read_condition
from .time_transition_initial import complete_history_transition


HELD_FIELDS=('r','Q','gamma','u','w','U','Omega','position','orientation')
SCOPE_KEY='saved_history_scope'
SCOPE_KINDS={1:'single-nonrotating-earth-velocity-linear-v1',
             2:'single-nonrotating-earth-velocity-spline-v2',
             3:'single-nonrotating-earth-velocity-transitions-v3',
             4:'single-nonrotating-earth-position-transitions-v4'}
SCOPE_KIND=SCOPE_KINDS[3]


def _scope(saved,launch,condition,motion,active_loads,constraints,frame,disturbance,*,version=None):
    rows=[row for row in constraints if row.variable.startswith(('control.','power.'))]
    if (frame!='mixed' or any(row.quantity not in ('force.x','force.y','force.z')
            for row in constraints if row not in rows)):
        raise AnalysisError('Saved history launch currently requires mixed motion with force-only frame targets; angular acceleration must remain prescribed zero.')
    quantities={kind+'.'+axis for kind in ('velocity_earth','position_earth') for axis in 'xyz'}
    if version is not None:
        kind='position_earth' if version==4 else 'velocity_earth'
        quantities={kind+'.'+axis for axis in 'xyz'}
    if (len(rows)!=1 or not isinstance(rows[0],TimeHistoryConstraint)
            or rows[0].quantity not in quantities):
        raise AnalysisError('Saved history launch requires exactly one Earth-velocity or Earth-position actuator target matching its recorded scope; other inverse histories remain pending.')
    if launch['controller'] is not None or saved.get('feedback') is not None:
        raise AnalysisError('Saved history launch with a controller is not implemented.')
    if disturbance is not None:
        raise AnalysisError('Saved history launch with a physical disturbance is not implemented.')
    if active_loads!=launch['loads']:
        raise AnalysisError('Saved history launch with changed loads is not implemented; retain the original loads.')
    if np.any(motion.rates!=0.) or np.any(motion.angular_acceleration!=0.):
        raise AnalysisError('Saved history launch currently requires zero saved angular velocity and angular acceleration.')
    if gust_field(None if condition is None else condition.gust).kind!='none':
        raise AnalysisError('Saved history launch with an active gust is not implemented.')
    return rows[0]


def _table_scope(histories,row,time,duration,*,version=3):
    if (len(histories.channels)!=1 or histories.channels[0]['group']!='targets'
            or histories.channels[0]['index']!=row.quantity):
        raise AnalysisError('Saved history launch requires one explicit inverse-target table channel; blank constant histories and other channels remain pending.')
    times=histories.channels[0]['distribution'].t
    if version==1 and len(times)!=2:
        raise AnalysisError('Legacy saved linear-history scope requires exactly two distinct table knots.')
    if version<3 and (len(times)<2 or np.any(np.diff(times)<=0)):
        raise AnalysisError('Saved history launch requires distinct increasing knots for a smooth cubic table; discontinuous transitions remain pending.')
    end=time+duration
    if not np.isfinite(end) or end<=time:
        raise AnalysisError('Saved history launch interval is below floating-point resolution or nonfinite.')
    if times[0]>time:
        raise AnalysisError('Saved history launch table must start at or before the saved time.')
    if version<3 and times[-1]<=end:
        raise AnalysisError('Legacy saved history launch table must end strictly beyond the requested interval; its original scope excludes cutoff transitions.')


def scope_record(row,*,version=None):
    if version is None:version=4 if row.quantity.startswith('position_earth.') else 3
    return dict(version=version,kind=SCOPE_KINDS[version],variable=row.variable,quantity=row.quantity)


def validate_scope(setup,*,required=False):
    """Check owned scope metadata and the physical setup it describes.

    This is conditional record consistency, not cryptographic authentication.
    Existing unmarked checkpoints retain their historical behavior.
    """
    if SCOPE_KEY not in setup:
        if required:raise AnalysisError('Saved history launch scope marker is required for the right-limit initial record.')
        return None
    marker=setup[SCOPE_KEY]
    if (not isinstance(marker,dict) or set(marker)!={'version','kind','variable','quantity'}
            or type(marker.get('version')) is not int or marker['version'] not in SCOPE_KINDS
            or marker['kind']!=SCOPE_KINDS[marker['version']]):
        raise AnalysisError('Saved history launch scope marker is malformed or unsupported.')
    from .inertia import Motion
    constraints=time_operating_constraints(setup['frame'],setup.get('load_targets'),setup.get('actuator_constraints'))
    row=_scope({},dict(controller=setup['controller'],loads=setup['loads']),read_condition(setup['condition']),
        Motion(**setup['motion']),setup['loads'],constraints,setup['frame'],None,version=marker['version'])
    if marker!=scope_record(row,version=marker['version']):
        raise AnalysisError('Saved history launch scope marker disagrees with its physical target setup.')
    return row


def require_continuation(setup,histories,time,duration):
    """Retain old smooth contracts; v3/v4 use explicit physical transitions."""
    row=validate_scope(setup,required=True)
    if setup[SCOPE_KEY]['version']<3 and histories.source!=setup['forcing']:
        raise AnalysisError('Saved history launch continuation cannot replace its forcing; explicit input-transition completion is pending.')
    _table_scope(histories,row,time,duration,version=setup[SCOPE_KEY]['version'])


def launch_history(model,saved,launch,c,motion,active_loads,mesh_loads,constraints,*,
                   duration,dt,order,frame,tolerance,max_steps,forcing,load_targets,
                   actuator_constraints,progress,disturbance,initial_difference_step,
                   initial_rank_tolerance,accuracy):
    """Internal branch of launch_time; its public arguments and controls persist."""
    row=_scope(saved,launch,c,motion,active_loads,constraints,frame,disturbance)
    time=0. if c is None else c.time
    histories=TimeForcing(forcing,model,c,motion,time+duration,frame,None,
        start_time=time,load_targets=load_targets,actuator_constraints=actuator_constraints)
    _table_scope(histories,row,time,duration,version=scope_record(row)['version'])
    n=StaticNetwork(model,launch['panels'],c,launch['gravity'],mesh_loads,
        motion if c is None else None,constraints,launch['strut_mode'],
        mesh_recipe=recipe_from_identity(saved.get('identity')))
    n.loads=deepcopy(launch['loads'])
    x=restore(n,saved)
    pose=launch['frame'];g=pose['gravity_magnitude']
    if c is None:
        from .inertia import vector
        position,attitude,velocity=(vector(pose[key],'Saved '+key) for key in ('position','attitude','velocity'))
    else:
        position,attitude=np.asarray(c.position_earth),np.asarray(c.attitude)
        velocity=-c.speed*c.vectors()[0]-np.cross(n.motion.rates,model.reference[3])
    # Repeat the actual network-motion check: condition-derived motion owns
    # this path when an aerodynamic condition is present.
    if np.any(n.motion.rates!=0.) or np.any(n.motion.angular_acceleration!=0.):
        raise AnalysisError('Saved history launch requires the restored condition to have zero angular velocity and angular acceleration.')
    r,Q,*_,gamma=n.unpack(x);zero=np.zeros_like(r)
    seed=TimeState(time,x,r,Q,zero.copy(),zero.copy(),velocity,n.motion.rates.copy(),
        position,body_to_earth(attitude),gamma)
    from .hinge_history import at_network
    seed.hinge_charts=at_network(n,Q)
    before_system=TimeSystem(n,gravity_magnitude=g)
    before_options=before_system.options(seed,zero,zero,np.zeros(n.circulation_basis.panels),apply_forcing=False)
    residual=n.residual(x,**before_options)
    before_error=float(np.max(abs(residual)))
    if not np.isfinite(before_error) or before_error>tolerance:
        raise AnalysisError(f'Saved equilibrium is inconsistent with the before-input time equations (residual {before_error:.3g}). The saved default target and selected force targets must agree with the original physical state; no history is applied to repair it.')
    # Own every before-input record now. Right-side evaluations mutate network
    # caches, and their solved algebraic values must never overwrite this source.
    before_snapshot=deepcopy(time_snapshot(before_system,seed,before_options,before_error,0,0.))
    before_snapshot['initial_phase']='saved_equilibrium_before_history_transition'
    seed_record=deepcopy(pack_state(n,seed))
    before_input=dict(snapshot=before_snapshot,saved_equilibrium=deepcopy(saved),
        input_context=dict(setup=deepcopy(launch),state=deepcopy(seed_record),options=deepcopy(pack_options(before_options))),
        restart_scope='saved_equilibrium_source_only')
    n.loads=deepcopy(active_loads)
    system=TimeSystem(n,histories,gravity_magnitude=g)
    state,options,completion=complete_history_transition(system,deepcopy(seed),frame,
        tolerance=tolerance,difference_step=initial_difference_step,
        rank_tolerance=initial_rank_tolerance,progress=progress)
    held_error={name:float(np.max(np.abs(getattr(state,name)-getattr(seed,name)),initial=0.)) for name in HELD_FIELDS}
    completion=deepcopy(completion)
    completion['seed_state']=deepcopy(seed_record)
    setup=dict(panels=n.panels,condition=condition_data(c),motion=motion_data(n.motion),gravity=launch['gravity'],
        gravity_magnitude=g,mesh_loads=mesh_loads,loads=active_loads,strut_mode=launch['strut_mode'],frame=frame,
        controller=None,forcing=forcing,**time_constraint_data(constraints))
    setup[SCOPE_KEY]=scope_record(row)
    result=integrate(system,state,None,options,portable(setup),duration=duration,dt=dt,order=order,
        tolerance=tolerance,max_steps=max_steps,continuation=0,progress=progress,
        initial_error=completion['residual'],accuracy=accuracy,side='right',
        initial_phase='history_transition_right_limit')
    result['launch_transition']=dict(version=1,kind='held_physical_state_right_limit',time=float(time),
        before_input=before_input,right_limit_snapshot_index=0,held_fields=list(HELD_FIELDS),
        held_state_max_error=held_error,completion=completion)
    result['initialization']=dict(source='saved steady equilibrium with held-state right-limit completion',
        equilibrium_recomputed=False,residual=completion['residual'],
        before_input_residual=before_error,right_limit_residual=completion['residual'],
        operating_values=deepcopy(result['snapshots'][0]['operating_values']),
        before_operating_values=deepcopy(saved['operating_values']),released_constraints=deepcopy(launch.get('released_constraints',[])),
        local_rates='saved zero local velocities and angular rates held; local accelerations completed on the right branch',
        inputs_apply='at the explicit right limit; original before-input snapshot retained in launch_transition')
    return result
