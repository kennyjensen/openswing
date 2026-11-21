"""Check four unchanged-production solves against the independent pose diagnostic."""
import argparse
import math
from pathlib import Path
import resource
import sys
import time

import verify_sa12_current_pilot as io

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / 'artifacts/isae/sa12-image-pose-20261109'
FOLLOW = ROOT / 'artifacts/isae/sa12-pose-followup-20261109'


def prepare(out):
    io.bounded()
    folders = [PILOT, *(FOLLOW / name for name in
        ('No_Flap-h05-a-5', 'No_Flap-h05-a5', 'No_Flap-h2-a8'))]
    cases, pins = [], {}
    for folder in folders:
        plan = io.read(folder / 'plan.json')
        io.authenticate(plan['pins'])
        pins.update(plan['pins'])
        job = plan['baseline_job']
        cases.append(dict(id=f"No_Flap-h{job['height_label']}-a{job['settings']['alpha']:g}",
                          job=job, diagnostic=str((folder / 'zero-frozen').relative_to(ROOT))))
        for path in [folder / 'plan.json', folder / 'zero-frozen/result.json', folder / 'zero-frozen/state.npz']:
            pins[str(path.relative_to(ROOT))] = io.sha(path)
    pins[str(Path(__file__).relative_to(ROOT))] = io.sha(Path(__file__))
    assert not out.exists()
    out.mkdir(parents=True)
    io.write(out / 'plan.json', dict(observed_utc=io.utc(), pins=pins, cases=cases,
        setup='Original models, alpha, height and raw targets; explicit alternative uses pitch0 and frozen influences. No claim to recover unarchived historical settings.',
        production_calls=4, primary_passes_added=0,
        acceptance='5% raw CL/CD/CDi; unchanged printed tiny Cm gates. Keep alternative separate from primary4080.'))
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    io.signal.alarm(0)
    print('Prepared four serial production comparisons of the disclosed frozen/zero-pitch alternative.')


def run(out, index):
    io.bounded()
    start = time.monotonic()
    plan = io.read(out / 'plan.json')
    io.authenticate(plan['pins'])
    case = plan['cases'][index]
    folder = out / case['id']
    assert not folder.exists()
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, solve_rigid
    job, settings = case['job'], dict(case['job']['settings'])
    settings.update(freeze_influences=True, attitude=[0., 0., 0.])
    model = parse_asw((ROOT / job['model_path']).read_text(), beam_interpolation=settings['beam_interpolation'])
    condition = FlightCondition(**{key:settings[key] for key in io.adapter.CONDITION_FIELDS})
    raw = solve_rigid(model, condition, panels=settings['panels'])
    assert raw['converged'] and raw['residual'] < 1e-8
    diagnostic_folder = ROOT / case['diagnostic']
    diagnostic = io.read(diagnostic_folder / 'result.json')
    with np.load(diagnostic_folder / 'state.npz') as state:
        replay_errors = dict(
            circulation=float(max(abs(state['gamma'] - [row['circulation'] for row in raw['strips']]))),
            velocity=float(np.max(abs(state['velocity'] - [row['relative_velocity'] for row in raw['strips']]))),
            force=float(np.max(abs(state['force'] - [row['force'] for row in raw['strips']]))))
    assert max(replay_errors.values()) < 2e-9, replay_errors
    comparisons = []
    for name in ('CL', 'CD', 'CDi', 'Cm'):
        actual = float(raw[name])
        ref = job['reference_row']['fields'][name]
        expected = ref['value']
        tolerance = ref['tolerance'] if abs(expected) <= 1e-8 else max(ref['tolerance'], .05 * abs(expected))
        if name != 'Cm':
            assert abs(actual - diagnostic['values'][name]) < 2e-12
        comparisons.append(dict(name=name, actual=actual, expected=expected, expected_token=ref['token'],
            tolerance=tolerance, passed=abs(actual-expected) <= tolerance,
            error_percent=None if abs(expected) <= 1e-8 else 100*(actual-expected)/abs(expected)))
    assert raw['ground_plane']['attitude'] == [0., 0., 0.]
    assert raw['ground_plane']['minimum_clearance'] > 0
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
    report = dict(observed_utc=io.utc(), case=case, settings=settings, comparisons=comparisons,
        passed=sum(c['passed'] for c in comparisons), required=4, numerical_pass=True,
        independent_replay_errors=replay_errors, production_calls=1, primary_passes_added=0,
        residual=float(raw['residual']), seconds=time.monotonic()-start,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=io.sha(out / 'plan.json'), result_sha256=io.sha(folder / 'result.json'))
    io.write(folder / 'report.json', report)
    io.signal.alarm(0)
    print({key:report[key] for key in ('comparisons','independent_replay_errors','residual','seconds','peak_rss_kib')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.action == 'prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(), args.index)
