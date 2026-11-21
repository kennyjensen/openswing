"""AE3 source and saved-result contracts; unit tests run no physical worker."""
import builtins
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

import pytest

from scripts import isae_suite_ae3 as adapter

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    return adapter.plan(ROOT)


def test_complete_native_and_embedded_denominators_and_unpaired_inventory(jobs):
    assert len(jobs)==len({job['id'] for job in jobs})==50
    assert sum(job['expected_outputs'] for job in jobs)==725
    native=[job for job in jobs if job['source_group']=='native_fmat']
    embedded=[job for job in jobs if job['source_group']=='embedded_postprocessor']
    inventory=[job for job in jobs if job['target_kind']=='model_inventory']
    assert len(native)==30 and sum(job['expected_outputs'] for job in native)==612
    cells={(job['table_path'],o['name']) for job in native for o in job['observations']}
    assert len(cells)==576 and len({job['table_path'] for job in native})==6
    assert len(embedded)==15 and sum(job['expected_outputs'] for job in embedded)==113
    assert len({(job['table_path'],o['name']) for job in embedded for o in job['observations']})==113
    assert Counter({kind:sum(job['expected_outputs'] for job in embedded if job['embedded_kind']==kind)
                    for kind in {job['embedded_kind'] for job in embedded}})=={
        'original_aswing_locked':43,'modified_aswing_locked':43,'modified_aswing_roll':27}
    assert len(inventory)==5 and {Path(job['model_path']).stem for job in inventory}=={'Roll','Straight_40O','Straight_60O','Straight_80O','Straight_95O'}
    assert all(job['expected_outputs']==0 and job['observations']==job['reference_rows']==job['required_components']==[] and
               job['table_path'] is None and job['blocker_code']=='NO_PAIRED_EXPORT' for job in inventory)
    assert all(not job['original_file_modified'] and not job['complete_family_reproduction'] for job in jobs)


def test_each_original_numeric_token_precision_and_source_position_survives(jobs):
    catalog=json.loads((ROOT/adapter.CATALOG).read_text())
    expected={(state['table_path'],item['name']):item for state in catalog['native_exports'] for item in state['observations']}
    for job in jobs:
        for item in job['observations']:
            number=Decimal(item['expected_token'].replace('D','E').replace('d','e'))
            assert item['expected']==float(number)
            assert item['tolerance']==float(Decimal(5).scaleb(number.as_tuple().exponent-1))
            line=item['raw_line'];start=item['source_character_1based']-1
            assert line[start:start+len(item['expected_token'])]==item['expected_token']
            assert item['exact_decimal_expected']==str(number)
            if job['source_group']=='native_fmat':
                original=expected[job['table_path'],item['name']]
                assert all(item[key]==value for key,value in original.items())
    zero=next(o for job in jobs for o in job['observations'] if o['expected_token']=='-0.000000')
    assert zero['negative_zero'] and math.copysign(1.,zero['expected'])==-1.
    assert zero['tolerance']==5e-7


def test_finite_control_original_pairing_and_prospective_meshes(jobs):
    workers=[job for job in jobs if job['target_kind']=='native_coefficients']
    assert len(workers)==12 and sum(job['expected_outputs'] for job in workers)==72
    assert {job['nominal'] for job in workers}=={80,160}
    assert sorted({job['condition']['speed'] for job in workers})==[27.0934,38.502,43.0429,47.234,50.9245,59.4556]
    for job in workers:
        assert job['target_kind']=='native_coefficients' and list(adapter.reference_contract(job))==list(adapter.NAMES)
        assert job['driver_path'].endswith('/Roll_rate.sh') and job['model_path'].endswith('/Straight_20O.asw')
        assert job['condition']['controls']=={'1':1.} and job['condition']['rates']==[0.,0.,0.]
        assert job['condition']['alpha']==job['condition']['beta']==job['condition']['mach']==0.
        assert job['condition']['density']==1.2256 and job['condition']['freeze_influences'] is True
        for name in ('cold_operating_setup','restored_operating_setup'):
            setup=adapter._expectations(job)[name]
            assert setup['frozen'] is True and setup['wind_angles']==[0.,0.]
        assert job['literal_reference']==adapter.REFERENCE and job['literal_reference'][0]==[.185,.15,1.2192]
        assert job['literal_weight_rows']==adapter.WEIGHTS and all(not any(row[5:]) for row in adapter.WEIGHTS)
        assert job['mandatory_stations']==[-.6096,-.8*.6096,0.,.8*.6096,.6096]
        assert .8*.6096 != .48768  # Preserve exact parsed scaling; no decimal re-rounding.
        assert len(job['native_context'])==17 and job['root_position']==[-.0523,0.,0.]
        assert job['expected_nodes']==job['nominal']+3 and job['expected_elements']==job['nominal']+2
        assert job['expected_operations']==dict(cold_solves=1,fresh_residuals=1,retries=0)


