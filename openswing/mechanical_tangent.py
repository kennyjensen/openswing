"""Physical fixed-geometry Jacobian for internal loads and reactions.

Compatibility uses the complete section compliance, including coupled axes.
Nodal balances retain offset force couples. Smooth Jangle constraints include
their moment/angle derivative. Geometry and external loads are not frozen in
any other columns: callers must assemble those separate partials in full.
"""
import numpy as np
from scipy.sparse import coo_matrix
from .structure import skew
from .local_motion import rotation_matrix,rotation_vector,left_jacobian


class MechanicalDerivativeUnavailable(ValueError):
    pass


def mechanical_columns(system, data, scales, step, *, limit=16*1024**2):
    from .source_discrete import SourceDiscreteNetwork
    source = isinstance(system.network, SourceDiscreteNetwork)
    if not source and not getattr(system.network, 'analytic_mechanics', True):
        raise MechanicalDerivativeUnavailable('The selected structural operator requires full residual mechanical derivatives.')
    if system.feedback is not None:
        raise MechanicalDerivativeUnavailable('Controller/custom measurements require complete residual derivatives.')
    if source:
        from .source_dynamics import SourceDynamicNetwork
        # These rate laws subtract geometry/motion terms independent of the
        # internal-load coordinates. An override needs its own chain rule.
        if getattr(system.network.constitutive_motion, '__func__', None) not in (
                SourceDiscreteNetwork.constitutive_motion, SourceDynamicNetwork.constitutive_motion):
            raise MechanicalDerivativeUnavailable('Unknown source rate-dependent constitutive law.')
        return source_network_mechanical_columns(system.network, data, scales, step,
            row_count=system.size, limit=limit)
    return network_mechanical_columns(system.network, data, scales, step,
        row_count=system.size, limit=limit)


def source_network_mechanical_columns(n, data, scales, step, *, row_count=None,
                                      factor=1., limit=16*1024**2):
    """Exact internal-load/reaction columns for the source box equations.

    At fixed endpoint frames, the source section law is linear in N and M.
    Its translation equation uses the transpose of the averaged endpoint
    transform, not the midpoint rotation used by the original spatial policy.
    Material damping depends on geometry and motion, not on these columns.
    Nodal balances and hinge laws retain the shared physical wrench derivative.
    """
    from .source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
    if not all(key in data for key in ('r', 'Q', 'section_frame', 'hinges')):
        raise MechanicalDerivativeUnavailable('Source mechanical state was not captured by this residual.')
    if (not isinstance(n, SourceDiscreteNetwork) or
            getattr(n.constitutive_response, '__func__', None) not in
            (SourceDiscreteNetwork.constitutive_response, SourceSectionNetwork.constitutive_response)):
        raise MechanicalDerivativeUnavailable('Unknown source constitutive load law.')
    matrix, report = network_mechanical_columns(n, data, scales, step,
        row_count=row_count, factor=factor, limit=limit)
    _, _, ra, rb, *_ = n.geometry(data['r'], data['Q'])
    ta = (np.swapaxes(ra, -1, -2)+np.swapaxes(rb, -1, -2))/2
    block = np.empty((n.ne, 6, 6))
    zero = np.zeros((n.ne, 3))
    for column in range(6):
        direction = ta[:, :, column % 3]*(n.F if column < 3 else n.F*n.L)
        # A basis evaluation of a linear map is its exact derivative; there
        # is no subtraction, perturbation size or full residual evaluation.
        strain, curvature = n.constitutive_response(direction if column < 3 else zero,
                                                   direction if column >= 3 else zero)
        block[:, :3, column] = -np.einsum('nji,nj->ni', ta, strain)*n.ds[:, None]/n.L
        block[:, 3:, column] = -curvature*n.ds[:, None]
    old = matrix.tocoo()
    keep = old.row >= 6*n.ne
    indices = np.arange(6*n.ne).reshape(n.ne, 6)
    rows = np.broadcast_to(indices[:, :, None], block.shape).ravel()
    columns = np.broadcast_to(indices[:, None, :], block.shape).ravel()
    matrix = coo_matrix((np.r_[old.data[keep], block.ravel()],
        (np.r_[old.row[keep], rows], np.r_[old.col[keep], columns])), shape=matrix.shape).tocsc()
    matrix.sum_duplicates(); matrix.eliminate_zeros()
    if not np.all(np.isfinite(matrix.data)):
        raise MechanicalDerivativeUnavailable('Nonfinite source mechanical derivative.')
    report.update(method='direct source endpoint-average compliance, nodal balances and hinge chain rule',
        nonzeros=matrix.nnz, bytes=matrix.data.nbytes+matrix.indices.nbytes+matrix.indptr.nbytes)
    return matrix, report


