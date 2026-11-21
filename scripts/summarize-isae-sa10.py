"""Plot every SA-10 polar branch and report discrepancies without tuning inputs."""
from pathlib import Path
from collections import Counter
import json, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
from isae_sa10_reference import sha
D = ROOT / 'docs/validation'
COLORS = ['#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f', '#2f7bff', '#9b5de5', '#f472b6', '#22d3ee']
SURFACE_COLORS = ['#ff0000', '#ff8c00', '#ffff00', '#00ff00', '#00ffff', '#0000ff', '#8a2be2', '#ff00ff']


def polar(case, panels=100, frozen=False, pg='zero'):
    rows = sorted([r for r in case['runs'] if r['specification']['panels'] == panels
        and r['specification']['frozen'] == frozen and r['specification']['pg'] == pg
        and r['specification']['alpha'] in range(26)], key=lambda r: r['specification']['alpha'])
    return {k: [r['specification']['alpha'] if k == 'alpha' else
                (r['result'][k] if r['status'] == 'computed' else np.nan) for r in rows]
            for k in ['alpha', 'CL', 'CD']}


def main():
    study = json.loads((D / 'isae-sa10.json').read_text()); source = json.loads((D / 'isae-sa10-sources.json').read_text())
    checks = json.loads((D / 'isae-sa10-checks.json').read_text()); drag = json.loads((D / 'isae-sa10-drag.json').read_text())
    cases = {c['name']: c for c in study['cases']}
    rows = [r for c in cases.values() for r in c['runs']]; rejected = [r for r in rows if r['status'] == 'rejected']
    low_angle = []
    for name, reference in source['experimental_lift'].items():
        case = cases[name]
        pairs = []
        requested = [r for r in reference['values'] if 0 <= r['xy'][0] <= 8]
        for measurement in requested:
            alpha, measured = measurement['xy']
            run = next(r for r in case['runs'] if r['specification'] == dict(
                case=case['case_id'], panels=100, frozen=False, pg='zero', alpha=alpha))
            if run['status'] == 'computed': pairs.append([alpha, measured, run['result']['CL']])
        values = np.array(pairs)
        measured_slope = float(np.polyfit(values[:, 0], values[:, 1], 1)[0])
        computed_slope = float(np.polyfit(values[:, 0], values[:, 2], 1)[0])
        low_angle.append(dict(case=case['case_id'], alpha_range=[0, 8], requested=len(requested), computed=len(pairs),
            measured_slope_per_degree=measured_slope, computed_slope_per_degree=computed_slope,
            relative_slope_error=computed_slope/measured_slope-1,
            CL_rmse=float(np.sqrt(np.mean((values[:, 2]-values[:, 1])**2)))))
    counts = []
    for case in cases.values():
        for frozen in [False, True]:
            for pg in ['zero', 'speed']:
                selected = [r for r in case['runs'] if r['specification']['frozen'] == frozen and r['specification']['pg'] == pg]
                errors = Counter('local_normal_Mach_limit' if 'Mach' in r['error'] else 'circulation_or_other_failure'
                                 for r in selected if r['status'] == 'rejected')
                counts.append(dict(case=case['case_id'], frozen=frozen, pg=pg, requested=len(selected),
                    computed=sum(r['status'] == 'computed' for r in selected), rejection_types=dict(errors)))
    selected = lambda seq: [r for r in seq if r.get('panels') == 100 and r['pg'] == 'zero' and not r['frozen']]
    output = dict(status='PARTIAL_VALIDATION_DISCREPANCIES_AND_SETUP_LIMITS_REMAIN',
        total=len(rows), computed=len(rows)-len(rejected), rejected=len(rejected), rejection_groups=counts,
        current_zero_pg_lift=selected(study['experimental_lift_comparisons']),
        current_zero_pg_low_angle=low_angle,
        current_zero_pg_archived=selected(study['archived_comparisons']),
        fixed_lift=drag['summary'], maximum_residual=checks['maximum_residual'],
        finer_junction_diagnostic=checks['finer_junction_diagnostic'],
        maximum_wrench_error=checks['maximum_wrench_error'], maximum_matched_lift_error=checks['maximum_fixed_lift_error'],
        script_sha256=sha(Path(__file__)), input_sha256={name: sha(D / name) for name in
            ['isae-sa10.json', 'isae-sa10-sources.json', 'isae-sa10-checks.json', 'isae-sa10-drag.json']})
    (D / 'isae-sa10-comparison.json').write_text(json.dumps(output, indent=2) + '\n')
    plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), layout='constrained')
    for ax, name in zip(axes, ['wing_alone', 'wing_extension', 'Louvered']):
        case = cases[name]
        for frozen, pg, color, style, label in [(False, 'zero', COLORS[0], '-', 'Current, zero PG'),
                (False, 'speed', COLORS[1], '--', 'Current, speed PG'), (True, 'zero', COLORS[4], ':', 'Frozen, zero PG')]:
            p = polar(case, frozen=frozen, pg=pg); ax.plot(p['alpha'], p['CL'], color=color, ls=style, label=label)
        raw = next(c for c in source['models'] if c['name'] == name)['archived']['rows']
        ax.plot([r[74] for r in raw], [r[77] for r in raw], color=COLORS[5], ls='-.', label='Archived ASWING')
        measured = np.array([r['xy'] for r in source['experimental_lift'][name]['values']])
        ax.scatter(measured[:, 0], measured[:, 1], s=20, facecolors='none', edgecolors='black', label='ISAE experiment digitization')
        ax.set(title=name, xlabel='Body alpha [deg]', ylabel='CL'); ax.grid(alpha=.2)
    axes[0].legend(fontsize=8, loc='upper left')
    fig.suptitle('SA-10 lift: 100 requested intervals, unchanged section properties')
    for suffix in ['png', 'svg']: fig.savefig(D / ('isae-sa10-lift.' + suffix), dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), layout='constrained')
    for ax, name in zip(axes.flat, ['wing_alone', 'wing_extension', 'Louvered', 'TS_60_45_30']):
        case = cases[name]
        for panels, color, style in [(25, COLORS[4], ':'), (50, COLORS[1], '--'), (100, COLORS[0], '-')]:
            p = polar(case, panels); ax.plot(p['CL'], p['CD'], color=color, ls=style, label=f'OpenSwing N={panels}')
        measured = np.array([r['xy'] for r in source['experimental_drag'][name]['values']])
        ax.scatter(measured[:, 0], measured[:, 1], s=24, facecolors='none', edgecolors='black', label='ISAE experiment digitization')
        roots = [(r['target_CL'], root['result']['CD']) for r in drag['rows'] if r['name'] == name and r['panels'] == 100 for root in r['roots']]
        if roots:
            x, y = np.array(roots).T; ax.scatter(x, y, s=12, marker='+', color=COLORS[0], label='Every matched-CL root, N=100')
        ax.set(title=case['case_id'].replace('_literal', ''), xlabel='CL', ylabel='CD'); ax.grid(alpha=.2)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle('SA-10 drag: current influences, zero PG; no selection by closest drag')
    for suffix in ['png', 'svg']: fig.savefig(D / ('isae-sa10-drag.' + suffix), dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(13, 8), layout='constrained')
    for j, name in enumerate(['TS_60_45_30', 'TS_60_40_80', 'TS_80_60_40']):
        for i, alpha in enumerate([5, 15]):
            ax = axes[i, j]
            for panels, style in [(25, ':'), (50, '--'), (100, '-')]:
                row = next(r for r in cases[name]['runs'] if r['specification'] == dict(
                    case=cases[name]['case_id'], panels=panels, frozen=False, pg='zero', alpha=float(alpha)))
                if row['status'] != 'computed':
                    ax.text(.02, .96-.07*[25,50,100].index(panels), f'N={panels}: rejected', transform=ax.transAxes); continue
                for beam in sorted({s['beam'] for s in row['result']['profiles']}):
                    local = [s for s in row['result']['profiles'] if s['beam'] == beam and s['position'][1] >= .45]
                    if local:
                        ax.plot([s['position'][1] for s in local], [s['cl'] for s in local], ls=style,
                            color=SURFACE_COLORS[(beam-1) % len(SURFACE_COLORS)], label=f'Beam {beam}' if panels==100 else None,
                            path_effects=[path_effects.Stroke(linewidth=2.4, foreground='#555555', alpha=.35), path_effects.Normal()])
            ax.axvline(.559, color='gray', lw=.7); ax.set(title=f'{name}, alpha={alpha}°', xlabel='Right-side physical y [m]', ylabel='Section cl')
            ax.grid(alpha=.2)
    for ax in axes[0]:
        ax.legend(fontsize=7)
    fig.suptitle('Tip junction loads: N=25 dotted, N=50 dashed, N=100 solid; current / zero PG')
    for suffix in ['png', 'svg']: fig.savefig(D / ('isae-sa10-junctions.' + suffix), dpi=180)
    plt.close(fig)
    lines = ['# SA-10 winglet and tip-sail validation', '',
        '**Status: partial quantitative comparison; no experimental validation pass.**', '',
        f"The unchanged production solver completed {output['computed']:,} of {len(rows):,} requested polar states; {len(rejected):,} were rejected and remain in the report. Five literal geometries are runnable. The sixth, `TS_60_45_30`, parses but rejects mesh construction because the first two root joints name the opposite-side beams. Its separately labeled reconstruction swaps only those two beam references. The literal source is preserved.", '',
        'The [explicitly reconstructed input](isae-sa10-TS_60_45_30-repaired-joints.asw) can be loaded directly into OpenSwing. Its bytes match the audited reconstruction used in the numerical and browser checks; it is not presented as an unmodified upstream file.', '',
        '## Sources and setup', '',
        '[Romain P. Jan’s ISAE archive](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865) is pinned to revision `f62943df20e9e4d7d9f50e070477b22426b5f865`. The [source audit](isae-sa10-sources.json) retains all 30 SA-10 files with hashes, the six inputs, archived 82-column polars, unexecuted shell scripts, CSV row mappings and the exact joint reconstruction. The setup discussion is Jan, *Experimental validation of ASWING, Part I: Aerodynamics*, SA-10 / Figure 21.', '',
        'The cited primary experiment is D. S. Miklosovic, [“Analytic and Experimental Investigation of Dihedral Configurations of Three-Winglet Planforms”](https://doi.org/10.1115/1.2948372), J. Fluids Engineering 130(7), 071103 (2008). Only publisher-deposited metadata and abstract parameters were recovered: effective wing aspect ratio 6.29, winglet aspect ratio 4.6 and Reynolds number 600,000. Full geometry, normalization, tunnel corrections and uncertainty remain unverified. The 2005 conference study is a different source and is not substituted.', '',
        'All runs use 55 m/s and the input density, reference dimensions and section properties. Each state starts independently with the production nonlinear model, tolerances, wake-core rules and continuation unchanged. The grid has 25/50/100 requested intervals per beam, current/frozen influences and zero/speed-derived PG Mach. Seven-segment tip models contain 176/350/700 actual strips. Lift is additionally solved at every experimental angle. The original shell files put K/F after the final solve; startup influence and PG choices are therefore treated as sensitivities, not known original settings.', '',
        'Important source limits:', '',
        '- The supplied schematic shows slotted extension/louvered tips; the literal single-beam models are continuous surfaces. Archived tip-sail span/chord is about 4.06, versus 4.6 in the primary abstract.',
        '- The 60/40/80 and 80/60/40 files use different section properties and half the reference span of 60/45/30. They are not isolated cant-angle changes. In increasing physical x, the file named 60/40/80 actually orders its right tip angles approximately 40/60/80.',
        '- The 60/45/30 input also has asymmetric friction drag: beam 2, the left leading sail, explicitly sets Cdf=0.01 in addition to Cdp=0.01; its right counterpart sets Cdf=0. This setting is preserved in the joint reconstruction. The independent zero-incidence drag check includes both terms and records each beam contribution; symmetric lateral forces/moments cannot be assumed.',
        '- Only the baseline, extension and louvered configurations have measured lift curves. The measured tip-sail drag curve is labeled 60/45/30; it is not assigned to the other two variants.',
        '- The planar drag CSV stores CD,CL; the tip-sail CSV stores CL,CD. The mapping is explicit. All six archived polars repeat alpha=12° identically; those rows are retained but counted once in statistics.', '',
        '## Comparison with the digitized measurements', '',
        'The following lift errors use current influences, zero PG and 100 requested intervals. They include post-stall samples and have no uncertainty-based acceptance band.', '',
        '| Configuration | Compared / requested | CL bias | CL RMSE | Maximum absolute CL error |', '|---|---:|---:|---:|---:|']
    for row in output['current_zero_pg_lift']:
        e=row['CL']; lines.append(f"| {row['case']} | {row['computed']} / {row['requested']} | {e['bias']:+.5f} | {e['rmse']:.5f} | {e['maximum_absolute_error']:.5f} |")
    lines += ['', 'For a separate, fixed 0°–8° low-angle window, least-squares slopes use exactly the same measured angles on both sides. The small sample counts and absent uncertainty prevent an acceptance claim.', '',
        '| Configuration | Samples | CL RMSE, 0°–8° | Lift-slope difference |', '|---|---:|---:|---:|']
    for row in low_angle:
        lines.append(f"| {row['case']} | {row['computed']} / {row['requested']} | {row['CL_rmse']:.5f} | {100*row['relative_slope_error']:+.1f}% |")
    lines += ['', '![Lift comparison](isae-sa10-lift.png)', '',
        'Drag is compared at matched CL using bracketed nonlinear solves on every sign-changing adjacent converged polar interval, at 50 and 100 intervals. Failed intervals are not bridged, values are not extrapolated and multiple roots are not reduced to the best drag match. The CSV supplies no angle for these drag observations. “Single observed root” applies only to the sampled 0°–25° domain and the independent solver’s branches; it is not a proof of global uniqueness.', '',
        '| Configuration, N=100 | Single observed root | Multiple roots | No resolved root | CD RMSE, single-root subset |', '|---|---:|---:|---:|---:|']
    for row in drag['summary']:
        if row['panels']==100:
            error=row['single_observed_root_errors']['rmse']; value='—' if error is None else f"{error:.5f} (n={row['complete_single_root_scan']})"
            lines.append(f"| {row['case']} | {row['single_observed_root']} | {row['multiple_observed_roots']} | {row['missing_roots']} | {value} |")
    lines += ['', 'Subset errors use only single observed roots with no failed scan intervals or root solves; their sample counts are explicit. They do not establish agreement over missing or ambiguous points. Every root, failed bracket, matched-lift residual and original CSV row appears in the [fixed-lift report](isae-sa10-drag.json).', '',
        '![Drag comparison](isae-sa10-drag.png)', '', '## Archived ASWING and numerical checks', '',
        '| Configuration, current / zero PG / N=100 | Compared / requested | Archived CL RMSE | Archived CD RMSE |', '|---|---:|---:|---:|']
    for row in output['current_zero_pg_archived']:
        lines.append(f"| {row['case']} | {row['computed']} / {row['requested']} | {row['errors']['CL']['rmse']:.6f} | {row['errors']['CD']['rmse']:.6f} |")
    lines += ['', 'Computed / requested states across all three meshes, including experimental lift angles where supplied:', '',
        '| Configuration | Current, zero PG | Current, speed PG | Frozen, zero PG | Frozen, speed PG |', '|---|---:|---:|---:|---:|']
    for case in cases.values():
        cells=[]
        for frozen, pg in [(False, 'zero'), (False, 'speed'), (True, 'zero'), (True, 'speed')]:
            row=next(r for r in counts if r['case']==case['case_id'] and r['frozen']==frozen and r['pg']==pg)
            cells.append(f"{row['computed']} / {row['requested']}")
        lines.append('| '+case['case_id']+' | '+' | '.join(cells)+' |')
    lines += ['',
        'The raw archived CM differs strongly from OpenSwing’s moment about the input `Xmom=0.05 m`. The check report also translates the computed wrench exactly to the origin, which is the archived zero CG. This substantially changes the comparison but does not establish the archived CM reference convention. Both errors remain reported; the solver reference point is not changed to fit the archive. Actual V/beta/alpha columns 69–71 equal reference-flow columns 72–74 for every archived row (zero-based indexing).', '',
        'The archived commands prescribe an angle sequence. OpenSwing requests here start independently, so these comparisons do not establish reproduction of the archived solution-branch history. This matters especially near stall and is a separate limitation from matching residual tolerances or global coefficients.', '',
        f"Independent force/moment reconstruction agrees within {checks['maximum_wrench_error']:.3g} in coefficient units. Analytical zero-angle profile drag checks pass for all six runnable geometries and all 12 mesh/flag combinations. The maximum accepted circulation residual is {checks['maximum_residual']:.3g}; matched-lift roots are within {checks['maximum_fixed_lift_error']:.3g} of their target CL. These are numerical checks, not experimental validation.", '',
        'The [full polar report](isae-sa10.json) retains every requested state, rejection, per-beam force and mesh comparison. Selected states retain sectional loads and local Mach. Some frozen-influence tip-junction states violate the subsonic local-Mach limit; these rejections are not removed or repaired by fitting a core radius. Jan’s report independently describes problematic close tip-sail interactions and missing circulation continuity. The check here does not establish an accurate junction model.', '',
        '![Junction mesh sensitivity](isae-sa10-junctions.png)', '',
        'Actual [Pyodide replays](isae-sa10-wasm.json) and [offline browser checks](isae-sa10-browser.json) compare with the pinned native solver, including the literal attachment rejection and explicitly repaired model. The browser also displays a frozen-influence local-Mach rejection, disables stale exports and recovers the matching valid current-influence result. These checks verify delivery of the same calculation; they do not make the physical discrepancies disappear.', '',
        'A separate [input-recovery regression](isae-sa10-input-recovery.json) first reproduced a stale error banner after loading a valid model. Model inspection now clears the previous error when a fresh inspection starts. This UI change leaves all numerical modules unchanged.', '',
        'Remaining work includes reconciling the apparatus and section polars with the full primary paper, determining the archived CM/reference and PG/K/F settings, resolving junction validity and nonlinear branch sensitivity, and obtaining measurement/setup uncertainty. The other ISAE families remain tracked separately in the [coverage ledger](isae-coverage.md).', '',
        '## Reproduction', '',
        'Restore the pinned ISAE cache with `scripts/fetch-isae-validation.py`. The separate SA-10 raw archive retains inputs, cached solves and logs. It does not redistribute the unavailable primary paper or the complete Crossref abstract. To regenerate the source audit, `scripts/fetch-isae-sa10.py` retrieves and checks the original public metadata; changed metadata is retained separately for review. Existing numerical caches are keyed by all production modules, scripts and source-report hashes.', '',
        '```sh', 'export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1', '.venv/bin/python scripts/fetch-isae-sa10.py',
        '.venv/bin/python scripts/isae_sa10_reference.py', '.venv/bin/python scripts/verify-isae-sa10.py',
        '.venv/bin/python scripts/verify-isae-sa10-drag.py', '.venv/bin/python scripts/check-isae-sa10.py',
        'node scripts/test-isae-sa10-wasm.mjs', 'npx playwright test tests/browser/isae-sa10.spec.js',
        '.venv/bin/python scripts/summarize-isae-sa10.py', '```', '']
    lines += ['For long runs, `scripts/precompute-isae-sa10.py` can fill selected case caches with separate process workers using the exact pinned compute function. Create-only atomic publication preserves entries already consumed by the serial report writer. Such rows retain the helper and compute-script hashes. The serial command above reproduces the same independent requests without requiring the helper.', '']
    diagnostic = ['Global coefficient refinement does not establish local-flow convergence. For the reconstructed 60/45/30 variant at 25° incidence, current influences and zero PG:', '',
        '| Requested intervals per beam | Peak section-normal Mach | Status |', '|---|---:|---|']
    for panels in [25, 50, 100]:
        row=next(r for r in cases['TS_60_45_30']['runs'] if r['specification']==dict(
            case=cases['TS_60_45_30']['case_id'], panels=panels, pg='zero', frozen=False, alpha=25.))
        if row['status']=='computed':
            diagnostic.append(f"| {panels} | {row['result']['maximum_normal_mach']['normal_mach']:.4f} | Computed |")
        else: diagnostic.append(f"| {panels} | — | Rejected: {row['error']} |")
    limit=checks['finer_junction_diagnostic']
    if limit['status']=='computed':
        diagnostic.append(f"| 150 | {limit['result']['maximum_normal_mach']['normal_mach']:.4f} | Computed diagnostic |")
    else:
        maximum=(limit.get('details') or {}).get('maximum',{}).get('normal_mach')
        value='—' if maximum is None else f'{maximum:.4f}'
        reason='Rejected: subsonic local-Mach limit' if (limit.get('details') or {}).get('kind')=='section_normal_mach' else 'Rejected; see numerical check report'
        diagnostic.append(f"| 150 | {value} | {reason} |")
    diagnostic += ['', 'This additional refinement is separate from the 2,676-state polar grid. It retains the same solver and validity checks; no core radius or local velocity is clipped to obtain a result.', '']
    index=lines.index('![Junction mesh sensitivity](isae-sa10-junctions.png)')
    lines[index:index]=diagnostic
    (D / 'isae-sa10.md').write_text('\n'.join(lines))
    print('COMPLETE: comparison report and three figures', flush=True)


if __name__ == '__main__':
    main()
