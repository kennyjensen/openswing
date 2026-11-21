"""Compare every plotted FW root at 64 ft/s, keeping unmatched roots visible."""
import argparse
import ast
import json
from pathlib import Path
import runpy

from check_daedalus_load_sensitivity import ROOT, pin, write
from check_fw_modes_20261114 import STUDY, GROUPS
from daedalus_bounded_job import run

JOBS = ['slow', 'damped', 'low-oscillatory', 'oscillatory']


def report(folder, args):
    import numpy as np
    from scipy.optimize import linear_sum_assignment
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    reference_path = ROOT/'docs/validation/fw-reference.json'
    reference = json.loads(reference_path.read_text())
    # Re-extract PDF markers, without invoking the extractor's file-writing CLI.
    extracted = runpy.run_path(str(ROOT/'scripts/extract-fw-reference.py'))['extract']()
    # JSON stores the extractor's tuple coordinates as arrays.
    assert json.loads(json.dumps(extracted, allow_nan=False)) == reference
    published = next(p for p in reference['points'] if p['speed_ft_s'] == 64.)
    roots = np.array([complex(*r) for r in published['plotted_roots_per_s']])
    source = ROOT/'scripts/check_fw_modes_20261114.py'
    current_functions = {n.name: ast.dump(n) for n in ast.parse(source.read_text()).body
                         if isinstance(n, ast.FunctionDef)}
    records, checks, terminals, verified, runner_pins = [], [], [], {}, {}
    for tag in JOBS:
        for suffix in ('', '-directions'):
            job = STUDY/(tag+suffix)
            terminal = json.loads((job/'terminal.json').read_text())
            assert terminal['returncode'] == 0 and terminal['process_reaped']
            assert terminal['inputs_unchanged'] and not terminal['timed_out']
            terminals.append(terminal)
            plan = json.loads((job/'plan.json').read_text())
            for name, sha in plan['inputs_sha256'].items():
                if Path(name) == source:
                    saved = job/'runner.py'
                    assert pin(saved) == sha
                    old = ast.parse(saved.read_text())
                    for node in old.body:
                        if isinstance(node, ast.FunctionDef):
                            assert ast.dump(node) == current_functions[node.name]
                        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GROUPS' for t in node.targets):
                            assert all(GROUPS[k] == v for k,v in ast.literal_eval(node.value).items())
                    runner_pins[str(saved)] = sha
                elif name not in verified:
                    assert pin(Path(name)) == sha, name
                    verified[name] = sha
                else:
                    assert verified[name] == sha
            data = json.loads((job/'result.json').read_text())
            if suffix:
                checks += [dict(job=tag, **r) for r in data['checks']]
            else:
                records += [dict(job=tag, index=i, **row) for i,row in enumerate(data['modes'])]
    candidates = np.array([complex(*r['eigenvalue']) for r in records])
    distances = abs(roots[:, None]-candidates[None, :])
    rows, cols = linear_sum_assignment(distances)
    assert len(rows) == 9
    comparisons = []
    for i,j in zip(rows,cols):
        reference_value, value = roots[i], candidates[j]
        delta = value-reference_value
        comparisons.append(dict(label=f'R{i+1}', reference=published['plotted_roots_per_s'][i],
            current=records[j]['eigenvalue'], job=records[j]['job'], index=records[j]['index'],
            difference=[float(delta.real),float(delta.imag)],
            relative_complex_distance_percent=float(100*abs(delta)/abs(reference_value)),
            growth_relative_error_percent=None if abs(reference_value.real)<.01 else float(100*delta.real/reference_value.real),
            frequency_relative_error_percent=None if abs(reference_value.imag)<.01 else float(100*delta.imag/reference_value.imag),
            second_nearest_distance=float(np.sort(distances[i])[1]),
            matched_distance=float(distances[i,j])))
    unmatched = [r for j,r in enumerate(records) if j not in cols]
    assert len(unmatched) == 1
    assert all(row['accepted'] for row in checks)
    fig, axes = plt.subplots(1,2,figsize=(10.5,6),gridspec_kw={'width_ratios':[1.4,1]})
    for ax, subset, title in [(axes[0], comparisons, 'All nine plotted roots'),
                              (axes[1], comparisons[:3], 'Slow modes, enlarged')]:
        ref = np.array([c['reference'] for c in subset])
        got = np.array([c['current'] for c in subset])
        ax.scatter(ref[:,0],ref[:,1],s=65,facecolors='none',edgecolors='#555555',
                   linewidths=1.6,label="Drela's root map",zorder=3)
        ax.scatter(got[:,0],got[:,1],s=45,marker='x',color='#007fba',
                   linewidths=1.7,label='Current OpenSwing',zorder=4)
        for c,a,b in zip(subset,ref,got):
            ax.plot([a[0],b[0]],[a[1],b[1]],color='#007fba',linewidth=.8,zorder=2)
            if ax is axes[1] or c['label'] not in ('R1','R2','R3'):
                ax.annotate(c['label'],a,xytext=(6,7),textcoords='offset points',fontsize=9)
        ax.axhline(0,color='#999999',linewidth=.8)
        ax.axvline(0,color='#999999',linewidth=.8)
        ax.grid(True,color='#dedede',linewidth=.7)
        ax.set_xlabel('Growth rate, σ (1/s)')
        ax.set_ylabel('Angular frequency, ω (rad/s)')
        ax.set_title(title,fontsize=12)
    axes[0].scatter([r['eigenvalue'][0] for r in unmatched],[r['eigenvalue'][1] for r in unmatched],
                    marker='^',color='#9a6546',s=45,label='Additional root; no plotted match')
    axes[0].set_xlim(-18,2.5);axes[0].set_ylim(-1.8,29)
    axes[0].legend(loc='upper left',fontsize=8)
    axes[1].set_xlim(-.22,.005);axes[1].set_ylim(-.035,.60)
    fig.suptitle('FW at 64 ft/s · current 42-panel model',fontsize=15)
    fig.text(.5,.025,'R1–R9 identify plotted points, not assigned physical mode names.\n'
             'Inferred glide trim; native mesh unspecified; this is not a Bode gain/phase comparison.',
             ha='center',fontsize=9,color='#444444')
    fig.tight_layout(rect=(0,.08,1,.94))
    fig.savefig(folder/'comparison.png',dpi=160)
    fig.savefig(folder/'comparison.svg')
    plt.close(fig)
    write(folder/'checks.json',checks)
    write(folder/'source-pins.json',dict(inputs=verified,runners=runner_pins))
    return dict(scope='All nine plotted roots at 64 ft/s only; one additional current root retained separately.',
        reference_extraction_rechecked=True, comparisons=comparisons, unmatched=unmatched,
        maximum_relative_complex_distance_percent=max(r['relative_complex_distance_percent'] for r in comparisons),
        maximum_frequency_error_percent=max(abs(r['frequency_relative_error_percent']) for r in comparisons if r['frequency_relative_error_percent'] is not None),
        direct_residual_checks=len(checks),direct_residual_passed=sum(r['accepted'] for r in checks),
        maximum_scaled_direct_residual=max(r['scaled_full_mode_residual'] for r in checks),
        maximum_pencil_backward_error=max(max(r['right_backward_error'],r['left_backward_error']) for r in records),
        completed_solver_jobs=len(terminals),
        max_solver_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        max_solver_wall_seconds=max(t['wall_seconds'] for t in terminals),
        max_solver_rss_kib=max(t['peak_rss_kib'] for t in terminals),
        limitation='Complex-distance agreement does not imply a 5% relative match of each near-zero growth coordinate. Full speed progression and native forced responses remain open.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_fw_modes_20261114.py',ROOT/'scripts/extract-fw-reference.py',
            ROOT/'docs/validation/fw-reference.json',ROOT/'reference/root_map_fw.pdf']
    for tag in JOBS:
        for suffix in ('','-directions'):
            inputs += [STUDY/(tag+suffix)/name for name in ('result.json','plan.json','terminal.json','runner.py')]
    run(STUDY,args['tag'],inputs,report,args,__file__)
