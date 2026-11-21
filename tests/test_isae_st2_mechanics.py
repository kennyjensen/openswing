"""Scope and rejection checks; saved-study fixtures are not fresh solver passes."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import isae_suite_st2 as legacy
import isae_suite_st2_mechanics as mechanics
from isae_acceptance import apply_reference_acceptance

SPEC = importlib.util.spec_from_file_location('st2_mechanics_runner', ROOT/'scripts/run-isae-suite.py')
runner = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(runner)
read = lambda path: json.loads(path.read_text())


@pytest.fixture(scope='module')
def jobs():
    before = {name for name in sys.modules if name.startswith('openswing')}
    jobs = legacy.plan(ROOT, comparison_scopes=['st2-mechanics'])
    assert {name for name in sys.modules if name.startswith('openswing')} == before
    return jobs


def test_all_targets_once_and_archive_separate(jobs):
    assert len(jobs) == 43
    assert sum(j['expected_outputs'] for j in jobs if j['target_kind'] == 'static') == 77
    assert sum(j['expected_outputs'] for j in jobs if j['target_kind'] == 'modal') == 14
    old = legacy._specs()
    assert len(old) == 17
    assert not {j['id'] for j in jobs} & {j['id'] for j in old}
    assert runner.plan_jobs(ROOT, ['st2'], comparison_scopes=['st2-mechanics']) == jobs
    assert all(not p['path'].startswith('openswing/') for j in jobs for p in j['source_pins'])
    pins = runner.code_pins(ROOT,['st2'])
    assert all(('scripts/'+p) in pins for p in mechanics.EXECUTION_HELPERS)


def test_default_scope_retains_legacy_dispatch(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(legacy,'build_jobs',lambda root:sentinel)
    assert legacy.plan(ROOT) is sentinel
    with pytest.raises(ValueError,match='Unknown ST2 mechanics'):legacy.plan(ROOT,comparison_scopes=['unknown'])


def test_parallel_mechanics_workers_are_rejected(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['run-isae-suite.py','--comparison-scope','st2-mechanics','--workers','2'])
    with pytest.raises(SystemExit) as error:runner.main()
    assert error.value.code == 2
    assert 'one worker' in capsys.readouterr().err


def test_scope_metadata_does_not_relabel_legacy_archive(jobs):
    catalog = {'cases':[dict(id='ST-2',path='ST-2',models=[],reference_candidates=[])]}
    old = [dict(id='archive',case_id='ST-2',expected_outputs=490)]
    assert 'comparison_scopes' not in runner.summarize(catalog,old,{})[0]
    assert runner.summarize(catalog,jobs,{})[0]['comparison_scopes']['st2-mechanics']['required'] == 91


def test_original_targets_and_setup_preserved(jobs):
    scope = read(ROOT/mechanics.TARGETS)
    observations = {r['name']:r for j in jobs for r in j['observations']}
    assert len(observations) == 91
    for target in scope['static_targets'] + scope['modal_targets']:
        row = observations[target['id']]
        assert row['expected'] == target.get('expected',target.get('expected_Hz'))
        assert row['original_tokens'] == target['original_tokens']
    static = read(ROOT/'artifacts/isae/st2-static-curves-20261109/plan.json')
    modal = read(ROOT/'artifacts/isae/st2-modal-current-20261109/plan.json')
    for job in jobs:
        assert job['config'] == (static if job['target_kind'] == 'static' else modal)['cases'][job['configuration']]
        assert job['literal_input_modified'] == (job['target_kind'] == 'static')
        for state in mechanics.state_jobs(job):
            assert state in (static if job['target_kind'] == 'static' else modal)['jobs']


def fixture_result(job):
    static = job['target_kind'] == 'static'
    base = ROOT/'artifacts/isae'/('st2-static-curves-20261109' if static else 'st2-modal-current-20261109')
    plan = read(base/'plan.json'); states = []
    for state in mechanics.state_jobs(job):
        i = plan['jobs'].index(state)
        states.append(read(base/(f'job-{i:02d}' if static else f'job-{i}')/'report.json'))
    if static:
        values, mesh = mechanics.static_evidence(job,states)
    else:
        summary = read(base/'summary.json'); mesh = []
        for i, obs in enumerate(job['observations']):
            m = next(r for r in summary['mesh_checks'] if r['orientation'] == job['configuration'] and
                     r['coarse_nodes'] == 80 and r['ordinal'] == i+1)
            c = next(r for r in summary['classifications'] if r['orientation'] == job['configuration'] and r['ordinal'] == i+1)
            a, b = [s['frequencies'][i]['frequency_Hz'] for s in states]
            mesh.append(dict(name=obs['name'], coarse_Hz=a, fine_Hz=b, relative_change=abs(a/b-1),
                shape_MAC=m['shape_MAC'], coarse_ordinal=m['ordinal_assignment'], label=c['label'],
                activity_fractions=c['activity_fractions']))
    checks = []
    for i, obs in enumerate(job['observations']):
        value = values[obs['quantity']] if static else max(
            (s['frequencies'][i]['frequency_Hz'] for s in states),key=lambda f:abs(f-obs['expected']))
        checks.append(dict(**obs,predicted=value,passed=abs(value-obs['expected']) <= obs['tolerance']))
    return dict(status='computed',comparison_scope='st2-mechanics',reference_checks=checks,states=states,
        mesh_checks=mesh,solver_calls=len(states),numerical_pass=True,source_pins_unchanged=True,
        complete_family_reproduction=False,literal_input_modified=job['literal_input_modified'])


def test_all_saved_study_fixtures_satisfy_contract(jobs):
    for job in jobs:
        result = runner.checked_result(job, fixture_result(job))
        assert result['status'] == 'computed', result.get('contract_error')
        assert apply_reference_acceptance(result)['reference_match']


@pytest.mark.parametrize('fault', ['target','missing_state','missing_mode','pencil','missing_mesh','wrong_family',
    'bad_MAC','negative_MAC','assignment','bad_residual','frequency','favorable_mesh','qualification'])
def test_incomplete_or_inconsistent_modal_evidence_rejected(jobs, fault):
    job = next(j for j in jobs if j['target_kind'] == 'modal')
    r = fixture_result(job)
    if fault == 'target': r['reference_checks'][0]['expected'] *= 1.1
    elif fault == 'missing_state': r['states'].pop()
    elif fault == 'missing_mode': r['states'][0]['frequencies'].pop()
    elif fault == 'pencil': r['states'][0]['pencil_audits'].pop()
    elif fault == 'missing_mesh': r['mesh_checks'].pop()
    elif fault == 'wrong_family': r['mesh_checks'][0]['label'] = 'T1'
    elif fault == 'bad_MAC': r['mesh_checks'][0]['shape_MAC'] = float('nan')
    elif fault == 'negative_MAC': r['mesh_checks'][0]['shape_MAC'] = -.9
    elif fault == 'assignment': r['mesh_checks'][0]['coarse_ordinal'] = 2
    elif fault == 'bad_residual': r['states'][0]['checks']['fresh_residual'] = 1e-3
    elif fault == 'frequency': r['states'][0]['frequencies'][0]['frequency_Hz'] *= 1.1
    elif fault == 'favorable_mesh':
        row = r['reference_checks'][0]
        row['predicted'] = min((s['frequencies'][0]['frequency_Hz'] for s in r['states']),key=lambda v:abs(v-row['expected']))
    else: r['literal_input_modified'] = True
    checked = runner.checked_result(job,r)
    assert checked['status'] == 'adapter_contract_failure'
    assert not apply_reference_acceptance(checked)['reference_match']


@pytest.mark.parametrize('fault',['missing_baseline','missing_fine_baseline','projected_twist','changed_mesh'])
def test_static_measurement_and_refinement_are_required(jobs,fault):
    job = next(j for j in jobs if j['configuration'] == 'torsion-on' and j['refine'])
    r = fixture_result(job)
    if fault == 'missing_baseline':r['states'].pop(0)
    elif fault == 'missing_fine_baseline':r['states'].pop(2)
    elif fault == 'projected_twist':
        row = next(r for r in r['reference_checks'] if r['quantity'] == 'twist_deg')
        row['predicted'] = -r['states'][1]['observable']['twist_projected_deg']
    else:r['mesh_checks'][0]['relative_change'] = 0
    assert runner.checked_result(job,r)['status'] == 'adapter_contract_failure'


def test_changed_targets_cannot_be_replanned(tmp_path):
    for name in (mechanics.INPUTS,mechanics.TARGETS):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    p=tmp_path/mechanics.TARGETS; data=read(p);data['modal_targets'][0]['expected_Hz']*=1.01
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='reference values changed'):mechanics.plan(tmp_path)


def test_modified_job_setup_rejected(jobs):
    job = deepcopy(jobs[0]); job['config']['x'] *= -1
    with pytest.raises(ValueError,match='canonical setup'):mechanics.verify_reference_sources(ROOT,job)


def test_child_timeout_stops_sequence(jobs,monkeypatch,tmp_path):
    monkeypatch.setattr(mechanics.resource,'setrlimit',lambda *a:None)
    monkeypatch.setattr(mechanics.signal,'alarm',lambda *a:None)
    monkeypatch.setattr(mechanics.tempfile,'mkdtemp',lambda **k:str(tmp_path))
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):monkeypatch.setenv(name,'1')
    calls=[]
    def timeout(command,**options):
        calls.append(command)
        assert options['timeout'] == 30 and 'start_new_session' not in options
        raise subprocess.TimeoutExpired(command,30)
    monkeypatch.setattr(mechanics.subprocess,'run',timeout)
    with pytest.raises(subprocess.TimeoutExpired):mechanics.run(ROOT,jobs[-1])
    assert len(calls) == 1
