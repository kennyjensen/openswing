"""Magnitude and phase of the saved attached-gyro averages; no new solve."""
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
from report_daedalus_sensor_average import SOURCE, REFERENCE, LABELS

STUDY = SOURCE.parent


def report(folder, args):
    import csv
    import hashlib
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter

    terminal = read(SOURCE/'terminal.json')
    assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
    for name, digest in read(SOURCE/'plan.json')['inputs_sha256'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    data = read(SOURCE/'result.json')
    rows = sorted(data['rows'], key=lambda r: r['frequency_hz'])
    f = np.array([r['frequency_hz'] for r in rows])
    assert np.all(np.diff(f) > 0)
    values = {key: np.array([complex(r['values'][key]['real'], r['values'][key]['imag'])
                            for r in rows]) for key in LABELS}
    phases = {key: np.degrees(np.unwrap(np.angle(z))) for key, z in values.items()}
    for key, z in values.items():
        np.testing.assert_allclose(abs(z), [r['values'][key]['magnitude'] for r in rows], rtol=1e-14)
        np.testing.assert_allclose(abs(z)*np.exp(1j*np.radians(phases[key])), z, rtol=1e-13, atol=1e-13)

    native = np.array(read(REFERENCE)['channels']['yaw_rate']['vertices'])
    groups = [('Across the aircraft', ['frame', 'aircraft_seven', 'all_nodes_equal'], (.1, 10), (.005, 20)),
              ('Cabin and wing: near the notch', ['frame', 'cabin_wing_root_two', 'wing_cabin_four'], (.5, 3), (.005, .5))]
    colors = {'frame':'#222222', 'aircraft_seven':'#d55e00', 'all_nodes_equal':'#009e73',
              'cabin_wing_root_two':'#0072b2', 'wing_cabin_four':'#d55e00'}
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True, sharex='col')
    for col, (title, keys, xlim, ylim) in enumerate(groups):
        mag, phase = axes[:, col]
        mag.loglog(native[:, 2], native[:, 3], '--', color='#8b2aa5', lw=2, label='Drela published magnitude')
        for key in keys:
            mag.loglog(f, abs(values[key]), color=colors[key], lw=1.7, label=LABELS[key])
            phase.semilogx(f, phases[key], color=colors[key], lw=1.7)
        mag.set(title=title, ylabel='Yaw-rate magnitude (deg/s per F3)', ylim=ylim)
        phase.set(xlabel='Frequency (Hz)', ylabel='Phase (degrees, unwrapped)')
        for ax in (mag, phase):
            ax.set_xlim(*xlim)
            ax.xaxis.set_major_locator(LogLocator(base=10))
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
            ax.xaxis.set_minor_locator(LogLocator(base=10, subs=range(2, 10)))
            ax.xaxis.set_minor_formatter(NullFormatter())
            ax.axvline(data['native_dip']['frequency_hz'], color='#8b2aa5', lw=.8, ls=':')
            ax.grid(which='major', color='#c1c7cd', lw=.7)
            ax.grid(which='minor', color='#e4e7eb', lw=.4)
            ax.set_axisbelow(True)
        mag.yaxis.set_major_locator(LogLocator(base=10))
        mag.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
        mag.yaxis.set_minor_locator(LogLocator(base=10, subs=range(2, 10)))
        mag.yaxis.set_minor_formatter(NullFormatter())
        mag.legend(fontsize=8, loc='upper left')
        if col:
            phase.set_xticks([.5, 1, 2, 3])
    fig.suptitle('Daedalus: Bode response of averaged yaw-rate sensors\nComplex averages of attached gyros; unchanged 6.7 m/s level-flight solution', fontsize=13)
    fig.savefig(folder/'bode.svg')
    fig.savefig(folder/'bode.png', dpi=140)
    plt.close(fig)

    with (folder/'bode.csv').open('x', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['frequency_hz', 'layout', 'real_deg_s_per_F3', 'imag_deg_s_per_F3', 'magnitude_deg_s_per_F3', 'phase_degrees_unwrapped'])
        for key, z in values.items():
            for freq, v, phase in zip(f, z, phases[key]):
                writer.writerow([freq, key, v.real, v.imag, abs(v), phase])
    write(folder/'sensor-locations.json', data['layouts'])
    table = []
    for key in ('frame', 'cabin_wing_root_two', 'wing_cabin_four', 'aircraft_seven', 'all_nodes_equal'):
        at = data['summaries'][key]['at_native_dip']['magnitude']
        mask = np.flatnonzero((f >= .7) & (f <= 3))
        j = mask[np.argmin(abs(values[key][mask]))]
        minimum = f'{f[j]:.3f} Hz / {abs(values[key][j]):.5f}' if key not in ('aircraft_seven', 'all_nodes_equal') else 'No comparable notch near 1 Hz'
        table.append(f'<tr><th scope="row">{LABELS[key]}</th><td>{at:.5f}</td><td>{minimum}</td></tr>')
    (folder/'index.html').write_text('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daedalus sensor-average Bode · OpenSwing</title><style>
:root{color-scheme:dark;background:#101719;color:#dce8e7;font:16px/1.6 system-ui,sans-serif}body{margin:0}main{max-width:1250px;margin:auto;padding:24px 20px 60px}a{color:#91e1bd}nav{display:flex;flex-wrap:wrap;gap:12px 24px}h1{line-height:1.2}p{max-width:95ch}.plot,.table{overflow:auto}.plot{background:white;border-radius:6px}.plot img{width:100%;min-width:760px;display:block}figure{margin:24px 0}figcaption{color:#a7bab8}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:12px;border-bottom:1px solid #2a393c}a:focus-visible,[tabindex]:focus-visible{outline:2px solid #91e1bd;outline-offset:3px}.finding{border-left:3px solid #e2a365;padding:12px 20px;background:#1e2425}
</style></head><body><main>
<nav><a href="/">OpenSwing</a><a href="/validation/daedalus-bode/index.html">Standard Daedalus comparison</a></nav>
<h1>Daedalus sensor-average Bode</h1>
<p>Virtual yaw-rate gyros at multiple aircraft attachment points are averaged at each frequency. The curves below come directly from their calculated motion. No GIF measurements enter this experiment.</p>
<p class="finding"><strong>Averaging produces deeper notches, but the tested layouts do not reproduce the published notch near 1.16 Hz.</strong> The cabin-and-wing averages dip near 1.5 and 2 Hz. Including the tail raises the average near 1 Hz because its local angular motion is much larger.</p>
<figure><div class="plot" tabindex="0" role="region" aria-label="Sensor-average Bode magnitude and phase; scroll horizontally on small screens"><a href="bode.svg"><img src="bode.svg" width="1300" height="800" alt="Magnitude and phase of averaged yaw sensors. Across-aircraft averages are dominated by tail motion. Cabin and wing averages show notches near 1.5 and 2 Hz, beyond Drela's 1.16 Hz notch."></a></div><figcaption>Top: magnitude. Bottom: phase relative to rudder input. Vertical dotted line: Drela’s published dip. The source drawing provides magnitude only. Tap the plot to enlarge.</figcaption></figure>
<nav><a href="bode.png" download>PNG plot</a><a href="bode.svg" download>SVG plot</a><a href="bode.csv" download>All 11 layouts, magnitude and phase (CSV)</a><a href="sensor-locations.json" download>Sensor positions and weights (JSON)</a></nav>
<h2>Comparison near the published dip</h2>
<p>Drela’s reference minimum is 0.03399 deg/s per F3 at 1.15738 Hz. Minima below are the lowest saved samples between 0.7 and 3 Hz.</p>
<div class="table" tabindex="0"><table><thead><tr><th>Measurement</th><th>Magnitude at 1.15738 Hz</th><th>Sampled minimum: frequency / magnitude</th></tr></thead><tbody>''' + ''.join(table) + '''</tbody></table></div>
<h2>What is averaged</h2>
<p>Each attached gyro measures aircraft-frame angular velocity plus local elastic angular velocity. The sensor z axes share the loaded aircraft’s body-z direction. We average the complex responses before calculating magnitude and phase, preserving cancellation between sensors. Each sensor has equal weight within the displayed layouts.</p>
<ul><li><strong>Cabin + wing root (2):</strong> pilot attachment and wing center.</li><li><strong>Cabin + wing root + both wingtips (4):</strong> those two points and the left/right tips.</li><li><strong>7 aircraft locations:</strong> pilot attachment, wing root, both tips, mid-boom, stabilizer center and mid-fin.</li><li><strong>All 103 nodes:</strong> one gyro at every structural node. This average depends on mesh density.</li></ul>
<p>H<sub>average</sub>(f) = (H<sub>1</sub>(f) + … + H<sub>N</sub>(f)) / N. The downloadable locations include beam, station, loaded coordinates in feet and exact weights. Sensors add no mass or stiffness. This is a measurement diagnostic; the normal Bode output and dynamics are unchanged.</p>
<h2>Saved case and checks</h2>
<p>Literal dae.asw, 6.7 m/s level-flight trim; 162 saved frequencies and all 1,953 dynamic states. Both tested sensor-axis conventions were checked against production gyro measurements at all 103 nodes at 1 Hz and 1.15738 Hz, agreeing within 1.341e-13 rad/s. The plot is a saved comparison, independent of your currently loaded model. Drela’s original operating point remains unknown.</p>
</main></body></html>
''')
    return dict(source=str(SOURCE.relative_to(ROOT)), samples=len(f), layouts=len(values),
                definition='Equal-weight complex attached-gyro averages before magnitude and phase; no image measurements or new solve.',
                phase_check='Every exported magnitude/phase reconstructs the original complex response.',
                source_observed_utc=terminal['observed_utc'])


if __name__ == '__main__':
    inputs = [SOURCE/name for name in ('result.json', 'terminal.json', 'plan.json')]
    inputs += [REFERENCE, ROOT/'scripts/report_daedalus_sensor_average.py']
    run(STUDY, 'bode-report', inputs, report, {}, __file__)
