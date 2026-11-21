"""Source-preserving rigid-pylon reduction, with no native-parity assertion."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import Distribution, RIGID, parse_asw, weight_station
from openswing.aero import AnalysisError
from openswing.bridge import dispatch
from openswing.equilibrium_state import capture, identity, restore
from openswing.geometry import attachment_geometry, model_meshes
from openswing.network import StaticNetwork, network_snapshot
from openswing.point_objects import analysis_weight_station, rigid_weight_attachments
from scripts.isae_ffwt4_rigid_extension_v2 import (
    fixture, balanced_state, physical_loads, point_oracle,
)


def model(*, station=.8, material=''):
    return parse_asw('Name\nRigid pylon\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n10 1.2 340\nEnd\n'
        'Reference\n1 .2 1\n0 0 0\nEnd\nGround\n1 2 0\nEnd\n'
        f'Weight\n1 {station:.17g} .17 -.09 .11 7 0 0 .6 -.4 .2 2 3 4 .1 -.2 .3\nEnd\n'
        'Beam 1\nRigid beam\nt x y z chord\n1 0 0 0 .2\n2 0 1 0 .2\n'
        + material + 'End\n')


@pytest.mark.parametrize('station,expected', [(.8,1.),(2.2,2.),(1.5,1.5),(1.,1.),
    (np.nextafter(1.,0.),1.),(100.,2.)])
def test_source_records_and_physical_point_are_unchanged(station, expected):
    m=model(station=station); raw=m.records['weight'][0].copy(); text=m.dumps()
    assert weight_station(m,m.records['weight'][0]) == station
    assert analysis_weight_station(m,m.records['weight'][0]) == expected
    n=StaticNetwork(m,4,None,None,[])
    assert n.weights[0][1] == expected
    np.testing.assert_array_equal(n.weights[0][2:],raw[2:])
    np.testing.assert_allclose(n.point_positions(n.rj,np.tile(np.eye(3),(n.nn,1,1)))[0],raw[2:5],rtol=0,atol=4*np.finfo(float).eps)
    np.testing.assert_allclose(attachment_geometry(m)[0]['segments'][0][1],raw[2:5],atol=1e-16)
    assert m.dumps() == text and m.source == text
    np.testing.assert_array_equal(m.records['weight'][0],raw)
    # Serialization after a genuine edit must not write the effective anchor.
    m.records['weight'][0][5] += .1
    again=parse_asw(m.dumps())
    assert again.records['weight'][0][1] == station


@pytest.mark.parametrize('name', sorted(RIGID)+['EIcn','EIcs','EIsn','tdeps','tdgam'])
def test_any_nonzero_table_rejects_reduction_even_between_mesh_nodes(name):
    value=1e200 if name in RIGID else 1e-100
    m=model(material=f't {name}\n1 0\n1.123 {value}\n2 0\n')
    assert analysis_weight_station(m,m.records['weight'][0]) == .8
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(m,4)


@pytest.mark.parametrize('name',sorted(RIGID))
def test_singleton_zero_stiffness_and_edited_tables_are_rechecked(name):
    m=model(material=f't {name}\n99 0\n')
    assert analysis_weight_station(m,m.records['weight'][0]) == 1
    # Live raw values cannot silently retain a previous rigid certificate.
    m.beams[0].distributions[name].values[0] = 1e100
    assert analysis_weight_station(m,m.records['weight'][0]) == .8
    # Conversely an old flexible compiled spline is not certified by raw zeros.
    d=Distribution(name,np.array([1.,2.]),np.array([10.,10.]),1)
    m.beams[0].distributions[name]=d;d.values[:]=0
    assert analysis_weight_station(m,m.records['weight'][0]) == .8
    d.__post_init__()
    assert analysis_weight_station(m,m.records['weight'][0]) == 1


@pytest.mark.parametrize('field',[6,7])
def test_point_flow_properties_are_outside_current_reduction_scope(field):
    m=model();m.records['weight'][0][field]=1e-100
    assert not rigid_weight_attachments(m)
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(m,4)


@pytest.mark.parametrize('lifting',[False,True])
@pytest.mark.parametrize('upper',[False,True])
@pytest.mark.parametrize('tilted,local',[(False,False),(True,True)])
def test_actual_reduction_matches_explicit_extension_and_independent_section_loads(lifting,upper,tilted,local):
    outer=2.2 if upper else .8
    reduced=fixture(extended=False,lifting=lifting,upper=upper,anchor=outer)
    explicit=fixture(extended=True,lifting=lifting,upper=upper)
    assert len(reduced.network.rigid_weight_attachments)==1
    _, data, residual, _, R, shift=balanced_state(reduced,tilted,local)
    _, other, *_=balanced_state(explicit,tilted,local)
    np.testing.assert_allclose(physical_loads(reduced,data),physical_loads(explicit,other),rtol=3e-13,atol=3e-13)
    p,force,couple=point_oracle(reduced,R,shift,local)
    expected=[];sign=1 if upper else -1;n=reduced.network
    for e in reduced.physical_elements:
        for node in (n.a[e],n.b[e]):
            expected.extend([sign*force,sign*(couple+np.cross(p-data['r'][node],force))])
    np.testing.assert_allclose(physical_loads(reduced,data),expected,rtol=3e-13,atol=3e-13)
    report=network_snapshot(n,residual,data)
    assert report['rigid_weight_attachments']==n.rigid_weight_attachments
    assert any('out-of-range' in s for s in report['limitations'])


def test_saved_state_requires_unchanged_reduction_provenance():
    n=StaticNetwork(model(),4,None,None,[])
    x=np.zeros(n.size);saved=capture(n,x)
    rebuilt=StaticNetwork(parse_asw(n.model.dumps()),4,None,None,[])
    np.testing.assert_array_equal(restore(rebuilt,saved),x)
    assert identity(rebuilt)==identity(n)
    bad=deepcopy(saved);del bad['identity']['rigid_weight_attachments']
    with pytest.raises(AnalysisError,match='does not match'):
        restore(rebuilt,bad)
    for key,value in [('effective_t',1.1),('original_t',.7),('policy','unknown'),('position',[0,0,0])]:
        bad=deepcopy(saved);bad['identity']['rigid_weight_attachments'][0][key]=value
        with pytest.raises(AnalysisError,match='does not match'):
            restore(rebuilt,bad)
    saved['identity']['rigid_weight_attachments'][0]['position'][0]=123
    assert n.rigid_weight_attachments[0]['position'][0] != 123
    ordinary=StaticNetwork(model(station=1.),4,None,None,[])
    assert 'rigid_weight_attachments' not in identity(ordinary)


@pytest.mark.parametrize('operator',[None,'drela-moving-vacuum-v1'])
def test_time_checkpoint_rejects_missing_or_changed_attachment_policy(operator):
    from openswing.time_integration import solve_time
    from openswing.time_state import checkpoint, resume_time
    m=parse_asw(model().dumps(),beam_interpolation='drela-segspl-v1' if operator else 'natural-v1')
    result=solve_time(m,panels=4,duration=.02,dt=.01,gravity=[0,0,0],structural_operator=operator)
    saved=checkpoint(result,1)
    resumed=resume_time(m,saved,duration=.01)
    assert resumed['accepted_steps']==1 and resumed['rejected_steps']==0
    for a,b in zip(result['snapshots'][-1]['nodes'],resumed['snapshots'][-1]['nodes']):
        np.testing.assert_allclose(a['position'],b['position'],atol=1e-14)
    bad=deepcopy(saved);del bad['context']['identity']['rigid_weight_attachments']
    with pytest.raises(AnalysisError,match='do not match'):
        resume_time(m,bad,duration=.01)
    bad=deepcopy(saved);bad['context']['identity']['rigid_weight_attachments'][0]['policy']='unrecognized'
    with pytest.raises(AnalysisError,match='do not match'):
        resume_time(m,bad,duration=.01)


REV='f62943df20e9e4d7d9f50e070477b22426b5f865'
NATIVE=(Path(__file__).resolve().parents[1]/'.reference/isae-validation'/REV/
    '4 - Aeroelasticity/FFWT - Flared Folding Wingtips Cases/'
    'FFWT-4-U - Gust Alleviation of a Wing with and wo FFWT - Quantitative')


@pytest.mark.parametrize('flare',[10,20,30])
@pytest.mark.parametrize('interpolation',['natural-v1','drela-segspl-v1'])
def test_literal_pm2_models_mesh_without_source_edits(flare,interpolation):
    path=NATIVE/f'FFWT_Flare{flare}_PM2.asw'
    if not path.exists():pytest.skip('Pinned ISAE reference cache not installed')
    text=path.read_text();m=parse_asw(text,beam_interpolation=interpolation)
    original=[r.copy() for r in m.records['weight']]
    meshes=model_meshes(m,4)
    assert len(meshes)==3
    changes=rigid_weight_attachments(m)
    assert [(a['record'],a['beam'],a['effective_t']) for a in changes]==[(52,2,.364),(57,3,-.364)]
    n=StaticNetwork(m,4,None,None,[])
    assert n.rigid_weight_attachments==changes
    assert m.dumps()==text and m.source==text
    for a,b in zip(original,m.records['weight']):np.testing.assert_array_equal(a,b)
    inspected=dispatch(dict(action='inspect',source=text,panels=4))
    assert inspected['rigid_weight_attachments']==changes
    assert len([a for a in inspected['compatibility_notes'] if a.get('message')])==2
