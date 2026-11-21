"""Fill six declared SA-11 upper/lower coverage gaps without changing setup."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

import verify_sa11_paper_aligned as recorder

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT / 'artifacts/isae/sa11-two-winglet-spacing-20261108'
ASSESSMENT = ROOT / 'artifacts/isae/sa11-paper-suite-aligned-20261108'


def prepare(out):
    recorder.bounded()
    assert not out.exists()
    parent = recorder.read(PARENT / 'plan.json')
    previous = recorder.read(ASSESSMENT / 'analysis.json')
    proof = recorder.read(ASSESSMENT / 'verification.json')
    assert proof['verified'] and proof['analysis_sha256'] == recorder.sha(ASSESSMENT / 'analysis.json')
    pins = dict(previous['pins'])
    pins.update(parent['pins'])
    recorder.check(pins)
    for name, digest in parent['generated_pins'].items():
        assert recorder.sha(PARENT / name) == digest
        pins[str((PARENT / name).relative_to(ROOT))] = digest
    cases = []
    # Quarter-degree brackets around CL=.3, plus the two missing alpha=3 checks.
    # Keep CL=.5/.7 required, without extending into post-stall operating points.
    for label, angles in [('0_70', (.5, .75, 3.)), ('0_80', (.25, .5, 3.))]:
        seed = next(c for c in parent['cases'] if c['label'] == label and c['alpha'] == 0)
        rows = [line.split() for line in (ROOT / seed['table']).read_text().splitlines()
                if len(line.split()) == 82 and line.split()[0].isdigit()]
        for alpha in angles:
            row = round(4 * alpha)
            condition = deepcopy(seed['condition'])
            condition['alpha'] = alpha
            assert float(rows[row][71]) == alpha
            cases.append(dict(id=f'upper_lower_winglets-m{label}-a{row:02d}',
                configuration='upper_lower_winglets', label=label, alpha=alpha, row=row,
                condition=condition, model_path=str((PARENT / 'model.asw').relative_to(ROOT)),
                mesh=recorder.read(PARENT / 'mesh-import.json')['panels'],
                table=seed['table'], tokens=rows[row], reused_accepted=None,
                reference={name: float(rows[row][column]) for name, column in recorder.FIELDS.items()}))
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    model = parse_asw((PARENT / 'model.asw').read_text(), beam_interpolation='natural-v1')
    meshes = model_meshes(model, cases[0]['mesh'])
    assert [len(m.tm) for m in meshes] == [32, 16, 16, 5, 5]
    assert all(m.beam.physical_index == 1 for m in meshes)
    assert all(np.all(m.beam.value('CLmax', m.tm) == .8) for m in meshes)
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    old_geometry = PARENT / 'm0_70-a00/geometry.npz'
    with np.load(old_geometry) as saved:
        for key in g:
            np.testing.assert_array_equal(g[key], saved[key])
    preflight = {'upper_lower_winglets': [dict(beam=m.beam.index,
        nodes=[float(m.t0[0]), *map(float, m.t1)], intervals=len(m.tm), minimum=float(min(m.length)))
        for m in meshes]}
    for path in (Path(__file__), Path(recorder.__file__), PARENT / 'plan.json',
                 PARENT / 'analysis.json', PARENT / 'verification.json', old_geometry,
                 ASSESSMENT / 'analysis.json', ASSESSMENT / 'verification.json',
                 ROOT / 'scripts/check_sa11_lower_coverage.py'):
        pins[str(path.relative_to(ROOT))] = recorder.sha(path)
    recorder.check(pins)
    out.mkdir(parents=True)
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    (out / 'recorder-used.py').write_text(Path(recorder.__file__).read_text())
    recorder.write(out / 'plan.json', dict(observed_utc=recorder.utc(), cases=cases,
        pins=pins, preflight=preflight, physical_calls=6,
        previous_goal_turn='Progress: representative 48-check scope authenticated; status clarified. Eight upper/lower targets remain missing.',
        protocol='Same disclosed upper/lower model, original CLmax=.8, fixed 32+16+16+5+5 mesh, minimum spacing and frozen influences. At240m/s alpha=.5,.75,3; at272m/s alpha=.25,.5,3. Fill CL=.3 brackets and alpha3 checks. No target, tolerance, parameter, mesh or equation changes; all failures and missing higher-lift targets retained.',
        source_basis='Jan PartI p35, Figure22 p39 and Figure40 p68; existing authenticated setup and source catalog. Post-stall repairs remain deferred.',
        limits='One physical call per foreground invocation, one BLAS thread,512MiB address-space,15CPU/25wall seconds; no browser/build/background jobs.'))
    recorder.signal.alarm(0)
    print(dict(prepared=True, physical_calls=len(cases), intervals=[len(m.tm) for m in meshes]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        recorder.batch(args.output.resolve(), args.index, 1)
