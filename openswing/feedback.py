"""Scheduled measurement feedback and error-integral residuals (unsteady §11).

The declarative law is an OpenSwing replacement for a user CONTROL routine.
Gains multiply measurement-minus-command, or its integrated error. Actuator
settings remain algebraic unknowns, including acceleration feedback loops.
"""
from copy import deepcopy
from dataclasses import replace
import re
import numpy as np
from .aero import AnalysisError
from .sensors import network_sensors
from .recovery import recover_structure
from .control_expressions import Expression


CHANNELS = {
    'V':('speed',None,'input L/T'), 'A':('alpha',None,'deg'), 'B':('beta',None,'deg'),
    'Ex':('bank',None,'deg'), 'Ey':('elevation',None,'deg'), 'Ez':('heading',None,'deg'),
    'Cr':('circulation',None,'input L^2/T'),
}
for prefix, field, axes, unit in [
    ('A','acceleration_sensor','xyz','input L/T^2'), ('G','angular_acceleration_sensor','xyz','deg/input T^2'),
    ('W','rates_sensor','xyz','deg/input T'), ('R','position_earth','XYZ','input L'),
    ('U','velocity_earth','XYZ','input L/T'), ('r','anchor_position_body','xyz','input L'),
    ('u','anchor_velocity_body','xyz','input L/T'), ('F','force_local','csn','input F'),
    ('M','moment_local','csn','input F L')]:
    CHANNELS.update({prefix+a:(field,i,unit) for i,a in enumerate(axes)})
ANGLE_CHANNELS = {'A','B','Ex','Ey','Ez'}
GLOBAL_CHANNELS = {'V','A','B','Ex','Ey','Ez','Ax','Ay','Az','Gx','Gy','Gz','Wx','Wy','Wz','RX','RY','RZ','UX','UY','UZ'}


def channel(name, model):
    match = re.fullmatch(r'([A-Za-z]+)(?:\[([1-9]\d*)\])?', name) if isinstance(name,str) else None
    if not match or match[1] not in CHANNELS:
        raise AnalysisError(f'Unknown feedback measurement {name!r}.')
    key, sensor = match[1], None if match[2] is None else int(match[2])
    if sensor is None and key not in GLOBAL_CHANNELS:
        raise AnalysisError(f'Feedback measurement {name} needs a Sensor index.')
    if sensor is not None and sensor not in {int(r[0]) for r in model.records.get('sensor',[])}:
        raise AnalysisError(f'Feedback measurement {name} refers to an undeclared Sensor.')
    return key, sensor


def actuator(name, model):
    match = re.fullmatch(r'([FE])([1-9]\d*)', name) if isinstance(name,str) else None
    if not match or int(match[2]) not in (model.controls if match[1]=='F' else model.engine_controls):
        raise AnalysisError(f'Feedback actuator {name!r} must be a declared F# or E#.')
    return ('controls' if match[1]=='F' else 'powers'), int(match[2])


class Gain:
    def __init__(self, value):
        self.constant = None
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            if not np.isfinite(value): raise AnalysisError('Feedback gain must be finite.')
            self.constant = float(value); return
        if not isinstance(value,dict) or set(value)-{'speed','density','values','outside'}:
            raise AnalysisError('Scheduled gain requires speed, density and values.')
        self.x = np.asarray(value.get('speed',[]),dtype=float)
        self.y = np.asarray(value.get('density',[]),dtype=float)
        self.z = np.asarray(value.get('values',[]),dtype=float)
        self.outside = value.get('outside','error')
        if (self.x.ndim!=1 or self.y.ndim!=1 or not len(self.x) or not len(self.y)
            or self.z.shape!=(len(self.y),len(self.x)) or any(not np.all(np.isfinite(a)) for a in (self.x,self.y,self.z))
            or np.any(np.diff(self.x)<=0) or np.any(np.diff(self.y)<=0) or self.outside not in ('error','linear','hold')):
            raise AnalysisError('Gain grids must be finite, strictly increasing and match values[density][speed]; outside must be error, linear or hold.')

    def __call__(self, speed, density):
        if self.constant is not None:return self.constant
        def interval(grid,value):
            if len(grid)==1:return 0,0,0.
            if self.outside=='error' and not grid[0]<=value<=grid[-1]:
                raise AnalysisError('Controller scheduling point is outside its gain table.')
            if self.outside=='hold':value=np.clip(value,grid[0],grid[-1])
            i=int(np.clip(np.searchsorted(grid,value)-1,0,len(grid)-2))
            return i,i+1,(value-grid[i])/(grid[i+1]-grid[i])
        a,b,u=interval(self.x,speed);c,d,v=interval(self.y,density)
        return float((1-v)*((1-u)*self.z[c,a]+u*self.z[c,b])+v*((1-u)*self.z[d,a]+u*self.z[d,b]))


