"""Freeze a bounded built-browser replay of the audited N20 inclined history.

This only prepares inputs. Run after other numerical jobs finish, then pilot
one browser segment before starting the remaining serial segments.
"""
from hashlib import sha256
import json
from pathlib import Path
import shutil

from isae_ua2_incidence_periodic import CYCLES, GATES, PERIOD, full_request, grid

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua2-incidence-periodic-browser-20261101'
OLD = ROOT / 'artifacts/isae/ua2-incidence-periodic-20261101-r1'
SUMMARY = ROOT / 'docs/validation/isae-ua2-incidence-periodic-20261101.json'


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    assert not BASE.exists(), 'Preserve any earlier prepared or interrupted study'
    summary = json.loads(SUMMARY.read_text())
    assert summary['passed'] and all(summary['checks'].values())
    assert summary['panels'] == 20 and summary['cycles'] == CYCLES == 8
    summary_pins = summary['source_sha256']
    production = {name: value for name, value in summary_pins.items() if name.startswith('openswing/')}
    assert len(production) == len(list((ROOT / 'openswing').glob('*.py'))) == 136
    assert all(digest(ROOT / name) == value for name, value in production.items())
    input_pins = {str(SUMMARY.relative_to(ROOT)): digest(SUMMARY)}
    for name in ('audit.json', 'audit-execution.json', 'reference.json', 'reference-plan.json'):
        path = OLD / name
        key = str(path.relative_to(ROOT))
        value = digest(path)
        assert summary_pins[key] == value, key
        input_pins[key] = value
    assert json.loads((OLD / 'audit-execution.json').read_text())['exit_code'] == 0
    times = grid(640)
    assert len(times) == 5281
    jobs = [dict(part=i, start_index=start, end_index=min(start + 16, len(times) - 1))
            for i, start in enumerate(range(0, len(times) - 1, 16))]
    assert len(jobs) == 330
    workers = sorted((ROOT / 'dist/assets').glob('worker-*.js'))
    assert len(workers) == 1
    module_names = json.loads((ROOT / 'dist/kernel/manifest.json').read_text())
    assert sorted(module_names) == sorted(Path(name).name for name in production)
    for name in module_names:
        assert digest(ROOT / 'dist/kernel' / name) == production['openswing/' + name]
    paths = [Path(__file__).resolve(), ROOT / 'scripts/run-isae-ua2-periodic-browser.mjs',
             ROOT / 'scripts/audit-isae-ua2-periodic-browser.py',
             ROOT / 'scripts/run-isae-ua2-periodic-browser-audits.py',
             ROOT / 'scripts/isae_ua2_incidence_periodic.py',
             ROOT / 'web/saved-state-data.js', workers[0],
             ROOT / 'dist/kernel/manifest.json',
             *[ROOT / 'dist/kernel' / name for name in module_names],
             *sorted(p for p in (ROOT / 'dist/runtime').rglob('*') if p.is_file())]
    helpers = {name: value for name, value in summary_pins.items()
               if name.startswith('scripts/') and name.endswith('.py')}
    assert all(digest(ROOT / name) == value for name, value in helpers.items())
    source_pins = {**production, **helpers,
                   **{str(path.relative_to(ROOT)): digest(path) for path in paths}}
    BASE.mkdir()
    for name in source_pins:
        if name.startswith('dist/runtime/'):
            continue
        target = BASE / 'frozen-code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (BASE / 'targets').mkdir()
    pending = []
    ordinal = part = 0
    targets = []
    for index in range(21):
        path = OLD / f'audit-n640-chunk{index:02d}.json'
        receipt_path = OLD / f'audit-n640-chunk{index:02d}-execution.json'
        for p in (path, receipt_path):
            key = str(p.relative_to(ROOT))
            value = digest(p)
            assert summary_pins[key] == value, key
            input_pins[key] = value
        receipt = json.loads(receipt_path.read_text())
        assert receipt['exit_code'] == 0 and receipt['report_sha256'] == digest(path)
        chunk = json.loads(path.read_text())
        assert chunk['passed'] and chunk['steps'] == 640 and chunk['chunk'] == index
        for row in chunk['rows']:
            assert row['time'] == times[ordinal]
            pending.append(row)
            ordinal += 1
            if len(pending) == 17:
                job = jobs[part]
                assert pending[0]['time'] == times[job['start_index']]
                assert pending[-1]['time'] == times[job['end_index']]
                target = BASE / 'targets' / f'part{part:03d}.json'
                write(target, dict(job=job, rows=pending))
                targets.append(dict(path=str(target.relative_to(BASE)), sha256=digest(target)))
                pending = [pending[-1]]
                part += 1
        del chunk
    assert ordinal == 5281 and part == 330 and len(pending) == 1
    # Reuse the already verified reference exactly. This is an input extraction,
    # not another integration or an initialization state for production.
    reference = json.loads((OLD / 'reference.json').read_text())
    assert reference['passed'] and max(reference['method_differences'].values()) < GATES['reference_agreement_fraction']
    periodic = reference['reference']['DOP853']['periodic']
    assert len(periodic['rows']) == 641 and periodic['closure_fraction'] < 1e-10
    write(BASE / 'periodic-reference.json', periodic)
    del reference
    gates = {key: value for key, value in GATES.items() if key != 'fine_to_coarse_ratio'}
    gates['CPython_scaled_difference'] = 2e-8
    plan = dict(full_request=full_request(640), times=times, jobs=jobs, targets=targets,
                gates=gates, source_sha256=source_pins, input_sha256=input_pins,
                periodic_reference_sha256=digest(BASE / 'periodic-reference.json'),
                baseline_fine_summary=summary['grids']['640'],
                worker_url='/assets/' + workers[0].name, panels=20, cycles=CYCLES,
                period=PERIOD, nominal_steps_per_cycle=640, max_steps_per_job=16,
                worker_request_timeout_seconds=45, audit_jobs_per_chunk=8, serial=True,
                scope='Built browser worker: eight continuous cycles from its own steady state, using checkpoints between bounded requests. This does not exercise full-history UI rendering or establish native ASWING parity.',
                production_changed=False, native_ASWING_comparison=False,
                full_history_UI_validation=False, new_temporal_refinement_claim=False)
    assert all(digest(ROOT / name) == value for name, value in {**source_pins, **input_pins}.items())
    write(BASE / 'plan.json', plan)
    print(json.dumps(dict(prepared=True, browser_jobs=len(jobs), physical_steps=len(times)-1,
                          numerical_jobs_started=0, new_pass_count=0)))


if __name__ == '__main__':
    main()
