"""Untuned spatial averages of physical local yaw gyros; reuse saved full states."""
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
import check_daedalus_regular_mesh_response as response

STUDY = ROOT/'artifacts/daedalus-sensor-average-20261114'
REPORT = response.STUDY/'report/result.json'


def audit(folder, args):
    import csv
    import hashlib
    import numpy as np
    from openswing.local_motion import LocalMotion
    from openswing.sensors import measure_sensor
    previous = response.configure()
    system = previous.dynamic(SimpleNamespace(seed=response.SEED)); n = system.network
    assert np.max(abs(system.motion.rates)) == 0
    metadata = {}
    for beam in n.model.beams:
        ts, ids = n.station_nodes[beam.index]
        for t, node in zip(ts, ids):
            metadata[int(node)] = dict(node=int(node), beam=beam.index, name=beam.name,
                station=float(t), loaded_position_body_ft=system.r0[node].tolist())
    def nearest(beam, fraction):
        ts, ids = n.station_nodes[beam]
        return int(ids[np.argmin(abs(ts-(ts[0]+fraction*(ts[-1]-ts[0]))))])
    sets = {
        'frame': [n.node(5, -15.6)],
        'cabin_three': [n.node(5, -15.6), n.node(5, -13.2), n.node(5, -10.)],
        'cabin_wing_root_two': [n.node(5, -13.2), n.node(1, 0.)],
        'wing_cabin_four': [n.node(5, -13.2), nearest(1, 0.), n.node(1, 0.), nearest(1, 1.)],
        'wing_three': [nearest(1, 0.), n.node(1, 0.), nearest(1, 1.)],
        'centerline_six': [n.node(5, -13.2), n.node(1, 0.), nearest(4, .5), n.node(4, 17.5), n.node(2, 0.), n.node(3, 0.)],
        'aircraft_seven': [n.node(5, -13.2), nearest(1, 0.), n.node(1, 0.), nearest(1, 1.), nearest(4, .5), n.node(2, 0.), nearest(3, .5)],
        'component_midpoints_five': [nearest(k, .5) for k in range(1, 6)],
        'distributed_fifteen': [nearest(k, f) for k in range(1, 6) for f in (0., .5, 1.)],
        'all_nodes_equal': list(range(n.nn)),
    }
    weights = {}
    for key, ids in sets.items():
        w = np.zeros(n.nn)
        for node in ids: w[node] += 1/len(ids)
        weights[key] = w
    w = np.zeros(n.nn)
    for ids in n.beam_nodes.values():
        lengths = np.linalg.norm(np.diff(system.r0[ids], axis=0), axis=1)
        w[ids[:-1]] += .5*lengths/lengths.sum()/len(n.beam_nodes)
        w[ids[1:]] += .5*lengths/lengths.sum()/len(n.beam_nodes)
    weights['equal_components_length_mean'] = w
    for w in weights.values(): np.testing.assert_allclose(w.sum(), 1, rtol=0, atol=1e-14)
    layouts = {key: [dict(**metadata[i], weight=float(w[i])) for i in np.flatnonzero(w)] for key, w in weights.items()}
    report = read(REPORT); rows = []; checks = []; pins = {}; local_records = []
    for record in report['samples']:
        f = record['frequency_hz']; omega = 2*np.pi*f
        path = response.STUDY/record['stages'][0]/record.get('state_file', f'state-{f:.9g}.npz')
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with np.load(path) as saved: z, mapped = saved['state'], saved['output']
        frame_rate = system.W*z[system.frame_start+3:system.frame_start+6]
        local = system.W*z[system.velocity_start+3*n.nn:system.frame_start].reshape(n.nn, 3)
        absolute = frame_rate+local
        jig_axes = np.einsum('nji,nj->ni', system.Q0, absolute)
        # All gyros' +z axes are aligned with loaded body +z. Since mean rates
        # are zero, perturbing those axes contributes no first-order rate term.
        # This is the complex absolute rate at the attachment, not the elastic
        # rate alone and not an average of magnitudes.
        np.testing.assert_allclose(frame_rate[2]*180/np.pi, mapped[0], rtol=1e-13, atol=1e-13)
        if f in (1., 1.15737773741517):
            # Independently exercise the production attached-sensor function at
            # every node, with fixed mount directions aligned in the loaded base.
            sampled = []; sampled_jig = []
            for part in (np.real, np.imag):
                pair = []; pair_jig = []
                h = .001
                for sign in (1, -1):
                    dz = sign*h*part(z); dzdot = sign*h*part(1j*omega*z)
                    state, _, options = system.unpack(dz, dzdot)
                    udot, wdot = dzdot[system.velocity_start:system.frame_start].reshape(2, n.nn, 3)
                    values = []; values_jig = []
                    for node in range(n.nn):
                        m = metadata[node]; beam = next(b for b in n.model.beams if b.index == m['beam'])
                        jig = beam.position(m['station'])
                        row = np.r_[node+1, m['beam'], m['station'], jig, system.Q0[node].T[:, 0], system.Q0[node].T[:, 2]]
                        local_motion = LocalMotion(state.r[node], state.u[node], state.w[node], system.V*udot[node], system.W*wdot[node])
                        sensor = measure_sensor(row, state.r[node], state.Q[node], local_motion, options['motion_override'],
                            model=n.model, condition=None, gravity=n.gravity,
                            frame=dict(body_to_earth=state.orientation, position_earth=state.position, velocity_origin_body=state.U))
                        values.append(sensor['rates_sensor'])
                        jig_row=row.copy();jig_row[6:]=[1.,0.,0.,0.,0.,1.]
                        sensor_jig=measure_sensor(jig_row,state.r[node],state.Q[node],local_motion,options['motion_override'],
                            model=n.model,condition=None,gravity=n.gravity,
                            frame=dict(body_to_earth=state.orientation,position_earth=state.position,velocity_origin_body=state.U))
                        values_jig.append(sensor_jig['rates_sensor'])
                    pair.append(np.asarray(values))
                    pair_jig.append(np.asarray(values_jig))
                sampled.append((pair[0]-pair[1])/(2*h))
                sampled_jig.append((pair_jig[0]-pair_jig[1])/(2*h))
            measured = sampled[0]+1j*sampled[1]
            error = float(np.max(abs(measured-absolute)))
            error_jig=float(np.max(abs(sampled_jig[0]+1j*sampled_jig[1]-jig_axes)))
            assert max(error,error_jig) < 1e-9
            checks.append(dict(frequency_hz=f, sensors=n.nn, maximum_complex_rate_error_rad_s=error,
                default_jig_axes_error_rad_s=error_jig))
            local_records.append(dict(frequency_hz=f, nodes=[dict(**metadata[node],
                body_z_real_deg_s=float(absolute[node,2].real*180/np.pi),body_z_imag_deg_s=float(absolute[node,2].imag*180/np.pi),
                magnitude_deg_s=float(abs(absolute[node,2])*180/np.pi),phase_deg=float(np.angle(absolute[node,2],deg=True))) for node in range(n.nn)]))
        entries = {}
        for key, w in weights.items():
            value = w@absolute[:, 2]*180/np.pi
            incoherent = float(w@abs(absolute[:, 2])*180/np.pi)
            entries[key] = dict(real=float(value.real), imag=float(value.imag), magnitude=float(abs(value)),
                mean_magnitude=incoherent, cancellation_ratio=float(abs(value)/incoherent) if incoherent else None,
                default_jig_axes_magnitude=float(abs(w@jig_axes[:,2])*180/np.pi))
        rows.append(dict(frequency_hz=f, values=entries))
    native = read(response.STUDY/'report/reference.json')['channels']['yaw_rate']['vertices']
    native_low = min((r for r in native if .7<=r[2]<=1.8), key=lambda r:r[3])
    summaries = {}
    for key in weights:
        chosen = min((r for r in rows if .7<=r['frequency_hz']<=1.8), key=lambda r:r['values'][key]['magnitude'])
        at = next(r for r in rows if abs(r['frequency_hz']-native_low[2])<1e-12)['values'][key]
        summaries[key] = dict(sensor_count=len(layouts[key]), sampled_minimum_hz=chosen['frequency_hz'],
            sampled_minimum_magnitude=chosen['values'][key]['magnitude'], at_one_hz=next(r for r in rows if r['frequency_hz']==1.)['values'][key],
            at_native_dip=at, native_dip_error_percent=100*(at['magnitude']/native_low[3]-1))
    with (folder/'comparison.csv').open('x', newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','layout','real_deg_s_per_F3','imag_deg_s_per_F3','magnitude_deg_s_per_F3','mean_magnitude_deg_s_per_F3','cancellation_ratio'])
        for row in rows:
            for key,v in row['values'].items():writer.writerow([row['frequency_hz'],key,v['real'],v['imag'],v['magnitude'],v['mean_magnitude'],v['cancellation_ratio']])
    write(folder/'state-pins.json', pins)
    return dict(frequencies=len(rows), nodes=n.nn, units='deg/s per native F3', layouts=layouts, summaries=summaries, rows=rows,
        production_sensor_checks=checks,local_sensor_values=local_records,native_dip=dict(frequency_hz=native_low[2],magnitude=native_low[3]),
        qualification='Predetermined positive weights, complex averaging, common loaded body axes; no fitting, added sensor mass, changed dynamics or new solve. Saved 6.7 m/s level-flight case; native operating point and user loaded result remain unknown. All-node equal weights depend on mesh density. Sampled minima are not newly refined extrema.')


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args=parser.parse_args()
    inputs=response.inputs()+[ROOT/'scripts/check_daedalus_regular_mesh_response.py', REPORT,
        response.STUDY/'report/reference.json', ROOT/'docs/validation/aswing-authoritative-references.md']
    for row in read(REPORT)['samples']:
        inputs.append(response.STUDY/row['stages'][0]/row.get('state_file', f"state-{row['frequency_hz']:.9g}.npz"))
    run(STUDY, args.tag, inputs, audit, {}, __file__)
