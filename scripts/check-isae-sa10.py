"""Independent SA-10 force conventions, zero-lift drag, source and branch checks."""
from pathlib import Path
import fcntl, hashlib, importlib.util, json, sys, time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'scripts'))
from isae_sa10_reference import CACHE, sha
spec = importlib.util.spec_from_file_location('sa10', ROOT / 'scripts/verify-isae-sa10.py')
sa10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(sa10)
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
D = ROOT / 'docs/validation'


def finer_junction_probe(study, modules):
    assert modules == study['provenance']['modules'] == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    assert sha(ROOT / 'scripts/verify-isae-sa10.py') == study['provenance']['script_sha256']
    # Global loads can settle while a force-point velocity grows under refinement.
    # Probe the measured tip-sail variant once beyond the regular 100-panel grid.
    tip = next(c for c in study['cases'] if c['name'] == 'TS_60_45_30')
    limit_spec = dict(case=tip['case_id'], panels=150, pg='zero', frozen=False, alpha=25.)
    limit_identity = dict(modules=modules, compute_script_sha256=study['provenance']['script_sha256'],
        source_sha256=hashlib.sha256(tip['source'].encode()).hexdigest(), specification=limit_spec)
    limit_folder = ROOT / '.reference/isae-sa10-checks'; limit_folder.mkdir(exist_ok=True)
    limit_path = limit_folder / (hashlib.sha256(json.dumps(limit_identity, sort_keys=True).encode()).hexdigest() + '.json')
    with limit_path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if limit_path.exists():
            limit = json.loads(limit_path.read_text()); assert limit['identity'] == limit_identity
        else:
            start = time.monotonic(); print('START diagnostic refinement', limit_spec, flush=True)
            try:
                limit = dict(identity=limit_identity, status='computed', result=sa10.compute(tip['source'], limit_spec))
            except sa10.AnalysisError as exc:
                limit = dict(identity=limit_identity, status='rejected', error=str(exc), details=getattr(exc, 'details', None))
            limit['seconds'] = time.monotonic()-start
            limit_path.write_text(json.dumps(limit, indent=2) + '\n')
        limit.update(cache_path=limit_path.relative_to(ROOT).as_posix(), cache_sha256=sha(limit_path))
        print('Diagnostic refinement', limit['status'], flush=True)
    return limit


