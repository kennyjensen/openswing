"""Retained nonlocal part of the physical output derivative.

The full moving-source field derivative is retained from A construction, not
lagged or omitted. Original local output stencils still include rate loads,
geometry, engines and sensors. Unsupported captures use the physical path.
"""
from contextlib import contextmanager
import numpy as np
from scipy.sparse import csc_matrix,hstack
from .structured_static import IterationFields,StructuredTangentUnavailable
from .circulation_tangent import CirculationDerivativeUnavailable


class FieldUnavailable(ValueError):
    pass


class Capture(IterationFields):
    def __init__(self, *, full=False, jet_regions=None):
        super().__init__()
        self.capture_circulation=full
        self.capture_rate_fields=full
        self.jet_regions={} if jet_regions is None else jet_regions
        self.capture_jets=jet_regions is None

    def observe_jet(self,name,points,engines,direction,density):
        check_jets(self.jet_regions,self.capture_jets,name,points,engines,direction,density)

    def fixed_geometry(self,key,compute):
        return compute()

    def get(self,key,compute):
        # Sensor receivers have no persistent query identity.
        if key[1] is None:return compute()
        try:return super().get(key,compute)
        except StructuredTangentUnavailable as exc:raise FieldUnavailable(str(exc)) from exc


@contextmanager
def context(system,fields):
    n=system.network
    if n.iteration_fields is not None:
        raise FieldUnavailable('Output field capture requires unowned iteration fields.')
    n.iteration_fields=fields;n.aero_key=None
    try:yield
    finally:n.iteration_fields=None;n.aero_key=None


def state_condition(system,z,rate,forcing=None):
    state,_,options=system.physical_state(z,rate,forcing)
    c,_,_=system.network.operating.apply(state.x[system.network.operating_start:],
        condition_override=options['condition_override'],motion_override=options['motion_override'])
    if c is None or not np.isfinite(c.speed) or c.speed<=0:
        raise FieldUnavailable('No positive finite aerodynamic speed.')
    return state,c


def check_jets(regions,capture,name,points,engines,direction,density):
    from .propulsion import jet_profile
    if name is None:return
    for i,engine in enumerate(engines):
        if not engine['jet_enabled']:continue
        relative=np.asarray(points)-engine['position'];downstream=relative@direction
        radial=relative-downstream[...,None]*direction
        outer=jet_profile(engine,downstream,density)[1]
        active=(downstream>0)&(np.linalg.norm(radial,axis=-1)<outer)
        key=(name,i)
        if capture:regions[key]=(active.copy(),radial.copy())
        else:
            if key not in regions:raise FieldUnavailable('Changed powered-jet receiver layout.')
            previous,before=regions[key]
            if np.any(active!=previous) or (engine['torque']!=0 and np.any(
                    active&previous&(np.sum(radial*before,axis=-1)<=0))):
                raise FieldUnavailable('Output stencil crosses a powered jet boundary or swirl axis.')


