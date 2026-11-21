"""Independent first variations of unloaded flexible source-beam trees.

These checks prepare an exact statics-first rank argument; they do not enable
a new production rank certificate or assert a conditioning bound. Constitutive
matrices below come directly from the literal synthetic section properties,
not the solver's constitutive or tangent helpers.
"""
import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.source_airflow import SourceAirflowNetwork
from openswing.source_discrete import SourceSectionNetwork


AXIS=np.array([2.,1.,3.])/np.sqrt(14.)
STIFFNESS=np.array([[30.,2.,-3.],[2.,25.,1.],[-3.,1.,40.]])
DIRECT=np.array([1/120.,1/300.,1/90.])
OFFSET=np.array([[0.,-.04,0.],[.02,0.,.01],[0.,-.03,0.]])


def setup(*, airflow=True, rigid_tips=False, offsets=False, ground_count=1):
    joints='Joint\n1 2 3 1 3\n1 3 1 3 3\nEnd\n'
    laws='Jangle\n1 2 1 3\n-100 -100\n100 100\nEnd\nJangle\n2 2 1 3\n-100 100\n100 -100\nEnd\n'
    # The public constructor correctly rejects a model without a Ground.
    # Build the missing-Ground algebraic counterexample by removing its
    # decoded equations/unknowns below, solely for the oracle and scope guard.
    ground='Ground\n'+''.join('1 2 0\n' for _ in range(max(1,ground_count)))+'End\n'
    beams=[];properties={}
    for index,(lo,hi) in enumerate(((-1.,1.),(1.,3.),(-3.,-1.)),1):
        rigid=rigid_tips and index!=1
        values='0 0 0 0 0 0 0 0 0' if rigid else '30 25 40 2 -3 1 300 120 90'
        off='.01 -.02 .03 -.04' if offsets else '0 0 0 0'
        beams.append(f'Beam {index} 1\nSynthetic source beam\n'
            't x y z chord EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn Cea Nea Cta Nta mg\n'
            f'1 0 {lo} 0 .2 {values} {off} 1\n'
            f'3 0 {hi} 0 .2 {values} {off} 1\nEnd\n')
        properties[index]=(np.zeros((3,3)) if rigid else np.linalg.inv(STIFFNESS),
            np.zeros(3) if rigid else DIRECT.copy(),OFFSET.copy() if offsets else np.zeros((3,3)))
    source=('Name\nFlexible zero-load oracle\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.2 340\nEnd\nReference\n1 .2 6\nEnd\n'+ground+joints+laws+''.join(beams))
    model=parse_asw(source,beam_interpolation='drela-segspl-v1')
    if airflow:
        net=SourceAirflowNetwork(model,4,FlightCondition(speed=10.,alpha=5.,beta=4.,mach=0.,freeze_influences=True),None,[],steady_trim=True)
    else:
        net=SourceSectionNetwork(model,4,None,[0.,0.,9.81],[])
    if ground_count==0:
        net.constraints=[c for c in net.constraints if c['b'] is not None]
        for i,c in enumerate(net.constraints):c['sl']=slice(6*i,6*(i+1))
        net.nc-=6;net.gamma_start-=6;net.operating_start-=6;net.size-=6
    assert np.array_equal(net.R0a,np.broadcast_to(np.eye(3),net.R0a.shape))
    assert np.array_equal(net.R0b,net.R0a)
    return net,properties


def variation(net,properties,delta):
    """Steady Eqs.18--20,48,54--56, independently linearized at the jig."""
    pose=delta[:6*net.nn].reshape(net.nn,6)
    u,theta=net.L*pose[:,:3],pose[:,3:]
    internal=delta[6*net.nn:6*(net.nn+net.ne)].reshape(net.ne,6)
    force,moment=net.F*internal[:,:3],net.F*net.L*internal[:,3:]
    reaction=delta[6*(net.nn+net.ne):net.gamma_start]
    nf=np.zeros((net.nn,3));nm=np.zeros_like(nf);compatibility=np.empty((net.ne,6))
    element_properties={e:properties[beam] for beam,sl in net.beam_elements.items() for e in range(sl.start,sl.stop)}
    for e,(a,b) in enumerate(net.ends):
        compliance,direct,h=element_properties[e]
        curvature=compliance@(moment[e]+h@force[e])
        strain=direct*force[e]+h.T@curvature
        compatibility[e,:3]=(u[b]-u[a]-net.ds[e]/2*np.cross(theta[a]+theta[b],[0.,1.,0.])-net.ds[e]*strain)/net.L
        compatibility[e,3:]=theta[b]-theta[a]-net.ds[e]*curvature
        chord=net.rj[b]-net.rj[a];half=np.cross(chord,force[e])/2
        nf[a]+=force[e];nf[b]-=force[e]
        nm[a]+=moment[e]+half;nm[b]+=-moment[e]+half
    constraints=[]
    for c in net.constraints:
        a,b=c['a'],c['b'];value=reaction[c['sl']]
        f,m=net.F*value[:3],net.F*net.L*value[3:]
        nf[a]+=f;nm[a]+=m
        if b is None:
            assert c['type']==0
            constraints.extend(u[a]/net.L);constraints.extend(theta[a]);continue
        nf[b]-=f;nm[b]-=m
        chord=net.rj[b]-net.rj[a];nm[a]+=np.cross(chord,f)
        constraints.extend((u[b]-u[a]-np.cross(theta[a],chord))/net.L)
        assert c['type']==3
        e=c['element'];edge=net.rj[net.b[e]]-net.rj[net.a[e]]
        trace=moment[e]+(-1 if c['end'] else 1)*np.cross(edge,force[e])/2
        slope=(1 if c['end'] else -1)*np.pi/180
        constraints.extend(theta[b]-theta[a]-slope*np.dot(AXIS,trace)*AXIS)
    return np.r_[compatibility.ravel(),(nf/net.F).ravel(),(nm/(net.F*net.L)).ravel(),constraints]


