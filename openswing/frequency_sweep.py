"""Transactional frequency refinement on one owned, frozen dynamic model.

The browser retains one live sweep in its local worker. Reports are ordinary
portable JSON; a continuation handle is deliberately local to that process.
"""
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import hashlib
import json
import uuid
import numpy as np
from .aero import AnalysisError
from .frequency_response import FrequencyAnalysis, frequency_grid
from .beam_spline import NATURAL


def _digest(value):
    def portable(v):
        if is_dataclass(v):return portable(asdict(v))
        if isinstance(v,np.ndarray):return portable(v.tolist())
        if isinstance(v,np.generic):return v.item()
        if isinstance(v,dict):return {str(k):portable(x) for k,x in v.items()}
        if isinstance(v,(tuple,list)):return [portable(x) for x in v]
        return v
    return hashlib.sha256(json.dumps(portable(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class FrequencySweep:
    def __init__(self,model,condition,panels=8,*,frequencies,progress=None,_base_analysis=None,**options):
        omega=frequency_grid(frequencies)
        self.handle=dict(format='openswing-live-frequency',version=1,id=uuid.uuid4().hex,
            model_sha256=hashlib.sha256(model.dumps().encode()).hexdigest(),
            settings_sha256=_digest(dict(condition=condition,panels=panels,options=options)))
        if model.beam_interpolation != NATURAL:
            self.handle['beam_interpolation']=model.beam_interpolation
        self.analysis=FrequencyAnalysis(model,condition,panels,progress=progress,_base_analysis=_base_analysis,**options)
        operator = getattr(self.analysis.system.network, 'structural_operator', 'midpoint-v1')
        if operator != 'midpoint-v1':
            self.handle['structural_operator'] = operator
        self.result=self.analysis.solve(omega,progress)
        self.result['frequency_session']=deepcopy(self.handle)
        self.result['frequency_refinement']=dict(revision=0,retained_samples=0,
            added_frequencies=omega.tolist(),duplicate_frequencies=[],linearization_reused=False)

    def report(self, *, _copy=True):
        # Native callers own independent results. The serial browser encoder
        # only reads nested data and can borrow it until transfer completes.
        # Keep its outer mapping separate: dispatch adds numerical provenance.
        return deepcopy(self.result) if _copy else dict(self.result)

    def extend(self,frequencies,progress=None,*,_copy_result=True):
        # Sorting is useful for clicked/list input. Only exact duplicates merge:
        # close frequencies may resolve a narrow resonance and must stay distinct.
        try:
            values=list(frequencies)
            if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.integer,np.floating)) for v in values):raise ValueError()
            omega=frequency_grid(np.unique(np.asarray(values,dtype=float)))
        except (TypeError,ValueError,OverflowError) as exc:
            raise AnalysisError('Additional frequencies must be a nonempty list of finite nonnegative numbers [rad/input T].') from exc
        previous={s['omega']:s for s in self.result['samples']}
        missing=[float(w) for w in omega if w not in previous]
        duplicate=[float(w) for w in omega if w in previous]
        # No stored grid or result changes until every new calculation succeeds.
        addition=[] if not missing else self.analysis.solve(missing,progress)['samples']
        # Existing samples/base are immutable inside the sweep. A new mapping
        # and sorted list give transactional replacement without cloning all
        # nested outputs. Reports returned to native callers still deep-copy.
        merged=dict(self.result)
        merged['samples']=sorted(merged['samples']+addition,key=lambda row:row['omega'])
        merged['converged']=all(s['converged'] for s in merged['samples'])
        merged['frequency_refinement']=dict(revision=self.result['frequency_refinement']['revision']+bool(missing),
            retained_samples=len(previous),added_frequencies=missing,duplicate_frequencies=duplicate,linearization_reused=True)
        self.result=merged
        return self.report(_copy=_copy_result)


_active=None
_retained=None


def start(model,condition,panels=8,*,_copy_result=True,**options):
    global _active,_retained
    prepared=_active.analysis if _active is not None else _retained
    sweep=FrequencySweep(model,condition,panels,_base_analysis=prepared,**options)
    _active=sweep
    _retained=None
    return sweep.report(_copy=_copy_result)


def extend(model,session,frequencies,progress=None,*,_copy_result=True):
    if _active is None or session!=_active.handle:
        raise AnalysisError('This frequency continuation session has expired. Run the frequency analysis again before adding samples.')
    if hashlib.sha256(model.dumps().encode()).hexdigest()!=_active.handle['model_sha256']:
        raise AnalysisError('Frequency refinement requires the exact ASW source of the loaded analysis; run a new analysis after changing the model.')
    if model.beam_interpolation != _active.handle.get('beam_interpolation', NATURAL):
        raise AnalysisError('Frequency refinement requires the same beam interpolation policy; run a new analysis after changing it.')
    return _active.extend(frequencies,progress,_copy_result=_copy_result)


def discard(session,*,retain_model=False):
    global _active,_retained
    if type(retain_model) is not bool:raise ValueError('retain_model must be boolean.')
    matched=_active is not None and session==_active.handle
    if matched:
        # Drop the potentially large frequency/output grid. Keep at most one
        # local physical model, whose complete identity is checked on reuse.
        _retained=_active.analysis if retain_model else None
        _active=None
    return dict(released=matched)
