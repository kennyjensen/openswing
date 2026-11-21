"""Concentric radius jumps as weak limits of the published slender-body laws.

The radius-dependent R/2 core is integrated across the area jump. It is not
replaced by an arbitrary single core. A coincident axis/tangent is necessary to
define this limit independently of an unspecified transition geometry.
"""
import numpy as np
from .geometry import surface_frame

LIMITATION='Body shoulder forces and sources are weak limits of smooth concentric radius transitions with a continuous axis/tangent and incident field. No additional separated-flow or annular-face drag is inferred; abrupt blunt steps are outside slender-body accuracy. ASWING discrete jump/core parity is unverified.'


def body_shoulders(mesh):
    beam=mesh.beam
    if beam.lifting or 'radius' not in beam.distributions:return []
    out=[]
    distribution=beam.distributions['radius']
    for k in np.flatnonzero(np.diff(distribution.t)==0):
        t=distribution.t[k]
        if not beam.domain[0]<t<beam.domain[1]:continue
        left,right=map(float,distribution.values[k:k+2])
        if min(left,right)<0:raise ValueError(f'Beam {beam.index}: shoulder radii must be nonnegative.')
        if left==right:continue
        before=np.flatnonzero(mesh.t1==t);after=np.flatnonzero(mesh.t0==t)
        if len(before)!=1 or len(after)!=1:raise ValueError('A radius jump must be an explicit mesh boundary.')
        i,j=int(before[0]),int(after[0]);a,b=mesh.r1[i],mesh.r0[j]
        scale=np.linalg.norm(a)+np.linalg.norm(b)+mesh.length[i]+mesh.length[j]
        if np.linalg.norm(b-a)>64*np.finfo(float).eps*scale:
            raise ValueError(f'Beam {beam.index}: a radius jump with an axis-position jump needs an explicit transition geometry.')
        sa=(surface_frame(beam,t,'left') if mesh.frame1 is None else mesh.frame1[i])[:,1]
        sb=(surface_frame(beam,t,'right') if mesh.frame0 is None else mesh.frame0[j])[:,1]
        if np.linalg.norm(sa-sb)>1e-8:
            raise ValueError(f'Beam {beam.index}: a radius jump at an axis-tangent break needs an explicit transition geometry.')
        tangent=(sa+sb)/np.linalg.norm(sa+sb)
        out.append(dict(beam=beam.index,physical_index=beam.physical_index,t=float(t),position=(a+b)/2,
            tangent=tangent,radius_left=left,radius_right=right,area_jump=np.pi*(right-left)*(right+left)))
    return out


def shoulder_source(displacement,radius_left,radius_right,coefficient=1.):
    """Exact integral δ/(4π) ∫dA/(|δ|²+A/(4π))**(3/2), times ξ·ell.

    This is the limit of a monotone smooth radius transition at fixed axis and
    field position. The rationalized expression also resolves small area jumps.
    Arrays broadcast; the last displacement axis is xyz. At δ=0 the value is
    zero, including a zero endpoint radius, matching the regularized kernel's
    coincident-point convention. Interior values are not resolved fluid flow.
    """
    delta=np.asarray(displacement,dtype=float);r2=np.sum(delta*delta,axis=-1)
    a=np.sqrt(r2+(np.asarray(radius_left)/2)**2);b=np.sqrt(r2+(np.asarray(radius_right)/2)**2)
    denominator=2*a*b*(a+b)
    numerator=np.asarray(coefficient)*(np.asarray(radius_right)-radius_left)*(np.asarray(radius_right)+radius_left)
    factor=np.divide(numerator,denominator,out=np.zeros_like(denominator),where=denominator>0)
    return factor[...,None]*delta
