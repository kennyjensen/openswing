"""Diagnostic transcription of native AVL VSRD/VORVELC (not production).

AVL 3.52 aic.f: same-component core = 0.0001 * transverse strip width;
quartic Leishman core, PG x transform, and native rounded PI4INV. This
reference deliberately preserves the distinct native core law. The optional
zero-core/extended-precision calls identify core and cancellation effects.
"""
import numpy as np


def matrix(points, start, end, mach, *, exclude_self=False, core_fraction=.0001,
           dtype=np.float64):
    points, start, end = [np.asarray(v, dtype=dtype) for v in (points,start,end)]
    beta = np.sqrt(dtype(1)-dtype(mach)**2)
    a = start[None,:,:]-points[:,None,:]
    b = end[None,:,:]-points[:,None,:]
    a[:,:,0] /= beta; b[:,:,0] /= beta
    dot = lambda x,y: x[...,0]*y[...,0]+x[...,1]*y[...,1]+x[...,2]*y[...,2]
    asq, bsq = dot(a,a), dot(b,b)
    amag,bmag = np.sqrt(asq),np.sqrt(bsq)
    core = dtype(core_fraction)*np.sqrt((end[:,1]-start[:,1])**2+(end[:,2]-start[:,2])**2)
    core4 = (core**2)**2
    cross = np.cross(a,b); crosssq = dot(cross,cross)
    adb = dot(a,b); lengthsq = asq+bsq-2*adb
    valid = (amag*bmag != 0) & (crosssq != 0)
    if exclude_self:
        assert len(points)==len(start)
        valid &= ~np.eye(len(points),dtype=bool)
    with np.errstate(divide='ignore',invalid='ignore'):
        numerator = (bsq-adb)/np.sqrt(np.sqrt(bsq**2+core4))+(asq-adb)/np.sqrt(np.sqrt(asq**2+core4))
        factor = np.divide(numerator,np.sqrt(crosssq**2+lengthsq**2*core4),
                           out=np.zeros_like(asq),where=valid)
        velocity = cross*factor[...,None]
        for r,magnitude,sign in [(a,amag,-1),(b,bmag,1)]:
            radius2 = r[:,:,1]**2+r[:,:,2]**2
            factor = np.divide(sign*(1-r[:,:,0]/magnitude),np.sqrt(radius2**2+core4),
                               out=np.zeros_like(asq),where=(magnitude!=0)&((radius2!=0)|(core4!=0)))
            velocity[:,:,1] += r[:,:,2]*factor
            velocity[:,:,2] -= r[:,:,1]*factor
    velocity *= dtype('.079577472'); velocity[:,:,0] /= beta
    return velocity
