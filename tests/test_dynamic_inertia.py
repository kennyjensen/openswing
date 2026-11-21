import numpy as np
import pytest
from openswing.network import StaticNetwork
from openswing.inertia import Motion, inertial_wrench
from openswing.local_motion import NetworkMotion, rotation_matrix as exp
from openswing.dynamic_inertia import moving_mass_loads
from test_network import model,beam


def network(curved=False):
    b=beam().replace('End','t mg Ccg Ncg mgcc mgnn Dmg DCcg DNcg Dmgcc Dmgnn\n0 19.6133 .13 -.08 .980665 1.96133 9.80665 -.1 .05 .392266 .2941995\n2 19.6133 .13 -.08 .980665 1.96133 9.80665 -.1 .05 .392266 .2941995\nEnd')
    if curved:
        b=b.replace('2 0 2 0','1 .1 1 .3 100 100 100 1000 1000 1000\n1 .3 1 .5 100 100 100 1000 1000 1000\n2 .7 2 .6')
        b=b.replace('End','t twist\n0 10\n2 65\nEnd')
    return StaticNetwork(model(b,'Ground\n1 0 0\nEnd\nWeight\n1 1 .4 1 .2 19.6133 0 0 0 0 0 2 3 4 .2 .1 .3\nEnd\n'),4,None,[0,0,0],[])


def loads(net,r,q,values,motion=None,gravity=(0,0,0)):
    field=NetworkMotion(net,r,q,*values)
    return moving_mass_loads(net,field,net.deformed_meshes(r,q,net.geometry(r,q)),Motion() if motion is None else motion,
        gravity,net.point_positions(r,q),[q[net.node(*row[:2])] for row in net.weights])


def energy(records):
    return sum(.5*np.sum(e['mass']*np.sum(e['relative_velocity']**2,axis=-1))
        +.5*np.einsum('ni,nij,nj->',e['relative_rates'],e['inertia'],e['relative_rates']) for e in records)


def test_elastic_mass_matrix_is_symmetric_positive_and_matches_kinetic_energy():
    net=network(curved=True);rng=np.random.default_rng(181)
    r=net.rj+rng.normal(0,.03,net.rj.shape);q=exp(rng.normal(0,.2,r.shape));z=np.zeros_like(r)
    matrix=np.zeros((6*net.nn,6*net.nn))
    for j in range(len(matrix)):
        v=np.zeros((2,net.nn,3));v.reshape(-1)[j]=1
        f,m,_,_=loads(net,r,q,(z,z,*v))
        matrix[:,j]=-np.r_[f.ravel(),m.ravel()]
    np.testing.assert_allclose(matrix,matrix.T,atol=2e-15)
    assert np.min(np.linalg.eigvalsh(matrix))>0
    u,w=rng.normal(0,.4,(2,net.nn,3));v=np.r_[u.ravel(),w.ravel()]
    records=loads(net,r,q,(u,w,z,z))[2]
    assert .5*v@matrix@v==pytest.approx(energy(records),rel=2e-14)


def test_general_motion_inertial_power_equals_negative_kinetic_energy_derivative():
    net=network(curved=True);rng=np.random.default_rng(940)
    r=net.rj+rng.normal(0,.02,net.rj.shape);q=exp(rng.normal(0,.15,r.shape))
    u,w,ud,wd=rng.normal(0,.4,(4,net.nn,3))
    f,m,_,_=loads(net,r,q,(u,w,ud,wd))
    def kinetic(t):
        def rotation(s):return exp(s*w+.5*s*s*wd)@q
        qt=rotation(t);h=1e-5;derivative=(rotation(t+h)-rotation(t-h))/(2*h)
        skew=derivative@qt.transpose(0,2,1)
        wt=np.stack([skew[:,2,1]-skew[:,1,2],skew[:,0,2]-skew[:,2,0],skew[:,1,0]-skew[:,0,1]],axis=-1)/2
        return energy(loads(net,r+t*u+.5*t*t*ud,qt,(u+t*ud,wt,ud,wd))[2])
    h=1e-4
    assert -np.sum(f*u+m*w)==pytest.approx((kinetic(h)-kinetic(-h))/(2*h),rel=2e-7,abs=1e-8)


def test_distributed_shear_motion_uses_centerline_mass_without_spurious_section_spin():
    b=beam().replace('End','t mg\n0 19.6133\n2 19.6133\nEnd')
    net=StaticNetwork(model(b),4,None,[0,0,0],[]);r=net.rj;q=np.broadcast_to(np.eye(3),(net.nn,3,3));z=np.zeros_like(r)
    u=np.zeros_like(r);u[:,2]=.7*r[:,1]
    f,m,records,_=loads(net,r,q,(u,z,u,z))
    assert energy(records)==pytest.approx(.5*2*.7**2*2**3/3,rel=1e-14)
    np.testing.assert_allclose(f.sum(axis=0),[0,0,-2*.7*2**2/2],atol=1e-14)
    np.testing.assert_allclose((m+np.cross(r,f)).sum(axis=0),[-2*.7*2**3/3,0,0],atol=1e-14)


def test_rigid_motion_global_mass_wrench_matches_finite_segment_formula():
    net=network();r=net.rj;q=np.broadcast_to(np.eye(3),(net.nn,3,3));z=np.zeros_like(r)
    motion=Motion([.3,-.4,.2],[.2,.3,-.1],[-.1,.3,.2]);gravity=[0,0,-9.81]
    f,m,records,_=loads(net,r,q,(z,z,z,z),motion,gravity)
    original=net.inertia_model.elements(net.meshes,net.point_positions(r,q),[q[net.node(*row[:2])] for row in net.weights])
    force=np.zeros(3);moment=np.zeros(3)
    for e in original:
        ef,em=inertial_wrench(*(e[k] for k in ('mass','position','inertia','spin')),motion,gravity,net.model.reference[2])
        force+=ef.sum(axis=0);moment+=(em+np.cross(e['position'],ef)).sum(axis=0)
    np.testing.assert_allclose(f.sum(axis=0),force,atol=2e-14)
    np.testing.assert_allclose((m+np.cross(r,f)).sum(axis=0),moment,atol=3e-14)
    for key in ('mass','cg','inertia_reference','inertia_cg','spatial_matrix'):
        np.testing.assert_allclose(net.inertia_model.summary(records)[key],net.inertia_model.summary(original)[key],atol=3e-15)
