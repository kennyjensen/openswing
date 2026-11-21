"""Independently audit saved AE-1 section-slope diagnostic data (stdlib only).

Reconstruct raw poses, tip observables and load sums using the established
saved-state auditor. No model construction, production imports, residual
evaluation or solve. Experimental agreement is reported, never a pass gate.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT/'scripts/check-isae-ae1-sweep.py'
loader = importlib.util.spec_from_file_location('ae1_saved_audit', HELPER)
SAVED = importlib.util.module_from_spec(loader)
loader.loader.exec_module(SAVED)
QUANTITIES = SAVED.QUANTITIES
POINTS = ((5., 30.), (5., 40.), (7., 30.))
GATES = dict(residual=1e-8, force_moment_balance_scaled=1e-7,
             mirror_position_scaled=1e-8, mirror_rotation=1e-8,
             displacement_mesh_relative=.01)


def specifications():
    return [dict(refinement=r, intervals_per_half=15*r, alpha_deg=a, speed_m_s=u)
            for r in (2, 4) for a, u in POINTS]


def key(spec):
    return spec['refinement'], spec['alpha_deg'], spec['speed_m_s']


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path, pins):
    pins.append(SAVED.pin(path))
    return json.loads(path.read_bytes())


def load_raw(run, entry, audit, pins, name):
    relative = Path(entry['raw']['file'])
    audit.check(name+'.safe_raw_name', relative.name == str(relative))
    if relative.name != str(relative):
        raise ValueError('Raw filename must be a basename.')
    path = run/'cases'/relative
    packed = path.read_bytes()
    pins.append(SAVED.pin(path))
    audit.equal(name+'.compressed_bytes', len(packed), entry['raw']['bytes'], atol=0, rtol=0)
    audit.check(name+'.compressed_sha256', digest(packed) == entry['raw']['sha256'])
    raw = gzip.decompress(packed)
    audit.equal(name+'.uncompressed_bytes', len(raw), entry['raw']['uncompressed_bytes'], atol=0, rtol=0)
    audit.check(name+'.uncompressed_sha256', digest(raw) == entry['raw']['uncompressed_sha256'])
    row = json.loads(raw)
    audit.equal(name+'.specification', row['specification'], entry['specification'], atol=0, rtol=0)
    audit.check(name+'.status', row['status'] == entry['status'])
    for field in ('observable', 'checks', 'counts', 'seconds', 'error', 'reason'):
        audit.check(name+'.presence.'+field, (field in row) == (field in entry))
        if field in row:
            audit.equal(name+'.manifest.'+field, entry[field], row[field], atol=0, rtol=0)
    if row['status'] == 'computed' and row['specification']['speed_m_s']:
        strips = [s for s in row['result']['strips'] if s['lifting']]
        audit.equal(name+'.aero_diagnostics', entry['aero_diagnostics'], dict(
            min_cl=min(s['cl'] for s in strips), max_cl=max(s['cl'] for s in strips),
            stalled_strips=sum(bool(s['stalled']) for s in strips)), atol=0, rtol=0)
    return row


def audit_mutation(original, candidate, audit, name):
    """Locate the two permitted scalar changes independently from table tokens."""
    before, after = original.split(), candidate.split()
    header = 't dCLda CLmax CLmin alpha Cm Cdf Cdp'.split()
    headers = [i for i in range(len(before)-len(header)+1) if before[i:i+len(header)] == header]
    audit.check(name+'.one_slope_table', len(headers) == 1)
    audit.check(name+'.token_count', len(before) == len(after))
    if len(headers) != 1 or len(before) != len(after):
        return []
    first = headers[0]+len(header)
    allowed = [first+1, first+9]
    audit.check(name+'.two_table_rows', before[first+16] == after[first+16] == 'End')
    changes = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    audit.equal(name+'.changed_indices', changes, allowed, atol=0, rtol=0)
    for i in allowed:
        audit.check(name+f'.old_value{i}', float(before[i]) == 6.1185)
        audit.check(name+f'.new_value{i}', float(after[i]) == 2*math.pi)
    return [dict(token_index=i, baseline=before[i], candidate=after[i]) for i in changes]


def recover(loaded, zero, alpha):
    displacement = [loaded['midchord_m'][i]-zero['midchord_m'][i] for i in range(3)]
    angle = alpha*math.pi/180.
    return dict(displacement_percent_semispan=displacement[2]/.55*100.,
                twist_deg=loaded['projected_twist_deg']-zero['projected_twist_deg'],
                wind_normal_displacement_percent_semispan=(displacement[2]*math.cos(angle)
                    -displacement[0]*math.sin(angle))/.55*100.)


def audit_circulation(row, original, audit, name):
    current, old = [r['result']['circulation_discretization'] for r in (row, original)]
    audit.equal(name+'.circulation_metadata',
                {k:v for k,v in current.items() if k != 'coefficients'},
                {k:v for k,v in old.items() if k != 'coefficients'}, atol=0, rtol=0)
    audit.check(name+'.pointwise_circulation', all(b['representation'] == 'pointwise' for b in current['beams']))
    count = 2*row['specification']['intervals_per_half']
    # Frozen input reference chord is .1 m. StaticNetwork nondimensionalizes
    # its final circulation block by speed*reference chord (network.py:174,221).
    gamma = [v*row['specification']['speed_m_s']*.1 for v in row['state'][-count:]]
    audit.equal(name+'.raw_circulation', current['coefficients'], gamma, group='raw_circulation')
    audit.equal(name+'.strip_circulation', [s['circulation'] for s in row['result']['strips']],
                gamma, group='raw_circulation')


def percent(change, reference):
    return None if change is None or reference is None or reference == 0 else 100.*change/reference


def differences(values, reference):
    return {q:None if reference[q] is None else values[q]-reference[q] for q in QUANTITIES}


def comparisons(entries, candidate, baseline, baseline_entries, measurements, controls, tags):
    output = []
    for entry in entries:
        spec = entry['specification']
        identity = key(spec)
        r, alpha, speed = identity
        old = recover(baseline[identity], baseline[r, 0., 0.], alpha)
        refs = [{q:lookup.get((alpha, speed, 'twist_deg' if q == 'twist_deg'
                               else 'displacement_percent_semispan')) for q in QUANTITIES}
                for lookup in (measurements, controls)]
        old_error = differences(old, refs[0])
        row = dict(index=entry['index'], **spec, status=entry['status'],
                   baseline_index=baseline_entries[identity]['index'], baseline=old,
                   experiment=refs[0], primary_beam_control=refs[1],
                   source_region=tags[alpha, speed]['tag'], baseline_error=old_error,
                   baseline_error_percent_of_measurement={q:percent(old_error[q], refs[0][q]) for q in QUANTITIES},
                   baseline_error_primary_beam_control=differences(old, refs[1]))
        if identity in candidate:
            new = recover(candidate[identity], baseline[r, 0., 0.], alpha)
            change = differences(new, old)
            row.update(candidate=new, candidate_minus_baseline=change,
                       candidate_change_percent={q:percent(change[q], old[q]) for q in QUANTITIES})
            for ref, label, error_key in ((refs[0], 'measurement', 'candidate_error'),
                                         (refs[1], 'primary_beam_control', 'candidate_error_primary_beam_control')):
                error = differences(new, ref)
                row[error_key] = error
                row['candidate_error_percent_of_'+label] = {q:percent(error[q], ref[q]) for q in QUANTITIES}
        output.append(row)
    return output


def mesh_pairs(rows):
    lookup = {key(r):r for r in rows}
    output = []
    for alpha, speed in POINTS:
        row = dict(alpha_deg=alpha, speed_m_s=speed, status='unavailable')
        coarse, fine = [lookup.get((r, alpha, speed)) for r in (2, 4)]
        if coarse and fine and coarse['status'] == fine['status'] == 'computed':
            row['status'] = 'computed'
            for model in ('baseline', 'candidate'):
                changes = differences(fine[model], coarse[model])
                ratios = {q:None if fine[model][q] == 0 else changes[q]/fine[model][q] for q in QUANTITIES}
                value = ratios['displacement_percent_semispan']
                row[model] = dict(fine_minus_coarse=changes, relative_to_fine=ratios,
                    displacement_within_one_percent=None if value is None else abs(value) <= .01)
        output.append(row)
    return output


def audit_csv(path, rows, audit, pins):
    pins.append(SAVED.pin(path))
    fields = ['intervals_per_half','alpha_deg','speed_m_s','status','quantity','baseline','candidate',
              'candidate_minus_baseline','candidate_change_percent','experiment',
              'baseline_error','candidate_error','primary_beam_control',
              'baseline_error_primary_beam_control','candidate_error_primary_beam_control']
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        audit.check('csv.header', reader.fieldnames == fields)
        actual = list(reader)
    expected = [(row, q) for row in rows for q in QUANTITIES]
    audit.check('csv.row_count', len(actual) == len(expected))
    for i, (current, (row, q)) in enumerate(zip(actual, expected)):
        values = {**{k:row[k] for k in fields[:4]}, 'quantity':q,
                  **{k:row.get(k, {}).get(q) for k in fields[5:]}}
        for field, value in values.items():
            if isinstance(value, str) or value is None:
                audit.check(f'csv.{i}.{field}', current[field] == ('' if value is None else value))
            else:
                audit.equal(f'csv.{i}.{field}', float(current[field]), value, group='csv')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--baseline-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--report-csv', type=Path)
    parser.add_argument('--source-review', type=Path)
    args = parser.parse_args()
    if args.report_csv and not args.report:
        parser.error('--report-csv requires --report')
    audit, pins = SAVED.Audit(), [SAVED.pin(Path(__file__)), SAVED.pin(HELPER)]
    plan = load_json(args.run/'plan.json', pins)
    manifest = load_json(args.run/'manifest.json', pins)
    baseline_path = ROOT/'docs/validation/isae-ae1-sweep.json'
    baseline = load_json(baseline_path, pins)
    pilot = load_json(ROOT/'docs/validation/isae-ae1-pilot.json', pins)
    audit.check('saved_only.no_production_import', 'numpy' not in sys.modules and 'openswing' not in sys.modules)
    audit.check('plan.identity', digest(json.dumps({k:v for k,v in plan.items() if k != 'identity'},
                                                  sort_keys=True).encode()) == plan['identity'])
    audit.equal('plan.specifications', plan['specifications'], specifications(), atol=0, rtol=0)
    audit.equal('plan.gates', plan['gates'], GATES, atol=0, rtol=0)
    audit.equal('plan.conditions', plan['conditions'], baseline['plan']['conditions'], atol=0, rtol=0)
    audit.equal('plan.path', plan['path'], baseline['plan']['path'])
    audit.check('baseline.completed', baseline['execution']['status'] == 'completed')
    audit.check('plan.baseline_identity', plan['baseline_identity'] == baseline['execution']['identity'])
    audit.equal('plan.candidate', plan['candidate'], dict(field='dCLda', baseline=6.1185, value=2*math.pi,
        relative_change=2*math.pi/6.1185-1, changed_table_tokens=2), atol=0, rtol=0)
    for field, expected in (('requested_new_states',6), ('requested_baseline_reuse',8),
                            ('per_state_seconds_limit',120), ('batch_seconds_limit',600),
                            ('experimental_acceptance_threshold',None), ('stability_computed',False)):
        audit.equal('plan.'+field, plan[field], expected, atol=0, rtol=0)
    expected_pins = {**baseline['plan']['source_sha256'],
        str(baseline_path.relative_to(ROOT)):SAVED.pin(baseline_path)['sha256'],
        'scripts/compare-isae-ae1-section.py':SAVED.pin(ROOT/'scripts/compare-isae-ae1-section.py')['sha256']}
    audit.equal('plan.exact_frozen_dependencies', plan['source_sha256'], expected_pins, atol=0, rtol=0)
    for relative, expected in plan['source_sha256'].items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Frozen dependency is not a safe repository-relative path.')
        actual = SAVED.pin(ROOT/path)
        pins.append(actual)
        audit.check('source_pin.'+relative, actual['sha256'] == expected)
    if args.source_review:
        review = load_json(args.source_review, pins)
        audit.equal('plan.source_review', plan['source_review'], review, atol=0, rtol=0)
        audit.check('plan.source_review_sha256', SAVED.pin(args.source_review)['sha256'] == plan['source_review_sha256'])
    paths = SAVED.SourcePaths(baseline['plan'], pilot)
    measurements, controls, tables = SAVED.read_reference_tables(pilot, audit, pins, paths)
    SAVED.audit_plan_tables(baseline['plan'], tables, audit)
    wanted = {key(s) for s in specifications()} | {(2, 0., 0.), (4, 0., 0.)}
    selected = [e for e in baseline['states'] if key(e['specification']) in wanted]
    audit.check('baseline.exact_eight', len(selected) == len(wanted) == 8)
    baseline_entries = {key(e['specification']):e for e in selected}
    baseline_rows, baseline_observations, diagnostics = {}, {}, []
    pilot_rows = {key(r['specification']):r for r in pilot['states']}
    for entry in selected:
        identity = key(entry['specification'])
        name = 'baseline.'+str(identity)
        row = load_raw(args.baseline_run, entry, audit, pins, name)
        audit.check(name+'.computed', row['status'] == 'computed')
        audit.equal(name+'.exact_pilot_copy', row, pilot_rows[identity], atol=0, rtol=0)
        own, diagnostic = SAVED.audit_state(row, baseline['plan'], audit, name)
        baseline_rows[identity], baseline_observations[identity] = row, own
        diagnostics.append(dict(model='baseline', **diagnostic))
    audit.check('fixtures.count', len(plan['fixtures']) == 2)
    mutations = []
    for refinement in (2, 4):
        fixture = next(f for f in plan['fixtures'] if f['refinement'] == refinement)
        old = baseline_rows[refinement, 0., 0.]
        name = 'fixture.'+str(refinement)
        audit.check(name+'.baseline_source_pin', fixture['baseline_source_sha256'] == old['source_sha256'])
        audit.check(name+'.candidate_source_pin', digest(fixture['source'].encode()) == fixture['source_sha256'])
        audit.equal(name+'.mesh', fixture['panels'], old['panels'], atol=0, rtol=0)
        mutations.append(dict(refinement=refinement,
            changes=audit_mutation(old['source'], fixture['source'], audit, name)))
    entries = manifest['states']
    audit.check('manifest.identity', manifest['identity'] == plan['identity'])
    audit.check('manifest.terminal', manifest['status'] != 'running')
    audit.equal('manifest.requested', manifest['requested'], 6, atol=0, rtol=0)
    audit.equal('manifest.recorded', manifest['recorded'], len(entries), atol=0, rtol=0)
    counts = {status:sum(e['status'] == status for e in entries) for status in ('computed','failed','unrun')}
    for status, count in counts.items():
        audit.equal('manifest.'+status, manifest[status], count, atol=0, rtol=0)
    complete = manifest['final_provenance_verified'] and len(entries) == 6 and counts['computed'] == 6
    expected_status = ('completed' if complete else 'completed_with_failures'
        if manifest['final_provenance_verified'] and len(entries) == 6 and counts['unrun'] == 0 else 'incomplete')
    audit.check('manifest.status_matches_records', manifest['status'] == expected_status)
    if manifest['final_provenance_verified']:
        audit.check('manifest.no_fatal_error', manifest['fatal_error'] is None)
    seen, observations, unavailable = set(), {}, []
    for i, entry in enumerate(entries):
        name = f'candidate.{i:03d}'
        audit.equal(name+'.index', entry['index'], i, atol=0, rtol=0)
        audit.equal(name+'.expected_specification', entry['specification'], specifications()[i], atol=0, rtol=0)
        identity = key(entry['specification'])
        audit.check(name+'.unique', identity not in seen)
        seen.add(identity)
        row = load_raw(args.run, entry, audit, pins, name)
        audit.check(name+'.identity', row['identity'] == plan['identity'])
        audit.check(name+'.known_status', row['status'] in counts)
        if row['status'] != 'computed':
            audit.check(name+'.no_observable', 'observable' not in row and 'result' not in row)
            unavailable.append(dict(specification=row['specification'], status=row['status'],
                                    reason=row.get('reason', row.get('error'))))
            continue
        old = baseline_rows[identity]
        audit.equal(name+'.unchanged_panels', row['panels'], old['panels'], atol=0, rtol=0)
        fixture = next(f for f in plan['fixtures'] if f['refinement'] == identity[0])
        audit.equal(name+'.fixture_text', row['source'], fixture['source'], atol=0, rtol=0)
        for field in ('analysis','circulation_solver','aerodynamic_lag',
                      'ground_plane','mach','reference_flow','atmosphere','mesh_discretization','gravity_source'):
            audit.equal(name+'.unchanged_result_setting.'+field, row['result'][field], old['result'][field], atol=0, rtol=0)
        audit_circulation(row, old, audit, name)
        own, diagnostic = SAVED.audit_state(row, plan, audit, name)
        observations[identity] = own
        diagnostics.append(dict(model='candidate', **diagnostic))
    for spec in specifications():
        if key(spec) not in seen:
            unavailable.append(dict(specification=spec, status='missing', reason='No saved request record.'))
    tags = {(t['alpha_deg'], t['speed_m_s']):t for t in baseline['source_scope']['coordinate_tags']}
    rows = comparisons(entries, observations, baseline_observations, baseline_entries, measurements, controls, tags)
    mesh = mesh_pairs(rows)
    result_counts = dict(new_states_requested=6, baseline_states_reused=8,
        unique_operating_points=3, unique_measured_values=6, mesh_pairs_requested=3,
        candidate_displacement_mesh_passes=sum(m.get('candidate',{}).get('displacement_within_one_percent') is True for m in mesh),
        candidate_displacement_mesh_failures=sum(m.get('candidate',{}).get('displacement_within_one_percent') is False for m in mesh),
        candidate_displacement_mesh_unavailable=sum(m.get('candidate',{}).get('displacement_within_one_percent') is None for m in mesh))
    if args.report:
        report = load_json(args.report, pins)
        for field, expected in (('plan',plan), ('execution',{k:v for k,v in manifest.items() if k != 'states'}),
                                ('states',entries), ('baseline_states',selected), ('source_tables',baseline['source_tables'])):
            audit.equal('report.'+field, report[field], expected, atol=0, rtol=0)
        audit.equal('report.comparisons', report['comparisons'], rows, group='reduction')
        audit.equal('report.mesh', report['mesh'], mesh, group='mesh_reduction')
        audit.equal('report.counts', report['counts'], result_counts, atol=0, rtol=0)
        for field, expected in (('experimental_acceptance_threshold',None), ('stability_computed',False), ('coverage_promoted',False)):
            audit.equal('report.'+field, report[field], expected, atol=0, rtol=0)
        reducer = SAVED.pin(ROOT/'scripts/summarize-isae-ae1-section.py')
        pins.append(reducer)
        audit.check('report.reducer_pin', report['reducer_sha256'] == reducer['sha256'])
    if args.report_csv:
        audit_csv(args.report_csv, rows, audit, pins)
    passed = not audit.failures
    output = dict(schema='openswing-isae-ae1-section-audit-v1', passed=passed,
        checks=audit.count, failures=audit.failures, maximum_reconstruction_errors=audit.errors,
        complete=bool(complete), numerical_gates_passed=bool(passed and complete
            and result_counts['candidate_displacement_mesh_passes'] == 3), counts=result_counts,
        fixture_mutations=mutations, baseline_reused=selected, comparisons=rows, mesh=mesh,
        diagnostics=diagnostics, unavailable=unavailable, provenance=pins,
        experimental_acceptance_threshold=None, stability_computed=False, coverage_promoted=False,
        scope='Saved-only independent raw pose, material-tip observable, load-sum, symmetry, input-token, '
              'mesh, provenance and reduction audit. Stored fresh residuals are checked, not reevaluated. '
              'Improved experimental agreement is not required to pass numerical gates.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k:output[k] for k in ('passed','checks','failures','complete','numerical_gates_passed','counts')}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
