"""Independent exhaustive matchings and real pathological beam graph."""
from functools import lru_cache
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix,csc_matrix,coo_matrix
from openswing.sparse_rank import structural_rank


def exhaustive_rank(pattern):
    @lru_cache(None)
    def visit(row,used):
        if row==len(pattern):return 0
        return max([visit(row+1,used)]+[1+visit(row+1,used|1<<int(column))
            for column in np.flatnonzero(pattern[row]) if not used&(1<<int(column))])
    return visit(0,0)


@pytest.mark.parametrize('format',[csr_matrix,csc_matrix,coo_matrix])
def test_matching_equals_exhaustive_rank_on_square_rectangular_and_empty_graphs(format):
    rng=np.random.default_rng(717)
    for nr in range(7):
        for nc in range(7):
            for density in [.1,.5,.9]:
                pattern=rng.random((nr,nc))<density
                matrix=format(pattern.astype(float))
                assert structural_rank(matrix)==exhaustive_rank(pattern)


def test_explicit_zeros_and_duplicate_cancellation_are_not_nonzero_edges():
    matrix=csr_matrix((np.array([1.,-1.,0.,2.]),np.array([0,0,1,1]),np.array([0,3,4])),shape=(2,2))
    before=(matrix.data.copy(),matrix.indices.copy(),matrix.indptr.copy())
    assert structural_rank(matrix)==1
    for actual,expected in zip((matrix.data,matrix.indices,matrix.indptr),before):
        np.testing.assert_array_equal(actual,expected)


def test_transient_wing_48_panel_graph_has_complete_independent_witness():
    from openswing.sparse_rank import maximum_matching
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.structured_static import jacobian,mechanical_rank_certificate
    n=StaticNetwork(parse_asw(Path('examples/transient-wing.asw').read_text()),48,FlightCondition(speed=20,alpha=3,mach=.1),None,[])
    matrix,counts=jacobian(n,np.zeros(n.size),0.)
    a=matrix.mechanical
    assert structural_rank(a)==a.shape[0]
    # Independently inspect the returned witness, then the numerical certificate.
    matched=maximum_matching(a)
    assert len(set(matched))==a.shape[0] and min(matched)>=0
    assert np.all(np.asarray(a[np.arange(len(matched)),matched]).ravel()!=0)
    assert mechanical_rank_certificate(a)
