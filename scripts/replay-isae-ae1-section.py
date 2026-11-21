"""Verify extracted evidence and run exactly one isolated, saved-only audit."""
from pathlib import Path
import argparse
import hashlib
import json
import runpy
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('replay-audit.json'))
    parser.add_argument('--receipt', type=Path, default=Path('replay-receipt.json'))
    args = parser.parse_args()
    output, receipt = [(ROOT/p).resolve() for p in (args.output, args.receipt)]
    assert output.is_relative_to(ROOT) and receipt.is_relative_to(ROOT)
    assert not output.exists() and not receipt.exists(), 'Replay output exists; inspect it before any new run.'
    manifest = json.loads((ROOT/'CONTENTS.json').read_bytes())
    for name, pin in manifest.items():
        path = (ROOT/name).resolve()
        assert path.is_relative_to(ROOT), 'Unsafe archive path: '+name
        raw = path.read_bytes()
        assert len(raw) == pin['bytes'] and hashlib.sha256(raw).hexdigest() == pin['sha256'], name
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
    assert actual == set(manifest) | {'CONTENTS.json'}, 'Extracted member set differs from CONTENTS.json.'
    historical = [Path(p).resolve() for p in json.loads((ROOT/'ARCHIVE-PATHS.json').read_bytes())['historical_roots'].values()]
    assert not any(ROOT.is_relative_to(p) for p in historical), 'Extract outside historical source directories.'
    blocked_reads, blocked_imports = [], []
    opened = set()

    def guard(event, values):
        if event == 'open' and isinstance(values[0], (str, bytes)):
            name = values[0].decode() if isinstance(values[0], bytes) else values[0]
            path = Path(name).resolve()
            if any(path.is_relative_to(old) for old in historical):
                blocked_reads.append(str(path))
                raise RuntimeError('Historical source read prohibited: '+str(path))
            if path.is_relative_to(ROOT):
                opened.add(path.relative_to(ROOT).as_posix())
        if event == 'import' and values[0].split('.')[0] in ('numpy', 'openswing'):
            blocked_imports.append(values[0])
            raise RuntimeError('Production/numerical package import prohibited: '+values[0])
        if event in ('subprocess.Popen', 'os.system'):
            raise RuntimeError('Child process prohibited during saved-only replay.')

    sys.addaudithook(guard)
    command = [str(ROOT/'scripts/check-isae-ae1-section.py'),
        '--run', str(ROOT/'evidence/section/native'), '--baseline-run', str(ROOT/'evidence/baseline'),
        '--source-review', str(ROOT/'evidence/section/source-review.json'),
        '--report', str(ROOT/'docs/validation/isae-ae1-section.json'),
        '--report-csv', str(ROOT/'docs/validation/isae-ae1-section.csv'), '--output', str(output)]
    result = dict(status='running', hashed_members_verified=len(manifest), audit_invocations=1,
                  original_source_reads=0, production_imports=0, new_physics_evaluations=0,
                  command=command, extracted_root=str(ROOT))
    error = None
    try:
        sys.argv = command
        runpy.run_path(command[0], run_name='__main__')
        audit = json.loads(output.read_bytes())
        assert audit['passed'] and audit['complete'] and audit['numerical_gates_passed']
        assert not blocked_reads and not blocked_imports
        result.update(status='passed', checks=audit['checks'], failures=audit['failures'],
                      numerical_gates_passed=audit['numerical_gates_passed'],
                      output=dict(path=str(output.relative_to(ROOT)), bytes=output.stat().st_size,
                                  sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
    except BaseException as exc:
        error = exc
        result.update(status='failed', error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc())
    finally:
        result.update(blocked_source_reads=blocked_reads, blocked_imports=blocked_imports,
                      extracted_files_opened=len(opened))
        receipt.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2))
    if error is not None:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
