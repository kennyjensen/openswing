"""SA-11 native calculations: pinned inputs, resumable requests, all rejections retained."""
from pathlib import Path
import argparse, hashlib, json, os, sys, time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from isae_sa11_reference import REVISION, sha, NAMES

DEST = ROOT/'docs/validation'
COEFFICIENTS = ['CL', 'CD', 'CDi', 'CDi_near', 'CDp', 'Cm', 'Cl', 'Cn', 'CY']


def compute(source, specification):
    model = parse_asw(source); speed = specification['speed']
    condition = FlightCondition(speed=speed, alpha=specification['alpha'],
        mach=0. if specification['pg'] == 'zero' else None,
        freeze_influences=specification['frozen'])
    result = solve_rigid(model, condition, panels=specification['panels'])
    assert result['converged'] and result['residual'] <= 1e-8
    strips = result['strips']; qS = .5*model.constants[1]*speed**2*model.reference[0, 0]
    force = np.sum([row['force'] for row in strips], axis=0)
    moment = np.sum([np.cross(np.array(row['position'])-model.reference[1], row['force'])
                     + row['moment'] for row in strips], axis=0)
    alpha = np.deg2rad(specification['alpha']); c, s = np.cos(alpha), np.sin(alpha)
    independent = dict(CL=force@[-s, 0, c]/qS, CD=force@[c, 0, s]/qS, CY=force[1]/qS,
        Cm=moment[1]/qS/model.reference[0, 1], Cl=-moment[0]/qS/model.reference[0, 2],
        Cn=-moment[2]/qS/model.reference[0, 2])
    error = max(abs(value-result[key]) for key, value in independent.items())
    drag_error = abs(result['CD']-sum(result[key] for key in
        ['CDi_near', 'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate']))
    assert max(error, drag_error) < 2e-10, (specification, error, drag_error)
    origin = moment+np.cross(model.reference[1], force)
    beams = []
    for beam in model.beams:
        local = [row for row in strips if row['beam'] == beam.index]
        f = np.sum([row['force'] for row in local], axis=0)
        beams.append(dict(beam=beam.index, strips=len(local), force=f.tolist(),
            CL=float(f@[-s, 0, c]/qS), CD=float(f@[c, 0, s]/qS),
            maximum_absolute_cl=max(abs(row['cl']) for row in local),
            maximum_normal_mach=max(row['normal_mach'] for row in local)))
    out = dict(**{key: float(result[key]) for key in COEFFICIENTS},
        residual=float(result['residual']), evaluations=result['evaluations'],
        solver=result['circulation_solver'], actual_strips=len(strips),
        force=force.tolist(), moment=moment.tolist(), Cm_origin=float(origin[1]/qS/model.reference[0, 1]),
        beam_loads=beams, independent_wrench_error=float(error), drag_decomposition_error=float(drag_error),
        maximum_normal_mach=result['lifting_airflow']['maximum'],
        stalled_strips=sum(row['stalled'] for row in strips),
        influences=result['aerodynamic_influences'], wake_core=result['wake_core'],
        kinematic_mach=float(speed/model.constants[2]))
    if specification['alpha'] in [-1., 0., 5., 10.]:
        out['profiles'] = [{key: row[key] for key in ['beam', 't', 'position', 'length',
            'circulation', 'cl', 'force', 'normal_mach', 'normal_speed', 'stalled']} for row in strips]
    return out


def case_entries(sources):
    out = []
    for name in NAMES+['wingtip_up_cant0']:
        original = next(row for row in sources['models'] if row['name'] == name)
        derived = next((row for row in sources['derived'] if row['name'] == name), None)
        row = derived or original
        out.append(dict(name=name, case_id=derived['case_id'] if derived else name+'_literal',
            source=row['source'], source_sha256=row['sha256'], upstream_path=original['path'],
            upstream_source_sha256=original['sha256'], reconstructed=derived is not None,
            reconstruction_note=derived['note'] if derived else None,
            has_experimental_reference=name in NAMES))
    return out


def specification(case, panels, speed, alpha, pg='speed', frozen=False):
    return dict(case=case['case_id'], panels=int(panels), speed=float(speed),
        alpha=float(alpha) or 0., pg=pg, frozen=bool(frozen))


