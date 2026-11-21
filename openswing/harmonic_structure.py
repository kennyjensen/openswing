"""Exact elimination of fixed beam equations in a harmonic descriptor pencil.

No state or equation is discarded: the eliminated variables are recovered for
each right-hand side. Full-system scaling, condition estimation and residual
checks remain the responsibility of the harmonic solver.
"""
import numpy as np
from scipy.sparse import csc_matrix, diags, hstack
from .beam_matching import row_matching
from scipy.sparse.linalg import splu, LinearOperator, onenormest


class StructureUnavailable(ValueError):
    """An optional exact reduction cannot be prepared within its safeguards."""


def storage(matrix):
    return matrix.data.nbytes+matrix.indices.nbytes+matrix.indptr.nbytes


class BalancedFactor:
    """One fixed real sparse block, also accepting complex right-hand sides."""
    def __init__(self, matrix):
        self.rows=np.maximum(abs(matrix).max(axis=1).toarray().ravel(),1e-30)
        rowed=diags(1/self.rows)@matrix
        self.columns=np.maximum(abs(rowed).max(axis=0).toarray().ravel(),1e-30)
        scaled=(rowed@diags(1/self.columns)).tocsc()
        self.norm_inf=float(abs(scaled).sum(axis=1).max())
        self.factor=splu(scaled)
        inverse=LinearOperator(scaled.shape,matvec=self.factor.solve,matmat=self.factor.solve,
            rmatvec=lambda b:self.factor.solve(b,trans='T'),rmatmat=lambda b:self.factor.solve(b,trans='T'),dtype=float)
        reciprocal=1/(float(abs(scaled).sum(axis=0).max())*onenormest(inverse,t=1))
        if not np.isfinite(reciprocal) or reciprocal<1e-9:
            raise StructureUnavailable('Beam elimination block is poorly conditioned.')
        self.bytes=storage(self.factor.L)+storage(self.factor.U)+self.rows.nbytes+self.columns.nbytes

    def solve(self, rhs, trans='N'):
        vector=np.asarray(rhs).ndim==1
        b=np.asarray(rhs)[:,None] if vector else np.asarray(rhs)
        rows,columns=(self.rows,self.columns) if trans=='N' else (self.columns,self.rows)
        b=b/rows[:,None]
        if np.iscomplexobj(b):
            value=self.factor.solve(b.real,trans=trans)+1j*self.factor.solve(b.imag,trans=trans)
        else:value=self.factor.solve(b,trans=trans)
        value=value/columns[:,None]
        return value[:,0] if vector else value


class DiagonalFactor:
    """Eliminate an actual diagonal block of the currently scaled matrix."""
    def __init__(self, matrix, rows, columns, *, _defer_factor=False):
        self.rows=np.asarray(rows,dtype=int);self.columns=np.asarray(columns,dtype=int)
        self.keep_rows=np.setdiff1d(np.arange(matrix.shape[0]),self.rows)
        self.keep_columns=np.setdiff1d(np.arange(matrix.shape[1]),self.columns)
        d=matrix[self.rows][:,self.columns].tocsc();self.diagonal=d.diagonal()
        off=d-diags(self.diagonal);off.eliminate_zeros()
        if (d.shape[0]!=d.shape[1] or off.nnz or not len(self.diagonal)
                or np.any(self.diagonal==0) or not np.all(np.isfinite(self.diagonal))):
            raise StructureUnavailable('Velocity-definition block is not an invertible diagonal.')
        self.upper=matrix[self.keep_rows][:,self.columns].tocsc()
        self.lower=matrix[self.rows][:,self.keep_columns].tocsc()
        reduced=(matrix[self.keep_rows][:,self.keep_columns]
                 -self.upper@diags(1/self.diagonal)@self.lower).tocsc()
        self.dimension=reduced.shape[0]
        self._pending_matrix=reduced
        if not _defer_factor:self.factorize()

    def factorize(self):
        """Factor after the caller can release the pre-elimination matrix."""
        matrix=self._pending_matrix
        del self._pending_matrix
        self.factor=splu(matrix)

    def solve(self, rhs, trans='N'):
        vector=np.asarray(rhs).ndim==1
        b=np.asarray(rhs)[:,None] if vector else np.asarray(rhs)
        if trans=='N':
            br,be=b[self.keep_rows],b[self.rows]
            local=self.factor.solve(br-self.upper@(be/self.diagonal[:,None]))
            eliminated=(be-self.lower@local)/self.diagonal[:,None]
            result=np.empty_like(b,dtype=complex)
            result[self.keep_columns]=local;result[self.columns]=eliminated
        else:
            conjugate=trans=='H'
            upper=self.lower.conj().T if conjugate else self.lower.T
            lower=self.upper.conj().T if conjugate else self.upper.T
            d=self.diagonal.conj() if conjugate else self.diagonal
            br,be=b[self.keep_columns],b[self.columns]
            local=self.factor.solve(br-upper@(be/d[:,None]),trans=trans)
            eliminated=(be-lower@local)/d[:,None]
            result=np.empty_like(b,dtype=complex)
            result[self.keep_rows]=local;result[self.rows]=eliminated
        return result[:,0] if vector else result


