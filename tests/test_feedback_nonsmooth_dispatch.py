"""Synthetic dispatch controls only; these are not aircraft mechanics tests."""
from types import SimpleNamespace as NS
import numpy as np
import pytest
import openswing.time_integration as api
import openswing.time_accuracy as checked
import openswing.time_state as saved

@pytest.mark.parametrize('route',['ordinary','checked'])
@pytest.mark.parametrize('fatal',[False,True],ids=['ordinary_step_failure_recovers','witness_refusal_stops'])
def test_march_refusal_dispatch_preserves_retry(monkeypatch,route,fatal):
    calls=[];original_newton=api.newton
    exception=api.UnresolvedControllerAuthority('Synthetic witnessed alternatives') if fatal else api.StepFailure('Synthetic ordinary nonlinear failure')
    if fatal:exception.accepted_root_witness={'synthetic_dispatch_only':True}
    def newton(function,guess,tolerance,factorization=None,*,check_rank=False):
        calls.append(float(guess[0]))
        if len(calls)==1:raise exception
        return original_newton(function,guess,tolerance,factorization,check_rank=check_rank)
    monkeypatch.setattr(api,'newton',newton)
    monkeypatch.setattr(api,'time_snapshot',lambda system,state,options,error,order,step,side:dict(time=state.time,residual=error,order=order,step=step))
    monkeypatch.setattr(saved,'context',lambda *args,**kwargs:{})
    monkeypatch.setattr(saved,'record',lambda *args,**kwargs:{})
    # This scalar dispatch fixture has no physical network/state to serialize.
    # Acceptance records are covered by real-state replay tests; keep this
    # test focused on retry versus fatal-authority dispatch on both paths.
    import openswing.time_acceptance as acceptance
    for name in ('capture_initial','capture_bdf','capture_radau'):
        monkeypatch.setattr(acceptance,name,lambda *args,**kwargs:{})
    # The scalar fixture also has no structural mesh for sparse assembly.
    # Exercise retry dispatch with its scalar Newton solve on both routes.
    import openswing.structured_time as structured
    monkeypatch.setattr(structured,'eligible',lambda system:False)
    monkeypatch.setattr(checked,'compare',lambda *args,**kwargs:dict(maximum_ratio=0.,limiting_quantity='synthetic'))
    net=NS(condition=None,loads=None,nfev=0,L=1.,F=1.,gamma_scale=1.,operating=NS(constraints=[]),residual=lambda *args,**kwargs:np.zeros(1))
    def residual(values,previous,older,time,coefficients,side='right',detail=False):
        value=np.array([values[0]-time]);state=NS(time=time,x=np.zeros(1))
        return (value,state,{}) if detail else value
    system=NS(network=net,feedback=None,V=1.,W=1.,requires_unique_time_solution=False,
        forcing=NS(events=np.array([]),breaks=set(),report=lambda:{}),guess=lambda previous,h:np.array([previous.time+h]),residual=residual)
    kwargs=dict(duration=.02,dt=.02,order=1,tolerance=1e-8,max_steps=10,continuation=0)
    if route=='checked':kwargs['accuracy']={'minimum_step':1e-6}
    function=api.integrate if route=='ordinary' else checked.integrate
    if fatal:
        with pytest.raises(api.UnresolvedControllerAuthority) as caught:
            function(system,NS(time=0.,x=np.zeros(1)),None,{},dict(frame='free',loads=[]),**kwargs)
        assert caught.value is exception and isinstance(caught.value,api.StepFailure)
        assert caught.value.accepted_root_witness=={'synthetic_dispatch_only':True}
        assert calls==[.02]
    else:
        result=function(system,NS(time=0.,x=np.zeros(1)),None,{},dict(frame='free',loads=[]),**kwargs)
        assert result['converged'] and result['snapshots'][-1]['time']==.02
        assert result['accepted_steps']==2 and result['rejected_steps']==1
        assert calls[:2]==[.02,.01]
        if route=='checked':assert result['accuracy']['rejected_nonlinear_steps']==1
