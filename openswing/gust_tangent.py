"""Harmonic gust columns from prescribed velocity and shared load partials."""
from dataclasses import replace
import numpy as np
from .gust import gust_field
from .circulation_tangent import EngineDerivative,flow_load_columns,CirculationDerivativeUnavailable
from .output_fields import Capture,context,check_jets,FieldUnavailable
from .structured_static import acceleration_load_constraints,StructuredTangentUnavailable
from .propulsion import engine_load


class GustDerivativeUnavailable(ValueError):
    pass


class GustFlow:
    def __init__(self, fields, channel, omega, step):
        self.fields=fields;self.data=data=fields.circulation_aero
        self.sample=np.zeros((len(data['gamma']),2))
        forcing,_=channel.at_frequency(omega)
        # The generated harmonic input is linear in its amplitude. Evaluate
        # that field alone using its original expression and Earth/body maps,
        # before adding the loaded background velocity.
        conditions=[forcing(part,1.)(None,dict(condition_override=replace(data['condition'],gust=None)))['condition_override']
            for part in (0,1)]
        self.gusts=[gust_field(c.gust) for c in conditions]
        incoming=self.free(data['engine_points'])
        self.engines=[EngineDerivative(data,i,incoming[i]) for i in range(len(data['engines']))]
        self.engine_trials=[]
        # Preserve the original finite input stencil's clipping/jet guards,
        # as well as the locally refined axial-inflow partials.
        for part in (0,1):
            for multiplier in (1,-1,2,-2):
                engines=[]
                for i,row in enumerate(data['engine_rows']):
                    rotation=None if data['engine_rotations'] is None else data['engine_rotations'][i]
                    value=engine_load(row,data['condition'].powers.get(int(row[0]),0.),data['rho'],
                        data['engine_points'][i],data['engine_velocity'][i]+multiplier*step*channel.scale*incoming[i,:,part],
                        data['engine_rates'][i],rotation)
                    if value['power_clipped']!=data['engines'][i]['power_clipped']:
                        raise GustDerivativeUnavailable('Harmonic gust stencil crosses engine clipping.')
                    engines.append(value)
                self.engine_trials.append(engines)

    def free(self, points):
        return np.stack([g.body_velocity(points,self.data['condition']) for g in self.gusts],axis=-1)

    def induced(self, name, points):
        result=np.zeros(points.shape+(2,))
        if name=='engine':return result
        d=self.data
        for trial in self.engine_trials:
            check_jets(self.fields.jet_regions,False,name,points,trial,d['jet_direction'],d['rho'])
        for i,engine in enumerate(self.engines):
            for pair in engine.states:
                for value in pair:
                    trial=list(d['engines']);trial[i]=value
                    check_jets(self.fields.jet_regions,False,name,points,trial,d['jet_direction'],d['rho'])
            result+=engine.jet(points)
        return result

    def velocity(self, name, points):
        return self.free(points)+self.induced(name,points)


def gust_column(system,channel,omega,step,field_tangent=None):
    n=system.network
    if (system.feedback is not None or n.condition is None or not acceleration_load_constraints(n)
            or n.iteration_fields is not None or channel.kind!='gust'):
        raise GustDerivativeUnavailable('Gust input requires full physical stencils.')
    if not np.isfinite(step*channel.scale) or step*channel.scale<=0:
        raise GustDerivativeUnavailable('Invalid gust difference scale.')
    fields=Capture(full=True);zero=np.zeros(system.size)
    try:
        with context(system,fields):system.residual(zero,zero)
        data=fields.circulation_aero
        if data is None:raise GustDerivativeUnavailable('Missing gust load capture.')
        flow=GustFlow(fields,channel,omega,step)
        block=flow_load_columns(n,fields,flow,1.)
        column=np.zeros(system.size,dtype=complex);column[:n.size]=block[:,0]+1j*block[:,1]
        field_column=None
        if field_tangent is not None and field_tangent.active and field_tangent.matrix is not None:
            from .volume import body_quadrature
            positions={key:data['p']['rm' if key=='axis' else key] for key in ('cp','hv','axis')}
            positions['engine']=data['engine_points']
            for mesh,_ in data['bodies']:positions['body',mesh.beam.index]=body_quadrature(mesh)[1].reshape(-1,3)
            for i,(point,_,_) in enumerate(data['points']):positions['point',i]=np.asarray(point).reshape(1,3)
            for row in data['shoulders']:positions['shoulder',row['beam'],row['t']]=np.asarray(row['position']).reshape(1,3)
            values={}
            for key in field_tangent.keys:
                value=flow.induced(key,positions[key]);values[key]=value[...,0]+1j*value[...,1]
            # Prescribed gust velocity is still applied by the local physical
            # output evaluator. Retain only its induced jet response here.
            field_column=field_tangent.flatten(values);field_column.flags.writeable=False
        return column,field_column
    except (CirculationDerivativeUnavailable,StructuredTangentUnavailable,FieldUnavailable) as exc:
        raise GustDerivativeUnavailable(str(exc)) from exc
