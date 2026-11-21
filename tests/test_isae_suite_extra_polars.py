"""Source declarations and adapter scope; no solver or physical imports."""
from pathlib import Path
import copy
import shutil
import subprocess
import sys

import pytest

from scripts import isae_suite_extra_polars as extra

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional pinned original archive unavailable')
    before = {name for name in sys.modules if name.startswith('openswing')}
    result = extra.plan(ROOT)
    assert {name for name in sys.modules if name.startswith('openswing')} == before
    return result


def test_all_rows_duplicates_and_blocked_variants_retained(jobs):
    assert len(jobs) == 710
    executable = [j for j in jobs if j['execution_route'] != 'unsupported']
    assert len(executable) == 630
    assert {j['case_id'] for j in executable} == {'SA-10', 'SA-14'}
    assert not any(j['case_id'] == 'SA-12' for j in jobs)
    assert sum(j['case_id'] == 'SA-15' for j in jobs) == 26
    broken = [j for j in jobs if 'TS_60_45_30.asw' in j['model_path']]
    assert len(broken) == 54 and all(j['execution_route'] == 'unsupported' for j in broken)
    duplicate = [j for j in executable if j['case_id'] == 'SA-10'
                 and j['table_path'].endswith('/wing_alone.txt')
                 and j['settings']['mesh_level'] == 0 and j['settings']['alpha'] == 12]
    assert len(duplicate) == 2 and duplicate[0]['id'] != duplicate[1]['id']
    assert len({j['id'] for j in jobs}) == len(jobs)
    assert all(j['complete_family_reproduction'] is False for j in jobs)


def test_source_incidence_and_sa15_settings_remain_explicit(jobs):
    one = next(j for j in jobs if j['case_id'] == 'SA-15')
    assert one['exact_driver_alpha_token'] == '-7.5990557718658005'
    assert one['settings']['speed'] == 380
    assert any(s['path'].endswith('/JW-1_FW_Only_Body.set') for s in one['sources'])
    assert 'undecoded' in one['unsupported_reason']


def test_sa14_uses_documented_fast_default_and_the_explicit_mach_toggle(jobs):
    selected = [j for j in jobs if j['case_id'] == 'SA-14']
    assert len(selected) == 360
    assert len({j['driver_path'] for j in selected}) == 3
    assert sum(j['reference_row']['fields']['conv']['value'] == 0 for j in selected) == 128
    for job in selected:
        assert job['settings']['freeze_influences'] is True
        assert job['settings']['mach'] is None
        assert job['settings']['speed'] == 70.
        assert job['settings']['stall_factor'] == 40.
        assert job['settings']['stall_width'] == .05
        assert not any(s['path'].endswith('.set') for s in job['sources'])
        assert 'historical startup settings remain unverified' in job['qualifications'][-1]
        assert extra.polar.RECONSTRUCTED_INFLUENCE_QUALIFICATION not in job['qualifications']
    # The SA14 correction must not change other families' explicit settings.
    assert all(j['settings']['freeze_influences'] is False and j['settings']['mach'] == 0.
               for j in jobs if j['case_id'] in ('SA-10', 'SA-15'))
    assert all(extra.polar.RECONSTRUCTED_INFLUENCE_QUALIFICATION in j['qualifications']
               for j in jobs if j['case_id'] in ('SA-10', 'SA-15'))


@pytest.mark.parametrize('change', ['freeze', 'no_mach', 'later_mach', 'wrong_menu', 'missing_exit'])
def test_sa14_rejects_unreviewed_menu_paths(jobs, change):
    job = next(j for j in jobs if j['case_id'] == 'SA-14' and '/W_only_' in j['driver_path'])
    text = (ROOT/job['driver_path']).read_text()
    if change == 'freeze': text = text.replace('k\nm\n', 'k\nf\nm\n', 1)
    elif change == 'no_mach': text = text.replace('k\nm\n', 'k\n', 1)
    elif change == 'later_mach': text = text.replace('!A 5.0', 'k\nm\n\n!A 5.0', 1)
    elif change == 'wrong_menu': text = text.replace('k\nm\n', 'm\n', 1)
    elif change == 'missing_exit': text = text.replace('k\nm\n\n', 'k\nm\n', 1)
    with pytest.raises(ValueError, match='Unreviewed SA14'):
        extra.sa14_startup_settings(text)


