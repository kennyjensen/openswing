"""Independent instantaneous aerodynamic audit of literal FFWT10/V15/DF21.

Uses numpy and saved positions, motion, Gamma and Gamma-dot only. No production
geometry, vortex, section-load, apparent-mass or stall routines are imported.
The source hash binds the manually decoded constant section properties. This
checks the spatial flow/load equations at a saved state, not time accuracy or
the unknown original ASWING startup. No output is fitted to the native table.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE_SHA = '4463b15ee5184d64b1684eae31b152bc88a1b69e1cd99c045021a1fa1c330893'
CHORD = .067
RHO = 1.2256
EX = np.array([1., 0., 0.])


def pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def segment_velocity(point, a, b):
    """Endpoint-vector form of the unsmoothed finite Biot--Savart integral."""
    r1, r2 = point-a, point-b
    cross = np.cross(r1, r2); square = cross@cross
    if square < 1e-28:
        return np.zeros(3)  # Collinear non-self segments have zero velocity.
    value = (b-a)@(r1/np.linalg.norm(r1)-r2/np.linalg.norm(r2))
    return cross*value/(4*np.pi*square)


def ray_velocity(point, origin):
    """Integral along a positive-x ray, analytically extended to infinity."""
    r = point-origin; radius = np.linalg.norm(r)
    transverse = r[1]*r[1]+r[2]*r[2]
    if transverse < 1e-28:
        return np.zeros(3)
    return np.cross(EX, r)*(radius+r[0])/(4*np.pi*radius*transverse)


def induced(point, starts, ends, gamma, exclude=None):
    velocity = np.zeros(3)
    for j, (a, b, strength) in enumerate(zip(starts, ends, gamma)):
        bound = np.zeros(3) if j == exclude else segment_velocity(point, a, b)
        velocity += strength*(bound+ray_velocity(point, b)-ray_velocity(point, a))
    return velocity


def audit(snapshot):
    s = snapshot
    assert s['converged'] and s['residual'] <= 1e-8
    assert s['mach'] == 0 and not s['engines'] and not s['body_shoulders']
    frame = s['frame']; omega = np.asarray(frame['rates_body'])
    angular = np.asarray(frame['angular_acceleration_body'])
    np.testing.assert_allclose(frame['velocity_origin_body'], -15*EX, atol=1e-12, rtol=0)
    np.testing.assert_array_equal(frame['acceleration_reference_body'], np.zeros(3))
    nodes = {(r['beam'], r['t']): r for r in s['nodes']}
    starts, ends, sections = [], [], []
    for strip, element in zip(s['strips'], s['elements']):
        beam = strip['beam']; assert beam == element['beam'] and strip['lifting']
        a, b = [nodes[(beam, element[key])] for key in ('t0', 't1')]
        qa, qb = np.asarray(a['rotation']), np.asarray(b['rotation'])
        np.testing.assert_allclose(qa, qb, atol=1e-8, rtol=0)
        c, span, normal = qa.T
        across = np.linalg.norm(np.cross(EX, span))
        offset = -.25*CHORD/across*EX
        ra, rb = np.asarray(a['position']), np.asarray(b['position'])
        length = float(np.linalg.norm(rb-ra))
        assert abs(length-strip['length']) < 1e-10
        starts.append(ra+offset); ends.append(rb+offset)
        fraction = (strip['t']-a['t'])/(b['t']-a['t'])
        assert 0 < fraction < 1
        rm = ra+fraction*(rb-ra)
        np.testing.assert_allclose(rm, strip['position'], atol=1e-9, rtol=0)
        fields = [(1-fraction)*np.asarray(s[key][a['index']])+fraction*np.asarray(s[key][b['index']])
                  for key in ('local_velocity', 'local_rates', 'local_acceleration', 'local_rate_derivative')]
        slope = 5.7897 if beam == 1 else 6.28
        control = np.copysign(.015*21/slope, strip['t']) if beam == 1 else 0.
        cp_normal = np.sin(control)*c+np.cos(control)*normal
        hv = rm+offset
        cp = hv+slope*CHORD/(4*np.pi*across)*EX
        np.testing.assert_allclose(hv, strip['velocity_position'], atol=1e-9, rtol=0)
        sections.append((strip, rm, c, span, normal, hv, cp, cp_normal, slope, fields, (ra+rb)/2, length))
    gamma = np.array([r['circulation'] for r in s['strips']])
    errors = dict(velocity=0., cl=0., circulation_equation=0., force=0., moment=0.,
                  apparent_force=0., apparent_moment=0., rate_force=0.)
    totals = {key: np.zeros(3) for key in ('force', 'moment', 'lift_moment', 'rate_moment', 'profile_moment', 'apparent_moment')}
    peak_cl = 0.; stall_count = 0
    for j, (strip, rm, c, span, normal, hv, cp, cp_normal, slope, fields, midpoint, length) in enumerate(sections):
        u, w, acceleration, wd = fields
        def velocity(point, exclude=None):
            return 15*EX-np.cross(omega, point)-u-np.cross(w, point-rm)+induced(point, starts, ends, gamma, exclude)
        v = velocity(hv, j); vc = velocity(cp); va = velocity(rm, j)
        perpendicular = v-(v@span)*span
        speed = np.linalg.norm(perpendicular)
        cl = 2*gamma[j]/(CHORD*speed)
        limit = 1.15 if strip['beam'] == 1 else 1.4
        leakage = .05*(np.logaddexp(0., (cl-limit)/.05)-np.logaddexp(0., (-limit-cl)/.05))
        dot_gamma = strip['circulation_rate']
        tangent = vc@cp_normal-2/np.pi*dot_gamma/speed
        equation = (tangent-speed*40/slope*leakage)/15
        fsteady = RHO*gamma[j]*np.cross(v, span)*length
        frate = RHO*dot_gamma*CHORD/speed*np.cross(v, span)*length
        fprofile = 2*RHO*CHORD*length*tangent**2*perpendicular/speed
        absolute_a = acceleration+np.cross(angular, rm)+np.cross(omega, np.cross(omega, rm))+2*np.cross(omega, u)
        absolute_w = omega+w; absolute_wd = angular+wd+np.cross(omega, w)
        rate_term = np.cross(va, absolute_w)@normal
        added_mass = RHO*np.pi*CHORD**2*length/4
        fam = added_mass*(rate_term-absolute_a@normal)*normal
        mam = -added_mass*(CHORD/4*rate_term+CHORD**2/32*(absolute_wd@span))*span
        arm = -.25*CHORD*c
        force = fsteady+frate+fprofile+fam
        moment = np.cross(arm, fsteady+frate)+np.cross(midpoint-rm, fprofile)+mam
        differences = dict(velocity=v-strip['relative_velocity'], cl=cl-strip['cl'],
            circulation_equation=equation, force=force-strip['force'], moment=moment-strip['moment'],
            apparent_force=fam-strip['apparent_force'], apparent_moment=mam-strip['apparent_moment'],
            rate_force=frate-strip['circulation_rate_force'])
        for key, value in differences.items():errors[key] = max(errors[key], float(np.max(np.abs(value))))
        totals['force'] += force; totals['moment'] += np.cross(rm, force)+moment
        totals['lift_moment'] += np.cross(rm+arm, fsteady)
        totals['rate_moment'] += np.cross(rm+arm, frate)
        totals['profile_moment'] += np.cross(midpoint, fprofile)
        totals['apparent_moment'] += np.cross(rm, fam)+mam
        peak_cl = max(peak_cl, abs(cl)); stall_count += abs(cl) > limit
    gates = {key: dict(error=value, tolerance=1e-8 if key == 'circulation_equation' else 2e-8,
                      passed=value <= (1e-8 if key == 'circulation_equation' else 2e-8)) for key, value in errors.items()}
    np.testing.assert_allclose(totals['force'], s['force'], atol=2e-8, rtol=0)
    np.testing.assert_allclose(totals['moment'], s['moment'], atol=2e-8, rtol=0)
    return dict(time=s['time'], gates=gates, all_passed=all(g['passed'] for g in gates.values()),
        strips=len(sections), peak_absolute_cl=peak_cl, stalled_strips=int(stall_count),
        totals={key: value.tolist() for key, value in totals.items()})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', type=Path, nargs='+', required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); source = pin(a.source); assert source['sha256'] == SOURCE_SHA
    rows = []; inputs = []
    for path in a.results:
        result = json.loads(path.read_text()); inputs.append(pin(path))
        rows.extend(audit(s) for s in result['snapshots'] if s['time'] > 0)
    assert rows
    output = dict(status='AERODYNAMIC_AUDIT_COMPLETE', source=source, inputs=inputs, helper=pin(__file__),
        snapshots=len(rows), unique_times=len({round(r['time'], 12) for r in rows}),
        all_passed=all(r['all_passed'] for r in rows), rows=rows,
        qualifications=['Conditioned on saved geometry, kinematics, Gamma and Gamma-dot.',
            'Literal constant-section zero-Mach/no-ground/no-engine model only.',
            'Retains the existing nodal horseshoe construction and own-bound exclusions; their off-filament historical interpretation remains qualified.',
            'Does not authenticate native initial state, historical flags, time accuracy or mesh convergence.'])
    a.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in output.items() if k not in ('rows', 'inputs')}))
    if not output['all_passed']:raise SystemExit(1)


if __name__ == '__main__':main()
