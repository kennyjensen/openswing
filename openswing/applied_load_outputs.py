"""Applied force/moment C/Q/D composed from the owned residual matrices.

Summing nodal balance equations cancels internal beam/joint wrenches:
W(x) R(x,xdot,u) = applied(x,xdot,u) + support(x).
Consequently C = W A + W_x R - C_support, Q = -W M, D = W B.
The W_x R term is retained even when the base residual is small. This is a
derivative of the physical output, not an equilibrium-only substitution.
"""
from dataclasses import dataclass
import numpy as np
from scipy.sparse import coo_matrix,issparse
from .structure import skew
from .equilibrium_tangent import identity
from .support_outputs import SupportTangent,SupportUnavailable


class AppliedLoadUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class AppliedLoadInput:
    owner: object
    forcing: object
    value: np.ndarray


def immutable(matrix):
    arrays=(matrix.data,matrix.indices,matrix.indptr) if issparse(matrix) else (matrix,)
    return all(not a.flags.writeable for a in arrays)


class AppliedLoadTangent:
    def __init__(self,system,a,m,step,*,limit=2*1024**2):
        n=system.network;size=system.size
        if (system.feedback is not None or n.iteration_fields is not None
                or a.shape!=(size,size) or m.shape!=(size,size)
                or not immutable(a) or not immutable(m)):
            raise AppliedLoadUnavailable('Applied-load recovery requires owned immutable physical matrices.')
        # C/Q plus construction products, sparse wrench map and base forces.
        if 4*6*size*8+3*n.nn*128>limit:
            raise AppliedLoadUnavailable('Applied-load derivative storage exceeds its budget.')
        self.owner,self.a,self.m,self.step=system,a,m,step
        self.signature=identity(system)
        support=getattr(system,'_support_output_tangent',None)
        try:
            if support is None or not support.matches(system):support=SupportTangent(system)
        except SupportUnavailable as exc:raise AppliedLoadUnavailable(str(exc)) from exc
        self.support=support
        rows=[];cols=[];values=[]
        def add(indices,block):
            rr,cc=np.nonzero(block)
            rows.extend(rr.tolist());cols.extend(np.asarray(indices)[cc].tolist());values.extend(block[rr,cc].tolist())
        for i,position in enumerate(system.r0):
            add(6*n.ne+3*i+np.arange(3),np.r_[n.F*np.eye(3),n.F*skew(position-n.model.reference[1])])
            add(6*n.ne+3*n.nn+3*i+np.arange(3),np.r_[np.zeros((3,3)),n.F*n.L*np.eye(3)])
        self.w=coo_matrix((values,(rows,cols)),shape=(6,size)).tocsr()
        zero=np.zeros(size);residual=system.residual(zero,zero)
        aero=n.aero_cached
        self.clips=() if aero is None else tuple(e['power_clipped'] for e in aero['engines'])
        self.base_force=n.F*residual[6*n.ne:6*n.ne+3*n.nn].reshape(n.nn,3)
        dense=lambda x:x.toarray() if issparse(x) else np.asarray(x)
        self.c=dense(self.w@a)-support.matrix.toarray()
        self.q=-dense(self.w@m)
        for i,force in enumerate(self.base_force):self.c[3:,6*i:6*i+3]-=system.L*skew(force)
        # At fixed geometry/kinematics, external loads do not depend on the
        # internal beam resultants or joint/ground reaction unknowns. Enforce
        # this exact partial, rather than retaining roundoff from cancelling
        # their opposite nodal contributions. No entry of A or M is changed.
        self.c[:,6*n.nn:n.gamma_start]=0.
        arrays=(self.c,self.q,self.w.data,self.w.indices,self.w.indptr,self.base_force)
        self.bytes=sum(v.nbytes for v in arrays)
        if self.bytes>limit or any(not np.all(np.isfinite(v)) for v in arrays):
            raise AppliedLoadUnavailable('Nonfinite or over-budget applied-load matrix.')
        for value in arrays:value.flags.writeable=False
        system._support_output_tangent=support
        self.applications=0;self.fallbacks={}

    def matches(self,system,a,m,step):
        return (self.owner is system and self.a is a and self.m is m and self.step==step
            and immutable(a) and immutable(m) and self.signature==identity(system))

    def input(self,forcing,column):
        column=np.asarray(column)
        if forcing is None or column.shape!=(self.owner.size,) or not np.all(np.isfinite(column)):
            raise AppliedLoadUnavailable('Invalid physical applied-load input column.')
        value=np.asarray(self.w@column);value.flags.writeable=False
        return AppliedLoadInput(self,forcing,value)

    def apply(self,vector,rate,forcing,input_column,snapshots):
        if not self.matches(self.owner,self.a,self.m,self.step):
            raise AppliedLoadUnavailable('Applied-load matrices no longer match the physical base.')
        # The actual output probes must stay on the same physical wire branch.
        try:self.support.apply(vector,snapshots)
        except SupportUnavailable as exc:raise AppliedLoadUnavailable(str(exc)) from exc
        if any(tuple(e['power_clipped'] for e in s.get('engines',[]))!=self.clips for s in snapshots):
            raise AppliedLoadUnavailable('Output stencil crosses an engine power-clipping transition.')
        value=self.c@vector+self.q@rate
        if forcing is not None:
            if (not isinstance(input_column,AppliedLoadInput) or input_column.owner is not self
                    or input_column.forcing is not forcing):
                raise AppliedLoadUnavailable('Applied-load input belongs to another forcing or operator.')
            value=value+input_column.value
        elif input_column is not None:
            raise AppliedLoadUnavailable('A homogeneous output cannot carry a direct input column.')
        if not np.all(np.isfinite(value)):raise AppliedLoadUnavailable('Nonfinite applied-load output.')
        self.applications+=1
        return dict(applied_force=value[:3],applied_moment=value[3:])

    def report(self):
        return dict(method='retained applied-load C/Q/D from full residual and support matrices',
            rows=6,cached_bytes=self.bytes,base_residual_moment_term=True,
            exact_internal_load_zeros=True,
            input_terms='W B; initial-condition right-hand sides are not direct inputs',
            applications=self.applications,fallback=dict(self.fallbacks) if self.fallbacks else None)
