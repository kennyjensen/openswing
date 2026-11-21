"""One serial UA-2 geometry diagnostic; not native ASWING acceptance.

Run each mesh separately. Geometry is reconstructed because the original
model and modified prescribed-motion driver are absent from the UA archive.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from isae_suite_unsteady import audit_sources, harmonic_response, model_text

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels', type=int, choices=(20, 40), required=True)
    parser.add_argument('--aspect-ratio', type=float, choices=(5., 10.), default=10.,
        help='Full-wing AR; default 10 follows the primary paper\'s semi-AR5. AR5 retains the earlier diagnostic.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve completed diagnostics')
    settings = dict(panels=args.panels, aspect_ratio=args.aspect_ratio, speed=30., mach=0.,
        alpha_deg=0., stall=False, aero_lag=True, derivative_step=1e-4)
    audit = audit_sources(ROOT)
    pins = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'openswing').glob('*.py'))}
    pins.update({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__).resolve(), ROOT/'scripts/isae_suite_unsteady.py')})
    start = time.monotonic()
    result = harmonic_response(ROOT, settings)
    elapsed = time.monotonic()-start
    comparisons = []
    for row in audit['ua2'][0]['observations']:
        response = min(result['response'], key=lambda r: abs(r['k']-row['k']))
        predicted = (response['amplitude']*row['amplitude_over_chord'] if row['output'] == 'amplitude'
                     else response['phase_deg'])
        comparisons.append(dict(row, predicted=predicted, difference=predicted-row['expected'],
            percentage_difference=100*(predicted-row['expected'])/abs(row['expected'])
                if row['expected'] else None))
    stable = all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == value for name, value in pins.items())
    result = dict(scope=f'Reconstructed full-span AR{args.aspect_ratio:g}, zero-incidence, linear harmonic 3D diagnostic.',
        native_reference_comparison=False, acceptance_pass_count=None,
        settings=settings, reconstructed_asw=model_text(args.aspect_ratio), seconds=elapsed,
        source_audit=audit['ua2'][0]['formula_max_absolute_error'],
        production=result, comparisons_to_plot_formula=comparisons, code_sha256=pins,
        unchanged_code=stable, limits=[
            'Original UA-2 .asw, root/end-wall treatment and prescribed-motion modification are unavailable.',
            'The primary finite-wing paper specifies semi-AR5, supporting a symmetric AR10 reconstruction. '
                'Actual ISAE native geometry and root-wall treatment remain unverified.',
            'No .85/.90 lift scaling is applied to the computed response.',
            'This small-signal response is not the report\'s finite-amplitude single-cycle time-march.',
            'Differences from corrected 2D plot curves do not measure error against native ASWING.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels, seconds=elapsed,
        numerical_passed=result['production']['numerical_passed'], unchanged_code=stable,
        maximum_harmonic_residual=result['production']['maximum_harmonic_residual'])))
    if not stable or not result['production']['numerical_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