class ParameterValues:
    """Evaluate a scheduled parameter only when its expression branch uses it."""
    def __init__(self,gains,speed,density):
        self.gains,self.speed,self.density=gains,speed,density

    def __getitem__(self,name):
        return self.gains[name](self.speed,self.density)


def measurements(network, state, data, signals=None):
    """Evaluate signals at the current implicit trial, using its actual loads."""
    from .time_integration import attitude_angles
    c,motion = data['condition'],data['motion']
    global_values=dict(zip(('Ex','Ey','Ez'),attitude_angles(state.orientation)))
    global_values.update(zip(('RX','RY','RZ'),state.position))
    global_values.update(zip(('UX','UY','UZ'),state.orientation@state.U))
    for names, values in [(('Wx','Wy','Wz'),np.rad2deg(motion.rates)),
                          (('Gx','Gy','Gz'),np.rad2deg(motion.angular_acceleration)),
                          (('Ax','Ay','Az'),motion.acceleration)]:
        global_values.update(zip(names,values))
    if c is not None:global_values.update(V=c.speed,A=c.alpha,B=c.beta)
    result={name:float(value) for name,value in global_values.items()}
    rows=network.model.records.get('sensor',[])
    requested=None if signals is None else [channel(name,network.model) for name in signals]
    selected=None if requested is None else {sensor for _,sensor in requested if sensor is not None}
    if rows and (selected is None or selected):
        frame=dict(body_to_earth=state.orientation,
            position_earth=state.position,velocity_origin_body=state.U)
        # Kinematic/airflow sensors do not consume section strain or stress.
        # Preserve the complete public measurement map by default; controller
        # expressions declare every referenced signal during construction.
        needs_structure=requested is None or any(
            sensor is not None and (key.startswith(('F','M')) or key=='Cr')
            for key,sensor in requested)
        if needs_structure:
            elements,_=recover_structure(network,data)
            sensors=network_sensors(network,data,elements,frame)
        else:
            from .sensors import measure_sensor
            from .local_motion import LocalMotion
            sensors=[];local=data['local_motion']
            for k,row in enumerate(rows):
                if int(row[0]) not in selected:continue
                i=network.node(*row[1:3])
                field=LocalMotion(data['r'][i],*([np.zeros(3)]*4 if local is None else [v[i] for v in local.values]))
                airflow=None if data['aero'] is None else data['aero']['sensor_airflow'][k]['relative_velocity']
                sensors.append(measure_sensor(row,data['r'][i],data['Q'][i],field,motion,
                    model=network.model,condition=c,gravity=data['gravity'],airflow=airflow,frame=frame))
        for sensor in sensors:
            for key,(field,axis,_) in CHANNELS.items():
                if selected is not None and (key,sensor['index']) not in requested:continue
                value=sensor[field]
                if value is not None:
                    value=value if axis is None else value[axis]
                    if key.startswith(('W','G')):value=np.rad2deg(value)
                result[f"{key}[{sensor['index']}]"]=value
    return result


