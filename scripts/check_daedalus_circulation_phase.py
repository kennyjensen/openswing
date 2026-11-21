"""Current loaded-aircraft aerodynamic replay against independent quadrature.

Serial, resource-bounded stages. The older independent full-aerodynamic
evaluator receives newly captured physical inputs from the current source
operator; old expected arrays and old trim states are never reused.
Pickle files contain only locally generated evidence, not downloaded input.
"""
import argparse
import importlib.util
import pickle
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, SOURCE, read, pin
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-circulation-phase-20261114'
CAPTURE = ROOT/'tests/data/daedalus-full-aero/capture.py'
TARGETS = ROOT/'tests/test_daedalus_full_aero.py'
SAVED = ROOT/'artifacts/daedalus-load-sensitivity-20261113'
CASES = {'slow': (.2, 'slow-animation'), 'dip': (1.15737773741517, 'reference-dip')}
REFERENCE = ['daedalus_full_aero_reference.py', 'daedalus_vortex_receivers.py',
             'daedalus_volume_reference.py', 'daedalus_jet_reference.py',
             'free_elastic_aero.py', 'elastic_fin_aero.py', 'elastic_fin_kinematics.py',
             'daedalus_source_aero_reference.py']


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def dump(path, value):
    with path.open('xb') as stream: pickle.dump(value, stream, protocol=5)


def restore(path):
    with path.open('rb') as stream: return pickle.load(stream)


def metrics(actual, expected):
    import numpy as np
    assert actual.keys() == expected.keys()
    errors = {}
    for key in actual:
        a, b = np.asarray(actual[key]), np.asarray(expected[key])
        assert a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all(), key
        difference = abs(a-b); gate = 2e-7+2e-7*abs(b)
        errors[key] = dict(max_absolute=float(np.max(difference, initial=0)),
                          max_gate_ratio=float(np.max(difference/gate, initial=0)), count=int(a.size))
    assert all(e['max_gate_ratio'] <= 1 for e in errors.values()), errors
    return errors


