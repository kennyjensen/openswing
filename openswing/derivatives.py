"""Implicit quasi-steady responses of the complete implemented residual.

Steady theory 8.3–8.6: J dx/dp = -R_p. Numerical partial derivatives are
centered, with scoped analytic circulation and control-input blocks. Checked
centered probes and directional output recovery remain. One factorization
serves all parameter columns. These are not modes.
"""
from copy import copy
from time import perf_counter
from dataclasses import replace
import numpy as np
from scipy.linalg import lu_factor, lu_solve
from .aero import AnalysisError
from .operating import OperatingSystem, free_flight_constraints
from .recovery import recover_structure


# Signed material outputs have ordinary directional derivatives. Absolute
# strain bounds/stress magnitudes are deliberately absent: their cusps do not
# define a unique linear response at a zero crossing.
SECTION_OUTPUTS = {
    'section_force_local': ('force_local', 'Local section force', 'input F', ['c','s','n']),
    'section_moment_local': ('moment_local', 'Local reference-axis moment', 'input F L', ['c','s','n']),
    'section_moment_axes': ('moment_axes', 'Section moment about tension/elastic axes', 'input F L', ['c','s','n']),
    'section_strain': ('strain', 'Mechanical strain', 'dimensionless', ['c','s','n']),
    'section_curvature': ('curvature_change', 'Curvature change', 'rad / input L', ['c','s','n']),
    'section_axial_strain': ('axial_strain_tension', 'Tension-axis axial strain', 'dimensionless', None),
    'shell_axial_strain': ('shell.axial_strain', 'Signed shell-point axial strain', 'dimensionless', None),
    'shell_shear_stress': ('shell.shear_stress', 'Signed torsional shear stress', 'input F / L^2', None),
}


def stability_rotation(alpha):
    a = np.deg2rad(alpha)
    return np.array([[-np.cos(a),0,-np.sin(a)],[0,1,0],[np.sin(a),0,-np.cos(a)]])


def parameter_catalog(model, condition, feedback=None):
    """Alpha/beta derivatives are per radian; flap units remain file-defined."""
    area, chord, span = model.reference[0]
    v = condition.speed
    out = {name:dict(name=name, unit=unit, scale=scale) for name,unit,scale in [
        ('u','fractional speed V/V0',1.),('alpha','rad',1.),('beta','rad',1.),
        ('p','p b/(2 V0)',1.),('q','q c/(2 V0)',1.),('r','r b/(2 V0)',1.),
        ('speed','input L/T',v)]}
    for axis in 'xyz':
        out[f'velocity.{axis}'] = dict(name=f'velocity.{axis}',unit='input L/T at velocity reference',scale=v)
        out[f'rates.{axis}'] = dict(name=f'rates.{axis}',unit='rad/input T, body axes',scale=v/span)
        out[f'origin_velocity.{axis}'] = dict(name=f'origin_velocity.{axis}',unit='input L/T at body origin',scale=v)
        out[f'origin_rates.{axis}'] = dict(name=f'origin_rates.{axis}',unit='rad/input T holding origin velocity',scale=v/span)
    for k in model.controls:
        out[f'control.{k}'] = dict(name=f'control.{k}',unit='file flap setting',scale=max(1.,abs(condition.controls.get(k,0.))))
    for k in model.engine_controls:
        out[f'power.{k}'] = dict(name=f'power.{k}',unit='file engine setting',scale=max(1.,abs(condition.powers.get(k,0.))))
    if feedback is not None:
        from .feedback import CHANNELS, channel
        for i,o in enumerate(feedback.outputs):
            key=('control.' if o['attribute']=='controls' else 'power.')+str(o['index'])
            entry=out.pop(key)
            name='command.'+o['actuator']
            out[name]=dict(name=name,unit=entry['unit'],scale=float(feedback.scales[i]),kind='actuator command')
        for signal in feedback.signals:
            name='command.'+signal
            out[name]=dict(name=name,unit=CHANNELS[channel(signal,model)[0]][2],
                           scale=float(feedback.signal_scales[signal]),kind='measurement command')
    return out


