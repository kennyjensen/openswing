"""Physical uniqueness and fixed-controller-IC gates; all mechanics use m=1 kg.

The ordinary BDF negative test raises an explicit observer sentinel only after
production's accepted-root rank check has actually rejected its first step.
This bounds the test without modifying retry policy or solving tolerances.
"""
from pathlib import Path
import json,os
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing import time_integration as api

B=Path(__file__).resolve().parents[1]
BODY=(B/'examples/guided-body.asw').read_text()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
class FirstStepRejected(RuntimeError):pass

def solve(controller,*,order=1,frame='free'):
    return api.solve_time(parse_asw(BODY),FlightCondition(speed=10,alpha=0,mach=0),
        panels=4,gravity=[0,0,0],duration=.02,dt=.02,order=order,frame=frame,
        load_targets={'force.x':0.} if frame=='mixed' else None,controller=controller)

@pytest.fixture
def observed(monkeypatch,tmp_path):
    calls=[];saved={};original_init=api.TimeSystem.__init__;original_newton=api.newton
    def write():
        Path(os.environ.get('RANK_RECORD',str(tmp_path/'newton-calls.json'))).write_text(json.dumps(calls,indent=2,allow_nan=False)+'\n')
    def init(self,*args,**kwargs):original_init(self,*args,**kwargs);saved['system']=self
    def newton(function,guess,tolerance,factorization=None,*,check_rank=False):
        module=function.__module__;phase='cold' if module.endswith('.feedback') else 'radau' if module.endswith('.radau_time') else 'accuracy' if module.endswith('.time_accuracy') else 'bdf'
        row=dict(phase=phase,check_rank=bool(check_rank),size=len(guess),entry_residual=float(np.max(abs(function(guess)))))
        calls.append(row);write()
        try:answer=original_newton(function,guess,tolerance,factorization,check_rank=check_rank)
        except api.StepFailure as exc:
            row.update(outcome='rejected',error=str(exc));write()
            if saved.get('halt_bdf_retry') and phase=='bdf' and 'locally unique' in str(exc):raise FirstStepRejected(str(exc)) from exc
            raise
        values=answer[0];row.update(outcome='accepted',residual=float(np.max(abs(function(values)))))
        # Only negative fixtures request this independent force/acceleration family.
        if saved.get('negative'):
            system=saved['system'];n=system.network;control=system.feedback
            ax=next(i for i,c in enumerate(n.operating.constraints) if c.variable=='acceleration.x')
            delta=np.zeros_like(values)
            if phase=='cold':
                delta[n.operating_start+ax]=1/n.operating.scale['acceleration.x'];delta[n.size]=1/control.scales[0]
            else:
                stages=delta.reshape(3,system.size) if phase=='radau' else delta[None,:]
                if phase=='radau':
                    from openswing.radau_time import NODES
                    fractions=NODES
                else:fractions=[1]
                for stage,fraction in zip(stages,fractions):
                    t=.02*float(fraction);stage[n.operating_start+ax]=1/n.operating.scale['acceleration.x']
                    stage[system.feedback_start]=1/control.scales[0];stage[system.frame_start]=t/system.V
                    stage[system.frame_start+6]=t*t*(.5 if phase=='radau' else 1)/n.L
            row['force_family']=[{'delta_force_N':v,'residual':float(np.max(abs(function(values+v*delta))))} for v in (-.3,.3)]
            function(values)
        write();return answer
    monkeypatch.setattr(api.TimeSystem,'__init__',init);monkeypatch.setattr(api,'newton',newton)
    saved['calls']=calls
    return saved

@pytest.mark.parametrize('kind',['implicit_zero','explicit_acceleration'])
def test_cold_rejects_unowned_actuator(observed,kind):
    observed['negative']=True
    output={'actuator':'E1','residual':'0'} if kind=='implicit_zero' else {'actuator':'E1','terms':[{'input':'Ax','gain':1.,'mode':'value'}]}
    with pytest.raises(api.StepFailure,match='locally unique'):
        solve({'outputs':[output]})
    assert observed['calls'][0]['phase']=='cold'

