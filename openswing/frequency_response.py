"""Forced harmonic response of the complete continuous descriptor residual.

Unsteady formulation §§9.4 and 13.2: (i omega M - A) xhat = B uhat.
The full pencil is solved so algebraic/direct response is retained; a modal
truncation would require additional quasi-static correction.
"""
from dataclasses import replace
from copy import deepcopy
import warnings
import numpy as np
from scipy.linalg import lu_factor, lu_solve, get_lapack_funcs, LinAlgWarning
from scipy.sparse import issparse, csc_matrix, diags
from scipy.sparse.linalg import splu, LinearOperator, onenormest
from .aero import AnalysisError
from .ground import vector3
from .linear_dynamics import make_system, linearize, output_perturbation, complex_data, state_layout


class HarmonicPole(AnalysisError):
    """No resolved unique harmonic particular solution at this frequency."""


def broken_loop_gain(response):
    """ASWING §13.2 display 1-u/x for a matched, dimensionless H=x/u.

    Scale the complex reciprocal to avoid squaring a very large/small H.
    There is no small-response cutoff: exact zero and overflow are explicit
    gaps. This scalar display is not a multivariable loop-opening operation.
    """
    h=complex(response)
    if not np.isfinite(h):return dict(available=False,error='Matched response is not finite.')
    scale=max(abs(h.real),abs(h.imag))
    if scale==0:return dict(available=False,response_gain=complex_data(h),error='Matched response is zero; 1 - u/x is undefined.')
    x,y=h.real/scale,h.imag/scale
    denominator=x*x+y*y
    if .5<=scale<=2:
        # (H-1)/H avoids subtracting two near-unit numbers when H is near 1.
        c,d=(h.real-1)/scale,h.imag/scale
        value=complex((c*x+d*y)/denominator,(d*x-c*y)/denominator)
    else:value=complex(1-(x/denominator)/scale,(y/denominator)/scale)
    if not np.isfinite(value):return dict(available=False,response_gain=complex_data(h),error='Reciprocal matched response overflows; refine the response calculation.')
    return dict(available=True,response_gain=complex_data(h),value=complex_data(value))


def broken_loop_output(channel):
    """Pair the forcing with the same physical variable in the same units."""
    c=channel
    if c.kind in ('control','power'):
        name=f'{c.kind}.{c.index}'
        return dict(group='operating',key=name,component=None,name=name,unit=c.report['unit'])
    if c.kind=='command':
        return dict(group='feedback',key='measurements_'+c.command,component=None,name=c.command,unit=c.report['unit'])
    if c.kind=='frame_acceleration':
        return dict(group='operating',key=c.quantity,component=None,name=c.quantity,unit=c.report['unit'])
    if c.kind=='frame_target':
        kind,axis=c.quantity.split('.')
        return dict(group='global',key='applied_'+kind,component='xyz'.index(axis),name=c.quantity,unit=c.report['unit'])
    return None


def matched_broken_loop(channel, output):
    match=channel.report['broken_loop_output']
    if match is None:return dict(available=False,error='This forcing has no matching aircraft response for 1 - u/x.')
    value=output.get(match['group'],{}).get(match['key'])
    if value is None:return dict(available=False,error='The matching physical output is undefined at this operating point.')
    h=complex(value['real'],value['imag']) if match['component'] is None else complex(value['real'][match['component']],value['imag'][match['component']])
    return broken_loop_gain(h)


def harmonic_solve(a, m, b, omega, *, shift=0., _structure=None):
    """Solve the original descriptor pencil with row/column equilibration."""
    if not np.isfinite(omega) or omega < 0:
        raise AnalysisError('Angular frequency must be finite and nonnegative, in rad/input T.')
    if not np.isfinite(shift) or shift < 0:
        raise AnalysisError('Laplace damping must be finite and nonnegative, in 1/input T.')
    if issparse(a) or issparse(m):
        return sparse_harmonic_solve(a,m,b,omega,shift=shift,_structure=_structure)
    k = (shift+1j*omega)*m-a
    b = np.asarray(b, dtype=complex)
    rows = np.maximum(np.max(abs(k), axis=1), 1e-30)
    rowed = k/rows[:, None]
    columns = np.maximum(np.max(abs(rowed), axis=0), 1e-30)
    scaled = rowed/columns
    with warnings.catch_warnings():
        warnings.simplefilter('error', LinAlgWarning)
        try:
            factor = lu_factor(scaled)
        except (LinAlgWarning, ValueError) as exc:
            raise HarmonicPole('Singular harmonic pencil: a pole, unconstrained motion or zero-frequency free-flight integrator.') from exc
    reciprocal, info = get_lapack_funcs('gecon', (scaled,))(factor[0], np.linalg.norm(scaled, 1))
    if info or not np.isfinite(reciprocal) or reciprocal < 1e-12:
        raise HarmonicPole('Harmonic pencil is singular or too ill-conditioned at this frequency; inspect resonance, constraints and frequency/mesh refinement.')
    rhs = b/rows[:, None] if b.ndim == 2 else b/rows
    scaled_x = lu_solve(factor, rhs)
    x = scaled_x/columns[:, None] if b.ndim == 2 else scaled_x/columns
    residual = k@x-b
    xx = x[:, None] if x.ndim == 1 else x
    bb = b[:, None] if b.ndim == 1 else b
    rr = residual[:, None] if residual.ndim == 1 else residual
    backward = np.linalg.norm(rr, axis=0)/(np.linalg.norm(k)*np.linalg.norm(xx, axis=0)+np.linalg.norm(bb, axis=0)+1e-30)
    relative = np.max(abs(rr)/rows[:, None], axis=0)/np.maximum(1., np.max(abs(bb)/rows[:, None], axis=0))
    if not np.all(np.isfinite(x)) or max(backward, default=0) > 1e-9 or max(relative, default=0) > 1e-7:
        raise AnalysisError('Harmonic response fails the original full-equation residual check.')
    return x, dict(reciprocal_condition=float(reciprocal), backward_errors=backward.tolist(),
                   scaled_residuals=relative.tolist())


