"""Compare the plotted body yaw rate with Earth-view motion and local rotation."""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
import check_daedalus_regular_mesh_response as response

STUDY = ROOT/'artifacts/daedalus-yaw-output-20261114'


def audit(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.ground import body_to_earth
    from openswing.linear_dynamics import euler_matrix, output_perturbation
    from openswing.frequency_response import HarmonicInput
    previous = response.configure()
    system = previous.dynamic(SimpleNamespace(seed=response.SEED))
    n = system.network
    f = args['frequency']; omega = 2*np.pi*f
    with np.load(response.STUDY/f'response/state-{f:.9g}.npz') as data:
        z, mapped = data['state'], data['output']
    a = sp.load_npz(response.STUDY/'assembled/A.npz')
    m = sp.load_npz(response.STUDY/'assembled/M.npz')
    with np.load(response.STUDY/'assembled/maps.npz') as data:
        b = data['B'][:, 0]
    base = system.base_report()
    forcing, _ = HarmonicInput(system, 'control.3', 0).at_frequency(omega)
    output = output_perturbation(system, z, 1j*omega*z, forcing=forcing)
    cv = lambda v: np.asarray(v['real'])+1j*np.asarray(v['imag'])
    rates = cv(output['frame']['rates_body'])
    angles = cv(output['frame']['attitude_rad'])
    recovered = euler_matrix(system.attitude)@(1j*omega*angles)
    rate_error = float(max(abs(recovered-rates)))
    assert rate_error < 1e-10
    np.testing.assert_allclose(rates[2]*180/np.pi, mapped[0], rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(cv(output['operating']['rates.z']), rates[2], rtol=1e-7, atol=1e-11)

    # Independently differentiate the actual body-to-Earth orientation matrix.
    # At the steady base, R.T dR/dt has the physical body angular velocity.
    width = .002
    derivative = []
    for component in (angles.real, angles.imag):
        rp = body_to_earth(system.attitude+np.rad2deg(width*component))
        rm = body_to_earth(system.attitude-np.rad2deg(width*component))
        derivative.append((rp-rm)/(2*width))
    dr = derivative[0]+1j*derivative[1]
    skew = system.R0.T@(1j*omega*dr)
    geometry_rates = np.array([skew[2, 1], skew[0, 2], skew[1, 0]])
    orientation_error = float(max(abs(geometry_rates-rates)))
    assert orientation_error < 1e-10

    # The renderer's Earth geometry must add the same frame rotation and
    # translation to every body-view point, without any fitted rigid motion.
    geometry_error = 0.
    translation = cv(output['frame']['position_earth'])
    for original, body, earth in zip(base['geometry'], output['geometry'], output['earth_geometry']):
        assert original['index'] == body['index'] == earth['index']
        for key in ('axis', 'quads', 'streamwise_quads'):
            if key not in original:
                continue
            points = np.asarray(original[key])
            expected = cv(body[key])@system.R0.T + points@dr.T + translation
            geometry_error = max(geometry_error, float(np.max(abs(cv(earth[key])-expected))))
    assert geometry_error < 1e-6

    local = z[:6*n.nn].reshape(n.nn, 6)[:, 3:]
    local_rates = system.W*z[system.velocity_start+3*n.nn:system.frame_start].reshape(n.nn, 3)
    assert np.max(abs(1j*omega*local-local_rates)) < 1e-10
    nodes = []
    for beam, station, label in [(5, -15.6, 'Frame anchor / fairing bottom'),
                                  (5, -13.2, 'Pilot attachment'),
                                  (5, -10., 'Fairing / boom joint'),
                                  (1, 0., 'Wing root'),
                                  (4, 17.5, 'Horizontal-tail attachment'),
                                  (3, 0., 'Fin root')]:
        node = n.node(beam, station)
        absolute = rates+local_rates[node]
        sensor = system.Q0[node].T@absolute
        # Heading of the deformed local fore/aft direction, as seen in Earth.
        axis = system.Q0[node][:, 0]
        axis_earth = system.R0@axis
        d_axis = dr@axis + system.R0@np.cross(local[node], axis)
        heading = (axis_earth[1]*d_axis[0]-axis_earth[0]*d_axis[1]) / sum(axis_earth[:2]**2)
        nodes.append(dict(label=label, beam=beam, station=station, node=node,
            elastic_body_z_rate_deg_s=float(abs(local_rates[node, 2])*180/np.pi),
            absolute_body_z_rate_deg_s=float(abs(absolute[2])*180/np.pi),
            attached_sensor_z_rate_deg_s=float(abs(sensor[2])*180/np.pi),
            heading_amplitude_deg=float(abs(heading)*180/np.pi)))
    assert nodes[0]['elastic_body_z_rate_deg_s'] < 1e-10

    # Complete nonlinear residual checks of this particular harmonic state.
    zero = np.zeros(system.size); checks = []
    for width in (.002, .004):
        def direction(v, rate):
            evaluate = lambda k: system.residual(zero, k*width*v) if rate else system.residual(k*width*v, zero)
            return (evaluate(-2)-8*evaluate(-1)+8*evaluate(1)-evaluate(2))/(12*width)
        state = direction(z.real, False)+1j*direction(z.imag, False)
        mass = -direction(z.real, True)-1j*direction(z.imag, True)
        error = float(max(abs(1j*omega*mass-state-b)))
        assert error < 1e-9
        checks.append(dict(width=width, complete_harmonic_residual=error,
            state_action_error=float(max(abs(a@z-state))),
            mass_action_error=float(max(abs(m@z-mass)))))

    fixture_base = {key: base[key] for key in ('geometry', 'attachments', 'modal_base', 'ground_plane') if key in base}
    fixture_output = {key: output[key] for key in ('geometry', 'earth_geometry', 'attachments', 'earth_attachments', 'frame')}
    write(folder/'animation-fixture.json', dict(base=fixture_base,
        inputs=[dict(kind='control', name='control.3')],
        samples=[dict(omega=omega, responses=[dict(output=fixture_output)])]))
    return dict(frequency_hz=f, unit_input='native F3', nodes=nodes,
        frame_yaw_rate_deg_s=float(abs(rates[2])*180/np.pi),
        frame_heading_amplitude_deg=float(abs(angles[2])*180/np.pi),
        frame_heading_rate_deg_s=float(abs(omega*angles[2])*180/np.pi),
        body_rate_from_euler_rate_error_rad_s=rate_error,
        body_rate_from_earth_orientation_error_rad_s=orientation_error,
        earth_geometry_max_error_ft_per_F3=geometry_error,
        harmonic_checks=checks,
        qualification='Exact recorded frame output and published Euler kinematics; local measurements include elastic rotation. No native sensor location or operating point is inferred.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--frequency', required=True, type=float)
    args = vars(parser.parse_args())
    inputs = response.inputs()+[ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        ROOT/'web/frequency-results.js', ROOT/'web/mode-results.js', ROOT/'web/time-results.js',
        ROOT/'web/frequency-data.js', response.REFERENCE,
        ROOT/'reference/drela-rudder-bode-20261113.pdf']
    for directory in (response.STUDY/'assembled', response.STUDY/'response'):
        inputs.extend(p for p in directory.iterdir() if p.suffix in ('.npz', '.json'))
    run(STUDY, args['tag'], inputs, audit, args, __file__)
