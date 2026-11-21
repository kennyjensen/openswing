"""Seeded-corrector eligibility, complete matrices, and injected recovery paths."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import gc
import json
import re
import weakref

import numpy as np
import pytest
from scipy.sparse import issparse, csc_matrix

from openswing.aero import AnalysisError, FlightCondition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork, equilibrate
from openswing.equilibrium_state import capture, correct
from openswing.newton_structure import NewtonBeamFactor, StructureUnavailable
import openswing.equilibrium_state as equilibrium
import openswing.seeded_corrector as seeded

EXAMPLES = Path(__file__).resolve().parents[1]/'examples'
EVIDENCE = []


def model(kind='flexible', zero=False, scaled=False):
    source = (EXAMPLES/('articulated.asw' if kind == 'joint' else 'flexible.asw')).read_text()
    if kind == 'joint':
        source = re.sub(r'Jangle\n.*?\nEnd\n', '', source, flags=re.S)
        source = source.replace('1 2 2 2 3', '1 2 2 3 0').replace('1 3 -2 -2 3', '1 3 -2 -3 0')
    if zero:
        source = source.replace('0 .008 2 -.035 0', '0 0 0 0 0').replace('8 .008 2 -.035 -2', '8 0 0 0 0')
    if scaled:
        source = source.replace('40000 800000 12000 10000000', '40000000 800000000 12000000 10000000000')
        source = source.replace('10000 200000 3000 4000000', '10000000 200000000 3000000 4000000000')
    value = parse_asw(source)
    assert not value.diagnostics
    return value


def network(*, frozen=False, zero=False, kind='flexible', scaled=False, cls=StaticNetwork):
    return cls(model(kind, zero, scaled), 4,
               FlightCondition(speed=8, alpha=0 if zero else 2, mach=.03,
                               freeze_influences=frozen), [0, 0, 0], [])


def zero_seed(n):
    return capture(n, np.zeros(n.size), residual=None)


def physical_check(n, x):
    residual = n.residual(x)
    assert np.isfinite(x).all() and np.isfinite(residual).all()
    assert np.max(abs(residual)) <= 1e-8
    rank = n.equilibrium_diagnostics
    if rank['rank_check'] == 'sparse inverse-norm certificate':
        assert rank['column_scaled_reciprocal_condition'] is None
        lower = rank['column_scaled_reciprocal_condition_lower_bound']
        assert np.isfinite(lower) and lower > 1e-10
    else:
        assert rank['rank_check'] == 'full-Jacobian SVD'
        assert np.isfinite(rank['column_scaled_reciprocal_condition'])
        assert rank['column_scaled_reciprocal_condition'] >= 1e-10
        assert 'column_scaled_reciprocal_condition_lower_bound' not in rank
    assert n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None
    return float(np.max(abs(residual)))


@pytest.mark.parametrize('frozen', [False, True])
def test_actual_mounted_seeded_public_solve_uses_builder_and_releases_factors(frozen, monkeypatch):
    n = network(frozen=frozen)
    initial = zero_seed(n); untouched = deepcopy(initial)
    contexts = []; wrappers = []; final_checks = []
    original_attach = seeded.attach; original_wrapper = seeded._ObservedFactor
    original_jacobian = StaticNetwork.jacobian

    @contextmanager
    def observe_attach(*args, **kwargs):
        contexts.append(args[1])
        with original_attach(*args, **kwargs) as builder:
            yield builder

    def observe_wrapper(*args):
        value = original_wrapper(*args); wrappers.append(weakref.ref(value)); return value

    def observe_jacobian(self, x, factor, **options):
        if getattr(self, '_seeded_corrector_diagnostics', {}).get('builder_detached', False):
            assert options.get('_sparse') is True and options.get('_direct_geometry') is False
            gc.collect()
            assert contexts and not hasattr(contexts[-1], 'factorization_builder')
            assert wrappers and all(value() is None for value in wrappers)
            final_checks.append(True)
        return original_jacobian(self, x, factor, **options)

    monkeypatch.setattr(seeded, 'attach', observe_attach)
    monkeypatch.setattr(seeded, '_ObservedFactor', observe_wrapper)
    monkeypatch.setattr(StaticNetwork, 'jacobian', observe_jacobian)
    x, steps = equilibrate(n, tolerance=1e-9, initial_state=initial)
    norm = physical_check(n, x)
    report = n.equilibrium_diagnostics['seeded_corrector']
    assert report['enabled'] and report['eligible'] and report['builder_detached']
    assert report['builds'] and all(row['status'] == 'BUILT' for row in report['builds'])
    assert sum(row['solve_completions'] for row in report['builds']) > 0
    assert report['factor_wrappers_alive_before_final_tangent'] == 0
    assert all(row['tangent_owner_restored'] and row['iteration_fields_unchanged']
               and row['tangent_load_owner_restored'] for row in report['builds'])
    assert final_checks == [True] and initial == untouched and steps == 1
    # The report is durable scalar/container data, with no matrix/factor owner.
    json.dumps(report, allow_nan=False)
    EVIDENCE.append(dict(test='public_solve', frozen=frozen, size=n.size, residual=norm,
                         diagnostics=n.equilibrium_diagnostics))


@pytest.mark.parametrize('case', [
    'subclass', 'residual_override', 'jacobian_override', '_jacobian_override',
    'condition', 'ground', 'operating_count', 'operating_constraint', 'custom', 'minimum',
    'feedback', 'hinges', 'type3', 'engine', 'strut', 'wire', 'residual_options',
    'final_tangent', 'frequency', 'iteration_owner', 'tangent_owner', 'load_owner', 'existing_builder'])
def test_declined_context_has_no_numerical_work_or_owner_mutation(case, monkeypatch):
    class Subclass(StaticNetwork):
        pass
    n = network(cls=Subclass if case == 'subclass' else StaticNetwork)
    initial = {}; options = {}; final = None
    function = lambda x: x
    if case.endswith('_override'):
        monkeypatch.setattr(n, case.removesuffix('_override'), lambda *args, **kwargs: None)
    if case == 'condition': n.condition = None
    if case == 'ground': n.constraints = []
    if case == 'operating_count': n.operating.count = 1
    if case == 'operating_constraint': n.operating.constraints = [object()]
    if case == 'custom': n.operating.custom = {'target': object()}
    if case == 'minimum': n.operating.minimum_indices = [0]
    if case == 'feedback': initial = {'feedback': {}}
    if case == 'hinges': n.hinges = [object()]
    if case == 'type3': n.constraints = [dict(kind='ground', type=3)]
    if case == 'engine': n.engines = [object()]
    if case == 'strut': n.struts = [object()]
    if case == 'wire': n.tension_only = True
    if case == 'residual_options': options = {'unused': True}
    if case == 'final_tangent': final = lambda x: x
    if case == 'frequency': n._frequency_local_geometry = True
    if case == 'iteration_owner': n.iteration_fields = object()
    if case == 'tangent_owner': n.tangent_influences = object()
    if case == 'load_owner': n._tangent_loads = object()
    if case == 'existing_builder': function.factorization_builder = object()
    before = n.nfev
    owners = (n.iteration_fields, n.tangent_influences, n._tangent_loads)
    previous = getattr(function, 'factorization_builder', None)
    report = {}
    with seeded.attach(n, function, initial, options, final_tangent=final, report=report) as builder:
        assert builder is None and not report['eligible'] and not report['enabled']
        assert report['decline_reasons'] and report['builds'] == []
        assert getattr(function, 'factorization_builder', None) is previous
    assert n.nfev == before and getattr(function, 'factorization_builder', None) is previous
    assert all(current is old for current, old in zip(
        (n.iteration_fields, n.tangent_influences, n._tangent_loads), owners))
    assert not hasattr(n, '_seeded_corrector_diagnostics')


def test_slot_adapter_without_nfev_or_new_attribute_support_keeps_old_path(monkeypatch):
    class Adapter:
        __slots__ = ('constraints', 'hinges', 'equilibrium_diagnostics')
        def __init__(self): self.constraints = []; self.hinges = []
        def residual(self, x, factor=1): return x-1
        def jacobian(self, x, factor=1): return np.eye(1)
    n = Adapter()
    monkeypatch.setattr(equilibrium, 'restore', lambda *args: np.zeros(1))
    values, steps = correct(n, {}, 1e-9, {})
    np.testing.assert_allclose(values, [1], atol=1e-9, rtol=0)
    assert steps == 1 and 'seeded_corrector' not in n.equilibrium_diagnostics
    assert not hasattr(n, 'nfev') and not hasattr(n, '_seeded_corrector_diagnostics')


def test_adapter_original_physical_error_is_not_replaced_by_observation_error(monkeypatch):
    class Adapter:
        __slots__ = ()
        constraints = []; hinges = []
        def residual(self, x, factor=1): raise AnalysisError('original adapter physical error')
    monkeypatch.setattr(equilibrium, 'restore', lambda *args: np.zeros(1))
    with pytest.raises(AnalysisError, match='Warm equilibrium correction failed: original adapter physical error'):
        correct(Adapter(), {}, 1e-9, {})


def test_feedback_rejection_still_precedes_restore(monkeypatch):
    def forbidden(*args): raise AssertionError('restore must not run')
    monkeypatch.setattr(equilibrium, 'restore', forbidden)
    with pytest.raises(AnalysisError, match='controller equilibrium seed'):
        correct(object(), {'feedback': {}}, 1e-9, {})


def test_custom_final_tangent_preserved_and_no_candidate_diagnostics():
    n = network(zero=True); seed = zero_seed(n); calls = []
    def final(x):
        calls.append(x.copy())
        return n.jacobian(x, 1.)
    x, steps = correct(n, seed, 1e-9, {}, final_tangent=final)
    assert len(calls) == 1 and steps == 1 and not hasattr(n, '_seeded_corrector_diagnostics')
    assert 'seeded_corrector' not in n.equilibrium_diagnostics
    assert n.equilibrium_diagnostics['final_tangent'].startswith('provided physical tangent')
    physical_check(n, x)


@pytest.mark.parametrize('failure', ['storage', 'factor', 'assembly', 'direction', 'line_search'])
def test_supported_structured_failure_uses_original_dense_recovery(failure, monkeypatch):
    n = network(); seed = zero_seed(n); original_factor = seeded.NewtonBeamFactor
    original_jacobian = StaticNetwork.jacobian
    attempted = []; corrupt_calls = []

    def factor(net, matrix):
        attempted.append(failure)
        if failure == 'storage':
            return original_factor(net, matrix, byte_budget=1)
        if failure == 'factor': raise RuntimeError('injected sparse factor failure')
        actual = original_factor(net, matrix)
        if failure == 'direction':
            def corrupted(rhs):
                corrupt_calls.append(rhs.shape)
                return np.zeros_like(rhs, dtype=complex)
            monkeypatch.setattr(actual.factor, 'solve', corrupted)
        if failure == 'line_search':
            def no_descent(rhs):
                corrupt_calls.append(rhs.shape)
                return np.zeros_like(rhs)
            monkeypatch.setattr(actual, 'solve', no_descent)
        return actual

    def jacobian(self, x, load, **options):
        if (failure == 'assembly' and options.get('_sparse')
                and not getattr(self, '_seeded_corrector_diagnostics', {}).get('builder_detached', False)):
            attempted.append(failure)
            raise ValueError('injected sparse assembly failure')
        return original_jacobian(self, x, load, **options)

    monkeypatch.setattr(seeded, 'NewtonBeamFactor', factor)
    monkeypatch.setattr(StaticNetwork, 'jacobian', jacobian)
    x, steps = equilibrate(n, tolerance=1e-9, initial_state=seed)
    norm = physical_check(n, x)
    report = n.equilibrium_diagnostics['seeded_corrector']
    assert attempted == [failure] and steps == 1 and report['dense_tangent_builds'] >= 1
    assert report['builder_detached'] and report['factor_wrappers_alive_before_final_tangent'] == 0
    build = report['builds'][0]
    if failure in ('storage', 'factor', 'assembly'):
        assert build['status'] == 'BUILD_EXCEPTION'
    if failure == 'direction':
        assert corrupt_calls and build['solve_failures']
        assert 'full-equation residual' in build['solve_failures'][0]['message']
    if failure == 'line_search':
        assert corrupt_calls and build['solve_calls'] == build['solve_completions'] == 1
        assert build['solve_failures'] == []
    EVIDENCE.append(dict(test='dense_recovery', injected=failure, size=n.size,
                         residual=norm, diagnostics=n.equilibrium_diagnostics))


@pytest.mark.parametrize('error_type', [MemoryError, KeyboardInterrupt])
@pytest.mark.parametrize('where', ['assembly', 'factor'])
def test_resource_or_interrupt_error_propagates_without_dense_retry(error_type, where, monkeypatch):
    n = network(); seed = zero_seed(n); error = error_type('deliberate propagation')
    original_jacobian = StaticNetwork.jacobian; calls = []
    def jacobian(self, x, load, **options):
        calls.append(bool(options.get('_sparse')))
        if where == 'assembly' and options.get('_sparse'): raise error
        return original_jacobian(self, x, load, **options)
    def unavailable(*args): raise error
    monkeypatch.setattr(StaticNetwork, 'jacobian', jacobian)
    if where == 'factor': monkeypatch.setattr(seeded, 'NewtonBeamFactor', unavailable)
    with pytest.raises(error_type) as caught:
        equilibrate(n, tolerance=1e-9, initial_state=seed)
    assert caught.value is error and calls == [True]
    report = n._seeded_corrector_diagnostics
    assert report['builder_detached'] and report['phases']['newton']['status'] == 'EXCEPTION'
    assert len(report['builds']) == 1 and report['builds'][0]['exception_type'] == error_type.__name__
    assert n.aero_key is n.aero_cached is None
    assert n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None


def test_zero_residual_seed_still_reaches_original_rank_rejection(monkeypatch):
    n = network(zero=True); seed = zero_seed(n)
    assert not np.any(n.residual(np.zeros(n.size)))
    calls = []
    def singular_final(self, x, factor, **options):
        assert options.get('_sparse') is True
        assert n._seeded_corrector_diagnostics['builder_detached']
        calls.append(True)
        return csc_matrix((n.size, n.size))
    monkeypatch.setattr(StaticNetwork, 'jacobian', singular_final)
    with pytest.raises(AnalysisError, match='Warm equilibrium tangent is singular'):
        equilibrate(n, tolerance=1e-9, initial_state=seed)
    report = n._seeded_corrector_diagnostics
    assert calls == [True] and report['builds'] == [] and report['newton_tangent_builds'] == 0
    assert report['factor_wrappers_alive_before_final_tangent'] == 0
    assert report['phases']['final_rank']['status'] == 'EXCEPTION'


@pytest.mark.parametrize('kind,frozen,scaled', [
    ('flexible', False, False), ('flexible', True, False),
    ('flexible', False, True), ('joint', True, False)])
def test_deformed_complete_sparse_matrix_matches_same_dense_and_full_equations(kind, frozen, scaled):
    n = network(kind=kind, frozen=frozen, scaled=scaled)
    x = np.random.default_rng(729).normal(0, .002, n.size)
    x[:6*n.nn].reshape(-1, 6)[:, 3:] += [.08, -.03, .04]
    x[n.gamma_start:] += .12
    owners = (n.tangent_influences, n.iteration_fields, n._tangent_loads)
    sparse = n.jacobian(x, 1., _sparse=True, _direct_geometry=False)
    dense = n.jacobian(x, 1., _sparse=False, _direct_geometry=False)
    assert issparse(sparse) and sparse.shape == dense.shape == (n.size, n.size)
    np.testing.assert_array_equal(sparse.toarray(), dense)
    assert np.count_nonzero(sparse.data) == np.count_nonzero(dense)  # no tolerance pruning
    factor = NewtonBeamFactor(n, sparse)
    rhs_vectors = [n.residual(x), np.random.default_rng(318).normal(size=n.size)]
    residuals = []
    for rhs in rhs_vectors:
        direction = factor.solve(rhs)
        residual = dense@direction-rhs
        gate = 1e-8*max(1., np.max(abs(rhs)))
        assert np.isfinite(direction).all() and np.max(abs(residual)) <= gate
        residuals.append(dict(residual=float(np.max(abs(residual))), limit=float(gate)))
    assert all(current is old for current, old in zip(
        (n.tangent_influences, n.iteration_fields, n._tangent_loads), owners))
    EVIDENCE.append(dict(test='complete_matrix', kind=kind, frozen=frozen, scaled=scaled,
                         size=n.size, nonzeros=sparse.nnz,
                         minimum_nonzero=float(np.min(abs(dense[dense != 0]))),
                         full_equation_checks=residuals))


@pytest.mark.parametrize('frozen', [False, True])
def test_converged_final_sparse_matrix_is_fresh_complete_at_returned_state(frozen, monkeypatch):
    n = network(frozen=frozen); initial = zero_seed(n); untouched = deepcopy(initial)
    original = StaticNetwork.jacobian; final = []; events = []; calls = []
    def observe(self, values, factor, **options):
        detached = getattr(self, '_seeded_corrector_diagnostics', {}).get('builder_detached', False)
        calls.append(dict(final=detached, sparse=bool(options.get('_sparse')), state=values.copy()))
        matrix = original(self, values, factor, **options)
        if detached:
            assert self._seeded_corrector_diagnostics['factor_wrappers_alive_before_final_tangent'] == 0
            assert options['_sparse'] is True and options['_direct_geometry'] is False
            assert issparse(matrix) and matrix.shape == (n.size, n.size)
            final.append((values.copy(), matrix.copy()))
        return matrix
    monkeypatch.setattr(StaticNetwork, 'jacobian', observe)
    x, steps = equilibrate(n, tolerance=1e-9, initial_state=initial,
                          progress=lambda *event: events.append(event))
    assert len(final) == 1 and sum(c['final'] for c in calls) == 1
    np.testing.assert_array_equal(final[0][0], x)
    # Exactly one independently fresh dense final assembly, from original
    # method with identical converged state and geometry options; no new solve.
    dense = original(n, x, 1., _sparse=False, _direct_geometry=False)
    sparse = final[0][1]
    np.testing.assert_array_equal(sparse.toarray(), dense)
    assert np.count_nonzero(sparse.data) == np.count_nonzero(dense)
    tangent = [event for event in events if event[0] == 'equilibrium_tangent']
    assert tangent[0] == ('equilibrium_tangent', 0, n.size)
    assert tangent[-1] == ('equilibrium_tangent', n.size, n.size)
    assert sum(event[1] == 0 for event in tangent) == 1
    assert not any(event[0] == 'static_tangent' for event in events)
    rank = n.equilibrium_diagnostics
    assert rank['rank_check'] == 'sparse inverse-norm certificate'
    report = rank['seeded_corrector']
    assert report['final_tangent_storage'] == 'sparse'
    assert report['final_tangent_values_unchanged'] and report['rank_acceptance_threshold_unchanged']
    assert report['phases']['final_tangent']['status'] == report['phases']['final_rank']['status'] == 'COMPLETED'
    assert steps == 1 and initial == untouched
    residual = physical_check(n, x)
    EVIDENCE.append(dict(test='actual_converged_final_matrix', frozen=frozen, size=n.size,
                         final_sparse_assemblies=1, independent_dense_assemblies=1,
                         solve_calls=1, residual=residual, state=x.tolist(),
                         sparse_final=sparse.toarray().tolist(), independent_dense=dense.tolist(),
                         events=events, diagnostics=rank))


def test_actual_sparse_final_inconclusive_certificate_uses_full_svd(monkeypatch):
    import openswing.sparse_rank as sparse_rank
    n = network(zero=True); initial = zero_seed(n)
    monkeypatch.setattr(sparse_rank, 'column_scaled_inverse_bound', lambda *args, **kwargs: 0.)
    original = np.linalg.svd; calls = []
    def observe(matrix, *args, **kwargs):
        if matrix.shape == (n.size, n.size): calls.append(matrix.copy())
        return original(matrix, *args, **kwargs)
    monkeypatch.setattr(np.linalg, 'svd', observe)
    x, steps = equilibrate(n, tolerance=1e-9, initial_state=initial)
    assert len(calls) == 1 and steps == 1
    rank = n.equilibrium_diagnostics
    assert rank['rank_check'] == 'full-Jacobian SVD'
    assert 'column_scaled_reciprocal_condition_lower_bound' not in rank
    assert rank['seeded_corrector']['final_tangent_storage'] == 'sparse'
    physical_check(n, x)


@pytest.mark.parametrize('kind', [ValueError, RuntimeError, MemoryError, KeyboardInterrupt])
def test_final_sparse_assembly_failure_propagates_without_retry_and_restores_owners(kind, monkeypatch):
    n = network(zero=True); initial = zero_seed(n); untouched = deepcopy(initial)
    original = StaticNetwork._jacobian; failure = kind('injected final assembly failure'); calls = []
    def unavailable(self, values, factor, **options):
        if getattr(self, '_seeded_corrector_diagnostics', {}).get('builder_detached', False):
            calls.append(True)
            assert options['sparse'] is True and self.tangent_influences is not None
            raise failure
        return original(self, values, factor, **options)
    monkeypatch.setattr(StaticNetwork, '_jacobian', unavailable)
    expected = AnalysisError if kind is ValueError else kind
    with pytest.raises(expected, match='injected final assembly failure') as caught:
        equilibrate(n, tolerance=1e-9, initial_state=initial)
    if kind is not ValueError: assert caught.value is failure
    assert calls == [True] and initial == untouched
    report = n._seeded_corrector_diagnostics
    assert report['builder_detached'] and report['factor_wrappers_alive_before_final_tangent'] == 0
    assert report['builds'] == [] and report['phases']['final_tangent']['status'] == 'EXCEPTION'
    assert 'final_rank' not in report['phases']
    assert n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None


@pytest.mark.parametrize('stage', ['equilibrium_tangent', 'equilibrium_rank'])
@pytest.mark.parametrize('kind', [ValueError, RuntimeError, KeyboardInterrupt])
def test_final_stage_callback_failure_propagates_and_restores_owners(stage, kind):
    n = network(zero=True); initial = zero_seed(n); untouched = deepcopy(initial)
    failure = kind('injected final callback failure'); calls = []
    def progress(name, done, total):
        if name == stage:
            calls.append((name, done, total))
            raise failure
    expected = AnalysisError if kind is ValueError else kind
    with pytest.raises(expected, match='injected final callback failure') as caught:
        equilibrate(n, tolerance=1e-9, initial_state=initial, progress=progress)
    if kind is not ValueError: assert caught.value is failure
    assert len(calls) == 1 and calls[0][1:] == (0, n.size) and initial == untouched
    report = n._seeded_corrector_diagnostics
    assert report['builder_detached'] and report['factor_wrappers_alive_before_final_tangent'] == 0
    phase = 'final_tangent' if stage == 'equilibrium_tangent' else 'final_rank'
    assert report['phases'][phase]['status'] == 'EXCEPTION'
    assert report['builds'] == []
    assert n.iteration_fields is None and n.tangent_influences is None and n._tangent_loads is None


@pytest.fixture(scope='module', autouse=True)
def retain_module_evidence(tmp_path_factory):
    yield
    # Raw final matrices and completed prior evidence survive assertion failure.
    (tmp_path_factory.mktemp('seeded-corrector-evidence')/'evidence.json').write_text(
        json.dumps(EVIDENCE, indent=2, allow_nan=False)+'\n')
