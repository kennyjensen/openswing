"""Physical velocity surveys of solved geometry and circulation, without a time step."""
from copy import deepcopy
from dataclasses import asdict
import numpy as np
from .aero import AnalysisError,FlightCondition,evaluate_aerodynamics,_validate
from .geometry import model_meshes
from .ground import body_to_earth,vector3
from .time_state import read_condition,restore_checkpoint,portable


def plane_grid(spec):
    """An orthonormal right-handed slice, in the selected coordinate frame."""
    if not isinstance(spec,dict) or set(spec)-{'origin','normal','direction','u','v','counts'}:
        raise AnalysisError('A survey plane accepts origin, normal, direction, u/v bounds and counts.')
    origin=vector3(spec.get('origin',[0,0,0]),'Plane origin')
    normal=vector3(spec.get('normal',[0,0,1]),'Plane normal')
    norm=np.linalg.norm(normal)
    if norm<1e-12:raise AnalysisError('Plane normal must be nonzero.')
    normal=normal/norm
    direction=vector3(spec.get('direction',np.eye(3)[np.argmin(abs(normal))]),'Plane direction')
    direction=direction-normal*(normal@direction);norm=np.linalg.norm(direction)
    if norm<1e-12:raise AnalysisError('Plane direction must not be parallel to its normal.')
    u=direction/norm;v=np.cross(normal,u)
    counts=spec.get('counts',[21,21])
    if not isinstance(counts,(list,tuple)) or len(counts)!=2 or any(type(n) is not int or not 2<=n<=99 for n in counts):
        raise AnalysisError('Plane counts must be two integers from 2 through 99.')
    bounds=np.asarray([spec.get('u',[-5,5]),spec.get('v',[-5,5])],dtype=float)
    if bounds.shape!=(2,2) or not np.all(np.isfinite(bounds)) or np.any(bounds[:,1]<=bounds[:,0]):
        raise AnalysisError('Plane u/v bounds must be finite increasing pairs.')
    us=np.linspace(*bounds[0],counts[0]);vs=np.linspace(*bounds[1],counts[1]);a,b=np.meshgrid(us,vs)
    points=origin+a.ravel()[:,None]*u+b.ravel()[:,None]*v
    return points,dict(origin=origin.tolist(),normal=normal.tolist(),direction=u.tolist(),
        transverse=v.tolist(),u=us.tolist(),v=vs.tolist(),counts=list(counts),ordering='v rows, u columns')


def _steady(model,saved):
    """Restore the solved condition and actual actuators for inspection."""
    from .network import StaticNetwork
    from .equilibrium_state import restore,restore_feedback,finite_array,recipe_from_identity
    from .feedback import FeedbackSystem
    from .time_integration import TimeState,TimeSystem
    if not isinstance(saved,dict) or not isinstance(saved.get('launch'),dict) or saved['launch'].get('version')!=1:
        raise AnalysisError('Flow inspection requires a saved equilibrium with its complete setup.')
    launch=deepcopy(saved['launch']);c=read_condition(launch['condition'])
    if c is None:raise AnalysisError('This structural equilibrium has no aerodynamic flight condition.')
    n=StaticNetwork(model,launch['panels'],c,launch['gravity'],launch['loads'],None,
        (),launch['strut_mode'],mesh_recipe=recipe_from_identity(saved.get('identity')))
    # The launch condition already contains the solved operating inputs.
    # Inspect that physical state with trim unknowns released; command trims
    # are preserved by restoring the saved controller commands below.
    x=restore(n,saved);r,Q,*_,gamma=n.unpack(x);zero=np.zeros_like(r)
    state=TimeState(c.time,x,r,Q,zero.copy(),zero.copy(),-c.speed*c.vectors()[0]-np.cross(n.motion.rates,model.reference[3]),
        n.motion.rates.copy(),np.asarray(c.position_earth),body_to_earth(c.attitude),gamma)
    from .hinge_history import at_network
    state.hinge_charts=at_network(n,Q)
    f=None if launch['controller'] is None else FeedbackSystem(n,launch['controller'])
    system=TimeSystem(n,controller=f,gravity_magnitude=launch['frame']['gravity_magnitude'])
    if f is not None:
        state.feedback=finite_array(saved.get('feedback',{}),'values',(f.size,))
        options=system.options(state,zero,zero,np.zeros(n.circulation_basis.panels),apply_forcing=False)
        _,data=n.residual(x,detail=True,**options);f.initialize(state,data)
        restore_feedback(n,f,state,saved,preserve_commands=True)
    elif saved.get('feedback') is not None:raise AnalysisError('Saved controller definition is missing.')
    options=system.options(state,zero,zero,np.zeros(n.circulation_basis.panels),apply_forcing=False)
    residual,data=n.residual(x,detail=True,**options)
    if f is not None:residual=np.r_[residual,f.evaluate(state,data,np.zeros(f.size))[0]]
    error=float(np.max(abs(residual)))
    if not np.isfinite(error) or error>1e-7:raise AnalysisError(f'Saved equilibrium is inconsistent ({error:.3g}).')
    return n,state,options,data,error