def test_node_requests_and_interval_reconstructions_are_separate(jobs):
    for job in jobs:
        declaration, settings = job['driver_declarations'], job['settings']
        assert 'declared_panels' not in declaration and 'panel_token' not in declaration
        count = declaration['requested_nodes']
        assert (declaration['node_count_token'] is None) is (count is None)
        if count is not None:
            assert extra.polar._number(declaration['node_count_token']) == count
        assert settings['base_panels'] == (count or 64)
        assert settings['panels'] == (count or 64) * 2 ** settings['mesh_level']
        assert 'interval-count reconstruction' in settings['mesh_source']
        assert 'historical node array and circulation K unknown' in settings['mesh_source']
        assert extra.polar.NODE_I_QUALIFICATION in job['qualifications']


@pytest.mark.parametrize('case', ['SA-15'])
def test_unsupported_never_calls_generic_solver(jobs, monkeypatch, case):
    def forbidden(*args):
        pytest.fail('Unsupported route attempted a physical call')
    monkeypatch.setattr(extra.polar, 'run', forbidden)
    job = next(j for j in jobs if j['case_id'] == case)
    result = extra.run(ROOT, job)
    assert result['status'] == 'unsupported' and result['physical_calls'] == 0
    assert len(result['reference_checks']) == job['expected_outputs']
    assert not result['reference_match']


def test_cl_subset_uses_null_unused_targets_and_keeps_numerical_gates(jobs, monkeypatch):
    job = next(j for j in jobs if j['case_id'] == 'SA-14')
    def fake_run(root, internal):
        for key in extra.polar.OUTPUTS:
            if key != 'CL':
                ref = internal['reference_row']['fields'][key]
                assert ref['value'] is ref['token'] is ref['tolerance'] is None
        return dict(status='computed', numerical_pass=True, physical_calls=1,
                    numerical_checks=[{'name': 'real helper checks retained', 'passed': True}],
                    reference_checks=[{'name': name, 'passed': name == 'CL',
                                       **({} if name == 'CL' else {'unavailable_reason': 'no target'})}
                                      for name in extra.polar.OUTPUTS])
    monkeypatch.setattr(extra.polar, 'run', fake_run)
    result = extra.run(ROOT, job)
    assert result['reference_match'] is True
    assert result['required_outputs'] == ['CL']
    assert result['reference_checks'] == [{'name': 'CL', 'passed': True}]
    assert result['numerical_checks'][0]['passed'] is True
    assert len(result['excluded_generic_reference_fields']) == 6
    assert job['reference_row']['fields'].keys() == {'index', 'time', 'conv', 'stall', 'alpha', 'CL'}


def test_added_ground_setting_cannot_be_silently_ignored(jobs, monkeypatch):
    job = copy.deepcopy(next(j for j in jobs if j['execution_route'] == 'seven_fields'))
    job['settings']['ground'] = 1
    monkeypatch.setattr(extra.polar, 'run', lambda *args: pytest.fail('Ignored physical setting'))
    result = extra.run(ROOT, job)
    assert result['status'] == 'unsupported' and result['physical_calls'] == 0


def test_inline_blocked_validation_never_replans_and_rejects_changed_reason(jobs, monkeypatch):
    job = copy.deepcopy(next(j for j in jobs if j['case_id'] == 'SA-15'))
    monkeypatch.setattr(extra, 'plan', lambda *args: pytest.fail('Replanned entire suite'))
    result = extra.validate_blocked(ROOT, job)
    assert result['physical_calls'] == 0 and result['blocker_code'] == 'FORCE_AXES_AND_SETTINGS_UNRESOLVED'
    assert len(result['reference_checks']) == 7
    job['unsupported_reason'] = 'changed reason'
    with pytest.raises(ValueError, match='reason'):
        extra.validate_blocked(ROOT, job)


def test_wrong_width_and_wrong_declared_output_rejected():
    text = '# model\n# Operating point sequence...\n# i t conv stall alpha CL\n1 1 1 0 0 .1 .2\n'
    with pytest.raises(ValueError, match='expected 6'):
        extra.decode_table(text, 14)
    driver = '#!/bin/sh\naswing model <<EOF\noper\n!V 10\n!A 0\nw\nwrong.txt\nEOF\n'
    with pytest.raises(ValueError, match='explicitly write'):
        extra.decode_driver(driver, 'expected.txt')


@pytest.fixture(scope='module')
def historical_jobs():
    if not (ROOT/extra.SOURCE_PAIRING_AUDIT).is_file():
        pytest.skip('Optional authenticated historical source evidence unavailable')
    return extra.plan_source_pairing(ROOT, extra.SOURCE_PAIRING_ID)