def main():
    study = json.loads((D / 'isae-sa10.json').read_text())
    sources = json.loads((D / 'isae-sa10-sources.json').read_text())
    assert sha(D / 'isae-sa10-TS_60_45_30-repaired-joints.asw') == sources['derived']['sha256']
    drag = json.loads((D / 'isae-sa10-drag.json').read_text())
    modules = {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    assert modules == study['provenance']['modules']
    assert sha(ROOT / 'scripts/verify-isae-sa10.py') == study['provenance']['script_sha256']
    assert sha(D / 'isae-sa10-sources.json') == study['provenance']['source_report_sha256']
    assert sha(D / 'isae-sa10.json') == drag['identity']['study_sha256']
    original = next(c for c in sources['models'] if c['name'] == 'TS_60_45_30')
    rejected = []
    for panels in [25, 50, 100]:
        try:
            model_meshes(parse_asw(original['source']), panels)
        except ValueError as exc:
            assert str(exc) == "Attachment station is outside beam 2's parameter range."
            rejected.append(dict(panels=panels, error=str(exc)))
        else:
            raise AssertionError('Invalid literal attachment unexpectedly accepted')
    zero_drag, origin_moments, header_checks, friction_audit = [], [], [], []
    for case in study['cases']:
        model = parse_asw(case['source']); area_cd = 0.; beam_drag = []
        for beam in model.beams:
            lo, hi = beam.domain; knots = {lo, hi}; pressure = friction = 0.
            for name in ['x', 'y', 'z', 'chord', 'Cdp', 'Cdf']:
                distribution = beam.distributions.get(name)
                if distribution is None:
                    continue
                knots.update(float(t) for t in distribution.t if lo <= t <= hi)
                if beam.lifting and distribution.t[0] == 0:
                    knots.update(float(-t) for t in distribution.t if lo <= -t <= hi)
            knots = sorted(knots)
            for a, b in zip(knots[:-1], knots[1:]):
                length = np.linalg.norm(beam.position(b) - beam.position(a))
                # At zero incidence these unswept surfaces have both full and
                # section-normal velocity equal to freestream. Pressure and
                # friction drag both contribute. The upstream left leading
                # tip sail sets Cdf = 0.01; the other sails explicitly set zero.
                area = length * beam.value('chord', (a+b)/2)
                pressure += area * beam.value('Cdp', (a+b)/2)
                friction += area * beam.value('Cdf', (a+b)/2)
            area_cd += pressure + friction
            beam_drag.append(dict(beam=beam.index, pressure_CD=pressure/model.reference[0, 0],
                                  friction_CD=friction/model.reference[0, 0]))
        expected = float(area_cd / model.reference[0, 0])
        zero = [r for r in case['runs'] if r['specification']['alpha'] == 0 and r['status'] == 'computed']
        assert len(zero) == 12
        errors = [abs(r['result']['CD'] - expected) for r in zero]
        assert max(errors) < 1e-8, (case['case_id'], errors)
        zero_drag.append(dict(case=case['case_id'], independent_CD=expected, requests=len(zero),
                              maximum_absolute_error=max(errors), beams=beam_drag))
        raw = next(c for c in sources['models'] if c['name'] == case['name'])
        original_model = parse_asw(raw['source'])
        for beam, original_beam in zip(model.beams, original_model.beams):
            assert beam.index == original_beam.index
            a = beam.distributions.get('Cdf'); b = original_beam.distributions.get('Cdf')
            assert (a is None) == (b is None)
            if a is not None:
                assert np.array_equal(a.t, b.t) and np.array_equal(a.values, b.values)
                friction_audit.append(dict(case=case['case_id'], beam=beam.index,
                    t=a.t.tolist(), values=a.values.tolist(), unchanged_from_literal=True))
        table = np.array(raw['archived']['rows'])
        assert np.array_equal(table[:, 69:72], table[:, 72:75])
        assert np.all(table[:, 66:69] == 0) and np.all(table[:, 2] == 1)
        assert np.array_equal(table[12, 75:], table[13, 75:])
        header_checks.append(dict(case=case['case_id'], archived_rows=27, unique_alpha=26,
            columns_zero_based={'CG': [66, 67, 68], 'V_beta_alpha': [69, 70, 71], 'VIAS_ref_beta_ref_alpha_ref': [72, 73, 74]},
            actual_and_reference_flow_identical=True, cg_is_origin=True, all_archived_converged=True,
            duplicate_alpha_12_coefficients_identical=True))
        for frozen in [False, True]:
            for pg in ['zero', 'speed']:
                selected = [r for r in case['runs'] if r['specification']['panels'] == 100
                            and r['specification']['frozen'] == frozen and r['specification']['pg'] == pg
                            and r['specification']['alpha'] in range(26) and r['status'] == 'computed']
                pairs = []
                for run in selected:
                    result = run['result']; alpha = run['specification']['alpha']
                    qSc = .5 * model.constants[1] * 55**2 * model.reference[0, 0] * model.reference[0, 1]
                    origin = np.array(result['moment']) + np.cross(model.reference[1], result['force'])
                    archived = next(row[80] for row in raw['archived']['rows'] if row[74] == alpha)
                    pairs.append(dict(alpha=alpha, Cm_input_reference=result['Cm'], Cm_origin=float(origin[1]/qSc), archived_CM=archived))
                origin_moments.append(dict(case=case['case_id'], pg=pg, frozen=frozen, rows=pairs,
                    input_reference_error=sa10.metrics([p['Cm_input_reference'] for p in pairs], [p['archived_CM'] for p in pairs]),
                    origin_reference_error=sa10.metrics([p['Cm_origin'] for p in pairs], [p['archived_CM'] for p in pairs]),
                    interpretation='Diagnostic exact wrench translation to archived zero CG. Archived CM reference is not established by the column header; smaller discrepancy is not proof of the reference convention.'))
    runs = [r for c in study['cases'] for r in c['runs']]
    assert len(runs) == 2676
    computed = [r for r in runs if r['status'] == 'computed']
    assert all(sha(ROOT / r['cache_path']) == r['cache_sha256'] for r in runs)
    for row in runs:
        if 'executor' in row:
            assert row['executor']['helper_sha256'] == sha(ROOT / 'scripts/precompute-isae-sa10.py')
            assert row['executor']['compute_script_sha256'] == study['provenance']['script_sha256']
    roots = [r for row in drag['rows'] for r in row['roots']]
    assert len(drag['rows']) == 160
    assert all(abs(r['lift_error']) <= 5e-8 for r in roots)
    limit = finer_junction_probe(study, modules)
    # Treat symmetry as a reported diagnostic; nonlinear stall can admit other branches.
    symmetry = max(max(abs(r['result'][k]) for k in ['Cl', 'Cn', 'CY']) for r in computed)
    report = dict(status='PASS_NUMERICAL_AND_SOURCE_CHECKS_NOT_EXPERIMENTAL_VALIDATION', modules=modules,
        script_sha256=sha(Path(__file__)), study_sha256=sha(D / 'isae-sa10.json'), drag_sha256=sha(D / 'isae-sa10-drag.json'),
        source_sha256=sha(D / 'isae-sa10-sources.json'), total=len(runs), computed=len(computed), rejected=len(runs)-len(computed),
        zero_alpha_drag=zero_drag, literal_attachment_rejections=rejected, archived_header_checks=header_checks,
        moment_reference_diagnostic=origin_moments, maximum_symmetry_coefficient=symmetry,
        maximum_residual=max(r['result']['residual'] for r in computed),
        maximum_wrench_error=max(r['result']['independent_wrench_error'] for r in computed),
        maximum_drag_decomposition_error=max(r['result']['drag_decomposition_error'] for r in computed),
        fixed_lift_roots=len(roots), maximum_fixed_lift_error=max(abs(r['lift_error']) for r in roots),
        finer_junction_diagnostic=limit,
        explicit_friction_distributions=friction_audit,
        source_friction_note='TS_60_45_30 beam 2 alone has explicit Cdf=0.01 in addition to Cdp=0.01. Its opposite sail sets Cdf=0. This source asymmetry is preserved, including in the joint reconstruction. Zero-incidence drag checks include both terms; force/moment symmetry cannot be presumed.',
        limitations=sources['limitations'])
    (D / 'isae-sa10-checks.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS', len(computed), '/', len(runs), 'computed;', len(roots), 'matched-lift roots', flush=True)


if __name__ == '__main__':
    main()
