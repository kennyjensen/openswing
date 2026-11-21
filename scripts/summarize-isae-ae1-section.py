"""Reduce the six saved slope-diagnostic states; no physics imports or calls."""
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


def percentage(change, reference):
    return None if reference == 0 or reference is None else 100*change/reference


def recover(current, base, alpha):
    delta = [a-b for a, b in zip(current['midchord_m'], base['midchord_m'])]
    a = math.radians(alpha)
    return dict(displacement_percent_semispan=100*delta[2]/.55,
        twist_deg=current['projected_twist_deg']-base['projected_twist_deg'],
        wind_normal_displacement_percent_semispan=100*(-math.sin(a)*delta[0]+math.cos(a)*delta[2])/.55)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    plan = json.loads((args.run/'plan.json').read_text())
    execution = json.loads((args.run/'manifest.json').read_text())
    assert execution['status'] != 'running'
    for name, digest in plan['source_sha256'].items():
        assert sha(ROOT/name) == digest, 'Changed frozen dependency: '+name
    baseline = json.loads((DEST/'isae-ae1-sweep.json').read_text())
    assert baseline['execution']['identity'] == plan['baseline_identity']
    key = lambda spec:(spec['refinement'], spec['alpha_deg'], spec['speed_m_s'])
    selected = {key(s) for s in plan['specifications']} | {(2,0.,0.), (4,0.,0.)}
    saved = [r for r in baseline['states'] if key(r['specification']) in selected]
    assert len(saved) == 8 and all(r['status']=='computed' for r in saved)
    zero = {r['specification']['refinement']:r['observable'] for r in saved
            if r['specification']['speed_m_s']==0}
    baseline_comparisons = {key(r):r for r in baseline['comparisons'] if key(r) in selected}
    comparisons = []
    for row in execution['states']:
        spec = row['specification']
        old = baseline_comparisons[key(spec)]
        entry = dict(index=row['index'], **spec, status=row['status'],
            baseline_index=old['index'], baseline=old['predicted'], experiment=old['experiment'],
            primary_beam_control=old['primary_beam_control'], source_region=old['source_region'],
            baseline_error=old['error'], baseline_error_percent_of_measurement=old['error_percent_of_measurement'],
            baseline_error_primary_beam_control=old['error_primary_beam_control'])
        if row['status']=='computed':
            candidate = recover(row['observable'], zero[spec['refinement']], spec['alpha_deg'])
            delta = {q:candidate[q]-old['predicted'][q] for q in QUANTITIES}
            entry.update(candidate=candidate, candidate_minus_baseline=delta,
                         candidate_change_percent={q:percentage(delta[q],old['predicted'][q]) for q in QUANTITIES})
            for reference, label in [('experiment','measurement'), ('primary_beam_control','primary_beam_control')]:
                error = {q:None if old[reference][q] is None else candidate[q]-old[reference][q] for q in QUANTITIES}
                entry['candidate_error' if reference=='experiment' else 'candidate_error_primary_beam_control'] = error
                entry['candidate_error_percent_of_'+label] = {
                    q:None if error[q] is None else percentage(error[q],old[reference][q]) for q in QUANTITIES}
        comparisons.append(entry)
    mesh = []
    for alpha, speed in ((5.,30.),(5.,40.),(7.,30.)):
        rows = [next((r for r in comparisons if key(r)==(ref,alpha,speed)),None) for ref in (2,4)]
        entry = dict(alpha_deg=alpha,speed_m_s=speed,status='unavailable')
        if all(r and r['status']=='computed' for r in rows):
            entry['status']='computed'
            for model in ('baseline','candidate'):
                coarse, fine = [r[model] for r in rows]
                changes = {q:fine[q]-coarse[q] for q in QUANTITIES}
                ratios = {q:None if fine[q]==0 else changes[q]/fine[q] for q in QUANTITIES}
                value = ratios['displacement_percent_semispan']
                entry[model] = dict(fine_minus_coarse=changes, relative_to_fine=ratios,
                    displacement_within_one_percent=None if value is None else abs(value)<=.01)
        mesh.append(entry)
    report = dict(schema='openswing-isae-ae1-section-v1', plan=plan,
        execution={k:v for k,v in execution.items() if k!='states'}, states=execution['states'],
        baseline_states=saved, comparisons=comparisons, mesh=mesh,
        source_tables=baseline['source_tables'], experimental_acceptance_threshold=None,
        stability_computed=False, coverage_promoted=False,
        reducer_sha256=sha(Path(__file__)),
        zero_flow_reuse='The two baseline no-airflow equations contain no aerodynamic section slope, so their exact saved states are reused.',
        scope=plan['scope'], counts=dict(new_states_requested=6, baseline_states_reused=8,
            unique_operating_points=3, unique_measured_values=6, mesh_pairs_requested=3,
            candidate_displacement_mesh_passes=sum(r.get('candidate',{}).get('displacement_within_one_percent') is True for r in mesh),
            candidate_displacement_mesh_failures=sum(r.get('candidate',{}).get('displacement_within_one_percent') is False for r in mesh),
            candidate_displacement_mesh_unavailable=sum(r.get('candidate',{}).get('displacement_within_one_percent') is None for r in mesh)))
    (DEST/'isae-ae1-section.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    fields=['intervals_per_half','alpha_deg','speed_m_s','status','quantity','baseline','candidate',
            'candidate_minus_baseline','candidate_change_percent','experiment',
            'baseline_error','candidate_error','primary_beam_control',
            'baseline_error_primary_beam_control','candidate_error_primary_beam_control']
    with (DEST/'isae-ae1-section.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in comparisons:
            for quantity in QUANTITIES:
                writer.writerow({**{k:row[k] for k in fields[:4]},'quantity':quantity,
                                 **{k:row.get(k,{}).get(quantity) for k in fields[5:]}})
    print(json.dumps(dict(execution=report['execution'],counts=report['counts'],
                         fine=[r for r in comparisons if r['refinement']==4],mesh=mesh),indent=2))


if __name__ == '__main__':
    main()
