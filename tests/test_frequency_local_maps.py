"""Exact moving-element maps reused only at unchanged physical inputs."""
import numpy as np
import pytest
from openswing.local_motion import rotation_matrix,rotation_interpolation,rotation_weights
from openswing.tangent_influences import TangentInfluences


@pytest.mark.parametrize('quadrature',[False,True])
@pytest.mark.parametrize('moving',[False,True])
def test_row_maps_match_complete_original_functions_after_every_input_changes(quadrature,moving):
    rng=np.random.default_rng(412);n=32
    a=rotation_matrix(rng.normal(size=(n,3))*.3)
    b=a@rotation_matrix(rng.normal(size=(n,3))*.2)
    rates=[rng.normal(size=(n,3))*.2 if moving else np.zeros((n,3)) for _ in range(4)]
    f=np.broadcast_to(np.linspace(.02,.98,8),(n,8)).copy() if quadrature else np.linspace(.1,.9,n)
    if quadrature:a,b=a[:,None],b[:,None];rates=[v[:,None] for v in rates]
    original=(a,b,*rates,f);cache=TangentInfluences(local_geometry=True)
    def run(arrays):
        stationary=not any(np.any(v) for v in arrays[2:6])
        out=cache.local_rows(('arc',quadrature,stationary),arrays,lambda rows:rotation_interpolation(*(v[rows] for v in arrays)))
        for x,y in zip(out,rotation_interpolation(*arrays)):np.testing.assert_array_equal(x,y)
        xyz=arrays[0],arrays[1],arrays[-1]
        out=cache.local_rows(('weights',quadrature),xyz,lambda rows:rotation_weights(*(v[rows] for v in xyz)))
        for x,y in zip(out,rotation_weights(*xyz)):np.testing.assert_array_equal(x,y)
        # Callers must not be able to corrupt the retained maps.
        out[0][0]=99
    run(original)
    for j in range(7):
        arrays=[v.copy() for v in original]
        if j<2:
            increment=rotation_matrix(np.array([.01,-.02,.03]));arrays[j][7]=arrays[j][7]@increment
        else:arrays[j][7]+=.03
        run(tuple(arrays));run(original)
    # The fallback for a large changed set is also the original full operation.
    arrays=[v.copy() for v in original];arrays[-1][::2]*=.8;run(tuple(arrays))
    assert 0<cache.bytes<=64*1024**2


def test_row_map_budget_disable_shape_change_and_rotation_domain():
    n=32;a=np.broadcast_to(np.eye(3),(n,3,3)).copy();b=a.copy();f=np.linspace(.1,.9,n)
    arrays=(a,b,f);cache=TangentInfluences(local_geometry=True)
    for active,budget in [(False,0),(True,64*1024**2)]:
        cache.local_geometry=active;cache.bytes=budget
        actual=cache.local_rows('weights',arrays,lambda rows:rotation_weights(*(v[rows] for v in arrays)))
        for x,y in zip(actual,rotation_weights(*arrays)):np.testing.assert_array_equal(x,y)
        assert not cache.local_entries
    cache=TangentInfluences(local_geometry=True)
    cache.local_rows('weights',arrays,lambda rows:rotation_weights(*(v[rows] for v in arrays)))
    short=tuple(v[:12] for v in arrays)
    for x,y in zip(cache.local_rows('weights',short,lambda rows:rotation_weights(*(v[rows] for v in short))),rotation_weights(*short)):
        np.testing.assert_array_equal(x,y)
    zero=np.zeros((n,3));args=(a,b,zero,zero,zero,zero,f)
    cache.local_rows('arc',args,lambda rows:rotation_interpolation(*(v[rows] for v in args)))
    b[7]=rotation_matrix(np.array([np.pi-1e-8,0,0]))
    with pytest.raises(ValueError,match='pi'):
        cache.local_rows('arc',args,lambda rows:rotation_interpolation(*(v[rows] for v in args)))
