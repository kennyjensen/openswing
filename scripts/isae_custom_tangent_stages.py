"""Partition the existing custom-trim verification without changing its math.

Diagnostic support only; production continues to use check_custom_tangent.
Every centered column and every one-sided custom-row stencil remains required.
"""
from contextlib import nullcontext
import numpy as np


def columns(operating, residual, x, start, first, stop, *, derivative_context=None):
    if not 0 <= first < stop <= len(x):
        raise ValueError('Invalid tangent column interval.')
    slots = [start+i for i,c in enumerate(operating.constraints) if c.quantity in operating.custom]
    if not slots:
        raise ValueError('Custom rows are required.')
    magnitudes = np.array([max(1.,abs(c.target)/c.residual_scale,
        abs(operating.initial_values[i])/c.residual_scale if operating.initial_values is not None else 0.)
        for i,c in enumerate(operating.constraints) if c.quantity in operating.custom])
    base = np.asarray(residual(x));jac = np.empty((len(base),stop-first));mismatch = 0.
    with nullcontext() if derivative_context is None else derivative_context(x):
        for k,j in enumerate(range(first,stop)):
            h = 1e-6*max(1.,abs(x[j]));a=x.copy();b=x.copy();a[j]+=h;b[j]-=h
            plus=np.asarray(residual(a));minus=np.asarray(residual(b));jac[:,k]=(plus-minus)/(2*h)
            a[j]+=h;b[j]-=h
            left=(3*base[slots]-4*minus[slots]+np.asarray(residual(b))[slots])/(2*h)
            right=(-3*base[slots]+4*plus[slots]-np.asarray(residual(a))[slots])/(2*h)
            roundoff=32*np.finfo(float).eps*magnitudes/h
            scaled=abs(left-right)/(1e-7+roundoff+2e-3*np.maximum(abs(left),abs(right)))
            mismatch=max(mismatch,float(np.max(scaled)))
    if not np.all(np.isfinite(jac)) or not np.isfinite(mismatch):
        raise ValueError('Nonfinite tangent evidence.')
    return dict(first=first,stop=stop,jacobian=jac,mismatch=mismatch,base=base,
                residual_evaluations=1+4*(stop-first))


def assemble(blocks, size):
    blocks = sorted(blocks,key=lambda b:b['first']);cursor=0
    for b in blocks:
        if b['first'] != cursor or not cursor < b['stop'] <= size:
            raise ValueError('Missing, duplicated or overlapping tangent columns.')
        if np.shape(b['jacobian']) != (size,b['stop']-cursor):
            raise ValueError('Tangent column shape differs from complete system.')
        if not np.all(np.isfinite(b['jacobian'])) or not np.isfinite(b['mismatch']):
            raise ValueError('Nonfinite tangent evidence.')
        cursor=b['stop']
    if cursor != size:
        raise ValueError('Missing, duplicated or overlapping tangent columns.')
    return np.concatenate([b['jacobian'] for b in blocks],axis=1), max(b['mismatch'] for b in blocks)


def conclude(blocks, size):
    jac,mismatch=assemble(blocks,size)
    if mismatch>1:
        raise ValueError('Custom trim has inconsistent one-sided tangents.')
    norms=np.linalg.norm(jac,axis=0)
    singular=np.linalg.svd(jac/np.maximum(norms,1e-30),compute_uv=False)
    reciprocal=float(singular[-1]/singular[0])
    if reciprocal<1e-10:
        raise ValueError('Custom trim tangent is singular.')
    return dict(one_sided_tangent_ratio=mismatch,column_scaled_reciprocal_condition=reciprocal,
        difference_step=1e-6,columns_checked=size,rows_checked=size,
        centered_evaluations=2*size,one_sided_extra_evaluations=2*size)
