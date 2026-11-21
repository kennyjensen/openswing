"""Optional complete sparse iteration factors for a narrow saved-state path.

This supplies the nonlinear iteration approximation. Full residual acceptance
and a fresh complete final tangent/rank check remain the caller's responsibility.
No lagged IterationFields are installed.
"""
from contextlib import contextmanager
from time import perf_counter
from weakref import ref

from .newton_structure import NewtonBeamFactor


@contextmanager
def phase(n, report, name):
    """Observe native nfev and elapsed time without wrapping numerical methods."""
    record = dict(status='STARTED', residual_count_before=int(n.nfev))
    report.setdefault('phases', {})[name] = record
    before = perf_counter()
    try:
        yield
    except BaseException as exc:
        record.update(status='EXCEPTION', exception_type=type(exc).__name__)
        raise
    else:
        record['status'] = 'COMPLETED'
    finally:
        record.update(seconds=perf_counter()-before, residual_count_after=int(n.nfev))
        record['residual_calls'] = record['residual_count_after']-record['residual_count_before']


def _decline_reasons(n, function, initial, residual_options, final_tangent):
    from .network import StaticNetwork
    from .source_coupled import SourceCoupledNetwork
    from .source_airflow import SourceAirflowNetwork
    from .structured_static import acceleration_load_constraints
    reasons = []
    if type(n) not in (StaticNetwork, SourceCoupledNetwork, SourceAirflowNetwork):
        # Do not impose new attributes or inspect overridden properties on a
        # previously supported subclass/adapter; leave its old path intact.
        return ['network is not an unmodified supported steady network instance']
    if type(n) is SourceAirflowNetwork and not n.steady_trim:
        return ['moving-airflow correction requires an explicit steady-trim network']
    for name in ('residual', 'jacobian', '_jacobian'):
        if getattr(getattr(n, name), '__func__', None) is not getattr(type(n), name):
            reasons.append(f'network {name} method is overridden')
    if n.condition is None:
        reasons.append('mounted aerodynamic FlightCondition is required')
    if not any(c['kind'] == 'ground' for c in n.constraints):
        reasons.append('mounted ground constraints are required')
    if n.operating.count or n.operating.constraints:
        # Retain the canonical acceleration unknowns and net-load rows in the
        # complete matrix. Beam elimination keeps these global variables in
        # its reduced solve; it does not freeze or remove a frame equation.
        if type(n) is not SourceAirflowNetwork or not acceleration_load_constraints(n):
            reasons.append('operating constraints require steady moving-frame acceleration/net-load pairs')
    if n.operating.custom or n.operating.minimum_indices:
        reasons.append('custom targets or control allocation are outside the first scope')
    if isinstance(initial, dict) and initial.get('feedback') is not None:
        reasons.append('feedback seed is outside the first scope')
    if n.hinges or any(c['type'] == 3 for c in n.constraints):
        reasons.append('hinges are outside the first scope')
    if n.engines or n.struts or n.tension_only:
        reasons.append('engines, struts and wire branches are outside the first scope')
    if residual_options:
        reasons.append('residual overrides are outside the first scope')
    if final_tangent is not None:
        reasons.append('a caller-supplied final tangent is outside the first scope')
    if getattr(n, '_frequency_local_geometry', False):
        reasons.append('an existing geometry-decomposition mode is outside the first scope')
    if n.iteration_fields is not None:
        reasons.append('an IterationFields owner already exists')
    if n.tangent_influences is not None:
        reasons.append('a tangent-influence owner already exists')
    if n._tangent_loads is not None:
        reasons.append('a tangent-load owner already exists')
    if hasattr(function, 'factorization_builder'):
        reasons.append('the residual function already owns a factorization builder')
    return reasons


