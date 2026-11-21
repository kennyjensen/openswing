"""Exact, retained body-axis ground/strut output derivatives.

Support forces and moments depend on positions, rotations and ground reaction
unknowns, with no direct input or rate term. This is the corresponding six-row
C block. It uses the same bilateral/tension-only law as the nonlinear residual.
"""
import hashlib
import numpy as np
from scipy.sparse import coo_matrix
from .structure import skew
from .struts import strut_load


class SupportUnavailable(ValueError):
    pass


def signature(system):
    """Only physical data used by the support law, including exact array bytes."""
    n=system.network;key=hashlib.sha256()
    def add(value):
        a=np.asarray(value)
        if not np.all(np.isfinite(a)):raise SupportUnavailable('Nonfinite support output context.')
        key.update(repr((a.shape,a.dtype.str)).encode());key.update(a.tobytes())
    add([n.nn,n.ne,n.nc,system.size,n.L,n.F,system.L,n.tension_only])
    add(n.model.reference[1])
    start=6*(n.nn+n.ne)
    for c in n.constraints:
        if c['b'] is not None:continue
        add([c['a'],c['type'],c['sl'].start,c['sl'].stop])
        add(system.r0[c['a']]);add(system.base[start:start+n.nc][c['sl']])
    for row in n.struts:
        i=n.node(*row[:2]);add(row);add(i)
        for value in (system.r0[i],system.Q0[i],n.rj[i]):add(value)
    return key.digest()


class SupportTangent:
    def __init__(self,system,*,limit=2*1024**2):
        self.owner=system;self.signature=signature(system)
        n=system.network
        # Bound retained sparse storage before forming the blocks. Construction
        # has at most 144 triplets per support, including duplicate contributions.
        count=sum(c['b'] is None for c in n.constraints)+len(n.struts)
        if 144*count*24+(7+6*n.nn)*8>limit:
            raise SupportUnavailable('Support output matrix exceeds its storage budget.')
        rows=[];cols=[];data=[]
        def block(columns,values):
            values=np.asarray(values);a,b=np.nonzero(values)
            rows.extend(a.tolist());cols.extend(np.asarray(columns)[b].tolist());data.extend(values[a,b].tolist())
        ref=n.model.reference[1];start=6*(n.nn+n.ne)
        base_reactions=system.base[start:start+n.nc]
        for c in n.constraints:
            if c['b'] is not None:continue
            i,typ=c['a'],c['type'];indices=start+np.arange(c['sl'].start,c['sl'].stop)
            if typ!=2:
                block(indices[:3],np.r_[n.F*np.eye(3),n.F*skew(system.r0[i]-ref)])
                force=n.F*base_reactions[c['sl']][:3]
                block(6*i+np.arange(3),np.r_[np.zeros((3,3)),-system.L*skew(force)])
            if typ!=1:block(indices[-3:],np.r_[np.zeros((3,3)),n.F*n.L*np.eye(3)])
        self.wires=[]
        nodal_rows=[];nodal_cols=[];nodal_data=[]
        for row in n.struts:
            i=n.node(*row[:2]);offset=system.Q0[i]@(row[2:5]-n.rj[i])
            state=strut_load(row,system.r0[i]+offset,tension_only=n.tension_only)
            extension=state['length']-state['unloaded_length']
            if n.tension_only and extension==0 and row[9]!=0:
                raise SupportUnavailable('Support derivative is undefined at a wire slack/taut boundary.')
            self.wires.append(state['slack'])
            if state['slack']:continue
            direction=(state['anchor']-state['position'])/state['length']
            axial=np.outer(direction,direction)
            stiffness=row[9]/state['unloaded_length']*axial+state['tension']/state['length']*(np.eye(3)-axial)
            force=np.c_[-system.L*stiffness,stiffness@skew(offset)]
            block(6*i+np.arange(6),np.r_[force,skew(state['anchor']-ref)@force])
            # The same strut derivative supplies nodal balance rows of A.
            # Moment includes the derivative of the rotating pylon arm.
            arm=np.c_[np.zeros((3,3)),-skew(offset)]
            moment=skew(offset)@force-skew(state['force'])@arm
            values=np.r_[force/n.F,moment/(n.F*n.L)]
            rr,cc=np.nonzero(values)
            indices=np.r_[6*n.ne+3*i+np.arange(3),6*n.ne+3*n.nn+3*i+np.arange(3)]
            nodal_rows.extend(indices[rr].tolist());nodal_cols.extend((6*i+cc).tolist());nodal_data.extend(values[rr,cc].tolist())
        self.matrix=coo_matrix((data,(rows,cols)),shape=(6,system.size)).tocsr()
        self.matrix.sum_duplicates();self.matrix.eliminate_zeros()
        if not np.all(np.isfinite(self.matrix.data)):raise SupportUnavailable('Nonfinite support output matrix.')
        self.nodal_struts=coo_matrix((nodal_data,(nodal_rows,nodal_cols)),shape=(n.size,6*n.nn)).tocsc()
        self.nodal_struts.sum_duplicates();self.nodal_struts.eliminate_zeros()
        arrays=(self.matrix.data,self.matrix.indices,self.matrix.indptr,self.nodal_struts.data,self.nodal_struts.indices,self.nodal_struts.indptr)
        if not np.all(np.isfinite(self.nodal_struts.data)):raise SupportUnavailable('Nonfinite strut nodal matrix.')
        self.bytes=sum(v.nbytes for v in arrays)
        if self.bytes>limit:raise SupportUnavailable('Support output matrix exceeds its storage budget.')
        for value in arrays:value.flags.writeable=False

    def matches(self,system):
        return self.owner is system and self.signature==signature(system)

    def apply(self,vector,snapshots):
        # Retain the original physical output path when an actual stencil
        # changes the active wire set; a single smooth C block is inapplicable.
        for snapshot in snapshots:
            if [s['slack'] for s in snapshot['struts']]!=self.wires:
                raise SupportUnavailable('Output stencil crosses a wire slack/taut boundary.')
        value=self.matrix@vector
        return dict(support_force=value[:3],support_moment=value[3:])


def support_outputs(system,vector,snapshots):
    try:
        tangent=getattr(system,'_support_output_tangent',None)
        if tangent is None or not tangent.matches(system):
            tangent=SupportTangent(system);system._support_output_tangent=tangent
        values=tangent.apply(vector,snapshots)
    except SupportUnavailable as exc:
        system.support_output_diagnostics=dict(method='physical output stencils',fallback=str(exc))
        return {}
    system.support_output_diagnostics=dict(method='retained analytic ground/strut C matrix',
        rows=6,nonzeros=tangent.matrix.nnz,cached_bytes=tangent.bytes,rate_and_input_terms='zero',fallback=None)
    return values
