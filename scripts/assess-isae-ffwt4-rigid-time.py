"""Assess complete synthetic tip histories against an independent oscillator."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from isae_ffwt4_evidence import pin, read, require, write


def oracle(times, points, hinge, angle, frequency):
    """Exact finite rotation of a vacuum rigid body with a linear hinge spring."""
    theta = angle*np.cos(frequency*times)
    rate = -angle*frequency*np.sin(frequency*times)
    acceleration = -frequency**2*theta
    position, velocity, point_acceleration = [], [], []
    for p in points:
        x, y, z = p[0], p[1]-hinge, p[2]
        Y = y*np.cos(theta)-z*np.sin(theta)
        Z = y*np.sin(theta)+z*np.cos(theta)
        position.append(np.stack((np.full_like(times, x), hinge+Y, Z), axis=-1))
        velocity.append(np.stack((np.zeros_like(times), -rate*Z, rate*Y), axis=-1))
        point_acceleration.append(np.stack((np.zeros_like(times), -acceleration*Z-rate**2*Y,
                                            acceleration*Y-rate**2*Z), axis=-1))
    return dict(angle=theta, rate=rate, angular_acceleration=acceleration,
                position=np.stack(position, axis=1), velocity=np.stack(velocity, axis=1),
                acceleration=np.stack(point_acceleration, axis=1))


def literal_point_properties():
    from openswing.asw import parse_asw
    path = ROOT/'artifacts/isae/ffwt4-source-audit-20261106/rigid-tip-preflight.json'
    previous = read(path)
    rows, pins = [], [pin(path)]
    for certificate in previous['certificates']:
        source = certificate['source']
        require(pin(source['path']) == source, 'Literal PM2 source changed')
        model = parse_asw(Path(source['path']).read_text(), beam_interpolation='drela-segspl-v1')
        r = model.records['weight'][certificate['original_weight_record']-1]
        require(int(r[0]) == certificate['beam'] and r[1] == certificate['literal_station'],
                'Wrong original point object')
        rows.append(dict(model=certificate['model'], source=source,
            record=certificate['original_weight_record'], beam=int(r[0]), station=float(r[1]),
            position=r[2:5].tolist(), weight=float(r[5]), mass=float(r[5]/model.constants[0]),
            gravity_constant=float(model.constants[0]), CDA=float(r[6]), volume=float(r[7]),
            spin=(r[8:11]/model.constants[0]).tolist(),
            inertia_entries=(r[11:17]/model.constants[0]).tolist()))
        pins.append(source)
    require(len(rows) == 6 and all(r['CDA'] == r['volume'] == 0 and not any(r['spin'])
            and not any(r['inertia_entries']) for r in rows), 'Unexpected point physics')
    return rows, pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve previous assessment')
    spec = importlib.util.spec_from_file_location('rigid_time', ROOT/'scripts/verify-isae-ffwt4-rigid-time.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    terminals = []
    for path in sorted(args.root.glob('terminal-*.json')):
        data = read(path)
        for row in data.get('attempts', [data]):
            require(row['exit_code'] == 0, 'Failed attempt needs explicit accounting')
            require(pin(row['helper']['path']) == row['helper'], 'Changed runner helper')
            cmd = row['command']; folder = Path(cmd[cmd.index('--output-dir')+1]).resolve()
            terminals.append((folder, pin(path)))
    folders = [folder for folder, _ in terminals]
    require(len(set(folders)) == len(folders), 'Duplicate successful process receipt')
    pins, studies = [], []
    series = {}
    for representation in ('pylon', 'extension'):
        for tag, dt, count in (('020', .02, 10), ('010', .01, 20), ('005', .005, 40)):
            rows, previous, kernel, helpers = [], None, None, None
            for end in range(10, count+1, 10):
                folder = (args.root/f'{representation}-h{tag}-s{end:03d}').resolve()
                require(folders.count(folder) == 1, 'Missing actual process receipt')
                report = read(folder/'report.json'); plan = read(folder/'plan.json')
                require(report['status'] == 'SEGMENT_COMPUTED' and report['accepted_steps'] == 10
                        and report['rejected_steps'] == 0, 'Incomplete segment')
                require(plan['start_step'] == end-10 and plan['end_step'] == end
                        and float(plan['dt']) == dt and plan['representation'] == representation,
                        'Wrong coverage or representation')
                require(plan['duration'] == .2 and plan['tolerance'] == 1e-10, 'Changed study gates')
                for value in [*plan['kernel_pins'], *plan['helper_pins'], plan['model'],
                              report['plan'], report['result'], report['checkpoint']]:
                    require(pin(value['path']) == value, 'Changed evidence: '+value['path'])
                    pins.append(value)
                if kernel is not None:
                    require(kernel == plan['kernel_pins'] and helpers == plan['helper_pins'], 'Mixed equations')
                kernel, helpers = plan['kernel_pins'], plan['helper_pins']
                result = read(report['result']['path'])
                require(result['converged'] and len(result['snapshots']) == 11, 'Invalid result')
                require(result['temporal_policy'] == 'drela-euler-bdf-v1', 'Wrong temporal equations')
                actual = helper.samples(result, representation == 'extension')
                require(actual == report['samples'], 'Report does not match saved states')
                if previous is None:
                    require(plan['parent_report'] is None, 'Cold start required')
                    require(abs(actual[0]['angle']-helper.ANGLE) < 1e-10
                            and abs(actual[0]['rate']) < 1e-12, 'Incorrect release initial state')
                else:
                    require(plan['parent_report'] == pin(previous/'report.json'), 'Wrong predecessor')
                    require(result['checkpoint_validation']['discrete_replayed'], 'Missing discrete replay')
                    # The first snapshot is labeled order=0 and recalculates
                    # the residual norm; both norms must still pass 1e-10.
                    # The accepted method and every physical value are exact.
                    require({k: v for k, v in actual[0].items() if k not in ('order', 'residual')} ==
                            {k: v for k, v in rows[-1].items() if k not in ('order', 'residual')},
                            'State changed at checkpoint boundary')
                for i, row in enumerate(actual):
                    tick = end-10+i
                    require(abs(row['time']-tick*dt) < 1e-12 and row['residual'] <= 1e-10, 'Invalid tick')
                    if i:
                        require(row['effective_order'] == (1 if tick == 1 else 2), 'Lost BDF predecessor')
                rows.extend(actual if previous is None else actual[1:]); previous = folder
                pins.append(pin(folder/'report.json'))
            require(len(rows) == count+1 and abs(rows[-1]['time']-.2) < 1e-12, 'Incomplete horizon')
            times = np.array([r['time'] for r in rows])
            expected = oracle(times, helper.POINTS, helper.HINGE, helper.ANGLE, helper.FREQUENCY)
            values = {k: np.array([r[k] for r in rows]) for k in ('angle', 'rate', 'angular_acceleration')}
            values.update({k: np.array([[p[k] for p in r['points']] for r in rows])
                           for k in ('position', 'velocity', 'acceleration')})
            radius = max(np.hypot(p[1]-helper.HINGE, p[2]) for p in helper.POINTS)
            scales = dict(angle=helper.ANGLE, rate=helper.ANGLE*helper.FREQUENCY,
                angular_acceleration=helper.ANGLE*helper.FREQUENCY**2,
                position=radius*helper.ANGLE, velocity=radius*helper.ANGLE*helper.FREQUENCY,
                acceleration=radius*(helper.ANGLE+helper.ANGLE**2)*helper.FREQUENCY**2)
            # The release instant is a pre-input equilibrium. Its zero recorded
            # acceleration is not the post-release oracle acceleration.
            errors = {k: float(np.max(np.abs(values[k][1:]-expected[k][1:]))/scales[k]) for k in values}
            studies.append(dict(representation=representation, dt=dt, accepted_steps=count,
                rejected_steps=0, maximum_residual=max(r['residual'] for r in rows),
                maximum_scaled_errors=errors, normalization_scales=scales,
                finer_than_0_1_percent={k: v <= .001 for k, v in errors.items()}))
            series[(representation, dt)] = dict(times=times, values=values, oracle=expected, rows=rows)
    ratios = []
    for representation in ('pylon', 'extension'):
        group = [s for s in studies if s['representation'] == representation]
        ratios.append(dict(representation=representation,
            error_reduction=[{k: coarse['maximum_scaled_errors'][k]/fine['maximum_scaled_errors'][k]
                              for k in coarse['maximum_scaled_errors']}
                             for coarse, fine in zip(group, group[1:])]))
    differences = []
    for dt in (.02, .01, .005):
        a, b = series[('pylon', dt)], series[('extension', dt)]
        require(np.max(abs(a['times']-b['times'])) < 1e-12, 'Mismatched physical times')
        scales = next(s for s in studies if s['dt'] == dt)['normalization_scales']
        differences.append(dict(dt=dt, maximum_scaled_differences={k:
            float(np.max(abs(a['values'][k][1:]-b['values'][k][1:]))/scales[k]) for k in scales}))
    properties, source_pins = literal_point_properties()
    pins += [pin(__file__)] + [receipt for _, receipt in terminals] + source_pins
    unique = {p['path']: p for p in pins}
    result = dict(status='INTEGRATED_RIGID_TIP_ASSESSED', observed_at=datetime.now(timezone.utc).isoformat(),
        successful_jobs=len(folders), trajectories=6, studies=studies, convergence=ratios,
        paired_differences=differences, pins=list(unique.values()), physical_solves=0,
        literal_out_of_range_point_properties=properties,
        native_predictions_added=0, production_attachment_rule_changed=False,
        native_attachment_semantics_established=False,
        qualifications=['Synthetic vacuum spring release using two literal right-tip point locations.',
            'The spring frequency 5 rad/s and initial angle .4 rad are declared inputs, not aircraft calibration.',
            'Only x-axis rotation and zero intrinsic tensor/spin/CDA/volume are integrated here.',
            'Error scales are fixed physical amplitudes, not per-grid fitted maxima.',
            'Initial acceleration is pre-release; acceleration comparisons use post-release steps.',
            'No complete FFWT-4 trajectory, browser execution or native attachment convention is established.'])
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ('status', 'successful_jobs', 'studies', 'convergence', 'paired_differences')}, indent=2))


if __name__ == '__main__':
    main()
