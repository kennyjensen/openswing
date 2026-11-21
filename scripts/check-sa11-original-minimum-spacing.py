"""Independently audit saved original SA-11 results; no solver or NumPy import."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/isae/sa11-original-minimum-spacing-20261108'
OLD = ROOT / 'artifacts/isae/sa11-complete-scope-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    signal.alarm(25)
    plan = read(OUT / 'plan.json')
    summary = read(OUT / 'analysis.json')
    previous = {j['id']: j for j in read(OLD / 'plan.json')['jobs']}
    digest = sha(OUT / 'plan.json')
    assert digest == summary['plan_sha256']
    for path, expected in plan['source_sha256'].items():
        assert sha(ROOT / path) == expected, path
    names = ('lift', 'drag', 'CL', 'CD', 'CDi', 'Cm', 'efficiency')
    groups = defaultdict(lambda: dict(passed=0, required=0, computed=0, errors=0, unavailable=0, all_pass=0))
    errors = defaultdict(lambda: defaultdict(list))
    meshes, source_tables, rejected = {}, {}, []
    max_residual = 0.0
    for i, job in enumerate(plan['jobs']):
        assert job == previous[job['id']], job['id']
        path = OUT / 'jobs' / f'{i:04d}' / 'result.json'
        assert sha(path) == summary['result_sha256'][str(path.relative_to(ROOT))]
        r = read(path)
        assert r['job_id'] == job['id'] and r['plan_sha256'] == digest
        strict, scored = r['strict'], r['acceptance']
        group = groups[job['variant']]
        group['required'] += 7
        assert scored['output_accounting']['required'] == 7
        if strict['status'] != 'computed':
            assert scored['output_accounting']['passed'] == 0
            if strict['status'] == 'unsupported':
                assert job['execution_route'] == 'unsupported'
                assert strict['physical_calls'] == 0
                group['unavailable'] += 1
            else:
                assert strict['status'] == 'error' and 'Local section-normal Mach' in strict['error']
                group['errors'] += 1
                rejected.append(dict(id=job['id'], alpha=job['settings']['alpha'], speed=job['settings']['speed']))
            continue
        group['computed'] += 1
        assert strict['physical_calls'] == 1 and strict['numerical_pass'] is True
        assert all(c['passed'] for c in strict['numerical_checks'])
        settings = strict['settings']
        assert {k: v for k, v in settings.items() if k not in ('panels', 'mesh_source')} == {
            k: v for k, v in job['settings'].items() if k not in ('panels', 'mesh_source')}
        mesh = strict['result']['mesh_discretization']
        requested = plan['meshes'][job['model_path']][str(job['settings']['panels'])]
        assert mesh['settings'] == settings['panels'] == requested
        key = f"{job['variant']}:n{job['settings']['panels']}"
        assert meshes.setdefault(key, mesh) == mesh
        for beam in mesh['beams']:
            nodes = beam['nodes']
            assert len(nodes) == beam['panels'] + 1
            assert all(b['s'] - a['s'] >= plan['minimum_spacing'] - 1e-12 for a, b in zip(nodes, nodes[1:]))
        assert sum(b['panels'] for b in mesh['beams']) == strict['result']['panels']
        table = source_tables.setdefault(job['table_path'], (ROOT / job['table_path']).read_text().splitlines())
        tokens = table[job['reference_row']['line_number'] - 1].split()
        assert tokens == job['reference_row']['tokens'] and len(tokens) == 82
        predicted = strict['result']['predicted']
        n_pass = 0
        for col, check in zip(range(75, 82), scored['reference_checks']):
            name = names[col - 75]
            assert check['name'] == name and check['expected_token'] == tokens[col]
            target = float(tokens[col])
            assert abs(target) > 1e-8 and check['expected'] == target
            value = predicted[name]
            assert math.isfinite(value) and value == check['predicted']
            error = abs(value - target) / abs(target)
            passes = abs(value - target) <= max(check['tolerance'], 0.05 * abs(target))
            assert passes == check['passed']
            n_pass += passes
            if not passes:
                errors[job['variant']][name].append(100 * error)
        assert n_pass == scored['output_accounting']['passed']
        group['passed'] += n_pass
        group['all_pass'] += n_pass == 7
        result = strict['result']
        max_residual = max(max_residual, result['residual'])
        force = result['force']
        alpha = math.radians(settings['alpha'])
        lift = -force[0] * math.sin(alpha) + force[2] * math.cos(alpha)
        drag = force[0] * math.cos(alpha) + force[2] * math.sin(alpha)
        qS = 0.5 * settings['density'] * settings['speed']**2 * result['reference'][0][0]
        for name, value in dict(lift=lift, drag=drag, CL=lift/qS, CD=drag/qS,
                                Cm=result['moment_origin'][1]/(qS*result['reference'][0][1])).items():
            assert math.isclose(value, predicted[name], rel_tol=2e-12, abs_tol=2e-12)
    assert len(plan['jobs']) == 1312 and sum(g['required'] for g in groups.values()) == 9184
    assert sum(g['passed'] for g in groups.values()) == summary['passed'] == 1060
    assert sum(g['computed'] for g in groups.values()) == 322
    assert sum(g['errors'] for g in groups.values()) == 6
    assert sum(g['unavailable'] for g in groups.values()) == 984
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), verified=True,
                  groups=dict(groups), rejected=rejected, maximum_residual=max_residual,
                  source_pins_verified=len(plan['source_sha256']), all_original_jobs_identical=True,
                  failed_percent_errors={variant: {name: dict(median=statistics.median(v), minimum=min(v), maximum=max(v))
                    for name, v in quantities.items()} for variant, quantities in errors.items()},
                  mesh_counts={k: [b['panels'] for b in v['beams']] for k, v in meshes.items()},
                  mesh_minimums={k: min(b['s']-a['s'] for beam in v['beams'] for a,b in zip(beam['nodes'],beam['nodes'][1:]))
                    for k, v in meshes.items()},
                  plan_sha256=digest, analysis_sha256=sha(OUT/'analysis.json'), checker_sha256=sha(Path(__file__)))
    with (OUT / 'verification.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    signal.alarm(0)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
