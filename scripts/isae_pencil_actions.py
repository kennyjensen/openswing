"""Check complex modes against real physical matrices without square copies."""
import numpy as np
from scipy.sparse import csr_matrix, issparse


def _real_matrix(value):
    """Retain every nonzero entry without first copying JSON rows to dense."""
    if issparse(value):
        result=value.tocsr(copy=False)
        if not result.has_canonical_format:
            result=result.copy()
            result.sum_duplicates()
    elif isinstance(value,np.ndarray):
        if np.iscomplexobj(value):
            raise ValueError('These validation actions require real pencil matrices.')
        result=csr_matrix(value)
    else:
        n=len(value)
        counts=np.empty(n,dtype=np.int64)
        for i,row in enumerate(value):
            r=np.asarray(row)
            if r.shape!=(n,) or np.iscomplexobj(r) or not np.isfinite(r).all():
                raise ValueError('Real, finite, square pencil matrices are required.')
            counts[i]=np.count_nonzero(r)
        indptr=np.r_[0,np.cumsum(counts)]
        indices=np.empty(int(indptr[-1]),dtype=np.int64)
        data=np.empty(int(indptr[-1]),dtype=float)
        for i,row in enumerate(value):
            r=np.asarray(row);nonzero=np.flatnonzero(r)
            start,end=int(indptr[i]),int(indptr[i+1])
            indices[start:end]=nonzero;data[start:end]=r[nonzero]
        result=csr_matrix((data,indices,indptr),shape=(n,n),copy=False)
    if (result.ndim!=2 or result.shape[0]!=result.shape[1] or np.iscomplexobj(result.data)
            or not np.isfinite(result.data).all()):
        raise ValueError('Real, finite, square pencil matrices are required.')
    return result


def real_pencil(matrices):
    """Read the complete physical pencil; exact zeros alone are implicit."""
    a,m=(_real_matrix(matrices[k]) for k in ('A','M'))
    if a.shape!=m.shape:raise ValueError('Pencil matrix dimensions differ.')
    return a,m


def matrix_norm(matrix):
    """Frobenius norm of the complete matrix, including implicit exact zeros."""
    return np.linalg.norm(_real_matrix(matrix).data if issparse(matrix) else matrix)


def pencil_residuals(a, m, pole, right, left):
    """Return A r - lambda M r, l^H A - lambda l^H M, and l^H M r.

    NumPy's real-matrix/complex-vector product can promote the whole matrix
    to complex storage. Splitting the vector instead retains the original
    real pencil and allocates only vectors. No entries or modes are
    rounded, filtered, reduced, or modified.
    """
    a, m = (v if issparse(v) else np.asarray(v) for v in (a,m))
    if np.iscomplexobj(a.data if issparse(a) else a) or np.iscomplexobj(m.data if issparse(m) else m):
        raise ValueError('These validation actions require real pencil matrices.')

    def action(matrix, vector):
        return matrix @ vector.real + 1j * (matrix @ vector.imag)

    ar, mr = action(a, right), action(m, right)
    conjugate_left = left.conj()
    la, lm = action(a.T, conjugate_left), action(m.T, conjugate_left)
    return ar-pole*mr, la-pole*lm, np.vdot(left, mr)
