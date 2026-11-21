"""Predeclared independent pose diagnostics at three more archived SA-12 points."""
import argparse
from pathlib import Path

import diagnose_sa12_image_pose as diagnostic
import verify_sa12_current_pilot as io

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'artifacts/isae/sa12-image-pose-20261109'
POINTS = [('05', -5.), ('05', 5.), ('2', 8.)]


def prepare(out):
    io.bounded()
    parent = io.read(PARENT / 'plan.json')
    io.authenticate(parent['pins'])
    pins = dict(parent['pins'])
    for p in [Path(__file__), PARENT / 'plan.json']:
        pins[str(p.relative_to(ROOT))] = io.sha(p)
    jobs = io.adapter.plan(ROOT)
    cases = []
    assert not out.exists()
    out.mkdir(parents=True)
    for height, alpha in POINTS:
        job, = [j for j in jobs if j['flap'] == 'No_Flap' and j['height_label'] == height
                and j['settings']['alpha'] == alpha and j['settings']['panels'] == 100]
        name = f'No_Flap-h{height}-a{alpha:g}'
        folder = out / name
        folder.mkdir()
        io.write(folder / 'plan.json', dict(observed_utc=io.utc(), pins=pins,
            variants=diagnostic.VARIANTS, baseline_job=job, selected_variant_indices=[2, 3],
            scope='Only shared-wake interpretation and zero-pitch frozen control, no additional baseline solves. Alternative diagnostics, not primary validation.'))
        for index in (2, 3):
            cases.append(dict(point=name, variant_index=index))
    io.write(out / 'plan.json', dict(observed_utc=io.utc(), cases=cases, pins=pins,
        purpose='Use the archived negative/positive-alpha asymmetry and a second height to distinguish two plausible explanations of the close-ground residual. No tuning. Shared-wake deliberately fails full image reflection; it cannot become a default on numerical agreement alone.',
        diagnostic_equilibrium_calls=6, production_calls=0, primary_passes_added=0))
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    io.signal.alarm(0)
    print('Prepared six independent diagnostics at three additional archived points.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    out = args.output.resolve()
    if args.action == 'prepare':
        prepare(out)
    else:
        plan = io.read(out / 'plan.json')
        case = plan['cases'][args.index]
        diagnostic.run(out / case['point'], case['variant_index'])
