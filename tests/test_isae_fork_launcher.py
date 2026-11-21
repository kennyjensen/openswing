"""Real process isolation and supervisor termination, without numerical solves."""
import asyncio
import json
import importlib.util
import mmap
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

import pytest

from scripts.isae_fork_launcher import make_launcher, make_server_launcher

STATE = []


def isolated_worker(request, output):
    STATE.append('child-only')
    Path(output).write_text(json.dumps(dict(state=STATE, pid=os.getpid(), session=os.getsid(0),
        temp=tempfile.gettempdir(), threads=os.environ['OPENBLAS_NUM_THREADS'], argv=sys.argv)))


def sleeping_worker(request, output):
    Path(output).write_text('started')
    time.sleep(60)


def exiting_worker(request, output):
    raise SystemExit(7)


def env_for(folder):
    return dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                MKL_NUM_THREADS='1', TMPDIR=str(folder))


def test_fresh_child_memory_environment_and_temporary_directory(tmp_path):
    tempfile.gettempdir()  # Prime the parent's different temporary-directory cache.
    launch = make_launcher(isolated_worker, __file__)
    parent_temp = tempfile.gettempdir()
    async def run():
        values = []
        for index in range(2):
            folder = tmp_path/str(index)
            folder.mkdir()
            output = folder/'result.json'
            with (folder/'stdout').open('wb') as out, (folder/'stderr').open('wb') as err:
                process = await launch(sys.executable, __file__, '--worker', 'request', str(output),
                    cwd=folder, env=env_for(folder), stdout=out, stderr=err, start_new_session=True)
                assert await process.wait() == 0
                assert await process.wait() == 0  # Repeated waits must not reap another process.
            value = json.loads(output.read_text())
            assert value['state'] == ['child-only']
            assert value['pid'] == value['session'] == process.pid
            assert value['temp'] == str(folder) and value['threads'] == '1'
            assert value['argv'] == [__file__, '--worker', 'request', str(output)]
            values.append(value)
        assert values[0]['pid'] != values[1]['pid']
    asyncio.run(run())
    assert STATE == [] and tempfile.gettempdir() == parent_temp


def test_timed_out_child_can_be_terminated_and_reaped(tmp_path):
    launch = make_launcher(sleeping_worker, __file__)
    async def run():
        output = tmp_path/'result.json'
        with (tmp_path/'stdout').open('wb') as out, (tmp_path/'stderr').open('wb') as err:
            process = await launch(sys.executable, __file__, '--worker', 'request', str(output),
                cwd=tmp_path, env=env_for(tmp_path), stdout=out, stderr=err, start_new_session=True)
            try:
                async def started():
                    while not output.exists():
                        await asyncio.sleep(.02)
                await asyncio.wait_for(started(), 5.)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), .25)
            finally:
                if output.exists():
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    os.kill(process.pid, signal.SIGTERM)
                assert await process.wait() == -signal.SIGTERM
            with pytest.raises(ChildProcessError):
                os.waitpid(process.pid, os.WNOHANG)
    asyncio.run(run())


def test_explicit_child_failure_keeps_exit_code(tmp_path):
    launch = make_launcher(exiting_worker, __file__)
    async def run():
        with (tmp_path/'stdout').open('wb') as out, (tmp_path/'stderr').open('wb') as err:
            process = await launch(sys.executable, __file__, '--worker', 'request', 'output',
                cwd=tmp_path, env=env_for(tmp_path), stdout=out, stderr=err, start_new_session=True)
            assert await process.wait() == 7
    asyncio.run(run())


def test_multithreaded_parent_rejected_before_fork(tmp_path, monkeypatch):
    launch = make_launcher(isolated_worker, __file__)
    monkeypatch.setattr(os, 'listdir', lambda path: ['one', 'two'])
    monkeypatch.setattr(os, 'fork', lambda: pytest.fail('Unsafe parent reached fork'))
    async def run():
        with (tmp_path/'stdout').open('wb') as out, (tmp_path/'stderr').open('wb') as err:
            with pytest.raises(RuntimeError, match='multithreaded'):
                await launch(sys.executable, __file__, '--worker', 'request', 'output',
                    cwd=tmp_path, env=env_for(tmp_path), stdout=out, stderr=err, start_new_session=True)
    asyncio.run(run())


