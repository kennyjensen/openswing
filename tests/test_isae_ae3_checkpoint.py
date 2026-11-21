"""Exact-base reuse rejects changed physics and incomplete saved evidence."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from scripts import isae_suite_ae3 as adapter
from scripts.replay_isae_ae3_checkpoint import validate_pair,validate_receipt,load_worker_input

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def evidence():
    path=ROOT/'artifacts/isae/ae3-native-adapter-20261111/jobs/AE-3-Straight_20O-fmat-001-coefficients-m80/strict-result.json'
    if not path.is_file():pytest.skip('Optional independently completed AE-3 checkpoint unavailable')
    # Audit this archived checkpoint against its own saved physical settings.
    # Current defaults may differ; validate_pair must reject mixing the two.
    jobs=json.loads((path.parents[2]/'plan.json').read_text())['jobs']
    target=next(j for j in jobs if j['target_kind']=='native_mass_properties' and j['native_operating_point']==1)
    base=next(j for j in jobs if j['target_kind']=='native_coefficients' and j['native_operating_point']==1 and j['nominal']==80)
    return target,base,json.loads(path.read_text())


def test_current_frozen_job_rejects_archived_updated_influence_checkpoint(evidence):
    job=next(j for j in adapter.plan(ROOT) if j['target_kind']=='native_mass_properties'
             and j['native_operating_point']==1)
    assert job['condition']['freeze_influences'] is True
    assert evidence[1]['condition']['freeze_influences'] is False
    with pytest.raises(ValueError,match='physical settings or source identity'):
        validate_pair(job,evidence[1],evidence[2])


def test_valid_completed_base_is_eligible_despite_native_coefficient_mismatch(evidence):
    job,base,result=evidence
    assert result['status']=='computed' and not result['reference_match']
    assert validate_pair(job,base,result)


@pytest.mark.parametrize('fault',['speed','flap','source','panels','policy','node_count','kernel',
    'unfinished','different_id','missing_check','failed_residual','false_prediction','auxiliary_base'])
def test_ineligible_checkpoint_cannot_supply_auxiliary_predictions(evidence,fault):
    job,base,result=(deepcopy(item) for item in evidence)
    if fault=='speed':base['condition']['speed']+=1
    if fault=='flap':base['condition']['controls']['1']=0
    if fault=='source':base['literal_model_sha256']='0'*64
    if fault=='panels':base['nominal']=160
    if fault=='policy':base['settings']['structural_operator']='other'
    if fault=='node_count':base['expected_nodes']+=1
    if fault=='kernel':base['kernel_pins'][0]['sha256']='0'*64
    if fault=='unfinished':result['status']='timeout'
    if fault=='different_id':result['id']='other'
    if fault=='missing_check':result['physical_checks'].pop()
    if fault=='failed_residual':
        next(c for c in result['physical_checks'] if c['name']=='fresh_full_residual')['metric']=1.
    if fault=='false_prediction':result['reference_checks'][0]['predicted']+=1
    if fault=='auxiliary_base':base['target_kind']='native_derivatives'
    with pytest.raises(ValueError):validate_pair(job,base,result)


def test_reuse_receipt_requires_original_file_hashes(evidence):
    with pytest.raises(ValueError,match='evidence or execution source'):
        validate_receipt(evidence[0],{'equilibrium_reuse':{'pins':[]}})


def test_worker_accepts_only_supervisor_bound_request_and_checkpoint(tmp_path,evidence):
    job,base,result=evidence
    checkpoint=tmp_path/'checkpoint.json';checkpoint.write_text('{}')
    packet=dict(job=job,verified_base_job=base,verified_base_result=result,
        checkpoint_path=str(checkpoint),checkpoint_pin=adapter._pin(checkpoint))
    request=tmp_path/'request.json';request.write_text(json.dumps(packet))
    digest=adapter._pin(request)['sha256']
    assert load_worker_input(request,digest)[1:]==(job,base,result)
    checkpoint.write_text('{"changed": true}')
    with pytest.raises(ValueError,match='checkpoint changed'):load_worker_input(request,digest)
    request.write_text('{}')
    with pytest.raises(ValueError,match='request changed'):load_worker_input(request,digest)
