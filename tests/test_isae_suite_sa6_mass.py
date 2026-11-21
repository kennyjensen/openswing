"""Source and synthetic tensor registration checks; no original geometry/solves."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from scripts import isae_suite_sa6 as sa6
from scripts import isae_suite_sa6_mass as mass


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


runner=load('sa6_mass_runner','run-isae-suite.py')
summary=load('sa6_mass_summary','summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():
    return sa6.plan(ROOT,comparison_scopes=(mass.SCOPE,))


def computed_fixture(job,*,uniform=False):
    """Explicit synthetic panel arrays; no parser, mesher or original-model call."""
    import numpy as np
    rho=job['settings']['density'];chord=.254
    edges=np.array(mass.declared_nodes(job));n=len(edges)-1
    if uniform:edges=np.linspace(-.762,.762,n+1)
    ds=np.diff(edges)
    ys=.5*(np.sqrt(np.maximum(0.,(edges[:-1]+.762)*(edges[1:]+.762)))-np.sqrt(np.maximum(0.,(.762-edges[:-1])*(.762-edges[1:]))))
    rm=np.column_stack((np.zeros(n),ys,np.zeros(n)))
    r0=rm.copy();r1=rm.copy();r0[:,1]=edges[:-1];r1[:,1]=edges[1:]
    a=math.radians(4.);c,s=math.cos(a),math.sin(a)
    frame=np.tile([[c,0,s],[0,1,0],[-s,0,c]],(n,1,1));normal=frame[:,:,2];span=frame[:,:,1]
    pos=rm+chord*.5*frame[:,:,0];weights=rho*np.pi/4*chord**2*ds
    rot=rho*np.pi/128*chord**4*ds
    references={'origin':[0.,0.,0.],'reported_centroid':[0.,0.,0.],'probe':(1.524*np.array([.37,-.21,.13])).tolist()}
    tensors={}
    for name,ref in references.items():
        directions=np.concatenate((normal,np.cross(pos-ref,normal)),axis=1)
        mat=np.einsum('n,ni,nj->ij',weights,directions,directions)
        mat[3:,3:]+=np.einsum('n,ni,nj->ij',rot,span,span)
        tensors[name]=dict(reference=ref,real_spatial_matrix=np.zeros((6,6)).tolist(),apparent_spatial_matrix=mat.tolist())
    evidence=dict(density=rho,body_added_mass_factor=1.,reference_span=1.524,reported_centroid=[0.,0.,0.],physical_real_cg=None,real_mass=0.,
        real_records=[dict(mass=np.zeros(n).tolist(),position=rm.tolist(),inertia=np.zeros((n,3,3)).tolist(),spin=np.zeros((n,3)).tolist())],
        apparent_records=[dict(kind='surface',mass=weights.tolist(),position=pos.tolist(),normal=normal.tolist(),span=span.tolist(),rotational_mass=rot.tolist())],
        tensors=tensors,geometry=dict(beam_count=1,nonlifting_beams=0,body_panels=[],lifting_panels=[dict(beam=1,rm=rm.tolist(),r0=r0.tolist(),r1=r1.tolist(),
            ds=ds.tolist(),frame=frame.tolist(),chord=[chord]*n,xax=[0.]*n)]),
        operations=dict(aerodynamic_calls=0,nonlinear_solves=0,derivative_factorizations=0,real_element_assemblies=1,
            tensor_reference_evaluations=2,real_matrix_assemblies=2,apparent_matrix_assemblies=2),
        discretization='Synthetic fixture only',centroid_qualification='Numeric reporting coordinate; physical real CG remains None.')
    result=dict(deepcopy(job),status='computed',sources_unchanged=True,numerical_pass=True,physical_calls=0,factorizations=0,
                operations=dict(mass.OPERATIONS),evidence=evidence)
    result['numerical_checks']=mass.evidence_checks(job,evidence)
    result['reference_checks']=mass.reference_checks(job,mass.tensor_math.tensor_predictions(evidence))
    result['reference_match']=all(c['passed'] for c in result['reference_checks'])
    return result


def test_default_each_scope_and_all_ledgers(jobs):
    default=sa6.plan(ROOT);all_jobs=sa6.plan(ROOT,comparison_scopes=('sa6-state-rigid',mass.SCOPE,'sa6-f1-rigid'))
    assert jobs[:91]==all_jobs[:91]==default and len(default)==91
    assert sum(j['expected_outputs'] for j in default)==528
    assert len(jobs)==179 and sum(j['expected_outputs'] for j in jobs)==3432
    assert len(all_jobs)==355 and sum(j['expected_outputs'] for j in all_jobs)==7128
    assert all_jobs[-88:]==jobs[91:]
    assert len({(j['table_path'],n) for j in jobs[91:] for n in j['required_outputs']})==1452
    scopes=summary.declared_scope(all_jobs)['sa6_comparison_scopes']
    assert {s:v['scalar_slots'] for s,v in scopes.items()}=={'static':528,'sa6-f1-rigid':528,'sa6-state-rigid':3168,mass.SCOPE:2904}
    assert scopes[mass.SCOPE]['distinct_native_cells']==1452
    assert Counter(r['comparison_scope'] for r in sa6.mesh_diagnostics(all_jobs,{}))==dict.fromkeys(scopes,44)


def test_all_original_cells_positions_signed_zero_and_tiny_values(jobs):
    catalog=json.loads((ROOT/mass.CATALOG).read_text());by_path={f['path']:f for f in catalog['files']}
    zeros=tiny=negative_zero=0
    for job in jobs[91:]:
        source=(ROOT/job['table_path']).read_text();original=by_path[job['table_path']]
        assert mass.decode(source)==job['reference_row']['fields']
        assert job['reported_centroid']==[0.,0.,0.] and job['physical_real_cg_expected'] is None
        assert len(job['tensor_centroid_context'])==9
        for obs in original['observations']:
            f=job['reference_row']['fields'][obs['label']]
            assert source[f['source_character_start_0based']:f['source_character_end_0based']]==f['token']==obs['token']
            assert f['source_line']==obs['line'] and f['source_column_1based']==obs['column_1based']
            assert Decimal(f['exact_decimal_tolerance'])==Decimal(obs['half_printed_unit'])
            v=Decimal(f['token']);zeros+=v==0;tiny+=0<abs(v)<Decimal('1e-8');negative_zero+=f['negative_zero']
    assert (zeros,tiny,negative_zero)==(1320,616,0)
    assert min(Decimal(f['exact_decimal_tolerance']) for j in jobs[91:] for f in j['reference_row']['fields'].values())==Decimal('5e-41')


def test_planning_imports_no_production_or_numpy():
    code="from pathlib import Path; import sys; from scripts.isae_suite_sa6 import plan; assert len(plan(Path.cwd(),comparison_scopes=('sa6-mass-rigid',)))==179; assert not any(n=='numpy' or n=='openswing' or n.startswith('openswing.') for n in sys.modules)"
    r=subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('fault',['token','precision','source_line','normalization','centroid','controls','source_binding','qualifications'])
def test_source_or_reporting_tampering_rejected(jobs,fault):
    job=deepcopy(jobs[91]);f=job['reference_row']['fields']['apparent_mass.yy']
    if fault=='token':f['token']='0.000'
    elif fault=='precision':f['exact_decimal_tolerance']='0.01'
    elif fault=='source_line':f['source_line']+=1
    elif fault=='normalization':job['tensor_axes']='stability'
    elif fault=='centroid':job['reporting_reference_is_physical_centroid']=True
    elif fault=='controls':job['settings']['controls']['1']=8.
    elif fault=='source_binding':job['source_binding']['control']['token']='8'
    else:job['qualifications']=[]
    with pytest.raises(ValueError):sa6.verify_mass_sources(ROOT,job)


def test_complete_synthetic_evidence_and_no_flow_call(jobs,monkeypatch):
    job=jobs[91];fixture=computed_fixture(job)
    assert all(c['passed'] for c in fixture['numerical_checks'])
    assert mass.validate_result_contract(job,fixture)
    calls=[]
    def execute(root,actual_job):calls.append(actual_job['id']);return deepcopy(fixture['evidence'])
    monkeypatch.setattr(mass,'_execute',execute)
    result=sa6.run(ROOT,job)
    assert calls==[job['id']] and mass.validate_result_contract(job,result)
    assert result['physical_calls']==result['factorizations']==0 and result['operations']==mass.OPERATIONS
    assert runner.checked_result(job,result)['numerical_pass']
    assert summary.scalar_counts(dict(job,result=result))['numerically_valid_finite']==33


def test_internally_consistent_alternative_quadrature_is_rejected(jobs):
    job=jobs[91];r=computed_fixture(job,uniform=True)
    assert all(c['passed'] for c in r['numerical_checks'] if c['name']!='literal SA6 physical geometry')
    assert not next(c for c in r['numerical_checks'] if c['name']=='literal SA6 physical geometry')['passed']
    with pytest.raises(ValueError):mass.validate_result_contract(job,r)


@pytest.mark.parametrize('fault',['within_roundoff','beyond_roundoff','negative','tolerance','flag','other_metric'])
def test_saved_psd_metric_roundoff_is_narrow_and_keeps_physical_gate(jobs,fault):
    job=jobs[91];r=computed_fixture(job)
    check=next(c for c in r['numerical_checks'] if c['name']=='origin apparent positive semidefinite')
    if fault=='within_roundoff':check['value']+=mass.PSD_METRIC_ROUNDOFF/2
    elif fault=='beyond_roundoff':check['value']+=mass.PSD_METRIC_ROUNDOFF*2
    elif fault=='negative':check['value']=-mass.PSD_METRIC_ROUNDOFF/2
    elif fault=='tolerance':check['tolerance']*=2
    elif fault=='flag':check['passed']=False
    else:
        check=next(c for c in r['numerical_checks'] if c['name']=='origin apparent energy reconstruction')
        check['value']+=mass.PSD_METRIC_ROUNDOFF/2
    if fault=='within_roundoff':
        assert check['value']<2e-12 and mass.validate_result_contract(job,r)
    else:
        with pytest.raises(ValueError):mass.validate_result_contract(job,r)


@pytest.mark.parametrize('fault',['cg','rho','physical_normal','chord','span','length','sample','real_inertia','reference','matrix','real_mass','prediction','counter','duplicate'])
def test_saved_tensor_corruptions_rejected(jobs,fault):
    job=jobs[91];r=computed_fixture(job);e=r['evidence']
    if fault=='cg':e['physical_real_cg']=[0.,0.,0.]
    elif fault=='rho':e['density']*=2
    elif fault=='physical_normal':e['geometry']['lifting_panels'][0]['frame'][0][0][2]=0.
    elif fault=='chord':e['geometry']['lifting_panels'][0]['chord'][0]=.25
    elif fault=='span':e['geometry']['lifting_panels'][0]['r1'][-1][1]=.76
    elif fault=='length':e['geometry']['lifting_panels'][0]['ds'][0]*=2
    elif fault=='sample':e['geometry']['lifting_panels'][0]['rm'][0][1]+=.001
    elif fault=='real_inertia':e['real_records'][0]['inertia'][0][0][0]=1e-15
    elif fault=='reference':e['tensors']['reported_centroid']['reference']=[1.,0.,0.]
    elif fault=='matrix':e['tensors']['origin']['apparent_spatial_matrix'][0][0]+=.01
    elif fault=='real_mass':e['real_mass']=1.
    elif fault=='prediction':r['reference_checks'][0]['predicted']=1.
    elif fault=='counter':r['physical_calls']=1
    else:r['reference_checks'][-1]=deepcopy(r['reference_checks'][0])
    with pytest.raises(ValueError):mass.validate_result_contract(job,r)


def test_tiny_native_nonzero_is_not_zero_or_hidden_by_numerical_gate(jobs):
    job=jobs[91];name='apparent_mass.yy';ref=mass.reference_contract(job)[name]
    assert ref['expected']!=0 and ref['tolerance']<1e-25
    check=next(c for c in mass.reference_checks(job,{name:0.}) if c['name']==name)
    assert not check['passed']
    edge=Decimal(ref['exact_decimal_expected'])+Decimal(ref['exact_decimal_tolerance'])
    check=next(c for c in mass.reference_checks(job,{name:float(edge)}) if c['name']==name)
    assert check['passed'] and summary.precision_pass(check,exact_decimal=True)


@pytest.mark.parametrize('status',['timeout','error','source_mismatch'])
def test_failure_keeps_all33_slots(jobs,status):
    job=jobs[91];r={'status':status}
    assert mass.validate_result_contract(job,r)
    counts=summary.scalar_counts(dict(job,result=r))
    assert counts['required']==counts['failed_job_required']==33
    for flag in ('numerical_pass','numerical_passed','reference_match'):
        with pytest.raises(ValueError):mass.validate_result_contract(job,dict(r,**{flag:True}))


@pytest.mark.parametrize('marker',['target_kind','comparison_scope','execution_route','adapter','case_id'])
def test_scope_relabelling_rejected(jobs,marker):
    job=deepcopy(jobs[91]);job.pop(marker)
    with pytest.raises(ValueError):summary.scalar_counts(job)


def test_selection_scope_resume_and_mass_unit_tables(jobs,tmp_path):
    assert runner.plan_jobs(ROOT,['sa6'],comparison_scopes=[mass.SCOPE])==jobs
    assert len(runner.select_jobs(jobs,{'cases':[{'id':'SA-6'}]},['SA-6'],['*:rigid-mass']))==88
    pins=runner.code_pins(ROOT,['sa6'])
    assert all('scripts/'+name in pins for name in ('isae_suite_sa6_mass.py','isae_suite_sa6_mass_math.py'))
    for scopes,adapters in [(['bad'],['sa6']),([mass.SCOPE,mass.SCOPE],['sa6']),([mass.SCOPE],['polars']),([mass.SCOPE],[])]:
        with pytest.raises(ValueError):runner.plan_jobs(ROOT,adapters,comparison_scopes=scopes)
    p=tmp_path/'plan.json';plan={'execution_policy':{'comparison_scopes':[mass.SCOPE]}};p.write_text(json.dumps(plan))
    runner.validate_resume_plan(p,plan,True)
    with pytest.raises(ValueError):runner.validate_resume_plan(p,{'execution_policy':{'comparison_scopes':[]}},True)
    tables=summary.sa6_tables(jobs,mass=True);assert len(tables)==4 and all(len(t['channels'])==33 for t in tables)
    assert tables[0]['channels']['apparent_mass.xx']['unit']=='kg'
    assert tables[0]['channels']['apparent_inertia_origin.xx']['unit']=='kg m^2'
    assert summary.sa6_tables([jobs[91]],mass=True)==[]
    with pytest.raises(ValueError):summary.sa6_tables([jobs[92],deepcopy(jobs[92])],mass=True)
    catalog={'cases':[dict(id=n,path=n,models=[],reference_candidates=[]) for n in sorted(summary.FAMILIES)],'counts':{}}
    data=summary.summarize(dict(catalog=catalog,jobs=[dict(jobs[91],result={'status':'timeout'})],runtime={},kernel_pins={},helper_pins={},source_provenance={}))
    assert data['scalar_counts']['required']==33 and len(data['families'])==41 and not data['full_suite_validated']
    assert not next(f for f in data['families'] if f['id']=='SA-6')['complete_family_reproduction']
    assert data['fine_grid_sa6_mass_tensors']==[]


@pytest.mark.parametrize('fault',['none','missing_option','missing_helper','missing_math','duplicate_option','unknown_option','setup','claim'])
def test_summary_canonical_once_and_frozen_options(jobs,tmp_path,monkeypatch,fault):
    root=tmp_path/'root';stage=tmp_path/'run';(root/'openswing').mkdir(parents=True);(root/'scripts').mkdir();stage.mkdir()
    files=[root/'openswing/kernel.py']+[root/'scripts'/n for n in ('isae_suite_sa6.py','isae_suite_sa6_controls.py','isae_suite_sa6_mass.py','isae_suite_sa6_mass_math.py')]
    for p in files:p.write_text('# isolated source verification fixture\n')
    rows=deepcopy(jobs[91:93])
    for row in rows:row['sources']=[]
    original=deepcopy(rows);calls=[]
    def canonical(actual_root,*,comparison_scopes=()):
        assert actual_root==root and comparison_scopes==(mass.SCOPE,)
        calls.append(actual_root);return deepcopy(original)
    monkeypatch.setattr(summary.importlib,'import_module',lambda name:SimpleNamespace(plan=canonical))
    if fault=='setup':rows[0]['settings']['controls']['1']=8.
    if fault=='claim':rows[0]['historical_producer_authenticated']=True
    cases=[dict(id=n,path=n,models=[],reference_candidates=[]) for n in sorted(summary.FAMILIES)]
    catalog=dict(repository='original',revision='frozen',sources=[],models=[],cases=cases,counts=dict(families=41,models=0,parse={}))
    pins={p.relative_to(root).as_posix():summary.pin(p)['sha256'] for p in files}
    if fault=='missing_helper':pins.pop('scripts/isae_suite_sa6_mass.py')
    if fault=='missing_math':pins.pop('scripts/isae_suite_sa6_mass_math.py')
    scopes=[] if fault=='missing_option' else [mass.SCOPE]
    if fault=='unknown_option':scopes+=['bad']
    if fault=='duplicate_option':scopes*=2
    policy=dict(comparison_scopes=scopes)
    plan=dict(catalog=catalog,jobs=rows,runtime={'python':'same'},code_sha256=pins,execution_policy=policy)
    report=dict(repository='original',revision='frozen',runtime=plan['runtime'],current_code_unchanged=True,
        jobs=[dict(row,result=None) for row in rows],code_sha256=pins,execution_policy=policy)
    for name,value in [('catalog',catalog),('plan',plan),('report',report)]: (stage/(name+'.json')).write_text(json.dumps(value))
    if fault=='none':
        merged=summary.load_runs([stage],root);assert calls==[root] and summary.totals(merged['jobs'])['unrun_required']==66
        summary.verify_summary_sources(merged)
    else:
        with pytest.raises(ValueError):summary.load_runs([stage],root)


def test_worker_geometry_call_and_reported_reference_mock(jobs,monkeypatch):
    job=jobs[91];fixture=computed_fixture(job);calls=[];model=SimpleNamespace(diagnostics=[],constants=[0.,1.2256]);meshes=object()
    def parse(text,**opts):
        assert text==(ROOT/job['model_path']).read_text() and opts=={'beam_interpolation':'natural-v1'}
        calls.append('parse');return model
    def geometry(actual,count):assert actual is model and count==64;calls.append('geometry');return meshes
    def compute(actual,actual_meshes,density,point,factor):
        assert actual is model and actual_meshes is meshes and density==1.2256 and point==[0.,0.,0.] and factor==1.
        calls.append('tensor');return deepcopy(fixture['evidence'])
    modules=dict(asw=SimpleNamespace(parse_asw=parse),geometry=SimpleNamespace(model_meshes=geometry))
    for name,module in modules.items():
        module.__file__=str(ROOT/'openswing'/(name+'.py'));module.__name__='openswing.'+name
    monkeypatch.setitem(sys.modules,'openswing',SimpleNamespace(**modules))
    for name,module in modules.items():monkeypatch.setitem(sys.modules,'openswing.'+name,module)
    monkeypatch.setattr(mass.tensor_math,'compute_tensor_evidence',compute)
    assert mass._execute(ROOT,job)==fixture['evidence'] and calls==['parse','geometry','tensor']
