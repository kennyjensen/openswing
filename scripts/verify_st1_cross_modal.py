"""Two bounded ST-1 modal checks with explicitly reconstructed cross-ply properties."""
import argparse
from pathlib import Path

import verify_st1_modal_mechanics as modal

common = modal.common
ROOT = common.ROOT
ORIGINAL = modal.BASE
CASE = dict(model='cross-physical', mass=.0683, icc=1.31e-8, inn=5.13e-6,
            fields=dict(EIcc=.707, GJ=.183, EInn=276., GKc=8.7e6,
                        EA=3.7e6, GKn=2.9e5, EIcs=0.),
            targets=dict(modal.PENDING['cross']['targets']))


def prepare(out):
    prior = common.read(ROOT/'artifacts/isae/st1-modal-mechanics-20261109/plan.json')
    common.authenticate(prior['pins'])
    out.mkdir()
    (out/'inputs').mkdir()
    source = (ORIGINAL/'[0_90]_3s.asw').read_text()
    lines = source.splitlines(keepends=True)
    headers = [i for i, line in enumerate(lines) if line.split()[:6] == ['t', 'x', 'y', 'z', 'chord', 'Xax']]
    assert len(headers) == 1
    index = headers[0] + 1
    fields = lines[index-1].split()
    scales = lines[index].split()
    assert len(fields) == 15 and len(scales) == 17 and scales[0] == '*'
    assert float(scales[1+fields.index('GKn')]) == 1e-5
    assert float(scales[1+fields.index('mgcc')]) == 1
    assert float(scales[-1]) == 9.81
    scales[1+fields.index('GKn')] = '1.0'
    scales[1+fields.index('mgcc')] = '9.8100'
    lines[index] = ' '.join(scales[:-1]) + '\n'
    derived = out/'inputs/cross-physical.asw'
    derived.write_text(''.join(lines))
    pins = dict(prior['pins'])
    for path in (Path(__file__), derived, ROOT/'reference/st1-minguet-1989/source.json',
                 ROOT/'reference/st1-minguet-1989/extraction.json',
                 ROOT/'reference/st1-minguet-1989/minguet-1989-thesis.pdf',
                 ROOT/'reference/st1-minguet-1989/minguet-1989-thesis.txt'):
        pins[path.relative_to(ROOT).as_posix()] = common.sha(path)
    assert common.sha(ROOT/'reference/st1-minguet-1989/minguet-1989-thesis.pdf') == '4ee59d32409a3becc9f7ffa0efc2fede65c03c079c8770084296ce8a7cdc9349'
    common.write(out/'plan.json', dict(
        observed_utc=common.utc(), pins=pins, cases={'cross': CASE},
        jobs=[dict(case='cross', nominal=n) for n in (40, 80)],
        modal_survey=dict(count=12, shift=[-.01, 0.], method='full_shift_invert', step=1e-5),
        named_frequency_required=22, reconstruction_targets=4, relative_tolerance=.05,
        source='ISAE Part III Table 3 p35; targets declared previously, unchanged.',
        changes=[
            'Restore GKn multiplier 1: Minguet Table5.1 p100 and Table5.2(a) p124, ISAE Table7 p52 give 2.9e5 N.',
            'Use mgcc multiplier 9.81 to convert the unchanged raw 1.31e-8 kg m to weight inertia; ISAE Table9 units.',
            'Remove the surplus unnamed final scale; preserve all 15 named columns and raw table entries.',
            'Runner appends End to the empty Engine block, as in the prior modal study.'],
        retained_conflicts=[
            'Mass .0683 kg/m agrees with original modal raw input and Minguet p124, but ISAE Table9 says .0795.',
            'GKc 8.7e6 N agrees with original modal input and Minguet; ISAE Table7 says 2.6e5.',
            'mgnn raw 5.13e-6 kg m retained; ISAE Table9 says 5.3e-6, Minguet gives polar inertia 5.13e-6.',
            'This is a physical-property reconstruction, not unchanged-input or historical-executable parity.'],
        physics=prior['physics'], selection=prior['selection'], gates=prior['gates'],
        limits=prior['limits'], primary_archive_passes_added=0,
        classification='Conditional reconstruction; do not automatically merge into primary accepted comparisons.'))
    print('Declared two cross-ply jobs with four unchanged targets; no production/source archive edits.')


def summarize(out):
    import numpy as np
    plan = common.read(out/'plan.json')
    common.authenticate(plan['pins'])
    packets = []
    for index in range(2):
        folder = out/f'job-{index}'
        report = common.read(folder/'report.json')
        assert report['plan_sha256'] == common.sha(out/'plan.json')
        for name, digest in report['artifacts'].items():
            assert common.sha(folder/name) == digest
        raw = common.read(folder/'result.json')
        t = np.array([n['t'] for n in raw['base']['nodes']])
        q = np.array([n['rotation'] for n in raw['base']['nodes']])
        modes = {}
        for row in report['comparisons']:
            mode = next(m for m in raw['modes'] if m['index'] == row['mode_index'])
            parts = []
            for name in ('displacement', 'rotation'):
                v = np.array([n[name]['real'] for n in mode['output']['nodes']]) + 1j*np.array([n[name]['imag'] for n in mode['output']['nodes']])
                parts.append(np.einsum('nji,nj->ni', q, v))
            modes[row['label']] = np.column_stack(parts)
        packets.append(dict(t=t, modes=modes, report=report))
        del raw
    coarse, fine = packets
    t = coarse['t']
    weights = np.zeros(len(t))
    weights[:-1] += np.diff(t)/2
    weights[1:] += np.diff(t)/2
    inertia = np.array([CASE['mass']]*3 + [CASE['icc'], CASE['icc']+CASE['inn'], CASE['inn']])
    rows = []
    for c, f in zip(coarse['report']['comparisons'], fine['report']['comparisons'], strict=True):
        assert c['label'] == f['label']
        label = f['label']
        field = fine['modes'][label]
        interp = np.column_stack([np.interp(t, fine['t'], field[:,j].real) + 1j*np.interp(t, fine['t'], field[:,j].imag) for j in range(6)])
        u = (coarse['modes'][label] * np.sqrt(weights[:,None]*inertia)).ravel()
        v = (interp * np.sqrt(weights[:,None]*inertia)).ravel()
        mac = float(abs(np.vdot(u,v))**2 / (np.vdot(u,u).real*np.vdot(v,v).real))
        change = abs(c['actual_Hz']/f['actual_Hz']-1)
        rows.append(dict(**f, coarse_Hz=c['actual_Hz'], mesh_change_percent=100*change,
                         shape_MAC=mac, accepted=c['passed'] and f['passed'] and change<.01 and mac>.99))
    summary = dict(observed_utc=common.utc(), required=4, passed=sum(r['accepted'] for r in rows), rows=rows,
                   conditional_reconstruction=True, primary_passes_added=0, primary_archive_passes_added=0,
                   production_physics_changed=False, plan_sha256=common.sha(out/'plan.json'),
                   reports={f'job-{i}/report.json':common.sha(out/f'job-{i}/report.json') for i in range(2)})
    common.write(out/'summary.json', summary)
    print(summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','run','summary'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    common.bounded()
    out = args.output.resolve()
    if args.action == 'prepare': prepare(out)
    elif args.action == 'summary': summarize(out)
    else:
        modal.BASE = out/'inputs'
        modal.run(out, args.index)
