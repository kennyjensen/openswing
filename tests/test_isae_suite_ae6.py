"""Source accounting and corruption rejection; synthetic pencils are not validation."""
import builtins
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from scripts import isae_suite_ae6 as a
from scripts.isae_acceptance import apply_reference_acceptance


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


RUNNER=load('ae6_runner','scripts/run-isae-suite.py')
SUMMARY=load('ae6_summary','scripts/summarize-isae-suite.py')


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation/manifest.json').exists():
        pytest.skip('Optional original archive unavailable')
    return RUNNER.plan_jobs(ROOT,['ae6'],comparison_scopes=[a.SCOPE])


@pytest.fixture(scope='module')
def job(jobs):
    return next(j for j in jobs if j['id']=='AE-6:declared:Weight7a:op002:n32')


@pytest.fixture(scope='module')
def raw(job):
    nodes=job['nominal']+2;n=19*nodes-1
    matrix=np.eye(n);mass=np.eye(n);modes=[]
    def split(v):return dict(real=v.real.tolist(),imag=v.imag.tolist())
    poles=[complex(*r['eigenvalue'])*1.02 for r in job['reference_rows']]
    poles[0]=complex(poles[0].real,poles[0].imag*1.4)
    poles += [complex(-3000-10*i,1000+10*i) for i in range(16-len(poles))]
    for i,pole in enumerate(poles):
        start=20+2*i
        matrix[start:start+2,start:start+2]=[[pole.real,-pole.imag],[pole.imag,pole.real]]
        v=np.zeros(n,dtype=complex);v[start:start+2]=np.array([1.,-1j])/np.sqrt(2)
        modes.append(dict(eigenvalue=[pole.real,pole.imag],right=split(v),left=split(v)))
    return dict(converged=True,frame_mode='fixed',vacuum=False,modes=modes,matrices=dict(A=matrix.tolist(),M=mass.tolist()),
        diagnostics=dict(structural_operator='drela-moving-airflow-v1',method='full_shift_invert',requested_count=16,
            shift=[0.,300.],base_residual=1e-15,state_layout=dict(node_coordinates=dict(start=0),
                local_velocity=dict(start=13*nodes-1,width=3*nodes),local_rates=dict(start=16*nodes-1,width=3*nodes),
                circulation=dict(width=nodes-1),frame=dict(width=0))),
        base=dict(converged=True,structural_nodes=nodes,structural_elements=nodes-1,gravity_body=[0.,0.,-9.81],
            ground_plane=dict(flag=0,kind='off'),reference_flow=dict(speed=120.5,alpha=0.,beta=0.,
                equivalent_airspeed=120.5,dynamic_pressure=.5*1.0771417304*120.5**2),
            atmosphere=dict(density=1.0771417304,density_source='override',density_ratio=1.,altitude_m=0.,
                sound_speed=340.21,gravity_magnitude=9.81,equivalent_airspeed=120.5,
                dynamic_pressure=.5*1.0771417304*120.5**2),CL=None,CD=None))


@pytest.fixture(scope='module')
def synthetic(job,raw):
    return a.assess_raw(job,raw,a.request(job,(ROOT/job['model_path']).read_text()))


def test_complete_inventory_speed_mapping_and_denominators(jobs):
    historical=[j for j in jobs if j['comparison_scope']=='historical-modal-exports']
    declared=[j for j in jobs if j['comparison_scope']==a.SCOPE]
    assert len(historical)==6 and sum(j['expected_outputs'] for j in historical)==3348
    assert len(declared)==446 and sum(j['expected_outputs'] for j in declared)==6696
    blocked=[j for j in declared if j['execution_route']=='unsupported']
    assert len(blocked)==80 and sum(j['expected_outputs'] for j in blocked)==1200
    for j in declared:
        assert j['IAS']==j['commanded_speeds'][j['native_index']-1]
        assert j['nominal'] in (32,64)
    scope=SUMMARY.declared_scope(jobs)
    assert scope['ae6_modal_tables']==6 and scope['ae6_stored_modal_rows']==1674
    assert scope['ae6_declared_scalar_slots']==6696 and scope['ae6_all_modal_tables_duplicate_st4']
    assert SUMMARY.totals(jobs)['unrun_required']==10044
    assert len(a.mesh_diagnostics(jobs,{}))==223
    assert all(r['status']=='INCOMPLETE' for r in a.mesh_diagnostics(jobs,{}))


