"""Audit current AE-2 runs against the complete registered sensor scope.

Saved-data only. Never combines different kernels, duplicate coordinates or
alternative branch settings. Missing native values remain required.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import resource
import signal
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_aeroelastic as adapter


def assess(runs, output, recoveries=(), continuations=()):
    spec = importlib.util.spec_from_file_location('saved_summary', ROOT/'scripts/summarize-isae-suite.py')
    summary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summary)
    merged = summary.load_runs(runs, root=ROOT)
    jobs = merged['jobs']
    assert jobs and all(j['case_id'] == 'AE-2' for j in jobs)
    full = {j['id']: j for j in adapter.plan(ROOT) if j['case_id'] == 'AE-2'}
    assert len(full) == 550
    required = sum(j['expected_outputs'] for j in full.values())
    unavailable = sum(o['missing'] for j in full.values() for o in j['observations'])
    assert required == 2200 and unavailable == 96
    for job in jobs:
        canonical = full[job['id']]
        assert all(job[key] == value for key, value in canonical.items()), job['id']
    recovery_evidence = []; recovery_pins = []
    if recoveries:
        from scripts.isae_ae2_saved_acceptance import load_recoveries
        replacements, recovery_evidence, recovery_pins = load_recoveries(
            recoveries, jobs, merged['reference_acceptance'])
        # Only a failed original comparison can acquire a completed, independently
        # rechecked state. Its immutable failure receipt stays in the evidence.
        for job in jobs:
            if job['id'] in replacements:
                job['result'] = replacements[job['id']]
    continuation_evidence = []; continuation_pins = []
    if continuations:
        from scripts.isae_ae2_continuation_acceptance import load_continuations
        replacements, continuation_evidence, continuation_pins = load_continuations(
            continuations, jobs, merged['reference_acceptance'])
        for job in jobs:
            if job['id'] in replacements:
                job['result'] = replacements[job['id']]
    results = {j['id']: j['result'] for j in jobs if j.get('result') is not None}
    counts = summary.totals(jobs)
    rows = []
    physical_checks = 0
    solve_seconds = []
    residuals = []
    staged_pins = []
    staged_jobs = []
    for job in jobs:
        result = job.get('result') or {}
        if not summary.numerically_valid(result):
            continue
        worker = result['worker_report']
        if result.get('completion_route') == 'verified_original_saved_equilibrium':
            terminal = result['verification_process']
            assert terminal['process_reaped'] and terminal['returncode'] == 0
            assert worker['operations'] == dict(new_cold_solves=0, fresh_residuals=1)
        elif result.get('completion_route') == 'verified_original_cold_continuation':
            terminal = result['verification_process']
            assert terminal['process_reaped'] and terminal['returncode'] == 0
            assert worker['operations'] == dict(cold_solves=1, fresh_residuals=1)
        else:
            assert result['process_reaped'] and result['process_exit_code'] == 0
            assert worker['operations'] == dict(cold_solves=1, fresh_residuals=1)
            if result.get('execution_kind') == 'staged_subprocess':
                from scripts.execute_isae_ae2_staged import verify_saved
                staged_pins.extend(verify_saved(job, result))
                staged_jobs.append(job['id'])
        assert all(c['passed'] is True for c in result['physical_checks'])
        physical_checks += len(result['physical_checks'])
        if worker['solve_seconds'] is not None:
            solve_seconds.append(worker['solve_seconds'])
        residuals.append(worker['fresh_residual'])
        for check in result['reference_checks']:
            rows.append(dict(job=job['id'], layup=job.get('layup', '03_90'),
                mesh=job['nominal'], speed=job['condition']['speed'], beta=job['condition']['beta'],
                name=check['name'], expected=check['expected'], predicted=check['predicted'],
                error_percent=100*check['relative_error'] if check['relative_error'] is not None else None,
                passed=check['passed'], strict_passed=check['strict_passed']))
    mesh = adapter.mesh_diagnostics(list(full.values()), results)
    errors = [r['error_percent'] for r in rows if r['error_percent'] is not None]
    compared = [r for r in mesh if r['status'] == 'COMPARED']
    full_scope = [dict(id=j['id'], coordinate=j['coordinate_id'],
        observations=j['observations'], executed=j['id'] in results) for j in full.values()]
    summary.verify_summary_sources(merged)
    if recovery_pins:
        from scripts.recover_isae_ae2_saved import pin
        assert all(pin(p['path']) == p for p in recovery_pins)
    if staged_pins:
        staged_pins = list({p['path']:p for p in staged_pins}.values())
        assert all(adapter._pin(p['path']) == p for p in staged_pins)
    if continuation_pins:
        from scripts.recover_isae_ae2_saved import pin
        assert all(pin(p['path']) == p for p in continuation_pins)
    assert not any(n == 'openswing' or n.startswith('openswing.') for n in sys.modules)
    report = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='CURRENT_SAVED_DATA_AUDIT_PASS', whole_family_validated=False,
        physics_calls=0, production_imports=0, assessor=summary.pin(__file__),
        source_inputs=merged['inputs'], verified_files=merged['_verified_file_pins'],
        verified_saved_state_completions=recovery_evidence,
        verified_recovery_files=recovery_pins,
        verified_staged_jobs=staged_jobs, verified_staged_files=staged_pins,
        verified_cold_continuations=continuation_evidence, verified_continuation_files=continuation_pins,
        full_scope=dict(passed=counts['passed'], required=required,
            unavailable_native=unavailable, valid_computed=len(rows),
            finite_unrun=sum(j['expected_outputs'] for j in full.values()
                if j['execution_route'] == 'worker' and j['id'] not in results),
            historical_results_reused=0),
        selected_counts=counts, reference_acceptance=merged['reference_acceptance'],
        physical_checks_passed=physical_checks,
        median_error_percent=statistics.median(errors) if errors else None,
        maximum_error_percent=max(errors, default=None),
        maximum_fresh_residual=max(residuals, default=None), solve_seconds=solve_seconds,
        compared_mesh_pairs=compared, missing_mesh_pairs=len(mesh)-len(compared),
        rows=rows, required_coordinates=full_scope)
    assert not output.exists(), 'Preserve earlier observations; use a fresh output.'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'full_scope', 'physical_checks_passed',
        'median_error_percent', 'maximum_error_percent', 'maximum_fresh_residual')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recovery', action='append', type=Path, default=[],
                        help='Independently verified original saved states; original failures stay immutable')
    parser.add_argument('--continuation', action='append', type=Path, default=[],
                        help='Audited unchanged cold continuation chains; one original slot per result')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    # This is a saved-file audit, with no solver imports or physical calls.
    # Allow filesystem verification to finish on UserLAnd while retaining
    # the same 15-CPU-second and 512-MiB limits.
    signal.alarm(60)
    assess(args.run, args.output, args.recovery, args.continuation)