def _inside_bodies(points,meshes):
    inside=np.zeros(len(points),dtype=bool)
    for mesh in meshes:
        if mesh.beam.lifting:continue
        for a,b,t0,t1 in zip(mesh.r0,mesh.r1,mesh.t0,mesh.t1):
            d=b-a;length2=d@d
            if length2<=0:continue
            fraction=(points-a)@d/length2
            radial=points-a-fraction[:,None]*d
            radius=mesh.beam.value('radius',t0+np.clip(fraction,0,1)*(t1-t0))
            inside|=(fraction>=0)&(fraction<=1)&(radius>0)&(np.linalg.norm(radial,axis=1)<=radius)
    return inside


def survey(model,*,positions=None,plane=None,coordinates='body',condition=None,panels=8,
           equilibrium_state=None,checkpoint=None,circulation=None):
    """Sample one rigid, saved-steady or checkpoint state; inputs remain owned by the caller."""
    if coordinates not in ('body','earth'):raise AnalysisError('Survey coordinates must be body or earth.')
    if (positions is None)==(plane is None):raise AnalysisError('Specify survey positions or a plane, but not both.')
    if equilibrium_state is not None and checkpoint is not None:raise AnalysisError('Select one saved flow state.')
    if (equilibrium_state is not None or checkpoint is not None) and (condition is not None or circulation is not None):
        raise AnalysisError('A saved flow state supplies its own condition and circulation.')
    error=None;options={};data=None;n=None
    if checkpoint is not None:
        n,_,state,_,options,data,error,_=restore_checkpoint(model,checkpoint)
        kind='time_checkpoint'
    elif equilibrium_state is not None:
        n,state,options,data,error=_steady(model,equilibrium_state);kind='saved_equilibrium'
    else:
        c=read_condition(condition,saved=False) if isinstance(condition,dict) else condition
        c=FlightCondition() if c is None else c
        meshes=model_meshes(model,panels);kind='rigid' if circulation is None else 'prescribed_circulation'
    if data is not None:
        c=data['condition'];meshes=data['meshes'];circulation=state.gamma
        if c is None:raise AnalysisError('This checkpoint has no aerodynamic flight condition.')
    _validate(model,c)
    points,grid=(np.asarray(positions,dtype=float),None) if plane is None else plane_grid(plane)
    if points.ndim!=2 or points.shape[1]!=3 or not 1<=len(points)<=10000 or not np.all(np.isfinite(points)):
        raise AnalysisError('A survey requires 1 to 10000 finite xyz positions.')
    rotation=body_to_earth(c.attitude);origin=np.asarray(c.position_earth)
    body=points if coordinates=='body' else (points-origin)@rotation
    args={}
    if data is not None:
        r,Q=data['r'],data['Q'];ids=[n.node(*row[2:4]) for row in n.engines]
        args=dict(point_positions=n.point_positions(r,Q),engine_positions=[r[i]+Q[i]@(row[4:7]-n.rj[i]) for row,i in zip(n.engines,ids)],
            engine_rotations=Q[ids],local_motion=data['local_motion'],circulation_rate=options.get('circulation_rate'),
            circulation_basis=n.circulation_basis,frozen_influences=n.frozen_influences,
            sensor_positions=[r[i]+Q[i]@(row[3:6]-n.rj[i]) for row in model.records.get('sensor',[]) for i in [n.node(*row[1:3])]])
    aero=evaluate_aerodynamics(model,c,meshes,circulation,survey_positions=body,**args);flow=aero['flow_survey']
    values={key:np.asarray(value) for key,value in flow['velocity_body'].items()}
    if coordinates=='earth':values={key:value@rotation.T for key,value in values.items()}
    inside=_inside_bodies(body,meshes);fluid=np.asarray(flow['fluid_side']);valid=fluid&~inside
    result=dict(analysis='flow_survey',state_kind=kind,coordinates=coordinates,time=c.time,position=points.tolist(),
        position_body=body.tolist(),position_earth=(body@rotation.T+origin).tolist(),plane=grid,
        velocity={key:value.tolist() for key,value in values.items()},valid=valid.tolist(),inside_body=inside.tolist(),
        fluid_side=fluid.tolist(),condition=portable(asdict(c)),wake_core=aero['wake_core'],
        aerodynamic_influences=aero['aerodynamic_influences'],saved_state_residual=error,
        units=dict(position='input L',velocity='input L/T',time='input T'),
        limitations=[flow['reference'],flow['wake'],flow['vortex_core'],
            'Samples inside circular body segments or beyond the ground plane are masked. Vortex/source cores regularize the external field; they do not resolve interior fluid or boundary layers.']+aero['ground_plane']['limitations'])
    if aero['body_shoulders']:
        from .body_shoulders import LIMITATION
        result['limitations'].append(LIMITATION)
    if c.gust is not None:
        from .gust import LIMITATIONS
        result['limitations']+=LIMITATIONS
    if grid is not None:
        axes=np.array([grid['direction'],grid['transverse'],grid['normal']])
        result['plane_velocity']={key:(value@axes.T).tolist() for key,value in values.items()}
    return result
