#!/usr/bin/env python3
"""Prepare or capture unchanged SA1 inputs; this is not a reference validator."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
SOURCE_DIRECTORY = (f'.reference/isae-validation/{REVISION}/1 - Aerodynamics/'
    'SA - Steady Aerodynamics Cases/SA - 1 - Straight Wing - Lift And Drag Up to Stall/'
    'Aswing_Simulation_V5_96_Only')
SOURCE_SPECS = {
    'SA_1.asw': (4427, '4c7a55235973171749afac41741e11792fc5b4fbf9e072aaee3bc57c6fc658bd'),
    'SA_1.sh': (309, '9d7b0dd1817850e22af370c59fc20f4d0f7da7313160fca3cc1e5684e35d6f82'),
    'SA_1_CL.txt': (1636, '462010781b4f65aa8f45d70d6923eb90d638e2afdac67b0c6ec84726df4a4f7d'),
}
PROBE_COMMANDS = b'DIMS\nSSAV\nSA_1_capture_startup.set\nQUIT\n'
QUALIFICATIONS = [
    'A new supplied executable run cannot recover the historical SA1 executable or startup settings.',
    'The original model, reference table and heredoc command bytes are preserved; the shell driver is never executed.',
    'The original commands are not repaired or extended, including their blank lines, trailing spaces and EOF termination.',
    'Each launch is a new process in a fresh directory without SA_1.set, SA_1.pnt or SA_1.con.',
    'The caller environment is inherited. No claim is made that it matches the historical machine or build.',
    'Any settings probe is a separate launch and directory; its settings are never copied into the original run.',
    'A captured polar, successful process exit or fake-executable test is not ASWING validation or archived agreement.',
]


def now():
    return datetime.now(timezone.utc).isoformat()


def pin(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Expected a regular, non-symlink file: {path}')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def original_commands(driver):
    """Only the authenticated driver is accepted; no shell expansion occurs."""
    size, sha = SOURCE_SPECS['SA_1.sh']
    if len(driver) != size or hashlib.sha256(driver).hexdigest() != sha:
        raise ValueError('Original SA_1.sh pin mismatch.')
    lines = driver.splitlines(keepends=True)
    if lines[1] != b'~/Documents/Softwares/AswingMAC_12_02_21/bin/aswing SA_1 <<EOF\n':
        raise ValueError('Unrecognized original executable invocation.')
    if lines[-1].rstrip(b'\r\n') != b'EOF':
        raise ValueError('Missing original heredoc terminator.')
    return b''.join(lines[2:-1])


def read_sources(source_root=ROOT, input_kit=None):
    source = Path(input_kit) / 'original' if input_kit is not None else Path(source_root) / SOURCE_DIRECTORY
    data = {}
    for name, (size, sha) in SOURCE_SPECS.items():
        path = source / name
        if pin(path) != {'bytes': size, 'sha256': sha}:
            raise ValueError(f'Original source pin mismatch: {name}')
        data[name] = path.read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != sha:
            raise ValueError(f'Original source changed while reading: {name}')
    commands = original_commands(data['SA_1.sh'])
    if input_kit is not None:
        saved = Path(input_kit) / 'original-run' / 'stdin.txt'
        pin(saved)
        if saved.read_bytes() != commands:
            raise ValueError('Prepared-kit command bytes differ from the original heredoc.')
    return data, commands


def prepare(output, *, source_root=ROOT, input_kit=None, settings_probe=False):
    data, commands = read_sources(source_root, input_kit)
    output = Path(output).absolute()
    # Never merge with, clean, or reuse an earlier run directory.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'original').mkdir()
    for name, content in data.items():
        (output / 'original' / name).write_bytes(content)
    stages = ['settings-probe', 'original-run'] if settings_probe else ['original-run']
    for name in stages:
        directory = output / name
        directory.mkdir()
        (directory / 'SA_1.asw').write_bytes(data['SA_1.asw'])
        (directory / 'stdin.txt').write_bytes(PROBE_COMMANDS if name == 'settings-probe' else commands)
    # A prepared kit carries its runner for transfer to a machine with ASWING.
    (output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output / 'README.txt').write_text(
        'SA1 capture kit. Preparation does not run ASWING.\n'
        'On a machine with a supplied executable, run the included script with:\n'
        '  --input-kit PATH_TO_THIS_KIT --output NEW_DIRECTORY --aswing /absolute/path/to/aswing\n'
        'Add --settings-probe only to request the separate DIMS/SSAV/QUIT launch.\n'
        'The reference table is in original/; a newly generated table belongs in original-run/.\n'
        'No commands are appended to the original input, including QUIT.\n'
        'Logs/output are preserved verbatim, including any printed dates or errors.\n'
        'This captures a new run; it does not reconstruct historical startup settings or certify agreement.\n')
    files = {str(p.relative_to(output)): pin(p) for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = dict(schema_version=1, family='SA-1', status='prepared', prepared_at_utc=now(),
        upstream_repository='https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation',
        upstream_revision=REVISION, source_directory=SOURCE_DIRECTORY,
        historical_label='ASWING 5.96; executable bytes and startup settings unrecovered',
        invocation_argument='SA_1', original_driver_invocation=data['SA_1.sh'].splitlines()[1].decode(),
        original_alpha_tokens=[line.split()[1].decode() for line in commands.splitlines() if line.startswith(b'!A ')],
        settings_probe_requested=bool(settings_probe), stage_order=stages,
        prepared_files=files, executed_processes=0, archived_reference_validation=False,
        probe_documentation=dict(guide='https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt',
            commands=['DIMS', 'SSAV', 'SA_1_capture_startup.set', 'QUIT'],
            scope='Startup settings and dimensions of the supplied executable after loading the literal model; no operating solve requested.'),
        qualifications=QUALIFICATIONS)
    write_json(output / 'manifest.json', manifest)
    return manifest


def _group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


@contextmanager
def _interruption_handlers():
    """Defer cancellation until the owned Popen handle can be cleaned up.

    Raising inside Popen can lose a child created before Popen returns. These
    handlers only set a flag, including during creation and group cleanup.
    """
    interruption = {'signal': None}
    previous = {}

    def request_stop(signum, _frame):
        if interruption['signal'] is None:
            interruption['signal'] = signum

    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)
        yield interruption
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _record_interruption(record, interruption):
    signum = interruption['signal']
    record.update(interrupted=signum is not None, interruption_signal_number=signum,
        interruption_signal=signal.Signals(signum).name if signum is not None else None)


def _stop_group(process, grace):
    """Stop only the new session/process group owned by this capture."""
    signals = []
    if _group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGTERM)
            signals.append('SIGTERM')
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while _group_exists(process.pid) and time.monotonic() < deadline:
            process.poll()  # reap the direct child as soon as it exits
            time.sleep(min(.02, max(0., deadline - time.monotonic())))
        if _group_exists(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
                signals.append('SIGKILL')
            except ProcessLookupError:
                pass
    process.wait()
    return signals


def inventory(directory):
    result = []
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            result.append({'path': str(path.relative_to(directory)), 'kind': 'symlink', 'target_not_followed': True})
        elif path.is_file():
            result.append({'path': str(path.relative_to(directory)), 'kind': 'file', **pin(path)})
    return result


def run_stage(output, stage, executable, *, timeout, kill_grace, expected_files, interruption):
    directory = output / stage
    before = {p.name for p in directory.iterdir()}
    if before != {'SA_1.asw', 'stdin.txt'}:
        raise ValueError(f'{stage}: cold directory contains unexpected files.')
    for name in before:
        if pin(directory / name) != expected_files[f'{stage}/{name}']:
            raise ValueError(f'{stage}: prepared input changed: {name}')
    record = dict(stage=stage, argv=[str(executable), 'SA_1'], cwd=str(directory),
        started_at_utc=now(), timeout_seconds=timeout, process_started=False,
        process_reaped=False, return_code=None, timed_out=False, interrupted=False,
        cleanup_signals=[], executable_before=pin(executable))
    start = time.monotonic()
    with (directory / 'stdin.txt').open('rb') as stdin, (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
        process = None
        try:
            if interruption['signal'] is None:
                process = subprocess.Popen(record['argv'], stdin=stdin, stdout=stdout, stderr=stderr,
                    cwd=directory, start_new_session=True, shell=False)
                record.update(process_started=True, pid=process.pid)
                deadline = time.monotonic() + timeout
                while process.poll() is None and interruption['signal'] is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        record['timed_out'] = True
                        break
                    try:
                        process.wait(timeout=min(.05, remaining))
                    except subprocess.TimeoutExpired:
                        pass
        except OSError as exc:
            record['spawn_error'] = f'{type(exc).__name__}: {exc}'
        finally:
            if process is not None:
                # Also clean any child processes remaining after a normal parent exit.
                record['cleanup_signals'] = _stop_group(process, kill_grace)
                record.update(return_code=process.returncode, process_reaped=True)
    record.update(finished_at_utc=now(), seconds=time.monotonic() - start)
    try:
        record['executable_after'] = pin(executable)
    except (OSError, ValueError) as exc:
        record['executable_after'] = None
        record['executable_after_error'] = str(exc)
    record['executable_unchanged'] = record['executable_before'] == record['executable_after']
    record['prepared_inputs_unchanged'] = all(
        (directory / name).is_file() and not (directory / name).is_symlink()
        and pin(directory / name) == expected_files[f'{stage}/{name}'] for name in before)
    record['files'] = inventory(directory)
    target = 'SA_1_CL.txt' if stage == 'original-run' else 'SA_1_capture_startup.set'
    record['requested_output'] = next((f for f in record['files'] if f['path'] == target), None)
    record['requested_output_captured'] = bool(record['requested_output'] and record['requested_output']['kind'] == 'file')
    _record_interruption(record, interruption)
    record['status'] = ('interrupted' if record['interrupted'] else 'timeout' if record['timed_out'] else
        'spawn_error' if not record['process_started'] else
        'input_or_executable_changed' if not record['executable_unchanged'] or not record['prepared_inputs_unchanged'] else
        'nonzero_exit' if record['return_code'] != 0 else
        'missing_output' if not record['requested_output_captured'] else 'captured')
    return record


def capture(output, manifest, executable, *, timeout=180., kill_grace=2.):
    if os.name != 'posix':
        raise ValueError('Execution requires POSIX process-group cleanup; prepare-only is portable.')
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(kill_grace) or not 0 <= kill_grace <= 10:
        raise ValueError('timeout must be finite and positive; kill-grace must be between0 and10 seconds.')
    executable = Path(executable).expanduser().resolve(strict=True)
    pin(executable)
    if not os.access(executable, os.X_OK):
        raise ValueError('Supplied ASWING path is not executable.')
    output = Path(output).absolute()
    record = dict(schema_version=1, family='SA-1', status='running', started_at_utc=now(),
        manifest=pin(output / 'manifest.json'), executable_path=str(executable),
        executable_initial=pin(executable), stages=[], archived_reference_validation=False,
        qualifications=QUALIFICATIONS)
    # Install before any launch and retain through terminal receipt publication.
    with _interruption_handlers() as interruption:
        try:
            write_json(output / 'capture.json', record)
            for stage in manifest['stage_order']:
                if interruption['signal'] is not None:
                    break
                # Do not continue with an executable modified by an earlier probe.
                if pin(executable) != record['executable_initial']:
                    raise ValueError('Executable changed before stage launch.')
                result = run_stage(output, stage, executable, timeout=timeout,
                    kill_grace=kill_grace, expected_files=manifest['prepared_files'],
                    interruption=interruption)
                record['stages'].append(result)
                write_json(output / 'capture.json', record)
            record['status'] = 'captured' if (len(record['stages']) == len(manifest['stage_order'])
                and all(r['status'] == 'captured' for r in record['stages'])) else 'incomplete'
        except (OSError, ValueError) as exc:
            record.update(status='error', error=f'{type(exc).__name__}: {exc}')
        finally:
            _record_interruption(record, interruption)
            if record['interrupted']:
                record['status'] = 'interrupted'
            record['finished_at_utc'] = now()
            record['executed_processes'] = sum(r['process_started'] for r in record['stages'])
            write_json(output / 'capture.json', record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New directory; an existing path is refused.')
    parser.add_argument('--source-root', type=Path, default=ROOT, help='Repository with the pinned original cache.')
    parser.add_argument('--input-kit', type=Path, help='Use verified originals from a previously prepared portable kit.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--prepare-only', action='store_true', help='Explicit preparation mode (also the default).')
    mode.add_argument('--aswing', type=Path, help='Explicit executable path; enables a new capture run.')
    parser.add_argument('--settings-probe', action='store_true', help='Prepare/run a separate startup DIMS/SSAV/QUIT probe.')
    parser.add_argument('--timeout', type=float, default=180., help='Wall time limit per launched process.')
    parser.add_argument('--kill-grace', type=float, default=2., help='Seconds before SIGKILL, between0 and10.')
    args = parser.parse_args(argv)
    try:
        manifest = prepare(args.output, source_root=args.source_root, input_kit=args.input_kit,
            settings_probe=args.settings_probe)
        result = capture(args.output, manifest, args.aswing, timeout=args.timeout, kill_grace=args.kill_grace) if args.aswing else manifest
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Capture refused: {exc}\n')
    print(json.dumps({'output': str(args.output.absolute()), 'status': result['status'],
        'executed_processes': result['executed_processes'], 'archived_reference_validation': False}))
    if result['status'] == 'interrupted':
        return 128 + result['interruption_signal_number']
    return 0 if result['status'] in ('prepared', 'captured') else 1


if __name__ == '__main__':
    raise SystemExit(main())
