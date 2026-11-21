"""Physical scope controls for the analytic initial rigid-tree certificate."""
from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest
from openswing.network import StaticNetwork
from openswing.rigid_initial_rank import rigid_tree_initial_certificate
from openswing.structured_static import check_initial_rank,StructuredMatrix
from openswing.aero import AnalysisError
from scipy.sparse import csc_matrix
from test_network import model,beam
from test_joints import linked

def net(m=None,panels=4):return StaticNetwork(linked() if m is None else m,panels,None,[0,0,0],())
def proof(n,factor=0.,x=None):return rigid_tree_initial_certificate(n,np.zeros(n.size) if x is None else x,factor)
def reject(n,reason,factor=0.,x=None):
    p=proof(n,factor,x);assert not p['certified'];assert reason in p['reason'];return p

@pytest.mark.parametrize('reverse',[False,True])
@pytest.mark.parametrize('panels',[4,5,9])
def test_hinge_positive_hinges_are_independent_of_refinement_and_trace_direction(reverse,panels):
    if reverse:
        b=beam(stiffness='0 0 0 0 0 0')+beam(2,start=-2,end=0,stiffness='0 0 0 0 0 0')
        m=model(b,'Ground\n1 2 0\nEnd\nJoint\n1 2 0 2 3\nEnd\nJangle\n1 1 0 0\n-100 100\n100 -100\nEnd\n')
    else:m=linked()
    n=net(m,panels);p=proof(n);assert p['certified'];assert p['rigid_bodies']==2
    assert p['hinges'][0]['effective_stiffness']==pytest.approx(180/np.pi)
    assert p['constrained_body_dofs']+p['positive_spring_dofs']==12

def test_hinge_renaming_and_reordering_are_not_case_name_checks():
    m=linked();m.name='arbitrary generic network'
    m.beams[0].index=17;m.beams[1].index=43;m.beams=m.beams[::-1]
    m.records['ground'][0][0]=17;m.records['joint'][0][:2]=[17,43]
    assert proof(net(m))['certified']

def test_hinge_reversed_coordinate_nonorthogonality_is_not_tolerance_relaxed():
    n=net(linked('-100 100\n100 -100',reverse=True))
    reject(n,'exact orthonormal')

def test_hinge_independent_grounded_forest_and_rigid_offset_joint():
    b=beam(stiffness='0 0 0 0 0 0')+beam(2,start=3,end=5,z=1,stiffness='0 0 0 0 0 0')
    p=proof(net(model(b,'Ground\n1 0 0\n2 0 0\nEnd\n')))
    assert p['certified'] and p['trees']==2
    p=proof(net(model(b,'Ground\n1 0 0\nEnd\nJoint\n1 2 2 0 0\nEnd\n')))
    assert p['certified'] and p['rigid_bodies']==1 and p['rigid_joint_edges']==1

def test_hinge_negative_stiffness_declines_positive_energy_proof():
    reject(net(linked('-100 100\n100 -100')),'nonpositive')

def test_hinge_exact_antisymmetry_accepts_evaluation_roundoff_but_nearby_preload_rejects():
    n=net(linked('-0.00000209436 -120\n0.00000209436 120'))
    p=proof(n);assert p['certified'];spring=p['hinges'][0]
    assert spring['zero_intercept_proof']=='exact antisymmetric two-point source curve'
    assert spring['evaluated_intercept_rad']!=0
    n=net(linked(f'-0.00000209436 -120\n0.00000209436 {float(np.nextafter(120.,np.inf))!r}'))
    reject(n,'source curve does not certify zero')

def test_hinge_released_hinge_and_rigid_slope_do_not_masquerade_as_positive_spring():
    n=net();law=n.constraints[1]['law'];law.spline=SimpleNamespace(evaluate=lambda *args,**kw: np.inf if kw.get('derivative') else 0.)
    reject(n,'nonfinite')
    reject(net(linked('-100 0\n100 0')),'zero or ambiguous')
    m=linked();m.records['joint'][0][-1]=1;m.records['jangle']=[]
    n=net(m);reject(n,'partial constraint')
    with pytest.raises(AnalysisError,match='mechanism or redundant'):check_initial_rank(n,np.zeros(n.size))

