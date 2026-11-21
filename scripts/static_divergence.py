"""Full static-block divergence for J(q) = [[A, q B], [C, D]].

The caller must establish this pressure scaling from physical equations.
Mechanical elimination is exact; every circulation coordinate is retained.
This finds a zero-frequency condition, not a general flutter boundary.
"""
import numpy as np
from scipy.linalg import eig
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu


def first_divergence(a, b, c, d, speed):
    a,b,c,d = [csc_matrix(x) for x in (a,b,c,d)]
    ns,ng = a.shape[0],d.shape[0]
    if (a.shape!=(ns,ns) or b.shape!=(ns,ng) or c.shape!=(ng,ns)
            or d.shape!=(ng,ng) or not np.isfinite(speed) or speed<=0
            or not all(np.all(np.isfinite(x.data)) for x in (a,b,c,d))):
        raise ValueError('Divergence blocks need compatible finite dimensions and a positive speed.')
    factor = splu(a)
    def solve(rhs, trans='N'):
        if np.iscomplexobj(rhs) and not np.iscomplexobj(a.data):
            return factor.solve(rhs.real,trans=trans)+1j*factor.solve(rhs.imag,trans=trans)
        return factor.solve(rhs,trans=trans)
    response = solve(b.toarray())
    ratios,lefts,rights = eig(d.toarray(),np.asarray(c@response),left=True,right=True)
    selected = [i for i,z in enumerate(ratios) if np.isfinite(z)
                and z.real>0 and abs(z.imag)<1e-10*max(1.,abs(z.real))]
    if not selected:
        raise ValueError('No finite positive real pressure singularity was found.')
    index = min(selected,key=lambda i:ratios[i].real)
    ratio = float(ratios[index].real)
    gamma = rights[:,index]
    right = np.r_[-ratio*(response@gamma),gamma]
    left = np.r_[-solve(c.conj().T@lefts[:,index],trans='H'),lefts[:,index]]
    right /= right[np.argmax(abs(right))]
    left /= left[np.argmax(abs(left))]
    right_product = np.r_[a@right[:ns]+ratio*(b@right[ns:]),c@right[:ns]+d@right[ns:]]
    left_product = np.r_[a.conj().T@left[:ns]+c.conj().T@left[ns:],
                         ratio*(b.conj().T@left[:ns])+d.conj().T@left[ns:]]
    row_norms = np.r_[np.asarray(abs(a).sum(axis=1)+ratio*abs(b).sum(axis=1)).ravel(),
                     np.asarray(abs(c).sum(axis=1)+abs(d).sum(axis=1)).ravel()]
    col_norms = np.r_[np.asarray(abs(a).sum(axis=0)+abs(c).sum(axis=0)).ravel(),
                     np.asarray(ratio*abs(b).sum(axis=0)+abs(d).sum(axis=0)).ravel()]
    critical = speed*np.sqrt(ratio)
    derivative = np.r_[2*critical/speed**2*(b@right[ns:]),np.zeros(ng)]
    pairing = complex(np.vdot(left,derivative))
    if not np.isfinite(pairing) or abs(pairing)==0:
        raise ValueError('Static mode has zero or invalid speed sensitivity.')
    return dict(speed=float(critical),pressure_ratio=ratio,right=right,left=left,
        speed_action=derivative,mechanical_size=ns,circulation_size=ng,
        right_backward_error=float(np.linalg.norm(right_product,np.inf)/(max(row_norms)*np.linalg.norm(right,np.inf))),
        left_backward_error=float(np.linalg.norm(left_product,np.inf)/(max(col_norms)*np.linalg.norm(left,np.inf))),
        matrix_norm=float(max(row_norms)),positive_pressure_candidates=len(selected))
