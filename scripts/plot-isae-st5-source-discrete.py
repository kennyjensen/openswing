#!/usr/bin/env python3
"""Plot saved ST-5 source-discrete and spline-only reference comparisons.

This is a data-only renderer. It imports no OpenSwing modules and performs no
model construction or physical evaluation. Explicit input paths allow replay
from an extracted evidence archive.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEW = Path('/tmp/openswing-isae-st5-source-discrete-r2-20261026/level0/comparison.json')
DEFAULT_OLD = Path('/tmp/openswing-isae-st5-spline-candidate-r2-20261025/level0/comparison.json')
DEFAULT_EVIDENCE = Path('/tmp/openswing-isae-st5-discrete-plot-20261026')
FIELDS = [(3, 'z-z0', r'Displacement $z-z_0$ (ft)', 'ft'),
          (5, 'tw-tw0', r'Twist $\vartheta-\vartheta_0$ (deg)', 'deg'),
          (8, 'Ms_prime', r'Torsion $M_s^\prime$ (lb ft)', 'lb ft')]


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-discrete', type=Path, default=DEFAULT_NEW)
    parser.add_argument('--spline-only', type=Path, default=DEFAULT_OLD)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/validation/isae-st5-source-discrete')
    parser.add_argument('--evidence', type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    palette_path = ROOT/'web/plot-colors.js'
    sources = [args.source_discrete, args.spline_only, palette_path, Path(__file__)]
    before = [pin(path) for path in sources]
    new = json.loads(args.source_discrete.read_text())
    old = json.loads(args.spline_only.read_text())
    assert new['intervals_by_beam'] == old['intervals_by_beam'] == {'1': 38, '2': 32}
    assert len(new['rows']) == len(old['rows']) == 80
    for a, b in zip(new['rows'], old['rows']):
        for key in ('beam', 'source_line', 't_printed', 't_evaluated', 'side', 'expected', 'half_last_place'):
            assert a[key] == b[key], (key, a['source_line'])
    palette = re.search(r'export const surfaceColors = Object.freeze\(\[(.*?)\]\);',
                        palette_path.read_text(), re.S)
    colors = re.findall(r'#[0-9a-fA-F]{6}', palette[1])[:2]
    assert colors == ['#ff0000', '#ff8c00']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.labelsize': 10, 'axes.titlesize': 12,
                         'svg.fonttype': 'none', 'svg.hashsalt': 'isae-st5-source-discrete'})
    fig, axes = plt.subplots(3, 2, figsize=(12, 10.6), sharex='col')
    metrics, rows = [], []
    for column, (beam, name, color) in enumerate(zip((1, 2), ('Forward wing', 'Rear wing'), colors)):
        pairs = [(a, b) for a, b in zip(new['rows'], old['rows']) if a['beam'] == beam]
        assert len(pairs) == (44 if beam == 1 else 36)
        t = np.array([a['t_evaluated'] for a, _ in pairs])
        assert np.all(np.diff(t) >= 0)
        for row, (index, field, label, units) in enumerate(FIELDS):
            ax = axes[row, column]
            reference = np.array([a['expected'][index] for a, _ in pairs])
            candidate = np.array([a['values'][index] for a, _ in pairs])
            previous = np.array([b['values'][index] for _, b in pairs])
            assert np.all(np.isfinite([reference, candidate, previous]))
            ax.plot(t, previous, color=color, linewidth=1.65, linestyle=(0, (5, 3)), zorder=2)
            ax.plot(t, candidate, color=color, linewidth=1.65, zorder=3)
            ax.plot(t, reference, linestyle='none', marker='o', markersize=3.7,
                    markerfacecolor='white', markeredgecolor='#23272b', markeredgewidth=.8, zorder=4)
            errors = {'source_discrete': candidate-reference, 'spline_only': previous-reference}
            metric = dict(beam=beam, field=field, units=units, archived_rows=len(pairs))
            for key, difference in errors.items():
                metric[key] = dict(max_absolute_error=float(np.max(abs(difference))),
                                   rmse=float(np.sqrt(np.mean(difference**2))))
            metrics.append(metric)
            ax.text(.5, 1.018,
                    f"Max |archive difference|: source {metric['source_discrete']['max_absolute_error']:.3g}"
                    f"  ·  spline only {metric['spline_only']['max_absolute_error']:.3g} {units}",
                    transform=ax.transAxes, va='bottom', ha='center', fontsize=8.5,
                    color='#424b55', zorder=5)
            if row == 0:
                ax.set_title(f'{name}  ·  {len(pairs)} archived rows', color=color, pad=30, fontweight='bold')
            ax.set_ylabel(label)
            ax.grid(color='#d8dde3', linewidth=.6, alpha=.75)
            ax.axhline(0, color='#8d969f', linewidth=.65, zorder=1)
            ax.spines[['top', 'right']].set_visible(False)
            ax.margins(x=.025, y=.16)
            if row == 2:
                ax.set_xlabel('Material station t (original input parameter)')
            for k, (a, b) in enumerate(pairs):
                rows.append(dict(beam=beam, source_line=a['source_line'], side=a['side'],
                                 t_printed=a['t_printed'], t_evaluated=a['t_evaluated'], field=field,
                                 units=units, archived=float(reference[k]), source_discrete=float(candidate[k]),
                                 spline_only=float(previous[k]), printed_half_last_place=a['half_last_place'][index],
                                 source_discrete_minus_archive=float(errors['source_discrete'][k]),
                                 spline_only_minus_archive=float(errors['spline_only'][k])))
    fig.suptitle('ST-5: archived ASWING and diagnostic structural operators', y=.982, fontsize=16)
    fig.text(.5, .951, 'Original archived-node grid reconstruction: 38 forward + 32 rear intervals',
             ha='center', fontsize=10.5, color='#424b55')
    handles = [Line2D([], [], color='#23272b', marker='o', markerfacecolor='white', linestyle='none',
                      markersize=5, label='Archived ASWING'),
               Line2D([], [], color='#424b55', linewidth=1.8,
                      label='Source-discrete + spline diagnostic'),
               Line2D([], [], color='#424b55', linewidth=1.8, linestyle=(0, (5, 3)),
                      label='Previous spline-only diagnostic')]
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .927), ncol=3,
               frameon=False, fontsize=10, handlelength=3)
    fig.text(.5, .047, 'Diagnostic-only comparison; no strict reference pass claimed. Curves join saved samples; '
             'duplicate one-sided rows are retained.', ha='center', fontsize=9.3, color='#424b55')
    fig.text(.5, .024, 'Known anchors use exact model stations; other stations use archived printed values. '
             'No experimental data or fitted parameters.', ha='center', fontsize=9.3, color='#424b55')
    fig.subplots_adjust(left=.085, right=.98, top=.815, bottom=.12, hspace=.29, wspace=.24)
    output_paths = []
    for extension in ('svg', 'png'):
        path = args.output.with_suffix('.'+extension)
        metadata = {'Date': None} if extension == 'svg' else {'Software': 'Matplotlib; saved data only'}
        fig.savefig(path, dpi=180, metadata=metadata)
        output_paths.append(path)
    plt.close(fig)
    with (args.evidence/'plot-data.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    assert before == [pin(path) for path in sources]
    report = dict(status='PLOTTED_SAVED_DATA_ONLY', source_pins=before, figures=[pin(p) for p in output_paths],
                  panels=6, archived_rows=80, displayed_channels=3, plotted_records=len(rows),
                  intervals_by_beam=new['intervals_by_beam'], surface_colors=colors, metrics=metrics,
                  source_inputs_unchanged=True, production_imports=0, residual_calls=0, solves=0,
                  claims=dict(strict_reference_pass=False, experimental_validation=False),
                  plot_data=pin(args.evidence/'plot-data.csv'))
    (args.evidence/'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status=report['status'], panels=6, plotted_records=len(rows),
                          figures=report['figures'], metrics=str(args.evidence/'metrics.json')), indent=2))


if __name__ == '__main__':
    main()
