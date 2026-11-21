"""Consistent initial disturbances of the frozen full descriptor equations.

For M zdot=A z, the one-sided Laplace transform satisfies
(s M-A) Z=M z0 and transform(zdot)=s Z-z0. Algebraic and hidden
constraints determine the missing loads/actuators; they are not discarded.
"""
import numpy as np
from copy import deepcopy
from scipy.linalg import lstsq, eigvals, svdvals
from .aero import AnalysisError
from .linear_dynamics import finite_subspace, complex_data, output_perturbation


def vector(value, shape, label):
    if np.iscomplexobj(value):raise AnalysisError(f'{label} must contain real physical values.')
    try:
        a = np.asarray(value, dtype=float)
    except (ValueError, TypeError) as exc:
        raise AnalysisError(f'{label} must contain finite real numbers.') from exc
    if a.shape != shape or not np.all(np.isfinite(a)):
        raise AnalysisError(f'{label} must have shape {shape} and finite real values.')
    return a


def dynamic_state(system, specification):
    """Map physical perturbations to the common local chart; omissions are zero."""
    if not isinstance(specification, dict) or set(specification)-{'nodes', 'beam_fields', 'circulation', 'frame', 'feedback'}:
        raise AnalysisError('Initial state supports nodes, beam_fields, circulation, frame and feedback.')
    n = system.network
    z = np.zeros(system.size)
    fields = {'displacement': (0, n.L), 'rotation': (3, 1.),
              'velocity': (system.velocity_start, system.V),
              'rates': (system.velocity_start+3*n.nn, system.W)}
    assigned = set()
    def put(node, name, value):
        if (node, name) in assigned:
            raise AnalysisError('An initial node field is specified more than once.')
        assigned.add((node, name))
        start, scale = fields[name]
        start += (6 if name in ('displacement', 'rotation') else 3)*node
        z[start:start+3] = vector(value, (3,), 'Initial '+name)/scale
    def beam_nodes(key):
        if isinstance(key, bool) or not isinstance(key, (int, np.integer)) or key not in n.station_nodes:
            raise AnalysisError('Initial disturbance references a missing logical beam.')
        return n.station_nodes[key]
    rows = specification.get('nodes', [])
    profiles = specification.get('beam_fields', [])
    if not isinstance(rows, list) or not isinstance(profiles, list):
        raise AnalysisError('Initial nodes and beam_fields must be lists.')
    for row in rows:
        if not isinstance(row, dict) or set(row)-{'beam', 't', *fields} or not {'beam', 't'} <= set(row):
            raise AnalysisError('Initial node rows require beam, t and physical displacement/rotation/velocity/rates.')
        ts, ids = beam_nodes(row['beam']);t = vector(row['t'], (), 'Initial station')
        i = int(np.argmin(abs(ts-t)))
        parameter_scale = max(np.max(abs(ts)), np.ptp(ts), np.finfo(float).tiny)
        if t < ts[0] or t > ts[-1] or abs(ts[i]-t) > 8*np.finfo(float).eps*parameter_scale:
            raise AnalysisError('Initial disturbance station is not a node of the current mesh.')
        for name in fields:
            if name in row:put(int(ids[i]), name, row[name])
    for row in profiles:
        if not isinstance(row, dict) or set(row)-{'beam', *fields} or 'beam' not in row:
            raise AnalysisError('Initial beam_fields require beam and physical field tables [t,x,y,z].')
        ts, ids = beam_nodes(row['beam'])
        for name in fields:
            if name not in row:continue
            if np.iscomplexobj(row[name]):raise AnalysisError('Initial beam field tables must contain real physical values.')
            try:table = np.asarray(row[name], dtype=float)
            except (ValueError, TypeError) as exc:raise AnalysisError('Initial beam field tables need finite [t,x,y,z] rows.') from exc
            if (table.ndim != 2 or table.shape[1] != 4 or len(table) < 2 or not np.all(np.isfinite(table))
                    or np.any(np.diff(table[:, 0]) <= 0) or table[0, 0] != ts[0] or table[-1, 0] != ts[-1]):
                raise AnalysisError('Initial beam field tables must increase in t and include both exact beam endpoints.')
            values = np.column_stack([np.interp(ts, table[:, 0], table[:, j]) for j in (1, 2, 3)])
            for node, value in zip(ids, values):put(int(node), name, value)
    if 'circulation' in specification:
        gamma = vector(specification['circulation'], (n.circulation_basis.panels,), 'Initial physical circulation')
        z[n.gamma_start:n.operating_start] = n.circulation_basis.encode(gamma)/n.gamma_scale
    frame = specification.get('frame', {})
    frame_fields = {'velocity_origin_body': system.V, 'rates_body': system.W,
                    'position_earth': system.L, 'attitude_rad': 1.}
    if not isinstance(frame, dict) or set(frame)-frame_fields.keys():
        raise AnalysisError('Initial frame fields are velocity_origin_body, rates_body, position_earth and attitude_rad.')
    if frame and system.frame == 'fixed':
        raise AnalysisError('Initial flight-frame disturbances require prescribed, free or mixed motion.')
    for i, (name, scale) in enumerate(frame_fields.items()):
        if name in frame:z[system.frame_start+3*i:system.frame_start+3*i+3] = vector(frame[name], (3,), 'Initial '+name)/scale
    feedback = specification.get('feedback', {})
    if not isinstance(feedback, dict) or set(feedback)-{'integrals', 'states'}:
        raise AnalysisError('Initial feedback supports physical integrals and custom states; actual actuators are determined by constraints.')
    f = system.feedback
    if feedback and f is None:raise AnalysisError('Initial controller state requires an active controller.')
    if f is not None:
        for group, names, offset in [('integrals', f.integrals, f.count),
                                     ('states', [s['name'] for s in f.states], f.state_start)]:
            values = feedback.get(group, {})
            if not isinstance(values, dict) or set(values)-set(names):
                raise AnalysisError('Initial controller state names must match the active controller.')
            for i, name in enumerate(names, offset):
                if name in values:z[system.feedback_start+i] = vector(values[name], (), 'Initial '+name)/f.scales[i]
    return z