def test_every_native_auxiliary_channel_has_a_physical_worker(jobs):
    workers=[job for job in jobs if job['execution_route']=='worker' and job['target_kind']!='native_coefficients']
    assert len(workers)==18 and sum(job['expected_outputs'] for job in workers)==540
    assert Counter(job['target_kind'] for job in workers)=={
        'native_derivatives':6,'native_mass_properties':6,'native_normalized_rates':6}
    for job in workers:
        assert job['nominal']==80 and job['condition']['controls']=={'1':1.}
        assert job['observable_settings']['structural_operator']=='drela-moving-airflow-v1'
        assert job['observable_settings']['response']=='fixed_acceleration'
        assert job['expected_operations']==dict(cold_solves=1,fresh_residuals=1,retries=0,observable_batches=1)
        assert any(p['path'].endswith('/scripts/isae_ae3_observables.py') for p in job['source_pins'])


def test_embedded_series_keep_unplotted_rows_original_modified_and_witnesses_separate(jobs):
    embedded=[job for job in jobs if job['source_group']=='embedded_postprocessor']
    assert sum(len(job['observations'])-len(job['embedded_series']['plotted_rows']) for job in embedded)>0
    assert all(job['execution_route']=='unsupported' and job['condition'] is None and job['nominal'] is None for job in embedded)
    assert all(job['embedded_series']['witness'] and job['source_variant'] in ('20O','40O','60O','80O','95O') for job in embedded)
    assert all(item['source_name']==original['name'] for job in embedded
               for item,original in zip(job['observations'],job['embedded_series']['values'],strict=True))
    assert all('experiment' not in item['category'] for job in jobs for item in job['observations'])


def test_planning_and_every_blocked_scope_import_no_numerics(monkeypatch,jobs):
    real_import=builtins.__import__
    def guarded(name,*args,**kwargs):
        assert not name.startswith(('openswing','numpy','scipy')), 'Source-only planning imported physical code'
        return real_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    monkeypatch.setattr(adapter,'_execute',lambda *a:pytest.fail('Blocked target started a worker'))
    assert len(adapter.plan(ROOT))==50
    selected={job['target_kind']:job for job in jobs if job['execution_route']=='unsupported'}
    for job in selected.values():
        result=adapter.run(ROOT,job)
        assert result['status']=='unsupported' and result['physical_calls']==result['production_imports']==0
        assert result['operations']==job['expected_operations'] and len(result['reference_checks'])==job['expected_outputs']
        assert all(item['predicted'] is None and not item['passed'] for item in result['reference_checks'])
        assert adapter.validate_result_contract(job,result)