def sparse_harmonic_solve(a,m,b,omega,*,shift=0.,_structure=None):
    """Full descriptor solve, storing exact nonzeros rather than dense zeros.

    Sparse pivoted LU retains every matrix entry. The inverse one-norm estimate
    uses solves with both the factor and its conjugate transpose, with the same
    condition gate as the dense path. No modal reduction or entry cutoff.
    """
    k=((shift+1j*omega)*csc_matrix(m)-csc_matrix(a)).tocsc()
    k.sum_duplicates();k.eliminate_zeros()
    b=np.asarray(b,dtype=complex)
    rows=np.maximum(abs(k).max(axis=1).toarray().ravel(),1e-30)
    rowed=diags(1/rows)@k
    columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
    scaled=(rowed@diags(1/columns)).tocsc()
    # Keep the original pencil for full residual checks and the fully scaled
    # one for factorization. The row-only intermediate can otherwise retain
    # another large complex sparse matrix throughout beam elimination/LU.
    del rowed
    norm=float(abs(scaled).sum(axis=0).max())
    if _structure is not None:
        # Exact beam factors use their own reduced matrices. Retain only the
        # original full pencil for residuals, not a duplicate scaled copy.
        del scaled
        try:factor=_structure.factor(a,m,shift+1j*omega,rows,columns)
        except (RuntimeError,ValueError,np.linalg.LinAlgError):
            return sparse_harmonic_solve(a,m,b,omega,shift=shift)
    else:
        try:factor=splu(scaled)
        except RuntimeError as exc:
            raise HarmonicPole('Singular harmonic pencil: a pole, unconstrained motion or zero-frequency free-flight integrator.') from exc
    inverse=LinearOperator(k.shape,matvec=factor.solve,matmat=factor.solve,
        rmatvec=lambda x:factor.solve(x,trans='H'),rmatmat=lambda x:factor.solve(x,trans='H'),dtype=complex)
    # t=1 is deterministic (no random sign columns), as in classical Hager
    # one-norm estimation. This is an estimate, like LAPACK GECON, not an SVD.
    try:reciprocal=1/(norm*onenormest(inverse,t=1))
    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):
        if _structure is not None:return sparse_harmonic_solve(a,m,b,omega,shift=shift)
        raise
    # Optional elimination must not change the original near-pole decision.
    # Use the full factorization in a conservative band above that gate.
    if _structure is not None and (not np.isfinite(reciprocal) or reciprocal<1e-10):
        return sparse_harmonic_solve(a,m,b,omega,shift=shift)
    if not np.isfinite(reciprocal) or reciprocal<1e-12:
        raise HarmonicPole('Harmonic pencil is singular or too ill-conditioned at this frequency; inspect resonance, constraints and frequency/mesh refinement.')
    rhs=b/rows[:,None] if b.ndim==2 else b/rows
    try:
        solved=factor.solve(rhs)
        if _structure is not None:
            # Form the defect in the original physical equations before row
            # scaling. This also avoids retaining a second full sparse pencil.
            physical=solved/columns[:,None] if b.ndim==2 else solved/columns
            defect=b-k@physical
            defect=defect/rows[:,None] if b.ndim==2 else defect/rows
            solved+=factor.solve(defect)
    except (RuntimeError,ValueError,np.linalg.LinAlgError,FloatingPointError):
        if _structure is not None:return sparse_harmonic_solve(a,m,b,omega,shift=shift)
        raise
    x=solved/columns[:,None] if b.ndim==2 else solved/columns
    residual=k@x-b
    xx=x[:,None] if x.ndim==1 else x
    bb=b[:,None] if b.ndim==1 else b
    rr=residual[:,None] if residual.ndim==1 else residual
    backward=np.linalg.norm(rr,axis=0)/(np.linalg.norm(k.data)*np.linalg.norm(xx,axis=0)+np.linalg.norm(bb,axis=0)+1e-30)
    relative=np.max(abs(rr)/rows[:,None],axis=0)/np.maximum(1.,np.max(abs(bb)/rows[:,None],axis=0))
    if not np.all(np.isfinite(x)) or max(backward,default=0)>1e-9 or max(relative,default=0)>1e-7:
        if _structure is not None:return sparse_harmonic_solve(a,m,b,omega,shift=shift)
        raise AnalysisError('Harmonic response fails the original full-equation residual check.')
    return x,dict(reciprocal_condition=float(reciprocal),backward_errors=backward.tolist(),scaled_residuals=relative.tolist(),
                  factor_dimension=getattr(factor,'dimension',a.shape[0]),
                  beam_equations_eliminated=0 if _structure is None else len(_structure.rows))


