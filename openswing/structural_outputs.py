"""Retained physical section-output C in the loaded spatial rotation chart.

Total internal loads are state unknowns; mechanical strains come from current
geometry, including material damping cases. These outputs have zero explicit
rate/input partials. See steady theory (18–20), (28–29), section 8.2, and the
unsteady perturbation output relation (133).
"""
import hashlib
import numpy as np
from scipy.sparse import coo_matrix
from .structure import skew
from .local_motion import checked_rotation_arc,left_jacobian,rotation_weights


class StructuralOutputUnavailable(ValueError):
    pass


def shell_data(network):
    values=np.zeros((network.ne,3));defined=np.zeros(network.ne,dtype=bool)
    for mesh in network.meshes:
        beam=mesh.beam;sl=network.beam_elements[beam.index]
        values[sl]=np.array([beam.value(key,mesh.ts) for key in ('Cshell','Nshell','Atshell')]).T
        defined[sl]='Cshell' in beam.distributions or 'Nshell' in beam.distributions
    return values,defined


def context(system):
    n=system.network;key=hashlib.sha256();shell,defined=shell_data(n)
    parameters=np.array([[s.Cta,s.Nta,s.Cea,s.Nea] for s in n.sections])
    def add(value):
        array=np.asarray(value)
        if not np.all(np.isfinite(array)):
            raise StructuralOutputUnavailable('Nonfinite section-output context.')
        key.update(repr((array.shape,array.dtype.str)).encode());key.update(array.tobytes())
    for value in ([n.nn,n.ne,system.size,n.L,n.F,system.L],n.ends,n.ds,n.R0a,n.R0b,
                  n.offa,n.offb,system.r0,system.Q0,system.base[6*n.nn:6*(n.nn+n.ne)],
                  parameters,shell,defined):add(value)
    return key.digest(),parameters,shell,defined


class StructuralOutputTangent:
    def __init__(self,system,*,limit=32*1024**2):
        self.owner=system;n=system.network
        if not getattr(n, 'analytic_mechanics', True):
            raise StructuralOutputUnavailable('The selected structural operator requires physical section-output stencils.')
        # Bound local dense blocks, triplet arrays and sparse construction.
        if n.ne*15*18*96>limit:
            raise StructuralOutputUnavailable('Section-output matrix exceeds its storage budget.')
        self.signature,parameters,self.shell,self.defined=context(system)
        pa,pb,ra,rb,oa,ob=n.geometry(system.r0,system.Q0)
        try:k=checked_rotation_arc(ra,rb)
        except ValueError as exc:raise StructuralOutputUnavailable(str(exc)) from exc
        self.arc=np.linalg.norm(k,axis=1)
        _,frame=n.constitutive_frame(ra,rb);rt=np.swapaxes(frame,-1,-2)
        wa,wb=rotation_weights(ra,rb,.5)
        dk=np.linalg.solve(left_jacobian(k),np.swapaxes(ra,-1,-2))
        loads=system.base[6*n.nn:6*(n.nn+n.ne)].reshape(n.ne,6)*np.array([n.F]*3+[n.F*n.L]*3)
        rows=[];columns=[];values=[]
        for e,(i,j) in enumerate(n.ends):
            block=np.zeros((15,18));dr=pb[e]-pa[e]
            # Columns: both endpoint [position,spatial angle], internal [N,M].
            theta=np.c_[np.zeros((3,3)),wa[e],np.zeros((3,3)),wb[e]]
            endpoint=np.c_[-system.L*np.eye(3),skew(oa[e]),system.L*np.eye(3),-skew(ob[e])]
            block[:3,:12]=rt[e]@skew(loads[e,:3])@theta
            block[3:6,:12]=rt[e]@skew(loads[e,3:])@theta
            block[:3,12:15]=n.F*rt[e]
            block[3:6,15:]=n.F*n.L*rt[e]
            block[6:9,:12]=rt[e]@(endpoint+skew(dr)@theta)/n.ds[e]
            block[9:12,3:6]=-dk[e]/n.ds[e]
            block[9:12,9:12]=dk[e]/n.ds[e]
            cta,nta,cea,nea=parameters[e];cs,ns,area=self.shell[e]
            block[12]=block[7]-nta*block[9]+cta*block[11]
            if self.defined[e]:block[13]=block[12]+cs*block[11]-ns*block[9]
            if area>0:block[14]=(block[4]-nea*block[0]+cea*block[2])/(2*area)
            rr,cc=np.nonzero(block)
            indices=np.r_[6*i+np.arange(6),6*j+np.arange(6),6*n.nn+6*e+np.arange(6)]
            rows.append(15*e+rr);columns.append(indices[cc]);values.append(block[rr,cc])
        self.matrix=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(columns))),
            shape=(15*n.ne,system.size)).tocsr()
        self.matrix.sum_duplicates();self.matrix.eliminate_zeros()
        if not np.all(np.isfinite(self.matrix.data)):
            raise StructuralOutputUnavailable('Nonfinite physical section-output derivative.')
        self.bytes=sum(v.nbytes for v in (self.matrix.data,self.matrix.indices,self.matrix.indptr))
        if self.bytes>limit:raise StructuralOutputUnavailable('Section-output matrix exceeds its storage budget.')
        for array in (self.matrix.data,self.matrix.indices,self.matrix.indptr,self.arc,self.shell,self.defined):
            array.flags.writeable=False

    def matches(self,system):
        return self.owner is system and self.signature==context(system)[0]

    def apply(self,vector,step,snapshots):
        n=self.owner.network
        if any(s['structure']['strain_source']!='current_geometry' for s in snapshots):
            raise StructuralOutputUnavailable('Section output uses a different strain recovery law.')
        theta=np.asarray(vector)[:6*n.nn].reshape(n.nn,6)[:,3:]
        excursion=np.maximum(*[np.linalg.norm(part(theta)[n.a],axis=1)+
            np.linalg.norm(part(theta)[n.b],axis=1) for part in (np.real,np.imag)])*abs(step)
        if np.any(self.arc+excursion>=np.pi-1e-7):
            raise StructuralOutputUnavailable('Section-output stencil approaches the rotation logarithm branch.')
        value=(self.matrix@vector).reshape(n.ne,15)
        return [dict(force_local=v[:3],moment_local=v[3:6],strain=v[6:9],curvature_change=v[9:12],
            axial_strain_tension=v[12],shell_strain=v[13] if self.defined[e] else None,
            shell_shear_stress=v[14] if self.shell[e,2]>0 else None) for e,v in enumerate(value)]


