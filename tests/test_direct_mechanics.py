"""Direct complete mechanical columns against original physical residuals."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem,linearize,make_system
from openswing.operating import time_load_constraints
from openswing.mechanical_tangent import mechanical_columns,MechanicalDerivativeUnavailable
from test_direct_circulation import model_for,state_for
from test_mechanical_groups import joint_aircraft


def capture(s):
    zero=np.zeros(s.size);state,_,options=s.physical_state(zero,zero)
    _,data=s.network.residual(state.x,detail=True,**options)
    scales=np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-s.network.size)]
    return data,scales


CASES=[('rectangular','fixed',{}),('flexible','free',{'circulation_modes':{1:3}}),
       ('wing-body','free',{'ground_effect':1}),('wing-body','fixed',{'freeze_influences':True}),
       ('powered','fixed',{'powers':{1:7}}),('torsion-joint','fixed',{}),
       ('torsion-joint','free',{'aero_lag':False})]


@pytest.mark.parametrize('example,frame,extra',CASES)
def test_all_internal_and_reaction_columns_match_full_physical_derivatives(example,frame,extra):
    n=StaticNetwork(model_for(example),4,FlightCondition(speed=20,alpha=5,beta=2,mach=.1,
        position_earth=[0,0,30],rates=[.03,-.02,.01],**extra),None,[],
        operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    x=state_for(n,.3)
    x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
    s=DynamicSystem(n,x,frame);data,scales=capture(s)
    before=n.nfev;actual,report=mechanical_columns(s,data,scales,1e-5)
    assert n.nfev==before
    assert report['columns']==6*n.ne+n.nc
    assert report['hinge_constraints']==len(n.hinges)
    zero=np.zeros(s.size)
    for step in (1e-5,3e-6):
        for k,j in enumerate(range(6*n.nn,n.gamma_start)):
            h=step*scales[j];d=zero.copy();d[j]=h
            p,m,pp,mm=[s.residual(f*d,zero) for f in (1,-1,2,-2)]
            expected=(8*(p-m)-(pp-mm))/(12*h)
            error=np.max(abs(actual[:,k].toarray().ravel()-expected)/(1+abs(expected)))
            assert error<2e-8,(example,frame,step,j,error)


@pytest.mark.parametrize('joint_type',[0,1,2])
@pytest.mark.parametrize('ground_type',[0,1,2])
def test_all_ground_joint_blocks_match_independent_force_couples(joint_type,ground_type):
    n=StaticNetwork(joint_aircraft(joint_type,ground_type),4,FlightCondition(speed=20,mach=.1),None,[])
    s=DynamicSystem(n,state_for(n,.3),'fixed');data,scales=capture(s)
    actual,_=mechanical_columns(s,data,scales,1e-5)
    for c in n.constraints:
        i,k,typ=c['a'],c['b'],c['type']
        for local,column in enumerate(range(6*n.ne+c['sl'].start,6*n.ne+c['sl'].stop)):
            expected=np.zeros(s.size);axis=local%3;unit=np.eye(3)[axis]
            if typ!=2 and local<3:
                expected[6*n.ne+3*i+axis]=1.
                if k is not None:
                    expected[6*n.ne+3*k+axis]=-1.
                    expected[6*n.ne+3*n.nn+3*i:6*n.ne+3*n.nn+3*i+3]=np.cross((s.r0[k]-s.r0[i])/n.L,unit)
            else:
                expected[6*n.ne+3*n.nn+3*i+axis]=1.
                if k is not None:expected[6*n.ne+3*n.nn+3*k+axis]=-1.
            np.testing.assert_array_equal(actual[:,column].toarray().ravel(),expected)


def test_direct_storage_limit_keeps_existing_physical_fallback(monkeypatch):
    s,_=make_system(model_for('flexible'),FlightCondition(speed=20,alpha=3,mach=.1),4,structured_base=True)
    data,scales=capture(s)
    with pytest.raises(MechanicalDerivativeUnavailable,match='budget'):
        mechanical_columns(s,data,scales,1e-5,limit=1)
    before=s.network.nfev;a,m=linearize(s,sparse=True,_output_fields=True)
    calls=s.network.nfev-before;g=s._output_field_tangent.matrix.copy()
    import openswing.mechanical_tangent as module
    def unavailable(*args,**kwargs):raise MechanicalDerivativeUnavailable('deliberate direct block limit')
    monkeypatch.setattr(module,'mechanical_columns',unavailable)
    before=s.network.nfev;reference,rm=linearize(s,sparse=True,_output_fields=True)
    assert s.network.nfev-before-calls==4*s.state_derivative_diagnostics['mechanical_column_groups']
    assert 'deliberate' in s.state_derivative_diagnostics['mechanical_fallback']
    np.testing.assert_allclose(a.toarray(),reference.toarray(),atol=2e-9,rtol=2e-9)
    for actual,expected in [(m,rm),(g,s._output_field_tangent.matrix)]:
        delta=actual-expected;delta.eliminate_zeros();assert delta.nnz==0


@pytest.mark.parametrize('stationary',[False,True])
@pytest.mark.parametrize('example',['flexible','torsion-joint'])
def test_dense_dynamic_and_stationary_operators_keep_physical_partials(example,stationary,monkeypatch):
    s,_=make_system(model_for(example),FlightCondition(speed=20,alpha=3,mach=.1),4,structured_base=True)
    n=s.network
    before=n.nfev;result=linearize(s,_stationary=stationary)
    a,m=(result,None) if stationary else result
    calls=n.nfev-before
    assert s.state_derivative_diagnostics['direct_mechanical_columns']==6*n.ne+n.nc
    import openswing.mechanical_tangent as module
    def unavailable(*args,**kwargs):raise MechanicalDerivativeUnavailable('independent complete residual oracle')
    monkeypatch.setattr(module,'mechanical_columns',unavailable)
    before=n.nfev;result=linearize(s,_stationary=stationary)
    reference,rm=(result,None) if stationary else result
    assert n.nfev-before-calls==(8 if n.hinges else 4)*(6*n.ne+n.nc)
    np.testing.assert_allclose(a,reference,atol=2e-8,rtol=2e-8)
    np.testing.assert_array_equal(a[:,:6*n.nn],reference[:,:6*n.nn])
    np.testing.assert_array_equal(a[:,n.gamma_start:],reference[:,n.gamma_start:])
    if not stationary:np.testing.assert_array_equal(m,rm)


@pytest.mark.parametrize('stiffness_scale',[1.,1e18])
def test_axis_jumps_coupled_compliance_and_weak_entries_match_80_digit_physics(stiffness_scale):
    from test_network import model
    from precision_reference import affine_reference,compare
    stiffness=' '.join(str(stiffness_scale*v) for v in (20,30,10,100,200,300,2,3,1))
    beam=f'''Beam 1
Offset coupled section
t y z
0 0 0
1 1 0
1 1 1
2 2 1
t EIcc EInn GJ EA GKc GKn EIcs EIcn EIsn Cea Nea Cta Nta
0 {stiffness} .1 .2 .3 .4
2 {stiffness} .1 .2 .3 .4
End
'''
    n=StaticNetwork(model(beam),4,None,[0,0,0],[])
    assert np.any(n.offa) or np.any(n.offb)
    x=state_for(n);x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
    s=DynamicSystem(n,x,'fixed');data,scales=capture(s)
    actual,_=mechanical_columns(s,data,scales,1e-5)
    reference,bound=affine_reference(s,data,'1e-20')
    finer,_=affine_reference(s,data,'1e-24')
    for result in (compare(actual,reference,bound),compare(reference,finer,bound)):
        assert result['max_normalized_error']<2e-13
        assert result['max_contribution_scaled_error']<2e-13
    if stiffness_scale>1:
        assert 0<np.max(abs(actual[:6*n.ne,:6*n.ne].data))<1e-17


@pytest.mark.parametrize('reverse',[False,True])
def test_nonlinear_hinge_chain_includes_both_moment_traces_and_offset_axes(reverse):
    from test_joints import linked
    model=linked(curve='-100 -60\n0 0\n100 120',axis='1 2 3',reverse=reverse,offset=True)
    n=StaticNetwork(model,4,None,[0,0,0],[])
    x=state_for(n);x[:6*n.nn].reshape(-1,6)[:,3:]+=[.5,-.2,.3]
    s=DynamicSystem(n,x,'fixed');data,scales=capture(s)
    actual,_=mechanical_columns(s,data,scales,1e-5);zero=np.zeros(s.size)
    hinge=next(c for c in n.constraints if c['type']==3)
    assert hinge['end'] is not reverse
    for j in range(6*n.nn+6*hinge['element'],6*n.nn+6*hinge['element']+6):
        for step in (1e-5,3e-6):
            h=step*scales[j];d=zero.copy();d[j]=h
            p,m,pp,mm=[s.residual(f*d,zero) for f in (1,-1,2,-2)]
            reference=(8*(p-m)-(pp-mm))/(12*h)
            assert np.max(abs(actual[:,j-6*n.nn].toarray().ravel()-reference)/(1+abs(reference)))<2e-8


def test_hinge_slope_break_keeps_original_probes():
    from test_joints import linked
    model=linked(curve='-100 -100\n0 0\n0 0\n100 200')
    n=StaticNetwork(model,4,None,[0,0,0],[]);x=np.zeros(n.size)
    s=DynamicSystem(n,x,'fixed');data,scales=capture(s)
    with pytest.raises(MechanicalDerivativeUnavailable,match='slope break'):
        mechanical_columns(s,data,scales,1e-5)


def test_near_pi_dynamic_base_rejects_hinge_chart_boundary():
    from openswing.aero import AnalysisError
    from test_joints import linked
    n=StaticNetwork(linked(),4,None,[0,0,0],[]);x=np.zeros(n.size)
    x[:6*n.nn].reshape(-1,6)[n.beam_nodes[2],3]=np.pi-1e-8
    charts=[c.get('angle_chart') for c in n.constraints if c['type']==3]
    # Dynamic base construction checks the owned chart before derivative blocks.
    with pytest.raises(AnalysisError,match='Hinge history approaches its local chart boundary'):
        DynamicSystem(n,x,'fixed')
    assert [c.get('angle_chart') for c in n.constraints if c['type']==3]==charts


def test_static_mechanical_block_retains_its_logarithm_branch_guard():
    from openswing.mechanical_tangent import network_mechanical_columns
    from test_joints import linked
    n=StaticNetwork(linked(),4,None,[0,0,0],[]);x=np.zeros(n.size)
    x[:6*n.nn].reshape(-1,6)[n.beam_nodes[2],3]=np.pi-1e-8
    # The raw static block remains separately guarded. Do not bypass the
    # DynamicSystem chart check to manufacture an admissible dynamic base.
    _,data=n.residual(x,detail=True)
    assert data['hinge_charts']=={1:0.}
    before=n.nfev
    with pytest.raises(MechanicalDerivativeUnavailable,match='logarithm branch'):
        network_mechanical_columns(n,data,np.maximum(1.,abs(x)),1e-5)
    assert n.nfev==before
