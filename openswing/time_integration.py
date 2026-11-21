"""Implicit BDF/Radau integration of the common elastic/circulation/frame equations.

ASWING unsteady theory §12 supplies the variable-step BDF coefficients. The
source moving policy applies BDF to material and Earth Euler coordinates;
legacy policies retain tangent SO(3) differences. Newton trial coordinates and
the OpenSwing Radau extension use continuous local SO(3) charts.
The aircraft frame moves through air with an optional Earth-coordinate gust. Open-loop controls, engines
and prescribed body accelerations can follow documented ASWING time tables.
"""
from dataclasses import dataclass, replace, field, asdict
from copy import copy
import warnings
import numpy as np
from .vector_ops import cross3
from scipy.linalg import lu_factor, lu_solve, LinAlgWarning
from .aero import AnalysisError
from .ground import body_to_earth
from .inertia import Motion, vector
from .local_motion import rotation_matrix as exp, rotation_vector as log
from .network import StaticNetwork, equilibrate, network_result
from .operating import time_operating_constraints, time_constraint_data
from .forcing import TimeForcing
from .gust import gust_field


def bdf_coefficients(step, previous_step=None):
    """First order for startup; second order when previous_step is supplied."""
    if not np.isfinite(step) or step <= 0:
        raise ValueError('Time step must be finite and positive.')
    if previous_step is None:
        return np.array([1., -1., 0.])/step
    if not np.isfinite(previous_step) or previous_step <= 0:
        raise ValueError('Previous time step must be finite and positive.')
    k0 = 1/step+1/(step+previous_step)
    k2 = step/((step+previous_step)*previous_step)
    return np.array([k0, -k0-k2, k2])


def local_position_derivative(network, state, previous, older, coefficients):
    """Differentiate nodal displacement before adding the constant jig position.

    ``network.unpack`` uses r = rj + L*x_translation. The constant rj cancels
    analytically in BDF; reconstructing r first can discard small displacements
    and amplify their rounding through the velocity and apparent-mass loads.
    The displacement chart retains the same physical BDF equations.
    """
    def displacement(sample):
        return sample.x[:6*network.nn].reshape(network.nn, 6)[:, :3]
    result = coefficients[0]*(displacement(state)-displacement(previous))
    if older is not None:
        result += coefficients[2]*(displacement(older)-displacement(previous))
    return network.L*result


def bdf_nonlinear_gate(system, coefficients, requested):
    """Control nonlinear residual amplification for explicit motion targets.

    The scaled derivative gain uses every coefficient in the actual BDF
    stencil. Squaring it is deliberately conservative for both first- and
    second-derivative inverse targets. This is not a force-error bound: old
    predecessor errors, conditioning and temporal truncation remain relevant.
    """
    import math
    from .operating import TimeHistoryConstraint
    from .time_history import TARGETS
    if not np.isfinite(requested) or requested <= 0:
        raise AnalysisError('BDF nonlinear tolerance must be finite and positive.')
    rows=[dict(variable=row.variable,quantity=row.quantity,
               derivative_order=TARGETS[row.quantity].derivative_order)
          for row in system.network.operating.constraints
          if isinstance(row,TimeHistoryConstraint) and TARGETS[row.quantity].derivative_order > 0]
    if not rows:
        return float(requested),dict(name='requested-bdf-tolerance-v1')
    rate=float(system.W)
    if not np.isfinite(rate) or rate <= 0:
        raise AnalysisError('Inverse-history BDF tolerance needs a finite positive rate scale.')
    values=np.asarray(coefficients,dtype=float)
    if values.shape!=(3,) or not np.all(np.isfinite(values)):
        raise AnalysisError('Inverse-history BDF tolerance needs three finite derivative coefficients.')
    try:norm=math.fsum(abs(float(value)) for value in values)
    except OverflowError as exc:
        raise AnalysisError('Inverse-history BDF derivative gain overflows; nonlinear accuracy cannot be represented.') from exc
    gain=max(1.,norm/rate)
    if not np.isfinite(gain):
        raise AnalysisError('Inverse-history BDF derivative gain overflows; nonlinear accuracy cannot be represented.')
    # Sequential division avoids forming gain**2, which can overflow even
    # when gain itself is finite. Never introduce a floor above the derived
    # gate, including when the user's requested tolerance is already tiny.
    gate=(float(requested)/gain)/gain
    if not np.isfinite(gate) or gate <= 0:
        raise AnalysisError('Inverse-history BDF nonlinear tolerance underflows; requested accuracy cannot be represented.')
    return gate,dict(name='inverse-kinematic-bdf-coefficient-l1-squared-v1',
        coefficient_l1=norm,rate_scale=rate,derivative_gain=gain,kinematic_targets=rows)


def attitude_angles(rotation):
    """ASW bank/elevation/heading display angles; dynamics use the matrix."""
    r = np.asarray(rotation)
    horizontal = np.hypot(r[0, 0], r[1, 0])
    elevation = np.arctan2(-r[2, 0], horizontal)
    if horizontal > 1e-10:
        bank, heading = -np.arctan2(r[2, 1], r[2, 2]), -np.arctan2(r[1, 0], r[0, 0])
    else:
        bank, heading = 0., np.arctan2(r[0, 1], r[1, 1])
    return np.rad2deg([bank, elevation, heading])


def rotation_rate(current, previous, older, coefficients, *, body=False):
    """Backward rotational derivative, spatial for nodes or body for frame.

    Anchoring both logarithms at the new state gives second-order accuracy for
    varying rotation axes, without differentiating global rotation-vector or
    Euler coordinates. Both history increments must stay below pi.
    """
    transpose = np.swapaxes(current, -1, -2)
    a = log(transpose@previous if body else previous@transpose)
    b = np.zeros_like(a) if older is None else log(transpose@older if body else older@transpose)
    if max(np.max(np.linalg.norm(a, axis=-1)), np.max(np.linalg.norm(b, axis=-1))) >= np.pi-.05:
        raise AnalysisError('Time-step rotation approaches pi; reduce the time step.')
    return coefficients[1]*a+coefficients[2]*b


