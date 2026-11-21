"""Sparse mounted equilibrium following Drela's steady theory, section 4.6.

Only the Newton matrix lags nonlocal aerodynamic geometry between rebuilds.
Full physical residuals update the current geometry and all induced fields.
Local mechanical equations use sparse LU; circulation uses their small dense
Schur complement. General joints retain their sparse graph connections.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import warnings
import numpy as np
from scipy import __version__ as scipy_version
from scipy.linalg import solve, lu_factor, lu_solve, LinAlgWarning
from scipy.linalg.lapack import get_lapack_funcs
from scipy.sparse import csc_matrix, coo_matrix, diags, issparse
from .sparse_rank import structural_rank
from scipy.sparse.linalg import splu
from .tangent_influences import TangentInfluences


class StructuredTangentUnavailable(ValueError):
    """A context outside the bounded structured linearization's scope."""


def acceleration_load_constraints(net):
    """Only the canonical frame acceleration/net-load pairs, or no constraints."""
    from .operating import OperatingConstraint
    pairs={f'{variable}.{axis}':f'{quantity}.{axis}'
           for variable,quantity in [('acceleration','force'),('angular_acceleration','moment')]
           for axis in 'xyz'}
    return (net.operating.count == len(net.operating.constraints)
            and all(type(c) is OperatingConstraint and pairs.get(c.variable) == c.quantity
                    for c in net.operating.constraints))


def load_kinematic_constraints(net):
    """Rows whose pose/circulation partials are loads or identically zero.

    Flight path is a function of the operating condition's velocity and Earth
    attitude, independent of elastic geometry and circulation. This does not
    admit its operating-variable partials; those still use the full residual.
    """
    from .operating import OperatingConstraint
    quantities={f'{kind}.{axis}' for kind in ('force','moment') for axis in 'xyz'}|{'flight_path'}
    return (net.operating.count == len(net.operating.constraints)
            and all(type(c) is OperatingConstraint and c.quantity in quantities
                    for c in net.operating.constraints))


