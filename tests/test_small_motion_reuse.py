"""Short beam maps retain the complete rotation and motion laws."""
import numpy as np
import pytest
from openswing.local_motion import rotation_interpolation,rotation_weights,rotation_matrix
from openswing.tangent_influences import TangentInfluences


@pytest.mark.parametrize('count',[1,2,4,8])
@pytest.mark.parametrize('rate',[0.,1e-18,.2])
def test_short_arc_and_wrench_maps_equal_full_recalculation(count,rate):
    rng=np.random.default_rng(1019)
    ra,rb=rotation_matrix(rng.normal(0,.3,(2,count,3)))
    wa,wb,aa,ab=rate*rng.normal(size=(4,count,3))
    fraction=np.linspace(.13,.87,count)
    original=(ra,rb,wa,wb,aa,ab,fraction)
    cache=TangentInfluences(local_geometry=True);calls=[]
    def evaluate(arrays):
        def arc(rows):
            calls.append(np.arange(count)[rows].tolist())
            return rotation_interpolation(*(a[rows] for a in arrays))
        value=cache.local_rows('arc',arrays,arc)
        angles=(arrays[0],arrays[1],arrays[-1])
        weights=cache.local_rows('weights',angles,lambda rows:rotation_weights(*(a[rows] for a in angles)))
        for actual,expected in zip(value,rotation_interpolation(*arrays)):
            np.testing.assert_array_equal(actual,expected)
        for actual,expected in zip(weights,rotation_weights(*angles)):
            np.testing.assert_array_equal(actual,expected)
        # A caller cannot change retained rotations, rates or transfer matrices.
        for array in (*value,*weights):array.fill(99.)
    evaluate(original);assert len(calls)==1
    evaluate(original);assert len(calls)==1
    for index in range(len(original)):
        changed=[a.copy() for a in original]
        if index<2:changed[index][-1]=rotation_matrix([.07,-.03,.02])@changed[index][-1]
        else:changed[index][-1]+=1e-18 if index<6 and rate<1e-10 else .01
        evaluate(changed);evaluate(original)
    assert cache.bytes<=64*1024**2


@pytest.mark.parametrize('count',[1,4,8])
def test_cached_stationary_arc_still_rejects_pi_rotation(count):
    identity=np.broadcast_to(np.eye(3),(count,3,3)).copy()
    zero=np.zeros((count,3));fraction=np.full(count,.5)
    cache=TangentInfluences(local_geometry=True)
    def evaluate(right):
        arrays=(identity,right,zero,zero,zero,zero,fraction)
        return cache.local_rows('arc',arrays,lambda rows:rotation_interpolation(*(a[rows] for a in arrays)))
    evaluate(identity)
    bad=identity.copy();bad[-1]=rotation_matrix([np.pi,0.,0.])
    for _ in range(2):
        with pytest.raises(ValueError,match='approaches pi'):evaluate(bad)
    np.testing.assert_array_equal(evaluate(identity)[0],identity)


def test_short_maps_respect_budget_and_changed_shapes_and_types():
    cache=TangentInfluences(local_geometry=True);calls=[]
    def evaluate(values):
        def compute(rows):
            calls.append(values[rows].shape)
            return (rotation_matrix(values[rows]),)
        actual,=cache.local_rows('rotation',(values,),compute)
        np.testing.assert_array_equal(actual,rotation_matrix(values))
    cache.bytes=64*1024**2
    values=np.array([[.3,-.2,.7]])
    evaluate(values);evaluate(values)
    assert len(calls)==2 and not cache.local_entries
    cache.bytes=0;evaluate(values);evaluate(values)
    assert len(calls)==3
    evaluate(np.repeat(values,4,axis=0))
    evaluate(values.astype(np.float32));evaluate(values)
    assert len(calls)==5 and cache.bytes<=64*1024**2


def test_empty_row_maps_keep_original_empty_result():
    cache=TangentInfluences(local_geometry=True)
    values=np.empty((0,3));calls=[]
    def compute(rows):calls.append(True);return (values[rows].copy(),)
    for _ in range(2):
        result,=cache.local_rows('empty',(values,),compute)
        assert result.shape==(0,3)
    assert len(calls)==2 and not cache.local_entries


def captured_fields(example,kind='zero'):
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.geometry_tangent import GeometryFields
    from openswing.structured_static import IterationFields
    from test_direct_circulation import model_for,state_for
    condition=FlightCondition(speed=30,mach=.2,alpha=7,beta=3,ground_effect=1,
        position_earth=[0,0,30],rates=[.03,-.04,.02],
        powers={1:50000.} if example=='jet-2' else {},
        gust=dict(type='sinusoid',amplitude=[.2,.1,.4],wavevector=[.21,.3,-.17],omega=.4))
    n=StaticNetwork(model_for(example),4,condition,None,[]);x=state_for(n,.3)
    values=np.zeros((4,n.nn,3))
    if kind=='negative_zero':values.fill(-0.)
    if kind in ('tiny','moving'):
        values=np.random.default_rng(1017).normal(size=values.shape)*(1e-300 if kind=='tiny' else .01)
    fields=IterationFields();fields.capture_circulation=True;n.iteration_fields=fields
    try:
        baseline=n.residual(x,.6,elastic_motion=tuple(values))
        evaluator=GeometryFields(n,fields)
    finally:n.iteration_fields=None;n.aero_key=None
    return n,x,fields,baseline,evaluator


@pytest.mark.parametrize('example',['wing-body','jet-2'])
@pytest.mark.parametrize('kind',['zero','negative_zero','tiny','moving'])
def test_stationary_fields_and_motion_fallback_equal_original_physics(example,kind,monkeypatch):
    import openswing.geometry_tangent as module
    n,x,fields,baseline,evaluator=captured_fields(example,kind)
    original=module.NetworkMotion;calls=[]
    def construct(*args,**kwargs):calls.append(True);return original(*args,**kwargs)
    monkeypatch.setattr(module,'NetworkMotion',construct)
    actual=evaluator(x)
    assert len(calls)==(0 if kind=='zero' else 1)
    np.testing.assert_allclose(actual.pop('circulation_residual'),
        baseline[n.gamma_start:n.operating_start],atol=2e-14,rtol=2e-14)
    for name,value in actual.items():
        expected=np.einsum('ijk,j->ik',fields.values['vortex',name],fields.circulation_aero['gamma'])
        expected+=n.condition.speed*fields.values['volume',name].reshape(-1,3)
        if name!='engine':expected+=fields.values['jet',name].reshape(-1,3)
        np.testing.assert_allclose(value,expected,atol=2e-12,rtol=2e-13)


@pytest.mark.parametrize('change',['shape','nan'])
def test_malformed_motion_fields_keep_the_original_validation(change):
    n,x,fields,baseline,evaluator=captured_fields('wing-body')
    values=[v.copy() for v in evaluator.local_values]
    if change=='shape':values[0]=values[0][:-1]
    else:values[0][0,0]=float('nan')
    evaluator.local_values=tuple(values)
    with pytest.raises(ValueError,match='Elastic motion fields must be finite'):evaluator(x)


def test_stationary_field_shortcut_keeps_the_surface_arc_domain_check(monkeypatch):
    import openswing.geometry_tangent as module
    n,x,fields,baseline,evaluator=captured_fields('wing-body')
    def reject(*args):raise ValueError('deliberate relative arc domain rejection')
    monkeypatch.setattr(module,'checked_rotation_arc',reject)
    with pytest.raises(ValueError,match='relative arc domain'):evaluator(x)
