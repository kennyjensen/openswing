"""Pass-through capture of one prescribed-state full native aero evaluation.

No trim, pencil, harmonic solve, circulation solve or added field evaluation.
The observation context forwards each original call and returns its object.
Native sampled velocities/field strengths are comparison targets, not inputs
to the independent physical evaluator.
"""
from contextlib import contextmanager
from dataclasses import asdict,replace
import time
import numpy as np


def copied(value):
    if isinstance(value,np.ndarray):return value.copy()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {key:copied(v) for key,v in value.items()}
    if isinstance(value,(list,tuple)):return [copied(v) for v in value]
    return value


def local_fields(local):
    return None if local is None else {key:copied(getattr(local,key)) for key in
        ('origin','velocity','rates','acceleration','rate_derivative')}


def mesh_fields(mesh):
    return dict(beam=mesh.beam.index,physical=mesh.beam.physical_index,lifting=bool(mesh.beam.lifting),
        **{key:copied(getattr(mesh,key)) for key in
           ('t0','t1','tm','ts','r0','r1','rm','frames','length','frame0','frame1')})


def fixed_fixture(system,model_source):
    """Fixed parsed material/mesh inputs. Does not evaluate an aircraft residual."""
    from openswing.volume import _GAUSS
    n=system.network;u=(_GAUSS[0]+1)/2;w=_GAUSS[1]/2
    beams=[]
    for mesh in n.meshes:
        b=mesh.beam;sl=n.beam_elements[b.index];nodes=n.beam_nodes[b.index]
        keys=['chord','Xax','dCLda','CLmin','CLmax','Cdf','Cdp','Cm','alpha'] if b.lifting else ['radius','Cdf','Cdp']
        keys += [f'dC{kind}dF{k}' for k in sorted(n.model.controls) for kind in ('L','M','D')]
        material={key:b.value(key,mesh.tm) for key in keys}
        endpoints={side:{key:b.value(key,t,side=side) for key in ('chord','Xax')} for side,t in
            (('right',mesh.t0),('left',mesh.t1))} if b.lifting else {}
        body=None
        if not b.lifting:
            t=mesh.t0[:,None]+(mesh.t1-mesh.t0)[:,None]*u
            body=dict(u=u.copy(),weights01=w.copy(),t=t,radius=b.value('radius',t),
                dradius_dt=b.value('radius',t,derivative=1),Cdf=b.value('Cdf',t),Cdp=b.value('Cdp',t))
        beams.append(dict(index=b.index,physical=b.physical_index,lifting=bool(b.lifting),
            node_ids=nodes.copy(),element_ids=np.arange(n.ne)[sl],stations=n.station_nodes[b.index][0].copy(),
            original_mesh=mesh_fields(mesh),fraction=n.fractions[b.index].copy(),
            jig_nodes=n.rj[nodes].copy(),R0a=n.R0a[sl].copy(),R0b=n.R0b[sl].copy(),
            offa=n.offa[sl].copy(),offb=n.offb[sl].copy(),material_receiver=material,
            material_endpoints=endpoints,body_quadrature=body,
            distributions={key:dict(t=d.t.copy(),values=d.values.copy()) for key,d in b.distributions.items()}))
    attachments={}
    for kind,start,position in (('weight',0,slice(2,5)),('engine',2,slice(4,7)),('sensor',1,slice(3,6))):
        attachments[kind]=[dict(index=i,node=n.node(*row[start:start+2]),row=np.array(row).copy(),
            offset=np.array(row[position])-n.rj[n.node(*row[start:start+2])])
            for i,row in enumerate(n.model.records.get(kind,[]))]
    return dict(schema='daedalus-full-aero-inputs-v1',model_source=model_source,
        constants=np.array(n.model.constants).copy(),reference=np.array(n.model.reference).copy(),
        records={key:np.array(value).copy() for key,value in n.model.records.items()},
        beams=beams,attachments=attachments,ends=n.ends.copy(),
        scales=dict(L=n.L,F=n.F,V=system.V,W=system.W,Gamma_scale=n.gamma_scale),
        loaded_base=dict(x=system.base.copy(),r=system.r0.copy(),Q=system.Q0.copy(),
            U=system.U0.copy(),Omega=system.Omega0.copy(),attitude_deg=system.attitude.copy(),
            position=system.position.copy(),orientation=system.R0.copy()),
        notes=['Material parser/spline inputs accepted; independent evaluator reconstructs motion and flow.',
               'body_quadrature.weights01 integrate [0,1]; lifting receiver fractions are fixed material fractions.',
               'Current mesh frames are native comparison targets; raw node poses and jig frames define independent geometry.',
               'Reference rows: area/length scales, moment origin, acceleration reference, velocity reference.'])


