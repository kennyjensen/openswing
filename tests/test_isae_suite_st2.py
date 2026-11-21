"""Bounded ST2 source registration checks; no physical model construction."""
from copy import deepcopy
import builtins
import json
from pathlib import Path
import sys

import pytest

from scripts import isae_suite_st2 as st2


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    before = {name for name in sys.modules if name == 'openswing' or name.startswith('openswing.')}
    result = st2.build_jobs(ROOT)
    assert {name for name in sys.modules if name == 'openswing' or name.startswith('openswing.')} == before
    return result


def select(jobs, kind):
    return next(job for job in jobs if job['target_kind'] == kind)


def test_all_native_exports_summary_cells_and_six_models_remain_distinct(jobs):
    native = [j for j in jobs if j['target_kind'].startswith('native_')]
    books = [j for j in jobs if j['target_kind'] == 'workbook_summary']
    models = [j for j in jobs if j['target_kind'] == 'model_inventory']
    assert len(jobs) == len({j['id'] for j in jobs}) == 17
    assert len(native) == 9 and sum(len(j['reference_rows']) for j in native) == 102
    assert len({(j['table_path'],r['line_number']) for j in native for r in j['reference_rows']}) == 60
    assert sum(j['expected_outputs'] for j in native) == 480
    assert len({(j['table_path'],o['name']) for j in native for o in j['observations']}) == 396
    assert len(books) == 2 and sum(j['expected_outputs'] for j in books) == 10
    assert len(models) == len({j['model_path'] for j in models}) == 6
    assert all(j['expected_outputs'] == 0 and j['observations'] == [] for j in models)
    assert sum(j['expected_outputs'] for j in jobs) == 490
    workers=[j for j in jobs if j['execution_route']=='worker']
    assert len(workers)==8 and sum(j['expected_outputs'] for j in workers)==112
    assert all(j['settings'] is None and not j['grid_counts'] for j in jobs if j['execution_route']=='unsupported')
    assert all(not j['complete_family_reproduction'] and not j['literal_input_modified'] for j in jobs)
    assert all(not Path(j['model_path']).is_absolute() for j in jobs if j['model_path'])


def test_native_modal_keeps_real_residues_seventh_root_and_modulus_frequency(jobs):
    modal = select(jobs, 'native_modal')
    row = modal['reference_rows'][0]
    assert row['tokens'] == ['1', '0.62197956E-13', '28.892273']
    assert row['real']['exact_decimal_tolerance'] == '5E-22'
    assert row['imaginary']['exact_decimal_tolerance'] == '5E-7'
    assert row['frequency_modulus_Hz'] == pytest.approx(4.598348065110504)
    assert len(modal['reference_rows']) == 7 and len(st2.reference_contract(modal)) == 14
    assert modal['observations'][-1]['name'] == 'row0007:imaginary'
    assert modal['observations'][-1]['expected_token'] == '996.33366'
    assert modal['observations'][0]['expected'] != 0
    assert all(x['units'] == '1/s' for x in modal['observations'])


def test_all_static_rows_columns_and_resultant_scaling_are_preserved(jobs):
    static = select(jobs, 'native_static')
    profile = static['target_profile']
    assert len(profile['rows']) == 46
    assert [r['line_number'] for r in profile['rows'][:2]] == [33, 34]
    assert [r['tokens'][0] for r in profile['rows'][:2]] == ['0.100E-03', '0.118E-02']
    assert len(static['observations']) == 46*8
    assert all(len(r['tokens']) == 9 for r in profile['rows'])
    checks = st2.reference_contract(static)
    assert checks["row0000:Mc'/10"]['expected_token'] == '-0.140E+01'
    assert checks["row0000:Mc'/10"]['expected'] == -14.0
    assert checks["row0000:Mc'/10"]['tolerance'] == .05
    assert checks["row0000:Ms'/10"]['expected'] == 1.24
    assert checks["row0000:Ms'/10"]['power10'] == 0
    assert checks['row0000:Fn/10']['expected'] == -31.5
    assert checks['row0045:tw-tw0']['expected'] == 5.11
    assert checks['row0045:a_flap']['units'] == 'unresolved display units'
    assert len(static['driver_paths']) == 2 and 'unique generating model byte state' in static['unknown_setup']


def test_workbook_cells_keep_original_storage_and_conflicting_labels(jobs):
    books = [j for j in jobs if j['target_kind'] == 'workbook_summary']
    assert [[r['value_cell'] for r in j['observations']] for j in books] == [
        ['I11', 'I12', 'I13', 'I14', 'I15'], ['G3', 'G4', 'G5', 'G6', 'G7']]
    assert [[r['expected'] for r in j['observations']] for j in books] == [
        [4.59, 29.1, 43.4, 128., 81.4], [4.67, 29.2, 43.2, 116., 81.4]]
    for job in books:
        assert job['model_path'] is None and job['blocker_code'] == 'SUMMARY_PAIRING_UNRESOLVED'
        assert job['observations'][3]['B_mode_label'] == 'IP1'
        assert job['observations'][3]['D_adjacent_label'] == 'OOP3'
        assert all(row['precision_scope'] == st2.CELL_PRECISION for row in job['observations'])


