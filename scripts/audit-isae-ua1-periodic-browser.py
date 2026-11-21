"""Audit retained built-worker snapshots and the declared periodic accuracy gates."""
import argparse
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path

import numpy as np
from isae_ua_periodic import fourier, phase_difference
from isae_ua2_browser_cutoff import validate_checkpoint

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua1-incidence-periodic-browser-20261102'
JOBS_PER_CHUNK = 4


def digest(path):
    result = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def setup():
    plan = json.loads((BASE / 'plan.json').read_text())
    assert plan['audit_jobs_per_chunk'] == JOBS_PER_CHUNK
    assert json.loads((BASE / 'production-complete.json').read_text())['computed_jobs'] == 64
    # Runtime bytes were checked by the producer and are checked again at
    # combine. Bounded raw readers do not reread the entire WASM runtime.
    pins = {name: value for name, value in plan['source_sha256'].items()
            if not name.startswith('dist/runtime/')}
    assert all(digest(ROOT / name) == value for name, value in pins.items())
    pins[str((BASE / 'plan.json').relative_to(ROOT))] = digest(BASE / 'plan.json')
    return plan, pins


def chunk(index):
    plan, pins = setup()
    first, last = index * JOBS_PER_CHUNK, min((index + 1) * JOBS_PER_CHUNK, len(plan['jobs']))
    assert 0 <= first < last
    rows, inputs, previous, fingerprint = [], {}, None, None
    angle = math.radians(9.)
    heave = [-math.sin(angle), 0., math.cos(angle)]
    wind = [math.cos(angle), 0., math.sin(angle)]
    dynamic_pressure_area = .5 * 1.225 * 100 * 200000
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    if first:
        path = BASE / 'production' / f'part{first-1:03d}' / 'trajectory.json.gz'
        inputs[str(path.relative_to(ROOT))] = digest(path)
        with gzip.open(path, 'rt') as stream:
            prior = json.load(stream)
        previous = prior['snapshots'][-1]
        fingerprint = prior['software_provenance']['fingerprint']
        del prior
    for part in range(first, last):
        folder = BASE / 'production' / f'part{part:03d}'
        receipt = json.loads((folder / 'receipt.json').read_text())
        report = json.loads((folder / 'report.json').read_text())
        target_path = BASE / plan['targets'][part]['path']
        assert digest(target_path) == plan['targets'][part]['sha256']
        target = json.loads(target_path.read_text())
        assert receipt['outcome'] == 'success' and receipt['job'] == plan['jobs'][part] == target['job'] == report['job']
        assert receipt['plan_sha256'] == report['plan_sha256'] == digest(BASE / 'plan.json')
        assert report['segment_passed'] and report['accepted_steps'] == 40 and report['rejected_steps'] == 0
        for name, value in receipt['output_sha256'].items():
            assert digest(folder / name) == value
            inputs[str((folder / name).relative_to(ROOT))] = value
        for path in (folder / 'receipt.json', target_path):
            inputs[str(path.relative_to(ROOT))] = digest(path)
        with gzip.open(folder / 'trajectory.json.gz', 'rt') as stream:
            raw = json.load(stream)
        assert raw['converged'] and raw['accepted_steps'] == 40 and raw['rejected_steps'] == 0
        assert raw['software_provenance'] == report['software_provenance']
        provenance = raw['software_provenance']
        if fingerprint is not None:
            assert fingerprint == provenance['fingerprint']
        fingerprint = provenance['fingerprint']
        assert len(provenance['modules']) == 136
        assert all(plan['source_sha256']['openswing/' + name] == value
                   for name, value in provenance['modules'].items())
        samples = raw['snapshots']
        assert len(samples) == len(report['rows']) == len(target['rows']) == 41
        if previous is not None:
            for key in ('force', 'circulation_rate', 'frame'):
                assert samples[0][key] == previous[key]
            assert [r['circulation'] for r in samples[0]['strips']] == [r['circulation'] for r in previous['strips']]
        for sample, row, expected in zip(samples, report['rows'], target['rows']):
            assert sample['time'] == row['time'] and abs(row['time'] - expected['time']) < 1e-12
            assert sample['residual'] == row['residual'] and sample['order'] == row['order']
            assert len(sample['strips']) == 4
            assert max(abs(v) for v in sample['frame']['attitude'] + sample['frame']['rates_body']) < 1e-12
            assert abs(dot(sample['frame']['velocity_origin_body'], wind) + 10) < 1e-10
            recovered = dict(CL=dot(sample['force'], heave) / dynamic_pressure_area,
                force_coefficient=[value / dynamic_pressure_area for value in sample['force']],
                circulation=[r['circulation'] for r in sample['strips']],
                circulation_rate=sample['circulation_rate'],
                heave_velocity=dot(sample['frame']['velocity_origin_body'], heave),
                heave_position=dot(sample['frame']['position_earth'], heave),
                heave_acceleration=dot(sample['frame']['acceleration_reference_body'], heave))
            differences = []
            for key, value in recovered.items():
                np.testing.assert_allclose(value, row[key], rtol=0, atol=1e-12)
                a, b = np.asarray(value), np.asarray(expected[key])
                assert a.shape == b.shape
                differences.append(float(np.max(abs(a - b) / np.maximum(1., abs(b)))))
            assert max(differences) < plan['gates']['CPython_scaled_difference']
            row.update(reference=expected['reference'], CPython_scaled_difference=max(differences))
        previous = samples[-1]
        record = dict(previous['restart'])
        version = record.pop('version', 1)
        checkpoint = dict(format='openswing-time-checkpoint', version=version,
                          context=previous.get('restart_context', raw['restart_context']), **record)
        assert checkpoint == json.loads((folder / 'checkpoint.json').read_text())
        validate_checkpoint(raw, final=part == len(plan['jobs']) - 1, expected_end=previous['time'])
        rows.extend(report['rows'] if part == 0 else report['rows'][1:])
        del raw, samples
    write(BASE / f'audit-chunk{index:03d}.json', dict(passed=True, index=index,
        first_part=first, last_part_exclusive=last, rows=rows, fingerprint=fingerprint,
        source_sha256=pins, input_sha256=inputs, native_ASWING_comparison=False))
    print(json.dumps(dict(passed=True, index=index, jobs=last-first, snapshots=len(rows))))


