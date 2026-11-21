"""Dense fixed-Jacobian reuse, diagnostics, and actual driver invalidation."""
from pathlib import Path
import json, warnings
import numpy as np
import pytest
from scipy.linalg import solve, LinAlgWarning
from scipy.sparse import csc_matrix
import openswing.structured_static as ss
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.equilibrium_state import capture

FIXTURES=Path(__file__).resolve().parent/'fixtures'/'hinge-history'

def count_lapack(monkeypatch):
    original=ss.get_lapack_funcs;counts={}
    def factory(names,*args,**kw):
        result=original(names,*args,**kw)
        def wrap(name,f):
            def call(*a,**k):
                counts[name]=counts.get(name,0)+1
                return f(*a,**k)
            return call
        return tuple(wrap(name,f) for name,f in zip(names,result))
    monkeypatch.setattr(ss,'get_lapack_funcs',factory)
    return counts

@pytest.mark.parametrize('sparse',[False,True])
def test_many_rhs_one_factor_and_matrix_snapshot(monkeypatch,sparse):
    rng=np.random.default_rng(10215);a=rng.normal(size=(37,37))+20*np.eye(37)
    original=a.copy();matrix=csc_matrix(a) if sparse else a
    counts=count_lapack(monkeypatch);factor=ss.DenseNewtonFactor(matrix)
    for rhs in rng.normal(size=(13,37)):
        saved=rhs.copy();actual=factor.solve(rhs)
        np.testing.assert_allclose(actual,solve(original,rhs),atol=2e-14,rtol=2e-13)
        np.testing.assert_array_equal(rhs,saved)
        assert max(abs(original@actual-rhs))<2e-14
    assert counts['getrf']==counts['gecon']==1 and counts['getrs']==13
    assert factor.report['solves']==13 and not factor.report['ill_conditioned']
    np.testing.assert_array_equal(matrix.toarray() if sparse else matrix,original)
    # Factors own their snapshot, so LAPACK never aliases or overwrites input.
    if sparse:matrix.data[:]=0
    else:matrix[:]=0
    rhs=np.ones(37)
    np.testing.assert_allclose(factor.solve(rhs),solve(original,rhs),atol=2e-14)

@pytest.mark.parametrize('small',[1e-14,3e-16,1e-16,1e-18])
def test_condition_warning_matches_installed_general_dense_solve(small):
    # Non-symmetric and non-triangular, with a controlled small singular scale.
    a=np.array([[1.,2.,3.],[4.,5.,6.],[7.,8.,10.]])@np.diag([1.,1.,small])
    rhs=np.array([1.,2.,-3.])
    with warnings.catch_warnings(record=True) as old:
        warnings.simplefilter('always');expected=solve(a,rhs,assume_a='gen')
    factor=ss.DenseNewtonFactor(a)
    with warnings.catch_warnings(record=True) as new:
        warnings.simplefilter('always');actual=factor.solve(rhs);factor.solve(rhs*.25)
    ill=any(issubclass(w.category,LinAlgWarning) for w in old)
    assert len(new)==(2 if ill else 0)
    assert factor.report['ill_conditioned']==ill
    np.testing.assert_allclose(actual,expected,atol=0,rtol=3e-15)
    if ill:
        with warnings.catch_warnings():
            warnings.simplefilter('error',LinAlgWarning)
            with pytest.raises(LinAlgWarning,match='rcond'):factor.solve(rhs)

@pytest.mark.parametrize('version,scale',[('1.14.1',.5),('1.16.3',.5),('1.17.0',1.)])
def test_scipy_warning_policy_compatibility(monkeypatch,version,scale):
    monkeypatch.setattr(ss,'scipy_version',version)
    factor=ss.DenseNewtonFactor(np.eye(3))
    assert factor.report['warning_threshold']==np.finfo(float).eps*scale

@pytest.mark.parametrize('matrix',[np.zeros((3,3)),np.array([[1.,2.],[2.,4.]])])
def test_singular_factor_is_error_not_a_retained_warning(matrix):
    with pytest.raises(np.linalg.LinAlgError):solve(matrix,np.ones(len(matrix)))
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        with pytest.raises(np.linalg.LinAlgError,match='singular'):ss.DenseNewtonFactor(matrix)

