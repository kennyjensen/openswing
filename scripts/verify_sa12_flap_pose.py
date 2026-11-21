"""Four predeclared SA-12 flapped points under baseline and frozen/zero-pitch setups."""
import argparse
from decimal import Decimal
from pathlib import Path
import resource
import sys
import time

import verify_sa12_current_pilot as io

ROOT = Path(__file__).resolve().parents[1]
POINTS = [('05', -5.), ('05', 2.), ('2', 5.), ('inf', 5.)]


def prepare(out):
    io.bounded()
    prior = io.read(ROOT / 'artifacts/isae/sa12-current-pilot-20261108/plan.json')
    io.authenticate(prior['pins'])
    pins = dict(prior['pins'])
    for path in [Path(__file__), ROOT / 'scripts/sa12_image_replay.py',
                 ROOT / 'docs/validation/isae-sa12-pose-diagnostics-20261109.md',
                 ROOT / 'artifacts/isae/sa12-frozen-pose-20261109/analysis.json']:
        pins[str(path.relative_to(ROOT))] = io.sha(path)
    jobs = io.adapter.plan(ROOT)
    cases = []
    for height, alpha in POINTS:
        job, = [j for j in jobs if j['flap'] == 'Flap' and j['height_label'] == height
                and j['settings']['alpha'] == alpha and j['settings']['panels'] == 100]
        assert job['archived_stall_flag'] == 0
        for frozen in (False, True):
            settings = dict(job['settings'])
            if frozen:settings.update(freeze_influences=True, attitude=[0.,0.,0.])
            cases.append(dict(id=f"Flap-h{height}-a{alpha:g}-{'frozen' if frozen else 'baseline'}",
                              job=job, settings=settings, setup='zero_pitch_frozen' if frozen else 'wind_parallel_current'))
    assert not out.exists()
    out.mkdir(parents=True)
    io.write(out / 'plan.json', dict(observed_utc=io.utc(), cases=cases, pins=pins,
        protocol='Four original flapped-model points with archived stall flag0: h/c0.5 at -5,+2deg; h/c2 and nominal infinity at5deg. Baseline pitch=alpha/current and alternative pitch0/frozen. Full nonlinear stall law stays enabled; no post-stall repair or selected output substitution.',
        acceptance='5% CL/CD/CDi, unchanged printed tiny Cm gates. Each setup separate; not added to primary4080.',
        production_calls=8, verification_calls=8, primary_passes_added=0,
        prior_turn='Progress: four production no-flap alternative states verified; historical K/F and pose remain ambiguous.'))
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    io.signal.alarm(0)
    print('Prepared eight serial solves and eight separate saved-field replays.')


def inputs(out, index):
    plan = io.read(out / 'plan.json')
    io.authenticate(plan['pins'])
    case = plan['cases'][index]
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    model = parse_asw((ROOT / case['job']['model_path']).read_text(),
                      beam_interpolation=case['settings']['beam_interpolation'])
    assert not model.diagnostics
    return plan, case, model


def run(out, index):
    io.bounded()
    start = time.monotonic()
    plan, case, model = inputs(out, index)
    from openswing.aero import FlightCondition, solve_rigid
    import numpy as np
    folder = out / case['id']
    assert not folder.exists()
    settings = case['settings']
    condition = FlightCondition(**{key:settings[key] for key in io.adapter.CONDITION_FIELDS})
    raw = solve_rigid(model, condition, panels=settings['panels'])
    assert raw['converged'] and raw['residual'] < 1e-8
    assert raw['ground_plane']['attitude'] == settings['attitude']
    assert raw['ground_plane']['minimum_clearance'] > 0
    comparisons = []
    for name in ('CL','CD','CDi','Cm'):
        value = float(raw[name])
        ref = case['job']['reference_row']['fields'][name]
        expected = ref['value']
        tolerance = ref['tolerance'] if abs(expected) <= 1e-8 else max(ref['tolerance'], .05 * abs(expected))
        comparisons.append(dict(name=name, actual=value, expected=expected, tolerance=tolerance,
            error_percent=None if abs(expected) <= 1e-8 else 100 * (value-expected) / abs(expected),
            passed=abs(value-expected) <= tolerance))
    payload = {key:raw[key] for key in ('CL','CD','CDi','Cm','CDi_near','CDp','force','moment',
                                      'strips','converged','residual','ground_plane','trefftz')}
    def clean(value):
        if isinstance(value, np.ndarray):return value.tolist()
        if isinstance(value, np.generic):return value.item()
        if isinstance(value, dict):return {k:clean(v) for k,v in value.items()}
        if isinstance(value, list):return [clean(v) for v in value]
        return value
    folder.mkdir()
    io.write(folder / 'result.json', clean(payload))
    report = dict(observed_utc=io.utc(), case=case, comparisons=comparisons,
        passed=sum(c['passed'] for c in comparisons), required=4, numerical_pass=True,
        production_calls=1, primary_passes_added=0, residual=float(raw['residual']),
        seconds=time.monotonic()-start, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=io.sha(out / 'plan.json'), result_sha256=io.sha(folder / 'result.json'))
    io.write(folder / 'report.json', report)
    io.signal.alarm(0)
    print({key:report[key] for key in ('comparisons','residual','seconds','peak_rss_kib')})


def verify(out, index):
    io.bounded()
    plan, case, model = inputs(out, index)
    from sa12_image_replay import replay
    folder = out / case['id']
    report = io.read(folder / 'report.json')
    assert report['case'] == case and report['plan_sha256'] == io.sha(out / 'plan.json')
    assert report['result_sha256'] == io.sha(folder / 'result.json')
    raw = io.read(folder / 'result.json')
    tokens = (ROOT / case['job']['table_path']).read_text().splitlines()[case['job']['reference_row']['line_number']-1].split()
    assert tokens == case['job']['reference_row']['tokens']
    for check, column in zip(report['comparisons'], range(5,9), strict=True):
        expected = Decimal(tokens[column])
        tolerance = Decimal(str(case['job']['reference_row']['fields'][check['name']]['tolerance']))
        if abs(expected) > Decimal('1e-8'):tolerance = max(tolerance, Decimal('.05') * abs(expected))
        assert check['actual'] == raw[check['name']] and check['expected'] == float(expected)
        assert check['passed'] == (abs(Decimal(str(check['actual']))-expected) <= tolerance)
    verification = replay(model, case['settings'], raw)
    verification.update(observed_utc=io.utc(), case=case['id'], production_calls=0,
        plan_sha256=io.sha(out / 'plan.json'), report_sha256=io.sha(folder / 'report.json'))
    io.write(folder / 'verification.json', verification)
    io.signal.alarm(0)
    print(verification)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run','verify'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.action == 'prepare':prepare(args.output.resolve())
    elif args.action == 'run':run(args.output.resolve(), args.index)
    else:verify(args.output.resolve(), args.index)
