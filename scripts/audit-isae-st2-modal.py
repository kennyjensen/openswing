#!/usr/bin/env python3
"""Audit saved ST2 modal evidence without importing or running the solver.

The original .e00 tokens, full saved A/M and left/right vectors are read
independently of the suite adapter. This checks the retained calculation;
it does not prove historical settings, mode identity or complete spectrum.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def pin(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def read(path):
    return json.loads(Path(path).read_text())


def vector(data):
    return np.asarray(data['real'], dtype=float) + 1j*np.asarray(data['imag'], dtype=float)


def audit_job(job, root):
    checks = []

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))

    saved = job['result']
    check('terminal worker reaped', saved.get('process_reaped') is True and
          saved.get('execution_completed') is True and saved.get('process_exit_code') == 0)
    stage = Path(saved['artifact_directory'])
    result, request = read(stage/'result.json'), read(stage/'request.json')
    original = root/job['model_path']
    check('literal request model', request['source'].encode() == original.read_bytes())
    check('declared loaded fixed setup', request['condition'] is None and
          request['gravity'] == [0., 0., -9.81] and request.get('loads', []) == [] and
          request['modes']['frame'] == 'fixed' and request['modes']['position'] == [0., 0., 0.] and
          request['modes']['attitude'] == [0., 0., 0.])
    check('prospective modal choices retained', all(request['modes'][key] == value
          for key, value in dict(count=20, shift=[-.01, 0.], method='full_shift_invert',
              step=1e-5, rank_tolerance=1e-9, tolerance=1e-9, matrices=True).items()))
    check('actual local search', result['diagnostics']['method'] == 'full_shift_invert' and
          result['diagnostics']['finite_dimension'] is None and
          result['diagnostics']['finite_spectrum'] is None)
    a, m = (np.asarray(result['matrices'][key], dtype=float) for key in ('A', 'M'))
    check('finite full square pencil', a.ndim == 2 and a.shape[0] == a.shape[1] and
          a.shape == m.shape and np.all(np.isfinite(a)) and np.all(np.isfinite(m)))
    modes = result['modes']
    values = np.array([complex(*mode['eigenvalue']) for mode in modes])
    check('all twenty finite roots retained', values.shape == (20,) and np.all(np.isfinite(values)))
    positive = sorted((i for i, value in enumerate(values) if value.imag > 0),
                      key=lambda i: values[i].imag)
    check('at least seven positive ordinal candidates', len(positive) >= 7, count=len(positive))
    conjugates = []
    for i, value in enumerate(values):
        candidates = [j for j in range(len(values)) if j != i]
        partner = min(candidates, key=lambda j: abs(values[j]-value.conjugate()))
        error = float(abs(values[partner]-value.conjugate()))
        limit = float(2e-8 + 2e-8*max(abs(value), abs(values[partner])))
        matching = [j for j in candidates if values[j].imag < 0 and
                    abs(values[j]-value.conjugate()) <= 2e-8+2e-8*max(abs(value), abs(values[j]))]
        conjugates.append(dict(index=i, partner=partner, error=error, gate=limit,
                               negative_witness_candidates=matching))
    witnesses = [conjugates[i]['negative_witness_candidates'] for i in positive[:7]]
    check('seven unique selected conjugate witnesses', len(witnesses) == 7 and
          all(len(row) == 1 for row in witnesses) and len({row[0] for row in witnesses if row}) == 7)
    distinct = all(abs(values[i]-values[j]) > 2e-8+2e-8*max(abs(values[i]), abs(values[j]))
                   for i in range(len(values)) for j in range(i))
    check('retained roots distinct', distinct)
    neutral = float(np.max(abs(values.real)/np.maximum(1., abs(values.imag))))
    check('undamped near-neutral numerical check', neutral <= 1e-8, value=neutral, gate=1e-8)
    anorm, mnorm = float(np.linalg.norm(a)), float(np.linalg.norm(m))
    pairs, lefts, rights = [], [], []
    for i, mode in enumerate(modes):
        lam = values[i]
        right, left = vector(mode['right']), vector(mode['left'])
        check(f'mode {i} finite full vectors', right.shape == left.shape == (len(a),) and
              np.all(np.isfinite(right)) and np.all(np.isfinite(left)))
        entry = dict(index=i, eigenvalue=mode['eigenvalue'])
        for side, v in (('right', right), ('left', left)):
            residual = a@v-lam*(m@v) if side == 'right' else a.T@v-lam.conjugate()*(m.T@v)
            denominator = (anorm+abs(lam)*mnorm)*np.linalg.norm(v)
            backward = float(np.linalg.norm(residual)/denominator)
            entry[side] = dict(backward_error=backward, residual_norm=float(np.linalg.norm(residual)),
                               denominator=float(denominator))
            check(f'mode {i} {side} full pencil', math.isfinite(backward) and backward <= 1e-8,
                  value=backward, gate=1e-8)
        pairing = np.vdot(left, m@right)
        entry['pairing'] = [float(pairing.real), float(pairing.imag)]
        check(f'mode {i} mass normalization', abs(pairing-1) <= 1e-8,
              error=float(abs(pairing-1)), gate=1e-8)
        pairs.append(entry); lefts.append(left); rights.append(right)
    cross = np.asarray(lefts).conj()@m@np.asarray(rights).T
    raw = read(stage/'restored-residual.json')
    residual = np.asarray(raw['vector'], dtype=float)
    maximum = float(np.max(abs(residual)))
    check('saved raw restored residual', np.all(np.isfinite(residual)) and maximum <= 1e-9,
          maximum=maximum, gate=1e-9, length=len(residual))
    check('raw residual reported maximum', raw['maximum_absolute'] == maximum)
    fresh = read(stage/'restored-result.json')
    balances = {}
    for kind in ('force', 'moment'):
        applied, support = (np.asarray(fresh[prefix+'_'+kind], dtype=float)
                            for prefix in ('applied', 'support'))
        relative = float(np.linalg.norm(applied+support)/max(1., np.linalg.norm(applied), np.linalg.norm(support)))
        balances[kind] = dict(applied=applied.tolist(), support=support.tolist(), relative=relative)
        check('fresh '+kind+' balance', relative <= 1e-7, value=relative, gate=1e-7)
    expected_gravity = np.array([0., 0., -.6787*.55*9.81])
    error = float(np.max(abs(np.asarray(fresh['applied_force'])-expected_gravity)))
    check('independent physical-span real weight', error <= 2e-10, error=error,
          expected_mass=.6787*.55, expected_force=expected_gravity.tolist())
    table = root/job['table_path']
    tokens = [line.split() for line in table.read_text().splitlines()
              if line.strip() and not line.lstrip().startswith('#')]
    check('all original seven complex rows', len(tokens) == 7 and all(len(row) == 3 and row[0] == '1' for row in tokens))
    comparisons = []
    reported = {row['name']: row for row in saved['reference_checks']}
    for ordinal, (index, row) in enumerate(zip(positive[:7], tokens), 1):
        for component, value, token in zip(('real', 'imaginary'),
                (float(values[index].real), float(values[index].imag)), row[1:]):
            target = Decimal(token.replace('D', 'E').replace('d', 'e'))
            half = Decimal(5).scaleb(target.as_tuple().exponent-1)
            error = abs(Decimal(str(value))-target)
            name = f'row{ordinal:04d}:{component}'
            entry = dict(name=name, ordinal=ordinal, mode_index=index, predicted=value, original_token=token,
                exact_decimal_error=str(error), exact_decimal_tolerance=str(half), passed=error <= half)
            comparisons.append(entry)
            other = reported[name]
            check(name+' independent comparison accounting', other['predicted'] == value and
                  other['passed'] == entry['passed'])
    return dict(id=job['id'], checks=checks, passed=all(row['passed'] for row in checks),
        original_table=pin(table), artifact_directory=str(stage), conjugates=conjugates, pairs=pairs,
        cross_pairing=dict(real=cross.real.tolist(), imag=cross.imag.tolist()), balances=balances,
        reference_comparisons=comparisons, reference_matches=sum(row['passed'] for row in comparisons),
        reference_targets=len(comparisons), matrix_shape=list(a.shape),
        scope='Saved local descriptor calculation and unchanged source tokens; no new solve, relinearization or historical mode identity proof.')


def cross_run_diagnostics(jobs):
    """Retain every declared medium and mesh; no result-based selection."""
    available = {job['id']: job for job in jobs if job['execution_route'] == 'worker' and
                 job.get('result', {}).get('artifact_directory') and
                 (Path(job['result']['artifact_directory'])/'result.json').exists()}
    groups = {}
    for job in available.values():
        groups.setdefault(job['model_path'], {})[(job['medium'], job['nominal'])] = job
    medium_rows, mesh_rows = [], []
    for model, group in groups.items():
        for nominal in (40, 80):
            if not all((medium, nominal) in group for medium in ('vacuum', 'still_air')):
                continue
            pair = [group[(medium, nominal)] for medium in ('vacuum', 'still_air')]
            raw = [read(Path(job['result']['artifact_directory'])/'result.json') for job in pair]
            if not all('matrices' in data for data in raw):
                continue
            matrices = [np.asarray(data['matrices']['A']) for data in raw]
            relative = float(np.max(abs(matrices[0]-matrices[1]))/max(1., np.max(abs(matrices[0])), np.max(abs(matrices[1]))))
            medium_rows.append(dict(model=model, nominal=nominal, jobs=[job['id'] for job in pair],
                quantity='full stationary A', relative_maximum=relative, gate=2e-10,
                passed=relative <= 2e-10, scope='Stationary apparent inertia changes M only; M symmetry is not assumed.'))
        for medium in ('vacuum', 'still_air'):
            if not all((medium, nominal) in group for nominal in (40, 80)):
                continue
            pair = [group[(medium, nominal)] for nominal in (40, 80)]
            raw = [read(Path(job['result']['artifact_directory'])/'result.json') for job in pair]
            if not all('modes' in data for data in raw):
                continue
            roots = [sorted((mode['eigenvalue'][1] for mode in data['modes'] if mode['eigenvalue'][1] > 0))[:7]
                     for data in raw]
            for ordinal, (coarse, fine) in enumerate(zip(*roots), 1):
                relative = abs(fine-coarse)/abs(fine)
                mesh_rows.append(dict(model=model, medium=medium, ordinal=ordinal,
                    coarse=coarse, fine=fine, relative=relative, gate=.001, passed=relative <= .001,
                    scope='Conditional ascending ordinal within each local retained set; mode identity and global coverage unproved.'))
    return dict(medium_checks=medium_rows, mesh_checks=mesh_rows,
                scope='Mesh and medium results remain separate from evidence-audit and archived-token acceptance.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = read(args.report)
    checks, pins, seen = [], [], set()
    for job in report['jobs']:
        for item in job.get('source_pins', [])+job.get('kernel_pins', [])+job.get('result', {}).get('artifact_files', []):
            key = (item['path'], item['sha256'])
            if key in seen:
                continue
            seen.add(key)
            actual = pin(item['path'])
            ok = actual['sha256'] == item['sha256'] and actual['bytes'] == item['bytes']
            pins.append(dict(**actual, passed=ok))
    checks.append(dict(name='all current source/kernel/artifact pins unchanged', passed=all(p['passed'] for p in pins)))
    results, unavailable = [], []
    for job in report['jobs']:
        if job['execution_route'] != 'worker':
            continue
        if not job.get('result', {}).get('artifact_directory'):
            unavailable.append(dict(id=job['id'], status=job.get('result', {}).get('status'),
                                    reason='No completed saved modal evidence to audit.'))
            continue
        stage = Path(job['result']['artifact_directory'])
        required = ['result.json', 'request.json', 'restored-result.json', 'restored-residual.json']
        if not all((stage/name).exists() for name in required):
            unavailable.append(dict(id=job['id'], status=job['result']['status'],
                                    reason='Saved modal evidence incomplete; retained execution failure.'))
            continue
        results.append(audit_job(job, root))
    output = dict(format='openswing-isae-st2-independent-saved-modal-audit', version=1,
        report=pin(args.report), script=pin(__file__), checks=checks, verified_files=pins, jobs=results,
        unavailable_jobs=unavailable, operations=dict(solves=0, residual_evaluations=0, linearizations=0, eigensolves=0),
        audit_pass=all(c['passed'] for c in checks) and all(j['passed'] for j in results),
        all_planned_workers_audited=len(results) == 8 and not unavailable,
        cross_run_diagnostics=cross_run_diagnostics(report['jobs']),
        qualifications=['Reference mismatches remain failures of their printed targets even if this evidence audit passes.',
                        'Saved matrices and vectors are checked algebraically; physical derivative assembly is not independently rerun.',
                        'Execution counters and process reaping are retained supervisor evidence, not new observations of the processes.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(output=str(args.output), audit_pass=output['audit_pass'],
        audited_jobs=len(results), unavailable_jobs=len(unavailable), verified_files=len(pins))))
    raise SystemExit(0 if output['audit_pass'] else 1)


if __name__ == '__main__':
    main()
