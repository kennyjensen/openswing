"""Compare saved current-mesh transfers with native PDF paths; no solve."""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
import check_daedalus_regular_mesh_response as response

STUDY = response.STUDY
BUNDLE = ROOT/'docs/validation/daedalus-rudder-four-outputs-20261025-evidence.zip'
PDF = ROOT/'reference/drela-rudder-bode-20261113.pdf'
PREFIX = 'four-outputs/bundle/evidence/accepted/results/reference/'
CHANNELS = ['yaw_rate', 'roll_rate', 'sideslip', 'bank']
STAGES = [*[f'geometry-{i}' for i in range(7)], 'other', 'mass',
          'geometry-joined', 'assembled', 'response',
          *[f'curve-{i:02d}' for i in range(17)],
          *['refine-'+name for name in ['yaw-low-min', 'roll-low-min',
             'yaw-high-min', 'roll-high-min', 'yaw-high-max']], 'native-features']


def report(folder, args):
    import csv
    import hashlib
    import io
    import json
    import math
    import zipfile
    import numpy as np
    import pymupdf
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter

    # Check the retained stages and their common model/matrix provenance.
    pins, receipts = {}, {}
    samples = {}
    for stage in STAGES:
        directory = STUDY/stage
        receipt = read(directory/'terminal.json')
        assert receipt['returncode'] == 0 and receipt['process_reaped']
        assert receipt['inputs_unchanged'] and not receipt['timed_out']
        receipts[stage] = receipt
        for path, digest in read(directory/'plan.json')['inputs_sha256'].items():
            assert path not in pins or pins[path] == digest, path
            pins[path] = digest
        data = read(directory/'result.json')
        if 'samples' not in data:
            continue
        assert data['channels'] == CHANNELS
        for row in data['samples']:
            f = row['frequency_hz']
            values = np.array(row['real'])+1j*np.array(row['imag'])
            assert np.all(np.isfinite(values)) and f > 0
            np.testing.assert_allclose(abs(values), row['magnitude'], rtol=2e-14)
            if f in samples:
                old = samples[f]
                np.testing.assert_allclose(values, np.array(old['real'])+1j*np.array(old['imag']), rtol=1e-11, atol=1e-14)
                old['stages'].append(stage)
            else:
                samples[f] = dict(row, stages=[stage])
    for path, digest in pins.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    write(folder/'source-pins.json', pins)
    rows = [samples[f] for f in sorted(samples)]
    assert rows[0]['frequency_hz'] == .1 and rows[-1]['frequency_hz'] == 10

    # Use only native reference vertices from the older evidence archive;
    # none of that archive's OpenSwing computations enter this comparison.
    native = {}
    names = dict(yaw_rate='yaw', roll_rate='roll_rate', sideslip='sideslip', bank='bank')
    grids = dict(yaw_rate=(18, .01, 1), roll_rate=(12, .001, .1),
                 sideslip=(6, .001, 1), bank=(0, .00001, 1))
    with zipfile.ZipFile(BUNDLE) as archive:
        metadata = json.loads(archive.read(PREFIX+'extractions.json'))
        pdf = archive.read('four-outputs/bundle/inputs/reference/rudder-bode.pdf')
        assert hashlib.sha256(pdf).hexdigest() == metadata['source_pin']['sha256']
        assert pdf == PDF.read_bytes()
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            drawings = document[0].get_drawings()
            for channel, name in names.items():
                records = list(csv.DictReader(io.StringIO(archive.read(PREFIX+name+'-reference.csv').decode())))
                array = np.array([[float(r[k]) for k in list(r)[1:]] for r in records])
                grid, low, high = grids[channel]
                box = drawings[grid]['rect']
                slope = math.log(high/low)/box.height
                np.testing.assert_allclose(.1*10**(2*(array[:, 0]-box.x0)/box.width), array[:, 2], rtol=2e-13)
                np.testing.assert_allclose(high*np.exp((box.y0-array[:, 1])*slope), array[:, 3], rtol=2e-13)
                assert np.all(np.diff(array[:, 0]) > 0)
                native[channel] = dict(vertices=array.tolist(), rectangle=list(box), log_magnitude_per_point=slope)
    write(folder/'reference.json', dict(pdf_url='https://web.mit.edu/drela/Public/web/aswing/rudder-bode.pdf',
        pdf_sha256=hashlib.sha256(pdf).hexdigest(), channels=native,
        qualification='Native PDF magnitude paths only; no reference response phases or original operating-point file available.'))

    def reference(channel, frequency):
        curve = native[channel]
        a = np.array(curve['vertices']); x0, _, x1, _ = curve['rectangle']
        x = x0+math.log10(frequency/.1)*(x1-x0)/2
        assert x0-1e-9 <= x <= x1+1e-9
        central = float(np.exp(np.interp(x, a[:, 0], np.log(a[:, 3]))))
        # Retain the previously declared conservative graphic-coordinate band.
        halfwidth = .75
        lo, hi = max(x0, x-2*halfwidth), min(x1, x+2*halfwidth)
        locations = np.r_[lo, a[(a[:, 0] > lo)&(a[:, 0] < hi), 0], hi]
        logs = np.interp(locations, a[:, 0], np.log(a[:, 3]))
        pad = halfwidth*curve['log_magnitude_per_point']
        return dict(magnitude=central, graphic_min=float(np.exp(logs.min()-pad)), graphic_max=float(np.exp(logs.max()+pad)))

    comparisons = []
    for row in rows:
        for i, channel in enumerate(CHANNELS):
            ref = reference(channel, row['frequency_hz'])
            comparisons.append(dict(channel=channel, frequency_hz=row['frequency_hz'],
                unit='deg/s/F3' if i < 2 else 'deg/F3', real=row['real'][i], imag=row['imag'][i],
                magnitude=row['magnitude'][i], reference_magnitude=ref['magnitude'],
                reference_graphic_min=ref['graphic_min'], reference_graphic_max=ref['graphic_max'],
                difference_percent=100*(row['magnitude'][i]/ref['magnitude']-1)))
    with (folder/'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader(); writer.writerows(comparisons)

    features = []
    specifications = [('yaw-low-min', 0, 'min', .8, 2), ('roll-low-min', 1, 'min', .8, 2),
                      ('yaw-high-min', 0, 'min', 6, 8), ('roll-high-min', 1, 'min', 6, 8),
                      ('yaw-high-max', 0, 'max', 8, 10)]
    for name, i, kind, lo, hi in specifications:
        ref_rows = [r for r in native[CHANNELS[i]]['vertices'] if lo <= r[2] <= hi]
        ref = (min if kind == 'min' else max)(ref_rows, key=lambda r:r[3])
        current = read(STUDY/('refine-'+name)/'result.json')['optimum']
        f = ref[2]
        same = next(r for r in rows if abs(r['frequency_hz']-f) < 1e-12)
        features.append(dict(name=name, channel=CHANNELS[i], kind=kind,
            reference_frequency_hz=f, reference_magnitude=ref[3],
            current_extremum_frequency_hz=current['frequency_hz'], current_extremum_magnitude=current['magnitude'][i],
            extremum_frequency_difference_percent=100*(current['frequency_hz']/f-1),
            extremum_magnitude_difference_percent=100*(current['magnitude'][i]/ref[3]-1),
            current_at_reference_frequency=same['magnitude'][i],
            same_frequency_difference_percent=100*(same['magnitude'][i]/ref[3]-1)))

    fig, axes = plt.subplots(2, 2, figsize=(12, 8.4), constrained_layout=True)
    titles = ['Yaw rate Ωz', 'Roll rate Ωx', 'Sideslip β', 'Bank Φ']
    fs = np.array([r['frequency_hz'] for r in rows])
    for i, (ax, channel, title) in enumerate(zip(axes.flat, CHANNELS, titles)):
        ref = np.array(native[channel]['vertices'])
        # The envelope includes horizontal graphic displacement near sharp dips.
        dense = np.unique(np.r_[np.geomspace(.1, 10, 800), ref[:, 2], fs])
        bands = [reference(channel, f) for f in dense]
        ax.fill_between(dense, [b['graphic_min'] for b in bands], [b['graphic_max'] for b in bands], color='#3b82c4', alpha=.14)
        ax.loglog(ref[:, 2], ref[:, 3], color='#2378b5', lw=1.7, ls='--', label='Drela drawing')
        ax.loglog(fs, [r['magnitude'][i] for r in rows], color='#c73439', lw=1.7, label='OpenSwing · current mesh')
        ax.set(title=title, xlabel='Frequency (Hz)', ylabel='Magnitude ('+('deg/s/F3' if i < 2 else 'deg/F3')+')', xlim=(.1, 10))
        ax.xaxis.set_major_locator(LogLocator(base=10)); ax.yaxis.set_major_locator(LogLocator(base=10))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _:f'{x:g}'))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _:f'{x:g}'))
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_minor_locator(LogLocator(base=10, subs=range(2, 10))); axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major', color='#bfc5cc', lw=.7); ax.grid(which='minor', color='#e5e8ec', lw=.45)
        ax.set_axisbelow(True)
    axes[0, 0].legend(loc='best', fontsize=9)
    fig.suptitle('Daedalus rudder response · unit native F3\nOpenSwing: trimmed level flight, 6.7 m/s · Drela operating point unknown', fontsize=13)
    fig.savefig(folder/'comparison.svg'); fig.savefig(folder/'comparison.png', dpi=140); plt.close(fig)
    result = dict(observed_samples=len(rows), channels=CHANNELS, units=['deg/s/F3', 'deg/s/F3', 'deg/F3', 'deg/F3'],
        setup=dict(speed_m_s=6.7, seed=str(response.SEED.relative_to(ROOT)),
            operating_values=read(response.SEED)['operating_values'], mesh=read(response.SEED)['launch']['panels'],
            nodes=103, intervals=98, full_states=1953, factor_dimension=717),
        features=features, one_hz=[r for r in comparisons if r['frequency_hz'] == 1], samples=rows,
        maximum_scaled_matrix_residual=max(max(r['checks']['scaled_residuals']) for r in rows),
        minimum_reciprocal_condition=min(r['checks']['reciprocal_condition'] for r in rows),
        assembly_check=read(STUDY/'assembled/result.json'), verified_numerical_stages=len(receipts), stage_receipts=receipts,
        graphic_band='Half-width 0.75 PDF point; curve extrema over x +/- 1.5 points and y +/- 0.75 points. Graphic envelope, not physical uncertainty or solver tolerance.',
        qualification='Saved full-state responses only; no parameter fit, solver run or reference phase. Feature-to-feature errors and same-frequency errors are distinct. Original ASWING operating point and mesh remain unknown. No validation pass count is assigned.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='report')
    args = vars(parser.parse_args())
    inputs = [BUNDLE, PDF, response.SEED, ROOT/'docs/validation/aswing-authoritative-sources.json',
              ROOT/'scripts/check_daedalus_regular_mesh_response.py']
    for stage in STAGES:
        inputs.extend(STUDY/stage/name for name in ['result.json', 'plan.json', 'terminal.json'])
    run(STUDY, args['tag'], inputs, report, args, __file__)