@dataclass
class TimeState:
    time: float
    x: np.ndarray
    r: np.ndarray
    Q: np.ndarray
    u: np.ndarray
    w: np.ndarray
    U: np.ndarray
    Omega: np.ndarray
    position: np.ndarray
    orientation: np.ndarray
    gamma: np.ndarray
    feedback: np.ndarray = field(default_factory=lambda:np.empty(0))
    commands: dict = field(default_factory=dict)
    position_history: object = None
    hinge_charts: tuple = field(default_factory=tuple)
    source_angles: object = None
    source_attitude: object = None


def initial_equilibrium(network, options, tolerance, continuation_steps, progress=None):
    """Use the steady sparse solver for an exactly stationary local initial state.

    The entered frame motion, physical t=0 forcing, gravity and posed condition
    stay fixed. Only explicit zero local rates/accelerations and circulation
    rate are removed. General inverse states retain their original path.
    The accepted result is checked in the original unsteady residual.
    """
    local_motion=options.get('elastic_motion')
    from .structured_static import acceleration_load_constraints
    targets=options.get('operating_targets') or {}
    eligible=(acceleration_load_constraints(network) and local_motion is not None
        and all(not np.any(value) for value in local_motion)
        and options.get('circulation_rate') is not None
        and not np.any(options['circulation_rate'])
        and isinstance(targets,dict) and not set(targets)-{c.quantity for c in network.operating.constraints}
        and options.get('history_context') is None
        and set(options) <= {'elastic_motion','circulation_rate','condition_override',
                             'motion_override','gravity_override','operating_targets','history_context'})
    if not eligible:
        return equilibrate(network,tolerance,continuation_steps,progress=progress,**options)
    if np.any(network.damping_times<0) or not np.all(np.isfinite(network.damping_times)):
        raise AnalysisError('Material damping times must be finite and nonnegative for unsteady analysis.')
    from .operating import OperatingSystem
    steady=copy(network)
    # Constraint dictionaries own the changing scalar angle_chart. Their
    # geometry and hinge laws remain shared read-only, as on the copied
    # network; SciPy spline runtime namespaces cannot be deep-copied in WASM.
    steady.constraints=[dict(c) for c in network.constraints]
    steady.condition=options.get('condition_override') or network.condition
    steady.motion=options.get('motion_override') or network.motion
    gravity=options.get('gravity_override')
    if gravity is not None:
        steady.gravity=np.asarray(gravity).copy();steady.gravity_override=True
    constraints=[replace(c,target=targets.get(c.quantity,c.target)) for c in network.operating.constraints]
    steady.operating=OperatingSystem(steady.model,steady.condition,steady.motion,constraints,steady.L,steady.F)
    # Preserve the original unknown coordinates even when forcing changes
    # prescribed motion/flow at t=0. Only the selected physical targets change.
    for c in constraints:
        steady.operating.base[c.variable]=network.operating.base[c.variable]
        steady.operating.scale[c.variable]=network.operating.scale[c.variable]
    steady.operating.initial_values=network.operating.initial_values
    steady.aero_key=steady.aero_cached=None
    state,steps=equilibrate(steady,tolerance,continuation_steps,progress=progress)
    network.nfev=steady.nfev
    network.operating.initial_values=steady.operating.initial_values
    from .hinge_history import current,joints
    centers=current(steady)
    residual=network.residual(state,hinge_charts=centers,**options)
    error=float(np.max(abs(residual)))
    if not np.isfinite(error) or error>tolerance:
        raise AnalysisError(f'Initial equilibrium does not satisfy the original unsteady equations (residual {error:.3g}).')
    for constraint,center in zip(joints(network),centers):constraint["angle_chart"]=center
    return state,steps


