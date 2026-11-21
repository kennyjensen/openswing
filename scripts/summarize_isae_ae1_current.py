"""Audit bounded AE-1 results without importing the production solver."""
from datetime import datetime, timezone
import hashlib
import json
from statistics import median
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_ae1 as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.replay_isae_ae1_bounded import checked_result


def read(path):
    return json.loads(path.read_text())


def main(out):
    plan = read(out/'plan.json')
    interior = read(out/'interior-plan.json')
    ids = plan['selected'] + interior['selected']
    assert len(ids) == len(set(ids))
    pins = {}
    jobs, results, rows, receipts = [], {}, [], []
    for identifier in ids:
        folder = out/identifier
        job, raw = read(folder/'job.json'), read(folder/'strict-result.json')
        assert job['id'] == identifier
        for pin in job['source_pins'] + job['kernel_pins'] + raw.get('artifact_files', []):
            path = Path(pin['path'])
            if str(path) not in pins:
                pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            assert pins[str(path)] == pin['sha256'], str(path)
        strict = checked_result(job, raw)
        assert strict['status'] in ('computed', 'unsupported'), strict
        view = apply_reference_acceptance(strict, relative_tolerance=.05)
        assert view['output_accounting']['required'] == 6
        if strict['status'] == 'computed':
            snapshot = read(Path(raw['artifact_directory'])/'result.json')
            recovered = adapter.sensor_values(snapshot['sensors'])
            assert snapshot['converged']
            assert len(strict['physical_checks']) == 29
            assert all(c['passed'] for c in strict['physical_checks'])
            assert all(c['predicted'] == recovered[c['name']] for c in strict['reference_checks'])
            receipts.append(read(folder/'receipt.json'))
        else:
            assert strict['physical_calls'] == 0
            assert all(c['predicted'] is None for c in strict['reference_checks'])
        for check in view['reference_checks']:
            error = (100*abs(check['predicted']-check['expected'])/abs(check['expected'])
                     if check['predicted'] is not None and check['expected'] else None)
            rows.append(dict(job=identifier, alpha=job['reference_rows'][0]['alpha_deg'],
                speed=job['condition']['speed'] if job['condition'] else None,
                mesh=job['nominal'], name=check['name'], expected=check['expected'],
                predicted=check['predicted'], passed=check['passed'],
                strict_passed=check['strict_passed'], error_percent=error))
        jobs.append(job);results[identifier] = strict
    mesh = adapter.mesh_diagnostics(jobs, results)
    values = [r for r in rows if r['predicted'] is not None]
    assert not any(name == 'openswing' or name.startswith('openswing.') for name in sys.modules)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='SAVED_DATA_CONTRACTS_PASS', required=len(rows), passed=sum(r['passed'] for r in rows),
        valid=len(values), unavailable=len(rows)-len(values),
        strict_passed=sum(r['strict_passed'] for r in rows),
        distinct_native_cells=len({(r['alpha'], r['speed'], r['name']) for r in values}),
        computed_states=len(receipts), physical_checks=sum(r['physical_checks_passed'] for r in receipts),
        maximum_error_percent=max(r['error_percent'] for r in values),
        median_error_percent=median(r['error_percent'] for r in values),
        maximum_mesh_change_percent=100*max(c['relative_change'] for m in mesh for c in m['channels'].values()),
        wall_seconds_range=[min(r['wall_seconds'] for r in receipts), max(r['wall_seconds'] for r in receipts)],
        peak_rss_kib=max(r['peak_rss_kib'] for r in receipts),
        full_scope_required=1200, full_scope_computed=len(values), full_scope_not_rerun=1176-len(values),
        full_scope_unknown_initial=24, historical_settings_recovered=False,
        primary_passes_added=0, mesh_diagnostics=mesh, rows=rows,
        source_and_artifact_sha256=pins, production_imports=0, physical_calls=0,
        accounting_note='First two worker-v1 accepted-result files lack common-runner accounting; this summary applies the common contract and policy to every saved strict result. No physical rerun or raw result rewrite.')
    with (out/'summary.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','mesh_diagnostics','source_and_artifact_sha256')}, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