@pytest.mark.parametrize('kind',['free_body','partial_ground','multiple_ground','rigid_cycle','hinge_cycle'])
def test_hinge_unrestrained_or_redundant_graph_declines_and_existing_check_rejects(kind):
    m=linked()
    if kind=='free_body':m.records['joint']=[];m.records['jangle']=[]
    elif kind=='partial_ground':m.records['ground'][0][-1]=1
    elif kind=='multiple_ground':m.records['ground'].append(m.records['ground'][0].copy())
    elif kind=='rigid_cycle':m.records['joint'][0][-1]=0;m.records['joint'].append(m.records['joint'][0].copy());m.records['jangle']=[]
    else:
        m.records['joint'].append(m.records['joint'][0].copy());j=deepcopy(m.records['jangle'][0]);j['header'][0]=2;m.records['jangle'].append(j)
    n=net(m);assert not proof(n)['certified']
    with pytest.raises(AnalysisError,match='mechanism or redundant'):check_initial_rank(n,np.zeros(n.size))

@pytest.mark.parametrize('kind',['displacement','rotation','internal','reaction','lambda','intercept','chart','rest_strain','section_offset','motion'])
def test_hinge_nonzero_initial_context_declines(kind):
    n=net();x=np.zeros(n.size);factor=0.
    if kind=='displacement':x[0]=1e-30
    elif kind=='rotation':x[3]=1e-30
    elif kind=='internal':x[6*n.nn]=1e-30
    elif kind=='reaction':x[6*(n.nn+n.ne)]=1e-30
    elif kind=='lambda':factor=1e-30
    elif kind=='intercept':n=net(linked('-100 -99\n100 101'));x=np.zeros(n.size)
    elif kind=='chart':n.constraints[1]['angle_chart']=1e-30
    elif kind=='rest_strain':n.v0[0,0]=1e-30
    elif kind=='section_offset':n.offa[0,0]=1e-30
    elif kind=='motion':n.motion.rates[0]=1e-30
    assert not proof(n,factor,x)['certified']

@pytest.mark.parametrize('kind',['offset','interior','extra_parent_attachment','finite_compliance','nonorthogonal_frame','unequal_frames'])
def test_hinge_unproved_mechanical_context_declines(kind):
    m=linked(offset=kind=='offset')
    if kind=='interior':m.records['joint'][0][2]=1
    if kind=='extra_parent_attachment':m.records['ground'].append([1,2,0])
    n=net(m)
    if kind=='finite_compliance':n.S[0,0,0]=1e-30
    if kind=='nonorthogonal_frame':n.R0a[0,0,0]=np.nextafter(n.R0a[0,0,0],np.inf);n.R0b=n.R0a.copy()
    if kind=='unequal_frames':n.R0b[0]=n.R0b[0]@np.array([[0,-1,0],[1,0,0],[0,0,1]])
    assert not proof(n)['certified']

def test_hinge_circulation_and_upper_right_coupling_cannot_be_bypassed(monkeypatch):
    import openswing.structured_static as module
    n=net();assert proof(n)['certified'];size=n.size
    # A dummy extra flow unknown lets both independent conditions be tested.
    n.size+=1;x=np.zeros(n.size)
    monkeypatch.setattr(n,'jacobian',lambda *args,**kw: np.zeros((n.size,n.size)))
    monkeypatch.setattr(module,'mechanical_rank_certificate',lambda *args,**kw:False)
    for d,b in [(np.zeros((1,1)),np.zeros((size,1))),(np.ones((1,1)),np.ones((size,1)))]:
        matrix=StructuredMatrix(csc_matrix(np.eye(size)),b,csc_matrix((1,size)),d)
        monkeypatch.setattr(module,'jacobian',lambda *args,**kw:(matrix,{}))
        with pytest.raises(AnalysisError,match='mechanism or redundant'):check_initial_rank(n,x)

def test_hinge_scoped_certificate_bypasses_only_mechanical_condition_gate(monkeypatch):
    import openswing.structured_static as module
    n=net();monkeypatch.setattr(module,'mechanical_rank_certificate',lambda *args,**kw:False)
    def forbidden(*args,**kw):raise AssertionError('unneeded full FD rank check')
    monkeypatch.setattr(n,'jacobian',forbidden)
    p=check_initial_rank(n,np.zeros(n.size));assert p['method']=='analytic rigid-tree rank certificate'
