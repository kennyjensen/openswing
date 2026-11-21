"""Sparse local maps retain the complete analytic geometry, in either chart."""
import numpy as np
import pytest
from openswing.local_geometry_matrix import LocalGeometryMatrix,LocalGeometryUnavailable
from openswing.geometry_field_partials import GeometryFieldPartials
from test_geometry_partials import CASES,fixture,leaves


@pytest.mark.parametrize('name,extra',CASES)
@pytest.mark.parametrize('chart',['spatial','absolute'])
def test_sparse_map_preserves_every_local_geometry_column(name,extra,chart):
    n,e,g,_=fixture(name,extra,chart)
    before=n.tangent_influences.bytes
    matrix=LocalGeometryMatrix(g)
    assert n.tangent_influences.bytes==before
    assert matrix.direction_evaluations<=1+matrix.groups
    batches=[np.arange(start,min(start+16,6*n.nn)) for start in range(0,6*n.nn,16)]
    batches+=[np.array([6*n.nn-1,0,0,7,3])]
    for columns in batches:
        actual=matrix.columns(columns);expected=g.columns(columns)
        for path,a,b in leaves(actual,expected):
            assert a.flags.c_contiguous,(name,chart,path)
            error=float(np.max(abs(a-b)/(1+abs(b)),initial=0.))
            assert error<3e-15,(name,chart,path,error)
    assert matrix.applications==len(batches)
    assert matrix.bytes<32*1024**2


@pytest.mark.parametrize('name,extra',[
    ('jet-2',dict(powers={1:50000.},ground_effect=1,
       gust=dict(type='sinusoid',amplitude=[.2,.1,.4],wavevector=[.21,.3,-.17],omega=.4))),
    ('stepped-wing-body',{}),('stepped-wing-body',{'freeze_influences':True})])
def test_full_flow_composition_reuses_local_map_without_changing_fields(name,extra):
    n,e,g,_=fixture(name,extra,'spatial')
    e.direct_vortex={};e.direct_volume={}
    cached=GeometryFieldPartials(e,g.state)
    direct=GeometryFieldPartials(e,g.state,_cache_geometry=False)
    assert cached.local_matrix is not None,cached.local_matrix_fallback
    for start in range(0,6*n.nn,16):
        columns=np.arange(start,min(start+16,6*n.nn))
        a,b=cached.columns(columns),direct.columns(columns)
        for key in a:
            error=float(np.max(abs(a[key]-b[key])/(1+abs(b[key])),initial=0.))
            assert error<3e-14,(name,key,error)


@pytest.mark.parametrize('which',['state','base','material','fraction','chart','core','reflection','spline'])
def test_changed_actual_inputs_reject_cached_geometry(which):
    n,e,g,_=fixture('wing-body',{'ground_effect':1},'absolute')
    matrix=LocalGeometryMatrix(g)
    if which=='state':g.state[0]+=1e-5
    elif which=='base':g.base['p']['a'][0,0]+=1e-5
    elif which=='material':n.weights[0][2]+=1e-5
    elif which=='fraction':n.fractions[n.meshes[0].beam.index][0]+=.01
    elif which=='chart':g.chart_map[0,0,0]+=.01
    elif which=='core':e.condition.wake_core_ratio+=.01
    elif which=='reflection':e.ground.reflection[0,0]+=.01
    else:n.meshes[0].beam.distributions['chord']._segments[0][2].c[0,0]+=.01
    with pytest.raises(LocalGeometryUnavailable,match='physical inputs'):matrix.columns([0])


def test_cache_owns_values_and_retains_tiny_nonzeros():
    n,e,g,_=fixture('rectangular',{},'spatial')
    g.chart_map[0]*=1e-50
    matrix=LocalGeometryMatrix(g)
    expected=g.columns([3]);actual=matrix.columns([3])
    assert np.any((abs(matrix.matrix.data)>0)&(abs(matrix.matrix.data)<1e-40))
    assert all(not a.flags.writeable for a in (matrix.matrix.data,matrix.matrix.indices,matrix.matrix.indptr))
    actual['q'][:]=999
    for path,a,b in leaves(matrix.columns([3]),expected):np.testing.assert_array_equal(a,b,err_msg=path)