class FeedbackSystem:
    def __init__(self, network, definition):
        original=deepcopy(definition)
        if isinstance(definition,dict) and 'con' in definition:
            if set(definition)-{'con','bindings','commands','initial_integrals'}:raise AnalysisError('Unknown .con controller settings.')
            from .control_tables import bind_control_tables
            definition=bind_control_tables(definition['con'],definition.get('bindings'),
                commands=definition.get('commands'),initial_integrals=definition.get('initial_integrals'))
        if not isinstance(definition,dict) or set(definition)-{'outputs','commands','initial_integrals','states','parameters'}:
            raise AnalysisError('Controller requires outputs, with optional commands, initial_integrals, states and parameters.')
        self.network=network;self.definition=original;self.outputs=[];self.integrals=[];self.signals=[]
        self.states=[];self.expressions=[]
        parameters=definition.get('parameters',{})
        if not isinstance(parameters,dict) or any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',k) for k in parameters):
            raise AnalysisError('Controller parameters must be a map of named finite constants or gain tables.')
        self.parameters={name:Gain(value) for name,value in parameters.items()}
        states=definition.get('states',[])
        if not isinstance(states,list):raise AnalysisError('Controller states must be a list.')
        for row in states:
            if not isinstance(row,dict) or set(row)-{'name','initial','scale','unit','rate'}:
                raise AnalysisError('Controller state requires name, scale, unit and rate, with optional initial value.')
            name=row.get('name');initial=row.get('initial',0.);scale=row.get('scale');unit=row.get('unit')
            if (not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}',name)
                or name in [s['name'] for s in self.states]
                or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not np.isfinite(v) for v in (initial,scale))
                or scale<=0 or not isinstance(unit,str) or not unit.strip() or len(unit)>64):
                raise AnalysisError('Controller states need distinct names, finite initial values, positive scales and explicit unit labels.')
            expression=Expression(row.get('rate'));self.expressions.append(expression)
            self.states.append(dict(name=name,initial=float(initial),scale=float(scale),unit=unit,rate=expression))
        if network.condition is None:raise AnalysisError('Feedback actuators require an aerodynamic condition.')
        if not isinstance(definition.get('outputs'),list):raise AnalysisError('Controller outputs must be a list.')
        for row in definition.get('outputs',[]):
            if not isinstance(row,dict) or set(row)-{'actuator','terms','expression','residual','residual_scale'}:
                raise AnalysisError('Controller output requires actuator and terms, expression or residual.')
            kinds=set(row)&{'terms','expression','residual'}
            if len(kinds)!=1:raise AnalysisError('Select exactly one of terms, expression or residual for each controller output.')
            kind=kinds.pop()
            residual_scale=row.get('residual_scale')
            if residual_scale is not None and (kind!='residual' or not isinstance(residual_scale,(int,float))
                or isinstance(residual_scale,bool) or not np.isfinite(residual_scale) or residual_scale<=0):
                raise AnalysisError('residual_scale must be positive and is only valid for an implicit residual expression.')
            name=row.get('actuator');attribute,index=actuator(name,network.model)
            if name in [o['actuator'] for o in self.outputs]:raise AnalysisError('Duplicate controller actuator.')
            terms=[]
            if kind=='terms' and not isinstance(row['terms'],list):raise AnalysisError('Controller terms must be a list.')
            for term in row.get('terms',[]):
                if not isinstance(term,dict) or set(term)-{'input','gain','mode'}:raise AnalysisError('Controller term requires input, gain and optional mode.')
                signal=term.get('input');channel(signal,network.model);mode=term.get('mode','error')
                if mode not in ('error','integral','value'):raise AnalysisError('Controller term mode must be error, integral or value.')
                terms.append((signal,Gain(term.get('gain')),mode))
                if signal not in self.signals:self.signals.append(signal)
                if mode=='integral' and signal not in self.integrals:self.integrals.append(signal)
            if kind=='terms' and not terms:raise AnalysisError('Controller output needs at least one term.')
            expression=None if kind=='terms' else Expression(row[kind])
            if expression is not None:self.expressions.append(expression)
            self.outputs.append(dict(actuator=name,attribute=attribute,index=index,terms=terms,
                kind=kind,expression=expression,residual_scale=residual_scale))
        if not self.outputs:raise AnalysisError('Controller needs at least one output.')
        for expression in self.expressions:
            for kind,name in expression.references:
                if kind=='state':
                    if name not in [s['name'] for s in self.states]:raise AnalysisError(f'Undeclared controller state {name!r}.')
                elif kind=='parameter':
                    if name not in self.parameters:raise AnalysisError(f'Undeclared controller parameter {name!r}.')
                elif kind=='actuator':actuator(name,network.model)
                elif kind=='command' and re.fullmatch(r'[FE][1-9]\d*',name):
                    if name not in [o['actuator'] for o in self.outputs]:raise AnalysisError('Command actuator must be controlled; use actuator() to read an uncontrolled setting.')
                else:
                    channel(name,network.model)
                    if name not in self.signals:self.signals.append(name)
                    if kind=='integral' and name not in self.integrals:self.integrals.append(name)
        self.needs_side_check=any(e.nonsmooth for e in self.expressions) or any(g.constant is None for g in self.parameters.values())
        self.commands=deepcopy(definition.get('commands',{}))
        self.initial_integrals=deepcopy(definition.get('initial_integrals',{}))
        if (not isinstance(self.commands,dict) or set(self.commands)-set(self.signals)
            or not isinstance(self.initial_integrals,dict) or set(self.initial_integrals)-set(self.integrals)
            or any(not isinstance(v,(float,int)) or not np.isfinite(v) for v in [*self.commands.values(),*self.initial_integrals.values()])):
            raise AnalysisError('Controller commands/integrals must contain finite values for selected measurements.')
        self.count=len(self.outputs);self.state_start=self.count+len(self.integrals);self.size=self.state_start+len(self.states)
        self.base=None
        self._linearization_reference=None

    def root_diagnostic(self, rows, tolerance):
        """Opt into bounded original-residual probes for expression branches."""
        if not any(expression.nonsmooth for expression in self.expressions):return None
        from .root_diagnostics import controller_alternatives
        return controller_alternatives(rows,tolerance)

    def initialize(self,state,data):
        self.reference=measurements(self.network,state,data,self.signals)
        for signal in self.signals:
            if self.reference.get(signal) is None or not np.isfinite(self.reference[signal]):
                raise AnalysisError(f'Controller measurement {signal} is undefined at the initial state.')
            self.commands.setdefault(signal,self.reference[signal])
        c=data['condition']
        self.bias={o['actuator']:float(getattr(c,o['attribute']).get(o['index'],0.)) for o in self.outputs}
        n=self.network;self.time_scale=n.L/max(c.speed,np.sqrt(n.model.constants[0]*n.L))
        self.signal_scales={}
        for signal in self.signals:
            key,_=channel(signal,n.model);unit=CHANNELS[key][2]
            typical={'input L':n.L,'input L/T':c.speed,'deg':10.,'deg/input T':10./self.time_scale,
                'input L/T^2':n.model.constants[0],'deg/input T^2':10./self.time_scale**2,
                'input F':n.F,'input F L':n.F*n.L,'input L^2/T':n.L*c.speed}[unit]
            # Scale perturbations by aircraft dimensions, never by an arbitrary
            # Earth-coordinate origin or a large commanded position datum.
            self.signal_scales[signal]=max(typical,1e-10)
        self.scales=np.array([n.operating.scale[('control.' if o['attribute']=='controls' else 'power.')+str(o['index'])] for o in self.outputs]
            +[self.signal_scales[s]*self.time_scale for s in self.integrals]+[s['scale'] for s in self.states])
        self.rate_scales=np.array([self.signal_scales[s] for s in self.integrals]+[s['scale']/self.time_scale for s in self.states])
        self.base=np.array(list(self.bias.values())+[self.initial_integrals.get(s,0.) for s in self.integrals]+[s['initial'] for s in self.states])
        state.feedback=self.base.copy()

    def apply(self,state,condition):
        settings=dict(controls=dict(condition.controls),powers=dict(condition.powers))
        for value,o in zip(state.feedback,self.outputs):settings[o['attribute']][o['index']]=float(value)
        return replace(condition,**settings)

    def evaluate(self,state,data,derivative=None):
        sensed=measurements(self.network,state,data,self.signals)
        return self.evaluate_measurements(state,data,sensed,derivative)

    def evaluate_measurements(self,state,data,sensed,derivative=None):
        """Controller residual given physical measurements, for chain-rule tangents."""
        commands={**self.commands,**self.bias,**state.commands}
        errors={}
        for name in self.signals:
            value=sensed.get(name)
            if value is None or not np.isfinite(value):raise AnalysisError(f'Controller measurement {name} is undefined.')
            error=value-commands[name]
            if channel(name,self.network.model)[0] in ANGLE_CHANNELS:error=(error+180)%360-180
            errors[name]=float(error)
        integrated=dict(zip(self.integrals,state.feedback[self.count:]))
        c=data['condition'];rho=data['aero']['atmosphere']['density']
        states={s['name']:float(value) for s,value in zip(self.states,state.feedback[self.state_start:])}
        actuators={**{f'F{k}':float(c.controls.get(k,0.)) for k in self.network.model.controls},
            **{f'E{k}':float(c.powers.get(k,0.)) for k in self.network.model.engine_controls}}
        env=dict(measurement=sensed,error=errors,integral=integrated,command=commands,actuator=actuators,state=states,
            parameter=ParameterValues(self.parameters,c.speed,rho),speed=c.speed,density=rho,time=state.time,pi=np.pi)
        actual=state.feedback[:self.count]
        control=[]
        for i,output in enumerate(self.outputs):
            if output['kind']=='residual':
                control.append(output['expression'](env)/(output['residual_scale'] or self.scales[i]));continue
            if output['kind']=='expression':total=output['expression'](env)
            else:
                total=commands[output['actuator']]
                for name,gain,mode in output['terms']:
                    total+=gain(c.speed,rho)*(integrated[name] if mode=='integral' else sensed[name] if mode=='value' else errors[name])
            control.append((actual[i]-total)/self.scales[i])
        rates={s['name']:s['rate'](env) for s in self.states}
        residual=np.array(control)
        if derivative is not None:
            residual=np.r_[residual,(derivative[self.count:]-np.array([errors[s] for s in self.integrals]+list(rates.values())))/self.rate_scales]
        report=dict(actuators=dict(zip(self.bias,map(float,actual))),commands=commands,errors=errors,
            integrals={s:float(v) for s,v in integrated.items()},measurements={s:float(sensed[s]) for s in self.signals})
        if self.states:report.update(states=states,state_rates=rates)
        for name,group,reference in self._linearization_reference or []:
            if abs(report[group][name]-reference)>180:
                raise AnalysisError('Controller difference stencil crosses an angle branch cut; reduce the difference step or change the command/base.')
        return residual,report

    def report(self):
        return dict(definition=self.definition,commands=self.commands,bias=self.bias,signals=self.signals,
            integral_channels=self.integrals,state_channels=[s['name'] for s in self.states],
            state_units={s['name']:s['unit'] for s in self.states},scales=self.scales.tolist(),
            units={s:CHANNELS[channel(s,self.network.model)[0]][2] for s in self.signals},
            equation='Scheduled law, target expression or implicit actuator residual; integral_dot = measurement - command; custom_state_dot = rate expression',
            limitations=['Declarative expressions and scheduled laws replace user CONTROL routines; they do not execute Fortran or Python source.',
                'Angles and angular rates in named feedback channels use degrees. Global Ax/Ay/Az are absolute reference accelerations; sensor accelerometers measure specific force.',
                'Commands default to initial measured values; actuator bias defaults to the solved open-loop setting. Angle errors use the shortest signed branch.',
                'No actuator dynamics, saturation or anti-windup is added implicitly. Gain-table behavior outside the grid is explicit.'])

    def check_linearization(self,state,data,*,moving_speed=False):
        """Do not average incompatible one-sided control-law derivatives."""
        _,report=self.evaluate(state,data)
        c=data['condition'];rho=data['aero']['atmosphere']['density']
        references=[]
        for expression in self.expressions:
            for kind,name in expression.references:
                if kind not in ('measurement','error','integral'):continue
                key,_=channel(name,self.network.model)
                group='measurements' if kind=='measurement' else 'errors'
                if key in ANGLE_CHANNELS:
                    angle=report[group][name]
                    references.append((name,group,angle))
                    if abs(abs(angle)-180)<1e-5:
                        raise AnalysisError('Controller angle is on its branch cut; choose a continuous local command/base.')
                if key=='Ey' and abs(abs(report['measurements'][name])-90)<1e-7:
                    raise AnalysisError('Controller elevation is at an Euler pole; choose a different measurement/base.')
        for output in self.outputs:
            for name,gain,mode in output['terms']:
                key,_=channel(name,self.network.model)
                value=report['integrals'][name] if mode=='integral' else report['measurements'][name] if mode=='value' else report['errors'][name]
                angle=report['measurements'][name] if mode=='value' else report['errors'][name]
                if key in ANGLE_CHANNELS:
                    references.append((name,'measurements' if mode=='value' else 'errors',angle))
                if key in ANGLE_CHANNELS and abs(abs(angle)-180)<1e-5:
                    raise AnalysisError('Controller angle is on its branch cut; choose a continuous local command/base.')
                if key=='Ey' and abs(abs(report['measurements'][name])-90)<1e-7:
                    raise AnalysisError('Controller elevation is at an Euler pole; choose a different measurement/base.')
                if gain.constant is not None or abs(value)<1e-10*self.signal_scales[name]:continue
                point=np.array([c.speed,rho])
                for axis,grid in ([(0,gain.x)] if moving_speed else []):
                    knots=grid[1:-1] if gain.outside=='linear' else grid
                    if len(grid)<2 or not np.any(abs(knots-point[axis])<1e-8*max(1.,abs(point[axis]))):continue
                    h=1e-6*max(1.,abs(point[axis]));plus=point.copy();minus=point.copy()
                    plus[axis]+=h;minus[axis]-=h
                    a=(gain(*plus)-gain(*point))/h;b=(gain(*point)-gain(*minus))/h
                    if not np.isclose(a,b,rtol=1e-5,atol=1e-8):
                        raise AnalysisError('Controller base is on a gain-schedule slope break with nonzero feedback; move the base or smooth the table.')
        self._linearization_reference=references


