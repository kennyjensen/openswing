"""Audit saved unswept junction diagnostics and plot without rerunning solves."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    args = parser.parse_args()
    folder = args.study
    plan = json.loads((folder/'plan.json').read_text())
    verification = json.loads((folder/'verification.json').read_text())
    assert all(sha(folder/name) == pin for name, pin in verification['artifacts'].items())
    assert all(sha(ROOT/name) == pin for name, pin in plan['pins'].items())
    rows = json.loads((folder/'results.json').read_text())
    assert [row['request'] for row in rows] == plan['requests']
    assert len(rows) == 6
    analysis = []
    for row in rows:
        assert row['condition'] == plan['condition']
        r, f, request = row['result'], row['field'], row['request']
        assert r['converged'] and r['residual'] < 1e-12
        assert r['mach'] == 0. and r['aerodynamic_influences']['frozen'] is False
        n = request['main_intervals']
        strips = r['strips']
        groups = [[s for s in strips if s['beam'] == k] for k in (1, 2, 3)]
        assert [len(g) for g in groups] == [n//5, n, n//5]
        assert r['lifting_panels'] == len(strips) == n*7//5
        velocities = np.array([s['relative_velocity'] for s in strips])
        assert f['maximum_speed'] == float(np.max(np.linalg.norm(velocities, axis=1)))
        # Independent scalar root-incidence accounting from saved physical
        # sample ownership, not FactoredInfluence's grouping.
        jumps = [groups[0][-1]['circulation']-groups[1][0]['circulation'],
                 groups[1][-1]['circulation']-groups[2][0]['circulation']]
        for root, jump in zip(f['roots'], jumps):
            assert root['distinct_origins'] == 1
            assert root['signed_wake_strengths'] == [jump]
        np.testing.assert_allclose(velocities[f['peak_index']],
            np.array(f['bound_velocity'])+f['wake_velocity']+[1., 0., 0.], atol=3e-12)
        assert abs(f['wake_velocity'][0]) < 1e-15
        assert np.max(abs(np.array(f['bound_velocity'])[1:])) < 1e-15
        assert abs(r['CD']-r['CDi']) < 1e-12
        if request['sampling'] == 'arithmetic-control':
            # All controls, including both sides of the bend, have the stated
            # material spacing. These are not production Glauert samples.
            ts = np.array([s['t'] for s in strips])
            np.testing.assert_allclose(np.diff(ts), 1/n, atol=3e-15, rtol=0.)
        pos = np.asarray(f['peak_position'])
        distance = min(np.linalg.norm(pos-[0., y, 0.]) for y in (-.5, .5))
        analysis.append(dict(**request, total_panels=len(strips), CL=r['CL'], CD=r['CD'],
            CDi=r['CDi'], Cm=r['Cm'], residual=r['residual'],
            peak_speed=f['maximum_speed'], peak_streamwise_speed=f['peak_velocity'][0],
            peak_bound_streamwise=f['bound_velocity'][0], peak_distance_from_junction=float(distance),
            peak_bound_times_distance=float(f['bound_velocity'][0]*distance),
            root_ray_magnitudes=[abs(g) for g in jumps], seconds=row['seconds']))
    partition = json.loads((folder/'partition-check.json').read_text())
    assert max(partition['differences'].values()) == 0.
    forks = json.loads((folder/'fork-checks.json').read_text())
    assert len(forks) == 8
    assert all(r['velocity_max_error'] < 2e-12 for r in forks)
    refinement = []
    for sampling in ('glauert', 'arithmetic-control'):
        a = [r for r in analysis if r['sampling'] == sampling]
        assert [r['main_intervals'] for r in a] == [50, 100, 200]
        assert all(y['peak_speed'] > x['peak_speed'] for x, y in zip(a, a[1:]))
        assert all(y['root_ray_magnitudes'][0] < x['root_ray_magnitudes'][0]
                   for x, y in zip(a, a[1:]))
        refinement.append(dict(sampling=sampling,
            coarse_to_fine_percent={key:100*(a[-1][key]/a[0][key]-1)
                                   for key in ('CL', 'CD', 'Cm', 'peak_speed')},
            last_refinement_percent={key:100*(a[-1][key]/a[-2][key]-1)
                                    for key in ('CL', 'CD', 'Cm', 'peak_speed')}))

    plt.rcParams.update({'font.size':9, 'axes.grid':True, 'grid.alpha':.22})
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 7.1), constrained_layout=True)
    colors = {50:'#0072B2', 100:'#D55E00', 200:'#009E73'}
    styles = {'glauert':'-', 'arithmetic-control':'--'}
    for row in rows:
        n, sampling = row['request']['main_intervals'], row['request']['sampling']
        strips = [s for s in row['result']['strips'] if s['t'] > 0.]
        color, style = colors[n], styles[sampling]
        name = f'N={n}, ' + ('Glauert' if sampling == 'glauert' else 'uniform controls')
        x = [s['t'] for s in strips]
        axes[0,0].plot(x, [s['circulation']/.05 for s in strips], style, color=color, label=name)
        axes[0,1].plot(x, [s['relative_velocity'][0] for s in strips], style, color=color)
    for ax in axes[0]:
        ax.axvline(.5, color='.35', linewidth=1, alpha=.6)
        ax.set_xlabel('Material distance from wing center s [m]')
        ax.set_xlim(0., .7)
    axes[0,0].set_ylabel(r'$\Gamma / \Gamma_{2D}$,  $\Gamma_{2D}=0.05$ m²/s')
    axes[0,1].set_ylabel(r'Streamwise velocity $u_x/U_\infty$')
    axes[0,0].set_title('Circulation approaches continuity at the bend')
    axes[0,1].set_title('Sharp-junction speed grows with refinement')
    axes[0,0].legend(fontsize=7, loc='lower left')
    for sampling in styles:
        a = [r for r in analysis if r['sampling'] == sampling]
        name = 'Glauert samples' if sampling == 'glauert' else 'Uniform control samples'
        color = '#0072B2' if sampling == 'glauert' else '#D55E00'
        axes[1,0].loglog([r['peak_distance_from_junction'] for r in a],
                        [r['peak_bound_streamwise'] for r in a], 'o'+styles[sampling],
                        color=color, label=name)
        axes[1,1].plot([r['total_panels'] for r in a], [r['CL'] for r in a],
                      'o'+styles[sampling], color=color, label=name)
    axes[1,0].set_xlabel('Closest peak receiver distance from junction [m]')
    axes[1,0].set_ylabel(r'Bound-vortex contribution $u_x/U_\infty$')
    axes[1,0].set_title('Approximately inverse-distance growth')
    axes[1,1].set_xlabel('Total lifting intervals')
    axes[1,1].set_ylabel(r'Integrated $C_L$, $S_{ref}=0.1$ m²')
    axes[1,1].set_title('Integrated lift is much less sensitive')
    axes[1,1].legend(fontsize=8)
    fig.suptitle('Unswept sharp winglet control — OpenSwing, no core or stall\n'
                 'Diagnostic sampling comparison; not an ASWING reference pass', fontsize=12)
    for extension in ('png', 'svg'):
        fig.savefig(folder/('junction-refinement.'+extension), dpi=170)
    plt.close(fig)
    output = dict(utc=datetime.now(timezone.utc).isoformat(), rows=analysis, refinement=refinement,
        max_partition_difference=max(partition['differences'].values()),
        max_independent_fork_error=max(r['velocity_max_error'] for r in forks),
        source_and_scope_pins_verified=True, raw_artifact_pins_verified=True,
        maximum_residual=max(r['residual'] for r in analysis),
        summed_winglet_solve_seconds=sum(r['seconds'] for r in analysis),
        analysis_driver_sha256=sha(Path(__file__)),
        plots={p.name:sha(p) for p in folder.glob('junction-refinement.*')},
        limitations=['No original ASWING output or paper curve has been scored.',
                     'The arithmetic sample control is a diagnostic, not a new production option.',
                     'Three grids show growth, not a proof of integrated mesh convergence.',
                     'A nonzero junction wake strength is permitted by the discrete horseshoes; '
                     'signed conservation includes that wake and is not a hard endpoint equality constraint.'])
    (folder/'analysis.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key:output[key] for key in ('maximum_residual', 'summed_winglet_solve_seconds',
        'max_independent_fork_error', 'max_partition_difference', 'refinement')}, indent=2))


if __name__ == '__main__':
    main()
