import numpy as np
import pytest
from openswing.local_motion import NetworkMotion,rotation_matrix,rotation_weights
from openswing.circulation_tangent import transfer
from openswing.network import StaticNetwork
from openswing.aero import FlightCondition
from test_direct_circulation import model_for,state_for


def fixture():
    n=StaticNetwork(model_for('wing-body'),4,FlightCondition(),None,[])
    r,q,*_=n.unpack(state_for(n));zero=np.zeros_like(r)
    return NetworkMotion(n,r,q,zero,zero,zero,zero)


@pytest.mark.parametrize('quadrature',[False,True])
@pytest.mark.parametrize('width',[1,4,16])
def test_physical_and_derivative_loads_share_exact_owned_weights(monkeypatch,quadrature,width):
    import openswing.local_motion as module
    motion=fixture();n=motion.network;beam=n.meshes[0].beam.index
    count=len(motion.pa[n.beam_elements[beam]])
    f=np.full((count,3) if quadrature else (count,),.37)
    rng=np.random.default_rng(324);shape=f.shape+(3,width)
    force=rng.normal(size=shape)+1j*rng.normal(size=shape)
    moment=rng.normal(size=shape)+1j*rng.normal(size=shape)
    expected=[motion.nodal_wrenches(beam,f,force[...,i],moment[...,i]) for i in range(width)]
    owned=motion.wrench_weights(beam,f)
    def forbidden(*args):raise AssertionError('Rebuilt the physical load-transfer matrices')
    monkeypatch.setattr(module,'rotation_weights',forbidden)
    actual=list(transfer(motion,beam,f,force,moment))
    for end,(ids,nf,nm) in enumerate(actual):
        np.testing.assert_array_equal(ids,expected[0][end][0])
        np.testing.assert_allclose(nf,np.stack([v[end][1] for v in expected],axis=-1),atol=2e-13,rtol=2e-13)
        np.testing.assert_allclose(nm,np.stack([v[end][2] for v in expected],axis=-1),atol=2e-13,rtol=2e-13)
    assert all(a is b for a,b in zip(owned,motion.wrench_weights(beam,f)))
    assert motion.cache_bytes<=motion.cache_limit
    for array in owned:
        assert not array.flags.writeable
        with pytest.raises(ValueError):array.flat[0]=0


def test_actual_geometry_fraction_dtype_and_shape_invalidate_transfer_weights():
    motion=fixture();n=motion.network;beam=n.meshes[0].beam.index;sl=n.beam_elements[beam]
    f=np.full(len(motion.pa[sl]),.37);previous=motion.wrench_weights(beam,f)
    for change in ['geometry','fraction','dtype','shape']:
        if change=='geometry':motion.q[n.a[sl][0]]=rotation_matrix(np.array([.1,.03,-.04]))@motion.q[n.a[sl][0]]
        elif change=='fraction':f=f+.1
        elif change=='dtype':f=f.astype(np.float32)
        else:f=np.broadcast_to(f[:,None],(len(f),3)).copy()
        current=motion.wrench_weights(beam,f);ra,rb=motion.q[n.a[sl]],motion.q[n.b[sl]]
        if f.ndim==2:ra,rb=ra[:,None],rb[:,None]
        for actual,expected in zip(current,rotation_weights(ra,rb,f)):np.testing.assert_array_equal(actual,expected)
        assert all(a is not b for a,b in zip(previous,current)),change
        previous=current


def test_zero_storage_budget_preserves_uncached_physical_transfer(monkeypatch):
    import openswing.local_motion as module
    motion=fixture();motion.cache_limit=0;n=motion.network;beam=n.meshes[0].beam.index
    f=np.full(len(motion.pa[n.beam_elements[beam]]),.37)
    calls=[];original=module.rotation_weights
    def counted(*args):calls.append(1);return original(*args)
    monkeypatch.setattr(module,'rotation_weights',counted)
    a=motion.wrench_weights(beam,f);b=motion.wrench_weights(beam,f)
    assert len(calls)==2 and motion.cache_bytes==0
    for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
