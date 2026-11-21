"""Isolate the 70-micrometre lower-winglet root gap; never edit a supplied model.

Run serially with one BLAS thread. An optional prior junction-study directory
can supply the four original states only when its source/condition/module pins
match. Without that directory, all eight original/perturbed states are solved.
"""
from argparse import ArgumentParser
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import AnalysisError, FlightCondition, solve_rigid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_condition(first, second):
    # Saved JSON has lists where asdict() retains tuples. Compare the serialized
    # physical settings, so an explicit cache request cannot silently miss.
    return json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-junction', type=Path)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'plan.json').exists():
        raise SystemExit('Use a fresh output directory; prior observations are retained.')
    path = ROOT / 'examples/isae-sa11-wingtip-up-and-down.asw'
    original = path.read_text()
    needle = '1.525    -7'
    assert original.count(needle) == 2
    changed = original.replace(needle, '1.5257   -7')
    inputs = {'original': original, 'root-height-aligned': changed}
    for name, text in inputs.items():
        (out / (name + '.asw')).write_text(text)
    models = {name: parse_asw(text) for name, text in inputs.items()}
    first, second = models.values()
    # Check exactly which physical input distributions changed.
    distribution_changes = []
    for a, b in zip(first.beams, second.beams):
        assert a.index == b.index and a.domain == b.domain
        assert a.distributions.keys() == b.distributions.keys()
        for key in a.distributions:
            x, y = a.distributions[key], b.distributions[key]
            assert x.name == y.name and x.interpolation == y.interpolation
            assert np.array_equal(x.t, y.t)
            if not np.array_equal(x.values, y.values):
                distribution_changes.append([a.index, key])
    assert distribution_changes == [[4, 'z'], [5, 'z']], distribution_changes
    module_pins = {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    reused = []
    baseline_files = {}
    if args.reuse_junction:
        for plan_name, result_name in [('plan.json', 'results.json'),
                                       ('unfrozen-plan.json', 'unfrozen-results.json')]:
            plan_path, result_path = [args.reuse_junction / x for x in (plan_name, result_name)]
            assert json.loads(plan_path.read_text())['modules'] == module_pins
            baseline_files[str(plan_path)] = sha(plan_path)
            baseline_files[str(result_path)] = sha(result_path)
            reused.extend(json.loads(result_path.read_text()))
    conditions = {freeze: asdict(FlightCondition(speed=30., alpha=5., freeze_influences=freeze))
                  for freeze in [True, False]}
    requests = [dict(input=name, panels=n, condition=conditions[freeze])
                for freeze in [True, False] for n in [48, 96] for name in inputs]
    def cached(request):
        matches = [r for r in reused if request['input'] == 'original'
                   and r['example'] == 'isae-sa11-wingtip-up-and-down'
                   and r['panels'] == request['panels']
                   and same_condition(r['condition'], request['condition'])
                   and r['input_sha256'] == sha(path)]
        assert len(matches) <= 1
        if args.reuse_junction and request['input'] == 'original' and not matches:
            raise ValueError('Requested baseline reuse has no exactly matching source and condition.')
        return matches
    # Validate all cache requests before making any new physical calls.
    for request in requests:
        cached(request)
    (out / 'driver-used.py').write_bytes(Path(__file__).read_bytes())
    plan = dict(utc=datetime.now(timezone.utc).isoformat(), requests=requests,
                modules=module_pins, driver_sha256=sha(Path(__file__)),
                input_sha256={name: sha(out / (name + '.asw')) for name in inputs},
                source_input_sha256=sha(path), cached_baseline_files=baseline_files,
                distribution_changes=distribution_changes,
                scope='Temporary source-height diagnostic, not a corrected reference input or new validation scope.')
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    rows = []
    for request in requests:
        row = dict(**request, utc=datetime.now(timezone.utc).isoformat())
        matches = cached(request)
        if matches:
            previous = matches[0]
            row.update(reused=True, status=previous['status'], details=previous['details'],
                       original_observation_utc=previous['utc'])
        else:
            start = time.monotonic()
            try:
                result = solve_rigid(models[request['input']],
                                     FlightCondition(**request['condition']), request['panels'])
                row.update(status='computed', result={k: result[k] for k in
                    ['CL', 'CD', 'CDi', 'Cm', 'residual', 'lifting_airflow']})
            except AnalysisError as exc:
                row.update(status='rejected', error=str(exc), details=exc.details)
            row.update(reused=False, seconds=time.monotonic() - start)
        rows.append(row)
        (out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
        maximum = (row.get('details') or {}).get('maximum') or row.get('result', {}).get('lifting_airflow', {}).get('maximum')
        print(request['input'], request['panels'], request['condition']['freeze_influences'],
              row['status'], maximum, 'reused' if row['reused'] else 'fresh', flush=True)
        gc.collect()
    assert module_pins == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    assert sha(path) == plan['source_input_sha256']
    pairs = []
    for freeze in conditions:
        for n in [48, 96]:
            a, b = [r for r in rows if r['panels'] == n and r['condition']['freeze_influences'] == freeze]
            def maximum_mach(row):
                if row['status'] == 'rejected':
                    return (row['details'] or {}).get('maximum', {}).get('normal_mach')
                return row['result']['lifting_airflow']['maximum']['normal_mach']
            pairs.append(dict(frozen=freeze, panels=n, original_status=a['status'],
                              aligned_status=b['status'], original_max_mach=maximum_mach(a),
                              aligned_max_mach=maximum_mach(b)))
    report = dict(utc=datetime.now(timezone.utc).isoformat(), pairs=pairs,
                  fresh_calls=sum(not r['reused'] for r in rows), reused_states=sum(r['reused'] for r in rows),
                  production_and_source_unchanged=True, plan_sha256=sha(out / 'plan.json'),
                  results_sha256=sha(out / 'results.json'))
    (out / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
