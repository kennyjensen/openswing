"""Declarative user trim equations evaluated at the coupled physical trial.

ASWING 5.86 documents C_user1/C_user2 in GCON, with sensor targets as examples.
This is an original bounded expression interface, not a Fortran interpreter.
"""
from copy import copy
from contextlib import nullcontext
import re
import numpy as np
from .aero import AnalysisError
from .control_expressions import Expression
from .sensors import UNITS, measure_sensor, network_sensors
from .local_motion import LocalMotion
from .recovery import recover_structure


SENSOR_AXES = {field:('csn' if field in ('force_local','moment_local','strain','curvature_change') else 'xyz')
    for field in ('air_velocity_sensor','rates_sensor','acceleration_sensor','angular_acceleration_sensor',
        'position_earth','velocity_earth','anchor_position_body','anchor_velocity_body','position_body',
        'displacement_body','force_local','moment_local','strain','curvature_change')}
AERO_UNITS = dict.fromkeys(('CL','CY','CD','Cl','Cm','Cn'), 'dimensionless')
LOAD_UNITS = {f'{group}.{axis}':unit for group,unit in [('force','input F'),('moment','input F L')] for axis in 'xyz'}
# Only these fields are complete without section-load/strain recovery. Keep an
# explicit allowlist so new sensor fields retain the full reporting path.
MEASUREMENT_FIELDS = frozenset(('speed','alpha','beta','bank','elevation','heading',
    'air_velocity_sensor','rates_sensor','acceleration_sensor','angular_acceleration_sensor',
    'position_earth','velocity_earth','anchor_position_body','anchor_velocity_body',
    'position_body','displacement_body'))


class CustomEquation:
    def __init__(self, constraint, model, variables, condition):
        c=constraint
        if not re.fullmatch(r'user\.[A-Za-z][A-Za-z0-9_]{0,47}', c.quantity):
            raise AnalysisError('Custom quantity must be user.<name>, with a letter followed by letters, digits or underscores.')
        if (isinstance(c.residual_scale,(bool,np.bool_)) or not isinstance(c.residual_scale,(int,float,np.integer,np.floating))
                or not np.isfinite(c.residual_scale) or c.residual_scale<=0):
            raise AnalysisError('Custom constraint residual_scale must be a positive finite number in the expression units.')
        if not isinstance(c.unit,str) or not c.unit.strip() or len(c.unit)>80 or any(ord(v)<32 for v in c.unit):
            raise AnalysisError('Custom constraint needs a nonempty unit label of at most 80 characters.')
        self.expression=Expression(c.expression,accessors={'sensor','variable','load','aero'},names={'pi'},label='Custom trim')
        self.references=[];self.sensor_keys={}
        sensors={int(row[0]) for row in model.records.get('sensor',[])}
        for kind,key in dict.fromkeys(self.expression.references):
            if kind=='sensor':
                match=re.fullmatch(r'([1-9]\d*)\.([a-z_]+)(?:\.([a-z]))?',key)
                if not match or int(match[1]) not in sensors or match[2] not in UNITS:
                    raise AnalysisError(f'Unknown custom-trim sensor reference {key!r}; use index.field[.axis].')
                index,field,axis=int(match[1]),match[2],match[3]
                axes=SENSOR_AXES.get(field)
                if (axes is None and axis is not None) or (axes is not None and (axis is None or axis not in axes)):
                    raise AnalysisError(f'Custom-trim sensor {key!r} needs '+('no component.' if axes is None else f'a component from {axes}.'))
                self.sensor_keys[key]=(index,field,None if axes is None else axes.index(axis))
                unit=UNITS[field]
            elif kind=='variable':
                if key not in variables:raise AnalysisError(f'Unknown custom-trim operating variable {key!r}.')
                unit=('deg' if key in ('alpha','beta') or key.startswith('attitude.') else
                      'input L/T' if key=='speed' else 'rad/input T' if key.startswith('rates.') else
                      'rad/input T^2' if key.startswith('angular_acceleration.') else
                      'input L/T^2' if key.startswith('acceleration.') else 'input L' if key.startswith('position_earth.') else 'file setting/command units')
            else:
                units=LOAD_UNITS if kind=='load' else AERO_UNITS
                if key not in units or (kind=='aero' and condition is None):
                    raise AnalysisError(f'Unknown or unavailable custom-trim {kind} reference {key!r}.')
                unit=units[key]
            self.references.append(dict(kind=kind,name=key,unit=unit))

    def evaluate(self, sensors, values, loads, aero):
        # Resolve only the branch actually used. Missing strain or a singular
        # angle is never silently replaced by zero, even inside arithmetic.
        class SensorValues:
            def __getitem__(_, key):
                index,field,axis=self.sensor_keys[key]
                value=sensors[index][field]
                if value is not None and axis is not None:value=value[axis]
                if value is None or not np.isfinite(value):
                    raise AnalysisError(f'Custom-trim sensor {key!r} is undefined at this state; check sensor flow, angle singularities and section data.')
                return value
        return self.expression(dict(sensor=SensorValues(),variable=values,load=loads,aero=aero,pi=np.pi))