@pytest.mark.parametrize('change', ['threads', 'command', 'session'])
def test_invalid_launch_rejected_before_fork(tmp_path, monkeypatch, change):
    launch = make_launcher(isolated_worker, __file__)
    monkeypatch.setattr(os, 'fork', lambda: pytest.fail('Invalid launch reached fork'))
    async def run():
        env = env_for(tmp_path)
        command = [sys.executable, __file__, '--worker', 'request', 'output']
        if change == 'threads':
            env['OMP_NUM_THREADS'] = '2'
        if change == 'command':
            command[2] = '--unexpected'
        with (tmp_path/'stdout').open('wb') as out, (tmp_path/'stderr').open('wb') as err:
            with pytest.raises(ValueError):
                await launch(*command, cwd=tmp_path, env=env, stdout=out, stderr=err,
                             start_new_session=change != 'session')
    asyncio.run(run())


def test_clean_server_excludes_parent_maps_and_keeps_children_separate(tmp_path):
    worker = tmp_path/'worker.py'
    worker.write_text('''import json,os,tempfile
from pathlib import Path
STATE=[]
def worker(request,output):
 STATE.append(1)
 Path(output).write_text(json.dumps(dict(state=STATE,pid=os.getpid(),session=os.getsid(0),
   maps=Path('/proc/self/maps').read_text(),temp=tempfile.gettempdir())))
''')
    marker = tmp_path/'parent-only-results-map'
    marker.write_bytes(b'\0'*4096)
    launcher = make_server_launcher(worker, [])
    with marker.open('r+b') as stream, mmap.mmap(stream.fileno(), 4096) as mapping:
        assert str(marker) in Path('/proc/self/maps').read_text()
        async def run():
            seen=[]
            for index in range(2):
                folder=tmp_path/str(index);folder.mkdir();output=folder/'result.json'
                with (folder/'stdout').open('wb') as out, (folder/'stderr').open('wb') as err:
                    process=await launcher(sys.executable,str(worker),'--worker','request',str(output),
                        cwd=folder,env=env_for(folder),stdout=out,stderr=err,start_new_session=True)
                    assert await asyncio.wait_for(process.wait(),10) == 0
                    assert await process.wait() == 0
                value=json.loads(output.read_text())
                assert value['state'] == [1]
                assert value['pid'] == value['session'] == process.pid
                assert value['temp'] == str(folder)
                assert str(marker) not in value['maps']
                seen.append(value['pid'])
            assert seen[0] != seen[1]
        asyncio.run(run())


def test_clean_server_timeout_is_reaped(tmp_path):
    worker=tmp_path/'worker.py'
    worker.write_text('from pathlib import Path\nimport time\ndef worker(request,output):\n Path(output).write_text("started")\n time.sleep(60)\n')
    launcher=make_server_launcher(worker, [])
    async def run():
        output=tmp_path/'result.json'
        with (tmp_path/'stdout').open('wb') as out,(tmp_path/'stderr').open('wb') as err:
            process=await launcher(sys.executable,str(worker),'--worker','request',str(output),
                cwd=tmp_path,env=env_for(tmp_path),stdout=out,stderr=err,start_new_session=True)
            try:
                async def started():
                    while not output.exists():await asyncio.sleep(.02)
                await asyncio.wait_for(started(),10)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(),.2)
            finally:
                if output.exists():os.killpg(process.pid,signal.SIGTERM)
                else:os.kill(process.pid,signal.SIGTERM)
                assert await asyncio.wait_for(process.wait(),5) == -signal.SIGTERM
            assert not Path(f'/proc/{process.pid}').exists()
    asyncio.run(run())


def test_streamed_report_preserves_format_and_previous_file_on_error(tmp_path):
    path=Path(__file__).resolve().parents[1]/'scripts/run-isae-preloaded.py'
    spec=importlib.util.spec_from_file_location('preloaded_for_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    output=tmp_path/'report.json';value={'nested':[1,2.5,None,{'value':'δ'}]}
    module.write_streamed_json(output,value)
    expected=json.dumps(value,indent=2,allow_nan=False)+'\n'
    assert output.read_text() == expected
    with pytest.raises(ValueError):module.write_streamed_json(output,{'value':float('nan')})
    assert output.read_text() == expected


def test_source_pin_tracks_logical_path_and_bytes_across_alias_changes(tmp_path):
    path=Path(__file__).resolve().parents[1]/'scripts/run-isae-preloaded.py'
    spec=importlib.util.spec_from_file_location('preloaded_pin_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    first=tmp_path/'first';second=tmp_path/'second';alias=tmp_path/'plan.json'
    first.write_text('identical plan');second.write_text('identical plan')
    alias.symlink_to(first)
    before=module.pin(alias)
    alias.unlink();alias.symlink_to(second)
    assert module.pin(alias) == before
    second.write_text('changed plan')
    assert module.pin(alias)['sha256'] != before['sha256']
