"""Reduce the fixed AE-1 pilot and published observations; never run physics."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    plan = json.loads((args.run/'plan.json').read_text())
    execution = json.loads((args.run/'execution.json').read_text())
    assert execution['status'] == 'completed' and execution['completed'] == 8
    for name, digest in plan['source_sha256'].items():
        assert sha(ROOT/name) == digest, 'Changed pilot dependency: '+name
    states = [json.loads((args.run/name).read_text()) for name in execution['outputs']]
    assert all(row['status'] == 'computed' and row['identity'] == plan['identity'] for row in states)
    readiness = json.loads((DEST/'isae-ae1-source-readiness.json').read_text())
    measurements = []
    observed = {}
    controls = []
    modeled = {}
    for entry in readiness['measured_conditions']['measurement_records']:
        path = Path(entry['source']['path'])
        assert sha(path) == entry['source']['sha256']
        alpha = int(re.search(r'aoa(\d+)', path.name)[1])
        quantity = 'displacement_percent_semispan' if '_disp_' in path.name else 'twist_deg'
        values = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            speed, value = map(float, line.split())
            assert math.isfinite(speed)
            values.append([speed, value if math.isfinite(value) else None])
            if math.isfinite(value):
                observed[alpha, speed, quantity] = value
        measurements.append(dict(alpha_deg=alpha, quantity=quantity,
                                 source_path=str(path.relative_to(ROOT)), sha256=sha(path),
                                 primary_url=entry['primary_url'], values=values))
    for entry in readiness['provenance_pins']:
        path = Path(entry['path'])
        if path.parent.name != '02_Beam':
            continue
        assert sha(path) == entry['sha256']
        alpha = int(re.search(r'aoa(\d+)', path.name)[1])
        quantity = 'displacement_percent_semispan' if '_disp_' in path.name else 'twist_deg'
        rows = [list(map(float, line.split())) for line in path.read_text().splitlines() if line.strip()]
        for row in rows:
            assert all(math.isfinite(v) for v in row)
            modeled[alpha, row[0], quantity] = row[1]
        controls.append(dict(alpha_deg=alpha, quantity=quantity, reference='primary UM/NAST-VLM control',
                             source_path=str(path.relative_to(ROOT)), sha256=sha(path), values=rows))
    baselines = {r['specification']['refinement']:r['observable'] for r in states
                 if r['specification']['speed_m_s'] == 0}
    comparisons = []
    for row in states:
        spec = row['specification']
        if spec['speed_m_s'] == 0:
            continue
        base = baselines[spec['refinement']]
        output = row['observable']
        predictions = dict(displacement_percent_semispan=(output['midchord_m'][2]-base['midchord_m'][2])/0.55*100,
                           twist_deg=output['projected_twist_deg']-base['projected_twist_deg'])
        alpha = math.radians(spec['alpha_deg'])
        delta = [p-q for p, q in zip(output['midchord_m'], base['midchord_m'])]
        predictions['wind_normal_displacement_percent_semispan'] = (-math.sin(alpha)*delta[0]+math.cos(alpha)*delta[2])/.55*100
        reference = {key:observed[spec['alpha_deg'], spec['speed_m_s'],
                                 'displacement_percent_semispan' if key.startswith('wind_normal') else key]
                     for key in predictions}
        error = {key:predictions[key]-reference[key] for key in predictions}
        relative = {key:100*error[key]/reference[key] if reference[key] != 0 else None for key in predictions}
        control = {key:modeled[spec['alpha_deg'], spec['speed_m_s'],
                              'displacement_percent_semispan' if key.startswith('wind_normal') else key]
                   for key in predictions}
        comparisons.append(dict(**spec, predicted=predictions, experiment=reference,
                                error=error, error_percent_of_measurement=relative,
                                primary_beam_control=control,
                                error_percent_of_primary_beam_control={key:100*(predictions[key]-control[key])/control[key]
                                                                      if control[key] != 0 else None for key in predictions}))
    mesh = []
    for alpha, speed in ((5., 30.), (5., 40.), (7., 30.)):
        coarse, fine = [next(r for r in comparisons if r['alpha_deg']==alpha and r['speed_m_s']==speed
                             and r['refinement']==refinement) for refinement in (2, 4)]
        change = {k:fine['predicted'][k]-coarse['predicted'][k] for k in fine['predicted']}
        relative = {k:change[k]/fine['predicted'][k] if fine['predicted'][k] != 0 else None for k in change}
        mesh.append(dict(alpha_deg=alpha, speed_m_s=speed, fine_minus_coarse=change,
                         relative_to_fine=relative,
                         displacement_within_one_percent=abs(relative['displacement_percent_semispan']) <= .01))
    report = dict(schema='openswing-isae-ae1-pilot-v1', plan=plan, execution=execution,
                  states=states, measurements=measurements, primary_beam_controls=controls,
                  comparisons=comparisons, mesh=mesh,
                  scope='Six coupled conditions and two zero-flow baselines. Explicit mirrored primary-property reconstruction; no fit.',
                  limitations=readiness['specific_unresolved_definitions'],
                  displacement_axis_status='Unresolved processed experimental axes. Root-normal and wind-normal are retained alternatives, not extra independent observations.',
                  experimental_acceptance_threshold=None, coverage_promoted=False,
                  reducer_sha256=sha(Path(__file__)))
    write(DEST/'isae-ae1-pilot.json', report)
    with (DEST/'isae-ae1-pilot.csv').open('w', newline='') as stream:
        fields=['intervals_per_half', 'alpha_deg', 'speed_m_s', 'quantity', 'predicted', 'experiment', 'error', 'error_percent_of_measurement']
        writer=csv.DictWriter(stream, fieldnames=fields);writer.writeheader()
        for row in comparisons:
            for key in row['predicted']:
                writer.writerow({**{k:row[k] for k in fields[:3]}, 'quantity':key,
                                 **{k:row[k][key] for k in fields[4:]}})
    print(json.dumps(dict(comparisons=comparisons, mesh=mesh), indent=2))


if __name__ == '__main__':
    main()