class Observer:
    """No cache or replay: each query evaluates its original callable once."""
    phase='observe'
    capture_circulation=False
    capture_frame_loads=False
    capture_rate_fields=False
    omit_strut_loads=False
    omit_stationary_mechanics=False

    def __init__(self):
        self.fixed={};self.fields=[];self.incident=[];self.jet_queries=[]

    def fixed_geometry(self,key,compute):
        value=compute()
        if key=='lifting_geometry':self.fixed[key]=copied(value)
        if key=='volume_field':
            self.fixed[key]={name:copied(getattr(value,name)) for name in
                ('pg','positions','sources','doublets','cores','owners','points','is_image','body_shoulders','shoulders')}
        return value

    def get(self,key,compute):
        value=compute()
        self.fields.append(dict(key=copied(key),value=copied(value) if isinstance(value,np.ndarray) else None))
        return value

    def incident_velocity(self,key,value):
        self.incident.append(dict(key=copied(key),value=value.copy()))
        return value

    def observe_jet(self,key,points,engines,direction,density):
        self.jet_queries.append(dict(key=copied(key),points=points.copy(),direction=direction.copy(),
            density=float(density),engines=copied(engines)))


@contextmanager
def observe_calls(network):
    """Capture calls already made by the original residual; no extra calls."""
    import openswing.aero as aero
    previous=network.iteration_fields
    assert previous is None and network.tangent_influences is None
    observer=Observer();network.iteration_fields=observer
    originals={key:getattr(aero,key) for key in ('engine_load','body_loads','surface_apparent_loads')}
    records=dict(engine=[],body=[],surface_apparent=[])
    def engine(row,power,density,position,velocity,mount_rate=(0.,0.,0.),rotation=None):
        value=originals['engine_load'](row,power,density,position,velocity,mount_rate,rotation)
        records['engine'].append(dict(row=copied(row),power=power,density=density,position=copied(position),
            velocity=copied(velocity),mount_rate=copied(mount_rate),rotation=copied(rotation),output=copied(value)))
        return value
    def body(mesh,density,velocity,motion,acceleration_reference,added_mass_factor=1.,*,local_motion=None):
        value=originals['body_loads'](mesh,density,velocity,motion,acceleration_reference,added_mass_factor,local_motion=local_motion)
        records['body'].append(dict(beam=mesh.beam.index,density=density,velocity=copied(velocity),
            motion=copied(asdict(motion)),acceleration_reference=copied(acceleration_reference),
            added_mass_factor=added_mass_factor,local_motion=local_fields(local_motion),output=copied(value)))
        return value
    def surface(position,frames,chord,xax,length,density,velocity,motion,acceleration_reference,*,local_motion=None):
        value=originals['surface_apparent_loads'](position,frames,chord,xax,length,density,velocity,motion,acceleration_reference,local_motion=local_motion)
        records['surface_apparent'].append(dict(position=copied(position),frames=copied(frames),chord=copied(chord),
            xax=copied(xax),length=copied(length),density=density,velocity=copied(velocity),
            motion=copied(asdict(motion)),acceleration_reference=copied(acceleration_reference),
            local_motion=local_fields(local_motion),force=copied(value[0]),moment=copied(value[1])))
        return value
    aero.engine_load=engine;aero.body_loads=body;aero.surface_apparent_loads=surface
    try:yield observer,records
    finally:
        for key,value in originals.items():setattr(aero,key,value)
        network.iteration_fields=previous


