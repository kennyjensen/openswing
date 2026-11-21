"""Check each oscillator point against its own physical motion scale.

The inboard point is much nearer the hinge. A shared outboard-radius scale
must not be used to infer the inboard point's individual relative accuracy.
"""
import argparse
import importlib.util
from pathlib import Path
import json
import numpy as np
from isae_ffwt4_evidence import pin, read, require, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve previous evidence')
    base = read(args.assessment)
    require(base['status'] == 'INTEGRATED_RIGID_TIP_ASSESSED', 'Complete histories required')
    root = args.assessment.parent
    known = {p['path']: p for p in base['pins']}
    module_path = Path(__file__).with_name('assess-isae-ffwt4-rigid-time.py').resolve()
    require(pin(module_path) == known[str(module_path)], 'Changed oracle helper')
    spec = importlib.util.spec_from_file_location('rigid_time_assessment', module_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    studies, pins = [], [pin(args.assessment), pin(module_path), pin(__file__)]
    for study in base['studies']:
        tag = {0.02: '020', 0.01: '010', .005: '005'}[study['dt']]
        rows = []
        for end in range(10, study['accepted_steps']+1, 10):
            folder = root/f'{study["representation"]}-h{tag}-s{end:03d}'
            for filename in ('plan.json', 'report.json'):
                p = pin(folder/filename)
                require(p == known[p['path']], 'Changed saved data'); pins.append(p)
            report, plan = read(folder/'report.json'), read(folder/'plan.json')
            rows.extend(report['samples'] if end == 10 else report['samples'][1:])
        t = np.array([r['time'] for r in rows])
        expected = module.oracle(t, plan['points'], plan['hinge_y'],
                                 plan['initial_angle_rad'], plan['frequency_rad_s'])
        points = []
        for i, p in enumerate(plan['points']):
            radius = np.hypot(p[1]-plan['hinge_y'], p[2])
            A, w = plan['initial_angle_rad'], plan['frequency_rad_s']
            scales = dict(position=radius*A, velocity=radius*A*w, acceleration=radius*(A+A*A)*w*w)
            errors = {}
            for quantity, scale in scales.items():
                actual = np.array([r['points'][i][quantity] for r in rows])
                errors[quantity] = float(np.max(abs(actual[1:]-expected[quantity][1:, i]))/scale)
            points.append(dict(index=i, jig_position=p, radius=float(radius), scales=scales,
                maximum_scaled_errors=errors, passes_0_1_percent={k: e <= .001 for k, e in errors.items()}))
        studies.append(dict(representation=study['representation'], dt=study['dt'], points=points))
    fine = [p for s in studies if s['dt'] == .005 for p in s['points']]
    result = dict(status='INDIVIDUAL_POINT_MOTION_ASSESSED', studies=studies,
        finest_passed=sum(sum(p['passes_0_1_percent'].values()) for p in fine), finest_required=12,
        finest_maximum_scaled_error=max(max(p['maximum_scaled_errors'].values()) for p in fine),
        pins=list({p['path']: p for p in pins}.values()), native_predictions_added=0, physical_solves=0)
    write(args.output, result)
    print(json.dumps({k: result[k] for k in ('status', 'finest_passed', 'finest_required', 'finest_maximum_scaled_error')}))


if __name__ == '__main__':
    main()