def test_blockers_import_no_production_or_numerical_modules(jobs,monkeypatch):
    original=builtins.__import__
    def guard(name,*args,**kwargs):
        if name.split('.')[0] in ('openswing','numpy','scipy'):
            raise AssertionError('Blocked route imported '+name)
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guard)
    baseline=RUNNER.plan_jobs(ROOT,['ae6'])
    assert len(baseline)==6 and all(j['execution_route']=='unsupported' for j in baseline)
    j=next(j for j in jobs if j['id']=='AE-6:declared:Weight0:op001:n32')
    for record in (baseline[0],j):
        result=RUNNER.checked_result(record,a.validate_blocked(ROOT,record))
        assert result['status']=='unsupported' and result['output_accounting']['passed']==0
        assert SUMMARY.scalar_counts(dict(record,result=result))['reported_unavailable']==record['expected_outputs']


def test_request_matches_independent_retained_anchor_prepare(job,tmp_path):
    payload,plan=a.helper().prepare(tmp_path/'anchor',32)
    assert payload==a.request(job,(ROOT/job['model_path']).read_text())
    assert job['reference_rows']==plan['targets']


@pytest.mark.parametrize('group,density',[
    ('Weight0',1.0771417304),('Weight7a',1.0771417304),('Weight7c',1.0771417304),
    ('Weight7d',1.1369256734),('Weight7e',1.1956788587),('Weight7f',1.1338334005)])
def test_each_configuration_uses_its_own_original_density(jobs,group,density):
    j=next(j for j in jobs if j['id']==f'AE-6:declared:{group}:op002:n32')
    source=(ROOT/j['model_path']).read_text()
    payload=a.request(j,source)
    assert payload['condition']['density']==density
    if group!='Weight0':
        from openswing.asw import parse_asw
        from openswing.aero import FlightCondition
        from openswing.atmosphere import operating_air
        model=parse_asw(source)
        assert list(model.constants)==[9.81,density,340.21]
        air=operating_air(model,FlightCondition(speed=j['IAS'],alpha=0.))
        assert air['density']==payload['condition']['density']
        assert air['equivalent_airspeed']==j['IAS'] and air['density_ratio']==1.
    assert j['source_constants']==a.literal_constants(source)


def test_five_percent_is_separate_from_pencil_and_mesh_gates(job,synthetic):
    checked=RUNNER.checked_result(job,deepcopy(synthetic))
    assert checked['status']=='computed'
    view=apply_reference_acceptance(checked)
    assert view['output_accounting']['passed']==11
    assert SUMMARY.scalar_counts(dict(job,result=view))['passed']==11
    assert len(view['numerical_evidence']['eigenvalues'])==16
    assert job['mesh_relative_gate']==.001


@pytest.mark.parametrize('fault',[
    'missing_root','detached_root','bad_pencil','bad_mass','bad_clamp','wrong_shift','wrong_frame',
    'wrong_mesh','wrong_dimension','wrong_layout','wrong_wall','wrong_density','wrong_speed','wrong_payload',
    'wrong_IAS','wrong_pressure','wrong_altitude','wrong_sound','wrong_source_constants',
    'fake_coefficient','claim_historical','missing_qualification','extra_solve','changed_prediction',
    'changed_target','changed_coordinates','missing_component'])