def test_budget_failure_and_invalid_support_release_construction_storage(monkeypatch):
    n,e,g,_=fixture('rectangular',{},'spatial')
    before=n.tangent_influences.bytes
    with pytest.raises(LocalGeometryUnavailable,match='storage budget'):LocalGeometryMatrix(g,limit=1)
    assert n.tangent_influences.bytes==before
    original=g.direction
    # Deliberately introduce a nonlocal derivative in a declared local row.
    def nonlocal_direction(dr,omega):
        result=original(dr,omega)
        if np.any(dr) or np.any(omega):result['r']+=np.sum(dr+omega,axis=0)[None]
        return result
    monkeypatch.setattr(g,'direction',nonlocal_direction)
    with pytest.raises(LocalGeometryUnavailable,match='declared local support'):LocalGeometryMatrix(g)
    assert n.tangent_influences.bytes==before


def test_unavailable_optional_cache_keeps_original_field_path(monkeypatch):
    from openswing import local_geometry_matrix as module
    n,e,g,_=fixture('rectangular',{},'spatial')
    e.direct_vortex={};e.direct_volume={}
    direct=GeometryFieldPartials(e,g.state,_cache_geometry=False)
    original=module.LocalGeometryMatrix
    def unavailable(*args,**kwargs):raise LocalGeometryUnavailable('test budget')
    with monkeypatch.context() as patch:
        patch.setattr(module,'LocalGeometryMatrix',unavailable)
        fallback=GeometryFieldPartials(e,g.state)
    assert fallback.local_matrix is None and fallback.local_matrix_fallback=='test budget'
    for key,value in direct.columns([0,3,7]).items():np.testing.assert_array_equal(value,fallback.columns([0,3,7])[key])
    cached=GeometryFieldPartials(e,g.state)
    assert isinstance(cached.local_matrix,original)
    cached.local_matrix.signature=b'changed'
    before=cached.bytes;size=cached.local_matrix.bytes
    for key,value in direct.columns([0,3,7]).items():np.testing.assert_array_equal(value,cached.columns([0,3,7])[key])
    assert cached.local_matrix is None and cached.bytes==before-size


@pytest.mark.parametrize('name',['Xax','dCLda','radius'])
def test_replaced_geometry_distributions_invalidate_the_map(name):
    from openswing.asw import Distribution
    n,e,g,_=fixture('wing-body',{},'spatial')
    matrix=LocalGeometryMatrix(g)
    beam=next(mesh.beam for mesh in n.meshes if mesh.beam.lifting==(name!='radius'))
    lo,hi=beam.domain
    beam.distributions[name]=Distribution(name,np.array([lo,hi]),np.array([.3,.4]),0)
    with pytest.raises(LocalGeometryUnavailable,match='physical inputs'):matrix.columns([0])


def test_unrelated_stiffness_does_not_invalidate_the_local_geometry_map():
    from openswing.asw import Distribution
    n,e,g,_=fixture('wing-body',{},'spatial')
    matrix=LocalGeometryMatrix(g);beam=n.meshes[0].beam
    lo,hi=beam.domain
    beam.distributions['EIcc']=Distribution('EIcc',np.array([lo,hi]),np.array([1e5,2e5]),0)
    for path,a,b in leaves(matrix.columns([0,3,7]),g.columns([0,3,7])):
        np.testing.assert_allclose(a,b,rtol=3e-15,atol=3e-15,err_msg=path)


@pytest.mark.parametrize('name,extra',[
    ('rectangular',{}),('stepped-wing-body',{'ground_effect':1})])
def test_consumed_column_storage_is_released_without_cyclic_collection(name,extra):
    import gc
    import weakref
    n,e,g,_=fixture(name,extra,'spatial')
    matrix=LocalGeometryMatrix(g)
    gc.collect()
    enabled=gc.isenabled();gc.disable()
    try:
        for columns in ([0,3,7],[1,4,8],[2,5,9]):
            result=matrix.columns(columns)
            owner=result['r']
            while isinstance(owner.base,np.ndarray):owner=owner.base
            released=weakref.ref(owner)
            del result,owner
            # Repeated full-Jacobian batches must not accumulate dense column
            # buffers until a cyclic-GC threshold happens to be reached.
            assert released() is None
    finally:
        if enabled:gc.enable()
        gc.collect()
