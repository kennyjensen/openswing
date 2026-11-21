"""Exact graph cardinality, finite augmenting paths and retained native-stall case."""
from functools import lru_cache
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csr_matrix,load_npz
from openswing.beam_matching import row_matching


def cardinality_by_assignments(graph):
    adjacency=graph.toarray().astype(bool)
    nr,nc=adjacency.shape
    @lru_cache(None)
    def assign(row,used):
        if row==nr:return 0
        possibilities=[assign(row+1,used)]
        for col in range(nc):
            if adjacency[row,col] and not used&(1<<col):
                possibilities.append(1+assign(row+1,used|(1<<col)))
        return max(possibilities)
    return assign(0,0)


def check(graph,expected=None):
    report={};match=row_matching(graph,diagnostics=report)
    np.testing.assert_array_equal(match,row_matching(graph))
    valid=match>=0
    assert match.shape==(graph.shape[0],)
    assert len(np.unique(match[valid]))==sum(valid)
    for row,col in enumerate(match):
        if col>=0:assert col in graph.indices[graph.indptr[row]:graph.indptr[row+1]]
    assert sum(valid)==(cardinality_by_assignments(graph) if expected is None else expected)
    assert report['edge_visits']<=graph.shape[0]*graph.nnz
    return match


def test_all_graphs_up_to_three_by_three_match_independent_assignments():
    for nr in range(4):
        for nc in range(4):
            for bits in range(1<<(nr*nc)):
                values=np.array([(bits>>i)&1 for i in range(nr*nc)]).reshape(nr,nc)
                check(csr_matrix(values))


def test_seeded_rectangular_graphs_match_independent_assignments():
    rng=np.random.default_rng(18291)
    for _ in range(400):
        nr,nc=rng.integers(0,9,size=2)
        check(csr_matrix(rng.random((nr,nc))<rng.uniform(.05,.95)))


@pytest.mark.parametrize('values',[
    [[1,1,0,0,0],[0,1,0,0,0],[0,0,0,1,0],[0,0,0,1,0]],
    [[1,1,0,0],[1,0,0,0],[0,1,1,0],[0,0,1,1]],
    [[0,0,0],[1,0,0],[0,0,0]],
])
def test_disconnected_augmenting_path_and_empty_row_column_graphs(values):
    check(csr_matrix(values))


def test_stored_zero_and_duplicate_unsorted_entries_remain_edges():
    check(csr_matrix((np.array([0.]),np.array([0]),np.array([0,1])),shape=(1,1)),1)
    check(csr_matrix((np.ones(4),np.array([1,0,1,0]),np.array([0,3,4])),shape=(2,3)),2)


def test_invalid_adjacency_is_rejected():
    bad=csr_matrix(np.eye(2));bad.indices[0]=3
    with pytest.raises(ValueError,match='valid CSR'):row_matching(bad)
    with pytest.raises(ValueError,match='CSR'):row_matching(csr_matrix(np.eye(2)).tocsc())


def test_original_ffwt_optional_elimination_stall_graph_completes_without_edge_loss():
    # Saved original-mesh Flare20 full-Newton zero-threshold CSR pattern.
    # Native matching stalled >71s; the matrix, controls and source pins live
    # in the independent FFWT diagnosis. No edge was dropped or threshold raised.
    graph=load_npz(Path(__file__).parent/'fixtures/ffwt-beam-matching-stall.npz')
    assert graph.shape==(1122,2226) and graph.nnz==10476
    assert graph.has_canonical_format and graph.has_sorted_indices
    check(graph,1122)
