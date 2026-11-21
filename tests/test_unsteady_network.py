from pathlib import Path
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.recovery import recover_structure, recover_section
from openswing.structure import Section
from openswing.structure import skew
from openswing.damping import damping_diagnostics
from test_network import model,beam


def test_axial_strain_rate_law_uses_mechanical_strain_in_recovery():
    b=beam(stiffness='0 0 0 1000 0 0').replace('End','t tdeps tdgam Cshell Nshell\n0 .2 .3 .1 .1\n2 .2 .3 .1 .1\nEnd')
    net=StaticNetwork(model(b),4,None,[0,0,0],[])
    x=np.zeros(net.size);kin=x[:6*net.nn].reshape(net.nn,6)
    kin[:,1]=.01*net.rj[:,1]/net.L
    internal=x[6*net.nn:6*(net.nn+net.ne)].reshape(net.ne,6)
    internal[:,1]=1000*(.01+.2*.03)/net.F
    z=np.zeros_like(net.rj);u=z.copy();u[:,1]=.03*net.rj[:,1]
    residual,data=net.residual(x,detail=True,elastic_motion=(u,z,z,z))
    np.testing.assert_allclose(residual[:6*net.ne],0,atol=1e-15)
    np.testing.assert_allclose(data['strain_rate'][:,1],.03,atol=1e-15)
    elements,meta=recover_structure(net,data)
    assert meta['strain_source']=='current_geometry'
    assert data['damping']['passive']
    for e in elements:
        assert e['axial_strain_tension']==pytest.approx(.01,abs=1e-15)
        assert e['shell']['axial_strain']==pytest.approx(.01,abs=1e-15)
        assert e['force_local'][1]==pytest.approx(16.)


def test_material_strain_recovery_translates_to_tension_axis_with_damped_loads():
    sec=Section(EA=1000,EIcc=100,GJ=200,EInn=300,Cta=.2,Nta=-.1)
    mechanical=np.array([0,.03,0,.04,.01,-.02])
    # Deliberately unrelated loads: geometric strain must determine shell strain.
    state=recover_section(sec,[1,900,3],[4,5,6],mechanical_strain=mechanical,cshell=.3,nshell=.2)
    axial=.03-(-.1)*.04+.2*(-.02)
    assert state['axial_strain_tension']==pytest.approx(axial)
    assert state['shell']['axial_strain']==pytest.approx(axial+.3*(-.02)-.2*.04)


def test_componentwise_damping_detects_energy_production_with_coupled_stiffness():
    s=Section(EIcc=10,GJ=10,EInn=20,EIcs=8,EA=100,GKc=50,GKn=50).compliance()
    d=np.array([1,0,1,0,1,0.])
    report=damping_diagnostics(s[None],d[None],[1.])
    assert not report['passive']
    assert report['elements'][0]['minimum_energy_damping_time']<-.1
    # Independent explicit strain velocity with negative viscous work.
    damping=np.linalg.solve(s,np.diag(d))
    eigen,v=np.linalg.eigh((damping+damping.T)/2)
    assert v[:,0]@damping@v[:,0]<0
    assert eigen[0]<0
    uniform=damping_diagnostics(s[None],np.full((1,6),.2),[.7])
    assert uniform['passive']
    assert uniform['elements'][0]['minimum_energy_damping_time']==pytest.approx(.2)


def test_dynamic_residual_cache_includes_velocities_acceleration_and_circulation_rate():
    m=parse_asw(Path('examples/stress-wing.asw').read_text());c=FlightCondition(alpha=0,mach=0,stall=False)
    net=StaticNetwork(m,4,c,[0,0,0],[]);x=np.zeros(net.size);z=np.zeros_like(net.rj)
    def run(u=z,a=z,rate=None):return net.residual(x,detail=True,elastic_motion=(u,z,a,z),circulation_rate=rate)
    a,da=run();velocity=z.copy();velocity[:,2]=.2
    b,db=run(u=velocity);acceleration=z.copy();acceleration[:,2]=.7
    d,dd=run(a=acceleration);rate=np.full(net.ng,.3);e,de=run(rate=rate)
    assert np.linalg.norm(b-a)>1e-3
    assert np.linalg.norm(d-a)>1e-3
    assert np.linalg.norm(e-a)>1e-6
    assert np.linalg.norm(np.array(db['aero']['circulation_residual'])-da['aero']['circulation_residual'])>1e-3
    assert dd['aero']['apparent_force'][2]<da['aero']['apparent_force'][2]
    assert de['aero']['circulation_rate_force'][2]>0
    repeated,dr=run()
    np.testing.assert_array_equal(repeated,a)
    np.testing.assert_array_equal(dr['aero']['force'],da['aero']['force'])


def test_invalid_material_damping_is_rejected_for_unsteady_residual():
    b=beam().replace('End','t tdeps\n0 -.2\n2 -.2\nEnd')
    net=StaticNetwork(model(b),4,None,[0,0,0],[]);z=np.zeros_like(net.rj)
    with pytest.raises(ValueError,match='damping times'):
        net.residual(np.zeros(net.size),elastic_motion=(z,z,z,z))


@pytest.mark.parametrize('example',['rectangular','wing-body'])
def test_complete_real_and_apparent_mass_operator_is_symmetric_positive_and_has_rigid_limit(example):
    model=parse_asw(Path(f'examples/{example}.asw').read_text())
    net=StaticNetwork(model,4,FlightCondition(alpha=0,mach=0,stall=False),[0,0,0],[])
    rng=np.random.default_rng(540);x=np.zeros(net.size)
    # Large enough deformation to distinguish rotation and force-transfer maps.
    kin=x[:6*net.nn].reshape(net.nn,6);kin[:,:3]=rng.normal(0,.004,(net.nn,3));kin[:,3:]=rng.normal(0,.08,(net.nn,3))
    z=np.zeros_like(net.rj);_,base=net.residual(x,detail=True,elastic_motion=(z,z,z,z))
    baseline=np.r_[base['force'].ravel(),base['moment'].ravel()]
    mass=np.empty((6*net.nn,6*net.nn))
    for j in range(len(mass)):
        acc=np.zeros((2,net.nn,3));acc.reshape(-1)[j]=1
        _,data=net.residual(x,detail=True,elastic_motion=(z,z,*acc))
        mass[:,j]=baseline-np.r_[data['force'].ravel(),data['moment'].ravel()]
    np.testing.assert_allclose(mass,mass.T,atol=2e-13)
    assert np.min(np.linalg.eigvalsh(mass))>-1e-12
    # Reduce the elastic operator to six rigid velocities/accelerations.
    rigid=np.zeros((6*net.nn,6))
    rigid[:3*net.nn,:3]=np.tile(np.eye(3),(net.nn,1))
    rigid[:3*net.nn,3:]=-skew(base['r']-model.reference[1]).reshape(-1,3)
    rigid[3*net.nn:,3:]=np.tile(np.eye(3),(net.nn,1))
    real=np.array(net.inertia_model.summary(base['masses'])['spatial_matrix'])
    apparent=np.array(base['aero']['apparent_mass']['spatial_matrix'])
    np.testing.assert_allclose(rigid.T@mass@rigid,real+apparent,atol=2e-11)
