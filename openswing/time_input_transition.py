"""Explicit continuous-state completion between two physical input branches."""
from copy import copy,deepcopy
import numpy as np
from .aero import AnalysisError
from .forcing import RightLimitForcing
from .time_cold_initial import cold_history_targets
from .time_transition_initial import complete_history_transition


def needed(system,state,side,changed=False):
    """Ordinary histories retain their existing input-switch convention."""
    if not changed and (side!='left' or state.time not in system.forcing.breaks):
        return False
    return bool(cold_history_targets(system.network.operating.constraints))


def complete(system,before,setup,*,tolerance,progress,step,reason,before_snapshot):
    """Return a separately owned right snapshot; never overwrite an old step.

    This operation is outside step retry: reducing a future step cannot repair
    an incompatible retained velocity/pose or manufacture an impulse.
    """
    from .time_integration import time_snapshot
    from .time_state import record
    from .time_acceptance import capture_initial
    try:
        state,options,completion=complete_history_transition(system,before,setup['frame'],
            tolerance=tolerance,progress=progress)
    except AnalysisError as exc:
        raise AnalysisError(f'Input transition at t={before.time:.9g} cannot retain the physical state: {exc}') from exc
    fields=('r','Q','gamma','u','w','U','Omega','position','orientation')
    held={name:float(np.max(abs(getattr(state,name)-getattr(before,name)),initial=0.)) for name in fields}
    if system.feedback is not None:
        first=system.feedback.count
        held['controller_dynamic_states']=float(np.max(abs(state.feedback[first:]-before.feedback[first:]),initial=0.))
    chart=completion['completion']
    if any(chart['state_increment'][i]!=0. for i in chart['dynamic_indices']):
        raise AnalysisError('Input transition changed a held dynamic chart coordinate.')
    physical=copy(system)
    physical.forcing=RightLimitForcing(system.forcing,state.time)
    snapshot=time_snapshot(physical,state,options,completion['residual'],0,0.,'right')
    snapshot['initial_phase']='input_transition_right_limit'
    snapshot['input_transition']=dict(version=1,reason=reason,time=float(state.time),
        held_physical_max_error=held,
        before_state=deepcopy(before_snapshot['restart']['state']),
        before_options=deepcopy(before_snapshot['restart']['options']),
        completion=deepcopy(completion),
        semantics='Zero elapsed time; physical dynamic chart coordinates are held. Algebraic settings and rates are completed on the right branch. SO(3)/scale roundoff in physical fields is reported.')
    accepted=capture_initial(system,state,options,setup,phase=snapshot['initial_phase'],side='right',tolerance=tolerance)
    snapshot['restart']=record(system,state,None,options,step,'right',accepted_method=accepted)
    return state,options,snapshot
