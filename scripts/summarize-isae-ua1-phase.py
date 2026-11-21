"""Summarize exact UA-1 phase curves and derivative sensitivity from saved jobs."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np

from isae_ua_phase import ROOT, GATES, source_binding

BASE = ROOT/'artifacts/isae/ua1-phase-20261101'
STEM = ROOT/'docs/validation/isae-ua1-phase-20261101'


def digest(p):
    return sha256(p.read_bytes()).hexdigest()


def main():
    if STEM.with_suffix('.json').exists() or (BASE/'summary-plan.json').exists():
        raise SystemExit('Preserve completed summary evidence.')
    source_binding()
    inputs = {}
    results = {}
    for panels in (4, 8):
        for label in ('base', 'half'):
            name = f'n{panels}-{label}'
            folder = BASE/name
            data = json.loads((folder/'report.json').read_text())
            receipt = json.loads((BASE/(name+'-execution.json')).read_text())
            assert receipt['exit_code'] == 0
            assert data['numerical_passed'] and data['reference_match'] and data['source_unchanged']
            assert data['plan'] == json.loads((folder/'plan.json').read_text())
            assert data['plan']['gates'] == GATES
            for file, expected in data['plan']['source_sha256'].items():
                assert digest(ROOT/file) == expected, file
                assert digest(folder/'frozen-code'/file) == expected, file
            for p in (folder/'plan.json', folder/'report.json', BASE/(name+'-execution.json')):
                inputs[str(p.relative_to(ROOT))] = digest(p)
            results[(panels, label)] = data
    tests = json.loads((BASE/'tests-execution.json').read_text())
    assert tests['exit_code'] == 0 and tests['tests_passed'] == 6
    inputs[str((BASE/'tests-execution.json').relative_to(ROOT))] = digest(BASE/'tests-execution.json')
    inputs[str(Path(__file__).resolve().relative_to(ROOT))] = digest(Path(__file__).resolve())
    plan = dict(input_sha256=inputs, gates=GATES, primary_jobs=['n4-base', 'n8-base'],
                sensitivity_jobs=['n4-half', 'n8-half'],
                counting='Six source curves per primary mesh, each with 100 lift samples. Sensitivity reruns add no counts.',
                native_ASWING_comparison=False, nonlinear_finite_incidence_validation=False)
    (BASE/'summary-plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    frozen = BASE/'frozen-code/scripts'/Path(__file__).name
    frozen.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, frozen)
    stability = []
    rows = []
    for panels in (4, 8):
        a, b = results[(panels, 'base')], results[(panels, 'half')]
        waveform = max(float(np.max(abs(np.asarray(x['CL'])-y['CL'])))/check['reference_dynamic_amplitude']
                       for x, y, check in zip(a['prediction']['responses'], b['prediction']['responses'], a['checks']))
        slope = abs(a['prediction']['mean_incidence_slope_per_rad']/b['prediction']['mean_incidence_slope_per_rad']-1)
        assert waveform < GATES['derivative_stability_fraction'] and slope < GATES['derivative_stability_fraction']
        stability.append(dict(panels=panels, maximum_waveform_change_fraction=waveform,
                              mean_slope_change_fraction=slope, passed=True))
        for check in a['checks']:
            rows.append(dict(panels=panels, **{k: v for k, v in check.items() if k != 'reference_CL'}))
    assert len(rows) == 12 and all(r['passed'] for r in rows)
    mesh_change = max(float(np.max(abs(np.asarray(a['CL'])-b['CL'])))/c['reference_dynamic_amplitude']
                      for a, b, c in zip(results[(4,'base')]['prediction']['responses'],
                                        results[(8,'base')]['prediction']['responses'], results[(8,'base')]['checks']))
    summary = dict(date='2026-11-01', plan=plan, curves_passed=12, curves_checked=12,
        phase_samples_checked=1200, phase_samples_passed=sum(r['points_passed'] for r in rows),
        checks=rows, derivative_sensitivity=stability, mesh_waveform_change_fraction=mesh_change,
        maximum_waveform_error_percent=100*max(r['maximum_waveform_error_fraction'] for r in rows),
        maximum_amplitude_error_percent=100*max(abs(r['amplitude_error_fraction']) for r in rows),
        maximum_phase_error_deg=max(abs(r['phase_error_deg']) for r in rows),
        maximum_absolute_mean_CL_error=max(abs(r['mean_error']) for r in rows),
        production_seconds={f'n{n}-{label}':d['seconds'] for (n,label),d in results.items()},
        mean_slopes={str(n):results[(n,'base')]['prediction']['mean_incidence_slope_per_rad'] for n in (4,8)},
        native_ASWING_comparison=False, nonlinear_finite_incidence_validation=False,
        limitations=['Both harmonic response and mean incidence are linearized about zero incidence.',
            'The finite A/c=.5 source curves do not test finite-amplitude nonlinear response.',
            'High aspect ratio is a 2D reconstruction, not a native model.',
            'Experimental offsets, experimental CSVs, Theodorsen curves and the hand-written static polar are excluded.',
            'Broader nonlinear periodic coverage and browser/WASM verification remain.'])

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), constrained_layout=True)
    fine = results[(8, 'base')]
    colors = {0.: '#2563eb', 5.: '#d97706', 9.: '#059669'}
    for col, k in enumerate((.47, .94)):
        for row, check in zip(fine['prediction']['responses'], fine['checks']):
            if row['k'] != k:
                continue
            color = colors[row['alpha_deg']]
            axes[0,col].plot(row['incidence_axis_deg'], check['reference_CL'], color=color, linewidth=2)
            axes[0,col].plot(row['incidence_axis_deg'], row['CL'], color=color, linestyle='--', linewidth=1)
            error = (np.asarray(row['CL'])-check['reference_CL'])*100/check['reference_dynamic_amplitude']
            axes[1,col].plot(row['phase'], error, color=color, label=f"{row['alpha_deg']:g}°")
        axes[0,col].set(title=f'Published linear phase loops, k={k:g}', xlabel='Prescribed linear incidence (deg)', ylabel='Lift coefficient CL')
        axes[1,col].set(title=f'OpenSwing minus source, k={k:g}', xlabel='Cycle phase', ylabel='Error (% of oscillatory CL amplitude)')
        axes[1,col].legend(title='Mean incidence')
        axes[0,col].legend(handles=[Line2D([0],[0],color='k',label='Published equation'),
                                   Line2D([0],[0],color='k',linestyle='--',label='Production linearization')],fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.2)
    fig.suptitle('UA-1: exact phase-curve comparison at A/c=0.5\n8 circulation unknowns; both responses use the source’s linear assumptions',fontsize=12)
    fig.savefig(STEM.with_suffix('.svg'))
    fig.savefig(STEM.with_suffix('.png'), dpi=170)
    plt.close(fig)

    table = '\n'.join(f"| {r['panels']} | {r['k']:g} | {r['alpha_deg']:g}° | {r['points_passed']}/100 | "
                      f"{100*r['maximum_waveform_error_fraction']:.6f}% | {r['mean_error']:+.8f} |"
                      for r in rows)
    text = f'''# UA-1: exact published phase-curve comparison

Updated 2026-11-01. **12/12 linear phase-curve checks pass**, covering the six
published curves on two meshes, with **1,200/1,200 lift samples** within their
declared tolerance. The largest waveform error is
**{summary['maximum_waveform_error_percent']:.6f}% of oscillatory lift amplitude**.
This closes the numerical comparison left open by the
[phase-source review](isae-ua1-phase-sources-20261101.md).

These are equation comparisons. The MATLAB source constructs its 0°, 5° and
9° curves by linear superposition about zero incidence. Accordingly, this
comparison verifies the production linearized oscillatory response **and the
production steady-incidence derivative**. It does not validate nonlinear
finite-amplitude motion at 5° or 9°, nor recover native ASWING trajectories.

| Circulation unknowns | k | Mean label | Passing samples | Max waveform error | Signed mean CL error |
|---:|---:|---:|---:|---:|---:|
{table}

The source uses exactly k=0.47/0.94, A/c=0.5 (peak-to-peak), and 100 equally
spaced phase samples including both endpoints. These frequencies differ from
the earlier k=0.475/0.95 time studies. The incidence coordinate is the source's
prescribed linear coordinate; it is not counted as an independent output test.
Mean errors are compared in absolute CL units; relative waveform errors use
the oscillatory amplitude so a larger mean offset cannot conceal dynamic error.

![Phase loops and lift errors](isae-ua1-phase-20261101.svg)

## Prediction and reference remain independent

The predictor centrally differentiates the actual production aerodynamic
residual and load routine with respect to circulation, circulation rate,
heave velocity, heave acceleration and incidence in radians. One derivative
matrix per mesh supplies one static solve and two complex harmonic solves.
The mean slope is obtained by solving `K Gamma_alpha = -R_alpha` and applying
the production load derivatives. No 2π lift slope is inserted into prediction.
The computed slopes are **{summary['mean_slopes']['4']:.10f}** and
**{summary['mean_slopes']['8']:.10f} per radian**, compared with 2π in the source.

For the oscillatory component, displacement amplitude is 0.25 chords and
`omega=2Vk/c`; its velocity and acceleration phasors are `i omega h` and
`-omega² h`. Circulation-rate lift and apparent mass participate. The comparison
side separately transcribes the pinned MATLAB bracket and linear mean offset.
The reference formula is never used to assemble or solve the production system.

The rigid rectangular AR200000 reconstruction uses V=30, unit chord, Mach zero,
stall disabled, and 4/8 circulation unknowns. This approaches the section limit
while retaining finite-tip effects. Mesh change is
**{100*mesh_change:.6f}% of oscillatory amplitude**; two meshes do not establish
an infinite-span or spatial-continuum convergence limit.

Acceptance was declared before the runs: every lift sample must differ by at
most 0.01% of oscillatory amplitude; harmonic amplitude by at most 0.01%; phase
by at most 0.01°; and mean CL by `max(1e-9, 1e-4*abs(reference mean))`.
The provisional SA 3% policy does not apply. Actual maximum amplitude and phase
errors are **{summary['maximum_amplitude_error_percent']:.6f}%** and
**{summary['maximum_phase_error_deg']:.6f}°**.

Both meshes are repeated with half-sized differentiation steps. The largest
normalized waveform change is
**{max(r['maximum_waveform_change_fraction'] for r in stability):.3e}**, below the
predeclared 1e-7 derivative-sensitivity gate. These repeats add no curve or
sample acceptance counts. Six focused tests pass, including deliberate omission
of the mean-incidence response or apparent mass, a wrong phase origin, and a
doubled physical amplitude. Those incorrect variants fail the appropriate curves.

Four small serial jobs take **{min(summary['production_seconds'].values()):.2f}–{max(summary['production_seconds'].values()):.2f}
seconds** each after source pinning, with one BLAS thread and a 45-second cap.
All exit successfully. All 136 production Python files and the earlier UA-2 and
steady results remain unchanged. No browser build or background numerical batch
is needed for this comparison.

## Remaining scope

This supplements the existing 148/148 harmonic equation checks and four
passing nonlinear periodic checks at zero incidence and k=0.95. The latter
remain separate from this linear source comparison. Nonlinear periodic motion
at nonzero mean incidence, other frequencies, and browser/WASM behavior still
require validation. The next useful step is an independently derived section
reference at nonzero incidence, checked against production instantaneous loads
before running bounded time histories.

Experimental CSVs, empirical mean-lift offsets, Theodorsen curves and the
hand-written static polar are separate source curves and are excluded from
these ASWING-equation counts. The UA-2 native-reference provenance issue remains;
none of its 222 blocked comparison slots is converted into a pass.

Evidence: [machine summary](isae-ua1-phase-20261101.json),
[plans, derivative matrices, full curves, receipts and frozen sources](../../artifacts/isae/ua1-phase-20261101),
[production-derivative comparison](../../scripts/isae_ua_phase.py),
[bounded runner](../../scripts/verify-isae-ua1-phase.py),
[focused tests](../../tests/test_isae_ua_phase.py), and
[pinned source manifest](isae-ua1-phase-sources-20261101.json).
'''
    assert all(digest(ROOT/n) == h for n,h in inputs.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    STEM.with_suffix('.md').write_text(text)
    print(json.dumps({k: summary[k] for k in ('curves_passed','phase_samples_passed',
        'maximum_waveform_error_percent','maximum_phase_error_deg','maximum_absolute_mean_CL_error',
        'derivative_sensitivity','mesh_waveform_change_fraction')}))


if __name__ == '__main__':
    main()
