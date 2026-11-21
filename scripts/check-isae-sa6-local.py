"""Independent stdlib reconstruction of retained SA6 local fields; no physics imports."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import itertools
import json
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/validation'
D = ROOT/'docs/validation'
PARTS = ('circulatory', 'Cdf', 'Cdp', 'stall')
REGIONS = ('controlled_right', 'uncontrolled_right', 'left', 'uncontrolled_rest', 'whole_wing')
counts, failures, maxima, pins = Counter(), [], {}, {}


def pin(path):
    path = Path(path); data = path.read_bytes()
    p = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    pins[str(path)] = p
    return p


def read(path):
    pin(path)
    return json.loads(Path(path).read_text())


def check(group, name, ok, **detail):
    counts[group] += 1
    if not ok:
        failures.append(dict(group=group, name=name, **detail))


def near(group, name, a, b, tolerance):
    if isinstance(a, (list, tuple)):
        errors = [abs(x-y) for x, y in zip(a, b, strict=True)]
        error = max(errors, default=0.)
    else:
        error = abs(a-b)
    maxima[group] = max(maxima.get(group, 0.), error)
    check(group, name, math.isfinite(error) and error <= tolerance,
          absolute_error=error, tolerance=tolerance)


def add(*vectors):
    return [math.fsum(v[i] for v in vectors) for i in range(3)]


def sub(a, b):
    return [x-y for x, y in zip(a, b, strict=True)]


def mul(a, v):
    return [a*x for x in v]


def dot(a, b):
    return math.fsum(x*y for x, y in zip(a, b, strict=True))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def norm(v):
    return math.sqrt(dot(v, v))


def softplus(x):
    return max(x, 0.)+math.log1p(math.exp(-abs(x)))


def angle(v, normal, chord):
    return math.degrees(math.atan2(dot(v, normal), dot(v, chord)))


def coeff(force, moment, qs, chord, span, alpha):
    return dict(Cl=-moment[0]/(qs*span), Cn=-moment[2]/(qs*span),
                Cm=moment[1]/(qs*chord),
                CL=(-math.sin(alpha)*force[0]+math.cos(alpha)*force[2])/qs,
                CD=(math.cos(alpha)*force[0]+math.sin(alpha)*force[2])/qs)


def sum3(vectors):
    vectors = list(vectors)
    return [math.fsum(v[i] for v in vectors) for i in range(3)]


def difference(a, b):
    return {k: a[k]-b[k] for k in a}


r = read(D/'isae-sa6-local.json')
old = read(D/'isae-sa6-single-aileron.json')
plan = r['plan']
identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
check('identity', 'report', identity == r['identity'])
cache = ROOT/'.reference/isae-sa6-local'/identity
check('identity', 'cache plan', read(cache/'plan.json') == plan)
for name, digest in plan['source_sha256'].items():
    check('source_hash', name, pin(ROOT/name)['sha256'] == digest)
check('counts', 'production modules', sum(p.startswith('openswing/') for p in plan['source_sha256']) == 110)
check('counts', 'retained states', len(r['states']) == 21)
check('scope', 'not full validation', r['full_suite_validated'] is False)
check('scope', 'original residual gate', plan['residual_limit'] == 1e-8)
check('scope', 'original coefficient gate', plan['baseline_coefficient_limit'] == 2e-10)
check('scope', 'original field gate', plan['captured_field_limit'] == 2e-12)
baseline = {(x['specification']['body_pitch_deg'], x['specification']['right_deflection_deg']): x['result']
            for x in old['states'] if x['specification']['case'] == '20b_35c_literal'
            and x['specification']['panels'] == 160}
results, by_state = [], {}
expected_keys = set(itertools.product((0, 8, 12), (0, 4, -4, 20, -20, 44, -44)))
observed_keys = {(x['specification']['body_pitch_deg'], x['specification']['right_deflection_deg']) for x in r['states']}
check('counts', 'exact state set', observed_keys == expected_keys)

for state in r['states']:
    spec, raw, native = state['specification'], state['raw'], state['result']
    pitch, delta = spec['body_pitch_deg'], spec['right_deflection_deg']
    label = f'{pitch}/{delta}'
    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    check('cache', label, read(cache/(key+'.json')) == state)
    p, mat = raw['parameters'], raw['material']
    rho, speed = raw['density'], raw['speed']
    area, chord_ref, span = raw['reference'][0]
    qs, alpha = .5*rho*speed*speed*area, math.radians(pitch)
    wind = [math.cos(alpha), 0., math.sin(alpha)]
    sound = native['atmosphere']['sound_speed']
    near('density', label, rho, native['atmosphere']['density'], 0.)
    near('F1', label, raw['F1'], delta, 0.)
    near('saved_residual', label, native['residual'], 0., 1e-8)
    near('saved_capture_field', label, state['captured_field_error'], 0., 2e-12)
    for k in ('Cl', 'Cn', 'CL', 'CD', 'Cm'):
        near('baseline_coefficients', label+'/'+k, native[k], baseline[pitch, delta][k], 2e-10)
    for k in ('point_forces',):
        for i, v in enumerate(native[k]):
            near('excluded_loads', label+f'/{k}/{i}', v, [0., 0., 0.], 0.)
    near('excluded_loads', label+'/engine-force', native['engine_force'], [0., 0., 0.], 0.)
    near('excluded_loads', label+'/body-force', native['body_force'], [0., 0., 0.], 0.)
    strips = []
    check('counts', label+'/164 strips', len(native['strips']) == len(raw['circulation']) == 164)
    for i, target in enumerate(native['strips']):
        tag = label+'/'+str(i)
        c, s, n, rm = (p[k][i] for k in ('c', 's', 'section_normal', 'rm'))
        chord, ds, slope = mat['chord'][i], p['ds'][i], mat['dCLda'][i]
        gamma, f1 = raw['circulation'][i], raw['F1']
        twist = math.radians(mat['twist'][i])
        near('physical_frame', tag+'/c', c, [math.cos(twist), 0., -math.sin(twist)], 2e-14)
        near('physical_frame', tag+'/s', s, [0., 1., 0.], 2e-14)
        near('physical_frame', tag+'/n', n, [math.sin(twist), 0., math.cos(twist)], 2e-14)
        a = math.radians(mat['alpha'][i])+f1*mat['dCLdF1'][i]/slope
        normal = add(mul(math.sin(a), c), mul(math.cos(a), n))
        zero_chord = sub(mul(math.cos(a), c), mul(math.sin(a), n))
        near('control_normal', tag, normal, p['normal'][i], 2e-14)
        vp_cp, vhv = raw['cp']['velocity'][i], raw['hv']['velocity'][i]
        for name in ('cp', 'hv'):
            near('field_free', tag+'/'+name, raw[name]['free'][i], mul(speed, wind), 2e-12)
            near('field_sum', tag+'/'+name, raw[name]['velocity'][i], add(raw[name]['free'][i], raw[name]['induced'][i]), 2e-12)
        across = norm(cross(wind, s))
        expected_hv = add(rm, mul((.25-mat['Xax'][i])*chord/across, wind))
        expected_cp = add(expected_hv, mul(slope/(4*math.pi)*chord/across, wind))
        near('geometry', tag+'/hv', p['hv'][i], expected_hv, 2e-13)
        near('geometry', tag+'/cp', p['cp'][i], expected_cp, 2e-13)
        near('native_velocity', tag, target['relative_velocity'], vhv, 2e-12)
        near('native_velocity_position', tag, target['velocity_position'], p['hv'][i], 2e-13)
        near('native_axis_position', tag, target['position'], rm, 2e-13)
        vp = sub(vhv, mul(dot(vhv, s), s))
        u, v = norm(vp), norm(vhv)
        check('speed_floor', tag, u > speed*1e-12)
        T = dot(vp_cp, normal)
        cl = 2*gamma/(chord*u)
        near('normal_speed', tag, target['normal_speed'], u, 2e-12)
        near('native_cl', tag, target['cl'], cl, 2e-13)
        near('direct_tangency', tag, raw['tangency'][i], T, 2e-12)
        lo, hi, width = mat['CLmin'][i], mat['CLmax'][i], raw['stall_width']
        fstall = width*(softplus((cl-hi)/width)-softplus((lo-cl)/width))
        leakage = u/slope*raw['stall_factor']*fstall
        local_residual = (T-leakage)/speed
        near('local_residual', tag, local_residual, native['circulation_local_residual'][i], 2e-12)
        near('pointwise_residual', tag, native['circulation_residual'][i], native['circulation_local_residual'][i], 0.)
        near('tangency_leakage_identity', tag, T-leakage, speed*native['circulation_local_residual'][i], 2e-12)
        check('stall_flag', tag, target['stalled'] == (cl > hi or cl < lo))
        cdp = mat['Cdp'][i]+f1*mat['dCDdF1'][i]
        cm = (mat['Cm'][i]+f1*mat['dCMdF1'][i])/math.sqrt(1-(u/sound)**2)
        near('native_cm', tag, target['cm'], cm, 2e-13)
        for k in ('circulation_rate_force', 'apparent_force', 'apparent_moment'):
            near('excluded_strip_loads', tag+'/'+k, target[k], [0., 0., 0.], 0.)
        near('excluded_strip_loads', tag+'/gamma-dot', target['circulation_rate'], 0., 0.)
        forces = dict(circulatory=mul(rho*gamma*ds, cross(vhv, s)),
                      Cdf=mul(.5*rho*v*chord*mat['Cdf'][i]*ds, vhv),
                      Cdp=mul(.5*rho*u*chord*cdp*ds, vp),
                      stall=mul(2*rho*T*T*chord*ds/u, vp))
        section_couple = add(cross(mul((.25-mat['Xax'][i])*chord, c), forces['circulatory']),
                            mul(.5*rho*u*u*chord*chord*cm*ds, s))
        near('section_moment_normalized', tag, mul(1/(qs*span), section_couple), mul(1/(qs*span), target['moment']), 2e-10)
        total_force = sum3(forces.values())
        total_moment = add(cross(sub(rm, raw['reference'][1]), total_force), section_couple)
        near('strip_force_normalized', tag, mul(1/qs, total_force), mul(1/qs, target['force']), 2e-10)
        moments = {part: cross(sub(rm, raw['reference'][1]), force) for part, force in forces.items()}
        moments['circulatory'] = add(moments['circulatory'], section_couple)
        region = 'left' if rm[1] < 0 else 'controlled_right' if mat['dCLdF1'][i] != 0 else 'uncontrolled_right'
        check('region_partition', tag+'/midpoint-not-center', rm[1] != 0)
        check('region_partition', tag+'/bound-segment-no-cross-center', not (p['a'][i][1] < 0 < p['b'][i][1]))
        if region == 'left':
            near('left_control_zero', tag, mat['dCLdF1'][i], 0., 0.)
        part_values = {part: dict(force=forces[part], moment=moments[part],
                       coefficients=coeff(forces[part], moments[part], qs, chord_ref, span, alpha)) for part in PARTS}
        angles = dict(hv_physical_deg=angle(vhv, n, c), hv_effective_deg=angle(vhv, normal, zero_chord),
                      cp_physical_deg=angle(vp_cp, n, c), cp_effective_deg=angle(vp_cp, normal, zero_chord),
                      freestream_physical_deg=angle(wind, n, c), freestream_effective_deg=angle(wind, normal, zero_chord),
                      aerodynamic_offset_deg=math.degrees(a))
        strips.append(dict(index=i, t=p['t'][i], y=rm[1], ds=ds, region=region,
                           circulation=gamma, cl=cl, CLmin=lo, CLmax=hi, normal_speed=u,
                           tangency=T, leakage=leakage, local_residual=local_residual,
                           Cdp_net=cdp, Cd_stall=4*(T/u)**2,
                           stalled_high=cl>hi, stalled_low=cl<lo, angles=angles,
                           components=part_values, total_force=total_force, total_moment=total_moment))
    global_force, global_moment = sum3(x['total_force'] for x in strips), sum3(x['total_moment'] for x in strips)
    near('global_force_normalized', label, mul(1/qs, global_force), mul(1/qs, native['force']), 2e-10)
    near('global_moment_normalized', label, mul(1/(qs*span), global_moment), mul(1/(qs*span), native['moment']), 2e-10)
    reconstructed_coeff = coeff(global_force, global_moment, qs, chord_ref, span, alpha)
    for k, value in reconstructed_coeff.items():
        near('global_coefficients', label+'/'+k, value, native[k], 2e-10)
    regions = {}
    for region in REGIONS:
        rows = [x for x in strips if region == 'whole_wing' or x['region'] == region
                or (region == 'uncontrolled_rest' and x['region'] != 'controlled_right')]
        check('region_partition', label+'/'+region+'/nonempty', bool(rows))
        components = {}
        for part in PARTS:
            force, moment = sum3(x['components'][part]['force'] for x in rows), sum3(x['components'][part]['moment'] for x in rows)
            components[part] = dict(force=force, moment=moment, coefficients=coeff(force, moment, qs, chord_ref, span, alpha))
        force, moment = sum3(x['force'] for x in components.values()), sum3(x['moment'] for x in components.values())
        def summary(values):
            values = list(values)
            return dict(minimum=min(values), maximum=max(values), length_weighted_mean=math.fsum(v*x['ds'] for v, x in zip(values, rows, strict=True))/math.fsum(x['ds'] for x in rows))
        regions[region] = dict(strips=len(rows), length=math.fsum(x['ds'] for x in rows),
            stalled_high=sum(x['stalled_high'] for x in rows), stalled_low=sum(x['stalled_low'] for x in rows),
            cl=summary(x['cl'] for x in rows), Cd_stall=summary(x['Cd_stall'] for x in rows),
            tangency=summary(x['tangency'] for x in rows), normal_speed=summary(x['normal_speed'] for x in rows),
            angles={k: summary(x['angles'][k] for x in rows) for k in strips[0]['angles']},
            components=components, total=dict(force=force, moment=moment, coefficients=coeff(force, moment, qs, chord_ref, span, alpha)))
    row = dict(specification=spec, reconstructed_coefficients=reconstructed_coeff,
               regions=regions, strips=strips)
    results.append(row); by_state[pitch, delta] = row

for row in results:
    pitch, delta = row['specification']['body_pitch_deg'], row['specification']['right_deflection_deg']
    neutral = by_state[pitch, 0]
    for strip, zero in zip(row['strips'], neutral['strips'], strict=True):
        check('neutral_grid', f'{pitch}/{delta}/{strip["index"]}',
              all(strip[k] == zero[k] for k in ('index', 't', 'y', 'ds', 'region')))
        for part in PARTS:
            actual, base = strip['components'][part], zero['components'][part]
            actual['neutral_subtracted'] = dict(force=sub(actual['force'], base['force']),
                  moment=sub(actual['moment'], base['moment']), coefficients=difference(actual['coefficients'], base['coefficients']))
    for region in REGIONS:
        actual, base = row['regions'][region], neutral['regions'][region]
        for part in (*PARTS, 'total'):
            a = actual['total'] if part == 'total' else actual['components'][part]
            b = base['total'] if part == 'total' else base['components'][part]
            a['neutral_subtracted'] = dict(force=sub(a['force'], b['force']), moment=sub(a['moment'], b['moment']),
                                           coefficients=difference(a['coefficients'], b['coefficients']))
    for field in ('Cl', 'Cn', 'CL', 'CD', 'Cm'):
        total = row['regions']['whole_wing']['total']['neutral_subtracted']['coefficients'][field]
        parts = [row['regions'][region]['total']['neutral_subtracted']['coefficients'][field]
                 for region in ('controlled_right', 'uncontrolled_right', 'left')]
        near('region_coefficient_sum', f'{pitch}/{delta}/{field}', math.fsum(parts), total, 2e-10)

combined = []
previous_pairs = {(x['body_pitch_deg'], x['deflection_deg']): x for x in old['combined']
                  if x['case'] == '20b_35c_literal' and x['panels'] == 160}
for pitch, delta in itertools.product((0, 8, 12), (4, 20, 44)):
    up, down = by_state[pitch, delta], by_state[pitch, -delta]
    regions = {}
    for region in REGIONS:
        components = {}
        for part in (*PARTS, 'total'):
            a = up['regions'][region]['total'] if part == 'total' else up['regions'][region]['components'][part]
            b = down['regions'][region]['total'] if part == 'total' else down['regions'][region]['components'][part]
            components[part] = dict(force=sub(a['force'], b['force']), moment=sub(a['moment'], b['moment']),
                                    coefficients=difference(a['coefficients'], b['coefficients']))
        regions[region] = components
    for field in ('Cl', 'Cn'):
        near('combined_baseline', f'{pitch}/{delta}/{field}', regions['whole_wing']['total']['coefficients'][field],
             previous_pairs[pitch, delta]['matched'][field], 2e-10)
        near('combined_component_sum', f'{pitch}/{delta}/{field}',
             math.fsum(regions['whole_wing'][part]['coefficients'][field] for part in PARTS),
             regions['whole_wing']['total']['coefficients'][field], 2e-10)
        for part in PARTS:
            near('combined_region_sum', f'{pitch}/{delta}/{part}/{field}',
                 math.fsum(regions[region][part]['coefficients'][field] for region in ('controlled_right', 'uncontrolled_right', 'left')),
                 regions['whole_wing'][part]['coefficients'][field], 2e-10)
        prior_profile = previous_pairs[pitch, delta]['combined_moment_contributions']['profile'][field]
        near('prior_profile_split', f'{pitch}/{delta}/{field}',
             math.fsum(regions['whole_wing'][part]['coefficients'][field] for part in ('Cdf', 'Cdp', 'stall')), prior_profile, 2e-10)
    combined.append(dict(body_pitch_deg=pitch, deflection_deg=delta, regions=regions))

OUT.mkdir(parents=True, exist_ok=True)
data = dict(status='INDEPENDENT_SAVED_FIELD_DECOMPOSITION', source_identity=identity,
            definitions=dict(region='controlled_right has nonzero retained dCLdF1; uncontrolled_right is the remaining positive-y region; left is all negative y; uncontrolled_rest is left plus uncontrolled_right.',
                physical_angle='atan2(V dot physical_n, V dot physical_c), degrees',
                effective_angle='atan2(V dot ncp, V dot ccp), where ccp=cos(alpha_A)c-sin(alpha_A)n; degrees',
                flow_sampling='hv is the force-point velocity, cp is the independent tangency-point velocity; their angles are separate.',
                Cd_stall='4*(T/normal_speed_hv)^2; local coefficient relative to 0.5*rho*normal_speed_hv^2*chord*ds.',
                neutral_subtracted='Each component at the same strip/region minus its identical-mesh neutral capture at the same pitch.',
                combined='Independent isolated-right-up result minus isolated-right-down result, separately for each region/component.'),
            states=results, combined=combined)
(OUT/'isae-sa6-local-decomposition.json').write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
with (OUT/'isae-sa6-local-strips.csv').open('w', newline='') as stream:
    fields = ['pitch', 'right_deflection', 'index', 't', 'y', 'ds', 'region', 'cl', 'CLmin', 'CLmax',
              'normal_speed', 'tangency', 'leakage', 'Cd_stall', 'stalled_high', 'stalled_low',
              *results[0]['strips'][0]['angles'],
              *(part+'_'+field for part in PARTS for field in ('Cl', 'Cn', 'delta_Cl', 'delta_Cn'))]
    writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
    for row in results:
        for strip in row['strips']:
            flat = {k: strip[k] for k in fields[2:16]}
            flat.update(pitch=row['specification']['body_pitch_deg'], right_deflection=row['specification']['right_deflection_deg'])
            flat.update(strip['angles'])
            for part in PARTS:
                for field in ('Cl', 'Cn'):
                    flat[part+'_'+field] = strip['components'][part]['coefficients'][field]
                    flat[part+'_delta_'+field] = strip['components'][part]['neutral_subtracted']['coefficients'][field]
            writer.writerow(flat)
pin(Path(__file__))
pin(OUT/'isae-sa6-local-decomposition.json'); pin(OUT/'isae-sa6-local-strips.csv')
audit = dict(status='PASS' if not failures else 'FAIL', checks=sum(counts.values()),
             passed=sum(counts.values())-len(failures), failed=failures,
             checks_by_category=dict(counts), maximum_absolute_errors=maxima,
             source_identity=identity, input_and_artifact_pins=pins,
             counts=dict(retained_states=21, strips_per_state=164, retained_strip_states=3444,
                         reconstructed_force_components=13776, combined_states=9,
                         capture_aerodynamic_calls_including_failed_attempt=22,
                         successful_capture_states=21, extra_capture_vortex_products=42),
             operations=dict(production_imports=0, aircraft_evaluations=0, solves=0, builds=0),
             scope=['Expected loads, moments, normals, leakage and reductions use only stdlib arithmetic and saved primitive fields/material values.',
                    'Captured native CP/HV induced velocities are supplied inputs; this does not independently validate vortex influence operators.',
                    'No coefficients, model constants or acceptance gates were fitted to experimental observations.',
                    'Flow angles are diagnostics of the published section model; agreement with the model equations is not experimental validation.'])
(OUT/'isae-sa6-local-audit.json').write_text(json.dumps(audit, indent=2, allow_nan=False)+'\n')
print(json.dumps({k:audit[k] for k in ('status','checks','passed','failed','maximum_absolute_errors','counts')},indent=2))
raise SystemExit(bool(failures))