class _ObservedFactor:
    """Pass-through observations; never keep a second matrix or change a RHS."""
    def __init__(self, factor, record):
        self._factor = factor
        self._record = record

    def solve(self, rhs):
        record = self._record
        record['solve_calls'] += 1
        start = perf_counter()
        try:
            result = self._factor.solve(rhs)
        except BaseException as exc:
            record['solve_failures'].append(dict(type=type(exc).__name__, message=str(exc)[:512]))
            raise
        else:
            record['solve_completions'] += 1
            return result
        finally:
            record['solve_seconds'] += perf_counter() - start


class _Builder:
    def __init__(self, network, report):
        self.network = network
        self.report = report
        self._factors = []  # Weak references only; never retain an old factor.

    def __call__(self, x):
        n = self.network
        record = dict(index=len(self.report['builds']) + 1, status='STARTED',
                      residual_count_before=int(n.nfev), solve_calls=0,
                      solve_completions=0, solve_failures=[], solve_seconds=0.)
        self.report['builds'].append(record)
        before = perf_counter()
        owners = n.tangent_influences, n.iteration_fields, n._tangent_loads
        try:
            matrix = n.jacobian(x, 1., _sparse=True, _direct_geometry=False)
            record.update(assembly_seconds=perf_counter() - before,
                          shape=list(matrix.shape), nonzeros=int(matrix.nnz),
                          matrix_payload_bytes=int(matrix.data.nbytes + matrix.indices.nbytes + matrix.indptr.nbytes),
                          residual_count_after_assembly=int(n.nfev))
            factor_start = perf_counter()
            factor = NewtonBeamFactor(n, matrix)
            record.update(factorization_seconds=perf_counter() - factor_start,
                          factor_report=dict(factor.report), status='BUILT')
            observed = _ObservedFactor(factor, record)
            self._factors.append(ref(observed))
            return observed
        except BaseException as exc:
            record.update(status='BUILD_EXCEPTION', exception_type=type(exc).__name__,
                          exception_message=str(exc)[:512])
            # Existing newton decides which exceptions permit its dense retry.
            # In particular MemoryError/interruption are not converted into an
            # allocation-heavy fallback or reported as successful sparse work.
            raise
        finally:
            n.aero_key = n.aero_cached = None
            record.update(total_build_seconds=perf_counter() - before,
                          residual_count_after=int(n.nfev),
                          tangent_owner_restored=n.tangent_influences is owners[0],
                          iteration_fields_unchanged=n.iteration_fields is owners[1],
                          tangent_load_owner_restored=n._tangent_loads is owners[2],
                          aero_cache_invalidated=True)

    def after_newton(self):
        # This runs after the caller deletes the returned factor and before
        # allocating the final tangent. The report itself stores scalars,
        # dictionaries and weak references, never a matrix/factor/RHS.
        self.report['factor_wrappers_alive_before_final_tangent'] = sum(
            value() is not None for value in self._factors)


@contextmanager
def attach(n, function, initial, residual_options, *, final_tangent, report):
    reasons = _decline_reasons(n, function, initial, residual_options, final_tangent)
    report.update(eligible=not reasons, enabled=False, decline_reasons=reasons,
                  method='existing complete sparse Newton matrix and beam elimination',
                  iteration_matrix='network.jacobian(x, 1., _sparse=True, _direct_geometry=False)',
                  default_factor_payload_budget_bytes=128*1024**2,
                  storage_limit_is_not_total_peak_memory=True,
                  complete_residual_acceptance_unchanged=True,
                  final_tangent_values_unchanged=True,
                  rank_acceptance_threshold_unchanged=True,
                  final_tangent_storage='sparse' if not reasons else 'caller original',
                  final_rank_strategy='conservative certificate with full SVD fallback' if not reasons else 'caller original',
                  lagged_iteration_fields_installed=False, builds=[])
    if reasons:
        yield None
        return
    builder = _Builder(n, report)
    function.factorization_builder = builder
    report['enabled'] = True
    try:
        yield builder
    finally:
        del function.factorization_builder
        report['builder_detached'] = not hasattr(function, 'factorization_builder')
