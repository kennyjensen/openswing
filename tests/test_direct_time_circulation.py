"""BDF circulation/rate derivatives against the original complete equations."""
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.time_integration import TimeState,TimeSystem,bdf_coefficients
from openswing.ground import body_to_earth
from openswing.hinge_history import at_network
from openswing.structured_time import jacobian
from test_direct_circulation import model_for


CASES=[
 ('rectangular',{},'prescribed',.08),
 ('transient-wing',{},'free',.08),
 ('flexible',{'circulation_modes':{1:3}},'mixed',.3),
 ('wing-body',{'ground_effect':1,'position_earth':[0,0,30],'attitude':[13,-7,21]},'free',.08),
 ('stepped-wing-body',{'freeze_influences':True},'free',.08),
 ('torsion-joint',{},'mixed',.3),
 ('rectangular',{},'free',1.2),
 ('rectangular',{'aero_lag':False},'free',.3),
 ('jet-0',{'powers':{1:50000.}},'mixed',.3),
 ('jet-1',{'powers':{1:50000.}},'free',.3),
 ('jet-2',{'powers':{1:50000.}},'free',.3),
]


def setup(example,extra,frame,circulation,previous_step):
    model=model_for(example)
    model.reference[1]=[.7,.2,-.4];model.reference[2]=[.3,-.2,.4]
    condition=FlightCondition(speed=30,mach=.2,alpha=7,beta=3,rates=[.03,-.04,.02],**extra)
    targets={'force.x':.1,'moment.y':.2} if frame=='mixed' else None
    net=StaticNetwork(model,4,condition,None,[],operating_constraints=time_load_constraints(frame,targets))
    system=TimeSystem(net)
    rng=np.random.default_rng(741)
    initial=rng.normal(0,.0002,net.size);initial[net.gamma_start:net.operating_start]+=circulation
    r,q,*_,gamma=net.unpack(initial)
    # This generated initial state owns its hinge branch. Preserve the actual
    # small-rotation chart when constructing the previous time state directly.
    previous=TimeState(0.,initial,r,q,rng.normal(0,.02,r.shape),rng.normal(0,.01,r.shape),
        -condition.speed*condition.vectors()[0]-np.cross(net.motion.rates,model.reference[3]),
        net.motion.rates.copy(),np.array(condition.position_earth),body_to_earth(condition.attitude),gamma,
        hinge_charts=at_network(net,q))
    coefficients=bdf_coefficients(.017,previous_step)
    values=system.guess(previous,.017)+rng.normal(0,.0001,system.size)
    function=lambda x:system.residual(x,previous,None if previous_step is None else previous,.017,coefficients)
    return system,function,values,coefficients[0]


@pytest.mark.parametrize('example,extra,frame,circulation',CASES)
@pytest.mark.parametrize('previous_step',[None,.013])
def test_direct_bdf_columns_match_refined_full_physical_differences(example,extra,frame,circulation,previous_step):
    system,function,x,k0=setup(example,extra,frame,circulation,previous_step)
    before=function(x).copy();net=system.network;events=[]
    direct,p,counts=jacobian(system,function,x,circulation_rate_factor=k0,progress=lambda *args:events.append(args))
    numerical,np_,old=jacobian(system,function,x)
    assert counts['circulation_derivative']=='direct BDF circulation blocks',counts
    assert old['evaluations']-counts['evaluations']==net.ng
    assert events[-1][1]==events[-1][2]==counts['groups']+1+net.operating.count+12
    np.testing.assert_array_equal(p,np_)
    np.testing.assert_array_equal(direct.mechanical.toarray(),numerical.mechanical.toarray())
    np.testing.assert_array_equal(direct.flow_geometry.toarray(),numerical.flow_geometry.toarray())
    actual=np.r_[direct.force_circulation,direct.circulation]
    full_old=np.r_[numerical.force_circulation,numerical.circulation]
    np.testing.assert_array_equal(actual[:,net.ng:],full_old[:,net.ng:])
    for step in [1e-5,3e-6]:
        for j,column in enumerate(range(net.gamma_start,net.operating_start)):
            h=step*max(1.,abs(x[column]));plus=x.copy();minus=x.copy()
            plus[column]+=h;minus[column]-=h
            expected=(function(plus)-function(minus))[p]/(2*h)
            error=np.max(abs(actual[:,j]-expected)/(1+abs(expected)))
            assert error<2e-7,(example,previous_step,j,step,error)
    np.testing.assert_array_equal(function(x),before)
    assert net.iteration_fields is None and net.tangent_influences is None


@pytest.mark.parametrize('example,extra,frame,circulation',CASES)
def test_load_only_time_residual_is_identical_to_detailed_equations(example,extra,frame,circulation):
    system,function,x,k0=setup(example,extra,frame,circulation,.013)
    # Force every residual through the existing detailed path, including all
    # original wake/mass/sensor work, without changing any equation or state.
    net=system.network;original=net.residual
    lean=function(x).copy()
    def complete(*args,**kwargs):
        assert not kwargs.get('detail',False)
        return original(*args,**kwargs,detail=True)[0]
    net.residual=complete
    detailed=function(x)
    np.testing.assert_array_equal(lean,detailed)


def test_unavailable_direct_time_derivatives_keep_original_columns(monkeypatch):
    import openswing.circulation_tangent as derivative
    system,function,x,k0=setup('wing-body',{},'free',.08,.013)
    original,p,_=jacobian(system,function,x)
    def unavailable(*args,**kwargs):raise derivative.CirculationDerivativeUnavailable('deliberate unavailable branch')
    monkeypatch.setattr(derivative,'circulation_columns',unavailable)
    actual,ap,counts=jacobian(system,function,x,circulation_rate_factor=k0)
    assert counts['circulation_derivative']=='forward differences'
    assert counts['circulation_derivative_fallback']=='deliberate unavailable branch'
    np.testing.assert_array_equal(ap,p)
    np.testing.assert_array_equal(actual.toarray(),original.toarray())
    assert system.network.iteration_fields is None and system.network.tangent_influences is None
