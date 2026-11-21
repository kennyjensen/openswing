"""Source accounting and rejection tests; synthetic records are not solver evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import isae_suite_st1 as legacy
import isae_suite_st1_mechanics as mechanics
from isae_acceptance import apply_reference_acceptance

SPEC=importlib.util.spec_from_file_location('st1_mechanics_suite_runner',ROOT/'scripts/run-isae-suite.py')
runner=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(runner)


@pytest.fixture(scope='module')
def jobs():return legacy.plan(ROOT,comparison_scopes=['st1-mechanics'])


def test_complete_scope_and_distinct_archive(jobs):
    assert len(jobs)==72 and sum(j['expected_outputs'] for j in jobs)==223
    assert sum(j['expected_outputs'] for j in jobs if j['target_kind']=='static')==201
    assert sum(j['expected_outputs'] for j in jobs if j['target_kind']=='modal')==22
    old=legacy.plan(ROOT)
    assert len(old)==37 and sum(j['expected_outputs'] for j in old)==200
    assert not ({j['id'] for j in old}&{j['id'] for j in jobs})
    assert runner.plan_jobs(ROOT,['st1'],comparison_scopes=['st1-mechanics'])==jobs
    assert all(not s['path'].startswith('openswing/') for j in jobs for s in j['source_pins'])


def test_reference_conflicts_remain_targets(jobs):
    targets={(j['configuration'],r['name']):r['expected'] for j in jobs if j['target_kind']=='modal' for r in j['observations']}
    assert targets['coupled','1T']==95
    assert targets['thin-down','3B']==218
    assert targets['thin-up','3B']==21.8


def tokens(source):
    result=[]
    for token in source.replace('*','* ').split():
        try:result.append(float(token))
        except ValueError:result.append(token)
    return result


def test_derived_inputs_equal_the_reviewed_physical_inputs(jobs):
    reviewed=json.loads((ROOT/'docs/validation/isae-st1-mechanics-reviewed-inputs.json').read_text())['inputs']
    assert set(reviewed)=={j['id'] for j in jobs}
    for j in jobs:
        actual=hashlib.sha256(json.dumps(tokens(mechanics.derive(ROOT,j))).encode()).hexdigest()
        assert actual==reviewed[j['id']]['tokens_sha256'],j['id']


def test_changed_reference_requires_source_review(tmp_path):
    for name in (mechanics.INPUTS,mechanics.TARGETS):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
    p=tmp_path/mechanics.TARGETS;scope=json.loads(p.read_text());scope['modal_targets'][0]['expected_Hz']*=1.1
    p.write_text(json.dumps(scope))
    with pytest.raises(ValueError,match='reference values changed'):mechanics.plan(tmp_path)


def synthetic_result(job):
    modal=job['target_kind']=='modal';checks=[];identities={};mesh=[]
    for r in job['observations']:
        extra={};value=r['expected']
        if modal:
            coarse=r['expected']*1.004;fine=r['expected']*1.002;value=coarse
            family=r['name'][-1];identity=dict(family=family,activity_fractions={family:.8},internal_zeros=int(r['name'][0])-1)
            if family=='T' and job['config']['allow_torsion_sign_change']:identity['internal_zeros']=1
            identities[r['name']]=dict(coarse=dict(**identity,frequency=coarse),fine=dict(**identity,frequency=fine))
            extra=dict(coarse_Hz=coarse,fine_Hz=fine,assessment='worst_error_across_meshes')
            mesh.append(dict(name=r['name'],relative_change=abs(coarse/fine-1),shape_MAC=.9999))
        checks.append(dict(**r,**extra,predicted=value,passed=abs(value-r['expected'])<=r['tolerance']))
    if not modal and job['refine']:mesh=[dict(relative_change=1e-4)]
    limits=mechanics.MODAL_LIMITS if modal else mechanics.STATIC_LIMITS
    count=2 if modal else 1+(job['mass']!=0)+job['refine']
    return dict(status='computed',reference_checks=checks,numerical_pass=True,
        state_checks=[{k:0. for k in limits} for _ in range(count)],solver_calls=count,
        mesh_checks=mesh,modal_identification=identities,source_pins_unchanged=True,complete_family_reproduction=False)


@pytest.mark.parametrize('name',['thin-up','coupled'])
def test_modal_contract_and_acceptance(jobs,name):
    job=next(j for j in jobs if j['target_kind']=='modal' and j['configuration']==name)
    result=runner.checked_result(job,synthetic_result(job))
    assert result['status']=='computed' and result['output_accounting']['required']==len(job['observations'])
    assert apply_reference_acceptance(result)['reference_match']


@pytest.mark.parametrize('fault',['missing_target','changed_expected','missing_state','missing_mesh',
                                 'bad_residual','bad_shape','wrong_family','wrong_zero_count','mesh_frequency','favorable_mesh_only'])
def test_incomplete_or_forged_result_cannot_pass(jobs,fault):
    job=next(j for j in jobs if j['target_kind']=='modal' and j['configuration']=='coupled')
    r=synthetic_result(job)
    if fault=='missing_target':r['reference_checks'].pop()
    elif fault=='changed_expected':r['reference_checks'][0]['expected']*=1.1
    elif fault=='missing_state':r['state_checks'].pop()
    elif fault=='missing_mesh':r['mesh_checks'].pop()
    elif fault=='bad_residual':r['state_checks'][0]['residual']=.1
    elif fault=='bad_shape':r['mesh_checks'][0]['shape_MAC']=.5
    elif fault=='wrong_family':r['modal_identification']['1T']['fine']['family']='F'
    elif fault=='wrong_zero_count':r['modal_identification']['1T']['fine']['internal_zeros']=1
    elif fault=='mesh_frequency':r['mesh_checks'][0]['relative_change']=0
    else:r['reference_checks'][0]['predicted']=r['reference_checks'][0]['fine_Hz']
    checked=runner.checked_result(job,r)
    assert checked['status']=='adapter_contract_failure'
    assert not apply_reference_acceptance(checked)['reference_match']


def test_static_baseline_and_refinement_are_required(jobs):
    job=next(j for j in jobs if j['target_kind']=='static' and j['mass']==.4 and j['refine'])
    r=synthetic_result(job)
    assert runner.checked_result(job,r)['status']=='computed'
    r['state_checks'].pop();r['solver_calls']-=1
    assert runner.checked_result(job,r)['status']=='adapter_contract_failure'
