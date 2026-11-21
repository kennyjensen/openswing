"""Bounded augmenting-path matching of actual sparse nonzeros.

Both native SciPy graph routines stalled on a retained pattern in this runtime.
Each breadth-first search here visits a column at most once. This is only a
necessary rank screen; the existing numerical certificates remain required.
"""
import numpy as np


def maximum_matching(matrix):
    """Return one column per row, or -1; at most rows*edges visits."""
    pattern=matrix.tocsr(copy=True)
    pattern.sum_duplicates()
    pattern.eliminate_zeros()
    pattern.sort_indices()
    nr,nc=pattern.shape
    edges=[pattern.indices[pattern.indptr[i]:pattern.indptr[i+1]].tolist() for i in range(nr)]
    left=[-1]*nr;right=[-1]*nc
    seen=[-1]*nc;parent=[-1]*nc
    for root in range(nr):
        queue=[root];head=0;endpoint=-1
        while head<len(queue) and endpoint<0:
            row=queue[head];head+=1
            for column in edges[row]:
                if seen[column]==root:continue
                seen[column]=root;parent[column]=row
                if right[column]<0:
                    endpoint=column;break
                queue.append(right[column])
        # Flip the alternating path, increasing cardinality by exactly one.
        while endpoint>=0:
            row=parent[endpoint];previous=left[row]
            left[row]=endpoint;right[endpoint]=row;endpoint=previous
    return np.asarray(left,dtype=int)


def structural_rank(matrix):
    return int(np.count_nonzero(maximum_matching(matrix)>=0))


def _up(value):
    return float(np.nextafter(value, np.inf))


def _down(value):
    return float(np.nextafter(value, -np.inf))


def _add_up(left, right):
    if left == 0.:return right
    if right == 0.:return left
    return _up(left+right)


def _multiply_up(left, right):
    if left == 0. or right == 0.:return 0.
    return _up(left*right)


def _divide_up(numerator, denominator):
    if numerator == 0.:return 0.
    return _up(numerator/denominator)


def _sqrt_up(value):
    return 0. if value == 0. else _up(float(np.sqrt(value)))


def _gamma(operations):
    """Outward upper bound k*u/(1-k*u), for exact integer k."""
    if not 0 <= operations <= 2**53:return np.inf
    product = _multiply_up(float(operations), np.finfo(float).eps/2)
    denominator = _down(1.-product)
    return np.inf if denominator <= 0. else _divide_up(product, denominator)


def _normal_squares(values):
    """Range guard: every nonzero square must avoid underflow."""
    if not np.all(np.isfinite(values)):return False
    absolute = np.abs(values)
    return not np.any((absolute != 0.) & (absolute < np.sqrt(np.finfo(float).tiny)))


def _squared_norm_upper(values):
    """Bound the exact sum of stored binary64 squares, or decline."""
    if values.dtype != np.dtype(np.float64) or not _normal_squares(values):return None
    rounding = _gamma(2*values.size+2)
    if not np.isfinite(rounding) or rounding >= .25:return None
    with np.errstate(over='ignore', invalid='ignore'):
        total = float(np.sum(values*values, dtype=np.float64))
    if not np.isfinite(total):return None
    result = _divide_up(total, _down(1.-rounding))
    return result if np.isfinite(result) else None


def _canonical_compressed(matrix):
    """Check the actual storage; SciPy's canonical-format flag is cached."""
    data,indices,indptr = matrix.data,matrix.indices,matrix.indptr
    size = matrix.shape[0]
    if (data.ndim != 1 or indices.ndim != 1 or indptr.ndim != 1
            or indices.dtype.kind not in 'iu' or indptr.dtype.kind not in 'iu'
            or len(indices) != len(data) or len(indptr) != size+1
            or indptr[0] != 0 or indptr[-1] != len(data)
            or np.any(indptr[1:] < indptr[:-1])
            or np.any(indices < 0) or np.any(indices >= size)):
        return False
    for start,end in zip(indptr[:-1],indptr[1:]):
        segment = indices[start:end]
        if np.any(segment[1:] <= segment[:-1]):return False
    return True


