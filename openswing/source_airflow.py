"""Source moving beam balances coupled to the unsteady lifting-line residual.

Real inertia/damping use the source endpoint box operator. Aerodynamic loads
retain Glauert section sampling (steady Eqs.150--160), including unsteady
Eqs.31--44 and the selected circulation-lag law. The integrated section wrench
is transferred symmetrically about the arithmetic structural midpoint, keeping
the mixed N/M variables their physical endpoint averages. No second apparent
mass matrix is added. This differs from the stationary endpoint-fluid policy's
quadrature and has a separate numerical identity.
"""
import numpy as np

from .aero import AnalysisError, FlightCondition
from .source_coupled import SourceCoupledNetwork
from .source_dynamics import SourceMovingNetwork, check_frame_constraints


AIRFLOW_POLICY = 'drela-moving-airflow-v1'


class SourceAirflowNetwork(SourceMovingNetwork):
    structural_operator = AIRFLOW_POLICY
    source_airflow = True
    compact_source_evaluation = True
    steady_lifting_wrenches = SourceCoupledNetwork.steady_lifting_wrenches
    add_aerodynamic_loads = SourceCoupledNetwork.add_aerodynamic_loads

    def __init__(self, *args, steady_trim=False, **kwargs):
        # Steady and dynamic analyses use the same physical operator. Only
        # the permitted operating constraints differ, as in OPER's flag.
        self.steady_trim = steady_trim
        super().__init__(*args, **kwargs)

    def _check_analysis_scope(self):
        if not isinstance(self.condition, FlightCondition):
            raise AnalysisError('Source airflow dynamics requires a FlightCondition.')
        if self.quiescent_density is not None:
            raise AnalysisError('Source airflow dynamics does not yet support a separate quiescent fluid.')
        if self.steady_trim:
            from .numerical_policy import validate_source_steady_constraints
            validate_source_steady_constraints(self.operating.constraints, moving=True)
        else:
            check_frame_constraints(self.operating.constraints, 'Source airflow dynamics')

    @staticmethod
    def _check_local_motion(kwargs):
        # The aerodynamic residual validates circulation/rate dimensions and
        # finite values. Unlike the vacuum policy these are physical states.
        return

    def external(self, r, Q, meshes, gamma, condition, motion, operating_key, *,
                 local_motion=None, circulation_rate=None, gravity=None, _loads_only=False):
        if not isinstance(condition, FlightCondition):
            raise AnalysisError('Source airflow loads require a FlightCondition.')
        # Dispatch only real inertia, gravity and applied loads through the
        # vacuum implementation, preserving its cache for f_reac reporting.
        force, moment, _, records, couples, ends = super().external(
            r, Q, meshes, np.empty(0), None, motion, operating_key,
            local_motion=local_motion, circulation_rate=None, gravity=gravity,
            _loads_only=_loads_only)
        # Engine forces/couples use the moving attachment's velocity and rate
        # in the aerodynamic evaluator, then the shared concentrated transfer.
        # Engine mass, inertia and rotor H are separate Weight records and have
        # already entered the real-inertia path above (unsteady Eqs.43--47).
        return self.add_aerodynamic_loads(r, Q, meshes, gamma, condition, operating_key,
            force, moment, records, couples, ends, local_motion=local_motion,
            circulation_rate=circulation_rate, _loads_only=_loads_only)


def solve_source_airflow_steady(model, condition, panels=24, *, gravity=None, loads=(),
        operating_constraints=(), tolerance=1e-8, continuation_steps=4,
        initial_state=None, progress=None, strut_mode='bilateral', controller=None, derivatives=None):
    """Zero-local-rate trim with full prescribed or solved frame motion.

    The instantaneous moving equilibrium uses the same inertia, aerodynamic
    loads and numerical identity as a time launch. Nonzero aircraft rates or
    accelerations do not imply constant Earth velocity or attitude.
    """
    from .equilibrium_state import warm_start_recipe
    from .source_discrete import _solve_source_network
    if controller is not None:
        return _solve_feedback(model, condition, panels, controller=controller,
            gravity=gravity, loads=loads, operating_constraints=operating_constraints,
            tolerance=tolerance, continuation_steps=continuation_steps,
            initial_state=initial_state, progress=progress, strut_mode=strut_mode, derivatives=derivatives)
    network = SourceAirflowNetwork(model, panels, condition, gravity, loads,
        operating_constraints=operating_constraints, steady_trim=True, strut_mode=strut_mode,
        mesh_recipe=warm_start_recipe(model, panels, initial_state))
    return _solve_source_network(network, tolerance, continuation_steps, initial_state, progress,
                                 derivatives=derivatives)


def _solve_feedback(model, condition, panels, *, controller, gravity, loads,
                    operating_constraints, tolerance, continuation_steps,
                    initial_state, progress, strut_mode, derivatives):
    """Couple the unchanged control-law equations to source mechanics and aero."""
    from functools import partial
    from .equilibrium_state import capture
    from .numerical_policy import validate_source_steady_constraints
    from .source_discrete import source_network_result
    from .steady_feedback import solve_feedback_base
    validate_source_steady_constraints(operating_constraints, moving=True)
    if progress is not None:
        progress('static_load', 0., 1.)
    n, state, feedback, options, steps, diagnostics = solve_feedback_base(
        model, condition, panels, controller=controller, gravity=gravity, loads=loads,
        operating_constraints=operating_constraints, tolerance=tolerance,
        continuation_steps=continuation_steps, strut_mode=strut_mode, initial_state=initial_state,
        network_class=partial(SourceAirflowNetwork, steady_trim=True))
    result = source_network_result(n, state.x, **options)
    _, data = n.residual(state.x, detail=True, **options)
    residual, result['feedback'] = feedback.evaluate(state, data, np.zeros(feedback.size))
    result.update(controller=feedback.report(), continuation_steps=steps,
        controller_equilibrium=diagnostics, equilibrium_initialization=diagnostics,
        residual=max(result['residual'], float(np.max(abs(residual)))))
    result['equilibrium_state'] = capture(n, state.x, feedback=feedback,
        feedback_values=state.feedback, commands=result['feedback']['commands'], residual=result['residual'])
    if derivatives is not None:
        from .derivatives import linearize_equilibrium
        result['derivatives'] = linearize_equilibrium(n, state.x,
            feedback=feedback, feedback_state=state, **derivatives)
    return result
