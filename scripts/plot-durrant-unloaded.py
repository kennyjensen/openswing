"""Plot pinned unloaded wing comparisons; no calculations or parameter fitting."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Output prefix, without suffix')
    args = parser.parse_args()
    manifest = args.results/'run.json'
    run = json.loads(manifest.read_text())
    if run['status'] != 'computed':
        raise ValueError('A completed comparison record is required.')
    variants = ['arithmetic_integrated', 'glauert_cp', 'glauert_circulation', 'glauert_all']
    labels = ['Arithmetic baseline', 'Glauert control point', 'Glauert + circulation loads', 'Glauert + all airloads']
    colors = ['#777777', '#bc6c25', '#6b52a3', '#007f86']
    cases, inputs = {}, {str(manifest): sha(manifest)}
    for item in run['cases']:
        file = args.results/item['file']
        if sha(file) != item['sha256']:
            raise ValueError('Changed case: '+str(file))
        inputs[str(file)] = item['sha256']
        case = json.loads(gzip.decompress(file.read_bytes()))
        spec = case['spec']
        if case['reference']['eigensystem']['scaling'] != 'energy_convective':
            raise ValueError('Figure requires the verified energy-scaled reference.')
        if case['status'] != 'computed' or spec['wing'] != '25' or spec['speed_m_s'] != 24:
            raise ValueError('The figure requires the declared unloaded 25% wing at 24 m/s.')
        comparison = case['comparisons'][0]
        if comparison['status'] != 'compared' or len(comparison['pairs']) != 2:
            raise ValueError('Expected two compared low-frequency modes.')
        pairs = sorted(comparison['pairs'], key=lambda pair: pair['reference_root_per_s'][1])
        if not all(pair['resolved_assignment'] for pair in pairs):
            raise ValueError('Cannot draw an unresolved mode assignment as a matched trace.')
        key = (spec['sampling'], spec['mechanical_elements'])
        if key in cases:
            raise ValueError('Duplicate sampling/grid case.')
        cases[key] = pairs
    if set(cases) != {(v, n) for v in variants for n in [8,16,32]}:
        raise ValueError('The figure requires all twelve declared sampling/grid cases.')

    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.6))
    fig.subplots_adjust(top=.88, bottom=.13, left=.085, right=.98, hspace=.42, wspace=.28)
    grid = [8,16,32]
    for mode, ax in enumerate(axes[0]):
        for variant, label, color in zip(variants, labels, colors):
            errors = [100*cases[(variant,n)][mode]['scaled_root_difference'] for n in grid]
            ax.plot(grid, errors, 'o-', label=label, color=color)
        ax.set_yscale('log')
        ax.set(ylabel='Complex-root difference (%)', title=f'Matched low mode {mode+1}: sampling sensitivity')
    for mode, color in enumerate(['#007f86','#994f92']):
        for kind, style in [('native','o-'),('reference','s--')]:
            roots = np.array([complex(*cases[('glauert_all',n)][mode][kind+'_root_per_s']) for n in grid])
            label = f'Mode {mode+1}, '+('production' if kind=='native' else 'independent')
            axes[1,0].plot(grid, roots.real, style, color=color, label=label)
            axes[1,1].plot(grid, roots.imag/(2*np.pi), style, color=color, label=label)
    axes[1,0].set(ylabel='Growth rate (1/s)',title='Full Glauert sampling: damping')
    axes[1,1].set(ylabel='Frequency (Hz)',title='Full Glauert sampling: frequency')
    for ax in axes.ravel():
        ax.set(xlabel='Requested mechanical / aerodynamic intervals',xticks=grid,xlim=(6,34))
        ax.grid(alpha=.2,which='both')
    axes[0,0].legend(frameon=False,fontsize=8,loc='lower left')
    axes[1,1].legend(frameon=False,fontsize=8,loc='center right')
    fig.suptitle('Independent unloaded-wing verification\n25% spar analogue, U = 24 m/s; zero incidence, camber, Cm and gravity',fontsize=14)
    fig.text(.085,.047,'Energy-scaled reference; all mechanical coordinates retained. Difference = 100 |production − independent| / |independent|.\nRequired material breaks add intervals. Local production searches do not prove full-spectrum stability; this is not loaded-flutter validation.',fontsize=9)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    outputs = {}
    for suffix in ['png','svg','pdf']:
        path = args.output.with_suffix('.'+suffix)
        fig.savefig(path,dpi=170)
        outputs[str(path)] = sha(path)
    record = dict(scope=__doc__,inputs_sha256=inputs,outputs_sha256=outputs,
                  plotter_sha256=sha(Path(__file__)),metric='100*abs(native-reference)/abs(reference)',
                  production_search_index=0,spatial_counts=grid)
    args.output.with_suffix('.provenance.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__ == '__main__':
    main()
