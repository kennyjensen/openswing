"""Literal catalog/worker packet tests only: no production imports or solves."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('suite_aeroelastic', ROOT/'scripts/isae_suite_aeroelastic.py')
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


def test_historical_alias_verifies_bytes_and_returns_canonical_pin(tmp_path):
    reference = tmp_path/'reference'
    reference.mkdir()
    source = reference/'model.asw'
    source.write_text('original model\n')
    alias = tmp_path/'.reference'
    alias.symlink_to(reference, target_is_directory=True)
    original = ADAPTER._pin(source)
    historical = dict(original, path=str(alias/source.name))
    assert ADAPTER._verified(historical) == original
    assert historical['path'] == str(alias/source.name)
    source.write_text('modified model\n')
    with pytest.raises(ValueError, match='Original source changed'):
        ADAPTER._verified(historical)


@pytest.fixture(scope='module')
def jobs():
    before = set(sys.modules)
    result = ADAPTER.plan(ROOT)
    assert not any(name.startswith('openswing') for name in set(sys.modules)-before)
    return result


def test_complete_rows_masks_and_literal_decimal_precision(jobs):
    assert len(jobs) == 566
    assert sum(j['expected_outputs'] for j in jobs) == 2264
    executable = [j for j in jobs if j['execution_route'] == 'worker']
    assert len(executable) == 542
    assert sum(j['expected_operations']['cold_solves'] for j in jobs) == 542
    assert sum(j['expected_operations']['fresh_residuals'] for j in jobs) == 542
    ae = [j for j in jobs if j['case_id'] == 'AE-2']
    ff = [j for j in jobs if j['case_id'] == 'FFWT-1']
    assert len(ae) == 550 and len(ff) == 16
    assert len({j['coordinate_id'] for j in ae}) == 275
    assert len({j['coordinate_id'] for j in ff}) == 8
    assert sum(o['missing'] for j in jobs for o in j['observations']) == 96
    for job in jobs:
        assert len(job['observations']) == 4
        row = job['reference_row']
        raw = Path(job['source_output']['path']).read_text().splitlines()
        for observation in job['observations']:
            token = raw[observation['source_line']-1].split()[observation['source_column_1based']-1]
            assert token == observation['token']
            if observation['missing']:
                assert token == 'NaN'
                assert observation['expected'] is observation['tolerance'] is None
            else:
                number = Decimal(token)
                assert observation['expected'] == float(number)
                assert observation['tolerance'] == float(Decimal(10)**number.as_tuple().exponent/2)
        assert job['condition']['speed'] == row['commanded_IAS_m_s']
        assert job['historical_settings_recovered'] is False
    json.dumps(jobs, allow_nan=False)


@pytest.mark.parametrize('family', ['AE-2', 'FFWT-1'])
def test_prepared_packet_reuses_unchanged_worker_contract(family, jobs, tmp_path):
    job = next(j for j in reversed(jobs) if j['case_id'] == family and j['execution_route'] == 'worker')
    before = set(sys.modules)
    plan = ADAPTER._prepare_worker(ROOT, job, tmp_path)
    helper = ADAPTER._load(job['helper'])
    assert helper.unchanged(plan)
    assert callable(helper.worker)
    assert not any(name.startswith('openswing') for name in set(sys.modules)-before)
    assert plan['cold_solves'] == plan['fresh_residuals'] == 1
    request = json.loads((tmp_path/'cases'/job['mesh']/'request.json').read_text())
    assert request['source'].encode() == Path(job['source']).read_bytes()
    assert request['condition'] == job['condition']
    assert request['panels'] == job['panels']
    assert request['numerics'] == ADAPTER.POLICY
    assert request['mode'] == 'mounted' and request['operating_constraints'] == []
    assert not request.get('initial_state')
    if family == 'AE-2':
        assert plan['archive']['raw_row'] == job['reference_row']
        assert plan['cases'][0]['expected_elements'] == 161
        assert plan['gates']['residual'] == 1e-8
        assert plan['gates']['mesh_relative'] == .01
        auth = json.loads((tmp_path/'authorization.json').read_text())
        assert auth['plan_sha256'] == ADAPTER._pin(tmp_path/'plan.json')['sha256']
    else:
        assert plan['reference']['selected_reference']['row'] == 8
        assert plan['reference']['condition']['speed'] == 32.97084548104957
        assert plan['gates']['residual'] == 1e-8 and plan['gates']['mesh'] == .001
        assert plan['reference']['reference_values'] == {o['name']:o['expected'] for o in job['observations']}
        assert plan['reference']['half_units'] == {o['name']:o['tolerance'] for o in job['observations']}


def test_all_missing_slots_fail_without_loading_worker(jobs, monkeypatch):
    def forbidden(*args):
        raise AssertionError('No physical worker may load for NaN targets.')
    monkeypatch.setattr(ADAPTER, '_load', forbidden)
    blocked = [j for j in jobs if j['execution_route'] == 'unsupported']
    assert len(blocked) == 24
    for job in blocked:
        result = ADAPTER.validate_blocked(ROOT, job)
        assert result['status'] == 'unsupported' and result['reference_match'] is False
        assert result['operations'] == dict(cold_solves=0, fresh_residuals=0)
        assert len(result['reference_checks']) == 4
        assert all(c['predicted'] is c['expected'] is None and c['passed'] is False for c in result['reference_checks'])


def test_declared_input_tampering_is_rejected_before_worker(jobs):
    changed = deepcopy(next(j for j in jobs if j['case_id'] == 'FFWT-1'))
    changed['condition']['speed'] += 1
    with pytest.raises(ValueError, match='condition'):
        ADAPTER.run(ROOT, changed)


def test_error_retains_every_reference_slot_and_failure(jobs, tmp_path, monkeypatch):
    job = next(j for j in jobs if j['execution_route'] == 'worker')
    def fail(stage, name):
        raise RuntimeError('deliberate test-only worker failure before any physical call')
    monkeypatch.setattr(ADAPTER, '_load', lambda _:SimpleNamespace(ROOT=ROOT, worker=fail))
    monkeypatch.setattr(ADAPTER.tempfile, 'mkdtemp', lambda **_:str(tmp_path))
    result = ADAPTER.run(ROOT, job)
    assert result['status'] == 'numerical_failure'
    assert len(result['reference_checks']) == 4
    assert all(c['predicted'] is None and c['passed'] is False for c in result['reference_checks'])
    assert result['error']['type'] == 'RuntimeError'
    assert not any(result['operation_evidence'].values())
    assert (tmp_path/'adapter-result.json').exists()


def test_precision_reduction_ignores_claimed_worker_pass_and_preserves_signs(jobs):
    job = next(j for j in jobs if j['case_id'] == 'FFWT-1')
    values = {o['name']:o['expected'] for o in job['observations']}
    assert all(c['passed'] for c in ADAPTER._checks(job, values))
    first = job['observations'][0]
    values[first['name']] += 2*first['tolerance']
    checks = ADAPTER._checks(job, values)
    assert checks[0]['passed'] is False and all(c['passed'] for c in checks[1:])
    assert checks[1]['expected'] < 0 and checks[2]['expected'] < 0
    values[first['name']] = float('nan')
    assert ADAPTER._checks(job, values)[0]['predicted'] is None


def test_mesh_gates_are_original_separate_and_do_not_use_reference_closeness(jobs):
    pair = [j for j in jobs if j['mesh_group'] == 'FFWT-1:row01']
    packets = {j['id']:dict(status='computed', reference_match=False,
        reference_checks=[dict(name=o['name'], predicted=10.) for o in j['observations']]) for j in pair}
    report = ADAPTER.mesh_diagnostics(pair, packets)[0]
    assert report['passed'] is True and report['gate']['relative_limit'] == .001
    packets[pair[1]['id']]['reference_checks'][0]['predicted'] = 0.
    report = ADAPTER.mesh_diagnostics(pair, packets)[0]
    assert report['passed'] is False and report['channels']['lift']['relative_change'] is None
    packets[pair[0]['id']]['status'] = 'numerical_failure'
    assert ADAPTER.mesh_diagnostics(pair, packets)[0]['status'] == 'UNAVAILABLE'


def test_fresh_selected_plan_equals_full_plan_and_cached_pins_are_rechecked(jobs, monkeypatch):
    for family in ('AE-2', 'FFWT-1'):
        selected = next(j for j in jobs if j['case_id'] == family and j['execution_route'] == 'worker')
        assert ADAPTER._plan(ROOT, selected=selected['id']) == [selected]
    original_pin = ADAPTER._pin
    source = jobs[0]['source_pins'][0]['path']
    def changed(path):
        result = original_pin(path)
        if str(path) == source:
            result['sha256'] = '0'*64
        return result
    monkeypatch.setattr(ADAPTER, '_pin', changed)
    with pytest.raises(ValueError, match='Cached canonical source changed'):
        ADAPTER.validate_blocked(ROOT, jobs[0])


def test_coupled_layups_keep_eight_exact_pairs_all_rows_and_original_parameters(jobs,tmp_path):
    coupled = [j for j in jobs if j.get('layup')]
    assert len(coupled) == 368 and sum(j['expected_outputs'] for j in coupled) == 1472
    assert sum(j['execution_route'] == 'worker' for j in coupled) == 352
    assert sum(o['missing'] for j in coupled for o in j['observations']) == 64
    baseline = next(j for j in jobs if j['case_id'] == 'AE-2' and not j.get('layup') and j['condition']['speed'] == 1)
    for layup,counts in ADAPTER.AE_COUPLED_COUNTS.items():
        cases = [j for j in coupled if j['layup'] == layup]
        assert len({j['coordinate_id'] for j in cases}) == sum(counts)
        assert len({j['source'] for j in cases}) == 1
        for beta,count in zip((1,5,10,15),counts):
            sweep = [j for j in cases if j['condition']['beta'] == beta]
            assert len(sweep) == 2*count
            assert {j['condition']['speed'] for j in sweep} == set(range(count))
            assert {j['mesh'] for j in sweep} == {'m80','m160'}
            for job in sweep:
                assert job['source'].endswith(f'/[{layup}]_S.asw')
                assert job['source_script']['path'].endswith(f'/[{layup}]_s_A{beta}.sh')
                assert job['source_output']['path'].endswith(f'/[{layup}]_S_A{beta}.txt')
                assert job['source_pairing']['model']['path'] == job['source']
                assert job['source_pairing']['beta_command_line_1based'] == 12
                assert [r['selection'] for r in job['source_pairing']['sensor_selections']] == [14,19,20,18]
                assert job['numerical_gates'] == baseline['numerical_gates'] and job['settings'] == baseline['settings']
                assert job['condition']['alpha'] == 0 and job['condition']['freeze_influences'] is True
                assert job['condition']['density'] == 1.23 and job['condition']['ground_effect'] == 1
                assert job['expected_elements'] == job['nominal']+1
        selected = next(j for j in cases if j['condition']['beta'] == 5 and j['condition']['speed'] == 10 and j['mesh'] == 'm160')
        ADAPTER._prepare_worker(ROOT,selected,tmp_path/layup)
        request = json.loads((tmp_path/layup/'cases/m160/request.json').read_text())
        assert request['source'].encode() == Path(selected['source']).read_bytes()
        tokens = request['source'].splitlines()
        assert tokens[17].split() == Path(baseline['source']).read_text().splitlines()[17].split()
        assert tokens[35].split()[8] == '1.0E4'
        assert tokens[34].split()[14] == ('-0.551' if layup == 'm15_02' else '0.250')
        assert tokens[40].split()[3] == ('0.35' if layup == 'm15_02' else '0.5')


def test_coupled_fresh_json_job_and_blocked_validation_remain_canonical(jobs):
    for layup in ADAPTER.AE_COUPLED_COUNTS:
        for speed in (0.,10.):
            job = next(j for j in jobs if j.get('layup') == layup and j['condition']['beta'] == 5 and
                       j['condition']['speed'] == speed and j['mesh'] == 'm160')
            decoded = json.loads(json.dumps(job,allow_nan=False))
            assert ADAPTER._plan(ROOT,selected=job['id']) == [decoded]
            assert ADAPTER._canonical(ROOT,decoded) == job
            if speed == 0:
                result = ADAPTER.validate_blocked(ROOT,decoded)
                assert not result['numerical_pass'] and not result['reference_match']
                assert all(c['predicted'] is c['expected'] is c['tolerance'] is None for c in result['reference_checks'])


def test_extra_distribution_export_is_pinned_and_explicitly_outside_sensor_scope(jobs):
    extras = [j for j in jobs if j.get('additional_driver_outputs')]
    assert len(extras) == 30
    for job in extras:
        assert job['layup'] == 'm15_02' and job['condition']['beta'] == 15
        extra, = job['additional_driver_outputs']
        assert extra['source']['path'].endswith('/[m15_02]_S_A15_dist.txt')
        assert extra['source'] in job['source_pins']
        assert 'outside the four-sensor-channel adapter' in extra['scope']
        assert job['expected_outputs'] == 4


@pytest.mark.parametrize('change',['missing_row','partial_nan','stack_order','speed_order'])
def test_coupled_decoder_rejects_truncation_missing_pattern_and_command_misalignment(jobs,change):
    job = next(j for j in jobs if j.get('layup') == 'p15_02' and j['condition']['beta'] == 5)
    text = Path(job['source_output']['path']).read_text()
    commands = [dict(line_number=i+1,token=line.split()[1]) for i,line in enumerate(Path(job['source_script']['path']).read_text().splitlines()) if line.strip().startswith('!V ')]
    if change == 'missing_row':text = '\n'.join(text.splitlines()[:-1])
    elif change == 'partial_nan':text = text.replace('NaN','0.0',1)
    elif change == 'stack_order':text = text.replace('  2  2.000','  9  2.000',1)
    else:commands[1]['token'] = '2'
    with pytest.raises(ValueError,match='AE2 coupled'):
        ADAPTER._decode_coupled_rows(text,commands,5,'p15_02')


@pytest.mark.parametrize('change',['layup','model','beta','speed','target','precision','source_pairing','additional_output'])
def test_coupled_prepared_job_tampering_is_rejected_before_physics(jobs,monkeypatch,change):
    job = deepcopy(next(j for j in jobs if j.get('layup') == 'm15_02' and j['condition']['beta'] == 15 and j['condition']['speed'] == 1))
    monkeypatch.setattr(ADAPTER,'_load',lambda *args:pytest.fail('Tampered job reached worker'))
    if change == 'layup':job['layup'] = 'p15_02'
    elif change == 'model':job['source'] = job['source'].replace('[m15_02]','[p15_02]')
    elif change == 'beta':job['condition']['beta'] = 5
    elif change == 'speed':job['condition']['speed'] = 2
    elif change == 'target':job['observations'][0]['expected'] += 1
    elif change == 'precision':job['observations'][0]['tolerance'] *= 10
    elif change == 'source_pairing':job['source_pairing']['model']['sha256'] = '0'*64
    else:job['additional_driver_outputs'] = []
    with pytest.raises(ValueError,match='Prepared aeroelastic job changed'):
        ADAPTER.run(ROOT,job)