class HarmonicInput:
    def __init__(self, system, specification, index):
        self.system = system
        model, c = system.network.model, system.condition
        if isinstance(specification,str) and specification.startswith('command.'):
            self.command=specification.removeprefix('command.')
            if system.feedback is None or self.command not in system.feedback.signals:
                raise AnalysisError('Harmonic command must name a measurement selected by the active controller.')
            from .feedback import CHANNELS,channel
            self.kind='command';self.scale=system.feedback.signal_scales[self.command]
            self.report=dict(name=specification,kind=self.kind,unit=CHANNELS[channel(self.command,model)[0]][2],scale=self.scale)
            return
        if isinstance(specification, str):
            # Unit-amplitude perturbations of active frame constraints. The
            # common residual carries both the physical and kinematic effects.
            if specification.startswith(('target.', 'acceleration.', 'angular_acceleration.')):
                if system.frame=='fixed':
                    raise AnalysisError('Harmonic frame inputs require prescribed, free or mixed motion.')
                constraints=system.network.operating.constraints
                targets={c.quantity:c.target for c in constraints}
                unknowns={c.variable for c in constraints}
                self.kind='frame_target' if specification.startswith('target.') else 'frame_acceleration'
                self.quantity=specification.removeprefix('target.')
                if self.kind=='frame_target':
                    if self.quantity not in targets:raise AnalysisError('Harmonic load target must be an active frame constraint.')
                    self.initial=targets[self.quantity]
                    self.scale=system.network.F*(system.L if self.quantity.startswith('moment.') else 1.)
                    unit='input F L' if self.quantity.startswith('moment.') else 'input F'
                else:
                    parts=specification.split('.')
                    if len(parts)!=2 or parts[1] not in ('x','y','z'):
                        raise AnalysisError('Harmonic acceleration must name an xyz component.')
                    if specification in unknowns:raise AnalysisError('Harmonic acceleration conflicts with an active frame load target.')
                    self.attribute,self.index=parts[0],'xyz'.index(parts[1])
                    self.initial=float(getattr(system.motion,self.attribute)[self.index])
                    self.scale=system.Ascale if self.attribute=='acceleration' else system.W**2
                    unit='input L/T^2' if self.attribute=='acceleration' else 'rad/input T^2'
                self.report=dict(name=specification,kind=self.kind,unit=unit,scale=self.scale,base_value=self.initial)
                return
            parts = specification.split('.')
            if len(parts) != 2 or parts[0] not in ('control', 'power') or not parts[1].isdigit():
                raise AnalysisError('Harmonic inputs must be declared controls, controller commands, active frame targets, prescribed accelerations or gust objects.')
            self.kind, self.index = parts[0], int(parts[1])
            declared = model.controls if self.kind == 'control' else model.engine_controls
            if c is None or self.index not in declared:
                raise AnalysisError(f'Undeclared harmonic input: {specification}.')
            self.attribute = 'controls' if self.kind == 'control' else 'powers'
            setting = getattr(c, self.attribute).get(self.index, 0.)
            self.scale = max(1., abs(setting))
            unit = 'file flap setting' if self.kind == 'control' else 'file engine setting'
            self.report = dict(name=specification, kind=self.kind, unit=unit, scale=self.scale)
            command=('F' if self.kind=='control' else 'E')+str(self.index)
            if system.feedback is not None and command in system.feedback.bias:
                self.command=command
                self.report['closed_loop_command']=command
            return
        if not isinstance(specification, dict) or specification.get('kind') != 'gust':
            raise AnalysisError('Unsupported harmonic input specification.')
        allowed = {'kind', 'name', 'direction', 'span_direction', 'span_mode', 'symmetry', 'span_reference', 'wave'}
        if set(specification)-allowed:
            raise AnalysisError('Unrecognized harmonic gust parameters: '+', '.join(sorted(set(specification)-allowed)))
        if c is None:
            raise AnalysisError('Harmonic gusts require an aerodynamic FlightCondition.')
        self.kind = 'gust'
        self.wave = specification.get('wave', 'convected')
        self.symmetry = specification.get('symmetry', 'cosine')
        self.order = specification.get('span_mode', 0)
        self.span = float(specification.get('span_reference', model.reference[0, 2]))
        if self.wave not in ('convected', 'uniform') or self.symmetry not in ('cosine', 'sine'):
            raise AnalysisError('Gust wave must be convected/uniform and symmetry cosine/sine.')
        if type(self.order) is not int or self.order < 0 or (self.order == 0 and self.symmetry == 'sine'):
            raise AnalysisError('Gust span mode must be a nonnegative integer; sine mode zero is identically zero.')
        if not np.isfinite(self.span) or self.span <= 0:
            raise AnalysisError('Gust reference span must be finite and positive.')
        self.direction = vector3(specification.get('direction', (0, 0, 1)), 'Harmonic gust direction').copy()
        self.velocity = system.R0@system.U0
        speed = np.linalg.norm(self.velocity)
        if self.wave == 'convected' and speed < 1e-8*system.V:
            raise AnalysisError('A convected gust needs nonzero Earth translation of the body origin; use a uniform temporal gust instead.')
        span_direction = vector3(specification.get('span_direction', system.R0[:, 1]), 'Harmonic gust span direction').copy()
        if speed > 1e-8*system.V:
            span_direction -= self.velocity*np.dot(span_direction, self.velocity)/speed**2
        if min(np.linalg.norm(self.direction), np.linalg.norm(span_direction)) < 1e-10:
            raise AnalysisError('Gust and transverse span directions must be nonzero and not parallel to the flight path.')
        self.direction /= np.linalg.norm(self.direction)
        self.ell = 2*np.pi*self.order/self.span*span_direction/np.linalg.norm(span_direction)
        self.origin = system.position
        self.scale = c.speed
        name = specification.get('name', f'gust_{index+1}')
        if not isinstance(name, str) or not name.strip():
            raise AnalysisError('Harmonic input name must be a nonempty string.')
        self.report = dict(name=name, kind='gust', unit='input L/T', scale=self.scale,
            direction_earth=self.direction.tolist(), span_direction_earth=(span_direction/np.linalg.norm(span_direction)).tolist(),
            span_mode=self.order, symmetry=self.symmetry, span_reference=self.span, wave=self.wave,
            phase_origin_earth=self.origin.tolist(), convection_velocity_earth=self.velocity.tolist())

    def at_frequency(self, omega):
        if self.kind != 'gust':
            def forcing(part, increment):
                def apply(state, options):
                    increment_real=increment if part==0 else 0.
                    if self.kind=='frame_target':
                        return {**options,'operating_targets':{**options.get('operating_targets',{}),self.quantity:self.initial+increment_real}}
                    if self.kind=='frame_acceleration':
                        motion=options['motion_override']
                        values=getattr(motion,self.attribute).copy();values[self.index]+=increment_real
                        c=options['condition_override']
                        return {**options,'motion_override':replace(motion,**{self.attribute:values}),
                                'condition_override':None if c is None else replace(c,**{self.attribute:values})}
                    if hasattr(self,'command'):
                        controller=self.system.feedback
                        base={**controller.commands,**controller.bias}[self.command]
                        return {**options,'feedback_commands':{self.command:base+(increment if part==0 else 0.)}}
                    c = options['condition_override']
                    settings = dict(getattr(c, self.attribute))
                    settings[self.index] = settings.get(self.index, 0.)+(increment if part == 0 else 0.)
                    return {**options, 'condition_override':replace(c, **{self.attribute:settings})}
                return apply
            return forcing, None
        k = np.zeros(3) if self.wave == 'uniform' else omega*self.velocity/np.dot(self.velocity, self.velocity)
        def argument(v):
            return '+'.join(f'({v[i]:.17g})*({axis}-({self.origin[i]:.17g}))' for i, axis in enumerate('xyz'))
        stream, span = argument(k), argument(self.ell)
        parity = 'cos' if self.symmetry == 'cosine' else 'sin'
        def forcing(part, increment):
            function = 'cos' if part == 0 else 'sin'
            expression = f'{function}({stream})*{parity}({span})'
            gust = dict(type='expression', components=[f'({increment*d:.17g})*({expression})' for d in self.direction])
            def apply(state, options):
                c = options['condition_override']
                previous = c.gust
                combined = gust if not previous or previous.get('type', 'none') == 'none' else dict(type='sum', fields=[previous, gust])
                return {**options, 'condition_override':replace(c, gust=combined)}
            return apply
        n = self.system.network
        dr = (self.system.r0[n.b]-self.system.r0[n.a])@self.system.R0.T
        phase = float(max(np.max(abs(dr@k)), np.max(abs(dr@self.ell))))
        return forcing, dict(streamwise_wavevector_earth=k.tolist(), spanwise_wavevector_earth=self.ell.tolist(),
                             maximum_element_phase_increment=phase, spatial_resolution_warning=phase > np.pi/4)