def capture(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from daedalus_full_aero_reference import physical_inputs
    helper = module(CAPTURE, '_current_aero_capture')
    targets = module(TARGETS, '_current_aero_targets').native_targets
    system = dynamic(); n = system.network; zero = np.zeros(system.size)
    fixture = helper.fixed_fixture(system, (ROOT/'examples/dae.asw').read_text())
    base = helper.capture(system, zero, zero)
    error = float(max(abs(base['native']['residual']))); assert error < 1e-9
    control_ids = sorted(map(int, base['inputs']['condition']['controls']))
    power_ids = sorted(map(int, base['inputs']['condition']['powers']))
    physical = lambda packet: physical_inputs(packet, control_ids, power_ids)
    dump(folder/'base.pkl', dict(fixture=fixture, packet=base))
    np.savez_compressed(folder/'base-targets.npz', **targets(base))
    if args['case'] == 'base':
        return dict(base_residual=error, nodes=n.nn, panels=n.ng, size=system.size,
                    structural_operator=n.structural_operator, nonlinear_evaluations=1)
    frequency, tag = CASES[args['case']]; omega = 2*np.pi*frequency
    saved = np.load(SAVED/tag/'arrays.npz'); z = saved['state']; rate = 1j*omega*z
    a, m = (sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz', 'M.npz'))
    maps = np.load(SOURCE/'assembled-6.7/maps.npz')
    replay_error = float(max(abs((1j*omega*m-a)@z-maps['B'][:, 0])))
    assert replay_error < 2e-10
    widths = []
    for step in (1e-3, 5e-4):
        directions, observed = [], []
        for part, component in enumerate((np.real, np.imag)):
            d = {k: np.zeros_like(v) for k, v in physical(base).items()}
            target = {k: np.zeros_like(v) for k, v in targets(base).items()}
            for offset, weight in [(-2, 1), (-1, -8), (1, 8), (2, -1)]:
                h = offset*step
                packet = helper.capture(system, h*component(z), h*component(rate), h if part == 0 else 0.)
                factor = weight/(12*step)
                for key, value in physical(packet).items(): d[key] += factor*value
                for key, value in targets(packet).items(): target[key] += factor*value
            directions.append(d); observed.append(target)
        widths.append(dict(step=step, directions=directions, targets=observed))
    differences = [metrics(widths[0]['targets'][i], widths[1]['targets'][i]) for i in range(2)]
    dump(folder/'directions.pkl', widths)
    np.savez_compressed(folder/'response.npz', state=z, rate=rate, output=maps['C']@z)
    return dict(base_residual=error, full_matrix_residual=replay_error, frequency_hz=frequency,
                nonlinear_evaluations=17, stencil_comparisons=differences,
                structural_operator=n.structural_operator,
                qualification='Physical input chart and material samples are supplied; observed fields and loads are comparison targets only.')


def reference(folder, args):
    import numpy as np
    from daedalus_source_aero_reference import FullAeroReference
    source = STUDY/args['source']; data = restore(source/'base.pkl')
    ref = FullAeroReference(data['fixture'], data['packet'], quadrature=args['quadrature'])
    if args['case'] == 'base':
        result = ref.evaluate(ref.base); expected = dict(np.load(source/'base-targets.npz'))
        np.savez_compressed(folder/'arrays.npz', **result)
        errors = metrics(result, expected)
        return dict(comparisons=errors, evaluations=ref.evaluations, quadrature=args['quadrature'])
    widths = restore(source/'directions.pkl'); part = args['part']
    # Check both native stencil widths against the independent analytic
    # continuation; do not reuse native aerodynamic derivatives as expectations.
    results, errors = [], []
    for step in (1e-24, 1e-20):
        direction = widths[-1]['directions'][part]
        state = {k: value.astype(complex)+1j*step*direction[k] for k, value in ref.base.items()}
        evaluated = ref.evaluate(state)
        result = {k: value.imag/step for k, value in evaluated.items()}
        errors.append([metrics(width['targets'][part], result) for width in widths])
        results.append(result)
    step_errors = metrics(results[0], results[1])
    np.savez_compressed(folder/'arrays.npz', **results[-1])
    return dict(comparisons=errors, complex_step_comparisons=step_errors,
                evaluations=ref.evaluations, quadrature=args['quadrature'], part=part,
                frequency_hz=CASES[args['case']][0])


def diagnose(folder, args):
    import numpy as np
    from daedalus_full_aero_reference import FullAeroReference, sample_beam
    data = restore(STUDY/args['source']/'base.pkl')
    ref = FullAeroReference(data['fixture'], data['packet'], quadrature=args['quadrature'])
    actual = ref.evaluate(ref.base); expected = dict(np.load(STUDY/args['source']/'base-targets.npz'))
    np.savez_compressed(folder/'arrays.npz', **actual)
    fields = {}
    for beam, native in zip(ref.beams, data['packet']['inputs']['meshes']):
        value = sample_beam(beam, ref.base, ref.ends)
        fields[str(beam['index'])] = {key:float(np.max(abs(value[key]-native[target]))) for key,target in
            [('r0','r0'), ('r1','r1'), ('rm','rm'), ('Rm','frames'), ('R0','frame0'), ('R1','frame1'), ('ds','length')]}
    differences = {key:dict(maximum=float(np.max(abs(value-expected[key]))),
        index=list(map(int,np.unravel_index(np.argmax(abs(value-expected[key])),value.shape)))) for key,value in actual.items()}
    strips = [s for s in data['packet']['native']['aero']['strips'] if s['lifting']]
    examples = []
    for index in sorted(set(differences[k]['index'][0] for k in ('lifting_force','lifting_moment','lifting_velocity','circulation_local_residual'))):
        examples.append(dict(index=index,beam=strips[index]['beam'],t=strips[index]['t'],native=strips[index],
            independent={k:v[index].tolist() for k,v in actual.items() if k.startswith('lifting_')}))
    result = dict(geometry_errors=fields,output_differences=differences,examples=examples,
                  qualification='Mismatch inspection; comparison gates unchanged and no pass claimed.')
    print(fields,flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['capture', 'reference', 'diagnose'])
    parser.add_argument('--case', choices=['base', *CASES], default='base')
    parser.add_argument('--tag', required=True); parser.add_argument('--source')
    parser.add_argument('--part', type=int, choices=[0, 1], default=0)
    parser.add_argument('--quadrature', type=int, choices=[16, 32], default=32)
    args = vars(parser.parse_args())
    inputs = [CAPTURE, TARGETS, ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json',
              ROOT/'scripts/check_daedalus_wing_paper.py', ROOT/'scripts/check_daedalus_source_operator.py',
              SOURCE/'trim-6.7-1/state.json', ROOT/'docs/validation/aswing-authoritative-sources.json',
              ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
              ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    inputs += [ROOT/'scripts'/name for name in REFERENCE]+list((ROOT/'openswing').glob('*.py'))
    if args['stage'] == 'capture' and args['case'] != 'base':
        inputs += [SAVED/CASES[args['case']][1]/'arrays.npz']
        inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz', 'M.npz', 'maps.npz')]
    if args['stage'] in ('reference', 'diagnose'):
        assert args['source']
        inputs += [STUDY/args['source']/name for name in ('base.pkl', 'base-targets.npz', 'result.json', 'terminal.json')]
        assert read(STUDY/args['source']/'terminal.json')['returncode'] == 0
        if args['case'] != 'base': inputs += [STUDY/args['source']/'directions.pkl']
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
