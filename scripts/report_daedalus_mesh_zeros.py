"""Quantify cancellation and bank-kinematic contributions to mesh differences."""
import argparse
from check_daedalus_load_sensitivity import ROOT, read
from check_daedalus_mesh_zeros import STUDY, ZEROS, paths, CHANNELS
from daedalus_bounded_job import run


def report(folder, args):
    import csv
    import numpy as np
    from elastic_fin_kinematics import exponential
    coarse = dict(np.load(STUDY/'coarse-samples/arrays.npz'))
    fine = dict(np.load(STUDY/'fine-samples/arrays.npz'))
    np.testing.assert_array_equal(coarse['frequencies'], fine['frequencies'])
    frequencies = coarse['frequencies']; zc = {}; zf = {}
    zero_rows = []
    for name, channel, tag in [('roll', 'roll_rate', 'fine-roll-1'), ('yaw', 'yaw_rate', args['yaw_source'])]:
        old = read(ZEROS/(name+'-verify')/'result.json'); new = read(STUDY/tag/'result.json')
        assert new['converged'] and new['channel']==channel
        zc[channel] = complex(*old['zero']); zf[channel] = complex(*new['evaluated_s'])
        for width in ('wide', 'fine'):
            verified = read(STUDY/('fine-'+name+'-check-'+width)/'result.json')
            assert verified['zero'] == new['evaluated_s'] and verified['full_residual_relative'] < 1e-9
            assert verified['output_magnitude'] < 1e-10
        zero_rows.append(dict(channel=channel, coarse=[zc[channel].real, zc[channel].imag],
            fine=[zf[channel].real, zf[channel].imag],
            coarse_imaginary_frequency_hz=zc[channel].imag/(2*np.pi),
            fine_imaginary_frequency_hz=zf[channel].imag/(2*np.pi),
            real_part_change_percent=100*(zf[channel].real/zc[channel].real-1)))
    def poly(s, z): return (s-z)*(s-z.conjugate())
    rows = []; budget = []; predicted = []; bank_closure = 0.
    ec = np.linalg.inv(coarse['euler_matrix'])[0]; ef = np.linalg.inv(fine['euler_matrix'])[0]
    for i, f in enumerate(frequencies):
        s = 2j*np.pi*f; old = coarse['outputs'][i]; new = fine['outputs'][i]
        prediction = old.copy()
        for channel in ('roll_rate', 'yaw_rate'):
            j = CHANNELS.index(channel); ratio = poly(s, zf[channel])/poly(s, zc[channel])
            prediction[j] = old[j]*ratio
            rows.append(dict(frequency_hz=float(f), channel=channel,
                coarse_magnitude=float(abs(old[j])), fine_magnitude=float(abs(new[j])),
                predicted_magnitude=float(abs(prediction[j])),
                original_complex_change_percent=float(100*abs(new[j]-old[j])/abs(new[j])),
                residual_after_zero_factor_percent=float(100*abs(new[j]-prediction[j])/abs(new[j])),
                remaining_transfer_ratio_real=float((new[j]/prediction[j]).real),
                remaining_transfer_ratio_imag=float((new[j]/prediction[j]).imag)))
        predicted.append(prediction)
        wc, wf = coarse['body_rates'][i], fine['body_rates'][i]
        scale = 180/np.pi/s
        components = np.r_[ef*(wf-wc)*scale, ((ef-ec)@wc)*scale]
        total = new[3]-old[3]; error = float(abs(components.sum()-total))
        bank_closure = max(bank_closure, error); assert error < 2e-10
        for label, value in zip(('roll_rate', 'pitch_rate', 'yaw_rate', 'equilibrium_attitude_readout'), components):
            budget.append(dict(frequency_hz=float(f), component=label, real=float(value.real), imag=float(value.imag),
                magnitude=float(abs(value)), projection_on_net_change_percent=float(100*(value*total.conjugate()).real/abs(total)**2)))
        assert abs(sum(b['projection_on_net_change_percent'] for b in budget[-4:])-100) < 2e-6
    for filename, values in [('zero-factor-comparison.csv', rows), ('bank-change-components.csv', budget)]:
        with (folder/filename).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0])); writer.writeheader(); writer.writerows(values)
    # Compare saved equilibrium geometry at common physical material stations.
    old = read(paths('coarse')[2]); new = read(paths('fine')[2]); geometry = []; matched = []
    for beam, (stations, nodes) in old['identity']['stations'].items():
        ft, fn = new['identity']['stations'][beam]; mapping = []
        for t, n in zip(stations, nodes):
            index = int(np.argmin(abs(np.asarray(ft)-t))); assert abs(ft[index]-t)<2e-12
            mapping.append((n, fn[index])); matched.append(n)
        changes = []; rotations = []
        for a, b in mapping:
            changes.append(np.linalg.norm(np.asarray(new['positions'][b])-old['positions'][a]))
            relative = exponential(np.asarray(new['rotations'][b]))@exponential(np.asarray(old['rotations'][a])).T
            sine = np.linalg.norm([relative[2,1]-relative[1,2], relative[0,2]-relative[2,0], relative[1,0]-relative[0,1]])/2
            cosine = (np.trace(relative)-1)/2
            rotations.append(np.rad2deg(np.arctan2(sine, cosine)))
        geometry.append(dict(beam=int(beam), common_nodes=len(mapping),
            maximum_position_change_ft=float(max(changes)), maximum_orientation_change_deg=float(max(rotations))))
    assert sorted(matched)==list(range(len(old['positions'])))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, NullFormatter, FuncFormatter
    predicted = np.asarray(predicted)
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.7), layout='constrained')
    colors = ['#ff4a3d', '#ff9f1a', '#ffd166']
    for value, label, color, style in [(abs(coarse['outputs'][:,1]), 'Original mesh', colors[0], '-'),
            (abs(fine['outputs'][:,1]), 'Refined mesh', colors[1], '-'),
            (abs(predicted[:,1]), 'Original response × zero-factor ratio', colors[2], '--')]:
        axes[0].loglog(frequencies, value, marker='o', ms=3, color=color, linestyle=style, label=label)
    roll = [r for r in rows if r['channel']=='roll_rate']
    for key, label, color in [('original_complex_change_percent', 'Complete mesh difference', colors[0]),
            ('residual_after_zero_factor_percent', 'Remaining after zero-factor change', colors[1])]:
        axes[1].semilogx(frequencies, [r[key] for r in roll], marker='o', ms=3, color=color, label=label)
    axes[0].set(title='Roll: cancellation shift accounts for most of the change', ylabel='Roll-rate magnitude (deg/s/F3)')
    axes[1].set(title='Complex difference relative to the refined response', ylabel='Difference (%)', ylim=(0, None))
    for ax in axes:
        ax.set(xlim=(.09, 1.8), xlabel='Frequency (Hz)')
        ax.xaxis.set_major_locator(LogLocator(base=10, numticks=4))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f'{x:g}'))
        ax.xaxis.set_minor_locator(LogLocator(base=10, subs=range(2,10), numticks=30)); ax.xaxis.set_minor_formatter(NullFormatter())
        ax.grid(which='major', alpha=.4); ax.grid(which='minor', alpha=.16); ax.legend(fontsize=8)
    axes[0].yaxis.set_major_locator(LogLocator(base=10)); axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x, pos:f'{x:g}'))
    axes[0].yaxis.set_minor_locator(LogLocator(base=10, subs=range(2,10), numticks=30)); axes[0].yaxis.set_minor_formatter(NullFormatter())
    fig.suptitle('Current Daedalus matrices; eight sampled frequencies; connecting lines are guides', fontsize=11)
    fig.savefig(folder/'roll-mesh-cancellation.png', dpi=150); fig.savefig(folder/'roll-mesh-cancellation.svg'); plt.close(fig)
    np.savez_compressed(folder/'arrays.npz', frequencies=frequencies, original=coarse['outputs'], refined=fine['outputs'], predicted=predicted)
    result = dict(zeros=zero_rows, comparisons=rows, bank_change_components=budget,
        bank_budget_closure=bank_closure, common_geometry=geometry,
        roll_maximum_unexplained_complex_change_percent=max(r['residual_after_zero_factor_percent'] for r in roll),
        qualification='Algebraically remove the independently located conjugate zero pair using a monic quadratic. No gains or frequencies are fitted. This explains differences between two computed meshes; it does not establish third-grid convergence, native ASWING zeros, or whether changed trim versus discretization caused the zero shift.')
    print(dict(zeros=zero_rows, maximum_remaining=result['roll_maximum_unexplained_complex_change_percent'], bank_budget_closure=bank_closure), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--tag', required=True)
    parser.add_argument('--yaw-source', required=True); args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_mesh_zeros.py', ROOT/'scripts/elastic_fin_kinematics.py',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json']
    for mesh in ('coarse', 'fine'):
        inputs += [paths(mesh)[2], STUDY/(mesh+'-samples')/'arrays.npz', STUDY/(mesh+'-samples')/'result.json']
    for name, tag in [('roll', 'fine-roll-1'), ('yaw', args['yaw_source'])]:
        inputs += [ZEROS/(name+'-verify')/'result.json', STUDY/tag/'result.json']
        inputs += [STUDY/('fine-'+name+'-check-'+width)/'result.json' for width in ('wide', 'fine')]
    run(STUDY, args['tag'], inputs, report, args, __file__)


if __name__ == '__main__': main()
