"""Run one bundled aircraft through a workbench analysis on the native kernel."""
import argparse
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openswing.bridge import dispatch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('aircraft', choices=('dae', 'usa', 'fw'))
    parser.add_argument('mode', choices=('rigid', 'structural', 'mounted', 'modes', 'frequency', 'time'))
    parser.add_argument('--progress', action='store_true', help='Print solver stage changes and completed frequency blocks.')
    args = parser.parse_args()

    name, mode = args.aircraft, args.mode
    mesh_name = {'dae': 'daedalus', 'usa': 'sailplane'}.get(name)
    panels = 48 if mesh_name is None else json.loads((ROOT / f'web/{mesh_name}-mesh.json').read_text())
    source = (ROOT / f'examples/{name}.asw').read_text()
    policy = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1')
    condition = dict(speed=21.981627296587927, alpha=3, beta=0, stall=True,
                     freeze_influences=True, aero_lag=True)
    request = dict(action=mode if mode in ('modes', 'frequency', 'time') else 'solve',
                   mode=mode, source=source, panels=panels, condition=condition, numerics=policy)

    if mode == 'rigid':
        del request['numerics']
    elif mode == 'structural':
        request['numerics'] = dict(policy, structural_operator='drela-steady-section-v1')
        request['condition'] = None
    elif mode == 'modes':
        request['modes'] = dict(frame='fixed', count=12, method='full_shift_invert')
    elif mode == 'frequency':
        model = dispatch(dict(action='inspect', source=source, panels=panels, numerics=policy))
        inputs = [f'control.{i}' for i in model['controls']]
        inputs.extend(f"power.{engine['index']}" for engine in model['engine_controls'])
        inputs.append(dict(kind='gust', name='gust cosine n=0', direction=[0, 0, 1],
                           span_mode=0, symmetry='cosine', wave='convected'))
        request['frequency'] = dict(frame='free', frequencies=[
            2*math.pi*10**(-1+i/10) for i in range(21)], inputs=inputs)
        request['retain_frequency'] = True
    elif mode == 'time':
        request['time'] = dict(frame='prescribed', duration=.2, dt=.01, order=2)

    start = time.monotonic()
    last = None

    def progress(stage, current, total):
        nonlocal last
        marker = (stage, int(current)//5 if stage == 'frequency' else None)
        if marker != last:
            last = marker
            print(f'{time.monotonic()-start:.2f} s: {stage} ({current}/{total})', flush=True)

    result = dispatch(request, progress=progress if args.progress else None,
                      _copy_frequency_result=False)
    if not result.get('converged'):
        errors = [sample['error'] for sample in result.get('samples', []) if 'error' in sample]
        raise SystemExit(f'{name} {mode} did not converge: {"; ".join(dict.fromkeys(errors))}')
    if mode == 'modes' and len(result['modes']) != 12:
        raise SystemExit('The eigensolver did not return the requested 12 modes.')
    if mode == 'frequency' and len(result['samples']) != 21:
        raise SystemExit('The frequency response did not return the requested 21 samples.')
    if mode == 'time' and not math.isclose(result['end_time'], .2, abs_tol=1e-12):
        raise SystemExit('The time response ended before the requested duration.')
    print(f'{name} {mode}: converged in {time.monotonic()-start:.2f} s', flush=True)


if __name__ == '__main__':
    main()