@pytest.mark.parametrize('fault',['speed','control','ground','influences','mesh','gravity','reference','weight','break','token','precision','model','context'])
def test_canonical_source_rebuild_rejects_mutation(jobs,fault):
    job=deepcopy(next(job for job in jobs if job['execution_route']=='worker'))
    if fault=='speed':job['condition']['speed']+=1.
    if fault=='control':job['condition']['controls']['1']=0.
    if fault=='ground':job['condition']['ground_effect']=1
    if fault=='influences':job['condition']['freeze_influences']=False
    if fault=='mesh':job['panels']['beams']['1']['count']+=1
    if fault=='gravity':job['gravity'][2]=0.
    if fault=='reference':job['literal_reference'][0][0]=.18580608
    if fault=='weight':job['literal_weight_rows'][0][5]=1.
    if fault=='break':job['mandatory_stations'].pop()
    if fault=='token':job['observations'][0]['expected_token']='0.0'
    if fault=='precision':job['observations'][0]['tolerance']*=2
    if fault=='model':job['literal_model_sha256']='0'*64
    if fault=='context':job['native_context'].pop()
    with pytest.raises(ValueError,match='differs from original'):adapter.verify_reference_sources(ROOT,job)


def test_independent_stability_axes_and_normalization_keep_literal_reference():
    values=adapter.coefficients([2.,3.,5.],[7.,11.,13.],0.,10.,2.,4.)
    assert values==dict(CX=-.2,CY=.3,CL=.5,Cl=-.175,Cm=.55,Cn=-.325)
    a=adapter.coefficients([2.,3.,5.],[7.,11.,13.],90.,10.,2.,4.)
    assert a==pytest.approx(dict(CX=-.5,CY=.3,CL=-.2,Cl=-.325,Cm=.55,Cn=.175))
    assert adapter.coefficients([4.,6.,10.],[14.,22.,26.],0.,20.,2.,4.)==values
    with pytest.raises(ValueError):adapter.coefficients([1.,2.,3.],[1.,2.,3.],0.,0.,1.,1.)


def test_strip_arms_and_engine_wrench_are_separate_from_coefficient_source():
    saved=dict(strips=[dict(position=[0.,2.,0.],force=[0.,0.,10.],moment=[0.,3.,0.])],
               engines=[dict(position=[0.,4.,0.],force=[5.,0.,0.],moment=[0.,0.,1.])])
    wrench=adapter.reconstruct_wrenches(saved,[0.,0.,0.])
    assert wrench['distributed_aero_force']==[0.,0.,10.] and wrench['distributed_aero_moment']==[20.,3.,0.]
    assert wrench['force']==[5.,0.,10.] and wrench['moment']==[20.,3.,-19.]
    aero=adapter.coefficients(wrench['distributed_aero_force'],wrench['distributed_aero_moment'],0.,10.,1.,2.)
    total=adapter.coefficients(wrench['force'],wrench['moment'],0.,10.,1.,2.)
    assert aero['CX']==0. and total['CX']==-.5 and aero['Cn']==0. and total['Cn']==.95


def physical_fixture(job):
    """Complete synthetic saved evidence, not a physical solve."""
    c=job['condition'];force=[.01,.02,.03];moment=[.04,.05,.06]
    values=adapter.coefficients(force,moment,c['alpha'],.5*c['density']*c['speed']**2*.185,.15,1.2192)
    expected=adapter._expectations(job);checks=[]
    for name,spec in adapter.PHYSICAL_CHECK_SPECS.items():
        item=dict(name=name,passed=True)
        if spec['kind']=='exact':
            value=expected.get(name,{'fixture':'same complete operator identity'})
            item.update(actual=deepcopy(value),expected=deepcopy(value))
        else:
            item.update(metric=0.,gate=job['numerical_gates'][spec['gate']])
            if spec['kind']=='vector':
                value=moment if name.endswith('moment') else force
                item.update(reported=list(value),reconstructed=list(value))
            elif spec['kind']=='balance':item.update(applied=[0.,0.,0.],support=[0.,0.,0.])
            elif spec['kind']=='clamp':
                value=job['root_position'] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                item.update(reported=list(value),expected=list(value))
            elif spec['kind']=='coefficients':item.update(reported=dict(values),reconstructed=dict(values),
                force=force,moment=moment,channels={name:0. for name in adapter.NAMES})
            elif spec['kind']=='parity':item.update(reported=dict(values),restored=dict(values),channels={name:0. for name in adapter.NAMES})
        checks.append(item)
    return checks,values


