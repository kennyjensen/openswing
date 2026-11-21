"""Check exact sparse corrections and narrowly scoped allocation recovery."""
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.linalg import solve
from scipy.sparse import csc_matrix
from openswing.sparse_newton import SparseNewtonFactor,memory_bounded_newton_factor
from openswing.harmonic_structure import StructureUnavailable
from openswing.structured_static import block_solve
from test_newton_structure import fixture


@pytest.mark.parametrize('example,frame,extra',[
    ('flexible','prescribed',{}),('wing-body','free',{'ground_effect':1}),
    ('torsion-joint','prescribed',{}),('powered','mixed',{'powers':{1:30}})])
def test_original_coupled_matrix_and_multiple_rhs(example,frame,extra):
    n,x=fixture(example,frame,extra)
    original=n.jacobian(x,.6);matrix=csc_matrix(original)
    factor=SparseNewtonFactor(n,matrix)
    for rhs in [n.residual(x,.6),*np.random.default_rng(819).normal(size=(2,n.size))]:
        actual=block_solve(matrix,rhs,factorization=factor)
        np.testing.assert_allclose(actual,solve(original,rhs),rtol=1e-8,atol=1e-8)
        assert np.max(abs(original@actual-rhs))<=1e-8*max(1.,np.max(abs(rhs)))
    np.testing.assert_array_equal(matrix.toarray(),original)
    assert not matrix.data.flags.writeable
    with pytest.raises(ValueError,match='different matrix'):
        block_solve(csc_matrix(original),rhs,factorization=factor)


def test_only_allocation_failure_enters_sparse_recovery(monkeypatch):
    import openswing.newton_structure as beam
    n=SimpleNamespace(size=3);matrix=csc_matrix([[2.,1.,0.],[0.,3.,1.],[1.,0.,4.]])
    sentinel=object()
    monkeypatch.setattr(beam,'NewtonBeamFactor',lambda *args,**kwargs:sentinel)
    assert memory_bounded_newton_factor(n,matrix) is sentinel
    def unavailable(*args,**kwargs):raise StructureUnavailable('original numerical gate')
    monkeypatch.setattr(beam,'NewtonBeamFactor',unavailable)
    with pytest.raises(StructureUnavailable,match='original numerical gate'):
        memory_bounded_newton_factor(n,matrix)
    def exhausted(*args,**kwargs):raise MemoryError('allocation failure')
    monkeypatch.setattr(beam,'NewtonBeamFactor',exhausted)
    factor=memory_bounded_newton_factor(n,matrix)
    rhs=np.array([1.,-2.,3.])
    np.testing.assert_allclose(matrix@factor.solve(rhs),rhs,rtol=1e-12,atol=1e-12)


def test_invalid_and_corrupted_factors_do_not_pass(monkeypatch):
    n=SimpleNamespace(size=3);matrix=csc_matrix(np.diag([1.,2.,3.]))
    with pytest.raises(StructureUnavailable,match='storage budget'):
        SparseNewtonFactor(n,matrix,byte_budget=1)
    with pytest.raises(RuntimeError):
        SparseNewtonFactor(n,csc_matrix(np.zeros((3,3))))
    factor=SparseNewtonFactor(n,matrix)
    factor.factor=SimpleNamespace(solve=lambda rhs:np.zeros_like(rhs))
    with pytest.raises(StructureUnavailable,match='full-equation residual'):
        factor.solve(np.ones(3))
    with pytest.raises(StructureUnavailable,match='finite real'):
        factor.solve(np.array([1.,np.nan,3.]))


def test_production_recovers_allocation_failure_without_changing_equilibrium(monkeypatch):
    import openswing.newton_structure as beam
    import openswing.structured_static as static
    control,_=fixture('flexible','prescribed',{},panels=24)
    candidate,_=fixture('flexible','prescribed',{},panels=24)
    assert candidate.size>256
    expected,steps=static.equilibrate(control)
    original=static.block_solve;forced=[];failures=[]
    def force_full(matrix,rhs,*args,**kwargs):
        if not forced:
            forced.append(True)
            raise ValueError('deliberate approximate-direction failure')
        return original(matrix,rhs,*args,**kwargs)
    def exhausted(*args,**kwargs):
        failures.append(True)
        raise MemoryError('deliberate beam allocation failure')
    monkeypatch.setattr(static,'block_solve',force_full)
    monkeypatch.setattr(beam,'NewtonBeamFactor',exhausted)
    actual,actual_steps=static.equilibrate(candidate)
    assert forced and failures and actual_steps==steps
    assert any(r.get('full_structure',{}).get('method')==
               'exact sparse full-Newton LU after beam allocation failure'
               for r in candidate.structured_iterations)
    assert np.max(abs(candidate.residual(actual)))<=1e-12
    np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=2e-9)
    assert candidate.iteration_fields is None and candidate.tangent_influences is None
