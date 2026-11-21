"""Audit saved ST-5 pilot comparisons without importing the production solver."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL = [*range(1,13),19,20]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(pins):
    for pin in pins:
        p = Path(pin['path'])
        assert p.stat().st_size == pin['bytes'] and sha(p) == pin['sha256'], p


def assess(out):
    study = read(out/'study.json')
    verify(study['pins']); verify(study['source_pins'])
    plan = read(out/'plan.json')
    target_path = Path(plan['target'])
    target = read(target_path)
    references = [(b, r) for b in target['beams'] for r in b['rows']]
    row_count = len(references)
    assert row_count in (58, 80)
    names = [c['name'] for c in target['columns']]
    grids = []
    for level in (0,1):
        folder = out/f'run-{level}'
        receipt = read(folder/'execution.json')
        assert receipt['exit_code'] == 0 and receipt['reaped'] and not receipt['timed_out']
        verify(receipt['outputs']); verify(receipt['retained'])
        packet = read(folder/f'level{level}/comparison.json')
        assert packet['numerical_gates_pass'] and len(packet['rows']) == row_count
        fields = {}
        for row, (block, reference) in zip(packet['rows'], references):
            assert (row['beam'],row['source_line']) == (block['beam'],reference['source_line'])
            assert row['expected'] == reference['physical']
            half = [float(Decimal(10)**Decimal(Decimal(token).as_tuple().exponent))/2*scale
                    for token,scale in zip(reference['raw_tokens'],block['physical_multipliers'])]
            assert row['half_last_place'] == half
            for j in range(28):
                assert row['difference'][j] == row['values'][j]-row['expected'][j]
                assert row['inside_printed_interval'][j] == (abs(row['difference'][j]) <= half[j])
        for j in range(1,28):
            rows = packet['rows']
            errors = [100*abs(r['difference'][j])/abs(r['expected'][j]) for r in rows if r['expected'][j]]
            failed = [dict(beam=r['beam'], source_line=r['source_line'],
                          expected=r['expected'][j], actual=r['values'][j],
                          half_last_place=r['half_last_place'][j]) for r in rows
                      if abs(r['difference'][j]) > .05*abs(r['expected'][j])+r['half_last_place'][j]]
            envelope = max(abs(r['expected'][j]) for r in rows)
            absolute = max(abs(r['difference'][j]) for r in rows)
            fields[names[j]] = dict(passed=row_count-len(failed), required=row_count,
                strict=sum(r['inside_printed_interval'][j] for r in rows),
                median_nonzero_error_percent=statistics.median(errors) if errors else None,
                maximum_nonzero_error_percent=max(errors) if errors else None,
                max_absolute_error=absolute,
                max_error_percent_of_reference_envelope=100*absolute/envelope if envelope else None,
                failures=failed)
        tips = []
        for beam in (b['beam'] for b in target['beams']):
            r = max((r for r in packet['rows'] if r['beam']==beam),key=lambda r:r['t_evaluated'])
            tips.append(dict(beam=beam, quantities={names[j]:dict(
                actual=r['values'][j],reference=r['expected'][j],
                error_percent=100*abs(r['difference'][j])/abs(r['expected'][j])) for j in (3,5)}))
        grids.append(dict(level=level, intervals=packet['intervals_by_beam'],
            passed=sum(fields[names[j]]['passed'] for j in STRUCTURAL), required=14*row_count,
            strict=sum(fields[names[j]]['strict'] for j in STRUCTURAL),
            fields=fields, positive_tips=tips, physical=packet['checks'],
            solve_seconds=packet['seconds'], job_seconds=receipt['elapsed_seconds'],
            peak_rss_kib=receipt['peak_child_rss_kib']))
    comparisons = [read(out/f'run-{i}/level{i}/comparison.json') for i in (0,1)]
    mesh = {}
    for k,j in enumerate(STRUCTURAL):
        a = [r['structural_deformation'][k] for r in comparisons[0]['rows']]
        b = [r['structural_deformation'][k] for r in comparisons[1]['rows']]
        change = max(abs(x-y) for x,y in zip(a,b))
        envelope = max(map(abs,b))
        ratio = change/envelope if envelope else (0 if change==0 else None)
        mesh[names[j]] = dict(relative_change=ratio,
            passed=ratio is not None and ratio <= plan['numerical_gates']['fine_structural_mesh_relative'])
    summary = read(out/'run-1/summary.json')
    for name, item in mesh.items():
        assert item['relative_change'] == summary['mesh_changes'][0]['measures'][name]['relative_change']
        assert item['passed'] == summary['mesh_changes'][0]['measures'][name]['passes']
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        assessment_script_sha256=sha(Path(__file__)), study_sha256=sha(out/'study.json'),
        target_sha256=sha(target_path), grids=grids, mesh=mesh,
        mesh_passed=sum(v['passed'] for v in mesh.values()),mesh_required=14,
        meshes_are_independent_targets=False, primary_votes_added=0,
        family_validated=False, production_changes=False,
        acceptance='5% relative plus the original printed half-last-place; strict counts remain separate.',
        limitations=['Two meshes of one original static snapshot only; literal joint type retained.',
            'Historical exact node coordinates and exporter source unavailable.',
            'Unresolved f_reac scalar display excluded from structural match counts.',
            'Paper ST-5.B modified in-plane link is not the archive type2 roller.'])
    path = out/'assessment.json'
    assert not path.exists()
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(grids=[{k:g[k] for k in ('level','passed','required','strict','solve_seconds')}
                               for g in grids], mesh_passed=result['mesh_passed'],
                         mesh_required=14,primary_votes_added=0)))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    assess(parser.parse_args().output.resolve())
