"""Declared attachment gyros versus literal frame outputs; no sensor fitting."""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read, write
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-local-rates-20261114'
CAPTURE = STUDY/'capture-v2'
SAVED = ROOT/'artifacts/daedalus-load-sensitivity-20261113'
LOCATIONS = [('frame_ground', 5, -15.6), ('pilot', 5, -13.2),
    ('fairing_top', 5, -10.), ('boom_fairing', 4, 2.5),
    ('boom_wing', 4, 0.), ('wing_root', 1, 0.),
    ('boom_stabilizer', 4, 17.5), ('stabilizer_root', 2, 0.),
    ('boom_fin', 4, 20.), ('fin_root', 3, 0.)]


def hat(v):
    import numpy as np
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def earth_rotation(angles):
    """Printed Eq.6, independent products of elementary rotations."""
    import numpy as np
    generators = [hat(v) for v in np.eye(3)]
    parts = []
    for g, a in [(generators[2], -angles[2]), (generators[1], angles[1]), (generators[0], -angles[0])]:
        parts.append(np.eye(3)+np.sin(a)*g+(1-np.cos(a))*(g@g))
    rz, ry, rx = parts; rotation = rz@ry@rx
    partials = np.array([-rotation@generators[0], rz@generators[1]@ry@rx, -generators[2]@rotation])
    return rotation, partials


def bank_derivative(axes, change):
    # Eq.114: Phi=atan2(-beta_Z,alpha_Z), radians.
    return (-axes[2, 2]*change[2, 1]+axes[2, 1]*change[2, 2])/(axes[2, 1]**2+axes[2, 2]**2)


