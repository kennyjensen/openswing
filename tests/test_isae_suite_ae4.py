"""AE4 source accounting and saved evidence; synthetic matrices are not validation."""
import builtins
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from scripts import isae_suite_ae4 as a
from scripts.isae_acceptance import apply_reference_acceptance


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


RUNNER=load('ae4_runner','scripts/run-isae-suite.py')
SUMMARY=load('ae4_summary','scripts/summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').exists():
        pytest.skip('Optional original archive unavailable')
    return RUNNER.plan_jobs(ROOT,['ae4'],comparison_scopes=[a.SCOPE])


@pytest.fixture(scope='module')
def job(jobs):
    return next(j for j in jobs if j['id']=='AE-4:declared:op081:n40')


@pytest.fixture(scope='module')
def synthetic(job):
    """A normal test pencil with two complex pairs and two slightly noisy real poles."""
    n=19*(job['nominal']+2)-1
    matrix=np.eye(n);mass=np.eye(n);modes=[]
    def split(v):return dict(real=v.real.tolist(),imag=v.imag.tolist())
    for offset,(re,im) in zip((10,12),[(-22.,164.),(6.4,196.)]):
        matrix[offset:offset+2,offset:offset+2]=[[re,-im],[im,re]]
        v=np.zeros(n,dtype=complex);v[offset:offset+2]=np.array([1.,-1j])/np.sqrt(2)
        modes.append(dict(eigenvalue=[re,im],right=split(v),left=split(v)))
    for offset,re,noise in ((14,-23.,1e-12),(15,-37.,-1e-12)):
        matrix[offset,offset]=re;v=np.zeros(n,dtype=complex);v[offset]=1.
        modes.append(dict(eigenvalue=[re,noise],right=split(v),left=split(v)))
    raw=dict(converged=True,frame_mode='fixed',vacuum=False,modes=modes,matrices=dict(A=matrix,M=mass),
        diagnostics=dict(structural_operator='drela-moving-airflow-v1',method='full_shift_invert',requested_count=4,
            shift=[0.,200.],time_scale=100.,base_residual=1e-15,state_layout=dict(node_coordinates=dict(start=0),
                local_velocity=dict(start=252),local_rates=dict(start=378),frame=dict(width=0))),
        base=dict(converged=True,structural_nodes=42,structural_elements=41,gravity_body=[0.,0.,-9.81],
            ground_plane=dict(flag=1,normal_body=[0.,0.,1.],normal_earth=[0.,0.,1.],wall_roots=[dict(beam=1,t=.0001)],
                offset=0.,position_earth=[0.,0.,0.],attitude=[0.,0.,0.],wall_root_derivative_probe=False)))
    return a.assess_raw(job,raw,a.request(job,(ROOT/job['model_path']).read_text()))


def test_all_original_modal_rows_and_conditional_denominators_are_retained(jobs):
    historical=[j for j in jobs if j['comparison_scope']=='historical-modal-exports']
    declared=[j for j in jobs if j['comparison_scope']==a.SCOPE]
    assert len(historical)==18 and sum(j['expected_outputs'] for j in historical)==9480
    assert len(declared)==218 and sum(j['expected_outputs'] for j in declared)==1200
    assert len([j for j in declared if j['execution_route']=='worker'])==216
    assert sum(j['expected_outputs'] for j in declared if j['native_index']==1)==12
    assert sum(j['expected_outputs'] for j in declared if j['native_index']==104)==16
    assert {j['IAS'] for j in declared if j['execution_route']=='worker'}==set(range(1,109))
    assert not any(j.get('IAS')==109 for j in jobs)
    scope=SUMMARY.declared_scope(jobs)
    assert scope['ae4_stored_modal_rows']==4740 and scope['ae4_declared_scalar_slots']==1200
    assert scope['ae4_distinct_file_content_modal_rows']<4740
    assert SUMMARY.totals(jobs)['unrun_required']==10680
    assert all(r['status']=='INCOMPLETE' for r in a.mesh_diagnostics(jobs,{}))


