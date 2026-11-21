"""Original stencil samples and bounded matrix-product rounding errors."""
from decimal import Decimal,localcontext
import numpy as np
import pytest
from openswing.field_products import source_product
from openswing.geometry_tangent import refined_field_column


@pytest.mark.parametrize('sources',[1,2,7,17])
def test_packed_action_against_independent_80_digit_dot_products(sources):
    rng=np.random.default_rng(7193+sources);receivers=3;samples=4
    a,b=[rng.normal(size=(receivers,sources,3,3)) for _ in range(2)]
    c=rng.normal(size=(receivers,sources,3))
    da,db=[rng.normal(size=(samples,sources,3)) for _ in range(2)]
    dc=rng.normal(size=(samples,sources))
    # A cancellation and scale mixture makes a relative-to-result check weak.
    a[1]*=1e30;b[1]=-a[1];db[1]=da[1];c[1]*=1e-20
    value=source_product(a,b,c,da,db,dc)
    with localcontext() as ctx:
        ctx.prec=80
        for k in range(samples):
            for i in range(receivers):
                for axis in range(3):
                    terms=[]
                    for j in range(sources):
                        terms += [Decimal.from_float(float(m))*Decimal.from_float(float(d)) for m,d in zip(
                            [*a[i,j,axis],*b[i,j,axis],c[i,j,axis]], [*da[k,j],*db[k,j],dc[k,j]])]
                    expected=sum(terms);magnitude=float(sum(abs(t) for t in terms))
                    rounding=float(abs(Decimal.from_float(float(value[k,i,axis]))-expected))
                    operations=2*7*sources;eps=np.finfo(float).eps
                    bound=operations*eps/(1-operations*eps)*magnitude
                    assert rounding<=bound,(sources,k,i,axis,rounding,bound)


def test_packing_keeps_fifth_order_geometry_error_visible_to_refinement():
    h=1e-5;a=np.zeros((1,1,3,3));a[0,0,0,0]=1.;b=np.zeros_like(a);c=np.zeros((1,1,3))
    def coordinate(x):return x+2e15*x**5
    delta=np.zeros((4,1,3));delta[:,0,0]=[coordinate(k*h) for k in (1,-1,2,-2)]
    samples=source_product(a,b,c,delta,np.zeros_like(delta),np.zeros((4,1)))
    values=[{'cp':s.copy(),'circulation_residual':np.array([0.])} for s in samples]
    def physical(x):return {'cp':np.array([[coordinate(x),0.,0.]]),'circulation_residual':np.array([0.])}
    actual,report=refined_field_column(physical,h,values,1.)
    assert report['refinements']>0
    np.testing.assert_allclose(actual['cp'],[[1.,0.,0.]],atol=2e-8,rtol=0.)


def test_empty_receivers_and_zero_source_columns():
    for receivers,sources in [(0,2),(2,0)]:
        shape=(receivers,sources,3,3);dshape=(4,sources,3)
        result=source_product(np.zeros(shape),np.zeros(shape),np.zeros(shape[:-1]),
            np.zeros(dshape),np.zeros(dshape),np.zeros(dshape[:-1]))
        assert result.shape==(4,receivers,3) and not np.any(result)


from test_geometry_tangent import CASES as PHYSICAL_CASES
@pytest.mark.parametrize('example,frame,extra,circulation',PHYSICAL_CASES)
def test_packed_complete_geometry_columns_against_full_physical_residual(example,frame,extra,circulation,monkeypatch):
    import test_geometry_tangent as reference
    original=reference.geometry_columns
    def packed(*args,**kwargs):
        return original(*args,**kwargs,_direct_vortex=True,_direct_volume=True,_nodewise_state=True)
    monkeypatch.setattr(reference,'geometry_columns',packed)
    reference.test_complete_geometry_columns_match_refined_full_residual(example,frame,extra,circulation)


@pytest.mark.parametrize('frozen',[False,True])
def test_packed_spatial_gust_jet_geometry_against_full_physical_residual(frozen,monkeypatch):
    import test_geometry_tangent as reference
    original=reference.geometry_columns
    def packed(*args,**kwargs):
        return original(*args,**kwargs,_direct_vortex=True,_direct_volume=True,_nodewise_state=True)
    monkeypatch.setattr(reference,'geometry_columns',packed)
    reference.test_spatial_gust_driven_jet_geometry_in_both_influence_modes(frozen)