class InputInfluences:
    """Bounded exact influence maps owned by one frozen dynamic system."""
    def __init__(self, system):
        from .tangent_influences import TangentInfluences
        self.owner = system
        self.tangent = TangentInfluences(local_geometry=True)


def constant_input_key(channel):
    """Exact definition of a frequency-independent physical input column."""
    if type(channel) is not HarmonicInput or channel.kind not in (
            'control','power','frame_target','frame_acceleration'):
        return None
    from .equilibrium_tangent import digest
    return digest({key:value for key,value in vars(channel).items() if key!='system'})


def input_partials(system, channels, omega, step, *, constant_inputs=None, influence_cache=None, _field_tangent=None):
    """Retain unchanged geometry maps between full physical input stencils.

    The input definition and its frequency-dependent gust phase are evaluated
    afresh. This shares only exact influence/kinematic entries whose arguments
    still match; it never freezes changed circulation, loads or jet strengths.
    """
    if _field_tangent is not None and (_field_tangent.owner is not system or _field_tangent.step!=step):
        raise ValueError('Output field derivatives belong to a different system or difference step.')
    if influence_cache is None:
        return _input_partials(system, channels, omega, step, constant_inputs=constant_inputs,field_tangent=_field_tangent)
    if influence_cache.owner is not system:
        raise ValueError('Input influence matrices belong to a different dynamic system.')
    n = system.network
    previous = n.tangent_influences
    n.tangent_influences = influence_cache.tangent
    n.aero_key = None
    try:
        return _input_partials(system, channels, omega, step, constant_inputs=constant_inputs,field_tangent=_field_tangent)
    finally:
        n.tangent_influences = previous
        n.aero_key = None