def structural_outputs(system,vector,step,snapshots):
    try:
        tangent=getattr(system,'_structural_output_tangent',None)
        if tangent is None or not tangent.matches(system):
            tangent=StructuralOutputTangent(system);system._structural_output_tangent=tangent
        values=tangent.apply(vector,step,snapshots)
    except StructuralOutputUnavailable as exc:
        system.structural_output_diagnostics=dict(method='physical output stencils',fallback=str(exc))
        return None
    system.structural_output_diagnostics=dict(method='retained analytic section C matrix',
        rows=tangent.matrix.shape[0],nonzeros=tangent.matrix.nnz,cached_bytes=tangent.bytes,
        rate_and_input_terms='zero',fallback=None)
    return values


def compatibility_columns(system):
    """Reuse section C for the stationary beam constitutive residual rows.

    R = ds * (geometric strain - S * local resultant), with the translation
    rows additionally divided by L. Material damping belongs to local-motion
    columns and must be retained separately by the caller.
    """
    from scipy.sparse import block_diag, diags, csr_matrix
    n=system.network
    if not getattr(n, 'analytic_mechanics', True):
        raise StructuralOutputUnavailable('The selected structural operator requires full residual compatibility derivatives.')
    tangent=getattr(system,'_structural_output_tangent',None)
    if tangent is None or not tangent.matches(system):
        tangent=StructuralOutputTangent(system)
        system._structural_output_tangent=tangent
    indices=15*np.arange(n.ne)[:,None]+np.arange(6)
    c=tangent.matrix[:,:n.size]
    compliance=block_diag([csr_matrix(block) for block in n.S],format='csr')
    deformation=c[(indices+6).ravel()]-compliance@c[indices.ravel()]
    scale=(n.ds[:,None]*np.array([1/n.L]*3+[1.]*3)[None,:]).ravel()
    matrix=(diags(scale)@deformation).tocsc()
    if not np.all(np.isfinite(matrix.data)):
        raise StructuralOutputUnavailable('Nonfinite constitutive derivative.')
    return matrix