def oracle(net,properties):
    return np.column_stack([variation(net,properties,d) for d in np.eye(net.gamma_start)])


@pytest.mark.parametrize('airflow,rigid_tips,offsets',[(False,False,False),(True,False,True),(True,True,False)])
def test_full_mechanical_first_variation_matches_independent_flexible_oracle(airflow,rigid_tips,offsets):
    net,properties=setup(airflow=airflow,rigid_tips=rigid_tips,offsets=offsets)
    expected=oracle(net,properties)
    singular=np.linalg.svd(expected,compute_uv=False)
    assert singular[-1]>1e-7*singular[0]
    # Every mechanical column is checked; no production tangent is imported.
    step=2e-6;actual=[]
    for j in range(net.gamma_start):
        direction=np.zeros(net.size);direction[j]=step
        actual.append((net.residual(direction,0.)-net.residual(-direction,0.))[:net.gamma_start]/(2*step))
    np.testing.assert_allclose(np.column_stack(actual),expected,atol=8e-9,rtol=3e-8)
    # Recheck the complete operator at a distinct step in arbitrary directions.
    rng=np.random.default_rng(381)
    for _ in range(3):
        direction=rng.normal(size=net.gamma_start);direction/=max(abs(direction))
        d=np.r_[direction,np.zeros(net.size-net.gamma_start)]*7e-7
        actual=(net.residual(d,0.)-net.residual(-d,0.))[:net.gamma_start]/(14e-7)
        np.testing.assert_allclose(actual,expected@direction,atol=8e-9,rtol=3e-8)


@pytest.mark.parametrize('ground_count',[0,2])
def test_missing_or_duplicate_ground_leaves_independent_oracle_singular(ground_count):
    net,properties=setup(ground_count=ground_count,rigid_tips=True)
    matrix=oracle(net,properties);singular=np.linalg.svd(matrix,compute_uv=False)
    assert np.count_nonzero(singular<=1e-10*singular[0])>=6


def test_finite_compliance_does_not_enter_unloaded_statics_block():
    flexible,fp=setup(offsets=True);mixed,mp=setup(rigid_tips=True,offsets=True)
    assert flexible.gamma_start==mixed.gamma_start
    a,b=oracle(flexible,fp),oracle(mixed,mp)
    # Loads/reactions are eliminated by conservative balance before the
    # compliance-dependent compatibility equations in the proposed proof.
    start=6*flexible.ne;stop=start+6*flexible.nn
    np.testing.assert_array_equal(a[start:stop],b[start:stop])
    assert np.linalg.norm(a[:start]-b[:start])>0.


def test_zero_load_mechanics_is_independent_of_nonzero_circulation():
    net,properties=setup(rigid_tips=True)
    expected=oracle(net,properties);base=np.zeros(net.size)
    base[net.gamma_start:net.operating_start]=np.linspace(.1,.4,net.operating_start-net.gamma_start)
    rng=np.random.default_rng(719)
    for _ in range(4):
        direction=rng.normal(size=net.gamma_start);direction/=max(abs(direction))
        d=np.r_[direction,np.zeros(net.size-net.gamma_start)]*1e-6
        actual=(net.residual(base+d,0.)-net.residual(base-d,0.))[:net.gamma_start]/2e-6
        np.testing.assert_allclose(actual,expected@direction,atol=8e-9,rtol=3e-8)


def test_rank_argument_does_not_require_zero_jig_translation_defect():
    net,properties=setup(airflow=False,rigid_tips=True,offsets=True)
    net.ds*=np.linspace(.8,1.2,net.ne)
    residual=net.residual(np.zeros(net.size),0.)
    assert max(abs(residual))>.01
    expected=oracle(net,properties);singular=np.linalg.svd(expected,compute_uv=False)
    assert singular[-1]>1e-7*singular[0]
    rng=np.random.default_rng(902)
    for _ in range(4):
        direction=rng.normal(size=net.size);direction/=max(abs(direction))
        actual=(net.residual(1e-6*direction,0.)-net.residual(-1e-6*direction,0.))/2e-6
        np.testing.assert_allclose(actual,expected@direction,atol=8e-9,rtol=3e-8)
