"""Pinned SA-10 polars; failed states and literal attachment errors are retained."""
from pathlib import Path
import hashlib, json, sys, time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from isae_sa10_reference import CACHE, REVISION, sha

DEST = ROOT / 'docs/validation'
COEFFICIENTS = ['CL', 'CD', 'CDi', 'CDi_near', 'CDp', 'Cm', 'Cl', 'Cn', 'CY']


def compute(source, spec):
    model = parse_asw(source)
    condition = FlightCondition(speed=55., alpha=spec['alpha'],
        mach=0. if spec['pg'] == 'zero' else None, freeze_influences=spec['frozen'])
    result = solve_rigid(model, condition, panels=spec['panels'])
    assert result['converged'] and result['residual'] <= 1e-8
    strips = result['strips']
    qS = .5 * model.constants[1] * 55.**2 * model.reference[0, 0]
    chord, span = model.reference[0, 1:3]
    force = np.sum([s['force'] for s in strips], axis=0)
    moment = np.sum([np.cross(np.array(s['position']) - model.reference[1], s['force'])
                     + s['moment'] for s in strips], axis=0)
    angle = np.deg2rad(spec['alpha']); c, s = np.cos(angle), np.sin(angle)
    independent = dict(CL=force @ [-s, 0, c] / qS, CD=force @ [c, 0, s] / qS,
                       CY=force[1] / qS, Cm=moment[1] / qS / chord,
                       Cl=-moment[0] / qS / span, Cn=-moment[2] / qS / span)
    error = max(abs(value - result[key]) for key, value in independent.items())
    drag_error = abs(result['CD'] - sum(result[k] for k in
        ['CDi_near', 'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate']))
    assert max(error, drag_error) < 2e-10, (spec, error, drag_error)
    beams = []
    for beam in model.beams:
        local = [s for s in strips if s['beam'] == beam.index]
        f = np.sum([s['force'] for s in local], axis=0)
        beams.append(dict(beam=beam.index, strips=len(local), force=f.tolist(),
            CL=float(f @ [-s, 0, c] / qS), CD=float(f @ [c, 0, s] / qS),
            maximum_absolute_cl=max(abs(s['cl']) for s in local),
            maximum_normal_mach=max(s['normal_mach'] for s in local)))
    output = dict(**{k: float(result[k]) for k in COEFFICIENTS},
        residual=float(result['residual']), evaluations=result['evaluations'],
        solver=result['circulation_solver'], actual_strips=len(strips),
        force=force.tolist(), moment=moment.tolist(), beam_loads=beams,
        independent_wrench_error=float(error), drag_decomposition_error=float(drag_error),
        maximum_normal_mach=result['lifting_airflow']['maximum'],
        stalled_strips=sum(s['stalled'] for s in strips),
        influences=result['aerodynamic_influences'], wake_core=result['wake_core'])
    if spec['alpha'] in [0., 5., 15., 25.]:
        output['profiles'] = [{k: s[k] for k in ['beam', 't', 'position', 'length',
            'circulation', 'cl', 'force', 'normal_mach', 'normal_speed', 'stalled']} for s in strips]
    return output


def metrics(actual, reference):
    error = np.asarray(actual) - np.asarray(reference)
    if not len(error):
        return dict(count=0, bias=None, rmse=None, maximum_absolute_error=None)
    return dict(count=len(error), bias=float(error.mean()),
        rmse=float(np.sqrt(np.mean(error**2))), maximum_absolute_error=float(max(abs(error))))


def case_entries(sources):
    entries = []
    for name in ['wing_alone', 'wing_extension', 'Louvered', 'TS_60_45_30', 'TS_60_40_80', 'TS_80_60_40']:
        entry = next(m for m in sources['models'] if m['name'] == name)
        reconstructed = name == 'TS_60_45_30'
        entries.append(dict(name=name, case_id=name + ('_repaired_joints' if reconstructed else '_literal'),
            reconstructed=reconstructed, path=entry['path'], source_sha256=entry['sha256'],
            source=sources['derived']['source'] if reconstructed else entry['source']))
    return entries