class TimeSystem:
    """Coupled differential-algebraic system with selected frame load targets."""
    def __init__(self, network, forcing=None, controller=None, *, gravity_magnitude=None):
        self.network = network
        if gravity_magnitude is not None and (not np.isfinite(gravity_magnitude) or gravity_magnitude < 0):
            raise AnalysisError('Time gravity magnitude must be finite and nonnegative.')
        self.gravity_magnitude = gravity_magnitude
        self.forcing = forcing
        self.feedback = controller
        self.has_actuator_constraints = bool(time_constraint_data(network.operating.constraints)['actuator_constraints'])
        self.requires_unique_time_solution = self.has_actuator_constraints or controller is not None
        if controller is not None:
            solved = {c.variable for c in network.operating.constraints}
            for output in controller.outputs:
                variable = ('control.' if output['attribute']=='controls' else 'power.')+str(output['index'])
                if variable in solved:
                    raise AnalysisError('An actuator cannot be solved by both a time target and a controller.')
        self.V = max(np.sqrt(network.model.constants[0]*network.L),
                     0. if network.condition is None else network.condition.speed)
        self.W = self.V/network.L
        self.A = self.V*self.W
        from .position_history_lift import position_history_lift
        self.position_lift = position_history_lift(network.operating.constraints, forcing,
            length_scale=network.L, velocity_scale=self.V)
        self.frame_start=network.size+6*network.nn
        self.feedback_start=self.frame_start+12
        self.size = self.feedback_start+(0 if controller is None else controller.size)

    @property
    def source_time(self):
        from .time_network import source_time_chart
        return source_time_chart(self.network)

    def condition(self, state):
        n = self.network
        motion = Motion(state.Omega, n.motion.acceleration, n.motion.angular_acceleration)
        if n.condition is None:
            return None, motion
        flow = -state.U-cross3(state.Omega, n.model.reference[3])
        speed = float(np.linalg.norm(flow))
        if speed <= 1e-8*self.V:
            raise AnalysisError('Trajectory reached zero reference airspeed; the aerodynamic model requires nonzero flow.')
        c = replace(n.condition, speed=speed,
                    alpha=float(np.rad2deg(np.arctan2(flow[2], flow[0]))),
                    beta=float(np.rad2deg(-np.arcsin(np.clip(flow[1]/speed, -1, 1)))),
                    rates=state.Omega.tolist(), position_earth=state.position.tolist(),
                    attitude=attitude_angles(state.orientation).tolist(), time=state.time)
        return c, motion

    def gravity(self, state):
        n = self.network
        if n.gravity_override:
            return n.gravity
        g = n.model.constants[0] if self.gravity_magnitude is None else self.gravity_magnitude
        if n.condition is not None and n.condition.gravity_magnitude is not None:
            g = n.condition.gravity_magnitude
        return state.orientation.T@np.array([0., 0., -g])

    def options(self, state, udot, wdot, gamma_dot, side='right', *, apply_forcing=True, history_context=None):
        c, motion = self.condition(state)
        targets={}
        if self.forcing is not None and apply_forcing:
            c, motion = self.forcing.apply(state.time, c, motion, side)
            state.commands=self.forcing.values(state.time,side)
            targets=self.forcing.targets(state.time,side)
        if self.feedback is not None and state.feedback.size:
            c=self.feedback.apply(state,c)
        if history_context is not None and not apply_forcing:
            raise ValueError('Periodic stencil context requires its explicit initialization forcing path.')
        options = dict(elastic_motion=(state.u, state.w, udot, wdot), circulation_rate=gamma_dot,
                    condition_override=c, motion_override=motion, gravity_override=self.gravity(state),operating_targets=targets)
        if self.network.hinges:
            from .hinge_history import checked
            options['hinge_charts']=checked(self.network,state.hinge_charts)
        if history_context is not None:
            options['history_context'] = history_context
        return options

    def initial(self, *, position, attitude, velocity, tolerance, continuation_steps, frame='prescribed', progress=None):
        n = self.network
        z = np.zeros_like(n.rj)
        orientation = body_to_earth(attitude)
        state = TimeState(0., np.zeros(n.size), n.rj.copy(), np.tile(np.eye(3), (n.nn, 1, 1)),
                          z.copy(), z.copy(), np.asarray(velocity), n.motion.rates.copy(),
                          np.asarray(position), orientation, np.zeros(n.circulation_basis.panels))
        from .hinge_history import at_network
        state.hinge_charts=at_network(n,state.Q)
        from .time_cold_initial import cold_history_targets, cold_history_initial
        self.initialization_report = None
        if cold_history_targets(n.operating.constraints):
            state, options, self.initialization_report = cold_history_initial(self, state, frame,
                tolerance=tolerance, continuation_steps=continuation_steps, progress=progress)
            if self.position_lift is not None:
                self.position_lift.bind_initial(state, self.forcing, tolerance)
            return state, options, 0
        options = self.options(state, z, z, np.zeros(n.circulation_basis.panels))
        options.pop('hinge_charts',None)  # Cold continuation owns/recenters its branch.
        if self.feedback is None:
            state.x, steps = initial_equilibrium(n, options, tolerance, continuation_steps, progress)
        else:
            state.x, steps = equilibrate(n, tolerance, continuation_steps, progress=progress, **options)
        state.r, state.Q, *_, state.gamma = n.unpack(state.x)
        state.hinge_charts=at_network(n,state.Q)
        if n.hinges:options["hinge_charts"]=state.hinge_charts
        if self.feedback is not None:
            from .feedback import equilibrium
            state,options=equilibrium(self,state,options,tolerance,steady=False)
        if self.source_time is not None:
            state.source_attitude=np.deg2rad(attitude).copy()
            self.source_time.bind(state)
        return state, options, steps

    def guess(self, previous, step):
        n = self.network
        x = previous.x.copy()
        kin = x[:6*n.nn].reshape(n.nn, 6)
        kin[:, :3] += step*previous.u/n.L
        kin[:, 3:] = step*previous.w
        position = previous.position+step*(previous.orientation@previous.U)
        return np.r_[x, (previous.u/self.V).ravel(), (previous.w/self.W).ravel(),
                     previous.U/self.V, previous.Omega/self.W, position/n.L, step*previous.Omega,
                     [] if self.feedback is None else previous.feedback/self.feedback.scales]

    def unpack(self, values, previous, time):
        n = self.network
        x = values[:n.size].copy()
        kin = x[:6*n.nn].reshape(n.nn, 6)
        if np.max(np.linalg.norm(kin[:, 3:], axis=1)) >= np.pi-.05 or np.linalg.norm(values[self.frame_start+9:self.feedback_start]) >= np.pi-.05:
            raise AnalysisError('Time-step rotation approaches pi; reduce the time step.')
        # Trial rotations are increments about the last accepted orientation.
        kin[:, 3:] = log(exp(kin[:, 3:])@previous.Q)
        r, Q, *_, gamma = n.unpack(x)
        u, w = values[n.size:self.frame_start].reshape(2, n.nn, 3)
        U, Omega, position, delta = values[self.frame_start:self.feedback_start].reshape(4, 3)
        from .hinge_history import lifted
        charts=lifted(n,Q,previous.hinge_charts,previous.Q)
        state=TimeState(time, x, r, Q, u*self.V, w*self.W, U*self.V, Omega*self.W,
                         position*n.L, previous.orientation@exp(delta), gamma,
                         np.empty(0) if self.feedback is None else values[self.feedback_start:]*self.feedback.scales,hinge_charts=charts)
        if self.source_time is not None:self.source_time.bind(state,previous)
        return state

    def residual(self, values, previous, older, time, coefficients, *, detail=False, side='right', _mechanical_data=None):
        n = self.network
        state = self.unpack(values, previous, time)
        if older is not None and self.source_time is None:
            # Prevent a two-step turn from aliasing across the logarithm branch,
            # including a full turn whose principal logarithm would look small.
            increments = np.linalg.norm(values[:6*n.nn].reshape(n.nn, 6)[:, 3:], axis=1)
            history = np.linalg.norm(log(previous.Q@np.swapaxes(older.Q, -1, -2)), axis=1)
            frame_history = np.linalg.norm(log(older.orientation.T@previous.orientation))
            if np.max(increments+history) >= np.pi-.05 or np.linalg.norm(values[self.frame_start+9:self.feedback_start])+frame_history >= np.pi-.05:
                raise AnalysisError('Two-step rotation approaches pi; reduce the time step.')
        def derivative(name):
            if name == 'r':
                return local_position_derivative(n, state, previous, older, coefficients)
            current = getattr(state, name)
            # Difference form avoids cancellation of large absolute positions.
            result = coefficients[0]*(current-getattr(previous, name))
            if older is not None:
                result += coefficients[2]*(getattr(older, name)-getattr(previous, name))
            return result
        options = self.options(state, derivative('u'), derivative('w'), derivative('gamma'), side)
        if n.hinges:options['hinge_charts']=previous.hinge_charts
        if self.feedback is None:
            fields = n.iteration_fields
            if _mechanical_data is not None:
                base = n.residual(state.x, **options, _mechanical_data=_mechanical_data)
            elif fields is not None and fields.phase == 'capture' and getattr(fields, 'capture_mechanics', False):
                base = n.residual(state.x, **options, _mechanical_data=fields.mechanical_data)
            else:
                base = n.residual(state.x, **options)
        else:base,data=n.residual(state.x,detail=True,**options,_mechanical_data=_mechanical_data)
        _, motion, _ = n.operating.apply(state.x[n.operating_start:],
                                         condition_override=options['condition_override'],
                                         motion_override=options['motion_override'])
        if self.source_time is None:
            local_residual = rotation_rate(state.Q, previous.Q, None if older is None else older.Q, coefficients)-state.w
            frame_residual = rotation_rate(state.orientation, previous.orientation,
                                       None if older is None else older.orientation, coefficients, body=True)-state.Omega
        else:
            local_residual,frame_residual=self.source_time.rates(state,previous,older,coefficients)
        if self.position_lift is None:
            velocity_residual = derivative('U')+cross3(state.Omega, state.U)-motion.at(np.zeros(3), n.model.reference[2])
            position_residual = derivative('position')-state.orientation@state.U
        else:
            velocity_residual, position_residual = self.position_lift.residuals(
                state, previous, older, coefficients, motion, n.model.reference[2], self.forcing, side)
        residual = np.r_[base, ((derivative('r')-state.u)/self.V).ravel(),
                         (local_residual/self.W).ravel(),
                         velocity_residual/self.A,
                         (derivative('Omega')-motion.angular_acceleration)/self.W**2,
                         position_residual/self.V,
                         frame_residual/self.W]
        if self.feedback is not None:
            control,_=self.feedback.evaluate(state,data,derivative('feedback'))
            residual=np.r_[residual,control]
        return (residual, state, options) if detail else residual


