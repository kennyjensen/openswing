"""Minimum strip separation in physical material length, without geometry edits."""
from copy import deepcopy
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.discretization import normalize, report
from openswing.geometry import model_meshes


def model(points='0 0\n2 2', extra=''):
    return parse_asw('Name\nSpacing test\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\n'
                     'Reference\n2 1 2\nEnd\nBeam 1\nBeam\nt y\n'+points+'\nEnd\n'+extra)


def settings(count, minimum, spacing='uniform'):
    return dict(default=count, beams={'1':dict(count=count, spacing=spacing, min_spacing=minimum)})


@pytest.mark.parametrize('count', [16,32,64,128])
def test_requested_refinement_cannot_shrink_uniform_intervals_below_minimum(count):
    m=model(); request=settings(count,.125); before=deepcopy(request); source=m.dumps()
    mesh=model_meshes(m,request)[0]
    np.testing.assert_allclose(mesh.length,np.full(16,.125),atol=2e-14,rtol=0)
    np.testing.assert_allclose(np.r_[mesh.t0,mesh.t1[-1]],np.linspace(0,2,17),atol=2e-14,rtol=0)
    assert m.dumps()==source and request==before
    out=report(m,[mesh],request)
    assert out['settings']==request and out['beams'][0]['panels']==16


@pytest.mark.parametrize('spacing', ['cosine','modified-cosine','uniform'])
def test_minimum_is_material_distance_and_symmetric_coarsening_keeps_mirrored_geometry(spacing):
    # An exactly straight 2 m beam with mirrored shape and a distinct t scale.
    m=model('-3 -1\n0 0\n3 1')
    mesh=model_meshes(m,settings(64,.12,spacing))[0]
    assert np.all(mesh.length >= .12-2e-12)
    y=np.r_[mesh.r0[:,1],mesh.r1[-1,1]]
    np.testing.assert_allclose(y+y[::-1],0,atol=2e-14,rtol=0)
    assert abs(sum(mesh.length)-2)<2e-14 and len(mesh.tm)<64


def test_nonlinear_parameter_does_not_set_the_minimum_length():
    m=model('-2 0\n0 .4\n3 2'); mesh=model_meshes(m,settings(32,.125))[0]
    np.testing.assert_allclose(mesh.length,np.full(16,.125),atol=5e-14,rtol=0)
    assert not np.allclose(np.diff(np.r_[mesh.t0,mesh.t1[-1]]),.125)


@pytest.mark.parametrize('count',[17,31,63])
@pytest.mark.parametrize('spacing',['cosine','modified-cosine','uniform'])
def test_odd_requested_counts_keep_minimum_and_do_not_choose_one_mirror_side(count,spacing):
    mesh=model_meshes(model(),settings(count,.125,spacing))[0]
    assert np.all(mesh.length>=.125-2e-12) and len(mesh.tm)<=16
    nodes=np.r_[mesh.r0[:,1],mesh.r1[-1,1]]
    np.testing.assert_allclose(nodes+nodes[::-1],2,atol=2e-14,rtol=0)


def test_required_stations_are_retained_and_close_required_stations_are_rejected():
    m=model(extra='Weight\n1 .7 0 .7 0 10\nEnd\n')
    mesh=model_meshes(m,settings(64,.2))[0]
    assert .7 in mesh.t0 and np.all(mesh.length>=.2-2e-12)
    with pytest.raises(ValueError,match='required stations are closer'):
        model_meshes(model(extra='Weight\n1 .05 0 .05 0 10\nEnd\n'),settings(64,.2))
    with pytest.raises(ValueError,match='required stations are closer'):
        model_meshes(m,settings(64,3.))


@pytest.mark.parametrize('spacing',['cosine','modified-cosine','uniform'])
def test_zero_minimum_retains_existing_geometry_bit_for_bit(spacing):
    m=model('-2 0\n0 .4\n3 2')
    base=dict(default=16,beams={'1':dict(count=16,spacing=spacing)})
    old=model_meshes(m,base)[0]; new=model_meshes(m,settings(16,0.,spacing))[0]
    for key in ('t0','t1','tm','r0','r1','rm','frames','length','theta'):
        np.testing.assert_array_equal(getattr(old,key),getattr(new,key))


def test_tiny_positive_minimum_terminates_without_repeated_candidate_selection():
    mesh=model_meshes(model(),settings(16,1e-30))[0]
    assert len(mesh.tm)==16


@pytest.mark.parametrize('minimum',[True,'0.1',None,[],float('nan'),float('inf'),-.1])
def test_invalid_minimum_is_rejected(minimum):
    with pytest.raises(ValueError,match='min_spacing'):
        normalize(settings(16,minimum))
