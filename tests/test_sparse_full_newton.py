"""Storage-only full Newton assembly keeps every physical matrix entry."""
import numpy as np
import pytest
from scipy.sparse import csc_matrix,isspmatrix_csc
from scipy.linalg import solve
from openswing.newton_structure import NewtonBeamFactor
from test_newton_structure import fixture


CASES=[('flexible','prescribed',{},.6),
       ('wing-body','free',{'ground_effect':1},.37),
       ('torsion-joint','prescribed',{},.8),
       ('powered','mixed',{'powers':{1:30}},.5),
       ('dae','prescribed',{},.25)]


def same_sparse(actual,expected):
    assert isspmatrix_csc(actual)
    expected=csc_matrix(expected);expected.eliminate_zeros();expected.sort_indices()
    for key in ['data','indices','indptr']:
        np.testing.assert_array_equal(getattr(actual,key),getattr(expected,key))


@pytest.mark.parametrize('example,frame,extra,factor',CASES)
def test_complete_sparse_matrix_is_exactly_the_dense_control(example,frame,extra,factor):
    n,x=fixture(example,frame,extra);control,y=fixture(example,frame,extra)
    progress=[];actual=n.jacobian(x,factor,_sparse=True,progress=lambda *args:progress.append(args))
    expected=control.jacobian(y,factor)
    same_sparse(actual,expected)
    assert n.nfev==control.nfev
    assert progress[0]==('static_tangent',0,n.size)
    assert progress[-1]==('static_tangent',n.size,n.size)
    assert n.iteration_fields is None and n.tangent_influences is None
    factorization=NewtonBeamFactor(n,actual)
    assert factorization.matrix is actual
    assert not any(v.flags.writeable for v in (actual.data,actual.indices,actual.indptr))
    rhs=n.residual(x,factor)
    value=factorization.solve(rhs)
    np.testing.assert_allclose(value,solve(expected,rhs),rtol=1e-8,atol=1e-10)
    assert np.max(abs(actual@value-rhs))<1e-8*max(1.,np.max(abs(rhs)))


@pytest.mark.parametrize('fallback',['geometry','circulation','mechanics-grouped','mechanics-individual','residual-options'])
def test_sparse_fallbacks_preserve_every_dense_column(fallback,monkeypatch):
    import openswing.geometry_tangent as geometry
    import openswing.circulation_tangent as circulation
    import openswing.mechanical_tangent as mechanics
    example='torsion-joint' if fallback=='mechanics-individual' else 'wing-body'
    n,x=fixture(example,'prescribed',{});control,y=fixture(example,'prescribed',{})
    options={}
    if fallback=='geometry':
        def unavailable(*args,**kwargs):raise geometry.GeometryDerivativeUnavailable('forced geometry fallback')
        monkeypatch.setattr(geometry,'geometry_columns',unavailable)
    elif fallback=='circulation':
        def unavailable(*args,**kwargs):raise circulation.CirculationDerivativeUnavailable('forced circulation fallback')
        monkeypatch.setattr(circulation,'circulation_columns',unavailable)
    elif fallback.startswith('mechanics'):
        def unavailable(*args,**kwargs):raise mechanics.MechanicalDerivativeUnavailable('forced mechanical fallback')
        monkeypatch.setattr(mechanics,'network_mechanical_columns',unavailable)
    else:options=dict(gravity_override=n.gravity)
    actual=n.jacobian(x,.4,_sparse=True,**options)
    expected=control.jacobian(y,.4,**options)
    same_sparse(actual,expected)
    assert n.nfev==control.nfev
    assert n.iteration_fields is None and n.tangent_influences is None


def test_sparse_assembly_does_not_allocate_a_full_dense_matrix(monkeypatch):
    import openswing.network as network
    n,x=fixture('flexible','prescribed',{})
    original=network.np.zeros
    def bounded(shape,*args,**kwargs):
        assert not isinstance(shape,tuple) or shape!=(n.size,n.size),'Dense full Newton allocation'
        return original(shape,*args,**kwargs)
    monkeypatch.setattr(network.np,'zeros',bounded)
    assert isspmatrix_csc(n.jacobian(x,.6,_sparse=True))
