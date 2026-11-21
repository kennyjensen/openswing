"""Grouped rate columns against independent columns and complete residuals."""
from copy import deepcopy
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem
from openswing.operating import time_load_constraints
from openswing.descriptor_mass import mass_matrix
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for

CASES=[
    ('rectangular','fixed',{}),
    ('flexible','free',{'circulation_modes':{1:3}}),
    ('wing-body','free',{'ground_effect':1}),
    ('wing-body','fixed',{'ground_effect':-1}),
    ('stepped-wing-body','free',{'freeze_influences':True}),
    ('torsion-joint','free',{}),
    ('rectangular','free',{'aero_lag':False}),
    ('jet-0','free',{'powers':{1:50000.}}),
    ('jet-1','free',{'powers':{1:50000.}}),
    ('jet-2','free',{'powers':{1:50000.}}),
    ('stepped-body','free',{}),
    ('dae','fixed',{}),
    ('dae','free',{'circulation_modes':{1:3}}),
]


@pytest.mark.parametrize('example,frame,extra',CASES)
def test_grouped_rate_columns_preserve_complete_matrix_and_physical_action(example,frame,extra):
    model=model_for(example)
    model.reference[1]=[.7,-.2,.3];model.reference[2]=[.1,.2,-.1]
    c=FlightCondition(speed=30,alpha=7,beta=3,mach=.2,rates=[.03,-.04,.02],
        position_earth=[0,0,30],attitude=[13,-7,21],**extra)
    n=StaticNetwork(model,4,c,None,[],operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    s=DynamicSystem(n,state_for(n,.3),frame);zero=np.zeros(s.size)
    _,state,options=s.residual(zero,zero,detail=True)
    _,data=n.residual(state.x,detail=True,**options)
    # Dense extraction independently probes every physical rate coordinate.
    expected=mass_matrix(s,state,data,1e-5)
    reference_diagnostics=deepcopy(s.derivative_diagnostics)
    n.tangent_influences=TangentInfluences(local_geometry=True);n.aero_key=None
    try:actual=mass_matrix(s,state,data,1e-5,sparse=True)
    finally:n.tangent_influences=None;n.aero_key=None
    np.testing.assert_allclose(actual.toarray(),expected,atol=2e-12,rtol=2e-12)
    if n.ng:
        assert s.derivative_diagnostics['grouped_circulation_rate_columns']==n.ng
        assert s.derivative_diagnostics['circulation_rate_groups']<=n.ng
        if not n.circulation_basis.modes:
            assert s.derivative_diagnostics['circulation_rate_groups']<n.ng
        assert s.derivative_diagnostics['load_evaluations']<reference_diagnostics['load_evaluations']
    # The odd part removes the quadratic rate-drag term without dropping it
    # from the actual nonlinear residual. Nonlinear Jangle rows use their
    # independently checked local chain rule, so exclude them here.
    rows=np.ones(s.size,dtype=bool)
    if n.hinges:rows[6*(n.nn+n.ne):n.gamma_start]=False
    d=zero.copy();d[s.dynamic_indices]=np.random.default_rng(317).normal(size=len(s.dynamic_indices))*s.W
    for scale in [.13,.7]:
        physical=(s.residual(zero,scale*d)-s.residual(zero,-scale*d))/(2*scale)
        np.testing.assert_allclose(physical[rows],(-actual@d)[rows],atol=2e-12,rtol=2e-12)


def test_grouped_rates_do_not_discard_quadratic_shed_vorticity_drag():
    n=StaticNetwork(model_for('flexible'),8,FlightCondition(speed=30,alpha=5,mach=.1),None,[])
    s=DynamicSystem(n,state_for(n,.3),'fixed');zero=np.zeros(s.size)
    _,state,options=s.residual(zero,zero,detail=True);_,data=n.residual(state.x,detail=True,**options)
    mass=mass_matrix(s,state,data,1e-5,sparse=True)
    rate=zero.copy();rate[n.gamma_start:n.operating_start]=np.linspace(-.7,1.3,n.ng)*s.W
    p,m,b=s.residual(zero,rate),s.residual(zero,-rate),s.residual(zero,zero)
    assert np.max(abs(p+m-2*b))>1e-5
    np.testing.assert_allclose((p-m)/2,-mass@rate,atol=2e-12,rtol=2e-12)
