"""Stable aerodynamic moment derivatives retain every original load source."""
from decimal import Decimal,localcontext
from copy import deepcopy
import numpy as np
import pytest
from openswing.output_derivatives import moment_difference,aerodynamic_moments
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from test_direct_circulation import model_for,state_for


def exact_moment(rows,reference):
    dec=lambda values:list(map(lambda x:Decimal.from_float(float(x)),values))
    total=[Decimal(0)]*3
    for row in rows:
        p,f,m=map(dec,[row['position'],row['force'],row.get('moment',[0.,0.,0.])])
        arm=[a-b for a,b in zip(p,dec(reference))]
        for i,j,k in [(0,1,2),(1,2,0),(2,0,1)]:total[i]+=m[i]+arm[j]*f[k]-arm[k]*f[j]
    return total


def test_large_opposing_moments_against_decimal_reference():
    reference=[.25,-.125,.5]
    rows=[dict(position=[2**25,2**25,0.],force=[2**26,2**26,2**26],moment=[1.,2.,3.]),
          dict(position=[-2**25,-2**25,0.],force=[2**26,2**26,2**26],moment=[-1.,-2.,-3.]),
          dict(position=[.25,-.125,.5],force=[0.,0.,0.],moment=[2**-20,-2**-19,2**-18])]
    plus,minus=deepcopy(rows),deepcopy(rows)
    plus[0]['position'][0]+=2**-10;minus[0]['position'][0]-=2**-10
    plus[1]['force'][2]+=2**-12;minus[1]['force'][2]-=2**-12
    plus[2]['moment'][1]+=2**-25;minus[2]['moment'][1]-=2**-25
    with localcontext() as ctx:
        ctx.prec=90
        a,b=exact_moment(plus,reference),exact_moment(minus,reference)
        expected=np.array([float(x-y) for x,y in zip(a,b)])
    actual=moment_difference(plus,minus,reference)
    np.testing.assert_allclose(actual,expected,rtol=2e-15,atol=1e-20)
    np.testing.assert_array_equal(moment_difference(plus[::-1],minus[::-1],reference),actual)


@pytest.mark.parametrize('example,extra',[
    ('wing-body',{'ground_effect':1}),('stepped-wing-body',{}),
    ('jet-2',{'powers':{1:50000.}}),('articulated',{})])
def test_complete_source_sum_matches_original_physical_moments(example,extra):
    n=StaticNetwork(model_for(example),4,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
        rates=[.03,-.04,.02],position_earth=[0,0,30],attitude=[13,-7,21],**extra),None,[])
    s=DynamicSystem(n,state_for(n,.08),'free');rng=np.random.default_rng(638)
    vector=rng.normal(size=s.size)+1j*rng.normal(size=s.size)
    step=1e-5;snapshots=[];points=[]
    for component in [vector.real,vector.imag]:
        for sign in [1,-1]:
            z=sign*step*component;state,snapshot=s.snapshot(z,.7*z)
            snapshots.append(snapshot);points.append(n.point_positions(state.r,state.Q))
    actual=aerodynamic_moments(snapshots,points,n.model.reference[1],step)
    assert set(actual)=={'moment','distributed_aero_moment','apparent_moment','engine_moment'}
    for key,value in actual.items():
        a,b,c,d=[np.array(snapshot[key]) for snapshot in snapshots]
        expected=((a-b)+1j*(c-d))/(2*step)
        assert np.max(abs(value-expected)/(1+abs(expected)))<2e-8,(example,key,value,expected)


def test_vacuum_and_empty_sources_keep_original_availability():
    assert aerodynamic_moments([{}]*4,[[]]*4,np.zeros(3),1e-5)=={}
    np.testing.assert_array_equal(moment_difference([],[],np.zeros(3)),np.zeros(3))
