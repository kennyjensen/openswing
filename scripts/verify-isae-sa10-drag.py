"""Compare drag at matched lift, retaining every sampled polar branch and gap."""
from pathlib import Path
import argparse, fcntl, hashlib, importlib.util, json, sys, time
import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from isae_sa10_reference import sha
spec = importlib.util.spec_from_file_location('sa10', ROOT / 'scripts/verify-isae-sa10.py')
study_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(study_module)
D = ROOT / 'docs/validation'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--polar-checkpoint', type=Path, help='Precompute from completed polar groups without publishing a final report')
    args = parser.parse_args()
    study_path = args.polar_checkpoint or D / 'isae-sa10.json'
    study = json.loads(study_path.read_text())
    sources = json.loads((D / 'isae-sa10-sources.json').read_text())
    cache_identity = dict(script_sha256=sha(Path(__file__)), provenance={k: study['provenance'][k] for k in
        ['modules', 'script_sha256', 'reference_script_sha256', 'source_report_sha256']})
    identity = dict(**cache_identity, study_sha256=sha(study_path), precomputed=bool(args.polar_checkpoint))
    assert identity['provenance']['modules'] == {p.name: sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    runroot = ROOT / '.reference/isae-sa10-drag' / hashlib.sha256(json.dumps(cache_identity, sort_keys=True).encode()).hexdigest()
    runroot.mkdir(parents=True, exist_ok=True)
    (runroot / 'identity.json').write_text(json.dumps(cache_identity, indent=2) + '\n')
    rows = []
    for case in study['cases']:
        if case['name'] not in sources['experimental_drag']:
            continue
        for panels in [50, 100]:
            polar = sorted([r for r in case['runs'] if r['specification']['panels'] == panels
                and r['specification']['pg'] == 'zero' and not r['specification']['frozen']],
                key=lambda r: r['specification']['alpha'])
            known = {r['specification']['alpha']: r for r in polar}
            assert set(range(26)).issubset(known), 'Required polar group is incomplete'

            def evaluate(alpha):
                if alpha in known:
                    return known[alpha]
                condition = dict(case=case['case_id'], panels=panels, alpha=float(alpha), pg='zero', frozen=False)
                path = runroot / (hashlib.sha256(json.dumps(condition, sort_keys=True).encode()).hexdigest() + '.json')
                with path.with_suffix('.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    if path.exists():
                        result = json.loads(path.read_text()); assert result['specification'] == condition
                    else:
                        start = time.monotonic()
                        try:
                            result = dict(specification=condition, status='computed', result=study_module.compute(case['source'], condition))
                        except study_module.AnalysisError as exc:
                            result = dict(specification=condition, status='rejected', error=str(exc), details=getattr(exc, 'details', None))
                        result['seconds'] = time.monotonic() - start
                        temporary = path.with_suffix('.tmp'); temporary.write_text(json.dumps(result, indent=2) + '\n'); temporary.replace(path)
                known[alpha] = dict(**result, cache_path=path.relative_to(ROOT).as_posix(), cache_sha256=sha(path))
                return known[alpha]

            for measurement in sources['experimental_drag'][case['name']]['values']:
                target, measured_drag = measurement['xy']; roots, brackets, gaps, failures = [], [], [], []
                for left, right in zip(polar[:-1], polar[1:]):
                    a, b = left['specification']['alpha'], right['specification']['alpha']
                    if left['status'] != 'computed' or right['status'] != 'computed':
                        gaps.append([a, b]); continue
                    fa, fb = left['result']['CL'] - target, right['result']['CL'] - target
                    if fa == 0:
                        roots.append(dict(alpha=a, result=left['result'], lift_error=0., bracket=[a, a]))
                    if fb == 0:
                        roots.append(dict(alpha=b, result=right['result'], lift_error=0., bracket=[b, b]))
                    if fa * fb >= 0:
                        continue
                    brackets.append([a, b]); trials = []

                    def residual(alpha):
                        result = evaluate(alpha); trials.append(dict(alpha=float(alpha), status=result['status']))
                        if result['status'] != 'computed':
                            raise study_module.AnalysisError(result['error'])
                        return result['result']['CL'] - target

                    try:
                        alpha = float(brentq(residual, a, b, xtol=1e-8, rtol=1e-12, maxiter=60))
                        state = evaluate(alpha); error = float(state['result']['CL'] - target)
                        if abs(error) > 5e-8:
                            failures.append(dict(bracket=[a, b], status='discontinuous_or_unresolved_branch',
                                alpha=alpha, lift_error=error, trials=trials)); continue
                        roots.append(dict(alpha=alpha, result=state['result'], lift_error=error, bracket=[a, b], trials=trials,
                            cache_path=state.get('cache_path'), cache_sha256=state.get('cache_sha256')))
                    except (study_module.AnalysisError, RuntimeError) as exc:
                        failures.append(dict(bracket=[a, b], status='branch_rejected', error=str(exc), trials=trials))
                unique = []
                for root in sorted(roots, key=lambda r: r['alpha']):
                    if not unique or abs(root['alpha'] - unique[-1]['alpha']) > 1e-6:
                        unique.append(dict(**root, CD_error=float(root['result']['CD'] - measured_drag)))
                rows.append(dict(case=case['case_id'], name=case['name'], panels=panels, pg='zero', frozen=False,
                    csv_row=measurement['row'], target_CL=target, measured_CD=measured_drag,
                    roots=unique, observed_brackets=brackets, failed_intervals=gaps, failed_roots=failures,
                    status='single_observed_root' if len(unique) == 1 else ('multiple_observed_roots' if unique else 'no_resolved_root'),
                    coverage='All sign-changing adjacent converged samples in alpha=0..25 degrees; no extrapolation. Unsampled folds/tangencies or disconnected branches are not excluded.'))
                progress_name = 'precompute-progress.json' if args.polar_checkpoint else 'progress.json'
                (runroot / progress_name).write_text(json.dumps(dict(status='RUNNING', rows=rows), indent=2) + '\n')
                print('DRAG', case['case_id'], panels, measurement['row'], 'roots', len(unique), 'failures', len(failures), flush=True)
    summary = []
    for case in study['cases']:
        for panels in [50, 100]:
            group = [r for r in rows if r['case'] == case['case_id'] and r['panels'] == panels]
            if not group:
                continue
            single = [r for r in group if len(r['roots']) == 1 and not r['failed_intervals'] and not r['failed_roots']]
            summary.append(dict(case=case['case_id'], panels=panels, requested=len(group),
                single_observed_root=sum(len(r['roots']) == 1 for r in group), complete_single_root_scan=len(single),
                incomplete_scans=sum(bool(r['failed_intervals'] or r['failed_roots']) for r in group),
                multiple_observed_roots=sum(len(r['roots']) > 1 for r in group),
                missing_roots=sum(not r['roots'] for r in group),
                single_observed_root_errors=study_module.metrics([r['roots'][0]['result']['CD'] for r in single], [r['measured_CD'] for r in single])))
    output = dict(status='FIXED_LIFT_COMPARISON_WITH_ALL_OBSERVED_BRANCHES', identity=identity,
        rows=rows, summary=summary, limitations=[
            'No experimental alpha accompanies the drag CSV. Multiple computed alpha branches are retained; no closest-drag branch is selected.',
            'Single observed root is conditional on the sampled alpha range and independent solver branch selection, not a proof of global uniqueness.',
            'Only current influences and zero PG Mach are root-solved. The full polar report retains both PG and influence choices.',
            'Experimental uncertainty, tunnel corrections and exact tip-sail geometry remain unrecovered.'])
    destination = runroot / 'precompute-report.json' if args.polar_checkpoint else D / 'isae-sa10-drag.json'
    if args.polar_checkpoint:
        output['status'] = 'PRECOMPUTED_FROM_COMPLETED_POLAR_GROUPS_NOT_FINAL_STUDY'
    destination.write_text(json.dumps(output, indent=2) + '\n')
    print('COMPLETE', len(rows), 'fixed-lift requests', flush=True)


if __name__ == '__main__':
    main()
