"""Plot saved, separately trimmed Daedalus meshes without evaluating the model.

Both base reports must contain their physical equilibrium packets. The report
checks the literal model and prescribed condition, while allowing the seven
steady-level trim coordinates and the mesh to differ. This is a descriptive
comparison; two meshes do not establish convergence or reference agreement.
"""
import argparse
from copy import deepcopy
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


TRIM = ['alpha', 'attitude.bank', 'power.1', 'beta', 'control.2',
        'control.3', 'attitude.elevation']


def read(path):
    return json.loads(path.read_text())


def pin(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def prescribed(base):
    launch = deepcopy(base['equilibrium_state']['launch'])
    assert [row['variable'] for row in launch['released_constraints']] == TRIM
    launch.pop('panels')
    condition = launch['condition']
    for name in ('alpha', 'beta'):
        condition.pop(name)
    condition['attitude'][:2] = [None, None]
    for key in ('2', '3'):
        condition['controls'].pop(key)
    condition['powers'].pop('1')
    return launch


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
    for name in ('coarse-base', 'fine-base', 'coarse-samples', 'fine-samples', 'output-prefix'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    bases = [read(args.coarse_base), read(args.fine_base)]
    samples = [read(args.coarse_samples), read(args.fine_samples)]
    packets = [base['equilibrium_state'] for base in bases]
    assert packets[0]['identity']['model_sha256'] == packets[1]['identity']['model_sha256']
    assert packets[0]['units'] == packets[1]['units']
    assert prescribed(bases[0]) == prescribed(bases[1]), 'Prescribed conditions differ.'
    assert bases[0]['atmosphere']['density'] == bases[1]['atmosphere']['density']
    assert all(base['modal_base']['frame'] == 'free' and
               base['modal_base']['kinematically_steady'] for base in bases)
    panels = [packet['launch']['panels'] for packet in packets]
    assert panels[1] > panels[0]
    frequencies = np.array([row['frequency_Hz'] for row in samples[0]])
    assert np.isfinite(frequencies).all() and (frequencies > 0).all()
    assert (np.diff(frequencies) > 0).all()
    assert np.array_equal(frequencies, [row['frequency_Hz'] for row in samples[1]])
    values = [np.array([complex(row['real_rad_s_per_F3'], row['imag_rad_s_per_F3'])
                       if row['available'] else complex(np.nan, np.nan) for row in rows])
              for rows in samples]
    valid = np.isfinite(values[0]) & np.isfinite(values[1])
    ratio_valid = valid & (abs(values[1]) > 0)
    absolute = np.full(len(frequencies), np.nan)
    relative = absolute.copy()
    magnitude = absolute.copy()
    absolute[valid] = abs(values[1][valid]-values[0][valid])
    relative[ratio_valid] = absolute[ratio_valid]/abs(values[1][ratio_valid])
    magnitude[ratio_valid] = abs(abs(values[1][ratio_valid])-abs(values[0][ratio_valid]))/abs(values[1][ratio_valid])
    extrema = {}
    for name, data in [('absolute_complex_rad_s_per_F3', absolute),
                       ('relative_complex', relative), ('relative_magnitude', magnitude)]:
        if np.isfinite(data).any():
            index = int(np.nanargmax(data))
            extrema[name] = dict(frequency_Hz=float(frequencies[index]), value=float(data[index]))
        else:
            extrema[name] = None

    reference_path = root/'docs/validation/daedalus-rudder-reference.csv'
    with reference_path.open() as stream:
        reference = list(csv.DictReader(stream))
    ref_f = np.array([float(row['frequency_Hz']) for row in reference])
    ref_h = np.array([float(row['yaw_magnitude_deg_s_per_file_F3']) for row in reference])
    anchors = []
    for frequency in (.1, 1., 8.90352386262554, 10.):
        hits = np.flatnonzero(frequencies == frequency)
        if not len(hits):
            continue
        index = int(hits[0])
        anchors.append(dict(frequency_Hz=frequency,
            coarse_magnitude_deg_s_per_F3=float(np.degrees(abs(values[0][index]))) if np.isfinite(values[0][index]) else None,
            fine_magnitude_deg_s_per_F3=float(np.degrees(abs(values[1][index]))) if np.isfinite(values[1][index]) else None,
            drawing_magnitude_deg_s_per_F3=float(np.exp(np.interp(np.log(frequency), np.log(ref_f), np.log(ref_h)))),
            relative_complex_change=float(relative[index]) if ratio_valid[index] else None))
    minima = {}
    for name, freq, mag in [('coarse', frequencies, np.degrees(abs(values[0]))),
                            ('fine', frequencies, np.degrees(abs(values[1]))),
                            ('drawing', ref_f, ref_h)]:
        eligible = np.flatnonzero((freq >= .7) & (freq <= 2) & np.isfinite(mag))
        index = int(eligible[np.argmin(mag[eligible])]) if len(eligible) else None
        minima[name] = None if index is None else dict(frequency_Hz=float(freq[index]),
            magnitude_deg_s_per_F3=float(mag[index]))

    palette_path = root/'web/plot-colors.js'
    palette = re.search(r'plotColors = Object.freeze\(\[([^]]+)', palette_path.read_text()).group(1)
    colors = re.findall(r"'([^']+)'", palette)[:2]
    plt.rcParams.update({'font.size':10, 'text.color':'#e8edf2', 'axes.labelcolor':'#e8edf2',
        'xtick.color':'#cbd5e1', 'ytick.color':'#cbd5e1', 'axes.edgecolor':'#718096',
        'figure.facecolor':'#17212b', 'axes.facecolor':'#17212b', 'savefig.facecolor':'#17212b'})
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), layout='constrained',
        gridspec_kw={'height_ratios':[1.4, 1, .8]}, sharex=True)
    axes[0].loglog(ref_f, ref_h, ':', color='#d6dde5', linewidth=1.4,
        label='Drela drawing: operating point unspecified')
    for i, (data, count) in enumerate(zip(values, panels)):
        style = '--' if i == 0 else '-'
        mag = np.degrees(abs(data))
        axes[0].loglog(frequencies, np.where(mag > 0, mag, np.nan), style,
            color=colors[i], label=f'{count} panels per beam')
        axes[1].semilogx(frequencies, phase(data), style, color=colors[i])
    axes[2].semilogx(frequencies, 100*relative, color=colors[1])
    speed = packets[0]['launch']['condition']['speed']
    axes[0].set(ylabel='Yaw magnitude [deg/s per F3]',
        title=f'Daedalus: mesh sensitivity at {speed*.3048:g} m/s', xlim=(.1, 10))
    low, high = axes[0].get_ylim()
    axes[0].set_ylim(10**np.floor(np.log10(low)), 10**np.ceil(np.log10(high)))
    axes[1].set(ylabel='Unwrapped phase [degrees]')
    axes[2].set(xlabel='Frequency [Hz]', ylabel='Complex mesh change [%]', ylim=(0, None))
    for axis in [axes[0].xaxis, axes[0].yaxis, axes[1].xaxis, axes[2].xaxis]:
        axis.set_major_locator(LogLocator(base=10))
        axis.set_major_formatter(FuncFormatter(lambda value, position: f'{value:g}'))
        axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
        axis.set_minor_formatter(NullFormatter())
    for ax in axes:
        ax.tick_params(axis='x', labelbottom=True)
        ax.grid(which='major', color='#536273', linewidth=.6, alpha=.7)
        ax.grid(which='minor', color='#384858', linewidth=.4, alpha=.7)
    axes[0].legend(fontsize=8.5, facecolor='#17212b', edgecolor='#536273')
    fig.get_layout_engine().set(rect=(0, .07, 1, .89))
    fig.text(.5, .025, 'Separately trimmed steady free flight; fixed PG Mach 0.1; unchanged literal dae.asw.\n'
        'Complex change = |Hfine − Hcoarse| / |Hfine|. Convergence and reference agreement remain open.',
        ha='center', va='center', fontsize=8.5)
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    for extension in ('svg', 'png', 'pdf'):
        fig.savefig(prefix.with_suffix('.'+extension), dpi=170)
    plt.close(fig)

    rows = []
    for i, frequency in enumerate(frequencies):
        row = dict(frequency_Hz=float(frequency))
        for name, data in zip(['coarse', 'fine'], values):
            value = data[i]
            row[name+'_resolved'] = bool(np.isfinite(value))
            row[name+'_real_rad_s_per_F3'] = float(value.real) if np.isfinite(value) else ''
            row[name+'_imag_rad_s_per_F3'] = float(value.imag) if np.isfinite(value) else ''
        for name, data in [('absolute_complex_rad_s_per_F3', absolute),
                           ('relative_complex_change', relative), ('relative_magnitude_change', magnitude)]:
            row[name] = float(data[i]) if np.isfinite(data[i]) else ''
        rows.append(row)
    with prefix.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = dict(status='DESCRIPTIVE_MESH_SENSITIVITY_REFERENCE_UNMATCHED',
        panels=panels, speed_ft_s=speed, samples=len(frequencies),
        resolved=[int(np.isfinite(data).sum()) for data in values],
        comparison_denominator='abs(H_fine), undefined at exact zero; no floor',
        extrema=extrema, anchors=anchors, sampled_minima_window_Hz=[.7, 2.], sampled_minima=minima,
        trim={key:dict(coarse=bases[0]['operating_values'][key], fine=bases[1]['operating_values'][key]) for key in TRIM},
        drawing_interpolation='Log-linear interpolation of digitized PDF-vector magnitude; reference phase and operating-point identity unavailable.',
        scientific_acceptance=False,
        evidence_pins={str(p):pin(p) for p in [Path(__file__), args.coarse_base, args.fine_base,
            args.coarse_samples, args.fine_samples, reference_path, palette_path]})
    prefix.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status=report['status'], extrema=extrema, anchors=anchors,
                         sampled_minima=minima), indent=2))


if __name__ == '__main__':
    main()
