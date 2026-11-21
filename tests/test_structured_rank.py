"""Sparse zero-load rank checks, including inconclusive and singular cases."""
from pathlib import Path
import numpy as np
import pytest
from scipy.sparse import csc_matrix
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, AnalysisError
from openswing.network import StaticNetwork
from openswing.structured_static import mechanical_rank_certificate, check_initial_rank


def test_certificate_is_conservative_for_ill_conditioned_and_singular_blocks():
    assert mechanical_rank_certificate(csc_matrix([[2.,1.],[0.,3.]]))
    assert not mechanical_rank_certificate(csc_matrix([[1.,1.],[0.,1e-12]]))
    assert not mechanical_rank_certificate(csc_matrix([[1.,1.],[0.,0.]]))


@pytest.mark.parametrize('ground', ['1 0 1', '1 0 0\n1 0 0'])
def test_coupled_mechanisms_and_redundant_reactions_are_rejected(ground):
    source = Path('examples/rectangular.asw').read_text()
    model = parse_asw(source)
    model.records['ground'] = [[float(v) for v in row.split()] for row in ground.splitlines()]
    net = StaticNetwork(model, 4, FlightCondition(), None, [])
    with pytest.raises(AnalysisError, match='mechanism or redundant'):
        check_initial_rank(net, np.zeros(net.size))


def test_inconclusive_certificate_uses_exact_full_check(monkeypatch):
    import openswing.structured_static as module
    model = parse_asw(Path('examples/flexible.asw').read_text())
    net = StaticNetwork(model, 4, FlightCondition(), None, [])
    monkeypatch.setattr(module, 'mechanical_rank_certificate', lambda matrix: False)
    monkeypatch.setattr(module, 'mechanical_svd_certificate', lambda matrix, **kwargs: dict(certified=False))
    report = check_initial_rank(net, np.zeros(net.size))
    assert report['method'] == 'full-Jacobian SVD fallback'


def test_inconclusive_bound_uses_existing_block_before_full_physics(monkeypatch):
    import openswing.structured_static as module
    model = parse_asw(Path('examples/flexible.asw').read_text())
    net = StaticNetwork(model, 4, FlightCondition(), None, [])
    monkeypatch.setattr(module, 'mechanical_rank_certificate', lambda matrix: False)
    def forbidden(*args, **kwargs):
        pytest.fail('Rank certification must reuse the existing mechanical block')
    monkeypatch.setattr(net, 'jacobian', forbidden)
    report, matrix = check_initial_rank(net, np.zeros(net.size), retain_matrix=True)
    assert report['method'] == 'block-triangular SVD certificate'
    assert report['mechanical_svd']['singular_ratio'] >= 1e-10
    assert matrix.mechanical.shape == (net.gamma_start, net.gamma_start)
