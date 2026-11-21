"""Prepare and audit public-API replays of the retained loaded flutter boundary.

The reference is the hashed native evidence archive, not a new solve generated
by this checker. This checks portability, not agreement with original ASWING.
"""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import runpy
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MATCH = runpy.run_path(str(ROOT/'scripts/analyze-durrant-flutter.py'))['match']
SELECTION = [('n16-negative', 16, 5), ('n16-positive', 16, 4), ('n32-positive', 32, 4)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare():
    report = json.loads((ROOT/'docs/validation/loaded-flutter.json').read_text())
    evidence = report['evidence']
    path = ROOT/'docs/validation'/evidence['path']
    assert sha(path.read_bytes()) == evidence['sha256'], 'Native evidence checksum changed'
    pins = {p.name: sha(p.read_bytes()) for p in sorted((ROOT/'openswing').glob('*.py'))}
    cases = []
    with zipfile.ZipFile(path) as archive:
        for name, panels, index in SELECTION:
            directory = f'boundary75-n{panels}-run-01'
            manifest = json.loads(archive.read(directory+'/run.json'))
            assert manifest['status'] == 'computed'
            native_pins = {k.split('/')[-1]: v for k, v in manifest['source_sha256'].items()
                           if k.startswith('openswing/')}
            assert pins == native_pins, 'Current kernel differs from the native reference'
            filename = f'case-{index:03d}.json'
            record = next(c for c in manifest['cases'] if c['file'] == filename)
            data = archive.read(directory+'/'+filename)
            assert sha(data) == record['sha256']
            native = json.loads(data)
            assert native['status'] == 'computed' and native['input_time_unit_s'] == 1.
            request = dict(action='modes', source=native['source'], panels=native['panels'],
                           condition=native['condition'], gravity=native['gravity'],
                           modes=dict(frame='fixed', vacuum=False, method='full_shift_invert',
                                      count=24, shift=native['searches'][0]['shift'], step=1e-5))
            cases.append(dict(id=name, native_path=directory+'/'+filename,
                              native_sha256=sha(data), native=native, request=request))
    return dict(scope='Public-API portability of a local loaded flutter branch; ASWING agreement remains open.',
                native_evidence=evidence, modules=pins, cases=cases)


def compare(entry, actual):
    native = entry['native']
    assert actual['converged'] and actual['analysis'] == 'eigenmodes'
    assert actual['vacuum'] is False and actual['frame_mode'] == 'fixed'
    assert actual['diagnostics']['finite_dimension'] is None
    assert actual['diagnostics']['base_residual'] < 1e-7
    assert actual['diagnostics']['difference_step'] == 1e-5
    assert actual['diagnostics']['requested_method'] == 'full_shift_invert'
    assert actual['diagnostics']['requested_count'] == 24
    assert actual['diagnostics']['shift'] == entry['request']['modes']['shift']
    base = actual['base']
    assert base['structural_elements'] == native['actual_elements']
    assert base['mesh_discretization']['settings'] == native['panels']
    np.testing.assert_array_equal([n['jig_position'] for n in base['nodes']], native['jig_positions'])
    compared = 0
    largest = 0.

    def physical(a, b, where):
        nonlocal compared, largest
        if isinstance(b, dict):
            assert a.keys() == b.keys(), where
            for k in b:
                physical(a[k], b[k], where+'.'+k)
        elif isinstance(b, list):
            assert len(a) == len(b), where
            for i, (x, y) in enumerate(zip(a, b)):
                physical(x, y, f'{where}[{i}]')
        elif isinstance(b, (int, float)) and not isinstance(b, bool):
            assert np.isfinite(a) and np.isfinite(b), where
            scaled = abs(a-b)/max(1., abs(b))
            largest = max(largest, scaled)
            compared += 1
            assert abs(a-b) <= 1e-8+1e-8*abs(b), (where, a, b)
        else:
            assert a == b, where

    # All station geometry, recovered mechanics and aerodynamic strip outputs,
    # plus integrated loads; solver counters and serialized state hashes differ.
    fields = ['nodes', 'elements', 'strips', 'geometry', 'reactions', 'applied_force',
              'applied_moment', 'support_force', 'support_moment', 'force_balance',
              'moment_balance', 'gravity_body', 'operating_values', 'force', 'moment',
              'CL', 'CY', 'CD', 'Cl', 'Cm', 'Cn', 'max_displacement', 'max_rotation_deg']
    for field in fields:
        physical(base[field], native['base'][field], field)
    layout = actual['diagnostics']['state_layout']
    coordinates = layout['node_coordinates']
    assert coordinates['start'] == 0 and coordinates['width'] == 6*len(base['nodes'])
    modes = []
    for mode in actual['modes']:
        assert max(mode['right_backward_error'], mode['left_backward_error']) < 1e-9
        shape = (np.asarray(mode['right']['real'])+1j*np.asarray(mode['right']['imag']))
        shape = shape[:coordinates['width']].reshape(-1, 6).copy()
        shape[:, :3] *= coordinates['translation_scale']
        displacement = np.asarray([n['displacement']['real'] for n in mode['output']['nodes']])
        displacement = displacement+1j*np.asarray([n['displacement']['imag'] for n in mode['output']['nodes']])
        np.testing.assert_allclose(displacement, shape[:, :3], rtol=2e-7, atol=1e-9)
        modes.append(dict(eigenvalue_per_s=mode['eigenvalue'], frequency_Hz=mode['eigenvalue'][1]/(2*np.pi),
                          mechanical_shape=dict(real=shape.real.tolist(), imag=shape.imag.tolist())))
    comparison = MATCH(native, dict(jig_positions=native['jig_positions'], searches=[dict(modes=modes)]))
    assert not comparison['unmatched_before'] and not comparison['unmatched_after']
    assert comparison['pairs']
    for pair in comparison['pairs']:
        assert pair['resolved'] and pair['modal_assurance'] > 1-1e-9, pair
        assert pair['scaled_root_change'] < 2e-7, pair
    critical = min(comparison['pairs'], key=lambda p: abs(p['before'][0]))
    assert critical['before'][0]*critical['after'][0] > 0, 'Critical growth sign changed'
    assert (critical['after'][0] < 0) == entry['id'].endswith('negative')
    return dict(id=entry['id'], status='PASS', physical_values=compared,
                largest_scaled_physical_difference=largest, critical=critical,
                oscillatory_modes=comparison, base_residual=actual['diagnostics']['base_residual'])


def negative_checks(entry, actual):
    assert compare(entry, actual)['status'] == 'PASS'
    critical = min((i for i, m in enumerate(actual['modes']) if m['eigenvalue'][1] > .1*2*np.pi),
                   key=lambda i: abs(actual['modes'][i]['eigenvalue'][0]))
    records = []

    def reject(label, mutate):
        altered = copy.deepcopy(actual)
        mutate(altered)
        try:
            compare(entry, altered)
        except (AssertionError, ValueError) as error:
            records.append(dict(mutation=label, status='REJECTED', message=str(error)[:400]))
        else:
            raise AssertionError('Bad evidence accepted: '+label)

    reject('critical growth sign reversed', lambda c: c['modes'][critical]['eigenvalue'].__setitem__(
        0, -c['modes'][critical]['eigenvalue'][0]))
    reject('mechanical shape changed', lambda c: c['modes'][critical]['right']['real'].__setitem__(
        8, c['modes'][critical]['right']['real'][8]+.1))
    reject('mesh changed', lambda c: c['base'].__setitem__('structural_elements', 999))
    reject('recovered base load changed', lambda c: c['base']['force'].__setitem__(0, c['base']['force'][0]+.01))
    reject('local search changed', lambda c: c['diagnostics'].__setitem__('shift', [0., 1.]))
    return records


def check_csv(actual, path):
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows[0] == ['mode', 'beam', 't', 'sensor', 'Displacement y real [input L]',
                       'Displacement y imaginary [input L]']
    mode = min((m for m in actual['modes'] if m['eigenvalue'][1] > .1*2*np.pi),
               key=lambda m: abs(m['eigenvalue'][0]))
    nodes = {n['index']: n for n in actual['base']['nodes']}
    expected = sorted(mode['output']['nodes'], key=lambda n: nodes[n['index']]['t'])
    assert len(rows)-1 == len(expected)
    for row, node in zip(rows[1:], expected):
        station = nodes[node['index']]
        assert [int(row[0]), int(row[1]), float(row[2]), row[3]] == [mode['index']+1, station['beam'], station['t'], '']
        assert float(row[4]) == node['displacement']['real'][1]
        assert float(row[5]) == node['displacement']['imag'][1]
    return dict(status='PASS', rows=len(expected), sha256=sha(path.read_bytes()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--results', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--negative-checks', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        assert not args.prepare.exists(), 'Use a fresh bundle path'
        args.prepare.write_text(json.dumps(prepare(), indent=2, allow_nan=False)+'\n')
        return
    assert args.bundle and args.results and args.output
    bundle = json.loads(args.bundle.read_text())
    assert bundle == prepare(), 'Replay bundle differs from the audited native evidence'
    records = []
    for entry in bundle['cases']:
        path = args.results/(entry['id']+'.json')
        result = json.loads(path.read_text())
        record = compare(entry, result)
        if args.negative_checks:
            record['negative_checks'] = negative_checks(entry, result)
        csv_path = args.results/(entry['id']+'.csv')
        if csv_path.is_file():
            record['csv'] = check_csv(result, csv_path)
        record['result_sha256'] = sha(path.read_bytes())
        records.append(record)
    args.output.write_text(json.dumps(dict(status='PASS', cases=records), indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status='PASS', cases=len(records))))


if __name__ == '__main__':
    main()
