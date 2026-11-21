"""Independent high-precision differences of fixed-geometry physical balances.

This oracle evaluates forces, couples and section strains, not their derivative
formulas. Captured geometry/material coefficients are exact binary64 inputs;
80-digit arithmetic resolves two separate small perturbation widths. A separate
sum-of-absolute-contributions bound checks weak entries at floating precision.
"""
from decimal import Decimal,localcontext
import numpy as np
from scipy.sparse import coo_matrix


def affine_reference(system,data,width='1e-20'):
    n=system.network
    assert not n.hinges
    from openswing.local_motion import rotation_vector
    r,q=data['r'],data['Q']
    pa,pb,ra,rb,oa,ob=n.geometry(r,q)
    dr=pb-pa;k=rotation_vector(np.swapaxes(ra,-1,-2)@rb)
    start=6*n.nn;force_start=6*n.ne;moment_start=force_start+3*n.nn
    rows=[];columns=[];values=[];bounds=[]
    def add(rr,cc,block,condition):
        block=np.asarray(block,dtype=float)
        rows.extend(np.broadcast_to(np.asarray(rr)[:,None],block.shape).ravel())
        columns.extend(np.broadcast_to(np.asarray(cc)[None,:],block.shape).ravel())
        values.extend(block.ravel());bounds.extend(np.asarray(condition).ravel())
    def vector(v):return [Decimal(float(x)) for x in v]
    def matrix(a):return [vector(row) for row in a]
    def plus(*vectors):return [sum(v,Decimal(0)) for v in zip(*vectors)]
    def minus(a,b):return [x-y for x,y in zip(a,b)]
    def times(a,s):return [x*s for x in a]
    def mv(a,v):return [sum((x*y for x,y in zip(row,v)),Decimal(0)) for row in a]
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    def difference(function,x):
        out=np.zeros((len(function(x)),len(x)))
        for j in range(len(x)):
            h=Decimal(width)*max(1,abs(x[j]));p=x.copy();m=x.copy();p[j]+=h;m[j]-=h
            out[:,j]=[float(v/(2*h)) for v in minus(function(p),function(m))]
        return out
    with localcontext() as context:
        context.prec=80
        F,L=Decimal(float(n.F)),Decimal(float(n.L))
        for e,(i,j) in enumerate(n.ends):
            frame=list(zip(*matrix(data['section_frame'][e])));section=matrix(n.S[e]);length=Decimal(float(n.ds[e]))
            d,a,b=map(vector,(dr[e],oa[e],ob[e]));v0=vector(n.v0[e]);curvature=vector(k[e]-n.k0[e])
            fa,fb,ma,mb=map(vector,(data['force'][i],data['force'][j],data['moment'][i],data['moment'][j]))
            def physical(loads):
                N=times(loads[:3],F);M=times(loads[3:],F*L)
                local=mv(frame,N)+mv(frame,M)
                strain=times(mv(section,local),length)
                compatibility=times(minus(minus(mv(frame,d),v0),strain[:3]),1/L)+minus(curvature,strain[3:])
                force_a=times(plus(fa,N),1/F);force_b=times(minus(fb,N),1/F)
                moment_a=times(plus(ma,M,times(cross(d,N),Decimal('.5')),cross(a,N)),1/(F*L))
                moment_b=times(minus(plus(minus(mb,M),times(cross(d,N),Decimal('.5'))),cross(b,N)),1/(F*L))
                return compatibility+force_a+force_b+moment_a+moment_b
            x=vector(system.base[start+6*e:start+6*e+6])
            reference=difference(physical,x)
            # This is solely a rounding-error scale. The oracle above is
            # obtained from physical values at two distinct perturbations.
            rotation=np.zeros((6,6));rotation[:3,:3]=rotation[3:,3:]=abs(data['section_frame'][e].T)
            condition=np.zeros((18,6))
            condition[:6]=abs(n.S[e])@rotation*n.ds[e]*np.array([n.F]*3+[n.F*n.L]*3)
            condition[:3]/=n.L
            condition[6:9,:3]=condition[9:12,:3]=np.eye(3)
            for row,offset in [(12,oa[e]),(15,ob[e])]:
                arm=(abs(dr[e])/2+abs(offset))/n.L
                condition[row:row+3,:3]=[[0,arm[2],arm[1]],[arm[2],0,arm[0]],[arm[1],arm[0],0]]
                condition[row:row+3,3:]=np.eye(3)
            rr=np.r_[6*e+np.arange(6),force_start+3*i+np.arange(3),force_start+3*j+np.arange(3),
                     moment_start+3*i+np.arange(3),moment_start+3*j+np.arange(3)]
            add(rr,6*e+np.arange(6),reference,condition)
        for c in n.constraints:
            i,j,typ=c['a'],c['b'],c['type'];count=c['sl'].stop-c['sl'].start
            d=None if j is None else vector(r[j]-r[i])
            def physical(reaction):
                force=times(reaction[:3],F) if typ!=2 else [Decimal(0)]*3
                moment=times(reaction[count-3:],F*L) if typ!=1 else [Decimal(0)]*3
                if j is None:return times(force,1/F)+times(moment,1/(F*L))
                return times(force,1/F)+times(force,-1/F)+times(plus(moment,cross(d,force)),1/(F*L))+times(moment,-1/(F*L))
            x=vector(system.base[start+6*n.ne+c['sl'].start:start+6*n.ne+c['sl'].stop])
            reference=difference(physical,x)
            rr=np.r_[force_start+3*i+np.arange(3),moment_start+3*i+np.arange(3)] if j is None else np.r_[
                force_start+3*i+np.arange(3),force_start+3*j+np.arange(3),
                moment_start+3*i+np.arange(3),moment_start+3*j+np.arange(3)]
            add(rr,6*n.ne+np.arange(c['sl'].start,c['sl'].stop),reference,abs(reference))
    shape=(system.size,6*n.ne+n.nc)
    def sparse(v):
        result=coo_matrix((v,(rows,columns)),shape=shape).tocsc();result.sum_duplicates();result.eliminate_zeros()
        return result
    return sparse(values),sparse(bounds)


def compare(actual,reference,bound):
    difference=(actual-reference).tocoo();difference.eliminate_zeros()
    if not difference.nnz:return dict(max_normalized_error=0.,max_contribution_scaled_error=0.,changed_entries=0)
    expected=np.asarray(reference[difference.row,difference.col]).ravel()
    scale=np.asarray(bound[difference.row,difference.col]).ravel()
    assert np.all(scale>0),[(int(i),int(j),float(v)) for i,j,v,b in zip(difference.row,difference.col,difference.data,scale) if b<=0][:10]
    normalized=float(np.max(abs(difference.data)/(1+abs(expected))))
    relative=float(np.max(abs(difference.data)/scale))
    return dict(max_normalized_error=normalized,max_contribution_scaled_error=relative,changed_entries=difference.nnz)
