"""Can one common input gain/filter reconcile all four published magnitudes?

No filter is fitted or inserted. At each frequency, intersect the gains
allowed by each output. An empty intersection disproves a common scalar
input correction as the sole explanation, even with arbitrary filter phase.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_rudder_input import STUDY
from check_daedalus_reference_kinematics import BUNDLE, PREFIX
from daedalus_bounded_job import run


def report(folder, args):
    import csv, hashlib, io, json, math, zipfile
    import numpy as np
    import pymupdf
    channels = ['yaw_rate', 'roll_rate', 'sideslip', 'bank']
    curves = {}; slopes = {}
    with zipfile.ZipFile(BUNDLE) as archive:
        metadata = json.loads(archive.read(PREFIX+'extractions.json'))
        pdf = archive.read('four-outputs/bundle/inputs/reference/rudder-bode.pdf')
        assert hashlib.sha256(pdf).hexdigest() == metadata['source_pin']['sha256']
        assert hashlib.sha256(pdf).hexdigest() == hashlib.sha256((ROOT/'reference/drela-rudder-bode-20261113.pdf').read_bytes()).hexdigest()
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            paths = document[0].get_drawings()
            for channel in channels:
                filename = 'yaw' if channel == 'yaw_rate' else channel
                raw = archive.read(PREFIX+filename+'-reference.csv')
                (folder/(channel+'-reference.csv')).write_bytes(raw)
                rows = list(csv.DictReader(io.StringIO(raw.decode())))
                curve = np.array([[float(r[k]) for k in list(r)[1:]] for r in rows])
                assert curve.shape[1] == 4 and np.all(np.diff(curve[:, 0]) > 0)
                entry = dict(grid_path=18, magnitude_limits=[.01, 1.]) if channel == 'yaw_rate' else metadata['new_curves'][channel]
                rectangle = paths[entry['grid_path']]['rect']; low, high = entry['magnitude_limits']
                slope = math.log(high/low)/rectangle.height
                np.testing.assert_allclose(high*np.exp((rectangle.y0-curve[:, 1])*slope), curve[:, 3], rtol=2e-13, atol=1e-14)
                np.testing.assert_allclose(.1*10**(2*(curve[:, 0]-rectangle.x0)/rectangle.width), curve[:, 2], rtol=2e-13, atol=1e-14)
                assert abs(rectangle.x0-91.) < 1e-10 and abs(rectangle.x1-558.9000244140625) < 1e-10
                curves[channel] = curve; slopes[channel] = slope
    x0, x1 = 91., 558.9000244140625
    xcoord = lambda f: x0+(x1-x0)*np.log10(f/.1)/2
    def envelope(channel, f, halfwidth):
        v = curves[channel]; x = xcoord(f)
        lo, hi = max(x0, x-2*halfwidth), min(x1, x+2*halfwidth)
        locations = np.r_[lo, v[(v[:, 0]>lo)&(v[:, 0]<hi), 0], hi]
        logs = np.interp(locations, v[:, 0], np.log(v[:, 3]))
        return np.exp(logs.min()-halfwidth*slopes[channel]), np.exp(logs.max()+halfwidth*slopes[channel])
    source = {}; reference_identity = 0.
    with (SOURCE/'report/comparison.csv').open() as stream:
        for row in csv.DictReader(stream):
            f, channel = float(row['frequency_hz']), row['channel']
            magnitude = abs(complex(float(row['real_display']), float(row['imag_display'])))
            assert abs(magnitude-float(row['magnitude_display'])) < 2e-14
            reference = np.exp(np.interp(xcoord(f), curves[channel][:, 0], np.log(curves[channel][:, 3])))
            reference_identity = max(reference_identity, float(abs(reference-float(row['reference_magnitude']))))
            source.setdefault(f, {})[channel] = magnitude
    assert len(source) == 65 and reference_identity < 2e-12, reference_identity
    samples = []; intervals = []
    for halfwidth in (0., .75, 1.5):
        for f, values in sorted(source.items()):
            assert set(values) == set(channels)
            gains = []
            for channel in channels:
                lo, hi = envelope(channel, f, halfwidth); actual = values[channel]
                a, b = float(lo/actual), float(hi/actual)
                gains.append((channel, a, b))
                intervals.append(dict(frequency_hz=f, graphic_halfwidth_pt=halfwidth, channel=channel,
                    current_magnitude=actual, drawing_min=float(lo), drawing_max=float(hi),
                    exact_gain_min=a, exact_gain_max=b, five_percent_gain_min=.95*a, five_percent_gain_max=1.05*b))
            lower = max(gains, key=lambda x:x[1]); upper = min(gains, key=lambda x:x[2])
            L, U = lower[1], upper[2]
            # To have relative error <= E to some value in every graphic band,
            # a common gain must satisfy (1-E)L <= g <= (1+E)U. Consequently:
            bound = max(0., (L-U)/(L+U))
            possible = bool(.95*L <= 1.05*U)
            assert possible == (bound <= .05+2e-15)
            samples.append(dict(frequency_hz=f, graphic_halfwidth_pt=halfwidth,
                gain_lower_without_solver_tolerance=L, gain_upper_without_solver_tolerance=U,
                five_percent_common_gain_min=.95*L, five_percent_common_gain_max=1.05*U,
                lower_limiting_channel=lower[0], upper_limiting_channel=upper[0],
                minimum_possible_worst_relative_error=bound,
                common_gain_necessary_condition_possible=possible))
    for filename, rows in [('bounds.csv', samples), ('gain-intervals.csv', intervals)]:
        with (folder/filename).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summaries = []
    for h in (0., .75, 1.5):
        rows = [r for r in samples if r['graphic_halfwidth_pt'] == h]
        dip = min(rows, key=lambda r:abs(r['frequency_hz']-1.15737773741517))
        assert abs(dip['frequency_hz']-1.15737773741517) < 1e-12
        impossible = [r['frequency_hz'] for r in rows if not r['common_gain_necessary_condition_possible']]
        summaries.append(dict(graphic_halfwidth_pt=h, impossible_count=len(impossible),
            impossible_frequencies_hz=impossible, dip=dip, maximum=max(rows, key=lambda r:r['minimum_possible_worst_relative_error'])))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, NullFormatter, FuncFormatter
    fig, axes = plt.subplots(1, 2, figsize=(11.7, 4.8), layout='constrained')
    for channel, color in zip(channels, ['#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f']):
        rows = [r for r in intervals if r['channel'] == channel and r['graphic_halfwidth_pt'] == .75]
        central = [r for r in intervals if r['channel'] == channel and r['graphic_halfwidth_pt'] == 0.]
        f = [r['frequency_hz'] for r in rows]
        axes[0].loglog(f, [r['exact_gain_min'] for r in central], color=color, label=channel.replace('_', ' '))
        axes[0].fill_between(f, [r['exact_gain_min'] for r in rows], [r['exact_gain_max'] for r in rows], color=color, alpha=.18)
    axes[0].set(title='Required input gain differs between outputs', ylabel='Drawing magnitude / current magnitude')
    for h, label, color in [(0., 'Central drawing', '#ff4a3d'), (.75, 'Allow graphic envelope', '#ff9f1a')]:
        rows = [r for r in samples if r['graphic_halfwidth_pt'] == h]
        axes[1].semilogx([r['frequency_hz'] for r in rows], [100*r['minimum_possible_worst_relative_error'] for r in rows], color=color, label=label)
    axes[1].axhline(5., color='#666666', linestyle=':', label='5% comparison tolerance')
    axes[1].set(title='Best possible common-gain error bound', ylabel='At least one output must err by (%)', ylim=(0, 100))
    for axis in axes:
        axis.set(xlim=(.1, 10), xlabel='Frequency (Hz)')
        axis.xaxis.set_major_locator(LogLocator(base=10, numticks=3))
        axis.xaxis.set_major_formatter(FuncFormatter(lambda v, pos:f'{v:g}'))
        axis.xaxis.set_minor_locator(LogLocator(base=10, subs=range(2, 10)))
        axis.xaxis.set_minor_formatter(NullFormatter()); axis.grid(which='major', alpha=.4); axis.grid(which='minor', alpha=.15)
        axis.legend(fontsize=8)
    fig.suptitle('Daedalus: a common input gain or scalar actuator filter cannot reconcile all outputs\nUnchanged aircraft; ±0.75 PDF-point graphic envelope; no filter fitted', fontsize=11)
    fig.savefig(folder/'input-invariant.png', dpi=150); fig.savefig(folder/'input-invariant.svg'); plt.close(fig)
    result = dict(frequency_count=65, reference_interpolation_identity=reference_identity,
        graphic_band_summaries=summaries,
        dip_channel_intervals=[r for r in intervals if r['graphic_halfwidth_pt']==.75 and abs(r['frequency_hz']-1.15737773741517)<1e-12],
        qualification='Necessary magnitude condition for unchanged output definitions and aircraft. Any scalar input filter multiplies all outputs equally at a frequency. Allow arbitrary gain separately at every frequency, which is more permissive than a physical actuator. Possible intersections are not validation passes. Feedback, spatially changed control mixing, different aircraft/trim and output remapping are outside this invariant.')
    print(json.dumps(dict(summaries=summaries, dip=result['dip_channel_intervals'])), flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_rudder_input.py', ROOT/'scripts/check_daedalus_reference_kinematics.py',
        BUNDLE, ROOT/'reference/drela-rudder-bode-20261113.pdf', SOURCE/'report/comparison.csv',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json']
    for tag in ('native', 'reference', 'input-response'):
        inputs += [STUDY/tag/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, report, args, __file__)


if __name__ == '__main__': main()