class StepFailure(AnalysisError):
    pass


class UnresolvedControllerAuthority(StepFailure):
    """Refuse this run after witnessed original-residual alternatives.

    Smaller-step no-witness sampling does not resolve an existing witness.
    This acceptance policy is not proof that every smaller step is nonunique.
    Ordinary Newton and centered-rank StepFailure remain recoverable.
    """


def regular_tangent(function, x):
    """Require local uniqueness for time constraints and controller outputs.

    Geometry, motion, circulation and control columns use centered differences
    of the accepted full equations. Eligible source load/reaction columns use
    their analytical derivative. Column and row scaling avoid an arbitrary
    force unit or time-step size determining the numerical rank.
    """
    progress = getattr(function, 'progress', None)
    if progress is not None: progress('time_rank', 0, len(x))
    jac = np.empty((len(x), len(x)))
    direct = set()
    builder = getattr(function, 'direct_mechanical_columns', None)
    if builder is not None:
        from .mechanical_tangent import MechanicalDerivativeUnavailable
        try:
            indices, block = builder(x)
        except MechanicalDerivativeUnavailable:
            pass  # Unsupported laws/hinge branches retain the full stencil.
        else:
            jac[:, indices] = 0.
            entries = block.tocoo()
            jac[entries.row, indices[entries.col]] = entries.data
            direct = set(indices)
    for j in range(len(x)):
        if j not in direct:
            delta = np.zeros(len(x)); delta[j] = 1e-6*max(1., abs(x[j]))
            jac[:, j] = (function(x+delta)-function(x-delta))/(2*delta[j])
        if progress is not None: progress('time_rank', j+1, len(x))
    if not np.all(np.isfinite(jac)):
        raise StepFailure('Nonfinite time-system tangent.')
    diagnostic = getattr(function, 'accepted_root_diagnostic', None)
    original_jac = jac.copy() if diagnostic is not None else None
    for _ in range(4):
        jac /= np.maximum(np.linalg.norm(jac, axis=0), 1e-30)
        jac /= np.maximum(np.linalg.norm(jac, axis=1), 1e-30)[:, None]
    singular = np.linalg.svd(jac, compute_uv=False)
    if singular[-1] <= 1e-10*singular[0]:
        raise StepFailure('Time constraints and controllers do not resolve a locally unique state and actuator setting; check control authority and independent constraints.')
    if diagnostic is not None:
        diagnostic(function, x, original_jac)


