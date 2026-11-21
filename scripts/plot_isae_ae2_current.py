"""Plot independently audited AE-2 native comparisons without importing a solver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal


def plot(assessment, output, beta):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,) * 2)
    signal.alarm(25)
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/openswing-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    data = json.loads(assessment.read_text())
    assert data['status'] == 'CURRENT_SAVED_DATA_AUDIT_PASS'
    assert data['physics_calls'] == data['production_imports'] == 0
    rows = [r for r in data['rows'] if r['beta'] == beta]
    assert rows
    references = {}
    for coordinate in data['required_coordinates']:
        match = re.fullmatch(r'AE-2-(?:(m15_02|p15_02)-)?b(\d+)-ias(\d+)-m(80|160)',
                             coordinate['id'])
        assert match, coordinate['id']
        layup, incidence, speed, _mesh = match.groups()
        if float(incidence) != beta:
            continue
        for obs in coordinate['observations']:
            if obs['missing']:
                continue
            key = (layup or '03_90', obs['name'], float(speed))
            if key in references:
                assert references[key] == obs['expected']
            references[key] = obs['expected']
    fields = [('RY_m', 'Tip Earth Y (m)'), ('Psi_deg', 'Tip heading (deg)'),
              ('sensor_V_m_s', 'Sensor speed (m/s)'),
              ('sensor_beta_deg', 'Sensor sideslip (deg)')]
    layups = [('03_90', 'Uncoupled'), ('m15_02', 'Negative coupling'),
              ('p15_02', 'Positive coupling')]
    fig, axes = plt.subplots(3, 4, figsize=(16, 10), constrained_layout=True)
    for i, (layup, title) in enumerate(layups):
        for k, (field, label) in enumerate(fields):
            ax = axes[i, k]
            group = [r for r in rows if r['layup'] == layup and r['name'] == field]
            native = {speed: value for (model, name, speed), value in references.items()
                      if model == layup and name == field}
            for r in group:
                assert native[r['speed']] == r['expected']
            speeds = sorted(native)
            ax.plot(speeds, [native[s] for s in speeds], 'o', ms=4,
                    color='black', label='Archived ASWING', zorder=3)
            for mesh, style, color in [(80, '--', '#d78b12'), (160, '-', '#2375b6')]:
                values = sorted((r for r in group if r['mesh'] == mesh),
                                key=lambda r: r['speed'])
                # Separate missing speed steps so a failed/unrun state is not interpolated.
                x, y, previous = [], [], None
                for r in values:
                    if previous is not None and r['speed'] - previous > 1.01:
                        x.append(float('nan')); y.append(float('nan'))
                    x.append(r['speed']); y.append(r['predicted']); previous = r['speed']
                # Hollow markers stay visible when an isolated prediction
                # agrees closely with the filled archived point beneath it.
                ax.plot(x, y, style, lw=1.7, color=color,
                        marker='s' if mesh == 80 else 'o', ms=6 if mesh == 80 else 5,
                        markerfacecolor='none', zorder=4,
                        label=f'OpenSwing nominal {mesh}')
            ax.set_title(f'{title}: {label}', fontsize=10)
            ax.set_xlabel('Commanded IAS (m/s)')
            ax.grid(alpha=.25)
            if i == k == 0:
                ax.legend(fontsize=8)
    scope = data['full_scope']
    fig.suptitle(f'AE-2: literal models, beta {beta:g} deg, independent cold starts\n'
                 f'Current full scope: {scope["passed"]:,}/{scope["required"]:,} at 5%; '
                 'unavailable references retained. Historical settings remain unresolved.',
                 fontsize=13)
    for suffix in ('png', 'svg'):
        path = output.with_suffix('.' + suffix)
        assert not path.exists(), 'Preserve earlier plots; use a fresh output.'
        fig.savefig(path, dpi=140)
    plt.close(fig)
    metadata = dict(assessment=str(assessment),
                    assessment_sha256=hashlib.sha256(assessment.read_bytes()).hexdigest(),
                    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    beta=beta, physical_calls=0,
                    reference_points='Every finite native beta-sweep value; missing predictions are not interpolated.')
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--beta', type=float, default=5.)
    args = parser.parse_args()
    plot(args.assessment, args.output, args.beta)
