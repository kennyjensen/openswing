from field_product_assertions import operators_close
"""Grouped geometry must reproduce full individual stencil fields exactly."""
from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.linear_dynamics import DynamicSystem,linearize,make_system
from openswing.structured_static import IterationFields
from openswing.tangent_influences import TangentInfluences
from openswing.geometry_tangent import GeometryFields,geometry_columns
from openswing.geometry_stencil import GeometryStencil,GeometryStencilUnavailable,same,owned,payload
from test_direct_circulation import model_for,state_for


def context(example='wing-body',extra=None,panels=4,absolute=False):
    n=StaticNetwork(model_for(example),panels,FlightCondition(speed=30,alpha=7,mach=.2,
        position_earth=[0.,0.,30.],**(extra or {})),None,[])
    s=DynamicSystem(n,state_for(n,.3),'fixed');zero=np.zeros(n.size if absolute else s.size)
    scales=np.maximum(1.,abs(s.base)) if absolute else np.r_[np.maximum(1.,abs(s.base)),np.ones(s.size-n.size)]
    state=(lambda d:s.base+d) if absolute else (lambda d:s.unpack(d,zero)[0].x)
    n.tangent_influences=TangentInfluences(local_geometry=True)
    fields=IterationFields();fields.capture_circulation=True;n.iteration_fields=fields;n.aero_key=None
    try:
        if absolute:n.residual(state(zero))
        else:s.residual(zero,zero)
    finally:n.iteration_fields=None;n.aero_key=None
    evaluator=GeometryFields(n,fields,direct_vortex=True,direct_volume=True)
    base=evaluator.prepare(state(zero));evaluator.evaluate(base)
    return n,s,evaluator,base,state,zero,scales


def equal(a,b):
    np.testing.assert_array_equal(a,b)
    assert same(a,b)


CASES=[('rectangular',{}),('flexible',{'circulation_modes':{1:3}}),
    ('wing-body',{'ground_effect':1}),('wing-body',{'ground_effect':-1}),
    ('wing-body',{'freeze_influences':True}),('stepped-body',{}),
    ('stepped-body',{'ground_effect':1}),('stepped-wing-body',{'freeze_influences':True}),
    ('powered',{'powers':{1:7}}),('dae',{}),
    ('jet-0',{'powers':{1:50000.}}),('jet-1',{'powers':{1:50000.}}),
    ('jet-2',{'powers':{1:50000.},'rates':[.03,-.04,.02],
        'gust':dict(type='sinusoid',amplitude=[.2,.1,.4],wavevector=[.21,.3,-.17],omega=.4)})]


@pytest.mark.parametrize('example,extra',CASES)
def test_all_grouped_samples_match_individual_fields(example,extra):
    n,s,e,base,state,zero,scales=context(example,extra)
    before=n.tangent_influences.bytes
    plan=GeometryStencil(e,base,4);reserved=plan.bytes
    assert n.tangent_influences.bytes==before+reserved and n.tangent_influences.bytes<=64*1024**2
    assert sorted(np.concatenate(plan.groups).tolist())==list(range(6*n.nn))
    plan.build(state,zero,scales,1e-5,(1.,-1.,2.,-2.))
    assert e.preparations==1+4*len(plan.groups)
    assert e.evaluations==1  # No nonlocal field was evaluated at a group perturbation.
    for j in range(6*n.nn):
        for phase,multiplier in enumerate((1.,-1.,2.,-2.)):
            d=zero.copy();d[j]=multiplier*1e-5*scales[j]
            actual=e.evaluate(plan.sample(j,phase));expected=e(state(d))
            for key in actual:equal(actual[key],expected[key])
    for field in plan.fields:
        assert field['values'].flags.owndata and not field['values'].flags.writeable
    remaining=n.tangent_influences.bytes-reserved
    plan.close();assert n.tangent_influences.bytes==remaining
    plan.close();assert n.tangent_influences.bytes==remaining


def test_absolute_chart_and_forward_stencil_match_each_sample():
    n,s,e,base,state,zero,scales=context('wing-body',{'ground_effect':-1},absolute=True)
    plan=GeometryStencil(e,base,1);plan.build(state,zero,scales,1e-6,(1.,))
    for j in range(6*n.nn):
        d=zero.copy();d[j]=1e-6*scales[j]
        actual=e.evaluate(plan.sample(j,0));expected=e(state(d))
        for key in actual:equal(actual[key],expected[key])
    plan.close()


