"""Joint/ground reaction supports against full equations and force couples."""
from pathlib import Path
import re
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem,make_system,linearize
from openswing.operating import time_load_constraints
from openswing.structured_static import structural_column_rows
from test_direct_circulation import model_for,state_for


def joint_aircraft(joint_type=0,ground_type=0):
    source=Path('examples/articulated.asw').read_text()
    source=re.sub(r'Jangle\n.*?\nEnd\n','',source,flags=re.S)
    source=source.replace('1 2 2 2 3',f'1 2 2 3 {joint_type}')
    source=source.replace('1 3 -2 -2 3',f'1 3 -2 -3 {joint_type}')
    source=source.replace('Ground\n1 0 0',f'Ground\n1 0 {ground_type}')
    return parse_asw(source)


@pytest.mark.parametrize('joint_type',[0,1,2])
@pytest.mark.parametrize('ground_type',[0,1,2])
@pytest.mark.parametrize('frame',['fixed','free'])
def test_reaction_columns_have_only_the_declared_physical_support(joint_type,ground_type,frame):
    n=StaticNetwork(joint_aircraft(joint_type,ground_type),4,
        FlightCondition(speed=20,alpha=5,beta=2,mach=.1,rates=[.03,-.02,.01]),None,[],
        operating_constraints=time_load_constraints('prescribed' if frame=='fixed' else frame))
    s=DynamicSystem(n,state_for(n,.3),frame);zero=np.zeros(s.size)
    rows=structural_column_rows(n);start=6*(n.nn+n.ne)
    forces=6*n.ne;moments=forces+3*n.nn
    for c in n.constraints:
        i,k,typ=c['a'],c['b'],c['type']
        for local,j in enumerate(range(start+c['sl'].start,start+c['sl'].stop)):
            expected=np.zeros(s.size);axis=local%3;unit=np.eye(3)[axis]
            if typ!=2 and local<3:
                expected[forces+3*i+axis]=1.
                if k is not None:
                    expected[forces+3*k+axis]=-1.
                    expected[moments+3*i:moments+3*i+3]=np.cross((s.r0[k]-s.r0[i])/n.L,unit)
            else:
                expected[moments+3*i+axis]=1.
                if k is not None:expected[moments+3*k+axis]=-1.
            h=1e-5*max(1.,abs(s.base[j]));d=zero.copy();d[j]=h
            p,m,pp,mm=[s.residual(mult*d,zero) for mult in (1,-1,2,-2)]
            actual=(8*(p-m)-(pp-mm))/(12*h)
            outside=np.setdiff1d(np.arange(s.size),rows[j])
            assert not np.any(actual[outside])
            np.testing.assert_allclose(actual,expected,atol=2e-9,rtol=2e-9)


CASES=[('rectangular','fixed',{}),('joint','fixed',{}),
       ('flexible','free',{'circulation_modes':{1:3}}),
       ('wing-body','free',{'ground_effect':1}),
       ('wing-body','fixed',{'freeze_influences':True}),
       ('powered','fixed',{'powers':{1:7}})]


@pytest.mark.parametrize('example,frame,extra',CASES)
def test_complete_operators_equal_individual_reaction_probes(example,frame,extra,monkeypatch):
    import openswing.structured_static as module
    # Explicitly exercise the grouped fallback now that production uses the
    # analytic physical mechanical block.
    import openswing.mechanical_tangent as direct
    def unavailable(*args,**kwargs):raise direct.MechanicalDerivativeUnavailable('grouped fallback oracle')
    monkeypatch.setattr(direct,'mechanical_columns',unavailable)
    model=joint_aircraft() if example=='joint' else model_for(example)
    s,_=make_system(model,FlightCondition(speed=20,alpha=3,mach=.1,
        position_earth=[0.,0.,30.],**extra),4,frame=frame,structured_base=True)
    n=s.network;before=n.nfev
    a,m=linearize(s,sparse=True,_output_fields=True)
    calls=n.nfev-before;g=s._output_field_tangent.matrix.copy()
    grouped=s.state_derivative_diagnostics['mechanical_column_groups']
    assert s.state_derivative_diagnostics['grouped_reaction_columns']==n.nc
    original=module.structural_column_rows
    def individual(net):
        rows=original(net)
        # A full support forces each reaction to have its own group and keeps
        # every original residual row, as in the preceding implementation.
        for j in range(6*(net.nn+net.ne),net.gamma_start):rows[j]=np.arange(s.size)
        return rows
    monkeypatch.setattr(module,'structural_column_rows',individual)
    before=n.nfev;aa,mm=linearize(s,sparse=True,_output_fields=True);gg=s._output_field_tangent.matrix
    assert n.nfev-before-calls==4*(s.state_derivative_diagnostics['mechanical_column_groups']-grouped)
    for actual,expected in [(a,aa),(m,mm),(g,gg)]:
        diff=actual-expected;diff.eliminate_zeros();assert diff.nnz==0


def test_hinge_context_uses_direct_mechanical_columns():
    s,_=make_system(model_for('torsion-joint'),FlightCondition(speed=20,alpha=3,mach=.1),4,structured_base=True)
    assert s.network.hinges
    linearize(s,sparse=True)
    assert s.state_derivative_diagnostics['direct_mechanical_columns']==6*s.network.ne+s.network.nc
    assert s.state_derivative_diagnostics['grouped_reaction_columns']==0
    assert s.state_derivative_diagnostics['mechanical_column_groups']==0


def test_controller_context_retains_individual_reaction_columns():
    from test_feedback import configuration,condition,law
    s,_=make_system(configuration(),condition(),4,gravity=[0,0,0],controller=law(ki=100,ka=3))
    linearize(s,sparse=True)
    assert s.state_derivative_diagnostics['grouped_reaction_columns']==0
    assert s.state_derivative_diagnostics['mechanical_column_groups']==0
