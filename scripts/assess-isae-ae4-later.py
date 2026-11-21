"""Reassess a pinned serial AE-4 study; never run a physical solve.

Usage: python scripts/assess-isae-ae4-later.py STUDY_FOLDER NEW_REPORT.json
The original reports are inputs and are never overwritten.
"""
import argparse
from decimal import Decimal
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.isae_modal_classification import classify_modes

SPEC = importlib.util.spec_from_file_location('ae4_anchor', ROOT/'scripts/verify-isae-ae4-wall-modes.py')
AE4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AE4)


def load(path):
    with path.open() as stream:
        return json.load(stream)


def pin(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest)


def cv(vector):
    return np.asarray(vector['real']) + 1j*np.asarray(vector['imag'])


def assess(base, destination):
    if destination.exists():
        raise ValueError('Use a new report path; earlier evidence must be retained.')
    plan = load(base/'plan.json')
    correction = load(base/'classification-plan-v2.json')
    assert pin(ROOT/correction['classifier']['path']) == correction['classifier']
    assert plan['reference_relative_tolerance'] == .05 and plan['tiny_reference'] == 1e-8
    assert all(pin(ROOT/p['path']) == p for p in plan['kernel_pins']+plan['original_sources'])
    saved_helper = pin(base/'original-anchor-helper.py')
    assert all(saved_helper[k] == plan['helper'][k] for k in ('bytes', 'sha256'))
    inputs = [pin(base/n) for n in ('plan.json', 'classification-plan-v2.json', 'original-anchor-helper.py')]
    inputs += [pin(Path(__file__)), pin(Path(AE4.__file__)), correction['classifier']]
    records = []
    for job in plan['jobs']:
        folder = base/job['folder']
        p, r, request = [load(folder/n) for n in ('plan.json', 'report.json', 'request.json')]
        assert p['nominal_intervals'] == job['panels'] and p['IAS'] == p['TAS'] == job['IAS']
        assert p['declared_native_index'] == job['native_index'] and p['targets'] == job['targets']
        assert p['kernel_pins'] == plan['kernel_pins'] and p['helper'] == plan['helper']
        assert p['original_sources'] == plan['original_sources']
        assert pin(ROOT/p['reference_manifest']['path']) == p['reference_manifest']
        assert request['condition']['speed'] == job['IAS']
        assert request['source'] == (AE4.ORIGINAL/'Pazy_wing.asw').read_text()
        assert request['modes']['count'] == 4 and request['modes']['shift'] == [0., 200.]
        assert request['modes']['step'] == 1e-5 and request['modes']['matrices'] is True
        assert r['status'] == 'computed' and len(r['checks']) == 14 and all(c['passed'] for c in r['checks'])
        assert pin(folder/'result.json') == r['result'] and pin(folder/'plan.json') == r['plan']
        inputs += [pin(folder/n) for n in ('request.json', 'plan.json', 'report.json', 'result.json')]
        result = load(folder/'result.json')
        a, m = [np.asarray(result['matrices'][k]) for k in ('A', 'M')]
        layout = result['diagnostics']['state_layout']
        assert layout['node_coordinates']['start'] == 0 and layout['frame']['width'] == 0
        assert result['diagnostics']['base_residual'] <= 1e-7
        assert result['base']['ground_plane']['flag'] == 1 and result['base']['ground_plane']['wall_roots']
        assert len(result['modes']) == 4
        assert [mode['eigenvalue'] for mode in result['modes']] == r['selected_eigenvalues']
        checks = []
        for i, mode in enumerate(result['modes']):
            pole = complex(*mode['eigenvalue'])
            right, left = [cv(mode[k]) for k in ('right', 'left')]
            norm = np.linalg.norm(a)+abs(pole)*np.linalg.norm(m)
            er = float(np.linalg.norm(a@right-pole*(m@right))/(norm*np.linalg.norm(right)))
            el = float(np.linalg.norm(left.conj()@a-pole*(left.conj()@m))/(norm*np.linalg.norm(left)))
            defect = float(abs(left.conj()@m@right-1))
            root = np.r_[right[:6], right[layout['local_velocity']['start']:layout['local_velocity']['start']+3],
                         right[layout['local_rates']['start']:layout['local_rates']['start']+3]]
            clamp = float(np.max(abs(root))/np.max(abs(right)))
            ok = er <= 1e-8 and el <= 1e-8 and defect <= 1e-6 and clamp <= 1e-8
            checks.append(dict(mode=i, right=er, left=el, mass_defect=defect, clamp_defect=clamp, passed=ok))
        assert all(c['passed'] for c in checks)
        classifications = classify_modes(result['modes'], a, m, shift=request['modes']['shift'],
                                         characteristic_rate=result['diagnostics']['time_scale'])
        comparison = AE4.compare_roots(result['modes'], p['targets'], classifications=classifications)
        reference = []
        for row in comparison:
            for k, name in enumerate(('real', 'imag')):
                token = row['original']['tokens'][k+1]
                expected = Decimal(token)
                tolerance = Decimal(10)**expected.as_tuple().exponent/2
                value = row['actual'][k] if row['status'] == 'computed' else None
                passed = value is not None and abs(Decimal.from_float(value)-expected) <= tolerance
                reference.append(dict(name=f"line{row['original']['line']}:{name}", predicted=value,
                    expected=float(expected), tolerance=float(tolerance), comparison='<=', passed=passed,
                    exact_decimal_expected=str(expected), exact_decimal_tolerance=str(tolerance)))
        strict = dict(status='computed', numerical_pass=True, reference_match=all(c['passed'] for c in reference),
                      reference_checks=reference, output_accounting=dict(required=len(reference),
                      missing=sum(c['predicted'] is None for c in reference)))
        accepted = apply_reference_acceptance(strict, relative_tolerance=.05)
        records.append(dict(job=job['folder'], nominal_intervals=job['panels'], IAS=job['IAS'],
            native_index=job['native_index'], selected_eigenvalues=r['selected_eigenvalues'],
            original_available_components=2*sum(row['status'] == 'computed' for row in r['comparison']),
            classifications=classifications, full_pencil_checks=checks, original_numerical_checks=r['checks'],
            comparisons=comparison, assessment=accepted, passed=sum(c['passed'] for c in accepted['reference_checks']),
            required=len(reference), missing=accepted['output_accounting']['missing'],
            qualification=p['qualification']))
        print(job['folder'], records[-1]['passed'], '/', len(reference), flush=True)
        del result, a, m
        gc.collect()
    assert sum(r['required'] for r in records) == plan['required_scalar_slots']
    assert all(pin(ROOT/p['path']) == p for p in inputs)
    report = dict(status='PROGRESS_VERIFIED', goal_complete=False, new_solves=0, registered_passes_credited=0,
                  scope=plan['scope'], reference_tolerance=.05,
                  passed=sum(r['passed'] for r in records), required=sum(r['required'] for r in records),
                  missing=sum(r['missing'] for r in records), distinct_native_scalar_targets=plan['distinct_native_targets'],
                  records=records, inputs=inputs, qualifications=plan['qualifications'])
    destination.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('status','passed','required','missing')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    assess(args.folder.resolve(), args.destination.resolve())
