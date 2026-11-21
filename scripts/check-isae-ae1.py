"""Independent stdlib-only audit of saved AE-1 pilot data and reductions.

No OpenSwing/NumPy imports, model construction, residual evaluation or solve.
Reconstructs poses from raw state and observables from retained physical nodes.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'docs/validation'


def pin(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def norm(v):
    return math.sqrt(sum(x*x for x in v))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def rotation(v):
    angle = norm(v)
    if angle == 0:
        return [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]
    x, y, z = [a/angle for a in v]
    axis = [x, y, z]
    skew = [[0., -z, y], [z, 0., -x], [-y, x, 0.]]
    c, s = math.cos(angle), math.sin(angle)
    return [[(c if i == j else 0.)+(1-c)*axis[i]*axis[j]+s*skew[i][j]
             for j in range(3)] for i in range(3)]


def observable(node):
    r, q = node['position'], node['rotation']
    le = [r[i]-.0441*q[i][0] for i in range(3)]
    te = [r[i]+.0559*q[i][0] for i in range(3)]
    return dict(leading_edge_m=le, trailing_edge_m=te,
                midchord_m=[(a+b)/2 for a, b in zip(le, te)],
                projected_twist_deg=math.degrees(math.atan2(le[2]-te[2], te[0]-le[0])))


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []
        self.errors = {}

    def check(self, name, condition):
        self.count += 1
        if not condition:
            self.failures.append(name)

    def equal(self, name, actual, expected, *, atol=3e-13, rtol=3e-12, group=None):
        if isinstance(expected, dict):
            self.check(name+'.keys', set(actual) == set(expected))
            for k, value in expected.items():
                if k in actual:
                    self.equal(name+'.'+str(k), actual[k], value, atol=atol, rtol=rtol, group=group)
        elif isinstance(expected, (list, tuple)):
            self.check(name+'.length', len(actual) == len(expected))
            for i, (a, e) in enumerate(zip(actual, expected)):
                self.equal(name+'.'+str(i), a, e, atol=atol, rtol=rtol, group=group)
        elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
            error = abs(actual-expected)
            if group:
                self.errors[group] = max(error, self.errors.get(group, 0.))
            self.check(name, math.isfinite(actual) and error <= atol+rtol*abs(expected))
        else:
            self.check(name, actual == expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, help='Also compare embedded states to this original pilot directory.')
    parser.add_argument('--output', type=Path, default=DEST/'isae-ae1-pilot-audit.json')
    args = parser.parse_args()
    path = DEST/'isae-ae1-pilot.json'
    report = json.loads(path.read_text())
    initial_pins = [pin(path), pin(DEST/'isae-ae1-pilot.csv'), pin(Path(__file__))]
    audit = Audit()
    plan, execution, states = report['plan'], report['execution'], report['states']
    unhashed = {k: v for k, v in plan.items() if k != 'identity'}
    audit.check('plan.identity', hashlib.sha256(json.dumps(unhashed, sort_keys=True).encode()).hexdigest() == plan['identity'])
    audit.check('execution.completed', execution['status'] == 'completed' and execution['completed'] == execution['attempted'] == 8)
    audit.check('state.count', len(states) == 8)
    for name, digest in plan['source_sha256'].items():
        audit.check('pin.'+name, pin(ROOT/name)['sha256'] == digest)
    audit.check('reducer.pin', report['reducer_sha256'] == pin(ROOT/'scripts/summarize-isae-ae1.py')['sha256'])
    if args.run:
        audit.equal('raw.plan', json.loads((args.run/'plan.json').read_text()), plan, atol=0, rtol=0)
        audit.equal('raw.execution', json.loads((args.run/'execution.json').read_text()), execution, atol=0, rtol=0)
    reflection = [1., -1., 1.]
    observations, diagnostics = {}, []
    for index, state in enumerate(states):
        name = f'state{index}'
        if args.run:
            raw_path = args.run/execution['outputs'][index]
            audit.equal(name+'.raw_copy', state, json.loads(raw_path.read_text()), atol=0, rtol=0)
            initial_pins.append(pin(raw_path))
        audit.check(name+'.identity', state['identity'] == plan['identity'])
        audit.check(name+'.computed', state['status'] == 'computed')
        audit.equal(name+'.specification', state['specification'], plan['specifications'][index], atol=0, rtol=0)
        audit.check(name+'.source_pin', hashlib.sha256(state['source'].encode()).hexdigest() == state['source_sha256'])
        specification, result = state['specification'], state['result']
        nodes = result['nodes']
        audit.check(name+'.nodes_count', len(nodes) == state['counts']['nodes'] == 2*specification['intervals_per_half']+1)
        audit.check(name+'.elements_count', len(result['elements']) == state['counts']['elements'] == len(nodes)-1)
        length = norm([max(n['jig_position'][i] for n in nodes)-min(n['jig_position'][i] for n in nodes) for i in range(3)])
        raw = state['state']
        mirror_position = mirror_rotation = 0.
        for i, node in enumerate(nodes):
            p = [node['jig_position'][j]+length*raw[6*i+j] for j in range(3)]
            q = rotation(raw[6*i+3:6*i+6])
            audit.equal(name+f'.raw_position{i}', node['position'], p, group='raw_position_m')
            audit.equal(name+f'.raw_rotation{i}', node['rotation'], q, group='raw_rotation')
            partner = nodes[-1-i]
            for j in range(3):
                mirror_position = max(mirror_position, abs(partner['position'][j]-reflection[j]*node['position'][j]))
                for k in range(3):
                    mirror_rotation = max(mirror_rotation, abs(partner['rotation'][j][k]-reflection[j]*reflection[k]*node['rotation'][j][k]))
        audit.equal(name+'.mirror_position', state['checks']['mirror_position_error_m'], mirror_position, group='saved_mirror_error')
        audit.equal(name+'.mirror_rotation', state['checks']['mirror_rotation_error'], mirror_rotation, group='saved_mirror_error')
        audit.check(name+'.mirror_gate', mirror_position/length <= 1e-8 and mirror_rotation <= 1e-8)
        root = next(n for n in nodes if n['t'] == 0.)
        audit.equal(name+'.root_position', root['position'], [0., 0., 0.], atol=1e-12, rtol=0)
        audit.equal(name+'.root_rotation', root['rotation'], rotation([0., 0., 0.]), atol=1e-12, rtol=0)
        audit.check(name+'.fresh_residual_gate', state['checks']['fresh_residual'] <= plan['gates']['residual'])
        f, m = result['applied_force'], result['applied_moment']
        sf, sm = result['support_force'], result['support_moment']
        force_balance, moment_balance = [[a+b for a, b in zip(x, y)] for x, y in ((f, sf), (m, sm))]
        audit.equal(name+'.force_balance', result['force_balance'], force_balance, group='balance_report')
        audit.equal(name+'.moment_balance', result['moment_balance'], moment_balance, group='balance_report')
        force_scale = max(1., norm(f), norm(sf))
        moment_scale = max(1., force_scale*length, norm(sm))
        for key, value in [('force_balance_scaled', max(map(abs, force_balance))/force_scale),
                           ('moment_balance_scaled', max(map(abs, moment_balance))/moment_scale)]:
            audit.equal(name+'.'+key, state['checks'][key], value)
            audit.check(name+'.'+key+'.gate', value <= 1e-7)
        audit.equal(name+'.gravity', result['gravity_body'], [0., 0., 0.], atol=0, rtol=0)
        positive_tip = max(nodes, key=lambda n:n['jig_position'][1])
        own = observable(positive_tip)
        audit.equal(name+'.observable', state['observable'], own, group='observable')
        key = (specification['refinement'], specification['alpha_deg'], specification['speed_m_s'])
        observations[key] = own
        strips = result.get('strips', [])
        if specification['speed_m_s'] > 0:
            audit.check(name+'.no_images', result['ground_plane']['flag'] == 0)
            audit.check(name+'.strips_count', len(strips) == 2*specification['intervals_per_half'])
            strip_force = [sum(s['force'][j] for s in strips) for j in range(3)]
            strip_moments = [[a+b for a,b in zip(cross(s['position'], s['force']), s['moment'])] for s in strips]
            strip_moment = [sum(s[j] for s in strip_moments) for j in range(3)]
            audit.equal(name+'.strip_force_sum', result['force'], strip_force, atol=2e-11, group='force_sum')
            audit.equal(name+'.strip_moment_sum', result['moment'], strip_moment, atol=2e-11, group='moment_sum')
            audit.equal(name+'.applied_equals_aero_force', f, strip_force, atol=2e-11, group='force_sum')
            audit.equal(name+'.applied_equals_aero_moment', m, strip_moment, atol=2e-11, group='moment_sum')
            for j, strip in enumerate(strips[:len(strips)//2]):
                partner = strips[-1-j]
                audit.equal(name+f'.gamma_mirror{j}', strip['circulation'], partner['circulation'], atol=3e-11, group='gamma_mirror')
                audit.equal(name+f'.strip_force_mirror{j}', strip['force'], [reflection[k]*partner['force'][k] for k in range(3)], atol=3e-11, group='force_mirror')
                audit.equal(name+f'.strip_moment_mirror{j}', strip['moment'], [-reflection[k]*partner['moment'][k] for k in range(3)], atol=3e-11, group='moment_mirror')
        else:
            audit.equal(name+'.vacuum_force', f, [0., 0., 0.], atol=0, rtol=0)
            audit.equal(name+'.vacuum_moment', m, [0., 0., 0.], atol=0, rtol=0)
            audit.equal(name+'.vacuum_state', raw, [0.]*len(raw), atol=0, rtol=0)
        diagnostics.append(dict(specification=specification, max_section_cl=max([s['cl'] for s in strips], default=0.),
                                stalled_sections=sum(s['stalled'] for s in strips), mirror_position_m=mirror_position,
                                mirror_rotation=mirror_rotation, fresh_residual=state['checks']['fresh_residual']))
    measured = {}
    for entry in report['measurements']:
        source = ROOT/entry['source_path']
        audit.check('measurement.pin.'+source.name, pin(source)['sha256'] == entry['sha256'])
        initial_pins.append(pin(source))
        expected = []
        for line in source.read_text().splitlines():
            if line.strip():
                speed, value = map(float, line.split())
                expected.append([speed, value if math.isfinite(value) else None])
                if math.isfinite(value):
                    measured[(entry['alpha_deg'], speed, entry['quantity'])] = value
        audit.equal('measurement.values.'+source.name, entry['values'], expected, atol=0, rtol=0)
    modeled = {}
    audit.check('primary_controls.count', len(report['primary_beam_controls']) == 4)
    for entry in report['primary_beam_controls']:
        source = ROOT/entry['source_path']
        audit.check('primary_control.pin.'+source.name, pin(source)['sha256'] == entry['sha256'])
        initial_pins.append(pin(source))
        expected = [list(map(float, line.split())) for line in source.read_text().splitlines() if line.strip()]
        audit.equal('primary_control.values.'+source.name, entry['values'], expected, atol=0, rtol=0)
        for row in expected:
            modeled[(entry['alpha_deg'], row[0], entry['quantity'])] = row[1]
    comparisons = []
    for state in states:
        spec = state['specification']
        ref, alpha, speed = spec['refinement'], spec['alpha_deg'], spec['speed_m_s']
        if speed == 0:
            continue
        current, baseline = observations[(ref, alpha, speed)], observations[(ref, 0., 0.)]
        delta = [a-b for a,b in zip(current['midchord_m'], baseline['midchord_m'])]
        angle = math.radians(alpha)
        prediction = dict(displacement_percent_semispan=100*delta[2]/.55,
                          twist_deg=current['projected_twist_deg']-baseline['projected_twist_deg'],
                          wind_normal_displacement_percent_semispan=100*(-math.sin(angle)*delta[0]+math.cos(angle)*delta[2])/.55)
        experimental = {k:measured[(alpha, speed, 'twist_deg' if k=='twist_deg' else 'displacement_percent_semispan')] for k in prediction}
        errors = {k:prediction[k]-experimental[k] for k in prediction}
        relative = {k:100*errors[k]/experimental[k] for k in prediction}
        control = {k:modeled[(alpha, speed, 'twist_deg' if k=='twist_deg' else 'displacement_percent_semispan')] for k in prediction}
        control_error = {k:100*(prediction[k]-control[k])/control[k] for k in prediction}
        comparisons.append(dict(**spec, predicted=prediction, experiment=experimental,
                                error=errors, error_percent_of_measurement=relative,
                                primary_beam_control=control, error_percent_of_primary_beam_control=control_error))
    audit.equal('comparisons', report['comparisons'], comparisons, group='reduction')
    mesh = []
    for alpha, speed in ((5., 30.), (5., 40.), (7., 30.)):
        coarse, fine = [next(c for c in comparisons if (c['refinement'], c['alpha_deg'], c['speed_m_s']) == (r, alpha, speed)) for r in (2, 4)]
        difference = {k:fine['predicted'][k]-coarse['predicted'][k] for k in fine['predicted']}
        relative = {k:difference[k]/fine['predicted'][k] for k in difference}
        mesh.append(dict(alpha_deg=alpha, speed_m_s=speed, fine_minus_coarse=difference,
                         relative_to_fine=relative, displacement_within_one_percent=abs(relative['displacement_percent_semispan']) <= .01))
    audit.equal('mesh', report['mesh'], mesh, group='mesh_reduction')
    with (DEST/'isae-ae1-pilot.csv').open(newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    expected_rows = [(row, quantity) for row in comparisons for quantity in row['predicted']]
    audit.check('csv.rows', len(csv_rows) == len(expected_rows) == 18)
    for index, (actual, (expected, quantity)) in enumerate(zip(csv_rows, expected_rows)):
        audit.check(f'csv.{index}.quantity', actual['quantity'] == quantity)
        for key in ('intervals_per_half', 'alpha_deg', 'speed_m_s'):
            audit.equal(f'csv.{index}.'+key, float(actual[key]), expected[key])
        for key in ('predicted', 'experiment', 'error', 'error_percent_of_measurement'):
            audit.equal(f'csv.{index}.'+key, float(actual[key]), expected[key][quantity], group='csv')
    audit.check('scope.no_acceptance_threshold', report['experimental_acceptance_threshold'] is None)
    audit.check('scope.coverage_not_promoted', report['coverage_promoted'] is False)
    audit.check('scope.axes_unresolved', 'Unresolved' in report['displacement_axis_status'])
    for entry in initial_pins:
        audit.check('unchanged.'+entry['path'], pin(entry['path']) == entry)
    output = dict(status='PASS' if not audit.failures else 'FAIL', checks=audit.count,
                  passed=audit.count-len(audit.failures), failed=len(audit.failures), failures=audit.failures,
                  maximum_absolute_errors=audit.errors, diagnostics=diagnostics,
                  fine_comparisons=[row for row in comparisons if row['refinement']==4], mesh=mesh,
                  counts=dict(saved_states=8, loaded_states=6, vacuum_baselines=2, unique_flow_conditions=3,
                              unique_selected_measured_values=6, reduction_csv_rows=18, new_physics_evaluations=0),
                  scope='Saved-only audit. Recomputed raw-state geometry, mirror symmetry, saved-load conservation, primary measurement copies, observables, alternatives for displacement axes, mesh differences and CSV. Fresh nonlinear residual values are retained evidence, not independently reevaluated.',
                  source_and_input_pins=initial_pins)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:output[k] for k in ('status', 'checks', 'passed', 'failed', 'maximum_absolute_errors')}))
    if audit.failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
