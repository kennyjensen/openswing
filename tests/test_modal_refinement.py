"""Full-pencil refinement against known oscillators and an algebraic constraint."""
import numpy as np
import pytest
from scipy.sparse import csc_matrix

from openswing.modal_refinement import bordered_matrix, refine_simple_pair


@pytest.mark.parametrize('n', [2, 5, 9])
@pytest.mark.parametrize('complex_coordinates', [False, True])
def test_border_is_derivative_of_full_eigen_equations_at_every_pivot(n, complex_coordinates):
    rng = np.random.default_rng(41+n)
    a, m = rng.normal(size=(2, n, n))
    a[abs(a) < .7] = 0
    m[abs(m) < .7] = 0
    # Include empty columns and algebraic rows; the pole border can be complex
    # even when the pencil itself is real.
    a[:, 0] = m[:, 0] = 0
    m[-1, :] = 0
    value = .3
    v = rng.normal(size=n)
    direction = rng.normal(size=n+1)
    if complex_coordinates:
        v = v+1j*rng.normal(size=n)
        direction = direction+1j*rng.normal(size=n+1)
    rows = np.geomspace(.01, 100., n)
    aa, mm = csc_matrix(a), csc_matrix(m)
    for pivot in range(n):
        border = bordered_matrix(aa, mm, value, m@v, rows, pivot)
        assert border.has_sorted_indices

        def residual(step):
            state = v+step*direction[:-1]
            pole = value+step*direction[-1]
            return np.r_[(a@state-pole*(m@state))/rows, state[pivot]-v[pivot]]

        h = 1e-4
        expected = (residual(h)-residual(-h))/(2*h)
        np.testing.assert_allclose(border@direction, expected, rtol=2e-10, atol=2e-10)
    np.testing.assert_array_equal(aa.toarray(), a)
    np.testing.assert_array_equal(mm.toarray(), m)


def test_zero_mass_action_leaves_only_normalization_in_the_border():
    a = csc_matrix([[0., 0.], [0., 2.]])
    m = csc_matrix((2, 2))
    actual = bordered_matrix(a, m, 0., np.zeros(2), np.array([1., 2.]), 0)
    np.testing.assert_array_equal(actual.toarray(), [[0., 0., 0.], [0., 1., 0.], [1., 0., 0.]])


@pytest.mark.parametrize('complex_coordinates',[False,True])
def test_inaccurate_pair_recovers_known_root_shape_and_checked_adjoint(complex_coordinates):
    omega=205.
    a=np.array([[0,1,0,0,0],[-.35**2,0,0,0,0],
        [0,0,0,1,0],[0,0,-omega**2,0,0],[0,0,1,2,-1]],dtype=complex)
    m=np.diag([1.,1.,1.,1.,0.]).astype(complex)
    coordinates=np.array([1.,.01,.001,4.,2.],dtype=complex)
    rows=np.array([1e4,.1,30.,1e-4,2.],dtype=complex)
    if complex_coordinates:
        coordinates*=np.exp(1j*np.linspace(.2,1.,5))
        rows*=np.exp(-1j*np.linspace(.1,.8,5))
    a,m=csc_matrix(rows[:,None]*a*coordinates),csc_matrix(rows[:,None]*m*coordinates)
    expected=np.array([0.,0.,1.,1j*omega,1+2j*omega])/coordinates
    expected/=expected[np.argmax(abs(expected))]
    seed=expected+1e-9*np.array([.3j,.2,1j,-.4j,.1])
    value,v,left,report=refine_simple_pair(a,m,1j*omega*(1+1e-9)+5e-10,seed)
    assert report['status']=='REFINED' and report['corrections']>0
    assert report['left_reused'] and left is not None
    assert abs(value-1j*omega)<1e-11
    np.testing.assert_allclose(v,expected,atol=2e-12,rtol=2e-12)
    assert np.linalg.norm(a@v-value*(m@v))<1e-8
    assert np.linalg.norm(a.conj().T@left-value.conjugate()*(m.conj().T@left))<1e-7
    assert np.vdot(left,m@v)==pytest.approx(1.,abs=1e-12)


def test_exact_pair_does_not_factor_or_change_the_root():
    a=csc_matrix(np.diag([2.,3.,4.]))
    m=csc_matrix(np.eye(3))
    value,v,left,report=refine_simple_pair(a,m,2.,[1.,0.,0.])
    assert value==2. and left is None and report['factorizations']==0
    np.testing.assert_array_equal(v,[1.,0.,0.])


def test_nonlocal_correction_is_rejected_without_changing_the_pair():
    a=csc_matrix(np.diag([2.,3.,4.]))
    m=csc_matrix(np.eye(3))
    value,v,left,report=refine_simple_pair(a,m,2.1,[1.,0.,0.])
    assert value==2.1 and left is None
    assert report['reason']=='nonlocal_or_nonfinite_correction'
    np.testing.assert_array_equal(v,[1.,0.,0.])


@pytest.mark.parametrize('reject_second',[False,True])
def test_refinement_releases_each_factor_and_keeps_last_accepted_adjoint(monkeypatch,reject_second):
    import weakref
    import openswing.modal_refinement as refinement
    original=refinement.splu
    live=weakref.WeakSet()
    calls=[]

    class TrackedFactor:
        def __init__(self,matrix):
            self.factor=original(matrix)
            self.index=len(calls)
            calls.append(self.index)
            live.add(self)

        def solve(self,rhs,**kwargs):
            if reject_second and self.index==1 and kwargs.get('trans','N')=='N':
                return np.zeros_like(rhs)
            return self.factor.solve(rhs,**kwargs)

    def factor(matrix):
        assert not live, 'A previous LU is still retained during the next allocation'
        return TrackedFactor(matrix)

    monkeypatch.setattr(refinement,'splu',factor)
    a=csc_matrix(np.diag([2.,3.]));m=csc_matrix(np.eye(2))
    value,v,left,report=refine_simple_pair(a,m,2.+1e-8,[1.,1e-3])
    assert len(calls)==2 and not live
    assert value==pytest.approx(2.,abs=1e-14)
    assert report['corrections']==(1 if reject_second else 2)
    assert report['left_reused'] and left is not None
    np.testing.assert_allclose(v,[1.,0.],atol=2e-11 if reject_second else 1e-14)
    np.testing.assert_allclose(a.conj().T@left-value.conjugate()*(m.conj().T@left),0.,atol=1e-12)
    assert np.vdot(left,m@v)==pytest.approx(1.,abs=1e-12)