def full_tangent(function, x, residual, *, direct_mechanics=True):
    """Complete Newton matrix with eligible exact load/reaction columns.

    All geometry, motion, circulation, frame and controller columns retain
    their original full-residual stencil. The same source mechanical helper
    used by the rank check supplies only its certified columns; unavailable
    constitutive/hinge contexts keep the original stencil for every column.
    """
    jac = np.empty((len(x), len(x)))
    direct = set()
    builder = getattr(function, 'direct_mechanical_columns', None) if direct_mechanics else None
    if builder is not None:
        from .mechanical_tangent import MechanicalDerivativeUnavailable
        try:
            indices, block = builder(x)
        except MechanicalDerivativeUnavailable:
            pass
        else:
            jac[:, indices] = 0.
            entries = block.tocoo()
            jac[entries.row, indices[entries.col]] = entries.data
            direct = set(indices)
    progress = getattr(function, 'progress', None)
    for j in range(len(x)):
        if j not in direct:
            h = 1e-6*max(1., abs(x[j]))
            trial = x.copy(); trial[j] += h
            jac[:, j] = (function(trial)-residual)/h
        if progress is not None: progress('time_tangent', j+1, len(x))
    return jac


def newton(function, guess, tolerance, factorization=None, *, check_rank=False,
           limit_correction=None,accepted_state=None):
    """Damped modified Newton; reuse a tangent only while it reduces residuals.

    Optional static chart hooks limit corrections and recenter accepted states.
    They are disabled for ordinary time callers. Trials never call the accepted
    state hook, and a changed coordinate chart always discards the tangent.
    """
    progress = getattr(function, 'progress', None)
    x = guess.copy()
    residual = function(x)
    rebuilt = False
    builds = 0
    tangent_age = 0
    builder = getattr(function, 'factorization_builder', None)
    dense_only = False
    for iteration in range(24):
        error = float(np.max(abs(residual)))
        if progress is not None: progress('time_iteration', iteration, error)
        if np.isfinite(error) and error <= tolerance:
            if check_rank:
                regular_tangent(function, x)
                builds += 1
            return x, factorization, iteration, builds
        if not np.isfinite(error):
            raise StepFailure('Nonfinite time residual.')
        if factorization is None:
            if builder is not None and not dense_only:
                builds += 1
                try:
                    factorization = builder(x)
                except (AnalysisError, ValueError, RuntimeError, LinAlgWarning, np.linalg.LinAlgError):
                    dense_only = True
            if factorization is None:
                if progress is not None: progress('time_tangent', 0, len(x))
                jacobian_builder = getattr(function, 'jacobian_builder', None)
                if jacobian_builder is not None:
                    # A caller with constrained physical probes owns its
                    # complete tangent, including dense-factor recovery.
                    jac = np.asarray(jacobian_builder(x), dtype=float)
                    if jac.shape != (len(x), len(x)) or not np.all(np.isfinite(jac)):
                        raise StepFailure('Invalid supplied full-system tangent.')
                    if progress is not None: progress('time_tangent', len(x), len(x))
                else:
                    jac = full_tangent(function, x, residual)
                with warnings.catch_warnings():
                    warnings.simplefilter('error', LinAlgWarning)
                    try:
                        factorization = lu_factor(jac)
                    except (ValueError, LinAlgWarning) as exc:
                        raise StepFailure('Singular time-system tangent; check mass and constraints.') from exc
                builds += 1
            rebuilt = True
            tangent_age = 0
        structured = hasattr(factorization, 'solve')
        try:
            correction = factorization.solve(-residual) if structured else lu_solve(factorization, -residual)
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            if not structured: raise
            factorization = None
            dense_only = True
            continue
        if not np.all(np.isfinite(correction)):
            raise StepFailure('Nonfinite time-system Newton correction.')
        if limit_correction is not None:correction=limit_correction(correction)
        accepted = False
        for power in range(9):
            trial = x+correction/2**power
            try:
                trial_residual = function(trial)
                next_error = float(np.max(abs(trial_residual)))
            except (AnalysisError, ValueError, FloatingPointError):
                continue
            if np.isfinite(next_error) and (next_error < error*(1-1e-4/2**power) or next_error <= tolerance):
                x, residual = trial, trial_residual
                if accepted_state is not None:
                    x=accepted_state(x)
                    residual=function(x)
                    next_error=float(np.max(abs(residual)))
                    # A coordinate change invalidates the previous tangent.
                    factorization=None
                accepted = True
                tangent_age += 1
                # Accept a converged final allowed correction, and refresh even
                # a contracting stale tangent after a change of control branch.
                if next_error <= tolerance:
                    if check_rank:
                        regular_tangent(function, x)
                        builds += 1
                    return x, factorization, iteration+1, builds
                if next_error > .7*error or tangent_age >= 6:
                    factorization = None
                rebuilt = False
                break
        if not accepted:
            if rebuilt:
                if structured:
                    dense_only = True
                else:
                    raise StepFailure(f'Time Newton line search failed at residual {error:.3g}.')
            factorization = None
    raise StepFailure(f'Time Newton did not converge; residual {np.max(abs(residual)):.3g}.')


