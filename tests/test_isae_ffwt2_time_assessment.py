"""Independent known-unit outputs, missing references and numerical gate failures."""
import importlib.util
import json
import math
from pathlib import Path
import sys

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('ffwt2_assessment',SCRIPTS/'assess-isae-ffwt2-time.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def saved_fixture(folder,*,bad_residual=False,gap=False):
    def write(name,value):
        p=folder/name;p.write_text(json.dumps(value));return module.pin(p)
    marker=folder/'fixture.txt';marker.write_text('Synthetic native-output contract; no aircraft solve.')
    samples=[]
    for i in range(3):
        if gap and i==1:continue
        samples.append(dict(time=i*.01,converged=True,residual=2e-8 if bad_residual else 1e-12,
            frame=dict(angular_acceleration_body=[math.pi,0,0],rates_body=[math.radians(96 if i==2 else 90),0,0],attitude=[120,0,0]),
            restart=dict(state=dict(source_attitude=[-4*math.pi/3,0,0])),
            sensors=[dict(index=2,bank=170),dict(index=3,bank=1e-4 if i==2 else -170)]))
    result=write('result.json',dict(converged=True,temporal_policy='drela-euler-bdf-v1',maximum_step=.01,
        snapshots=samples,accepted_steps=2,rejected_steps=0))
    checkpoint=write('checkpoint.json',{'synthetic':True})
    write('report.json',dict(status='SEGMENT_COMPUTED',result=result,checkpoint=checkpoint,seconds=0))
    rows=[dict(line=i+1,tokens=[str(i),str(i*.01),'180.000','90.000',
          '-250.000' if i==2 else '-240.000','170.000',
          '0.000000000000E+00' if i==2 else '-170.000']) for i in (1,2,3)]
    write('plan.json',dict(source_pins=[module.pin(marker)],kernel_pins=[],helper=module.pin(marker),
        nominal=4,native_rows=rows,configuration='Synthetic',qualifications=['Fixture only']))


def test_all_channels_use_units_and_continuous_bank_without_filling_missing_rows(tmp_path):
    saved_fixture(tmp_path)
    report=module.assess(tmp_path)
    assert report['output_accounting']==dict(required=15,computed=10,missing=5,passed=8)
    assert report['numerical_pass'] and not report['reference_match']
    bank=[c for c in report['reference_checks'] if c['channel']=='bank_deg' and c['time']==.02][0]
    assert bank['predicted']==pytest.approx(-240)  # Not the principal +120-degree display.
    assert bank['passed'] and bank['relative_error']==pytest.approx(.04)
    zero=[c for c in report['reference_checks'] if c['channel']=='sensor3_bank_deg' and c['time']==.02][0]
    assert not zero['passed'] and zero['acceptance_basis']=='tiny_reference_original_strict'


def test_failed_solver_residual_cannot_earn_reference_passes(tmp_path):
    saved_fixture(tmp_path,bad_residual=True)
    report=module.assess(tmp_path)
    assert not report['numerical_pass'] and report['output_accounting']['passed']==0
    assert all(c['passed']==0 for c in report['channels'].values())


def test_missing_time_step_is_not_interpolated(tmp_path):
    saved_fixture(tmp_path,gap=True)
    with pytest.raises(AssertionError,match='Missing time step'):module.assess(tmp_path)


@pytest.mark.parametrize('defect',[None,'changed_prefix','changed_frozen_kernel'])
def test_versioned_continuation_checks_its_frozen_prefix(tmp_path,defect):
    old=tmp_path/'old';new=tmp_path/'new';old.mkdir();new.mkdir()
    saved_fixture(old);saved_fixture(new)
    read=lambda p:json.loads(p.read_text())
    def write(p,v):p.write_text(json.dumps(v));return module.pin(p)
    prior=read(old/'result.json')['snapshots'][-1]
    result=read(new/'result.json')
    result['snapshots']=[dict(prior,time=.02+i*.01) for i in range(3)]
    if defect=='changed_prefix':
        result['snapshots'][0]=dict(result['snapshots'][0],residual=2e-12,
            frame=dict(prior['frame'],rates_body=[0,0,0]))
    report=read(new/'report.json');report['result']=write(new/'result.json',result)
    write(new/'report.json',report)
    original=tmp_path/'time_integration.py';original.write_text('old derivative assembly')
    before=module.pin(original)
    frozen=tmp_path/'frozen.py';frozen.write_text(original.read_text())
    original.write_text('new derivative assembly')
    manifest=write(tmp_path/'manifest.json',[dict(original=before,frozen_path=str(frozen))])
    plan=read(new/'plan.json')
    plan.update(continuation_version=1,declared_segment_start=.02,
        prefix_checkpoint=module.pin(old/'checkpoint.json'),prefix_report=module.pin(old/'report.json'),
        frozen_prefix_manifest=manifest,kernel_pins=[module.pin(original)],
        kernel_upgrade=dict(changed_modules=['time_integration.py']))
    write(new/'plan.json',plan)
    if defect=='changed_frozen_kernel':frozen.write_text('different original kernel')
    if defect is not None:
        with pytest.raises(AssertionError):module.assess(new)
    else:
        assessed=module.assess(new)
        assert assessed['start_time']==.02 and assessed['unique_snapshots']==3
        assert assessed['output_accounting']['missing']==5  # t=.01 stays unavailable.


@pytest.mark.parametrize('defect',[None,'seed_pose','missing_replay','wrong_first_method'])
def test_declared_jig_start_requires_retained_seed_and_first_discrete_replay(tmp_path,defect):
    from copy import deepcopy
    saved_fixture(tmp_path)
    read=lambda name:json.loads((tmp_path/name).read_text())
    def write(name,value):
        p=tmp_path/name;p.write_text(json.dumps(value));return module.pin(p)
    result=read('result.json')
    result['snapshots']=[dict(s,time=.01+i*.01) for i,s in enumerate(result['snapshots'])]
    result['checkpoint_validation']=dict(discrete_replayed=defect!='missing_replay',residual=1e-12)
    raw=dict(time=0.,position_chart=dict(coordinates=[[0.,0.,0.]]),
        local_velocity=[[0.,0.,0.]],local_rates=[[0.,0.,0.]],rates_body=[0.,0.,0.],
        position_earth=[0.,0.,0.],source_attitude=[0.,0.,0.],
        body_to_earth=[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],velocity_origin_body=[-15.,0.,0.],
        network=dict(rotations=[[0.,0.,0.]],circulation=[0.]))
    if defect=='seed_pose':raw['position_chart']['coordinates'][0][1]=.1
    seed=dict(time=0.,initial_phase='declared_uncomputed_jig_seed',residual=.5,
        converged=False,restart=dict(state=raw))
    first=dict(snapshots=[seed,deepcopy(result['snapshots'][0])],accepted_steps=1,rejected_steps=0)
    first_checkpoint=dict(state=first['snapshots'][1]['restart']['state'],
        accepted_method=dict(kind='bdf',scheme='drela-euler-bdf-v1',
            effective_order=2 if defect=='wrong_first_method' else 1,previous=raw,previous2=None))
    plan=read('plan.json')
    plan.update(continuation_version=2,declared_segment_start=.01,
        startup='jig-zero-motion-zero-circulation',seed_residual=.5,
        first_step_result=write('first-step.json',first),
        first_checkpoint=write('first-checkpoint.json',first_checkpoint),
        preparation_helper=module.pin(tmp_path/'fixture.txt'))
    write('plan.json',plan)
    report=read('report.json');report['result']=write('result.json',result)
    write('report.json',report)
    if defect is not None:
        with pytest.raises(AssertionError):module.assess(tmp_path)
    else:
        assessed=module.assess(tmp_path)
        assert assessed['start_time']==.01 and assessed['unique_snapshots']==3
        assert assessed['numerical_pass']
        assert assessed['output_accounting']['computed']==15
        assert all(row['time']>0 for row in assessed['reference_checks'])


@pytest.mark.parametrize('restart_order',[1,2])
def test_original_second_run_requires_one_bdf1_step_then_bdf2(tmp_path,restart_order):
    from copy import deepcopy
    saved_fixture(tmp_path)
    read=lambda name:json.loads((tmp_path/name).read_text())
    def write(name,value):
        p=tmp_path/name;p.write_text(json.dumps(value));return module.pin(p)
    result=read('result.json');base=result['snapshots'][0]
    result['snapshots']=[]
    for tick in range(203):
        s=deepcopy(base);s['time']=tick*.01
        s['restart']['accepted_method']=dict(effective_order=restart_order if tick==201 else 2)
        result['snapshots'].append(s)
    child=tmp_path/'restart';child.mkdir()
    continued=deepcopy(result);continued['snapshots']=continued['snapshots'][200:];continued['accepted_steps']=2
    result['snapshots']=result['snapshots'][:201];result['accepted_steps']=200
    report=read('report.json');report['result']=write('result.json',result);write('report.json',report)
    plan=read('plan.json');plan.update(command_restarts=[2.],parent_checkpoint=module.pin(tmp_path/'checkpoint.json'))
    write('restart/plan.json',plan)
    child_report=dict(report,result=write('restart/result.json',continued),
        checkpoint=write('restart/checkpoint.json',{'synthetic':True}))
    write('restart/report.json',child_report)
    if restart_order==2:
        with pytest.raises(AssertionError,match='Wrong command-restart stencil'):module.assess(child)
    else:
        assessed=module.assess(child)
        assert assessed['unique_snapshots']==203 and assessed['numerical_pass']
        assert assessed['command_restarts']==[2.]