class ReusableBeamStructure:
    """Fixed compatibility factors and reduced A/M, owned by exact matrix objects.

    Matching selects pivots only. Every original matrix entry participates in
    the reduction, including entries smaller than the matching preference.
    Unavailable or unstable optional reductions leave the full solver usable.
    """
    def __init__(self, a, m, static_rows, eligible_columns, velocity_rows, velocity_columns,
                 *, byte_budget=128*1024**2):
        self.a,self.m=a,m
        if a.shape!=m.shape or a.shape[0]!=a.shape[1] or np.iscomplexobj(a.data) or np.iscomplexobj(m.data):
            raise StructureUnavailable('Beam reduction requires square real descriptor matrices.')
        if any(values.flags.writeable for matrix in (a,m)
               for values in (matrix.data,matrix.indices,matrix.indptr)):
            raise StructureUnavailable('Reusable beam factors require immutable descriptor matrices.')
        matrix=csc_matrix(a);mass=csc_matrix(m);size=matrix.shape[0]
        rows=np.asarray(static_rows,dtype=int)
        rows=rows[np.asarray(mass[rows].getnnz(axis=1)).ravel()==0]
        eligible=np.asarray(eligible_columns,dtype=int)
        if not len(rows) or len(rows)>=size:
            raise StructureUnavailable('No proper frequency-independent beam block.')
        block=matrix[rows][:,eligible].tocsr()
        scale=np.maximum(abs(block).max(axis=1).toarray().ravel(),1e-30)
        failure='No independent beam elimination pattern.'
        for threshold in [.5,.1,.01,1e-4,0.]:
            pattern=block.copy()
            pattern.data=(abs(pattern.data)>threshold*np.repeat(scale,np.diff(pattern.indptr))).astype(float)
            pattern.eliminate_zeros()
            match=row_matching(pattern)
            if np.any(match<0):continue
            columns=eligible[match]
            keep_columns=np.setdiff1d(np.arange(size),columns)
            keep_rows=np.setdiff1d(np.arange(size),rows)
            d=matrix[rows][:,columns].tocsc();c=matrix[rows][:,keep_columns].tocsc()
            try:fixed=BalancedFactor(d)
            except (RuntimeError,ValueError) as exc:
                failure=str(exc);continue
            pieces=[];used=fixed.bytes;resolved=True
            for start in range(0,len(keep_columns),32):
                rhs=c[:,start:start+32].toarray();value=fixed.solve(rhs)
                defect=d@value-rhs
                # Normwise backward error in the balanced block. Componentwise
                # ratios can approach one for harmless fill in an exact zero
                # entry; no small entries are removed to force those to zero.
                numerator=np.max(abs(defect)/fixed.rows[:,None],axis=0)
                denominator=(fixed.norm_inf*np.max(abs(value)*fixed.columns[:,None],axis=0)
                             +np.max(abs(rhs)/fixed.rows[:,None],axis=0)+1e-30)
                if not np.all(np.isfinite(value)) or np.max(numerator/denominator)>1e-12:
                    failure='Beam substitution fails its original block residual.';resolved=False;break
                part=csc_matrix(value);used+=storage(part)
                if used>byte_budget:raise StructureUnavailable('Beam substitution exceeds its retained storage budget.')
                pieces.append(part)
            if not resolved:continue
            coupling=hstack(pieces,format='csc')
            ae=matrix[keep_rows][:,columns].tocsc();me=mass[keep_rows][:,columns].tocsc()
            ar=(matrix[keep_rows][:,keep_columns]-ae@coupling).tocsc()
            mr=(mass[keep_rows][:,keep_columns]-me@coupling).tocsc()
            used=fixed.bytes+sum(storage(v) for v in [coupling,ae,me,ar,mr])
            if used>byte_budget:raise StructureUnavailable('Reduced beam matrices exceed their retained storage budget.')
            if not all(np.all(np.isfinite(v.data)) for v in [coupling,ae,me,ar,mr]):
                failure='Nonfinite reduced beam matrices.';continue
            self.rows,self.columns,self.keep_rows,self.keep_columns=rows,columns,keep_rows,keep_columns
            self.fixed,self.coupling,self.ae,self.me,self.ar,self.mr=fixed,coupling,ae,me,ar,mr
            row_map=np.full(size,-1,dtype=int);row_map[keep_rows]=np.arange(len(keep_rows))
            col_map=np.full(size,-1,dtype=int);col_map[keep_columns]=np.arange(len(keep_columns))
            self.velocity_rows=row_map[np.asarray(velocity_rows,dtype=int)]
            self.velocity_columns=col_map[np.asarray(velocity_columns,dtype=int)]
            if np.any(self.velocity_rows<0) or np.any(self.velocity_columns<0):
                self.velocity_rows=self.velocity_columns=np.empty(0,dtype=int)
            self.report=dict(method='exact fixed beam elimination with optional diagonal kinematics',
                full_dimension=size,beam_equations_eliminated=len(rows),beam_reduced_dimension=len(keep_rows),
                cached_matrix_bytes=used,pivot_preference=threshold)
            return
        raise StructureUnavailable(failure)

    def factor(self, a, m, s, rows, columns):
        if a is not self.a or m is not self.m:
            raise StructureUnavailable('Beam factors belong to different descriptor matrices.')
        return BeamFactor(self,s,rows,columns)


