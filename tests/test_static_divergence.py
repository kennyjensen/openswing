import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.linalg import eigvals

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from static_divergence import first_divergence


def test_scalar_pressure_condition_and_both_null_vectors_are_exact():
    result = first_divergence([[4.]],[[2.]],[[1.]],[[3.]],10.)
    assert result['pressure_ratio'] == pytest.approx(6.,abs=1e-14)
    assert result['speed'] == pytest.approx(10*np.sqrt(6),abs=1e-13)
    matrix = np.array([[4.,12.],[1.,3.]])
    np.testing.assert_allclose(matrix@result['right'],0.,atol=1e-14)
    np.testing.assert_allclose(matrix.T@result['left'],0.,atol=1e-14)
    expected = np.array([4*result['speed']/100*result['right'][1],0.])
    np.testing.assert_allclose(result['speed_action'],expected,atol=1e-14)


@pytest.mark.parametrize('complex_coordinates',[False,True])
def test_all_unknowns_match_the_full_generalized_pencil(complex_coordinates):
    a=np.array([[5.,1.,.2],[1.,4.,.3],[.2,.3,3.]])
    b=np.array([[1.,.2],[.3,1.],[.5,.4]])
    c=b.T.copy();d=np.array([[2.,.1],[.1,3.]])
    original=np.block([[a,np.zeros_like(b)],[c,d]])
    pressure=np.block([[np.zeros_like(a),b],[np.zeros_like(c),np.zeros_like(d)]])
    roots=eigvals(-original,pressure)
    expected=min(z.real for z in roots if np.isfinite(z) and z.real>0 and abs(z.imag)<1e-12)
    if complex_coordinates:
        # Exact invertible row/coordinate transformations preserve the roots.
        rows=np.diag([1.+2j,2.-1j,3.+1j]);coords=np.diag([.5-.3j,2.+1j,1.-.2j])
        flow_rows=np.diag([3.-1j,1.+2j]);flow_coords=np.diag([.4+.2j,2.-1j])
        a,b,c,d=rows@a@coords,rows@b@flow_coords,flow_rows@c@coords,flow_rows@d@flow_coords
    result=first_divergence(a,b,c,d,7.)
    assert result['pressure_ratio']==pytest.approx(expected,rel=1e-13)
    matrix=np.block([[a,expected*b],[c,d]])
    np.testing.assert_allclose(matrix@result['right'],0.,atol=2e-13)
    np.testing.assert_allclose(matrix.conj().T@result['left'],0.,atol=2e-13)
    assert result['right_backward_error']<1e-14 and result['left_backward_error']<1e-14


def test_no_positive_pressure_candidate_is_not_a_boundary():
    with pytest.raises(ValueError,match='No finite positive'):
        first_divergence([[4.]],[[-2.]],[[1.]],[[3.]],10.)


def test_singular_mechanical_block_is_not_regularized():
    with pytest.raises(RuntimeError,match='singular'):
        first_divergence([[0.]],[[2.]],[[1.]],[[3.]],10.)
