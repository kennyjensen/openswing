"""Source-only ST1 contracts; these tests never parse a model or solve physics."""
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('isae_st1_test_adapter', ROOT/'scripts/isae_suite_st1.py')
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


@pytest.fixture(scope='module')
def jobs():
    return adapter.plan(ROOT)


@pytest.fixture
def worker(jobs):
    return deepcopy(next(j for j in jobs if j['execution_route']=='worker'))


def physical_fixture(job):
    """Synthetic validator evidence, explicitly not a physical ST1 result."""
    expected=adapter._expectations(job)
    identity=dict(model_sha256=job['literal_model_sha256'],structural_operator=adapter.POLICY['structural_operator'])
    position=[.02,-.20,-.09]
    values=dict(zip(adapter.NAMES,position))
    force=[adapter.WEIGHT[5]/9.81*g for g in job['gravity']]
    point=[.025,-.25,-.1];moment=adapter._cross(point,force)
    checks=[]
    for name,spec in adapter.PHYSICAL_CHECK_SPECS.items():
        if spec['kind']=='exact':
            value=identity if name=='same_operator_identity' else deepcopy(expected[name])
            checks.append(dict(name=name,actual=value,expected=deepcopy(value),passed=True));continue
        row=dict(name=name,metric=0.,gate=adapter.GATES[spec['gate']],passed=True)
        if spec['kind']=='balance':
            applied=force if name=='force_balance' else moment
            row.update(applied=applied,support=[-x for x in applied])
        elif spec['kind']=='clamp':
            v=job['root_position'] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
            row.update(expected=v,reported=list(v))
        elif spec['kind']=='weight_wrench':
            row.update(position=point,force=force,moment=moment,reported_force=force,reported_moment=moment)
        elif spec['kind']=='sensor_anchor':
            row.update(node=dict(beam=1,t=-.22,jig_position=[0.,-.22,0.],position=position),
                reported=values,reconstructed=values,body_position=position,earth_position=position)
        elif spec['kind']=='parity':row.update(reported=values,restored=values,channels={k:0. for k in values})
        checks.append(row)
    return checks,values


def computed_fixture(job):
    physical,values=physical_fixture(job)
    checks=adapter._checks(job,values)
    return dict(status='computed',numerical_pass=True,reference_match=all(c['passed'] for c in checks),
        reference_checks=checks,physical_checks=physical,physical_calls=2,
        operations=deepcopy(job['expected_operations']),source_pins_unchanged=True,kernel_pins_unchanged=True)


def test_complete_native_and_model_scope(jobs):
    assert len(jobs)==37
    assert sum(j['expected_outputs'] for j in jobs)==200
    workers=[j for j in jobs if j['execution_route']=='worker']
    assert len(workers)==2
    assert [j['nominal'] for j in workers]==[100,200]
    assert [j['expected_elements'] for j in workers]==[101,201]
    assert [j['expected_nodes'] for j in workers]==[102,202]
    assert len({j['table_path'] for j in jobs if j['table_path']})==27
    assert len({j['model_path'] for j in jobs if j['model_path']})==10
    assert len([j for j in jobs if j['target_kind']=='model_inventory'])==9


def test_all_complex_roots_and_real_only_roots_retained(jobs):
    modal=[j for j in jobs if j['target_kind']=='blocked_native_eigenvalues']
    assert sum(len(j['reference_rows']) for j in modal)==76
    assert sum(j['expected_outputs'] for j in modal)==152
    assert sum(row['real_only_root'] for j in modal for row in j['reference_rows'])==25
    assert all(len(j['observations'])==2*len(j['reference_rows']) for j in modal)


def test_distinct197_cells_mesh_duplicates_only_candidate(jobs):
    keys={}
    for job in jobs:
        for obs in job['observations']:
            key=(job['table_path'],obs['name'])
            keys.setdefault(key,[]).append(job['id'])
    assert len(keys)==197
    assert sorted(map(len,keys.values()))==[1]*194+[2]*3


def test_all_tokens_precision_and_positions(jobs):
    for job in jobs:
        for obs in job['observations']:
            token=obs['expected_token'];start=obs['source_character_1based']-1
            assert obs['raw_line'][start:start+len(token)]==token
            assert obs['raw_tokens'][obs['source_column_1based']-1]==token
            value=Decimal(token);half=Decimal(5).scaleb(value.as_tuple().exponent-1)
            assert obs['exact_decimal_tolerance']==str(half)
            assert obs['tolerance']==float(half)


def test_candidate_preserves_original_settings_and_output_mapping(worker):
    assert worker['source_node_request']==worker['source_oper_iteration_limit']==100
    assert worker['condition'] is None
    assert worker['gravity']==[0.,0.,-9.81]
    assert worker['literal_sensor_rows']==[adapter.SENSOR]
    assert worker['mandatory_stations']==[-.28,-.22,.28]
    assert worker['observations'][2]['expected_token']=='-0.949139E-01'
    assert worker['observations'][2]['tolerance']==5e-8
    assert worker['original_file_modified'] is worker['complete_family_reproduction'] is False
    assert 'UNDEFINED_SUPPLIED_SENSOR_FRAME' in next(iter(worker['source_model_blockers'].values()))


def test_unpaired_and_shared_files_not_given_guessed_model(jobs):
    selected=[j for j in jobs if j.get('pairing_status') in ('NO_RETAINED_DRIVER_WRITE_NAME','SHARED_OUTPUT_OVERWRITTEN_BY_MULTIPLE_DRIVERS')]
    assert len(selected)==5
    assert sum(j['expected_outputs'] for j in selected)==24
    assert all(j['model_path'] is None and j['execution_route']=='unsupported' for j in selected)