def request_key(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def requests(cases, sources, pilot=False):
    out = {}
    for case in cases:
        if pilot:
            for speed in [240., 272.]:
                for alpha in [0., 5., 10.]:
                    spec = specification(case, 25, speed, alpha); out[request_key(spec)] = spec
            continue
        archived = [row for row in sources['archived'] if row['name'] == case['name']]
        for panels in [25, 50, 100]:
            for frozen in [False, True]:
                if archived:
                    for table in archived:
                        assert len(table['speeds']) == 1 and table['actual_equals_reference_flow']
                        for pg in ['speed', 'zero']:
                            angles = table['alpha'] if pg == 'speed' else [0., 5., 10.]
                            for alpha in angles:
                                spec = specification(case, panels, table['speeds'][0], alpha, pg, frozen)
                                out[request_key(spec)] = spec
                else:
                    # Unmeasured cant0 input: a separately labeled numerical diagnostic.
                    for speed in [240., 255., 266., 272.]:
                        for pg in ['speed', 'zero']:
                            for alpha in [0., 5., 10.]:
                                spec = specification(case, panels, speed, alpha, pg, frozen)
                                out[request_key(spec)] = spec
        if case['has_experimental_reference']:
            sound = float(parse_asw(case['source']).constants[2])
            for mach, data in sources['experimental'].items():
                speed = float(mach)*sound
                for panels in [25, 50, 100]:
                    angles = [row['xy'][0] for row in data['lift'][case['name']]['values']]
                    if panels in [50, 100]:
                        angles += [-1.]+np.linspace(0, 10, 41).tolist()
                    for alpha in angles:
                        spec = specification(case, panels, speed, alpha)
                        out[request_key(spec)] = spec
    return list(out.values())


def cached_request(payload):
    import fcntl
    folder, source, spec = payload; folder = Path(folder)
    path = folder/(request_key(spec)+'.json')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            row = json.loads(path.read_text()); assert row['specification'] == spec
        else:
            start = time.monotonic()
            try:
                row = dict(specification=spec, status='computed', result=compute(source, spec))
            except AnalysisError as exc:
                row = dict(specification=spec, status='rejected', error=str(exc), details=getattr(exc, 'details', None))
            row['seconds'] = time.monotonic()-start
            temporary = path.with_suffix(f'.{os.getpid()}.tmp')
            temporary.write_text(json.dumps(row, indent=2)+'\n'); temporary.replace(path)
        row.update(cache_path=path.relative_to(ROOT).as_posix(), cache_sha256=sha(path))
        return row


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--workers', type=int, default=1); args = parser.parse_args()
    assert 1 <= args.workers <= 4
    sources = json.loads((DEST/'isae-sa11-sources.json').read_text())
    assert sources['revision'] == REVISION
    assert sources['script_sha256'] == sha(ROOT/'scripts/isae_sa11_reference.py')
    modules = {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    provenance = dict(revision=REVISION, modules=modules, script_sha256=sha(Path(__file__)),
        reference_script_sha256=sha(ROOT/'scripts/isae_sa11_reference.py'), source_report_sha256=sha(DEST/'isae-sa11-sources.json'))
    identity = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    folder = ROOT/'.reference/isae-sa11-runs'/identity; folder.mkdir(parents=True, exist_ok=True)
    manifest = folder/'identity.json'
    if manifest.exists(): assert json.loads(manifest.read_text()) == provenance
    else: manifest.write_text(json.dumps(provenance, indent=2)+'\n')
    cases = case_entries(sources); plan = requests(cases, sources, args.pilot)
    assert len(plan) == (30 if args.pilot else 5304), len(plan)
    source_map = {case['case_id']: case['source'] for case in cases}
    payloads = [(str(folder), source_map[spec['case']], spec) for spec in plan]
    print('START', 'pilot' if args.pilot else 'full', len(plan), 'requests;', args.workers, 'workers;', folder, flush=True)
    pool = None
    if args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        pool = ProcessPoolExecutor(max_workers=args.workers)
        iterator = pool.map(cached_request, payloads, chunksize=1, buffersize=2*args.workers)
    else: iterator = map(cached_request, payloads)
    rows = []; counts = dict(computed=0, rejected=0)
    try:
        for i, row in enumerate(iterator, 1):
            rows.append(row); counts[row['status']] += 1
            progress = dict(completed=i, total=len(plan), **counts, last=row['specification'], pilot=args.pilot)
            (folder/('pilot-progress.json' if args.pilot else 'progress.json')).write_text(json.dumps(progress, indent=2)+'\n')
            if i % 10 == 0 or i == len(plan): print(json.dumps(progress), flush=True)
    finally:
        if pool is not None: pool.shutdown(wait=True, cancel_futures=True)
    assert modules == {p.name: sha(p) for p in (ROOT/'openswing').glob('*.py')}
    for case in cases: case['runs'] = [row for row in rows if row['specification']['case'] == case['case_id']]
    result = dict(status='PILOT_NUMERICAL_DIAGNOSTIC' if args.pilot else 'COMPUTATIONS_COMPLETE_PHYSICAL_COMPARISONS_PENDING',
        provenance=provenance, cases=cases, total=len(rows), **counts, limitations=sources['limitations'],
        protocol=dict(archived='All41angles of all16polars; actual archived V; PG fromV/a, three meshes, bothK/F. PGoff only0/5/10degree diagnostics.',
            experimental='All88measured lift angles at exact nominal Mach .7/.8, current influences and PGon, three meshes. Additional -1 and0..10by.25degree scans at50/100intervals for matched-lift comparisons.',
            cant0='No measured or archived reference:3angles,4speeds,3meshes,2PG and2K/F settings; separate numerical diagnostic.',
            state_initialization='Every state starts independently with unmodified production tolerances and internal continuation. Archived solution-history equivalence is unverified.',
            drag='Raw force projection. No undocumented drag offset, section-property fit, velocity clipping or core adjustment.'))
    name = 'isae-sa11-pilot.json' if args.pilot else 'isae-sa11.json'
    temporary = DEST/(name+'.tmp'); temporary.write_text(json.dumps(result, indent=2)+'\n'); temporary.replace(DEST/name)
    print('COMPLETE',len(rows),counts,flush=True)


if __name__ == '__main__': main()
