"""Accounting and one complete archived P-1 component job, no aircraft solve."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('isae_suite_components',ROOT/'scripts/isae_suite_components.py')
ADAPTER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ADAPTER)


def test_plan_covers_all_six_archived_curves_without_experimental_targets():
    jobs=ADAPTER.plan(ROOT)
    assert len(jobs)==6
    assert all(j['case_id']=='P-1' and j['adapter']=='components' for j in jobs)
    assert sum(j['expected_output_count'] for j in jobs)==110
    assert [j['coordinate_count'] for j in jobs]==[20,20,20,20,15,15]
    assert len({(j['settings']['blades'],r['rpm']) for j in jobs for r in j['observations']})==55
    assert all(not j['reference']['experimental_comparison_performed'] for j in jobs)
    assert all(j['numerical_gate']==dict(quantity='absolute CT difference',comparison='<',value=2e-12) for j in jobs)
    json.dumps(jobs,allow_nan=False)


def test_prepared_reference_gate_cannot_be_widened():
    job=deepcopy(ADAPTER.plan(ROOT)[0]);job['numerical_gate']['value']=1
    with pytest.raises(ValueError,match='numerical_gate'):
        ADAPTER.run(ROOT,job)


def test_four_blade_inviscid_component_matches_every_archived_scalar():
    job=next(j for j in ADAPTER.plan(ROOT) if j['id']=='P-1-4blade-PvOFF')
    report=ADAPTER.run(ROOT,job)
    assert report['status']=='computed' and report['reference_match']
    assert len(report['reference_checks'])==15
    assert all(check['passed'] for check in report['reference_checks'])
    assert report['accounting']['required_outputs']==report['accounting']['computed_outputs']==report['accounting']['passed_outputs']==15
    assert report['accounting']['missing_outputs']==report['accounting']['unrun_outputs']==0
    assert report['maximum_absolute_CT_difference']<2e-12
    assert report['rows'][0]['predicted_CT']==pytest.approx(.3441123185749631,abs=2e-12,rel=0)
    assert report['operations']['engine_load_calls']==15
    assert report['operations']['aircraft_solves']==0
    json.dumps(report,allow_nan=False)
