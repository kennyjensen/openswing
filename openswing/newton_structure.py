"""Exact full-Newton beam elimination using the harmonic solver's structure.

The owned matrix is a frozen Newton approximation, never a new physical state.
Reusing its factors is allowed only by the caller's full-residual merit checks.
Every original row participates in the solve and the eliminated variables are
recovered. An unavailable reduction leaves the original dense solve available.
"""
import numpy as np
from scipy.sparse import csc_matrix,diags,issparse
from .harmonic_structure import ReusableBeamStructure,StructureUnavailable,storage


class NewtonBeamFactor:
    def __init__(self,network,matrix,*,byte_budget=128*1024**2):
        n=network
        data=matrix.data if issparse(matrix) else matrix
        if (matrix.shape!=(n.size,n.size) or np.iscomplexobj(data)
                or not np.all(np.isfinite(data))):
            raise StructureUnavailable('Newton beam factors require a finite real full matrix.')
        self.matrix=matrix
        physical=csc_matrix(matrix)
        if 3*storage(physical)+4*n.size*8>byte_budget:
            raise StructureUnavailable('Newton beam matrices exceed their additional storage budget.')
        self.rows=np.maximum(abs(physical).max(axis=1).toarray().ravel(),1e-30)
        rowed=diags(1/self.rows)@physical
        self.columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
        # The common solver represents s*M-A. Here M=0 and A=-J.
        a=-physical;m=csc_matrix(physical.shape)
        del physical,rowed
        for block in (a,m):
            for values in (block.data,block.indices,block.indptr):values.flags.writeable=False
        structure=ReusableBeamStructure(a,m,
            np.r_[np.arange(6*n.ne),np.arange(6*(n.ne+n.nn),n.gamma_start)],
            np.arange(6*(n.nn+n.ne)),np.empty(0,dtype=int),np.empty(0,dtype=int),
            byte_budget=byte_budget)
        self.factor=structure.factor(a,m,0.,self.rows,self.columns)
        self.report=dict(structure.report)
        reduced=self.factor.factor
        extra=(structure.report['cached_matrix_bytes']+storage(a)+storage(m)
            +storage(self.factor.upper)
            +2*(storage(reduced.L)+storage(reduced.U))
            +sum(v.nbytes for v in (self.rows,self.columns,structure.rows,structure.columns,
                structure.keep_rows,structure.keep_columns)))
        if extra>byte_budget:
            raise StructureUnavailable('Newton beam factors exceed their additional storage budget.')
        self.report.update(additional_factor_bytes=extra)
        # The iteration must not mutate the matrix behind retained factors.
        for values in ((matrix.data,matrix.indices,matrix.indptr) if issparse(matrix) else (matrix,)):
            values.flags.writeable=False

    def solve(self,rhs):
        b=np.asarray(rhs)
        if b.shape!=(self.matrix.shape[0],) or np.iscomplexobj(b) or not np.all(np.isfinite(b)):
            raise StructureUnavailable('Newton beam solve requires a finite real residual vector.')
        scaled_rhs=b/self.rows
        solution=self.factor.solve(scaled_rhs)
        if np.any(solution.imag):raise StructureUnavailable('Nonreal Newton beam direction.')
        solution=solution.real
        # Refine against the original scaled full equations, including every
        # small entry, as in the shared harmonic elimination path.
        # Apply the original matrix with diagonal scales instead of retaining
        # a second scaled copy. This saves its entire sparse storage and checks
        # the same physical equations used for nonlinear acceptance.
        correction=self.factor.solve(scaled_rhs-(self.matrix@(solution/self.columns))/self.rows)
        if np.any(correction.imag):raise StructureUnavailable('Nonreal Newton beam refinement.')
        solution=(solution+correction.real)/self.columns
        residual=self.matrix@solution-b
        if (not np.all(np.isfinite(solution))
                or np.max(abs(residual))>1e-8*max(1.,np.max(abs(b)))):
            raise StructureUnavailable('Newton beam solve failed the original full-equation residual check.')
        return solution
