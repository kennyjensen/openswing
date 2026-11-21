"""Plot every native AE3 finite-control coefficient at both declared meshes."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output-prefix', required=True, type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('ae3_plot_summary', ROOT/'scripts/summarize-isae-suite.py')
    summary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summary)
    packet = summary.load_runs([args.run], ROOT)
    from scripts.isae_suite_ae3 import NAMES, NOMINALS
    jobs = [job for job in packet['jobs'] if job['adapter'] == 'ae3'
            and job['target_kind'] == 'native_coefficients']
    coordinates = sorted({job['coordinate_id'] for job in jobs})
    if len(coordinates) != 6 or len(jobs) != 12:
        raise ValueError('This plot requires all six native states at both predeclared meshes.')
    records = []
    for coordinate in coordinates:
        pair = sorted((job for job in jobs if job['coordinate_id'] == coordinate), key=lambda job:job['nominal'])
        if tuple(job['nominal'] for job in pair) != NOMINALS:
            raise ValueError('Missing or substituted mesh at '+coordinate)
        for name in NAMES:
            references = [next(row for row in job['observations'] if row['name'] == name) for job in pair]
            if references[0] != references[1]:
                raise ValueError('Original reference differs between meshes.')
            reference = references[0]
            row = dict(coordinate_id=coordinate, speed=pair[0]['condition']['speed'], coefficient=name,
                       expected=reference['expected'], expected_token=reference['expected_token'],
                       tolerance=reference['tolerance'], table_path=pair[0]['table_path'])
            for job in pair:
                result = job.get('result') or {}
                check = next((item for item in result.get('reference_checks', []) if item['name'] == name), {})
                valid = summary.numerically_valid(result)
                row['status_m'+str(job['nominal'])] = result.get('status', 'unrun')
                row['predicted_m'+str(job['nominal'])] = check.get('predicted') if valid else None
            records.append(row)
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    with prefix.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(2, 3, figsize=(13, 7.8), constrained_layout=True)
    for name, ax in zip(NAMES, axes.flat):
        rows = sorted((row for row in records if row['coefficient'] == name), key=lambda row:row['speed'])
        speed = [row['speed'] for row in rows]
        ax.errorbar(speed, [row['expected'] for row in rows],
                    yerr=[row['tolerance'] for row in rows], fmt='ko', capsize=3,
                    label='Archived ASWING (print precision)')
        for nominal, color in zip(NOMINALS, ('#4477aa', '#ee7733')):
            ax.plot(speed, [row['predicted_m'+str(nominal)] if row['predicted_m'+str(nominal)] is not None
                           else float('nan') for row in rows], '.-', color=color, label=f'OpenSwing {nominal} intervals')
        ax.set_title(name); ax.set_xlabel('Speed (m/s)'); ax.set_ylabel('Coefficient')
        ax.grid(True, alpha=.3); ax.ticklabel_format(axis='y', style='sci', scilimits=(-3,3))
    axes.flat[0].legend(fontsize=8)
    figure.suptitle('AE-3: all six native F1=+1 states\nConditional original-model replay; derivatives and other targets remain unfinished', fontsize=13)
    figure.savefig(prefix.with_suffix('.png'), dpi=160)
    figure.savefig(prefix.with_suffix('.svg'))
    plt.close(figure)
    summary.verify_summary_sources(packet)
    report = dict(scope='All36 distinct original native finite-control coefficient cells, both prospective80/160 meshes.',
                  original_states=6, distinct_reference_cells=36, prediction_slots=72,
                  finite_predictions=sum(summary.finite(row['predicted_m'+str(n)]) for row in records for n in NOMINALS),
                  unavailability='Unrun, failed or unsupported numerical predictions remain blank/plot gaps; never zero-filled.',
                  acceptance='Original printed precision unchanged; these plots do not validate a complete family.',
                  sources=packet['inputs'], plotter=summary.pin(__file__), records=records,
                  artifacts=[summary.pin(prefix.with_suffix(suffix)) for suffix in ('.csv','.png','.svg')])
    prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key:report[key] for key in ('original_states','distinct_reference_cells','prediction_slots','finite_predictions')}))


if __name__ == '__main__':
    main()
