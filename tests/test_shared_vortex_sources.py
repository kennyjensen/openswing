from field_product_assertions import operators_close
"""Exact shared vortex-source motion with receiver-specific physical core masks."""
import numpy as np
import pytest
from openswing.vortex_tangent import VortexSourceTangent, VortexFieldTangent, VortexDerivativeUnavailable
from openswing.ground import GroundPlane


def equal(actual, expected):
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes()


def fixture(flag, kind):
    rng=np.random.default_rng(8187)
    points=rng.normal(size=(7,3))+[0.,0.,4.]
    a=rng.normal(size=(5,3));b=a+[.2,1.1,-.1]
    wind=np.array([1.,.2,-.1]);pg=np.diag([1.3,1.,1.])
    gamma=rng.normal(size=5);core=np.array([.17,0.,.23,.04,.19]);owners=np.array([1,2,1,3,2])
    physical={'none':None,'mixed':np.array([1,2,1,3,2,1,3]),'one':np.full(7,1),
              'all':np.full(7,4),'empty':np.empty(0,dtype=int),'single':np.array([2])}[kind]
    if kind=='empty':points=points[:0]
    if kind=='single':points=points[:1]
    bound=np.zeros((len(points),len(a)),dtype=bool)
    if len(points):bound[0,2]=True
    ground=GroundPlane(flag,[0.,0.,10.],[3.,-2.,1.])
    return points,a,b,wind,pg,core,gamma,owners,physical,bound,ground


def query_core(core,owners,physical):
    return core[None,:] if physical is None else np.where(physical[:,None]==owners[None,:],0.,core[None,:])


@pytest.mark.parametrize('flag',[-1,0,1])
@pytest.mark.parametrize('kind',['none','mixed','one','all','empty','single'])
def test_shared_vortex_changes_equal_separate_evaluation(flag,kind):
    points,a,b,wind,pg,core,gamma,owners,physical,bound,ground=fixture(flag,kind)
    source=VortexSourceTangent(a,b,core,owners)
    options=dict(exclude_bound=bound,single_dot=kind=='single')
    args=(points,a,b,wind,pg,query_core(core,owners,physical),gamma,ground)
    shared=VortexFieldTangent(*args,**options,_source=source,_physical=physical)
    separate=VortexFieldTangent(*args,**options)
    rng=np.random.default_rng(94617)
    for change in ['base','receivers','a','b','core','inactive-core','all','signed-zero','base']:
        p,av,bv,cv=[v.copy() for v in (points,a,b,core)]
        for name,value in [('receivers',p),('a',av),('b',bv),('core',cv)]:
            if change in (name,'all'):value[::2]+=1e-4*rng.normal(size=value[::2].shape)
        if change=='inactive-core':cv[owners==1]+=.0003
        if change=='signed-zero':cv[1]=-0.
        delta=source.difference(av,bv,cv,owners)
        equal(shared.value_shared(p,delta,physical),separate.value(p,av,bv,query_core(cv,owners,physical)))
        for value in vars(delta).values():
            if isinstance(value,np.ndarray):assert value.flags.owndata and not value.flags.writeable
    assert source.bytes==sum(getattr(source,name).nbytes for name in ['a','b','core','physical'])
    for name in ['a','b','core','physical']:
        value=getattr(source,name);assert value.flags.owndata and not value.flags.writeable
    # A new explicit snapshot observes an in-place change of the same source arrays.
    av[0,0]+=.1
    equal(shared.value_shared(points,source.difference(av,bv,cv,owners),physical),
          separate.value(points,av,bv,query_core(cv,owners,physical)))


def test_source_context_layout_ownership_and_core_mask_guards():
    points,a,b,wind,pg,core,gamma,owners,physical,bound,ground=fixture(1,'one')
    source=VortexSourceTangent(a,b,core,owners)
    args=(points,a,b,wind,pg,query_core(core,owners,physical),gamma,ground)
    tangent=VortexFieldTangent(*args,exclude_bound=bound,_source=source,_physical=physical)
    def rejected(fn):
        try:fn()
        except VortexDerivativeUnavailable:return
        raise AssertionError('An invalid shared vortex context was accepted')
    rejected(lambda:VortexSourceTangent(a,b,core,owners,limit=1))
    for idx in range(4):
        values=[v.copy() for v in [a,b,core,owners]];values[idx]=values[idx][:-1]
        rejected(lambda:VortexSourceTangent(*values))
        rejected(lambda:source.difference(*values))
    changed=owners.copy();changed[0]+=1
    rejected(lambda:source.difference(a,b,core,changed))
    other=VortexSourceTangent(a,b,core,owners)
    rejected(lambda:tangent.value_shared(points,other.difference(a,b,core,owners),physical))
    rejected(lambda:tangent.value_shared(points[:1],source.difference(a,b,core,owners),physical))
    for current in [None,physical[:-1],physical+1]:
        rejected(lambda:tangent.value_shared(points,source.difference(a,b,core,owners),current))
    rejected(lambda:VortexFieldTangent(*args,exclude_bound=bound,_source=source,_physical=physical+1))
    wrong=list(args);wrong[5]=wrong[5]+.01
    rejected(lambda:VortexFieldTangent(*wrong,exclude_bound=bound,_source=source,_physical=physical))
    a[0,0]+=.1
    assert source.a[0,0]!=a[0,0]
    rejected(lambda:VortexFieldTangent(*args,exclude_bound=bound,_source=source,_physical=physical))
    for bad in [np.nan,np.inf,-np.inf]:
        current=core.copy();current[0]=bad
        rejected(lambda:VortexSourceTangent(a,b,current,owners))