def evaluate_custom(network, data, values, force, moment):
    equations=network.operating.custom
    if not equations:return {}
    sensors={}
    requested={reference for eq in equations.values() for reference in eq.sensor_keys.values()}
    if requested and any(field not in MEASUREMENT_FIELDS for _,field,_ in requested):
        elements,_=recover_structure(network,data)
        sensors={s['index']:s for s in network_sensors(network,data,elements)}
    elif requested:
        # Use the same moving-pylon measurements and aerodynamic sensor field
        # as the complete report. Position/flow targets do not consume section
        # traces; their omission changes no residual row or tangent stencil.
        indices={index for index,_,_ in requested};local=data['local_motion']
        for k,row in enumerate(network.model.records.get('sensor',[])):
            if int(row[0]) not in indices:continue
            i=network.node(*row[1:3])
            field=LocalMotion(data['r'][i],*([np.zeros(3)]*4 if local is None else [v[i] for v in local.values]))
            airflow=None if data['aero'] is None else data['aero']['sensor_airflow'][k]['relative_velocity']
            sensors[int(row[0])]=measure_sensor(row,data['r'][i],data['Q'][i],field,data['motion'],
                model=network.model,condition=data['condition'],gravity=data['gravity'],airflow=airflow)
    loads={f'{group}.{axis}':float(value) for group,vector in [('force',force),('moment',moment)] for axis,value in zip('xyz',vector)}
    return {name:eq.evaluate(sensors,values,loads,data['aero']) for name,eq in equations.items()}


