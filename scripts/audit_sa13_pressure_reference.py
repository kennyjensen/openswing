"""Read-only SA-13 pressure admissibility audit; no solver or numerical imports.

This tests a necessary condition for the declared incompressible Bernoulli
observable. It does not infer missing inputs or score the archived curves.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from isae_suite_sa13 import plan, verify_reference_sources


def pin(path):
    path = ROOT / path
    data = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def audit():
    jobs = plan(ROOT)
    for job in jobs:
        verify_reference_sources(ROOT, job)
    catalog_path = 'docs/validation/aswing-authoritative-sources.json'
    catalog = json.loads((ROOT / catalog_path).read_text())
    report = next(r for r in catalog['files'] if r['id'] == 'isae-part-1')
    assert pin(report['local_pdf'])['sha256'] == report['sha256']
    assert pin(report['local_text'])['sha256'] == report['text_sha256']
    decoded = json.loads((ROOT / 'docs/validation/isae-sa13-sources.json').read_text())
    primary = next(p for p in decoded['primary'] if 'naca-tm-574' in p['path'])
    primary_path = primary['path'].replace('.reference/', 'reference/', 1)
    assert pin(primary_path)['sha256'] == primary['sha256']
    curves, conflicts = [], []
    for job in jobs:
        finite = [r for r in job['observations'] if r['expected'] is not None]
        curves.append(dict(id=job['id'], target_kind=job['target_kind'],
            retained=job['expected_outputs'], finite=len(finite),
            unavailable=job['unavailable_reference_outputs'],
            minimum=min(r['expected'] for r in finite),
            maximum=max(r['expected'] for r in finite)))
        if job['figure'] != 'pressure':
            continue
        for row in finite:
            with localcontext() as context:
                context.prec = 50
                percent_cp = Decimal.from_float(row['expected'])
                if percent_cp <= 100:
                    continue
                conflicts.append(dict(id=job['id'],
                    source_row_1based=row['source_row_1based'],
                    coordinate=row['coordinate'], coordinate_hex=row['coordinate_hex'],
                    ordinate=row['expected'], ordinate_hex=row['expected_hex'],
                    implied_speed_squared_ratio=str(1-percent_cp/100),
                    minimum_relative_error_percent=str(100*(percent_cp-100)/percent_cp),
                    lower_edge_of_hypothetical_five_percent_band=str(percent_cp*Decimal('.95')),
                    acceptance_tolerance_set=False, source=job['sources'][0]))
    assert len(jobs) == 8 and sum(r['retained'] for r in curves) == 612
    assert sum(r['finite'] for r in curves) == 476
    assert sum(r['unavailable'] for r in curves) == 136
    assert len(conflicts) == 1 and conflicts[0]['id'] == 'SA-13:pressure:discrete'
    assert conflicts[0]['source_row_1based'] == 2
    assert not any(name == 'numpy' or name.startswith('openswing') for name in sys.modules)
    sources = {p['path']: p for j in jobs for p in j['sources']}
    for path in (Path(__file__).resolve().relative_to(ROOT), catalog_path, report['local_pdf'],
                 report['local_text'], primary_path, 'reference/isae-sa13/naca-tm-574.txt'):
        p = pin(path)
        sources[p['path']] = p
    return dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='REFERENCE_OBSERVABLE_CONFLICT_UNDER_DECLARED_BERNOULLI_INTERPRETATION',
        assumptions=['Steady incompressible flow with the reference stagnation pressure.',
                     'The plotted ordinate means 100Cp = 100*(1 - |V|^2/U_infinity^2).'],
        evidence=['Jan Part I section 6.2, printed page 40; Figure 24(d), printed page 42.',
                  'NACA-TM-574 printed page 11 (PDF page 13), pressure derivation; Figure 3.'],
        curves=curves, conflicts=conflicts, sources=list(sources.values()),
        required=612, finite_reference=476, unavailable_reference=136,
        new_passes=0, primary_passes=0, physical_solver_calls=0,
        production_imports=0, reference_values_changed=False,
        qualifications=[
            'All original rows and missing values remain in the existing denominator.',
            'Passing this bound would not establish a matching geometry or a validated curve.',
            'The five-percent band is illustrative; the adapter still has no figure precision/tolerance contract.',
            'Different normalization, a linearized pressure formula or export/postprocessing could explain the conflict; none is established.',
            'No model, derivative, sensor or historical executable setup is recovered by this audit.',
            'Do not clamp the reference or install an alternative pressure law to reproduce this point.',
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'required', 'finite_reference',
        'unavailable_reference', 'new_passes', 'physical_solver_calls')}))
    print(json.dumps(result['conflicts'], indent=2))