def equilibrium(system,state,options,tolerance,*,steady):
    """Couple the loaded network and actuators; time startup holds integral ICs."""
    from .time_integration import newton
    n=system.network;controller=system.feedback
    _,data=n.residual(state.x,detail=True,**options)
    controller.initialize(state,data)
    if getattr(system,'forcing',None) is not None:
        system.forcing.bind_commands(controller.commands)
        state.commands=system.forcing.values(state.time)
    size=controller.size if steady else controller.count
    initial=state.feedback.copy()
    def function(values,detail=False,_mechanical_data=None):
        x=values[:n.size]
        trial=replace(state,x=x,feedback=np.r_[values[n.size:]*controller.scales[:size],initial[size:]])
        trial.r,trial.Q,*_,trial.gamma=n.unpack(x)
        applied={**options,'condition_override':controller.apply(trial,options['condition_override'])}
        base,data=n.residual(x,detail=True,**applied,_mechanical_data=_mechanical_data)
        control,_=controller.evaluate(trial,data,np.zeros(controller.size) if steady else None)
        residual=np.r_[base,control]
        return (residual,trial,applied) if detail else residual
    if not steady:
        function.accepted_root_diagnostic=controller.root_diagnostic(range(n.size,n.size+controller.count),tolerance)
        from .time_tangent import attach_mechanical_columns
        attach_mechanical_columns(system, function,
            lambda values, data: function(values, _mechanical_data=data[0]))
    values,*_=newton(function,np.r_[state.x,initial[:size]/controller.scales[:size]],tolerance,check_rank=not steady)
    _,state,options=function(values,True)
    if n.hinges:
        from .hinge_history import lifted
        state.hinge_charts=lifted(n,state.Q,options['hinge_charts'])
    controller.base=state.feedback.copy()
    return state,options
