"""Audit serial UA-1 finite-heave trajectories against an independent ODE solve."""
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua-finite-heave-20261101'


def main():
    batch = json.loads((BASE/'batch-plan.json').read_text())
    summaries, audited = [], 0
    figure, axes = plt.subplots(2, 2, figsize=(10, 6.5), constrained_layout=True)
    for axis, (tag, amplitude) in zip(axes.flat, [('005', .05), ('010', .1), ('030', .3), ('050', .5)]):
        records = []
        for steps in ([40, 80, 160] if amplitude == .5 else [80, 160]):
            folder = BASE/f'k095-a{tag}-n{steps}'
            plan = json.loads((folder/'plan.json').read_text())
            report = json.loads((folder/'report.json').read_text())
            assert report['status'] == 'computed' and report['converged'] and report['production_unchanged']
            assert report['accepted_steps'] == steps and report['rejected_steps'] == 0
            assert report['structural_operator'] == 'drela-moving-airflow-v1'
            assert report['temporal_policy'] == 'drela-euler-bdf-v1'
            for name, digest in plan['code_sha256'].items():
                assert sha256((BASE/'frozen-code'/name).read_bytes()).hexdigest() == digest, name
                if name.startswith('openswing/'):
                    assert sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
            assert {n for n in plan['code_sha256'] if n.startswith('openswing/')} == {
                str(p.relative_to(ROOT)) for p in (ROOT/'openswing').glob('*.py')}
            assert plan['aspect_ratio'] == 200000. and plan['amplitude_ratio'] == amplitude and plan['k'] == .95
            request = plan['request']
            assert not request['condition']['stall'] and request['condition']['aero_lag']
            with gzip.open(folder/'trajectory.json.gz', 'rt') as stream:
                raw = json.load(stream)
            snapshots, rows = raw['snapshots'], report['comparison']['samples']
            nonlinear = report['nonlinear_section_comparison']
            assert nonlinear['native_ASWING_comparison'] is False
            assert len(snapshots) == len(rows) == len(nonlinear['rows']) == steps+1
            audited += len(snapshots)
            speed, k, h = request['condition']['speed'], plan['k'], amplitude/2
            omega = 2*speed*k
            times = np.array([s['time'] for s in snapshots])
            # This integration is separate from the verifier's quadrature
            # convolution, and imports no production code or oracle helper.
            def derivative(t, y):
                w = -h*omega*math.sin(omega*t)
                return [-speed*y[0]/2-math.pi*math.hypot(speed, w)*w/2]
            ode = solve_ivp(derivative, (0., times[-1]), [0.], method='DOP853',
                rtol=1e-12, atol=1e-13, t_eval=times)
            assert ode.success
            velocity, acceleration = -h*omega*np.sin(omega*times), -h*omega**2*np.cos(omega*times)
            crossflow = np.hypot(speed, velocity)
            gamma = ode.y[0]
            rate = -speed*gamma/2-math.pi*crossflow*velocity/2
            expected = 2*gamma/speed+2*rate/(speed*crossflow)-math.pi*acceleration/(2*speed**2)
            oracle = np.array([s['expected']['CL'] for s in nonlinear['rows']])
            ode_difference = float(np.max(np.abs(expected-oracle)))
            assert ode_difference < 1e-10
            qs = .5*1.225*speed**2*plan['aspect_ratio']
            actual = np.array([s['force'][2]/qs for s in snapshots])
            linear = np.array([s['expected']['CL'] for s in rows])
            for s, r in zip(snapshots, rows):
                assert s['time'] == r['time'] and s['force'][2]/qs == r['CL_vertical']
                assert s['residual'] == r['residual'] and s['residual'] < 1e-10
                assert abs(r['acceleration_error']) < 1e-14
                assert max(abs(v) for v in s['frame']['rates_body']+s['frame']['attitude']) < 1e-12
            error = float(np.max(np.abs(actual-expected))/np.max(np.abs(expected)))
            assert abs(error-nonlinear['maximum_waveform_error_fraction']) < 1e-9
            actual_gamma = np.array([[r['circulation'] for r in s['strips']] for s in snapshots])
            actual_rate = np.array([s['circulation_rate'] for s in snapshots])
            records.append(dict(steps=steps, seconds=report['seconds'],
                maximum_waveform_error_percent=100*error,
                maximum_circulation_error_percent=float(100*np.max(np.abs(actual_gamma-gamma[:,None]))/np.max(np.abs(gamma))),
                maximum_circulation_rate_error_percent=float(100*np.max(np.abs(actual_rate-rate[:,None]))/np.max(np.abs(rate))),
                linear_waveform_difference_percent=100*report['comparison']['maximum_waveform_error_fraction'],
                nonlinear_minus_linear_reference_percent=100*nonlinear['maximum_nonlinear_linear_difference_fraction'],
                independent_ODE_max_CL_difference=ode_difference,
                maximum_residual=report['comparison']['maximum_residual'],
                rejected_steps=report['rejected_steps'], jacobian_builds=report['jacobian_builds'],
                evidence=str(folder.relative_to(ROOT)),
                evidence_sha256={n:sha256((folder/n).read_bytes()).hexdigest()
                    for n in ('plan.json', 'report.json', 'trajectory.json.gz')}))
            if steps == 160:
                axis.plot(times/times[-1], actual/amplitude, label='OpenSwing, 160 steps', lw=1.5)
                axis.plot(times/times[-1], expected/amplitude, '--', label='Nonlinear section equations', lw=1.2)
                axis.plot(times/times[-1], linear/amplitude, ':', label='Linear equation + startup', lw=1.3)
        errors = [r['maximum_waveform_error_percent'] for r in records]
        ratios = [b/a for a,b in zip(errors[:-1], errors[1:])]
        passed = max(ratios) < batch['successive_error_ratio_maximum'] and errors[-1]/100 < batch['finest_error_fraction_maximum']
        assert passed
        summaries.append(dict(amplitude_peak_to_peak_over_chord=amplitude, k=.95,
            maximum_effective_incidence_deg=math.degrees(math.atan(amplitude*.95)),
            records=records, successive_error_ratios=ratios, refinement_gate_passed=passed))
        axis.set(title=f'A/c = {amplitude:g}; max error {errors[-1]:.4f}%',
            xlabel='Time / period (zero-circulation start)', ylabel='Vertical CL / (A/c)')
        axis.grid(alpha=.25)
        axis.legend(fontsize=7)
    result = dict(scope='UA-1 finite-amplitude attached-flow first-cycle verification at k=.95',
        native_ASWING_time_comparison=False, experimental_comparison=False,
        production_files_unchanged=len(batch['production_sha256']),
        audit_snapshots=audited, checks_passed=len(summaries), cases=summaries,
        limitations=['Not a periodic harmonic amplitude/phase or mean-lift comparison.',
                    'Only k=.95 and zero mean incidence; remaining frequencies/incidences are pending.',
                    'Stall is disabled to isolate the published attached-flow equations.',
                    'Large-aspect-ratio reconstructed limit, not a native archived model.',
                    'UA-2 native provenance and 3D time response remain separate unfinished work.'],
        summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    stem = ROOT/'docs/validation/isae-ua-finite-heave-20261101'
    stem.with_suffix('.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    figure.suptitle('UA-1: nonlinear finite-heave equation verification, k = 0.95')
    figure.savefig(stem.with_suffix('.svg'))
    figure.savefig(stem.with_suffix('.png'), dpi=150)
    plt.close(figure)
    print(json.dumps(dict(checks_passed=len(summaries), audited_snapshots=audited,
        finest_errors_percent=[s['records'][-1]['maximum_waveform_error_percent'] for s in summaries],
        maximum_ODE_difference=max(r['independent_ODE_max_CL_difference'] for s in summaries for r in s['records']))))


if __name__ == '__main__':
    main()