@pytest.mark.parametrize('route',['bdf','radau','accuracy'])
def test_valid_cold_rejects_lost_step_authority(observed,monkeypatch,route):
    observed['negative']=True
    control={'outputs':[{'actuator':'E1','residual':"where(time <= 0, actuator('E1'), 0)"}]}
    if route=='bdf':observed['halt_bdf_retry']=True;expected=FirstStepRejected
    else:
        expected=api.StepFailure
        def one_step(system,previous,older,options,setup,**kwargs):
            assert previous.time==0 and previous.feedback[0]==pytest.approx(0,abs=1e-10)
            system.network.loads=setup['loads']
            if route=='radau':
                from openswing.radau_time import step
                return step(system,previous,.02,setup['frame'],'right',1e-8)
            from openswing.time_accuracy import take_step
            return take_step(system,previous,None,.02,1,setup['frame'],'right',1e-8)
        monkeypatch.setattr(api,'integrate',one_step)
    with pytest.raises(expected,match='locally unique'):
        solve(control,order=5 if route=='radau' else 1)
    calls=observed['calls'];assert len(calls)==2 and calls[0]['outcome']=='accepted'
    assert calls[1]['phase']==route and calls[1]['outcome']=='rejected'
    assert all(c['check_rank'] for c in calls)

@pytest.mark.parametrize('kind,order,frame',[('implicit',1,'free'),('explicit',5,'mixed')])
def test_regular_controller_has_independent_force_and_trajectory(observed,kind,order,frame):
    output={'actuator':'E1',**({'residual':"actuator('E1')-.2"} if kind=='implicit' else {'expression':'.2'})}
    out=solve({'outputs':[output]},order=order,frame=frame)
    assert out['accepted_steps']==1 and out['rejected_steps']==0
    for snapshot in out['snapshots']:
        assert snapshot['feedback']['actuators']['E1']==pytest.approx(.2,abs=1e-7)
        np.testing.assert_allclose(snapshot['frame']['acceleration_reference_body'],[.2,0,0],atol=1e-7)
    final=out['snapshots'][-1]
    assert final['frame']['velocity_origin_body'][0]==pytest.approx(-10+.2*.02,abs=1e-8)
    assert final['frame']['position_earth'][0]==pytest.approx(-10*.02+.2*.02**2*(1 if order==1 else .5),abs=1e-8)
    assert len(observed['calls'])==2


def test_nonzero_custom_initial_value_and_rate_are_preserved(observed):
    control={'outputs':[{'actuator':'E1','expression':"state('held')"}],
        'states':[{'name':'held','initial':.2,'scale':1.,'unit':'N','rate':'.1'}]}
    out=solve(control)
    assert out['accepted_steps']==1 and out['rejected_steps']==0
    for row in out['snapshots']:
        t=row['time'];expected=.2+.1*t
        assert row['feedback']['states']['held']==pytest.approx(expected,abs=1e-9)
        assert row['feedback']['state_rates']['held']==pytest.approx(.1,abs=1e-12)
        assert row['feedback']['actuators']['E1']==pytest.approx(expected,abs=1e-7)
        assert row['frame']['acceleration_reference_body'][0]==pytest.approx(expected,abs=1e-7)
    final=out['snapshots'][-1]
    assert final['frame']['velocity_origin_body'][0]==pytest.approx(-10+.202*.02,abs=1e-8)
    assert final['frame']['position_earth'][0]==pytest.approx(-10*.02+.202*.02**2,abs=1e-8)
    assert observed['calls'][0]['size']==observed['system'].network.size+1


def test_steady_helper_keeps_existing_neutral_state_family(observed,monkeypatch):
    # This is helper compatibility, not a claim that public steady trim accepts
    # a nonunique controller equilibrium. Its separate trim rank gates remain.
    control={'outputs':[{'actuator':'E1','expression':'0'}],
        'states':[{'name':'held','initial':.3,'scale':1.,'unit':'N','rate':'0'}]}
    def handoff(system,previous,older,options,setup,**kwargs):
        from openswing.feedback import equilibrium
        state,_=equilibrium(system,previous,options,1e-8,steady=True)
        return state
    monkeypatch.setattr(api,'integrate',handoff)
    state=solve(control)
    assert state.feedback[1]==pytest.approx(.3,abs=1e-12)
    assert len(observed['calls'])==2 and observed['calls'][1]['check_rank'] is False
    assert observed['calls'][1]['size']==observed['system'].network.size+2
