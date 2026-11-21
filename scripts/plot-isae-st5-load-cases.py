#!/usr/bin/env python3
"""Render two original ST-5 load cases from terminal saved comparisons only.

No OpenSwing imports or physical evaluations. Curves connect the saved positive
material stations, retaining duplicate one-sided rows. The data check reconstructs
dz and twist from saved positions/frames and binds every archived value to its
separately decoded target. Normalized errors are descriptive, never passbands.
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
CASES = ('20lb_90_10', '30lb_90_10')
STRUCTURAL = list(range(1, 13)) + [19, 20]
FIELDS = ((3, 'z-z0', r'Displacement $z-z_0$ (ft)', 'ft'),
          (5, 'tw-tw0', r'Twist $\vartheta-\vartheta_0$ (deg)', 'deg'))
DEFAULT_STAGE = Path('/tmp/openswing-st5-load-cases-native-20261026')
DEFAULT_OUTPUT = Path('/tmp/openswing-st5-load-cases-plot-20261026')


def read(path):
    return json.loads(path.read_text())


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def require(ok, label):
    if not ok:
        raise RuntimeError(label)


def twist(frame):
    """Invert the primary c/s/n Euler frame using scalar arithmetic."""
    c, s = [[frame[i][j] for i in range(3)] for j in (0, 1)]
    phi = math.atan2(s[2], s[1])
    psi = -math.asin(max(-1., min(1., s[0])))
    c0 = (math.cos(psi), math.sin(psi)*math.cos(phi), math.sin(psi)*math.sin(phi))
    n0 = (0., -math.sin(phi), math.cos(phi))
    return math.degrees(math.atan2(-sum(a*b for a, b in zip(c, n0)),
                                  sum(a*b for a, b in zip(c, c0))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, default=DEFAULT_STAGE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                        help='New artifact directory; existing artifacts are never overwritten.')
    parser.add_argument('--palette', type=Path, default=ROOT/'web/plot-colors.js')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__).resolve(), args.palette, args.stage/'execution.json', args.stage/'summary.json']
    for case in CASES:
        sources += [args.stage/case/p for p in ('target.json', 'summary.json', 'level0/comparison.json')]
    before = [pin(p) for p in sources]
    write(args.output/'plan.json', dict(scope='Terminal saved-data plotting and arithmetic only',
        source_pins=before, cases=list(CASES), level=0, structural_channels=STRUCTURAL,
        plotted_columns=[f[0] for f in FIELDS], plotted_domain='t_evaluated >= 0; duplicate rows retained',
        normalization='For each structural channel: max over all 80 rows of |native-archive| / max over all 80 rows of |archive|.',
        zero_envelope='0 if both envelope and error are zero, otherwise undefined (null).',
        production_imports=0, solves=0, residual_calls=0))
    try:
        execution, summary = read(args.stage/'execution.json'), read(args.stage/'summary.json')
        require(execution['status'] == 'PASS' and execution['all_children_reaped']
                and execution['input_pins_unchanged'], 'Native execution is not terminal PASS with fixed inputs')
        require(len(execution['children']) == 2 and all(c['state'] == 'TERMINAL' and c['reaped']
                and c['exit_code'] == 0 and not c['timed_out'] for c in execution['children']), 'Native children not reaped')
        require(summary['cold_solves'] == summary['fresh_residuals'] == 6, 'Unexpected native operation count')
        match = re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);', args.palette.read_text(), re.S)
        require(match is not None, 'VibeLattice plotColors not found')
        colors = re.findall(r'#[0-9a-fA-F]{6}', match[1])[:2]
        require(len(colors) == 2, 'Two palette colors required')
        checks, plotted, case_reports = [], [], {}

        def check(label, ok):
            checks.append(dict(name=label, passed=bool(ok)))
            require(ok, label)

        plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none',
                             'svg.hashsalt': 'isae-st5-load-cases'})
        fig, axes = plt.subplots(2, 2, figsize=(12, 8.7), sharex=True)
        for case_index, case in enumerate(CASES):
            folder = args.stage/case
            packet, target, case_summary = [read(folder/p) for p in ('level0/comparison.json', 'target.json', 'summary.json')]
            check(case+' embedded summary', summary['cases'][case] == case_summary)
            check(case+' completed physical gates', case_summary['all_numerical_gates_pass'] and packet['numerical_gates_pass'])
            check(case+' coarse grid', packet['level'] == 0 and packet['intervals_by_beam'] == {'1': 38, '2': 32})
            rows, names = packet['rows'], case_summary['columns']
            refs = [(block, row) for block in target['beams'] for row in block['rows']]
            check(case+' 80 archived rows', len(rows) == len(refs) == 80)
            check(case+' target pin', pin(folder/'target.json')['sha256'] == case_summary['target_sha256'])
            check(case+' unchanged source identity', target['source_pins'][0]['sha256'] == case_summary['source_sha256'])
            for row, (block, ref) in zip(rows, refs):
                label = f"{case} beam {row['beam']} source line {row['source_line']}"
                check(label+' archived identity', row['beam'] == block['beam'] and row['source_line'] == ref['source_line']
                      and row['expected'] == ref['physical'] and row['t_printed'] == ref['printed_t'])
                t = ref['printed_t'] if ref['exact_anchor_t'] is None else ref['exact_anchor_t']
                check(label+' station', row['t_evaluated'] == t)
                half = [float(Decimal(10)**Decimal(Decimal(token).as_tuple().exponent))/2*scale
                        for token, scale in zip(ref['raw_tokens'], block['physical_multipliers'])]
                check(label+' printed precision', row['half_last_place'] == half)
                diff = [a-b for a, b in zip(row['values'], row['expected'])]
                check(label+' all finite', all(math.isfinite(v) for v in row['values']+row['expected']))
                check(label+' all differences and precision masks', diff == row['difference'] and
                      [abs(d) <= h for d, h in zip(diff, half)] == row['inside_printed_interval'])
                check(label+' reconstructed dz', math.isclose(row['position'][2]-row['jig_position'][2], row['values'][3], abs_tol=2e-13, rel_tol=2e-13))
                check(label+' reconstructed twist', math.isclose(twist(row['frame'])-twist(row['jig_frame']), row['values'][5], abs_tol=2e-11, rel_tol=2e-13))
            metrics = []
            for j in STRUCTURAL:
                diff = [r['values'][j]-r['expected'][j] for r in rows]
                envelope = max(abs(r['expected'][j]) for r in rows)
                maximum = max(map(abs, diff))
                rmse = math.sqrt(math.fsum(d*d for d in diff)/len(diff))
                old = packet['metrics'][names[j]]
                check(case+' metric '+names[j], maximum == old['max_abs_difference'] and
                      math.isclose(rmse, old['rmse'], rel_tol=2e-13, abs_tol=2e-15))
                ratio = maximum/envelope if envelope else (0. if maximum == 0 else None)
                metrics.append(dict(column=j, name=names[j], archived_absolute_envelope=envelope,
                    max_absolute_difference=maximum, rmse=rmse, max_normalized_difference=ratio,
                    max_normalized_difference_percent=None if ratio is None else 100*ratio,
                    strict_matches=sum(abs(d) <= r['half_last_place'][j] for d, r in zip(diff, rows))))
            check(case+' structural count', sum(m['strict_matches'] for m in metrics) == packet['structural_matches'])
            tips = []
            for beam, label, color in zip((1, 2), ('Front wing', 'Rear wing'), colors):
                positive = [r for r in rows if r['beam'] == beam and r['t_evaluated'] >= 0]
                check(case+f' beam {beam} station order', len(positive) > 1 and
                      all(a['t_evaluated'] <= b['t_evaluated'] for a, b in zip(positive[:-1], positive[1:])))
                for column, (j, name, ylabel, units) in enumerate(FIELDS):
                    ax = axes[case_index, column]
                    t = [r['t_evaluated'] for r in positive]
                    actual = [r['values'][j] for r in positive]
                    archived = [r['expected'][j] for r in positive]
                    ax.plot(t, actual, color=color, linewidth=1.7, zorder=2)
                    ax.plot(t, archived, linestyle='none', marker='o', markersize=4.2,
                            markerfacecolor='white', markeredgecolor=color, markeredgewidth=1., zorder=3)
                    for r in positive:
                        plotted.append(dict(case=case, level=0, beam=beam, source_line=r['source_line'], side=r['side'],
                            t_printed=r['t_printed'], t_evaluated=r['t_evaluated'], field=name, units=units,
                            archived=r['expected'][j], native=r['values'][j], native_minus_archive=r['values'][j]-r['expected'][j],
                            printed_half_unit=r['half_last_place'][j]))
                    tip = positive[-1]
                    difference = tip['values'][j]-tip['expected'][j]
                    tips.append(dict(beam=beam, name=label, field=name, units=units, t=tip['t_evaluated'],
                        native=tip['values'][j], archived=tip['expected'][j], difference=difference,
                        signed_percent_of_absolute_archive=100*difference/abs(tip['expected'][j]) if tip['expected'][j] else None))
            for column, (_, _, ylabel, _) in enumerate(FIELDS):
                ax = axes[case_index, column]
                ax.set_title(f"{case.replace('_', ' / ')}  ·  38 front + 32 rear intervals", fontsize=11, pad=10)
                ax.set_ylabel(ylabel)
                ax.grid(color='#d8dde3', linewidth=.6)
                ax.axhline(0, color='#89939e', linewidth=.6, zorder=1)
                ax.spines[['top', 'right']].set_visible(False)
                ax.margins(x=.02, y=.10)
                if case_index == 1:
                    ax.set_xlabel('Positive material station t (ft)')
            finite_metrics = [m for m in metrics if m['max_normalized_difference'] is not None]
            case_reports[case] = dict(level=0, intervals_by_beam=packet['intervals_by_beam'],
                structural_matches=packet['structural_matches'], structural_entries=packet['structural_entries'],
                channel_metrics=metrics, worst_normalized_channel=max(finite_metrics, key=lambda m: m['max_normalized_difference']),
                tip_differences=tips, native_summary_flags={k: case_summary[k] for k in
                    ('all_numerical_gates_pass', 'all_fine_mesh_gates_pass', 'strict_structural_reference_match')})
        fig.suptitle('ST-5: two additional original load cases', fontsize=16, y=.985)
        fig.text(.5, .95, 'Archived ASWING vs native source-section operator; original models unchanged', ha='center', fontsize=10)
        handles = [Line2D([], [], color=c, lw=2, label=n) for c, n in zip(colors, ('Front wing', 'Rear wing'))]
        handles += [Line2D([], [], color='#414953', marker='o', markerfacecolor='white', linestyle='none', label='Archived ASWING'),
                    Line2D([], [], color='#414953', lw=1.7, label='Native saved samples')]
        fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .932), ncol=4, frameon=False)
        fig.text(.5, .045, 'Lines join saved samples; duplicate one-sided rows retained. Exact model anchors + other printed station centers.', ha='center', fontsize=9)
        fig.text(.5, .023, 'Conditional historical grid reconstruction. No fitted parameters, tolerance adjustment, or full reference-pass claim.', ha='center', fontsize=9)
        fig.subplots_adjust(left=.085, right=.98, top=.85, bottom=.12, hspace=.31, wspace=.24)
        figures = []
        for suffix in ('svg', 'png'):
            path = args.output/f'isae-st5-load-cases.{suffix}'
            fig.savefig(path, dpi=180, metadata={'Date': None} if suffix == 'svg' else {'Software': 'Matplotlib; saved data only'})
            figures.append(pin(path))
        plt.close(fig)
        with (args.output/'plot-data.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(plotted[0]))
            writer.writeheader(); writer.writerows(plotted)
        check('all inputs unchanged', before == [pin(p) for p in sources])
        report = dict(status='PASS_SAVED_DATA_CHECKS_AND_RENDERED', source_pins=before, figures=figures,
            cases=case_reports, normalization=read(args.output/'plan.json')['normalization'], checks=checks,
            checks_passed=len(checks), checks_total=len(checks), plotted_records=len(plotted),
            palette=dict(path=str(args.palette), array='plotColors', colors=colors, roles=['front', 'rear']),
            plot_data=pin(args.output/'plot-data.csv'), production_imports=0, solves=0, residual_calls=0,
            limitations=['Saved-array arithmetic does not independently verify the equilibrium.',
                         'Normalized errors are descriptive full-table values, not numerical or reference acceptance gates.',
                         'Only the original-station level0 curves are drawn; all three grid outcomes remain in the native summaries.'])
        write(args.output/'report.json', report)
        print(json.dumps(dict(status=report['status'], checks=len(checks), figures=figures,
                              report=pin(args.output/'report.json')), indent=2))
    except BaseException as exc:
        write(args.output/'failure.json', dict(status='FAILURE_RETAINED', error=f'{type(exc).__name__}: {exc}',
                                             production_imports=0, solves=0, residual_calls=0))
        raise


if __name__ == '__main__':
    main()
