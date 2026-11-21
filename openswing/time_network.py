"""Select the physical time operator consistently at every reconstruction site."""
from .aero import AnalysisError
from .beam_spline import DRELA_SEGSPL
from .network import StaticNetwork
from .source_dynamics import SourceMovingNetwork, MOVING_POLICY
from .source_airflow import SourceAirflowNetwork, AIRFLOW_POLICY


def source_time_chart(network):
    """Lazily require the temporal chart, leaving existing modal scope intact."""
    if not getattr(network, 'source_moving', False):
        return None
    if not hasattr(network, '_source_time_chart'):
        from .source_time import SourceTimeChart
        network._source_time_chart = SourceTimeChart(network)
    return network._source_time_chart


def time_network_class(model, condition, *, frame, structural_operator=None,
                       identity=None, controller=None, actuator_constraints=None,
                       strut_mode='bilateral', require_saved_operator=False):
    """Saved identity selects the equations; an explicit setup must agree.

    Modal launch packets predate the time setup field and may select through
    their identity alone. Newly produced time checkpoints require both fields.
    """
    saved = None if identity is None else identity.get('structural_operator', 'midpoint-v1')
    if saved is not None and structural_operator is not None and saved != structural_operator:
        raise AnalysisError('Saved time structural operator and setup disagree.')
    operator = structural_operator if structural_operator is not None else saved
    if operator in (None, 'midpoint-v1'):
        return StaticNetwork
    if operator not in (MOVING_POLICY, AIRFLOW_POLICY):
        raise AnalysisError('This source structural operator does not support nonlinear time response.')
    if require_saved_operator and structural_operator != operator:
        raise AnalysisError('Source time checkpoint setup is missing its structural operator.')
    if model.beam_interpolation != DRELA_SEGSPL:
        raise AnalysisError('Source time dynamics requires drela-segspl-v1 interpolation.')
    flowing = operator == AIRFLOW_POLICY
    if flowing:
        from .aero import FlightCondition
        if not isinstance(condition, FlightCondition):
            raise AnalysisError('Source airflow time dynamics requires a FlightCondition.')
    elif condition is not None:
        raise AnalysisError('Source moving time dynamics currently requires vacuum, without a FlightCondition.')
    if frame not in ('prescribed', 'free', 'mixed'):
        raise AnalysisError('Source time frame must be prescribed, free or mixed.')
    if not flowing and controller is not None:
        raise AnalysisError('Source moving vacuum time dynamics does not support controllers.')
    if actuator_constraints:
        raise AnalysisError('Source moving time dynamics does not support actuator/history constraints.')
    if strut_mode not in ('bilateral', 'wire'):
        raise AnalysisError('Strut mode must be bilateral or wire.')
    return SourceAirflowNetwork if flowing else SourceMovingNetwork


def source_time_result(system, result, order):
    """Declare the actual source equations and the independent time method."""
    if not getattr(system.network, 'source_moving', False):
        return result
    from .time_acceptance import SOURCE_BDF_SCHEME, RADAU_SCHEME
    operator = system.network.structural_operator
    result.update(structural_operator=operator,
                  numerics=dict(beam_interpolation=DRELA_SEGSPL, structural_operator=operator),
                  temporal_policy=RADAU_SCHEME if order == 5 else SOURCE_BDF_SCHEME)
    result['limitations'] = [
        'Source endpoint vacuum inertia and material damping with moving-frame transport. ASWING executable parity remains unverified.',
        'BDF1/BDF2 discretize the material and Earth Euler angles in the published kinematic equations. Saved continuous angle branches are binding; singular or ambiguous charts are rejected.',
        'Radau IIA is an OpenSwing continuous-equation extension, not the time discretization described in the ASWING paper.',
        'Prescribed, free and mixed canonical frame loads are supported. Airflow, fluid inertia, controllers, actuator/history constraints, engines and stepped axes remain unavailable for this source policy.',
        'Time-step and mesh refinement remain necessary. Nonlinear convergence alone does not establish trajectory accuracy.']
    if getattr(system.network, 'source_airflow', False):
        result['limitations'][0] = ('Source moving-frame real inertia and material damping coupled to circulation, '
            'circulation-rate lift and apparent-fluid loads at Glauert aerodynamic sections. ASWING executable parity remains unverified.')
        result['limitations'][3] = ('Prescribed, free and mixed canonical frame loads, aerodynamic controls, engine settings and gusts are supported. '
            'Feedback actuator equations and error integrals are supported; actuator/history constraints and stepped axes remain unavailable. '
            'Fluid quadrature differs from the stationary source still-air policy.')
    return result
