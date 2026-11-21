"""Audit the six completed UA-1 time runs and render their refinement evidence."""
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua-time-20261101'


def main():
    summaries = []
    audited_snapshots = 0
    figure, axes = plt.subplots(2, 2, figsize=(10, 6.5), constrained_layout=True)
    for column, (tag, frequency) in enumerate((('k0475', .475), ('k095', .95))):
        records = []
        for count in (40, 80, 160):
            folder = BASE/f'{tag}-small-n{count}'
            plan = json.loads((folder/'plan.json').read_text())
            report = json.loads((folder/'report.json').read_text())
            assert report['converged'] and report['production_unchanged']
            assert report['accepted_steps'] == count and report['rejected_steps'] == 0
            assert report['structural_operator'] == 'drela-moving-airflow-v1'
            assert report['temporal_policy'] == 'drela-euler-bdf-v1'
            for name, expected in plan['code_sha256'].items():
                assert sha256((BASE/'frozen-code'/name).read_bytes()).hexdigest() == expected
                if name.startswith('openswing/'):
                    assert sha256((ROOT/name).read_bytes()).hexdigest() == expected
            with gzip.open(folder/'trajectory.json.gz','rt') as stream:
                raw = json.load(stream)
            samples = report['comparison']['samples']
            assert len(samples) == len(raw['snapshots']) == count+1
            audited_snapshots += len(samples)
            production = {name for name in plan['code_sha256'] if name.startswith('openswing/')}
            assert production == {str(p.relative_to(ROOT)) for p in (ROOT/'openswing').glob('*.py')}
            assert len(production) == 136
            speed, k, amplitude = plan['request']['condition']['speed'], plan['k'], plan['amplitude_ratio']
            assert k == frequency and amplitude == .001 and plan['aspect_ratio'] == 200000.
            tau, omega, h = 2/speed, 2*speed*k, amplitude/2
            qs = .5*1.225*speed**2*plan['aspect_ratio']
            errors, expected_lift = [], []
            gamma_errors, rate_errors, gammas, rates = [], [], [], []
            convolution_error = 0.
            for s, actual in zip(samples, raw['snapshots']):
                t = s['time']
                assert actual['time'] == t and s['CL_vertical'] == actual['force'][2]/qs
                # Independent convolution of the circulation ODE, not the
                # verifier's closed-form startup solution.
                velocity = -h*omega*math.sin(omega*t)
                acceleration = -h*omega**2*math.cos(omega*t)
                gamma = quad(lambda u: math.pi*h*omega*math.sin(omega*u)
                    *math.exp(-(t-u)/tau)/tau, 0., t, epsabs=1e-14)[0]
                rate = (-math.pi*velocity-gamma)/tau
                cl = 2*gamma/speed+2*rate/speed**2-math.pi*acceleration/(2*speed**2)
                convolution_error = max(convolution_error, abs(cl-s['expected']['CL']))
                errors.append(abs(s['CL_vertical']-cl))
                expected_lift.append(cl)
                gamma_errors.extend(abs(g-gamma) for g in s['circulation'])
                rate_errors.extend(abs(g-rate) for g in s['circulation_rate'])
                gammas.append(abs(gamma)); rates.append(abs(rate))
                assert abs(s['acceleration_error']) < 1e-14 and s['residual'] < 1e-10
                assert max(abs(x) for x in s['frame_rates']+s['frame_attitude']) < 1e-12
            error = max(errors)/max(map(abs,expected_lift))
            assert abs(error-report['comparison']['maximum_waveform_error_fraction']) < 1e-12
            assert convolution_error < 1e-14
            records.append(dict(steps=count, maximum_waveform_error_percent=100*error,
                maximum_circulation_error_fraction=max(gamma_errors)/max(gammas),
                maximum_circulation_rate_error_fraction=max(rate_errors)/max(rates),
                independent_convolution_max_CL_difference=convolution_error,
                maximum_residual=report['comparison']['maximum_residual'],
                seconds=report['seconds'], rejected_steps=0, jacobian_builds=report['jacobian_builds']))
            times = [r['time']/plan['request']['time']['duration'] for r in samples]
            axes[0,column].plot(times,[s['CL_vertical']/amplitude for s in samples],label=f'{count} steps',lw=1)
            if count == 160:
                axes[0,column].plot(times,[c/amplitude for c in expected_lift],'k--',label='Equation + startup',lw=1)
        errors = [r['maximum_waveform_error_percent'] for r in records]
        ratios = [errors[i+1]/errors[i] for i in (0,1)]
        passed = all(r < .35 for r in ratios) and errors[-1] < .1
        assert passed
        summaries.append(dict(k=frequency, amplitude_peak_to_peak_over_chord=.001,
            records=records, successive_error_ratios=ratios, refinement_gate_passed=passed,
            gate='Both halving ratios <0.35; finest max waveform error <0.1%.'))
        axes[0,column].set(title=f'UA-1 small-signal heave, k={frequency:g}',xlabel='Time / period',ylabel='Vertical CL / (A/c)')
        axes[0,column].grid(alpha=.25)
        axes[0,column].legend(fontsize=8)
        axes[1,column].loglog([40,80,160],errors,'o-',label='Measured waveform error')
        axes[1,column].loglog([40,80,160],[errors[0],errors[0]/4,errors[0]/16],'k--',label='Second-order slope')
        axes[1,column].set(xlabel='Steps per cycle',ylabel='Maximum waveform error (%)',xticks=[40,80,160],xticklabels=['40','80','160'])
        axes[1,column].grid(which='both',alpha=.25)
        axes[1,column].legend(fontsize=8)
    a=json.loads((BASE/'wing-ar10-n20.json').read_text())
    b=json.loads((BASE/'wing-ar10-n40.json').read_text())
    for r in (a,b):
        assert r['settings']['aspect_ratio'] == 10 and r['production']['numerical_passed']
        assert r['unchanged_code'] and r['native_reference_comparison'] is False
    pairs=list(zip(a['production']['response'],b['production']['response']))
    finite=dict(full_aspect_ratio=10, semi_aspect_ratio=5,
        maximum_amplitude_mesh_change_percent=max(100*abs(p['amplitude']-q['amplitude'])/q['amplitude'] for p,q in pairs if q['amplitude']),
        maximum_phase_mesh_change_deg=max(abs(p['phase_deg']-q['phase_deg']) for p,q in pairs if q['phase_deg'] is not None),
        maximum_harmonic_residual=max(r['production']['maximum_harmonic_residual'] for r in (a,b)),
        native_ASWING_comparison=False, corrected_2D_formula_is_not_native_acceptance=True)
    for kind in ('amplitude','phase_deg'):
        rows=[r for r in b['comparisons_to_plot_formula'] if r['output']==kind and r['expected']]
        finite[kind+'_difference_to_plot_formula']=dict(
            percent_range=[min(r['percentage_difference'] for r in rows),max(r['percentage_difference'] for r in rows)],
            signed_absolute_range=[min(r['difference'] for r in rows),max(r['difference'] for r in rows)])
    output=dict(date='2026-11-01', previous_goal_turn='progress', full_goal_complete=False,
        ua1_time_refinement=summaries, ua2_harmonic_reconstruction=finite,
        independently_audited_snapshots=audited_snapshots,
        production_files_unchanged=136, targeted_tests_passed=7,
        source_conventions='Primary papers confirm peak-to-peak A and semi-AR5; see isae-ua-primary-sources-20261101.json.',
        limits=['Two frequencies and a small amplitude; not the full finite-amplitude/mean/phase-average UA scope.',
                'No native UA-2 ASWING time histories or deck recovered.',
                'No browser/WASM execution or new bundle built.'])
    path=ROOT/'docs/validation/isae-ua-time-20261101.json'
    path.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    figure.savefig(path.with_suffix('.svg'))
    figure.savefig(path.with_suffix('.png'),dpi=140)
    plt.close(figure)
    print(json.dumps(dict(time_refinement_checks_passed=2, completed_time_runs=6,
        independently_audited_snapshots=audited_snapshots, production_files_unchanged=136,
        maximum_finest_waveform_error_percent=max(s['records'][-1]['maximum_waveform_error_percent'] for s in summaries))))


if __name__=='__main__':
    main()
