"""Public point-mass transitions and retry ownership, with independent forces."""
from pathlib import Path
from copy import deepcopy
import json
import pytest
from openswing.bridge import dispatch
from openswing.asw import parse_asw
from openswing.time_state import checkpoint,restore_checkpoint
from openswing.aero import AnalysisError

B=Path(__file__).parent/'inputs'

@pytest.mark.parametrize('adaptive',[False,True])
def test_rejected_future_left_trial_keeps_completed_right_state(monkeypatch,adaptive):
    import openswing.time_integration as fixed
    import openswing.time_accuracy as checked
    import openswing.time_input_transition as transition
    source=(B/'rigid.asw').read_text();saved=json.loads((B/'right-checkpoint.json').read_text())
    # Only the next scheduling hint changes. All accepted physical data and
    # original method metadata remain owned by the retained checkpoint.
    saved['next_step']=.94;before=deepcopy(saved)
    module=checked if adaptive else fixed;name='take_step' if adaptive else 'newton'
    original=getattr(module,name);calls=[]
    def reject_once(*args,**kwargs):
        calls.append(True)
        if len(calls)==1:raise fixed.StepFailure('Injected first trial failure')
        return original(*args,**kwargs)
    def forbidden(*args,**kwargs):raise AssertionError('A completed right state was initialized again')
    monkeypatch.setattr(module,name,reject_once);monkeypatch.setattr(transition,'complete',forbidden)
    settings=dict(duration=.94,dt=.94,order=1,tolerance=1e-11)
    if adaptive:settings['accuracy']=dict(rtol=.1,atol=.1)
    result=dispatch(dict(action='resume_time',source=source,checkpoint=saved,time=settings))
    assert saved==before and result['rejected_steps']==1 and len(calls)>1
    assert result['snapshots'][-1]['time']==1.
    assert all('input_transition' not in s for s in result['snapshots'])
    for i,s in enumerate(result['snapshots']):
        restore_checkpoint(parse_asw(source),checkpoint(result,i))
        if i:
            expected=saved['state']['velocity_origin_body'][0]-.2*(s['time']-.06)
            assert abs(s['operating_values']['power.1']+.2)<1e-7
            assert abs(s['frame']['velocity_origin_body'][0]-expected)<1e-9

def test_incompatible_cutoff_refuses_before_derivative_completion(monkeypatch):
    import openswing.time_transition_initial as transition
    source=(B/'rigid.asw').read_text();saved=json.loads((B/'right-checkpoint.json').read_text());before=deepcopy(saved)
    v=saved['state']['velocity_origin_body'][0]
    def forbidden(*args,**kwargs):raise AssertionError('Incompatible velocity entered derivative sweep')
    monkeypatch.setattr(transition,'consistent_initial',forbidden)
    table=f'time velocity_earth.x\n.04 {v+.004!r}\n.06 {v!r}'
    with pytest.raises(AnalysisError,match='disagrees with the retained physical state'):
        dispatch(dict(action='resume_time',source=source,checkpoint=saved,time=dict(duration=.02,dt=.02,forcing=table)))
    assert saved==before

def test_replacement_and_interior_break_preserve_motion_and_restart_each_branch():
    source=(B/'rigid.asw').read_text();saved=json.loads((B/'before-checkpoint.json').read_text());before=deepcopy(saved)
    v0=saved['state']['velocity_origin_body'][0];v1=v0+.016
    table=f'time velocity_earth.x\n.04 {v0!r}\n.06 {v1!r}\n.06 {v1!r}\n1 {v1-.94*.2!r}'
    result=dispatch(dict(action='resume_time',source=source,checkpoint=saved,time=dict(duration=.04,dt=.02,order=2,forcing=table)))
    assert saved==before and checkpoint(result,0)==before
    assert result['accepted_steps']==2 and result['rejected_steps']==0
    assert [s['order'] for s in result['snapshots']]==[0,0,1,0,1]
    p=saved['state']['position_earth'][0]
    for i,s in enumerate(result['snapshots']):
        restore_checkpoint(parse_asw(source),checkpoint(result,i))
        if not i:continue
        a=.8 if i<3 else -.2
        v=v0+.8*(s['time']-.04) if s['time']<=.06 else v1-.2*(s['time']-.06)
        if s['step']>0:p+=s['step']*v
        assert abs(s['operating_values']['power.1']-a)<1e-7
        assert abs(s['frame']['acceleration_reference_body'][0]-a)<1e-7
        assert abs(s['frame']['velocity_origin_body'][0]-v)<1e-9
        assert abs(s['frame']['position_earth'][0]-p)<1e-8
        if 'input_transition' in s:
            assert max(s['input_transition']['held_physical_max_error'].values())<1e-12
