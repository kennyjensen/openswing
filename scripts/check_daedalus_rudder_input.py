"""Isolate literal rudder effectiveness and the full descriptor input column."""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run
from check_daedalus_circulation_phase import restore, REFERENCE

STUDY = ROOT/'artifacts/daedalus-rudder-input-20261114'
AERO = ROOT/'artifacts/daedalus-circulation-phase-20261114'


def native(folder, args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from openswing.frequency_response import HarmonicInput
    system = dynamic(); n = system.network; zero = np.zeros(system.size)
    assert system.feedback is None
    materials = []
    for mesh in n.meshes:
        if not mesh.beam.lifting: continue
        beam = mesh.beam; stations = np.r_[mesh.t0, mesh.tm, mesh.t1]
        gain = beam.value('dCLdF3', stations)/beam.value('dCLda', stations)
        expected = -.01745 if beam.index == 3 else 0.
        np.testing.assert_allclose(gain, expected, atol=2e-17, rtol=0)
        for key in ('dCMdF3', 'dCDdF3'):
            assert not np.any(beam.value(key, stations)), (beam.index, key)
        if beam.index == 3:
            np.testing.assert_allclose(beam.value('dCLda', stations), 6.2, atol=0, rtol=0)
        materials.append(dict(beam=beam.index, samples=len(stations),
            incidence_radians_per_F3_min=float(gain.min()), incidence_radians_per_F3_max=float(gain.max())))
    input_map = HarmonicInput(system, 'control.3', 0)
    matrices = []; checks = []
    for frequency in (.2, 1.15737773741517):
        forcing, extra = input_map.at_frequency(2*np.pi*frequency)
        assert extra is None
        estimates = []
        for h in (1e-3, 5e-4):
            value = np.zeros(system.size)
            for offset, weight in [(-2, 1), (-1, -8), (1, 8), (2, -1)]:
                value += weight*system.residual(zero, zero, forcing=forcing(0, h*offset))/(12*h)
            estimates.append(value)
        step_error = float(max(abs(estimates[0]-estimates[1])))
        assert step_error < 2e-8, step_error
        matrices.append(estimates[-1]); checks.append(dict(frequency_hz=frequency, step_error=step_error))
    np.testing.assert_array_equal(matrices[0], matrices[1])
    saved = np.load(SOURCE/'assembled-6.7/maps.npz')['B'][:, 0]
    error = float(max(abs(saved-matrices[-1]))); assert error < 2e-8, error
    np.savez_compressed(folder/'arrays.npz', fresh_input=matrices[-1], saved_input=saved)
    result = dict(materials=materials, input_report=input_map.report, frequency_checks=checks,
        saved_column_error=error, nonlinear_evaluations=16, feedback_active=False,
        literal_radians_per_degree_difference_percent=100*(.01745/(np.pi/180)-1),
        qualification='Current literal F3 incidence mixing, pure input at fixed physical state, no state feedback. Frequency-independent direct-command column; no actuator or rudder material parameter inferred.')
    print(result, flush=True); return result


def reference(folder, args):
    import copy
    import numpy as np
    from daedalus_source_aero_reference import FullAeroReference, sample_beam
    packet = restore(AERO/'capture-base/base.pkl'); fixture = copy.deepcopy(packet['fixture'])
    # Literal file values, independently imposed instead of trusting captured
    # control coefficients. Other geometry/material/mean-state inputs remain
    # the same declared current aircraft.
    for beam in fixture['beams']:
        if not beam['lifting']: continue
        material = beam['material_receiver']; size = len(material['chord'])
        target = -.01745*6.2 if beam['index'] == 3 else 0.
        np.testing.assert_allclose(material['dCLdF3'], target, atol=2e-17, rtol=0)
        material['dCLdF3'] = np.full(size, target)
        for key in ('dCMdF3', 'dCDdF3'):
            assert not np.any(material[key]); material[key] = np.zeros(size)
        if beam['index'] == 3:
            np.testing.assert_allclose(material['dCLda'], 6.2, atol=0, rtol=0)
            material['dCLda'] = np.full(size, 6.2)
    ref = FullAeroReference(fixture, packet['packet'], quadrature=32)
    estimates = []
    for step in (1e-24, 1e-20):
        state = {k: v.astype(complex) for k, v in ref.base.items()}
        state['controls'][ref.control_ids.index(3)] += 1j*step
        values = ref.evaluate(state)
        estimates.append({k: np.asarray(v).imag/step for k, v in values.items()})
    maxstep = max(float(np.max(abs(estimates[0][k]-v), initial=0)) for k, v in estimates[1].items())
    assert maxstep < 2e-10, maxstep
    value = estimates[-1]; layout = read(SOURCE/'mass-6.7/layout.json')
    nn, ne = layout['nodes'], layout['elements']; start = layout['circulation']['start']
    ng = layout['circulation']['width']; operating = layout['operating']['start']
    F = layout['internal_loads']['force_scale']; ML = layout['internal_loads']['moment_scale']
    expected = np.zeros(2044); nodal_force = np.zeros((nn, 3)); nodal_moment = np.zeros((nn, 3))
    sections = [sample_beam(b, ref.base, fixture['ends']) for b in ref.lifting]
    ends = np.concatenate([fixture['ends'][b['element_ids']] for b in ref.lifting])
    midpoint = np.concatenate([(s['r0']+s['r1'])/2 for s in sections])
    receiver = np.concatenate([s['rm'] for s in sections])
    force = value['lifting_force']
    couple = value['lifting_moment']+np.cross(receiver-midpoint, force)
    for j, (a, b) in enumerate(ends):
        for node in (a, b):
            nodal_force[node] += force[j]/2; nodal_moment[node] += couple[j]/2
    expected[6*ne:6*ne+3*nn] = nodal_force.ravel()/F
    expected[6*ne+3*nn:6*(ne+nn)] = nodal_moment.ravel()/ML
    expected[start:start+ng] = value['circulation_local_residual']
    expected[operating:operating+6] = np.r_[value['total_force']/F, value['total_moment']/ML]
    target = np.load(STUDY/'native/arrays.npz')
    errors = {key: float(max(abs(expected-target[key]))) for key in ('fresh_input', 'saved_input')}
    gate = 2e-8+2e-8*abs(expected)
    for key in errors: assert np.all(abs(expected-target[key]) <= gate), errors
    beam_ids = np.concatenate([np.full(len(b['element_ids']), b['index']) for b in ref.lifting])
    only_fin = beam_ids == 3
    assert np.max(abs(expected[start:start+ng][~only_fin]), initial=0) == 0
    # Direct F3 changes the quasi-normal and its tangency/profile term. It is
    # not a physical node rotation, angular acceleration, or circulation rate.
    absent = ('lifting_rate_force', 'lifting_apparent_force', 'lifting_apparent_moment',
        'body_force', 'body_moment', 'point_force', 'engine_force', 'engine_moment')
    missing_terms = {k: float(np.max(abs(value[k]), initial=0)) for k in absent}
    assert max(missing_terms.values()) == 0, missing_terms
    nodal_total = np.r_[nodal_force.sum(axis=0),
        (nodal_moment+np.cross(ref.base['r']-ref.reference[1], nodal_force)).sum(axis=0)]
    total = np.r_[value['total_force'], value['total_moment']]
    closure = float(max(abs(nodal_total-total))); assert closure < 2e-10
    np.savez_compressed(folder/'arrays.npz', expected_input=expected, beam=beam_ids,
        derivative_force=force, derivative_couple=couple, total_wrench=total,
        nodal_force=nodal_force, nodal_moment=nodal_moment)
    result = dict(rows=2044, fin_circulation_rows=int(only_fin.sum()), comparison_errors=errors,
        independent_complex_step_difference=maxstep, absent_direct_terms=missing_terms,
        nodal_global_wrench_closure=closure, direct_wrench=total.tolist(),
        maximum_circulation_input=float(max(abs(expected[start:start+ng]))),
        qualification='Isolated complete F3 column checked against independently integrated aerodynamic fields and literal raw control coefficients. No physical rudder hinge motion or direct flap-rate force is specified by the documented incidence-mixing input. These do not prove historical run settings.')
    print(result, flush=True); return result


def response(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    a = sp.load_npz(SOURCE/'assembled-6.7/A.npz')
    m = sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    for matrix in (a, m):
        for data in (matrix.data, matrix.indices, matrix.indptr): data.flags.writeable = False
    maps = np.load(SOURCE/'assembled-6.7/maps.npz')
    reference = np.load(STUDY/'reference/arrays.npz')['expected_input']
    rhs = np.c_[maps['B'][:, 0], reference]
    structure = ReusableBeamStructure(a, m, np.r_[np.arange(618), np.arange(1266, 1296)],
        np.arange(1266), np.arange(1384, 2032), np.arange(1384, 2032))
    cases = []; saved = {}
    for name, f in [('slow', .2), ('dip', 1.15737773741517)]:
        z, checks = harmonic_solve(a, m, rhs, 2*np.pi*f, _structure=structure)
        y = maps['C']@z
        difference = abs(y[:, 1]-y[:, 0])/abs(y[:, 0])
        assert max(difference) < 2e-7, difference
        cases.append(dict(name=name, frequency_hz=f, relative_output_differences=difference.tolist(),
            original_magnitudes=abs(y[:, 0]).tolist(), independent_input_magnitudes=abs(y[:, 1]).tolist(),
            solve_checks=checks))
        saved[name+'_state'] = z; saved[name+'_output'] = y
    np.savez_compressed(folder/'arrays.npz', **saved)
    result = dict(cases=cases, factorizations=2, right_hand_sides=4,
        qualification='Complete current descriptor, original numerical gates, original versus independently constructed pure F3 input. Temporary comparison only; no saved production input column or aircraft state is replaced.')
    print(result, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('stage', choices=['native', 'reference', 'response'])
    parser.add_argument('--tag', required=True); args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_circulation_phase.py', ROOT/'scripts/check_daedalus_wing_paper.py',
        ROOT/'scripts/check_daedalus_source_operator.py', SOURCE/'trim-6.7-1/state.json',
        SOURCE/'mass-6.7/layout.json', SOURCE/'assembled-6.7/maps.npz',
        ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += list((ROOT/'openswing').glob('*.py'))+[ROOT/'scripts'/p for p in REFERENCE]
    if args['stage'] == 'reference':
        inputs += [AERO/'capture-base/base.pkl']
        inputs += [STUDY/'native'/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    if args['stage'] == 'response':
        inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz', 'M.npz')]
        inputs += [STUDY/'reference'/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