@pytest.mark.parametrize('example,extra',[('flexible',{'circulation_modes':{1:3}}),
    ('wing-body',{'ground_effect':1}),('wing-body',{'ground_effect':-1}),
    ('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})])
def test_complete_operators_equal_separate_vortex_changes(example,extra,monkeypatch):
    from openswing.aero import FlightCondition
    from openswing.linear_dynamics import make_system,linearize
    import openswing.vortex_tangent as module
    from test_direct_circulation import model_for
    system,_=make_system(model_for(example),FlightCondition(speed=20,alpha=3,mach=.1,
        position_earth=[0.,0.,30.],**extra),4,structured_base=True)
    a,m=linearize(system,sparse=True,_output_fields=True)
    g=system._output_field_tangent.matrix.copy()
    def unavailable(*args,**kwargs):raise VortexDerivativeUnavailable('Shared source storage unavailable')
    monkeypatch.setattr(module,'VortexSourceTangent',unavailable)
    expected,mass=linearize(system,sparse=True,_output_fields=True)
    for name,actual,reference in [('A',a,expected),('M',m,mass),('G',g,system._output_field_tangent.matrix)]:
        operators_close(actual,reference,6*system.network.nn,mass=name=='M')


def test_one_source_change_per_field_and_complete_budget_accounting(monkeypatch):
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.structured_static import linearization
    from openswing.geometry_tangent import GeometryFields
    from test_direct_circulation import model_for,state_for
    n=StaticNetwork(model_for('wing-body'),8,FlightCondition(mach=.2,alpha=7,beta=3),None,[])
    x=state_for(n,.3);calls=[];original=VortexSourceTangent.difference
    def counted(self,*args):calls.append(1);return original(self,*args)
    monkeypatch.setattr(VortexSourceTangent,'difference',counted)
    with linearization(n,x,.6,capture_circulation=True) as (fields,baseline):
        evaluator=GeometryFields(n,fields,direct_vortex=True,direct_volume=True)
        for offset in [0.,1e-5,-1e-5]:
            current=x.copy();current[0]+=offset;evaluator(current)
            assert len(calls)==evaluator.evaluations
        assert len(evaluator.direct_vortex)>1
        assert evaluator.direct_vortex_bytes==evaluator.vortex_sources.bytes+sum(
            t.bytes for t in evaluator.direct_vortex.values() if t is not None)
        assert evaluator.direct_volume_bytes+evaluator.direct_vortex_bytes<=128*1024**2
        assert all(t._source is evaluator.vortex_sources for t in evaluator.direct_vortex.values() if t is not None)


def test_shared_storage_and_query_fallback_preserve_fields(monkeypatch):
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.structured_static import linearization
    from openswing.geometry_tangent import GeometryFields
    from test_direct_circulation import model_for,state_for
    import openswing.vortex_tangent as module
    n=StaticNetwork(model_for('wing-body'),8,FlightCondition(mach=.2,alpha=7),None,[])
    x=state_for(n,.3)
    with linearization(n,x,.6,capture_circulation=True) as (fields,baseline):
        original=GeometryFields(n,fields,direct_vortex=True,direct_volume=True)
        plain=GeometryFields(n,fields,direct_volume=True)
        expected=original(x);physical=plain(x)
        constructor=module.VortexSourceTangent
        def limited(*args,**kwargs):kwargs['limit']=1;return constructor(*args,**kwargs)
        monkeypatch.setattr(module,'VortexSourceTangent',limited)
        separate=GeometryFields(n,fields,direct_vortex=True,direct_volume=True)
        for key,value in separate(x).items():equal(value,expected[key])
        assert separate.vortex_sources is None
        assert separate.direct_vortex_bytes==sum(t.bytes for t in separate.direct_vortex.values() if t is not None)
        query=module.VortexFieldTangent
        def unavailable(*args,**kwargs):kwargs['limit']=1;return query(*args,**kwargs)
        monkeypatch.setattr(module,'VortexFieldTangent',unavailable)
        fallback=GeometryFields(n,fields,direct_vortex=True,direct_volume=True)
        for key,value in fallback(x).items():equal(value,physical[key])
        assert fallback.direct_vortex_bytes==0 and fallback.vortex_sources is None
        assert fallback.direct_vortex_fallbacks
