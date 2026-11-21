"""Compare saved Daedalus speed cases; no physical evaluations or solves.

Inputs are base reports and primitive-yaw sample lists. This produces a
descriptive comparison, not a matched-reference or convergence verdict.
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
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
import numpy as np


def read(path):
    return json.loads(path.read_text())


def pin(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def phase(values):
    result = np.full(len(values), np.nan)
    start = 0
    for stop in range(len(values)+1):
        if stop == len(values) or not np.isfinite(values[stop]) or values[stop] == 0:
            if stop > start:
                result[start:stop] = np.degrees(np.unwrap(np.angle(values[start:stop])))
            start = stop+1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['baseline-base', 'candidate-base', 'baseline-samples', 'candidate-samples', 'output-prefix']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bases = [read(args.baseline_base), read(args.candidate_base)]
    samples = [read(args.baseline_samples), read(args.candidate_samples)]
    expected = bases[0]['equilibrium_state']['identity']
    assert bases[1]['equilibrium_state']['identity'] == expected, 'Model or mesh differs.'
    frequencies = np.array([row['frequency_Hz'] for row in samples[0]])
    assert np.all(np.diff(frequencies) > 0)
    assert np.array_equal(frequencies, [row['frequency_Hz'] for row in samples[1]])
    responses = [np.array([complex(row['real_rad_s_per_F3'], row['imag_rad_s_per_F3'])
        if row['available'] else complex(np.nan, np.nan) for row in rows]) for rows in samples]
    speeds = [base['operating_values']['speed'] for base in bases]
    labels = [f'{value*.3048:.3f} m/s ({value:.5g} ft/s)' for value in speeds]
    valid = np.isfinite(responses[0]) & np.isfinite(responses[1])
    ratio_valid = valid & (abs(responses[0]) > 0)
    absolute = np.full(len(frequencies), np.nan)
    relative = absolute.copy()
    magnitude = absolute.copy()
    absolute[valid] = abs(responses[1][valid]-responses[0][valid])
    relative[ratio_valid] = absolute[ratio_valid]/abs(responses[0][ratio_valid])
    magnitude[ratio_valid] = abs(abs(responses[1][ratio_valid])-abs(responses[0][ratio_valid]))/abs(responses[0][ratio_valid])
    extrema = {}
    for name, values in [('absolute_complex_rad_s_per_F3', absolute),
                         ('relative_complex', relative), ('relative_magnitude', magnitude)]:
        if np.isfinite(values).any():
            index = int(np.nanargmax(values))
            extrema[name] = dict(frequency_Hz=float(frequencies[index]), value=float(values[index]))
        else:
            extrema[name] = None

    node_sets = [base['nodes'] for base in bases]
    assert [(n['beam'], n['t'], n['jig_position']) for n in node_sets[0]] == [
        (n['beam'], n['t'], n['jig_position']) for n in node_sets[1]]
    positions = [np.array([n['position'] for n in nodes]) for nodes in node_sets]
    rotations = [np.array([n['rotation'] for n in nodes]) for nodes in node_sets]
    distances = np.linalg.norm(positions[1]-positions[0], axis=1)
    cosines = (np.einsum('nij,nij->n', *rotations)-1)/2
    angles = np.degrees(np.arccos(np.clip(cosines, -1, 1)))
    trim_keys = ['alpha', 'beta', 'attitude.bank', 'attitude.elevation', 'control.2', 'control.3', 'power.1']
    trim = {key:dict(baseline=bases[0]['operating_values'][key], candidate=bases[1]['operating_values'][key]) for key in trim_keys}
    wing = [[n for n in nodes if n['beam'] == 1] for nodes in node_sets]
    wing_root = [next(n for n in nodes if n['t'] == 0) for nodes in wing]
    tip_heights = []
    for nodes, center in zip(wing, wing_root):
        tip_heights.append({str(node['t']):node['position'][2]-center['position'][2]
            for node in (nodes[0], nodes[-1])})

    reference_path = root/'docs/validation/daedalus-rudder-reference.csv'
    with reference_path.open() as stream:
        reference = list(csv.DictReader(stream))
    ref_f = np.array([float(row['frequency_Hz']) for row in reference])
    ref_h = np.array([float(row['yaw_magnitude_deg_s_per_file_F3']) for row in reference])
    anchors = []
    for f in (.1, 1., 8.90352386262554, 10.):
        hits = np.flatnonzero(frequencies == f)
        if not len(hits):
            continue
        index = int(hits[0])
        anchors.append(dict(frequency_Hz=f,
            baseline_magnitude_deg_s_per_F3=float(np.degrees(abs(responses[0][index]))) if np.isfinite(responses[0][index]) else None,
            candidate_magnitude_deg_s_per_F3=float(np.degrees(abs(responses[1][index]))) if np.isfinite(responses[1][index]) else None,
            drawing_magnitude_deg_s_per_F3=float(np.exp(np.interp(np.log(f), np.log(ref_f), np.log(ref_h)))),
            relative_complex_change=float(relative[index]) if ratio_valid[index] else None))

    palette_path = root/'web/plot-colors.js'
    palette = re.search(r'plotColors = Object.freeze\(\[([^]]+)', palette_path.read_text()).group(1)
    colors = re.findall(r"'([^']+)'", palette)[:2]
    plt.rcParams.update({'font.size':10, 'text.color':'#e8edf2', 'axes.labelcolor':'#e8edf2',
        'xtick.color':'#cbd5e1', 'ytick.color':'#cbd5e1', 'axes.edgecolor':'#718096',
        'figure.facecolor':'#17212b', 'axes.facecolor':'#17212b', 'savefig.facecolor':'#17212b'})
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), layout='constrained',
        gridspec_kw={'height_ratios':[1.4, 1, .85]})
    axes[0].loglog(ref_f, ref_h, ':', color='#d6dde5', linewidth=1.4,
        label='Drela drawing: operating point unspecified')
    for i, (values, label, nodes, center) in enumerate(zip(responses, labels, wing, wing_root)):
        style = '--' if i == 0 else '-'
        axes[0].loglog(frequencies, np.degrees(abs(values)), style, color=colors[i], label=label)
        axes[1].semilogx(frequencies, phase(values), style, color=colors[i])
        axes[2].plot([n['position'][1] for n in nodes],
            [n['position'][2]-center['position'][2] for n in nodes], style, color=colors[i], label=label)
    axes[0].set(ylabel='Yaw magnitude [deg/s per F3]', title='Daedalus: speed sensitivity at 16 panels per beam', xlim=(.1, 10))
    low, high = axes[0].get_ylim()
    axes[0].set_ylim(10**np.floor(np.log10(low)), 10**np.ceil(np.log10(high)))
    axes[1].set(xlabel='Frequency [Hz]', ylabel='Unwrapped phase [degrees]', xlim=(.1, 10))
    axes[2].set(xlabel='Loaded wing axis y [ft]', ylabel='Height above wing root [ft]', title='Steady elastic-axis shape in the body frame')
    for axis in [axes[0].xaxis, axes[0].yaxis, axes[1].xaxis]:
        axis.set_major_locator(LogLocator(base=10))
        axis.set_major_formatter(FuncFormatter(lambda value, position: f'{value:g}'))
        axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
        axis.set_minor_formatter(NullFormatter())
    for ax in axes:
        ax.grid(which='major', color='#536273', linewidth=.6, alpha=.7)
        ax.grid(which='minor', color='#384858', linewidth=.4, alpha=.7)
    axes[0].legend(fontsize=8.5, facecolor='#17212b', edgecolor='#536273')
    fig.get_layout_engine().set(rect=(0, .07, 1, .90))
    fig.text(.5, .025, 'Separately trimmed steady free flight; fixed PG Mach 0.1; unchanged literal dae.asw.\n'
        'Design cruise is a declared sensitivity case, not the identified reference state. Mesh convergence remains open.',
        ha='center', va='center', fontsize=8.5)
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for extension in ('svg', 'png', 'pdf'):
        fig.savefig(prefix.with_suffix('.'+extension), dpi=170)
    plt.close(fig)

    rows = []
    for i, frequency in enumerate(frequencies):
        row = dict(frequency_Hz=float(frequency))
        for name, values in zip(['baseline', 'candidate'], responses):
            value = values[i]
            row[name+'_resolved'] = bool(np.isfinite(value))
            row[name+'_real_rad_s_per_F3'] = float(value.real) if np.isfinite(value) else ''
            row[name+'_imag_rad_s_per_F3'] = float(value.imag) if np.isfinite(value) else ''
        for name, values in [('absolute_complex_rad_s_per_F3', absolute), ('relative_complex_change', relative), ('relative_magnitude_change', magnitude)]:
            row[name] = float(values[i]) if np.isfinite(values[i]) else ''
        rows.append(row)
    with prefix.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(status='DESCRIPTIVE_SPEED_SENSITIVITY_REFERENCE_UNMATCHED',
        speeds_ft_s=speeds, samples=len(frequencies), comparison_denominator='abs(H_baseline30ft_s), undefined at exact zero',
        extrema=extrema, anchors=anchors, trim=trim,
        shape=dict(max_node_position_change_ft=float(max(distances)),
            max_node_rotation_change_deg=float(max(angles)), wing_tip_heights_above_root_ft=tip_heights,
            scope='Same nodes in aircraft body coordinates; Earth attitude reported separately.'),
        drawing_interpolation='Log-linear interpolation of the digitized PDF-vector curve for displayed anchors; no reference phase or operating-point identity.',
        scientific_acceptance=False,
        evidence_pins={str(p):pin(p) for p in [Path(__file__),args.baseline_base,args.candidate_base,
            args.baseline_samples,args.candidate_samples,reference_path,palette_path]})
    prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status=report['status'], extrema=extrema, anchors=anchors, shape=report['shape']), indent=2))


if __name__ == '__main__':
    main()
