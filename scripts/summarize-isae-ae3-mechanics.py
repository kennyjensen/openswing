#!/usr/bin/env python3
"""Reduce saved AE-3 unit-load evidence; this script performs no physical solves."""
from pathlib import Path
import argparse
import hashlib
import json


def read(path):
    return json.loads(path.read_text())


def pin(path):
    return dict(bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    work, dest = args.work.resolve(), args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    contract = read(work/'native/contract.json')
    for name, expected in contract['pins'].items():
        assert pin(work/'native'/name) == expected, name
    table = read(work/'primary/table-ii-contract.json')
    reduction = read(work/'comparison-review/report.json')
    independent = read(work/'reference/postrun-review.json')
    centered = read(work/'reference/centered-extension-01/report.json')
    assert centered['status'] == 'PASS_CENTERED_LINEAR_LIMIT'
    assert centered['original_gate_values_unchanged']
    wasm = read(work/'wasm/summary.json')
    primary = read(work/'primary/report.json')
    native = {}
    for folder in ('native', 'native-refinement'):
        assert read(work/folder/'batch.json')['status'] == 'pass'
        for case in sorted((work/folder/'results').iterdir()):
            if not case.is_dir():
                continue
            status = read(case/'status.json')
            assert status['status'] == 'pass'
            native[case.name] = status
    assert len(native) == 12
    bend = read(work/'native-refinement/results/force256/observables.json')
    twist = read(work/'native/results/torque64/observables.json')
    reference_bend = read(work/'reference/results-01/bending-level2.json')
    reference_twist = read(work/'reference/results-01/torsion-level2.json')
    rows = []
    for index, (measured, b, t) in enumerate(zip(table['rows'], bend, twist), 1):
        row = dict(eta=measured['eta'], bending_measured_m=measured['bending_m'],
                   twist_measured_deg=measured['twist_deg'],
                   bending_native_m=b['points']['EA']['downward_deflection_m'],
                   twist_native_deg=t['material_euler_twist_deg'],
                   bending_reference_m=-reference_bend['elastic_axis_displacement'][index][2])
        # Pure torsion leaves the span direction unchanged, making its jig
        # projected angle equal to the common Euler angle (independently checked).
        from math import degrees
        row['twist_reference_deg'] = degrees(reference_twist['twist_projected_rad'][index])
        for quantity, unit in [('bending', 'm'), ('twist', 'deg')]:
            observed = row[f'{quantity}_measured_{unit}']
            predicted = row[f'{quantity}_native_{unit}']
            row[f'{quantity}_difference_{unit}'] = None if observed is None else predicted-observed
            row[f'{quantity}_difference_percent'] = None if observed is None else 100*(predicted/observed-1)
        rows.append(row)
    evidence_files = ['native/contract.json', 'native-refinement/contract.json',
                      'primary/table-ii-contract.json', 'primary/report.json',
                      'primary/figure18-observations.csv', 'comparison-review/report.json',
                      'reference/plan.json', 'reference/results-01/report.json',
                      'reference/postrun-review.json', 'reference/centered-extension-01/report.json',
                      'wasm/summary.json', 'setup-review/report.json']
    report = dict(
        format='openswing-isae-ae3-mechanics', version=1,
        status='CONDITIONAL_MECHANICAL_COMPARISON_WITH_EXPERIMENTAL_DISCREPANCIES',
        original_ASWING_executable_available=False,
        evidence_archive='isae-ae3-mechanics-20261024-evidence.zip',
        production_changes=0, frozen_kernel_modules=105,
        coverage=dict(partial=17, pending=24, fully_validated=0, AE3='pending'),
        primary_source='https://ntrs.nasa.gov/citations/19930083276',
        contract=contract, native_cases=native, measurement_rows=rows,
        refinement=reduction['refinement'], sign_reversal=reduction['sign_reversal'],
        native_continuous_comparisons=independent['native_continuous_comparisons'],
        independent_original_run_status=independent['original_run_status'],
        independent_original_failed_checks=independent['failed_recomputed_original_checks'],
        independent_centered_extension=centered,
        wasm=wasm,
        digitization=dict(counts=primary['counts'], calibration=primary['calibration'],
                          observations=primary['observations']),
        evidence_pins={name: pin(work/name) for name in evidence_files},
        limitations=[
            'Ideal clamp, other half unloaded, declared body-fixed loads and t=eta*0.6096 station mapping are conditional fixture reconstructions.',
            'Experimental bending marker and twist instrument are not specified; LE, elastic-axis and midchord outputs are retained separately.',
            'Primary Table II has no measurement uncertainty or acceptance threshold. Decimal precision is not an uncertainty bound.',
            'Agreement with the independent continuous literal model checks mechanics, not experimental setup or stiffness provenance.',
            'Original positive-only small-load full-vector checks failed and remain failed. A separate centered derivative study tests the linear limit.',
            'WASM checks replay force64 and torque64 through the public bridge. They do not cover the 256-panel refinement or browser UI.',
            'Digitization bounds describe scan/marker reading, not laboratory measurement uncertainty. Original archive CSV is unchanged.',
        ],
        remaining=[
            'Compare locked-control predictions across all five variants using primary pressure readings, with explicit incidence, finite-amplitude, sign and normalization assumptions.',
            'Resolve specimen/fixture discrepancy and control conventions before claiming experimental acceptance.',
            'Complete driven zero-average-moment roll and reversal comparisons; distinguish measured points from extrapolations.',
        ],
        release_scope='Workspace research evidence; existing runtime bundles and hosted deployment are unchanged.')
    (dest/'isae-ae3-mechanics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    plot(rows, dest)
    maximum_residual = max(c['verification']['fresh_normalized_residual'] for c in native.values())
    lines = [
        '# AE-3 unit-load mechanics and primary pressure readings', '',
        'The literal wing agrees with an independent continuous beam calculation, but the conditional comparison with the original measured deflections has unresolved discrepancies. **AE-3 remains pending.** No stiffness, source measurements or production kernel code were changed.', '',
        'This study uses Table II and Figures 11/18 of [NACA TN 2563](https://ntrs.nasa.gov/citations/19930083276). It follows the [source audit and numerical pilot](isae-ae3-progress.json). The [machine-readable report](isae-ae3-mechanics.json) retains conventions, all rows, numerical failures and input hashes; the [raw evidence archive](isae-ae3-mechanics-20261024-evidence.zip) includes scripts, frozen source and complete saved states.', '',
        '## Unit-load comparison', '',
        'The two separate tests apply a 1 lbf force at 96.6% semispan on the elastic axis, or a 1 lbf-in tip torque. The reconstruction uses an ideal root clamp, no air, an unloaded opposite half, a fixed body-force direction and a tip couple along the undeformed material span. The displacement marker, exact clamp and torque apparatus were not recovered from the report. The table below uses elastic-axis displacement and material Euler twist; alternative leading-edge and midchord readings remain in the raw evidence.', '',
        '| Semispan fraction | Measured bend (in) | Computed bend (in) | Difference | Measured twist (deg) | Computed twist (deg) | Difference |',
        '|---:|---:|---:|---:|---:|---:|---:|',
    ]
    def fmt(value, pattern):
        return '—' if value is None else format(value, pattern)
    for r in rows:
        lines.append('| '+ ' | '.join([
            fmt(r['eta'], '.3f'), fmt(None if r['bending_measured_m'] is None else r['bending_measured_m']/.0254, '.3f'),
            fmt(r['bending_native_m']/.0254, '.5f'), fmt(r['bending_difference_percent'], '+.2f')+'%' if r['bending_difference_percent'] is not None else '—',
            fmt(r['twist_measured_deg'], '.3f'), fmt(r['twist_native_deg'], '.5f'),
            fmt(r['twist_difference_percent'], '+.2f')+'%' if r['twist_difference_percent'] is not None else '—'])+' |')
    lines += ['', 'Missing measurements remain missing. Force predictions use 256 requested intervals and torque predictions use 64. No experimental error bars or pass threshold were invented.', '',
              '![Measured and computed unit-load responses](isae-ae3-mechanics.svg)', '',
              '## Numerical evidence', '',
              f'All 12 native states pass the original equation and balance gates; the maximum freshly evaluated normalized residual is {maximum_residual:.4g}. Actual node counts increase from 24 to 264. Bending refinement initially fails at 16→32 and 32→64; 64→128 and 128→256 pass the unchanged 1e-5 m gate. The final adjacent difference is 2.421e-6 m. Torque refinement initially fails at 16→32; 32→64 passes the original 0.005° gate, with a maximum change of 0.0019374°.', '',
              'The independently implemented continuous beam agrees with the finest native bending result within 8.28e-7 m at the sampled elastic-axis points. The maximum common twist difference for the torque case is 0.000889°. Its ten original finite solutions satisfy shooting and rotation checks. The original positive-only small-load checks fail because their full-vector comparison retains quadratic in-plane displacement; those failures are preserved. Six additional opposite-load solutions support centered derivatives at two step sizes. All 16 full-component derivative checks pass the unchanged 2e-8 m displacement and 2e-8 rad rotation gates. Maximum errors are 2.17e-10 m and 6.20e-10 rad; maximum adjacent step changes are 1.37e-10 m and 4.24e-10 rad.', '',
              'Both force64 and torque64 also pass actual Pyodide replay through the public structural API. Complete physical outputs and states agree within the declared componentwise tolerances, with fresh normalized full residuals below 6.60e-14. This is WebAssembly API evidence, not a browser UI check or a new experimental result.', '',
              '## Pressure readings for the next aerodynamic comparison', '',
              'Figure 18 was independently re-read using its printed axis ticks. All 18 archived response values fall inside the declared pixel bounds; none of the 18 archived pressure values do. The first 20% aileron point is 9.9255 psf with a digitization interval of 9.3497–10.5014 psf, whereas the archived CSV gives 11.3559 psf. Nominal grid pressures and measured marker coordinates are stored separately. The original CSV is unchanged.', '',
              'Exact experimental incidence, finite aileron amplitudes and positive-deflection convention remain unresolved. The plotted finite ratio Cl/δ cannot automatically be treated as an infinitesimal control derivative. The next comparison must retain those assumptions and the mechanical discrepancy; it must also distinguish driven zero-moment rolling from a free-roll transient.', '',
              'The complete goal and the 41-family suite remain incomplete: **17 partial / 24 pending / 0 fully validated**. These workspace results do not certify a new hosted release.', '']
    (dest/'isae-ae3-mechanics.md').write_text('\n'.join(lines))
    print(json.dumps(dict(status='REDUCED_SAVED_EVIDENCE', cases=len(native), measurements=10,
                         report=pin(dest/'isae-ae3-mechanics.json'))))


def plot(rows, dest):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with plt.rc_context({'font.size': 10, 'svg.hashsalt': 'isae-ae3-mechanics'}):
        fig, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True,
                                 gridspec_kw={'height_ratios': [2.3, 1]})
        for column, (quantity, unit, label, scale) in enumerate([
                ('bending', 'm', 'Downward elastic-axis displacement (in)', 1/.0254),
                ('twist', 'deg', 'Material twist (deg)', 1)]):
            ax, error = axes[:, column]
            x = [r['eta'] for r in rows]
            measured = [r for r in rows if r[f'{quantity}_measured_{unit}'] is not None]
            ax.plot(x, [r[f'{quantity}_native_{unit}']*scale for r in rows],
                    'o-', color='#2563eb', label='OpenSwing, refined')
            ax.plot(x, [r[f'{quantity}_reference_{unit}']*scale for r in rows],
                    'x--', color='#d97706', label='Independent continuous beam')
            ax.scatter([r['eta'] for r in measured],
                       [r[f'{quantity}_measured_{unit}']*scale for r in measured],
                       marker='s', facecolors='none', edgecolors='black', s=55,
                       label='NACA Table II')
            ax.set_ylabel(label)
            ax.set_title('1 lbf force at η = 0.966' if column == 0 else '1 lbf-in tip torque')
            ax.legend(fontsize=8)
            error.axhline(0, color='black', lw=.7)
            error.plot([r['eta'] for r in measured],
                       [r[f'{quantity}_difference_percent'] for r in measured],
                       'o-', color='#2563eb')
            error.set_ylabel('Difference (%)')
            error.set_xlabel('Semispan fraction η')
            for panel in (ax, error):
                panel.grid(alpha=.2)
                panel.set_xlim(.2, 1.03)
        fig.suptitle('Conditional literal-wing comparison; fixture and measurement-marker limits remain')
        fig.savefig(dest/'isae-ae3-mechanics.svg', metadata={'Date': None})
        fig.savefig(dest/'isae-ae3-mechanics.png', dpi=160)
        plt.close(fig)


if __name__ == '__main__':
    main()
