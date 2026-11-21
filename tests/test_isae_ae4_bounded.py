"""Resumable AE-4 work must preserve failed attempts and unavailable targets."""
from pathlib import Path
import pytest
from scripts import replay_isae_ae4_bounded as r


def job(number,scope='ae4-undeformed-alpha0',route='worker'):
    return dict(id=f'job{number}',execution_route=route,IAS=number,nominal=40,
                comparison_scope=scope,expected_outputs=6,blocker_code=None)


def test_terminal_failure_is_preserved_and_selection_advances(tmp_path):
    plan=dict(jobs=[job(69),job(70)])
    folder=tmp_path/'jobs/job69';folder.mkdir(parents=True)
    r.write(folder/'terminal.json',dict(status='timeout'))
    assert r.choose_job(plan,tmp_path)['id']=='job70'
    assert r.choose_job(plan,tmp_path,speed=69) is None
    assert r.read(folder/'terminal.json')==dict(status='timeout')


def test_unterminated_attempt_cannot_trigger_a_second_solve(tmp_path):
    (tmp_path/'jobs/job69').mkdir(parents=True)
    with pytest.raises(ValueError,match='unterminated'):
        r.choose_job(dict(jobs=[job(69)]),tmp_path)


def test_summary_retains_failed_and_blocked_values_in_separate_scopes(tmp_path,monkeypatch):
    jobs=[job(69),job(70),job(1,route='unsupported'),job(2,scope='historical-modal-exports',route='unsupported')]
    folder=tmp_path/'jobs/job69';folder.mkdir(parents=True)
    r.write(folder/'terminal.json',dict(status='timeout'))
    monkeypatch.setattr(r.adapter,'mesh_diagnostics',lambda jobs,results:[])
    report=r.summarize(tmp_path,dict(jobs=jobs))
    scope=report['scopes']['ae4-undeformed-alpha0']
    assert (scope['required'],scope['passed'],scope['unrun'],scope['blocked'],scope['failed'])==(18,0,6,6,6)
    assert scope['unavailable']==18
    assert report['scopes']['historical-modal-exports']['required']==6


def test_computed_result_requires_reaped_source_verified_receipt(tmp_path):
    folder=tmp_path/'jobs/job69';folder.mkdir(parents=True)
    r.write(folder/'terminal.json',dict(status='computed',returncode=0,process_reaped=False,sources_unchanged=True))
    with pytest.raises(ValueError,match='terminal receipt'):
        r.summarize(tmp_path,dict(jobs=[job(69)]))


def test_real_os_lock_rejects_second_invocation_and_releases(tmp_path,monkeypatch):
    monkeypatch.setattr(r,'ROOT',tmp_path)
    with r.serial_lock():
        with pytest.raises(RuntimeError,match='serial lock'):
            with r.serial_lock():pass
    with r.serial_lock():pass