def perturb_condition(condition, parameter, increment, model):
    """One physical input perturbation; normalized rates use BASE stability axes."""
    if parameter in ('u','speed'):
        return replace(condition,speed=condition.speed+increment*(condition.speed if parameter=='u' else 1.))
    if parameter in ('alpha','beta'):
        return replace(condition,**{parameter:getattr(condition,parameter)+np.rad2deg(increment)})
    if parameter in ('p','q','r'):
        axis = 'pqr'.index(parameter)
        ref = model.reference[0,1 if axis==1 else 2]
        delta = stability_rotation(condition.alpha).T[:,axis]*(2*condition.speed/ref)*increment
        return replace(condition,rates=(np.asarray(condition.rates)+delta).tolist())
    group, axis = parameter.split('.')
    if group == 'rates':
        rates = np.array(condition.rates,dtype=float); rates['xyz'.index(axis)] += increment
        return replace(condition,rates=rates.tolist())
    if group in ('velocity','origin_velocity','origin_rates'):
        velocity = -condition.speed*condition.vectors()[0]
        if group=='origin_rates':
            delta = np.zeros(3);delta['xyz'.index(axis)] = increment
            velocity += np.cross(delta,model.reference[3])
            condition = replace(condition,rates=(np.asarray(condition.rates)+delta).tolist())
        else:
            velocity['xyz'.index(axis)] += increment
        speed = float(np.linalg.norm(velocity))
        return replace(condition,speed=speed,alpha=float(np.rad2deg(np.arctan2(-velocity[2],-velocity[0]))),
                       beta=float(np.rad2deg(np.arctan2(velocity[1],np.hypot(velocity[0],velocity[2])))))
    attr = 'controls' if group == 'control' else 'powers'
    values = dict(getattr(condition,attr)); k = int(axis)
    values[k] = values.get(k,0.)+increment
    return replace(condition,**{attr:values})