def capture(system,z,zdot,control3_delta=0.):
    """Exactly one detailed residual at prescribed physical state and Gamma."""
    n=system.network;z=np.asarray(z);zdot=np.asarray(zdot)
    assert z.shape==zdot.shape==(system.size,) and np.isfinite(z).all() and np.isfinite(zdot).all()
    def forcing(state,options):
        c=options['condition_override'];controls=dict(c.controls)
        controls[3]=controls.get(3,0.)+control3_delta
        return dict(options,condition_override=replace(c,controls=controls))
    state,attitude,options=system.physical_state(z,zdot,forcing)
    before=n.nfev
    with observe_calls(n) as (observer,observed):
        started=time.monotonic()
        residual,data=n.residual(state.x,detail=True,**options)
        residual_seconds=time.monotonic()-started
    assert n.nfev==before+1
    actual_condition=data['condition'];actual_motion=data['motion']
    assert actual_condition is not None and data['aero']['circulation_solver']['method']=='prescribed'
    attachments={}
    for kind,start,position in (('weight',0,slice(2,5)),('engine',2,slice(4,7)),('sensor',1,slice(3,6))):
        attachments[kind]=[]
        for i,row in enumerate(n.model.records.get(kind,[])):
            node=n.node(*row[start:start+2]);point=state.r[node]+state.Q[node]@(row[position]-n.rj[node])
            attachments[kind].append(dict(index=i,node=node,position=point,deformation_rotation=state.Q[node].copy(),
                local_motion=local_fields(data['local_motion'].point(kind,i))))
    input_state=dict(r=state.r.copy(),Q=state.Q.copy(),u=state.u.copy(),w=state.w.copy(),
        udot=options['elastic_motion'][2].copy(),wdot=options['elastic_motion'][3].copy(),
        gamma=state.gamma.copy(),gamma_dot=options['circulation_rate'].copy(),
        frame=dict(U=state.U.copy(),Omega=state.Omega.copy(),position=state.position.copy(),orientation=state.orientation.copy(),
            attitude_deg=np.asarray(attitude).copy(),Udot=system.Udot0+system.V*zdot[system.frame_start:system.frame_start+3],
            Omegadot=system.Omegadot0+system.W*zdot[system.frame_start+3:system.frame_start+6]),
        condition=copied(asdict(actual_condition)),motion=copied(asdict(actual_motion)),gravity=data['gravity'].copy(),
        wind=actual_condition.vectors()[0].copy(),atmosphere=copied(data['aero']['atmosphere']),
        flow=dict(speed=float(actual_condition.speed),wind=actual_condition.vectors()[0].copy(),
            density=float(data['aero']['atmosphere']['density']),sound_speed=float(data['aero']['atmosphere']['sound_speed']),
            mach=float(data['aero']['mach']),controls=copied(actual_condition.controls),powers=copied(actual_condition.powers)),
        meshes=[mesh_fields(mesh) for mesh in data['meshes']],attachments=attachments)
    native=dict(residual=residual.copy(),aero=copied(data['aero']),observed_calls=observed,
        observed_geometry=observer.fixed,observed_fields=observer.fields,
        observed_incident=observer.incident,observed_jet_queries=observer.jet_queries,
        nodal_force=data['force'].copy(),nodal_moment=data['moment'].copy(),
        element_forces=data['element_forces'].copy(),element_moments=data['element_moments'].copy(),
        operating_values=copied(data['operating_values']),operating_constraints=copied(data['operating_constraints']))
    return dict(schema='daedalus-full-aero-capture-v1',residual_seconds=residual_seconds,
        raw=dict(z=z.copy(),zdot=zdot.copy(),control3_delta=float(control3_delta)),
        inputs=input_state,native=native)


def selected_outputs(packet):
    """Numeric comparison arrays; force moments use the saved moment origin."""
    a=packet['native']['aero'];strips=a['strips'];engines=a['engines']
    out={key:np.asarray(a[key],dtype=float) for key in
        ('force','moment','point_forces','circulation_residual','engine_force','engine_moment',
         'surface_force','circulation_rate_force','circulation_rate_moment','body_force',
         'surface_apparent_force','apparent_force','apparent_moment')}
    for key in ('force','moment','apparent_force','apparent_moment'):
        out['strip_'+key]=np.array([s[key] for s in strips])
    out['strip_rate_force']=np.array([s.get('circulation_rate_force',[0.,0.,0.]) for s in strips])
    out['lifting_relative_velocity']=np.array([s['relative_velocity'] for s in strips if s['lifting']])
    out['engine_force_intrinsic']=np.array([e['force'] for e in engines]).reshape(-1,3)
    out['engine_moment_intrinsic']=np.array([e['moment'] for e in engines]).reshape(-1,3)
    return out


def physical_derivative_inputs(packet):
    """Only actual physical state/flow inputs; excludes observed targets."""
    p=packet['inputs']
    return {**{key:copied(p[key]) for key in ('r','Q','u','w','udot','wdot','gamma','gamma_dot')},
        'frame':copied(p['frame']),'motion':copied(p['motion']),'flow':copied(p['flow'])}