def test_budget_layout_and_declared_dependency_guards():
    n,s,e,base,state,zero,scales=context()
    def rejected(fn):
        try:fn()
        except GeometryStencilUnavailable:return
        raise AssertionError('An invalid geometry stencil context was accepted')
    before=n.tangent_influences.bytes
    n.tangent_influences.bytes=64*1024**2
    rejected(lambda:GeometryStencil(e,base,4));assert n.tangent_influences.bytes==64*1024**2
    n.tangent_influences.bytes=before
    plan=GeometryStencil(e,base,4)
    rejected(lambda:plan.sample(0,0))
    current=e.prepare(state(zero));current['p']['physical']=current['p']['physical'].copy();current['p']['physical'][0]+=1
    rejected(lambda:plan.capture(current,np.array([0])))
    current=e.prepare(state(zero));current['q']=current['q'][:-1]
    rejected(lambda:plan.capture(current,np.array([0])))
    # A hidden dependency outside the declared node support must abort grouping.
    current=e.prepare(state(zero));current['r'][-1,0]+=.01
    rejected(lambda:plan.capture(current,np.array([0])))
    current=e.prepare(state(zero));current['volume'].pg=current['volume'].pg.copy();current['volume'].pg[0,0]+=.1
    rejected(lambda:plan.capture(current,np.array([0])))
    plan.close();assert n.tangent_influences.bytes>=before
    rejected(lambda:plan.build(state,zero,scales,1e-5,(1.,-1.,2.,-2.)))


@pytest.mark.parametrize('example,extra',[('flexible',{'circulation_modes':{1:3}}),
    ('wing-body',{'ground_effect':1}),('wing-body',{'ground_effect':-1}),
    ('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})])
def test_complete_pencil_and_output_fields_equal_individual_geometry(example,extra,monkeypatch):
    import openswing.geometry_stencil as module
    import openswing.geometry_field_partials as direct
    from openswing.geometry_partials import GeometryPartialsUnavailable
    # Exercise the grouped-stencil fallback deliberately. Eligible production
    # cases now use direct geometry derivatives before considering this path.
    def no_direct_geometry(*args,**kwargs):
        raise GeometryPartialsUnavailable('Exercise grouped versus individual geometry stencils')
    monkeypatch.setattr(direct,'GeometryFieldPartials',no_direct_geometry)
    system,_=make_system(model_for(example),FlightCondition(speed=20,alpha=3,mach=.1,
        position_earth=[0.,0.,30.],**extra),4,structured_base=True)
    a,m=linearize(system,sparse=True,_output_fields=True)
    g=system._output_field_tangent.matrix.copy()
    diagnostics=system.state_derivative_diagnostics['geometry_assembly']
    assert diagnostics['geometry_groups']>0 and diagnostics['geometry_stencil_fallback'] is None
    assert diagnostics['geometry_preparations']<diagnostics['field_evaluations']
    def unavailable(*args,**kwargs):raise GeometryStencilUnavailable('Grouped geometry storage unavailable')
    monkeypatch.setattr(module,'GeometryStencil',unavailable)
    expected,mass=linearize(system,sparse=True,_output_fields=True)
    assert system.state_derivative_diagnostics['geometry_assembly']['geometry_groups']==0
    for name,actual,reference in [('A',a,expected),('M',m,mass),('G',g,system._output_field_tangent.matrix)]:
        operators_close(actual,reference,6*system.network.nn,mass=name=='M')


def test_nonzero_local_motion_and_signed_zero_keep_individual_fields():
    n,s,e,base,state,zero,scales=context('wing-body',{'ground_effect':1})
    rng=np.random.default_rng(7743)
    for motion in [tuple(rng.normal(size=(n.nn,3))*.03 for _ in range(4)),
                   tuple(np.full((n.nn,3),-0.) for _ in range(4))]:
        e.local_values=motion
        plan=GeometryStencil(e,base,4);plan.build(state,zero,scales,1e-5,(1.,-1.,2.,-2.))
        for j in range(6*n.nn):
            d=zero.copy();d[j]=1e-5*scales[j]
            actual=e.evaluate(plan.sample(j,0));expected=e(state(d))
            for key in actual:equal(actual[key],expected[key])
        plan.close()


def test_failed_group_preparation_releases_reserved_budget_and_context(monkeypatch):
    from openswing.geometry_tangent import GeometryDerivativeUnavailable
    n,s,e,base,state,zero,scales=context()
    closed=[];original=GeometryStencil.close
    def fail(self,*args,**kwargs):raise GeometryStencilUnavailable('Deliberate grouped preparation failure')
    def close(self):
        before=self.cache.bytes;original(self)
        closed.append((before-self.cache.bytes,self.bytes,self.active))
    monkeypatch.setattr(GeometryStencil,'build',fail)
    monkeypatch.setattr(GeometryStencil,'close',close)
    try:
        geometry_columns(n,lambda d:s.residual(d,zero),state,scales,
            _direct_vortex=True,_direct_volume=True,_nodewise_state=True)
    except GeometryDerivativeUnavailable as error:assert 'Deliberate grouped preparation failure' in str(error)
    else:raise AssertionError('Failed grouped geometry preparation did not propagate')
    assert len(closed)==1 and closed[0][0]==closed[0][1] and closed[0][2] is False
    assert n.iteration_fields is None and n.aero_key is None
