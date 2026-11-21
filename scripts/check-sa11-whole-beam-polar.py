"""Check saved SA-11 force vectors against literal source coefficients.

Independent scalar reductions, axes and local-Mach calculations. No solver
imports or calls; original printed targets and rejected states stay explicit.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def block_numbers(path, label):
    active = False
    for line in path.read_text().splitlines():
        line = line.split('#')[0].strip()
        if line == label:
            active = True
        elif active and line:
            assert line != 'End' and not line.startswith('*')
            return list(map(float, line.split()))
    raise AssertionError(label)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    folder = parser.parse_args().input.resolve()
    receipt = folder/'verification.json'
    assert not receipt.exists()
    analysis = read(folder/'analysis.json')
    plan = read(folder/'plan.json')
    for name, pin in plan['pins'].items():
        assert sha(ROOT/name) == pin, name
    source = ROOT/'examples/isae-sa11-wingtip-up.asw'
    _, rho, sound = block_numbers(source, 'Constant')
    area, _, _ = block_numbers(source, 'Reference')
    table = next((ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865').glob('1 - Aerodynamics/SA*/SA - 11 - */Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt'))
    # The current plan pins the earlier polar plan, which directly pins the
    # original table. Follow that existing chain; do not invent a new target.
    parent = ROOT/'artifacts/isae/sa11-winglet-polar-20261108/plan.json'
    assert sha(parent) == plan['pins'][str(parent.relative_to(ROOT))]
    assert sha(table) == read(parent)['unchanged_pins'][str(table.relative_to(ROOT))]
    manifest_path = ROOT/'reference/isae-validation/manifest.json'
    manifest = read(manifest_path)
    revision = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
    assert manifest['revision'] == revision
    entry = manifest['files'][str(table.relative_to(manifest_path.parent/revision))]
    content = table.read_bytes()
    assert len(content) == entry['bytes'] and sha(table) == entry['sha256']
    assert hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest() == entry['git_blob_sha1']
    raw = {}
    for line in table.read_text().splitlines():
        fields = line.split()
        if len(fields) == 82 and fields[0].isdigit():
            alpha = float(fields[71])
            if alpha <= 5:
                assert alpha not in raw
                raw[alpha] = fields
    assert len(raw) == len(analysis['cases']) == 21
    errors = dict(CL=0., CD=0., local_mach=0., reported_percent=0., geometry=0.)
    baseline_geometry = None
    roots = []
    for row in analysis['cases']:
        path = ROOT/row['report']
        assert sha(path) == row['report_sha256']
        report = read(path)
        for name, pin in report['artifact_sha256'].items():
            assert sha(path.parent/name) == pin, name
        fields = raw[row['alpha']]
        speed, alpha = float(fields[69]), math.radians(float(fields[71]))
        assert speed == 240 and float(fields[70]) == 0
        reference = dict(CL=float(fields[77]), CD=float(fields[78]))
        assert all(reference[k] == report['reference'][k] for k in reference)
        qS = .5*rho*speed**2*area
        with np.load(path.parent/'whole-new.npz') as d:
            force = [math.fsum(float(x) for x in d['force_terms'][..., k].ravel()) for k in range(3)]
            predicted = dict(CL=(-math.sin(alpha)*force[0]+math.cos(alpha)*force[2])/qS,
                             CD=(math.cos(alpha)*force[0]+math.sin(alpha)*force[2])/qS)
            for key, value in predicted.items():
                errors[key] = max(errors[key], abs(value-row[f'new_formal_{key}']))
                error = 100*(value/reference[key]-1)
                errors['reported_percent'] = max(errors['reported_percent'], abs(error-row['new_formal_errors_percent'][key]))
            mach = []
            for velocity, span in zip(d['velocity'], d['span']):
                dot = math.fsum(float(v)*float(s) for v, s in zip(velocity, span))
                speed2 = math.fsum((float(v)-dot*float(s))**2 for v, s in zip(velocity, span))
                mach.append(math.sqrt(speed2)/sound)
            errors['local_mach'] = max(errors['local_mach'], max(abs(x-y) for x, y in zip(mach, d['mach'])))
            invalid = [i for i, value in enumerate(mach) if value >= 1]
            assert len(invalid) == row['invalid_receivers'] == 2
            assert set(map(int, d['beam'][invalid])) == {2, 3}
            roots.append(dict(alpha=row['alpha'], indices=invalid, beam=list(map(int, d['beam'][invalid])),
                              local_mach=[mach[i] for i in invalid]))
        with np.load(path.parent/'geometry.npz') as g:
            current = {k:g[k].copy() for k in ('a', 'b', 'hv', 'cp')}
            if baseline_geometry is None:
                baseline_geometry = current
            else:
                errors['geometry'] = max(errors['geometry'], *(float(np.max(abs(current[k]-baseline_geometry[k]))) for k in current))
        rejected = read(path.parent/'openswing-rejected.json')
        assert row['production_status'] == rejected['status'] == 'rejected'
        assert rejected['details']['kind'] == 'section_normal_mach'
        assert not (path.parent/'openswing.json').exists()
    assert max(errors['CL'], errors['CD'], errors['local_mach']) < 3e-14, errors
    assert errors['reported_percent'] < 2e-11 and errors['geometry'] == 0., errors
    chunks = sorted(folder.glob('chunk-*.json'))
    covered = []
    for chunk in chunks:
        data = read(chunk)
        assert data['runner_sha256'] == sha(ROOT/'scripts/run-sa11-whole-beam-chunk.py')
        assert data['plan_sha256'] == sha(folder/'plan.json')
        for name, pin in data['reports'].items():
            assert sha(folder/name/'report.json') == pin
        covered.extend(data['indices'])
    assert sorted(covered) == list(range(7, 19))
    result = dict(verified_utc=datetime.now(timezone.utc).isoformat(), cases=21, raw_reference_rows=21,
        source_pins_verified=len(plan['pins']), errors=errors, roots=roots,
        analysis_sha256=sha(folder/'analysis.json'), script_sha256=sha(Path(__file__)),
        original_table_sha256=sha(table), source_manifest_sha256=sha(manifest_path),
        parent_plan_sha256=sha(parent), chunks_verified=len(chunks),
        physical_calls=0, accepted_moments=0, primary_passes_added=0,
        finding='All21 frozen geometries are identical. Independent dimensional force reductions and local-Mach reconstruction agree with saved diagnostics; every production state remains rejected at exactly the two winglet roots.')
    receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('cases', 'raw_reference_rows', 'source_pins_verified', 'errors', 'chunks_verified', 'primary_passes_added')}), flush=True)


if __name__ == '__main__': main()