def test_literal_model_inventory_does_not_clamp_or_delete_zero_objects(jobs):
    models = [j for j in jobs if j['target_kind'] == 'model_inventory']
    assert sum(j['model_record']['all_zero_point_objects'] for j in models) == 2
    for job in models:
        model = job['model_record']
        assert len(model['weights']) == 2 and model['beam_parameter_domain'] == [.0001, .55]
        assert all(w['tokens'][1] == '0.558' and w['scaled_values'][1] == .558 for w in model['weights'])
        assert model['construction_attempted'] is False
        assert model['source'] in job['source_pins']
        assert job['expected_operations'] == st2.BLOCKED_OPERATIONS
        assert job['blocker_code'] == ('MODAL_SCOPE_REGISTERED_SEPARATELY' if model['all_zero_point_objects'] else 'LITERAL_ATTACHMENT_OUTSIDE_DOMAIN')


def test_blocked_validation_retains_every_slot_without_replanning_or_production_import(jobs, monkeypatch):
    original_import = builtins.__import__
    def no_physics(name, *args, **kwargs):
        if name.split('.')[0] in ('openswing', 'numpy', 'scipy'):
            pytest.fail('Blocked registration imported a production/numerical package: '+name)
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', no_physics)
    monkeypatch.setattr(st2, 'plan', lambda *a: pytest.fail('Blocked record rebuilt whole plan'))
    monkeypatch.setattr(st2, 'build_jobs', lambda *a: pytest.fail('Blocked record rebuilt whole family'))
    for job in (j for j in jobs if j['execution_route']=='unsupported'):
        result = st2.run(ROOT, job)
        assert result['status'] == 'unsupported' and result['source_pins_unchanged']
        assert result['physical_calls'] == result['production_imports'] == result['equilibrium_solves'] == result['modal_solves'] == 0
        assert not result['numerical_pass'] and not result['reference_match']
        assert len(result['reference_checks']) == job['expected_outputs']
        contract = st2.reference_contract(job)
        assert all(row['predicted'] is None and row['passed'] is False and row['comparison'] == '<='
                   and all(row[key] == value for key, value in contract[row['name']].items())
                   for row in result['reference_checks'])


@pytest.mark.parametrize('mutation', ['expected', 'tolerance', 'token', 'coordinate', 'missing_row', 'count', 'route', 'settings'])
def test_static_scope_and_execution_tampering_is_rejected(jobs, mutation):
    job = deepcopy(select(jobs, 'native_static'))
    if mutation == 'expected': job['observations'][0]['expected'] = 1.
    if mutation == 'tolerance': job['observations'][0]['tolerance'] *= 10
    if mutation == 'token': job['reference_rows'][0]['tokens'][1] = '0.0'
    if mutation == 'coordinate': job['observations'][0]['coordinate_token'] = '0.0'
    if mutation == 'missing_row': job['reference_rows'].pop(0)
    if mutation == 'count': job['expected_outputs'] -= 1
    if mutation == 'route': job['execution_route'] = 'local_static'
    if mutation == 'settings': job['settings'] = {'gravity_magnitude': 9.81}
    with pytest.raises(ValueError, match='ST2'):
        st2.run(ROOT, job)


@pytest.mark.parametrize('kind', ['native_modal', 'native_static', 'workbook_summary', 'model_inventory'])
def test_canonical_rebuild_rejects_model_source_location_and_pairing_changes(jobs, kind):
    job = deepcopy(select(jobs, kind))
    if kind == 'workbook_summary':
        job['observations'][0].update(st2._number('9.99'))
    elif kind == 'native_static':
        job['driver_paths'] = job['driver_paths'][:1]
    elif kind == 'native_modal':
        job['reference_rows'][0]['line_number'] += 1
        job['observations'][0]['source_line'] += 1
        job['observations'][1]['source_line'] += 1
    else:
        job['model_record']['weights'][0]['tokens'][1] = '0.55'
    with pytest.raises(ValueError, match='original sources'):
        st2.run(ROOT, job)


def test_changed_and_removed_source_pins_report_mismatch_without_reference_match(jobs):
    for missing in (False, True):
        job = deepcopy(select(jobs, 'native_static'))
        if missing:
            job['source_pins'].pop()
        else:
            job['source_pins'][0]['sha256'] = '0'*64
        result = st2.run(ROOT, job)
        assert result['status'] == 'source_mismatch' and not result['source_pins_unchanged']
        assert not result['reference_match'] and result['physical_calls'] == 0
        assert len(result['reference_checks']) == 368


