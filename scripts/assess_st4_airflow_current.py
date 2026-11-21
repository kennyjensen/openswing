"""Audit saved ST-4 airflow probes; do not turn spacing hypotheses into passes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(folder):
    assert all(os.environ.get(k) == '1' for k in
               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,) * 2)
    signal.alarm(25)
    import numpy as np
    from scipy.sparse import load_npz
    from isae_suite_modes import decode_table

    plan = read(folder / 'plan.json')
    for path, digest in plan['pins'].items():
        assert sha(ROOT / path) == digest, path
    native_path = (ROOT / plan['model']).with_name('eig.txt')
    native = decode_table(native_path.read_text(), False)
    source_pins = {str(native_path.relative_to(ROOT)): sha(native_path)}
    for entry in read(ROOT / 'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] == 'isae-part-4':
            for field, key in [('local_pdf', 'sha256'), ('local_text', 'text_sha256')]:
                path = ROOT / entry[field]
                assert sha(path) == entry[key]
                source_pins[entry[field]] = entry[key]
    evaluated = []
    for index, job in enumerate(plan['jobs']):
        path = folder / f'job-{index:02d}'
        receipt = read(folder / f'execution-{index:02d}.json')
        assert receipt['terminal'] and receipt['returncode'] == 0 and not receipt['timeout']
        report = read(path / 'report.json')
        assert report['plan_sha256'] == sha(folder / 'plan.json')
        assert report['actual_nodes'] == job['expected_nodes'] == 40
        for name, digest in report['artifacts'].items():
            assert sha(path / name) == digest, name
        result = read(path / 'result.json')
        assert result['converged'] and result['base']['converged']
        assert report['fresh_residual'] < 1e-8
        a, m = load_npz(path / 'A.npz'), load_npz(path / 'M.npz')
        checks = []
        for mode in result['modes']:
            lam = complex(*mode['eigenvalue'])
            vectors = {}
            for side in ('left', 'right'):
                v = np.asarray(mode[side]['real']) + 1j * np.asarray(mode[side]['imag'])
                vectors[side] = v
                av, mv = (a @ v, m @ v) if side == 'right' else (v.conjugate() @ a, v.conjugate() @ m)
                error = float(np.linalg.norm(av - lam * mv) /
                              (np.linalg.norm(av) + abs(lam) * np.linalg.norm(mv)))
                assert error < 1e-8
                checks.append(dict(mode=mode['index'], side=side, relative_action_error=error))
            pairing = float(abs(np.vdot(vectors['left'], m @ vectors['right']) - 1))
            assert pairing < 1e-8
            checks.append(dict(mode=mode['index'], side='mass-pairing', error=pairing))

        # Rank within real/oscillatory families, never nearest-target selection.
        # No archived eigenvectors exist to authenticate physical branch identity.
        real = sorted((v for v in result['modes'] if abs(v['eigenvalue'][1]) < 5e-8),
                      key=lambda v: abs(v['eigenvalue'][0]))
        oscillatory = sorted((v for v in result['modes'] if v['eigenvalue'][1] >= 5e-8),
                            key=lambda v: v['eigenvalue'][1])
        point = {120.5: 2, 139.5: 40}[job['speed']]
        rows = [r for r in native if r['operating_point'] == point]
        assert len(rows) == {2: 6, 40: 9}[point]
        real_rank = oscillatory_rank = 0
        comparisons = []
        for ordinal, row in enumerate(rows, 1):
            unavailable = point == 40 and ordinal in (1, 2)
            if not unavailable:
                if row['eigenvalue'][1] == 0:
                    chosen = real[real_rank]
                    real_rank += 1
                else:
                    chosen = oscillatory[oscillatory_rank]
                    oscillatory_rank += 1
            for component, ref in enumerate(row['eigenvalue']):
                value = None if unavailable else chosen['eigenvalue'][component]
                percent = None if value is None or ref == 0 else 100 * abs(value - ref) / abs(ref)
                within = None if value is None else (
                    abs(value) <= 5e-8 if ref == 0 else percent <= 5)
                comparisons.append(dict(ordinal=ordinal, source=row,
                    component=['real', 'imaginary'][component], reference=ref,
                    actual=value, error_percent=percent,
                    absolute_error=None if value is None else abs(value - ref),
                    within_diagnostic_tolerance=within,
                    mode_index=None if unavailable else chosen['index'],
                    qualification='unidentified native tiny root' if unavailable else
                        'conditional family/rank correspondence; no native eigenvectors'))
        evaluated.append(dict(job=job, execution=receipt, comparisons=comparisons,
            equation_checks=checks, report_sha256=sha(path / 'report.json'),
            equation_check_count=len(checks),
            raw_component_matches=sum(c['within_diagnostic_tolerance'] is True for c in comparisons),
            declared_components=len(comparisons),
            unavailable_components=sum(c['actual'] is None for c in comparisons)))
        del a, m, result, vectors

    totals = {}
    for spacing in sorted({e['job']['spacing'] for e in evaluated}):
        subset = [e for e in evaluated if e['job']['spacing'] == spacing]
        totals[spacing] = dict(
            raw_component_matches=sum(e['raw_component_matches'] for e in subset),
            declared_components=sum(e['declared_components'] for e in subset),
            unavailable_components=sum(e['unavailable_components'] for e in subset),
            validated_passes_added=0, mesh_convergence_established=False)
        assert totals[spacing]['declared_components'] == 30
        assert totals[spacing]['unavailable_components'] == 4
    output = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan_sha256=sha(folder / 'plan.json'), source_pins=source_pins,
        assessment_script_sha256=sha(Path(__file__)), cases=evaluated, alternatives=totals,
        equation_checks=sum(e['equation_check_count'] for e in evaluated),
        qualification='Prospective spacing diagnostics only; exact historical mesh/startup unknown. '
            'Do not pool alternatives, discard unidentified rows, or alter primary/strict archive totals.')
    with (folder / 'assessment.json').open('x') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(equation_checks=output['equation_checks'], alternatives=totals)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    assess(parser.parse_args().folder.resolve())
