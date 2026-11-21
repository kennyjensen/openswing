"""Conditional plume-receiver diagnostics; not a recreation of an old bug.

Keep the accepted equilibrium by an explicit constant residual offset. Replace
only the selected receivers' aerodynamic linearization by its plume-free value.
Exact full-descriptor correction solves retain every state; convergence is
checked separately from the one-correction screen. No production module changes.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_circulation_phase import restore, dump, REFERENCE
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-plume-receivers-20261114'
AERO = ROOT/'artifacts/daedalus-circulation-phase-20261114'
BALANCE = ROOT/'artifacts/daedalus-source-balance-20261114/capture-dip/fixture.pkl'
SAVED = ROOT/'artifacts/daedalus-load-sensitivity-20261113'
CASES = {'slow': (.2, 'slow-animation'), 'dip': (1.15737773741517, 'reference-dip')}
GROUPS = {'wing': [1], 'stabilizer': [2], 'fin': [3], 'boom': [4],
          'fairing': [5], 'points': [], 'nonwing': [2, 3, 4, 5], 'all': [1, 2, 3, 4, 5]}


def setup():
    from daedalus_source_aero_reference import FullAeroReference
    packet = restore(AERO/'capture-base/base.pkl')
    return FullAeroReference(packet['fixture'], packet['packet']), restore(BALANCE)


def evaluate(ref, state, *, plume):
    import numpy as np
    import daedalus_source_aero_reference as module
    if plume:
        return ref.evaluate(state)
    original = module.jet_velocity; calls = []
    def zero(points, engines, direction, density, **kwargs):
        calls.append(np.shape(points))
        return np.zeros_like(points)
    module.jet_velocity = zero
    try:
        value = ref.evaluate(state)
    finally:
        module.jet_velocity = original
    # Three lifting receivers, one body quadrature array and five point masses.
    assert len(calls) == 9 and all(s == (82, 3) for s in calls[:3]), calls
    return value


def direction(ref, fixture, z, frequency, forcing=1.):
    import numpy as np
    from daedalus_source_balance_reference import chart
    d = chart(fixture, z, frequency); layout = fixture['layout']
    op = layout['operating']; value = np.asarray(op['scales'])*z[op['start']:op['start']+6]
    g = layout['circulation']; gamma = g['scale']*z[g['start']:g['start']+g['width']]
    out = dict(r=d['dr'], Q=d['dQ'], u=d['u'], w=d['w'],
        udot=2j*np.pi*frequency*d['u'], wdot=2j*np.pi*frequency*d['w'],
        gamma=gamma, gamma_dot=2j*np.pi*frequency*gamma,
        U=d['U'], Omega=d['Omega'], acceleration=value[:3], angular_acceleration=value[3:],
        controls=np.zeros_like(ref.base['controls'], complex), powers=np.zeros_like(ref.base['powers'], complex))
    out['controls'][ref.control_ids.index(3)] = forcing
    assert out.keys() == ref.base.keys()
    return out, d


def difference(ref, d, step=1e-24):
    import numpy as np
    result = None
    for part, component in enumerate((np.real, np.imag)):
        state = {k: np.asarray(v, complex)+1j*step*component(d[k]) for k, v in ref.base.items()}
        full = evaluate(ref, state, plume=True); off = evaluate(ref, state, plume=False)
        delta = {k: (off[k].imag-full[k].imag)/step*(1+0j if part == 0 else 1j) for k in full}
        if result is None: result = delta
        else:
            for k in result: result[k] += delta[k]
    assert max(abs(result['engine_force']).ravel()) == 0
    assert max(abs(result['engine_moment']).ravel()) == 0
    return result


def select(ref, values, group):
    import numpy as np
    ids = np.concatenate([np.full(len(b['element_ids']), b['index']) for b in ref.lifting])
    mask = np.isin(ids, GROUPS[group]); out = {k: np.zeros_like(v) for k, v in values.items()}
    for k in ('lifting_force', 'lifting_moment', 'circulation_local_residual'):
        out[k][mask] = values[k][mask]
    if 4 in GROUPS[group]:
        for k in ('body_force', 'body_moment'): out[k] = values[k].copy()
    if group in ('points', 'all'): out['point_force'] = values['point_force'].copy()
    return out


def residual_action(ref, fixture, motion, base_delta, derivative_delta, group):
    import numpy as np
    from daedalus_source_balance_reference import aerodynamic_transfer, derivative_wrench
    b = select(ref, base_delta, group); v = select(ref, derivative_delta, group)
    transferred = aerodynamic_transfer(fixture, motion, b, v)
    layout = fixture['layout']; nn, ne = layout['nodes'], layout['elements']
    F = layout['internal_loads']['force_scale']; ML = layout['internal_loads']['moment_scale']
    out = np.zeros(2044, complex)
    out[6*ne:6*ne+3*nn] = transferred['force'].ravel()/F
    out[6*ne+3*nn:6*(ne+nn)] = transferred['moment'].ravel()/ML
    gs = layout['circulation']['start']; ng = layout['circulation']['width']
    out[gs:gs+ng] = v['circulation_local_residual']
    wrench = derivative_wrench(fixture['base']['r'], motion['dr'], transferred['base_force'],
        transferred['force'], transferred['moment'], ref.reference[1])
    op = layout['operating']['start']; out[op:op+6] = wrench/np.r_[np.full(3, F), np.full(3, ML)]
    return out


def matrices():
    import numpy as np
    import scipy.sparse as sp
    from openswing.harmonic_structure import ReusableBeamStructure
    a, m = (sp.load_npz(SOURCE/'assembled-6.7'/name) for name in ('A.npz', 'M.npz'))
    maps = np.load(SOURCE/'assembled-6.7/maps.npz')
    for matrix in (a, m):
        for array in (matrix.data, matrix.indices, matrix.indptr): array.flags.writeable = False
    structure = ReusableBeamStructure(a, m, np.r_[np.arange(618), np.arange(1266, 1296)],
        np.arange(1266), np.arange(1384, 2032), np.arange(1384, 2032))
    return a, m, maps['B'][:, 0], maps['C'], structure


def prepare(folder, args):
    import numpy as np
    ref, fixture = setup(); full = evaluate(ref, ref.base, plume=True); off = evaluate(ref, ref.base, plume=False)
    delta = {k: off[k]-full[k] for k in full}; dump(folder/'base.pkl', dict(full=full, off=off, delta=delta))
    checks = []
    for case, (frequency, tag) in CASES.items():
        z = np.load(SAVED/tag/'arrays.npz')['state']; d, motion = direction(ref, fixture, z, frequency)
        saved = restore(AERO/('capture-'+case)/'directions.pkl')
        errors = {}
        for key in d:
            expected = saved[-1]['directions'][0][key]+1j*saved[-1]['directions'][1][key]
            errors[key] = float(np.max(abs(d[key]-expected), initial=0))
            assert np.all(abs(d[key]-expected) < 2e-8*(1+abs(expected))), (case, key, errors[key])
        checks.append(dict(case=case, physical_chart_errors=errors))
    beams = np.concatenate([np.full(len(b['element_ids']), b['index']) for b in ref.lifting])
    velocities = full['lifting_velocity']-off['lifting_velocity']
    rows = [dict(beam=int(b), maximum_plume_speed=float(np.max(np.linalg.norm(velocities[beams==b], axis=1)))) for b in np.unique(beams)]
    np.savez_compressed(folder/'arrays.npz', beam=beams, plume_velocity=velocities)
    return dict(physical_chart_checks=checks, lifting_receivers=rows, evaluations=ref.evaluations,
        maximum_static_circulation_defect=float(max(abs(delta['circulation_local_residual']))),
        static_wrench_change=np.r_[delta['total_force'], delta['total_moment']].tolist(),
        qualification='Removing plume changes equilibrium loads. Later diagnostics subtract this constant defect; they are not retrimmed physical aircraft or native historical responses.')


def screen(folder, args):
    import numpy as np
    from openswing.frequency_response import harmonic_solve
    ref, fixture = setup(); base = restore(STUDY/'prepare/base.pkl')['delta']
    frequency, tag = CASES[args['case']]; z = np.load(SAVED/tag/'arrays.npz')['state']
    d, motion = direction(ref, fixture, z, frequency)
    first = difference(ref, d, 1e-24); second = difference(ref, d, 1e-20)
    keys = list(GROUPS)
    rhs = np.column_stack([residual_action(ref, fixture, motion, base, second, k) for k in keys])
    earlier = np.column_stack([residual_action(ref, fixture, motion, base, first, k) for k in keys])
    error = float(np.max(abs(rhs-earlier))); assert error < 2e-10, error
    partition = float(max(abs(rhs[:, :6].sum(axis=1)-rhs[:, -1]))); assert partition < 2e-12, partition
    a, m, b, c, structure = matrices(); assert max(abs((2j*np.pi*frequency*m-a)@z-b)) < 2e-10
    correction, checks = harmonic_solve(a, m, rhs, 2*np.pi*frequency, _structure=structure)
    states = z[:, None]+correction; output = c@states; original = c@z
    np.savez_compressed(folder/'arrays.npz', state=z, corrections=correction, states=states,
        output=output, original_output=original, rhs=rhs)
    rows = [dict(group=k, first_correction_magnitudes=abs(output[:, i]).tolist(),
        output_change=abs(c@correction[:, i]).tolist()) for i, k in enumerate(keys)]
    return dict(frequency_hz=frequency, groups=keys, original_magnitudes=abs(original).tolist(),
        samples=rows, complex_step_change=error, receiver_partition_error=partition, full_solve_checks=checks,
        independent_aero_evaluations=ref.evaluations,
        qualification='One correction only. These magnitudes are not converged responses of the modified linearization; feedback must be iterated before interpreting them as such.')


def iterate(folder, args):
    import numpy as np
    from openswing.frequency_response import harmonic_solve
    ref, fixture = setup(); base = restore(STUDY/'prepare/base.pkl')['delta']
    frequency, tag = CASES[args['case']]; a, m, b, c, structure = matrices(); k = 2j*np.pi*frequency*m-a
    previous = read(STUDY/args['source']/'result.json'); saved = np.load(STUDY/args['source']/'arrays.npz')
    if 'groups' in previous:
        z = saved['states'][:, previous['groups'].index(args['group'])].copy(); iteration = 1
    else:
        assert previous['group'] == args['group']; z = saved['state'].copy(); iteration = previous['iterations']
    assert abs(previous['frequency_hz']-frequency) < 1e-14
    samples = []
    for _ in range(args['count']):
        d, motion = direction(ref, fixture, z, frequency)
        delta = difference(ref, d)
        action = residual_action(ref, fixture, motion, base, delta, args['group'])
        defect = b+action-k@z
        correction, checks = harmonic_solve(a, m, defect, 2*np.pi*frequency, _structure=structure)
        samples.append(dict(iteration=iteration, residual_max=float(max(abs(defect))),
            residual_relative=float(np.linalg.norm(defect)/(np.linalg.norm(k@z)+np.linalg.norm(b+action)+1e-30)),
            output_magnitudes=abs(c@z).tolist(), next_correction_output=float(max(abs(c@correction))),
            full_correction_solve_checks=checks))
        # Stop on the checked state, not an unchecked final iterate.
        if samples[-1]['residual_relative'] < 2e-10 and samples[-1]['next_correction_output'] < 2e-10:
            break
        z += correction; iteration += 1
    accepted = samples[-1]['iteration'] == iteration
    np.savez_compressed(folder/'arrays.npz', state=z, output=c@z)
    return dict(group=args['group'], frequency_hz=frequency, iterations=iteration,
        converged=accepted, samples=samples, output_magnitudes=abs(c@z).tolist(),
        independent_aero_evaluations=ref.evaluations,
        qualification='Affine equilibrium-preserving plume-receiver diagnostic, with full physical-coordinate residual checks. This is not a retrimmed aircraft, an identified historical bug, a new condition estimate for the modified pencil, or a reference pass.')


def native(folder, args):
    import numpy as np
    import openswing.propulsion as propulsion
    from check_daedalus_wing_paper import dynamic
    from openswing.frequency_response import HarmonicInput
    system = dynamic(); frequency, tag = CASES[args['case']]
    z = np.load(SAVED/tag/'arrays.npz')['state']; rate = 2j*np.pi*frequency*z
    forcing, _ = HarmonicInput(system, 'control.3', 0).at_frequency(2*np.pi*frequency)
    original = propulsion.jet_velocity; calls = [0]; jet_calls = [0]
    assert system.network.iteration_fields is None
    def zero_jet(points, *a, **kw):
        jet_calls[0] += 1
        return np.zeros_like(points)
    def sample(q, dq, force, plume):
        calls[0] += 1
        # The field hook changes without a state-key change. Explicitly discard
        # the normal aerodynamic cache before each diagnostic evaluation.
        system.network.aero_key = system.network.aero_cached = None
        if not plume:
            propulsion.jet_velocity = zero_jet
        try:
            return system.residual(q, dq, forcing=force)
        finally:
            propulsion.jet_velocity = original
    zero = np.zeros(system.size)
    base = sample(zero, zero, None, False)-sample(zero, zero, None, True)
    derivatives = []
    for h in (1e-3, 5e-4):
        value = np.zeros(system.size, complex)
        for part, component in enumerate((np.real, np.imag)):
            for offset, weight in [(-2, 1), (-1, -8), (1, 8), (2, -1)]:
                step = h*offset; force = forcing(part, step)
                off = sample(step*component(z), step*component(rate), force, False)
                full = sample(step*component(z), step*component(rate), force, True)
                value += (1 if part == 0 else 1j)*weight*(off-full)/(12*h)
        derivatives.append(value)
    source = read(STUDY/args['source']/'result.json')
    assert abs(source['frequency_hz']-frequency) < 1e-14
    expected = np.load(STUDY/args['source']/'arrays.npz')['rhs'][:, source['groups'].index('all')]
    ref, fixture = setup(); delta = restore(STUDY/'prepare/base.pkl')['delta']
    _, zero_motion = direction(ref, fixture, zero, frequency, forcing=0.)
    expected_base = residual_action(ref, fixture, zero_motion, delta, delta, 'all')
    errors = dict(stencil_width=float(max(abs(derivatives[0]-derivatives[1]))),
        independent_direction=float(max(abs(derivatives[1]-expected))),
        independent_base=float(max(abs(base-expected_base))))
    assert jet_calls[0] > calls[0]//2 and max(errors.values()) < 2e-8, (jet_calls, errors)
    np.savez_compressed(folder/'arrays.npz', native=derivatives[-1], independent=expected,
        native_base=base, independent_base=expected_base)
    return dict(frequency_hz=frequency, errors=errors, native_residual_evaluations=calls[0], zero_jet_calls=jet_calls[0],
        qualification='Independent full plume-deletion action versus production residual stencils. This validates the diagnostic, not a historical ASWING implementation or a changed aircraft equilibrium.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'screen', 'iterate', 'native']); parser.add_argument('--tag', required=True)
    parser.add_argument('--case', choices=CASES, default='dip'); parser.add_argument('--group', choices=GROUPS, default='nonwing')
    parser.add_argument('--source'); parser.add_argument('--count', type=int, default=2)
    args = vars(parser.parse_args()); assert 1 <= args['count'] <= 2
    inputs = [BALANCE, AERO/'capture-base/base.pkl', ROOT/'reference/version_notes.txt',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        ROOT/'docs/validation/aswing-authoritative-sources.json', ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'examples/dae.asw',
        ROOT/'scripts/check_daedalus_circulation_phase.py', ROOT/'scripts/daedalus_source_balance_reference.py',
        ROOT/'scripts/wing_inertia_reference.py', ROOT/'scripts/check_daedalus_wing_paper.py',
        ROOT/'scripts/check_daedalus_source_operator.py', SOURCE/'trim-6.7-1/state.json',
        SOURCE/'mass-6.7/layout.json', ROOT/'examples/dae-cruise-physical-mesh-project.json']
    inputs += [ROOT/'scripts'/p for p in REFERENCE]+list((ROOT/'openswing').glob('*.py'))
    inputs += [SOURCE/'assembled-6.7'/p for p in ('A.npz', 'M.npz', 'maps.npz')]
    for case, (_, tag) in CASES.items():
        inputs += [SAVED/tag/'arrays.npz', AERO/('capture-'+case)/'directions.pkl']
    if args['stage'] != 'prepare': inputs += [STUDY/'prepare'/p for p in ('base.pkl', 'result.json', 'terminal.json')]
    if args['stage'] in ('iterate', 'native'):
        assert args['source']; inputs += [STUDY/args['source']/p for p in ('arrays.npz', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