def test_plan_source_contract_pins_exact_models_drivers_and_archive_evidence(jobs):
    manifest = json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    cache = (ROOT/'.reference/isae-validation'/st2.REVISION).resolve()
    static = select(jobs, 'native_static')
    paths = {item['path'] for item in static['source_pins']}
    # The legacy spelling is a compatibility symlink to visible reference/.
    # Pins use canonical paths, so compare the same physical files here.
    assert all(str((ROOT/name).resolve()) in paths for name in static['driver_paths'])
    assert str(ROOT/st2.READINESS) in paths
    checked = set()
    for job in jobs:
        for pin in job['source_pins']:
            path = Path(pin['path'])
            if path.is_relative_to(cache):
                original = manifest['files'][path.relative_to(cache).as_posix()]
                assert all(pin[k] == original[k] for k in ('bytes', 'sha256'))
                checked.add(path)
    assert {(cache/st2.FAMILY/name) for name in (*st2.MODEL_NAMES, *st2.STATIC_DRIVERS)} <= checked


def test_modal_decoder_rejects_missing_root_and_wrong_frequency_header(jobs):
    job = select(jobs, 'native_modal')
    text = (ROOT/job['table_path']).read_text()
    with pytest.raises(ValueError, match='seven'):
        st2.decode_modal('\n'.join(text.splitlines()[:-2]))
    with pytest.raises(ValueError, match='header'):
        st2.decode_modal(text.replace('moduli', 'imaginary parts'))


def test_every_modal_component_is_bound_to_literal_token_position(jobs):
    for job in (j for j in jobs if j['target_kind']=='native_modal'):
        lines=(ROOT/job['table_path']).read_text().splitlines()
        for target in job['observations']:
            raw=lines[target['source_line']-1]
            token=target['expected_token'];start=target['source_character_1based']-1
            assert target['raw_line']==raw
            assert target['raw_tokens']==raw.split()
            assert raw[start:start+len(token)]==token
            assert raw.split()[target['source_column_1based']-1]==token


def test_modal_request_is_exact_source_and_prospective_policy(jobs):
    for job in (j for j in jobs if j['execution_route']=='worker'):
        assert job['request']['source'].encode()==(ROOT/job['model_path']).read_bytes()
        assert job['request']['condition'] is None and job['request']['loads']==[]
        assert job['request']['gravity']==[0.,0.,-9.81]
        assert job['expected_real_mass']==.373285
        assert job['suggested_cap_seconds']==180
        assert job['expected_operations']==st2.MODAL_OPERATIONS
        assert job['request']['modes']['matrices'] is True
        assert all(job['request']['modes'][key]==value for key,value in st2.MODAL_PROTOCOL.items()
                   if key in ('count','shift','method','step','rank_tolerance'))
        paths={pin['path'] for pin in job['source_pins']}
        assert all(str(ROOT/name) in paths for name in
                   (st2.MODAL_READINESS,st2.MODAL_PREFLIGHT,st2.PROSPECTIVE_PROTOCOL,
                    'scripts/isae_suite_st2_modal.py'))


@pytest.mark.parametrize('mutation', ['count','shift','method','step','rank_tolerance','gravity',
    'density','gate','retry','nodes','source','root_selection','global_claim','historical_claim'])
def test_modal_protocol_is_fixed_before_worker_import(jobs,mutation):
    job=deepcopy(select(jobs,'native_modal'))
    if mutation in ('count','shift','method','step','rank_tolerance'):
        job['request']['modes'][mutation]={'count':24,'shift':[0.,0.],'method':'dense',
            'step':1e-6,'rank_tolerance':1e-6}[mutation]
    elif mutation=='gravity':job['gravity']=[0.,0.,0.]
    elif mutation=='density':job['density']=1.2256
    elif mutation=='gate':job['numerical_gates']['pencil']*=10
    elif mutation=='retry':job['expected_operations']['retries']=1
    elif mutation=='nodes':job['expected_nodes']-=1
    elif mutation=='source':job['request']['source']=job['request']['source'].replace('.558','.55')
    elif mutation=='root_selection':job['modal_protocol']['selected_positive_roots']=5
    elif mutation=='global_claim':job['complete_finite_spectrum']=True
    else:job['historical_settings_recovered']=True
    with pytest.raises(ValueError,match='ST2'):
        st2.validate_record_contract(job)


@pytest.mark.parametrize('status',['error','timeout','cancelled','source_mismatch','numerical_failure'])
def test_modal_failure_can_retain_empty_or_partial_checks_without_success(jobs,status):
    job=select(jobs,'native_modal')
    for checks in ([],st2._reference_checks(job)[:3]):
        result=dict(status=status,reference_checks=checks,numerical_pass=False,reference_match=False)
        assert st2.validate_result_contract(job,result)
        result['numerical_passed']=True
        with pytest.raises(ValueError,match='success'):
            st2.validate_result_contract(job,result)


def test_modal_worker_cannot_be_downgraded_to_zero_call_blocker(jobs):
    with pytest.raises(ValueError,match='executable modal'):
        st2.validate_blocked(ROOT,select(jobs,'native_modal'))


def test_modal_mesh_groups_keep_both_media_and_no_selection_gate(jobs):
    diagnostics=st2.mesh_diagnostics(jobs,{})
    assert len(diagnostics)==4 and {row['medium'] for row in diagnostics}=={'vacuum','still_air'}
    assert all(len(row['jobs'])==2 and row['status']=='UNAVAILABLE' and row['passed'] is None and
               row['acceptance_gate'] is None for row in diagnostics)
