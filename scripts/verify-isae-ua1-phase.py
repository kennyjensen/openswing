"""Run one small, serial production-matrix UA-1 phase comparison."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time

import numpy as np
from isae_ua_phase import ROOT, GATES, source_binding, production_matrix, predict, assess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels', type=int, choices=(4, 8), required=True)
    parser.add_argument('--derivative-scale', type=float, choices=(.5, 1.), default=1.)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Preserve existing evidence; choose a fresh output directory')
    binding = source_binding()
    paths = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__).resolve(),
        ROOT/'scripts/isae_ua_phase.py', ROOT/'scripts/isae_suite_unsteady.py',
        ROOT/'tests/test_isae_ua_phase.py', ROOT/'docs/validation/isae-ua1-phase-sources-20261101.json',
        *[ROOT/n for n in binding['source_sha256']]]
    pins = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}
    args.output_dir.mkdir(parents=True)
    plan = dict(panels=args.panels, derivative_scale=args.derivative_scale, source_sha256=pins,
        gates=GATES, source_settings=binding['phase_average'],
        model=dict(aspect_ratio=200000., speed=30., base_alpha_deg=0., mach=0., stall=False, aero_lag=True),
        scope='Six linear-superposition source curves at k=.47/.94 and mean labels 0/5/9 degrees.',
        native_ASWING_comparison=False, nonlinear_finite_incidence_validation=False,
        registered_rows_before=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
    (args.output_dir/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    for p in paths:
        frozen = args.output_dir/'frozen-code'/p.relative_to(ROOT)
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, frozen)
    started = time.monotonic()
    matrix = production_matrix(args.panels, args.derivative_scale)
    prediction = predict(matrix['matrix'], speed=matrix['speed'])
    checks = assess(prediction)
    numerical = bool(np.isfinite(matrix['matrix']).all() and np.max(abs(matrix['base'])) < 1e-10
                     and prediction['static_residual'] < GATES['equation_residual'])
    source_unchanged = all(sha256((ROOT/n).read_bytes()).hexdigest() == h for n, h in pins.items())
    output = dict(plan=plan, seconds=time.monotonic()-started,
        production={k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in matrix.items()},
        prediction=prediction, checks=checks, numerical_passed=numerical,
        reference_match=all(c['passed'] for c in checks), source_unchanged=source_unchanged,
        native_ASWING_comparison=False, nonlinear_finite_incidence_validation=False)
    (args.output_dir/'report.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels, derivative_scale=args.derivative_scale,
        seconds=output['seconds'], curves_passed=sum(c['passed'] for c in checks),
        points_passed=sum(c['points_passed'] for c in checks),
        maximum_waveform_error_percent=100*max(c['maximum_waveform_error_fraction'] for c in checks),
        mean_slope=prediction['mean_incidence_slope_per_rad'], numerical_passed=numerical)), flush=True)
    if not (numerical and output['reference_match'] and source_unchanged):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
