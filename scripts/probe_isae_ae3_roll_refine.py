"""One additional near-reversal mesh diagnostic under unchanged resource caps."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae3_roll_control as run
from scripts.probe_isae_ae2_cold_trace import read, write, pin

OUT = ROOT / 'artifacts/isae/ae3-roll-refine-20261111'
BASE = ROOT / 'artifacts/isae/ae3-roll-sweep-20261111'
run.OUT = run.run.OUT = run.run.supervisor.OUT = OUT
run.run.supervisor.__file__ = __file__


def prepare():
    assert not OUT.exists()
    parent = read(BASE / 'plan.json')
    for p in parent['pins']:
        assert pin(p['path']) == p, p['path']
    paths = {p['path'] for p in parent['pins']}
    paths.update(str(p) for p in (Path(__file__), BASE / 'plan.json'))
    for previous in parent['cases']:
        folder = BASE / 'cases' / previous['name']
        terminal = read(folder / 'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped']
        paths.update(str(folder / f) for f in ('report.json', 'terminal.json', 'sources-verified.json'))
    previous = next(c for c in parent['cases'] if c['name'] == 'sibling-lift-roll-free-op6-m160')
    report = read(BASE / 'cases' / previous['name'] / 'report.json')
    assert report['error_percent']['Cl'] > 5
    case = deepcopy(previous)
    case.update(name='sibling-lift-roll-free-op6-m320', baseline_fixed_nominal=160)
    case['job'].update(nominal=320, mesh='m320', expected_elements=322, expected_nodes=323,
        panels=dict(default=320, beams={'1':dict(count=320, spacing='cosine')}))
    OUT.mkdir()
    write(OUT / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=[case], pins=[pin(p) for p in sorted(paths)], limits=run.run.supervisor.LIMITS,
        constraint=parent['constraint'], control_change=parent['control_change'],
        qualifications=parent['qualifications'] + [
            'One extra nominal320 mesh at op6 because nominal80/160 Cl differs by more than5%. No historical NODE array is inferred.',
            'The retained literal fixed-acceleration baseline is nominal160; no fixed-acceleration nominal320 solution is claimed.'],
        previous_evidence=dict(Cl_error_percent_at_160=report['error_percent']['Cl'],
            maximum_160_peak_rss_kib=max(read(BASE / 'cases' / c['name'] / 'terminal.json')['peak_rss_kib']
                for c in parent['cases'] if c['job']['nominal'] == 160)),
        primary_votes_added=0, selected_mesh_comparison_gate_percent=5.))
    print('Prepared one near-reversal nominal320 solve; limits unchanged.')


def worker(name):
    run.worker(name)
    folder = OUT / 'cases' / name
    result = read(folder / 'result.json')
    report = read(folder / 'report.json')
    assert result['converged'] and len(result['strips']) == 322
    assert len(result['equilibrium_state']['positions']) == 323
    report.update(actual_intervals=322, actual_nodes=323, literal_fixed_acceleration_nominal=160)
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
