"""Prospective SA4 fixed-Fourier sensitivity; never changes registered scores.

Prepare the complete source-pinned protocol before launching any worker. Each
case makes one cold solve_rigid call; no previous solution, retries or fitted K.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'artifacts/isae/sa4-fourier-refinement-20261029'
BASELINE = ROOT / 'artifacts/isae/sa2-sa5-baseline-20261028/report.json'
ALPHAS = (4.06, 4.60, 5.13, 5.57, 6.10, 6.55)
CAP = 90


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path.relative_to(ROOT)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': repr(value)}
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    if type(value).__module__.startswith('numpy'):
        return safe(value.tolist())
    return value


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(safe(value), indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def verify(pins):
    for item in pins:
        if pin(ROOT/item['path']) != item:
            raise ValueError('Pinned source changed: '+item['path'])


def prepare(out):
    if out.exists() and any(p.name!='pre-review' for p in out.iterdir()):
        raise ValueError('Preparation requires a fresh evidence directory.')
    out.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE.read_text())
    selected = [j for j in baseline['jobs'] if j['case_id']=='SA-4'
                and j['id'].startswith('SA-4:SA_4:') and j['settings']['panels']==160
                and j['settings']['alpha'] in ALPHAS]
    assert len(selected)==6 and {j['settings']['alpha'] for j in selected}==set(ALPHAS)
    assert all(j['result']['status']=='error' for j in selected)
    assert len({j['model_path'] for j in selected})==1
    reference = selected[0]['settings']
    assert reference['circulation_method']=='auto' and reference['beam_interpolation']=='natural-v1'
    assert all({k:v for k,v in j['settings'].items() if k not in ('alpha','alpha_token')} ==
               {k:v for k,v in reference.items() if k not in ('alpha','alpha_token')} for j in selected)
    jobs = []
    for panels, modes, alpha in ([(160,k,a) for a in ALPHAS for k in (20,40,80)] +
                                 [(320,k,a) for a in ALPHAS[:2] for k in (40,80)]):
        original = next(j for j in selected if j['settings']['alpha']==alpha)
        tokens = (ROOT/original['table_path']).read_text().splitlines()[original['reference_row']['line_number']-1].split()
        assert tokens==original['reference_row']['tokens']
        settings = dict(original['settings'], panels=panels, mesh_level=1 if panels==160 else 2,
                        circulation_modes={'1':modes})
        jobs.append(dict(id=f"row{original['row_index']:03d}-n{panels}-k{modes}",
            baseline_job_id=original['id'], baseline_status=original['result']['status'],
            model_path=original['model_path'], table_path=original['table_path'],
            driver_path=original['driver_path'], reference_row=original['reference_row'],
            inherited_settings=original['settings'], settings=settings,
            required_reference_checks=7, initial_circulation=None))
    assert len(jobs)==22 and len({j['id'] for j in jobs})==22
    originals = {p['path']:p for j in selected for p in j['sources']}
    verify(originals.values())
    sources = [pin(BASELINE),pin(Path(__file__)),pin(ROOT/'scripts/isae_suite_polars.py')]
    sources += [pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    sources += list(originals.values())
    for name in ('.reference/asw_theory.txt','.reference/aswing_doc.txt',
                 '.reference/isae-sa1/aerodynamics-report.txt',
                 '.reference/ASWING_Extended_User_Manual.txt','.reference/version_notes.txt'):
        sources.append(pin(ROOT/name))
    protocol = dict(format='sa4-fourier-refinement-v1', jobs=jobs, source_pins=sources,
        execution=dict(workers=1, per_worker_cap_seconds=CAP, outer_solve_calls_per_job=1,
                       retries=0, initialization='cold production auto; no supplied seed',
                       internal_solver='Existing automatic direct/continuation/fallback policy unchanged.'),
        accounting=dict(jobs=22, required_reference_checks=154, distinct_native_cells=42),
        gates=dict(projected_circulation_residual=1e-8, wrench_and_normalization=2e-10,
                   local_section_normal_mach_upper_exclusive=1.0),
        source_basis=[dict(path='.reference/asw_theory.txt',lines=[733,746],equations='62-63'),
                      dict(path='.reference/asw_theory.txt',lines=[2026,2055],equations='200-204'),
                      dict(path='.reference/isae-sa1/aerodynamics-report.txt',lines=[1489,1519],
                           meaning='20-40 variables recommended after elliptical-wing study, not historical SA4 default.')],
        qualifications=['K20/40 plus K80 and n320 are prospective discretization sensitivity, not recovered historical settings.',
            'All outcomes are retained; no best K is selected for a validation claim.',
            'A truncated Fourier root satisfies projected residual constraints; local residuals are retained and need not vanish.',
            'No original model, physical parameter, target, acceptance tolerance or registered score is changed.',
            'Selected older baseline supplies source/settings/targets; its cold status is historical because kernel code has changed.',
            'Nominal panel requests are interval reconstructions; historical NODE arrays, startup files, K and producer identity remain unverified.',
            'Source prescribed alpha values are taken from the same native-row settings as baseline; original alpha tokens are retained.',
            'No equilibrium is recomputed for verification: checks use the complete returned raw state and its fresh production residual.'])
    verify(sources)
    write(out/'protocol.json',protocol)
    (out/'run.py').write_bytes(Path(__file__).read_bytes())
    write(out/'preparation-receipt.json',dict(protocol=pin(out/'protocol.json'),script=pin(Path(__file__)),
        frozen_copy=pin(out/'run.py'),source_pin_count=len(sources),jobs=22,physical_calls=0))
    print(json.dumps(dict(event='prepared',protocol=pin(out/'protocol.json'),jobs=22)),flush=True)


def worker(out, job_id):
    expected_protocol=json.loads((out/'preparation-receipt.json').read_text())['protocol']
    assert pin(out/'protocol.json')==expected_protocol
    protocol = json.loads((out/'protocol.json').read_text())
    verify(protocol['source_pins'])
    job = next(j for j in protocol['jobs'] if j['id']==job_id)
    stage = out/'jobs'/job_id
    stage.mkdir(parents=True,exist_ok=True)
    assert not (stage/'result.json').exists()
    write(stage/'request.json',job)
    record = dict(id=job_id,status='error',physical_calls=0,reference_checks=[],numerical_checks=[],
                  required_reference_checks=7,reference_match=False)
    start = time.monotonic()
    try:
        sys.path.insert(0,str(ROOT))
        sys.path.insert(1,str(ROOT/'scripts'))
        import numpy as np
        from openswing import aero,asw
        from isae_suite_polars import reconstructed_wrench,reference_checks
        assert Path(aero.__file__).resolve()==ROOT/'openswing/aero.py'
        assert Path(asw.__file__).resolve()==ROOT/'openswing/asw.py'
        s = job['settings']
        model = asw.parse_asw((ROOT/job['model_path']).read_text(),beam_interpolation='natural-v1')
        assert float(model.constants[1])==s['density']
        fields = ('speed','alpha','beta','density','mach','freeze_influences','stall',
                  'stall_factor','stall_width','wake_core_ratio','aero_lag','body_added_mass_factor')
        condition = aero.FlightCondition(**{k:s[k] for k in fields},
            circulation_modes={int(k):v for k,v in s['circulation_modes'].items()})
        record['physical_calls']=1
        write(stage/'call-started.json',dict(id=job_id,physical_calls=1,method='cold solve_rigid'))
        result = aero.solve_rigid(model,condition,s['panels'],circulation_method=s['circulation_method'])
        write(stage/'raw-result.json',result)
        record['raw_result']=pin(stage/'raw-result.json')
        gamma = np.asarray([x['circulation'] for x in result['strips'] if x['lifting']])
        local = np.asarray(result['circulation_local_residual'])
        projected = np.asarray(result['circulation_residual'])
        disc = result['circulation_discretization']
        assert len(disc['beams'])==1 and disc['beams'][0]['beam']==1
        assert disc['beams'][0]['representation']=='fourier'
        assert disc['independent_unknowns']==s['circulation_modes']['1']
        assert gamma.shape==local.shape==(disc['lifting_panels'],)
        assert projected.shape==(disc['independent_unknowns'],)
        # Independent replay of Eq201 from retained material-angle widths.
        b = disc['beams'][0]
        angles=np.asarray(b['theta_midpoint']); widths=np.asarray(b['theta_width'])
        replay=(2/np.pi)*(np.sin(angles[:,None]*np.arange(1,disc['independent_unknowns']+1)).T @ (widths*local))
        record['circulation_residuals']=dict(local=local.tolist(),projected=projected.tolist(),
            local_max_abs=float(np.max(abs(local),initial=0)),projected_max_abs=float(np.max(abs(projected),initial=0)),
            independent_projected=replay.tolist(),pointwise_local_zero_required=False)
        force,moment,_=reconstructed_wrench(model,result)
        e,_,up=condition.vectors()
        qs=.5*condition.density*condition.speed**2*model.reference[0,0]
        chord=model.reference[0,1]
        predicted={k:result[k] for k in ('CL','CD','CDi','Cm','efficiency')}
        predicted.update(lift=float(force@up),drag=float(force@e))
        finite_fields=[result[k] for k in ('CL','CD','CDi','Cm','CDi_near','CDp','CDbody','CDam','CDeng','CDrate')]
        finite=all(np.all(np.isfinite(x)) for x in (gamma,local,projected,replay,force,moment,result['force'],result['moment'],finite_fields))
        finite=finite and (result['efficiency'] is None or math.isfinite(result['efficiency']))
        mach=result['lifting_airflow']['maximum']['normal_mach']
        residual=float(result['residual'])
        checks=record['numerical_checks']
        checks.extend([dict(name='no parser diagnostics',passed=not model.diagnostics),
            dict(name='converged',passed=bool(result['converged'])),
            dict(name='finite circulation, residuals, loads and available coefficients',passed=bool(finite)),
            dict(name='projected circulation residual',value=residual,tolerance=1e-8,
                 passed=math.isfinite(residual) and 0<=residual<=1e-8),
            dict(name='local section-normal Mach',value=mach,upper_exclusive=1.,
                 passed=math.isfinite(mach) and 0<=mach<1.)])
        errors={'CL force normalization':abs(predicted['lift']/qs-result['CL']),
            'CD force normalization':abs(predicted['drag']/qs-result['CD']),
            'Cm moment normalization':abs(moment[1]/(qs*chord)-result['Cm']),
            'near-field drag decomposition':abs(result['CD']-sum(result[k] for k in ('CDi_near','CDp','CDbody','CDam','CDeng','CDrate'))),
            'reconstructed total force':np.max(abs(force-result['force']))/qs,
            'reconstructed total moment':np.max(abs(moment-result['moment']))/(qs*chord),
            'reported residual norm':abs(residual-float(np.max(abs(projected),initial=0))),
            'independent Fourier projection':float(np.max(abs(replay-projected),initial=0))}
        for name,error in errors.items():
            value=float(error)
            checks.append(dict(name=name,value=value,tolerance=2e-10,
                               passed=math.isfinite(value) and 0<=value<=2e-10))
        if not all(c['passed'] for c in checks):
            raise ValueError('Independent numerical verification failed.')
        record['reference_checks']=reference_checks(predicted,job['reference_row'])
        assert len(record['reference_checks'])==7
        record.update(status='computed',predicted=predicted,numerical_checks_passed=True,
                      reference_match=all(c['passed'] for c in record['reference_checks']))
    except Exception as error:
        record.update(status='error',error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        if getattr(error,'details',None) is not None:record['error_details']=error.details
    record['seconds']=time.monotonic()-start
    try:
        verify(protocol['source_pins'])
        assert pin(out/'protocol.json')==expected_protocol
        record['source_pins_unchanged']=True
    except Exception as error:
        record.update(status='error',source_pins_unchanged=False,pin_error=str(error))
    write(stage/'result.json',record)
    print(json.dumps(dict(id=job_id,status=record['status'],seconds=record['seconds'])),flush=True)
    return 0 if record['status']=='computed' else 1


def execute(out):
    expected_protocol=json.loads((out/'preparation-receipt.json').read_text())['protocol']
    assert pin(out/'protocol.json')==expected_protocol
    protocol=json.loads((out/'protocol.json').read_text())
    verify(protocol['source_pins'])
    assert not (out/'report.json').exists() and not (out/'jobs').exists(), 'No replay or retry in this scope.'
    records=[];started=time.monotonic()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    interrupted=[None]
    def request_stop(signum, frame):
        # Do not raise between process creation and assigning its handle.
        # The bounded poll loop observes the flag, terminates and reaps it.
        interrupted[0]=signum
    signal.signal(signal.SIGTERM,request_stop)
    signal.signal(signal.SIGINT,request_stop)
    for job in protocol['jobs']:
        if interrupted[0] is not None:break
        stage=out/'jobs'/job['id'];stage.mkdir(parents=True)
        print(json.dumps(dict(event='start',id=job['id'])),flush=True)
        begin=time.monotonic();timed_out=False;signals=[]
        proc=None
        with (stage/'stdout.log').open('w') as stdout,(stage/'stderr.log').open('w') as stderr:
            try:
                proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',job['id'],'--output-dir',str(out)],
                    cwd=ROOT,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
                deadline=time.monotonic()+CAP
                while proc.poll() is None and interrupted[0] is None and time.monotonic()<deadline:
                    time.sleep(.1)
                if proc.poll() is None:
                    timed_out=interrupted[0] is None
                    signals.append('SIGTERM')
                    try:os.killpg(proc.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                    try:proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        signals.append('SIGKILL')
                        try:os.killpg(proc.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                proc.wait()
            finally:
                if proc is not None:
                    if proc.poll() is None:
                        signals.append('SIGKILL')
                        try:os.killpg(proc.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                    proc.wait()
        result_path=stage/'result.json'
        record=json.loads(result_path.read_text()) if result_path.exists() else dict(id=job['id'],status='timeout' if timed_out else 'error',
            error='Worker exceeded cap.' if timed_out else 'Worker exited without a result.',
            reference_checks=[],numerical_checks=[],required_reference_checks=7,
            physical_calls=int((stage/'call-started.json').exists()))
        record['process']=dict(pid=proc.pid,returncode=proc.returncode,reaped=proc.poll() is not None,
            timed_out=timed_out,signals=signals,interrupted_by_parent_signal=interrupted[0],
            wall_seconds=time.monotonic()-begin,cap_seconds=CAP)
        if timed_out or proc.returncode not in (0,1):record['status']='timeout' if timed_out else 'error'
        if record['status']=='computed' and proc.returncode!=0:record['status']='error'
        record['job']=job
        records.append(record)
        write(stage/'supervisor-result.json',record)
        write(out/'progress.json',dict(completed=len(records),planned=22,records=records))
        print(json.dumps(dict(event='finish',id=job['id'],status=record['status'],seconds=record['process']['wall_seconds'])),flush=True)
    verify(protocol['source_pins'])
    assert pin(out/'protocol.json')==expected_protocol
    checks=[c for r in records if r['status']=='computed' for c in r['reference_checks']]
    report=dict(format='sa4-fourier-refinement-results-v1',status='INTERRUPTED' if interrupted[0] else 'COMPLETED',protocol=pin(out/'protocol.json'),
        source_pins_unchanged=True,seconds=time.monotonic()-started,records=records,
        interrupted_by_signal=interrupted[0],unattempted_job_ids=[j['id'] for j in protocol['jobs'][len(records):]],
        counts=dict(jobs=22,attempted=len(records),unattempted=22-len(records),computed=sum(r['status']=='computed' for r in records),
            errors=sum(r['status']=='error' for r in records),timeouts=sum(r['status']=='timeout' for r in records),
            reaped=sum(r['process']['reaped'] for r in records),physical_calls=sum(r['physical_calls'] for r in records),
            required_reference_checks=154,reported_reference_checks=len(checks),finite_reference_checks=sum(c['predicted'] is not None for c in checks),
            reference_passes=sum(c['passed'] for c in checks),complete_reference_rows=sum(r.get('reference_match',False) and r['status']=='computed' for r in records),
            numerical_checks=sum(len(r['numerical_checks']) for r in records),numerical_checks_passed=sum(c['passed'] for r in records for c in r['numerical_checks'])),
        registered_scores_changed=False,qualifications=protocol['qualifications'])
    write(out/'report.json',report)
    print(json.dumps(dict(event='complete',counts=report['counts'],report=pin(out/'report.json'))),flush=True)
    return 128+interrupted[0] if interrupted[0] else (0 if report['counts']['computed']==22 else 1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true');action.add_argument('--execute',action='store_true')
    action.add_argument('--worker')
    parser.add_argument('--output-dir',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args();out=args.output_dir.resolve()
    if args.prepare:prepare(out);return 0
    if args.worker:return worker(out,args.worker)
    return execute(out)


if __name__=='__main__':
    raise SystemExit(main())
