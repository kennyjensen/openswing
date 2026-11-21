"""Recurring ST3 scope and saved-evidence contracts; fixtures are not new solves."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import isae_suite_st3_mechanics as mechanics
from isae_acceptance import apply_reference_acceptance


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


runner=load('st3_mechanics_runner','scripts/run-isae-suite.py')
summary=load('st3_mechanics_summary','scripts/summarize-isae-suite.py')
read=lambda p:json.loads(p.read_text())
STATIC=ROOT/'artifacts/isae/st3-static-curves-20261109/replay'
MODAL=ROOT/'artifacts/isae/st3-modal-current-20261109'


@pytest.fixture(scope='module')
def jobs():return mechanics.plan(ROOT,comparison_scopes=[mechanics.SCOPE])


def fixture_result(job):
    static=job['target_kind']=='static';folder=STATIC if static else MODAL
    plan=read(folder/'plan.json');states=[]
    for state in mechanics.state_jobs(job):
        index=plan['jobs'].index(state)
        states.append(read(folder/(f'job-{index:02d}' if static else f'job-{index}')/'report.json'))
    if static:mesh=mechanics.evidence(job,states)
    else:
        reviewed=[r for r in read(MODAL/'summary.json')['rows'] if r['layup']==job['configuration']]
        mesh=[]
        for i,row in enumerate(job['observations']):
            pair=mechanics.frequency_pair(states,i)
            mesh.append(dict(name=row['name'],predictions=pair,absolute_change=abs(pair[1]-pair[0]),
                gate=.001*abs(pair[1]),shape_MAC=reviewed[i]['shape_MAC'],mutual_shape_assignment=True))
    checks=[]
    for row,m in zip(job['observations'],mesh,strict=True):
        value=mechanics.predicted(row,m['predictions'])
        checks.append(dict(row,predicted=value,passed=mechanics.strict_pass(row,value)))
    return dict(status='computed',comparison_scope=mechanics.SCOPE,numerical_pass=mechanics.numerical(job,states,mesh),
        source_pins_unchanged=True,states=states,mesh_checks=mesh,reference_checks=checks,solver_calls=2)


def test_scope_is_explicit_and_preserves_all_targets(jobs):
    assert mechanics.plan(ROOT)==[]
    assert len(jobs)==43 and sum(j['expected_outputs'] for j in jobs)==95
    assert sum(j['expected_outputs'] for j in jobs if j['target_kind']=='static')==86
    unavailable=[r for j in jobs for r in j['observations'] if not r['source_available']]
    assert len(unavailable)==2 and all(r['expected'] is None for r in unavailable)
    assert len({j['model_path'] for j in jobs})==6
    assert all(len(mechanics.state_jobs(j))==2 for j in jobs)
    assert len(runner.plan_jobs(ROOT,['st3'],comparison_scopes=[mechanics.SCOPE]))==43


@pytest.mark.parametrize('scopes',[['unknown'],['st3-mechanics','st3-mechanics']])
def test_unknown_or_duplicate_scope_is_rejected(scopes):
    with pytest.raises(ValueError):mechanics.plan(ROOT,comparison_scopes=scopes)


def test_saved_physical_fixtures_reproduce_the_reviewed_counts(jobs):
    rows=[]
    for job in jobs:
        raw=fixture_result(job);assert mechanics.validate_result_contract(job,raw)
        strict=runner.checked_result(job,raw)
        assert strict['status']=='computed',strict.get('contract_error')
        accepted=apply_reference_acceptance(strict)
        rows.append(dict(job,result=accepted))
    counts=summary.totals(rows)
    assert counts['required']==95 and counts['passed']==93 and counts['reported_unavailable']==2
    assert counts['finite']==93 and counts['failed_job_required']==0
    assert summary.totals([summary.strict_policy_job(j) for j in rows])['passed']<93


def test_mechanics_cannot_be_added_to_overlapping_archive(jobs):
    with pytest.raises(ValueError,match='overlapping historical'):
        summary.merge_runs([dict(report=dict(jobs=jobs)),dict(report=dict(jobs=[dict(case_id='ST-3',adapter='structure')]))])


def test_declared_scope_counts_unavailable_references(jobs):
    scope=summary.declared_scope(jobs)
    assert scope['original_reference_samples']==scope['mechanics_scalar_targets']==95
    assert scope['mechanics_static_targets']==86 and scope['mechanics_modal_targets']==9
    assert scope['unavailable_reference_targets']==2
    assert summary.totals(jobs)['unrun_required']==95


def test_combined_st2_st3_mechanics_accounting_does_not_overwrite_a_family(jobs):
    import isae_suite_st2_mechanics as st2
    scope=summary.declared_scope(st2.plan(ROOT)+jobs)
    assert scope['mechanics_scalar_targets']==186 and scope['mechanics_static_targets']==163
    assert scope['mechanics_modal_targets']==23 and scope['mechanics_jobs']==86


@pytest.mark.parametrize('fault',['target','prediction','mesh_gate','state','missing_check','nonfinite','missing_mesh','provenance'])
def test_changed_static_evidence_is_rejected(jobs,fault):
    job=jobs[1];r=fixture_result(job)
    if fault=='target':r['reference_checks'][0]['expected']+=1
    elif fault=='prediction':r['reference_checks'][0]['predicted']+=1
    elif fault=='mesh_gate':r['mesh_checks'][0]['gate']+=1
    elif fault=='state':r['states'][0]['job']['panels']=32
    elif fault=='missing_check':r['states'][0]['checks'].pop('gravity_force')
    elif fault=='nonfinite':r['states'][0]['checks']['gravity_force']=float('nan')
    elif fault=='missing_mesh':r['mesh_checks'].pop()
    else:r['source_pins_unchanged']=False
    with pytest.raises(ValueError):mechanics.validate_result_contract(job,r)


@pytest.mark.parametrize('fault',['pencil','neutral','shape','identity','missing_root','missing_matrix_check'])
def test_changed_modal_evidence_is_rejected(jobs,fault):
    job=jobs[-1];r=fixture_result(job)
    if fault=='pencil':r['states'][0]['pencil_audits'][0]['left']=.01
    elif fault=='neutral':r['states'][0]['pencil_audits'][0]['neutral_relative']=.1
    elif fault=='shape':r['mesh_checks'][0]['shape_MAC']=.5
    elif fault=='identity':r['mesh_checks'][0]['mutual_shape_assignment']=False
    elif fault=='missing_root':r['states'][0]['frequencies'].pop()
    else:r['states'][0]['pencil_audits'].pop()
    with pytest.raises(ValueError):mechanics.validate_result_contract(job,r)


def test_source_clipped_ordinate_cannot_be_invented(jobs):
    job=next(j for j in jobs if any(not r['source_available'] for r in j['observations']))
    r=fixture_result(job);missing=next(c for c in r['reference_checks'] if not c['source_available'])
    assert missing['predicted'] is None and missing['passed'] is False
    missing['predicted']=0.
    with pytest.raises(ValueError,match='unavailable reference'):mechanics.validate_result_contract(job,r)


@pytest.mark.parametrize('status',['error','timeout','adapter_contract_failure'])
def test_failed_states_keep_their_required_denominator(jobs,status):
    job=jobs[-1];r=apply_reference_acceptance(runner.checked_result(job,dict(status=status)))
    counts=summary.scalar_counts(dict(job,result=r))
    assert counts['required']==counts['failed_job_required']==3 and counts['passed']==0


def test_changed_canonical_setup_is_rejected(jobs):
    changed=deepcopy(jobs[0]);changed['state']['masses_kg']=[1.,1.]
    with pytest.raises(ValueError,match='canonical'):mechanics.verify_reference_sources(ROOT,changed)


def test_helpers_include_every_bounded_executor_and_acceptance_dependency():
    pins=runner.code_pins(ROOT,['st3'])
    assert all('scripts/'+p in pins for p in (*mechanics.EXECUTION_HELPERS,'isae_suite_st3_mechanics.py','summarize-isae-suite.py'))


@pytest.fixture(scope='module')
def prepared(jobs):
    p=read(ROOT/'artifacts/isae/st2-mechanics-summary-20261109/full-run/plan.json')
    p['jobs']=jobs;p['code_sha256']=runner.code_pins(ROOT,['st3'])
    p['execution_policy'].update(adapters=['st3'],cases=['ST-3'],comparison_scopes=[mechanics.SCOPE],timeout_seconds=90.)
    p['selection_scope']['families_without_selected_jobs']=[c['id'] for c in p['catalog']['cases'] if c['id']!='ST-3']
    p['selection_scope'].pop('st2_scope_note')
    return p,runner.report(p,{},ROOT,0.)


def write_run(folder,p,r):
    for name,value in [('plan',p),('report',r),('catalog',p['catalog'])]:
        (folder/(name+'.json')).write_text(json.dumps(value))


def test_full_unrun_scope_loads_without_a_solver(prepared,tmp_path):
    p,r=prepared;write_run(tmp_path,p,r)
    before={k for k in sys.modules if k.startswith('openswing')}
    imported=summary.load_runs([tmp_path]);summary.verify_summary_sources(imported)
    assert len(imported['jobs'])==43 and summary.totals(imported['jobs'])['required']==95
    assert {k for k in sys.modules if k.startswith('openswing')}==before


@pytest.mark.parametrize('fault',['no_opt_in','missing_helper','source_bytes'])
def test_loader_rejects_incomplete_setup_provenance(prepared,tmp_path,fault):
    p,r=deepcopy(prepared)
    if fault=='no_opt_in':
        p['execution_policy']['comparison_scopes']=[];r['execution_policy']=deepcopy(p['execution_policy'])
    elif fault=='missing_helper':
        p['code_sha256'].pop('scripts/verify_st3_static_curves_current.py');r['code_sha256']=deepcopy(p['code_sha256'])
    else:
        p['jobs'][0]['source_pins'][0]['bytes']+=1;r['jobs'][0]['source_pins']=deepcopy(p['jobs'][0]['source_pins'])
    write_run(tmp_path,p,r)
    with pytest.raises(ValueError):summary.load_runs([tmp_path])


def test_full_matching_readable_scope_still_reports_two_unavailable_references(jobs,prepared):
    p,_=prepared
    results={j['id']:runner.checked_result(j,fixture_result(j)) for j in jobs}
    report=runner.report(p,results,ROOT,0.)
    case=next(c for c in report['cases'] if c['id']=='ST-3')
    assert case['status']=='AVAILABLE_REFERENCES_MATCH' and case['output_accounting']['passed']==93
    merged=summary.merge_runs([dict(catalog=p['catalog'],report=report)])
    data=summary.summarize(merged)
    case=next(c for c in data['families'] if c['id']=='ST-3')
    assert case['status']=='AVAILABLE_REFERENCES_MATCH'
    assert case['declared_scope']['numerically_valid_reference_samples']==93
    assert data['full_suite_validated'] is False
    assert '86 static ordinates and 9 modal frequencies in 43 jobs' in summary.markdown(data)


def test_opt_in_replaces_historical_st3_jobs_but_preserves_other_families(jobs,monkeypatch):
    import isae_suite_structure as structure
    import isae_suite_st3_modal as modal
    old=[dict(id='old-st3',case_id='ST-3'),dict(id='keep-st5',case_id='ST-5')]
    monkeypatch.setattr(structure,'plan',lambda root:old)
    monkeypatch.setattr(modal,'plan',lambda root:[dict(id='old-modal',case_id='ST-3')])
    result=runner.plan_jobs(ROOT,['structure','st3_modal','st3'],comparison_scopes=[mechanics.SCOPE])
    assert len(result)==44 and result[0]['id']=='keep-st5'
    assert all(j['adapter']=='st3' for j in result[1:])