class FieldTangent:
    def __init__(self,system,step,*,limit=128*1024**2):
        from .equilibrium_tangent import identity
        self.owner,self.step,self.limit=system,step,limit
        self.signature=identity(system)
        self.reason=None;self.matrix=None;self.columns={};self.bytes=0
        self.base={};self.values={};self.pending=set();self.rows=0
        n=system.network
        if system.feedback is not None or n.condition is None or n.operating.custom:
            raise FieldUnavailable('Output field reuse requires an aerodynamic base without custom constraints or controllers.')
        zero=np.zeros(system.size);fields=Capture(full=True)
        with context(system,fields):system.residual(zero,zero)
        data=fields.circulation_aero
        if data is None:raise FieldUnavailable('No captured aerodynamic source fields.')
        self.base=fields.values
        self.jet_regions=fields.jet_regions
        self.jet_bytes=sum(v.nbytes for pair in self.jet_regions.values() for v in pair)
        self.gamma=data['gamma'].copy();self.speed=data['condition'].speed
        self.axis_irrelevant=not np.any(data['rates'])
        self.values=self.vectors(fields,system,zero,zero)
        self.keys=sorted(self.values,key=repr)
        self.breaks=np.r_[0,np.cumsum([self.values[k].size for k in self.keys])]
        self.rows=int(self.breaks[-1])
        self.bytes=sum(v.nbytes for v in self.base.values())+sum(v.nbytes for v in self.values.values())+self.gamma.nbytes+self.breaks.nbytes+self.jet_bytes
        nodes={n.node(*row[2:4]) for row in n.engines}
        velocity=[system.velocity_start+part*3*n.nn+3*node+axis for node in nodes for part in (0,1) for axis in range(3)]
        self.pending=set(map(int,np.r_[np.arange(6*n.nn),np.arange(n.gamma_start,n.size),velocity,np.arange(system.frame_start,system.size)]))
        if self.bytes>limit:raise FieldUnavailable('Output field storage exceeds its budget.')
        if n.ng:
            from .circulation_tangent import FlowDerivative
            from .volume import body_quadrature
            flow=FlowDerivative(n,fields,data)
            positions={key:data['p']['rm' if key=='axis' else key] for key in ('cp','hv','axis')}
            positions['engine']=data['engine_points']
            for mesh,_ in data['bodies']:positions['body',mesh.beam.index]=body_quadrature(mesh)[1].reshape(-1,3)
            for i,(point,_,_) in enumerate(data['points']):positions['point',i]=np.asarray(point).reshape(1,3)
            for row in data['shoulders']:positions['shoulder',row['beam'],row['t']]=np.asarray(row['position']).reshape(1,3)
            values={key:(flow.vortex(key) if key=='engine' else flow.velocity(key,positions[key])) for key in self.keys}
            for k,j in enumerate(range(n.gamma_start,n.operating_start)):
                self.save(j,self.flatten({key:value[...,k] for key,value in values.items()}))
        for values in (*self.base.values(),*self.values.values(),self.gamma,self.breaks):values.setflags(write=False)

    @property
    def active(self):return self.reason is None

    def matches(self,system,step):
        from .equilibrium_tangent import identity
        return self.active and self.owner is system and self.step==step and self.signature==identity(system)

    def disable(self,reason):
        self.reason=str(reason);self.columns.clear();self.base.clear();self.values.clear()
        self.jet_regions.clear()
        self.pending.clear();self.matrix=None;self.bytes=0

    def save(self,j,value):
        if not self.active:return
        column=csc_matrix(np.asarray(value).reshape(self.rows,1))
        if j not in self.pending or not np.all(np.isfinite(column.data)):
            raise FieldUnavailable('Incomplete or repeated output field derivative column.')
        storage=sum(v.nbytes for v in (column.data,column.indices,column.indptr))
        if self.bytes+storage>self.limit:raise FieldUnavailable('Output field storage exceeds its budget.')
        self.columns[j]=column;self.bytes+=storage;self.pending.remove(j)

    def geometry_columns(self,selected,gradients):
        if not self.active:return
        try:
            for offset,j in enumerate(selected):
                values={}
                for key in self.keys:
                    if key in gradients:values[key]=gradients[key][...,offset]
                    elif key=='axis' and self.axis_irrelevant:values[key]=np.zeros_like(self.values[key])
                    else:raise FieldUnavailable('Missing moving output field derivative.')
                self.save(j,self.flatten(values))
        except FieldUnavailable as exc:self.disable(exc)

    def vectors(self,fields,system,z,rate,forcing=None):
        state,c=state_condition(system,z,rate,forcing)
        values={}
        for kind,key in fields.values:
            if kind!='volume':continue
            volume=fields.values['volume',key].reshape(-1,3)
            vortex=fields.values['vortex',key].apply(state.gamma)
            jet=fields.values.get(('jet',key),np.zeros_like(volume)).reshape(-1,3)
            values[key]=c.speed*volume+vortex+jet
        if self.values and 'axis' in self.values and 'axis' not in values and self.axis_irrelevant:
            values['axis']=self.values['axis']
        return values

    def flatten(self,values):
        if set(values)!=set(self.keys):raise FieldUnavailable('Changed aerodynamic receiver layout.')
        return np.concatenate([values[k].ravel() for k in self.keys])

    def probe(self,evaluate,z,rate,forcing=None):
        if not self.active:return evaluate(),None
        fields=Capture(jet_regions=self.jet_regions)
        try:
            with context(self.owner,fields):result=evaluate()
            values=self.flatten(self.vectors(fields,self.owner,z,rate,forcing))
            return result,values
        except FieldUnavailable as exc:
            self.disable(exc)
            return evaluate(),None

    def finish(self):
        if not self.active or self.matrix is not None:return
        if self.pending:
            self.disable('Missing output field derivative columns.');return
        self.matrix=hstack([self.columns.get(j,csc_matrix((self.rows,1))) for j in range(self.owner.size)],format='csc')
        self.columns.clear()
        self.bytes=sum(v.nbytes for v in (*self.base.values(),*self.values.values(),self.gamma,self.breaks,self.matrix.data,self.matrix.indices,self.matrix.indptr))+self.jet_bytes
        if self.bytes>self.limit:
            self.disable('Output field storage exceeds its budget.');return
        for value in (self.matrix.data,self.matrix.indices,self.matrix.indptr):value.flags.writeable=False

    def input_column(self,forcing):
        packet=getattr(forcing,'_output_fields',None)
        if packet is None or packet[0] is not self or packet[1]!=self.step:return None
        return packet[2]

    def snapshot(self,z,rate,*,forcing=None,input_delta=0.,linear_output=False):
        if not self.active or self.matrix is None:return self.owner.snapshot(z,rate,forcing=forcing,linear_output=linear_output)
        try:
            fields=Replay(self,z,rate,forcing,self.matrix@z+input_delta)
            with context(self.owner,fields):return self.owner.snapshot(z,rate,forcing=forcing,linear_output=linear_output)
        except FieldUnavailable as exc:
            self.disable(exc)
            return self.owner.snapshot(z,rate,forcing=forcing,linear_output=linear_output)

    def report(self):
        return dict(method='retained full moving-source derivatives with local physical output stencils' if self.active and self.matrix is not None else 'full physical output stencils',
                    field_rows=self.rows,cached_bytes=self.bytes,fallback=self.reason)


class Replay:
    phase='output_linear';capture_circulation=False;capture_rate_fields=True
    def __init__(self,owner,z,rate,forcing,delta):
        self.owner=owner
        state,c=state_condition(owner.owner,z,rate,forcing)
        self.speed=c.speed;self.dspeed=c.speed-owner.speed;self.dgamma=state.gamma-owner.gamma
        self.delta={k:delta[a:b].reshape(owner.values[k].shape) for k,a,b in zip(owner.keys,owner.breaks[:-1],owner.breaks[1:])}

    def fixed_geometry(self,key,compute):return compute()

    def observe_jet(self,name,points,engines,direction,density):
        check_jets(self.owner.jet_regions,False,name,points,engines,direction,density)

    def get(self,key,compute):
        if key[1] is None:return compute()
        if key not in self.owner.base:raise FieldUnavailable('Uncaptured output field receiver.')
        kind,name=key;base=self.owner.base[key]
        if kind!='volume':return base.copy()
        correction=self.delta[name]-self.owner.base['vortex',name].apply(self.dgamma)
        correction-=self.dspeed*base.reshape(-1,3)
        return base+correction.reshape(base.shape)/self.speed
