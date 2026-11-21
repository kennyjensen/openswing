"""Independently reduce and audit saved Pazy AE-1 sweep data using stdlib only.

No model construction, NumPy/OpenSwing imports, residual evaluation or solve.
Missing/failed states remain explicit. Passing arithmetic/provenance checks
does not establish experimental agreement, equilibrium uniqueness or stability.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import math


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / 'docs/validation/isae-ae1-pilot.json'
QUANTITIES = ('displacement_percent_semispan', 'twist_deg',
              'wind_normal_displacement_percent_semispan')


class SourcePaths:
    """Resolve frozen inputs under this script's ROOT, never the old workspace.

    The pilot records relative source names and the sweep records the matching
    absolute names/hashes. Their agreement identifies the historical root.
    Original scientific records and hashes are not rewritten for replay.
    """
    def __init__(self, plan, pilot):
        relatives = pilot['measurements']+pilot['primary_beam_controls']
        roots = set()
        for table in plan['source_tables']:
            recorded = Path(table['source_pin']['path'])
            if not recorded.is_absolute():
                raise ValueError('Sweep source table must retain its historical absolute path.')
            matches = [Path(row['source_path']) for row in relatives
                       if row['sha256'] == table['source_pin']['sha256']
                       and not Path(row['source_path']).is_absolute()
                       and recorded.parts[-len(Path(row['source_path']).parts):] == Path(row['source_path']).parts]
            if len(matches) != 1:
                raise ValueError('Historical source path is not uniquely linked to a pinned pilot table: '+str(recorded))
            roots.add(Path(*recorded.parts[:-len(matches[0].parts)]))
        if len(roots) != 1:
            raise ValueError('Inconsistent historical source roots in recorded source tables.')
        self.historical_root = roots.pop()
        self.known = set(plan['source_sha256'])
        if any(Path(name).is_absolute() or '..' in Path(name).parts for name in self.known):
            raise ValueError('Sweep dependencies must use safe ROOT-relative names.')
        self.resolutions = {}

    def resolve(self, recorded):
        path = Path(recorded)
        if path.is_absolute():
            try:
                relative = path.relative_to(self.historical_root)
            except ValueError as exc:
                raise ValueError('Historical input lies outside the recorded source root: '+str(path)) from exc
        else:
            relative = path
        if '..' in relative.parts or str(relative) not in self.known:
            raise ValueError('Input is not a declared frozen sweep dependency: '+str(recorded))
        resolved = (ROOT/relative).resolve()
        if not resolved.is_relative_to(ROOT):
            raise ValueError('Frozen source path escapes the replay root: '+str(relative))
        self.resolutions[str(recorded)] = dict(historical_path=str(self.historical_root/relative),
                                              relative_path=str(relative), resolved_path=str(resolved))
        return resolved

    def historical(self, relative):
        self.resolve(relative)
        return str(self.historical_root/relative)


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def norm(values):
    return math.sqrt(sum(value*value for value in values))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def rotation(vector):
    theta = norm(vector)
    if theta == 0:
        return [[float(i == j) for j in range(3)] for i in range(3)]
    axis = [value/theta for value in vector]
    x, y, z = axis
    skew = [[0., -z, y], [z, 0., -x], [-y, x, 0.]]
    c, s = math.cos(theta), math.sin(theta)
    return [[c*float(i == j)+(1-c)*axis[i]*axis[j]+s*skew[i][j]
             for j in range(3)] for i in range(3)]


def observable(node):
    position, q = node['position'], node['rotation']
    leading = [position[i]-.0441*q[i][0] for i in range(3)]
    trailing = [position[i]+.0559*q[i][0] for i in range(3)]
    return dict(leading_edge_m=leading, trailing_edge_m=trailing,
                midchord_m=[(a+b)/2 for a, b in zip(leading, trailing)],
                projected_twist_deg=math.degrees(math.atan2(
                    leading[2]-trailing[2], trailing[0]-leading[0])))


def ratio(numerator, denominator, factor=1.):
    return factor*numerator/denominator if denominator != 0 else None


def key(spec):
    return spec['refinement'], spec['alpha_deg'], spec['speed_m_s']


def expected_specifications():
    return [dict(refinement=r, intervals_per_half=15*r, alpha_deg=a, speed_m_s=v)
            for r in (2, 4)
            for a, v in [(0., 0.), *[(5., float(v)) for v in range(3, 57)],
                         *[(7., float(v)) for v in range(4, 42)]]]


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []
        self.errors = {}

    def check(self, name, passed):
        self.count += 1
        if not passed:
            self.failures.append(name)

    def equal(self, name, actual, expected, *, atol=3e-13, rtol=3e-12, group=None):
        if isinstance(expected, dict):
            self.check(name+'.type', isinstance(actual, dict))
            if not isinstance(actual, dict):
                return
            self.check(name+'.keys', set(actual) == set(expected))
            for k in actual.keys() & expected.keys():
                self.equal(name+'.'+str(k), actual[k], expected[k], atol=atol, rtol=rtol, group=group)
        elif isinstance(expected, (list, tuple)):
            self.check(name+'.type', isinstance(actual, (list, tuple)))
            if not isinstance(actual, (list, tuple)):
                return
            self.check(name+'.length', len(actual) == len(expected))
            for i, (a, e) in enumerate(zip(actual, expected)):
                self.equal(name+'.'+str(i), a, e, atol=atol, rtol=rtol, group=group)
        elif isinstance(expected, (float, int)) and not isinstance(expected, bool):
            numeric = isinstance(actual, (float, int)) and not isinstance(actual, bool)
            finite = numeric and math.isfinite(actual) and math.isfinite(expected)
            error = abs(actual-expected) if finite else None
            if group and error is not None:
                self.errors[group] = max(error, self.errors.get(group, 0.))
            self.check(name, finite and error <= atol+rtol*abs(expected))
        else:
            self.check(name, actual == expected)


def read_reference_tables(pilot, audit, pins, source_paths):
    """Original text files are the observations; pilot arrays are checked copies."""
    measurements, controls = {}, {}
    records = []
    for kind, entries, target in (
        ('measurement', pilot['measurements'], measurements),
        ('primary_control', pilot['primary_beam_controls'], controls),
    ):
        audit.check(kind+'.table_count', len(entries) == 4)
        for entry in entries:
            path = source_paths.resolve(entry['source_path'])
            snapshot = pin(path)
            pins.append(snapshot)
            audit.check(kind+'.pin.'+path.name, snapshot['sha256'] == entry['sha256'])
            rows = []
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                columns = list(map(float, line.split()))
                audit.check(kind+'.column_count.'+path.name,
                            len(columns) == 2 if kind == 'measurement' else len(columns) >= 2)
                speed, value = columns[:2]
                audit.check(kind+'.finite_speed.'+path.name, math.isfinite(speed))
                value = value if math.isfinite(value) else None
                rows.append([v if math.isfinite(v) else None for v in columns])
                if value is not None:
                    item = (entry['alpha_deg'], speed, entry['quantity'])
                    audit.check(kind+'.unique.'+str(item), item not in target)
                    target[item] = value
            audit.equal(kind+'.copy.'+path.name, entry['values'], rows, atol=0, rtol=0)
            historical_pin = dict(snapshot, path=source_paths.historical(entry['source_path']))
            records.append(dict(kind=kind, alpha_deg=entry['alpha_deg'], quantity=entry['quantity'],
                                source=historical_pin, rows=rows))
    expected = {(a, float(v), q) for a, speeds in ((5., range(3, 57)), (7., range(4, 42)))
                for v in speeds for q in QUANTITIES[:2]}
    audit.check('measurement.exact_finite_coverage', set(measurements) == expected)
    return measurements, controls, records


def audit_plan_tables(plan, tables, audit):
    originals = {entry['source']['path']:entry for entry in tables}
    audit.check('plan.source_tables.count', len(plan['source_tables']) == len(originals) == 8)
    visited = set()
    for entry in plan['source_tables']:
        path = str(Path(entry['path']))
        audit.check('plan.source_table.unique.'+path, path not in visited)
        visited.add(path)
        audit.check('plan.source_table.present.'+path, path in originals)
        if path not in originals:
            continue
        original = originals[path]
        audit.equal('plan.source_table.values.'+path, entry['values'], original['rows'], atol=0, rtol=0)
        audit.equal('plan.source_table.pin.'+path, entry['source_pin'], original['source'], atol=0, rtol=0)
        audit.equal('plan.source_table.alpha.'+path, entry['alpha_deg'], original['alpha_deg'], atol=0, rtol=0)
        audit.check('plan.source_table.quantity.'+path,
                    entry['quantity'] == ('twist' if original['quantity'] == 'twist_deg' else 'displacement'))
        audit.check('plan.source_table.reference.'+path,
                    entry['reference'] == ('experiment' if original['kind'] == 'measurement' else 'UM/NAST-VLM'))
        audit.equal('plan.source_table.finite.'+path, entry['finite_value'],
                    [row[1] is not None for row in original['rows']], atol=0, rtol=0)


def audit_state(row, plan, audit, name):
    """Reconstruct every saved pose, then recover positive-tip measurements."""
    spec, result = row['specification'], row['result']
    nodes, raw = result['nodes'], row['state']
    n = 2*spec['intervals_per_half']+1
    audit.check(name+'.source_pin', hashlib.sha256(row['source'].encode()).hexdigest() == row['source_sha256'])
    fixture = next(item for item in plan['fixtures'] if item['refinement'] == spec['refinement'])
    audit.check(name+'.fixture_source', row['source_sha256'] == fixture['source_sha256'])
    audit.check(name+'.nodes_count', len(nodes) == row['counts']['nodes'] == n)
    audit.check(name+'.elements_count', len(result['elements']) == row['counts']['elements'] == n-1)
    audit.equal(name+'.nominal_semispan', fixture['nominal_semispan_m'], .55, atol=0, rtol=0)
    length = norm([max(node['jig_position'][i] for node in nodes)-min(node['jig_position'][i] for node in nodes)
                   for i in range(3)])
    audit.equal(name+'.actual_span', length, 2*fixture['actual_semispan_m'], atol=2e-14, rtol=0)
    required_raw = 6*n+6*(n-1)+6+(n-1 if spec['speed_m_s'] else 0)
    audit.check(name+'.state_size', len(raw) == required_raw)
    audit.check(name+'.finite_state', all(isinstance(v, (float, int)) and math.isfinite(v) for v in raw))
    reflection = [1., -1., 1.]
    mirror_position = mirror_rotation = 0.
    for i, node in enumerate(nodes):
        audit.check(name+f'.node{i}.index', node['index'] == i and node['beam'] == 1)
        # Evaluating the affine input spline introduces ordinary roundoff.
        audit.equal(name+f'.node{i}.jig', node['jig_position'], [0., node['t'], 0.], atol=2e-14, rtol=0)
        p = [node['jig_position'][j]+length*raw[6*i+j] for j in range(3)]
        q = rotation(raw[6*i+3:6*i+6])
        audit.equal(name+f'.raw_position{i}', node['position'], p, group='raw_position_m')
        audit.equal(name+f'.raw_rotation{i}', node['rotation'], q, group='raw_rotation')
        partner = nodes[-1-i]
        for j in range(3):
            mirror_position = max(mirror_position, abs(partner['position'][j]-reflection[j]*node['position'][j]))
            for k in range(3):
                mirror_rotation = max(mirror_rotation, abs(partner['rotation'][j][k]-reflection[j]*reflection[k]*node['rotation'][j][k]))
    audit.equal(name+'.panel_nodes', [node['t'] for node in nodes], row['panels']['beams']['1']['nodes'], atol=0, rtol=0)
    audit.check(name+'.ordered_nodes', all(a['t'] < b['t'] for a, b in zip(nodes[:-1], nodes[1:])))
    root = [node for node in nodes if node['t'] == 0.]
    audit.check(name+'.single_root', len(root) == 1)
    if root:
        audit.equal(name+'.root_position', root[0]['position'], [0., 0., 0.], atol=1e-12, rtol=0)
        audit.equal(name+'.root_rotation', root[0]['rotation'], rotation([0., 0., 0.]), atol=1e-12, rtol=0)
    audit.equal(name+'.mirror_position', row['checks']['mirror_position_error_m'], mirror_position, group='mirror_report')
    audit.equal(name+'.mirror_rotation', row['checks']['mirror_rotation_error'], mirror_rotation, group='mirror_report')
    audit.check(name+'.mirror_position_gate', mirror_position/length <= plan['gates']['mirror_position_scaled'])
    audit.check(name+'.mirror_rotation_gate', mirror_rotation <= plan['gates']['mirror_rotation'])
    audit.check(name+'.saved_converged', result['converged'] is True)
    for label, value in (('fresh', row['checks']['fresh_residual']), ('reported', result['residual'])):
        audit.check(name+'.'+label+'_residual_gate', math.isfinite(value) and 0 <= value <= plan['gates']['residual'])
    applied, moment = result['applied_force'], result['applied_moment']
    support, support_moment = result['support_force'], result['support_moment']
    balances = [[a+b for a, b in zip(x, y)] for x, y in ((applied, support), (moment, support_moment))]
    force_scale = max(1., norm(applied), norm(support))
    moment_scale = max(1., force_scale*length, norm(support_moment))
    for label, value, scale in zip(('force', 'moment'), balances, (force_scale, moment_scale)):
        audit.equal(name+'.'+label+'_balance', result[label+'_balance'], value, group='balance_report')
        scaled = max(map(abs, value))/scale
        audit.equal(name+'.'+label+'_balance_scaled', row['checks'][label+'_balance_scaled'], scaled)
        audit.check(name+'.'+label+'_balance_gate', scaled <= plan['gates']['force_moment_balance_scaled'])
    audit.equal(name+'.gravity', result['gravity_body'], [0., 0., 0.], atol=0, rtol=0)
    own = observable(max(nodes, key=lambda node: node['jig_position'][1]))
    audit.equal(name+'.observable', row['observable'], own, group='observable')
    strips = result.get('strips', [])
    if spec['speed_m_s']:
        audit.check(name+'.no_image_kernel', result['ground_plane']['flag'] == 0)
        audit.check(name+'.strip_count', len(strips) == n-1 and row['counts']['half_lifting_strips'] == (n-1)//2)
        flow = result['reference_flow']
        audit.equal(name+'.speed', flow['speed'], spec['speed_m_s'])
        audit.equal(name+'.alpha', flow['alpha'], spec['alpha_deg'])
        audit.equal(name+'.beta', flow['beta'], 0., atol=0, rtol=0)
        audit.equal(name+'.density', result['atmosphere']['density'], 1.23, atol=0, rtol=0)
        audit.equal(name+'.PG_mach', result['mach'], 0., atol=0, rtol=0)
        sf = [sum(s['force'][j] for s in strips) for j in range(3)]
        moments = [[a+b for a, b in zip(cross(s['position'], s['force']), s['moment'])] for s in strips]
        sm = [sum(value[j] for value in moments) for j in range(3)]
        audit.equal(name+'.strip_force_sum', result['force'], sf, atol=2e-11, group='force_sum')
        audit.equal(name+'.strip_moment_sum', result['moment'], sm, atol=2e-11, group='moment_sum')
        audit.equal(name+'.applied_force', applied, sf, atol=2e-11, group='force_sum')
        audit.equal(name+'.applied_moment', moment, sm, atol=2e-11, group='moment_sum')
        for j, strip in enumerate(strips[:len(strips)//2]):
            partner = strips[-1-j]
            audit.equal(name+f'.gamma_mirror{j}', strip['circulation'], partner['circulation'], atol=3e-11, group='gamma_mirror')
            audit.equal(name+f'.force_mirror{j}', strip['force'], [reflection[k]*partner['force'][k] for k in range(3)], atol=3e-11, group='force_mirror')
            audit.equal(name+f'.moment_mirror{j}', strip['moment'], [-reflection[k]*partner['moment'][k] for k in range(3)], atol=3e-11, group='moment_mirror')
    else:
        audit.equal(name+'.vacuum_state', raw, [0.]*len(raw), atol=0, rtol=0)
        audit.equal(name+'.vacuum_force', applied, [0., 0., 0.], atol=0, rtol=0)
        audit.equal(name+'.vacuum_moment', moment, [0., 0., 0.], atol=0, rtol=0)
    return own, dict(specification=spec, max_section_cl=max([s['cl'] for s in strips], default=0.),
                     stalled_sections=sum(s['stalled'] for s in strips), mirror_position_m=mirror_position,
                     mirror_rotation=mirror_rotation, fresh_residual=row['checks']['fresh_residual'])


def reductions(observations, measurements, controls):
    comparisons, unmatched = [], []
    for (refinement, alpha, speed), current in sorted(observations.items()):
        if speed == 0:
            continue
        base = observations.get((refinement, 0., 0.))
        if base is None:
            unmatched.append(dict(refinement=refinement, alpha_deg=alpha, speed_m_s=speed,
                                  reason='missing computed zero-flow baseline'))
            continue
        delta = [a-b for a, b in zip(current['midchord_m'], base['midchord_m'])]
        angle = math.radians(alpha)
        predictions = dict(displacement_percent_semispan=100*delta[2]/.55,
                           twist_deg=current['projected_twist_deg']-base['projected_twist_deg'],
                           wind_normal_displacement_percent_semispan=100*(-math.sin(angle)*delta[0]+math.cos(angle)*delta[2])/.55)
        experiment, primary, error, relative, control_relative = {}, {}, {}, {}, {}
        for quantity, value in predictions.items():
            source_quantity = 'twist_deg' if quantity == 'twist_deg' else 'displacement_percent_semispan'
            source_key = (alpha, speed, source_quantity)
            experiment[quantity] = measurements.get(source_key)
            primary[quantity] = controls.get(source_key)
            reference, control = experiment[quantity], primary[quantity]
            error[quantity] = None if reference is None else value-reference
            relative[quantity] = None if reference is None else ratio(value-reference, reference, 100.)
            control_relative[quantity] = None if control is None else ratio(value-control, control, 100.)
        comparisons.append(dict(refinement=refinement, intervals_per_half=15*refinement,
                                alpha_deg=alpha, speed_m_s=speed, predicted=predictions,
                                experiment=experiment, error=error, error_percent_of_measurement=relative,
                                primary_beam_control=primary, error_percent_of_primary_beam_control=control_relative))
    by_key = {key(row): row for row in comparisons}
    mesh = []
    for alpha, speed in sorted({(k[1], k[2]) for k in by_key}):
        coarse, fine = by_key.get((2, alpha, speed)), by_key.get((4, alpha, speed))
        if coarse is None or fine is None:
            mesh.append(dict(alpha_deg=alpha, speed_m_s=speed, status='missing_computed_mesh_pair'))
            continue
        difference = {q:fine['predicted'][q]-coarse['predicted'][q] for q in QUANTITIES}
        relative = {q:ratio(difference[q], fine['predicted'][q]) for q in QUANTITIES}
        mesh.append(dict(alpha_deg=alpha, speed_m_s=speed, status='compared',
                         fine_minus_coarse=difference, relative_to_fine=relative,
                         displacement_within_one_percent=(None if relative[QUANTITIES[0]] is None
                                                         else abs(relative[QUANTITIES[0]]) <= .01)))
    return comparisons, mesh, unmatched


def grouped_statistics(comparisons):
    groups = []
    for refinement in (2, 4):
        for alpha in (5., 7.):
            rows = [r for r in comparisons if r['refinement'] == refinement and r['alpha_deg'] == alpha]
            for quantity in QUANTITIES:
                selected = [r for r in rows if r['error'][quantity] is not None]
                errors = [r['error'][quantity] for r in selected]
                relative = [r['error_percent_of_measurement'][quantity] for r in selected
                            if r['error_percent_of_measurement'][quantity] is not None]
                worst = max(selected, key=lambda row:abs(row['error'][quantity]), default=None)
                groups.append(dict(refinement=refinement, alpha_deg=alpha, quantity=quantity,
                    count=len(errors), mean_error=sum(errors)/len(errors) if errors else None,
                    mean_absolute_error=sum(map(abs, errors))/len(errors) if errors else None,
                    root_mean_square_error=math.sqrt(sum(e*e for e in errors)/len(errors)) if errors else None,
                    maximum_absolute_error=max(map(abs, errors), default=None),
                    maximum_absolute_error_speed_m_s=worst['speed_m_s'] if worst else None,
                    maximum_absolute_percent_error=max(map(abs, relative), default=None)))
    return groups


def audit_source_scope(path, measurements, audit, pins, source_paths):
    """Verify the recorded source tags without turning them into stability results."""
    snapshot = pin(path)
    pins.append(snapshot)
    scope = json.loads(Path(path).read_text())
    expected_enum = {'below_reported_dynamic_indicator', 'reported_possible_instability_peak',
                     'after_reported_peak_recovery_boundary_unresolved',
                     'at_or_above_reported_instability_indicator'}
    audit.check('source_scope.enum', set(scope['tag_enum']) == expected_enum)
    tags = {}
    for entry in scope['coordinate_tags']:
        identity = entry['alpha_deg'], entry['speed_m_s']
        audit.check('source_scope.unique.'+str(identity), identity not in tags)
        tags[identity] = entry['tag']
        audit.check('source_scope.no_formal_stability.'+str(identity), entry['formal_stability_classification'] is None)
        audit.check('source_scope.locator.'+str(identity), bool(entry['source_locator']))
        alpha, speed = identity
        # These are reviewed documentary locations, not inferred onset bounds.
        if alpha == 5:
            expected = ('below_reported_dynamic_indicator' if speed < 48 else
                        'reported_possible_instability_peak' if speed == 48 else
                        'after_reported_peak_recovery_boundary_unresolved')
        else:
            audit.check('source_scope.alpha.'+str(identity), alpha == 7)
            expected = ('below_reported_dynamic_indicator' if speed < 40 else
                        'at_or_above_reported_instability_indicator')
        audit.check('source_scope.mapping.'+str(identity), entry['tag'] == expected)
        for field, quantity in (('measured_displacement_percent_semispan', QUANTITIES[0]),
                                ('measured_twist_deg', 'twist_deg')):
            audit.equal('source_scope.measurement.'+str(identity)+'.'+field,
                        entry[field], measurements.get((alpha,speed,quantity)), atol=0, rtol=0)
    audit.check('source_scope.exact_coverage', set(tags) == {(a,v) for a,v,q in measurements})
    counts = {tag:sum(value == tag for value in tags.values()) for tag in expected_enum}
    audit.equal('source_scope.counts', scope['tag_counts'], counts, atol=0, rtol=0)
    for source in scope['direct_input_pins']:
        actual = pin(source_paths.resolve(source['path'])); pins.append(actual)
        historical_pin = dict(actual,path=source['path'])
        audit.equal('source_scope.pin.'+source['path'], historical_pin, source, atol=0, rtol=0)
    return scope, tags, snapshot


def expected_report_rows(manifest, comparisons, measurements, controls, tags):
    indexed = {key(row):row for row in comparisons}
    rows = []
    for entry in manifest['states']:
        spec = entry['specification']
        if spec['speed_m_s'] == 0:
            continue
        identity = key(spec)
        a,v = identity[1:]
        row = dict(index=entry['index'], **spec, status=entry['status'], source_region=tags[a,v])
        if identity in indexed:
            row.update(indexed[identity])
            row['error_primary_beam_control'] = {
                q:None if row['primary_beam_control'][q] is None else row['predicted'][q]-row['primary_beam_control'][q]
                for q in QUANTITIES}
        else:
            for name, values in (('experiment',measurements), ('primary_beam_control',controls)):
                row[name] = {q:values.get((a,v,'twist_deg' if q == 'twist_deg' else QUANTITIES[0]))
                             for q in QUANTITIES}
            if entry['status'] == 'computed':
                row.update(status='baseline_unavailable', reason='No successful same-mesh zero-flow baseline.')
        rows.append(row)
    return rows


def report_statistics(rows):
    """Calculate each group directly from independently reconstructed predictions."""
    result = []
    for refinement in (2,4):
        for alpha in (5,7):
            selected = [r for r in rows if r['refinement'] == refinement and r['alpha_deg'] == alpha]
            labels = ['all_exported']+sorted({r['source_region'] for r in selected})
            for label in labels:
                group = selected if label == 'all_exported' else [r for r in selected if r['source_region'] == label]
                record = dict(refinement=refinement, alpha_deg=alpha, source_region=label,
                              requested=len(group), computed=sum(r['status'] == 'computed' for r in group))
                for reference in ('experiment','primary_beam_control'):
                    record[reference] = {}
                    for quantity in QUANTITIES:
                        errors = [r['predicted'][quantity]-r[reference][quantity] for r in group
                                  if r['status'] == 'computed' and r[reference][quantity] is not None]
                        record[reference][quantity] = dict(count=len(errors),
                            bias=sum(errors)/len(errors) if errors else None,
                            rmse=math.sqrt(sum(e*e for e in errors)/len(errors)) if errors else None,
                            maximum_absolute_error=max(map(abs,errors),default=None))
                result.append(record)
    return result


def check_reduction(report, plan, manifest, comparisons, mesh, measurements, controls,
                    source_scope, tags, scope_pin, audit, pins, csv_path=None):
    audit.equal('reduction.plan', report['plan'], plan, atol=0, rtol=0)
    audit.equal('reduction.execution', report['execution'], {k:v for k,v in manifest.items() if k != 'states'}, atol=0, rtol=0)
    audit.equal('reduction.states', report['states'], manifest['states'], atol=0, rtol=0)
    audit.equal('reduction.source_tables', report['source_tables'], plan['source_tables'], atol=0, rtol=0)
    audit.equal('reduction.source_scope', report['source_scope'], source_scope, atol=0, rtol=0)
    audit.check('reduction.scope_pin', report['source_scope_sha256'] == scope_pin['sha256'])
    reducer_pin = pin(ROOT/'scripts/summarize-isae-ae1-sweep.py'); pins.append(reducer_pin)
    audit.check('reduction.reducer_pin', report['reducer_sha256'] == reducer_pin['sha256'])
    expected = expected_report_rows(manifest, comparisons, measurements, controls, tags)
    audit.equal('reduction.comparisons', report['comparisons'], expected, group='reduction')
    indexed_mesh = {(r['alpha_deg'],r['speed_m_s']):r for r in mesh}
    expected_mesh = []
    for a,v in sorted({(r['alpha_deg'],r['speed_m_s']) for r in expected}):
        row = dict(alpha_deg=a, speed_m_s=v, source_region=tags[a,v], status='unavailable')
        current = indexed_mesh.get((a,v))
        if current and current['status'] == 'compared':
            row.update({k:current[k] for k in ('fine_minus_coarse','relative_to_fine','displacement_within_one_percent')})
            row['status'] = 'computed'
        expected_mesh.append(row)
    audit.equal('reduction.mesh', report['mesh'], expected_mesh, group='mesh_reduction')
    statistics = report_statistics(expected)
    audit.equal('reduction.statistics', report['statistics'], statistics, group='statistics')
    coverage_counts = dict(requested_states=186, requested_loaded_states=184, unique_measured_coordinates=92,
                           unique_measured_values=184, requested_mesh_pairs=92,
        passing_displacement_mesh_pairs=sum(r.get('displacement_within_one_percent') is True for r in expected_mesh),
        failing_displacement_mesh_pairs=sum(r.get('displacement_within_one_percent') is False for r in expected_mesh),
        unavailable_displacement_mesh_pairs=sum(r.get('displacement_within_one_percent') is None for r in expected_mesh))
    audit.equal('reduction.coverage_counts', report['counts'], coverage_counts, atol=0, rtol=0)
    audit.check('scope.no_experimental_threshold', 'experimental_acceptance_threshold' in report and report['experimental_acceptance_threshold'] is None)
    audit.check('scope.no_stability_computation', report.get('stability_computed') is False)
    if csv_path:
        pins.append(pin(csv_path))
        with Path(csv_path).open(newline='') as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames
            actual = list(reader)
        fields = ['intervals_per_half','alpha_deg','speed_m_s','source_region','status','quantity',
                  'predicted','experiment','error','error_percent_of_measurement','primary_beam_control']
        audit.equal('csv.columns', columns, fields)
        pairs = [(row,q) for row in expected for q in QUANTITIES]
        audit.check('csv.row_count', len(actual) == len(pairs))
        for i,(saved,(row,q)) in enumerate(zip(actual,pairs)):
            for field in fields[:3]:
                audit.equal(f'csv.{i}.'+field,float(saved[field]),row[field],group='csv')
            for field in ('source_region','status'):
                audit.check(f'csv.{i}.'+field,saved[field] == row[field])
            audit.check(f'csv.{i}.quantity',saved['quantity'] == q)
            for field in fields[6:]:
                want = row.get(field,{}).get(q)
                got = None if saved[field] == '' else float(saved[field])
                audit.equal(f'csv.{i}.'+field,got,want,group='csv')
    return statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, help='Optional independent producer reduction to compare.')
    parser.add_argument('--report-csv', type=Path, help='Optional producer CSV to verify with --report.')
    parser.add_argument('--source-scope', type=Path, help='Reviewed source tag records; required with --report.')
    parser.add_argument('--csv-output', type=Path, help='Optional independent long-form observable/error table.')
    args = parser.parse_args()
    if args.report and not args.source_scope:
        parser.error('--report requires --source-scope')
    if args.report_csv and not args.report:
        parser.error('--report-csv requires --report')
    audit = Audit()
    plan_path, manifest_path = args.run/'plan.json', args.run/'manifest.json'
    pins = [pin(Path(__file__)), pin(PILOT), pin(plan_path), pin(manifest_path)]
    plan = json.loads(plan_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    pilot = json.loads(PILOT.read_text())
    source_paths = SourcePaths(plan, pilot)
    unhashed = {k:v for k,v in plan.items() if k != 'identity'}
    audit.check('plan.identity', hashlib.sha256(json.dumps(unhashed, sort_keys=True).encode()).hexdigest() == plan['identity'])
    audit.equal('plan.specifications', plan['specifications'], expected_specifications(), atol=0, rtol=0)
    audit.equal('plan.conditions', plan['conditions'], dict(density=1.23, mach=0., gravity=[0.,0.,0.]), atol=0, rtol=0)
    audit.check('plan.pilot_identity', plan['pilot_identity'] == pilot['plan']['identity'])
    audit.equal('plan.fixtures', plan['fixtures'], pilot['plan']['fixtures'], atol=0, rtol=0)
    audit.equal('plan.gates', plan['gates'], pilot['plan']['gates'], atol=0, rtol=0)
    audit.check('plan.no_experimental_threshold', plan['experimental_acceptance_threshold'] is None)
    for field, count in (('unique_measured_coordinates',92), ('unique_measured_values',184),
                         ('requested_states',186), ('reused_pilot_states',8), ('requested_new_states',178)):
        audit.check('plan.'+field, plan[field] == count)
    for name, digest in plan['source_sha256'].items():
        source = pin(source_paths.resolve(name))
        pins.append(source)
        audit.check('source_pin.'+name, source['sha256'] == digest)
    measurements, controls, tables = read_reference_tables(pilot, audit, pins, source_paths)
    audit_plan_tables(plan, tables, audit)
    lookup = {key(row['specification']):row for row in pilot['states']}
    entries = manifest['states']
    audit.check('manifest.identity', manifest['identity'] == plan['identity'])
    audit.check('manifest.terminal', manifest['status'] in ('completed', 'completed_with_failures', 'incomplete'))
    audit.check('manifest.requested', manifest['requested'] == 186)
    audit.check('manifest.recorded', manifest['recorded'] == len(entries))
    seen, observations, diagnostics, unavailable = set(), {}, [], []
    counts = dict(computed=0, failed=0, unrun=0, reused=0, new_attempted=0)
    for index, entry in enumerate(entries):
        name = f'state{index:03d}'
        audit.check(name+'.manifest_index', entry['index'] == index)
        audit.equal(name+'.specification', entry['specification'], plan['specifications'][index], atol=0, rtol=0)
        identity = key(entry['specification'])
        audit.check(name+'.unique', identity not in seen)
        seen.add(identity)
        path = args.run/'cases'/entry['raw']['file']
        snapshot = pin(path)
        pins.append(snapshot)
        audit.equal(name+'.compressed_pin', {k:snapshot[k] for k in ('bytes','sha256')},
                    {k:entry['raw'][k] for k in ('bytes','sha256')}, atol=0, rtol=0)
        content = gzip.decompress(path.read_bytes())
        audit.check(name+'.uncompressed_bytes', len(content) == entry['raw']['uncompressed_bytes'])
        audit.check(name+'.uncompressed_pin', hashlib.sha256(content).hexdigest() == entry['raw']['uncompressed_sha256'])
        row = json.loads(content)
        audit.equal(name+'.raw_specification', row['specification'], entry['specification'], atol=0, rtol=0)
        audit.check(name+'.raw_status', row['status'] == entry['status'])
        status = row['status']
        audit.check(name+'.known_status', status in ('computed', 'failed', 'unrun'))
        counts[status] = counts.get(status,0)+1
        if entry['origin']['kind'] == 'reused_pilot':
            counts['reused'] += 1
            audit.check(name+'.pilot_membership', identity in lookup)
            audit.check(name+'.pilot_identity', row['identity'] == plan['pilot_identity'] == entry['origin']['identity'])
            audit.check(name+'.pilot_source', entry['origin']['source_sha256'] == pin(PILOT)['sha256'])
            if identity in lookup:
                # All scientific values, provenance, iterations and original timings survive.
                audit.equal(name+'.exact_pilot_content', row, lookup[identity], atol=0, rtol=0)
        else:
            audit.check(name+'.new_origin', entry['origin']['kind'] == 'new')
            audit.check(name+'.not_recomputed_pilot', identity not in lookup)
            if status != 'unrun':
                counts['new_attempted'] += 1
                audit.check(name+'.new_identity', row['identity'] == plan['identity'])
        for field in ('observable','checks','counts','seconds','error','reason'):
            audit.check(name+'.copy_presence.'+field, (field in row) == (field in entry))
            if field in row:
                audit.equal(name+'.manifest_copy.'+field, entry[field], row[field], atol=0, rtol=0)
        if status == 'computed':
            own, diagnostic = audit_state(row, plan, audit, name)
            observations[identity] = own
            diagnostics.append(diagnostic)
            if identity[2]:
                strips = [s for s in row['result']['strips'] if s['lifting']]
                audit.equal(name+'.aero_diagnostics', entry['aero_diagnostics'], dict(
                    min_cl=min(s['cl'] for s in strips), max_cl=max(s['cl'] for s in strips),
                    stalled_strips=sum(bool(s['stalled']) for s in strips)), atol=0, rtol=0)
        else:
            audit.check(name+'.no_claimed_observable', 'observable' not in row and 'result' not in row)
            unavailable.append(dict(index=index, specification=entry['specification'], status=status,
                                    reason=row.get('reason',row.get('error'))))
    for field, value in counts.items():
        audit.check('manifest.count.'+field, manifest[field] == value)
    for index, spec in enumerate(plan['specifications']):
        if key(spec) not in seen:
            unavailable.append(dict(index=index, specification=spec, status='missing', reason='No retained request record.'))
    full = len(entries) == 186 and counts['computed'] == 186
    expected_status = ('completed' if full else 'completed_with_failures'
                       if len(entries) == 186 and counts['unrun'] == 0 else 'incomplete')
    audit.check('manifest.status_matches_records', manifest['status'] == expected_status)
    if len(entries) == 186:
        audit.check('reuse.exact_eight', counts['reused'] == 8)
        audit.check('requests.exact_new', counts['new_attempted']+counts['unrun'] == 178)
    comparisons, mesh, unmatched = reductions(observations, measurements, controls)
    selected_measurements = {(row['alpha_deg'],row['speed_m_s'],quantity)
                             for row in comparisons for quantity in QUANTITIES[:2]
                             if row['experiment'][quantity] is not None}
    counts.update(saved_states=len(entries), missing_states=186-len(entries),
                  loaded_states=sum(key[2] != 0 for key in observations),
                  vacuum_baselines=sum(key[2] == 0 for key in observations),
                  unique_loaded_coordinates=len({(key[1],key[2]) for key in observations if key[2]}),
                  unique_compared_measurements=len(selected_measurements),
                  measured_values_available=len(measurements), comparisons=len(comparisons),
                  complete_mesh_pairs=sum(row['status'] == 'compared' for row in mesh),
                  long_form_rows=3*len(comparisons), new_physics_evaluations=0,
                  residual_evaluations=0, new_aircraft_solves=0)
    if full:
        for field, value in (('loaded_states',184), ('vacuum_baselines',2), ('unique_loaded_coordinates',92),
                             ('unique_compared_measurements',184), ('comparisons',184),
                             ('complete_mesh_pairs',92), ('long_form_rows',552)):
            audit.check('complete_coverage.'+field, counts[field] == value)
    source_statistics = None
    if args.source_scope:
        source_scope,tags,scope_pin = audit_source_scope(args.source_scope, measurements, audit, pins, source_paths)
    if args.report:
        pins.append(pin(args.report))
        source_statistics = check_reduction(json.loads(args.report.read_text()), plan, manifest,
            comparisons, mesh, measurements, controls, source_scope, tags, scope_pin, audit, pins, args.report_csv)
    for snapshot in pins:
        audit.check('unchanged.'+snapshot['path'], pin(snapshot['path']) == snapshot)
    output = dict(schema='openswing-isae-ae1-sweep-saved-audit-v1',
        status='PASS' if not audit.failures else 'FAIL', checks=audit.count,
        passed=audit.count-len(audit.failures), failed=len(audit.failures), failures=audit.failures,
        plan_identity=plan['identity'], study_coverage='complete' if full else 'incomplete',
        maximum_absolute_errors=audit.errors, counts=counts, unavailable=unavailable,
        unmatched_baselines=unmatched, diagnostics=diagnostics, comparisons=comparisons, mesh=mesh,
        grouped_statistics=grouped_statistics(comparisons), source_region_statistics=source_statistics,
        source_tables=tables, experimental_acceptance_threshold=None, stability_computed=False,
        displacement_axis_status='Unresolved; root-normal and wind-normal use the same observation, not independent measurements.',
        stability_status='Not assessed. Static residual convergence and symmetry do not establish static or dynamic stability.',
        scope='Independent saved-only reconstruction of raw-state geometry, material-tip observables, load sums, symmetry, original measurements, two displacement axes, errors and mesh changes. Stored fresh residual values are checked, not independently reevaluated.',
        source_and_input_pins=pins,
        source_path_resolution=dict(historical_root=str(source_paths.historical_root),
                                    replay_root=str(ROOT), entries=list(source_paths.resolutions.values())))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    if args.csv_output:
        args.csv_output.parent.mkdir(parents=True,exist_ok=True)
        fields=['refinement','intervals_per_half','alpha_deg','speed_m_s','quantity','predicted','experiment','error','error_percent_of_measurement']
        with args.csv_output.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
            for row in comparisons:
                for quantity in QUANTITIES:
                    writer.writerow({**{field:row[field] for field in fields[:4]},'quantity':quantity,
                                     **{field:row[field][quantity] for field in fields[5:]}})
    print(json.dumps({k:output[k] for k in ('status','checks','passed','failed','study_coverage','counts','maximum_absolute_errors')}))
    if audit.failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
