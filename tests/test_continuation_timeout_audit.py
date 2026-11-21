"""A timeout may expose a saved boundary, but must never imply process success."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('continuation_audit_v2',
    Path(__file__).resolve().parents[1]/'scripts/assess-isae-ffwt4-continuation-v2.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


@pytest.fixture
def boundary(tmp_path):
    raw=b'{"continuation_status":"pending"}'
    (tmp_path/'result.json').write_bytes(raw)
    (tmp_path/'execution.json').write_text(json.dumps(dict(exit_code=124)))
    (tmp_path/'report.json').write_text(json.dumps(dict(status='ACCEPTED_CONTINUATION',
        seconds=65.,accepted_steps=2,rebuilt_residual=2e-13,
        result=dict(path=str(tmp_path/'result.json'),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))))
    return tmp_path


def test_timeout_requires_explicit_opt_in(boundary):
    with pytest.raises(AssertionError,match='Unaccepted process exit'):
        audit.completed_output(boundary)
    execution,_,_=audit.completed_output(boundary,True)
    assert execution['exit_code']==124


@pytest.mark.parametrize('code',[1,137,-9])
def test_other_termination_is_not_recovered(boundary,code):
    (boundary/'execution.json').write_text(json.dumps(dict(exit_code=code)))
    with pytest.raises(AssertionError,match='Unaccepted process exit'):
        audit.completed_output(boundary,True)


@pytest.mark.parametrize('name',['result.json','report.json'])
def test_incomplete_output_is_rejected(boundary,name):
    (boundary/name).unlink()
    with pytest.raises(FileNotFoundError):audit.completed_output(boundary,True)


def test_changed_result_is_rejected(boundary):
    (boundary/'result.json').write_text('{"continuation_status":"changed"}')
    with pytest.raises(AssertionError):audit.completed_output(boundary,True)


def test_helper_failure_is_rejected(boundary):
    (boundary/'failure.json').write_text('{}')
    with pytest.raises(AssertionError,match='Helper reported failure'):
        audit.completed_output(boundary,True)


@pytest.mark.parametrize('change',[dict(status='RUNNING'),dict(rebuilt_residual=1e-6),
    dict(rebuilt_residual=float('nan')),dict(accepted_steps=0)])
def test_incomplete_or_unconverged_report_is_rejected(boundary,change):
    p=boundary/'report.json';value=json.loads(p.read_text());value.update(change)
    p.write_text(json.dumps(value))
    with pytest.raises(AssertionError):audit.completed_output(boundary,True)
