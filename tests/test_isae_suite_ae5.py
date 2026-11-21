"""AE5 source mismatches remain explicit; source gaps cannot gain 5% passes."""
import builtins
from copy import deepcopy
from functools import lru_cache
import importlib.util
from pathlib import Path
import sys

import pytest

from scripts import isae_suite_ae5 as adapter
from scripts.isae_acceptance import apply_reference_acceptance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


@lru_cache(maxsize=None)
def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'scripts'/name)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture(scope='module')
def jobs():
    return adapter.plan(ROOT)


def test_all_original_modal_and_boundary_values_are_retained(jobs):
    assert [j['expected_outputs'] for j in jobs] == [532,55]
    assert {o['native_index'] for o in jobs[0]['observations']} == set(range(1,30))
    assert all(o['IAS'] is None for o in jobs[0]['observations'])
    assert jobs[0]['commanded_IAS'] == list(range(9,31))
    assert sum(o['dataset']=='Analysis.m explicit ASWING arrays' for o in jobs[1]['observations']) == 46
    assert [o['expected'] for o in jobs[1]['observations'][-9:]] == [25.5,29.,25.,9.89,14.89,23.7,27.,96.,16.5]
    assert all(len({o['name'] for o in j['observations']}) == j['expected_outputs'] for j in jobs)


def test_blocked_route_imports_no_numerical_or_production_code(jobs,monkeypatch):
    original = builtins.__import__
    def guarded(name,*args,**kwargs):
        assert name.split('.')[0] not in ('numpy','scipy','openswing')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    for job in jobs:
        result = adapter.run(ROOT,job)
        assert result['status'] == 'unsupported' and result['physical_calls'] == 0
        assert len(result['reference_checks']) == job['expected_outputs']


def test_five_percent_does_not_turn_unmapped_outputs_green(jobs):
    runner, summary = module('run-isae-suite.py'), module('summarize-isae-suite.py')
    for job in jobs:
        result = runner.checked_result(job,adapter.run(ROOT,job))
        assert result['status'] == 'unsupported'
        accepted = apply_reference_acceptance(result)
        assert not accepted['reference_match']
        assert accepted['output_accounting']['passed'] == 0
        counts = summary.scalar_counts(dict(job,result=accepted))
        assert counts['passed'] == counts['numerically_valid_finite'] == 0
        assert counts['required'] == job['expected_outputs']


@pytest.mark.parametrize('fault',['prediction','numerical','secondary_numerical','match','computed','physical','imports',
                                  'calls','drop','duplicate','target','gate','code','whole_family'])
def test_fabricated_execution_and_changed_targets_are_rejected(jobs,fault):
    job = jobs[0]
    result = adapter.run(ROOT,job)
    if fault=='prediction':result['reference_checks'][0]['predicted']=result['reference_checks'][0]['expected']
    if fault=='numerical':result['numerical_pass']=True
    if fault=='secondary_numerical':result['numerical_passed']=True
    if fault=='match':result['reference_match']=True
    if fault=='computed':result['status']='computed'
    if fault=='physical':result['physical_calls']=1
    if fault=='imports':result['production_imports']=1
    if fault=='calls':result['operations']=dict(job['expected_operations'],cold_bridge_calls=1)
    if fault=='drop':result['reference_checks'].pop()
    if fault=='duplicate':result['reference_checks'][-1]=result['reference_checks'][0]
    if fault=='target':result['reference_checks'][0]['expected']*=1.01
    if fault=='gate':result['reference_checks'][0]['tolerance']=.05
    if fault=='code':result['blocker_code']='SOLVED'
    if fault=='whole_family':result['full_family_validated']=True
    runner, summary = module('run-isae-suite.py'), module('summarize-isae-suite.py')
    assert runner.checked_result(job,result)['status']=='adapter_contract_failure'
    with pytest.raises(ValueError): summary.scalar_counts(dict(job,result=result))


def test_guessed_speed_mapping_is_rejected(jobs):
    job = deepcopy(jobs[0]);job['observations'][0]['IAS']=2.
    with pytest.raises(ValueError,match='prepared source'):
        adapter.verify_reference_sources(ROOT,job)


def test_literal_stiffness_and_unterminated_alternate_are_not_silently_repaired():
    from openswing.asw import parse_asw, AswError
    base=ROOT/'.reference/isae-validation'/adapter.REVISION/adapter.FAMILY
    model=parse_asw((base/'Flutter_Boundaries/[03_90].asw').read_text())
    beam=model.beams[0]
    assert float(beam.value('GJ',.25)) == 8000.
    assert float(beam.value('EInn',.25)) == 2.5
    assert float(beam.value('EIcn',.25)) == 0.
    with pytest.raises(AswError):
        parse_asw((base/'[0_3_90]_S/[03_90]_S.asw').read_text())
