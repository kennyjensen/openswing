import numpy as np
import pytest
from scipy.linalg import block_diag,qr,null_space,eigh
from openswing.linear_dynamics import eigensystem,finite_subspace

def match(modes,expected):
    from scipy.optimize import linear_sum_assignment
    actual=np.array([complex(*m['eigenvalue']) for m in modes]);expected=np.asarray(expected)
    assert len(actual)==len(expected)
    cost=abs(actual[:,None]-expected)/np.maximum(abs(expected),1.)
    a,b=linear_sum_assignment(cost)
    assert max(cost[a,b])<2e-6
    assert max(max(m['right_backward_error'],m['left_backward_error']) for m in modes)<1e-9

@pytest.mark.parametrize('index',[1,2,3,4,5,6])
@pytest.mark.parametrize('seed',[1,5,19])
def test_dense_orthogonal_mixtures_do_not_convert_infinite_chains_to_finite_modes(index,seed):
    finite=np.array([[0.,1.],[-49.,-.6]])
    nilpotent=np.diag(np.ones(index-1),1)
    a=block_diag(finite,-np.diag([2.,20.,200.]),np.eye(index),np.eye(index+1))
    m=block_diag(np.eye(5),nilpotent,np.diag(np.ones(index),1))
    rng=np.random.default_rng(seed);left=qr(rng.normal(size=a.shape))[0];right=qr(rng.normal(size=a.shape))[0]
    rows=10**rng.uniform(-3,3,len(a));columns=10**rng.uniform(-1,1,len(a))
    a=rows[:,None]*(left@a@right)*columns;m=rows[:,None]*(left@m@right)*columns
    modes,meta=eigensystem(a,m,count=100)
    assert meta['finite_dimension']==5
    match(modes,[*np.roots([1.,.6,49.]),-2.,-20.,-200.])

@pytest.mark.parametrize('stiffness',[1e4,1e7,1e9])
@pytest.mark.parametrize('seed',[2,11])
def test_all_modes_of_stiff_constrained_mechanics(stiffness,seed):
    n=8;rng=np.random.default_rng(seed)
    k=np.diag(np.geomspace(1.,stiffness,n))+3*np.ones((n,n));mass=np.diag(np.linspace(.3,2,n))
    g=np.array([[1,0,0,-1,0,0,0,0],[0,1,0,0,0,0,-1,0]],float)
    null=null_space(g);w=eigh(null.T@k@null,null.T@mass@null,eigvals_only=True)**.5
    a=np.block([[np.zeros((n,n)),np.eye(n),np.zeros((n,2))],[-k,np.zeros((n,n)),g.T],[g,np.zeros((2,n+2))]])
    m=block_diag(np.eye(n),mass,np.zeros((2,2)))
    # Fixed coordinates, exact equations and complete finite count are all
    # independent of the descriptor reduction being tested.
    rows=10**rng.uniform(-3,3,len(a));columns=10**rng.uniform(-1,1,len(a))
    a=rows[:,None]*a*columns;m=rows[:,None]*m*columns
    modes,meta=eigensystem(a,m,count=100,rank_tolerance=1e-12 if stiffness==1e9 else 1e-9)
    assert meta['finite_dimension']==2*(n-2)
    match(modes,np.r_[1j*w,-1j*w])
    for mode in modes:
        physical=columns*mode['right']
        assert np.linalg.norm(g@physical[:n])<1e-7*np.linalg.norm(physical[:n])