class ConsistentSubspace:
    """Full finite invariant space, including neutral/integrator chains."""
    def __init__(self, a, m, dynamic_indices, time_scale=1., tolerance=1e-9):
        if not np.isfinite(tolerance) or not 1e-12 <= tolerance <= 1e-5:
            raise AnalysisError('Initial-state rank tolerance must be between 1e-12 and 1e-5.')
        if not np.isfinite(time_scale) or time_scale <= 0:
            raise AnalysisError('Initial-state time scale must be finite and positive.')
        self.a, self.m = np.asarray(a), np.asarray(m)
        self.rows = np.maximum(np.maximum(np.linalg.norm(a, axis=1), np.linalg.norm(m*time_scale, axis=1)), 1e-30)
        aa, mm = a/self.rows[:, None], m*time_scale/self.rows[:, None]
        self.lift, history = finite_subspace(aa, mm, tolerance)
        if not self.lift.shape[1]:raise AnalysisError('This constrained system has no finite dynamic initial disturbances.')
        az, mz = aa@self.lift, mm@self.lift
        self.generator, _, rank, _ = lstsq(mz, az, cond=tolerance)
        if rank != self.lift.shape[1]:raise AnalysisError('Initial-state finite dynamics are not uniquely resolved.')
        defect = mz@self.generator-az
        residual = float(np.linalg.norm(defect)/(np.linalg.norm(mz)*np.linalg.norm(self.generator)+np.linalg.norm(az)+1e-30))
        if residual > 1e-9:raise AnalysisError('Initial-state reduction fails the complete descriptor equations.')
        self.generator *= time_scale
        self.indices = np.asarray(dynamic_indices, dtype=int)
        self.observed = self.lift[self.indices]
        singular = svdvals(self.observed)
        if len(singular) < self.lift.shape[1] or singular[-1] < 1e-10*singular[0]:
            raise AnalysisError('The physical initial coordinates do not uniquely determine the finite state; refine rank and difference settings.')
        values = eigvals(self.generator)
        self.growth = float(np.max(values.real))
        self.time_scale = time_scale
        self.report = dict(finite_dimension=self.lift.shape[1], rank_tolerance=tolerance, constraint_reduction=history,
            full_equation_backward_error=residual, dynamic_coordinate_reciprocal_condition=float(singular[-1]/singular[0]),
            spectral_abscissa=self.growth, eigenvalues=complex_data(values),
            interpretation='Complete finite descriptor subspace, including constitutive relaxation and integrator chains; no selected-mode truncation.')

    def complete(self, requested):
        known = requested[self.indices];amplitude = float(np.max(abs(known), initial=0.))
        if not amplitude:raise AnalysisError('Initial disturbance must contain at least one nonzero physical dynamic coordinate.')
        coordinates, _, rank, _ = lstsq(self.observed, known/amplitude, cond=1e-10)
        mismatch = float(np.max(abs(self.observed@coordinates-known/amplitude)))
        if rank != self.lift.shape[1] or mismatch > 1e-7:
            raise AnalysisError(f'Initial disturbance violates algebraic or hidden dynamic constraints (relative mismatch {mismatch:.3g}). Specify compatible nodal/frame fields; no inconsistent state is projected silently.')
        z = self.lift@coordinates*amplitude
        rate = self.lift@(self.generator@coordinates)*amplitude
        residual = (self.m@rate-self.a@z)/self.rows
        error = float(np.max(abs(residual))/max(np.max(abs(self.a@z/self.rows)), np.max(abs(self.m@rate/self.rows)), amplitude, 1e-30))
        if error > 1e-7:raise AnalysisError('Completed initial disturbance fails the full dynamic residual.')
        return z, rate, dict(dynamic_coordinate_mismatch=mismatch, full_equation_scaled_residual=error)

    def transform_shift(self, shift):
        """Require convergence of the complete finite-system Laplace transform."""
        if not np.isfinite(shift) or shift < 0:
            raise AnalysisError('Initial Laplace damping must be finite and nonnegative in 1/input T.')
        margin = 1e-8*max(self.time_scale, abs(self.growth))
        if shift <= self.growth+margin:
            raise AnalysisError(f'Initial-state transform requires Laplace damping above the resolved spectral abscissa {self.growth:.6g}/T plus a {margin:.3g}/T numerical margin. Increase initial_shift or refine the dynamic tangent; a nondecaying initial response has no ordinary Fourier integral.')
        return float(shift)


