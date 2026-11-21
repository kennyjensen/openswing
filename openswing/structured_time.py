"""Sparse local BDF mechanics with circulation/frame Schur complement.

Nonlocal aerodynamic geometry/jet fields are lagged only in the Newton matrix.
The caller always uses the original complete residual for step acceptance.
Net force/moment rows use the same nodal external loads as the full residual.
Inverse actuator constraints and controllers retain their general solver.
Structured Radau also uses this assembler for continuous state/rate partials.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import warnings
import numpy as np
from scipy.sparse import coo_matrix
from .sparse_rank import structural_rank
from scipy.sparse.linalg import splu
from scipy.linalg import lu_factor, lu_solve, LinAlgWarning
from .structured_static import (IterationFields, StructuredMatrix,
    StructuredTangentUnavailable, structural_column_rows, coloring,
    acceleration_load_constraints, frame_load_pattern, full_fields)
from .tangent_influences import TangentInfluences


def eligible(system):
    n=system.network
    return (system.feedback is None and system.position_lift is None
            and acceleration_load_constraints(n))


def pattern(system):
    """Conservative support of local geometry, resultants, reactions and rates."""
    if not eligible(system):
        raise StructuredTangentUnavailable('Structured BDF matrix requires prescribed or load-constrained frame motion without inverse actuators or feedback.')
    n=system.network
    rows=[set(r) for r in structural_column_rows(n)]
    velocity_rows=[]
    for node in range(n.nn):
        kinematics={n.size+offset+3*node+k for offset in (0,3*n.nn) for k in range(3)}
        support=rows[6*node].copy()|kinematics
        for column in range(6*node,6*node+6):rows[column].update(kinematics)
        velocity_rows.append(support)
    # The public time vector stores all translational rates before angular rates.
    for _ in range(2):
        for support in velocity_rows:
            rows.extend(support.copy() for _ in range(3))
    rows=[np.array(sorted(r),dtype=int) for r in rows]
    local=np.r_[np.arange(n.gamma_start),np.arange(n.size,system.frame_start)]
    border=np.r_[np.arange(n.gamma_start,n.size),np.arange(system.frame_start,system.size)]
    return local,border,rows,coloring(rows)


@contextmanager
def linearization(system,function,x,*,capture_circulation=False,capture_mechanics=False):
    n=system.network
    fields=IterationFields()
    # Zero base rates can become nonzero in velocity columns. Capture the
    # axis-induced velocity at the unperturbed geometry before that branch opens.
    fields.capture_rate_fields=True
    fields.capture_circulation=capture_circulation
    fields.capture_mechanics=capture_mechanics
    fields.mechanical_data={}
    fields.capture_frame_loads=bool(n.operating.count)
    old_fields,old_pairs=n.iteration_fields,n.tangent_influences
    n.iteration_fields,n.tangent_influences=fields,TangentInfluences()
    n.aero_key=None
    try:
        base=function(x)
        fields.phase='geometry'
        yield fields,base
    finally:
        n.iteration_fields,n.tangent_influences=old_fields,old_pairs
        n.aero_key=None


def jacobian(system,function,x,*,grouped=True,progress=None,circulation_rate_factor=None,direct_mechanics=True):
    """Assemble sparse local columns directly; never allocate a global dense J."""
    if not hasattr(system,'_time_pattern'):system._time_pattern=pattern(system)
    local,border,rows,groups=system._time_pattern
    permutation=np.r_[local,border]
    inverse=np.argsort(permutation)
    nlocal=len(local)
    load_nodes,load_components,load_scales=frame_load_pattern(system.network,rows)
    rr=[];cc=[];vv=[]
    coupling=np.empty((system.size,len(border)))
    total=(len(groups) if grouped else nlocal)+len(border)
    done=0;before=system.network.nfev
    derivative_method='forward differences';derivative_fallback=None
    capture=circulation_rate_factor is not None and system.network.ng > 0
    from .source_discrete import SourceDiscreteNetwork
    mechanical_capture=direct_mechanics and isinstance(system.network,SourceDiscreteNetwork)
    mechanical_report=mechanical_fallback=None
    with linearization(system,function,x,capture_circulation=capture,capture_mechanics=mechanical_capture) as (fields,base):
        active_groups=groups if grouped else [np.array([i]) for i in range(nlocal)]
        mechanical=None
        if mechanical_capture:
            from .mechanical_tangent import source_network_mechanical_columns,MechanicalDerivativeUnavailable
            try:
                mechanical,mechanical_report=source_network_mechanical_columns(system.network,
                    fields.mechanical_data,np.maximum(1.,abs(x)),1e-6,row_count=system.size)
            except MechanicalDerivativeUnavailable as exc:
                mechanical_fallback=str(exc)
            else:
                # Internal loads/reactions occupy the same leading local
                # columns in both the physical and permuted time vectors.
                block=mechanical.tocoo()
                rr.append(inverse[block.row]);cc.append(block.col+6*system.network.nn);vv.append(block.data)
                remaining=np.r_[np.arange(6*system.network.nn),np.arange(system.network.gamma_start,nlocal)]
                if grouped:
                    if not hasattr(system,'_time_nonmechanical_groups'):
                        system._time_nonmechanical_groups=[remaining[g] for g in coloring([rows[i] for i in remaining])]
                    active_groups=system._time_nonmechanical_groups
                else:
                    active_groups=[np.array([i]) for i in remaining]
        total=len(active_groups)+int(mechanical is not None)+len(border)
        direct=None
        if capture:
            from .circulation_tangent import circulation_columns,CirculationDerivativeUnavailable
            try:
                direct=circulation_columns(system.network,fields,1.,
                    circulation_rate_factor=circulation_rate_factor)
                derivative_method='direct BDF circulation blocks'
                total=len(active_groups)+int(mechanical is not None)+1+len(border)-system.network.ng
            except CirculationDerivativeUnavailable as exc:
                derivative_fallback=str(exc)
        if progress is not None:progress('time_tangent',0,total)
        if mechanical is not None:
            done+=1
            if progress is not None:progress('time_tangent',done,total)
        base_loads=fields.frame_loads.copy() if fields.capture_frame_loads else None
        for columns in active_groups:
            indices=local[columns]
            h=1e-6*np.maximum(1.,abs(x[indices]))
            trial=x.copy();trial[indices]+=h
            difference=function(trial)-base
            load_difference=None if base_loads is None else fields.frame_loads-base_loads
            for column,step in zip(columns,h):
                support=rows[column] if grouped else np.arange(system.size)
                values=difference[support]/step
                if grouped and load_difference is not None:
                    wrench=load_difference[load_nodes[column]].sum(axis=0)
                    support=np.r_[support,np.arange(system.network.operating_start,system.network.size)]
                    values=np.r_[values,wrench[load_components]/load_scales/step]
                nonzero=values!=0
                rr.append(inverse[support[nonzero]])
                cc.append(np.full(np.count_nonzero(nonzero),column,dtype=int))
                vv.append(values[nonzero])
            done+=1
            if progress is not None:progress('time_tangent',done,total)
        # These trials keep geometry and motion fixed, and include Gamma-dot.
        fields.phase='circulation'
        if direct is not None:
            coupling[:,:system.network.ng]=0
            coupling[inverse[:system.network.size],:system.network.ng]=direct
            done+=1
            if progress is not None:progress('time_tangent',done,total)
        else:
            for j,column in enumerate(border[:system.network.ng]):
                h=1e-6*max(1.,abs(x[column]));trial=x.copy();trial[column]+=h
                coupling[:,j]=(function(trial)-base)[permutation]/h
                done+=1
                if progress is not None:progress('time_tangent',done,total)
        # Frame motion changes global loads, flow, gravity and gust pose. Exact
        # pair reuse remains valid; geometry-lagged fields must be disabled.
        with full_fields(system.network):
            base=function(x)
            for j in range(system.network.ng,len(border)):
                column=border[j];h=1e-6*max(1.,abs(x[column]));trial=x.copy();trial[column]+=h
                coupling[:,j]=(function(trial)-base)[permutation]/h
                done+=1
                if progress is not None:progress('time_tangent',done,total)
    sparse=coo_matrix((np.concatenate(vv),(np.concatenate(rr),np.concatenate(cc))),
                      shape=(system.size,nlocal)).tocsc()
    matrix=StructuredMatrix(sparse[:nlocal],coupling[:nlocal],sparse[nlocal:],coupling[nlocal:])
    return matrix,permutation,dict(groups=len(active_groups),columns=system.size,
        evaluations=system.network.nfev-before,matrix_storage_bytes=matrix.storage_bytes,
        circulation_derivative=derivative_method,circulation_derivative_fallback=derivative_fallback,
        mechanical_derivative=mechanical_report,mechanical_derivative_fallback=mechanical_fallback)


@dataclass
class Factorization:
    matrix: StructuredMatrix
    permutation: np.ndarray

    def __post_init__(self):
        a,b,c,d=(self.matrix.mechanical,self.matrix.force_circulation,
                 self.matrix.flow_geometry,self.matrix.circulation)
        if not all(np.all(np.isfinite(v)) for v in (a.data,b,c.data,d)):
            raise ValueError('Nonfinite structured time matrix.')
        if structural_rank(a)<a.shape[0]:
            raise ValueError('Structurally singular local time block; use the full matrix.')
        self.local=splu(a)
        self.coupling=self.local.solve(b)
        with warnings.catch_warnings():
            warnings.simplefilter('error',LinAlgWarning)
            self.border=lu_factor(d-c@self.coupling)

    def solve(self,rhs):
        rhs=rhs[self.permutation];split=self.matrix.mechanical.shape[0]
        solution=self._solve_blocks(rhs,split)
        # Back substitution subtracts two possibly large local solutions.
        # Small constrained motions can be lost even when the global norm
        # of the linear residual is tiny. Refine the original block equations
        # with the existing factors; do not rebuild or densify the matrix.
        # Double precision suffices, including in the browser runtime.
        for _ in range(3):
            defect=rhs-self._product(solution,split)
            if not np.any(defect):break
            solution+=self._solve_blocks(defect,split)
        product=self._product(solution,split)
        if not np.all(np.isfinite(solution)) or np.max(abs(product-rhs))>1e-8*max(1.,np.max(abs(rhs))):
            raise ValueError('Structured time linear solve failed its residual check.')
        original=np.empty_like(solution);original[self.permutation]=solution
        return original

    def _solve_blocks(self,rhs,split):
        local=self.local.solve(rhs[:split])
        border=lu_solve(self.border,rhs[split:]-self.matrix.flow_geometry@local)
        return np.r_[local-self.coupling@border,border]

    def _product(self,solution,split):
        local,border=solution[:split],solution[split:]
        return np.r_[self.matrix.mechanical@local+self.matrix.force_circulation@border,
                     self.matrix.flow_geometry@local+self.matrix.circulation@border]


def attach(system,function,progress=None,*,circulation_rate_factor=None):
    if not eligible(system):return
    def build(x):
        matrix,permutation,_=jacobian(system,function,x,progress=progress,
            circulation_rate_factor=circulation_rate_factor)
        return Factorization(matrix,permutation)
    function.factorization_builder=build
