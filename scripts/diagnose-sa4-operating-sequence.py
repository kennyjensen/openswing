"""Explicit previous-circulation initialization in the SA-4 CL driver order.

This is a current-equation initialization diagnostic. The shell builds an
operating stack and executes XX; historical copying of converged circulation
between its points is not established. No source script is executed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_suite_polars import reference_checks, reconstructed_wrench


def pin(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(path, value):
    # Preserve an invalid raw output for diagnosis without emitting JSON NaN.
    def serializable(item):
        if isinstance(item, float) and not math.isfinite(item):
            return {'nonfinite': repr(item)}
        if isinstance(item, dict):
            return {k: serializable(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [serializable(v) for v in item]
        return item
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(serializable(value), indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels', type=int, choices=(80, 160), required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    assert not (out/'report.json').exists(), 'Choose a fresh evidence directory.'
    source = ROOT/'artifacts/isae/sa2-sa5-baseline-20261028/report.json'
    pins = [pin(source), pin(Path(__file__))]
    pins += [pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    pins += [pin(ROOT/'scripts/isae_suite_polars.py')]
    baseline = json.loads(source.read_text())
    jobs = [j for j in baseline['jobs'] if j['case_id']=='SA-4'
            and j['id'].startswith('SA-4:SA_4:') and j['settings']['panels']==args.panels]
    assert len(jobs)==21 and len({j['model_path'] for j in jobs})==1
    jobs.sort(key=lambda j:j['reference_row']['fields']['index']['value'])
    original = {p['path']:p for job in jobs for p in job['sources']}
    for p in original.values():
        assert pin(ROOT/p['path']) == p, 'Original model/driver/table changed.'
    pins += list(original.values())
    states = {int(j['reference_row']['fields']['index']['value']): j for j in jobs}
    assert set(states)==set(range(1,23))-{18}
    # Point 18 is declared in the original driver but has no archived row.
    # It participates in initialization only and adds no reference check.
    records, seed, seed_index = [], None, None
    started = time.monotonic()
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, solve_rigid
    model = parse_asw((ROOT/jobs[0]['model_path']).read_text(), beam_interpolation='natural-v1')
    settings = jobs[0]['settings']
    assert float(model.constants[1]) == settings['density'], 'Parsed density disagrees with archive setup.'
    assert all({k:v for k,v in j['settings'].items() if k not in ('alpha','alpha_token')} ==
               {k:v for k,v in settings.items() if k not in ('alpha','alpha_token')} for j in jobs)
    condition_fields = ('speed','beta','density','mach','freeze_influences','stall','stall_factor',
                        'stall_width','wake_core_ratio','aero_lag','body_added_mass_factor')
    def timeout(signum, frame):
        raise TimeoutError('Operating state exceeded the declared 90-second bound.')
    signal.signal(signal.SIGALRM, timeout)
    chain_failed = False
    for index in range(1,23):
        job = states.get(index)
        alpha = job['settings']['alpha'] if job else 8.06
        row = dict(index=index, alpha=alpha, reference_job=None if job is None else job['id'],
            seed_source_index=seed_index, status='blocked' if chain_failed else 'running',
            reference_checks=[], numerical_checks=[], required_reference_checks=7 if job else 0)
        if chain_failed:
            row['reason']='Preceding state failed; no continuation across an uncomputed state.'
            records.append(row)
            continue
        print(json.dumps(dict(event='start', panels=args.panels, index=index, alpha=alpha,
                              seed_source_index=seed_index)), flush=True)
        begin = time.monotonic()
        try:
            signal.alarm(90)
            condition = FlightCondition(alpha=alpha, **{k:settings[k] for k in condition_fields})
            result = solve_rigid(model, condition, args.panels, initial_circulation=seed)
            row['result'] = result
            gamma = np.array([s['circulation'] for s in result['strips'] if s['lifting']])
            force, moment, _ = reconstructed_wrench(model, result)
            qS = .5*condition.density*condition.speed**2*model.reference[0,0]
            e, _, up = condition.vectors()
            predicted = {k:result[k] for k in ('CL','CD','CDi','Cm','efficiency')}
            predicted.update(lift=float(force@up), drag=float(force@e))
            finite_fields = [result[k] for k in ('CL','CD','CDi','Cm','CDi_near','CDp',
                                                'CDbody','CDam','CDeng','CDrate')]
            finite = all(np.all(np.isfinite(v)) for v in
                         (force,moment,result['force'],result['moment'],gamma,finite_fields))
            finite = finite and (result['efficiency'] is None or math.isfinite(result['efficiency']))
            checks = row['numerical_checks']
            checks.extend([
                dict(name='no parser diagnostics',passed=not model.diagnostics,diagnostics=list(model.diagnostics)),
                dict(name='converged',passed=bool(result['converged'])),
                dict(name='finite circulation, loads and available coefficients',passed=bool(finite)),
                dict(name='circulation residual',value=result['residual'],tolerance=1e-8,
                     passed=math.isfinite(result['residual']) and result['residual']<=1e-8)])
            errors = {'CL force normalization':abs(predicted['lift']/qS-result['CL']),
                'CD force normalization':abs(predicted['drag']/qS-result['CD']),
                'Cm moment normalization':abs(moment[1]/(qS*model.reference[0,1])-result['Cm']),
                'near-field drag decomposition':abs(result['CD']-sum(result[k] for k in
                    ('CDi_near','CDp','CDbody','CDam','CDeng','CDrate'))),
                'reconstructed total force':np.max(abs(force-result['force']))/qS,
                'reconstructed total moment':np.max(abs(moment-result['moment']))/(qS*model.reference[0,1])}
            for name, error in errors.items():
                error = float(error)
                checks.append(dict(name=name,value=error,tolerance=2e-10,
                                   passed=math.isfinite(error) and error<=2e-10))
            assert all(c['passed'] for c in checks), 'Independent numerical verification failed.'
            checks = reference_checks(predicted,job['reference_row']) if job else []
            for check in checks:
                expected = check['expected']
                check['absolute_percent_error'] = (100*check['abs_error']/abs(expected)
                    if check['abs_error'] is not None and expected else None)
            seed = gamma
            seed_index = index
            row.update(status='computed',reference_checks=checks,result=result,
                cold_baseline_status=None if job is None else job['result']['status'],
                numerical_checks_passed=True)
        except (ValueError, AssertionError, TimeoutError, np.linalg.LinAlgError) as error:
            row.update(status='error',error_type=type(error).__name__,error=str(error))
            if getattr(error,'details',None) is not None:
                row['error_details']=error.details
            chain_failed=True
        finally:
            signal.alarm(0)
        row['seconds']=time.monotonic()-begin
        records.append(row)
        write(out/f'point-{index:02d}.json',row)
        print(json.dumps({k:row[k] for k in ('index','alpha','status','seconds')},allow_nan=False),flush=True)
    for p in pins:
        assert pin(ROOT/p['path'])==p, 'Input or implementation changed during sequence.'
    summary = dict(status='COMPLETED',panels=args.panels,elapsed_seconds=time.monotonic()-started,
        initialization='Previous successfully computed circulation seeds Newton; existing automatic cold fallback remains explicit. First state cold; stop on any failed/invalid state.',
        qualifications=['Current-equation diagnostic, not recovered historical XX Newton initialization.',
            'Diagnostic initializes the first state at archived printed -0.0; historical startup is unspecified. Scripted 0.016150740242261596 is overwritten by 0.29 before the next +.',
            'Driver state18 alpha8.06 has no archived row and is unscored.',
            'A successful seed or cold fallback does not establish uniqueness, branch continuity or physical stability.',
            'No mesh, physical parameter, reference tolerance or registered pass count is changed.'],
        source_pins=pins,records=records,
        counts=dict(required_states=22,reference_states=21,required_reference_checks=147,
            computed=sum(r['status']=='computed' for r in records),
            seeded_accepted=sum(r.get('result',{}).get('circulation_solver',{}).get('initialization',{}).get('seed_attempt',{}).get('accepted',False) for r in records),
            cold_fallbacks=sum(r.get('result',{}).get('circulation_solver',{}).get('initialization',{}).get('cold_fallback',False) for r in records),
            errors=sum(r['status']=='error' for r in records),blocked=sum(r['status']=='blocked' for r in records),
            reference_passes=sum(c['passed'] for r in records for c in r['reference_checks'])))
    write(out/'report.json',summary)
    print(json.dumps(dict(event='complete',panels=args.panels,counts=summary['counts'])),flush=True)


if __name__=='__main__':
    main()
