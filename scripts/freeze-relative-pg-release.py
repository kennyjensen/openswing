"""Freeze an explicitly selected, final pre-build release audit specification.

Selection JSON names only root/work relative paths and optional JSON assertions.
This does not infer or approve release scope, build anything, or read old raw
archives. Every added archive must also be present in root_files.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json


def pin(path):
    value = hashlib.sha256()
    count = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            count += len(block)
            value.update(block)
    return dict(bytes=count, sha256=value.hexdigest())


def path_in(folder, name):
    part = PurePosixPath(name)
    if not part.parts or part.is_absolute() or '..' in part.parts or '\\' in name or part.as_posix() != name:
        raise ValueError('Invalid relative path: ' + name)
    path = folder / name
    if path.is_symlink() or not path.resolve().is_relative_to(folder):
        raise ValueError('External or symlink path: ' + name)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    root, work = a.root.resolve(), a.work.resolve()
    output = a.output.resolve()
    if output.exists() or output.is_relative_to(root):
        raise ValueError('Use a new external spec path.')
    selection = json.loads(a.selection.read_text())
    if selection['status'] != 'FINAL_SELECTION_APPROVED_FOR_BUILD':
        raise ValueError('Selection must be explicitly finalized before freezing.')
    for group in ('root_files', 'work_files', 'added_archives'):
        if len(selection[group]) != len(set(selection[group])):
            raise ValueError('Duplicate selection in ' + group)
    if not set(selection['added_archives']) <= set(selection['root_files']):
        raise ValueError('Added raw archives must be explicitly pinned root_files.')
    expected_claims = dict(recorded_new_full_app_equilibrium=True, original_full_app_harness_pass=False,
                           followup_residual_replay=True, numerical_runs_by_release_auditor=False,
                           full_repository_suite=False, experimental_validation=False)
    if selection['claims'] != expected_claims:
        raise ValueError('Qualified full-app claims must retain the original harness failure and scoped replays.')
    spec = dict(format='openswing-relative-pg-release-spec', version=1, status='FINAL_FROZEN_BEFORE_BUILD',
                composition_sha256='7c975b8be70942dc49a301c6bd4c61dc60c84decd3c3ba1333661ef10e411b65',
                claims=selection['claims'],
                selection_pin=pin(a.selection), freezer_pin=pin(Path(__file__)),
                root_files={n: pin(path_in(root, n)) for n in selection['root_files']},
                work_files={n: pin(path_in(work, n)) for n in selection['work_files']},
                json_assertions=selection['json_assertions'])
    spec['added_archives'] = {n: spec['root_files'][n] for n in selection['added_archives']}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(spec, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(output=str(output), pin=pin(output))))


if __name__ == '__main__':
    main()
