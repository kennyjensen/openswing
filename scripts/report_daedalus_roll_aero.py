"""Report aerodynamic-only first variation at 1.5 Hz, retaining its scope."""
import argparse
from check_daedalus_load_sensitivity import ROOT, read
from check_daedalus_roll_aero import STUDY
from daedalus_bounded_job import run


def report(folder, args):
    import csv
    import numpy as np
    projection = read(STUDY/'project/result.json')
    b = np.array(projection['baseline_real'])+1j*np.array(projection['baseline_imag'])
    observed = projection['full_mesh_comparison']
    f = np.array(observed['refined_output_real'])+1j*np.array(observed['refined_output_imag'])
    delta = f-b
    actual = 100*(abs(f)/abs(b)-1)
    actual_complex = 100*abs(delta)/abs(b)
    rows = []; components = []; checks = []; original_mean_errors = []
    for factor, tag in [(1,'shape-1-v2'), (2,'shape-2'), (4,'shape-4-joined')]:
        shape = read(STUDY/tag/'result.json'); loads = read(STUDY/f'loads-{factor}'/'result.json')
        for name in (tag, f'loads-{factor}'):
            t = read(STUDY/name/'terminal.json'); assert t['returncode']==0 and t['process_reaped'] and t['inputs_unchanged']
        assert shape['frequency_hz']==loads['frequency_hz']==1.5
        assert loads['circulation_directional_error']<2e-8
        with np.load(STUDY/f'loads-{factor}'/'arrays.npz') as current:
            with np.load(ROOT/f'artifacts/daedalus-aero-feedback-20261113/capture-{factor}/arrays.npz') as earlier:
                e = float(np.max(abs(current['base_wrenches']-earlier['base_wrenches'])))
                assert e < 2e-9, (factor, e)
                original_mean_errors.append(dict(factor=factor, maximum_base_wrench_error=e))
        checks.append(dict(factor=factor, shape=shape, loads=loads))
    for row in projection['comparisons']:
        change = np.array(row['change_real'])+1j*np.array(row['change_imag'])
        group = np.array(row['component_output_real'])+1j*np.array(row['component_output_imag'])
        assert np.max(abs(group.sum(axis=1)-change)) < 2e-12
        for i, channel in enumerate(projection['channels']):
            rows.append(dict(channel=channel, aerodynamic_panels=row['panels'], baseline_magnitude=float(abs(b[i])),
                aerodynamic_amplitude_first_variation_percent=float(100*(change[i]/b[i]).real),
                aerodynamic_phase_first_variation_deg=float(np.rad2deg((change[i]/b[i]).imag)),
                aerodynamic_complex_first_variation_percent=float(100*abs(change[i])/abs(b[i])),
                full_mesh_and_retrim_amplitude_change_percent=float(actual[i]),
                full_mesh_and_retrim_complex_change_percent=float(actual_complex[i]),
                projection_on_full_mesh_change_percent=float(100*(change[i]*delta[i].conjugate()).real/abs(delta[i])**2)))
        for j, name in enumerate(projection['groups']):
            components.append(dict(group=name, aerodynamic_panels=row['panels'],
                roll_amplitude_first_variation_percent=float(100*(group[1,j]/b[1]).real),
                roll_phase_first_variation_deg=float(np.rad2deg((group[1,j]/b[1]).imag)),
                roll_complex_change_real=float(group[1,j].real), roll_complex_change_imag=float(group[1,j].imag)))
    for filename, values in [('comparison.csv', rows), ('roll-components.csv', components)]:
        with (folder/filename).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0])); writer.writeheader(); writer.writerows(values)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12.3, 4.8), layout='constrained')
    positions = np.arange(4); width = .24
    colors = ['#ff4a3d','#ff9f1a','#ffd166']
    axes[0].bar(positions-width, actual, width, color=colors[0], edgecolor='#555', linewidth=.5, label='Full mesh + retrim: actual')
    for j, row in enumerate(projection['comparisons']):
        axes[0].bar(positions+j*width, row['magnitude_first_variation_percent'], width,
            color=colors[j+1], edgecolor='#555', linewidth=.5, label=f"Aero {row['panels']} panels: first variation")
    axes[0].set(xticks=positions, xticklabels=['Yaw','Roll','Sideslip','Bank'], ylabel='Amplitude change / original amplitude (%)', title='Aerodynamic-only versus full-grid changes at 1.5 Hz')
    positions = np.arange(len(projection['groups'])); width = .34
    for j, panels in enumerate([164,328]):
        values = [r['roll_amplitude_first_variation_percent'] for r in components if r['aerodynamic_panels']==panels]
        axes[1].bar(positions+(j-.5)*width, values, width, color=colors[j+1], edgecolor='#555', linewidth=.5, label=f'{panels} aerodynamic panels')
    axes[1].set(xticks=positions, xticklabels=['Wing','Stabilizer','Fin','Boom','Fairing','Points /\nengines'],
        ylabel='Roll-amplitude first variation (percentage points)', title='Contributions to the aerodynamic correction')
    for ax in axes:
        ax.axhline(0, color='#444', linewidth=.8); ax.grid(axis='y', alpha=.2); ax.set_axisbelow(True); ax.legend(fontsize=8)
    fig.suptitle('Fixed original structure and equilibrium; first variations are not refined-aircraft Bode solutions', fontsize=11)
    fig.savefig(folder/'roll-aero-refinement.png', dpi=150); fig.savefig(folder/'roll-aero-refinement.svg'); plt.close(fig)
    result = dict(frequency_hz=1.5, comparisons=rows, roll_components=components, checks=checks,
        original_mean_wrench_replays=original_mean_errors,
        scope='Fine aerodynamic circulation is solved at prescribed coarse structural motion; complete loads are conservatively projected through the full original descriptor. This is a derivative at zero of an affine operator interpolation, not full recoupling or retrim.',
        qualifications=['Projection onto the observed whole-mesh change is a diagnostic scalar, not an exact partition of its causes.',
            'The whole-mesh comparison also changes structure, body discretization and equilibrium. Denominators here use the original magnitude for both complex changes.',
            'No physical parameter, reference tolerance, production default or ISAE completion count is changed.'])
    print(rows, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--tag', required=True); args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_roll_aero.py', STUDY/'project/result.json',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json']
    for factor, tag in [(1,'shape-1-v2'),(2,'shape-2'),(4,'shape-4-joined')]:
        inputs += [STUDY/name/p for name in [tag,f'loads-{factor}'] for p in ['arrays.npz','result.json','terminal.json']]
        inputs += [ROOT/f'artifacts/daedalus-aero-feedback-20261113/capture-{factor}/arrays.npz']
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__': main()
