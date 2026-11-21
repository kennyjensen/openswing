"""Final equilibrium derivatives retained in the dynamic spatial-rotation chart.

Only a tangent freshly assembled at the corrected physical state is retained.
The steady rank check uses its absolute-rotation columns; Bode uses the original
spatial columns, without transforming a finite-difference matrix back again.
Iteration tangents, imported certificates and lagged influences are not reused.
"""
from copy import deepcopy
from dataclasses import asdict,is_dataclass
import hashlib
import json
import numpy as np
from scipy.sparse import issparse,coo_matrix
from .time_state import condition_data, motion_data, portable


def digest(value):
    def encode(v):
        if is_dataclass(v):return encode(asdict(v))
        if isinstance(v,np.ndarray):return encode(v.tolist())
        if isinstance(v,np.generic):return v.item()
        if isinstance(v,dict):return {str(k):encode(x) for k,x in v.items()}
        if isinstance(v,(tuple,list)):return [encode(x) for x in v]
        return v
    return hashlib.sha256(json.dumps(encode(value),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def identity(system):
    n = system.network
    # Include the actual physical data, not just the original ASW text. Cache
    # counters and last evaluated loads do not define the residual operator.
    def arrays(obj):
        return {key:value for key,value in vars(obj).items() if isinstance(value,np.ndarray)}
    context=dict(model=n.model.dumps(canonical=True),
        system=arrays(system),network=arrays(n),
        meshes=[arrays(mesh) for mesh in n.meshes],
        condition=condition_data(n.condition),motion=motion_data(n.motion),
        base_condition=condition_data(system.condition),base_motion=motion_data(system.motion),
        frame=system.frame,gravity_magnitude=system.gravity_magnitude,
        gravity_override=n.gravity_override,loads=n.loads,wire=n.tension_only,
        scales=[n.L,n.F,n.gamma_scale,system.L,system.V,system.W,system.Ascale],
        dimensions=[n.nn,n.ne,n.nc,n.ng,n.size,n.gamma_start,n.operating_start,system.size,
                    system.velocity_start,system.frame_start,system.feedback_start],
        operating=dict(constraints=[asdict(c) for c in n.operating.constraints],
                       base=n.operating.base,scale=n.operating.scale),
        circulation=dict(sample=n.circulation_basis.sample,test=n.circulation_basis.test))
    from .beam_spline import NATURAL
    if n.model.beam_interpolation != NATURAL:
        context['beam_interpolation']=n.model.beam_interpolation
    if getattr(n, 'structural_operator', None) is not None:
        context['structural_operator']=n.structural_operator
    return digest(context)


class EquilibriumTangent:
    def __init__(self, system, matrix, step):
        self.owner, self.step, self.sparse = system, step, issparse(matrix)
        self.signature = identity(system)
        self.matrix = matrix.copy()
        for value in ((self.matrix.data,self.matrix.indices,self.matrix.indptr) if self.sparse else (self.matrix,)):
            value.flags.writeable = False
        self.diagnostics = deepcopy(system.state_derivative_diagnostics)

    def matches(self, system, step, sparse):
        return (self.owner is system and self.step == step and self.sparse == sparse
                and system.feedback is None and self.signature == identity(system))


def retain_for_rank(system, absolute_state, step, *, sparse, progress=None):
    """Assemble once; return the same physical derivative in the steady chart."""
    from .linear_dynamics import linearize
    from .local_motion import left_jacobian
    matrix = linearize(system,step,progress,sparse=sparse,_stationary=True,_output_fields=sparse)
    n = system.network
    rank = matrix[:n.size,:].copy()
    # exp(theta + dtheta) = exp(J_left(theta) dtheta) exp(theta) + O(dtheta²).
    # The rank gate retains its previous column normalization and threshold.
    angles = absolute_state[:6*n.nn].reshape(n.nn,6)[:,3:]
    transforms=left_jacobian(angles)
    if sparse:
        # A sparse change of chart keeps the shared physical tangent sparse
        # through the constraint check. The retained spatial columns are untouched.
        rotations=6*np.arange(n.nn)[:,None]+np.arange(3,6)
        identity=np.ones(n.size,dtype=bool);identity[rotations.ravel()]=False
        indices=np.flatnonzero(identity)
        rows=np.broadcast_to(rotations[:,:,None],transforms.shape).ravel()
        cols=np.broadcast_to(rotations[:,None,:],transforms.shape).ravel()
        chart=coo_matrix((np.r_[np.ones(len(indices)),transforms.ravel()],
            (np.r_[indices,rows],np.r_[indices,cols])),shape=(n.size,n.size)).tocsc()
        rank=(rank@chart).tocsc()
    else:
        for i, transform in enumerate(transforms):
            sl = slice(6*i+3,6*i+6)
            rank[:,sl] = rank[:,sl]@transform
    system._equilibrium_tangent = EquilibriumTangent(system,matrix,step)
    return rank