def test_historical_pairing_is_opt_in_and_preserves_every_default_job(jobs, historical_jobs):
    combined = extra.plan(ROOT, source_pairings=(extra.SOURCE_PAIRING_ID,))
    assert combined[:710] == jobs
    assert combined[710:] == historical_jobs
    assert len(combined) == 768 and len({job['id'] for job in combined}) == 768
    assert not any(job['case_id'] == 'SA-7' for job in jobs)
    literal = extra.polar.plan(ROOT)
    assert len(literal) == 372
    assert len([j for j in literal if j['case_id'] == 'SA-7']) == 116
    assert not ({j['id'] for j in literal} & {j['id'] for j in historical_jobs})


def test_historical_pairing_retains_all_original_rows_signs_and_precision(historical_jobs):
    literal = {job['id']: job for job in extra.polar.plan(ROOT)}
    assert len(historical_jobs) == 58
    assert sum(job['expected_outputs'] for job in historical_jobs) == 406
    assert {j['row_index'] for j in historical_jobs} == set(range(29))
    for job in historical_jobs:
        pairing = job['source_pairing']
        original = literal[pairing['original_job_id']]
        for key in ('reference_row', 'settings', 'table_path', 'driver_path', 'driver_declarations'):
            assert job[key] == original[key]
        assert pairing['current_model_path'] == original['model_path']
        assert job['model_path'] != original['model_path']
        assert pairing['historical_model_path'] == job['model_path']
        assert job['required_outputs'] == list(extra.polar.OUTPUTS)
        assert job['settings']['panels'] in (64, 128)
        assert job['settings']['speed'] == 69.15
        assert job['complete_family_reproduction'] is False
        assert pairing['producer_execution_authenticated'] is False
        assert pairing['existing_native_targets_reused'] is True
        assert pairing['unchanged_driver_and_table'] is True
        assert job['exact_driver_alpha_token'] == job['driver_declarations']['alpha_tokens'][job['row_index']]
        assert all((ROOT/source['path']).is_file() for source in job['sources'])
        assert all(not Path(source['path']).is_absolute() for source in job['sources'])
    coarse = [j for j in historical_jobs if j['settings']['panels'] == 64]
    assert sum(j['reference_row']['fields']['drag']['value'] < 0 for j in coarse) == 21
    assert sum(j['reference_row']['fields']['CD']['value'] < 0 for j in coarse) == 21
    assert coarse[6]['reference_row']['fields']['alpha']['token'] == '-0.00000'
    assert coarse[8]['reference_row']['fields']['drag'] == dict(
        token='-8.56776', value=-8.56776, tolerance=5e-6)


@pytest.mark.parametrize('selection', [None, extra.SOURCE_PAIRING_ID, ('unknown',),
                                       (extra.SOURCE_PAIRING_ID, extra.SOURCE_PAIRING_ID)])
def test_historical_selection_rejects_ambiguous_or_unreviewed_overrides(selection):
    with pytest.raises(ValueError, match='source pairing'):
        extra.plan(ROOT, source_pairings=selection)
    with pytest.raises(ValueError, match='Unknown source pairing'):
        extra.plan_source_pairing(ROOT, 'arbitrary-model-path')


def test_historical_plan_and_validation_are_stdlib_only(historical_jobs):
    program = '''import pathlib, sys
from scripts import isae_suite_extra_polars as e
r=pathlib.Path(sys.argv[1]); jobs=e.plan_source_pairing(r)
assert len(jobs)==58 and e.validate_source_pairing(r,jobs[0]) is True
assert not any(n=='openswing' or n.startswith('openswing.') or n in ('numpy','scipy') for n in sys.modules)
print('58 source-only jobs; no production imports')
'''
    completed = subprocess.run([sys.executable, '-B', '-c', program, str(ROOT)],
                               cwd=ROOT, capture_output=True, text=True, check=True, timeout=20)
    assert completed.stdout.strip() == '58 source-only jobs; no production imports'


