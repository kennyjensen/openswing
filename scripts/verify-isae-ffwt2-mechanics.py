"""Independent saved-state mechanics audit of the literal FFWT10/V15/DF21 rig.

No OpenSwing mechanics, interpolation, inertia or joint routines are imported.
The fixed source hash binds the manually decoded masses and rigid geometry.
Compare the endpoint-product equations with the saved total wrench; separately
measure the exact three-coordinate rigid mechanism at the same pose/rates.
The latter is a diagnostic of discrete kinematics, not a replacement solver or
a native-reference match. Aerodynamic forces are held at their saved values.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE_SHA = '4463b15ee5184d64b1684eae31b152bc88a1b69e1cd99c045021a1fa1c330893'
POINT_MASS = .3865
TIP_DENSITY = .3676
ROOT_Y = .364
TIP_Y = .5
EX = np.array([1., 0., 0.])
H = {b: np.array([0., sign*ROOT_Y, 0.]) for b, sign in ((2, 1), (3, -1))}
AXIS = {2: np.array([.9848, -.1736, 0.]), 3: np.array([.9848, .1736, 0.])}
AXIS = {b: h/np.linalg.norm(h) for b, h in AXIS.items()}


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def rotation(axis, angle):
    x, y, z = axis
    k = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k)


def point_cloud(angles):
    """Four-point Gauss integrates each uniform rod's quadratic moments exactly."""
    points = [(POINT_MASS, np.array([.0335, y, 0.]), 1) for y in (.1588, -.1588)]
    x, w = np.polynomial.legendre.leggauss(4)
    length = TIP_Y-ROOT_Y
    for b, sign in ((2, 1), (3, -1)):
        q = rotation(AXIS[b], angles[b-2])
        for s, weight in zip((x+1)*length/2, w*length/2):
            points.append((TIP_DENSITY*weight, H[b]+q@np.array([0., sign*s, 0.]), b))
    return points


def mass_and_bias(angles, rates):
    """Lagrange mass matrix and centrifugal/Coriolis generalized force.

    Coordinates are right-handed aircraft roll and two right-handed hinge
    rotations about their fixed body axes. Products use actual line particles;
    no segment rotary correction is present in this continuum calculation.
    """
    matrix = np.zeros((3, 3)); bias = np.zeros(3)
    omega = rates[0]*EX
    for mass, r, beam in point_cloud(angles):
        jac = np.zeros((3, 3)); jac[:, 0] = np.cross(EX, r)
        a = np.cross(omega, np.cross(omega, r))
        if beam != 1:
            arm = r-H[beam]; h = AXIS[beam]; rate = rates[beam-1]
            jac[:, beam-1] = np.cross(h, arm)
            u = np.cross(h, arm)*rate
            a += 2*np.cross(omega, u)+np.cross(h, np.cross(h, arm))*rate**2
        matrix += mass*(jac.T@jac)
        bias += mass*(jac.T@a)
    return matrix, bias


def project(force, moment, r, beam):
    out = np.zeros(3)
    out[0] = (moment+np.cross(r, force))[0]
    if beam != 1:
        out[beam-1] = AXIS[beam]@(moment+np.cross(r-H[beam], force))
    return out


def check_oracle():
    points = point_cloud([0., 0.])
    assert abs(sum(m for m, _, _ in points)-.8729872) < 1e-15
    matrix, bias = mass_and_bias([0., 0.], [0., 0., 0.])
    span = TIP_Y-ROOT_Y
    expected = np.zeros((3, 3))
    expected[0, 0] = 2*POINT_MASS*.1588**2+2*TIP_DENSITY*(TIP_Y**3-ROOT_Y**3)/3
    for b in (2, 3):
        expected[b-1, b-1] = TIP_DENSITY*AXIS[b][0]**2*span**3/3
        expected[0, b-1] = expected[b-1, 0] = TIP_DENSITY*AXIS[b][0]*(ROOT_Y*span**2/2+span**3/3)
    np.testing.assert_allclose(matrix, expected, rtol=2e-15, atol=2e-18)
    np.testing.assert_array_equal(bias, np.zeros(3))
    for angles in ([.3, -.7], [-1.2, .8], [2.4, -2.]):
        m, _ = mass_and_bias(angles, [3., .4, -2.])
        np.testing.assert_allclose(m, m.T, atol=2e-18, rtol=0)
        assert np.linalg.eigvalsh(m)[0] > 0
    return dict(total_mass=.8729872, flat_mass_matrix=matrix.tolist(),
                analytical_flat_matrix_verified=True, positive_definite_poses=4)


