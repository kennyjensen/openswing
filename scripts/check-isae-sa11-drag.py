"""Audit SA-11 matched-lift coverage, cached states and independently reduced loads."""
from collections import Counter
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from isae_sa11_reference import sha
from openswing.asw import parse_asw

spec = importlib.util.spec_from_file_location('sa11', ROOT / 'scripts/verify-isae-sa11.py')
sa11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa11)
D = ROOT / 'docs/validation'


def main():
    sources = json.loads((D / 'isae-sa11-sources.json').read_text())
    native = json.loads((D / 'isae-sa11.json').read_text())
    drag = json.loads((D / 'isae-sa11-drag.json').read_text())
    identity = drag['identity']
    assert identity['study_sha256'] == sha(D / 'isae-sa11.json')
    assert identity['native_provenance'] == native['provenance']
    assert identity['script_sha256'] == sha(ROOT / 'scripts/verify-isae-sa11-drag.py')
    assert native['provenance']['modules'] == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    assert native['provenance']['source_report_sha256'] == sha(D / 'isae-sa11-sources.json')
    cache_identity = {k: v for k, v in identity.items() if k != 'study_sha256'}
    folder = ROOT / '.reference/isae-sa11-drag' / hashlib.sha256(json.dumps(cache_identity, sort_keys=True).encode()).hexdigest()
    assert json.loads((folder / 'identity.json').read_text()) == cache_identity
    cases = {c['case_id']: c for c in sa11.case_entries(sources)}
    native_rows = {sa11.request_key(r['specification']): r for c in native['cases'] for r in c['runs']}
    scans = {r['id']: r for r in drag['scans']}
    assert len(scans) == len(drag['scans']) == 16
    verified_cache = {}

    def cached(row):
        path = ROOT / row['cache_path']
        digest = sha(path)
        assert digest == row['cache_sha256']
        verified_cache[row['cache_path']] = digest
        return json.loads(path.read_text())

    expected_requests = []
    for case in cases.values():
        if not case['has_experimental_reference']:
            continue
        model = parse_asw(case['source'])
        for mach, data in sources['experimental'].items():
            speed = float(mach) * float(model.constants[2])
            angles = sorted(set([-1.] + np.linspace(0, 10, 41).tolist() +
                                [r['xy'][0] for r in data['lift'][case['name']]['values']]))
            for panels in [50, 100]:
                scan_id = f"{case['case_id']}_M{mach}_N{panels}"
                scan = scans[scan_id]
                assert (scan['case'], scan['nominal_mach'], scan['speed'], scan['panels']) == (case['case_id'], float(mach), speed, panels)
                assert [r['alpha'] for r in scan['rows']] == angles
                for row in scan['rows']:
                    request = sa11.specification(case, panels, speed, row['alpha'])
                    reference = native_rows[sa11.request_key(request)]
                    state = cached(row)
                    assert state['specification'] == request and row['status'] == state['status'] == reference['status']
                    assert row['cache_sha256'] == reference['cache_sha256']
                    assert row['CL'] == state.get('result', {}).get('CL')
                    assert row['error'] == state.get('error')
                for measurement in data['drag'][case['name']]['values']:
                    expected_requests.append(dict(case=case['case_id'], nominal_mach=float(mach), speed=speed,
                        panels=panels, csv_row=measurement['row'], target_CL=measurement['xy'][0],
                        measured_CD=measurement['xy'][1], scan_id=scan_id))
    assert len(expected_requests) == len(drag['rows']) == 166
    assert [r['request'] for r in drag['rows']] == expected_requests
    maximum_load_error = maximum_lift_error = maximum_flow_error = 0.
    root_checks = []
    for row in drag['rows']:
        point = cached(row)
        assert point == {k: v for k, v in row.items() if k not in ['cache_path', 'cache_sha256']}
        request = row['request']
        scan = scans[request['scan_id']]['rows']
        gaps = [[a['alpha'], b['alpha']] for a, b in zip(scan[:-1], scan[1:])
                if a['status'] != 'computed' or b['status'] != 'computed']
        assert row['unresolved_scan_intervals'] == gaps
        assert row['complete_sampled_scan'] == (not gaps and not row['failed_brackets'])
        brackets = [r['bracket'] for r in row['roots']] + [r['bracket'] for r in row['failed_brackets']]
        for a, b in zip(scan[:-1], scan[1:]):
            if a['status'] == b['status'] == 'computed' and (a['CL'] - request['target_CL']) * (b['CL'] - request['target_CL']) < 0:
                assert [a['alpha'], b['alpha']] in brackets
        for failed in row['failed_brackets']:
            assert cached(failed['rejected_state'])['status'] == 'rejected'
        model = parse_asw(cases[request['case']]['source'])
        for root in row['roots']:
            assert root['bracket'][0] <= root['alpha'] <= root['bracket'][1]
            state = cached(root)
            assert state['status'] == 'computed' and state['result'] == root['result']
            assert state['specification'] == sa11.specification(cases[request['case']], request['panels'], request['speed'], root['alpha'])
            result = root['result']
            assert result['residual'] <= 1e-8
            assert all(np.isfinite(result[k]) for k in sa11.COEFFICIENTS)
            lift_error = result['CL'] - request['target_CL']
            assert abs(lift_error) <= 5e-8 and lift_error == root['lift_error']
            maximum_lift_error = max(maximum_lift_error, abs(lift_error))
            qS = .5 * model.constants[1] * request['speed']**2 * model.reference[0, 0]
            angle = np.radians(root['alpha'])
            force = np.array(result['force'])
            CL = (-np.sin(angle) * force[0] + np.cos(angle) * force[2]) / qS
            CD = (np.cos(angle) * force[0] + np.sin(angle) * force[2]) / qS
            Cm = result['moment'][1] / (qS * model.reference[0, 1])
            maximum_load_error = max(maximum_load_error, abs(CL-result['CL']), abs(CD-result['CD']), abs(Cm-result['Cm']),
                                     abs(result['CD']-result['CDi_near']-result['CDp']))
            flow = result['maximum_normal_mach']
            beam = next(b for b in model.beams if b.index == flow['beam'])
            tangent = beam.position(flow['t'], derivative=1)
            tangent /= np.linalg.norm(tangent)
            velocity = np.array(flow['relative_velocity'])
            normal_mach = np.linalg.norm(velocity - tangent * np.dot(tangent, velocity)) / model.constants[2]
            assert normal_mach < 1
            maximum_flow_error = max(maximum_flow_error, abs(normal_mach-flow['normal_mach']))
            root_checks.append(dict(request=request, alpha=root['alpha'], lift_error=lift_error, independently_reduced_CD=float(CD)))
    assert max(maximum_flow_error, maximum_load_error) < 2e-10
    for summary in drag['summary']:
        group = [r for r in drag['rows'] if r['request']['scan_id'] == summary['scan_id']]
        single = [r for r in group if len(r['roots']) == 1]
        complete = [r for r in single if r['complete_sampled_scan']]
        assert summary['requested'] == len(group)
        assert summary['single_observed_root'] == len(single)
        assert summary['no_observed_root'] == sum(not r['roots'] for r in group)
        assert summary['multiple_observed_roots'] == sum(len(r['roots']) > 1 for r in group)
        assert summary['complete_single_root_scan'] == len(complete)
        assert summary['unresolved_scan_intervals'] == len(group[0]['unresolved_scan_intervals'])
        offset = sources['postprocessing']['drag_offsets'][str(summary['nominal_mach'])]
        for key, selected, shift in [('raw_CD_observed_single_root', single, 0.),
                                     ('raw_CD_complete_single_root', complete, 0.),
                                     ('documented_offset_CD_observed_single_root', single, offset)]:
            metric = summary[key]
            assert metric['count'] == len(selected)
            if not selected:
                assert all(metric[k] is None for k in ['rmse', 'bias', 'maximum_absolute_error'])
                continue
            error = np.array([r['roots'][0]['result']['CD'] + shift - r['request']['measured_CD'] for r in selected])
            assert abs(metric['rmse']-np.linalg.norm(error)/np.sqrt(len(error))) < 1e-14
            assert abs(metric['bias']-sum(error)/len(error)) < 1e-14
            assert abs(metric['maximum_absolute_error']-max(abs(error))) < 1e-14
    report = dict(status='PASS_MATCHED_LIFT_EVIDENCE_AUDIT_PHYSICAL_VALIDATION_INCOMPLETE',
        script_sha256=sha(Path(__file__)), source_report_sha256=sha(D/'isae-sa11-sources.json'),
        study_sha256=sha(D/'isae-sa11.json'), drag_sha256=sha(D/'isae-sa11-drag.json'),
        modules=native['provenance']['modules'], requested=166, scans=len(scans),
        root_counts=dict(Counter(str(len(r['roots'])) for r in drag['rows'])),
        complete_sampled_scans=sum(all(r['status']=='computed' for r in s['rows']) for s in scans.values()),
        maximum_lift_error=maximum_lift_error, maximum_coefficient_reduction_error=maximum_load_error,
        maximum_normal_mach_projection_error=maximum_flow_error, root_checks=root_checks,
        cache_manifest=[dict(path=p, sha256=h) for p, h in sorted(verified_cache.items())],
        limitations=['Every sampled angle scan contains rejected intervals; one observed root is not proof of uniqueness.',
            'This audit verifies recorded states, source coverage and load reductions; it is not an independent circulation solver.',
            'No raw drag offset, missing-root extrapolation or best-matching-branch selection was applied.'])
    (D/'isae-sa11-drag-checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report['status'], report['root_counts'], 'maximum lift error', maximum_lift_error, flush=True)


if __name__ == '__main__':
    main()
