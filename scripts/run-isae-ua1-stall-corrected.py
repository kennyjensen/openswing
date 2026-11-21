"""Current-source UA-1 stall revalidation: frozen inputs, small serial jobs.

Reuses the established numerical/audit engine and independent reference data.
Only orchestration and the extra physical-state checks differ from that study.
"""
import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua1-stall-corrected-20261103'
OLD = ROOT/'artifacts/isae/ua1-stall-periodic-20261102'
SCRIPT = Path(__file__).resolve()
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('stall_engine', ROOT/'scripts/run-isae-ua1-stall-periodic.py')
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
from isae_ua1_stall_expanded import physical_row, LOCAL_FIELDS, RIGID_LIMIT
from isae_ua1_stall_browser import pins, flatten

read, write, digest, verify = engine.read, engine.write, engine.digest, engine.verify
original_audit = engine.audit_raw


def expanded_audit(section, raw, steps, part, size, targets):
    rows = original_audit(section, raw, steps, part, size, targets)
    expanded = [physical_row(s, asdict(section)) for s in raw['snapshots']]
    for row, extra in zip(rows, expanded[1:] if part else expanded, strict=True):
        row.update(extra)
    return rows


engine.audit_raw = expanded_audit
engine.SCRIPT = SCRIPT


def prepare():
    assert not BASE.exists(), 'Keep existing study evidence intact'
    previous = read(OLD/'plan.json')
    section = engine.Section()
    assert previous['section'] == asdict(section)
    assert previous['gates'] == engine.GATES
    assert previous['reference_steps'] == 640 and previous['reference_cycles'] == 8
    reference_sources = ('scripts/isae_ua_stall_reference.py',
                         '.reference/asw_theory.txt', '.reference/asw_uns_theory.txt')
    verify({name: previous['source_sha256'][name] for name in reference_sources})
    for name in ('reference-DOP853', 'reference-Radau', 'reference-check'):
        engine.completed(OLD, name)
    assert read(OLD/'reference-check.json')['passed']
    verify(read(OLD/'reference-check.json')['input_sha256'])
    extras = [SCRIPT, ROOT/'scripts/isae_ua1_stall_expanded.py',
        ROOT/'scripts/isae_ua1_stall_browser.py',
        ROOT/'scripts/isae_ua1_stall_corrected_browser.py',
        ROOT/'scripts/run-isae-ua1-stall-corrected-browser.mjs',
        ROOT/'scripts/isae_time_browser_compare.mjs',
        ROOT/'web/saved-state-data.js', ROOT/'tests/test_isae_ua1_stall_expanded.py']
    paths = [ROOT/name for name in previous['source_sha256']] + extras
    source = pins(paths)
    modules = {name: value for name, value in source.items() if name.startswith('openswing/')}
    assert len(modules) == 136
    for name, value in modules.items():
        assert digest(ROOT/'dist/kernel'/Path(name).name) == value
    BASE.mkdir()
    plan = dict(**{**previous, 'segment_steps':20, 'source_sha256':source},
        previous_goal_turn='no progress: status only; this study advances validation',
        prior_study=str(OLD.relative_to(ROOT)), reference_reused=True,
        independent_rigid_local_motion_limit=RIGID_LIMIT,
        runtime_scaled_difference=2e-8,
        expanded_fields='All aerodynamic/frame, nodal kinematics, positions/rotations, internal resultants and reactions.',
        force_scale='qS', moment_scale='qS*span', other_scale='max(1,abs(expected))',
        precision_fixes=['displacement BDF', 'bordered-solve iterative refinement', 'constant-preserving arc quadrature'],
        full_current_source_validation=False,
        input_sha256=pins([OLD/'plan.json', *[OLD/(name+suffix) for name in
            ('reference-DOP853', 'reference-Radau', 'reference-check') for suffix in ('.json', '-execution.json')]]))
    write(BASE/'plan.json', plan)
    shutil.copyfile(ROOT/'docs/validation/ISAE_STATUS.md', BASE/'status-before.md')
    for name in source:
        target = BASE/'frozen-code'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    for name in ('reference-DOP853', 'reference-Radau', 'reference-check'):
        target = BASE/(name+'.json')
        shutil.copyfile(OLD/(name+'.json'), target)
        write(BASE/(name+'-execution.json'), dict(exit_code=0,
            reused_verified_result=True, original_receipt=str((OLD/(name+'-execution.json')).relative_to(ROOT)),
            output_sha256=pins([target])))
    for grid in plan['grids']:
        write(BASE/f'request-n{grid}.json', engine.request(section, grid, 4))
    print(json.dumps(dict(prepared=True, jobs=192, grids=plan['grids'], segment_steps=20,
                         reference_reused=True, numerical_jobs_started=0)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','run','segment','combine'])
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--steps', type=int)
    parser.add_argument('--part', type=int)
    parser.add_argument('--max-jobs', type=int)
    args = parser.parse_args()
    assert args.base.resolve() == BASE
    if args.action == 'prepare':
        prepare(); return
    plan = read(BASE/'plan.json')
    assert plan['gates'] == engine.GATES and plan['segment_steps'] == 20
    verify(plan['source_sha256']); verify(plan['input_sha256'])
    if args.action == 'run':
        engine.run(BASE, plan, 'production', args.max_jobs)
    elif args.action == 'segment':
        engine.segment(BASE, plan, args.steps, args.part)
    else:
        engine.combine(BASE, plan, args.steps)


if __name__ == '__main__':
    main()
