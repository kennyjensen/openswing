"""Kernel equivalence at the solver's vector, quadrature and influence shapes."""
import numpy as np
import pytest
from openswing.vector_ops import cross3, dot3


def same_bits(a, b):
    before = (a.tobytes(), b.tobytes())
    with np.errstate(all='ignore'):
        expected, actual = np.cross(a, b), cross3(a, b)
    assert actual.shape == expected.shape
    assert actual.dtype == expected.dtype
    assert actual.tobytes() == expected.tobytes()
    assert before == (a.tobytes(), b.tobytes())


@pytest.mark.parametrize('dtype', [np.float32, np.float64, np.complex64,
                                   np.complex128, np.int16, np.int64, np.uint64])
def test_xyz_products_preserve_numpy_bits_across_solver_shapes(dtype):
    rng = np.random.default_rng(816)
    shapes = [((3,), (3,)), ((1,3), (3,)), ((24,3), (24,3)),
              ((48,3), (3,)), ((24,8,3), (24,1,3)),
              ((48,1,3), (1,48,3)), ((0,3), (3,)), ((2,0,3), (1,3))]
    for sa, sb in shapes:
        a = rng.integers(0, 13, size=sa).astype(dtype)
        b = rng.integers(0, 13, size=sb).astype(dtype)
        if np.issubdtype(dtype, np.inexact):
            a = a / dtype(7)
            b = b / dtype(11)
        if np.issubdtype(dtype, np.complexfloating):
            a = a + dtype(.37j)*a[..., ::-1]
            b = b - dtype(.29j)*b[..., ::-1]
        same_bits(a, b)


@pytest.mark.parametrize('left,right', [(np.float32,np.float64), (np.float32,np.complex64),
    (np.float64,np.complex64), (np.int64,np.uint64), (np.int16,np.float32),
    (np.uint64,np.complex128)])
def test_mixed_inputs_promote_before_component_arithmetic(left, right):
    a = np.array([[1,2,7], [3,9,5]], dtype=left)
    b = np.array([9,4,3], dtype=right)
    same_bits(a, b)


@pytest.mark.parametrize('layout', ['strided', 'fortran', 'readonly'])
def test_noncontiguous_and_shared_inputs_remain_unchanged(layout):
    a = np.arange(144., dtype=np.float64).reshape(24,6)[:,::2][::-1]
    b = np.arange(144., dtype=np.float64).reshape(24,6)[:,1::2]
    if layout == 'fortran':
        a, b = np.asfortranarray(a), np.asfortranarray(b)
    elif layout == 'readonly':
        b = np.broadcast_to(b[0], a.shape)
        a.setflags(write=False)
    same_bits(a, b)


@pytest.mark.parametrize('dtype', [np.float64, np.complex128])
def test_signed_zeros_and_nonfinite_values_keep_numpy_arithmetic(dtype):
    a = np.array([[0.,-0.,1.], [np.nan,np.inf,-np.inf], [-1.,-0.,0.]], dtype=dtype)
    same_bits(a, a[::-1])


@pytest.mark.parametrize('dtype', [np.int8,np.int64,np.uint64])
def test_integer_overflow_preserves_numpy_dtype_and_bits(dtype):
    limits = np.iinfo(dtype)
    a = np.array([limits.min,limits.max,1], dtype=dtype)
    b = np.array([limits.max,1,limits.min], dtype=dtype)
    same_bits(a, b)


@pytest.mark.parametrize('a,b', [(np.array(1), np.ones(3)), (np.ones(2),np.ones(3)),
    (np.ones(4),np.ones(3)), (np.ones((2,3)),np.ones((4,3)))])
def test_xyz_contract_rejects_incompatible_shapes(a, b):
    with pytest.raises(ValueError):
        cross3(a, b)


def test_boolean_subtraction_is_not_silently_redefined():
    with pytest.raises(TypeError):
        cross3(np.ones(3, dtype=bool), np.ones(3, dtype=bool))


@pytest.mark.parametrize('dtype', [np.float16,np.float32,np.float64,np.complex128,np.int16,np.int64,np.uint64,np.bool_])
def test_dot_preserves_numpy_reduction_values_dtype_and_input_arrays(dtype):
    rng=np.random.default_rng(763)
    for sa,sb in [((3,),(3,)),((24,8,3),(24,1,3)),((72,1,3),(1,72,3)),((0,3),(3,))]:
        a=rng.integers(-13,14,size=sa).astype(dtype)
        b=rng.integers(-13,14,size=sb).astype(dtype)
        if np.issubdtype(dtype,np.inexact):a=a/dtype(7);b=b/dtype(11)
        before=a.tobytes(),b.tobytes()
        with np.errstate(all='ignore'):expected=np.sum(a*b,axis=-1);actual=dot3(a,b)
        assert actual.dtype==expected.dtype
        assert actual.tobytes()==expected.tobytes()
        assert before==(a.tobytes(),b.tobytes())


@pytest.mark.parametrize('layout',['strided','fortran','readonly'])
def test_dot_handles_layout_and_mixed_precision_without_mutation(layout):
    rng=np.random.default_rng(183)
    a=rng.normal(size=(72,6))[:,::2][::-1]
    b=rng.normal(size=a.shape).astype(np.float32)
    if layout=='fortran':a,b=np.asfortranarray(a),np.asfortranarray(b)
    if layout=='readonly':a=np.broadcast_to(a[0],b.shape);b.setflags(write=False)
    before=a.tobytes(),b.tobytes();expected=np.sum(a*b,axis=-1);actual=dot3(a,b)
    assert actual.dtype==expected.dtype and actual.tobytes()==expected.tobytes()
    assert before==(a.tobytes(),b.tobytes())


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
def test_dot_retains_signed_zero_and_nonfinite_behavior(dtype):
    a=np.array([[-0.,-0.,-0.],[-0.,0.,1.],[np.nan,np.inf,-np.inf]],dtype=dtype)
    with np.errstate(all='ignore'):expected=np.sum(a*a[::-1],axis=-1);actual=dot3(a,a[::-1])
    np.testing.assert_array_equal(actual,expected)
    np.testing.assert_array_equal(np.signbit(actual[np.isfinite(actual)]),np.signbit(expected[np.isfinite(expected)]))