def capture(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from dataclasses import replace
    from check_daedalus_wing_paper import dynamic
    from openswing.sensors import measure_sensor
    from openswing.local_motion import LocalMotion
    system = dynamic(); n = system.network; zero = np.zeros(system.size)
    state, attitude, options = system.physical_state(zero, zero, None)
    assert not np.any(state.w) and not np.any(state.Omega)
    np.testing.assert_array_equal(np.array(n.model.records['ground']), [[5., -15.6, 0.]])
    nodes = np.array([n.node(b, t) for _, b, t in LOCATIONS])
    earth, earth_partials = earth_rotation(np.deg2rad(attitude))
    assert np.max(abs(earth-state.orientation)) < 2e-14
    maps = np.load(SOURCE/'assembled-6.7/maps.npz'); C = np.zeros((len(nodes), 3, system.size))
    rate_start = system.velocity_start+3*n.nn
    for j, node in enumerate(nodes):
        q = system.Q0[node]; axes = earth@q
        for out, component in [(0, 2), (1, 0)]:
            C[j, out, rate_start+3*node:rate_start+3*node+3] = q[:, component]*system.W*180/np.pi
            C[j, out, system.frame_start+3:system.frame_start+6] = q[:, component]*system.W*180/np.pi
        for axis in range(3):
            C[j, 2, system.frame_start+9+axis] = bank_derivative(axes, earth_partials[axis]@q)*180/np.pi
            C[j, 2, 6*node+3+axis] = bank_derivative(axes, earth@hat(np.eye(3)[axis])@q)*180/np.pi
    a = sp.load_npz(SOURCE/'assembled-6.7/A.npz'); m = sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    checks = []; arrays = dict(C=C, nodes=nodes, frames=system.Q0[nodes], earth=earth)
    for name, frequency, tag in [('slow', .2, 'slow-animation'), ('dip', 1.15737773741517, 'reference-dip')]:
        z = np.load(SAVED/tag/'arrays.npz')['state']; rate = 2j*np.pi*frequency*z
        full_residual = float(max(abs((2j*np.pi*frequency*m-a)@z-maps['B'][:, 0])))
        assert full_residual < 2e-10, full_residual
        expected = C@z; observed = []
        # Validate the independent linear maps against the actual sensor API
        # at perturbed physical poses/rates. Airflow is not a tested observable.
        for h in (1e-3, 5e-4):
            value = np.zeros((len(nodes), 3), complex)
            for part, component in enumerate((np.real, np.imag)):
                for offset, weight in [(-2, 1), (-1, -8), (1, 8), (2, -1)]:
                    v = component(z)*h*offset; dv = component(rate)*h*offset
                    current, _, current_options = system.physical_state(v, dv, None)
                    c = replace(current_options['condition_override'], sensor_flow='kinematic')
                    motion = current_options['motion_override']
                    local_accel, local_alpha = dv[system.velocity_start:system.frame_start].reshape(2, n.nn, 3)
                    values = []
                    for (_, beam_id, t), node in zip(LOCATIONS, nodes):
                        beam = next(b for b in n.model.beams if b.index == beam_id)
                        row = np.r_[1., beam_id, t, beam.position(t), 1., 0., 0., 0., 0., 1.]
                        local = LocalMotion(current.r[node], current.u[node], current.w[node],
                            system.V*local_accel[node], system.W*local_alpha[node])
                        result = measure_sensor(row, current.r[node], current.Q[node], local, motion,
                            model=n.model, condition=c, gravity=np.zeros(3),
                            frame=dict(body_to_earth=current.orientation, position_earth=current.position, velocity_origin_body=current.U))
                        values.append([result['rates_sensor'][2]*180/np.pi, result['rates_sensor'][0]*180/np.pi, result['bank']])
                    value += (1 if part == 0 else 1j)*weight*np.array(values)/(12*h)
            observed.append(value)
        sensor_error = float(np.max(abs(observed[-1]-expected)))
        stencil_error = float(np.max(abs(observed[-1]-observed[0])))
        assert sensor_error < 2e-8 and stencil_error < 2e-8, (sensor_error, stencil_error)
        ground_error = float(max(abs(expected[0]-maps['C'][[0, 1, 3]]@z)))
        assert ground_error < 2e-10, ground_error
        joint_error = max(float(max(abs(expected[i]-expected[j]))) for i, j in [(2, 3), (4, 5), (6, 7), (8, 9)])
        assert joint_error < 2e-10, joint_error
        # Independent time derivative of the Earth-oriented sensor triad must
        # yield exactly the absolute gyro rate at this stationary base.
        dE = np.einsum('i,ijk->jk', z[system.frame_start+9:system.frame_start+12], earth_partials)
        theta = z[:6*n.nn].reshape(n.nn, 6)[:, 3:]
        omega = system.W*z[system.frame_start+3:system.frame_start+6]
        local = system.W*z[rate_start:system.frame_start].reshape(n.nn, 3)
        kinematic_error = 0.
        body_rates = []; elastic_rates = []
        for node in nodes:
            q = system.Q0[node]; E = earth@q
            dQ = hat(theta[node])@q
            skew = E.T@(2j*np.pi*frequency*(dE@q+earth@dQ))
            measured = np.array([skew[2, 1]-skew[1, 2], skew[0, 2]-skew[2, 0], skew[1, 0]-skew[0, 1]])/2
            predicted = q.T@(omega+local[node])
            kinematic_error = max(kinematic_error, float(max(abs(measured-predicted))))
            body_rates.append(q.T@omega*180/np.pi); elastic_rates.append(q.T@local[node]*180/np.pi)
        assert kinematic_error < 2e-10, kinematic_error
        arrays.update({name+'_state':z, name+'_output':expected, name+'_native_sensor':observed[-1],
            name+'_body_rates':np.array(body_rates), name+'_elastic_rates':np.array(elastic_rates)})
        checks.append(dict(case=name, frequency_hz=frequency, full_residual=full_residual,
            native_sensor_error=sensor_error, native_stencil_width_change=stencil_error,
            frame_ground_error=ground_error, joint_pair_error=joint_error, triad_rate_error=kinematic_error,
            magnitudes=abs(expected).tolist()))
    np.savez_compressed(folder/'arrays.npz', **arrays)
    fixture = dict(locations=[dict(name=name, beam=beam, station=t, node=int(node)) for (name, beam, t), node in zip(LOCATIONS, nodes)],
        channels=['yaw_rate', 'roll_rate', 'bank'], units=['deg/s/F3', 'deg/s/F3', 'deg/F3'],
        geometry='Zero-offset sensors, original sensor axes equal body XYZ. Local axes follow each attachment deformation.',
        original_ground=np.asarray(n.model.records['ground']).tolist(), checks=checks,
        qualification='Local gyros use Eq108 and local bank Eq114. The published frame Omega-z is unchanged. Local sideslip/airflow is not substituted or tested. No output station, axis or linear combination is fitted.')
    write(folder/'fixture.json', fixture)
    result = dict(checks=checks, locations=fixture['locations'], sensor_evaluations=320,
        physical_state_evaluations=33, aircraft_residual_evaluations=0, full_solves=0,
        qualification=fixture['qualification'])
    print(result, flush=True); return result


def sweep(folder, args):
    import csv
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    with (SOURCE/'report/comparison.csv').open() as stream:
        source = list(csv.DictReader(stream))
    frequencies = sorted(set(float(r['frequency_hz']) for r in source))
    assert len(frequencies) == 65
    selected = frequencies[args['start']:args['start']+args['count']]
    assert selected
    capture = np.load(CAPTURE/'arrays.npz'); C = capture['C']
    a = sp.load_npz(SOURCE/'assembled-6.7/A.npz'); m = sp.load_npz(SOURCE/'assembled-6.7/M.npz')
    maps = np.load(SOURCE/'assembled-6.7/maps.npz')
    for matrix in (a, m):
        for v in (matrix.data, matrix.indices, matrix.indptr): v.flags.writeable = False
    structure = ReusableBeamStructure(a, m, np.r_[np.arange(618), np.arange(1266, 1296)],
        np.arange(1266), np.arange(1384, 2032), np.arange(1384, 2032))
    samples = []; outputs = []; states = []; solves = 0
    for f in selected:
        reuse = next((name for name, value in [('slow', .2), ('dip', 1.15737773741517)] if abs(f-value)<1e-13), None)
        if reuse:
            z = capture[reuse+'_state']; checks = dict(reused_case=reuse)
        else:
            z, checks = harmonic_solve(a, m, maps['B'][:, 0], 2*np.pi*f, _structure=structure); solves += 1
        original = maps['C']@z
        reference = {r['channel']:complex(float(r['real_display']), float(r['imag_display'])) for r in source if float(r['frequency_hz'])==f}
        difference = max(abs(original[i]-reference[name]) for i, name in enumerate(['yaw_rate', 'roll_rate', 'sideslip', 'bank']))
        assert difference < 2e-9, difference
        output = C@z; states.append(z); outputs.append(output)
        ground_error = float(max(abs(output[0]-original[[0, 1, 3]]))); assert ground_error < 2e-9
        samples.append(dict(frequency_hz=f, full_checks=checks, previous_output_error=float(difference), ground_output_error=ground_error))
    np.savez_compressed(folder/'arrays.npz', frequency=np.array(selected), outputs=np.array(outputs), states=np.array(states))
    result = dict(start=args['start'], samples=samples, new_full_solves=solves, reused_full_states=len(selected)-solves,
        qualification='Unchanged descriptor and original numerical gates. Only newly defined local output maps are evaluated; all full states are retained to avoid repeating these solves.')
    print(result, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('stage', choices=['capture', 'sweep'])
    parser.add_argument('--tag', required=True); parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=10); args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_wing_paper.py', ROOT/'scripts/check_daedalus_source_operator.py',
        SOURCE/'trim-6.7-1/state.json', SOURCE/'mass-6.7/layout.json', SOURCE/'report/comparison.csv',
        ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json', ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json', ROOT/'reference/aswing_doc.txt',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz', 'M.npz', 'maps.npz')]
    inputs += list((ROOT/'openswing').glob('*.py'))
    if args['stage'] == 'capture':
        inputs += [SAVED/tag/'arrays.npz' for tag in ('slow-animation', 'reference-dip')]
    else:
        inputs += [CAPTURE/name for name in ('arrays.npz', 'fixture.json', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