def test_historical_kernel_pins_are_not_current_source_requirements(jobs):
    assert all('/openswing/' not in p['path'] for p in jobs[0]['source_pins'])
    assert jobs[0]['kernel_pins']==[]  # first table is an unsupported mode export
    inventories=[j for j in jobs if j['target_kind']=='model_inventory']
    assert len(inventories[0]['output_candidates'])==61
    assert inventories[0]['supplemental_duplicate_tree']['additional_independent_targets']==0


def test_source_only_planning_and_blocked_route_import_no_production(jobs):
    before={name for name in sys.modules if name=='openswing' or name.startswith('openswing.')}
    blocked=next(j for j in jobs if j['target_kind']=='blocked_native_eigenvalues')
    result=adapter.validate_blocked(ROOT,blocked)
    assert adapter.validate_result_contract(blocked,result)
    assert result['physical_calls']==0 and result['production_imports']==0
    assert len(result['reference_checks'])==blocked['expected_outputs']
    assert all(c['predicted'] is None and not c['passed'] for c in result['reference_checks'])
    assert before=={name for name in sys.modules if name=='openswing' or name.startswith('openswing.')}


def test_zero_target_inventory_is_blocked_not_pass(jobs):
    job=next(j for j in jobs if j['target_kind']=='model_inventory')
    result=adapter.validate_blocked(ROOT,job)
    assert adapter.validate_result_contract(job,result)
    assert result['reference_checks']==[]
    assert result['status']=='unsupported' and result['reference_match'] is False


@pytest.mark.parametrize('field,value',[('expected_token','0.0'),('tolerance',1.),('source_line',1),('source_column_1based',1),('raw_line','changed')])
def test_canonical_source_contract_rejects_tampering(jobs,field,value):
    job=deepcopy(next(j for j in jobs if j['target_kind']=='blocked_native_eigenvalues'))
    job['observations'][0][field]=value
    with pytest.raises(ValueError):adapter.verify_reference_sources(ROOT,job)


def test_complete_physical_fixture_and_result_contract(worker):
    result=computed_fixture(worker)
    assert len(result['physical_checks'])==26
    assert adapter.validate_physical_checks(worker,result['physical_checks'])
    assert adapter.validate_result_contract(worker,result)


@pytest.mark.parametrize('fault',['missing','duplicate','metric','gate','expected','tip_force','sensor_position','null_axis','prediction','whole_state','physical_calls','operations','identity','balance_binding','historical_claim'])
def test_computed_evidence_tampering_rejected(worker,fault):
    result=computed_fixture(worker);items={c['name']:c for c in result['physical_checks']}
    if fault=='missing':result['physical_checks'].pop()
    elif fault=='duplicate':result['physical_checks'][-1]=deepcopy(result['physical_checks'][0])
    elif fault=='metric':items['fresh_full_residual']['metric']=1.
    elif fault=='gate':items['fresh_full_residual']['gate']=1.
    elif fault=='expected':items['active_tip_weight']['expected']=0
    elif fault=='tip_force':items['independent_tip_weight_wrench']['force']=[0.,0.,0.]
    elif fault=='sensor_position':items['independent_sensor_anchor']['node']['t']=-.28
    elif fault=='null_axis':items['sensor_frame_scope']['actual']['axes_available']=True
    elif fault=='prediction':result['reference_checks'][0]['predicted']+=.1
    elif fault=='whole_state':result['reference_match']=True
    elif fault=='physical_calls':result['physical_calls']=1
    elif fault=='operations':result['operations']['retries']=1
    elif fault=='identity':
        items['same_operator_identity']['actual']={};items['same_operator_identity']['expected']={}
    elif fault=='balance_binding':
        items['force_balance'].update(applied=[0.,0.,0.],support=[0.,0.,0.])
    elif fault=='historical_claim':result['historical_settings_recovered']=True
    with pytest.raises(ValueError):adapter.validate_result_contract(worker,result)


def test_consistent_physical_failure_is_false(worker):
    checks,_=physical_fixture(worker)
    row=next(c for c in checks if c['name']=='fresh_full_residual')
    row.update(metric=1.,passed=False)
    assert adapter.validate_physical_checks(worker,checks) is False


def test_blocked_result_cannot_claim_predictions(jobs):
    job=next(j for j in jobs if j['target_kind']=='blocked_native_eigenvalues')
    result=dict(status='computed',numerical_pass=True,reference_match=True,operations=job['expected_operations'],
                physical_calls=0,reference_checks=adapter._checks(job,{o['name']:o['expected'] for o in job['observations']}))
    with pytest.raises(ValueError):adapter.validate_result_contract(job,result)


def test_mesh_diagnostics_are_descriptive(jobs):
    workers=[j for j in jobs if j['execution_route']=='worker']
    packets={j['id']:computed_fixture(j) for j in workers}
    row=adapter.mesh_diagnostics(workers,packets)[0]
    assert row['status']=='COMPARED' and row['passed'] is None and row['acceptance_gate'] is None
    assert set(row['channels'])==set(adapter.NAMES)
    assert adapter.mesh_diagnostics(workers[:1],packets)[0]['status']=='UNAVAILABLE'
    assert adapter.mesh_diagnostics([],packets)==[]
