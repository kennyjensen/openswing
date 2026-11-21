"""Cold inverse-history equilibrium through the continuous time equations.

This helper completes the initial continuous state. Periodic charts are owned
by each local derivative stencil; controller defaults use a separate open-loop
completion before the joint solve. Event and saved-launch completion remain
separate work. Combined behavior requires its own validation.
"""
from copy import copy
from dataclasses import replace
import numpy as np
from .aero import AnalysisError
from .operating import TimeHistoryConstraint
from .time_history import TARGETS, PeriodicStencilContext
from .nonlinear_initial import InitialSystem, consistent_initial


def cold_history_targets(constraints):
    """Global inverse rows whose actuator first appears after differentiation."""
    return [row for row in constraints if isinstance(row, TimeHistoryConstraint)
            and TARGETS[row.quantity].derivative_order > 0]


def cold_history_initial(system, seed, frame, *, tolerance, continuation_steps, progress=None):
    """Hold frame and local velocity; solve a zero-local-acceleration state.

Initial elastic positions, orientations, circulation and algebraic values are
unknown. Local u/w and the complete frame state remain prescribed; local u'/w'
and circulation rate are zero only at the initial instant, not over the stencil.
The ordinary physical forcing object stays on the original TimeSystem.
"""
    n = system.network
    rows = cold_history_targets(n.operating.constraints)
    if not rows:
        raise AnalysisError('Cold inverse completion requires an active kinematic history target.')
    periodic = [row.quantity for row in rows if TARGETS[row.quantity].periodic]
    if not isinstance(continuation_steps, int) or continuation_steps < 1:
        raise AnalysisError('At least one continuation step is required.')
    if not np.isfinite(tolerance) or not 1e-10 <= tolerance <= 1e-6:
        raise AnalysisError('Cold inverse consistency tolerance must be between 1e-10 and 1e-6.')
    if system.forcing is not None and system.forcing.end_time == seed.time:
        raise AnalysisError('Cold inverse initialization at the forcing cutoff needs explicit endpoint/right-branch compatibility; this path is not implemented.')
    if system.position_lift is not None:
        # The complete frame position/orientation/velocity is held below.
        # Check the selected position and its first derivative before any
        # controller bootstrap or expensive derivative-array completion.
        sample = system.position_lift.sample(seed.time, system.forcing, 'right')
        system.position_lift._compatible(seed, sample, tolerance=tolerance)
    bootstrap = None
    controller = system.feedback
    if controller is not None:
        # Default measurements must come from an actual open-loop equilibrium
        # satisfying the motion history, rather than the unequilibrated jig.
        # Construct its own chart dimensions: removing feedback from a shallow
        # copy would leave controller coordinates in the continuous system.
        from .time_integration import TimeSystem
        open_loop = TimeSystem(n, system.forcing, gravity_magnitude=system.gravity_magnitude)
        seed, open_options, open_report = cold_history_initial(open_loop, seed, frame,
            tolerance=tolerance, continuation_steps=continuation_steps, progress=progress)
        _, data = n.residual(seed.x, detail=True, **open_options)
        explicit_commands = dict(controller.commands)
        controller.initialize(seed, data)
        if system.forcing is not None:
            system.forcing.bind_commands(controller.commands)
            seed.commands = system.forcing.values(seed.time)
        bootstrap = dict(initialization=open_report, explicit_commands=explicit_commands,
            default_commands={key:value for key,value in controller.commands.items() if key not in explicit_commands},
            actuator_bias=dict(controller.bias),
            held_controller_initial_values=seed.feedback[controller.count:].tolist())
    r, Q, *_, gamma = n.unpack(seed.x)
    seed = replace(seed, r=r, Q=Q, gamma=gamma)
    # Share the same physical equations/operating unknowns, but own a separate
    # forcing reference. A local jet must never replace physical march lookup.
    local = copy(system)
    local.forcing = None if system.forcing is None else system.forcing.stencil_forcing(seed.time, 'right')
    chart = InitialSystem(local, seed, frame, apply_forcing=True)
    requested = np.zeros(chart.size)
    initial_residual, anchor_state, anchor_options = chart.residual(requested, np.zeros(chart.size), seed.time, detail=True)
    # Every selected value here depends on held frame quantities, not on the
    # released beam shape. Reject a mismatch instead of projecting physical U/R/p.
    for i, row in enumerate(n.operating.constraints):
        if row in rows:
            error = abs(float(initial_residual[n.size-n.operating.count+i]))
            if error > tolerance:
                raise AnalysisError(f'Cold inverse target {row.quantity} is inconsistent with the prescribed initial frame state (scaled value residual {error:.3g}); the initial motion is not projected.')
    context = None
    if periodic:
        _, anchor_data = n.residual(anchor_state.x, detail=True, **anchor_options)
        report_rows = [row for row in anchor_data['operating_constraints'] if row['quantity'] in periodic]
        context = PeriodicStencilContext.from_report(seed.time, 'right',
            'constant active targets' if local.forcing is None else local.forcing.jet.source, report_rows)
        chart = InitialSystem(local, seed, frame, apply_forcing=True, history_context=context)
    held = np.r_[np.arange(chart.velocity_start, chart.feedback_start),
        [] if controller is None else np.arange(chart.feedback_start+controller.count, chart.size)].astype(int)
    fixed = {int(i): 0. for i in np.r_[np.arange(n.gamma_start, n.operating_start),
                                       np.arange(chart.velocity_start, chart.frame_start)]}
    physical = InitialSystem(system, seed, frame, apply_forcing=True)
    diagnostic = None
    if controller is not None and any(expression.nonsmooth for expression in controller.expressions):
        from .initial_diagnostics import controller_initial_alternatives
        output_indices=range(chart.feedback_start,chart.feedback_start+controller.count)
        diagnostic=controller_initial_alternatives(output_indices,output_indices,physical.residual,tolerance)
    completed, rate, consistency = consistent_initial(chart.residual, requested, chart.dynamic_indices,
        chart.rate_guess(requested), time=seed.time, time_scale=chart.W, tolerance=tolerance,
        fixed_state_indices=held, fixed_rates=fixed, progress=progress,accepted_initial_diagnostic=diagnostic)
    # Check the accepted initial state with actual physical t=0 forcing and
    # retain those options for snapshot zero and the subsequent caller.
    residual, state, options = physical.residual(completed, rate, seed.time, detail=True)
    error = float(np.max(abs(residual)))
    if not np.isfinite(error) or error > tolerance:
        raise AnalysisError(f'Cold inverse completion disagrees with physical forcing at its initial time (full residual {error:.3g}); a cutoff/branch transition needs separate compatibility handling.')
    report = dict(source='cold inverse-history equilibrium', equilibrium_recomputed=True,
        initial_state_semantics='Hold the prescribed complete frame state and zero local velocity/angular velocity; solve initial elastic position/orientation, circulation and algebraic values with zero local acceleration/angular acceleration/circulation rate.',
        actuator_bootstrap='No separately equilibrated actuator setting or frozen elastic bootstrap shape.',
        seed='Zero-increment jig with declared base actuator guesses; physical actuator settings are solved unknowns, not prescribed initial fields.',
        targets=[dict(variable=row.variable, quantity=row.quantity, derivative_order=TARGETS[row.quantity].derivative_order) for row in rows],
        inputs_apply='right branch at initial time; original physical forcing preserved and used for returned options',
        forcing_stencil=None if local.forcing is None else local.forcing.report(),
        periodic_stencil=None if context is None else context.report(),
        residual=error, consistency=consistency,
        limitations=['This report certifies initial-state completion only; general kinematic events/cutoff, saved launch/replacement-input completion and coupled time-march force accuracy require separate validation.',
                     'Periodic branches are local initialization charts, not multi-turn table semantics or Euler-pole support; combined controller/periodic initialization requires independent validation.',
                     'Nonsmooth controller initialization is not generally certified; smooth local rank alone does not establish one-sided uniqueness.',
                     'The derivative array is a local numerical certificate through R, R prime and R double prime; it does not prove arbitrary actuator authority or higher-index support.'])
    if controller is not None:
        controller.base = state.feedback.copy()
        report.update(controller_bootstrap=bootstrap,
            initial_state_semantics=report['initial_state_semantics']+' Integral and custom controller initial values are also held; their rates satisfy the controller equations and need not vanish.',
            actuator_bootstrap='Controller commands and actuator biases come from a separately solved open-loop continuous inverse-history equilibrium. The joint solve releases its elastic shape and actual actuator settings.',
            seed='Physically consistent open-loop state with declared controller initial values; elastic positions/orientations, circulation, inverse actuators and controller actuators remain solved unknowns.',
            controller_initial_rates=(rate[chart.feedback_start+controller.count:]*controller.scales[controller.count:]).tolist())
    return state, options, report