def test_runner_and_summary_reject_corrupted_evidence(job,synthetic,fault):
    j,r=deepcopy(job),deepcopy(synthetic);e=r['numerical_evidence']
    if fault=='missing_root':e['eigenvalues'].pop()
    elif fault=='detached_root':e['eigenvalues'][0]=[42.,42.]
    elif fault=='bad_pencil':e['pencil_proofs'][0]['residual_norms'][0]=1e6
    elif fault=='bad_mass':e['pencil_proofs'][0]['mass_pair']=[0.,0.]
    elif fault=='bad_clamp':e['pencil_proofs'][0]['clamp_norm']=1.
    elif fault=='wrong_shift':e['shift']=[0.,200.]
    elif fault=='wrong_frame':e['frame']='free'
    elif fault=='wrong_mesh':e['nodes']+=1
    elif fault=='wrong_dimension':e['full_dimension']-=6
    elif fault=='wrong_layout':e['layout']['local_rates']['start']+=1
    elif fault=='wrong_wall':e['wall']['flag']=1
    elif fault=='wrong_density':e['atmosphere']['density']=1.23
    elif fault=='wrong_speed':e['reference_flow']['speed']=120.
    elif fault=='wrong_IAS':e['reference_flow']['equivalent_airspeed']=119.
    elif fault=='wrong_pressure':e['atmosphere']['dynamic_pressure']*=.95
    elif fault=='wrong_altitude':e['atmosphere']['altitude_m']=100.
    elif fault=='wrong_sound':e['atmosphere']['sound_speed']=330.
    elif fault=='wrong_source_constants':j['source_constants']['density']=1.23
    elif fault=='wrong_payload':e['request']['condition']['freeze_influences']=True
    elif fault=='fake_coefficient':e['CL']=0.
    elif fault=='claim_historical':r['historical_settings_authenticated']=True
    elif fault=='missing_qualification':r['qualifications']=[]
    elif fault=='extra_solve':r['operations']['retries']=1
    elif fault=='changed_prediction':r['reference_checks'][0]['predicted']=-21.
    elif fault=='changed_target':j['reference_rows'][0]['tokens'][1]='-21.000'
    elif fault=='changed_coordinates':j['IAS']+=.5
    elif fault=='missing_component':r['reference_checks'].pop()
    checked=RUNNER.checked_result(j,r)
    assert checked['status']=='adapter_contract_failure'
    assert checked['output_accounting']['numerically_valid']==0
    with pytest.raises((ValueError,KeyError)):
        SUMMARY.scalar_counts(dict(j,result=r))


def test_literal_model_mutation_rejected_before_a_solve(job,tmp_path):
    # One altered file suffices; all other sources stay read-only symlinks.
    import shutil
    root=tmp_path/'root';root.mkdir()
    (root/'scripts').symlink_to(ROOT/'scripts',target_is_directory=True)
    for p in job['source_pins']:
        target=root/p['path'];target.parent.mkdir(parents=True,exist_ok=True)
        if p['path']==job['model_path']:
            shutil.copyfile(ROOT/p['path'],target);target.write_text(target.read_text()+'# altered\n')
        else:target.symlink_to(ROOT/p['path'])
    with pytest.raises(ValueError,match='original bytes changed'):
        a.validate_record_contract(job,root)


def test_driver_increment_cannot_silently_shift_point_mapping(job):
    text=(ROOT/job['driver_path']).read_text()
    with pytest.raises(ValueError,match='operating'):
        a.driver_speeds(text.replace('+\n!V 120.5','!V 120.5',1))


def test_constant_decoder_preserves_last_line_and_units():
    text='Units\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.81 1.2 340\n# last line wins\n9.8 1.15D0 330\nEnd\n'
    constants=a.literal_constants(text)
    assert constants==dict(line=9,tokens=['9.8','1.15D0','330'],gravity=9.8,density=1.15,sound_speed=330.)
    with pytest.raises(ValueError,match='SI units'):
        a.literal_constants(text.replace('L 1 m','L 0.3048 ft'))
    with pytest.raises(ValueError,match='invalid Constant'):
        a.literal_constants(text.replace('1.15D0','nan'))


def test_full_artifacts_are_reassessed_after_hash_verification(job,raw,synthetic,tmp_path):
    folder=tmp_path/'evidence';folder.mkdir()
    for name,data in [('request',synthetic['numerical_evidence']['request']),('plan',job),('result',raw),('report',synthetic)]:
        a._write(folder/(name+'.json'),data)
    result=deepcopy(synthetic)
    def pins():return [a.pin(tmp_path,p.relative_to(tmp_path)) for p in sorted(folder.iterdir())]
    result['artifacts']=pins()
    a.verify_artifacts(tmp_path,result)
    changed=deepcopy(raw);changed['modes'][0]['right']['real'][20]+=1.
    a._write(folder/'result.json',changed);result['artifacts']=pins()
    with pytest.raises(ValueError,match='full physical evidence'):
        a.verify_artifacts(tmp_path,result)