def _input_partials(system, channels, omega, step, *, constant_inputs=None, field_tangent=None):
    """Original full stencils, optionally reusing this frozen model's columns.

    Non-gust forcing has no frequency argument in its physical definition.
    A gust in the same sweep must not invalidate those independent columns.
    Every gust retains its own frequency-dependent spatial phase and stencil.
    """
    zero = np.zeros(system.size)
    n = system.network
    pending = any(c.kind != 'initial' and (c.kind == 'gust' or constant_inputs is None
        or index not in constant_inputs) for index,c in enumerate(channels))
    baseline = system.residual(zero, zero) if pending else None
    clips = () if not pending or n.aero_cached is None else tuple(e['power_clipped'] for e in n.aero_cached['engines'])
    columns, forcings, profiles = [], [], []
    for index,channel in enumerate(channels):
        if constant_inputs is not None and index in constant_inputs:
            column,forcing,profile=constant_inputs[index]
            columns.append(column);forcings.append(forcing);profiles.append(deepcopy(profile));continue
        if type(channel) is HarmonicInput and channel.kind=='gust':
            from .gust_tangent import gust_column, GustDerivativeUnavailable
            try:
                column,field_column=gust_column(system,channel,omega,step,field_tangent)
            except GustDerivativeUnavailable:
                pass
            else:
                forcing,profile=channel.at_frequency(omega)
                if field_column is not None:forcing._output_fields=(field_tangent,step,field_column)
                columns.append(column);forcings.append(forcing);profiles.append(profile)
                continue
        if type(channel) is HarmonicInput and channel.kind=='power':
            from .power_tangent import power_column, PowerDerivativeUnavailable
            try:
                column,field_column=power_column(system,channel,step,field_tangent)
            except PowerDerivativeUnavailable:
                pass
            else:
                forcing,profile=channel.at_frequency(omega)
                if field_column is not None:forcing._output_fields=(field_tangent,step,field_column)
                if constant_inputs is not None:
                    frozen=column.copy();frozen.flags.writeable=False
                    constant_inputs[index]=(frozen,forcing,deepcopy(profile))
                columns.append(column);forcings.append(forcing);profiles.append(profile)
                continue
        if channel.kind == 'initial':
            column=channel.rhs.astype(complex);forcing=None
            profile=dict(kind='initial', laplace_shift=channel.shift)
        else:
            forcing, profile = channel.at_frequency(omega)
            h = step*channel.scale
            parts = [];field_parts=[]
            collect=field_tangent is not None and field_tangent.active and field_tangent.matrix is not None
            for part in (0, 1):
                if part == 1 and channel.kind != 'gust':
                    if collect:field_parts.append(np.zeros(field_tangent.rows))
                    parts.append(np.zeros(system.size)); continue
                values = [];field_values=[]
                for factor in (1, -1, 2, -2):
                    applied=forcing(part,factor*h)
                    if collect:
                        value,field_value=field_tangent.probe(lambda:system.residual(zero,zero,forcing=applied),zero,zero,applied)
                        values.append(value);field_values.append(field_value)
                    else:values.append(system.residual(zero,zero,forcing=applied))
                    if n.aero_cached is not None and tuple(e['power_clipped'] for e in n.aero_cached['engines']) != clips:
                        raise AnalysisError('Harmonic input stencil crosses an engine power-clipping transition.')
                if system.feedback is not None and system.feedback.needs_side_check:
                    from .control_expressions import check_sides
                    rows=slice(system.feedback_start,None)
                    check_sides(*(v[rows] for v in (baseline,values[1],values[0],values[3],values[2])),h)
                parts.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*h))
                if collect and field_tangent.active:
                    field_parts.append((8*(field_values[0]-field_values[1])-(field_values[2]-field_values[3]))/(12*h))
            column=parts[0]+1j*parts[1]
            if collect and field_tangent.active:
                field_column=field_parts[0]+1j*field_parts[1];field_column.flags.writeable=False
                forcing._output_fields=(field_tangent,step,field_column)
        if constant_inputs is not None and channel.kind != 'gust':
            frozen=column.copy();frozen.flags.writeable=False
            constant_inputs[index]=(frozen,forcing,deepcopy(profile))
        columns.append(column);forcings.append(forcing);profiles.append(profile)
    return np.column_stack(columns), forcings, profiles


def frequency_grid(frequencies):
    """Validate angular frequencies without merging nearby physical samples."""
    try:
        if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.integer,np.floating)) for v in frequencies):raise ValueError()
        omega=np.asarray(frequencies,dtype=float)
    except (TypeError,ValueError,OverflowError) as exc:
        raise AnalysisError('Frequencies must be finite numeric angular frequencies [rad/input T].') from exc
    if omega.ndim!=1 or not len(omega) or not np.all(np.isfinite(omega)) or np.any(omega<0) or np.any(np.diff(omega)<=0):
        raise AnalysisError('Frequencies must be a nonempty, strictly increasing list of nonnegative angular frequencies [rad/input T].')
    return omega