def combine():
    plan, pins = setup()
    rows, inputs, expected_part, fingerprint = [], {}, 0, None
    for index in range((len(plan['jobs']) + JOBS_PER_CHUNK - 1) // JOBS_PER_CHUNK):
        path = BASE / f'audit-chunk{index:03d}.json'
        receipt_path = BASE / f'audit-chunk{index:03d}-execution.json'
        receipt = json.loads(receipt_path.read_text())
        assert receipt['exit_code'] == 0 and receipt['report_sha256'] == digest(path)
        data = json.loads(path.read_text())
        assert data['passed'] and data['index'] == index and data['first_part'] == expected_part
        expected_part = data['last_part_exclusive']
        if fingerprint is not None:
            assert fingerprint == data['fingerprint']
        fingerprint = data['fingerprint']
        rows.extend(data['rows'])
        for name, value in {**data['source_sha256'], **data['input_sha256']}.items():
            if name in pins:
                assert pins[name] == value
            pins[name] = value
        for p in (path, receipt_path):
            inputs[str(p.relative_to(ROOT))] = digest(p)
    assert expected_part == 64 and len(rows) == len(plan['times']) == 2561
    times = np.array([r['time'] for r in rows])
    np.testing.assert_allclose(times, plan['times'], rtol=0, atol=1e-12)
    assert all(row['order'] == (1 if i == 1 else 2) for i, row in enumerate(rows) if i)
    keys = ('CL', 'circulation', 'circulation_rate')
    actual = {key: np.array([r[key] for r in rows]) for key in keys}
    reference = {key: np.array([r['reference'][key] for r in rows]) for key in keys}
    scales = {key: np.asarray(value) for key, value in plan['baseline_fine_summary']['cold_scales'].items()}
    assert all(np.min(value) > 0 for value in scales.values())
    cold = {key: float(np.max(abs(actual[key] - (reference[key] if key == 'CL' else reference[key][:, None])) / scales[key])) for key in keys}
    periodic_path = BASE / 'periodic-reference.json'
    assert digest(periodic_path) == plan['periodic_reference_sha256']
    periodic = json.loads(periodic_path.read_text())
    phase = np.array([r['time'] for r in periodic['rows']])
    target = {key: np.array([r[key] for r in periodic['rows']]) for key in keys}
    periodic_scales = {key: np.asarray(value) for key, value in plan['baseline_fine_summary']['periodic_scales'].items()}
    assert all(np.min(value) > 0 for value in periodic_scales.values())
    measured_reference = fourier(phase, target['CL'], plan['period'])
    cycles, previous = [], None
    for cycle in range(1, 9):
        start = int(np.argmin(abs(times - (cycle-1)*plan['period'])))
        end = int(np.argmin(abs(times - cycle*plan['period'])))
        np.testing.assert_allclose(times[start:end+1] - (cycle-1)*plan['period'], phase, rtol=0, atol=1e-12)
        values = {key: value[start:end+1] for key, value in actual.items()}
        errors = {key: float(np.max(abs(values[key] - (target[key] if key == 'CL' else target[key][:, None])) / periodic_scales[key])) for key in keys}
        measured = fourier(phase, values['CL'], plan['period'])
        harmonics = [dict(order=a['order'], amplitude_error_fraction=a['amplitude']/b['amplitude']-1,
                          phase_error_deg=phase_difference(a['phase_deg'], b['phase_deg']))
                     for a, b in zip(measured['harmonics'], measured_reference['harmonics'])]
        change = None if previous is None else {key: float(np.max(abs(values[key] - previous[key]) / periodic_scales[key])) for key in keys}
        cycles.append(dict(cycle=cycle, error_fractions=errors, measured=measured, harmonic_errors=harmonics,
                           mean_CL_error_dynamic_fraction=float((measured['mean']-measured_reference['mean'])/periodic_scales['CL']),
                           cycle_change_fractions=change))
        previous = values
    diagnostics = dict(
        first_step_rate_relative_error=float(np.max(abs(actual['circulation_rate'][1]-reference['circulation_rate'][1])/abs(reference['circulation_rate'][1]))),
        maximum_heave_velocity_error=max(abs(r['heave_velocity']-r['reference']['velocity']) for r in rows),
        maximum_heave_position_error=max(abs(r['heave_position']-r['reference']['displacement']) for r in rows),
        maximum_residual=max(r['residual'] for r in rows),
        maximum_CPython_scaled_difference=max(r['CPython_scaled_difference'] for r in rows))
    gates, final, checks = plan['gates'], cycles[-1], {}
    for key, label in (('CL', 'CL'), ('circulation', 'circulation'), ('circulation_rate', 'rate')):
        checks['cold_' + key] = cold[key] < gates['cold_' + label + '_fraction']
        checks['periodic_' + key] = final['error_fractions'][key] < gates['periodic_' + label + '_fraction']
        checks['last_cycle_change_' + key] = final['cycle_change_fractions'][key] < gates['last_cycle_change_fraction']
    checks.update(amplitude=abs(final['harmonic_errors'][0]['amplitude_error_fraction']) < gates['amplitude_fraction'],
        phase=abs(final['harmonic_errors'][0]['phase_error_deg']) < gates['phase_deg'],
        mean=abs(final['mean_CL_error_dynamic_fraction']) < gates['mean_CL_dynamic_fraction'],
        residual=diagnostics['maximum_residual'] < gates['normalized_residual'],
        CPython_agreement=diagnostics['maximum_CPython_scaled_difference'] < gates['CPython_scaled_difference'])
    assert len(checks) == 14
    for name, value in {**plan['source_sha256'], **plan['input_sha256']}.items():
        if name in pins:
            assert pins[name] == value
        pins[name] = value
    inputs[str(periodic_path.relative_to(ROOT))] = digest(periodic_path)
    assert all(digest(ROOT / name) == value for name, value in {**pins, **inputs}.items())
    output = dict(passed=all(checks.values()), checks=checks, cold_error_fractions=cold,
        cycles=cycles, diagnostics=diagnostics, audited_unique_snapshots=len(rows),
        source_sha256=pins, input_sha256=inputs, fingerprint=fingerprint,
        production_changed=False, native_ASWING_comparison=False, full_history_UI_validation=False,
        new_temporal_refinement_claim=False, full_goal_complete=False)
    write(BASE / 'audit.json', output)
    print(json.dumps(dict(passed=output['passed'], checks=checks, diagnostics=diagnostics,
                          periodic_errors=final['error_fractions'])))
    if not output['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('chunk', 'combine'))
    parser.add_argument('--index', type=int)
    args = parser.parse_args()
    if args.action == 'combine':
        combine()
    elif args.index is None:
        parser.error('Chunk index required')
    else:
        chunk(args.index)
