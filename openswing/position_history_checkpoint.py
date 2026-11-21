"""Accepted position-history provenance and compatible BDF/Radau restarts.

Replacement tables and support breaks complete a separate right state.
Saved-before-input position-history bootstrap remains unsupported.
Never manufacture an old sample from future inputs.
"""
from dataclasses import asdict
from numbers import Real
import numpy as np
from .aero import AnalysisError
from .position_history_lift import PositionSample


def pack_sample(sample):
    if not isinstance(sample,PositionSample):
        raise AnalysisError('Invalid accepted position-history sample.')
    return asdict(sample)


def _number(value):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,Real):
        raise AnalysisError('Checkpoint position-history sample requires finite real numbers.')
    try:value=float(value)
    except (ValueError,OverflowError) as exc:
        raise AnalysisError('Checkpoint position-history sample requires finite real numbers.') from exc
    if not np.isfinite(value):raise AnalysisError('Checkpoint position-history sample requires finite real numbers.')
    return value


def unpack_sample(data):
    keys={'time','side','signature','value','rate','acceleration','branch','intervals'}
    if not isinstance(data,dict) or set(data)!=keys:
        raise AnalysisError('Invalid checkpoint position-history sample fields.')
    if not isinstance(data['side'],str) or data['side'] not in ('left','right'):
        raise AnalysisError('Invalid checkpoint position-history side.')
    signature=data['signature']
    if not isinstance(signature,str) or len(signature)!=64 or any(c not in '0123456789abcdef' for c in signature):
        raise AnalysisError('Invalid checkpoint position-history definition signature.')
    if not isinstance(data['branch'],str) or data['branch'] not in ('constant target','table','empty','zero cutoff'):
        raise AnalysisError('Invalid checkpoint position-history branch.')
    vectors=[]
    for key in ('value','rate','acceleration'):
        values=data[key]
        if not isinstance(values,(list,tuple)) or len(values)!=3:
            raise AnalysisError('Invalid checkpoint position-history '+key+' shape.')
        vectors.append(tuple(_number(v) for v in values))
    intervals=[]
    if not isinstance(data['intervals'],(list,tuple)):
        raise AnalysisError('Invalid checkpoint position-history intervals.')
    for entry in data['intervals']:
        if not isinstance(entry,(list,tuple)) or len(entry)!=2 or entry[0] not in ('position_earth.x','position_earth.y','position_earth.z'):
            raise AnalysisError('Invalid checkpoint position-history interval owner.')
        interval=entry[1]
        if interval is not None:
            if not isinstance(interval,(list,tuple)) or len(interval)!=2:
                raise AnalysisError('Invalid checkpoint position-history interval.')
            interval=tuple(_number(v) for v in interval)
            if interval[0]>=interval[1]:raise AnalysisError('Invalid checkpoint position-history interval order.')
        intervals.append((entry[0],interval))
    if len({entry[0] for entry in intervals})!=len(intervals):
        raise AnalysisError('Duplicate checkpoint position-history interval owner.')
    return PositionSample(_number(data['time']),data['side'],signature,*vectors,data['branch'],tuple(intervals))


def method_metadata(system,order):
    lift=system.position_lift
    if lift is None:return None
    lift._check_context(system.forcing)
    from .position_history_radau import POLICY
    return dict(version=1,policy=lift.policy if order in (1,2) else POLICY if order==5 else 'original-continuous-dae-v1',
        signature=lift.signature,definition=lift.definition(system.forcing))


def _same_definition(actual, expected):
    """Exact input identity across JSON numeric spellings; no tolerance.

    JavaScript serializes integral floats as integers and removes signed zero.
    Compare their numerical values without changing stored definition signatures.
    Booleans, text, fields and array order retain their distinct meanings.
    """
    if isinstance(expected, dict):
        return (isinstance(actual, dict) and actual.keys() == expected.keys()
                and all(_same_definition(actual[key], value) for key, value in expected.items()))
    if isinstance(expected, (list, tuple)):
        return (isinstance(actual, (list, tuple)) and len(actual) == len(expected)
                and all(_same_definition(a, b) for a, b in zip(actual, expected)))
    if isinstance(expected, Real) and not isinstance(expected, (bool, np.bool_)):
        return (isinstance(actual, Real) and not isinstance(actual, (bool, np.bool_))
                and actual == expected)
    return type(actual) is type(expected) and actual == expected


