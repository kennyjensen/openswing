"""Retain the historical blocker while verifying the explicit seven-field scope."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import pytest
from scripts import isae_suite_sa15 as sa15, isae_suite_extra_polars as extra

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').exists():pytest.skip('Original ISAE cache required')
    before={m for m in sys.modules if m.startswith('openswing')}
    result=sa15.plan(ROOT)
    assert {m for m in sys.modules if m.startswith('openswing')}==before
    return result


@pytest.fixture(scope='module')
def anchor(jobs):
    job=next(j for j in jobs if j['row_index']==3 and j['settings']['panels']==64)
    return job,sa15.run(ROOT,job)


def test_all_original_angles_meshes_columns_and_settings_dump_retained(jobs):
    baseline=extra.plan(ROOT)
    extended=extra.plan(ROOT,comparison_scopes=[sa15.SCOPE])
    assert len(baseline)==710 and extended[:710]==baseline and extended[710:]==jobs
    old=[j for j in baseline if j['case_id']=='SA-15']
    assert len(jobs)==len(old)==26 and len({j['id'] for j in extended})==736
    for a,b in zip(old,jobs,strict=True):
        assert a['reference_row']==b['reference_row'] and a['row_index']==b['row_index']
        assert b['settings']['alpha_token']==a['exact_driver_alpha_token']
        assert b['settings']['alpha']==float(a['exact_driver_alpha_token'])
        assert b['required_outputs']==list(sa15.OUTPUTS) and b['expected_outputs']==7
        assert any(p['path'].endswith('.set') for p in b['sources'])
        assert a['execution_route']=='unsupported' and not b['original_set_decoded']
        assert not b['historical_settings_recovered'] and not b['complete_family_reproduction']


@pytest.mark.parametrize('fault',['scope','angle','mach','panels','target','gate','historical','source'])
def test_source_verification_rejects_altered_setup_or_reference(jobs,fault):
    j=deepcopy(jobs[0])
    if fault=='scope':j.pop('comparison_scope')
    if fault=='angle':j['settings']['alpha']=0.
    if fault=='mach':j['settings']['mach']=.35
    if fault=='panels':j['settings']['panels']=40
    if fault=='target':j['reference_row']['fields']['CD']['value']*=.9
    if fault=='gate':j['numerical_gates']['residual']=.05
    if fault=='historical':j['original_set_decoded']=True
    if fault=='source':j['sources'][0]['sha256']='0'*64
    with pytest.raises(ValueError):sa15.verify_reference_sources(ROOT,j)


def test_one_actual_anchor_keeps_full_physics_and_strict_reference_results(anchor):
    j,r=anchor
    assert r['status']=='computed' and r['numerical_pass'] and sa15.validate_result_contract(j,r)
    assert len(r['reference_checks'])==7 and not any(c['passed'] for c in r['reference_checks'])
    from scripts.isae_acceptance import apply_reference_acceptance
    view=apply_reference_acceptance(r)
    assert [c['name'] for c in view['reference_checks'] if c['passed']]==['CL','Cm','efficiency']
    assert r['operations']==dict(cold_rigid_solves=1,retries=0)


@pytest.mark.parametrize('fault',['qualification','residual','check','gate','output','wrench','efficiency','missing'])
def test_saved_evidence_cannot_promote_missing_physics_or_change_outputs(anchor,fault):
    j,r=deepcopy(anchor)
    if fault=='qualification':r['historical_settings_recovered']=True
    if fault=='residual':r['metrics']['residual']=1e-4
    if fault=='check':r['numerical_checks'][2]['value']=.1
    if fault=='gate':r['reference_checks'][0]['tolerance']=.05
    if fault=='output':
        r['predicted']['CD']*=1.1;r['reference_checks'][0]['predicted']=r['predicted']['CD']
    if fault=='wrench':r['physical']['force'][0]+=1.
    if fault=='efficiency':
        r['predicted']['efficiency']*=1.1;r['reference_checks'][-1]['predicted']=r['predicted']['efficiency']
    if fault=='missing':r['reference_checks'].pop()
    with pytest.raises(ValueError):sa15.validate_result_contract(j,r)


def test_runner_and_summary_preserve_scope_and_do_not_mix_meshes(jobs,anchor,monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('sa15_runner',ROOT/'scripts/run-isae-suite.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    assert runner.COMPARISON_SCOPES[sa15.SCOPE]=='extra_polars'
    with pytest.raises(ValueError,match='owning adapter'):
        runner.plan_jobs(ROOT,adapters=['polars'],comparison_scopes=[sa15.SCOPE])
    baseline=[j for j in extra.plan(ROOT) if j['case_id']=='SA-15']
    results={j['id']:extra.run(ROOT,j) for j in baseline}
    j,r=anchor;results[j['id']]=runner.checked_result(j,r)
    assert results[j['id']]['status']=='computed'
    comparisons=runner.mesh_diagnostics(baseline+jobs,results)
    assert len(comparisons)==26
    assert sum(c.get('comparison_scope')==sa15.SCOPE for c in comparisons)==13
    from test_isae_suite_summary import SUMMARY,policy_packet
    rows=[dict(j,result=results.get(j['id'])) for j in baseline+jobs]
    packet=policy_packet(rows,.05)
    packet['report']['code_sha256']['scripts/isae_suite_extra_polars.py']='adapter'
    packet['report']['code_sha256']['scripts/isae_suite_sa15.py']='helper'
    data=SUMMARY.summarize(SUMMARY.merge_runs([packet]))
    family=next(r for r in data['families'] if r['id']=='SA-15')
    assert family['comparison_scopes']['static']['required']==182
    assert family['comparison_scopes'][sa15.SCOPE]['passed']==3
    assert family['comparison_scopes'][sa15.SCOPE]['required']==182
    assert family['declared_scope']['original_reference_samples']==13
    assert len(data['fine_grid_polar_tables'])==2
    rendered=SUMMARY.markdown(data)
    assert 'sa15-declared-setup reconstruction has 3/182 matching scalar slots' in rendered
    assert 'original .set is undecoded' in rendered
    assert 'alternative settings add no independent native targets' in rendered
    assert '[scope sa15-declared-setup]' in rendered


def test_historical_blocker_cannot_be_erased_by_relabeling_a_computed_result(anchor):
    job=next(j for j in extra.plan(ROOT) if j['case_id']=='SA-15')
    with pytest.raises(ValueError,match='historical setup remains blocked'):
        extra.validate_result_contract(job,anchor[1])


@pytest.mark.parametrize('scopes',[[sa15.SCOPE]*2,['unknown']])
def test_duplicate_or_unknown_scope_refused(scopes):
    with pytest.raises(ValueError,match='unique reviewed'):
        extra.plan(ROOT,comparison_scopes=scopes)
