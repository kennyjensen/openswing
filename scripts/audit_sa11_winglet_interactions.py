"""Account for SA-11 main/winglet drag interactions using nine saved states.

No physical solves or modified force laws. Frozen body-x wake/PG mapping;
actual flight direction is retained when projecting forces onto drag.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/sa11-same-mainwing-20261108'
FINE = ROOT / 'artifacts/isae/sa11-same-mainwing-mesh-20261108'
UPPER = ROOT / 'artifacts/isae/sa11-minimum-spacing-20261108'
UPPER_GEOMETRY = ROOT / 'artifacts/isae/sa11-paper-aligned-20261108/upper_winglet-m0_70-a21/geometry.npz'
OPERATOR = ROOT / 'scripts/audit-sa11-extension-drag-pairs.py'
AVL = ROOT / 'scripts/avl_vorvelc_reference.py'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def bounded():
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        assert os.environ.get(key) == '1'
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)


def authenticate(pins):
    for path, digest in pins.items():
        assert sha(ROOT / path) == digest, path


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def prepare(out):
    bounded()
    assert not out.exists()
    pins = {}
    for folder in (BASE, FINE):
        analysis = read(folder / 'analysis.json')
        assert analysis['verified']
        authenticate(analysis['pins'])
        pins.update(analysis['pins'])
        pins[str((folder / 'analysis.json').relative_to(ROOT))] = sha(folder / 'analysis.json')
    catalog = ROOT / 'docs/validation/aswing-authoritative-sources.json'
    for entry in read(catalog)['files']:
        if entry['id'] in ('isae-part-1', 'drela-steady') or entry['filename'] == 'drela-aswing-steady.pdf':
            for field, digest in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
                path = ROOT / entry[field]
                assert sha(path) == entry[digest]
                pins[entry[field]] = entry[digest]
    cases = []
    for count, configuration, angles in [
        (32, 'bare', (3., 3.25, 3.5)), (32, 'upper', (2.75, 3.)),
        (62, 'bare', (3., 3.25)), (62, 'upper', (2.75, 3.)),
    ]:
        for alpha in angles:
            if count == 62:
                config = 'wing_alone' if configuration == 'bare' else 'upper_winglet'
                folder = FINE / f'{config}-main64-m0_70-a{int(4*alpha):02d}'
            elif configuration == 'bare':
                folder = BASE / f'mainwing-control-m0_70-a{int(4*alpha):02d}'
            else:
                folder = UPPER / f'm0_70-a{int(4*alpha):02d}'
            geometry = UPPER_GEOMETRY if count == 32 and configuration == 'upper' else folder / 'geometry.npz'
            report = read(folder / 'report.json')
            assert report['status'] in ('computed', 'COMPUTED_DIAGNOSTIC')
            assert report['case']['condition']['freeze_influences'] is True
            for path in (folder / 'report.json', folder / 'accepted.json', geometry):
                pins[str(path.relative_to(ROOT))] = sha(path)
            cases.append(dict(id=f'{configuration}-main{count}-a{int(4*alpha):02d}', main_intervals=count,
                              configuration=configuration, alpha=alpha, speed=240.,
                              accepted=str((folder / 'accepted.json').relative_to(ROOT)),
                              report=str((folder / 'report.json').relative_to(ROOT)),
                              geometry=str(geometry.relative_to(ROOT))))
    for path in (Path(__file__), OPERATOR, AVL, catalog,
                 ROOT / 'docs/validation/aswing-authoritative-references.md'):
        pins[str(path.relative_to(ROOT))] = sha(path)
    out.mkdir(parents=True)
    (out / 'driver-used.py').write_text(Path(__file__).read_text())
    write(out / 'plan.json', dict(observed_utc=utc(), pins=pins, cases=cases,
        previous_goal_turn='Progress: same-main-wing control and six main-mesh trials completed and independently verified; near-field drag changes while Trefftz benefit nearly matches at one sample.',
        source_basis='Jan Part I p35 and Fig22 p39; Drela steady Eqs55--56,64--70,149--161,207--211. Conservative local force uses bound-location velocity; Trefftz is a separate observable.',
        protocol='Nine accepted240m/s states covering both CL=.5 brackets and alpha3 for bare/upper on main32/62, winglets16each. Split exact saved forces into ordered receiver/source beam blocks, and bound/half-infinite/finite-origin terms. Within main-main separate own, adjacent and other pairs. Keep all wake terms and exclude own bound only. Compare same-alpha and guarded equal-lift increments. No field replacement or fitted input.',
        geometry='Frozen body-x wake and PG direction; drag projection uses actual incidence. Main geometry identical within each pair; winglet geometry identical between meshes.',
        physical_solves=0, primary_passes_added=0,
        limits='One BLAS thread,512MiB address space,15CPU/25wall seconds per saved-state audit. No browser or background jobs.'))
    print(json.dumps(dict(prepared=True, saved_states=len(cases), pins=len(pins))))


def run(out, index):
    bounded()
    started = time.monotonic()
    plan = read(out / 'plan.json')
    authenticate(plan['pins'])
    case = plan['cases'][index]
    folder = out / case['id']
    assert not folder.exists()
    import numpy as np
    raw = read(ROOT / case['accepted'])
    with np.load(ROOT / case['geometry']) as f:
        g = {key: f[key] for key in f}
    assert raw['converged'] and raw['residual'] < 1e-8
    assert all(s['normal_mach'] < 1 for s in raw['strips'])
    gamma = np.array([s['circulation'] for s in raw['strips']], dtype=np.longdouble)
    beam = np.array([s['beam'] for s in raw['strips']])
    v = np.array([s['relative_velocity'] for s in raw['strips']])
    assert sum(beam == 1) == case['main_intervals']
    assert np.array_equal(g['hv'], [s['velocity_position'] for s in raw['strips']])
    assert np.array_equal(g['ds'], [s['length'] for s in raw['strips']])
    alpha = math.radians(case['alpha'])
    e = np.array([math.cos(alpha), 0., math.sin(alpha)], dtype=np.longdouble)
    rho, speed = 1.2256, case['speed']
    qs = .5 * rho * speed**2 * .9329
    beta = np.sqrt(np.longdouble(1) - np.longdouble(speed / 340.21)**2)
    tensors = module(OPERATOR, 'pair_operator').operators(g['hv'], g['a'], g['b'], beta)
    # Cross-check the combined field against the separately transcribed native
    # AVL zero-core formulas, correcting its rounded inverse-four-pi constant.
    native = module(AVL, 'native_operator').matrix(g['hv'], g['a'], g['b'], speed / 340.21,
                    exclude_self=True, core_fraction=0., dtype=np.longdouble)
    native *= 1 / (4 * np.arccos(np.longdouble(-1)) * np.longdouble('.079577472'))
    combined = sum(tensors.values())
    operator_error = float(np.max(abs(combined - native)))
    induced = np.einsum('ijq,j->iq', combined, gamma)
    velocity_error = float(np.max(abs(induced + speed * e - v)) / speed)
    assert operator_error < 2e-10 and velocity_error < 2e-10
    measure = np.asarray(g['span'] * g['ds'][:, None], dtype=np.longdouble)
    pairs = {name: rho * gamma[:, None] * gamma[None, :] *
             (np.cross(tensor, measure[:, None, :]) @ e) / qs
             for name, tensor in tensors.items()}
    # Uniform freestream force has exactly zero drag projection analytically.
    uniform = rho * gamma[:, None] * np.cross(speed * e, measure)
    uniform_drag = float((uniform @ e).sum() / qs)
    assert abs(uniform_drag) < 2e-14
    error = abs(float(sum(p.sum() for p in pairs.values())) - raw['CDi_near'])
    assert error < 2e-12
    ii, jj = np.indices((len(beam), len(beam)))
    main = beam == 1
    blocks = {
        'main_from_main': main[:, None] & main[None, :],
        'main_from_winglet': main[:, None] & ~main[None, :],
        'winglet_from_main': ~main[:, None] & main[None, :],
        'winglet_from_winglet': ~main[:, None] & ~main[None, :],
    }
    details = {
        'main_own': blocks['main_from_main'] & (ii == jj),
        'main_adjacent': blocks['main_from_main'] & (abs(ii - jj) == 1),
        'main_other': blocks['main_from_main'] & (abs(ii - jj) > 1),
        **{key: mask for key, mask in blocks.items() if key != 'main_from_main'},
    }
    assert np.all(sum(mask.astype(int) for mask in details.values()) == 1)
    totals = {name: float(p.sum()) for name, p in pairs.items()}
    partition = {name: {key: float(p[mask].sum()) for key, mask in blocks.items()} for name, p in pairs.items()}
    detail = {name: {key: float(p[mask].sum()) for key, mask in details.items()} for name, p in pairs.items()}
    # Store each ordered contribution for an independent scalar reduction and
    # exact same-mesh subtraction; none is removed from the production force.
    folder.mkdir()
    np.savez(folder / 'pairs.npz', **{key: np.asarray(p, dtype=float) for key, p in pairs.items()},
             gamma=np.asarray(gamma, dtype=float), beam=beam, t=np.array([s['t'] for s in raw['strips']]),
             ds=g['ds'], a=g['a'], b=g['b'], hv=g['hv'], span=g['span'])
    report = dict(observed_utc=utc(), case=case, CL=raw['CL'], CD=raw['CD'], CDi=raw['CDi'],
                  CDi_near=raw['CDi_near'], CDp=raw['CDp'], totals=totals, blocks=partition, details=detail,
                  errors=dict(operator=operator_error, velocity_relative=velocity_error, near_CD=error,
                              uniform_drag=abs(uniform_drag)), physical_solves=0,
                  plan_sha256=sha(out / 'plan.json'), pairs_sha256=sha(folder / 'pairs.npz'),
                  seconds=time.monotonic()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    write(folder / 'report.json', report)
    print(json.dumps(dict(id=case['id'], CDi_near=raw['CDi_near'], errors=report['errors'],
                         seconds=report['seconds'], peak_rss_kib=report['peak_rss_kib'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'run'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--index', type=int)
    args = p.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        run(args.output.resolve(), args.index)
    signal.alarm(0)
