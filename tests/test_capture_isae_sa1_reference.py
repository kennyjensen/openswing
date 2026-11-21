"""Capture mechanics only: fake processes here are never ASWING validation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/capture-isae-sa1-reference.py'
SPEC = importlib.util.spec_from_file_location('capture_isae_sa1_reference', SCRIPT)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


@pytest.fixture
def sources(tmp_path):
    """Copy authentic bytes without importing any production implementation."""
    root = tmp_path / 'source'
    target = root / CAPTURE.SOURCE_DIRECTORY
    target.mkdir(parents=True)
    for name in CAPTURE.SOURCE_SPECS:
        original = ROOT / CAPTURE.SOURCE_DIRECTORY / name
        if not original.is_file():
            pytest.skip('Pinned upstream SA1 cache is required for this source-contract test.')
        (target / name).write_bytes(original.read_bytes())
    return root


def fake_executable(tmp_path, body):
    if os.name != 'posix':
        pytest.skip('Execution capture explicitly requires POSIX process groups.')
    path = tmp_path / 'fake ASWING; not validation'
    path.write_text(f'#!{sys.executable}\n' + body)
    path.chmod(0o700)
    return path


FAKE_SUCCESS = '''import pathlib,sys
p=pathlib.Path('.')
commands=sys.stdin.buffer.read()
assert sys.argv[1:]==['SA_1']
assert not any((p/name).exists() for name in ['SA_1.set','SA_1.pnt','SA_1.con','SA_1_CL.txt'])
(p/'observed-stdin.bin').write_bytes(commands)
sys.stdout.buffer.write(b'FAKE executable mechanics only\\n\\xff\\n')
sys.stderr.buffer.write(b'FAKE stderr\\n')
if commands.startswith(b'DIMS\\n'):
    (p/'SA_1_capture_startup.set').write_bytes(b'FAKE settings; no validated format\\n')
else:
    (p/'SA_1_CL.txt').write_bytes(b'FAKE native-named output; not a polar or ASWING evidence\\n')
'''


def test_prepare_is_source_only_and_preserves_exact_heredoc(sources, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Preparation attempted to launch a process')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    output = tmp_path / 'kit'
    manifest = CAPTURE.prepare(output, source_root=sources)
    driver = (sources / CAPTURE.SOURCE_DIRECTORY / 'SA_1.sh').read_bytes()
    assert (output / 'original-run/stdin.txt').read_bytes() == b''.join(driver.splitlines(keepends=True)[2:-1])
    assert manifest['original_alpha_tokens'] == [
        '0.029369', '1.9971', '4.1116', '6.1087', '8.1351', '10.103',
        '12.1', '14.097', '15.095', '16.006', '18.091']
    assert (output / 'original-run/stdin.txt').read_bytes().endswith(b'SA_1_CL.txt\no\n')
    assert not (output / 'original-run/SA_1_CL.txt').exists()
    assert not (output / 'capture.json').exists()
    assert manifest['executed_processes'] == 0 and not manifest['archived_reference_validation']
    assert manifest['stage_order'] == ['original-run']
    for name, (size, sha) in CAPTURE.SOURCE_SPECS.items():
        assert CAPTURE.pin(output / 'original' / name) == {'bytes': size, 'sha256': sha}


def test_cli_defaults_to_preparation_without_executable(sources, tmp_path, capsys):
    output = tmp_path / 'kit'
    assert CAPTURE.main(['--source-root', str(sources), '--output', str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'prepared' and result['executed_processes'] == 0


def test_explicit_prepare_and_executable_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit) as exc:
        CAPTURE.main(['--output', str(tmp_path / 'kit'), '--prepare-only', '--aswing', '/fake'])
    assert exc.value.code == 2
    assert not (tmp_path / 'kit').exists()


@pytest.mark.parametrize('name', list(CAPTURE.SOURCE_SPECS))
def test_source_tampering_is_rejected_before_creating_output(sources, tmp_path, name):
    source = sources / CAPTURE.SOURCE_DIRECTORY / name
    source.write_bytes(source.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='pin mismatch'):
        CAPTURE.prepare(tmp_path / 'refused', source_root=sources)
    assert not (tmp_path / 'refused').exists()


def test_existing_output_is_never_reused_or_cleaned(sources, tmp_path):
    output = tmp_path / 'existing'
    output.mkdir()
    sentinel = output / 'keep-me'
    sentinel.write_bytes(b'previous data')
    with pytest.raises(FileExistsError):
        CAPTURE.prepare(output, source_root=sources)
    assert sentinel.read_bytes() == b'previous data'


def test_prepared_kit_can_be_moved_and_used_without_repository_cache(sources, tmp_path):
    first = tmp_path / 'first'
    CAPTURE.prepare(first, source_root=sources)
    moved = tmp_path / 'moved'
    first.rename(moved)
    second = tmp_path / 'second'
    CAPTURE.prepare(second, source_root=tmp_path / 'nonexistent', input_kit=moved)
    assert (second / 'original-run/stdin.txt').read_bytes() == (moved / 'original-run/stdin.txt').read_bytes()


def test_prepared_kit_command_tampering_is_rejected(sources, tmp_path):
    first = tmp_path / 'first'
    CAPTURE.prepare(first, source_root=sources)
    (first / 'original-run/stdin.txt').write_bytes(b'QUIT\n')
    with pytest.raises(ValueError, match='heredoc'):
        CAPTURE.prepare(tmp_path / 'second', input_kit=first)


def test_fake_capture_preserves_logs_and_probes_in_separate_cold_directories(sources, tmp_path):
    executable = fake_executable(tmp_path, FAKE_SUCCESS)
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources, settings_probe=True)
    before = CAPTURE.pin(executable)
    record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
    assert record['status'] == 'captured' and record['executed_processes'] == 2
    assert not record['archived_reference_validation']
    assert [s['stage'] for s in record['stages']] == ['settings-probe', 'original-run']
    assert (output / 'settings-probe/observed-stdin.bin').read_bytes() == CAPTURE.PROBE_COMMANDS
    assert (output / 'original-run/observed-stdin.bin').read_bytes() == (output / 'original-run/stdin.txt').read_bytes()
    assert not (output / 'original-run/SA_1_capture_startup.set').exists()
    for stage in record['stages']:
        directory = output / stage['stage']
        assert stage['executable_before'] == stage['executable_after'] == before
        assert stage['process_reaped'] and stage['return_code'] == 0
        assert stage['prepared_inputs_unchanged'] and stage['requested_output_captured']
        assert (directory / 'stdout.log').read_bytes() == b'FAKE executable mechanics only\n\xff\n'
        assert (directory / 'stderr.log').read_bytes() == b'FAKE stderr\n'
        assert stage['started_at_utc'] <= stage['finished_at_utc']
    assert json.loads((output / 'capture.json').read_text()) == record


def test_fake_nonzero_exit_retains_partial_output(sources, tmp_path):
    executable = fake_executable(tmp_path, FAKE_SUCCESS + '\nraise SystemExit(7)\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources)
    record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
    assert record['status'] == 'incomplete'
    stage = record['stages'][0]
    assert stage['status'] == 'nonzero_exit' and stage['return_code'] == 7
    assert stage['process_reaped'] and stage['requested_output_captured']


def test_fake_zero_exit_without_polar_is_not_success(sources, tmp_path):
    executable = fake_executable(tmp_path, 'print("FAKE no output")\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources)
    record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
    assert record['status'] == 'incomplete' and record['stages'][0]['status'] == 'missing_output'


def test_fake_timeout_terminates_and_reaps_direct_process(sources, tmp_path, monkeypatch):
    executable = fake_executable(tmp_path,
        'import pathlib,signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
        'pathlib.Path("fake-ready.txt").write_text("TERM ignored")\n'
        'print("FAKE timeout",flush=True)\ntime.sleep(60)\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources)
    original_popen = subprocess.Popen

    def ready_launch(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        deadline = time.monotonic() + 5
        ready = Path(kwargs['cwd']) / 'fake-ready.txt'
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        if not ready.exists():
            child.kill()
            child.wait()
            raise AssertionError('Fake timeout child did not install its TERM handler.')
        return child

    # Test escalation after readiness, independently of interpreter startup time.
    monkeypatch.setattr(subprocess, 'Popen', ready_launch)
    record = CAPTURE.capture(output, manifest, executable, timeout=.3, kill_grace=.05)
    stage = record['stages'][0]
    assert record['status'] == 'incomplete' and stage['status'] == 'timeout'
    assert stage['timed_out'] and stage['process_reaped'] and stage['return_code'] < 0
    assert stage['cleanup_signals'] == ['SIGTERM', 'SIGKILL']
    with pytest.raises(ProcessLookupError):
        os.kill(stage['pid'], 0)


@pytest.mark.parametrize('settings_probe', [False, True])
@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGINT])
def test_wrapper_signal_reaps_child_and_writes_terminal_receipt(sources, tmp_path, settings_probe, signum):
    executable = fake_executable(tmp_path,
        'import os,pathlib,signal,time\n'
        'signal.signal(signal.SIGTERM,signal.SIG_IGN)\n'
        'pathlib.Path("fake-ready-pid.txt").write_text(str(os.getpid()))\n'
        'print("FAKE interruption mechanics only",flush=True)\ntime.sleep(60)\n')
    output = tmp_path / 'capture'
    first_stage = 'settings-probe' if settings_probe else 'original-run'
    ready = output / first_stage / 'fake-ready-pid.txt'
    command = [sys.executable, str(SCRIPT), '--source-root', str(sources),
        '--output', str(output), '--aswing', str(executable), '--timeout', '30',
        '--kill-grace', '.05']
    if settings_probe:
        command.append('--settings-probe')
    wrapper = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    child_pid = None
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and wrapper.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists(), 'Fake child did not become ready before the signal test.'
        child_pid = int(ready.read_text())
        # Signal only the wrapper: the fake child has its own session and ignores TERM.
        os.kill(wrapper.pid, signum)
        stdout, stderr = wrapper.communicate(timeout=5)
        assert wrapper.returncode == 128 + signum, stderr.decode()
        assert json.loads(stdout)['status'] == 'interrupted'
        receipt = json.loads((output / 'capture.json').read_text())
        assert receipt['status'] == 'interrupted' and receipt['executed_processes'] == 1
        assert receipt['interruption_signal_number'] == signum
        assert receipt['interruption_signal'] == signal.Signals(signum).name
        assert receipt['finished_at_utc'] >= receipt['started_at_utc']
        assert len(receipt['stages']) == 1
        stage = receipt['stages'][0]
        assert stage['stage'] == first_stage and stage['status'] == 'interrupted'
        assert stage['interruption_signal_number'] == signum and stage['process_reaped']
        assert stage['pid'] == child_pid and stage['return_code'] == -signal.SIGKILL
        assert stage['cleanup_signals'] == ['SIGTERM', 'SIGKILL']
        assert stage['prepared_inputs_unchanged'] and stage['executable_unchanged']
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        if settings_probe:
            assert not (output / 'original-run/stdout.log').exists()
    finally:
        # Keep this regression itself bounded even when run against the old defect.
        if wrapper.poll() is None:
            wrapper.kill()
        wrapper.communicate(timeout=5)
        if child_pid is None and ready.exists():
            child_pid = int(ready.read_text())
        if child_pid is not None:
            try:
                os.killpg(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGINT])
def test_signal_after_child_creation_before_popen_returns_is_not_lost(sources, tmp_path, monkeypatch, signum):
    executable = fake_executable(tmp_path, 'import time\ntime.sleep(60)\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources)
    original_popen = subprocess.Popen
    original_handler = signal.getsignal(signum)
    previous_calls = []

    def previous_handler(received, _frame):
        previous_calls.append(received)

    def interrupted_launch(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        # Exactly the vulnerable interval: the caller has not received its handle.
        os.kill(os.getpid(), signum)
        return child

    signal.signal(signum, previous_handler)
    monkeypatch.setattr(subprocess, 'Popen', interrupted_launch)
    try:
        record = CAPTURE.capture(output, manifest, executable, timeout=.3, kill_grace=.05)
        assert signal.getsignal(signum) is previous_handler
    finally:
        signal.signal(signum, original_handler)
    assert previous_calls == []
    assert record['status'] == 'interrupted' and record['interruption_signal_number'] == signum
    stage = record['stages'][0]
    assert stage['process_started'] and stage['process_reaped'] and not stage['timed_out']
    with pytest.raises(ProcessLookupError):
        os.kill(stage['pid'], 0)


@pytest.mark.parametrize('spawn_error', [False, True])
def test_previous_signal_handlers_are_restored_after_capture(sources, tmp_path, monkeypatch, spawn_error):
    executable = fake_executable(tmp_path, FAKE_SUCCESS)
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources)
    prior = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}

    def previous_handler(_signum, _frame):
        raise AssertionError('No interruption requested in this test.')

    def rejected_launch(*_args, **_kwargs):
        raise OSError('FAKE spawn rejection')

    if spawn_error:
        monkeypatch.setattr(subprocess, 'Popen', rejected_launch)
    try:
        for signum in prior:
            signal.signal(signum, previous_handler)
        record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
        assert all(signal.getsignal(s) is previous_handler for s in prior)
    finally:
        for signum, handler in prior.items():
            signal.signal(signum, handler)
    assert record['status'] == ('incomplete' if spawn_error else 'captured')
    assert not record['interrupted'] and record['interruption_signal'] is None


def test_nonzero_probe_does_not_contaminate_or_skip_original_run(sources, tmp_path):
    executable = fake_executable(tmp_path, FAKE_SUCCESS + '\nif commands.startswith(b"DIMS\\n"): raise SystemExit(8)\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources, settings_probe=True)
    record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
    assert [s['status'] for s in record['stages']] == ['nonzero_exit', 'captured']


def test_fake_input_mutation_is_reported(sources, tmp_path):
    executable = fake_executable(tmp_path, FAKE_SUCCESS + '\n(p/"SA_1.asw").write_bytes(b"changed")\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources)
    record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
    assert record['stages'][0]['status'] == 'input_or_executable_changed'
    assert not record['stages'][0]['prepared_inputs_unchanged']


def test_fake_executable_mutation_stops_before_second_launch(sources, tmp_path):
    executable = fake_executable(tmp_path, FAKE_SUCCESS + '\npathlib.Path(sys.argv[0]).write_bytes(b"changed")\n')
    output = tmp_path / 'capture'
    manifest = CAPTURE.prepare(output, source_root=sources, settings_probe=True)
    record = CAPTURE.capture(output, manifest, executable, timeout=5, kill_grace=.05)
    assert record['status'] == 'error' and record['executed_processes'] == 1
    assert not record['stages'][0]['executable_unchanged']
    assert not (output / 'original-run/stdout.log').exists()


def test_source_only_import_has_no_production_modules():
    code = ('import importlib.util,sys; '
        f's=importlib.util.spec_from_file_location("capture_sa1",{str(SCRIPT)!r}); '
        'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
        'assert not any(n=="openswing" or n.startswith("openswing.") for n in sys.modules)')
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr.decode()
