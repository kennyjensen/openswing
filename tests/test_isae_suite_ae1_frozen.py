"""Keep the documented K/F alternative explicit and its evidence independent."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import pytest

from scripts import isae_suite_ae1 as adapter
from test_isae_suite_ae1 import computed_fixture

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').exists():
        pytest.skip('Original ISAE archive unavailable')
    return adapter.plan(ROOT,comparison_scopes=[adapter.FROZEN_SCOPE])


def test_original_baseline_and_every_native_sensor_token_remain_separate(jobs):
    baseline=adapter.plan(ROOT)
    assert jobs[:200]==baseline
    assert len(jobs)==400 and len({j['id'] for j in jobs})==400
    for original,alternate in zip(baseline,jobs[200:],strict=True):
        assert alternate['base_static_job_id']==original['id']
        assert alternate['comparison_scope']==adapter.FROZEN_SCOPE
        assert alternate['coordinate_id']!=original['coordinate_id']
        for field in ['source','literal_model_sha256','observations','reference_rows','panels',
                      'gravity','settings','numerical_gates','literal_sensor_rows','literal_weight_rows']:
            assert alternate[field]==original[field]
        if original['condition'] is None:
            assert alternate['condition'] is None and alternate['execution_route']=='unsupported'
        else:
            expected=deepcopy(original['condition']);expected['freeze_influences']=True
            assert alternate['condition']==expected
        assert not alternate['historical_settings_recovered']
    assert sum(j['execution_route']=='unsupported' for j in jobs[200:])==4
    assert sum(j['expected_outputs'] for j in jobs[200:])==1200


@pytest.mark.parametrize('fault',['flag','scope','identifier','target','gravity','original-source'])
def test_frozen_scope_cannot_silently_change_physics_or_reference(jobs,fault):
    job=deepcopy(next(j for j in jobs[200:] if j['condition']))
    if fault=='flag':job['condition']['freeze_influences']=False
    elif fault=='scope':job.pop('comparison_scope')
    elif fault=='identifier':job['id']=job['base_static_job_id']
    elif fault=='target':job['observations'][0]['tolerance']*=100
    elif fault=='gravity':job['gravity']=[0.,0.,0.]
    else:job['literal_model_sha256']='0'*64
    with pytest.raises(ValueError):adapter.verify_reference_sources(ROOT,job)


def test_frozen_initial_state_stays_unavailable_without_solving(jobs,monkeypatch):
    monkeypatch.setattr(adapter,'_execute',lambda *args:pytest.fail('Unknown initial state solved'))
    job=next(j for j in jobs[200:] if j['condition'] is None)
    result=adapter.run(ROOT,job)
    assert result['status']=='unsupported' and result['physical_calls']==0
    assert len(result['reference_checks'])==6
    assert all(r['predicted'] is None and not r['passed'] for r in result['reference_checks'])


@pytest.mark.parametrize('blocked',[False,True])
def test_saved_contract_rejects_relabeling_a_baseline_job_as_frozen(jobs,blocked):
    job=deepcopy(next(j for j in jobs[:200] if (j['condition'] is None)==blocked))
    job['comparison_scope']=adapter.FROZEN_SCOPE
    with pytest.raises(ValueError,match='own job and mesh-pair identity'):
        adapter.reference_contract(job)


def test_four_mesh_states_are_compared_only_with_their_own_influence_setting(jobs):
    selected=[j for j in jobs if j['coordinate_id'] in ('a05-row002','a05-row002-frozen')]
    assert len(selected)==4
    results={j['id']:computed_fixture(j) for j in selected}
    for job in selected:
        assert adapter.validate_result_contract(job,results[job['id']])
        setup=next(c for c in results[job['id']]['physical_checks'] if c['name']=='cold_operating_setup')
        frozen=job.get('comparison_scope')==adapter.FROZEN_SCOPE
        assert setup['expected']['frozen'] is frozen
        assert setup['expected']['wind_angles']==([0.,0.] if frozen else [5.,0.])
    comparisons=adapter.mesh_diagnostics(selected,results)
    assert len(comparisons)==2
    assert all(r['status']=='COMPARED' and len(r['jobs'])==2 for r in comparisons)
    assert all(r['acceptance_gate'] is None for r in comparisons)
    from test_isae_suite_summary import SUMMARY,ae1_packet
    rows=[{**deepcopy(j),'result':results[j['id']]} for j in selected]
    summary=SUMMARY.summarize(SUMMARY.merge_runs([ae1_packet(rows)]))
    family=next(row for row in summary['families'] if row['id']=='AE-1')
    assert family['comparison_scopes']['static']['required']==12
    assert family['comparison_scopes'][adapter.FROZEN_SCOPE]['required']==12
    assert len(summary['ae1_mesh_diagnostics'])==2
    assert family['declared_scope']['sensor_reference_rows']==1
    assert family['declared_scope']['original_reference_samples']==1
    rendered=SUMMARY.markdown(summary)
    assert 'alternative settings add no independent native targets' in rendered
    assert 'historical OPER K/F setting remains unknown' in rendered


def test_shared_runner_requires_scope_owner_and_preserves_default_plan(jobs,monkeypatch):
    # Match the import path supplied by invoking the runner as a CLI script.
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('ae1_scope_runner',ROOT/'scripts/run-isae-suite.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    assert runner.COMPARISON_SCOPES[adapter.FROZEN_SCOPE]=='ae1'
    with pytest.raises(ValueError,match='owning adapter'):
        runner.plan_jobs(ROOT,adapters=['sa6'],comparison_scopes=[adapter.FROZEN_SCOPE])
    planned=runner.plan_jobs(ROOT,adapters=['ae1'],comparison_scopes=[adapter.FROZEN_SCOPE])
    assert [j['id'] for j in planned]==[j['id'] for j in jobs]


@pytest.mark.parametrize('scopes',[[adapter.FROZEN_SCOPE]*2,['unknown-scope']])
def test_unreviewed_or_duplicate_scope_rejected(scopes):
    with pytest.raises(ValueError,match='unique reviewed'):
        adapter.plan(ROOT,comparison_scopes=scopes)