class InitialInput:
    kind = 'initial'
    scale = 1.

    def __init__(self, system, specification, index):
        if set(specification)-{'kind', 'name', 'state'} or 'state' not in specification:
            raise AnalysisError('Initial inputs require kind=initial, a physical state, and an optional name.')
        self.system = system
        self.requested = dynamic_state(system, specification['state'])
        name = specification.get('name', f'initial_{index+1}')
        if not isinstance(name, str) or not name.strip():raise AnalysisError('Initial input name must be a nonempty string.')
        self.report = dict(name=name, kind=self.kind, unit='profile amplitude (dimensionless)', scale=1., output_time_power=1,
            specified_state=deepcopy(specification['state']), broken_loop_output=None)

    def prepare(self, subspace, shift, step):
        self.shift = subspace.transform_shift(shift)
        self.initial, rate, checks = subspace.complete(self.requested)
        self.rhs = subspace.m@self.initial
        self.report.update(laplace_shift=self.shift, resolved_state=self.initial.tolist(), resolved_rate=rate.tolist(),
            consistency=checks, initial_output=output_perturbation(self.system, self.initial, rate, step),
            transform='X(s)=integral_0^infinity delta_x(t) exp(-s t) dt; s=initial_shift+i omega. Rate transform=s X-x0. All output spectra carry one additional input time unit.')
