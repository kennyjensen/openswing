"""Held-physical-state right-branch completion for inverse history transitions.

Saved launches, input replacements and forcing breaks call this primitive.
The caller owns before-input provenance, active right loads and method restart.
It must not replace cold equilibrium or reinterpret a discrete accepted step.
"""
from copy import copy
import numpy as np
from .aero import AnalysisError
from .nonlinear_initial import InitialSystem, consistent_initial
from .time_cold_initial import cold_history_targets
from .time_history import TARGETS, PeriodicStencilContext
from .forcing import RightLimitForcing


def complete_history_transition(system, seed, frame, *, tolerance=1e-8,
                                difference_step=.01, rank_tolerance=1e-7,
                                progress=None):
    """Keep the physical state and solve right-side algebraic values and rates.

All beam positions/orientations, circulation, local velocities/angular rates,
frame position/orientation/velocity/angular rates and dynamic controller states
are held through the original continuous derivative-array equations. Internal
wrenches, frame accelerations and actuator outputs remain algebraic unknowns.
Their right-side values may differ from the saved before-input snapshot.

The system must already contain the new right-side forcing, active loads and
original effective controller commands/bias. This function does not initialize
new controller defaults or free the saved elastic shape. It returns a separate
state; the caller must retain the old snapshot and describe the transition.
"""
    n=system.network
    rows=cold_history_targets(n.operating.constraints)
    if not rows:
        raise AnalysisError('History transition completion requires an active kinematic history target.')
    physical_system=copy(system)
    physical_system.forcing=None if system.forcing is None else RightLimitForcing(system.forcing,seed.time)
    if system.position_lift is not None:
        sample=system.position_lift.sample(seed.time,physical_system.forcing,'right')
        system.position_lift._compatible(seed,sample,tolerance=tolerance)
    local=copy(system)
    local.forcing=None if system.forcing is None else system.forcing.stencil_forcing(seed.time,'right')
    chart=InitialSystem(local,seed,frame,apply_forcing=True)
    requested=np.zeros(chart.size)
    initial,anchor,anchor_options=chart.residual(requested,np.zeros(chart.size),seed.time,detail=True)
    for i,row in enumerate(n.operating.constraints):
        if row in rows:
            error=abs(float(initial[n.size-n.operating.count+i]))
            if not np.isfinite(error) or error>tolerance:
                raise AnalysisError(f'History transition target {row.quantity} disagrees with the retained physical state (scaled value residual {error:.3g}); no physical state is projected.')
    context=None
    periodic=[row.quantity for row in rows if TARGETS[row.quantity].periodic]
    if periodic:
        _,data=n.residual(anchor.x,detail=True,**anchor_options)
        context=PeriodicStencilContext.from_report(seed.time,'right',
            'constant active targets' if local.forcing is None else local.forcing.jet.source,
            [row for row in data['operating_constraints'] if row['quantity'] in periodic])
        chart=InitialSystem(local,seed,frame,apply_forcing=True,history_context=context)
    physical=InitialSystem(physical_system,seed,frame,apply_forcing=True)
    diagnostic=None
    controller=system.feedback
    if controller is not None and any(expression.nonsmooth for expression in controller.expressions):
        from .initial_diagnostics import controller_initial_alternatives
        indices=range(chart.feedback_start,chart.feedback_start+controller.count)
        diagnostic=controller_initial_alternatives(indices,indices,physical.residual,tolerance)
    completed,rate,consistency=consistent_initial(chart.residual,requested,chart.dynamic_indices,
        chart.rate_guess(requested),time=seed.time,time_scale=chart.W,tolerance=tolerance,
        difference_step=difference_step,rank_tolerance=rank_tolerance,progress=progress,
        accepted_initial_diagnostic=diagnostic)
    residual,state,options=physical.residual(completed,rate,seed.time,detail=True)
    error=float(np.max(abs(residual)))
    if not np.isfinite(error) or error>tolerance:
        raise AnalysisError(f'History transition differs from the original physical right branch (full residual {error:.3g}).')
    if system.position_lift is not None:
        # New right-branch samples belong to this completed state, never to
        # the retained finite-step state on the old side of the transition.
        system.position_lift.bind_initial(state,physical_system.forcing,tolerance)
    report=dict(source='held physical history transition',equilibrium_recomputed=False,
        inputs_apply='right branch at the retained physical time',
        initial_state_semantics='Hold every physical dynamic coordinate; solve algebraic settings and dynamic rates without re-equilibrating elastic geometry.',
        targets=[dict(variable=row.variable,quantity=row.quantity,derivative_order=TARGETS[row.quantity].derivative_order) for row in rows],
        forcing_stencil=None if local.forcing is None else local.forcing.report(),
        periodic_stencil=None if context is None else context.report(),
        completion=dict(chart='InitialSystem local physical-state chart v1',
            seed_required=True,time=float(seed.time),state_increment=completed.tolist(),
            coordinate_rate=rate.tolist(),dynamic_indices=chart.dynamic_indices.tolist(),
            scales=dict(length=float(chart.L),velocity=float(chart.V),angular_rate=float(chart.W)),
            rate_units='Derivatives of the scaled chart coordinates per input time unit; not a dimensionless stencil derivative.'),
        residual=error,consistency=consistency,
        limitations=['Before-input provenance and method restart are owned by the launch or time-integration caller.',
            'It constructs a continuous right-side state; it must not authenticate or replace a finite-step accepted state.',
            'Compatible position-history samples are bound only to the returned right state; BDF/Radau continuation retains the original before-state ownership.',
            'Finite derivative and nonsmooth alternative checks do not prove arbitrary higher-index support or uniqueness.'])
    return state,options,report
