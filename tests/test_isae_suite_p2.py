"""Source-only input recovery, complete P-2 outputs, and rejection of bad evidence."""
from copy import deepcopy
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from scripts import isae_suite_p2 as adapter
from scripts.isae_acceptance import apply_reference_acceptance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


@lru_cache(maxsize=None)
def module(filename):
    spec = importlib.util.spec_from_file_location(filename.replace('-', '_'), ROOT/'scripts'/filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture(scope='module')
def evidence():
    jobs = adapter.plan(ROOT)
    return [(job, adapter.run(ROOT, job)) for job in jobs]


def test_complete_original_input_and_target_inventory():
    jobs = adapter.plan(ROOT)
    assert len(jobs) == 4
    assert sum(j['expected_outputs'] for j in jobs) == 312
    assert sum(len(j['samples']) for j in jobs) == 52
    assert [j['samples'][0]['tokens'][2] for j in jobs] == ['0.083298', '0.077088', '0.154376', '0.147676']
    assert all(j['comparison_scope'] == 'p2-reconstructed-inputs' for j in jobs)
    assert all(len({o['name'] for o in j['observations']}) == j['expected_outputs'] for j in jobs)
    json.dumps(jobs, allow_nan=False)


def test_all_312_declared_comparisons_pass_five_percent(evidence):
    runner = module('run-isae-suite.py')
    summary = module('summarize-isae-suite.py')
    total = 0
    for job, raw in evidence:
        checked = runner.checked_result(job, raw)
        assert checked['status'] == 'computed', checked.get('contract_error')
        assert not checked['reference_match']  # Printed-coefficient recovery is not bitwise reproduction.
        accepted = apply_reference_acceptance(checked)
        assert accepted['reference_match']
        counts = summary.scalar_counts(dict(job, result=accepted))
        assert counts['passed'] == counts['required'] == job['expected_outputs']
        total += counts['passed']
        assert max(abs(c['predicted']-c['expected'])/abs(c['expected']) for c in raw['reference_checks'] if abs(c['expected'])>1e-8) < .0064
    assert total == 312


def test_inputs_do_not_depend_on_archived_predictions(evidence):
    job = deepcopy(evidence[0][0])
    before = adapter.reconstruct_drag(job['samples'][1:], .2286)
    for observation in job['observations']:
        observation['expected'] *= 7
    assert adapter.reconstruct_drag(job['samples'][1:], .2286) == before
    assert not before['model_targets_used'] and not before['static_row_included']
    assert [float(f'{x:.1e}') for x in before['coefficients']] == job['rounded_coefficients']
    with pytest.raises(ValueError, match='forward-flow'):
        adapter.reconstruct_drag(job['samples'], .2286)


def test_nondimensional_results_do_not_depend_on_nominal_rpm_density(evidence):
    job, result = evidence[0]
    settings = dict(job['settings'], nominal_rpm=2813., density_kg_m3=.91)
    rows = adapter.evaluate(job['samples'], settings, result['input_reconstruction']['coefficients'])
    for row, original in zip(rows, result['rows']):
        assert row['CT'] == pytest.approx(original['CT'], abs=2e-12, rel=0)
        assert row['eta'] == pytest.approx(original['eta'], abs=2e-12, rel=0)
        assert max(row['physical_metrics'].values()) < 2e-12


@pytest.mark.parametrize('fault', ['gate', 'target', 'scope', 'source_row', 'density'])
def test_changed_prepared_sources_are_rejected(fault):
    job = deepcopy(adapter.plan(ROOT)[0])
    if fault == 'gate': job['strict_tolerance'] = .05
    if fault == 'target': job['observations'][0]['expected'] *= 1.01
    if fault == 'scope': job['comparison_scope'] = 'historically_exact'
    if fault == 'source_row': job['samples'][0]['CP'] *= 1.01
    if fault == 'density': job['settings']['density_kg_m3'] = .91
    with pytest.raises(ValueError, match='Prepared P-2'):
        adapter.verify_reference_sources(ROOT, job)


@pytest.mark.parametrize('fault', ['target', 'gate', 'prediction', 'power', 'calibration', 'drop',
                                  'duplicate', 'scope', 'numerical', 'operations', 'pins'])
def test_runner_and_summary_reject_corrupted_results(evidence, fault):
    job, original = evidence[0]
    result = deepcopy(original)
    if fault == 'target': result['reference_checks'][0]['expected'] *= 1.01
    if fault == 'gate': result['reference_checks'][0]['tolerance'] = .05
    if fault == 'prediction': result['reference_checks'][0]['predicted'] *= 1.01
    if fault == 'power': result['rows'][0]['state']['requested_power'] *= 1.01
    if fault == 'calibration': result['input_reconstruction']['coefficients'][0] *= 1.00001
    if fault == 'drop': result['rows'].pop()
    if fault == 'duplicate': result['rows'][-1] = result['rows'][0]
    if fault == 'scope': result['comparison_scope'] = 'unqualified'
    if fault == 'numerical': result['numerical_passed'] = False
    if fault == 'operations': result['operations']['engine_load_calls'] -= 1
    if fault == 'pins': result['source_pins_unchanged'] = False
    runner = module('run-isae-suite.py')
    assert runner.checked_result(job, result)['status'] == 'adapter_contract_failure'
    summary = module('summarize-isae-suite.py')
    with pytest.raises(ValueError):
        summary.scalar_counts(dict(job, result=result))
