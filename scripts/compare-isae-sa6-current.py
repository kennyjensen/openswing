"""Refresh SA-6 at primary table coordinates without replacing historical data.

Run fetch-isae-validation.py and fetch-isae-sa6.py if the pinned inputs are absent.
Only current influences are used. No properties or acceptance limits are fitted.
The appended zero-deflection anchors are excluded from experimental error metrics.
Each completed state is cached under the complete input/source identity.
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from isae_sa6_reference import CACHE, primary_tables

SPEC = importlib.util.spec_from_file_location('sa6_verifier', ROOT / 'scripts/verify-isae-sa6.py')
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)
DEST = ROOT / 'docs/validation'
SHA = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def stats(predicted, observed):
    error = np.asarray(predicted) - np.asarray(observed)
    return dict(count=len(error), bias=float(error.mean()),
                rmse=float(np.sqrt(np.mean(error ** 2))),
                maximum_absolute_error=float(np.max(np.abs(error))))


def main():
    sources = json.loads((DEST / 'isae-sa6-sources.json').read_text())
    old = json.loads((DEST / 'isae-sa6.json').read_text())
    primary = primary_tables()
    assert primary == sources['primary']
    paths = [Path(__file__), ROOT / 'scripts/verify-isae-sa6.py',
             ROOT / 'scripts/isae_sa6_reference.py', DEST / 'isae-sa6-sources.json',
             DEST / 'isae-sa6.json', *sorted((ROOT / 'openswing').glob('*.py'))]
    pins = {str(p.relative_to(ROOT)): SHA(p) for p in paths}
    for entry in sources['models']:
        p = CACHE / entry['path']
        assert SHA(p) == entry['sha256']
        pins[str(p.relative_to(ROOT))] = SHA(p)
    plan = dict(source_sha256=pins, requested_cases=504, meshes=[80, 160],
                body_pitch_deg=[0, 8, 12], physical_deflection_deg=list(range(0, 45, 4)),
                current_influences=True, speed_m_s=20, pg_mach=0,
                maximum_full_residual=1e-8, maximum_wrench_error=2e-10,
                experimental_acceptance_threshold=None,
                mesh_acceptance_threshold=None,
                zero_deflection_role='Appended symmetry anchors, not measured table entries',
                note='20 m/s is the archived computation setting; primary curves combine three speeds.')
    identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    cache = ROOT / '.reference/isae-sa6-current' / identity
    cache.mkdir(parents=True, exist_ok=True)
    write(cache / 'plan.json', plan)
    rows, comparisons, mesh, historical = [], [], [], []
    computed = reused = 0
    for entry in sources['models']:
        reconstructed = entry['id'] == '10b_25c'
        case_id = entry['id'] + ('_reconstructed' if reconstructed else '_literal')
        source = (CACHE / entry['path']).read_text()
        former = next(c for c in old['cases'] if c['case_id'] == case_id)
        former_rows = {(r['specification']['panels'], r['specification']['alpha'],
                        r['specification']['delta']): r for r in former['runs']
                       if not r['specification']['frozen']}
        lookup = {}
        for panels in plan['meshes']:
            for alpha in plan['body_pitch_deg']:
                ref = next(r for r in primary if r['id'] == entry['id'] and r['body_alpha'] == alpha)
                for i, delta in enumerate(ref['delta']):
                    spec = dict(case=case_id, reconstructed=reconstructed, panels=panels,
                                alpha=alpha, delta=delta, frozen=False)
                    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
                    path = cache / (key + '.json')
                    if path.exists():
                        row = json.loads(path.read_text())
                        assert row['specification'] == spec and row['identity'] == identity
                        reused += 1
                    else:
                        started = time.monotonic()
                        try:
                            result = VERIFIER.compute(source, spec)
                            row = dict(status='computed', result=result)
                        except VERIFIER.AnalysisError as exc:
                            row = dict(status='rejected', error=str(exc))
                        row.update(specification=spec, identity=identity,
                                   seconds=time.monotonic() - started)
                        write(path, row)
                        computed += 1
                    row = dict(row, primary=dict(Cl=ref['Cl_body'][i], Cn=ref['Cn_body'][i]),
                               reference_kind='symmetry_anchor' if delta == 0 else 'primary_tabulated',
                               source_table=dict(report=ref['report'], table=ref['table'],
                                                 pdf_page=ref['pdf_page']))
                    lookup[panels, alpha, delta] = row
                    rows.append(row)
                print(f'{case_id}: N={panels}, pitch={alpha}, 12 states recorded', flush=True)
        for alpha in plan['body_pitch_deg']:
            fine = [lookup[160, alpha, d] for d in plan['physical_deflection_deg']]
            measured = [r for r in fine if r['reference_kind'] == 'primary_tabulated']
            valid = [r for r in measured if r['status'] == 'computed']
            all_valid = [r for r in fine if r['status'] == 'computed']
            comparisons.append(dict(case=case_id, body_pitch_deg=alpha,
                requested_measured=len(measured), completed_measured=len(valid),
                measured_errors={k: stats([r['result'][k] for r in valid],
                                          [r['primary'][k] for r in valid]) if valid else None
                                 for k in ('Cl', 'Cn')},
                historical_style_including_anchor_errors={k: stats(
                    [r['result'][k] for r in all_valid], [r['primary'][k] for r in all_valid])
                    if all_valid else None for k in ('Cl', 'Cn')}))
            pairs = [(lookup[80, alpha, d], lookup[160, alpha, d])
                     for d in plan['physical_deflection_deg']]
            valid_pairs = [(a, b) for a, b in pairs if a['status'] == b['status'] == 'computed']
            mesh.append(dict(case=case_id, body_pitch_deg=alpha, requested=len(pairs),
                completed=len(valid_pairs), coarse=80, fine=160,
                difference={k: stats([a['result'][k] for a, b in valid_pairs],
                                     [b['result'][k] for a, b in valid_pairs])
                            if valid_pairs else None for k in ('Cl', 'Cn')}))
        for (panels, alpha, delta), row in lookup.items():
            previous = former_rows[panels, alpha, delta]
            if row['status'] == previous['status'] == 'computed':
                historical.append(dict(case=case_id, panels=panels, body_pitch_deg=alpha,
                    deflection_deg=delta, difference={k: row['result'][k] - previous['result'][k]
                                                    for k in ('Cl', 'Cn', 'CL', 'CD', 'Cm')}))
    assert len(rows) == 504
    assert all(SHA(ROOT / p) == sha for p, sha in pins.items()), 'Inputs changed during comparison'
    valid = [r for r in rows if r['status'] == 'computed']
    anchors = [r for r in valid if r['reference_kind'] == 'symmetry_anchor']
    report = dict(status='COMPARISON_COMPLETE_WITH_RETAINED_DISCREPANCIES' if len(valid) == 504
                  else 'COMPARISON_INCOMPLETE_WITH_REJECTIONS', full_suite_validated=False,
                  identity=identity, plan=plan, cases=rows, comparisons=comparisons,
                  mesh_comparisons=mesh, historical_differences=historical,
                  accounting=dict(requested=len(rows), completed=len(valid), rejected=len(rows)-len(valid),
                      newly_computed=computed, reused=reused, unique_tabulated_locations=231,
                      tabulated_coefficients=462, unique_added_symmetry_anchors=21),
                  maximum_residual=max(r['result']['residual'] for r in valid),
                  maximum_wrench_error=max(r['result']['independent_wrench_error'] for r in valid),
                  maximum_zero_control_lateral_moment=max(abs(r['result'][k]) for r in anchors for k in ('Cl', 'Cn')),
                  limitations=[
                      'Primary tabulations are faired curves from observations at three speeds; 20 m/s is the archived calculation setting.',
                      'Wing-only models omit the experimental fuselage; section/control properties and coefficient uncertainty remain unresolved.',
                      '10b uses the documented +/-0.508 m control-boundary reconstruction. Its mislabeled literal file and historical results remain unchanged.',
                      'No physical parameter was fitted. Residual gates test equations, not experimental agreement.',
                      'Two mesh levels give a sensitivity, not a rigorous continuum error bound. Historical archived ASWING startup settings remain unknown.',
                      'This current-influence study adds no frozen-influence, dynamic, WASM or browser validation.'])
    write(DEST / 'isae-sa6-current.json', report)
    fields = ['case', 'panels', 'body_pitch_deg', 'deflection_deg', 'reference_kind',
              'status', 'Cl_measured', 'Cn_measured', 'Cl', 'Cn', 'Cl_error', 'Cn_error']
    with (DEST / 'isae-sa6-current.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            s, p, r = row['specification'], row['primary'], row.get('result', {})
            writer.writerow(dict(case=s['case'], panels=s['panels'], body_pitch_deg=s['alpha'],
                deflection_deg=s['delta'], reference_kind=row['reference_kind'], status=row['status'],
                Cl_measured=p['Cl'], Cn_measured=p['Cn'], Cl=r.get('Cl'), Cn=r.get('Cn'),
                Cl_error=r['Cl']-p['Cl'] if r else None, Cn_error=r['Cn']-p['Cn'] if r else None))
    print(json.dumps(report['accounting']), flush=True)
    print('Report:', DEST / 'isae-sa6-current.json', flush=True)


if __name__ == '__main__':
    main()