def frame_load_pattern(net, rows, *, constraints=None):
    """Disjoint nodal supports and scaling for grouped global load derivatives.

    Use external nodal wrenches before internal forces, joints and struts enter
    nodal balance, exactly as the full operating equations do. Adding global
    rows to the coloring would make every structural column conflict.
    """
    nodes=[np.unique((r[(r >= 6*net.ne) & (r < 6*net.ne+3*net.nn)]-6*net.ne)//3)
           for r in rows]
    components=np.array([('xyz'.index(c.quantity[-1])
                          +(3 if c.quantity.startswith('moment.') else 0))
                         for c in (net.operating.constraints if constraints is None else constraints)],dtype=int)
    scales=np.where(components < 3,net.F,net.F*net.L)
    return nodes,components,scales


class IterationFields:
    def __init__(self):
        self.phase = 'capture'
        self.values = {}
        self.bytes = 0
        self.fixed_values = {}
        self.fixed_bytes = 0
        self.fixed_limit = 16*1024**2
        self.capture_circulation = False
        self.capture_local_flow = False
        self.local_flow_residual = None
        self.circulation_aero = None
        self.circulation_mechanics = None

    def fixed_geometry(self, key, compute):
        """Read-only setup reuse for the base geometry's circulation columns.

        Geometry columns recompute these values. Only the circulation phase,
        whose geometry equals the captured base state, may reuse them.
        """
        if self.phase == 'circulation' and key in self.fixed_values:
            return self.fixed_values[key]
        value = compute()
        if self.phase == 'capture' and key not in self.fixed_values:
            def size(v):
                if isinstance(v,np.ndarray):return v.nbytes
                if isinstance(v,dict):return sum(size(a) for a in v.values())
                if isinstance(v,(tuple,list)):return sum(size(a) for a in v)
                if hasattr(v,'__dict__'):return size(vars(v))
                return 0
            storage=size(value)
            if self.fixed_bytes+storage <= self.fixed_limit:
                self.fixed_values[key]=value
                self.fixed_bytes+=storage
        return value

    def get(self, key, compute):
        if key[1] is None:
            raise StructuredTangentUnavailable('Unidentified aerodynamic query in structured tangent.')
        if self.phase == 'circulation' and key[0] == 'jet':
            return compute()
        if self.phase == 'capture':
            result = compute()
            if key not in self.values:
                self.bytes += result.nbytes
                if self.bytes > 64*1024**2:
                    raise StructuredTangentUnavailable('Structured tangent field storage exceeds its budget.')
                self.values[key] = result.copy()
            else:
                if hasattr(result, 'assert_equal'):
                    result.assert_equal(self.values[key])
                else:
                    np.testing.assert_array_equal(result, self.values[key])
            return result
        return self.values[key].copy()


@contextmanager
def linearization(network, x, factor, *, capture_circulation=False, capture_mechanics=False,
                  capture_local_flow=False):
    fields = IterationFields()
    fields.capture_circulation = capture_circulation
    fields.capture_local_flow = capture_local_flow
    fields.capture_frame_loads = bool(network.operating.count)
    old_fields, old_pairs = network.iteration_fields, network.tangent_influences
    network.iteration_fields, network.tangent_influences = fields, TangentInfluences()
    network.aero_key = None
    try:
        if capture_mechanics:
            fields.mechanical_data={}
            base=network.residual(x,factor,_mechanical_data=fields.mechanical_data)
        else:
            base=network.residual(x,factor)
        fields.phase = 'geometry'
        yield fields, base
    finally:
        network.iteration_fields, network.tangent_influences = old_fields, old_pairs
        network.aero_key = None


@contextmanager
def full_fields(network):
    """Use current physical fields while retaining exact influence-pair reuse.

    Frame columns must not use captured/lagged fields. The independently keyed
    pair cache remains valid when geometry, direction, PG or images change.
    Its storage and lifetime are still bounded by the enclosing linearization.
    """
    old_fields = network.iteration_fields
    network.iteration_fields = None
    network.aero_key = None
    try:
        yield
    finally:
        network.iteration_fields = old_fields
        network.aero_key = None


def structural_column_rows(net, *, local_flow=False):
    """Conservative local support after lagging nonlocal geometry influences."""
    rows = [set() for _ in range(net.gamma_start)]
    nrows = [set() for _ in range(net.nn)]
    erows = []
    def balance(nodes):
        return {int(offset+3*i+k) for i in nodes for offset in (6*net.ne, 6*net.ne+3*net.nn) for k in range(3)}
    for i in range(net.nn):
        nrows[i].update(balance([i]))
    for e, (a, b) in enumerate(net.ends):
        support = set(range(6*e, 6*e+6)) | balance([a, b])
        erows.append(support)
        nrows[a].update(support); nrows[b].update(support)
    for beam in net.circulation_basis.beams:
        elements = net.beam_elements[beam['beam']]
        start = net.gamma_start+beam['panel_start' if local_flow else 'coefficient_start']
        for local, e in enumerate(range(elements.start, elements.stop)):
            support = (set(range(start, start+beam['unknowns'])) if beam['representation'] == 'fourier' and not local_flow
                       else {start+local})
            for node in net.ends[e]: nrows[node].update(support)
    constraint_start = 6*(net.nn+net.ne)
    for c in net.constraints:
        nodes = [c['a']] if c['b'] is None else [c['a'], c['b']]
        support = set(range(constraint_start+c['sl'].start, constraint_start+c['sl'].stop)) | balance(nodes)
        for node in nodes: nrows[node].update(support)
        if c['type'] == 3:
            erows[c['element']].update(support)
            for node in net.ends[c['element']]: nrows[node].update(support)
        for column in range(constraint_start+c['sl'].start, constraint_start+c['sl'].stop):
            rows[column].update(balance(nodes))
    for node, support in enumerate(nrows):
        for column in range(6*node, 6*node+6): rows[column].update(support)
    for e, support in enumerate(erows):
        for column in range(6*net.nn+6*e, 6*net.nn+6*e+6): rows[column].update(support)
    return [np.array(sorted(support), dtype=int) for support in rows]


def coloring(rows):
    groups, occupied = [], []
    for column, support in enumerate(rows):
        support = set(support)
        for group, used in zip(groups, occupied):
            if used.isdisjoint(support):
                group.append(column); used.update(support); break
        else:
            groups.append([column]); occupied.append(support)
    return [np.array(group, dtype=int) for group in groups]


@dataclass
class StructuredMatrix:
    """Local mechanics and aerodynamic coupling, with no dense global matrix."""
    mechanical: csc_matrix
    force_circulation: np.ndarray
    flow_geometry: csc_matrix
    circulation: np.ndarray

    def toarray(self):
        """Explicit dense conversion for verification only."""
        return np.block([[self.mechanical.toarray(), self.force_circulation],
                         [self.flow_geometry.toarray(), self.circulation]])

    @property
    def storage_bytes(self):
        return sum(a.data.nbytes+a.indices.nbytes+a.indptr.nbytes
                   for a in (self.mechanical, self.flow_geometry)) + self.force_circulation.nbytes + self.circulation.nbytes


def jacobian(net, x, factor, *, grouped=True, progress=None, direct_circulation=True, direct_mechanics=True):
    from .wall_root import wall_root_derivatives
    from .source_discrete import SourceDiscreteNetwork
    # Source equations have a distinct endpoint-average compliance block.
    # Reuse their exact load/reaction derivative without enabling the
    # original policy's midpoint geometry or constitutive derivatives.
    direct_mechanics = direct_mechanics and (isinstance(net, SourceDiscreteNetwork)
                                            or getattr(net, 'analytic_mechanics', True))
    with wall_root_derivatives(net, x):
        return _jacobian(net, x, factor, grouped=grouped, progress=progress,
                         direct_circulation=direct_circulation, direct_mechanics=direct_mechanics)


def _jacobian(net, x, factor, *, grouped=True, progress=None, direct_circulation=True, direct_mechanics=True):
    if not acceleration_load_constraints(net):
        raise StructuredTangentUnavailable('Structured steady tangents require prescribed or load-constrained frame accelerations.')
    # Fourier projection couples every mode row to every strip. The physical
    # tangency residual remains local when induced fields are held fixed.
    # Color that local stencil first, then project each recovered column.
    local_flow = grouped and bool(net.circulation_basis.modes)
    pattern_key = '_structured_local_flow_pattern' if local_flow else '_structured_pattern'
    if not hasattr(net, pattern_key):
        rows = structural_column_rows(net, local_flow=local_flow)
        setattr(net, pattern_key, (rows, coloring(rows)))
    rows, groups = getattr(net, pattern_key)
    load_nodes,load_components,load_scales = frame_load_pattern(net,rows)
    split = net.gamma_start
    triplet_rows, triplet_columns, triplet_values = [], [], []
    force_circulation = np.empty((split, net.size-split))
    circulation = np.empty((net.size-split, net.size-split))
    before = net.nfev
    total = (len(groups) if grouped else split) + net.size-split
    done = 0
    derivative_method = 'forward differences'
    derivative_fallback = None
    mechanical_report=None;mechanical_fallback=None
    with linearization(net, x, factor, capture_circulation=direct_circulation and net.ng > 0,
                       capture_mechanics=direct_mechanics, capture_local_flow=local_flow) as (fields, base):
        base_flow = fields.local_flow_residual.copy() if local_flow else None
        mechanical=None
        active_groups=groups if grouped else [np.array([i]) for i in range(net.gamma_start)]
        if direct_mechanics:
            from .mechanical_tangent import (network_mechanical_columns,
                source_network_mechanical_columns,MechanicalDerivativeUnavailable)
            from .source_discrete import SourceDiscreteNetwork
            build_mechanical = (source_network_mechanical_columns if isinstance(net, SourceDiscreteNetwork)
                                else network_mechanical_columns)
            try:
                mechanical,mechanical_report=build_mechanical(net,fields.mechanical_data,
                    np.maximum(1.,abs(x)),1e-6,factor=factor)
            except MechanicalDerivativeUnavailable as exc:
                mechanical_fallback=str(exc)
            else:
                # Recolor the remaining physical geometry columns. Merely
                # deleting load columns from the old colors misses many
                # disjoint groups that can now share a residual evaluation.
                geometry_key = '_structured_local_flow_geometry_groups' if local_flow else '_structured_geometry_groups'
                if grouped and not hasattr(net,geometry_key):
                    setattr(net,geometry_key,coloring(rows[:6*net.nn]))
                active_groups=getattr(net,geometry_key) if grouped else [np.array([i]) for i in range(6*net.nn)]
                block=mechanical.tocoo()
                triplet_rows.append(block.row);triplet_columns.append(block.col+6*net.nn)
                triplet_values.append(block.data)
        total=len(active_groups)+net.size-split

        direct = None
        if direct_circulation and net.ng:
            from .circulation_tangent import circulation_columns, CirculationDerivativeUnavailable
            try:
                direct = circulation_columns(net, fields, factor)
                derivative_method = 'direct fixed-geometry blocks'
                total = len(active_groups)+1+net.operating.count
            except CirculationDerivativeUnavailable as exc:
                derivative_fallback = str(exc)
        if progress is not None: progress('static_tangent', done, total)
        base_loads=fields.frame_loads.copy() if fields.capture_frame_loads else None
        for columns in active_groups:
            h = 1e-6*np.maximum(1., np.abs(x[columns]))
            trial = x.copy(); trial[columns] += h
            difference = net.residual(trial, factor)-base
            load_difference=None if base_loads is None else fields.frame_loads-base_loads
            for column, step in zip(columns, h):
                if grouped:
                    support = rows[column]
                    if local_flow:
                        strips = support[support >= split]-split
                        support = support[support < split]
                        values = difference[support]/step
                        if strips.size:
                            # Restore untouched strips before applying the same
                            # matrix-vector projection as the physical residual.
                            # Projecting differences instead would change the
                            # forward stencil's cancellation and roundoff.
                            trial_flow = base_flow.copy()
                            trial_flow[strips] = fields.local_flow_residual[strips]
                            projected = net.circulation_basis.test@trial_flow
                            support = np.r_[support,np.arange(split,net.operating_start)]
                            values = np.r_[values,(projected-base[split:net.operating_start])/step]
                    else:
                        values = difference[support]/step
                else:
                    support = np.arange(net.size)
                    values = difference/step
                if grouped and load_difference is not None:
                    wrench=load_difference[load_nodes[column]].sum(axis=0)
                    support=np.r_[support,np.arange(net.operating_start,net.size)]
                    values=np.r_[values,wrench[load_components]/load_scales/step]
                nonzero = values != 0
                triplet_rows.append(support[nonzero])
                triplet_columns.append(np.full(np.count_nonzero(nonzero), column, dtype=int))
                triplet_values.append(values[nonzero])
            done += 1
            if progress is not None: progress('static_tangent', done, total)
        fields.phase = 'circulation'
        if direct is not None:
            force_circulation[:,:net.ng], circulation[:,:net.ng] = direct[:split], direct[split:]
            done += 1
            if progress is not None: progress('static_tangent', done, total)
        else:
            for column in range(net.gamma_start, net.operating_start):
                h = 1e-6*max(1., abs(x[column]))
                trial = x.copy(); trial[column] += h
                values = (net.residual(trial, factor)-base)/h
                force_circulation[:, column-split] = values[:split]
                circulation[:, column-split] = values[split:]
                done += 1
                if progress is not None: progress('static_tangent', done, total)
        # Frame accelerations affect every inertial load. Keep the exact pair
        # cache, but remove all geometry-lagged fields for their full columns.
        if net.operating.count:
            with full_fields(net):
                base=net.residual(x,factor)
                for column in range(net.operating_start,net.size):
                    h=1e-6*max(1.,abs(x[column]));trial=x.copy();trial[column]+=h
                    values=(net.residual(trial,factor)-base)/h
                    force_circulation[:,column-split]=values[:split]
                    circulation[:,column-split]=values[split:]
                    done+=1
                    if progress is not None:progress('static_tangent',done,total)
    local = coo_matrix((np.concatenate(triplet_values),
                        (np.concatenate(triplet_rows), np.concatenate(triplet_columns))),
                       shape=(net.size, split)).tocsc()
    matrix = StructuredMatrix(local[:split], force_circulation, local[split:], circulation)
    return matrix, dict(evaluations=net.nfev-before, groups=len(active_groups), columns=net.size,
                        local_flow_before_projection=local_flow,
                        mechanical_derivative=mechanical_report,mechanical_derivative_fallback=mechanical_fallback,
                        matrix_storage_bytes=matrix.storage_bytes,
                        circulation_derivative=derivative_method,
                        circulation_derivative_fallback=derivative_fallback)


@dataclass
class BlockFactorization:
    """Reusable sparse mechanics and global Schur factors for a fixed matrix."""
    matrix: StructuredMatrix

    def __post_init__(self):
        a,b,c,d=(self.matrix.mechanical,self.matrix.force_circulation,
                 self.matrix.flow_geometry,self.matrix.circulation)
        if not all(np.all(np.isfinite(v)) for v in (a.data,b,c.data,d)):
            raise ValueError('Nonfinite structured equilibrium matrix.')
        self.local=splu(a)
        self.coupling=self.local.solve(b) if b.shape[1] else b.copy()
        self.border=None
        if d.size:
            with warnings.catch_warnings():
                warnings.simplefilter('error',LinAlgWarning)
                self.border=lu_factor(d-c@self.coupling)

    def solve(self,rhs):
        a,b,c,d=(self.matrix.mechanical,self.matrix.force_circulation,
                 self.matrix.flow_geometry,self.matrix.circulation)
        split=a.shape[0]
        local=self.local.solve(rhs[:split])
        border=np.empty(0) if self.border is None else lu_solve(self.border,rhs[split:]-c@local)
        solution=np.r_[local-self.coupling@border,border]
        product=np.r_[a@solution[:split]+b@border,c@solution[:split]+d@border]
        if not np.all(np.isfinite(solution)) or np.max(abs(product-rhs))>1e-8*max(1.,np.max(abs(rhs))):
            raise ValueError('Structured equilibrium linear solve failed its residual check.')
        return solution


def block_solve(jac, rhs, split=None, *, factorization=None):
    """Solve with fresh factors, or an explicitly supplied fixed-matrix factor."""
    if factorization is None:factorization=BlockFactorization(jac)
    if factorization.matrix is not jac:
        raise ValueError('Equilibrium factors belong to a different matrix.')
    return factorization.solve(rhs)



class DenseNewtonFactor:
    """One private full-matrix LU for one Newton direction and its line search.

    No factor survives a new Jacobian, Newton iteration or continuation stage.
    GECON retains the general dense solve's conditioning warning, including
    warning-as-error behavior. This is not a rank certificate or a new gate.
    """
    def __init__(self, matrix):
        dense=matrix.toarray(order='F') if issparse(matrix) else np.array(matrix,copy=True,order='F')
        if (dense.ndim!=2 or dense.shape[0]!=dense.shape[1] or not dense.size
                or np.iscomplexobj(dense) or not np.all(np.isfinite(dense))):
            raise ValueError('Dense Newton factors require a finite real square matrix.')
        getrf,self.getrs,gecon,lange,lamch=get_lapack_funcs(
            ('getrf','getrs','gecon','lange','lamch'),(dense,))
        anorm=lange('1',dense)
        self.lu,self.pivots,info=getrf(dense,overwrite_a=True)
        self.check_info(info)
        self.rcond,info=gecon(self.lu,anorm,norm='1')
        self.check_info(info)
        # SciPy 1.17 changed solve's warning threshold from LAPACK E (unit
        # roundoff) to dtype epsilon. Preserve the running library's warning
        # policy; neither threshold participates in nonlinear acceptance.
        version=tuple(int(v) for v in scipy_version.split('.')[:2])
        threshold=np.finfo(self.lu.dtype).eps if version>=(1,17) else lamch('E')
        self.ill_conditioned=not np.isfinite(self.rcond) or self.rcond<threshold
        self.report=dict(method='dense LU with reciprocal condition estimate',
            size=len(self.lu),factorizations=1,solves=0,
            reciprocal_condition=float(self.rcond) if np.isfinite(self.rcond) else None,
            warning_threshold=float(threshold),ill_conditioned=bool(self.ill_conditioned))

    @staticmethod
    def check_info(info):
        if info<0:raise ValueError(f'LAPACK reported an illegal value in {-info}-th argument.')
        if info>0:raise np.linalg.LinAlgError('Matrix is singular.')

    def solve(self, rhs):
        rhs=np.asarray(rhs)
        if rhs.shape!=(len(self.lu),) or np.iscomplexobj(rhs) or not np.all(np.isfinite(rhs)):
            raise ValueError('Dense Newton solve requires a finite real residual vector.')
        solution,info=self.getrs(self.lu,self.pivots,rhs,overwrite_b=False)
        self.check_info(info)
        self.report['solves']+=1
        if self.ill_conditioned:
            warnings.warn(f'Ill-conditioned matrix (rcond={self.rcond:.6g}): result may not be accurate.',
                          LinAlgWarning,stacklevel=2)
        return solution


def mechanical_rank_certificate(matrix, threshold=1e-10):
    """Conservative inverse-norm bound, using bounded sparse solve batches.

    For computed inverse Y, ||A^-1|| <= ||Y|| / (1-||I-AY||).
    Frobenius norms bound the spectral norms in this inequality. Failure to
    certify is inconclusive and triggers the established full SVD check.
    """
    norms = np.sqrt(np.asarray(matrix.power(2).sum(axis=0)).ravel())
    if not np.all(np.isfinite(norms)) or np.any(norms == 0):
        return False
    # A deficient sparsity pattern cannot have full numerical rank. Avoid
    # passing known singular mechanisms/redundant reactions to sparse LU.
    if structural_rank(matrix) < matrix.shape[0]:
        return False
    scaled = (matrix @ diags(1/norms)).tocsc()
    try:
        factor = splu(scaled)
    except RuntimeError:
        return False
    size = matrix.shape[0]
    inverse_squared = error_squared = 0.
    for start in range(0, size, 64):
        indices = np.arange(start, min(start+64, size))
        rhs = np.zeros((size, len(indices)))
        rhs[indices, np.arange(len(indices))] = 1.
        inverse = factor.solve(rhs)
        error = scaled@inverse-rhs
        inverse_squared += float(np.sum(inverse*inverse))
        error_squared += float(np.sum(error*error))
    error_norm = np.sqrt(error_squared)
    upper_condition = np.linalg.norm(scaled.data)*np.sqrt(inverse_squared)/max(1-error_norm, np.finfo(float).tiny)
    return bool(error_norm < 1 and np.isfinite(upper_condition) and upper_condition < 1/threshold)


def equilibrate_rank_matrix(matrix, iterations=30):
    """Invertible row/column norm scaling for a numerical rank decision.

    Keep the physical matrix unchanged. Alternating square-root norm updates
    avoid overflow from one aggressive rescaling; zero or nonfinite rows and
    columns remain evidence that a rank certificate is unavailable.
    """
    sparse = issparse(matrix)
    scaled = matrix.astype(float).tocsc(copy=True) if sparse else np.array(matrix,dtype=float,copy=True)
    row = np.ones(scaled.shape[0]); column = np.ones(scaled.shape[1])
    for _ in range(iterations):
        rn = np.sqrt(np.asarray(scaled.power(2).sum(axis=1)).ravel()) if sparse else np.linalg.norm(scaled,axis=1)
        if np.any(rn == 0) or not np.all(np.isfinite(rn)):
            return None, dict(valid=False,reason='zero or nonfinite row norm')
        r = 1/np.sqrt(rn); row *= r
        scaled = diags(r)@scaled if sparse else r[:,None]*scaled
        cn = np.sqrt(np.asarray(scaled.power(2).sum(axis=0)).ravel()) if sparse else np.linalg.norm(scaled,axis=0)
        if np.any(cn == 0) or not np.all(np.isfinite(cn)):
            return None, dict(valid=False,reason='zero or nonfinite column norm')
        c = 1/np.sqrt(cn); column *= c
        scaled = scaled@diags(c) if sparse else scaled*c[None,:]
    if not np.all(np.isfinite(row)) or not np.all(np.isfinite(column)):
        return None, dict(valid=False,reason='nonfinite accumulated rank scale')
    return (scaled.tocsc() if sparse else scaled), dict(valid=True,method='alternating square-root row/column 2-norm scaling',
        iterations=iterations,row_scale=row.tolist(),column_scale=column.tolist(),threshold=1e-10)


def mechanical_svd_certificate(matrix, threshold=1e-10, max_size=2048):
    """Resolve an inconclusive inverse-norm bound without rebuilding physics.

    Input is the existing, invertibly equilibrated mechanical block. Its
    smallest/largest singular-value ratio uses the same gate as the full
    fallback. The Frobenius bound can be pessimistic by a dimension factor;
    a failed bound is not evidence of a mechanism. Cap the dense input at
    32 MiB (float64); larger or inconclusive cases retain the full fallback.
    """
    report = dict(certified=False, threshold=threshold, size=matrix.shape[0])
    if matrix.shape[0] != matrix.shape[1] or not 0 < matrix.shape[0] <= max_size:
        return dict(report, reason='mechanical block exceeds bounded SVD scope')
    if not np.all(np.isfinite(matrix.data)):
        return dict(report, reason='nonfinite mechanical block')
    try:
        singular = np.linalg.svd(matrix.toarray(), compute_uv=False)
    except np.linalg.LinAlgError:
        return dict(report, reason='mechanical SVD did not converge')
    ratio = float(singular[-1]/singular[0]) if singular[0] > 0 else 0.
    return dict(report, certified=bool(np.all(np.isfinite(singular)) and ratio >= threshold),
                singular_ratio=ratio, reason='equilibrated mechanical singular values')


def refine_mechanical_rank_certificate(matrix, scaling, *, max_dense_bytes=64*1024**2):
    """Bounded further equilibration of an inconclusive mechanical block.

    Only rank-test coordinates change. The physical Newton matrix is untouched.
    Limit work to 300 total scaling updates and one SVD with at most 64 MiB
    dense input (LAPACK workspace is additional). A norm stopping criterion
    avoids needless updates; only the unchanged 1e-10 singular ratio certifies
    rank, even if norm equilibration reaches its iteration cap first.
    """
    size = matrix.shape[0]
    declined = dict(certified=False,threshold=1e-10,size=size,
                    dense_input_bytes=8*size*size,dense_input_limit_bytes=max_dense_bytes)
    if (matrix.shape != (size,size) or size <= 0 or 8*size*size > max_dense_bytes):
        return dict(declined,reason='mechanical block exceeds refined SVD byte budget'), scaling
    if not scaling.get('valid', False):
        return dict(declined,reason='invalid initial rank scaling'), scaling
    row = np.asarray(scaling['row_scale'],dtype=float).copy()
    column = np.asarray(scaling['column_scale'],dtype=float).copy()
    updates = scaling['iterations']
    def valid_scales():
        return (row.shape == (size,) and column.shape == (size,)
                and np.all(np.isfinite(row)) and np.all(np.isfinite(column))
                and np.all(row > 0) and np.all(column > 0))
    if not valid_scales():
        return dict(declined,reason='noninvertible initial rank scaling'), scaling
    def norm_error(value):
        rn = np.sqrt(np.asarray(value.power(2).sum(axis=1)).ravel())
        cn = np.sqrt(np.asarray(value.power(2).sum(axis=0)).ravel())
        if (not np.all(np.isfinite(rn)) or not np.all(np.isfinite(cn))
                or np.any(rn <= 0) or np.any(cn <= 0)):
            return np.inf
        return float(max(np.max(abs(np.log(rn))),np.max(abs(np.log(cn)))))
    error = norm_error(matrix); trace = [dict(iterations=updates,max_log_norm_error=error)]
    if not np.isfinite(error):
        return dict(declined,reason='nonfinite or zero refined norm'), scaling
    refined = matrix
    while updates < 300 and error > 1e-3:
        batch = min(10,300-updates)
        refined, step = equilibrate_rank_matrix(refined,iterations=batch)
        if refined is None:
            return dict(declined,reason='refined norm scaling unavailable'), scaling
        with np.errstate(over='ignore',under='ignore',invalid='ignore'):
            row *= step['row_scale']; column *= step['column_scale']
        if not valid_scales():
            return dict(declined,reason='noninvertible accumulated rank scaling'), scaling
        updates += batch; error = norm_error(refined)
        if not np.isfinite(error):
            return dict(declined,reason='nonfinite or zero refined norm'), scaling
        trace.append(dict(iterations=updates,max_log_norm_error=error))
    report = dict(scaling,iterations=updates,row_scale=row.tolist(),column_scale=column.tolist(),
        refinement=dict(initial_iterations=scaling['iterations'],maximum_iterations=300,
            norm_log_tolerance=1e-3,max_log_norm_error=error,norm_converged=error<=1e-3,trace=trace))
    svd = mechanical_svd_certificate(refined,max_size=size)
    return dict(svd,dense_input_bytes=8*size*size,dense_input_limit_bytes=max_dense_bytes), report


def check_initial_rank(net, x, progress=None, *, retain_matrix=False):
    """At zero load the exact Jacobian is block triangular.

    Geometry lagging changes only its lower-left block: mechanics and the
    circulation diagonal are unchanged, and aerodynamic force coupling is
    exactly zero. Their nonsingularity therefore certifies full rank. An
    inconclusive original certificate gets an invertible two-sided scaling
    check before the full-Jacobian SVD. Its rank gate stays at 1e-10.
    """
    from .aero import AnalysisError
    matrix, counts = jacobian(net, x, 0., progress=progress)
    def result(report):
        return (report, matrix) if retain_matrix else report
    d = matrix.circulation
    if d.size:
        norms = np.linalg.norm(d, axis=0)
        singular = np.linalg.svd(d/np.maximum(norms,1e-30), compute_uv=False)
        circulation_ok = bool(singular[0] > 0 and singular[-1] >= 1e-10*singular[0])
    else:
        circulation_ok = True
    from .rigid_initial_rank import rigid_tree_initial_certificate
    physical = rigid_tree_initial_certificate(net,x,0.)
    if not np.any(matrix.force_circulation) and circulation_ok and physical['certified']:
        method = ('source rigid-tree rank certificate' if 'source_scope' in physical
                  else 'analytic rigid-tree rank certificate')
        return result(dict(method=method,physical_certificate=physical,**counts))
    from .source_initial_rank import source_tree_initial_certificate
    source_tree = source_tree_initial_certificate(net,x,0.)
    if not np.any(matrix.force_circulation) and circulation_ok and source_tree['certified']:
        # Conservative tree balance removes all resultants/reactions before
        # finite source compliance enters compatibility. This is an exact
        # nullspace argument, not a numerical conditioning estimate. Keep the
        # separately evaluated circulation SVD and the actual Newton matrix.
        return result(dict(method='source flexible-tree rank certificate',
            physical_certificate=source_tree,
            circulation_rank=dict(certified=True,threshold=1e-10,unknowns=int(d.shape[0]),
                singular_ratio=float(singular[-1]/singular[0]) if d.size else None),**counts))
    if (not np.any(matrix.force_circulation) and circulation_ok
            and mechanical_rank_certificate(matrix.mechanical)):
        return result(dict(method='block-triangular rank certificate', physical_certificate=physical, **counts))
    balanced_mechanics, mechanical_scaling = equilibrate_rank_matrix(matrix.mechanical)
    if (not np.any(matrix.force_circulation) and circulation_ok
            and balanced_mechanics is not None and mechanical_rank_certificate(balanced_mechanics)):
        return result(dict(method='block-triangular rank certificate',rank_scaling=mechanical_scaling,
                           physical_certificate=physical,**counts))
    if not np.any(matrix.force_circulation) and circulation_ok and balanced_mechanics is not None:
        svd = mechanical_svd_certificate(balanced_mechanics)
        if svd['certified']:
            return result(dict(method='block-triangular SVD certificate', rank_scaling=mechanical_scaling,
                               mechanical_svd=svd, physical_certificate=physical, **counts))
        refined_svd, refined_scaling = refine_mechanical_rank_certificate(balanced_mechanics,mechanical_scaling)
        if refined_svd['certified']:
            return result(dict(method='block-triangular SVD certificate',rank_scaling=refined_scaling,
                mechanical_svd=refined_svd,initial_mechanical_svd=svd,
                physical_certificate=physical,**counts))
    full = net.jacobian(x, 0., progress=progress)
    norms = np.linalg.norm(full, axis=0)
    original = np.linalg.svd(full/np.maximum(norms,1e-30), compute_uv=False)
    balanced, scaling = equilibrate_rank_matrix(full)
    singular = None if balanced is None else np.linalg.svd(balanced,compute_uv=False)
    if singular is None or singular[0] <= 0 or singular[-1] < 1e-10*singular[0]:
        raise AnalysisError('Constraints leave a mechanism or redundant reactions/operating targets; check Ground, Joint and operating definitions.')
    return result(dict(method='full-Jacobian SVD fallback',rank_scaling=scaling,physical_certificate=physical,
                original_column_singular_ratio=float(original[-1]/original[0]) if original[0] else 0.,
                equilibrated_singular_ratio=float(singular[-1]/singular[0]),**counts))


def rotation_increment(net, state, delta):
    """Physical nodal and relative-hinge infinitesimal rotation magnitude."""
    from .local_motion import left_jacobian
    nodal = state[:6*net.nn].reshape(net.nn, 6)
    direction = delta[:6*net.nn].reshape(net.nn, 6)
    spatial = np.einsum('nij,nj->ni', left_jacobian(nodal[:, 3:]), direction[:, 3:])
    values = list(np.linalg.norm(spatial, axis=1))
    values += [np.linalg.norm(spatial[joint['b']]-spatial[joint['a']])
               for joint in net.constraints if joint['type'] == 3]
    return float(max(values, default=0.))


def load_fraction_derivative(net, data):
    """Exact explicit load derivative of the prescribed static equations.

    ``data`` must belong to a fresh physical residual at the same state and
    factor. External wrenches and endpoint couples are unscaled in that data.
    Strut rest-length continuation and operating targets need separate laws.
    """
    if net.operating.count or net.struts:
        raise StructuredTangentUnavailable('Load prediction requires prescribed conditions without struts.')
    derivative = np.zeros(net.size)
    start = 6*net.ne
    derivative[start:start+3*net.nn] = (data['force']/net.F).ravel()
    start += 3*net.nn
    derivative[start:start+3*net.nn] = (data['moment']/(net.F*net.L)).ravel()
    hinge_data = {h['joint']: h for h in data['hinges']}
    for c in net.constraints:
        if c['type'] != 3:
            continue
        law = c['law']; moment = hinge_data[law.index]['structural_moment']
        knots = law.curve[:-1, 0][np.diff(law.curve[:, 0]) == 0]
        if np.any(abs(knots-moment) <= 1e-8*max(1., abs(moment))):
            raise StructuredTangentUnavailable('Load prediction is unavailable at a Jangle slope break.')
        # At a slope break there is no unique two-sided load derivative.
        # A predictor is optional: retain the existing continuation there.
        left = float(law.spline.evaluate(moment, derivative=1, side='left'))
        right = float(law.spline.evaluate(moment, derivative=1, side='right'))
        if left != right:
            raise StructuredTangentUnavailable('Load prediction is unavailable at a Jangle slope break.')
        axis = data['Q'][c['a']]@law.axis
        sign = -1 if c['end'] else 1
        moment_rate = sign*float(data['element_moments'][c['element'], int(c['end'])]@axis)
        start = 6*(net.nn+net.ne)+c['sl'].start+3
        derivative[start:start+3] = -law.axis*(np.deg2rad(right)*moment_rate+law.zero_angle)
    if not np.all(np.isfinite(derivative)):
        raise StructuredTangentUnavailable('Nonfinite explicit load derivative.')
    return derivative


def initial_load_step(net, x, matrix, increment, target_error, rotation_limit):
    """Propose a smaller first target; never accept or change a physical state.

    Reuse only the zero-load rank matrix. At zero load its upper-right block
    vanishes, so lagging flow geometry cannot change the mechanical predictor.
    Every proposed target still receives its own fresh Newton matrix and all
    existing continuation, line-search, rank and final residual checks.
    """
    from .network import StaticNetwork
    from .source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
    from .source_coupled import SourceCoupledNetwork
    from .source_dynamics import SourceMovingNetwork
    from .source_airflow import SourceAirflowNetwork
    from .aero import AnalysisError
    report = dict(method='zero-load rotation predictor', applied=False,
                  original_increment=float(increment), proposed_increment=float(increment))
    known = (StaticNetwork, SourceDiscreteNetwork, SourceSectionNetwork, SourceCoupledNetwork,
             SourceMovingNetwork, SourceAirflowNetwork)
    if (type(net) not in known or not net.hinges or net.operating.count or net.struts
            or net.iteration_fields is not None or net.tangent_influences is not None):
        report['reason'] = 'unsupported state or field context'
        return increment, report
    if np.any(matrix.force_circulation):
        report['reason'] = 'nonzero force/circulation coupling at zero load'
        return increment, report
    before = net.nfev
    try:
        residual, data = net.residual(x, 0., detail=True)
        error = float(np.max(abs(residual)))
        report['zero_load_residual'] = error if np.isfinite(error) else None
        if not np.all(np.isfinite(residual)) or error > target_error:
            report['reason'] = 'zero-load state is not converged'
            return increment, report
        derivative = load_fraction_derivative(net, data)
        direction = block_solve(matrix, -derivative, net.gamma_start)
        if not np.all(np.isfinite(direction)):
            raise ValueError('Nonfinite zero-load prediction.')
        rate = rotation_increment(net, x, direction)
        if not np.isfinite(rate):
            raise ValueError('Nonfinite predicted rotation rate.')
        report['rotation_rate_rad'] = rate
        candidate = min(increment, .9*rotation_limit/rate) if rate > 0 else increment
        if not np.isfinite(candidate) or candidate < 128*np.finfo(float).eps:
            report['reason'] = 'predicted increment is below load resolution'
            return increment, report
        report.update(applied=bool(candidate < increment), proposed_increment=float(candidate),
                      reason='smaller first target' if candidate < increment else 'original target retained')
        return candidate, report
    except (StructuredTangentUnavailable, AnalysisError, RuntimeError, ValueError,
            LinAlgWarning, np.linalg.LinAlgError) as exc:
        report['reason'] = type(exc).__name__+': '+str(exc)
        return increment, report
    finally:
        # A detailed physical load query must not be mistaken for a later
        # compact Newton query. No matrix or field context survives prediction.
        net.aero_key = None
        report['evaluations'] = net.nfev-before


def _polish_fixed_geometry_circulation(net, x, factor, residual, target_error):
    """Try a circulation-only finish, accepted by every original equation.

    Near convergence, sub-ulp nodal corrections can change induced-velocity
    rounding more than the remaining flow defect. Holding the mechanical and
    operating state fixed avoids that geometry jitter. This is only a candidate:
    the changed aerodynamic loads must still satisfy the full physical target.
    Failure leaves the existing coupled Newton path available at the same state.
    """
    if (net.iteration_fields is not None or not net.ng or not np.all(np.isfinite(residual))
            or np.max(abs(residual[:net.gamma_start]), initial=0.) > target_error
            or np.max(abs(residual[net.operating_start:]), initial=0.) > target_error):
        return None
    from .circulation_tangent import circulation_residual_columns, CirculationDerivativeUnavailable
    from .aero import AnalysisError
    before = net.nfev
    try:
        with linearization(net, x, factor, capture_circulation=True) as (fields, base):
            if (not np.all(np.isfinite(base))
                    or np.max(abs(base[:net.gamma_start]), initial=0.) > target_error
                    or np.max(abs(base[net.operating_start:]), initial=0.) > target_error):
                return None
            block = circulation_residual_columns(net, fields)
            delta = np.linalg.solve(block, -base[net.gamma_start:net.operating_start])
        if not np.all(np.isfinite(delta)):
            return None
        trial = x.copy()
        trial[net.gamma_start:net.operating_start] += delta
        value = net.residual(trial, factor)
    except (CirculationDerivativeUnavailable, StructuredTangentUnavailable,
            np.linalg.LinAlgError, AnalysisError):
        return None
    finally:
        net.aero_key = None
    if (not np.all(np.isfinite(trial)) or not np.all(np.isfinite(value))
            or np.max(abs(value)) > target_error or value@value >= base@base):
        return None
    return trial, value, dict(method='fixed-geometry circulation finish',
        evaluations=net.nfev-before, correction_max=float(np.max(abs(delta))),
        residual_before=float(np.max(abs(base))), residual_after=float(np.max(abs(value))))


def equilibrate(net, tolerance=1e-8, continuation_steps=4, *, initial_state=None, progress=None,
                reuse_matrices=True, full_structure=True, checkpoint=None, max_load_steps=None, **options):
    """Prescribed or load-constrained acceleration solve with full acceptance.

    Unsupported operating/state contexts use the full-Jacobian solver. A failed
    approximate Newton direction gets a full Jacobian before load refinement.
    """
    from .network import _equilibrate_full as original_equilibrate
    from .aero import evaluate_aerodynamics, AnalysisError
    from .ground import GroundIntersectionError
    bounded = checkpoint is not None or max_load_steps is not None
    if options or initial_state is not None or not acceleration_load_constraints(net):
        if bounded:
            raise AnalysisError('Continuation jobs require the structured steady route without warm states or residual overrides.')
        return original_equilibrate(net,tolerance,continuation_steps,initial_state=initial_state,progress=progress,**options)
    if not np.isfinite(tolerance) or not 0 < tolerance <= 1e-5:
        raise AnalysisError('Equilibrium tolerance must be positive and no greater than 1e-5.')
    if not isinstance(continuation_steps,int) or continuation_steps < 1:
        raise AnalysisError('At least one continuation step is required.')
    if max_load_steps is not None and (type(max_load_steps) is not int or max_load_steps < 1):
        raise AnalysisError('max_load_steps must be a positive integer.')
    saved = ctx = None
    if bounded:
        from .steady_continuation import context, restore, capture, ContinuationPending
        ctx = context(net,tolerance,continuation_steps,reuse_matrices,full_structure)
        if checkpoint is not None:
            saved = restore(net,checkpoint,ctx)
    if progress is not None: progress('static_load',0.,1.)
    x = np.zeros(net.size)
    if net.condition is not None:
        initial = evaluate_aerodynamics(net.model,net.condition,net.meshes,frozen_influences=net.frozen_influences)
        physical = np.array([s['circulation'] for s in initial['strips'] if s['lifting']])
        x[net.gamma_start:net.operating_start] = net.circulation_basis.encode(physical)/net.gamma_scale
    initial_matrix = None
    # Recheck the original unloaded rank gate in each job. A saved packet is
    # never authority to skip rank verification or retain a Newton factor.
    from .hinge_history import current, joints
    original_charts = current(net)
    if saved is not None:
        for joint in joints(net): joint['angle_chart'] = 0.
    try:
        if net.hinges:
            net.structured_rank_check, initial_matrix = check_initial_rank(net,x,progress,retain_matrix=True)
        else:
            net.structured_rank_check = check_initial_rank(net,x,progress)
    finally:
        if saved is not None:
            for joint,center in zip(joints(net),original_charts): joint['angle_chart'] = center
    reached, increment, steps = 0., 1./continuation_steps, 0
    net.structured_iterations = []
    net.continuation_diagnostics = []
    rejected_attempts = 0
    rotation_limit = np.deg2rad(5.)

    def actual_rotation_increment(state, trial):
        from .network import exp,log
        before=exp(state[:6*net.nn].reshape(net.nn,6)[:,3:])
        after=exp(trial[:6*net.nn].reshape(net.nn,6)[:,3:])
        values=list(np.linalg.norm(log(before.transpose(0,2,1)@after),axis=1))
        for joint in net.constraints:
            if joint['type']!=3:continue
            i,j=joint['a'],joint['b']
            old=before[i].T@before[j];new=after[i].T@after[j]
            values.append(np.linalg.norm(log(old.T@new)))
        return float(max(values,default=0.))
    # Resolve load/stress recovery as well as the normalized equations. A
    # default residual threshold alone can leave small recovery differences.
    target_error = min(tolerance,1e-12)
    if initial_matrix is not None:
        if saved is None:
            increment, prediction = initial_load_step(net, x, initial_matrix, increment, target_error, rotation_limit)
            net.equilibrium_diagnostics = dict(initialization='undeformed load continuation', cold_start_prediction=prediction)
        del initial_matrix
    if saved is not None:
        x,reached,increment,steps,rejected_attempts,centers,initialization = saved
        for joint,center in zip(joints(net),centers): joint['angle_chart'] = center
        net.equilibrium_diagnostics = initialization
        net.aero_key = None
    starting_steps = steps
    while reached < 1-1e-12:
        target = min(1.,reached+increment)
        state = x.copy()
        chart_snapshot = [(joint,joint.get('angle_chart',0.)) for joint in net.constraints if joint['type']==3]
        load_record=dict(reached=reached,target=target,increment=target-reached,
            starting_charts=[center for joint,center in chart_snapshot],accepted=False)
        net.continuation_diagnostics.append(load_record)
        load_retry_increment=None
        if progress is not None: progress('static_load',target,1.)
        accepted = False
        # A continuation change always starts with a new matrix. Within this
        # load level, retain factors only while full physical merit contracts.
        matrix=factorization=None
        tangent_age=0
        for iteration in range(30):
            residual = net.residual(state,target)
            error = float(np.max(abs(residual)))
            if error <= target_error:
                accepted = True; break
            polished = _polish_fixed_geometry_circulation(net, state, target, residual, target_error)
            if polished is not None:
                state, residual, diagnostic = polished
                error = float(np.max(abs(residual)))
                load_record['circulation_polish'] = diagnostic
                accepted = True
                break
            merit = float(residual@residual)
            record = dict(load_fraction=target,iteration=iteration,residual=error,
                          evaluations=0,matrix_reused=False)
            net.structured_iterations.append(record)
            improved = False
            attempts=('reused','fresh','full') if factorization is not None else ('fresh','full')
            for method in attempts:
                dense_factor=None
                if method=='fresh':
                    matrix,counts=jacobian(net,state,target,progress=progress)
                    record.update(counts)
                    factorization=None;tangent_age=0
                elif method=='full':
                    # Include every moving-field term through the same
                    # complete decomposition used by harmonic startup. Unsafe
                    # geometries still fall back to the original full stencil.
                    matrix = net.jacobian(state,target,progress=progress,
                        _sparse=full_structure and net.size>256, _direct_geometry=True)
                    factorization=None;tangent_age=0
                    record['exact_fallback'] = True
                try:
                    if method=='full':
                        if full_structure and net.size>256:
                            from .newton_structure import StructureUnavailable
                            from .sparse_newton import memory_bounded_newton_factor
                            try:
                                factorization=memory_bounded_newton_factor(net,matrix)
                                delta=factorization.solve(-residual)
                            except (StructureUnavailable,RuntimeError,ValueError,np.linalg.LinAlgError) as exc:
                                factorization=None
                                record['full_structure_fallback']=str(exc)
                            else:record['full_structure']=factorization.report
                        if factorization is None:
                            dense_factor=DenseNewtonFactor(matrix)
                            record['full_dense']=dense_factor.report
                            delta=dense_factor.solve(-residual)
                    else:
                        if factorization is None:factorization=BlockFactorization(matrix)
                        delta=block_solve(matrix,-residual,net.gamma_start,factorization=factorization)
                    if not np.all(np.isfinite(delta)):raise ValueError('Nonfinite equilibrium correction.')
                except (RuntimeError,ValueError,LinAlgWarning,np.linalg.LinAlgError) as exc:
                    if method=='full' and factorization is None:
                        record['full_dense_failure']=type(exc).__name__+': '+str(exc)
                    factorization=None
                    if method=='reused':record['reuse_failed']=True
                    continue
                if net.hinges:
                    merit = float(delta@delta)
                    angular_correction=rotation_increment(net,state,delta)
                    record['predicted_rotation_increment_rad']=angular_correction
                    # The first correction estimates the geometry change from
                    # the previously converged load state. Refine the load
                    # increment before walking to a distant equilibrium branch.
                    if iteration==0 and angular_correction>rotation_limit:
                        load_retry_increment=(target-reached)*.9*rotation_limit/angular_correction
                        load_record.update(rejection='predicted_rotation_increment',
                            predicted_rotation_increment_rad=angular_correction,
                            proposed_increment=load_retry_increment)
                        break
                # Limit geometry and circulation changes. Internal resultants,
                # reactions and solved accelerations are load coordinates;
                # their normalization is not a physical step-size bound. A
                # large gravity override can otherwise turn a linear reaction
                # solve into hundreds of damped updates and load retries.
                # Every candidate still passes the full physical merit search;
                # nonlinear hinges also retain their rotation/load-step gates.
                change = max(float(np.max(abs(delta[:6*net.nn]), initial=0.)),
                             float(np.max(abs(delta[net.gamma_start:net.operating_start]), initial=0.)))
                alpha = 1./max(1., change)
                if net.hinges:
                    alpha=min(alpha,rotation_limit/max(rotation_limit,angular_correction))
                for _ in range(12):
                    trial = state+alpha*delta
                    if net.hinges:
                        actual_angle=actual_rotation_increment(state,trial)
                        if actual_angle>rotation_limit*(1+1e-12):
                            alpha/=2
                            continue
                    try:
                        value = net.residual(trial,target)
                        if net.hinges:
                            if factorization is not None:
                                correction = factorization.solve(-value) if method == 'full' else block_solve(matrix,-value,net.gamma_start,factorization=factorization)
                            else:
                                correction = dense_factor.solve(-value)
                            trial_merit = float(correction@correction)
                        else:
                            trial_merit = float(value@value)
                    except (AnalysisError, GroundIntersectionError):
                        trial_merit = np.inf
                    if np.isfinite(trial_merit) and trial_merit < merit*(1-1e-4*alpha):
                        state = trial; improved = True; record['alpha'] = alpha
                        chart_changed=False
                        if net.hinges:
                            record['accepted_rotation_increment_rad']=actual_angle
                            from .network import exp, log
                            nodal=state[:6*net.nn].reshape(net.nn,6)
                            rotations=exp(nodal[:,3:])
                            for joint in net.constraints:
                                if joint['type'] != 3: continue
                                law=joint['law'];center=joint.get('angle_chart',0.)
                                relative=rotations[joint['a']].T@rotations[joint['b']]
                                joint['angle_chart']=center+float(law.axis@log(exp(-center*law.axis)@relative))
                            # Recenter absolute nodal charts while preserving physical frames.
                            recentered=log(rotations)
                            # A principal-log branch crossing changes the
                            # coordinates of the matrix columns. Small updates
                            # on the same branch permit modified Newton reuse;
                            # a crossing always requires a fresh matrix.
                            chart_changed=bool(np.max(abs(recentered-nodal[:,3:]),initial=0.)>1e-10)
                            nodal[:,3:]=recentered
                            record['rotation_chart_changed']=chart_changed
                            record['hinge_charts']=[joint['angle_chart'] for joint in net.constraints if joint['type']==3]

                        tangent_age+=1
                        record.update(matrix_reused=method=='reused',matrix_age=tangent_age)
                        # Limit stale tangents, and refresh after damping or
                        # weak contraction. Acceptance still uses the original
                        # full equations and the unchanged final tolerance.
                        if (chart_changed or not reuse_matrices or alpha<1
                                or trial_merit>.49*merit or tangent_age>=6):
                            factorization=None
                        break
                    alpha /= 2
                if improved: break
                factorization=None
                if method=='reused':record['reuse_failed']=True
            if not improved: break
        if not accepted:
            error = float(np.max(abs(net.residual(state,target))))
            accepted = bool(error <= target_error and np.all(np.isfinite(state)))
        if accepted:
            completed_rotation=actual_rotation_increment(x,state) if net.hinges else 0.
            x = state; reached = target; steps += 1
            load_record.update(accepted=True,residual=error,
                final_charts=[joint.get('angle_chart',0.) for joint in net.constraints if joint['type']==3])
            if net.hinges:
                load_record['accepted_load_rotation_increment_rad']=completed_rotation
                increment=min(1.-reached,increment*.9*rotation_limit/max(completed_rotation,128*np.finfo(float).eps))
            else:
                increment = min(1./continuation_steps,increment*1.5)
            if (max_load_steps is not None and steps-starting_steps >= max_load_steps
                    and reached < 1-1e-12):
                raise ContinuationPending(capture(net,x,ctx,reached,increment,steps,rejected_attempts))
        else:
            load_record.update(residual=error,
                rejected_charts=[joint.get('angle_chart',0.) for joint in net.constraints if joint['type']==3])
            for joint,center in chart_snapshot:
                joint['angle_chart']=center
            load_record['restored_charts']=[joint.get('angle_chart',0.) for joint in net.constraints if joint['type']==3]
            increment = load_retry_increment if load_retry_increment is not None else increment/2
            # A finite soft hinge can require an initial load step far below
            # 1/256. Stop at floating-point resolution, not an unrelated load
            # scale, while retaining the existing Newton and line-search caps.
            minimum_increment=128*np.finfo(float).eps*max(1.,abs(reached)) if net.hinges else 1/256
            if increment < minimum_increment or reached+increment==reached:
                raise AnalysisError(f'Structured equilibrium did not converge; last residual {error:g}.')
            # Successful finite-angle progress does not consume a failure
            # budget; retain a finite budget for unsuccessful load attempts.
            rejected_attempts += 1
            load_record['rejected_attempts'] = rejected_attempts
            if rejected_attempts >= 128:
                raise AnalysisError('Continuation exhausted 128 rejected load attempts.')
    return x,steps