def comparisons(cases, sources):
    archived, experimental, meshes = [], [], []
    for case in cases:
        name = case['name']; source = next(m for m in sources['models'] if m['name'] == name)
        lookup = {(r['specification']['panels'], r['specification']['pg'],
                   r['specification']['frozen'], r['specification']['alpha']): r for r in case['runs']}
        for frozen in [False, True]:
            for pg in ['zero', 'speed']:
                for panels in [25, 50, 100]:
                    # Duplicate alpha=12 remains in the source audit, not the statistics.
                    unique = {row[74]: row for row in source['archived']['rows']}
                    pairs = [(lookup.get((panels, pg, frozen, alpha)), row)
                             for alpha, row in unique.items() if row[2] == 1]
                    valid = [(a, b) for a, b in pairs if a and a['status'] == 'computed']
                    archived.append(dict(case=case['case_id'], panels=panels, pg=pg, frozen=frozen,
                        requested=len(pairs), computed=len(valid),
                        errors={k: metrics([a['result'][k] for a, b in valid], [b[j] for a, b in valid])
                                for k, j in [('CL', 77), ('CD', 78), ('CDi', 79), ('Cm', 80)]}))
                    if name in sources['experimental_lift']:
                        data = sources['experimental_lift'][name]['values']
                        pairs = [(lookup.get((panels, pg, frozen, row['xy'][0])), row) for row in data]
                        valid = [(a, b) for a, b in pairs if a and a['status'] == 'computed']
                        experimental.append(dict(case=case['case_id'], panels=panels, pg=pg, frozen=frozen,
                            requested=len(pairs), computed=len(valid),
                            CL=metrics([a['result']['CL'] for a, b in valid], [b['xy'][1] for a, b in valid])))
                for low, high in [(25, 50), (50, 100)]:
                    pairs = [(lookup.get((low, pg, frozen, alpha)), lookup.get((high, pg, frozen, alpha)))
                             for alpha in range(26)]
                    valid = [(a, b) for a, b in pairs if a and b and a['status'] == b['status'] == 'computed']
                    meshes.append(dict(case=case['case_id'], pg=pg, frozen=frozen, low=low, high=high,
                        requested=len(pairs), computed=len(valid), errors={k: metrics(
                            [a['result'][k] for a, b in valid], [b['result'][k] for a, b in valid])
                            for k in COEFFICIENTS}))
    return dict(archived_comparisons=archived, experimental_lift_comparisons=experimental, mesh_comparisons=meshes)


def main():
    sources = json.loads((DEST / 'isae-sa10-sources.json').read_text())
    pins = {p.name: sha(p) for p in sorted((ROOT / 'openswing').glob('*.py'))}
    identity = dict(modules=pins, script_sha256=sha(Path(__file__)),
        reference_script_sha256=sha(ROOT / 'scripts/isae_sa10_reference.py'),
        source_report_sha256=sha(DEST / 'isae-sa10-sources.json'))
    runroot = ROOT / '.reference/isae-sa10-runs' / hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    runroot.mkdir(parents=True, exist_ok=True)
    (runroot / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    cases = case_entries(sources)
    for case in cases:
        assert sha(CACHE / case['path']) == case['source_sha256']
        case['runs'] = []
        alphas = sorted(set(range(26)) | {r['xy'][0] for r in sources['experimental_lift'].get(case['name'], {}).get('values', [])})
        for panels in [25, 50, 100]:
            for frozen in [False, True]:
                for pg in ['zero', 'speed']:
                    for alpha in alphas:
                        spec = dict(case=case['case_id'], panels=panels, pg=pg, frozen=frozen, alpha=float(alpha))
                        key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
                        path = runroot / (key + '.json')
                        if path.exists():
                            row = json.loads(path.read_text()); assert row['specification'] == spec
                        else:
                            print('START', json.dumps(spec), flush=True); start = time.monotonic()
                            try:
                                row = dict(specification=spec, status='computed', result=compute(case['source'], spec))
                            except AnalysisError as exc:
                                row = dict(specification=spec, status='rejected', error=str(exc), details=getattr(exc, 'details', None))
                            row['seconds'] = time.monotonic() - start
                            temporary = path.with_suffix('.tmp'); temporary.write_text(json.dumps(row, indent=2) + '\n'); temporary.replace(path)
                        case['runs'].append(dict(**row, cache_sha256=sha(path), cache_path=path.relative_to(ROOT).as_posix()))
                    print('GROUP', case['case_id'], panels, frozen, pg, len(case['runs']), flush=True)
                    checkpoint = dict(status='RUNNING', runroot=str(runroot), cases=cases, provenance=identity)
                    (runroot / 'progress.json').write_text(json.dumps(checkpoint, indent=2) + '\n')
    assert pins == {p.name: sha(p) for p in sorted((ROOT / 'openswing').glob('*.py'))}
    report = dict(status='QUANTITATIVE_COMPARISONS_WITH_UNRESOLVED_SETUP_AND_EXPERIMENTAL_DIFFERENCES',
        full_suite_validated=False, provenance=dict(**identity, revision=REVISION), cases=cases,
        literal_rejections=[dict(name=m['name'], setups=m['setups']) for m in sources['models']
                            if any(s['status'] == 'rejected' for s in m['setups'])],
        **comparisons(cases, sources), limitations=sources['limitations'],
        settings=dict(speed=55., alpha_range=[0, 25], panels=[25, 50, 100], pg=['zero', 'speed'], frozen=[False, True],
            solver='Unmodified production solve_rigid; each requested state starts independently with default nonlinear tolerances and continuation',
            experimental_lift='Solved at each supplied experimental alpha, without interpolating or fitting CL',
            experimental_drag='Requires separate fixed-lift branch analysis; no alpha inferred from the experimental drag table',
            timing='Recorded monotonic host timings are diagnostic, not portable performance claims'))
    (DEST / 'isae-sa10.json').write_text(json.dumps(report, indent=2) + '\n')
    print('COMPLETE', sum(len(c['runs']) for c in cases), 'states', flush=True)


if __name__ == '__main__':
    main()
