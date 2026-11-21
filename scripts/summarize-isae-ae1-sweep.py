"""Saved-only reduction of the full AE-1 sweep, including missing/failed rows."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
QUANTITIES = ('displacement_percent_semispan', 'twist_deg', 'wind_normal_displacement_percent_semispan')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def relative(value, denominator):
    return None if denominator is None or denominator == 0 or value is None else value/denominator


def stats(rows, reference, quantity):
    errors = [row['predicted'][quantity]-row[reference][quantity] for row in rows
              if row['status']=='computed' and row[reference][quantity] is not None]
    return dict(count=len(errors), bias=sum(errors)/len(errors) if errors else None,
                rmse=math.sqrt(sum(e*e for e in errors)/len(errors)) if errors else None,
                maximum_absolute_error=max(map(abs, errors), default=None))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--source-scope', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((args.run/'plan.json').read_text())
    manifest = json.loads((args.run/'manifest.json').read_text())
    assert manifest['status'] != 'running', 'Do not summarize an active run.'
    for name, digest in plan['source_sha256'].items():
        assert sha(ROOT/name) == digest, 'Changed frozen dependency: '+name
    source_scope = json.loads(args.source_scope.read_text())
    tables = plan['source_tables']
    lookup = {}
    for table in tables:
        path = Path(table['source_pin']['path'])
        assert sha(path) == table['source_pin']['sha256']
        for row in table['values']:
            lookup[table['alpha_deg'], row[0], table['reference'], table['quantity']] = row[1]
    # All processed experimental finite coordinates were requested, including
    # those whose measured response may be oscillatory. Labels qualify the
    # experiment; they never turn a converged static root into a stability test.
    tags = {(row['alpha_deg'], row['speed_m_s']):row for row in source_scope['coordinate_tags']}
    assert len(tags) == 92 and all(row['formal_stability_classification'] is None for row in tags.values())
    def region(alpha, speed):
        return tags[alpha, speed]['tag']
    baseline = {r['specification']['refinement']:r['observable'] for r in manifest['states']
                if r['specification']['speed_m_s']==0 and r['status']=='computed'}
    comparisons = []
    for row in manifest['states']:
        spec = row['specification']
        if spec['speed_m_s']==0:
            continue
        alpha, speed = spec['alpha_deg'], spec['speed_m_s']
        references = {}
        for name, reference in [('experiment', 'experiment'), ('primary_beam_control', 'UM/NAST-VLM')]:
            references[name] = {key:lookup.get((alpha, speed, reference, 'twist' if key=='twist_deg' else 'displacement'))
                                for key in QUANTITIES}
        entry = dict(index=row['index'], **spec, status=row['status'], source_region=region(alpha, speed), **references)
        if row['status']=='computed' and spec['refinement'] in baseline:
            base, current = baseline[spec['refinement']], row['observable']
            delta = [p-q for p, q in zip(current['midchord_m'], base['midchord_m'])]
            angle = math.radians(alpha)
            prediction = dict(displacement_percent_semispan=100*delta[2]/.55,
                twist_deg=current['projected_twist_deg']-base['projected_twist_deg'],
                wind_normal_displacement_percent_semispan=100*(-math.sin(angle)*delta[0]+math.cos(angle)*delta[2])/.55)
            entry['predicted'] = prediction
            for name, label in [('experiment', 'measurement'), ('primary_beam_control', 'primary_beam_control')]:
                error = {k:prediction[k]-references[name][k] if references[name][k] is not None else None for k in QUANTITIES}
                entry['error' if name=='experiment' else 'error_primary_beam_control'] = error
                entry['error_percent_of_'+label] = {k:None if relative(error[k], references[name][k]) is None else
                                                    100*relative(error[k], references[name][k]) for k in QUANTITIES}
        elif row['status']=='computed':
            entry.update(status='baseline_unavailable', reason='No successful same-mesh zero-flow baseline.')
        comparisons.append(entry)
    mesh = []
    coordinates = sorted({(row['alpha_deg'], row['speed_m_s']) for row in comparisons})
    indexed = {(r['refinement'], r['alpha_deg'], r['speed_m_s']):r for r in comparisons}
    for alpha, speed in coordinates:
        coarse, fine = [indexed.get((r, alpha, speed)) for r in (2, 4)]
        entry = dict(alpha_deg=alpha, speed_m_s=speed, source_region=region(alpha,speed), status='unavailable')
        if coarse and fine and coarse['status']==fine['status']=='computed':
            delta = {k:fine['predicted'][k]-coarse['predicted'][k] for k in QUANTITIES}
            ratios = {k:relative(delta[k], fine['predicted'][k]) for k in QUANTITIES}
            gate = ratios['displacement_percent_semispan']
            entry.update(status='computed', fine_minus_coarse=delta, relative_to_fine=ratios,
                         displacement_within_one_percent=None if gate is None else abs(gate)<=.01)
        mesh.append(entry)
    statistics = []
    for refinement in (2, 4):
        for alpha in (5, 7):
            selected = [r for r in comparisons if r['refinement']==refinement and r['alpha_deg']==alpha]
            for label, rows in [('all_exported', selected)]+[
                    (group, [r for r in selected if r['source_region']==group]) for group in sorted({r['source_region'] for r in selected})]:
                statistics.append(dict(refinement=refinement, alpha_deg=alpha, source_region=label,
                    requested=len(rows), computed=sum(r['status']=='computed' for r in rows),
                    experiment={k:stats(rows, 'experiment', k) for k in QUANTITIES},
                    primary_beam_control={k:stats(rows, 'primary_beam_control', k) for k in QUANTITIES}))
    report = dict(schema='openswing-isae-ae1-sweep-v1', plan=plan,
        execution={k:v for k,v in manifest.items() if k!='states'}, states=manifest['states'],
        source_tables=tables, comparisons=comparisons, mesh=mesh, statistics=statistics,
        source_scope=source_scope, source_scope_sha256=sha(args.source_scope),
        source_region_note='Source-derived location relative to reported instability evidence; below a reported feature is not a certified stable region.',
        displacement_axis_status='Unresolved processed experimental axes. Root-normal and wind-normal are alternatives for the same measured displacement.',
        experimental_acceptance_threshold=None, stability_computed=False,
        reducer_sha256=sha(Path(__file__)),
        counts=dict(requested_states=186, requested_loaded_states=184, unique_measured_coordinates=92,
                    unique_measured_values=184, requested_mesh_pairs=92,
                    passing_displacement_mesh_pairs=sum(r.get('displacement_within_one_percent') is True for r in mesh),
                    failing_displacement_mesh_pairs=sum(r.get('displacement_within_one_percent') is False for r in mesh),
                    unavailable_displacement_mesh_pairs=sum(r.get('displacement_within_one_percent') is None for r in mesh)))
    write(DEST/'isae-ae1-sweep.json', report)
    with (DEST/'isae-ae1-sweep.csv').open('w',newline='') as stream:
        fields=['intervals_per_half','alpha_deg','speed_m_s','source_region','status','quantity',
                'predicted','experiment','error','error_percent_of_measurement','primary_beam_control']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in comparisons:
            for quantity in QUANTITIES:
                writer.writerow({**{k:row[k] for k in fields[:5]}, 'quantity':quantity,
                                 **{k:row.get(k,{}).get(quantity) for k in fields[6:]}})
    print(json.dumps(dict(execution=report['execution'], counts=report['counts'],
                         fine_statistics=[r for r in statistics if r['refinement']==4 and r['source_region']=='all_exported']),indent=2))


if __name__ == '__main__':
    main()