class FrequencyAnalysis:
    """One owned loaded base, descriptor pencil and set of physical inputs.

    Additional frequencies reuse this exact linearization. The object belongs
    to the local process; returned JSON reports contain independent copies.
    """
    def __init__(self,model,condition,panels=8,*,inputs=None,frame='fixed',step=1e-5,
                 matrices=False,progress=None,initial_shift=0.,initial_rank_tolerance=1e-9,
                 _base_analysis=None,**base_options):
        if (base_options.get('quiescent_density') is not None
                and base_options.get('structural_operator') != 'drela-fixed-still-air-v1'):
            raise AnalysisError('Quiescent fluid is currently supported for fixed-frame modes only, not frequency response.')
        # Own the model through its validated physical ASW representation.
        # SciPy spline objects carry a non-copyable array-module reference in
        # Pyodide; reparsing also rebuilds every spline from its actual data.
        from .asw import parse_asw
        from .beam_spline import NATURAL
        model=parse_asw(model.dumps(), beam_interpolation=model.beam_interpolation)
        condition,panels,inputs,base_options=deepcopy((condition,panels,inputs,base_options))
        from .equilibrium_tangent import digest,identity
        operator=dict(model=model.dumps(),condition=condition,panels=panels,frame=frame,step=step,options=base_options)
        if model.beam_interpolation != NATURAL:
            operator['beam_interpolation']=model.beam_interpolation
        key=digest(operator)
        initial_inputs=any(isinstance(spec,dict) and spec.get('kind')=='initial' for spec in (inputs or []))
        reused_model=(isinstance(_base_analysis,FrequencyAnalysis)
            and _base_analysis._operator_key==key and _base_analysis.system.feedback is None
            and issparse(_base_analysis.a)==(_base_analysis.system.size>256 and not initial_inputs)
            and _base_analysis._operator_signature==identity(_base_analysis.system))
        if reused_model:
            system=_base_analysis.system
            continuation=_base_analysis.template['diagnostics']['continuation_steps']
            if progress is not None:progress('matrix_reuse',system.size,system.size)
        else:
            if progress is not None:progress('base',0,1)
            system, continuation = make_system(model, condition, panels, frame=frame,
                progress=progress,structured_base=True,
                _retain_equilibrium_tangent=(step,lambda size:size>256 and not initial_inputs),**base_options)
        if inputs is None:
            inputs = [f'control.{k}' for k in model.controls]+[f'power.{k}' for k in model.engine_controls]
        if not isinstance(inputs, (tuple, list)) or not inputs:
            raise AnalysisError('Select at least one harmonic input or initial disturbance.')
        from .initial_response import InitialInput, ConsistentSubspace
        channels = [(InitialInput if isinstance(specification, dict) and specification.get('kind') == 'initial' else HarmonicInput)(system, specification, i)
                    for i, specification in enumerate(inputs)]
        if len({c.report['name'] for c in channels}) != len(channels):
            raise AnalysisError('Harmonic input names must be distinct.')
        for c in channels:c.report['broken_loop_output']=broken_loop_output(c)
        use_sparse=system.size>256 and not any(c.kind=='initial' for c in channels)
        if not reused_model and progress is not None and getattr(system,'_equilibrium_tangent',None) is not None:
            progress('equilibrium_reuse',system.network.size,system.size)
        def tangent_progress(current,total):
            if current<=system.size:progress('linearizing',current,system.size)
            else:progress('inertia',current-system.size,total-system.size)
        if reused_model:a,m=_base_analysis.a,_base_analysis.m
        else:a, m = linearize(system, step, None if progress is None else tangent_progress,sparse=use_sparse,_output_fields=use_sparse)
        initial_subspace = None
        if any(c.kind == 'initial' for c in channels):
            initial_subspace = ConsistentSubspace(a, m, system.dynamic_indices, system.W, initial_rank_tolerance)
            for c in channels:
                if c.kind == 'initial':c.prepare(initial_subspace, initial_shift, step)
        base = system.base_report(); base['continuation_steps'] = continuation
        base['limitations'][0] = 'Loaded base state for the frozen harmonic linearization.'
        self.system,self.channels,self.a,self.m=system,channels,a,m
        self._operator_key,self._operator_signature=key,identity(system)
        self.step,self.matrices,self.constant_inputs=step,matrices,{}
        self.input_influences = _base_analysis.input_influences if reused_model else InputInfluences(system)
        self.output_fields=getattr(system,'_output_field_tangent',None) if use_sparse else None
        self._input_keys={i:constant_input_key(channel) for i,channel in enumerate(channels)}
        if reused_model:
            retained={}
            for i,entry in _base_analysis.constant_inputs.items():
                key=_base_analysis._input_keys.get(i)
                if key is not None and key==constant_input_key(_base_analysis.channels[i]):
                    retained[key]=entry
            for i,channel in enumerate(channels):
                entry=retained.get(self._input_keys[i])
                if entry is None:continue
                column,previous_forcing,profile=entry
                # Bind the forcing to this analysis's new channel. The old
                # closure refers to a channel the previous caller still owns.
                forcing,_=channel.at_frequency(0.)
                field_column=getattr(previous_forcing,'_output_fields',None)
                if field_column is not None and field_column[0] is self.output_fields and field_column[1]==step:
                    forcing._output_fields=field_column
                self.constant_inputs[i]=(column,forcing,deepcopy(profile))
        for matrix in (a,m):
            if issparse(matrix):
                for values in (matrix.data,matrix.indices,matrix.indptr):values.flags.writeable=False
            else:matrix.flags.writeable=False
        from .applied_load_outputs import AppliedLoadTangent,AppliedLoadUnavailable
        self.applied_loads=getattr(_base_analysis,'applied_loads',None) if reused_model else None
        if self.applied_loads is None or not self.applied_loads.matches(system,a,m,step):
            try:self.applied_loads=AppliedLoadTangent(system,a,m,step)
            except AppliedLoadUnavailable as exc:
                self.applied_loads=None
                load_report=dict(method='physical output stencils',fallback=str(exc))
        if self.applied_loads is not None:load_report=self.applied_loads.report()
        n = system.network
        self.harmonic_structure=None
        structure_report=dict(method='full descriptor factorization')
        if reused_model:
            self.harmonic_structure=_base_analysis.harmonic_structure
            structure_report=deepcopy(_base_analysis.template['diagnostics']['harmonic_structure'])
        elif use_sparse:
            from .harmonic_structure import ReusableBeamStructure,StructureUnavailable
            if progress is not None:progress('frequency_structure',0,1)
            try:
                self.harmonic_structure=ReusableBeamStructure(a,m,
                    np.r_[np.arange(6*n.ne),np.arange(6*(n.ne+n.nn),n.gamma_start)],
                    np.arange(6*(n.nn+n.ne)),np.arange(n.size,system.frame_start),
                    np.arange(system.velocity_start,system.frame_start))
            except (StructureUnavailable,RuntimeError,np.linalg.LinAlgError) as exc:
                structure_report['fallback']=str(exc)
            else:structure_report=deepcopy(self.harmonic_structure.report)
        result = dict(analysis='frequency_response', converged=True, base=base,
            frame_mode=frame, frame_load_targets=base['modal_base']['load_targets'], inputs=[c.report for c in channels], samples=[],
            controller=None if system.feedback is None else system.feedback.report(),
            diagnostics=dict(full_dimension=system.size, state_layout=state_layout(system), difference_step=step, state_difference_order=4,
                             matrix_storage='sparse full descriptor' if use_sparse else 'dense full descriptor',
                             loaded_matrices_reused=reused_model,
                             loaded_input_columns_reused=len(self.constant_inputs),
                             harmonic_structure=structure_report,
                             output_linearization=dict(method='full physical output stencils') if self.output_fields is None else self.output_fields.report(),
                             applied_load_linearization=load_report,
                             state_linearization=system.state_derivative_diagnostics,
                             derivative_linearization=system.derivative_diagnostics, input_difference_order=4,
                             base_residual=base['modal_base']['continuous_residual'], continuation_steps=continuation,
                             material_damping=n.damping_report(),
                             equation='(i omega M - A) xhat = B; x(t)=base+Re(xhat exp(i omega t)); unit input amplitude.',
                             broken_loop_definition='1 - u/x = 1 - 1/H, H=x/u for the matching physical command/response, in identical units. Other commanded increments are zero.',
                             units='Angular frequency rad/input T; frequency cycles/input T; response per stated input unit.'),
            limitations=[
                'Experimental full-descriptor harmonic particular response. ASWING discrete parity and measured frequency-response validation remain unverified.',
                'Base coefficients are frozen. Stability and transient decay are not established by a Bode solve; check eigenmodes and the base drift/timescale.',
                'Real inertia, apparent mass, material damping and direct input/rate-dependent loads are retained. Circulation uses the aerodynamic-lag setting recorded in the base. The gust response is not exact Sears/Theodorsen theory.',
                'Convected gusts satisfy omega = k dot U_E at the body origin. Spatial phase and span parity use the loaded base and are sampled at the actual fluid load/control locations.',
                'Frequency singularities are reported as missing responses, never filled by a pseudoinverse. Zero-frequency free-flight position/attitude integrators commonly make the full pencil singular.',
                'Controls are held or constrained by declared feedback laws. Controlled-actuator and selected measurement commands act through the complete controller residual, including integrated errors. Active frame load targets and prescribed accelerations can be harmonic inputs. General inverse dynamic constraints remain pending.',
                'Broken-loop data implements the documented scalar display 1-u/x only for matched command/response quantities. It is not a unique multivariable return ratio or a gain/phase-margin certificate. No controller or plant equation is removed; other loops retain their solved configuration. Zero response and reciprocal overflow are gaps.',
                'Input amplitude and display scale must remain small enough for the linearization. Refine the mesh, frequency range and difference step; monitor gust spatial phase resolution.'
            ])
        if not result['diagnostics']['material_damping']['passive']:
            result['limitations'].append('The componentwise material damping fails the finite-strain passivity diagnostic. This model may add energy; inspect its eigenmodes and constitutive law before interpreting resonances.')
        if getattr(n, 'source_dynamic', False):
            result['structural_operator'] = n.structural_operator
            flowing = getattr(n, 'source_airflow', False)
            result['vacuum'] = not (getattr(n, 'source_quiescent', False) or flowing)
            if not flowing:
                result['condition'] = None
            if getattr(n, 'source_quiescent', False):
                result['fluid'] = deepcopy(base['fluid'])
            result['limitations'][0] = ('Full-descriptor response of the source endpoint-average structural operator. '
                'Historical ASWING discrete/executable parity remains unverified.')
            result['limitations'][2] = ('Real inertia and material damping use the same source equations as eigenmodes. '
                'The explicit still-air policy also retains thin-strip apparent inertia. No mean airflow or circulation is present.')
            result['limitations'][3] = 'Inputs are compatible structural initial disturbances and, for moving vacuum frames, active frame load targets or prescribed accelerations.'
            result['limitations'][5] = 'Feedback, aerodynamic controls and gusts are unavailable for these source structural operators.'
            if flowing:
                result['limitations'][2] = ('Real inertia/damping use the source endpoint equations; circulation, circulation-rate '
                    'and apparent-fluid loads use Glauert aerodynamic sections and symmetric box-wrench transfer. '
                    'The stationary still-air policy uses different fluid quadrature.')
                result['limitations'][3] = ('Aerodynamic controls, engine settings, gusts, compatible initial disturbances and canonical frame '
                    'load/acceleration inputs act through the same coupled residual.')
                result['limitations'][5] = 'Controllers and stepped axes remain unsupported by this source policy.'
        if matrices:
            result['matrices'] = dict(A=(a.toarray() if issparse(a) else a).tolist(), M=(m.toarray() if issparse(m) else m).tolist())
        if initial_subspace is not None:
            result['diagnostics']['initial_conditions'] = initial_subspace.report
            result['diagnostics']['initial_equation'] = '(s M-A) X=M x0; transform(xdot)=s X-x0; s=initial_shift+i omega. Initial spectra carry one additional input time unit.'
            result['limitations'] += [
                'Initial disturbances are infinitesimal physical perturbations about the loaded base; omitted dynamic fields are zero. Loads, reactions, dynamic accelerations and actual actuators are completed from the full finite constraint subspace.',
                'Initial spectra are one-sided Laplace transforms, not periodic transfer functions. Positive initial_shift exponentially weights the time response. The shift must exceed the full resolved spectral abscissa with a numerical margin; this condition depends on rank and tangent refinement.',
                'Rate-dependent outputs use s X-x0, including apparent-mass, damping and sensor feedthrough. A complex spectral shape is not a physical harmonic animation or a nonlinear trajectory.']
        self.template = deepcopy(result)

    def solve(self,frequencies,progress=None):
        omega=frequency_grid(frequencies)
        system,channels,a,m=self.system,self.channels,self.a,self.m
        step,matrices=self.step,self.matrices
        fields=self.output_fields
        if fields is not None and not fields.matches(system,step):fields=None
        loads=self.applied_loads
        if loads is not None and not loads.matches(system,a,m,step):loads=None
        load_applications=loads.applications if loads is not None else 0
        load_fallbacks=dict(loads.fallbacks) if loads is not None else {}
        samples = []
        constant_inputs = self.constant_inputs.copy()
        for index, w in enumerate(omega):
            if progress is not None:progress('frequency',index,len(omega))
            b, forcings, profiles = input_partials(system, channels, w, step,
                constant_inputs=constant_inputs, influence_cache=self.input_influences,_field_tangent=fields)
            sample = dict(omega=float(w), frequency=float(w/(2*np.pi)), gust_profiles=deepcopy(profiles))
            groups = {}
            for column, channel in enumerate(channels):groups.setdefault(channel.shift if channel.kind == 'initial' else 0., []).append(column)
            responses = [None]*len(channels)
            diagnostic = dict(backward_errors=[None]*len(channels), scaled_residuals=[None]*len(channels), reciprocal_conditions=[None]*len(channels),
                              factor_dimensions=[None]*len(channels),beam_equations_eliminated=[None]*len(channels))
            errors = []
            for shift, columns in groups.items():
                try:
                    response, checks = harmonic_solve(a, m, b[:, columns], w, shift=shift,
                        _structure=self.harmonic_structure)
                except HarmonicPole as exc:
                    errors.append(str(exc))
                    for column in columns:responses[column] = dict(input=channels[column].report['name'], converged=False, error=str(exc), output=None)
                    continue
                for j, column in enumerate(columns):
                    channel = channels[column];vector = response[:, j]
                    rate = (shift+1j*w)*vector-(channel.initial if channel.kind == 'initial' else 0.)
                    direct=None
                    if loads is not None and type(channel) is HarmonicInput:
                        direct=loads.input(forcings[column],b[:,column])
                    output = output_perturbation(system, vector, rate, step, forcing=forcings[column], input_scale=channel.scale,
                        _field_tangent=fields,_load_tangent=loads,_load_input=direct)
                    responses[column] = dict(input=channel.report['name'], converged=True, state=complex_data(vector),
                        state_rate=complex_data(rate), output=output, broken_loop=matched_broken_loop(channel,output))
                    for key in ('backward_errors', 'scaled_residuals'):diagnostic[key][column] = checks[key][j]
                    diagnostic['reciprocal_conditions'][column] = checks['reciprocal_condition']
                    diagnostic['factor_dimensions'][column] = checks.get('factor_dimension',system.size)
                    diagnostic['beam_equations_eliminated'][column] = checks.get('beam_equations_eliminated',0)
            resolved = sum(r['converged'] for r in responses)
            diagnostic['reciprocal_condition'] = min((c for c in diagnostic['reciprocal_conditions'] if c is not None), default=0.)
            sample.update(converged=not errors, resolved_inputs=resolved, responses=responses if resolved else [])
            if errors:sample['error'] = '; '.join(dict.fromkeys(errors))
            if resolved:sample['diagnostics'] = diagnostic
            if matrices:
                sample['B'] = complex_data(b)
            samples.append(sample)
            if progress is not None:
                progress('frequency', index+1, len(omega))
        self.constant_inputs=constant_inputs
        if progress is not None:progress('reporting',len(omega),len(omega))
        result=deepcopy(self.template)
        if fields is not None:result['diagnostics']['output_linearization']=fields.report()
        if loads is not None:
            report=loads.report()
            report['applications']-=load_applications
            failures={key:value-load_fallbacks.get(key,0) for key,value in loads.fallbacks.items()
                      if value>load_fallbacks.get(key,0)}
            report['fallback']=failures or None
            result['diagnostics']['applied_load_linearization']=report
        elif self.applied_loads is not None:
            result['diagnostics']['applied_load_linearization']=dict(method='physical output stencils',fallback='Changed operator or physical base.')
        if hasattr(system,'support_output_diagnostics'):
            result['diagnostics']['support_output_linearization']=deepcopy(system.support_output_diagnostics)
        if hasattr(system,'structural_output_diagnostics'):
            result['diagnostics']['structural_output_linearization']=deepcopy(system.structural_output_diagnostics)
        result.update(samples=samples,converged=all(s['converged'] for s in samples))
        return result


def solve_frequency_response(model, condition, panels=8, *, frequencies, inputs=None, frame='fixed',
                             step=1e-5, matrices=False, progress=None, initial_shift=0., initial_rank_tolerance=1e-9, **base_options):
    omega=frequency_grid(frequencies)
    analysis=FrequencyAnalysis(model,condition,panels,inputs=inputs,frame=frame,step=step,
        matrices=matrices,progress=progress,initial_shift=initial_shift,
        initial_rank_tolerance=initial_rank_tolerance,**base_options)
    return analysis.solve(omega,progress)
