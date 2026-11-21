"""Exact sparse recovery when full-Newton beam elimination runs out of memory.

The normal beam factor remains unchanged. This recovery retains every matrix
entry, uses the same diagonal scaling and full-equation residual gate, and
refines against the original operator. It changes no nonlinear acceptance rule.
"""
import numpy as np
from scipy.sparse import csc_matrix, diags, issparse
from scipy.sparse.linalg import splu
from openswing.harmonic_structure import storage, StructureUnavailable


class SparseNewtonFactor:
    def __init__(self, network, matrix, *, byte_budget=128*1024**2):
        data=matrix.data if issparse(matrix) else matrix
        if (matrix.shape!=(network.size,network.size) or not network.size
                or np.iscomplexobj(data) or not np.all(np.isfinite(data))):
            raise StructureUnavailable('Sparse Newton factors require a finite real full matrix.')
        self.matrix=matrix
        physical=csc_matrix(matrix)
        if 3*storage(physical)+4*network.size*8>byte_budget:
            raise StructureUnavailable('Sparse Newton matrices exceed their additional storage budget.')
        self.rows=np.maximum(abs(physical).max(axis=1).toarray().ravel(),1e-30)
        rowed=diags(1/self.rows)@physical
        self.columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
        scaled=(rowed@diags(1/self.columns)).tocsc()
        del physical,rowed
        self.factor=splu(scaled)
        extra=(2*(storage(self.factor.L)+storage(self.factor.U))
               +self.rows.nbytes+self.columns.nbytes)
        if extra>byte_budget:
            raise StructureUnavailable('Sparse Newton factors exceed their additional storage budget.')
        self.report=dict(method='exact sparse full-Newton LU after beam allocation failure',
            full_dimension=network.size,additional_factor_bytes=extra,
            matrix_nonzeros=scaled.nnz,solves=0)
        for values in ((matrix.data,matrix.indices,matrix.indptr) if issparse(matrix) else (matrix,)):
            values.flags.writeable=False

    def solve(self, rhs):
        b=np.asarray(rhs)
        if b.shape!=(self.matrix.shape[0],) or np.iscomplexobj(b) or not np.all(np.isfinite(b)):
            raise StructureUnavailable('Sparse Newton solve requires a finite real residual vector.')
        scaled_rhs=b/self.rows
        solution=self.factor.solve(scaled_rhs)
        correction=self.factor.solve(scaled_rhs-(self.matrix@(solution/self.columns))/self.rows)
        solution=(solution+correction)/self.columns
        residual=self.matrix@solution-b
        if (not np.all(np.isfinite(solution))
                or np.max(abs(residual))>1e-8*max(1.,np.max(abs(b)))):
            raise StructureUnavailable('Sparse Newton solve failed the original full-equation residual check.')
        self.report['solves']+=1
        return solution


def memory_bounded_newton_factor(network, matrix, **options):
    from openswing.newton_structure import NewtonBeamFactor
    try:
        return NewtonBeamFactor(network,matrix,**options)
    except MemoryError:
        # Leave the handler before allocating again so the failed constructor's
        # traceback no longer retains its temporary matrices and partial factors.
        pass
    return SparseNewtonFactor(network,matrix,**options)