@pytest.mark.parametrize('matrix',[np.full((2,2),np.nan),np.full((2,2),np.inf),np.ones((2,3)),np.eye(2)*1j])
def test_invalid_matrix_rejected(matrix):
    with pytest.raises(ValueError):ss.DenseNewtonFactor(matrix)

@pytest.mark.parametrize('rhs',[np.ones(4),[np.nan,1,2],[np.inf,1,2],[1j,2,3]])
def test_invalid_rhs_does_not_invoke_lapack(monkeypatch,rhs):
    counts=count_lapack(monkeypatch);factor=ss.DenseNewtonFactor(np.eye(3))
    with pytest.raises(ValueError):factor.solve(rhs)
    assert counts.get('getrs',0)==0 and factor.report['solves']==0

@pytest.mark.parametrize('failure',['getrf_negative','getrf_singular','gecon_negative','getrs_negative'])
def test_lapack_failure_propagates_and_new_factor_is_independent(monkeypatch,failure):
    original=ss.get_lapack_funcs
    def factory(names,*args,**kwargs):
        result=list(original(names,*args,**kwargs));name,kind=failure.split('_')
        index=names.index(name);real=result[index]
        def fail(*a,**k):
            output=list(real(*a,**k));output[-1]=1 if kind=='singular' else -1;return tuple(output)
        result[index]=fail;return tuple(result)
    with monkeypatch.context() as m:
        m.setattr(ss,'get_lapack_funcs',factory)
        with pytest.raises(np.linalg.LinAlgError if 'singular' in failure else ValueError):
            ss.DenseNewtonFactor(np.eye(3)).solve(np.ones(3))
    np.testing.assert_array_equal(ss.DenseNewtonFactor(2*np.eye(3)).solve(np.ones(3)),[.5]*3)

@pytest.mark.parametrize('failed_first',[False,True])
def test_real_hinge_driver_discards_dense_factors_at_each_rebuild_and_stage(monkeypatch,failed_first,tmp_path):
    model=parse_asw((FIXTURES/'source'/'dead-couple.asw').read_text())
    net=StaticNetwork(model,4,None,[0,0,0],[dict(beam=2,t=2,moment=[24.,0,0])])
    # Force the existing fallback, leaving every physical equation unchanged.
    def no_block(*a,**k):raise ValueError('injected approximate factor failure')
    monkeypatch.setattr(ss,'BlockFactorization',no_block)
    original=net.jacobian;matrices=[]
    def jacobian(*a,**kw):
        matrix=original(*a,**kw)
        if failed_first and not matrices:matrix=np.zeros_like(matrix)
        matrices.append(matrix);return matrix
    monkeypatch.setattr(net,'jacobian',jacobian)
    counts=count_lapack(monkeypatch)
    x,steps=ss.equilibrate(net,full_structure=False)
    assert max(abs(net.residual(x)))<=1e-12
    np.testing.assert_allclose(capture(net,x)['hinge_charts'][0]['angle_rad'],np.deg2rad(24),atol=2e-12)
    rows=net.structured_iterations;reports=[r['full_dense'] for r in rows if 'full_dense' in r]
    assert len(matrices)==counts['getrf']>steps>=4
    assert len(reports)==len(matrices)-int(failed_first)
    assert all(r['factorizations']==1 and 1<=r['solves']<=13 for r in reports)
    assert sum(r['solves'] for r in reports)==counts['getrs']>counts['getrf']
    assert any(not r['accepted'] for r in net.continuation_diagnostics)
    assert all(not r['matrix_reused'] for r in rows)
    failures=[r['full_dense_failure'] for r in rows if 'full_dense_failure' in r]
    assert bool(failures)==failed_first
    if failed_first:assert 'singular' in failures[0]
    (tmp_path/f'driver-{failed_first}.json').write_text(json.dumps(dict(counts=counts,steps=steps,
        residual=float(max(abs(net.residual(x)))),iterations=rows,continuation=net.continuation_diagnostics),indent=2)+'\n')
