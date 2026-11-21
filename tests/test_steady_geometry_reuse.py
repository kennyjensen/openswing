"""Exact tangent equivalence and invalidation of geometry-only work."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.local_motion import NetworkMotion
from openswing.tangent_influences import TangentInfluences
from openswing.structured_static import IterationFields, jacobian


@pytest.mark.parametrize('example,extra',[
    ('rectangular',{}),('flexible',{}),('wing-body',{}),('stepped-body',{}),
    ('powered',{'powers':{1:50.}}),('articulated',{}),('dae',{}),
    ('flexible',{'circulation_modes':{1:3}}),('wing-body',{'freeze_influences':True})])
def test_structured_tangent_is_exact_with_geometry_recomputation(example,extra,monkeypatch):
    model=parse_asw(Path(f'examples/{example}.asw').read_text())
    def network():return StaticNetwork(model,4,FlightCondition(mach=.2,beta=2,rates=[.01,-.02,.03],ground_effect=1,position_earth=[0,0,30],**extra),None,[])
    net,reference=network(),network()
    x=np.random.default_rng(731).normal(0,.0001,net.size)
    x[net.gamma_start:net.operating_start]+=.04
    actual,_=jacobian(net,x,.6)
    monkeypatch.setattr(TangentInfluences,'steady_geometry',lambda self,network,r,q,compute:compute())
    monkeypatch.setattr(IterationFields,'fixed_geometry',lambda self,key,compute:compute())
    monkeypatch.setattr(NetworkMotion,'remember',lambda self,slot,key,value:value)
    expected,_=jacobian(reference,x,.6)
    np.testing.assert_array_equal(actual.toarray(),expected.toarray())
    np.testing.assert_array_equal(net.residual(x,.6),reference.residual(x,.6))


@pytest.mark.parametrize('scope',['steady','trim','dynamic'])
def test_full_physical_tangent_is_exact_with_geometry_recomputation(scope,monkeypatch):
    model=parse_asw(Path('examples/wing-body.asw').read_text())
    settings=dict(operating_constraints=[dict(variable='alpha',quantity='CL',target=.4)]) if scope=='trim' else {}
    def network():return StaticNetwork(model,4,FlightCondition(mach=.2),None,[],**settings)
    net,reference=network(),network()
    rng=np.random.default_rng(347);x=rng.normal(0,.0001,net.size)
    x[net.gamma_start:net.operating_start]+=.04
    options=dict(elastic_motion=tuple(rng.normal(0,.01,(4,net.nn,3)))) if scope=='dynamic' else {}
    actual=net.jacobian(x,.6,**options)
    monkeypatch.setattr(TangentInfluences,'steady_geometry',lambda self,network,r,q,compute:compute())
    monkeypatch.setattr(NetworkMotion,'remember',lambda self,slot,key,value:value)
    np.testing.assert_array_equal(actual,reference.jacobian(x,.6,**options))


def test_steady_geometry_invalidates_actual_state_and_obeys_its_budget():
    net=StaticNetwork(parse_asw(Path('examples/flexible.asw').read_text()),4,FlightCondition(),None,[])
    r,q,*_=net.unpack(np.zeros(net.size));cache=TangentInfluences();calls=[]
    def compute():calls.append(True);return net.steady_geometry(r,q)
    first=cache.steady_geometry(net,r,q,compute)
    assert cache.steady_geometry(net,r.copy(),q.copy(),compute) is first
    r[0,0]+=.01
    second=cache.steady_geometry(net,r,q,compute)
    assert second is not first and len(calls)==2
    cache.static_limit=0
    third=cache.steady_geometry(net,r,q,compute)
    assert third is not second and cache.static_state is None and cache.static_bytes==0


def test_fixed_setup_reuses_only_base_circulation_geometry():
    fields=IterationFields();calls=[]
    def compute():calls.append(True);return np.array([len(calls)],dtype=float)
    base=fields.fixed_geometry('probe',compute)
    fields.phase='geometry'
    trial=fields.fixed_geometry('probe',compute)
    assert trial[0]==2
    fields.phase='circulation'
    np.testing.assert_array_equal(fields.fixed_geometry('probe',compute),base)
    assert len(calls)==2
    empty=IterationFields();empty.fixed_limit=0
    empty.fixed_geometry('probe',compute);empty.phase='circulation'
    empty.fixed_geometry('probe',compute)
    assert empty.fixed_values=={} and empty.fixed_bytes==0 and len(calls)==4
