"""Source-only registration and corruption checks; no aircraft evaluations."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from scripts import isae_suite_sa6 as sa6
from scripts import isae_suite_sa6_controls as f1


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


runner = load('sa6_control_runner', 'run-isae-suite.py')
summary = load('sa6_control_summary', 'summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():
    return sa6.plan(ROOT, comparison_scopes=(f1.SCOPE,))


def computed_fixture(job, values=None):
    """Internally consistent synthetic saved algebra, never an aircraft solve."""
    values = values or {name:0. for name in f1.NAMES}
    x,y,z,l,m,n = [values[name] for name in f1.NAMES]
    s = job['settings']; qs = .5*s['density']*s['speed']**2*.3871
    c,sn = math.cos(math.radians(s['alpha'])), math.sin(math.radians(s['alpha']))
    wrench = [qs*(-c*x-sn*z),qs*y,qs*(-sn*x+c*z),qs*1.524*(-c*l+sn*n),qs*.254*m,qs*1.524*(-sn*l-c*n)]
    base_wrench = [1.,0.,2.,0.,0.,0.]
    tr = f1.transform(job)
    api = dict(method='analytic implicit rigid control derivatives', controls=[1], units='per file flap setting',
        axes='stability', coefficient_rows=list(f1.CHANNELS), coefficients=[[f1.dot(row,wrench)] for row in tr],
        distributed_aero_wrench=[[v] for v in wrench], circulation=[[1.]], circulation_coefficients=[[1.]],
        base_coefficients=[f1.dot(row,base_wrench) for row in tr], base_residual=1e-14, linear_residuals=[0.],
        reciprocal_condition=1., physical_evaluations=1, factorizations=1, panels=1)
    evidence = dict(jacobian=[[1.]], input_partials=[[-1.]], coefficient_response=[[1.]],
        wrench_gamma=[[v] for v in wrench], wrench_direct=[[0.] for _ in range(6)], coefficient_transform=tr,
        sample=[[1.]], surface=[dict(normal=[0.,0.,1.],section_normal=[0.,0.,1.],c=[1.,0.,0.],s=[0.,1.,0.],
            velocity=[20.,0.,0.],cp_velocity=[20.,0.,0.],position=[0.,.5,0.],profile_arm=[.1,0.,0.],
            ds=1.,chord=.254,slope=6.28,dCLdF1=-.04,dCDdF1=0.,dCMdF1=0.,tangency=0.)],
        base=dict(gamma=[.1],force=base_wrench[:3],moment=base_wrench[3:],residual=1e-14,
                  converged=True,maximum_normal_mach=.1))
    result = dict(deepcopy(job), status='computed', numerical_pass=True, sources_unchanged=True,
        physical_calls=1,factorizations=1,operations=dict(f1.OPERATIONS),api_result=api,evidence=evidence)
    result['numerical_checks'] = f1.evidence_checks(job,api,evidence)
    result['reference_checks'] = f1.reference_checks(job,{name:row[0] for name,row in zip(f1.NAMES,api['coefficients'])})
    result['reference_match'] = all(c['passed'] for c in result['reference_checks'])
    return result


def test_default_scope_preserved_and_all_f1_cells_are_opt_in(jobs):
    static = sa6.plan(ROOT)
    assert jobs[:91] == static and len(jobs) == 179
    extra = jobs[91:]
    assert sum(j['expected_outputs'] for j in static) == 528
    assert sum(j['expected_outputs'] for j in extra) == 528
    assert len({(j['table_path'],name) for j in extra for name in j['required_outputs']}) == 264
    assert {j['settings']['panels'] for j in extra} == {64,128}
    for job in extra:
        base = next(j for j in static if j['id'] == job['base_static_job_id'])
        assert job['settings'] == base['settings']
        assert job['driver_path'] == base['driver_path']
        assert job.get('source_binding') == base.get('source_binding')
        assert job['static_reference_row'] == base['reference_row']
        assert job['reference_row']['fields'] == f1.decode((ROOT/job['table_path']).read_text())
        assert f1.validate_record_contract(job)


def test_planning_does_not_import_production_or_numpy():
    code = "from pathlib import Path; import sys; from scripts.isae_suite_sa6 import plan; assert len(plan(Path.cwd(),comparison_scopes=('sa6-f1-rigid',)))==179; assert not any(n=='numpy' or n=='openswing' or n.startswith('openswing.') for n in sys.modules)"
    completed = subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
    assert completed.returncode == 0,completed.stderr


@pytest.mark.parametrize('scopes',[('unknown',),(f1.SCOPE,f1.SCOPE)])
def test_unknown_or_duplicate_scope_rejected(scopes):
    with pytest.raises(ValueError): sa6.plan(ROOT,comparison_scopes=scopes)


def test_source_line_column_and_signed_tokens_are_exact(jobs):
    for job in jobs[91::2]:
        lines=(ROOT/job['table_path']).read_text().splitlines()
        for field in job['reference_row']['fields'].values():
            assert lines[field['source_line']-1][field['source_column_1based']-1:].split()[0] == field['token']
            assert Decimal(field['exact_decimal_tolerance']) == Decimal(5).scaleb(Decimal(field['token']).as_tuple().exponent-1)


@pytest.mark.parametrize('field',['control','token','source_line','qualifications','route'])
def test_canonical_source_tampering_rejected(jobs,field):
    job=deepcopy(jobs[91])
    if field=='control': job['settings']['controls']['1']=8.
    elif field=='token': job['reference_row']['fields']['CLdF1']['token']='1.0'
    elif field=='source_line': job['reference_row']['fields']['CLdF1']['source_line']+=1
    elif field=='qualifications': job['historical_producer_authenticated']=True
    else: job['execution_route']='rigid_static_coefficients'
    with pytest.raises(ValueError): sa6.verify_control_sources(ROOT,job)


def test_control_source_verifier_outer_result_only(jobs):
    job=deepcopy(jobs[91]);job['result']={'status':'timeout'}
    assert sa6.verify_control_sources(ROOT,job)
    job['extra']=True
    with pytest.raises(ValueError): sa6.verify_control_sources(ROOT,job)


def test_synthetic_result_contract_and_independent_summary(jobs):
    job=jobs[91];result=computed_fixture(job)
    assert f1.validate_result_contract(job,result)
    checked=runner.checked_result(job,deepcopy(result))
    assert checked['status']=='computed' and checked['output_accounting']['numerically_valid']==6
    counts=summary.scalar_counts(dict(job,result=result))
    assert counts['required']==counts['numerically_valid_finite']==6
    assert counts['passed']==1  # Original zero CYdF1 is required, not excluded.


@pytest.mark.parametrize('corruption',['missing_check','duplicate_check','gamma','J','direct_wrench','CP','normal',
    'transform','output','partial','operations','status_claim','source_binding','reference_token'])
def test_saved_tangent_corruption_cannot_pass(jobs,corruption):
    job=jobs[91];result=computed_fixture(job)
    if corruption=='missing_check': result['numerical_checks'].pop()
    elif corruption=='duplicate_check': result['numerical_checks'][-1]=deepcopy(result['numerical_checks'][0])
    elif corruption=='gamma': result['api_result']['circulation'][0][0]=2.
    elif corruption=='J': result['evidence']['jacobian'][0][0]=2.
    elif corruption=='direct_wrench': result['evidence']['wrench_direct'][0][0]=1.
    elif corruption=='CP': result['evidence']['surface'][0]['cp_velocity'][2]=1.
    elif corruption=='normal': result['evidence']['surface'][0]['normal'][0]=1.
    elif corruption=='transform': result['evidence']['coefficient_transform'][0][0]=1.
    elif corruption=='output': result['reference_checks'][0]['predicted']=1.
    elif corruption=='partial': result['evidence']['input_partials'][0][0]=1.
    elif corruption=='operations': result['operations']['perturbed_calls']=1
    elif corruption=='status_claim': result['status']='error'
    elif corruption=='source_binding': result.pop('source_binding')
    else: result['reference_checks'][0]['expected_token']='0.0'
    with pytest.raises(ValueError): f1.validate_result_contract(job,result)
    with pytest.raises(ValueError): summary.scalar_counts(dict(job,result=result))
    assert runner.checked_result(job,result)['status']=='adapter_contract_failure' or corruption=='status_claim'


def test_failed_or_timed_out_worker_keeps_all_targets(jobs):
    job=jobs[91]
    for result in ({'status':'timeout'}, {'status':'error','numerical_pass':False,'reference_match':False,
            'reference_checks':f1.reference_checks(job,reason='Retained failure')}):
        assert f1.validate_result_contract(job,result)
        counts=summary.scalar_counts(dict(job,result=result))
        assert counts['required']==counts['failed_job_required']==6 and counts['passed']==0


def test_decimal_endpoints_keep_original_tolerance(jobs):
    job=deepcopy(jobs[91]);field=job['reference_row']['fields']['CXdF1']
    # Contract-level decimal endpoint; no synthetic source amendment is executed.
    field.update(token='-0.129671',value=-.129671,tolerance=5e-7,
                 exact_decimal_expected='-0.129671',exact_decimal_tolerance='5E-7')
    checks=f1.reference_checks(job,{'CXdF1':-.1296705})
    assert checks[0]['passed'] and summary.precision_pass(checks[0],exact_decimal=True)
    assert not summary.precision_pass(checks[0])
    result={'status':'numerical_failure','numerical_pass':False,'reference_match':False,'reference_checks':checks}
    checked=runner.checked_result(job,result)
    assert checked['status']=='numerical_failure'
    assert f1.reference_checks(job,{'CXdF1':-.129670499999})[0]['passed'] is False


def test_run_dispatch_has_one_analytic_call_and_no_stale_static_artifact_dependency(jobs,monkeypatch):
    job=jobs[91];fixture=computed_fixture(job);calls=[]
    def execute(root,record):
        assert root==ROOT and record==job
        calls.append(record['id']);return fixture['api_result'],fixture['evidence']
    monkeypatch.setattr(f1,'_execute',execute)
    result=sa6.run(ROOT,job)
    assert len(calls)==1 and result['status']=='computed'
    assert f1.validate_result_contract(job,result)


def test_numerical_exception_is_retained_without_retry(jobs,monkeypatch):
    calls=[]
    def execute(*args):
        calls.append(1);raise RuntimeError('Retained local-flow failure')
    monkeypatch.setattr(f1,'_execute',execute)
    result=sa6.run(ROOT,jobs[91])
    assert len(calls)==1 and result['status']=='error' and len(result['reference_checks'])==6
    assert result['physical_calls']==1 and not result['numerical_pass']


def test_numerical_entry_uses_existing_audit_fields_and_literal_settings(jobs,monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    job=jobs[91];fixture=computed_fixture(job);e=fixture['evidence'];surface=e['surface'][0]
    beam=SimpleNamespace(index=1,value=lambda name,t:surface[name])
    model=SimpleNamespace(diagnostics=[],constants=[9.81,1.2256],reference=np.array([[.3871,.254,1.524],[0.,0.,0.]]),beams=[beam])
    parsed=[];calls=[]
    def parse(text,**options):
        parsed.append((text,options));return model
    p={key:np.asarray([surface[key]]) for key in ('normal','section_normal','c','s','ds','chord','slope','profile_arm')}
    p.update(rm=np.asarray([surface['position']]),t=np.array([.5]),beam=np.array([1]))
    data=dict(p=p,gamma=np.array([.1]),velocity=np.asarray([surface['velocity']]),
        cp_velocity=np.asarray([surface['cp_velocity']]),tangency=np.array([surface['tangency']]),
        basis=SimpleNamespace(sample=np.array([[1.]])))
    def analytic(actual_model,condition,**options):
        calls.append((actual_model,condition,options))
        audit={key:np.asarray(e[key]) for key in ('jacobian','input_partials','coefficient_response','wrench_gamma','wrench_direct','coefficient_transform')}
        audit.update(fields=SimpleNamespace(circulation_aero=data),base=dict(distributed_aero_force=np.array([1.,0.,2.]),
            distributed_aero_moment=np.zeros(3),residual=1e-14,converged=True,strips=[dict(normal_mach=.1)]))
        options['_audit'](audit);return deepcopy(fixture['api_result'])
    modules=dict(asw=SimpleNamespace(parse_asw=parse),aero=SimpleNamespace(FlightCondition=lambda **kw:SimpleNamespace(**kw)),
                 rigid_derivatives=SimpleNamespace(rigid_control_derivatives=analytic))
    for name,module in modules.items():
        module.__file__=str(ROOT/'openswing'/(name+'.py'))
        module.__name__='openswing.'+name
    monkeypatch.setitem(sys.modules,'openswing',SimpleNamespace(**modules))
    for name,module in modules.items():monkeypatch.setitem(sys.modules,'openswing.'+name,module)
    api,evidence=f1._execute(ROOT,job)
    assert len(calls)==len(parsed)==1 and parsed[0][0]==(ROOT/job['model_path']).read_text()
    assert parsed[0][1]==dict(beam_interpolation='natural-v1')
    _,condition,options=calls[0]
    assert condition.controls=={1:4.} and condition.speed==20. and condition.alpha==12.
    assert options['controls']==[1] and options['panels']==64 and options['circulation_method']=='auto'
    assert all(check['passed'] for check in f1.evidence_checks(job,api,evidence))


@pytest.mark.parametrize('fault',['none','missing_option','missing_helper','setup','claim'])
def test_summary_loader_binds_opt_in_canonical_context_once(jobs,tmp_path,monkeypatch,fault):
    from types import SimpleNamespace
    root=tmp_path/'root';stage=tmp_path/'run';(root/'openswing').mkdir(parents=True);(root/'scripts').mkdir();stage.mkdir()
    files=[root/'openswing/kernel.py',root/'scripts/isae_suite_sa6.py',root/'scripts/isae_suite_sa6_controls.py']
    for path in files:path.write_text('# isolated source verification fixture\n')
    rows=deepcopy(jobs[91:93])
    for row in rows:row['sources']=[]
    original=deepcopy(rows);calls=[]
    def canonical(actual_root,*,comparison_scopes=()):
        assert actual_root==root and comparison_scopes==(f1.SCOPE,)
        calls.append(actual_root);return deepcopy(original)
    monkeypatch.setattr(summary.importlib,'import_module',lambda name:SimpleNamespace(plan=canonical))
    if fault=='setup': rows[0]['settings']['controls']['1']=8.
    if fault=='claim': rows[0]['historical_producer_authenticated']=True
    cases=[dict(id=name,path=name,models=[],reference_candidates=[]) for name in sorted(summary.FAMILIES)]
    catalog=dict(repository='original',revision='frozen',sources=[],models=[],cases=cases,counts=dict(families=41,models=0,parse={}))
    pins={path.relative_to(root).as_posix():summary.pin(path)['sha256'] for path in files}
    if fault=='missing_helper':pins.pop('scripts/isae_suite_sa6_controls.py')
    policy={} if fault=='missing_option' else dict(comparison_scopes=[f1.SCOPE])
    plan=dict(catalog=catalog,jobs=rows,runtime={'python':'same'},code_sha256=pins,execution_policy=policy)
    report=dict(repository='original',revision='frozen',runtime=plan['runtime'],current_code_unchanged=True,
                jobs=[dict(row,result=None) for row in rows],code_sha256=pins,execution_policy=policy)
    for name,value in [('catalog',catalog),('plan',plan),('report',report)]: (stage/(name+'.json')).write_text(json.dumps(value))
    if fault=='none':
        merged=summary.load_runs([stage],root)
        assert calls==[root] and len(merged['jobs'])==2
        assert summary.totals(merged['jobs'])['unrun_required']==12
        summary.verify_summary_sources(merged)
    else:
        with pytest.raises(ValueError):summary.load_runs([stage],root)


def test_runner_opt_in_selection_resume_and_helper_pins(jobs,tmp_path):
    assert len(runner.plan_jobs(ROOT,['sa6']))==91
    selected=runner.plan_jobs(ROOT,['sa6'],comparison_scopes=[f1.SCOPE])
    assert selected==jobs
    assert 'scripts/isae_suite_sa6_controls.py' in runner.code_pins(ROOT,['sa6'])
    assert len(runner.select_jobs(selected,{'cases':[{'id':'SA-6'}]},['SA-6'],['*:rigid-F1']))==88
    for names,adapters in [(['bad'],['sa6']),([f1.SCOPE,f1.SCOPE],['sa6']),([f1.SCOPE],['polars'])]:
        with pytest.raises(ValueError): runner.plan_jobs(ROOT,adapters,comparison_scopes=names)
    path=tmp_path/'plan.json';plan={'execution_policy':{'comparison_scopes':[f1.SCOPE]}}
    path.write_text(json.dumps(plan));runner.validate_resume_plan(path,plan,True)
    with pytest.raises(ValueError):runner.validate_resume_plan(path,{'execution_policy':{}},True)


def test_summary_separates_static_and_derivative_tables_and_native_cells(jobs):
    assert len(summary.sa6_tables(jobs))==len(summary.sa6_tables(jobs,controls=True))==4
    scope=summary.declared_scope(jobs)
    assert scope['original_reference_samples']==44
    assert scope['sa6_comparison_scopes']['static']['distinct_native_cells']==264
    assert scope['sa6_comparison_scopes'][f1.SCOPE]['distinct_native_cells']==264
    assert scope['sa6_comparison_scopes']['static']['scalar_slots']==528
    assert scope['sa6_comparison_scopes'][f1.SCOPE]['scalar_slots']==528
    records=runner.summarize({'cases':[{'id':'SA-6','path':'sa6','models':[],'reference_candidates':[]}]},jobs,{})
    assert records[0]['comparison_scopes']['static']['required']==528
    assert records[0]['comparison_scopes'][f1.SCOPE]['required']==528
    assert not records[0]['complete_family_reproduction']


@pytest.mark.parametrize('controls',[False,True])
def test_selected_summary_never_requires_unselected_jobs_or_substitutes_coarse(jobs,controls):
    offset=91 if controls else 0
    coarse,fine=deepcopy(jobs[offset:offset+2])
    assert summary.sa6_tables([coarse],controls=controls)==[]
    tables=summary.sa6_tables([fine],controls=controls)
    assert len(tables)==1 and tables[0]['rows']==1 and tables[0]['scalar_counts']['required']==6
    assert tables[0]['table_paths']==[fine['table_path']]
    with pytest.raises(ValueError):summary.sa6_tables([fine,deepcopy(fine)],controls=controls)
    invalid=deepcopy(fine);invalid['settings']['panels']=256
    with pytest.raises(ValueError):summary.sa6_tables([invalid],controls=controls)
    coarse['result']={'status':'timeout'}
    catalog={'cases':[dict(id=name,path=name,models=[],reference_candidates=[]) for name in sorted(summary.FAMILIES)],'counts':{}}
    data=summary.summarize(dict(catalog=catalog,jobs=[coarse],runtime={},kernel_pins={},helper_pins={},source_provenance={}))
    assert data['scalar_counts']['required']==data['scalar_counts']['failed_job_required']==6
    family=next(row for row in data['families'] if row['id']=='SA-6')
    assert family['declared_scope']['original_reference_samples']==1
    assert not family['complete_family_reproduction'] and not data['full_suite_validated']


@pytest.mark.parametrize('field',['target_kind','comparison_scope','execution_route','case_id','adapter'])
def test_scope_marker_removal_cannot_relabel_derivatives(jobs,field):
    job=deepcopy(jobs[91]);job.pop(field)
    with pytest.raises(ValueError):summary.scalar_counts(job)