def check_custom_tangent(operating, residual, x, start, *, rank=True, derivative_context=None):
    """Check the final full physical tangent and one-sided custom row slopes."""
    slots=[start+i for i,c in enumerate(operating.constraints) if c.quantity in operating.custom]
    if not slots:return None
    magnitudes=np.array([max(1.,abs(c.target)/c.residual_scale,
        abs(operating.initial_values[i])/c.residual_scale if operating.initial_values is not None else 0.)
        for i,c in enumerate(operating.constraints) if c.quantity in operating.custom])
    base=np.asarray(residual(x));jac=np.empty((len(base),len(x)));mismatch=0.
    # The accepted physical state above is checked outside any mathematical
    # probe extension. Keep the full centered and one-sided stencils, allowing
    # only an explicitly owned boundary context during their evaluation.
    with nullcontext() if derivative_context is None else derivative_context(x):
        for j in range(len(x)):
            h=1e-6*max(1.,abs(x[j]));a=x.copy();b=x.copy();a[j]+=h;b[j]-=h
            plus=np.asarray(residual(a));minus=np.asarray(residual(b));jac[:,j]=(plus-minus)/(2*h)
            a[j]+=h;b[j]-=h
            left=(3*base[slots]-4*minus[slots]+np.asarray(residual(b))[slots])/(2*h)
            right=(-3*base[slots]+4*plus[slots]-np.asarray(residual(a))[slots])/(2*h)
            # Subtracting a large target before normalization incurs roundoff even
            # for exactly smooth constant signals. Bound that loss in the slope
            # comparison rather than classifying it as a switching discontinuity.
            roundoff=32*np.finfo(float).eps*magnitudes/h
            scaled=abs(left-right)/(1e-7+roundoff+2e-3*np.maximum(abs(left),abs(right)))
            mismatch=max(mismatch,float(np.max(scaled)))
    if mismatch>1:
        raise AnalysisError('Custom trim has inconsistent one-sided tangents at the solved state; choose a smooth branch or a nonsingular sensor state.')
    reciprocal=None
    if rank:
        norms=np.linalg.norm(jac,axis=0)
        singular=np.linalg.svd(jac/np.maximum(norms,1e-30),compute_uv=False)
        reciprocal=float(singular[-1]/singular[0])
        if reciprocal<1e-10:raise AnalysisError('Custom trim tangent is singular: dependent equations or an undetermined operating variable.')
    return dict(one_sided_tangent_ratio=mismatch,column_scaled_reciprocal_condition=reciprocal,
        difference_step=1e-6,scope='Local steady equations; dynamic and derivative responses release these trim constraints.',
        limitations=['Expression units and constants are specified by the user; no dimensional inference or automatic unit conversion is applied.',
            'Sensor structural quantities use the selected operator\'s reported one-sided load traces and declared strain/stress sampling; inspect the sensor sample location.',
            'A locally regular equilibrium does not establish global uniqueness or stability. Refine mesh and finite-difference steps for sensitive constraints.',
            'This original expression interface replaces custom GCON equations; arbitrary Fortran routines are not imported.'])


def equilibrate_custom(n,tolerance,continuation_steps,initial_state,options):
    from .network import equilibrate
    from .operating import OperatingSystem
    from .time_integration import newton, StepFailure
    from .equilibrium_state import restore
    from .wall_root import wall_root_derivatives
    if initial_state is None:
        seed=copy(n);seed.operating=OperatingSystem(n.model,n.condition,n.motion,(),n.L,n.F)
        seed.size=seed.operating_start
        initial,seed_steps=equilibrate(seed,tolerance,continuation_steps,**options)
        x=np.r_[initial,np.zeros(n.operating.count)]
    else:
        x=restore(n,initial_state);seed_steps=0
    def residual(v,factor=1.):return n.residual(v,**{**options,'operating_factor':factor})
    residual(x)
    reached,step,steps=0.,1. if initial_state is not None else 1./continuation_steps,0
    while reached<1-1e-12:
        fraction=min(1.,reached+step)
        function=lambda v:residual(v,fraction)
        function.jacobian_builder=lambda v:n.jacobian(v,1.,_direct_geometry=False,
            **{**options,'operating_factor':fraction})
        try:trial,*_=newton(function,x,tolerance)
        except (StepFailure,ValueError) as exc:
            step*=.5
            if step<1/256:raise AnalysisError(f'Custom trim failed at target fraction {fraction:.4f}: {exc}') from exc
            continue
        x=trial;reached=fraction;steps+=1;step=min(1./continuation_steps,step*1.5)
    n.custom_trim=check_custom_tangent(n.operating,residual,x,n.operating_start,
        derivative_context=lambda v:wall_root_derivatives(n,v,
            condition_override=options.get('condition_override'),motion_override=options.get('motion_override')))
    n.custom_trim.update(seed_continuation_steps=seed_steps,target_continuation_steps=steps)
    n.equilibrium_diagnostics=dict(initialization='saved physical equilibrium' if initial_state is not None else 'prescribed-control equilibrium and custom trim',target_continuation_steps=steps)
    return x,steps
