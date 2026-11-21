"""Independent geometry and closed Biot-Savart integrals for one loaded wing."""
import numpy as np
from scipy.spatial.transform import Rotation
JIG=np.array([[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])


def rows(source):
    out={};header=None
    for line in source.splitlines():
        p=line.split()
        if not p or p[0].startswith('#'):continue
        if p[0]=='t':header=p;continue
        if p[0]=='End':header=None;continue
        if header is not None:
            assert len(p)==len(header)
            for key,value in zip(header[1:],p[1:]):out.setdefault(key,[]).append([float(p[0]),float(value)])
    return {k:np.asarray(v) for k,v in out.items()}


def prop(data,key,t,default=0.):
    if key not in data:return np.zeros_like(np.asarray(t))+default
    return np.interp(t,data[key][:,0],data[key][:,1])


def interpolate(r,Q,f):
    f=np.asarray(f);k=Rotation.from_matrix(Q[:-1].swapaxes(-1,-2)@Q[1:]).as_rotvec()
    if f.ndim==1:
        return r[:-1]+f[:,None]*(r[1:]-r[:-1]),Q[:-1]@Rotation.from_rotvec(f[:,None]*k).as_matrix()
    matrix=Rotation.from_rotvec((f[...,None]*k[:,None,:]).reshape(-1,3)).as_matrix().reshape(*f.shape,3,3)
    return r[:-1,None,:]+f[...,None]*(r[1:]-r[:-1])[:,None,:],Q[:-1,None]@matrix


def vortex(points,a,b,w,exclude_self=False):
    ra=np.asarray(points)[:,None,:]-np.asarray(a)[None,:,:]
    rb=np.asarray(points)[:,None,:]-np.asarray(b)[None,:,:]
    cross=np.cross(ra,rb);den=np.einsum('ijk,ijk->ij',cross,cross)
    factor=np.einsum('jk,ijk->ij',b-a,ra/np.linalg.norm(ra,axis=-1)[...,None]-rb/np.linalg.norm(rb,axis=-1)[...,None])
    valid=den>1e-26
    if exclude_self:valid&=~np.eye(len(points),len(a),dtype=bool)
    velocity=cross*np.divide(factor,den,out=np.zeros_like(den),where=valid)[...,None]
    for sign,rr in [(1.,rb),(-1.,ra)]:
        cross=np.cross(w,rr);den=np.einsum('ijk,ijk->ij',cross,cross)
        assert np.all(den>1e-26)
        velocity+=sign*cross*((1+np.einsum('k,ijk->ij',w,rr)/np.linalg.norm(rr,axis=-1))/den)[...,None]
    return velocity/(4*np.pi)


GX,GW=np.polynomial.legendre.leggauss(12)
GX=(GX+1)/2;GW=GW/2


def rotation_weights(Q,f):
    """Spatial virtual-motion maps using the integral of matrix exponentials."""
    k=Rotation.from_matrix(Q[:-1].swapaxes(-1,-2)@Q[1:]).as_rotvec()
    def integral(v):
        shape=v.shape[:-1]
        matrices=Rotation.from_rotvec((v[...,None,:]*GX[:,None]).reshape(-1,3)).as_matrix()
        return np.einsum('g,...gij->...ij',GW,matrices.reshape(*shape,len(GX),3,3))
    f=np.asarray(f)
    if f.ndim==1:
        left=Q[:-1];right=left@integral(k*f[:,None])@np.linalg.inv(integral(k))*f[:,None,None]@left.swapaxes(-1,-2)
    else:
        left=Q[:-1,None];right=left@integral(k[:,None,:]*f[...,None])@np.linalg.inv(integral(k))[:,None]*f[...,None,None]@left.swapaxes(-1,-2)
    return np.eye(3)-right,right


def nodal_loads(Q,f,force,moment):
    wa,wb=rotation_weights(Q,f)
    nodal_force=np.zeros((len(Q),3));nodal_moment=np.zeros_like(nodal_force)
    for sl,factor,angular in [(slice(None,-1),1-f,wa),(slice(1,None),f,wb)]:
        F=factor[...,None]*force;M=np.einsum('...ji,...j->...i',angular,moment)
        if f.ndim==2:F=F.sum(axis=1);M=M.sum(axis=1)
        nodal_force[sl]+=F;nodal_moment[sl]+=M
    return np.c_[nodal_force,nodal_moment]
