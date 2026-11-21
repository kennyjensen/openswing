"""Exact influence caches must never lag physical frame-variable columns."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.ground import body_to_earth
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.time_integration import TimeState,TimeSystem,bdf_coefficients
from openswing.structured_static import full_fields
import openswing.structured_static as static
import openswing.structured_time as dynamic


def setup(ground=0):
    model=parse_asw(Path('examples/dae.asw').read_text())
    model.reference[1]=[.7,.2,-.4];model.reference[2]=[.3,-.2,.4]
    condition=FlightCondition(speed=30,alpha=5,beta=3,mach=.2,rates=[.03,-.04,.02],
        ground_effect=ground,position_earth=[3,4,200],attitude=[13,-7,21])
    net=StaticNetwork(model,16,condition,None,[],operating_constraints=time_load_constraints('free'))
    rng=np.random.default_rng(486)
    x=rng.normal(0,.0001,net.size);x[net.gamma_start:net.operating_start]+=.04
    r,q,*_,gamma=net.unpack(x)
    previous=TimeState(0.,x,r,q,rng.normal(0,.002,r.shape),rng.normal(0,.001,r.shape),
        -condition.speed*condition.vectors()[0]-np.cross(net.motion.rates,model.reference[3]),
        net.motion.rates.copy(),np.array(condition.position_earth),body_to_earth(condition.attitude),gamma)
    system=TimeSystem(net);coefficients=bdf_coefficients(.017,.013)
    values=system.guess(previous,.017)+rng.normal(0,.00001,system.size)
    function=lambda value:system.residual(value,previous,previous,.017,coefficients)
    return net,x,system,function,values,coefficients[0]


@pytest.mark.parametrize('kind',['static','time'])
@pytest.mark.parametrize('ground',[0,1,-1])
def test_every_frame_column_equals_original_uncached_equations(kind,ground):
    net,x,system,function,values,k0=setup(ground)
    assert net.ng>=64 # Exercise actual stored influence tensors, not the small-array bypass.
    if kind=='static':
        matrix,_=static.jacobian(net,x,.7)
        permutation=np.arange(net.size);split=net.gamma_start
        function=lambda value:net.residual(value,.7)
    else:
        x=values;matrix,permutation,_=dynamic.jacobian(system,function,x,circulation_rate_factor=k0)
        split=matrix.mechanical.shape[0]
    assert net.iteration_fields is None and net.tangent_influences is None
    base=function(x)
    for j,column in enumerate(permutation[split:]):
        if net.gamma_start<=column<net.operating_start:continue
        trial=x.copy();h=1e-6*max(1.,abs(x[column]));trial[column]+=h
        expected=(function(trial)-base)[permutation]/h
        actual=np.r_[matrix.force_circulation[:,j],matrix.circulation[:,j]]
        np.testing.assert_array_equal(actual,expected)


@pytest.mark.parametrize('kind',['static','time'])
def test_full_field_context_keeps_only_exact_cache_and_cleans_up_on_failure(kind):
    net,x,system,function,values,k0=setup()
    context=static.linearization(net,x,.7) if kind=='static' else dynamic.linearization(system,function,values)
    with pytest.raises(RuntimeError,match='deliberate frame-column failure'):
        with context:
            cached=net.tangent_influences
            assert cached.entries # Full-size physical tensors were captured.
            with full_fields(net):
                assert net.iteration_fields is None and net.tangent_influences is cached
                if kind=='static':net.residual(x,.7)
                else:function(values)
                raise RuntimeError('deliberate frame-column failure')
    assert net.iteration_fields is None and net.tangent_influences is None and net.aero_key is None
