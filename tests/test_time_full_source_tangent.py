"""Complete source time matrices and Newton fallback against full stencils."""
from copy import deepcopy
import numpy as np
import pytest

from openswing.time_integration import full_tangent, newton, bdf_coefficients
from openswing.time_tangent import attach_mechanical_columns
from openswing.mechanical_tangent import MechanicalDerivativeUnavailable
from test_time_source_mechanical_columns import setup


def problem(previous_step=.013, signal='rx[1]'):
    system, previous=setup(signal)
    older=None if previous_step is None else deepcopy(previous)
    if older is not None:older.time=-previous_step
    coefficients=bdf_coefficients(.017,previous_step)
    values=system.guess(previous,.017)
    values+=np.random.default_rng(112).normal(0,1e-5,len(values))
    calls=[]
    def residual(x,data=None):
        calls.append(x.copy())
        return system.residual(x,previous,older,.017,coefficients,
            **({} if data is None else dict(_mechanical_data=data[0])))
    attach_mechanical_columns(system,residual,lambda x,data:residual(x,data))
    return residual,values,calls


@pytest.mark.parametrize('previous_step',[None,.013])
def test_complete_bdf_matrix_matches_independent_stencils_and_skips_only_load_columns(previous_step):
    f,x,calls=problem(previous_step)
    base=f(x).copy();indices,block=f.direct_mechanical_columns(x)
    calls.clear();actual=full_tangent(f,x,base)
    assert len(calls)==len(x)-len(indices)+1  # one physical capture
    raw=np.empty_like(actual)
    for j in range(len(x)):
        h=1e-6*max(1.,abs(x[j]));trial=x.copy();trial[j]+=h
        raw[:,j]=(f(trial)-base)/h
    remaining=np.setdiff1d(np.arange(len(x)),indices)
    np.testing.assert_array_equal(actual[:,remaining],raw[:,remaining])
    np.testing.assert_allclose(actual[:,indices],raw[:,indices],rtol=2e-6,atol=2e-8)
    # Independent centered probes resolve the analytical columns more tightly.
    for j in indices:
        h=3e-6*max(1.,abs(x[j]));delta=np.zeros_like(x);delta[j]=h
        expected=(f(x+delta)-f(x-delta))/(2*h)
        np.testing.assert_allclose(actual[:,j],expected,rtol=2e-8,atol=2e-8)
    np.testing.assert_array_equal(f(x),base)


def test_unavailable_mechanics_keeps_original_full_matrix_exactly():
    f,x,_=problem();base=f(x)
    expected=full_tangent(f,x,base,direct_mechanics=False)
    def unavailable(x):raise MechanicalDerivativeUnavailable('unsupported hinge branch')
    f.direct_mechanical_columns=unavailable
    np.testing.assert_array_equal(full_tangent(f,x,base),expected)


def test_load_measurement_feedback_keeps_full_coupled_columns():
    f,x,calls=problem(signal='Ms[1]')
    assert not hasattr(f,'direct_mechanical_columns')
    base=f(x);calls.clear();actual=full_tangent(f,x,base)
    assert len(calls)==len(x)
    np.testing.assert_array_equal(actual,full_tangent(f,x,base,direct_mechanics=False))


def test_failed_sparse_builder_uses_complete_source_columns_in_newton(monkeypatch):
    import openswing.time_integration as time
    from scipy.sparse import csc_matrix
    # Coupled nonlinear equations with a known root; coordinate 1 is linear.
    def f(x):return np.array([x[0]**2+x[1]-5, x[0]+2*x[1]-4])
    def sparse(x):raise ValueError('deliberate sparse failure')
    f.factorization_builder=sparse
    called=[]
    def columns(x):
        called.append(True)
        return np.array([1]),csc_matrix([[1.],[2.]])
    f.direct_mechanical_columns=columns
    actual,_,_,_=newton(f,np.array([1.8,1.1]),1e-12)
    assert called
    np.testing.assert_allclose(actual,[2.,1.],atol=1e-12,rtol=0)
    assert max(abs(f(actual)))<=1e-12
