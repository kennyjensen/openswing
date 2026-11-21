"""Signed static distributions: independent balance, continuum and inertia guards."""
import numpy as np
import pytest
from scipy.integrate import solve_bvp
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.inertia import Motion
from openswing.network import StaticNetwork


def source(mg=0., dmg=-2., offsets=(0.,0.,0.,0.), inertias=(0.,0.,0.,0.)):
    c,n,dc,dn=offsets;cc,nn,dcc,dnn=inertias
    return f'''Name
Distributed static verification
End
Units
L 1 m
T 1 s
F 1 N
End
Constant
10 1.225 340
End
Reference
1 1 1
End
Ground
1 0 0
End
Beam 1
Cantilever
t y EIcc EInn GJ mg Dmg Ccg Ncg DCcg DNcg mgcc mgnn Dmgcc Dmgnn
0 0 1 3 2 {mg} {dmg} {c} {n} {dc} {dn} {cc} {nn} {dcc} {dnn}
1 1 1 3 2 {mg} {dmg} {c} {n} {dc} {dn} {cc} {nn} {dcc} {dnn}
End
'''


@pytest.mark.parametrize('gravity',[[0,0,-10],[1.2,-4.,2.3],[0,0,0]])
@pytest.mark.parametrize('weights',[(2.,-2.),(-3.,1.)])
def test_independent_centroid_wrench_at_large_rotation(gravity,weights):
    offsets=(.12,-.07,-.23,.18);model=parse_asw(source(*weights,offsets=offsets))
    net=StaticNetwork(model,8,None,gravity,[],allow_signed_distributed_weights=True)
    v=np.array([.7,-.4,.3]);q=Rotation.from_rotvec(v).as_matrix();shift=np.array([.2,-.6,.4])
    x=np.zeros(net.size);nodes=x[:6*net.nn].reshape(-1,6)
    nodes[:,:3]=net.rj@q.T+shift-net.rj;nodes[:,3:]=v
    _,data=net.residual(x,detail=True)
    forces=np.array(weights)[:,None]/10*np.array(gravity)
    centers=np.array([[offsets[0],.5,offsets[1]],[offsets[2],.5,offsets[3]]])@q.T+shift
    expected_force=forces.sum(axis=0);expected_moment=np.cross(centers-model.reference[1],forces).sum(axis=0)
    actual_moment=(data['moment']+np.cross(data['r']-model.reference[1],data['force'])).sum(axis=0)
    np.testing.assert_allclose(data['force'].sum(axis=0),expected_force,atol=3e-14)
    np.testing.assert_allclose(actual_moment,expected_moment,atol=3e-14)


@pytest.mark.parametrize('q',[2.,-2.])
def test_distributed_large_deflection_matches_independent_elastica(q):
    # Unit EI, unit length, vertical force q per undeformed length. No kernel
    # geometry, element law or residual is used to construct this reference.
    def rhs(s,u):
        theta,moment,y,z=u
        return np.array([moment,-q*(1-s)*np.cos(theta),np.cos(theta),np.sin(theta)])
    def bc(a,b):return np.array([a[0],a[2],a[3],b[1]])
    s=np.linspace(0,1,81);guess=np.zeros((4,len(s)));guess[2]=s
    ref=solve_bvp(rhs,bc,s,guess,tol=1e-10,max_nodes=10000)
    assert ref.success and np.max(abs(bc(ref.y[:,0],ref.y[:,-1])))<1e-12
    exact=ref.sol(1);errors=[]
    for panels in [16,32,64]:
        result=dispatch(dict(action='solve',mode='structural',source=source(dmg=-q),panels=panels))
        tip=result['nodes'][-1];rotation=np.asarray(tip['rotation'])
        theta=np.arctan2(rotation[2,1],rotation[1,1])
        error=max(abs(theta-exact[0]),np.max(abs(np.array(tip['position'])-[0,exact[2],exact[3]])))
        errors.append(error)
        assert result['residual']<1e-8
        np.testing.assert_allclose(result['applied_force'],[0,0,q],atol=2e-13)
    assert errors[-1]<1e-4
    assert all(b<a/3.5 for a,b in zip(errors[:-1],errors[1:]))


def test_inspection_classification_and_zero_gravity_state():
    text=source();inspected=dispatch(dict(action='inspect',source=text,panels=8))
    assert inspected['signed_point_weights']==[]
    assert inspected['signed_distributed_weights']==[dict(beam=1,field='Dmg')]
    result=dispatch(dict(action='solve',mode='structural',source=text,panels=8,gravity=[0,0,0]))
    assert result['max_displacement']<1e-12
    assert result['mass_properties']['physical'] is False
    assert result['mass_properties']['cg'] is None and 'launch' not in result['equilibrium_state']


@pytest.mark.parametrize('field',['mg','Dmg'])
def test_default_and_point_only_options_do_not_enable_signed_distributions(field):
    model=parse_asw(source(**{field.lower() if field=='Dmg' else field:-2.},**({'dmg':0.} if field=='mg' else {})))
    for options in [{},{'allow_signed_point_weights':True}]:
        with pytest.raises(ValueError,match='Distributed weights'):
            StaticNetwork(model,8,None,None,[],**options)


@pytest.mark.parametrize('index',range(4))
def test_negative_centroidal_inertia_remains_invalid(index):
    values=[0.]*4;values[index]=-.01
    with pytest.raises(ValueError,match='centroidal inertias'):
        dispatch(dict(action='solve',mode='structural',source=source(inertias=values),panels=8))


@pytest.mark.parametrize('action,options',[
    ('solve',{'mode':'mounted'}),('solve',{'mode':'rigid'}),
    ('modes',{'modes':{'vacuum':True}}),('time',{'time':{'duration':.01,'dt':.01}}),
    ('frequency',{'frequency':{'frequencies':[1.]}})])
def test_physical_analyses_reject_signed_distributed_mass(action,options):
    with pytest.raises(ValueError,match='Distributed weights'):
        dispatch(dict(action=action,source=source(),panels=8,condition={'speed':10},**options))


def test_signed_distributed_network_rejects_moving_evaluation():
    model=parse_asw(source())
    with pytest.raises(ValueError,match='zero motion'):
        StaticNetwork(model,8,None,None,[],motion=Motion(rates=[0,0,1]),allow_signed_distributed_weights=True)
    net=StaticNetwork(model,8,None,None,[],allow_signed_distributed_weights=True)
    with pytest.raises(ValueError,match='not physical negative masses'):
        net.residual(np.zeros(net.size),elastic_motion=[np.zeros_like(net.rj)]*4)


def test_negative_input_knot_is_not_hidden_by_coarse_positive_samples():
    from openswing.asw import Distribution
    from openswing.geometry import model_meshes
    from openswing.inertia import InertiaModel
    model=parse_asw(source(dmg=0.))
    model.beams[0].distributions['Dmg']=Distribution('Dmg',np.array([0.,1.]),np.array([-1.,1000.]),0)
    meshes=model_meshes(model,8)
    assert np.all(model.beams[0].value('Dmg',meshes[0].ts)>0)
    with pytest.raises(ValueError,match='Distributed weights'):InertiaModel(model,meshes)
    signed=InertiaModel(model,meshes,allow_signed_distributed_weights=True)
    assert signed.signed_distributed_weights==[dict(beam=1,field='Dmg')]
    assert signed.summary(signed.elements(meshes))['physical'] is False
