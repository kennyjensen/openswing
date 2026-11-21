"""Export source-pinned ST-4 conditional still-air spectral comparisons.

Each point is one original zero-speed observation at one inertia endpoint.
Repeated before/after points are retained; there is no averaging or fitting.
"""
from pathlib import Path
import argparse
import hashlib
import json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output-prefix', type=Path, required=True)
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args()
    report = json.loads(args.summary.read_text())
    require(report['density'] == 1.225 and not report['full_physical_validation'], 'Unexpected study scope')
    require(not report['method']['nearest_frequency_assignment_used']
            and not report['method']['frequency_fitting_or_input_tuning_used'], 'Unsupported pairing/fitting method')
    require(report['complete'] or args.allow_incomplete, 'Incomplete summary: use --allow-incomplete to label interim figures')
    observations = report['experiment']['all_observations']
    require(len(observations) == 78 and sum(v['complete_triplet'] for v in observations) == 72
            and len(report['experiment']['not_clear_cells']) == 6, 'Unexpected observation coverage')
    rows = [r for r in report['experiment']['individual_spectral_residuals'] if r['panels'] == 32]
    require(rows, 'No N32 comparison points available')
    ids = {(r['observation_id'], r['icc_endpoint'], r['spectral_rank']) for r in rows}
    require(len(ids) == len(rows), 'Duplicate spectral comparison point')
    series = []
    for rank in (1, 2, 3):
        for endpoint in ('lower', 'upper'):
            points = [r for r in rows if r['spectral_rank'] == rank and r['icc_endpoint'] == endpoint]
            require(len(points) <= 72, 'Too many points in one rank/endpoint series')
            series.append(dict(spectral_rank=rank, icc_endpoint=endpoint, points=len(points), expected_points=72))
    complete_coverage = len(rows) == 432
    prefix = args.output_prefix
    paths = {kind:Path(str(prefix)+extension) for kind, extension in
             [('png', '.png'), ('pdf', '.pdf'), ('manifest', '.plot.json')]}
    require(all(not p.exists() for p in paths.values()), 'Use a fresh output prefix to preserve earlier figures')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.ticker import MaxNLocator

    fig, axes = plt.subplots(1, 3, figsize=(12.8, 5.1))
    fig.subplots_adjust(left=.075, right=.99, bottom=.25, top=.78, wspace=.29)
    for rank, ax in enumerate(axes, 1):
        subset = [r for r in rows if r['spectral_rank'] == rank]
        for endpoint, color, marker in [('lower', '#2171b5', 'o'), ('upper', '#b14a21', 'x')]:
            points = [r for r in subset if r['icc_endpoint'] == endpoint]
            ax.scatter([r['observed_frequency_Hz'] for r in points], [r['native_frequency_Hz'] for r in points],
                       s=27, alpha=.62, color=color, marker=marker, linewidths=.9,
                       label=f'Icc {endpoint} ({len(points)}/72)')
        values = [v for r in subset for v in (r['observed_frequency_Hz'], r['native_frequency_Hz'])]
        if values:
            low, high = min(values), max(values)
            pad = max(.04*(high-low), .02*high)
            limits = [max(0., low-pad), high+pad]
            ax.plot(limits, limits, '--', color='.35', linewidth=.8, label='Equal frequency')
            ax.set(xlim=limits, ylim=limits)
        ax.set_title(f'Frequency rank {rank}', fontsize=11)
        ax.set_xlabel('Measured at zero airspeed [Hz]', fontsize=9)
        ax.set_ylabel('Computed in still air, N32 [Hz]', fontsize=9)
        ax.xaxis.set_major_locator(MaxNLocator(5))
        ax.yaxis.set_major_locator(MaxNLocator(5))
        ax.tick_params(labelsize=8)
        ax.grid(alpha=.2)
        ax.set_aspect('equal', adjustable='box')
        ax.legend(fontsize=7, loc='upper left')
    qualifier = 'Final sweep' if report['complete'] else 'INTERIM — incomplete sweep'
    if report['complete'] and not complete_coverage:
        qualifier += ' — missing/rejected comparisons retained'
    fig.suptitle(f'Primary ST-4: conditional still-air spectral comparison\n{qualifier}; '
                 f"{report['terminal_native_states']}/252 terminal calculations", fontsize=12, y=.96)
    caption = (
        'Assumed density 1.225 kg/m³; thin-strip apparent mass; hanging gravity +z. '
        'Laboratory zero-speed density and fixture/pylon details remain unresolved.\n'
        'Each printed complete B1/B2/T triplet is sorted and compared with the lowest three computed frequencies; '
        'spectral rank does not establish physical mode identity.\n'
        f'{len(rows)}/432 N32 points retained (216 per endpoint when complete). '
        'Every phase is separate, including coincident points; no averaging, fits or nearest-frequency pairing.\n'
        'All 6 incomplete triplets containing a “Not clear” cell are excluded from this spectral plot and retained in the source summary. '
        'No experimental acceptance threshold is asserted.'
    )
    fig.text(.075, .035, caption, ha='left', va='bottom', fontsize=7.6, linespacing=1.5)
    for kind in ('png', 'pdf'):
        fig.savefig(paths[kind], dpi=180, metadata={'Title':'Conditional primary ST-4 still-air spectral comparison',
                    'Subject':f"Summary SHA256 {sha(args.summary)}"} if kind == 'pdf' else
                    {'Title':'Conditional primary ST-4 still-air spectral comparison', 'Description':caption})
    plt.close(fig)
    result = dict(status='FINAL_SWEEP_FIGURE' if report['complete'] else 'INTERIM_INCOMPLETE_SWEEP_FIGURE',
        full_physical_validation=False, all_expected_N32_points_present=complete_coverage,
        script_sha256=sha(__file__), summary=dict(path=str(args.summary.resolve()), sha256=sha(args.summary)),
        summary_status=report['status'], density=report['density'], panels=32, plotted_points=len(rows), expected_points=432,
        series=series, points=rows, caption=caption,
        method=dict(frequency_ranks=[1, 2, 3], before_after_averaging=False, fits=False,
                    nearest_frequency_pairing=False, coincident_points_retained=True),
        outputs={kind:dict(path=str(paths[kind].resolve()), sha256=sha(paths[kind])) for kind in ('png', 'pdf')})
    paths['manifest'].write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status', 'plotted_points', 'expected_points', 'series', 'outputs')}, indent=2))


if __name__ == '__main__':
    main()
