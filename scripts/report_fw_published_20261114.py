"""Plot the current, bounded FW checks without rerunning the solver."""
import ast
import json
from pathlib import Path

from daedalus_bounded_job import run
from check_daedalus_load_sensitivity import ROOT, pin, write

STUDY = ROOT/'artifacts/fw-published-20261114'
CASES = [(8, 64), (16, 64), (32, 64), (32, 62), (32, 66)]


def report(folder, args):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows, verified, terminals = [], {}, []
    runner = ROOT/'scripts/check_fw_published_20261114.py'
    current_nodes = {ast.dump(node) for node in ast.parse(runner.read_text()).body}
    for panels, speed in CASES:
        data = {}
        for mode in ('trim', 'matrices', 'roots'):
            job = STUDY/f'{mode}-{panels}-{speed}'
            terminal = json.loads((job/'terminal.json').read_text())
            assert terminal['returncode'] == 0 and terminal['process_reaped']
            assert terminal['inputs_unchanged'] and not terminal['timed_out']
            terminals.append(terminal)
            for name, sha in json.loads((job/'plan.json').read_text())['inputs_sha256'].items():
                if Path(name) == runner:
                    # The first trim preceded addition of matrices/roots CLI
                    # modes. Verify its immutable runner and that every old
                    # non-CLI definition still exists unchanged in the current
                    # runner, rather than pretending all CLI versions match.
                    saved = job/'runner.py'
                    assert pin(saved) == sha
                    for node in ast.parse(saved.read_text()).body:
                        if isinstance(node, ast.If):
                            continue
                        assert ast.dump(node) in current_nodes
                    verified[str(saved)] = sha
                    continue
                if name in verified:
                    assert verified[name] == sha
                else:
                    assert pin(Path(name)) == sha, name
                    verified[name] = sha
            data[mode] = json.loads((job/'result.json').read_text())
        t, r = data['trim'], data['roots']
        rows.append(dict(requested_panels=panels, lifting_panels=t['lifting_panels'],
            speed_ft_s=speed, trim=t['actual'], trim_difference=t['difference'],
            residual=t['residual'], current_root=r['current_bff_per_s'],
            reference_root=r['reference_bff_per_s'],
            current_hz=r['current_frequency_hz'], reference_hz=r['reference_frequency_hz'],
            frequency_error_percent=100*(r['current_frequency_hz']/r['reference_frequency_hz']-1),
            growth_error_per_s=r['difference_per_s'][0],
            backward_error=r['maximum_pencil_backward_error']))
    finest = sorted((r for r in rows if r['requested_panels'] == 32), key=lambda r:r['speed_ft_s'])
    def onset(key):
        for a, b in zip(finest, finest[1:]):
            if a[key][0] <= 0 <= b[key][0]:
                return a['speed_ft_s']-a[key][0]*(b['speed_ft_s']-a['speed_ft_s'])/(b[key][0]-a[key][0])
        raise AssertionError('The sampled branch must bracket onset.')
    fig, axes = plt.subplots(2, 1, figsize=(8.6, 6.5), sharex=True)
    x = [r['speed_ft_s'] for r in finest]
    for ax, current, reference, label in (
        (axes[0], 'current_hz', 'reference_hz', 'Oscillation frequency (Hz)'),
        (axes[1], 'current_root', 'reference_root', 'Growth rate (1/s)')):
        index = (lambda v:v[0]) if current.endswith('root') else (lambda v:v)
        ax.plot(x, [index(r[reference]) for r in finest], 'o--', color='#444444',
                linewidth=1.6, markersize=7, label="Drela's published root map")
        ax.plot(x, [index(r[current]) for r in finest], 's-', color='#007fba',
                linewidth=1.6, markersize=5, label='Current OpenSwing, 42 lifting panels')
        ax.set_ylabel(label)
        ax.grid(True, color='#dedede', linewidth=.7)
        ax.axvline(64, color='#aaaaaa', linestyle=':', linewidth=1)
        ax.set_xlim(61.7, 66.3)
    axes[0].legend(loc='upper right', fontsize=9)
    axes[1].axhline(0, color='#777777', linewidth=.8)
    axes[1].set_xlabel('Airspeed (ft/s)')
    axes[1].set_xticks([62, 63, 64, 65, 66])
    fig.suptitle('FW flutter branch near the published 64 ft/s onset', fontsize=14)
    fig.text(.5, .02, 'Literal fw.asw; glide trim inferred; native mesh unspecified.\n'
             'Three-speed comparison of one mode; Bode gain and phase remain unvalidated.',
             ha='center', fontsize=9, color='#444444')
    fig.tight_layout(rect=(0, .07, 1, .95))
    fig.savefig(folder/'comparison.png', dpi=160)
    fig.savefig(folder/'comparison.svg')
    plt.close(fig)
    write(folder/'source-pins.json', verified)
    return dict(scope='Current FW trim and one flutter branch, not native Bode validation.',
        rows=rows, interpolated_current_onset_ft_s=onset('current_root'),
        interpolated_reference_onset_ft_s=onset('reference_root'),
        onset_limitation='Linear interpolation of the nearest sampled sign bracket, not a solved flutter boundary.',
        completed_solver_jobs=len(terminals),
        max_solver_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        max_solver_wall_seconds=max(t['wall_seconds'] for t in terminals),
        max_solver_rss_kib=max(t['peak_rss_kib'] for t in terminals),
        source_pins_verified=len(verified))


if __name__ == '__main__':
    inputs = []
    for panels, speed in CASES:
        for mode in ('trim', 'matrices', 'roots'):
            inputs += [STUDY/f'{mode}-{panels}-{speed}'/name
                       for name in ('result.json', 'plan.json', 'terminal.json', 'runner.py')]
    inputs.append(ROOT/'scripts/check_fw_published_20261114.py')
    run(STUDY, 'report-fixed', inputs, report, {}, __file__)
