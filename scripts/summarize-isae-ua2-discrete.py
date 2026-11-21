"""Publish the saved UA-2 discrete-equation audit without rerunning production."""
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua2-discrete-audit-20261101'
PERIODIC = ROOT / 'artifacts/isae/ua2-periodic-20261101'
STEM = ROOT / 'docs/validation/isae-ua2-discrete-audit-20261101'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = BASE / 'report-plan.json'
    if plan_path.exists() or STEM.with_suffix('.json').exists():
        raise SystemExit('Preserve the existing report; choose a new output scope.')
    cases = {}
    paths = [Path(__file__).resolve(), ROOT / 'scripts/extract-isae-ua2-periodic-state.py']
    for panels in (20, 40):
        for steps in (80, 160):
            path = BASE / f'analysis-n{panels}-t{steps}.json'
            state_path = BASE / f'state-n{panels}-t{steps}.json'
            data = json.loads(path.read_text())
            state = json.loads(state_path.read_text())
            assert data['discrete_identity_passed']
            assert data['plan']['panels'] == panels and data['plan']['nominal_steps'] == steps
            assert state['unique_snapshots'] == 8 * steps + 41
            assert state['all_checkpoint_joins_exact']
            assert digest(ROOT / 'scripts/extract-isae-ua2-periodic-state.py') == state['plan']['extractor_sha256']
            for name, expected in data['plan']['source_sha256'].items():
                assert digest(ROOT / name) == expected, name
                assert digest(BASE / 'frozen-code' / name) == expected, name
            for name, expected in state['input_sha256'].items():
                assert digest(ROOT / name) == expected, name
            assert max(data['identity_error_fractions'].values()) < data['plan']['normalized_discrete_identity_gate']
            assert data['maximum_normalized_circulation_equation_residual'] < data['plan']['normalized_circulation_equation_gate']
            cases[(panels, steps)] = data
            paths.extend([path, state_path])
    batch_path = PERIODIC / 'accepted-evidence/batch-plan.json'
    batch = json.loads(batch_path.read_text())
    for name, expected in batch['source_sha256'].items():
        assert digest(ROOT / name) == expected, name
    pins = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    plan = dict(source_sha256=pins, batch_plan_sha256=digest(batch_path),
                registered_rows_before=[r for r in (ROOT / 'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')],
                inputs='Four complete saved extractions and discrete analyses; no new production trajectories.',
                production_changed=False, native_ASWING_comparison=False,
                ISAE_acceptance_counts_changed=False)
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    for p in paths[:2]:
        frozen = BASE / 'frozen-code' / p.relative_to(ROOT)
        frozen.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, frozen)

    maximum_identity = max(max(d['identity_error_fractions'].values()) for d in cases.values())
    maximum_residual = max(d['maximum_normalized_circulation_equation_residual'] for d in cases.values())
    compact = []
    for (panels, steps), data in cases.items():
        compact.append(dict(panels=panels, nominal_steps=steps,
            analysis=str((BASE / f'analysis-n{panels}-t{steps}.json').relative_to(ROOT)),
            **{key: value for key, value in data.items() if key not in ('plan', 'waveforms')}))
    summary = dict(date='2026-11-01', discrete_identity_checks_passed=4,
        audited_unique_snapshots=4004, maximum_normalized_identity_error=maximum_identity,
        maximum_normalized_circulation_equation_residual=maximum_residual,
        source_sha256=pins, cases=compact, production_changed=False,
        ISAE_acceptance_counts_changed=False, native_ASWING_comparison=False,
        native_comparison_slots_blocked=222,
        limitations=['Zero-incidence rigid AR10 wing, A/c=.5, k=.95, Mach=0, stall off.',
            'Three-trajectory decomposition is path dependent; maximum component norms do not sum.',
            'Circulation values, position and higher harmonics have no additional acceptance gate.',
            'Ideal-motion substitution is a diagnostic, not a production change.',
            'Broader periodic cases, native provenance and browser/WASM validation remain.'])

    reference = json.loads((PERIODIC / 'reference-n40.json').read_text())
    periodic_rows = reference['reference']['DOP853']['periodic']['rows']
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8), constrained_layout=True)
    for ax, steps in zip(axes[0], (80, 160)):
        data = cases[(40, steps)]
        waves = data['waveforms']
        t = np.asarray(waves['times'])[-steps-1:]
        a = np.asarray(waves['discrete_CL'])[-steps-1:]
        b = np.asarray(waves['ideal_motion_discrete_CL'])[-steps-1:]
        c = np.asarray(waves['continuous_cold_CL'])[-steps-1:]
        p = np.asarray([r['CL'] for r in periodic_rows[::160 // steps]])
        scale = 100 / np.max(abs(p))
        phase = (t - t[0]) / (2 * math.pi / 19)
        for values, label, color, style in ((a-p, 'Total', '#172554', '-'),
                (a-b, 'Motion integration', '#c2410c', '--'),
                (b-c, 'Circulation integration', '#047857', '-.'),
                (c-p, 'Startup transient', '#7e22ce', ':')):
            ax.plot(phase, scale * values, label=label, color=color, linestyle=style)
        ax.set(title=f'Final-cycle lift error: {steps} steps/cycle',
               xlabel='Cycle phase', ylabel='Error (% of reference peak CL)')
        ax.axhline(0, color='.6', linewidth=.6)
        ax.grid(alpha=.22)
        ax.legend(fontsize=8)
    for steps, color in ((80, '#c2410c'), (160, '#1d4ed8')):
        data = cases[(40, steps)]
        axes[1, 0].plot(range(1, 9), np.asarray(data['motion']['cycle_end_position_errors']) * 100 / .25,
                        marker='o', color=color, label=f'{steps} steps/cycle')
        wave = data['waveforms']
        t = np.asarray(wave['times'])[-steps-1:]
        axes[1, 1].plot((t-t[0]) / (2*math.pi/19), np.asarray(wave['velocity_error'])[-steps-1:] * 100 / 4.75,
                        color=color, label=f'{steps} steps/cycle')
    axes[1, 0].set(title='Position drift accumulates across cycles', xlabel='Completed cycle',
                   ylabel='Position error (% of heave amplitude)', xticks=range(1, 9))
    axes[1, 1].set(title='Final-cycle heave velocity error', xlabel='Cycle phase',
                   ylabel='Velocity error (% of peak heave velocity)')
    for ax in axes[1]:
        ax.grid(alpha=.22)
        ax.legend(fontsize=8)
    fig.suptitle('UA-2: independent discrete equations reproduce the production error\n'
                 '40 strips; A/c = 0.5, k = 0.95; signed components add pointwise', fontsize=12)
    fig.savefig(STEM.with_suffix('.svg'))
    fig.savefig(STEM.with_suffix('.png'), dpi=170)
    plt.close(fig)

    rows = []
    for (panels, steps), d in cases.items():
        cl = d['final_cycle_error_decomposition']['CL']
        parts = cl['component_error_percent']
        rows.append(f"| {panels} | {steps} | {max(d['identity_error_fractions'].values()):.3e} | "
                    f"{cl['total_error_percent']:.5f}% | {parts['motion']:.5f}% | "
                    f"{parts['circulation_integration']:.5f}% |")
    circulation_rows = []
    for (panels, steps), d in cases.items():
        c = d['final_cycle_error_decomposition']['circulation']
        p = c['component_error_percent']
        circulation_rows.append(f"| {panels} | {steps} | {c['total_error_percent']:.5f}% | "
                                f"{p['motion']:.5f}% | {p['circulation_integration']:.5f}% |")
    motion_rows = []
    for steps in (80, 160):
        m = cases[(40, steps)]['motion']
        motion_rows.append(f"| {steps} | {m['maximum_velocity_error']:.8f} | "
                           f"{100*m['maximum_velocity_error']/4.75:.5f}% | "
                           f"{m['maximum_position_error']:.8f} | {100*m['maximum_position_error']/.25:.5f}% | "
                           f"{m['final_cycle_position_change']:.8f} |")
    report = f'''# UA-2: discrete-equation and error attribution audit

Updated 2026-11-01. **All four saved trajectories agree with an independent
implementation of Drela's documented time discretization.** The largest
normalized state/load difference is **{maximum_identity:.3e}**, and the largest
reconstructed normalized circulation residual is **{maximum_residual:.3e}**.
The remaining periodic lift error is dominated by time discretization of the
prescribed motion. This checks the equations on this particular straight-wing
case; it does not establish native ASWING parity.

The audit reuses every one of the **4,004 snapshots** in the
[eight-cycle pilot](isae-ua2-periodic-20261101.md). It adds no production solves
or ISAE pass counts. The existing **16/16 first-cycle and 2/2 periodic checks**,
**8/8 first-cycle and 1/1 periodic mesh checks**, and **222 blocked native
comparison slots** remain unchanged. All 136 production Python files are unchanged.

| Strips | Nominal steps/cycle | Largest normalized identity difference | Periodic lift error | Motion component | Circulation-integration component |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Lift errors use the maximum periodic reference lift as denominator. Components
are separate maximum norms: **they add pointwise, not as table percentages**.
The residual cold-start transient contributes at most 0.00001035% of peak lift
in the final cycle. Doubling the time resolution reduces the total lift error
from about 0.329% to 0.0680%; the two strip counts give essentially the same
attribution.

![Lift error components, position drift and velocity error](isae-ua2-discrete-audit-20261101.svg)

## What is independently implemented

The [unsteady technical description](../../.reference/asw_uns_theory.txt),
Section 12.1–12.2, Eqs. 123–129, defines backward derivatives and a Newton solve
with matrix `r_x + k0 r_xdot`. The independent helper derives derivative weights
from polynomial moment conditions on the actual nonuniform sample times,
without importing production coefficient or integrator code. The first step
is backward Euler; all subsequent steps use the second-order formula.

For this nonrotating, acceleration-driven frame, the motion equations are
`BDF(w)=a(t)` and `BDF(z)=w`. The nonlinear circulation equation is
`BDF(Gamma)=(pi/2) U_perp [-w-e_x C Gamma]`, with
`U_perp=sqrt(V^2+w^2+(H Gamma)^2)` and `e_x=V/sqrt(V^2+w^2)`.
The independent [straight-wing vortex integrals and load equations](isae-straight-wing-heave-reference.md)
retain bound-induced speed, circulation-rate lift and apparent mass.
An analytic coupled Newton matrix differentiates this residual, and each step
starts from the previous circulation. At most three Newton updates suffice.

Checks compare velocity, position, circulation, per-strip circulation rate,
lift, the rate stored in each snapshot, and a separate load replay at each
production state. Predeclared normalized identity and equation-residual gates
are 1e-7 and 2e-10. All four pass. Six focused tests also pass: three polynomial
derivative cases, constant-velocity kinematics, a finite-amplitude complex-step
Jacobian check, and an independent linear-system small-signal limit.

## Separating the errors

Three independently computed histories define a controlled diagnostic:

1. **A:** backward-difference motion and nonlinear circulation on the saved grid.
2. **B:** ideal sinusoidal velocity with the same discrete circulation equations.
3. **C:** the previously verified continuous cold-start ODE solution.

The components are A−B (motion), B−C (circulation time integration), and
C−periodic (remaining startup transient). Their signed sum reconstructs the
total waveform error to roundoff. Because the equations are nonlinear, this
is an attribution along the stated sequence, not a unique additive physical
partition. B is an input substitution used only to diagnose the discrepancy;
the production forcing and state evolution are unchanged.

For final-cycle circulation, errors use **each strip's own periodic peak**:

| Strips | Nominal steps/cycle | Circulation error | Motion component | Circulation-integration component |
|---:|---:|---:|---:|---:|
{chr(10).join(circulation_rows)}

The fine error is about 0.1478%, larger than the lift error. The earlier pilot
used the largest circulation peak over all strips and reported 0.1477%; the
small difference here is the explicitly changed diagnostic normalization.
Neither report imposes an additional 0.1% gate on circulation values.
The prior 0.245% third-harmonic amplitude error is retained; this audit does
not separately decompose that harmonic.

## Motion drift and mean lift

The motion is identical on both meshes because the frame acceleration is
prescribed. Here `c=1`, `V=10`, `z_ideal=0.25 cos(19t)` and peak heave velocity
is 4.75. A/c=0.5 denotes peak-to-peak displacement. Motion errors below cover
all eight cycles; final-cycle position change is signed.

| Steps/cycle | Max velocity error | % peak velocity | Max position error, chords | % heave amplitude | Position change in last cycle, chords |
|---:|---:|---:|---:|---:|---:|
{chr(10).join(motion_rows)}

The fine final-cycle mean velocity error is −0.000516524; the coarse value is
−0.004002594. The associated mean-lift error falls from about **0.112% to
0.0145% of peak lift**. The motion component accounts for essentially all of
that mean bias: the fine circulation-integration contribution is less than
0.000000006% of peak and the remaining startup transient is about 0.0000049%.

Position drift is an accumulated motion-integration error, reproduced by the
independent discrete kinematics to roundoff. Absolute vertical translation
does not affect the aerodynamic load in this uniform, unbounded-flow case;
the velocity error changes the lift. A small nonlinear residual therefore
does not guarantee small accumulated trajectory error. These diagnostics
support refining the time grid and checking trajectory accuracy, not changing
the aerodynamic equations or inserting a fitted correction.

## Evidence and remaining scope

This is the rigid AR10, zero-incidence, zero-Mach, stall-disabled A/c=0.5,
k=0.95 pilot. Other periodic amplitudes/frequencies, nonzero mean incidence,
arbitrary-model automatic error control and browser/WASM validation remain.
The existing fine lift/rate gates pass, but position and higher-harmonic
accuracy still need explicit gates if those outputs become acceptance targets.
Native UA-2 geometry/run provenance remains unresolved.

All extraction and analysis work is serial, one BLAS thread, with a 45-second
cap per numerical job. The independent discrete computations take 0.32–0.85
seconds each after imports and input verification. Full saved-state extraction
takes 2.75–11.21 seconds per trajectory; these are not production solve timings.
The terminal output for the last three analyses was truncated. Their complete
outputs, source hashes and passing gates were verified, and process inspection
confirmed no analysis remained running; their original exit codes are recorded
as unavailable rather than inferred.

Evidence: [machine summary](isae-ua2-discrete-audit-20261101.json),
[saved analyses, pinned inputs and frozen code](../../artifacts/isae/ua2-discrete-audit-20261101),
[independent discrete equations](../../scripts/isae_ua_discrete_reference.py),
[analyzer](../../scripts/analyze-isae-ua2-discrete.py),
[focused tests](../../tests/test_isae_ua_discrete_reference.py), and
[saved-state extractor](../../scripts/extract-isae-ua2-periodic-state.py).
'''
    assert all(digest(ROOT / name) == expected for name, expected in pins.items())
    STEM.with_suffix('.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    STEM.with_suffix('.md').write_text(report)
    print(json.dumps(dict(discrete_checks=4, snapshots=4004, maximum_identity=maximum_identity,
        maximum_equation_residual=maximum_residual, production_changed=False,
        native_comparisons_added=0, report=str(STEM.with_suffix('.md').relative_to(ROOT)))))


if __name__ == '__main__':
    main()
