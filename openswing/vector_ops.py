"""Small vector operations for the solver's last-axis xyz arrays."""
import numpy as np


def dot3(a, b):
    """Last-axis xyz dot product without a three-component reduction array.

    Geometry uses real float32/float64 arrays. Add their three products in
    the same order as a short NumPy sum. Other dtypes retain NumPy's reduction
    rules, including widened integer and half-precision accumulation.
    """
    a, b = np.asarray(a), np.asarray(b)
    if a.ndim < 1 or b.ndim < 1 or a.shape[-1] != 3 or b.shape[-1] != 3:
        raise ValueError('dot3 requires arrays with a final dimension of three')
    dtype = np.result_type(a, b)
    if dtype not in (np.dtype('float32'), np.dtype('float64')):
        return np.sum(a*b, axis=-1)
    # NumPy initializes its short reduction with positive zero.
    return ((a[..., 0]*b[..., 0]+0)+a[..., 1]*b[..., 1])+a[..., 2]*b[..., 2]


def cross3(a, b):
    """Cross product of xyz arrays with NumPy dtype promotion and broadcasting.

    Every vector has exactly three components on the final axis. Products and
    differences retain the order of ``np.cross``; inputs are never modified.
    """
    a, b = np.asarray(a), np.asarray(b)
    if a.ndim < 1 or b.ndim < 1 or a.shape[-1] != 3 or b.shape[-1] != 3:
        raise ValueError('cross3 requires arrays with a final dimension of three')
    dtype = np.promote_types(a.dtype, b.dtype)
    a, b = a.astype(dtype, copy=False), b.astype(dtype, copy=False)
    result = np.empty(np.broadcast(a[..., 0], b[..., 0]).shape + (3,), dtype=dtype)
    result[..., 0] = a[..., 1]*b[..., 2] - a[..., 2]*b[..., 1]
    result[..., 1] = a[..., 2]*b[..., 0] - a[..., 0]*b[..., 2]
    result[..., 2] = a[..., 0]*b[..., 1] - a[..., 1]*b[..., 0]
    return result