def column_scaled_inverse_bound(matrix, *, progress=None):
    """Conservative rcond2 certificate for the original normalized matrix.

    The target C uses the dense SVD path's column norms and direct division.
    Sparse norms define B; an explicit scaling enclosure bounds C-B. For any
    computed inverse Y, ||I-CY|| < 1 bounds ||C^-1||. All Frobenius norm and
    residual bounds use outward scalar rounding. Uncovered types/ranges,
    factor failures, or an inconclusive bound return zero for the full SVD.

    The arithmetic enclosure assumes binary64 round-to-nearest, gradual
    underflow, and classical sparse dot accumulation (including FMA). It does
    not claim bit-identical decisions to a rounded SVD at its threshold.
    """
    from scipy.sparse.linalg import splu
    size = matrix.shape[0]
    if (matrix.shape != (size,size) or size == 0
            or matrix.dtype != np.dtype(np.float64)
            or matrix.format not in ('csr','csc')
            or not _canonical_compressed(matrix)
            or not _normal_squares(matrix.data)):
        return 0.
    # Besides bounding all counts exactly, this keeps the numerical enclosure
    # away from its gamma singularity before allocating any inverse batches.
    if size*(2*size+2) > 2**53:return 0.
    normalization_rounding = _gamma(2*size+3)
    dot_rounding = _gamma(2*size+2)
    if max(normalization_rounding,dot_rounding) >= .25:return 0.
    # Own the conversion, norms and scaling: scipy.power may refresh format
    # flags even on validated canonical input with a stale flag cache.
    scaled = matrix.tocsc(copy=True)
    with np.errstate(over='ignore', invalid='ignore'):
        norms = np.sqrt(np.asarray(scaled.power(2).sum(axis=0)).ravel())
    maximum_norm = _down(float(np.sqrt(np.finfo(float).max)))*.5
    if (not np.all(np.isfinite(norms)) or np.any(norms == 0.)
            or np.any(norms > maximum_norm)):
        return 0.
    # The finite-range margin also proves a different dense positive reduction
    # order cannot overflow. Clamping both norms to the same floor preserves
    # their ratio bound. Each scaled entry uses ONE rounded direct division.
    nonzero = scaled.data != 0.
    scaled.data /= np.repeat(np.maximum(norms,1e-30),np.diff(scaled.indptr))
    if np.any(nonzero & (scaled.data == 0.)):
        return 0.
    del nonzero
    scaled_squared = _squared_norm_upper(scaled.data)
    if scaled_squared is None or scaled_squared == 0.:return 0.
    scaled_norm = _sqrt_up(scaled_squared)
    u = np.finfo(float).eps/2
    norm_ratio = _divide_up(_add_up(1.,normalization_rounding),
                            _down(1.-normalization_rounding))
    division_ratio = _divide_up(_add_up(1.,u),_down(1.-u))
    scaling_error = _up(_multiply_up(norm_ratio,division_ratio)-1.)
    if progress is not None:progress(0,size)
    if structural_rank(matrix) < size:return 0.
    try:factor = splu(scaled)
    except RuntimeError:return 0.
    inverse_squared = error_squared = 0.
    for start in range(0,size,64):
        indices = np.arange(start,min(start+64,size))
        rhs = np.zeros((size,len(indices)))
        rhs[indices,np.arange(len(indices))] = 1.
        try:inverse = factor.solve(rhs)
        except RuntimeError:return 0.
        if (not isinstance(inverse,np.ndarray) or inverse.shape != rhs.shape
                or inverse.dtype != np.dtype(np.float64)):
            return 0.
        inverse_bound = _squared_norm_upper(inverse)
        if inverse_bound is None:return 0.
        with np.errstate(over='ignore',invalid='ignore'):
            error = scaled@inverse-rhs
        error_bound = _squared_norm_upper(error)
        if error_bound is None:return 0.
        inverse_squared = _add_up(inverse_squared,inverse_bound)
        error_squared = _add_up(error_squared,error_bound)
        if not np.isfinite(inverse_squared+error_squared):return 0.
        if progress is not None:progress(int(indices[-1])+1,size)
    inverse_norm = _sqrt_up(inverse_squared)
    product = _multiply_up(scaled_norm,inverse_norm)
    if not np.isfinite(product) or product <= 0.:return 0.
    residual_rounding = _multiply_up(dot_rounding,_add_up(product,_sqrt_up(float(size))))
    # Absolute underflow allowance for n*n residual entries, each with at most
    # 2*n+2 operations, also covering fused dot kernels. The smallest NORMAL is
    # a conservative replacement for the subnormal rounding quantum; it keeps
    # this outward-bound calculation itself out of the underflow range.
    underflow_numerator = _multiply_up(float(size*(2*size+2)),np.finfo(float).tiny)
    underflow_denominator = _down(1.-_multiply_up(float(2*size+2),u))
    underflow = _divide_up(underflow_numerator,underflow_denominator)
    residual_bound = _add_up(_sqrt_up(error_squared),residual_rounding)
    residual_bound = _add_up(residual_bound,_multiply_up(scaling_error,product))
    residual_bound = _add_up(residual_bound,underflow)
    if not np.isfinite(residual_bound) or residual_bound >= 1.:return 0.
    denominator = _multiply_up(_add_up(1.,scaling_error),product)
    bound = _down(_down(1.-residual_bound)/denominator)
    return max(0.,bound) if np.isfinite(bound) else 0.
