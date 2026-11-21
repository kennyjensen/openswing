"""Physical engine-command columns composed before loaded-force subtraction.

Engine and jet partials are refined locally, then passed through the shared
analytic circulation/load/transfer Jacobian. The same jet partials supply
output recovery. Branches or contexts without this complete chain fall back.
"""
import numpy as np
from .circulation_tangent import flow_load_columns, resolved, CirculationDerivativeUnavailable
from .output_fields import Capture, context, check_jets, FieldUnavailable
from .structured_static import acceleration_load_constraints, StructuredTangentUnavailable
from .propulsion import engine_load, jet_velocity


class PowerDerivativeUnavailable(ValueError):
    pass


def fourth(values, h):
    return (8*(values[0]-values[1])-(values[2]-values[3]))/(12*h)


class EnginePowerDerivative:
    def __init__(self, fields, index, command, step, scale):
        self.fields=fields;self.data=data=fields.circulation_aero
        self.index=index;self.steps=[];self.states=[]
        self.force=np.zeros((3,1));self.moment=np.zeros((3,1))
        row=data['engine_rows'][index];engine=data['engines'][index]
        if int(row[0])!=command:return
        setting=data['condition'].powers.get(command,0.)
        rotation=None if data['engine_rotations'] is None else data['engine_rotations'][index]
        derivatives=[]
        for h in (step*scale,step*scale/3):
            try:
                samples=[engine_load(row,setting+factor*h,data['rho'],data['engine_points'][index],
                    data['engine_velocity'][index],data['engine_rates'][index],rotation)
                    for factor in (1,-1,2,-2)]
            except ValueError as exc:
                raise PowerDerivativeUnavailable('Engine-command perturbation: '+str(exc)) from exc
            if any(value['power_clipped']!=engine['power_clipped'] for value in samples):
                raise PowerDerivativeUnavailable('Engine command stencil crosses power clipping.')
            self.steps.append(h);self.states.append(samples)
            derivatives.append(fourth([np.r_[v['force'],v['moment']] for v in samples],h))
        value=resolved(*derivatives,'Engine-command load derivative')
        self.force=value[:3,None];self.moment=value[3:,None]

    def jet(self, name, points):
        data=self.data;engine=data['engines'][self.index]
        if not self.states or not engine['jet_enabled']:return np.zeros(points.shape+(1,))
        derivatives=[]
        for h,samples in zip(self.steps,self.states):
            values=[]
            for value in samples:
                engines=list(data['engines']);engines[self.index]=value
                check_jets(self.fields.jet_regions,False,name,points,engines,data['jet_direction'],data['rho'])
                try:values.append(jet_velocity(points,[value],data['jet_direction'],data['rho']))
                except ValueError as exc:
                    raise PowerDerivativeUnavailable('Engine-command jet perturbation: '+str(exc)) from exc
            derivatives.append(fourth(values,h))
        return resolved(*derivatives,'Engine-command jet derivative')[...,None]


class PowerFlow:
    def __init__(self, fields, command, step, scale):
        data=fields.circulation_aero
        self.sample=np.zeros((len(data['gamma']),1))
        self.engines=[EnginePowerDerivative(fields,i,command,step,scale)
            for i in range(len(data['engines']))]

    def velocity(self, name, points):
        result=np.zeros(points.shape+(1,))
        # ASWING engine inflow has vortex/volume flow; jets act downstream.
        if name!='engine':
            for engine in self.engines:result+=engine.jet(name,points)
        return result


def power_column(system, channel, step, field_tangent=None):
    n=system.network
    if (system.feedback is not None or n.condition is None or not acceleration_load_constraints(n)
            or n.iteration_fields is not None or channel.kind!='power'):
        raise PowerDerivativeUnavailable('Engine command requires full physical input stencils.')
    if not np.isfinite(step*channel.scale) or step*channel.scale<=0:
        raise PowerDerivativeUnavailable('Invalid engine-command difference scale.')
    fields=Capture(full=True);zero=np.zeros(system.size)
    try:
        with context(system,fields):system.residual(zero,zero)
        data=fields.circulation_aero
        if data is None:raise PowerDerivativeUnavailable('Missing engine-command load capture.')
        flow=PowerFlow(fields,channel.index,step,channel.scale)
        column=np.zeros(system.size,dtype=complex)
        column[:n.size]=flow_load_columns(n,fields,flow,1.)[:,0]
        field_column=None
        if field_tangent is not None and field_tangent.active and field_tangent.matrix is not None:
            from .volume import body_quadrature
            positions={key:data['p']['rm' if key=='axis' else key] for key in ('cp','hv','axis')}
            positions['engine']=data['engine_points']
            for mesh,_ in data['bodies']:positions['body',mesh.beam.index]=body_quadrature(mesh)[1].reshape(-1,3)
            for i,(point,_,_) in enumerate(data['points']):positions['point',i]=np.asarray(point).reshape(1,3)
            for row in data['shoulders']:positions['shoulder',row['beam'],row['t']]=np.asarray(row['position']).reshape(1,3)
            field_column=field_tangent.flatten({key:flow.velocity(key,positions[key])[...,0]
                for key in field_tangent.keys}).astype(complex)
            field_column.flags.writeable=False
        return column,field_column
    except (CirculationDerivativeUnavailable,StructuredTangentUnavailable,FieldUnavailable) as exc:
        raise PowerDerivativeUnavailable(str(exc)) from exc