def test_default_scope_and_blocker_validation_do_not_import_production_or_numerics(jobs,monkeypatch):
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.split('.')[0] in ('openswing','numpy','scipy'):
            raise AssertionError('Blocked planning imported '+name)
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    baseline=RUNNER.plan_jobs(ROOT,['ae4'])
    assert len(baseline)==18 and all(j['execution_route']=='unsupported' for j in baseline)
    initial=next(j for j in jobs if j['id']=='AE-4:declared:op001:n40')
    for j in (baseline[0],initial):
        result=RUNNER.checked_result(j,a.validate_blocked(ROOT,j))
        assert result['status']=='unsupported' and result['output_accounting']['passed']==0
        assert SUMMARY.scalar_counts(dict(j,result=result))['reported_unavailable']==j['expected_outputs']


def test_declared_request_matches_retained_source_settings(job):
    payload=a.request(job,(ROOT/job['model_path']).read_text())
    assert payload['condition']['speed']==80 and payload['condition']['ground_effect']==1
    assert payload['modes']['count']==4 and payload['modes']['shift']==[0.,200.] and payload['modes']['matrices'] is True
    assert payload['panels']['beams']['1']==dict(count=40,spacing='cosine')


def test_five_percent_policy_preserves_strict_precision_and_real_poles(job,synthetic):
    checked=RUNNER.checked_result(job,deepcopy(synthetic))
    assert checked['status']=='computed' and checked['output_accounting']['passed']==0
    view=apply_reference_acceptance(checked)
    assert view['output_accounting']['passed']==4 and view['reference_match'] is True
    assert SUMMARY.scalar_counts(dict(job,result=view))['passed']==4
    assert len(view['numerical_evidence']['eigenvalues'])==4


def test_adapter_reuses_the_checked_raw_result_without_decoding_it_again(job,synthetic,monkeypatch):
    import json
    raw=object()
    payload=a.request(job,(ROOT/job['model_path']).read_text())
    def run(folder,nominal,*,speed):
        folder.mkdir()
        (folder/'request.json').write_text(json.dumps(payload))
        (folder/'result.json').write_text('{"synthetic_transport_test":true}')
        return raw
    def assess(actual_job,actual_raw,actual_payload):
        assert actual_job==job and actual_raw is raw and actual_payload==payload
        return deepcopy(synthetic)
    original=a.json.load
    def guarded(stream,*args,**kwargs):
        assert Path(stream.name).name!='result.json','Do not decode the complete matrix export twice.'
        return original(stream,*args,**kwargs)
    helper=a.helper(ROOT)
    monkeypatch.setattr(helper,'run',run)
    monkeypatch.setattr(a,'helper',lambda root=ROOT:helper)
    monkeypatch.setattr(a,'assess_raw',assess)
    monkeypatch.setattr(a.json,'load',guarded)
    with a.tempfile.TemporaryDirectory(dir=ROOT/'artifacts/isae') as stage:
        monkeypatch.setattr(a.tempfile,'mkdtemp',lambda **kwargs:stage)
        actual=a.run(ROOT,job)
    assert actual['numerical_evidence']==synthetic['numerical_evidence']


@pytest.mark.parametrize('fault',[
    'missing_root','detached_root','wrong_shift','changed_target','bad_pencil','bad_mass','bad_clamp',
    'wrong_wall','wrong_frame','wrong_dimension','wrong_mesh','wrong_payload','real_certificate','classification',
    'claim_historical','missing_qualification','extra_solve','changed_prediction','missing_component'])
def test_runner_and_summary_reject_corrupted_modal_evidence(job,synthetic,fault):
    j,r=deepcopy(job),deepcopy(synthetic);e=r['numerical_evidence']
    if fault=='missing_root':e['eigenvalues'].pop()
    elif fault=='detached_root':e['eigenvalues'][0][0]=42.
    elif fault=='wrong_shift':e['shift']=[0.,100.]
    elif fault=='changed_target':j['reference_rows'][0]['tokens'][1]='-22.000'
    elif fault=='bad_pencil':e['pencil_proofs'][0]['residual_norms'][0]=1e6
    elif fault=='bad_mass':e['pencil_proofs'][0]['mass_pair']=[0.,0.]
    elif fault=='bad_clamp':e['pencil_proofs'][0]['clamp_norm']=1.
    elif fault=='wrong_wall':e['wall']['flag']=0
    elif fault=='wrong_frame':e['frame']='free'
    elif fault=='wrong_dimension':e['full_dimension']-=6
    elif fault=='wrong_mesh':e['nodes']+=1
    elif fault=='wrong_payload':e['request']['condition']['freeze_influences']=True
    elif fault=='real_certificate':e['classifications'][2]['right']['phase_defect']=1.
    elif fault=='classification':e['classifications'][0]['classification']='certified_real'
    elif fault=='claim_historical':r['historical_settings_authenticated']=True
    elif fault=='missing_qualification':r['qualifications']=[]
    elif fault=='extra_solve':r['operations']['retries']=1
    elif fault=='changed_prediction':r['reference_checks'][0]['predicted']=-21.
    elif fault=='missing_component':r['reference_checks'].pop()
    checked=RUNNER.checked_result(j,r)
    assert checked['status']=='adapter_contract_failure'
    assert checked['output_accounting']['numerically_valid']==0
    with pytest.raises((ValueError,KeyError)):
        SUMMARY.scalar_counts(dict(j,result=r))