def validate_checkpoint(n,feedback,state,older,saved):
    """Reconstruct accepted inputs and cross-check cache and hidden constraints."""
    from .forcing import TimeForcing
    from .time_integration import TimeSystem
    from .time_state import scalar
    ctx=saved['context'];setup=ctx['setup'];method=ctx['method']
    bare=TimeSystem(n,gravity_magnitude=setup.get('gravity_magnitude'))
    if bare.position_lift is None:
        if method.get('position_history') is not None or state.position_history is not None or (older is not None and older.position_history is not None):
            raise AnalysisError('Checkpoint position-history metadata has no selected position target.')
        return None
    metadata=method.get('position_history')
    if isinstance(method.get('order'),bool) or method.get('order') not in (1,2,5):
        raise AnalysisError('Position-history checkpoint continuation requires BDF1, BDF2 or Radau IIA.')
    if not isinstance(metadata,dict) or set(metadata)!= {'version','policy','signature','definition'} or type(metadata['version']) is not int or metadata['version']!=1:
        raise AnalysisError('Position-history checkpoint requires accepted-definition and derivative-policy metadata; legacy samples cannot be regenerated.')
    first=state.time if older is None else older.time
    forcing=TimeForcing(setup['forcing'],n.model,n.condition,n.motion,state.time,setup['frame'],feedback,
        start_time=first,load_targets=setup.get('load_targets'),actuator_constraints=setup.get('actuator_constraints'))
    offsets=ctx['forcing_offsets']
    if not isinstance(offsets,dict) or set(offsets)!={c['name'] for c in forcing.channels}:
        raise AnalysisError('Checkpoint position-history original forcing offsets are missing or mismatched.')
    for channel in forcing.channels:
        channel['initial']=scalar(offsets[channel['name']],'original forcing offset')
    system=TimeSystem(n,forcing,feedback,gravity_magnitude=setup.get('gravity_magnitude'))
    lift=system.position_lift
    expected=method_metadata(system,method['order'])
    try:matches=_same_definition(metadata,expected)
    except (ValueError,TypeError,OverflowError) as exc:
        raise AnalysisError('Invalid checkpoint position-history definition metadata.') from exc
    if not matches:
        raise AnalysisError('Checkpoint position-history definition or derivative policy disagrees with its original inputs and offsets.')
    tolerance=max(scalar(method['tolerance'],'saved tolerance',True),1e-8)
    lift.tolerance=tolerance
    lift.validate_sample(state,forcing,tolerance=tolerance)
    if state.position_history.side!=saved['forcing_side']:
        raise AnalysisError('Checkpoint forcing side disagrees with its accepted position-history sample.')
    if older is not None:lift.validate_sample(older,forcing,tolerance=tolerance)
    return system


def validate_acceleration(system,state,options):
    """Certify selected hidden accelerations using accepted physical inputs.

    Call after original sample and physical/cache validation. OperatingSystem
    supplies the solved acceleration/actuator values; the prescribed Motion
    cache alone is not the actual inertial state. Transport r_a to the origin
    once, then rotate to Earth. Never reapply future forcing or constrain an
    unselected Earth component. Only the current checkpoint has full options.
    """
    if system is None or system.position_lift is None:return
    n=system.network;lift=system.position_lift
    _,motion,_=n.operating.apply(state.x[n.operating_start:],
        condition_override=options['condition_override'],motion_override=options['motion_override'])
    physical=state.orientation@motion.at(np.zeros(3),n.model.reference[2])
    difference=(physical-np.asarray(state.position_history.acceleration))/system.A
    error=float(np.max(abs(difference[lift.mask]),initial=0.))
    if not np.isfinite(error) or error>lift.tolerance:
        raise AnalysisError(f'Checkpoint position-history physical origin acceleration disagrees with the accepted target jet (scaled difference {error:.3g}).')


def require_smooth_continuation(system,source,original_source,state,order,*,end_time=None):
    if system.position_lift is None:return
    if order not in (1,2,5):
        raise AnalysisError('Unsupported position-history continuation method.')
    # The original sample was already validated against its owned definition.
    # Replacements and left-side breaks are completed explicitly before the
    # next time step; only the new right state receives a new target sample.