def audit(s):
    assert s['converged'] and s['residual'] <= 1e-8
    assert not s['engines'] and not s['struts'] and not s['body_shoulders']
    # Two literal tip Weight records have zero mass, drag, volume and spin;
    # the result carries only the two active center-wing point objects.
    np.testing.assert_array_equal(s['point_forces'], np.zeros((2, 3)))
    nodes = {row['index']: row for row in s['nodes']}
    by_station = {(row['beam'], row['t']): row['index'] for row in s['nodes']}
    fields = {k: np.asarray(s[k]) for k in ('local_velocity', 'local_rates', 'local_acceleration', 'local_rate_derivative')}
    frame = s['frame']; omega = np.asarray(frame['rates_body'])
    alpha = np.asarray(frame['angular_acceleration_body']); g = np.asarray(s['gravity_body'])
    np.testing.assert_array_equal(frame['acceleration_reference_body'], np.zeros(3))
    np.testing.assert_array_equal(omega[1:], np.zeros(2))
    np.testing.assert_array_equal(alpha[1:], np.zeros(2))
    real_force = np.zeros(3); real_moment = np.zeros(3); real_generalized = np.zeros(3)
    # The main wing has zero distributed mass, two point masses, no point J/H.
    for mass, r, _ in point_cloud([0., 0.])[:2]:
        f = mass*(g-np.cross(alpha, r)-np.cross(omega, np.cross(omega, r)))
        real_force += f; real_moment += np.cross(r, f)
        real_generalized += project(f, np.zeros(3), r, 1)
    # Independent endpoint products, averaged AFTER acceleration evaluation.
    for element in s['elements']:
        b = element['beam']
        if b == 1:
            continue
        i, j = [by_station[(b, element[k])] for k in ('t0', 't1')]
        ra, rb = np.asarray(nodes[i]['position']), np.asarray(nodes[j]['position'])
        mid = (ra+rb)/2
        ds = abs(element['t1']-element['t0'])
        for index in (i, j):
            r = np.asarray(nodes[index]['position']); q = np.asarray(nodes[index]['rotation'])
            u, w, a, wd = [fields[k][index] for k in fields]
            mass = TIP_DENSITY*ds/2
            absolute_a = a+np.cross(alpha, r)+np.cross(omega, np.cross(omega, r))+2*np.cross(omega, u)
            f = mass*(g-absolute_a)
            inertia = mass*ds**2/12*(np.eye(3)-np.outer(q[:, 1], q[:, 1]))
            absolute_w = omega+w
            absolute_wd = alpha+wd+np.cross(omega, w)
            moment = -inertia@absolute_wd-np.cross(absolute_w, inertia@absolute_w)
            real_force += f; real_moment += moment+np.cross(mid, f)
            real_generalized += project(f, moment, mid, b)
    aero_force = np.zeros(3); aero_moment = np.zeros(3); aero_generalized = np.zeros(3)
    for strip in s['strips']:
        r, f, m = map(np.asarray, (strip['position'], strip['force'], strip['moment']))
        aero_force += f; aero_moment += m+np.cross(r, f)
        aero_generalized += project(f, m, r, strip['beam'])
    np.testing.assert_allclose(aero_force, s['force'], atol=2e-12, rtol=2e-12)
    np.testing.assert_allclose(aero_moment, s['moment'], atol=2e-12, rtol=2e-12)
    force_error = real_force+aero_force-s['applied_force']
    moment_error = real_moment+aero_moment-s['applied_moment']
    assert np.max(abs(force_error)) < 2e-10
    assert np.max(abs(moment_error)) < 2e-10
    angles = [np.deg2rad(row['angle_deg']) for row in s['hinges']]
    rates = [omega[0]]; accelerations = [alpha[0]]; defects = {}
    spring = np.zeros(3); stiffness = 1.7453e-8*180/np.pi
    for b in (2, 3):
        row = next(h for h in s['hinges'] if h['other_beam'] == b)
        ids = [i for i, n in nodes.items() if n['beam'] == b]
        w = fields['local_rates'][ids].mean(axis=0)
        wd = fields['local_rate_derivative'][ids].mean(axis=0)
        rate, accel = AXIS[b]@w, AXIS[b]@wd
        rates.append(rate); accelerations.append(accel)
        q = rotation(AXIS[b], angles[b-2])
        defects[b] = dict(rotation=0., position=0., velocity=0., acceleration=0., transverse_rate=0., transverse_rate_derivative=0.)
        for i in ids:
            node = nodes[i]; r = np.asarray(node['position']); arm = r-H[b]
            ideal_r = H[b]+q@np.array([0., node['t']-H[b][1], 0.])
            ideal_u = np.cross(AXIS[b], arm)*rate
            ideal_a = np.cross(AXIS[b], arm)*accel+np.cross(AXIS[b], np.cross(AXIS[b], arm))*rate**2
            values = dict(rotation=np.linalg.norm(np.asarray(node['rotation'])-q), position=np.linalg.norm(r-ideal_r),
                velocity=np.linalg.norm(fields['local_velocity'][i]-ideal_u),
                acceleration=np.linalg.norm(fields['local_acceleration'][i]-ideal_a),
                transverse_rate=np.linalg.norm(fields['local_rates'][i]-AXIS[b]*rate),
                transverse_rate_derivative=np.linalg.norm(fields['local_rate_derivative'][i]-AXIS[b]*accel))
            for k, v in values.items():defects[b][k] = max(defects[b][k], float(v))
        assert defects[b]['rotation'] < 1e-7 and defects[b]['position'] < 1e-8
        reaction = next(r for r in s['reactions'] if r['kind'] == 'joint' and r['other_node'] == row['other_node'])
        spring[b-1] = -stiffness*angles[b-2]
        # At these endpoint hinges the opposite structural-trace signs result
        # in the same restoring spring torque on either tip.
        assert abs(AXIS[b]@reaction['other_moment']-spring[b-1]) < 1e-8
    matrix, bias = mass_and_bias(angles, rates)
    gravity = np.zeros(3)
    for mass, r, b in point_cloud(angles):gravity += project(mass*g, np.zeros(3), r, b)
    continuum_real = gravity-bias-matrix@accelerations
    continuum_acceleration = np.linalg.solve(matrix, aero_generalized+spring+gravity-bias)
    balance = real_generalized+aero_generalized+spring
    assert np.max(abs(balance)) < 1e-6
    return dict(time=s['time'], numerical_residual=s['residual'],
        endpoint_force_reconstruction_error=force_error.tolist(), endpoint_moment_reconstruction_error=moment_error.tolist(),
        endpoint_generalized_balance=balance.tolist(), rigid_kinematic_defects=defects,
        angles_rad=angles, rates_rad_s=list(rates), accelerations_rad_s2=list(accelerations),
        real_generalized_moment=real_generalized.tolist(), aerodynamic_generalized_moment=aero_generalized.tolist(),
        spring_generalized_moment=spring.tolist(), gravity_generalized_moment=gravity.tolist(),
        centrifugal_coriolis_generalized_moment=bias.tolist(), exact_rigid_mass_matrix=matrix.tolist(),
        continuum_real_minus_endpoint=(continuum_real-real_generalized).tolist(),
        continuum_acceleration_same_saved_aero=continuum_acceleration.tolist(),
        continuum_acceleration_difference_deg_s2=np.rad2deg(continuum_acceleration-accelerations).tolist(),
        saved_aero_is_not_an_independent_reference=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', type=Path, nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); assert not args.output.exists()
    oracle = check_oracle(); cases = []; sources = []
    for path in args.results:
        plan = json.loads((path.parent/'plan.json').read_text())
        for row in plan['source_pins']:assert pin(row['path']) == row
        assert plan['source_pins'][0]['sha256'] == SOURCE_SHA
        source = pin(path); report = json.loads((path.parent/'report.json').read_text())
        assert report['result'] == source and report['status'] == 'SEGMENT_COMPUTED'
        result = json.loads(path.read_text())
        assert result['converged'] and result['rejected_steps'] == 0
        states = [audit(s) for s in result['snapshots']]
        assert pin(path) == source
        cases.append(dict(result=source, states=states)); sources.append(plan['source_pins'])
    out = dict(status='SAVED_STATE_MECHANICS_AUDITED', oracle=oracle, cases=cases, source_pins=sources,
        script=pin(__file__), new_physical_solves=0, native_passes_added=0,
        full_family_validated=False, production_changes=False,
        scope='Literal uniform rigid rods and point masses; prescribed zero translation/pitch/yaw acceleration; saved aerodynamic wrenches held fixed.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, allow_nan=False)+'\n')
    for c in cases:
        print(json.dumps(dict(result=c['result']['path'], states=len(c['states']),
            maximum_endpoint_balance=max(max(abs(v) for v in s['endpoint_generalized_balance']) for s in c['states']),
            maximum_roll_acceleration_difference_deg_s2=max(abs(s['continuum_acceleration_difference_deg_s2'][0]) for s in c['states']))))


if __name__ == '__main__':main()
