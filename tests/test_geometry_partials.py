"""Analytic local geometry against independent physical geometry stencils."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.geometry_tangent import GeometryFields
from openswing.geometry_partials import GeometryPartials,GeometryPartialsUnavailable
from openswing.structured_static import linearization
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for


CASES=[('rectangular',{}),('flexible',{'circulation_modes':{1:3}}),
 ('wing-body',{'ground_effect':1}),('wing-body',{'ground_effect':-1}),
 ('stepped-wing-body',{}),('stepped-wing-body',{'freeze_influences':True}),
 ('torsion-joint',{}),('jet-2',{'powers':{1:50000.}}),('dae',{}),('stepped-body',{})]


def fixture(name,extra,chart,panels=4):
    n=StaticNetwork(model_for(name),panels,FlightCondition(speed=30,alpha=7,beta=3,mach=.2,
        rates=[.03,-.04,.02],position_earth=[0,0,30],attitude=[13,-7,21],**extra),None,[])
    x=state_for(n,.3);n.tangent_influences=TangentInfluences(local_geometry=True)
    with linearization(n,x,.6,capture_circulation=True) as (fields,_):e=GeometryFields(n,fields)
    system=DynamicSystem(n,x,'fixed');zero=np.zeros(system.size)
    if chart=='absolute':state_at=lambda d:x+np.pad(d,(0,n.size-len(d)))
    else:state_at=lambda d:system.unpack(np.pad(d,(0,system.size-len(d))),zero)[0].x
    base=state_at(np.zeros(6*n.nn))
    return n,e,GeometryPartials(e,base,chart=chart),state_at


def leaves(derivative,geometry,path=''):
    if isinstance(derivative,dict):
        for key,value in derivative.items():
            actual=geometry[key] if isinstance(geometry,dict) else getattr(geometry,key)
            yield from leaves(value,actual,path+'.'+str(key))
    elif isinstance(derivative,(tuple,list)):
        for i,value in enumerate(derivative):yield from leaves(value,geometry[i],path+'.'+str(i))
    elif derivative is not None:yield path,np.asarray(derivative),np.asarray(geometry)


@pytest.mark.parametrize('name,extra',CASES)
@pytest.mark.parametrize('chart',['spatial','absolute'])
def test_local_geometry_columns_match_independent_fourth_order_stencils(name,extra,chart):
    n,e,g,state_at=fixture(name,extra,chart)
    # Every local degree of freedom on the small meshes, including endpoint
    # offsets, two-sided properties, body quadrature, point objects and images.
    worst=(0.,'')
    for start in range(0,6*n.nn,16):
        columns=np.arange(start,min(start+16,6*n.nn));actual=g.columns(columns)
        for offset,j in enumerate(columns):
            for step in [1e-5,3e-6]:
                d=np.zeros(6*n.nn);d[j]=step
                samples=[e.prepare(state_at(k*d)) for k in [1,-1,2,-2]]
                arrays=[list(leaves(actual,s)) for s in samples]
                for rows in zip(*arrays):
                    path,derivative,_=rows[0]
                    a,b,c,d=[v[2] for v in rows]
                    expected=(8*(a-b)-(c-d))/(12*step)
                    error=float(np.max(abs(derivative[...,offset]-expected)/(1+abs(expected)))) if expected.size else 0.
                    worst=max(worst,(error,path))
                    assert error<2e-8,(name,chart,j,step,path,error)
    assert n.iteration_fields is None


def test_invalid_chart_direction_and_core_tie_are_explicit():
    n,e,g,_=fixture('rectangular',{},'spatial')
    with pytest.raises(ValueError,match='chart'):GeometryPartials(e,g.state,chart='unknown')
    with pytest.raises(ValueError,match='32'):g.columns(np.arange(33))
    with pytest.raises(ValueError,match='finite'):g.direction(np.full((n.nn,3,1),np.nan),np.zeros((n.nn,3,1)))
    e.condition.wake_core_ratio=float(g.base['p']['ds'][0]/g.base['p']['chord'][0])
    # Set the exact threshold to isolate the non-differentiable maximum branch.
    g.base['p']['ds'][0]=e.condition.wake_core_ratio*g.base['p']['chord'][0]
    with pytest.raises(GeometryPartialsUnavailable,match='tie'):g.columns([0])
