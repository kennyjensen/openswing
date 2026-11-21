"""Audit Trefftz CDi/efficiency of all saved SA-11 whole-beam fields.

No physical solves or validity bypass. Rejected-state wake diagnostics use the
existing frozen-wake convention and preserve every original printed target.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.trefftz import wake_forces

PRIOR = ROOT/'artifacts/isae/sa11-whole-beam-polar-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def block(path, name):
    rows, active = [], False
    for line in path.read_text().splitlines():
        line = line.split('#')[0].strip()
        if line == name:
            active = True
        elif active and line == 'End':
            return np.array(rows)
        elif active and line:
            assert not line.startswith('*')
            rows.append(list(map(float, line.split())))
    raise AssertionError(name)


def scalar_wake(start, end, points, gamma, speed, rho, reference):
    """Independent 2D infinite-filament sum for body-x frozen wake."""
    endpoints = [(float(p[1]), float(p[2]), float(sign*g)) for a, sign in ((start, -1.), (end, 1.)) for p, g in zip(a, gamma)]
    velocity, drag_terms, lift_terms, side_terms = [], [], [], []
    for left, right, point, circulation in zip(start, end, points, gamma):
        vy, vz = [], []
        for y, z, strength in endpoints:
            dy, dz = float(point[1])-y, float(point[2])-z
            d2 = dy*dy+dz*dz
            assert d2 > 0, 'This independent check requires nonsingular probes.'
            vy.append(-strength*dz/d2)
            vz.append(strength*dy/d2)
        v = [0., math.fsum(vy)/(2*math.pi), math.fsum(vz)/(2*math.pi)]
        dy, dz = float(right[1])-float(left[1]), float(right[2])-float(left[2])
        drag_terms.append(-.5*rho*float(circulation)*(-dz*v[1]+dy*v[2]))
        lift_terms.append(rho*speed*float(circulation)*dy)
        side_terms.append(-rho*speed*float(circulation)*dz)
        velocity.append(v)
    area, _, span = reference[0]
    qS = .5*rho*speed**2*area
    cli, cyi, cdi = [math.fsum(values)/qS for values in (lift_terms, side_terms, drag_terms)]
    return dict(CLi=cli, CYi=cyi, CDi=cdi, efficiency=(cli*cli+cyi*cyi)*area/(math.pi*span*span*cdi)), np.array(velocity)


def main():
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output.resolve()
    assert not out.exists(), out
    old = read(PRIOR/'analysis.json')
    pins = dict(read(PRIOR/'plan.json')['pins'])
    for name, pin in pins.items(): assert sha(ROOT/name) == pin, name
    assert read(PRIOR/'verification.json')['analysis_sha256'] == sha(PRIOR/'analysis.json')
    for item in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        assert sha(ROOT/item['local_pdf']) == item['sha256']
    model_path = ROOT/'examples/isae-sa11-wingtip-up.asw'
    reference = block(model_path, 'Reference')
    _, rho, sound = block(model_path, 'Constant')[0]
    parent = ROOT/'artifacts/isae/sa11-winglet-polar-20261108/plan.json'
    parent_pins = read(parent)['unchanged_pins']
    table_name = next(name for name in parent_pins if name.endswith('Wing_tip_up/wingtip_up_Ma_0_70.txt'))
    table = ROOT/table_name
    assert sha(table) == parent_pins[table_name]
    raw = {}
    for line in table.read_text().splitlines():
        t = line.split()
        if len(t) == 82 and t[0].isdigit() and 0 <= float(t[71]) <= 5:
            assert float(t[71]) not in raw
            raw[float(t[71])] = t
    assert len(raw) == len(old['cases']) == 21
    for path in (Path(__file__), PRIOR/'analysis.json', PRIOR/'verification.json', table):
        pins[str(path.relative_to(ROOT))] = sha(path)
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out/'driver-used.py')
    write(out/'plan.json', dict(observed_utc=utc(), pins=pins, alphas=sorted(raw),
        previous_turn='Progress: all21 whole-beam states show close formal CL/CD while exactly two root points remain Mach-invalid.',
        protocol='Reuse all21 converged/rejected fields. Cross native/whole receiver sampling with old/new circulation at identical source endpoints; evaluate the existing frozen body-x Trefftz operator without re-solving or computing undefined moments.',
        references='Drela steady section8.1, Eqs.207-211, p49; section4.6, p36. Production theta-midpoint wake quadrature retained; no substitution of near-field drag.',
        limits='Formal wake diagnostics of rejected report-minus4 states, not accepted loads or primary passes. Archive CD-CDi is not assumed to equal profile drag. No fitting, local Mach clipping, changed geometry or source constants.'))
    errors = dict(velocity=0., coefficient=0., endpoint=0.)
    rows = []
    for prior in old['cases']:
        report_path = ROOT/prior['report']
        assert sha(report_path) == prior['report_sha256']
        report = read(report_path)
        folder = report_path.parent
        for name, pin in report['artifact_sha256'].items(): assert sha(folder/name) == pin, name
        source_report = ROOT/report['source_report']
        assert sha(source_report) == report['source_report_sha256']
        source = read(source_report)
        native_path = source_report.parent/'native-fields.npz'
        assert sha(native_path) == source['artifact_sha256']['native-fields.npz']
        with np.load(native_path) as f:
            native = {k:f[k].copy() for k in ('RV1','RV2','RV')}
        with np.load(folder/'geometry.npz') as f:
            geometry = {k:f[k].copy() for k in ('a','b','hv','rm')}
        errors['endpoint'] = max(errors['endpoint'], float(np.max(abs(native['RV1']-geometry['a']))), float(np.max(abs(native['RV2']-geometry['b']))))
        reference_row = raw[prior['alpha']]
        target = dict(CDi=float(reference_row[79]), efficiency=float(reference_row[81]))
        assert float(reference_row[69]) == 240. and float(reference_row[70]) == 0.
        replays = {}
        for label in ('native-old', 'native-new', 'whole-old', 'whole-new'):
            with np.load(folder/f'{label}.npz') as f:
                gamma = f['gamma'].copy()
            points = native['RV'] if label.startswith('native') else geometry['rm']
            result = wake_forces(geometry['a'], geometry['b'], points, gamma,
                np.array([1.,0.,0.]), np.array([0.,1.,0.]), np.array([0.,0.,1.]), 240., rho, reference)
            assert result['available'], result['reason']
            scalar, velocity = scalar_wake(geometry['a'], geometry['b'], points, gamma, 240., rho, reference)
            errors['velocity'] = max(errors['velocity'], float(np.max(abs(velocity-np.array(result['velocity_body'])))))
            errors['coefficient'] = max(errors['coefficient'], *(abs(scalar[k]-result[k]) for k in scalar))
            replays[label] = {k:result[k] for k in ('CLi','CYi','CDi','efficiency','induced_drag')}
        final = replays['whole-new']
        formal_near = report['replays']['whole-new']['CD_terms']['circulation']
        decomposition = {}
        for key in ('CDi','efficiency'):
            a,b,c,d = [replays[k][key] for k in ('native-old','whole-old','native-new','whole-new')]
            receiver = .5*math.fsum([b,-a,d,-c]); circulation = .5*math.fsum([c,-a,d,-b])
            assert abs(receiver+circulation-(d-a)) < 1e-14
            decomposition[key] = dict(change=d-a, receiver=receiver, circulation=circulation)
        row = dict(alpha=prior['alpha'], source_report=prior['report'], source_report_sha256=sha(report_path),
            status='REJECTED_STATE_WAKE_DIAGNOSTIC', target=target, reference_tokens=dict(CDi=reference_row[79], efficiency=reference_row[81]),
            replays=replays, errors_percent={key:100*(final[key]/target[key]-1) for key in target},
            old_errors_percent={key:100*(replays['native-old'][key]/target[key]-1) for key in target},
            symmetric_decomposition=decomposition, formal_near_CD=report['replays']['whole-new']['formal_CD'],
            formal_near_vortex_CD=formal_near, formal_profile_CD=sum(report['replays']['whole-new']['CD_terms'][k] for k in ('friction','pressure','stall')),
            near_vortex_minus_trefftz=formal_near-final['CDi'],
            invalid_receiver_count=prior['invalid_receivers'], maximum_local_mach=prior['new_maximum_mach'])
        assert prior['production_status'] == 'rejected' and row['invalid_receiver_count'] == 2
        rows.append(row)
    assert errors['endpoint'] < 2e-11 and errors['velocity'] < 2e-9 and errors['coefficient'] < 2e-12, errors
    for name, pin in pins.items(): assert sha(ROOT/name) == pin, name
    result = dict(observed_utc=utc(), cases=rows, verification_errors=errors,
        source_pins_verified=len(pins), field_replays=84, physical_solves=0, accepted_loads=0, primary_passes_added=0,
        error_ranges_percent={key:[min(r['errors_percent'][key] for r in rows),max(r['errors_percent'][key] for r in rows)] for key in ('CDi','efficiency')},
        near_minus_trefftz_range=[min(r['near_vortex_minus_trefftz'] for r in rows),max(r['near_vortex_minus_trefftz'] for r in rows)],
        interpretation='Native CDi and efficiency are separate Trefftz quantities. Do not identify CD-CDi with profile drag when near-field vortex drag differs from Trefftz. Every full production state remains Mach-rejected.',
        artifact_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    write(out/'analysis.json', result)
    print(json.dumps({k:result[k] for k in ('error_ranges_percent','near_minus_trefftz_range','verification_errors','source_pins_verified','physical_solves')}), flush=True)


if __name__ == '__main__': main()