@pytest.mark.parametrize('change', [
    'model', 'mesh', 'alpha', 'mach', 'tolerance', 'negative_sign', 'omit_output',
    'source_pin', 'historical_revision', 'authenticated_claim', 'new_target_claim',
    'route', 'target_kind', 'id', 'driver_alpha', 'qualifications',
])
def test_historical_contract_tampering_is_rejected_before_worker(historical_jobs, monkeypatch, change):
    job = copy.deepcopy(historical_jobs[16])  # The first negative-drag original row.
    if change == 'model':
        job['model_path'] = job['source_pairing']['current_model_path']
    elif change == 'mesh':
        job['settings']['panels'] += 1
    elif change in ('alpha', 'mach'):
        job['settings'][change] += 1
    elif change == 'tolerance':
        job['reference_row']['fields']['drag']['tolerance'] *= 10
    elif change == 'negative_sign':
        ref = job['reference_row']['fields']['drag']
        ref.update(value=abs(ref['value']), token=ref['token'].lstrip('-'))
    elif change == 'omit_output':
        job['required_outputs'].remove('drag')
        job['expected_outputs'] = 6
    elif change == 'source_pin':
        job['sources'][0]['sha256'] = '0' * 64
    elif change == 'historical_revision':
        job['source_pairing']['revision'] = extra.REVISION
    elif change == 'authenticated_claim':
        job['source_pairing']['producer_execution_authenticated'] = True
    elif change == 'new_target_claim':
        job['source_pairing']['existing_native_targets_reused'] = False
    elif change == 'route':
        job['execution_route'] = 'seven_fields'
    elif change == 'target_kind':
        job['target_kind'] = 'original_polar'
    elif change == 'id':
        job['id'] = job['source_pairing']['original_job_id']
    elif change == 'driver_alpha':
        job['exact_driver_alpha_token'] = '0'
    elif change == 'qualifications':
        job['qualifications'].pop()
    monkeypatch.setattr(extra.polar, 'run', lambda *args: pytest.fail('Tampered source pairing called worker'))
    with pytest.raises(ValueError, match='canonical contract'):
        extra.run(ROOT, job)


@pytest.mark.parametrize('suffix', [
    'history.json', 'earliest-Tandem_GAW2_L163_G05_Fore_Only.asw',
    'earliest-Tandem_GAW2_L163_G05_Fore_Only.sh',
    'earliest-Tandem_GAW2_L163_G05_Fore_Only.txt',
    'Tandem_GAW2_L163_G05_Fore_Only.asw.earliest.blob.json',
    'Tandem_GAW2_L163_G05_Fore_Only.asw',
    'Tandem_GAW2_L163_G05_Fore_Only.sh',
    'Tandem_GAW2_L163_G05_Fore_Only.txt',
    'tree-f745fb40b308d85a2a99e039665457177686a9bd.json',
    'manifest.json',
])
def test_historical_evidence_byte_tampering_is_rejected(tmp_path, historical_jobs, suffix):
    # Copy only the pinned evidence for this pairing, never the production tree.
    for pin in historical_jobs[0]['sources']:
        target = tmp_path/pin['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/pin['path'], target)
    targets = [tmp_path/pin['path'] for pin in historical_jobs[0]['sources']
               if Path(pin['path']).name == suffix]
    assert len(targets) == 1
    targets[0].write_bytes(targets[0].read_bytes() + b' ')
    with pytest.raises(ValueError, match='changed'):
        extra.plan_source_pairing(tmp_path)


@pytest.mark.parametrize('status', ['computed', 'numerical_failure', 'error', 'source_mismatch'])
def test_historical_worker_reuses_generic_route_and_preserves_provenance(
        historical_jobs, monkeypatch, status):
    job = historical_jobs[0]
    calls = []
    def fake_run(root, internal):
        calls.append(copy.deepcopy(internal))
        assert root == ROOT
        assert internal['settings'] == job['settings']
        assert internal['reference_row'] == job['reference_row']
        assert internal['model_path'] == job['model_path']
        checks = extra.polar.reference_checks(
            {name: job['reference_row']['fields'][name]['value'] for name in extra.polar.OUTPUTS},
            job['reference_row'])
        return dict(status=status, numerical_pass=status == 'computed', physical_calls=1,
                    numerical_checks=[dict(name='existing worker gate', passed=status == 'computed')],
                    reference_checks=checks)
    monkeypatch.setattr(extra.polar, 'run', fake_run)
    report = extra.run(ROOT, job)
    assert len(calls) == 1
    assert report['reference_match'] is (status == 'computed')
    assert report['source_pairing'] == job['source_pairing']
    assert report['source_pairing'] is not job['source_pairing']
    assert report['comparison_scope'] == 'supplemental_historical_source_pairing'
    assert report['target_kind'] == 'historical_source_polar'
    assert report['complete_family_reproduction'] is False
    assert len(report['reference_checks']) == 7
    assert report['excluded_generic_reference_fields'] == []
