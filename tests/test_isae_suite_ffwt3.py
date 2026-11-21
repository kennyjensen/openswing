"""Original gust histories stay visible without guessing incompatible inputs."""
import builtins
from copy import deepcopy
from functools import lru_cache
import importlib.util
from pathlib import Path
import sys

import pytest
from scripts import isae_suite_ffwt3 as adapter
from scripts.isae_acceptance import apply_reference_acceptance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


@lru_cache(maxsize=None)
def module(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'scripts'/name)
    loaded=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture(scope='module')
def jobs():
    return adapter.plan(ROOT)


def test_all_history_rows_and_missing_output_slots_are_retained(jobs):
    assert len(jobs)==27
    assert sum(j['expected_outputs'] for j in jobs)==36462
    assert sum(j['retained_reference_values'] for j in jobs)==35256
    for job in jobs:
        assert len({o['name'] for o in job['observations']})==job['expected_outputs']
        assert job['expected_outputs']==job['scheduled_rows']*6
        assert job['execution_route']=='unsupported'
    by_name={j['output_basename']:j for j in jobs}
    mismatched=by_name['Free_Sweep_10_A-10']
    assert mismatched['native_rows']==701 and mismatched['time_range']==[0.,2.45]
    assert 'DRIVER_OUTPUT_TIME_GRID_MISMATCH' in mismatched['blocker_codes']
    orphan=by_name['Free_Sweep_10_A30']
    assert orphan['native_rows']==351 and orphan['driver_contract'] is None
    assert orphan['blocker_codes'][-1]=='MISSING_ORIGINAL_DRIVER'
    missing=by_name['Free_Sweep_30_A-10']
    assert missing['native_rows']==0 and missing['expected_outputs']==1206
    assert all(o['expected'] is None and o['tolerance'] is None for o in missing['observations'])


def test_registration_and_blocked_route_need_no_physics_imports(jobs,monkeypatch):
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        assert name.split('.')[0] not in ('numpy','scipy','openswing')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    for job in jobs:
        result=adapter.run(ROOT,job)
        assert result['status']=='unsupported' and result['physical_calls']==0


def test_five_percent_cannot_pass_uncomputed_or_missing_values(jobs):
    runner,summary=module('run-isae-suite.py'),module('summarize-isae-suite.py')
    for job in jobs:
        result=runner.checked_result(job,adapter.run(ROOT,job))
        assert result['status']=='unsupported'
        accepted=apply_reference_acceptance(result)
        counts=summary.scalar_counts(dict(job,result=accepted))
        assert counts['passed']==counts['numerically_valid_finite']==0
        assert counts['required']==job['expected_outputs']


@pytest.mark.parametrize('fault',['prediction','numerical','computed','physical','drop','duplicate',
                                  'target','precision','code','qualification','whole_family'])
def test_fabricated_outputs_and_lost_blockers_are_rejected(jobs,fault):
    job=jobs[0]
    result=adapter.run(ROOT,job)
    if fault=='prediction':result['reference_checks'][0]['predicted']=1.
    if fault=='numerical':result['numerical_pass']=True
    if fault=='computed':result['status']='computed'
    if fault=='physical':result['physical_calls']=1
    if fault=='drop':result['reference_checks'].pop()
    if fault=='duplicate':result['reference_checks'][-1]=result['reference_checks'][0]
    if fault=='target':result['reference_checks'][0]['expected']=123.
    if fault=='precision':result['reference_checks'][0]['tolerance']=5.
    if fault=='code':result['blocker_codes']=[]
    if fault=='qualification':result['qualifications']=[]
    if fault=='whole_family':result['full_family_validated']=True
    runner,summary=module('run-isae-suite.py'),module('summarize-isae-suite.py')
    assert runner.checked_result(job,result)['status']=='adapter_contract_failure'
    with pytest.raises(ValueError):summary.scalar_counts(dict(job,result=result))


def test_source_coordinates_cannot_be_silently_repaired(jobs):
    job=deepcopy(jobs[0])
    job['model_contract']['out_of_range_joints'][0]['station']=.6591
    with pytest.raises(ValueError,match='prepared source contract'):
        adapter.verify_reference_sources(ROOT,job)


def test_literal_models_confirm_joint_blocker_and_valid_sensors():
    audit=module('verify-isae-ffwt3-sources.py')
    for path in sorted(adapter.sources(ROOT)[1].glob('*.asw')):
        result=audit.audit_model(path)
        assert len(result['out_of_range_joints'])==(2 if path.stem.endswith('_10') else 4)
        assert len(result['meshing_rejections'])==2
        assert all(s['inside'] for s in result['sensors'])
