"""Guard the distinct ST-5 native denominator and independent validity gates."""
import importlib.util
from pathlib import Path

MODULE=Path(__file__).resolve().parents[1]/'scripts/assess_st5_convergence.py'
spec=importlib.util.spec_from_file_location('st5_convergence_acceptance',MODULE)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def good():
    return {i:True for i in range(5)},{str(i):True for i in range(14)}


def test_native_miss_is_retained_after_successful_convergence():
    states,mesh=good()
    result=audit.qualify(1120,1119,states,mesh)
    assert result['qualified']
    assert (result['passed'],result['required'])==(1119,1120)


def test_missing_refinement_retains_every_native_target():
    states,mesh=good();del states[4]
    result=audit.qualify(1120,1120,states,mesh)
    assert not result['qualified']
    assert (result['passed'],result['required'])==(0,1120)


def test_failed_intermediate_physical_state_cannot_be_skipped():
    states,mesh=good();states[2]=False
    assert audit.qualify(812,812,states,mesh)['passed']==0


def test_one_failed_mesh_field_prevents_qualification():
    states,mesh=good();mesh['13']=False
    result=audit.qualify(1120,1120,states,mesh)
    assert not result['mesh_complete'] and result['passed']==0


def test_missing_mesh_field_cannot_reduce_requirement():
    states,mesh=good();del mesh['13']
    assert audit.qualify(1120,1120,states,mesh)['passed']==0


def test_report_strings_are_not_boolean_physical_evidence():
    states,mesh=good();states[4]='true'
    assert audit.qualify(1120,1120,states,mesh)['passed']==0