def time_snapshot(system, state, options, residual, order, step, side='right'):
    n = system.network
    result = network_result(n, state.x, sensor_frame=dict(body_to_earth=state.orientation,
        position_earth=state.position, velocity_origin_body=state.U), **options)
    _, motion, _ = n.operating.apply(state.x[n.operating_start:],
                                     condition_override=options['condition_override'],
                                     motion_override=options['motion_override'])
    result.update(analysis='time_state', time=state.time, residual=residual, order=order, step=step,
                  local_velocity=state.u.tolist(), local_rates=state.w.tolist(),
                  local_acceleration=options['elastic_motion'][2].tolist(),
                  local_rate_derivative=options['elastic_motion'][3].tolist(),
                  circulation_rate=options['circulation_rate'].tolist(),
                  frame=dict(position_earth=state.position.tolist(), body_to_earth=state.orientation.tolist(),
                             attitude=attitude_angles(state.orientation).tolist(),
                             velocity_origin_body=state.U.tolist(), rates_body=state.Omega.tolist(),
                             acceleration_reference_body=motion.acceleration.tolist(),
                             angular_acceleration_body=motion.angular_acceleration.tolist()))
    if getattr(n,'source_moving',False):
        result['limitations'][0] = 'Source moving-frame vacuum state with endpoint inertia and material damping; temporal and spatial refinement are required.'
        if getattr(n,'source_airflow',False):
            result['limitations'][0] = 'Source moving-frame state with endpoint real inertia/damping and Glauert unsteady aerodynamic loads; temporal and spatial refinement are required.'
        result['frame']['attitude']=np.rad2deg(state.source_attitude).tolist()
    else:
        result['limitations'][0] = 'Implicit unsteady state with elastic inertia, damping and the selected aerodynamic-lag setting; temporal and spatial refinement are required.'
    result['forcing_side'] = side
    result['forcing_values'] = {} if system.forcing is None else system.forcing.values(state.time, side)
    if state.position_history is not None:
        E, W = system.position_lift.coordinates(state, state.position_history)
        result['position_history_sample'] = dict(asdict(state.position_history),
            position_defect_earth=E.tolist(), velocity_defect_earth=W.tolist())
    if system.feedback is not None:
        _,data=n.residual(state.x,detail=True,**options)
        _,result['feedback']=system.feedback.evaluate(state,data)
    return result


def solve_time(model, condition=None, panels=8, *, duration, dt, order=2, frame='prescribed',
               gravity=None, loads=(), initial_loads=None, motion=None, position=(0., 0., 0.),
               attitude=(0., 0., 0.), velocity=(0., 0., 0.), tolerance=1e-8,
               continuation_steps=4, strut_mode='bilateral', max_steps=10000, forcing='', controller=None, load_targets=None, actuator_constraints=None, progress=None,
               accuracy=None, structural_operator=None, gravity_magnitude=None):
    """Evolve a zero-local-rate equilibrium, optionally releasing initial loads.

    frame='free' solves six body accelerations from zero net force and moment;
    Ground records then define the local coordinate gauge. frame='prescribed'
    holds body acceleration/angular-acceleration components fixed and integrates
    the resulting frame trajectory. frame='mixed' determines the components
    selected by load_targets from net force/moment targets; all others remain
    prescribed. actuator_constraints adds implicit flap/engine equations for
    load, lift or frame-acceleration targets. Solved actuators cannot also be
    prescribed by a forcing column or a feedback controller. Velocity and pose
    retain their unsteady kinematic equations. Position/attitude/velocity specify the
    initial frame for structural-only problems (velocity is at the body origin).
    Aerodynamic problems take their initial frame from FlightCondition.

    Loads are constant body-axis nodal wrenches. With initial_loads, snapshot 0
    is the equilibrium immediately BEFORE switching to loads. The first implicit
    step resolves the release. dt is a maximum step, not an accuracy tolerance;
    failed nonlinear steps are retried at half-size. No local error estimator is
    implied. Atmospheric altitude is prescribed; Earth gusts are sampled on the
    current geometry at each trial time. Cosine/sinusoid fields additionally limit
    sample-point phase travel to pi/8 per step, including outside their support.
    This prevents stepping over a narrow pulse in monotonic motion, but does not
    supply an accuracy estimate or resolve arbitrary expression fields. `forcing`
    is a documented ASWING open-loop text table; values override prescribed
    settings. Snapshot 0 equilibrates at its right-hand t=0 values. Integration
    lands on table knots, approaches discontinuities from the left, then
    uses right-hand forcing after each doubled time and the
    final table time. Specified values are zero beyond the last table sample.
    Orders 1/2 select BDF1/BDF2 with BDF1 startup at each break; order 5 selects
    three-stage Radau IIA, whose stages satisfy the continuous residual.
    """
    validate_time_settings(duration,dt,order,frame,max_steps,tolerance)
    from .time_accuracy import settings
    accuracy=settings(accuracy)
    loads = list(loads)
    initial_loads = loads if initial_loads is None else list(initial_loads)
    # Include both attachment sets before meshing; preserve normalization after
    # removing an initial force so every time step has the same residual scales.
    constraints=time_operating_constraints(frame,load_targets,actuator_constraints)
    from .time_network import time_network_class
    network_class = time_network_class(model, condition, frame=frame,
        structural_operator=structural_operator, controller=controller,
        actuator_constraints=actuator_constraints, strut_mode=strut_mode)
    n = network_class(model, panels, condition, gravity, loads+initial_loads, motion,constraints,strut_mode)
    n.loads = initial_loads
    if condition is not None:
        if condition.time != 0:
            raise AnalysisError('Time response starts at t=0; use the gust phase/origin to shift the field.')
        if np.any(position) or np.any(attitude) or np.any(velocity):
            raise AnalysisError('With aerodynamics, specify initial frame motion and pose in FlightCondition.')
        position, attitude = condition.position_earth, condition.attitude
        velocity = -condition.speed*condition.vectors()[0]-cross3(n.motion.rates, model.reference[3])
    position, attitude, velocity = (vector(v, name) for v, name in
                                    [(position, 'Initial position'), (attitude, 'Initial attitude'), (velocity, 'Initial velocity')])
    from .feedback import FeedbackSystem
    feedback=None if controller is None else FeedbackSystem(n,controller)
    histories = TimeForcing(forcing, model, condition, n.motion, duration, frame,feedback,load_targets=load_targets,actuator_constraints=actuator_constraints)
    system = TimeSystem(n, histories,feedback,gravity_magnitude=gravity_magnitude)
    previous, options, continuation = system.initial(position=position, attitude=attitude, velocity=velocity,
                                                     tolerance=tolerance, continuation_steps=continuation_steps, frame=frame, progress=progress)
    setup=dict(panels=panels,condition=None if condition is None else asdict(condition),
        motion={key:getattr(n.motion,key).tolist() for key in ('rates','acceleration','angular_acceleration')},
        gravity=n.gravity.tolist() if n.gravity_override else None,mesh_loads=loads+initial_loads,loads=loads,
        strut_mode=strut_mode,frame=frame,**time_constraint_data(constraints),
        controller=None if feedback is None else feedback.definition,forcing=forcing)
    if getattr(n, 'source_moving', False):setup['structural_operator']=n.structural_operator
    if gravity_magnitude is not None:setup['gravity_magnitude']=gravity_magnitude
    initial = {} if system.initialization_report is None else dict(
        initial_phase='cold_inverse_history', initial_error=system.initialization_report['residual'])
    result = integrate(system,previous,None,options,setup,duration=duration,dt=dt,order=order,tolerance=tolerance,
        max_steps=max_steps,continuation=continuation,progress=progress,accuracy=accuracy,**initial)
    if system.initialization_report is not None:
        result['initialization'] = system.initialization_report
    if order != 5 and system.position_lift is not None:
        result['frame_derivative_policy'] = system.position_lift.policy
    return result


