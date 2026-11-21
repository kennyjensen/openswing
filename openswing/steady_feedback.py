"""Simultaneous operating, structural and steady control-law equilibrium.

Actual actuators satisfy controller equations. Independently selected command
variables may satisfy trim targets; zero integrated-error rates are retained.
"""
import numpy as np
from .aero import AnalysisError
from .feedback import FeedbackSystem
from .ground import body_to_earth
from .network import StaticNetwork, equilibrate
from .operating import OperatingSystem, OperatingConstraint
from .time_integration import TimeState, newton, StepFailure


def solve_feedback_base(model, condition, panels, *, controller, gravity=None, loads=(), motion=None,
                        operating_constraints=(), tolerance=1e-9, continuation_steps=4,
                        strut_mode='bilateral', residual_options=None,initial_state=None,
                        network_class=StaticNetwork):
    if not np.isfinite(tolerance) or not 0<tolerance<=1e-5:
        raise AnalysisError('Equilibrium tolerance must be positive and no greater than 1e-5.')
    if not isinstance(continuation_steps,int) or isinstance(continuation_steps,bool) or continuation_steps<1:
        raise AnalysisError('Continuation steps must be a positive integer.')
    from .equilibrium_state import warm_start_recipe
    n = network_class(model, panels, condition, gravity, loads, motion, (), strut_mode,
                      mesh_recipe=warm_start_recipe(model, panels, initial_state))
    feedback = FeedbackSystem(n, controller)
    constraints = [OperatingConstraint(**c) if isinstance(c, dict) else c for c in operating_constraints]
    owned = {('control.' if o['attribute']=='controls' else 'power.')+str(o['index']):o['actuator'] for o in feedback.outputs}
    for c in constraints:
        if c.variable in owned:
            raise AnalysisError(f'{c.variable} is determined by the controller. Select command.{owned[c.variable]} or a measurement command as the trim unknown.')
    options = dict(residual_options or {})
    if options.pop('zero_local_rates', False):
        zero = np.zeros_like(n.rj)
        options.update(elastic_motion=(zero, zero, zero, zero), circulation_rate=np.zeros(n.circulation_basis.panels))
    # Defaults have a reproducible meaning even when no open-loop trimmed
    # solution exists: solve the loaded structure at prescribed operating values.
    if initial_state is None:
        x, seed_steps = equilibrate(n, tolerance, continuation_steps, **options)
    else:
        from .equilibrium_state import restore,restore_feedback
        x=restore(n,initial_state);seed_steps=0

    def state_at(x, values):
        c, motion, operating = n.operating.apply(x[n.operating_start:])
        r, Q, *_, gamma = n.unpack(x)
        zero = np.zeros_like(r)
        state = TimeState(c.time, x, r, Q, zero, zero,
            -c.speed*c.vectors()[0]-np.cross(motion.rates, model.reference[3]), motion.rates,
            np.asarray(c.position_earth), body_to_earth(c.attitude), gamma, values,
            {key.removeprefix('command.'):value for key,value in operating.items() if key.startswith('command.')})
        from .hinge_history import at_network
        state.hinge_charts=at_network(n,Q)
        return state, c

    state, c = state_at(x, np.empty(0))
    _, data = n.residual(x, detail=True, **options)
    feedback.initialize(state, data)
    if initial_state is not None:restore_feedback(n,feedback,state,initial_state)
    extra = {f'command.{name}':(value, feedback.signal_scales[name]) for name,value in feedback.commands.items()}
    extra.update({f'command.{o["actuator"]}':(feedback.bias[o['actuator']], feedback.scales[i]) for i,o in enumerate(feedback.outputs)})
    n.operating = OperatingSystem(model, condition, n.motion, constraints, n.L, n.F, additional_variables=extra)
    n.size = n.operating_start+n.operating.count
    x = np.r_[x[:n.operating_start], np.zeros(n.operating.count)]
    if initial_state is not None:x=restore(n,initial_state)
    initial = np.r_[x, state.feedback/feedback.scales]

    def residual(values, factor=1., detail=False):
        state, c = state_at(values[:n.size], values[n.size:]*feedback.scales)
        applied = {**options, 'condition_override':feedback.apply(state, c), 'operating_factor':factor}
        base, data = n.residual(state.x, detail=True, **applied)
        control, report = feedback.evaluate(state, data, np.zeros(feedback.size))
        value = np.r_[base, control]
        return (value, state, applied, report) if detail else value

    # Record target continuation origins once, before trial states alter them.
    residual(initial)
    reached, step, steps = 0., 1./continuation_steps, 0
    values = initial
    allocation=None
    if n.operating.minimum_indices:
        from .control_allocation import allocate
        values,steps,allocation=allocate(residual,initial,n.operating,n.operating_start,
            tolerance=tolerance,continuation_steps=continuation_steps,warm=initial_state is not None)
        n.control_allocation=allocation
        reached=1.
    elif initial_state is not None:
        try:values,*_=newton(lambda v:residual(v,1.),values,tolerance)
        except (StepFailure,ValueError) as exc:raise AnalysisError(f'Warm controller equilibrium correction failed: {exc}') from exc
        reached,steps=1.,1
    while reached < 1-1e-12:
        target = min(1., reached+step)
        try:
            trial, *_ = newton(lambda v:residual(v, target), values, tolerance)
        except (StepFailure, ValueError, AnalysisError) as exc:
            step /= 2
            if step < 1/256:
                raise AnalysisError(f'Coupled controller/trim equilibrium failed at target fraction {target:.4f}: {exc}') from exc
            continue
        values, reached, steps = trial, target, steps+1
        step = min(1./continuation_steps, step*1.5)
    result, state, options, report = residual(values, detail=True)
    if n.operating.custom:
        from .custom_constraints import check_custom_tangent
        n.custom_trim=check_custom_tangent(n.operating,residual,values,n.operating_start,rank=allocation is None)
    # Zero residual alone cannot distinguish a unique equilibrium from redundant
    # integral/command/trim constraints. Check the full final tangent, including
    # command unknowns, even when Newton needed no correction.
    if allocation is not None:
        reciprocal=allocation['equality_reciprocal_condition']
    else:
        jac = np.empty((len(values), len(values)))
        for j in range(len(values)):
            h = 1e-6*max(1., abs(values[j])); plus=values.copy(); minus=values.copy()
            plus[j] += h; minus[j] -= h
            jac[:,j] = (residual(plus)-residual(minus))/(2*h)
        norms = np.linalg.norm(jac, axis=0)
        singular = np.linalg.svd(jac/np.maximum(norms, 1e-30), compute_uv=False)
        reciprocal = float(singular[-1]/singular[0])
    if reciprocal < 1e-10:
        raise AnalysisError('Steady controller/trim tangent is singular: redundant commands, integral constraints or operating targets leave a nonunique equilibrium.')
    feedback.base = state.feedback.copy()
    initial_commands={**feedback.commands, **feedback.bias}
    feedback.commands.update({name:report['commands'][name] for name in feedback.signals})
    feedback.bias.update({name:report['commands'][name] for name in feedback.bias})
    diagnostics = dict(residual=float(np.max(abs(result))), column_scaled_reciprocal_condition=reciprocal,
        seed_continuation_steps=seed_steps, target_continuation_steps=steps,
        initial_commands=initial_commands,
        solved_commands={c.variable:report['commands'][c.variable.removeprefix('command.')] for c in constraints if c.variable.startswith('command.')},
        initialization=('Saved physical equilibrium; unspecified commands retain their solved values, explicit new commands/bias settings take precedence.' if initial_state is not None else
                        'Commands default to measurements at the loaded structure with the prescribed operating settings; initial_integrals are guesses in steady equilibrium.'),
        integral_condition='measurement - command = 0 for every selected integrated error')
    if allocation is not None:diagnostics['control_allocation']=allocation
    return n, state, feedback, options, steps, diagnostics
