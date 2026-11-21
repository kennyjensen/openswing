"""Freeze the complete refined UA-1 case for small serial built-worker requests."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

from isae_ua_incidence_periodic import CYCLES, GATES, PERIOD, full_request

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua1-incidence-periodic-browser-20261102'
OLD = ROOT / 'artifacts/isae/ua1-incidence-periodic-refined-20261101'


def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main():
    assert not BASE.exists(), 'Preserve existing plans and interrupted evidence'
    audit = json.loads((OLD / 'audit.json').read_text())
    batch = json.loads((OLD / 'batch-plan.json').read_text())
    reference = json.loads((OLD / 'reference.json').read_text())
    assert audit['passed'] and all(audit['checks'].values()) and reference['passed']
    assert json.loads((OLD / 'audit-execution.json').read_text())['exit_code'] == 0
    assert json.loads((OLD / 'reference-execution.json').read_text())['exit_code'] == 0
    historical = {name: value for name, value in batch['source_sha256'].items() if name.startswith('openswing/')}
    production = {name: digest(ROOT / name) for name in historical}
    assert len(production) == len(list((ROOT / 'openswing').glob('*.py'))) == 136
    changed = {name: dict(historical=value, current=production[name])
               for name, value in historical.items() if value != production[name]}
    assert changed == {'openswing/forcing.py': dict(
        historical='ce2732c205763ae75144d40dddc9f5248d83bd90fc97c03e6123160487bfde79',
        current='356bf9c04710ce59ee056cd8e15aed7508cf7d93ffabe9f3f886c49bd3c4f5fe')}
    fine = audit['results']['320']
    rows = fine['rows']
    assert len(rows) == CYCLES * 320 + 1 == 2561
    assert max(reference['agreement_fractions'].values()) < GATES['reference_agreement_fraction']
    full = full_request(320)
    inputs = {}
    # Bind the audit to the exact raw inputs and producing plans/receipts.
    for name, value in {**batch['source_sha256'], **audit['input_sha256'], **audit['plan']['source_sha256']}.items():
        path = OLD / 'frozen-code' / name if name in changed else ROOT / name
        assert digest(path) == value, name
        inputs[str(path.relative_to(ROOT))] = value
    for name in ['audit.json', 'audit-execution.json', 'reference.json', 'reference-execution.json', 'batch-plan.json']:
        path = OLD / name
        inputs[str(path.relative_to(ROOT))] = digest(path)
    for part in range(32):
        prior = json.loads((OLD / f'n320-part{part:02d}/plan.json').read_text())
        assert prior['full_request'] == full and prior['gates'] == GATES
    times = [row['time'] for row in rows]
    jobs = [dict(part=i, start_index=start, end_index=start + 40)
            for i, start in enumerate(range(0, len(times) - 1, 40))]
    workers = list((ROOT / 'dist/assets').glob('worker-*.js'))
    assert len(workers) == 1
    modules = json.loads((ROOT / 'dist/kernel/manifest.json').read_text())
    assert sorted(modules) == sorted(Path(name).name for name in production)
    for name in modules:
        assert digest(ROOT / 'dist/kernel' / name) == production['openswing/' + name]
    paths = [Path(__file__).resolve(), ROOT / 'scripts/run-isae-ua1-periodic-browser.mjs',
             ROOT / 'scripts/audit-isae-ua1-periodic-browser.py',
             ROOT / 'scripts/run-isae-ua1-periodic-browser-audits.py',
             ROOT / 'scripts/isae_ua_incidence_periodic.py', ROOT / 'scripts/isae_ua_periodic.py',
             ROOT / 'scripts/isae_ua2_browser_cutoff.py', ROOT / 'tests/test_isae_ua2_browser_cutoff.py',
             ROOT / 'web/saved-state-data.js', workers[0], ROOT / 'dist/kernel/manifest.json',
             *[ROOT / 'dist/kernel' / name for name in modules],
             *sorted(p for p in (ROOT / 'dist/runtime').rglob('*') if p.is_file())]
    sources = {**production, **{str(p.relative_to(ROOT)): digest(p) for p in paths}}
    assert all(digest(ROOT / name) == value for name, value in sources.items())
    BASE.mkdir()
    (BASE / 'targets').mkdir()
    for name in sources:
        if name.startswith('dist/runtime/'):
            continue
        target = BASE / 'frozen-code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    targets = []
    for job in jobs:
        path = BASE / 'targets' / f'part{job["part"]:03d}.json'
        write(path, dict(job=job, rows=rows[job['start_index']:job['end_index'] + 1]))
        targets.append(dict(path=str(path.relative_to(BASE)), sha256=digest(path)))
    write(BASE / 'periodic-reference.json', reference['reference']['periodic'])
    gates = {key: value for key, value in GATES.items() if key != 'fine_to_coarse_ratio'}
    gates['CPython_scaled_difference'] = 2e-8
    plan = dict(full_request=full, times=times, jobs=jobs, targets=targets, gates=gates,
                source_sha256=sources, input_sha256=inputs,
                periodic_reference_sha256=digest(BASE / 'periodic-reference.json'),
                baseline_fine_summary={key: value for key, value in fine.items() if key != 'rows'},
                worker_url='/assets/' + workers[0].name, panels=4, cycles=CYCLES, period=PERIOD,
                nominal_steps_per_cycle=320, max_steps_per_job=40,
                worker_request_timeout_seconds=45, audit_jobs_per_chunk=4, serial=True,
                initial_state='Production steady equilibrium; no independent reference state is supplied to the solver.',
                scope='Built browser worker: eight continuous cycles at alpha9, k.94, peak-to-peak A/c.5, AR200000 and four circulation unknowns. Short checkpointed requests preserve the complete forcing table and BDF history.',
                clock_comparison_absolute_tolerance=1e-12,
                retained_CPython_kernel_changes=changed,
                retained_CPython_note='The baseline predates the separately validated terminal-knot rounding fix in forcing.py; its frozen source is pinned. All other 135 scientific modules match. This is a comparison against the retained earlier CPython calculation, not a claim that both runs used identical source. Original independent-reference gates remain unchanged.',
                production_changed=False, native_ASWING_comparison=False,
                full_history_UI_validation=False, new_temporal_refinement_claim=False)
    assert all(digest(ROOT / name) == value for name, value in {**sources, **inputs}.items())
    write(BASE / 'plan.json', plan)
    shutil.copyfile(ROOT / 'docs/validation/ISAE_STATUS.md', BASE / 'status-before.md')
    print(json.dumps(dict(prepared=True, browser_jobs=len(jobs), physical_steps=2560,
                          numerical_jobs_started=0, new_pass_count=0)))


if __name__ == '__main__':
    main()