class BeamFactor:
    """Inverse action of the original fully scaled pencil, including its adjoint."""
    def __init__(self, structure, s, rows, columns):
        self.structure=structure;self.rows=rows;self.columns=columns
        t=structure
        self.upper=(s*t.me-t.ae).tocsc()
        reduced=(s*t.mr-t.ar).tocsc()
        # This is an owned frequency-specific matrix. Scale its stored entries
        # directly to avoid two additional complex sparse products. Cached
        # real A/M and the original full pencil remain untouched.
        reduced.data *= (1/rows[t.keep_rows])[reduced.indices]
        reduced.data *= np.repeat(1/columns[t.keep_columns],np.diff(reduced.indptr))
        dimension=reduced.shape[0]
        try:self.factor=DiagonalFactor(reduced,t.velocity_rows,t.velocity_columns,_defer_factor=True)
        except (RuntimeError,ValueError):self.factor=splu(reduced)
        else:
            del reduced
            try:self.factor.factorize()
            except (RuntimeError,ValueError):
                # Preserve the original full-block fallback if diagonal
                # elimination cannot be factored. Rebuild only on failure.
                reduced=(s*t.mr-t.ar).tocsc()
                reduced.data *= (1/rows[t.keep_rows])[reduced.indices]
                reduced.data *= np.repeat(1/columns[t.keep_columns],np.diff(reduced.indptr))
                self.factor=splu(reduced)
        self.dimension=getattr(self.factor,'dimension',dimension)

    def solve(self, rhs, trans='N'):
        vector=np.asarray(rhs).ndim==1
        b=np.asarray(rhs)[:,None] if vector else np.asarray(rhs)
        t=self.structure
        if trans=='N':
            physical=self.rows[:,None]*b
            direct=-t.fixed.solve(physical[t.rows])
            reduced_rhs=(physical[t.keep_rows]-self.upper@direct)/self.rows[t.keep_rows,None]
            retained=self.factor.solve(reduced_rhs)/self.columns[t.keep_columns,None]
            eliminated=direct-t.coupling@retained
            result=np.empty_like(b,dtype=complex)
            result[t.keep_columns]=retained;result[t.columns]=eliminated
            result*=self.columns[:,None]
        else:
            physical=self.columns[:,None]*b
            adjoint=t.coupling.conj().T if trans=='H' else t.coupling.T
            upper=self.upper.conj().T if trans=='H' else self.upper.T
            reduced_rhs=(physical[t.keep_columns]-adjoint@physical[t.columns])/self.columns[t.keep_columns,None]
            retained=self.factor.solve(reduced_rhs,trans=trans)/self.rows[t.keep_rows,None]
            eliminated=t.fixed.solve(upper@retained-physical[t.columns],trans=trans)
            result=np.empty_like(b,dtype=complex)
            result[t.keep_rows]=retained;result[t.rows]=eliminated
            result*=self.rows[:,None]
        return result[:,0] if vector else result
