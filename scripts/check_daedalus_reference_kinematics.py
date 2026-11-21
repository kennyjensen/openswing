"""Phase-independent consistency of the published Daedalus lateral outputs.

No aircraft parameter is fitted. Bounds concern a stationary, zero-bank base
and body-axis roll/yaw rates, as specified explicitly in the report.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run

STUDY = ROOT / 'artifacts/daedalus-reference-kinematics-20261114'
BUNDLE = ROOT / 'docs/validation/daedalus-rudder-four-outputs-20261025-evidence.zip'
PREFIX = 'four-outputs/bundle/evidence/accepted/results/reference/'


def analyze(folder, args):
    import csv
    import hashlib
    import io
    import json
    import math
    import zipfile
    import numpy as np

    curves = {}
    with zipfile.ZipFile(BUNDLE) as archive:
        metadata = json.loads(archive.read(PREFIX + 'extractions.json'))
        for channel, name in [('roll', 'roll_rate'), ('yaw', 'yaw'), ('bank', 'bank')]:
            raw = archive.read(PREFIX + name + '-reference.csv')
            (folder / (channel + '-reference.csv')).write_bytes(raw)
            records = list(csv.DictReader(io.StringIO(raw.decode())))
            curves[channel] = np.array([[float(r[k]) for k in list(r)[1:]] for r in records])
            assert curves[channel].shape[1] == 4  # graphic x/y, Hz, magnitude
            assert np.all(np.diff(curves[channel][:, 0]) > 0)
        pdf = archive.read('four-outputs/bundle/inputs/reference/rudder-bode.pdf')
        assert hashlib.sha256(pdf).hexdigest() == metadata['source_pin']['sha256']
        assert hashlib.sha256(pdf).hexdigest() == hashlib.sha256(
            (ROOT / 'reference/drela-rudder-bode-20261113.pdf').read_bytes()).hexdigest()

    # Every frequency is a native shared roll/bank vertex. Yaw is evaluated on
    # its published connected log-log polyline, including its internal vertices.
    shared = np.intersect1d(curves['roll'][:, 0], curves['bank'][:, 0])
    assert len(shared) == 99
    x0, x1 = metadata['new_curves']['roll_rate']['rectangle'][::2]
    freq = lambda x: .1 * 10 ** (2 * (x - x0) / (x1 - x0))
    for value in curves.values():
        np.testing.assert_allclose(freq(value[:, 0]), value[:, 2], atol=2e-14, rtol=2e-14)
    slopes = {}
    import pymupdf
    with pymupdf.open(stream=pdf, filetype='pdf') as document:
        paths = document[0].get_drawings()
        for channel, index, low, high in [('roll',12,.001,.1),
                                         ('bank',0,.00001,1.),('yaw',18,.01,1.)]:
            rectangle=paths[index]['rect']; observed=curves[channel]
            assert abs(rectangle.x0-x0)<1e-10 and abs(rectangle.x1-x1)<1e-10
            slope=math.log(high/low)/rectangle.height
            slopes[channel]=slope
            reconstructed=high*np.exp((rectangle.y0-observed[:,1])*slope)
            np.testing.assert_allclose(reconstructed,observed[:,3],atol=2e-14,rtol=2e-14)
    rows = []
    ranges = []
    # The 0.75-point band is inherited from the original extraction, not
    # selected after evaluating the bound. 0 and 1.5 are sensitivity reports.
    for halfwidth in (0., .75, 1.5):
        current = []
        for x in shared:
            bands = {}
            for channel, v in curves.items():
                lo = max(x0, x - 2*halfwidth)
                hi = min(x1, x + 2*halfwidth)
                locations = np.r_[lo, v[(v[:, 0] > lo) & (v[:, 0] < hi), 0], hi]
                logs = np.interp(locations, v[:, 0], np.log(v[:, 3]))
                bands[channel] = (float(np.exp(logs.min() - slopes[channel]*halfwidth)),
                                  float(np.exp(logs.max() + slopes[channel]*halfwidth)))
            wlo = 2*math.pi*freq(max(x0, x-halfwidth))
            whi = 2*math.pi*freq(min(x1, x+halfwidth))
            plo, phi = bands['roll']; rlo, rhi = bands['yaw']; blo, bhi = bands['bank']
            lower = max(0., plo-whi*bhi, wlo*blo-phi)/rhi
            upper = (phi+whi*bhi)/rlo
            current.append(dict(frequency_hz=float(freq(x)), x_pdf_pt=float(x),
                coordinate_halfwidth_pt=halfwidth,
                lower_tan_elevation=lower, upper_tan_elevation=upper,
                lower_abs_elevation_deg=math.degrees(math.atan(lower)),
                upper_abs_elevation_deg=math.degrees(math.atan(upper)),
                **{ch+'_'+side: bounds[j] for ch,bounds in bands.items()
                   for j,side in enumerate(('min','max'))}))
        low = max(current, key=lambda r:r['lower_tan_elevation'])
        high = min(current, key=lambda r:r['upper_tan_elevation'])
        ranges.append(dict(coordinate_halfwidth_pt=halfwidth,
            lower_abs_elevation_deg=low['lower_abs_elevation_deg'],
            upper_abs_elevation_deg=high['upper_abs_elevation_deg'],
            limiting_lower_frequency_hz=low['frequency_hz'],
            limiting_upper_frequency_hz=high['frequency_hz']))
        rows.extend(current)
    state = read(SOURCE / 'trim-6.7-1/state.json')['operating_values']
    elevation = math.radians(state['attitude.elevation'])
    bank = math.radians(state['attitude.bank'])
    # Bound the pitch rate needed to evade the inequality at the *current*
    # attitude. This does not establish the unknown reference attitude.
    ratios = []
    for x in shared:
        p, r, b = [float(np.exp(np.interp(x, curves[ch][:, 0], np.log(curves[ch][:, 3]))))
                   for ch in ('roll', 'yaw', 'bank')]
        ratios.append(2*math.pi*freq(x)*b/p)
    bound_at_current_bank = []
    for row in rows:
        need = max(0., abs(math.tan(elevation)*math.cos(bank))*row['yaw_min']
                   - row['roll_max'] - 2*math.pi*freq(min(x1,row['x_pdf_pt']+row['coordinate_halfwidth_pt']))*row['bank_max'])
        bound_at_current_bank.append(dict(frequency_hz=row['frequency_hz'],
            coordinate_halfwidth_pt=row['coordinate_halfwidth_pt'],
            required_pitch_rate_lower_bound_deg_s=need/abs(math.tan(elevation)*math.sin(bank))))
    with (folder / 'bounds.csv').open('x', newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    result = dict(shared_roll_bank_vertices=len(shared),range_by_graphic_band=ranges,
        current_elevation_deg=state['attitude.elevation'], current_bank_deg=state['attitude.bank'],
        integrated_roll_to_bank_ratio_range=[min(ratios),max(ratios)],
        current_attitude_required_pitch_bounds=[max(
            [r for r in bound_at_current_bank if r['coordinate_halfwidth_pt']==h],
            key=lambda r:r['required_pitch_rate_lower_bound_deg_s']) for h in (0.,.75,1.5)],
        source_pdf_sha256=hashlib.sha256(pdf).hexdigest(),
        equation='At a zero-rate, zero-bank base: i*w*Phi = -p - tan(Theta)*r. Triangle inequality gives |w*|Phi|-|p||/|r| <= |tan(Theta)| <= (w*|Phi|+|p|)/|r|.',
        band_definition='At each common graphic x, allow its true x +/- h, independent curve horizontal displacement +/- h, and vertical displacement +/- h. Evaluate each connected log-log polyline over x +/- 2h and the frequency over x +/- h. These independent extrema are conservative graphic envelopes, not statistical or physical uncertainty.',
        qualification='Necessary bounds only. Assume a stationary base and reported body-axis rates. The zero-bank bound is conditional; unknown nonzero bank and pitch response can alter it. No phase, speed, trim, run setting or aircraft property is fitted or recovered.')
    print(json.dumps(result,indent=2),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True)
    args=vars(p.parse_args())
    inputs=[BUNDLE,ROOT/'reference/drela-rudder-bode-20261113.pdf',
        SOURCE/'trim-6.7-1/state.json',SOURCE/'report/comparison.csv',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    run(STUDY,args['tag'],inputs,analyze,args,__file__)


if __name__=='__main__':main()
