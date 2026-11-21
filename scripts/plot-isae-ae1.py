"""Plot all AE1 native sensor rows from a completed, frozen suite run."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path


CHANNELS = (
    ('sensor1_RX_earth_m', 'Sensor 1: Earth X (m)'),
    ('sensor1_RZ_earth_m', 'Sensor 1: Earth Z (m)'),
    ('sensor2_RX_earth_m', 'Sensor 2: Earth X (m)'),
    ('sensor2_RZ_earth_m', 'Sensor 2: Earth Z (m)'),
    ('sensor3_RZ_earth_m', 'Sensor 3: Earth Z (m)'),
    ('sensor3_Theta_elevation_deg', 'Sensor 3: elevation (deg)'),
)


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output-prefix', required=True, type=Path)
    args = parser.parse_args()
    plan_path, report_path = args.run/'plan.json', args.run/'report.json'
    plan, report = (json.loads(p.read_text()) for p in (plan_path, report_path))
    if report['jobs_finished'] != report['jobs_planned'] or not report['current_code_unchanged']:
        raise ValueError('A completed run with unchanged numerical code is required.')
    planned = {job['id']:job for job in plan['jobs']}
    selected = [job for job in report['jobs'] if job['adapter'] == 'ae1' and job['nominal'] == 80]
    if len(selected) != 100:
        raise ValueError('All 100 native rows on the predeclared finer mesh are required.')
    for job in selected:
        if {k:v for k,v in job.items() if k != 'result'} != planned[job['id']]:
            raise ValueError('Reported row or declared settings differ from the frozen plan.')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    plt.rcParams.update({'figure.facecolor':'#111827', 'axes.facecolor':'#111827', 'text.color':'#e5e7eb',
        'axes.labelcolor':'#e5e7eb', 'axes.edgecolor':'#64748b', 'xtick.color':'#cbd5e1', 'ytick.color':'#cbd5e1',
        'grid.color':'#334155', 'savefig.facecolor':'#111827', 'font.size':10})
    fig, axes = plt.subplots(3, 2, figsize=(12.8, 11.3), sharex=True)
    rows, statistics = [], {}
    for axis, (channel, label) in zip(axes.flat, CHANNELS):
        channel_stats = {}
        for alpha, color in ((5, '#ff4a3d'), (7, '#ff9f1a')):
            series = sorted([job for job in selected if f'alpha{alpha}.sh' in job['driver_path']],
                            key=lambda job:job['reference_rows'][0]['row_number'])
            if len(series) != (57 if alpha == 5 else 43):
                raise ValueError('Complete original series is required.')
            xs, archived, predicted, errors = [], [], [], []
            for job in series:
                source = job['reference_rows'][0]
                target = next(c for c in job['observations'] if c['name'] == channel)
                check = next(c for c in job['result']['reference_checks'] if c['name'] == channel)
                if check['expected'] != target['expected'] or check['tolerance'] != target['tolerance']:
                    raise ValueError('Native target or precision changed.')
                speed = None if source['command'] is None else float(source['command']['value'])
                value = check['predicted'] if job['result']['status'] == 'computed' and job['result']['numerical_pass'] else None
                if value is not None and not math.isfinite(value):
                    value = None
                rows.append(dict(alpha_series=alpha, original_row=source['row_number'],
                    archived_IAS_command_mps=speed, channel=channel, archived=target['expected'],
                    predicted=value, physical_status=job['result']['status'], source_job=job['id']))
                if speed is None:
                    continue
                xs.append(speed); archived.append(target['expected'])
                predicted.append(float('nan') if value is None else value)
                if value is not None:
                    errors.append(value-target['expected'])
            axis.plot(xs, archived, color=color, marker='o', markerfacecolor='none',
                      linestyle='none', markersize=3.8)
            axis.plot(xs, predicted, color=color, linestyle='--', linewidth=1.4)
            channel_stats[str(alpha)] = dict(source_rows=len(series), known_coordinates=len(xs),
                finite_predictions=len(errors), rmse=math.sqrt(sum(e*e for e in errors)/len(errors)) if errors else None,
                max_abs_error=max(map(abs, errors)) if errors else None)
        axis.set_ylabel(label); axis.grid(True, alpha=.7)
        statistics[channel] = channel_stats
    for axis in axes[-1]:
        axis.set_xlabel('Archived IAS command (m/s); conditional TAS reconstruction')
    fig.suptitle('ISAE AE-1: both original sweeps, all six absolute sensor outputs', fontsize=16, y=.985)
    fig.legend(handles=[
        Line2D([], [], color='#ff4a3d', label='alpha 5°'),
        Line2D([], [], color='#ff9f1a', label='alpha 7°'),
        Line2D([], [], color='#e5e7eb', marker='o', markerfacecolor='none', linestyle='none', label='Archived ASWING'),
        Line2D([], [], color='#e5e7eb', linestyle='--', label='OpenSwing, nominal 80 intervals')],
        loc='upper center', bbox_to_anchor=(.5,.955), ncol=4, frameon=False)
    fig.text(.5, .025, 'Literal model and sensor coordinates retained. Historical setup and continuation remain conditional.\n'
             'Two initial rows have unknown operating coordinates: retained in CSV/report, not placed at an invented speed.\n'
             'Lines connect independent cold starts. Failed or unavailable predictions remain gaps.',
             ha='center', fontsize=10, color='#cbd5e1')
    fig.tight_layout(rect=(.01,.105,.99,.925))
    prefix = args.output_prefix; prefix.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('.png', '.svg'):
        fig.savefig(prefix.with_suffix(suffix), dpi=160)
    plt.close(fig)
    if len(rows) != 600:
        raise ValueError('All 600 native scalar targets must remain in CSV.')
    with prefix.with_suffix('.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    metadata = dict(status='SAVED_RESULTS_NO_SOLVES', physics_calls=0, original_rows=100,
        known_operating_coordinates=98, initial_unknown_coordinates=2, scalar_targets=600,
        finite_predictions=sum(row['predicted'] is not None for row in rows),
        mesh_selection='Predeclared nominal80 finer mesh; no selection by reference agreement.',
        statuses=dict(Counter(job['result']['status'] for job in selected)), statistics=statistics,
        source_pins=[pin(plan_path), pin(report_path)], script=pin(Path(__file__)),
        outputs=[pin(prefix.with_suffix(suffix)) for suffix in ('.png','.svg','.csv')])
    prefix.with_suffix('.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in metadata.items() if k not in ('source_pins','script','outputs','statistics')}, indent=2))


if __name__ == '__main__':
    main()