def network_mechanical_columns(n, data, scales, step, *, row_count=None, factor=1., limit=16*1024**2):
    """Shared physical partials at fixed geometry in either steady/dynamic charts.

    Load continuation changes the unloaded hinge angle, not its spring slope.
    This block has no state-rate dependence; external loads do not depend on
    internal beam resultants or reactions. Custom measurements need their own
    derivatives and retain the complete-residual fallback.
    """
    if n.operating.custom:
        raise MechanicalDerivativeUnavailable('Controller/custom measurements require complete residual derivatives.')
    row_count=n.size if row_count is None else row_count
    # Conservative bound for COO construction, its final CSC arrays and local
    # block temporaries. Large models retain their previous residual path.
    if (128*n.ne+48*len(n.constraints))*32>limit:
        raise MechanicalDerivativeUnavailable('Direct mechanical blocks exceed their storage budget.')
    r,q,frame=(data[key] for key in ('r','Q','section_frame'))
    pa,pb,_,_,oa,ob=n.geometry(r,q);dr=pb-pa
    rotation=np.zeros((n.ne,6,6))
    rotation[:,:3,:3]=rotation[:,3:,3:]=np.swapaxes(frame,-1,-2)
    compliance=-np.einsum('eij,ejk->eik',n.S,rotation)
    compliance*=n.ds[:,None,None]
    compliance*=np.array([n.F]*3+[n.F*n.L]*3)[None,None,:]
    compliance[:,:3]/=n.L
    rows=[];columns=[];values=[]
    def add(rr,cc,block):
        block=np.asarray(block,dtype=float)
        rows.append(np.broadcast_to(np.asarray(rr)[:,None],block.shape).ravel())
        columns.append(np.broadcast_to(np.asarray(cc)[None,:],block.shape).ravel())
        values.append(block.ravel())
    force_start=6*n.ne;moment_start=force_start+3*n.nn
    constraint_start=6*(n.ne+n.nn)
    xyz=np.arange(3);identity=np.eye(3)
    for e,(i,j) in enumerate(n.ends):
        local=6*e+np.arange(6)
        add(6*e+np.arange(6),local,compliance[e])
        add(force_start+3*i+xyz,local[:3],identity)
        add(force_start+3*j+xyz,local[:3],-identity)
        add(moment_start+3*i+xyz,local[:3],skew((dr[e]/2+oa[e])/n.L))
        add(moment_start+3*j+xyz,local[:3],skew((dr[e]/2-ob[e])/n.L))
        add(moment_start+3*i+xyz,local[3:],identity)
        add(moment_start+3*j+xyz,local[3:],-identity)
    hinge_count=0
    for c in n.constraints:
        i,j,typ=c['a'],c['b'],c['type']
        if typ not in (0,1,2,3):
            raise MechanicalDerivativeUnavailable('Unknown mechanical constraint type.')
        local=6*n.ne+np.arange(c['sl'].start,c['sl'].stop)
        if typ!=2:
            add(force_start+3*i+xyz,local[:3],identity)
            if j is not None:
                add(force_start+3*j+xyz,local[:3],-identity)
                add(moment_start+3*i+xyz,local[:3],skew((r[j]-r[i])/n.L))
        if typ!=1:
            add(moment_start+3*i+xyz,local[-3:],identity)
            if j is not None:add(moment_start+3*j+xyz,local[-3:],-identity)
        if typ==3:
            law=c['law'];e=c['element'];end=c['end'];sign=-1 if end else 1
            offset=ob[e] if end else oa[e];axis=q[i]@law.axis
            moment=next(v['structural_moment'] for v in data['hinges'] if v['joint']==law.index)
            dm=np.r_[n.F*(axis@skew(sign*dr[e]/2+offset)),n.F*n.L*axis]
            increments=2*step*np.asarray(scales)[6*n.nn+6*e+np.arange(6)]*abs(dm)
            for point in law.spline.breaks:
                if (np.any(abs(moment-point)<=increments) and not np.isclose(
                        law.spline.evaluate(point,side='left',derivative=1),
                        law.spline.evaluate(point,side='right',derivative=1),rtol=1e-7,atol=1e-12)):
                    raise MechanicalDerivativeUnavailable('Mechanical stencil reaches a Jangle slope break.')
            angle=law.angle(moment,factor)
            relative=rotation_matrix(-data.get('hinge_charts',{}).get(law.index,c.get('angle_chart',0.))*law.axis)@(q[i].T@q[j])
            vector=rotation_vector(relative)
            slope=np.deg2rad(law.spline.evaluate(moment,derivative=1))
            # This is an analytic local derivative, not a finite stencil.
            # A soft spring can rotate many turns across the nominal finite
            # difference step while its derivative at this state is regular.
            if np.linalg.norm(vector)>=np.pi-1e-7:
                raise MechanicalDerivativeUnavailable('Hinge rotation derivative approaches the logarithm branch.')
            derivative=-law.axis*slope
            add(constraint_start+c['sl'].start+3+xyz,6*e+np.arange(6),np.outer(derivative,dm))
            hinge_count+=1
    matrix=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(columns))),
        shape=(row_count,6*n.ne+n.nc)).tocsc()
    matrix.sum_duplicates();matrix.eliminate_zeros()
    if not np.all(np.isfinite(matrix.data)):
        raise MechanicalDerivativeUnavailable('Nonfinite physical mechanical derivative.')
    return matrix,dict(method='direct section compliance, nodal force couples and hinge chain rule',
        columns=matrix.shape[1],internal_columns=6*n.ne,reaction_columns=n.nc,
        hinge_constraints=hinge_count,nonzeros=matrix.nnz,
        bytes=matrix.data.nbytes+matrix.indices.nbytes+matrix.indptr.nbytes)
