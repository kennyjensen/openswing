"""Report the bounded mounting-span comparison; no aircraft refit or solve."""
import argparse
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
from check_daedalus_mount_continuum import STUDY, CAPTURE, FREQUENCIES


def work(folder, args):
    import csv
    import numpy as np
    from scipy.integrate import quad
    from scipy.spatial.transform import Rotation
    from daedalus_mount_reference import Mount, hat, properties
    fine = np.load(STUDY/'continuum-12/arrays.npz')
    wide = np.load(STUDY/'continuum-10/arrays.npz')
    fixture = read(CAPTURE/'fixture.json')
    pose_scale = np.array([1/2.5]*3+[1.]*3)
    labels = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz', 'cut x', 'cut y', 'cut z', 'cut rx', 'cut ry', 'cut rz']
    tolerance = []
    for name, s in FREQUENCIES:
        ref = fine[name+'_motion'][0]*pose_scale[:, None]
        delta = (wide[name+'_motion'][0]-fine[name+'_motion'][0])*pose_scale[:, None]
        errors = np.linalg.norm(delta, axis=0)/np.maximum(np.linalg.norm(ref, axis=0), 1e-30)
        tolerance.append(float(max(errors)))
    assert max(tolerance) < 2e-7, tolerance
    # Independent zero-preload analytical compliance. The variable EI remains
    # the literal one; quadrature of 1/EI, t/EI, t^2/EI gives the closed beam
    # compliance, without using the spatial ODE or source charts.
    analytic_fixture = dict(fixture)
    q = np.array([[0., 1., 0.], [-1., 0., 0.], [0., 0., 1.]])
    analytic_fixture.update(positions=[[float(t), 0., 0.] for t in fixture['stations']],
        frames=[q.tolist() for t in fixture['stations']],
        dead_force=np.zeros((3, 3)).tolist(), dead_moment=np.zeros((3, 3)).tolist(),
        left_wrench=[0.]*6, right_wrench=[0.]*6)
    control = Mount(analytic_fixture, 1e-12)
    base, _, _ = control.equilibrium(); response, _, _ = control.response(base, 0j)
    integrals = []
    for power in range(3):
        integrals.append((q*np.array([quad(lambda t: t**power/properties(t)[0][j], 0., 2.5,
            epsabs=1e-14, epsrel=1e-12)[0] for j in range(3)]))@q.T)
    h = hat(q[:, 1]); c0, c1, c2 = integrals
    analytic = np.block([[h@c2@h, -h@c1], [c1@h, -c0]])
    analytical_error = float(np.max(abs(response[0, :6, :6]-analytic)))
    assert analytical_error < 2e-13, analytical_error
    summaries = []; rows = []; plot_values = []
    for elements in (2, 4, 8):
        native = np.load(STUDY/f'discrete-{elements}/arrays.npz')
        left_displacement = float(np.linalg.norm(native['positions'][0]-fine['base'][0, :3]))
        refq = fine['base'][0, 3:12].reshape(3, 3)
        left_rotation = float(np.linalg.norm(Rotation.from_matrix(native['frames'][0]@refq.T).as_rotvec()))
        percase = []
        for name, s in FREQUENCIES:
            expected = fine[name+'_motion'][0]
            actual = native[name+'_motion'][0]
            delta = (actual-expected)*pose_scale[:, None]
            denominator = np.linalg.norm(expected*pose_scale[:, None], axis=0)
            errors = np.linalg.norm(delta, axis=0)/np.maximum(denominator, 1e-30)
            rotation_norm = np.linalg.norm(expected[3:], axis=0)
            rotational = np.linalg.norm(actual[3:]-expected[3:], axis=0)/np.maximum(rotation_norm, 1e-30)
            entries = []
            for j, label in enumerate(labels):
                row = dict(elements=elements, case=name, input=label,
                    left_motion_relative_error=float(errors[j]),
                    left_motion_reference_norm=float(denominator[j]),
                    left_rotation_relative_error=float(rotational[j]) if rotation_norm[j]>1e-12 else None,
                    left_rotation_reference_norm=float(rotation_norm[j]),
                    max_translation_absolute_error_ft=float(max(abs(actual[:3, j]-expected[:3, j]))),
                    max_rotation_absolute_error_rad=float(max(abs(actual[3:, j]-expected[3:, j]))))
                rows.append(row); entries.append(row)
            percase.append(dict(case=name, maximum_motion_error=float(max(errors)),
                maximum_load_motion_error=float(max(errors[:6])),
                maximum_cut_motion_error=float(max(errors[6:])),
                Mz_rotation_error=float(rotational[5]), Mx_rotation_error=float(rotational[3])))
            if name == 'dip': plot_values.append((elements, errors))
        summaries.append(dict(elements=elements, left_base_displacement_error_ft=left_displacement,
            left_base_rotation_error_rad=left_rotation, cases=percase))
    with (folder/'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    result = dict(continuum_tolerance_max_relative_change=max(tolerance),
        zero_preload_analytical_compliance_absolute_error=analytical_error,
        metric='Wing-end motion norm uses translations/2.5 ft and spatial rotations. Separate unit force, moment, cut translation and cut rotation inputs; no averaging or fitted weighting across inputs.',
        summaries=summaries,
        qualification='Component mechanics only. Discrete Eq80 interval rotary inertia vanishes in the continuum limit. Original interior dead loads are retained on every mesh. No aircraft zero or Bode curve is recomputed.')
    result['maximum_separate_rotation_errors'] = {
        str(n): max(row['left_rotation_relative_error'] for row in rows
                    if row['elements'] == n and row['left_rotation_relative_error'] is not None)
        for n in (2, 4, 8)}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    colors = ['#ff4a3d', '#ff9f1a', '#ffd166']
    for (elements, errors), color in zip(plot_values, colors):
        axes[0].plot(np.arange(6), 100*errors[:6], marker='o', color=color, label=f'{elements} elements')
        axes[1].plot(np.arange(6), 100*errors[6:], marker='o', color=color, label=f'{elements} elements')
    for axis, names, title in zip(axes, [labels[:6], labels[6:]], ['Wing-end load inputs', 'Fairing-end motion inputs']):
        axis.set_xticks(np.arange(6), names); axis.set_yscale('log')
        axis.grid(True, which='both', alpha=.25); axis.set_title(title)
        axis.set_ylabel('Wing-end motion error (%)'); axis.legend()
    fig.suptitle('Daedalus mounting span versus independent continuous beam\n1.157378 Hz; fixed preload and literal material properties')
    fig.tight_layout(); fig.savefig(folder/'mount-comparison.svg'); fig.savefig(folder/'mount-comparison.png', dpi=150); plt.close(fig)
    replay = read(STUDY/'actual-forcing/result.json')
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3))
    for case, color in zip(replay['cases'], ['#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f']):
        for axis, metric in zip(axes, ['motion_error', 'relative_rotation_error']):
            axis.plot([2, 4, 8], [100*case['comparisons'][str(n)][metric] for n in (2, 4, 8)],
                      marker='o', color=color, label=case['case'].replace('_', ' '))
    for axis, title in zip(axes, ['Wing-end combined motion', 'Rotation relative to fairing']):
        axis.set_xticks([2, 4, 8]); axis.set_yscale('log'); axis.grid(True, which='both', alpha=.25)
        axis.set_xlabel('Elements in mounting span'); axis.set_ylabel('Error versus continuum (%)')
        axis.set_title(title); axis.legend()
    fig.suptitle('Same supplied aircraft loads, independent mounting mechanics\nConditional component replay; the aircraft is not recoupled')
    fig.tight_layout(); fig.savefig(folder/'actual-forcing.svg'); fig.savefig(folder/'actual-forcing.png', dpi=150); plt.close(fig)
    print(result, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/daedalus_mount_reference.py', ROOT/'scripts/check_daedalus_mount_continuum.py',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json', CAPTURE/'fixture.json',
        STUDY/'actual-forcing/result.json', STUDY/'actual-forcing/terminal.json']
    for tag in ['discrete-2', 'discrete-4', 'discrete-8', 'continuum-10', 'continuum-12']:
        inputs += [STUDY/tag/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, work, args, __file__)


if __name__ == '__main__': main()
