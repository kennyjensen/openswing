"""Stationary structural geometry partials shared by Newton and dynamics.

External loads, passive struts, and all rate partials remain separate. The
section C matrix supplies compatibility; nodal force couples and ideal
joint/ground geometry use their exact spatial-rotation derivatives.
"""
from types import SimpleNamespace
import numpy as np
from scipy.sparse import coo_matrix,vstack
from .structure import skew
from .local_motion import left_jacobian,rotation_vector
from .structural_outputs import compatibility_columns,StructuralOutputUnavailable


class StructuralGeometryUnavailable(ValueError):
    pass


def local_load_rows(n):
    """Conservative supports of local external loads with induced fields fixed."""
    adjacent=[{i} for i in range(n.nn)]
    for i,j in n.ends:
        adjacent[i].add(int(j));adjacent[j].add(int(i))
    force=6*n.ne;moment=force+3*n.nn
    result=[]
    for neighbours in adjacent:
        nodes=np.array(sorted(neighbours))
        rows=np.r_[(force+3*nodes[:,None]+np.arange(3)).ravel(),
                   (moment+3*nodes[:,None]+np.arange(3)).ravel()]
        result.extend([rows]*6)
    return result


def geometry_columns(n,x,*,chart='absolute',row_count=None,system=None,limit=32*1024**2):
    if chart not in ('absolute','spatial') or n.operating.custom or any(c['type']==3 for c in n.constraints):
        raise StructuralGeometryUnavailable('Structural geometry requires ideal joints and canonical load constraints.')
    row_count=n.size if row_count is None else row_count
    if row_count<n.size or (256*n.ne+128*len(n.constraints))*32>limit:
        raise StructuralGeometryUnavailable('Structural geometry matrix exceeds its dimension or storage budget.')
    r,q,N,_,reactions,_=n.unpack(x)
    if system is None:
        system=SimpleNamespace(network=n,base=np.asarray(x),r0=r,Q0=q,L=n.L,size=row_count)
    elif (system.network is not n or system.size!=row_count or system.L!=n.L
            or not np.array_equal(system.base[6*n.nn:],np.asarray(x)[6*n.nn:])
            or not np.allclose(system.r0,r,rtol=2e-14,atol=2e-14*n.L)
            or not np.allclose(system.Q0,q,rtol=2e-14,atol=2e-14)):
        raise StructuralGeometryUnavailable('Section matrix does not belong to this structural base.')
    try:compatibility=compatibility_columns(system)[:,:6*n.nn]
    except StructuralOutputUnavailable as exc:raise StructuralGeometryUnavailable(str(exc)) from exc
    rows=[];columns=[];values=[]
    def add(rr,cc,block):
        rr,cc=np.asarray(rr),np.asarray(cc);block=np.asarray(block)
        ii,jj=np.nonzero(block)
        rows.extend(rr[ii].tolist());columns.extend(cc[jj].tolist());values.extend(block[ii,jj].tolist())
    xyz=np.arange(3);identity=np.eye(3)
    moment_start=6*n.ne+3*n.nn;constraint_start=6*(n.ne+n.nn)
    _,_,_,_,oa,ob=n.geometry(r,q)
    for e,(i,j) in enumerate(n.ends):
        # M_a=M+(r_b-r_a+o_b+o_a)xN/2,
        # M_b=-M+(r_b-r_a-o_b-o_a)xN/2.
        spatial=skew(N[e])/(2*n.F)
        for node in (i,j):
            add(moment_start+3*node+xyz,6*i+xyz,spatial)
            add(moment_start+3*node+xyz,6*j+xyz,-spatial)
        for node,offset in [(i,oa[e]),(j,ob[e])]:
            block=spatial@skew(offset)/n.L
            add(moment_start+3*i+xyz,6*node+3+xyz,block)
            add(moment_start+3*j+xyz,6*node+3+xyz,-block)
    for c in n.constraints:
        i,j,typ=c['a'],c['b'],c['type'];start=constraint_start+c['sl'].start
        if typ not in (0,1,2):raise StructuralGeometryUnavailable('Unknown ideal constraint type.')
        if typ!=2:
            if j is None:
                add(start+xyz,6*i+xyz,identity)
            else:
                add(start+xyz,6*i+xyz,-identity);add(start+xyz,6*j+xyz,identity)
                add(start+xyz,6*i+3+xyz,skew(q[i]@(n.rj[j]-n.rj[i]))/n.L)
                force=reactions[c['sl']][:3]*n.F
                block=skew(force)/n.F
                add(moment_start+3*i+xyz,6*i+xyz,block)
                add(moment_start+3*i+xyz,6*j+xyz,-block)
        if typ!=1:
            vector=rotation_vector(q[i] if j is None else q[i].T@q[j])
            if np.linalg.norm(vector)>=np.pi-1e-7:
                raise StructuralGeometryUnavailable('Constraint approaches the rotation-logarithm branch.')
            block=np.linalg.solve(left_jacobian(vector),identity if j is None else q[i].T)
            rr=start+(0 if typ==2 else 3)+xyz
            add(rr,6*i+3+xyz,block if j is None else -block)
            if j is not None:add(rr,6*j+3+xyz,block)
    tail=coo_matrix((values,(rows,columns)),shape=(row_count,6*n.nn)).tocsc()
    matrix=vstack([compatibility,tail[6*n.ne:]],format='csc')
    if chart=='absolute':
        angles=np.asarray(x)[:6*n.nn].reshape(n.nn,6)[:,3:]
        transforms=left_jacobian(angles)
        rotations=6*np.arange(n.nn)[:,None]+np.arange(3,6)
        translations=(6*np.arange(n.nn)[:,None]+np.arange(3)).ravel()
        rr=np.broadcast_to(rotations[:,:,None],transforms.shape).ravel()
        cc=np.broadcast_to(rotations[:,None,:],transforms.shape).ravel()
        change=coo_matrix((np.r_[np.ones(len(translations)),transforms.ravel()],
            (np.r_[translations,rr],np.r_[translations,cc])),shape=(6*n.nn,6*n.nn)).tocsc()
        matrix=(matrix@change).tocsc()
    matrix.sum_duplicates();matrix.eliminate_zeros()
    arrays=(matrix.data,matrix.indices,matrix.indptr)
    if sum(a.nbytes for a in arrays)>limit or not np.all(np.isfinite(matrix.data)):
        raise StructuralGeometryUnavailable('Nonfinite or over-budget structural geometry matrix.')
    for array in arrays:array.flags.writeable=False
    return matrix,dict(method='retained section C, exact nodal couples and ideal-constraint geometry',
        columns=matrix.shape[1],nonzeros=matrix.nnz,cached_bytes=sum(a.nbytes for a in arrays),chart=chart)
