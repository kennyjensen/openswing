"""Phase-independent lateral-acceleration bounds from native Bode magnitudes.

Only saved full-state responses and native graphic paths are read. No model
parameter, phase, equilibrium or response is fitted or solved here.
"""
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-lateral-kinematics-20261114'
RESPONSES = ROOT/'artifacts/daedalus-regular-mesh-response-20261114'
REPORT = RESPONSES/'report'
SEED = ROOT/'artifacts/daedalus-regular-mesh-20261114/trim-1/state.json'


def state_path(row):
    name = row.get('state_file', f'state-{row["frequency_hz"]:.9g}.npz')
    return RESPONSES/row['stages'][0]/name


def check(folder, args):
    import csv
    import hashlib
    import math
    import numpy as np

    report = read(REPORT/'result.json')
    ref = read(REPORT/'reference.json')
    metadata = read(REPORT/'terminal.json')
    assert metadata['returncode'] == 0 and metadata['process_reaped'] and metadata['inputs_unchanged']
    for path, digest in read(REPORT/'source-pins.json').items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    layout = read(RESPONSES/'mass/layout.json')
    seed = read(SEED)['operating_values']
    alpha, beta = np.deg2rad([seed['alpha'], seed['beta']])
    speed = seed['speed']
    # Independently form the physical velocity and the sideslip-direction unit
    # vector. The latter is orthogonal to the mean aircraft velocity.
    direction = np.array([-math.cos(alpha)*math.cos(beta), math.sin(beta), -math.sin(alpha)*math.cos(beta)])
    side = np.array([math.cos(alpha)*math.sin(beta), math.cos(beta), math.sin(alpha)*math.sin(beta)])
    np.testing.assert_allclose(np.cross(direction, side), [math.sin(alpha), 0, -math.cos(alpha)], atol=1e-15)
    np.testing.assert_allclose(np.dot(direction, side), 0, atol=1e-15)
    assert all(seed['rates.'+axis] == 0 for axis in 'xyz')
    # The literal Daedalus references are all at the origin. Inspect raw records
    # here, not a dynamic production helper, before identifying acceleration rows.
    raw = (ROOT/'examples/dae.asw').read_text().split('Reference', 1)[1].split('End', 1)[0]
    numbers = [list(map(float, line.split())) for line in raw.splitlines() if line.strip() and not line.lstrip().startswith(('#', '!', '*'))]
    assert all(v == 0 for line in numbers[1:] for v in line), numbers
    op = layout['operating']; frame = layout['frame']; start = frame['start']
    assert op['variables'] == ['acceleration.x', 'acceleration.y', 'acceleration.z',
                               'angular_acceleration.x', 'angular_acceleration.y', 'angular_acceleration.z']

    def graphic(channel, f):
        curve = ref['channels'][channel]; points = np.asarray(curve['vertices'])
        x0, _, x1, _ = curve['rectangle']; x = x0+math.log10(f/.1)*(x1-x0)/2
        halfwidth = .75
        lo, hi = max(x0, x-2*halfwidth), min(x1, x+2*halfwidth)
        xs = np.r_[lo, points[(points[:, 0] > lo)&(points[:, 0] < hi), 0], hi]
        values = np.interp(xs, points[:, 0], np.log(points[:, 3]))
        dy = halfwidth*curve['log_magnitude_per_point']
        return (float(np.exp(np.interp(x, points[:, 0], np.log(points[:, 3])))),
                float(np.exp(values.min()-dy)), float(np.exp(values.max()+dy)))

    rows = []; max_velocity = max_angular = max_beta = max_identity = 0.
    for row in report['samples']:
        f = row['frequency_hz']; omega = 2*np.pi*f
        with np.load(state_path(row)) as data:
            z = data['state']; saved_output = data['output']
        assert z.size == report['setup']['full_states']
        np.testing.assert_allclose(saved_output, np.array(row['real'])+1j*np.array(row['imag']), rtol=1e-12, atol=1e-14)
        du = frame['scales'][0]*z[start:start+3]
        rates = frame['scales'][1]*z[start+3:start+6]
        accels = z[op['start']:op['start']+6]*np.array(op['scales'])
        velocity_error = float(max(abs(1j*omega*du+np.cross(rates, speed*direction)-accels[:3])))
        angular_error = float(max(abs(1j*omega*rates-accels[3:])))
        beta_hat = side@du/speed
        beta_error = float(abs(beta_hat-np.deg2rad(1.)*saved_output[2]))
        side_acceleration = side@accels[:3]/speed
        reconstructed = 1j*omega*beta_hat+math.sin(alpha)*rates[0]-math.cos(alpha)*rates[2]
        identity_error = float(abs(side_acceleration-reconstructed))
        assert velocity_error < 1e-9 and angular_error < 1e-10
        assert beta_error < 1e-9 and identity_error < 1e-10
        max_velocity = max(max_velocity, velocity_error); max_angular = max(max_angular, angular_error)
        max_beta = max(max_beta, beta_error); max_identity = max(max_identity, identity_error)

        b, blo, bhi = graphic('sideslip', f)
        p, plo, phi = graphic('roll_rate', f)
        r, rlo, rhi = graphic('yaw_rate', f)
        # Permit a horizontal frequency-coordinate displacement as well as
        # each curve's x/y envelope. This repeats the declared graphic allowance.
        box = ref['channels']['sideslip']['rectangle']
        x0, x1 = box[0], box[2]; x = x0+math.log10(f/.1)*(x1-x0)/2
        wlo = 2*np.pi*.1*10**(2*(max(x0, x-.75)-x0)/(x1-x0))
        whi = 2*np.pi*.1*10**(2*(min(x1, x+.75)-x0)/(x1-x0))
        norm, norm_hi = math.hypot(p, r), math.hypot(phi, rhi)
        # |sin(alpha)*p - cos(alpha)*r| <= sqrt(|p|²+|r|²)
        # for every real alpha and every relative phase. Use radians for a/V.
        lower = math.radians(max(0, wlo*blo-norm_hi))
        upper = math.radians(whi*bhi+norm_hi)
        rows.append(dict(frequency_hz=f, reference_rate_norm_deg_s=norm,
            reference_beta_rate_deg_s=omega*b, central_zero_acceleration_ratio=omega*b/norm,
            conservative_zero_acceleration_ratio=wlo*blo/norm_hi,
            required_side_acceleration_over_speed_min_s_inv=lower,
            required_side_acceleration_over_speed_max_s_inv=upper,
            current_side_acceleration_over_speed_s_inv=float(abs(side_acceleration)),
            current_body_y_acceleration_over_speed_s_inv=float(abs(accels[1]/speed)),
            current_within_necessary_reference_bounds=bool(lower <= abs(side_acceleration) <= upper),
            zero_side_acceleration_excluded=bool(lower > 0)))

    with (folder/'bounds.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return dict(rows=rows, saved_states_checked=len(rows),
        example_rows=[r for r in rows if r['frequency_hz'] in (.1, 1.)],
        zero_side_acceleration_excluded_frequencies=sum(r['zero_side_acceleration_excluded'] for r in rows),
        current_outside_necessary_bounds_frequencies=sum(not r['current_within_necessary_reference_bounds'] for r in rows),
        maximum_frame_velocity_equation_error_ft_s2=max_velocity,
        maximum_frame_angular_acceleration_equation_error_rad_s2=max_angular,
        maximum_sideslip_output_error_rad=max_beta, maximum_acceleration_identity_error_s_inv=max_identity,
        equation='a_side/V = i*omega*beta_hat + sin(alpha0)*p_hat - cos(alpha0)*r_hat; zero base angular rates and coincident velocity/acceleration reference points.',
        necessary_bound='max(0, omega*|beta|-sqrt(|p|^2+|r|^2)) <= |a_side|/V <= omega*|beta|+sqrt(|p|^2+|r|^2). No alpha or response phase is fitted.',
        qualification='Conditioned on a stationary zero-rate base, still air and the literal coincident reference points. a_side is the acceleration projected onto the mean sideslip-direction unit vector; it equals body y acceleration only at zero mean sideslip. This can exclude a zero-side-acceleration constraint, not recover the native operating point or prove matching where necessary bounds overlap. Counts describe sampled bounds, not validation passes.')


if __name__ == '__main__':
    report = read(REPORT/'result.json')
    files = [REPORT/name for name in ['result.json', 'reference.json', 'terminal.json', 'source-pins.json']]
    files += [RESPONSES/'mass/layout.json', SEED, ROOT/'examples/dae.asw',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        ROOT/'reference/drela-rudder-bode-20261113.pdf',
        ROOT/'openswing/linear_dynamics.py', ROOT/'openswing/kinematics.py']
    files += [state_path(row) for row in report['samples']]
    run(STUDY, 'audit', files, check, {}, __file__)