def validate_time_settings(duration,dt,order,frame,max_steps,tolerance):
    if not np.isfinite(duration) or duration <= 0:
        raise AnalysisError('Time duration must be finite and positive.')
    bdf_coefficients(dt)
    if order not in (1, 2, 5) or isinstance(order, bool):
        raise AnalysisError('Time order must be 1 (BDF1), 2 (BDF2) or 5 (three-stage Radau IIA).')
    if frame not in ('prescribed', 'free','mixed'):
        raise AnalysisError('Time frame must be prescribed, free or mixed.')
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 1:
        raise AnalysisError('Maximum step count must be a positive integer.')
    if not np.isfinite(tolerance) or not 0<tolerance<=1e-5:
        raise AnalysisError('Time tolerance must be positive and no greater than 1e-5.')


def integrate(system,previous,older,options,setup,*,duration,dt,order,tolerance,max_steps,continuation,
              progress=None,initial_step=None,side='right',initial_phase='before_load_switch',initial_error=None,accuracy=None,
              initial_acceptance=None,initial_transition=None):
    system.progress = progress
    if accuracy is not None:
        from .time_accuracy import integrate as refined_integrate,settings
        result=refined_integrate(system,previous,older,options,setup,duration=duration,dt=dt,order=order,
            tolerance=tolerance,max_steps=max_steps,continuation=continuation,progress=progress,
            initial_step=initial_step,side=side,initial_phase=initial_phase,initial_error=initial_error,accuracy=settings(accuracy),
            initial_acceptance=initial_acceptance,initial_transition=initial_transition)
        from .time_network import source_time_result
        return source_time_result(system,result,order)
    from .time_state import context,record
    from .time_acceptance import capture_initial,capture_bdf,capture_radau
    n=system.network;histories=system.forcing;feedback=system.feedback;condition=n.condition
    frame=setup['frame'];start_time=previous.time;end_time=start_time+duration
    if not np.isfinite(end_time) or end_time<=start_time:raise AnalysisError('Time interval is below floating-point resolution or nonfinite.')
    restart_context=context(system,setup,order,dt,tolerance)
    error = float(np.max(abs(n.residual(previous.x, **options)))) if initial_error is None else initial_error
    from .time_snapshot_storage import snapshot_history
    snapshots = snapshot_history(time_snapshot(system, previous, options, error, 0, 0.,side))
    snapshots[0]['initial_phase'] = initial_phase
    if initial_phase.startswith(('checkpoint','saved_equilibrium')):snapshots[0]['forcing_values']=previous.commands.copy()
    if progress is not None:
        progress(start_time, 0)
    step = min(dt,duration) if initial_step is None else min(initial_step,duration)
    accepted_initial=initial_acceptance if initial_acceptance is not None else capture_initial(
        system,previous,options,setup,phase=initial_phase,side=side,tolerance=tolerance)
    snapshots[0]['restart']=record(system,previous,older,options,step,side,accepted_method=accepted_initial)
    if initial_transition is not None:
        snapshots[0]['restart_context']=initial_transition['before_context']
        snapshots[0]['restart']=initial_transition['before_record']
    n.loads = setup['loads']
    factorization = None
    previous_coefficients = None
    rejected = builds = iterations = 0
    gust_retries = 0
    gust = gust_field(None if condition is None else condition.gust)
    minimum_step = min(dt, duration)/4096
    accepted_steps=0
    while previous.time < end_time-1e-13*max(end_time, dt):
        if accepted_steps >= max_steps:
            raise AnalysisError('Time integration exceeded the maximum accepted step count.')
        from .time_input_transition import needed,complete
        if needed(system,previous,side,changed=initial_transition is not None):
            reason='replacement forcing' if initial_transition is not None else 'forcing cutoff' if previous.time==histories.end_time else 'forcing break'
            previous,options,right=complete(system,previous,setup,tolerance=tolerance,progress=progress,
                step=step,reason=reason,before_snapshot=snapshots[-1])
            snapshots.append(right)
            older=None;factorization=previous_coefficients=None;side='right'
        initial_transition=None
        step = min(step, end_time-previous.time)
        upcoming = histories.events[histories.events > previous.time]
        event = float(upcoming[0]) if len(upcoming) else end_time
        # Assign the exact table time, avoiding drift to the wrong spline side.
        time = min(previous.time+step, event, end_time)
        if event-time <= 8*np.finfo(float).eps*max(abs(event), abs(time), dt):
            time = event
        step = time-previous.time
        at_break = time in histories.breaks
        target_side = 'left' if at_break else 'right'
        previous_step = None if older is None or order != 2 else previous.time-older.time
        coefficients = bdf_coefficients(step, previous_step)
        if previous_coefficients is None or not np.allclose(coefficients, previous_coefficients, rtol=1e-12, atol=0):
            factorization = None
        if progress is not None: progress('time_step', previous.time, time)
        function = lambda values: system.residual(values, previous, older if order == 2 else None, time, coefficients, side=target_side)
        function.progress = progress
        if order != 5:
            from .structured_time import attach
            attach(system,function,progress,circulation_rate_factor=coefficients[0])
            from .time_tangent import attach_mechanical_columns
            attach_mechanical_columns(system, function, lambda values, data: system.residual(
                values, previous, older if order == 2 else None, time, coefficients,
                side=target_side, _mechanical_data=data[0]))
            nonlinear_tolerance,nonlinear_policy=bdf_nonlinear_gate(system,coefficients,tolerance)
        if order != 5 and system.feedback is not None:
            function.accepted_root_diagnostic = system.feedback.root_diagnostic(
                range(system.feedback_start, system.feedback_start+system.feedback.count), nonlinear_tolerance)
        phase_travel = 0.
        try:
            if order==5:
                from .radau_time import step as collocation_step
                state,options,factorization,count,rebuilt,stage_error,stage_tolerance,stage_data=collocation_step(
                    system,previous,time,frame,target_side,tolerance,factorization=factorization,capture=True)
                residual=np.array([stage_error])
            else:
                values, factorization, count, rebuilt = newton(function, system.guess(previous, step), nonlinear_tolerance, factorization,
                    check_rank=system.requires_unique_time_solution)
                residual, state, options = system.residual(values, previous, older if order == 2 else None,
                                                           time, coefficients, detail=True, side=target_side)
            if gust.kind != 'none':
                before = snapshots[-1]['gust']['sample_positions_earth']
                after = n.aero_cached['gust']['sample_positions_earth']
                phase_travel = gust.phase_change(before, after, step)
                if phase_travel > np.pi/8*(1+1e-9):
                    gust_retries += 1
                    raise StepFailure('Gust phase travel exceeds pi/8; reducing time step.')
        except UnresolvedControllerAuthority:
            raise
        except (AnalysisError, ValueError, FloatingPointError) as exc:
            rejected += 1
            factorization = None
            step /= 2
            if progress is not None: progress('time_retry', previous.time, step)
            if step < minimum_step:
                raise AnalysisError(f'Time integration failed after t={previous.time:.9g}: {exc}') from exc
            continue
        builds += rebuilt
        iterations += count
        # A rejected trial must not change the side owned by the retained state.
        side = target_side
        if order==5:
            accepted_method=capture_radau(system,previous,state,options,setup,
                stage_data=stage_data,side=side,tolerance=tolerance)
        else:
            accepted_method=capture_bdf(system,previous,older if order==2 else None,state,options,setup,
                values=values,time=time,coefficients=coefficients,side=side,tolerance=tolerance,
                nonlinear_tolerance=nonlinear_tolerance,nonlinear_policy=nonlinear_policy)
        snapshots.append(time_snapshot(system, state, options, float(np.max(abs(residual))),
                                       5 if order==5 else 1 if previous_step is None else 2, step, side))
        accepted_steps+=1
        if order==5:snapshots[-1]['collocation']=dict(stages=3,maximum_stage_residual=stage_error,stage_tolerance=stage_tolerance)
        if progress is not None:
            progress(state.time, accepted_steps)
        older, previous = None if order==5 else previous, state
        previous_coefficients = coefficients
        if at_break:
            older = None
            factorization = previous_coefficients = None
        # BDF2 zero stability requires bounded step ratios; keep growth <= 1.5.
        step = dt if at_break else min(dt, step*1.5)
        if phase_travel > 0:
            step = min(step, .99*snapshots[-1]['step']*np.pi/8/phase_travel)
        snapshots[-1]['restart']=record(system,previous,older,options,step,side,accepted_method=accepted_method)
    result=dict(analysis='time_response', converged=True, frame_mode=frame, method='Radau IIA (3 stages)' if order==5 else f'BDF{order}',
                frame_load_targets=time_constraint_data(n.operating.constraints)['load_targets'],
                actuator_constraints=time_constraint_data(n.operating.constraints)['actuator_constraints'],
                duration=duration, start_time=start_time,end_time=end_time,restart_context=restart_context,maximum_step=dt, accepted_steps=accepted_steps,
                rejected_steps=rejected, jacobian_builds=builds, newton_iterations=iterations,
                gust_resolution_retries=gust_retries,
                continuation_steps=continuation, evaluations=n.nfev, snapshots=snapshots, forcing=histories.report(),
                controller=None if feedback is None else feedback.report(),
                limitations=['Experimental time solver; ASWING executable/discrete parity is unverified.',
                             'Cold trajectories start at zero local rates. Saved-equilibrium launches can complete compatible physical disturbances with nonlinear constraint checks. Checkpoint continuation retains elastic velocities, circulation, frame motion, controller states and BDF history.',
                             'Flap/engine, prescribed acceleration and active load/lift/radial-acceleration target tables are supported. Actuator constraints solve flaps/engines while retaining the frame equations. Specified values become zero after the last table time, including relative channels. Earth gusts, selected controller commands and supported inverse motion histories participate in the implicit solve. Compatible history input changes complete a separate right state; impulse events and companion-file parity remain unimplemented.',
                             'The time step controls resolution. Halving after nonlinear failure does not estimate temporal error.',
                             'Radau IIA has fifth-order ODE accuracy; constrained velocities and reactions can converge at lower order. BDF startup can produce nonconvergent peak reaction transients for curved constraints with nonzero initial velocity; use Radau and check temporal refinement for those motions.',
                             'Prescribed atmospheric altitude and ambient-relative frame motion; atmospheric variation with trajectory is pending.'])
    from .time_network import source_time_result
    return source_time_result(system,result,order)
