"""Owned capture of the discrete problem that produced a checkpoint.

Capture changes output metadata only. It neither replays acceptance nor turns
an initial physical snapshot into a continuous derivative certificate.
"""
from copy import deepcopy
import numpy as np
from .equilibrium_state import identity
from .time_state import portable,pack_state,pack_options,feedback_data

VERSION=1
PRODUCER='openswing-time-acceptance-v1'
BDF_SCHEME_V1='openswing-so3-bdf-v1'
BDF_SCHEME='openswing-so3-bdf-v2'
SOURCE_BDF_SCHEME='drela-euler-bdf-v1'
RADAU_SCHEME='openswing-so3-radau-iia-3-v1'
RADAU_POSITION_SCHEME='openswing-so3-position-defect-radau-iia-3-v1'
INITIAL_SCHEME='openswing-cached-initial-physical-v1'


def chart_layout(system,*,position_radau=False):
    """Declare the exact ordered chart and scales used by the stored unknowns."""
    n=system.network;f=system.feedback
    result=dict(chart='scaled-local-so3-and-earth-position-defect-v1' if position_radau else 'scaled-local-so3-and-body-frame-v1',size=system.size,
        network_size=n.size,node_count=n.nn,circulation_coefficients=n.ng,
        circulation_start=n.gamma_start,operating_start=n.operating_start,
        local_velocity_start=n.size,frame_start=system.frame_start,feedback_start=system.feedback_start,
        feedback_count=0 if f is None else f.count,feedback_size=0 if f is None else f.size,
        ordered_blocks=['network','local_velocity','local_angular_velocity',
                        'origin_earth_velocity_defect' if position_radau else 'origin_body_velocity',
                        'body_angular_velocity','earth_position_defect' if position_radau else 'earth_position',
                        'frame_rotation_increment','feedback'],
        scales=portable(dict(length=n.L,velocity=system.V,rate=system.W,acceleration=system.A,
            force=n.F,circulation=n.gamma_scale,operating=deepcopy(n.operating.scale),
            feedback=[] if f is None else f.scales.copy())))
    if getattr(n,'source_moving',False):result['angle_history']='source-material-and-aircraft-euler-v1'
    return result


def accepted_inputs(system,setup,order,step,tolerance,*,cached=False):
    """Own old accepted inputs independently of the next continuation request."""
    n=system.network;forcing=system.forcing;owned=deepcopy(setup)
    owned['loads']=portable(deepcopy(n.loads))
    owned['forcing']='' if cached or forcing is None else forcing.source
    result=dict(identity=identity(n),setup=portable(owned),feedback=feedback_data(system.feedback),
        forcing_offsets={} if cached or forcing is None else {c['name']:float(c['initial']) for c in forcing.channels},
        method=dict(order=int(order),maximum_step=float(step),tolerance=float(tolerance)),
        input_policy='cached_anchor_before_next_inputs' if cached else 'physical_time_forcing')
    if not cached:
        from .position_history_checkpoint import method_metadata
        metadata=method_metadata(system,order)
        if metadata is not None:result['method']['position_history']=portable(metadata)
    return deepcopy(result)


def _common(system,state,options,setup,*,kind,scheme,order,step,side,tolerance,selection,cached=False):
    return dict(version=VERSION,producer_policy=PRODUCER,kind=kind,scheme=scheme,
        validation_level='physical_only' if kind=='initial' else 'captured_discrete_problem',
        accepted_inputs=accepted_inputs(system,setup,order,step,tolerance,cached=cached),
        layout=chart_layout(system),end_time=float(state.time),endpoint_side=side,tolerance=float(tolerance),
        endpoint=dict(state=pack_state(system.network,state),options=pack_options(options)),
        selection=deepcopy(selection or dict(mode='ordinary')))


def capture_initial(system,state,options,setup,*,phase,side,tolerance):
    cached=phase.startswith(('checkpoint','saved_equilibrium'))
    result=_common(system,state,options,setup,kind='initial',scheme=INITIAL_SCHEME,order=0,
        step=0.,side=side,tolerance=tolerance,selection=dict(mode='initial_snapshot'),cached=cached)
    result.update(phase=phase,continuous_certificate=False,
        limitation='Initial cached physical state/options only; no authenticated continuous rates, hidden constraints or derivative-array certificate are captured here.')
    return result


def capture_bdf(system,previous,previous2,state,options,setup,*,values,time,coefficients,side,tolerance,
                nonlinear_tolerance,nonlinear_policy,selection=None):
    effective=1 if previous2 is None else 2
    result=_common(system,state,options,setup,kind='bdf',
        scheme=SOURCE_BDF_SCHEME if getattr(system.network,'source_moving',False) else BDF_SCHEME,order=effective,
        step=time-previous.time,side=side,tolerance=tolerance,selection=selection)
    result.update(effective_order=effective,step=float(time-previous.time),values=np.asarray(values).copy().tolist(),
        previous=pack_state(system.network,previous),
        previous2=None if previous2 is None else pack_state(system.network,previous2),
        coefficients=np.asarray(coefficients).copy().tolist(),nonlinear_tolerance=float(nonlinear_tolerance),
        nonlinear_policy=deepcopy(nonlinear_policy))
    return result


def capture_radau(system,seed,state,options,setup,*,stage_data,side,tolerance,selection=None):
    position_radau=system.position_lift is not None
    result=_common(system,state,options,setup,kind='radau_iia',scheme=RADAU_POSITION_SCHEME if position_radau else RADAU_SCHEME,order=5,
        step=stage_data['step'],side=side,tolerance=tolerance,selection=selection)
    result['layout']=chart_layout(system,position_radau=position_radau)
    result.update(step=float(stage_data['step']),seed=pack_state(system.network,seed),
        initial_chart_values=deepcopy(stage_data['initial']),increments=deepcopy(stage_data['increments']),
        stage_times=deepcopy(stage_data['times']),stage_sides=deepcopy(stage_data['sides']),
        stage_tolerance=float(stage_data['tolerance']))
    return result
