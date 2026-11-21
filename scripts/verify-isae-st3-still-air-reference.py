"""Compare retained ST3 still-air modes with an independent energy beam.

Only the source-property audit uses OpenSwing's parser. All independent modal
calculations use isae_st3_reference, which imports no OpenSwing physics.
No new production solve or parameter adjustment is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from isae_st3_reference import MATERIALS, LENGTH, ICC, INN, modes, weighted_shapes, assurance


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def verify_properties(source, name):
    model = parse_asw(source, beam_interpolation='drela-segspl-v1')
    assert model.dumps() == source and len(model.beams) == 1 and not model.diagnostics
    np.testing.assert_array_equal(model.constants, [9.81, 1.23, 340.21])
    beam, p = model.beams[0], MATERIALS[name]
    t = [.0001, .27905, .558]
    expected = dict(EIcc=p['EI'], GJ=p['GJ'], EIcs=p['coupling'], EIcn=0., EIsn=0.,
        EA=1.132e7, mg=p['mass']*9.81, mgcc=ICC*9.81, mgnn=INN*9.81,
        chord=.14, Xax=.5-p['offset']/.14, Cea=p['offset'], Cta=p['offset'],
        Ccg=p['offset'], Nea=0., Nta=0., Ncg=0., twist=0.)
    for field, value in expected.items():
        np.testing.assert_allclose(beam.value(field, t), value, rtol=2e-15, atol=1e-15)
    assert beam.domain == (.0001, .558)
    np.testing.assert_allclose(beam.position([.0001, .558]), [[0,0,0],[0,0,LENGTH]])
    np.testing.assert_allclose(beam.value('EInn', t), np.inf if p['EInn'] == 0 else p['EInn'])
    assert not any(model.records.get(k) for k in ('weight', 'engine', 'strut', 'joint'))
    # Literal Xax scale is zero in the coupled files: midchord, CG and the
    # elastic/torsion axes coincide at +.07 m. The uncoupled axes coincide at 0.
    np.testing.assert_allclose((.5-beam.value('Xax', t))*beam.value('chord', t),
                               beam.value('Ccg', t), atol=1e-15)
    return expected


def production_shapes(raw, selected, name):
    def vector(value):
        return np.asarray(value['real']) + 1j*np.asarray(value['imag'])
    fields = []
    for mode in selected:
        displacement = np.asarray([vector(node['displacement']) for node in mode['output']['nodes']])
        rotation = np.asarray([vector(node['rotation']) for node in mode['output']['nodes']])
        fields.append(np.column_stack([displacement[:,1]+MATERIALS[name]['offset']*rotation[:,2],
                                       -rotation[:,0], rotation[:,2]]))
    nodes = [node['jig_position'][2] for node in raw['base']['nodes']]
    return weighted_shapes(nodes, fields, MATERIALS[name]['mass'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=False)
    old = ROOT/'artifacts/isae/st3-additional-20261104'
    study, saved = read(old/'modal-plan.json'), read(old/'assessment.json')
    pins = dict(study['pins'])
    for path in (Path(__file__).resolve(), ROOT/'scripts/isae_st3_reference.py',
                 ROOT/'tests/test_isae_st3_reference.py', old/'modal-plan.json', old/'assessment.json',
                 ROOT/'.reference/asw_uns_theory.pdf'):
        pins[str(path.relative_to(ROOT))] = sha(path)
    for item in saved['evidence']:
        pins[item['path']] = item['sha256']
    def verify_pins():
        for path, expected in pins.items():
            assert sha(ROOT/path) == expected, path
    verify_pins()
    write(out/'plan.json', dict(pins=pins, independent_grids=[96,192],
        production_grids=[64,128], gravity=9.81, air_density=1.23,
        frequency_relative_gate=.001, mechanical_MAC_gate=.99,
        selection='First three ascending frequencies; shape checks cannot choose closer workbook targets.',
        physical_assumption='Uniform centered Rayleigh beam, real self-weight and thin-strip still-air inertia; finite axial shortening neglected.'))
    cases = {}
    start = time.monotonic()
    for name in MATERIALS:
        properties = verify_properties((ROOT/study['sources'][name]).read_text(), name)
        refs = [modes(name, n, gravity=9.81, air_density=1.23, count=5) for n in (96,192)]
        write(out/(name+'-reference.json'), refs)
        frequencies = np.asarray(refs[-1]['frequencies_Hz'][:3])
        mesh_error = abs(np.asarray(refs[0]['frequencies_Hz'][:3])/frequencies-1)
        assert max(mesh_error) < .001
        reference_shapes = weighted_shapes(refs[-1]['nodes'], refs[-1]['shapes'][:3], MATERIALS[name]['mass'])
        comparisons = []
        for n in (64,128):
            folder = old/'modal'/name/f'n{n}'
            receipt = read(folder/'execution.json')
            assert receipt['exit_code'] == 0 and receipt['terminal_observed'] is True
            raw = read(folder/'result.json')
            selected = sorted((m for m in raw['modes'] if m['eigenvalue'][1]>1e-6), key=lambda m:m['frequency'])[:3]
            native = np.asarray([m['frequency'] for m in selected])
            matrix = assurance(reference_shapes, production_shapes(raw, selected, name))
            assert np.array_equal(np.argmax(matrix, axis=1), np.arange(3))
            diagonal = np.diag(matrix)
            assert min(diagonal) > .99
            errors = abs(native/frequencies-1)
            comparisons.append(dict(intervals=n, frequencies_Hz=native.tolist(),
                relative_errors=errors.tolist(), mechanical_shape_MAC=diagonal.tolist(),
                frequency_passes=(errors<=.001).tolist()))
        assert max(comparisons[-1]['relative_errors']) < .001
        cases[name] = dict(source_properties=properties, reference_frequencies_Hz=frequencies.tolist(),
            reference_mesh_relative_errors=mesh_error.tolist(), production_comparisons=comparisons)
        print(name, json.dumps(dict(reference_Hz=frequencies.tolist(),
            fine_error_percent=(100*np.asarray(comparisons[-1]['relative_errors'])).tolist(),
            fine_minimum_MAC=min(comparisons[-1]['mechanical_shape_MAC']))), flush=True)
    verify_pins()
    write(out/'assessment.json', dict(status='INDEPENDENT_STILL_AIR_REFERENCE_CHECKED', cases=cases,
        seconds=time.monotonic()-start, pins_verified=len(pins), independent_solves=6,
        new_production_solves=0, native_workbook_matches=8, native_workbook_targets=9,
        fine_independent_frequency_matches=9, fine_independent_frequency_targets=9,
        frequency_relative_gate=.001, production_code_changed=False, whole_family_validated=False,
        qualification='Agreement checks this declared beam/strip model; native settings and modal labels remain unauthenticated.'))


if __name__ == '__main__':
    main()
