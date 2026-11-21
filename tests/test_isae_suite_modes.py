"""Source-only ST4 adapter checks; no equilibrium or modal solves."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

from scripts import isae_suite_modes as modes

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original archive unavailable')
    before = {n for n in sys.modules if n.startswith('openswing')}
    result = modes.plan(ROOT)
    assert {n for n in sys.modules if n.startswith('openswing')} == before
    return result


def test_complete_original_model_export_and_scalar_accounting(jobs):
    assert len(jobs) == 42 and len({j['id'] for j in jobs}) == 42
    executable = [j for j in jobs if j['execution_route'] != 'unsupported']
    assert len(executable) == 5
    assert sum(j['expected_outputs'] for j in executable) == 93
    assert sum(j['expected_outputs'] for j in jobs) == 3749
    assert sum(j['blocker_code'] == 'NO_PAIRED_EXPORT' for j in jobs) == 27
    assert len({j['model_path'] for j in jobs if j['model_path']}) == 33
    assert len({j['table_path'] for j in jobs if j['table_path']}) == 15
    assert sum(len(j['reference_rows']) for j in jobs if j['blocker_code'] == 'COUPLED_MODAL_PROTOCOL_UNREVIEWED') == 1674
    assert all(j['complete_family_reproduction'] is False for j in jobs)


def test_seventh_ordinal_not_cherry_picked_and_endpoint_mesh_count(jobs):
    d = next(j for j in jobs if j['id'] == 'ST-4:Weight7d:vaccum')
    a = next(j for j in jobs if j['id'] == 'ST-4:Weight7a:vaccum')
    assert len(d['reference_rows']) == 7 and d['expected_outputs'] == 21
    assert d['reference_rows'][-1]['raw_tokens'] == ['1','-0.19935567E-10','1069.9037']
    assert [g['expected_elements'] for g in d['grids']] == [16,32,64]
    assert [g['expected_elements'] for g in a['grids']] == [17,33,65]
    assert 'positive[:7]' in d['verifier_sources']['verify']
    assert "len(cr['reference_comparison']) == len(fr['reference_comparison']) == 7" in d['verifier_sources']['compare_pair']
    assert 'reference.PENCIL_GATE' in d['verifier_sources']['verify']
    assert d['mesh_gate']['relative_gate'] == .001


def test_weight7a_request_matches_existing_reviewed_protocol(jobs,tmp_path):
    spec = importlib.util.spec_from_file_location('_test_st4_original_protocol', ROOT/'scripts/verify-isae-st4-arnoldi.py')
    helper = importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    request, plan = helper.prepare(tmp_path,16)
    job = next(j for j in jobs if j['id'] == 'ST-4:Weight7a:vaccum')
    assert request == job['grids'][0]['request']
    assert plan['reference_rows'] == job['reference_rows']
    assert plan['expected_elements'] == job['grids'][0]['expected_elements']


def test_blocked_entries_retain_raw_rows_without_replan_or_dispatch(jobs,monkeypatch):
    monkeypatch.setattr(modes,'plan',lambda *a:pytest.fail('Whole plan rebuilt'))
    monkeypatch.setattr(modes,'_dispatch',lambda *a:pytest.fail('Unsupported physical call'))
    for code in ('MISSING_BEAM_END','MISSING_EXACT_W0_PAIR','COUPLED_MODAL_PROTOCOL_UNREVIEWED','NO_PAIRED_EXPORT','AGGREGATE_PAIRING_UNRESOLVED'):
        job = next(j for j in jobs if j['blocker_code'] == code)
        result = modes.run(ROOT,job)
        assert result['status'] == 'unsupported' and result['physical_calls'] == 0
        assert len(result['reference_checks']) == job['expected_outputs']
        assert all(c['predicted'] is None and not c['passed'] for c in result['reference_checks'])


def test_modal_failure_stops_before_refining_and_keeps_all_targets(jobs,monkeypatch):
    job = next(j for j in jobs if j['execution_route'] == 'local_vacuum')
    calls = []
    def fail(request,progress):
        calls.append(request)
        raise RuntimeError('Deliberate mocked dispatch failure; no physics')
    monkeypatch.setattr(modes,'_dispatch',fail)
    result = modes.run(ROOT,job)
    assert len(calls) == result['physical_calls'] == 1
    assert result['status'] == 'numerical_failure' and not result['reference_match']
    assert len(result['reference_checks']) == job['expected_outputs'] == 18
    assert all(c['predicted'] is None for c in result['reference_checks'])
    assert result['errors'][0]['type'] == 'RuntimeError'


def test_changed_source_fails_before_any_dispatch(jobs,monkeypatch):
    job = deepcopy(next(j for j in jobs if j['execution_route'] == 'local_vacuum'))
    job['source_pins'][0]['sha256']='0'*64
    monkeypatch.setattr(modes,'_dispatch',lambda *a:pytest.fail('Source mismatch was ignored'))
    result = modes.run(ROOT,job)
    assert result['status'] == 'numerical_failure' and result['physical_calls'] == 0
    assert not result['source_pins_unchanged']


def test_target_rounding_and_sequence_validation():
    header = '# Beam\n#\n# Op.Point Eigenvalue\n'
    rows = modes.decode_table(header+'1 0.12018164E-12 38.924987\n1 1.0E-10 120.74387\n',True)
    assert rows[0]['exact_decimal_half_units'] == ['5E-21','5E-7']
    with pytest.raises(ValueError,match='sorting'):
        modes.decode_table(header+'1 0 40\n1 0 30\n',True)
    with pytest.raises(ValueError,match='row'):
        modes.decode_table(header+'1 0 30 extra\n',True)


def test_seventh_reference_check_and_real_residue_remain_separate(jobs):
    job = deepcopy(next(j for j in jobs if j['id'] == 'ST-4:Weight7d:vaccum'))
    job['grid_counts']=[16]
    packet = dict(reference_comparison=[dict(ordinal=i, actual_eigenvalue=[3.,r['eigenvalue'][1]],
        printed_precision=dict(real=False,imaginary=True)) for i,r in enumerate(job['reference_rows'],1)])
    checks = modes._reference_checks(job,{16:packet})
    assert len(checks) == 7 and all(c['passed'] for c in checks)
    assert checks[-1]['expected_token'] == '1069.9037'
    assert all(c['name'].endswith(':imaginary') for c in checks)


def test_aggregate_candidates_keep_missing_cells_and_exclude_experiments(jobs):
    candidates = [j for j in jobs if 'aggregate_targets' in j]
    assert [len(j['aggregate_targets']) for j in candidates] == [160,135]
    targets = [t for j in candidates for t in j['aggregate_targets']]
    assert sum(t['expected'] is None for t in targets) == 22
    assert all(t['name'].endswith('_Asw') for t in targets)
    assert any(t['raw_token'] == 'NC' for t in targets)
    assert all(j['execution_route'] == 'unsupported' and j['model_path'] is None for j in candidates)
