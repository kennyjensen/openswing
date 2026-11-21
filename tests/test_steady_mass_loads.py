"""Load-only quadrature preserves complete nodal and element mass wrenches."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.inertia import Motion
from openswing.local_motion import NetworkMotion, rotation_matrix
from openswing.dynamic_inertia import moving_mass_loads
from test_dynamic_inertia import network as mass_network


@pytest.mark.parametrize('motion', [Motion(), Motion(acceleration=[.2,-.4,.3]),
    Motion(rates=[.2,-.3,.1]), Motion(angular_acceleration=[-.2,.1,.3])])
@pytest.mark.parametrize('elastic', ['stationary','velocity','rates','acceleration','angular_acceleration'])
def test_every_mass_wrench_matches_the_full_quadrature(motion, elastic):
    net=mass_network(curved=True);rng=np.random.default_rng(635)
    r=net.rj+rng.normal(0,.03,net.rj.shape);q=rotation_matrix(rng.normal(0,.2,r.shape))
    values=np.zeros((4,net.nn,3))
    if elastic!='stationary':
        values[['velocity','rates','acceleration','angular_acceleration'].index(elastic)]=rng.normal(0,.2,r.shape)
    field=NetworkMotion(net,r,q,*values);meshes=net.deformed_meshes(r,q,net.geometry(r,q))
    args=(net,field,meshes,motion,[.1,-.2,-9.81],net.point_positions(r,q),[q[net.node(*row[:2])] for row in net.weights])
    expected=moving_mass_loads(*args,with_end_forces=True)
    actual=moving_mass_loads(*args,with_end_forces=True,_loads_only=True)
    for i in [0,1,3,4]:np.testing.assert_array_equal(actual[i],expected[i])
    assert expected[2] and actual[2]==[]


@pytest.mark.parametrize('example',['rectangular','flexible','wing-body','stepped-body','powered','articulated','dae'])
def test_detail_after_load_only_restores_all_mass_records_and_physical_rows(example, monkeypatch):
    import openswing.network as module
    model=parse_asw(Path(f'examples/{example}.asw').read_text())
    net=StaticNetwork(model,4,FlightCondition(mach=.2),None,[])
    x=np.random.default_rng(327).normal(0,.0002,net.size);x[net.gamma_start:]+=.04
    actual=net.residual(x,.7).copy()
    detailed,report=net.residual(x,.7,detail=True)
    np.testing.assert_array_equal(actual,detailed)
    assert len(report['masses'])==2*len(net.meshes)+len(net.weights)
    original=module.moving_mass_loads
    def full(*args,**kwargs):
        kwargs['_loads_only']=False
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'moving_mass_loads',full)
    control=StaticNetwork(model,4,FlightCondition(mach=.2),None,[])
    expected,full_report=control.residual(x,.7,detail=True)
    np.testing.assert_array_equal(actual,expected)
    for a,b in zip(report['masses'],full_report['masses']):
        assert a.keys()==b.keys()
        for key in a:np.testing.assert_array_equal(a[key],b[key])


def test_nonzero_centroid_inertia_survives_a_zero_mass_density():
    net=mass_network(curved=True)
    for entries in net.inertia_model.data.values():
        for values in entries:values[0][:]=0
    r=net.rj;q=rotation_matrix(np.zeros_like(r));z=np.zeros_like(r)
    field=NetworkMotion(net,r,q,z,z,z,z)
    args=(net,field,net.meshes,Motion(angular_acceleration=[.2,-.3,.4]),[0,0,0],net.point_positions(r,q),[q[net.node(*row[:2])] for row in net.weights])
    expected=moving_mass_loads(*args,with_end_forces=True)
    actual=moving_mass_loads(*args,with_end_forces=True,_loads_only=True)
    assert np.linalg.norm(expected[3])>0
    for i in [0,1,3,4]:np.testing.assert_array_equal(actual[i],expected[i])