def computed_fixture(job):
    physical,values=physical_fixture(job);checks=adapter._checks(job,values)
    return dict(status='computed',numerical_pass=True,reference_match=all(item['passed'] for item in checks),
        source_pins_unchanged=True,kernel_pins_unchanged=True,physical_calls=2,
        operations=dict(cold_solves=1,fresh_residuals=1,retries=0),reference_checks=checks,physical_checks=physical)


def test_complete_saved_evidence_can_pass_physics_while_archive_disagrees(jobs):
    pair=[job for job in jobs if job['target_kind']=='native_coefficients' and job['native_operating_point']==1]
    results={job['id']:computed_fixture(job) for job in pair}
    for job in pair:
        assert len(results[job['id']]['physical_checks'])==29
        assert adapter.validate_result_contract(job,results[job['id']]) and not results[job['id']]['reference_match']
    row,=adapter.mesh_diagnostics(pair,results)
    assert row['status']=='COMPARED' and row['acceptance_gate'] is row['passed'] is None and len(row['channels'])==6
    assert all(item['abs_change']==0 for item in row['channels'].values())
    assert len(adapter.mesh_diagnostics(jobs,{}))==6
    assert all(row['status']=='UNAVAILABLE' for row in adapter.mesh_diagnostics(jobs,{}))
    assert adapter.mesh_diagnostics([],results)==[]
    assert adapter.mesh_diagnostics(pair[:1],results)[0]['status']=='UNAVAILABLE'


@pytest.mark.parametrize('fault',['missing','duplicate','residual','gate','source','kernel','calls','retry','prediction','wrench','coefficient',
                                  'cold_setup','restored_setup','restored_condition','clamp','balance','weights','precision','finite'])
def test_computed_claim_rejects_incomplete_or_inconsistent_physics(jobs,fault):
    job=deepcopy(next(job for job in jobs if job['execution_route']=='worker'));result=computed_fixture(job)
    checks={item['name']:item for item in result['physical_checks']}
    if fault=='missing':result['physical_checks'].pop()
    if fault=='duplicate':result['physical_checks'][-1]=deepcopy(result['physical_checks'][0])
    if fault=='residual':checks['fresh_full_residual']['metric']=1.
    if fault=='gate':job['numerical_gates']['residual']=1.
    if fault=='source':result['source_pins_unchanged']=False
    if fault=='kernel':result['kernel_pins_unchanged']=False
    if fault=='calls':result['physical_calls']=1
    if fault=='retry':result['operations']['retries']=1
    if fault=='prediction':result['reference_checks'][0]['predicted']+=1.
    if fault=='wrench':checks['independent_distributed_aero_moment']['reconstructed'][0]+=1.
    if fault=='coefficient':checks['independent_coefficient_mapping']['force'][0]+=1.
    if fault=='cold_setup':checks['cold_operating_setup']['actual']['density']=1.292
    if fault=='restored_setup':checks['restored_operating_setup']['actual']['frozen']=False
    if fault=='restored_condition':checks['restored_condition']['actual']['controls']['1']=0.
    if fault=='clamp':checks['root_clamp_position']['reported'][0]=0.
    if fault=='balance':checks['force_balance']['support'][0]=1.
    if fault=='weights':checks['inactive_null_weights']['actual']=2
    if fault=='precision':result['reference_checks'][0]['tolerance']*=2
    if fault=='finite':result['reference_checks'][0]['predicted']=float('nan')
    with pytest.raises(ValueError):adapter.validate_result_contract(job,result)


def test_blocked_native_and_embedded_cannot_promote_zero_or_arbitrary_predictions(jobs):
    for kind in adapter.BLOCKERS:
        job=next(job for job in jobs if job['target_kind']==kind)
        result=dict(status='computed',numerical_pass=True,reference_match=True,physical_calls=0,
            operations=deepcopy(job['expected_operations']),reference_checks=adapter._checks(job,{}))
        with pytest.raises(ValueError):adapter.validate_result_contract(job,result)