def linearize_equilibrium(network, state, *, response='fixed_acceleration', basis='standard',
                         parameters=None, axes='stability', step=1e-5, feedback=None, feedback_state=None, _audit=None):
    if network.condition is None:
        raise AnalysisError('Aerodynamic derivatives require a FlightCondition.')
    from .aero import _reference_area
    _reference_area(network.model, required=True)
    if response not in ('fixed_acceleration','free_flight'):
        raise AnalysisError('Derivative response must be fixed_acceleration or free_flight.')
    if basis not in ('standard','body','body_origin') or axes not in ('body','stability','reverse_stability'):
        raise AnalysisError('Unsupported derivative input basis or output axes.')
    if not np.isfinite(step) or not 1e-7 <= step <= 1e-3:
        raise AnalysisError('Derivative step must be finite and between 1e-7 and 1e-3.')
    condition, motion, operating_values = network.operating.apply(state[network.operating_start:])
    if feedback is not None:
        if feedback_state is None:raise AnalysisError('Closed-loop derivatives require the solved physical controller state.')
        condition=feedback.apply(feedback_state,condition)
        operating_values={**operating_values,**{
            ('control.' if o['attribute']=='controls' else 'power.')+str(o['index']):float(value)
            for o,value in zip(feedback.outputs,feedback_state.feedback)}}
    catalog = parameter_catalog(network.model,condition,feedback)
    if parameters is None:
        parameters = (['u','alpha','beta','p','q','r'] if basis=='standard' else
                      [f'{group}.{axis}' for group in (('origin_velocity','origin_rates') if basis=='body_origin' else ('velocity','rates')) for axis in 'xyz'])
        parameters += [key for key in catalog if key.startswith(('control.','power.','command.'))]
    if (not isinstance(parameters,(list,tuple)) or not parameters or any(not isinstance(p,str) or p not in catalog for p in parameters)
            or len(set(parameters)) != len(parameters)):
        raise AnalysisError('Derivative parameters must be distinct supported state, control or command names. A controlled actuator uses command.F# or command.E#; its actual setting is solved by the controller.')
    columns = [dict(catalog[p],step=float(step*catalog[p]['scale'])) for p in parameters]

    # Freeze solved trim variables at their converged values. For free-flight
    # responses ONLY the six accelerations respond to net-load equations.
    n = copy(network)
    n.condition, n.motion = condition, motion
    constraints = free_flight_constraints() if response=='free_flight' else []
    n.size = n.operating_start+len(constraints)
    x = np.r_[state[:n.operating_start],np.zeros(len(constraints))]
    control = None
    if feedback is not None:
        control=copy(feedback);control.network=n;control._linearization_reference=None
        commands={**feedback.commands,**feedback.bias,**feedback_state.commands}
        control.commands={key:commands[key] for key in feedback.commands}
        control.bias={key:commands[key] for key in feedback.bias}
        x=np.r_[x,feedback_state.feedback/control.scales]
    size=len(x)
    current = None
    def evaluate(z, c=condition, detail=False, commands=None):
        nonlocal current
        if current is not c:
            n.operating = OperatingSystem(n.model,c,c.motion(),constraints,n.L,n.F)
            n.aero_key = n.aero_cached = None
            current = c
        if control is None:return n.residual(z,detail=detail)
        from .time_integration import TimeState
        from .ground import body_to_earth
        nx=z[:n.size]
        actual,m,_=n.operating.apply(nx[n.operating_start:])
        r,q,*_,gamma=n.unpack(nx);zero=np.zeros_like(r)
        trial=TimeState(actual.time,nx,r,q,zero,zero,
            -actual.speed*actual.vectors()[0]-np.cross(m.rates,n.model.reference[3]),m.rates,
            np.asarray(actual.position_earth),body_to_earth(actual.attitude),gamma,
            z[n.size:]*control.scales,{} if commands is None else commands)
        from .hinge_history import at_network
        trial.hinge_charts=at_network(n,q)
        base,data=n.residual(nx,detail=True,condition_override=control.apply(trial,actual))
        residual,report=control.evaluate(trial,data,np.zeros(control.size))
        data['feedback_state'],data['feedback']=trial,report
        result=np.r_[base,residual]
        return (result,data) if detail else result

    def perturb(parameter,increment):
        if parameter.startswith('command.'):
            name=parameter.removeprefix('command.')
            return condition,{name:({**control.commands,**control.bias})[name]+increment}
        return perturb_condition(condition,parameter,increment,n.model),None

    baseline, data0 = evaluate(x,detail=True)
    if np.max(abs(baseline)) > 1e-7:
        raise AnalysisError('Free-flight derivatives require a converged zero-net-force/moment state; use free-flight or full flight-trim targets first.')
    if control is not None:
        moving_speed=any(p in ('u','speed') or p.startswith(('velocity.','origin_velocity.','origin_rates.')) for p in parameters)
        control.check_linearization(data0['feedback_state'],data0,moving_speed=moving_speed)
    for h in data0['hinges']:
        law = n.hinges[h['joint']]
        moment = h['structural_moment']
        for breakpoint in law.spline.breaks:
            if abs(moment-breakpoint) <= 10*step*n.F*n.L:
                left = law.spline.evaluate(breakpoint,side='left',derivative=1)
                right = law.spline.evaluate(breakpoint,side='right',derivative=1)
                if not np.isclose(left,right,rtol=1e-7,atol=1e-12):
                    raise AnalysisError('Derivative state is too close to a Jangle slope break; a unique tangent is not established.')
    if n.tension_only and any(abs(s['strain']) < 10*step for s in data0['struts']):
        raise AnalysisError('Derivative state is too close to a wire slack/taut transition; a unique tangent is not established.')
    clips = tuple(e['power_clipped'] for e in data0['aero']['engines'])
    def checked(z,c=condition,commands=None):
        # A branch change across a stencil must not masquerade as a derivative.
        residual = evaluate(z,c,commands=commands)
        if tuple(e['power_clipped'] for e in n.aero_cached['engines']) != clips:
            raise AnalysisError('Derivative stencil crosses an engine power-clipping transition; change the operating point or step.')
        if n.tension_only:
            from .struts import strut_load
            r, q = n.unpack(z[:n.size])[:2]
            for row, original in zip(n.struts,data0['struts']):
                i = n.node(*row[:2]); position = r[i]+q[i]@(row[2:5]-n.rj[i])
                if strut_load(row,position,tension_only=True)['slack'] != original['slack']:
                    raise AnalysisError('Derivative stencil crosses a wire slack/taut transition; change the operating point or step.')
        return residual

    side_check=control is not None and control.needs_side_check
    def difference(function,h):
        plus,minus=function(h),function(-h)
        if side_check:
            from .control_expressions import check_sides
            plus2,minus2=function(2*h),function(-2*h)
            check_sides(*(v[n.size:] for v in (baseline,minus,plus,minus2,plus2)),h)
        return (plus-minus)/(2*h)
    from .derivative_circulation import capture_circulation_columns
    circulation_audit={}
    try:
        direct_gamma=capture_circulation_columns(n,x,checked,baseline,
            response=response,feedback=feedback,step=step,report=circulation_audit)
    finally:
        if _audit is not None:
            _audit(dict(circulation_derivative=copy(circulation_audit)))
    from .derivative_controls import capture_control_columns
    control_positions = [i for i,p in enumerate(columns) if p['name'].startswith('control.')]
    control_indices = [int(columns[i]['name'].split('.')[1]) for i in control_positions]
    control_audit = {}
    try:
        direct_controls = capture_control_columns(n,x,checked,baseline,
            controls=control_indices,response=response,feedback=feedback,step=step,report=control_audit)
    finally:
        if _audit is not None:
            _audit(dict(control_derivative=copy(control_audit)))
    from .derivative_cache import derivative_probe_cache
    cache_audit={}
    try:
        with derivative_probe_cache(n,response=response,feedback=feedback,report=cache_audit):
            phase_start=perf_counter();phase_seconds={}
            jac = np.empty((size,size))
            for j in range(size):
                h = step*max(1.,abs(x[j])); delta = np.zeros(size); delta[j] = 1.
                jac[:,j] = difference(lambda h:checked(x+h*delta),h)
            if direct_gamma is not None:
                # Keep the original probes above for branch parity and raw
                # comparison during validation of this isolated prototype.
                if _audit is not None:
                    _audit(dict(centered_gamma_columns=jac[:,n.gamma_start:n.operating_start].copy(),
                                analytic_gamma_columns=direct_gamma.copy()))
                jac[:,n.gamma_start:n.operating_start]=direct_gamma
            norms = np.maximum(np.linalg.norm(jac,axis=0),1e-30)
            scaled = jac/norms
            phase_seconds['centered_J_and_scaling']=perf_counter()-phase_start
            phase_start=perf_counter()
            singular = np.linalg.svd(scaled,compute_uv=False)
            reciprocal_condition = float(singular[-1]/singular[0])
            if reciprocal_condition < 1e-10:
                raise AnalysisError('Coupled derivative tangent is singular or too ill-conditioned; inspect constraints and proximity to a static instability.')
            phase_seconds['rank_and_optional_sparse_factor']=perf_counter()-phase_start
            phase_start=perf_counter()
            partials = np.empty((size,len(columns)))
            for j,p in enumerate(columns):
                h = p['step']
                partials[:,j] = difference(lambda h:checked(x,*perturb(p['name'],h)),h)
            if direct_controls is not None:
                # Retain every checked input probe above for branch validation;
                # only the declared file-control input partials are replaced.
                if _audit is not None:
                    _audit(dict(centered_control_columns=partials[:,control_positions].copy(),
                                analytic_control_columns=direct_controls.copy()))
                partials[:,control_positions] = direct_controls
            phase_seconds['centered_input_columns']=perf_counter()-phase_start
    finally:
        if _audit is not None:
            _audit(dict(derivative_cache=copy(cache_audit)))
    phase_start=perf_counter()
    factor = lu_factor(scaled)
    dx = lu_solve(factor,-partials)/norms[:,None]
    errors = np.max(abs(jac@dx+partials),axis=0)/np.maximum(1.,np.max(abs(partials),axis=0))
    phase_seconds['physical_RHS_solve_and_full_residual']=perf_counter()-phase_start
    if not np.all(np.isfinite(dx)) or np.max(errors) > 1e-8:
        raise AnalysisError('Coupled derivative linear solve failed its residual check.')

    if _audit is not None:
        _audit(dict(jacobian=jac.copy(),column_norms=norms.copy(),scaled_jacobian=scaled.copy(),
                    input_partials=partials.copy(),state_response=dx.copy(),
                    full_linear_residual=(jac@dx+partials).copy(),linear_residuals=errors.copy(),
                    phase_seconds=dict(phase_seconds),linear_solver='original_dense',sparse_factor_report=None))
    phase_start=perf_counter()
    rotation = stability_rotation(condition.alpha)
    if axes=='body': rotation = np.eye(3)
    elif axes=='reverse_stability': rotation = np.diag([-1.,1.,-1.])@rotation
    qs = data0['aero']['atmosphere']['dynamic_pressure']*n.model.reference[0,0]
    lever = n.model.reference[0,[2,1,2]]
    signs = np.array([1,1,-1 if axes=='stability' else 1])
    def coefficients(wrench):
        return np.r_[signs*(rotation@wrench[:3])/qs,(rotation@wrench[3:])/(qs*lever)]
    feedback_rows=[]
    if control is not None:
        from .feedback import CHANNELS,channel
        for group,entries in data0['feedback'].items():
            for name in entries:
                if group.startswith('state'):
                    unit=next(s['unit'] for s in control.states if s['name']==name)+(' / input T' if group=='state_rates' else '')
                elif name in control.bias:unit='file flap setting' if name.startswith('F') else 'file engine setting'
                else:unit=CHANNELS[channel(name,n.model)[0]][2]+(' · input T' if group=='integrals' else '')
                feedback_rows.append(dict(name=group+'.'+name,group=group,channel=name,unit=unit))
    section_available = {}
    def outputs(z,c,commands=None):
        _, data = evaluate(z,c,detail=True,commands=commands)
        aero = data['aero']; r = data['r']
        fluid = np.r_[aero['force'],aero['moment']]
        distributed = np.r_[aero['distributed_aero_force'],aero['distributed_aero_moment']]
        m = data['motion']
        result = dict(distributed_aero_wrench=distributed,fluid_wrench=fluid,
                    net_wrench=np.r_[data['force'].sum(axis=0),(data['moment']+np.cross(r-n.model.reference[1],data['force'])).sum(axis=0)],
                    coefficients=coefficients(distributed),fluid_coefficients=coefficients(fluid),
                    accelerations=np.r_[m.acceleration,m.angular_acceleration],
                    origin_accelerations=np.r_[m.at(np.zeros(3),n.model.reference[2]),m.angular_acceleration],
                    body_velocity_derivative=np.asarray(aero['earth_state']['velocity_derivative_body']),
                    positions=r,rotation_matrices=data['Q'],internal_forces=data['N'],internal_moments=data['M'],
                    circulation=n.unpack(z[:n.size])[-1])
        sections, _ = recover_structure(n, data)
        for key,(path,*_) in SECTION_OUTPUTS.items():
            values=[]
            for section in sections:
                value=section
                for part in path.split('.'):value=value[part]
                values.append(value)
            available=np.array([value is not None for value in values])
            if key in section_available and not np.array_equal(available,section_available[key]):
                raise AnalysisError('Structural derivative stencil changed section-output availability.')
            section_available[key]=available
            result[key]=np.asarray([value if value is not None else 0. for value in values],dtype=float)
            if not np.all(np.isfinite(result[key])):
                raise AnalysisError('Nonfinite structural derivative output; inspect the section properties.')
        if control is not None:result['feedback']=np.array([data['feedback'][row['group']][row['channel']] for row in feedback_rows])
        return result
    base_outputs = outputs(x,condition)
    source_sections = 'source_discrete' in data0
    section_location = 'element constitutive average' if source_sections else 'material midpoint'
    section_axes = ('arithmetic average of endpoint c,s,n transforms; generally nonorthogonal'
                    if source_sections else 'current local c,s,n')
    matrices = {k:[] for k in base_outputs if k!='rotation_matrices'}
    matrices['rotations'] = []
    for j,p in enumerate(columns):
        # Take the directional output derivative along the implicit response;
        # shorten the stencil if the structural response is unusually large.
        h = min(p['step'],step/max(np.max(abs(dx[:,j])),1e-30))
        p['output_step'] = float(h)
        plus = outputs(x+h*dx[:,j],*perturb(p['name'],h))
        minus = outputs(x-h*dx[:,j],*perturb(p['name'],-h))
        for key in matrices:
            if key=='rotations':
                dq = (plus['rotation_matrices']-minus['rotation_matrices'])/(2*h)
                skew = dq@base_outputs['rotation_matrices'].transpose(0,2,1)
                values = np.stack([skew[:,2,1]-skew[:,1,2],skew[:,0,2]-skew[:,2,0],skew[:,1,0]-skew[:,0,1]],axis=1)/2
            else: values = (plus[key]-minus[key])/(2*h)
            matrices[key].append(values)
    def serialize(key, values):
        # Missing section metadata remains null in both base and derivative
        # arrays. Zero torque is not evidence for a missing shell dimension.
        if key in section_available:
            values=values.astype(object)
            values[~section_available[key]]=None
        return values.tolist()
    matrices = {k:serialize(k,np.stack(v,axis=-1)) for k,v in matrices.items()}
    method=('implicit residual derivatives with analytic circulation columns' if direct_gamma is not None
            else 'implicit centered residual derivatives')
    result = dict(method=method,response=response,axes=axes,basis=basis,
                input_derivative_methods={p['name']:('analytic fixed-geometry control partial'
                    if direct_controls is not None and i in control_positions else 'checked centered partial')
                    for i,p in enumerate(columns)},
                control_derivative=copy(control_audit),
                output_derivative_method='centered directional derivatives along the implicit response',
                parameters=columns,matrices=matrices,coefficient_rows=['CX','CY','CL' if axes!='body' else 'CZ','Cl','Cm','Cn'],
                controller=None if control is None else control.report(),feedback_rows=feedback_rows,
                wrench_rows=['Fx','Fy','Fz','Mx','My','Mz'],acceleration_rows=['ax','ay','az','angular_ax','angular_ay','angular_az'],
                output_rotation=rotation.tolist(),normalization=dict(dynamic_pressure_area=qs,moment_lengths=lever.tolist(),
                    convention='Fixed base axes, dynamic pressure and reference lengths; no derivative of the normalization or output axes.'),
                references=dict(velocity=n.model.reference[3].tolist(),acceleration=n.model.reference[2].tolist(),moment=n.model.reference[1].tolist()),
                base_operating_values=operating_values,base_outputs={k:serialize(k,v) for k,v in base_outputs.items()},
                section_output_fields={key:dict(label=label,unit=unit,components=components,
                    source=path,sample_location=section_location,axes=section_axes,
                    available=section_available[key].tolist())
                    for key,(path,label,unit,components) in SECTION_OUTPUTS.items()},
                node_order=[dict(beam=mesh.beam.index,t=float(t)) for mesh in n.meshes for t in np.r_[mesh.t0,mesh.t1[-1]]],
                element_order=[dict(beam=mesh.beam.index,t=float(t),t0=float(mesh.t0[i]),t1=float(mesh.t1[i]))
                    for mesh in n.meshes for i,t in enumerate(mesh.ts)],
                circulation_order=[dict(beam=s['beam'],t=s['t']) for s in data0['aero']['strips'] if s['lifting']],
                column_scaled_reciprocal_condition=reciprocal_condition,linear_residuals=errors.tolist(),step=step,
                residual_evaluations=n.nfev-network.nfev,system_size=size,
                limitations=['Quasi-steady structural response: local elastic velocities, unsteady circulation states and flutter are not included.',
                    'Original inverse/trim constraints are released for these responses. Other inputs, attitude, position and atmosphere stay at their converged values.',
                    'With feedback, actual actuators and controller equilibrium states respond. Solved commands remain fixed except the requested command column; integral and custom-state rates remain zero. These equilibrium derivatives do not establish closed-loop stability.',
                    'Distributed aerodynamic coefficients follow steady eqs. 220–229: lift/profile loads on beams, excluding direct point-object, engine and apparent-mass loads. Fluid coefficients include them.',
                    'Alpha/beta columns use radians. u is fractional speed; p/q/r are normalized rates in base stability axes. Flap/engine columns retain file setting units.',
                    'Automatic PG Mach varies with perturbed speed; a specified PG Mach stays fixed. Local section Mach follows the perturbed flow.',
                    ('Section derivatives include changes in the source averaged endpoint transform and averaged constitutive law. They are element constitutive estimates, not sensor-anchor values or endpoint extrema.' if source_sections else
                     'Section derivatives include rotation of the local axes and load-dependent constitutive recovery along the implicit equilibrium response. They are material-midpoint samples, not endpoint extrema.'),
                    'Shell strain uses Cshell/Nshell measured from the tension axis; torsional shear stress requires positive Atshell. Missing shell data remain null. Normal stress, strength margins and derivatives of absolute strain bounds/stress magnitudes are not inferred.',
                    'Numerical tangent and mesh refinement are required; this is not a proof of stability or ASWING executable parity.'])

    if _audit is not None:
        _audit(dict(output_phase_seconds=perf_counter()-phase_start))
    return result
