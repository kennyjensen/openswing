"""Retain both original native-time gates and every shared-time field gate."""
import argparse
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path

from isae_ffwt4_evidence import pin, require, write

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'scripts/assess-isae-ffwt4-field-refinement.py'
spec = importlib.util.spec_from_file_location('ffwt4_shared_fields', BASE)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
DT = Decimal('.0149')
LIMIT = .001


def native_moments(frames, divisor):
    """Select the original 200 physical times, without interpolating values."""
    require(divisor in (2, 4, 8, 16), 'Unsupported time grid')
    values = []
    count = 0
    for tick, frame in enumerate(frames):
        require(tick <= 199*divisor and frame['tick'] == tick and
                math.isfinite(frame['time']) and abs(frame['time']-float(tick*DT/divisor)) <= 1e-10,
                'Incomplete or shifted time grid')
        require(math.isfinite(frame['moment']), 'Nonfinite saved moment')
        if tick % divisor == 0:
            values.append(frame['moment'])
        count += 1
    require(count == 199*divisor+1 and len(values) == 200, 'Complete 200-time comparison required')
    return values


def compare_native(coarser, finer):
    require(len(coarser) == len(finer) == 200 and all(math.isfinite(v) for v in coarser+finer),
            'Two complete finite native-time moment series required')
    gates = {}
    for name in ('root_moment', 'gust_increment'):
        c = [v-coarser[0] for v in coarser] if name == 'gust_increment' else coarser
        f = [v-finer[0] for v in finer] if name == 'gust_increment' else finer
        scale = max(map(abs, f))
        require(math.isfinite(scale) and scale > 0, 'Nonzero finite native-time scale required')
        differences = [abs(a-b) for a, b in zip(c, f)]
        require(all(math.isfinite(v) for v in differences), 'Nonfinite comparison difference')
        worst = max(range(200), key=differences.__getitem__)
        delta = differences[worst]
        gates[name] = dict(maximum_absolute_difference=delta, fine_scale=scale,
                           maximum_percent_of_scale=100*delta/scale, relative_limit=LIMIT,
                           passed=delta <= LIMIT*scale, worst_native_row=worst+1,
                           worst_time=float(worst*DT))
    return dict(common_times=200, gates=gates, passed=sum(g['passed'] for g in gates.values()), required=2)


def combine(shared, native):
    names = ('root_moment', 'gust_increment', 'displacement', 'rotation_vector')
    require(set(shared['gates']) == set(names) and
            set(native['gates']) == {'root_moment', 'gust_increment'}, 'Changed accuracy scope')
    require(all(g['relative_limit'] == LIMIT for result in (shared, native) for g in result['gates'].values()),
            'Numerical accuracy allowance changed')
    gates = {name: shared['gates'][name]['passed'] and
             (native['gates'][name]['passed'] if name in native['gates'] else True) for name in names}
    return dict(gates=gates, passed=sum(gates.values()), required=4)


def assess(coarse_path, fine_path, kind, output):
    require(not output.exists(), 'Preserve earlier comparison artifacts')
    helper_pin, base_pin = pin(__file__), pin(BASE)
    shared_folder = output/'shared-time-comparison'
    shared = base.assess(coarse_path, fine_path, kind, shared_folder)
    require(pin(BASE) == base_pin and shared['helper'] == base_pin, 'Shared-time checker changed')
    values = []
    for extract, divisor in zip(shared['extracts'], shared['divisors']):
        saved = extract['file']
        require(pin(saved['path']) == saved, 'Extracted fields changed')
        values.append(native_moments(base.frames(saved['path']), divisor))
        require(pin(saved['path']) == saved, 'Extracted fields changed during native-time comparison')
    native = compare_native(*values)
    combined = combine(shared, native)
    require(pin(__file__) == helper_pin and pin(BASE) == base_pin, 'Checker changed during comparison')
    result = dict(status='FULL_HISTORY_FIELDS_AND_NATIVE_TIMES_ASSESSED', kind=kind,
                  shared_time_assessment=pin(shared_folder/'assessment.json'),
                  all_shared_times={k: shared[k] for k in ('common_times', 'common_nodes', 'gates', 'passed', 'required')},
                  original_native_times=native, combined_accuracy=combined,
                  inputs=[pin(coarse_path), pin(fine_path)]+[e['file'] for e in shared['extracts']],
                  helper=helper_pin, shared_time_helper=base_pin, physical_solves=0,
                  native_fraction_change=0, full_family_validated=False,
                  qualifications=shared['qualifications']+[
                      'The original 200-time root-moment and gust-increment gates retain their own fine-grid normalizations.',
                      'Each root quantity must pass both its original native-time gate and its denser shared-time gate.',
                      'A peak between native output times cannot enlarge the original gates\' normalization scales.',
                      'The four combined quantity gates do not count repeated native targets as additional coverage.'])
    write(output/'assessment.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coarser', required=True, type=Path)
    parser.add_argument('--finer', required=True, type=Path)
    parser.add_argument('--kind', required=True, choices=('spatial', 'temporal'))
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    result = assess(args.coarser, args.finer, args.kind, args.output_dir)
    print(json.dumps({k: result[k] for k in ('status', 'kind', 'original_native_times', 'combined_accuracy')}))


if __name__ == '__main__':
    main()
