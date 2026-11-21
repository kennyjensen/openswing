"""Isolated exact-equation candidate: discard obsolete Newton storage first."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae3_roll_control as run
from scripts.probe_isae_ae2_cold_trace import read, write, pin

OUT = ROOT / 'artifacts/isae/ae3-rebuild-memory-20261111'
BASE = ROOT / 'artifacts/isae/ae3-roll-refine-20261111'
SWEEP = ROOT / 'artifacts/isae/ae3-roll-sweep-20261111'
run.OUT = run.run.OUT = run.run.supervisor.OUT = OUT
run.run.supervisor.__file__ = __file__


def prepare():
    assert not OUT.exists()
    parent = read(BASE / 'plan.json')
    for p in parent['pins']:
        assert pin(p['path']) == p, p['path']
    failed = BASE / 'cases' / parent['cases'][0]['name']
    terminal = read(failed / 'terminal.json')
    assert terminal['returncode'] == 1 and terminal['process_reaped']
    assert 'Unable to allocate' in (failed / 'stderr.log').read_text()
    source = ROOT / 'openswing/structured_static.py'
    original = source.read_text()
    changes = [
        ("                if method=='fresh':\n                    matrix,counts=jacobian",
         "                if method=='fresh':\n                    matrix=factorization=None\n                    matrix,counts=jacobian"),
        ("                    matrix = net.jacobian(state,target,progress=progress,",
         "                    matrix=factorization=None\n                    matrix = net.jacobian(state,target,progress=progress,")]
    candidate = original
    for before, after in changes:
        assert candidate.count(before) == 1
        candidate = candidate.replace(before, after)
    code = OUT / 'candidate'
    shutil.copytree(ROOT / 'openswing', code / 'openswing', ignore=shutil.ignore_patterns('__pycache__'))
    (code / 'openswing/structured_static.py').write_text(candidate)
    paths = {p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__), BASE / 'plan.json',
        SWEEP / 'plan.json', failed / 'terminal.json', failed / 'stderr.log'))
    paths.update(str(p) for p in (code / 'openswing').rglob('*') if p.is_file())
    control = deepcopy(next(c for c in read(SWEEP / 'plan.json')['cases']
                            if c['name'] == 'sibling-lift-roll-free-op6-m160'))
    saved = SWEEP / 'cases' / control['name']
    control.update(name='rebuild-control-op6-m160', parity_result=str(saved / 'result.json'))
    paths.update(str(saved / name) for name in ('result.json', 'report.json', 'terminal.json'))
    high = deepcopy(parent['cases'][0]); high['name'] = 'rebuild-refine-op6-m320'
    write(OUT / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=[control, high], pins=[pin(p) for p in sorted(paths)],
        limits=run.run.supervisor.LIMITS, constraint=parent['constraint'],
        control_change=parent['control_change'], qualifications=parent['qualifications'],
        method=__doc__, changes=changes, candidate_root=str(code),
        parity_gate=2e-10, primary_votes_added=0, production_changes=False,
        rationale='The discarded matrix/factor will be replaced unconditionally. Release it before, rather than after, constructing the next exact matrix. No column, equation or numerical gate changes.'))
    print('Prepared isolated release-before-rebuild candidate: one parity control, one refinement.')


def worker(name):
    plan = read(OUT / 'plan.json')
    case = next(c for c in plan['cases'] if c['name'] == name)
    sys.path.insert(0, plan['candidate_root'])
    import openswing
    assert Path(openswing.__file__).resolve().parent == Path(plan['candidate_root']) / 'openswing'
    run.worker(name)
    folder = OUT / 'cases' / name
    result = read(folder / 'result.json'); report = read(folder / 'report.json')
    nominal = case['job']['nominal']
    assert result['converged'] and len(result['strips']) == nominal+2
    assert len(result['equilibrium_state']['positions']) == nominal+3
    report.update(actual_intervals=nominal+2, actual_nodes=nominal+3,
                  literal_fixed_acceleration_nominal=case.get('baseline_fixed_nominal', nominal))
    if 'parity_result' in case:
        import numpy as np
        prior = read(case['parity_result'])
        checks = []
        for key in ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions', 'circulation'):
            a, b = (np.asarray(r['equilibrium_state'][key]) for r in (result, prior))
            error = float(np.max(abs(a-b), initial=0)/max(1., np.max(abs(b), initial=0)))
            checks.append(dict(name=key, metric=error, gate=plan['parity_gate'], passed=error <= plan['parity_gate']))
        for key in ('distributed_aero_force', 'distributed_aero_moment'):
            a, b = (np.asarray(r[key]) for r in (result, prior))
            error = float(np.max(abs(a-b), initial=0)/max(1., np.max(abs(b), initial=0)))
            checks.append(dict(name=key, metric=error, gate=plan['parity_gate'], passed=error <= plan['parity_gate']))
        error = max(abs(result['operating_values'][k]-v)/max(1., abs(v)) for k, v in prior['operating_values'].items())
        checks.append(dict(name='operating_values', metric=error, gate=plan['parity_gate'], passed=error <= plan['parity_gate']))
        report['candidate_parity_checks'] = checks
        assert all(c['passed'] for c in checks), checks
    write(folder / 'report.json', report)


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'launch':
        run.run.supervisor.launch(sys.argv[2])
    elif sys.argv[1] == 'worker':
        worker(sys.argv[2])
    else:
        raise ValueError(sys.argv[1])
