"""SA11 original-source accounting and mocked forwarding; zero aircraft solves."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import isae_suite_sa11 as sa11

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').exists():
        pytest.skip('Optional pinned original archive unavailable.')
    before = {n for n in sys.modules if n == 'openswing' or n.startswith('openswing.')}
    result = sa11.plan(ROOT)
    assert {n for n in sys.modules if n == 'openswing' or n.startswith('openswing.')} == before
    return result


def test_planning_in_fresh_process_is_stdlib_only(jobs):
    code = '''import json,sys
from pathlib import Path
from scripts import isae_suite_sa11 as adapter
jobs=adapter.plan(Path(sys.argv[1]))
assert not any(n=='openswing' or n.startswith('openswing.') or n in ('numpy','scipy') for n in sys.modules)
print(json.dumps({'jobs':len(jobs),'outputs':sum(j['expected_outputs'] for j in jobs)}))
'''
    result = subprocess.run([sys.executable,'-c',code,str(ROOT)],cwd=ROOT,
                            capture_output=True,text=True,timeout=20,check=True)
    assert json.loads(result.stdout) == {'jobs':1312,'outputs':9184}


def test_all_sixteen_tables_and_both_meshes_remain_required(jobs):
    assert len(jobs) == len({j['id'] for j in jobs}) == 1312
    assert len({j['table_path'] for j in jobs}) == 16
    assert len({j['model_path'] for j in jobs}) == 4
    assert sum(j['execution_route'] == 'seven_fields' for j in jobs) == 328
    assert sum(j['execution_route'] == 'unsupported' for j in jobs) == 984
    for table in {j['table_path'] for j in jobs}:
        group = [j for j in jobs if j['table_path'] == table]
        assert len(group) == 82
        assert {(j['row_index'],j['settings']['panels']) for j in group} == {(r,n) for r in range(41) for n in (64,128)}
    assert all(j['expected_outputs'] == 7 and j['required_outputs'] == list(sa11.polar.OUTPUTS)
               and j['complete_family_reproduction'] is False for j in jobs)


def test_every_printed_target_and_original_pair_is_retained(jobs):
    texts = {name:(ROOT/name).read_text().splitlines() for name in {j['table_path'] for j in jobs}}
    for job in jobs:
        row = job['reference_row']; tokens = texts[job['table_path']][row['line_number']-1].split()
        assert len(tokens) == 82 and row['tokens'] == tokens
        for column,name in enumerate(sa11.OUTPUTS,75):
            value = Decimal(tokens[column]); half = Decimal(5)*Decimal(10)**(value.as_tuple().exponent-1)
            assert row['fields'][name] == {'token':tokens[column],'value':float(value),'tolerance':float(half)}
        assert row['fields']['actual_speed']['token'] == tokens[69]
        assert row['fields']['speed']['token'] == tokens[72]
        assert row['fields']['actual_alpha']['token'] == tokens[71]
        assert row['fields']['alpha']['token'] == tokens[74]
        declaration = job['driver_declarations']
        assert declaration['output_files'] == [Path(job['table_path']).name]
        assert declaration['model_file'] == Path(job['model_path']).name
        assert Path(job['model_path']).parent == Path(job['table_path']).parent
        if job['variant'] == 'wing_extension':
            assert Path(job['driver_path']).name.startswith('wing_extentsion_')
    for variant in sa11.VARIANTS:
        model = ROOT/next(j['model_path'] for j in jobs if j['variant'] == variant)
        assert hashlib.sha256(model.read_bytes()).hexdigest() == sa11.MODEL_SHA256[variant]
        assert 'Wing_alone' in model.read_text()  # Original extension title is not its filename.


def test_pg_speeds_density_and_unrecovered_mesh_are_explicit(jobs):
    for job in jobs:
        s = job['settings']
        assert s['mach'] is None and s['speed'] == {'0_70':240,'0_75':255,'0_78':266,'0_80':272}[job['mach_label']]
        assert s['density'] == 1.2256 and s['density_token'] == '1.2256'
        assert s['alpha'] == job['row_index']/4 and s['beta'] == 0
        assert s['beam_interpolation'] == 'natural-v1' and s['freeze_influences'] is False
        assert s['stall'] is True and s['panels'] in (64,128)
        assert 'cosine' in s['mesh_source'] and job['driver_declarations']['requested_nodes'] is None
        assert job['driver_declarations']['node_count_token'] is None
        assert 'declared_panels' not in job['driver_declarations']
        assert 'panel_token' not in job['driver_declarations']
        assert any('startup PG/K/F' in q for q in job['qualifications'])
        assert not any('Mach=0' in q for q in job['qualifications'])
        toggles = [c['command'] for c in job['driver_declarations']['settings_commands']]
        assert toggles == (['kk','mm'] if job['mach_label'] in ('0_70','0_80')
                           or job['variant']=='wingtip_up_and_down' else [])


def test_all_stalled_rows_survive(jobs):
    coarse = [j for j in jobs if j['settings']['panels'] == 64 and j['archived_stall_flag']
              and j['variant'] in ('wing_alone','wing_extension')]
    assert [(j['variant'],j['mach_label'],j['row_index']+1) for j in coarse] == [
        ('wing_extension','0_70',40),('wing_extension','0_70',41),
        *[('wing_extension','0_80',r) for r in range(36,42)]]
    assert all(j['execution_route'] == 'seven_fields' for j in coarse)
    for variant in ('wingtip_up','wingtip_up_and_down'):
        stalled = [j for j in jobs if j['variant']==variant and j['archived_stall_flag']]
        assert stalled and all(j['execution_route']=='unsupported' and j['expected_outputs']==7 for j in stalled)


def test_normalization_conflicts_and_two_small_exceptions_are_not_hidden(jobs):
    coarse = [j for j in jobs if j['settings']['panels'] == 64]
    blocked = [j for j in coarse if j['normalization_conflict']]
    assert len(blocked) == 328
    assert {j['mach_label'] for j in blocked} == {'0_75','0_78'}
    for job in blocked:
        channels = job['normalization_evidence']['channels']
        assert all(not c['literal_qS_inside'] for c in channels.values())
        assert all(97.66 < c['implied_area_at_literal_density'] < 97.68 for c in channels.values())
        assert job['blocker_code'] == sa11.BLOCKER and job['unsupported_reason'].startswith(sa11.BLOCKED_REASON)
    exceptions = [(j['variant'],j['mach_label'],j['row_index']+1,name)
                  for j in coarse if not j['normalization_conflict']
                  for name,c in j['normalization_evidence']['channels'].items() if not c['literal_qS_inside']]
    assert exceptions == [('wing_alone','0_70',23,'drag'),('wing_alone','0_70',37,'lift')]


@pytest.mark.parametrize('variant,label',[(v,m) for v in sa11.VARIANTS for m in ('0_75','0_78')])
def test_conflict_jobs_never_call_physics_or_drop_targets(jobs,monkeypatch,variant,label):
    monkeypatch.setattr(sa11.polar,'run',lambda *a:pytest.fail('Blocked job attempted physical execution.'))
    monkeypatch.setattr(sa11,'plan',lambda *a:pytest.fail('Per-job validation rebuilt all1312 jobs.'))
    job = next(j for j in jobs if j['variant'] == variant and j['mach_label'] == label)
    report = sa11.run(ROOT,job)
    assert report['status'] == 'unsupported' and report['physical_calls'] == 0
    assert not report['reference_match'] and not report['numerical_pass']
    assert len(report['reference_checks']) == 7
    for check in report['reference_checks']:
        ref = job['reference_row']['fields'][check['name']]
        assert check['expected'] == ref['value'] and check['expected_token'] == ref['token']
        assert check['tolerance'] == ref['tolerance'] and not check['passed'] and check['predicted'] is None
    json.dumps(report,allow_nan=False)


@pytest.mark.parametrize('variant', ['wingtip_up','wingtip_up_and_down'])
def test_original_winglet_input_blockers_are_verified_without_aero_solves(jobs,variant):
    from openswing.asw import AswError, parse_asw
    from openswing.geometry import model_meshes
    selected = [j for j in jobs if j['variant']==variant]
    assert len(selected)==328 and all(j['input_issue'] and j['execution_route']=='unsupported' for j in selected)
    text = (ROOT/selected[0]['model_path']).read_text()
    if variant=='wingtip_up':
        with pytest.raises(AswError,match=r'Line 32: Too many scaling values'):
            parse_asw(text)
    else:
        model = parse_asw(text)
        assert tuple(float(t) for t in model.beams[0].domain)==pytest.approx((-1.2426,1.2426))
        assert all(abs(row[2])==12.426 and abs(row[3])==12.426 for row in model.records['joint'])
        with pytest.raises(ValueError,match="Attachment station is outside beam 1's parameter range"):
            model_meshes(model,64)


@pytest.mark.parametrize('variant,label',[(v,m) for v in ('wingtip_up','wingtip_up_and_down') for m in sa11.LABELS])
def test_winglet_jobs_preserve_both_independent_blockers_and_all_targets(jobs,monkeypatch,variant,label):
    job = next(j for j in jobs if j['variant']==variant and j['mach_label']==label)
    monkeypatch.setattr(sa11.polar,'run',lambda *a:pytest.fail('Original blocked winglet attempted an aero solve.'))
    result = sa11.run(ROOT,job)
    codes = ([sa11.BLOCKER] if label in ('0_75','0_78') else [])+[sa11.INPUT_BLOCKS[variant][0]]
    assert job['blocker_codes']==result['blocker_codes']==codes
    assert result['input_issue']==job['input_issue'] and result['status']=='unsupported'
    assert result['physical_calls']==0 and len(result['reference_checks'])==7
    assert all(c['predicted'] is None and not c['passed'] for c in result['reference_checks'])
    mutated = deepcopy(job);mutated['input_issue']=None;mutated['blocker_codes']=[]
    with pytest.raises(ValueError,match='differs from the declared literal plan'):
        sa11.run(ROOT,mutated)


@pytest.mark.parametrize('change',['pg','new_setting','target','gate','conflict_route'])
def test_changed_physical_or_reference_protocol_rejected_before_worker(jobs,monkeypatch,change):
    job = deepcopy(next(j for j in jobs if j['execution_route'] == ('unsupported' if change == 'conflict_route' else 'seven_fields')))
    if change == 'pg':job['settings']['mach'] = 0.
    if change == 'new_setting':job['settings']['ground_effect'] = 1
    if change == 'target':job['reference_row']['fields']['drag']['value'] *= 2
    if change == 'gate':job['reference_row']['fields']['drag']['tolerance'] *= 10
    if change == 'conflict_route':job['execution_route'] = 'seven_fields'
    monkeypatch.setattr(sa11.polar,'run',lambda *a:pytest.fail('Changed job attempted execution.'))
    with pytest.raises(ValueError,match='differs from the declared literal plan'):
        sa11.run(ROOT,job)


def test_changed_source_cannot_pass(jobs,monkeypatch):
    job = jobs[0]; original = sa11.polar._pin
    def changed(path,root):
        result = original(path,root)
        if result['path'] == job['table_path']:result['sha256'] = '0'*64
        return result
    monkeypatch.setattr(sa11.polar,'_pin',changed)
    monkeypatch.setattr(sa11.polar,'run',lambda *a:pytest.fail('Changed source attempted execution.'))
    report = sa11.run(ROOT,job)
    assert report['status'] == 'source_mismatch' and report['physical_calls'] == 0
    assert len(report['reference_checks']) == 7 and not report['reference_match']


@pytest.mark.parametrize('change',['sidecar','manifest'])
def test_hot_cache_does_not_hide_new_startup_or_manifest(jobs,monkeypatch,change):
    job = next(j for j in jobs if j['execution_route'] == 'unsupported')
    assert sa11.validate_blocked(ROOT,job)['status'] == 'unsupported'  # Prime the exact table cache.
    if change == 'sidecar':
        original = Path.exists; sidecar = (ROOT/job['model_path']).with_suffix('.set')
        monkeypatch.setattr(Path,'exists',lambda path: True if path == sidecar else original(path))
        message = 'New startup sidecar'
    else:
        original = Path.read_bytes; manifest = ROOT/'.reference/isae-validation/manifest.json'
        monkeypatch.setattr(Path,'read_bytes',lambda path: b'changed manifest' if path == manifest else original(path))
        message = 'Original archive manifest changed'
    monkeypatch.setattr(sa11.polar,'run',lambda *a:pytest.fail('New setup attempted physical execution.'))
    with pytest.raises(ValueError,match=message):
        sa11.validate_blocked(ROOT,job)


@pytest.mark.parametrize('failure',[None,'numerical','reference','missing','duplicate'])
def test_worker_forwarding_keeps_pg_and_all_existing_gates(jobs,monkeypatch,failure):
    job = next(j for j in jobs if j['variant'] == 'wing_extension' and j['archived_stall_flag'] == 1)
    before = deepcopy(job); calls = []
    numerical = [{'name':'circulation residual','value':1e-12,'tolerance':1e-8,'passed':failure != 'numerical'},
                 {'name':'force normalization','value':1e-12,'tolerance':2e-10,'passed':True}]
    def fake_worker(root,forwarded):
        assert root == ROOT and forwarded == job and forwarded is not job
        assert forwarded['settings']['mach'] is None and forwarded['settings']['speed'] == 240
        assert forwarded['settings']['density'] == 1.2256 and forwarded['archived_stall_flag'] == 1
        predicted = {n:forwarded['reference_row']['fields'][n]['value'] for n in sa11.OUTPUTS}
        if failure == 'reference':predicted['drag'] += 2*forwarded['reference_row']['fields']['drag']['tolerance']
        checks = sa11.polar.reference_checks(predicted,forwarded['reference_row'])
        if failure == 'missing':checks.pop()
        if failure == 'duplicate':checks[-1] = deepcopy(checks[0])
        calls.append(forwarded)
        return dict(status='numerical_failure' if failure == 'numerical' else 'computed',
                    numerical_pass=failure != 'numerical',reference_checks=checks,numerical_checks=numerical,physical_calls=1)
    monkeypatch.setattr(sa11.polar,'run',fake_worker)
    result = sa11.run(ROOT,job)
    assert len(calls) == 1 and job == before
    assert result['reference_match'] is (failure is None)
    assert result['numerical_checks'] == numerical and result['numerical_pass'] is (failure != 'numerical')
    assert result['physical_calls'] == 1 and result['expected_outputs'] == 7
    assert result['normalization_conflict'] is False and not result['complete_family_reproduction']
