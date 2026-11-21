"""Checked local Newton correction of a simple full-pencil Ritz pair.

The bordered system retains every descriptor coordinate. It fixes one vector
component while correcting A v - lambda M v, without changing either matrix.
An adjoint solve can reuse the last bordered LU for left-vector recovery.
"""
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu, norm


def bordered_matrix(a, m, value, mass_action, rows, pivot):
    """Build [[(A-lambda M)/rows, -Mv/rows], [e_p^T, 0]] in CSC storage.

    Append the normalization row to column p and the pole correction as the
    last column. Direct assembly avoids CSR/COO copies of the full pencil.
    """
    pencil = (a-value*m).tocsc()
    pencil.data *= (1/rows)[pencil.indices]
    n = pencil.shape[0]
    column = -mass_action/rows
    column_rows = np.flatnonzero(column)
    count = pencil.nnz+1+len(column_rows)
    index_type = np.int32 if max(n+1, count) <= np.iinfo(np.int32).max else np.int64
    data = np.empty(count, dtype=np.result_type(pencil.dtype, column.dtype))
    indices = np.empty(count, dtype=index_type)
    pointers = np.empty(n+2, dtype=index_type)
    edge = int(pencil.indptr[pivot+1])
    data[:edge] = pencil.data[:edge]
    indices[:edge] = pencil.indices[:edge]
    data[edge], indices[edge] = 1., n
    data[edge+1:pencil.nnz+1] = pencil.data[edge:]
    indices[edge+1:pencil.nnz+1] = pencil.indices[edge:]
    data[pencil.nnz+1:] = column[column_rows]
    indices[pencil.nnz+1:] = column_rows
    pointers[:n+1] = pencil.indptr
    pointers[pivot+1:n+1] += 1
    pointers[-1] = count
    return csc_matrix((data, indices, pointers), shape=(n+1, n+1), copy=False)


def refine_simple_pair(a, m, value, vector, *, max_iterations=2):
    a,m=csc_matrix(a),csc_matrix(m)
    original=complex(value)
    v=np.asarray(vector,dtype=complex).copy()
    pivot=int(np.argmax(abs(v)))
    report=dict(status='UNCHANGED',factorizations=0,corrections=0,
        trigger=512*np.finfo(float).eps,target=64*np.finfo(float).eps,
        left_reused=False,reason=None)
    if not np.all(np.isfinite(v)) or not abs(v[pivot]):
        report['reason']='invalid_vector'
        return original,vector,None,report
    v/=v[pivot];value=original
    def defect(lam,w):
        av,mv=a@w,m@w
        residual=av-lam*mv
        scale=np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)
        error=float(np.linalg.norm(residual)/max(scale,np.finfo(float).tiny))
        return residual,mv,error
    residual,mv,error=defect(value,v)
    report.update(initial_relative_residual=error,final_relative_residual=error)
    if not np.isfinite(error) or error<=report['trigger']:
        report['reason']='already_accurate' if np.isfinite(error) else 'nonfinite_residual'
        return value,v,None,report
    left=None
    for _ in range(max_iterations):
        rows=np.maximum(np.asarray(abs(a).sum(axis=1)).ravel()+abs(value)*np.asarray(abs(m).sum(axis=1)).ravel(),1e-30)
        border=bordered_matrix(a,m,value,mv,rows,pivot)
        report['factorizations']+=1
        factor=None
        try:
            try:
                factor=splu(border)
                correction=factor.solve(np.r_[-residual/rows,0j])
            except RuntimeError:
                report['reason']='singular_border'
                break
            candidate_value=value+correction[-1]
            candidate=v+correction[:-1]
            if (not np.isfinite(candidate_value) or not np.all(np.isfinite(candidate))
                    or abs(candidate_value-original)>1e-6*max(1.,abs(original))):
                report['reason']='nonlocal_or_nonfinite_correction'
                break
            trial,trial_mv,trial_error=defect(candidate_value,candidate)
            if not np.isfinite(trial_error) or trial_error>=error:
                report['reason']='no_residual_improvement'
                break
            value,v,residual,mv,error=candidate_value,candidate,trial,trial_mv,trial_error
            report.update(status='REFINED',corrections=report['corrections']+1,final_relative_residual=error)
            # Recover the adjoint while this LU is available. Retaining it for
            # later recovery would overlap two large factors on the next step.
            left=_checked_left(a,m,value,v,mv,factor,rows,report)
            if error<=report['target']:
                report['reason']='target_reached'
                break
        finally:
            del factor,border
    report['relative_root_correction']=float(abs(value-original)/max(1.,abs(original)))
    return value,v,left,report


def _checked_left(a,m,value,v,mv,factor,rows,report):
    # B^H [y,eta] = [0,-1] gives w=y/rows and w^H M v=1 at an
    # exact simple pole. Check the actual corrected pair before reuse.
    report['left_reused']=False
    report.pop('left_backward_error',None)
    report.pop('mass_pairing_error',None)
    trial=factor.solve(np.r_[np.zeros(len(v),dtype=complex),-1.+0j],trans='H')[:-1]/rows
    pairing=np.vdot(trial,mv)
    pairing_scale=np.linalg.norm(trial)*np.linalg.norm(mv)
    if (np.all(np.isfinite(trial)) and np.isfinite(pairing) and pairing_scale>0
            and abs(pairing)>100*np.finfo(float).eps*pairing_scale):
        trial/=np.conj(pairing)
        residual_left=a.conj().T@trial-value.conjugate()*(m.conj().T@trial)
        backward=float(np.linalg.norm(residual_left)/((norm(a)+abs(value)*norm(m))*np.linalg.norm(trial)))
        mass_error=float(abs(np.vdot(trial,mv)-1))
        report.update(left_backward_error=backward,mass_pairing_error=mass_error)
        if backward<=1e-10 and mass_error<=1e-10:
            report['left_reused']=True
            return trial
    return None
