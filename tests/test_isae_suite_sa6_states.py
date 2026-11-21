"""Source, mock and historical saved-algebra tests; no aircraft evaluation."""
from copy import deepcopy
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from scripts import isae_suite_sa6 as sa6
from scripts import isae_suite_sa6_controls as f1
from scripts import isae_suite_sa6_states as state


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


runner=load('sa6_state_runner','run-isae-suite.py')
summary=load('sa6_state_summary','summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():
    return sa6.plan(ROOT,comparison_scopes=(f1.SCOPE,state.SCOPE))


def computed_fixture(job,values=None):
    """Nonidentity sampling and a coupled two-unknown, six-input tangent."""
    values=values or {name:(i+1)*.0001 for i,name in enumerate(state.NAMES)}
    coeff=[[values[c+s] for s in state.SUFFIXES] for c in state.CHANNELS]
    settings=job['settings'];qs=.5*settings['density']*settings['speed']**2*.3871
    c,s=math.cos(math.radians(settings['alpha'])),math.sin(math.radians(settings['alpha']))
    wrench=[[] for _ in range(6)]
    for k in range(6):
        x,y,z,l,m,n=[row[k] for row in coeff]
        column=[qs*(-c*x-s*z),qs*y,qs*(-s*x+c*z),qs*1.524*(-c*l+s*n),qs*.254*m,qs*1.524*(-s*l-c*n)]
        for row,value in zip(wrench,column):row.append(value)
    jac=[[2.,.3],[.2,1.4]];response=[[.1*(k+1) for k in range(6)],[-.03*(k+1) for k in range(6)]]
    partial=[[-state.dot(row,[v[k] for v in response]) for k in range(6)] for row in jac]
    wg=[[.01*(i+1),-.02*(i+1)] for i in range(6)]
    direct=[[wrench[i][k]-state.dot(wg[i],[v[k] for v in response]) for k in range(6)] for i in range(6)]
    sample=[[1.,0.],[.25,.75],[0.,1.]];tr=f1.transform(job);base_wrench=[1.,0.,2.,0.,0.,0.]
    api=dict(method='analytic implicit rigid state derivatives',parameters=list(state.PARAMETERS),units=list(state.UNITS),axes='stability',
        influence_derivative='complete current-wind source, receiver, wake, volume and PG derivatives',
        coefficient_rows=list(state.CHANNELS),coefficients=coeff,distributed_aero_wrench=wrench,
        circulation=[[state.dot(row,[v[k] for v in response]) for k in range(6)] for row in sample],
        circulation_coefficients=deepcopy(response),base_coefficients=[state.dot(row,base_wrench) for row in tr],
        base_residual=1e-14,linear_residuals=[0.]*6,reciprocal_condition=.1,physical_evaluations=1,factorizations=1,panels=3)
    evidence=dict(jacobian=jac,input_partials=partial,coefficient_response=response,wrench_gamma=wg,wrench_direct=direct,
        coefficient_transform=tr,sample=sample,base=dict(gamma=[.1,.2,.3],force=base_wrench[:3],moment=base_wrench[3:],
        residual=1e-14,converged=True,maximum_normal_mach=.1,t=[0.,.5,1.],beam=[1,1,1],positions=[[0.,t,0.] for t in [0.,.5,1.]]))
    result=dict(deepcopy(job),status='computed',numerical_pass=True,sources_unchanged=True,physical_calls=1,factorizations=1,
                operations=dict(state.OPERATIONS),api_result=api,evidence=evidence)
    result['numerical_checks']=state.evidence_checks(job,api,evidence)
    result['reference_checks']=state.reference_checks(job,state.predictions(api))
    result['reference_match']=all(c['passed'] for c in result['reference_checks'])
    return result


def test_default_and_each_opt_in_scope_counts_and_order(jobs):
    default=sa6.plan(ROOT);only=sa6.plan(ROOT,comparison_scopes=(state.SCOPE,))
    assert jobs[:91]==only[:91]==default and len(default)==91
    assert len(only)==179 and sum(j['expected_outputs'] for j in only)==3696
    assert len(jobs)==267 and sum(j['expected_outputs'] for j in jobs)==4224
    assert sum(j['expected_outputs'] for j in default)==528
    assert jobs==sa6.plan(ROOT,comparison_scopes=(state.SCOPE,f1.SCOPE))
    assert jobs[179:]==only[91:]
    assert len({(j['table_path'],n) for j in jobs[179:] for n in j['required_outputs']})==1584
    for job in jobs[179:]:
        base=next(j for j in default if j['id']==job['base_static_job_id'])
        assert job['settings']==base['settings'] and job['driver_path']==base['driver_path']
        assert job.get('source_binding')==base.get('source_binding') and job['static_reference_row']==base['reference_row']
        assert state.validate_record_contract(job)


def test_all_original_tokens_signed_zeros_positions_and_prior_protocol(jobs):
    old=json.loads((ROOT/'artifacts/isae/sa6-state-tangent-20261028/state-comparison-r2/protocol.json').read_text())
    previous={j['id']:j for j in old['analytic_jobs']}
    zeros=negative=0
    for job in jobs[179:]:
        text=(ROOT/job['table_path']).read_text();fields=state.decode(text)
        assert fields==job['reference_row']['fields']
        for obs in previous[job['id']]['observations']:
            f=fields[obs['name']]
            assert text[f['source_character_start_0based']:f['source_character_end_0based']]==obs['expected_token']==f['token']
            assert f['source_line']==obs['source_line'] and f['source_column_1based']==obs['source_column_1based']
            assert f['negative_zero'] is obs['negative_zero']
            assert Decimal(f['exact_decimal_tolerance'])==Decimal(obs['tolerance_decimal'])
            zeros+=f['value']==0.;negative+=f['negative_zero']
    assert zeros==968 and negative==468


def test_planning_no_production_or_numpy():
    code="from pathlib import Path; import sys; from scripts.isae_suite_sa6 import plan; assert len(plan(Path.cwd(),comparison_scopes=('sa6-state-rigid',)))==179; assert not any(n=='numpy' or n=='openswing' or n.startswith('openswing.') for n in sys.modules)"
    r=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('scopes',[('unknown',),(state.SCOPE,state.SCOPE),(f1.SCOPE,state.SCOPE,f1.SCOPE)])
def test_unknown_duplicate_scopes(scopes):
    with pytest.raises(ValueError):sa6.plan(ROOT,comparison_scopes=scopes)


@pytest.mark.parametrize('field',['token','negative_zero','source_line','source_character_end_0based','control','qualifications','operator'])
def test_canonical_source_tampering_rejected(jobs,field):
    job=deepcopy(jobs[179])
    if field=='control':job['settings']['controls']['1']=8.
    elif field=='qualifications':job['qualifications']=[]
    elif field=='operator':job['influence_derivative_convention']='lagged'
    else:
        f=job['reference_row']['fields']['CXu']
        f[field]=('0.00000' if field=='token' else True if field=='negative_zero' else f[field]+1)
    with pytest.raises(ValueError):sa6.verify_state_sources(ROOT,job)


def test_outer_result_only_and_complete_synthetic_contract(jobs):
    job=deepcopy(jobs[179]);job['result']={'status':'timeout'}
    assert sa6.verify_state_sources(ROOT,job)
    job['other']=1
    with pytest.raises(ValueError):sa6.verify_state_sources(ROOT,job)
    job=jobs[179];result=computed_fixture(job)
    assert len(result['numerical_checks'])==13 and all(c['passed'] for c in result['numerical_checks'])
    assert state.validate_result_contract(job,result)
    assert summary.scalar_counts(dict(job,result=result))['required']==36


@pytest.mark.parametrize('fault',['jacobian','partial','response','sample','wrench_gamma','wrench_direct','transform','api_gamma','api_coeff','api_units','api_operator','missing_check','duplicate_ref','detached_ref','counter','gate'])
def test_saved_state_evidence_corruption_rejected(jobs,fault):
    job=jobs[179];r=computed_fixture(job)
    keys={'jacobian':'jacobian','partial':'input_partials','response':'coefficient_response','sample':'sample','wrench_gamma':'wrench_gamma','wrench_direct':'wrench_direct','transform':'coefficient_transform'}
    if fault in keys:r['evidence'][keys[fault]][0][0]+=.1
    elif fault=='api_gamma':r['api_result']['circulation'][0][0]+=.1
    elif fault=='api_coeff':r['api_result']['coefficients'][0][0]+=.1
    elif fault=='api_units':r['api_result']['units'][1]='degree'
    elif fault=='api_operator':r['api_result']['influence_derivative']='lagged'
    elif fault=='missing_check':r['numerical_checks'].pop()
    elif fault=='duplicate_ref':r['reference_checks'][-1]=deepcopy(r['reference_checks'][0])
    elif fault=='detached_ref':r['reference_checks']=state.reference_checks(job,{n:0. for n in state.NAMES})
    elif fault=='counter':r['physical_calls']=2
    elif fault=='gate':r['numerical_gates']['linear_residual']=1.
    with pytest.raises(ValueError):state.validate_result_contract(job,r)


def test_exact_decimal_boundary_and_failure_denominator(jobs):
    job=jobs[179];field=job['reference_row']['fields']['CXu']
    edge=float(Decimal(field['exact_decimal_expected'])+Decimal(field['exact_decimal_tolerance']))
    r=computed_fixture(job,dict.fromkeys(state.NAMES,0.)|{'CXu':edge})
    assert r['reference_checks'][0]['passed']
    checked=runner.checked_result(job,r)
    assert checked['reference_checks'][0]['passed']
    assert summary.scalar_counts(dict(job,result=r))['required']==36
    assert summary.scalar_counts(dict(job,result={'status':'timeout'}))['failed_job_required']==36
    assert summary.scalar_counts(job)['unrun_required']==36
    for flag in ('numerical_pass','numerical_passed','reference_match'):
        with pytest.raises(ValueError):state.validate_result_contract(job,{'status':'timeout',flag:True})


@pytest.mark.parametrize('metric',['linear','base','mach','condition'])
def test_invalid_metric_cannot_hide_behind_another_valid_maximum(jobs,metric):
    job=jobs[179];result=computed_fixture(job)
    if metric=='linear':result['api_result']['linear_residuals'][0]=-1.
    elif metric=='base':result['evidence']['base']['residual']=-1.
    elif metric=='mach':result['evidence']['base']['maximum_normal_mach']=-1.
    else:result['api_result']['reciprocal_condition']=2.
    with pytest.raises(ValueError):state.validate_result_contract(job,result)


@pytest.mark.parametrize('marker',['target_kind','comparison_scope','execution_route','case_id','adapter'])
def test_marker_removal_cannot_relabel_state_scope(jobs,marker):
    job=deepcopy(jobs[179]);job.pop(marker)
    with pytest.raises(ValueError):summary.scalar_counts(job)


def test_runner_scope_selection_resume_and_three_independent_ledgers(jobs,tmp_path):
    assert runner.plan_jobs(ROOT,['sa6'],comparison_scopes=[f1.SCOPE,state.SCOPE])==jobs
    assert 'scripts/isae_suite_sa6_states.py' in runner.code_pins(ROOT,['sa6'])
    assert len(runner.select_jobs(jobs,{'cases':[{'id':'SA-6'}]},['SA-6'],['*:rigid-state']))==88
    for names,adapters in [(['bad'],['sa6']),([state.SCOPE,state.SCOPE],['sa6']),([state.SCOPE],['polars'])]:
        with pytest.raises(ValueError):runner.plan_jobs(ROOT,adapters,comparison_scopes=names)
    path=tmp_path/'plan.json';plan={'execution_policy':{'comparison_scopes':[state.SCOPE]}}
    path.write_text(json.dumps(plan));runner.validate_resume_plan(path,plan,True)
    with pytest.raises(ValueError):runner.validate_resume_plan(path,{'execution_policy':{'comparison_scopes':[f1.SCOPE]}},True)
    scopes=summary.declared_scope(jobs)['sa6_comparison_scopes']
    assert {k:(v['scalar_slots'],v['distinct_native_cells']) for k,v in scopes.items()}=={'static':(528,264),f1.SCOPE:(528,264),state.SCOPE:(3168,1584)}
    assert summary.declared_scope(jobs)['original_reference_samples']==44
    assert len(summary.sa6_tables(jobs))==len(summary.sa6_tables(jobs,controls=True))==len(summary.sa6_tables(jobs,states=True))==4
    tables=summary.sa6_tables(jobs,states=True);assert all(len(t['channels'])==36 for t in tables)
    mesh=sa6.mesh_diagnostics(jobs,{})
    assert len(mesh)==132 and Counter(x['comparison_scope'] for x in mesh)=={'static':44,f1.SCOPE:44,state.SCOPE:44}


def test_selected_state_summary_and_mesh_never_substitute_scope(jobs):
    coarse,fine=deepcopy(jobs[179:181]);coarse['result']={'status':'timeout'}
    assert summary.sa6_tables([coarse],states=True)==[]
    assert summary.sa6_tables([fine],states=True)[0]['scalar_counts']['required']==36
    with pytest.raises(ValueError):summary.sa6_tables([fine,deepcopy(fine)],states=True)
    catalog={'cases':[dict(id=n,path=n,models=[],reference_candidates=[]) for n in sorted(summary.FAMILIES)],'counts':{}}
    data=summary.summarize(dict(catalog=catalog,jobs=[coarse],runtime={},kernel_pins={},helper_pins={},source_provenance={}))
    assert data['scalar_counts']['required']==data['scalar_counts']['failed_job_required']==36
    assert len(data['families'])==41 and not data['full_suite_validated']
    assert not next(r for r in data['families'] if r['id']=='SA-6')['complete_family_reproduction']
    assert len(data['sa6_mesh_diagnostics'])==1 and data['sa6_mesh_diagnostics'][0]['status']=='UNAVAILABLE'
    assert data['fine_grid_sa6_control_derivatives']==data['fine_grid_sa6_coefficients']==[]


@pytest.mark.parametrize('fault',['none','missing_option','missing_helper','unknown_option','duplicate_option','setup','claim'])
def test_summary_canonical_once_and_explicit_frozen_option(jobs,tmp_path,monkeypatch,fault):
    root=tmp_path/'root';stage=tmp_path/'run';(root/'openswing').mkdir(parents=True);(root/'scripts').mkdir();stage.mkdir()
    files=[root/'openswing/kernel.py']+[root/'scripts'/n for n in ['isae_suite_sa6.py','isae_suite_sa6_controls.py','isae_suite_sa6_states.py']]
    for path in files:path.write_text('# isolated source verification fixture\n')
    rows=deepcopy(jobs[179:181])
    for row in rows:row['sources']=[]
    original=deepcopy(rows);calls=[]
    def canonical(actual_root,*,comparison_scopes=()):
        assert actual_root==root and comparison_scopes==(state.SCOPE,)
        calls.append(actual_root);return deepcopy(original)
    monkeypatch.setattr(summary.importlib,'import_module',lambda name:SimpleNamespace(plan=canonical))
    if fault=='setup':rows[0]['settings']['controls']['1']=8.
    if fault=='claim':rows[0]['historical_producer_authenticated']=True
    cases=[dict(id=n,path=n,models=[],reference_candidates=[]) for n in sorted(summary.FAMILIES)]
    catalog=dict(repository='original',revision='frozen',sources=[],models=[],cases=cases,counts=dict(families=41,models=0,parse={}))
    pins={p.relative_to(root).as_posix():summary.pin(p)['sha256'] for p in files}
    if fault=='missing_helper':pins.pop('scripts/isae_suite_sa6_states.py')
    scopes=[] if fault=='missing_option' else [state.SCOPE]
    if fault=='unknown_option':scopes+=['bad']
    if fault=='duplicate_option':scopes*=2
    policy=dict(comparison_scopes=scopes)
    plan=dict(catalog=catalog,jobs=rows,runtime={'python':'same'},code_sha256=pins,execution_policy=policy)
    report=dict(repository='original',revision='frozen',runtime=plan['runtime'],current_code_unchanged=True,
        jobs=[dict(row,result=None) for row in rows],code_sha256=pins,execution_policy=policy)
    for name,value in [('catalog',catalog),('plan',plan),('report',report)]: (stage/(name+'.json')).write_text(json.dumps(value))
    if fault=='none':
        merged=summary.load_runs([stage],root);assert calls==[root] and summary.totals(merged['jobs'])['unrun_required']==72
        summary.verify_summary_sources(merged)
    else:
        with pytest.raises(ValueError):summary.load_runs([stage],root)


@pytest.mark.parametrize('variant',['15c','20c','30c','35c'])
@pytest.mark.parametrize('mesh',[64,128])
def test_historical_saved_algebra_is_supported_without_current_physics(jobs,variant,mesh):
    # Deliberately an old saved-data fixture, not a claim that old physics ran
    # under current helper/kernel pins. Current source metadata is synthetic.
    job=next(j for j in jobs[179:] if f'_{variant}:' in j['id'] and j['row_index']==10 and j['settings']['panels']==mesh)
    folder=ROOT/'artifacts/isae/sa6-state-tangent-20261028';path=folder/'state-comparison-r2/jobs'/hashlib.sha256(job['id'].encode()).hexdigest()[:20]/'result.json'
    ledger={r['path']:r for r in json.loads((folder/'analysis/summary.json').read_text())['source_pins']}
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ledger[path.relative_to(ROOT).as_posix()]['sha256']
    old=json.loads(raw);api=old['api_result'];e=deepcopy(old['evidence']);n=len(e['jacobian'])
    assert n==len(api['circulation']) and api['circulation']==api['circulation_coefficients']
    e['sample']=[[float(i==j) for j in range(n)] for i in range(n)]
    r=dict(deepcopy(job),status='computed',numerical_pass=True,sources_unchanged=True,physical_calls=1,factorizations=1,
        operations=dict(state.OPERATIONS),api_result=api,evidence=e)
    r['numerical_checks']=state.evidence_checks(job,api,e);r['reference_checks']=state.reference_checks(job,state.predictions(api))
    r['reference_match']=all(c['passed'] for c in r['reference_checks'])
    assert state.validate_result_contract(job,r)
    assert [c['passed'] for c in r['reference_checks']]==[c['passed'] for c in old['reference_checks']]


def test_worker_entry_mock_binds_six_parameters_and_sampling(jobs,monkeypatch):
    import numpy as np
    job=jobs[179];fixture=computed_fixture(job);e=fixture['evidence'];calls=[];parsed=[]
    model=SimpleNamespace(diagnostics=[],constants=[0.,job['settings']['density']],reference=np.array([[.3871,.254,1.524],[0.,0.,0.]]))
    def parse(text,**options):parsed.append((text,options));return model
    data=dict(gamma=np.array(e['base']['gamma']),basis=SimpleNamespace(sample=np.array(e['sample'])),
              p={k:np.array(v) for k,v in [('t',[0.,.5,1.]),('beam',[1,1,1]),('rm',[[0.,t,0.] for t in [0.,.5,1.]])]})
    def analytic(actual_model,condition,**options):
        calls.append((actual_model,condition,options))
        audit={k:np.array(e[k]) for k in ['jacobian','input_partials','coefficient_response','wrench_gamma','wrench_direct','coefficient_transform']}
        audit.update(fields=SimpleNamespace(circulation_aero=data),base=dict(distributed_aero_force=np.array(e['base']['force']),
            distributed_aero_moment=np.array(e['base']['moment']),residual=1e-14,converged=True,strips=[dict(normal_mach=.1)]))
        options['_audit'](audit);return deepcopy(fixture['api_result'])
    modules=dict(asw=SimpleNamespace(parse_asw=parse),aero=SimpleNamespace(FlightCondition=lambda **kw:SimpleNamespace(**kw)),
                 rigid_derivatives=SimpleNamespace(rigid_state_derivatives=analytic))
    for name,module in modules.items():
        module.__file__=str(ROOT/'openswing'/(name+'.py'));module.__name__='openswing.'+name
    monkeypatch.setitem(sys.modules,'openswing',SimpleNamespace(**modules))
    for name,module in modules.items():monkeypatch.setitem(sys.modules,'openswing.'+name,module)
    api,evidence=state._execute(ROOT,job)
    assert len(calls)==len(parsed)==1 and parsed[0][0]==(ROOT/job['model_path']).read_text()
    _,condition,options=calls[0]
    assert condition.controls=={1:4.} and condition.speed==20. and condition.alpha==12.
    assert options['parameters']==list(state.PARAMETERS) and options['panels']==64 and options['circulation_method']=='auto'
    assert all(c['passed'] for c in state.evidence_checks(job,api,evidence))
