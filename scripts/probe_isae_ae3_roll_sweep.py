"""Complete the independently sourced AE-3 roll-constraint diagnostic curve.

Original native targets, literal primary inputs and all comparison scopes stay
unchanged. This extends the previous two endpoint probes without fitted inputs.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae3_roll_control as run
from scripts.probe_isae_ae2_cold_trace import read, write, pin

OUT = ROOT / 'artifacts/isae/ae3-roll-sweep-20261111'
PRIOR = ROOT / 'artifacts/isae/ae3-roll-control-20261111'
BASE = ROOT / 'artifacts/isae/ae3-current-20261111'
run.OUT = run.run.OUT = run.run.supervisor.OUT = OUT
run.run.supervisor.__file__ = __file__


def prepare():
    assert not OUT.exists()
    parent = read(PRIOR / 'plan.json')
    base = read(BASE / 'plan.json')
    sources = {}
    for plan in (parent, base):
        for p in plan['pins']:
            assert sources.setdefault(p['path'], p) == p
    for p in sources.values():
        assert pin(p['path']) == p, p['path']
    paths = set(sources)
    paths.update(str(p) for p in (Path(__file__), PRIOR / 'plan.json', BASE / 'plan.json',
        ROOT / 'scripts/probe_isae_ae3_roll_control.py',
        ROOT / 'docs/validation/isae-ae3-control-response-20261111.md',
        ROOT / 'artifacts/isae/ae3-control-response-20261111/assessment.json'))
    template = parent['cases'][0]
    cases, reused = [], []
    for job in base['jobs']:
        if job['execution_route'] != 'worker':
            continue
        op, nominal = job['native_operating_point'], job['nominal']
        name = f'sibling-lift-roll-free-op{op}-m{nominal}'
        if nominal == 80 and op in (1, 6):
            folder = PRIOR / 'cases' / name
            terminal = read(folder / 'terminal.json')
            assert terminal['returncode'] == 0 and terminal['process_reaped']
            assert read(folder / 'report.json')['numerical_pass']
            reused.append(dict(name=name, operating_point=op, nominal=nominal,
                               folder=str(folder), speed=job['condition']['speed']))
            paths.update(str(folder / f) for f in ('report.json', 'result.json',
                         'terminal.json', 'sources-verified.json', 'request.json'))
            continue
        strict = BASE / 'jobs' / job['id'] / 'strict-result.json'
        baseline = read(strict)
        assert baseline['numerical_pass'] and baseline['status'] == 'computed'
        result = Path(baseline['artifact_directory']) / 'result.json'
        paths.update((str(strict), str(result)))
        case = deepcopy(template)
        case.update(name=name, kind='roll_constraint', job=deepcopy(job), baseline=str(result))
        case['job']['source'] = template['job']['source']
        assert 'saved_result' not in case
        cases.append(case)
    assert len(cases) == 10 and len(reused) == 2
    # Check the most discriminating mesh endpoint before starting the rest.
    cases.sort(key=lambda c: (c['name'] != 'sibling-lift-roll-free-op6-m160',
                              c['job']['nominal'], c['job']['native_operating_point']))
    OUT.mkdir()
    write(OUT / 'plan.json', dict(
        observed_utc=datetime.now(timezone.utc).isoformat(), cases=cases, reused=reused,
        pins=[pin(p) for p in sorted(paths)], limits=run.run.supervisor.LIMITS,
        constraint=parent['constraint'], control_change=parent['control_change'],
        qualifications=parent['qualifications'] + [
            'All six archived speeds on nominal80/160, with previous endpoint solves reused only after source/receipt checks.',
            'The active-control row mapping and MM derivative convention remain conditional after the original and extended manual review.',
            'No primary pass, scope, default or input adoption follows from these alternatives.'],
        previous_goal_turn='Progress: verified full coupled derivative and two endpoint operating-constraint diagnostics; published 176 checks and preserved original failures.',
        method=__doc__, primary_votes_added=0,
        derivative_convention_review='Drela steady Eqs212-213 include free acceleration response. Original manual describes M axis selection, and extended manual p23 only identifies force derivative reporting; neither establishes the archived MM mask or force-response convention.',
        selected_mesh_comparison_gate_percent=5.0))
    print('Prepared 10 serial diagnostic solves; 2 verified endpoint results retained.')


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'launch':
        run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1] == 'worker':
        run.worker(sys.argv[2])
    else:
        raise ValueError(sys.argv[1])
