"""Evaluate physical gyro outputs at CG and origin with explicit attachments."""
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT
from daedalus_bounded_job import run
import check_daedalus_regular_mesh_response as response

STUDY = ROOT/'artifacts/daedalus-reference-gyro-20261114'


def audit(folder, args):
    import numpy as np
    from openswing.local_motion import LocalMotion
    from openswing.sensors import measure_sensor
    previous = response.configure()
    system = previous.dynamic(SimpleNamespace(seed=response.SEED)); n = system.network
    base = system.base_report(); cg = np.asarray(base['mass_properties']['cg'])
    rows = []
    for frequency in (1., 1.15737773741517):
        omega = 2*np.pi*frequency
        with np.load(response.STUDY/f'response/state-{frequency:.9g}.npz') as data:
            z = data['state']; rate = 1j*omega*z
        frame_rate = system.W*z[system.frame_start+3:system.frame_start+6]
        for beam, station, anchor_name in [(5, -15.6, 'Aircraft frame'),
                                          (5, -13.2, 'Pilot attachment'),
                                          (1, 0., 'Wing root')]:
            node = n.node(beam, station)
            jig = next(b for b in n.model.beams if b.index == beam).position(station)
            values = []
            for position_name, point in [('Reference origin', np.zeros(3)), ('Loaded-base CG', cg)]:
                # Sensor rows describe the undeformed pylon tip. Choose it so
                # the deformed base sensor sits at the requested actual point.
                specified = jig+system.Q0[node].T@(point-system.r0[node])
                row = np.r_[1, beam, station, specified, [1., 0., 0.], [0., 0., 1.]]
                components = []
                for part in (np.real, np.imag):
                    sampled = []
                    h = .002
                    for sign in (1, -1):
                        dz, dzdot = sign*h*part(z), sign*h*part(rate)
                        state, _, options = system.unpack(dz, dzdot)
                        udot, wdot = dzdot[system.velocity_start:system.frame_start].reshape(2, n.nn, 3)
                        local = LocalMotion(state.r[node], state.u[node], state.w[node],
                                            system.V*udot[node], system.W*wdot[node])
                        sensor = measure_sensor(row, state.r[node], state.Q[node], local,
                            options['motion_override'], model=n.model, condition=None,
                            gravity=options.get('gravity_override', n.gravity),
                            frame=dict(body_to_earth=state.orientation,
                                       position_earth=state.position, velocity_origin_body=state.U))
                        sampled.append(np.asarray(sensor['rates_sensor']))
                    components.append((sampled[0]-sampled[1])/(2*h))
                measured = components[0]+1j*components[1]
                values.append(measured)
                rows.append(dict(frequency_hz=frequency, attachment=anchor_name,
                    attachment_beam=beam, attachment_station=station,
                    location=position_name, base_location_body_ft=point.tolist(),
                    yaw_rate_deg_s_per_F3=float(abs(measured[2])*180/np.pi),
                    real_rad_s_per_F3=measured.real.tolist(), imag_rad_s_per_F3=measured.imag.tolist()))
                if beam == 5 and station == -15.6:
                    np.testing.assert_allclose(measured, frame_rate, atol=1e-12, rtol=1e-10)
            np.testing.assert_allclose(values[0], values[1], atol=1e-14, rtol=0)
    return dict(rows=rows,loaded_cg_body_ft=cg.tolist(),
        qualification='Actual production gyro measurement at two positions for each explicitly stated pylon attachment. No sensor/model change enters the dynamic solve. Airflow is not evaluated because angular rate is independent of air velocity. No claim about Drela\'s undocumented historical sensor definition.')


if __name__ == '__main__':
    inputs = response.inputs()+[ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        ROOT/'reference/aswing_doc.txt']
    inputs.extend(p for p in (response.STUDY/'response').iterdir() if p.suffix in ('.npz', '.json'))
    run(STUDY, 'audit', inputs, audit, {}, __file__)