def test_real_native_pole_and_extra_native_branch_remain_in_denominator(jobs,synthetic):
    j=next(j for j in jobs if j['id']=='AE-4:declared:op104:n40')
    e=synthetic['numerical_evidence']
    checks=a.reference_checks(j,e['eigenvalues'],e['classifications'])
    assert len(checks)==8 and all(c['predicted'] is None and c['passed'] is False for c in checks)


def test_solved_but_unpaired_roots_do_not_inflate_valid_reference_sample_count(job,jobs,synthetic):
    unmatched=next(j for j in jobs if j['id']=='AE-4:declared:op104:n40')
    e=synthetic['numerical_evidence']
    result=dict(status='computed',numerical_pass=True,reference_match=False,
                reference_checks=a.reference_checks(unmatched,e['eigenvalues'],e['classifications']))
    scope=SUMMARY.declared_scope([dict(job,result=synthetic),dict(unmatched,result=result)])
    assert scope['original_reference_samples']==6
    assert scope['ae4_rows_with_finite_predictions']==2


def test_unresolved_real_candidate_blocks_a_positive_frequency_match(job,synthetic):
    e=deepcopy(synthetic['numerical_evidence']);c=e['classifications'][2]
    c['classification']='unresolved_near_real';c['right']['phase_defect']=1.;c['right']['passed']=False
    checks=a.reference_checks(job,e['eigenvalues'],e['classifications'])
    assert len(checks)==4 and all(c['predicted'] is None for c in checks)


def test_blocked_historical_scope_cannot_be_promoted(jobs):
    j=jobs[0];r=a.validate_blocked(ROOT,j);r.update(status='computed',numerical_pass=True)
    assert RUNNER.checked_result(j,r)['status']=='adapter_contract_failure'
    with pytest.raises(ValueError):SUMMARY.scalar_counts(dict(j,result=r))


@pytest.mark.parametrize('status',['error','timeout'])
def test_failed_jobs_remain_required_without_fabricated_numerical_evidence(job,status):
    counts=SUMMARY.scalar_counts(dict(job,result=dict(status=status,reference_match=False)))
    assert counts['required']==counts['absent']==counts['failed_job_required']==4
    assert counts['passed']==counts['numerically_valid_finite']==0


def test_modal_decoder_preserves_real_zero_and_printed_decimal_exponents():
    text='# model\n#\n# Op.Point Eigenvalue\n 104 0.33334576E-01 0.0000000\n'
    rows=a.decode_table(text)
    assert rows==[dict(line=4,tokens=['104','0.33334576E-01','0.0000000'],values=[104,.033334576,0.])]
    contract=a.reference_contract(dict(reference_rows=rows,expected_outputs=2))
    assert contract['line4:real']['exact_decimal_tolerance']=='5E-10'
    assert contract['line4:imaginary']['exact_decimal_tolerance']=='5E-8'


@pytest.mark.parametrize('row',['1 NaN 1','1 0 1 2','0 1 2','one 1 2'])
def test_invalid_modal_source_row_is_rejected(row):
    with pytest.raises(ValueError):a.decode_table('# model\n#\n# Op.Point Eigenvalue\n'+row+'\n')


def test_mesh_gate_is_not_replaced_by_reference_allowance(job,synthetic):
    fine=a._declared(ROOT,a._table_record(ROOT,a.TABLE),81,80)
    coarse=apply_reference_acceptance(RUNNER.checked_result(job,deepcopy(synthetic)))
    r=deepcopy(coarse);r['reference_checks'][0]['predicted']*=1.02
    rows=a.mesh_diagnostics([job,fine],{job['id']:coarse,fine['id']:r})
    assert rows[0]['status']=='FAIL' and rows[0]['relative_gate']==.001
