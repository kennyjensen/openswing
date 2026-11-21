"""Conditional native-MM comparison at saved roll-acceleration equilibria.

This does not change the primary AE-3 adapter or award primary passes. It
tests fixed-acceleration derivatives about an explicitly nonzero-acceleration
base. The original 20O and independently documented sibling lift-control
scale are separate cases. No new equilibrium solve or parameter fit is used.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from scripts import isae_suite_ae3 as adapter
from scripts.isae_acceptance import apply_reference_acceptance
from scripts.replay_isae_ae3_bounded import LIMITS, THREADS, limits, read, write

OUT = ROOT / 'artifacts/isae/ae3-mm-setup-r2-20261111'
CONSTRAINT = dict(variable='angular_acceleration.x', quantity='moment.x', target=0.)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def prepare():
    require(not OUT.exists(), 'Preserve prior evidence; output directory already exists.')
    jobs = adapter.plan(ROOT)
    catalog = read(ROOT / adapter.CATALOG)
    paths = {Path(__file__), ROOT / adapter.CATALOG,
             ROOT / 'scripts/isae_suite_ae3.py', ROOT / 'scripts/isae_ae3_observables.py',
             ROOT / 'scripts/isae_acceptance.py', ROOT / 'scripts/replay_isae_ae3_bounded.py',
             ROOT / 'docs/validation/aswing-authoritative-references.md',
             ROOT / 'docs/validation/aswing-authoritative-sources.json',
             ROOT / 'docs/validation/isae-ae3-roll-sweep-20261111.md'}
    paths.update((ROOT / 'openswing').glob('*.py'))
    cases = []
    for parent in ('ae3-roll-constraint-r2-20261111', 'ae3-roll-control-20261111'):
        parent_path = ROOT / 'artifacts/isae' / parent / 'plan.json'
        old_plan = read(parent_path)
        paths.add(parent_path)
        for old in old_plan['cases']:
            op = old['job']['native_operating_point']
            job = next(j for j in jobs if j['target_kind'] == 'native_coefficients'
                       and j['native_operating_point'] == op and j['nominal'] == 80)
            paths.update(Path(p['path']) for p in job['source_pins'])
            folder = parent_path.parent / 'cases' / old['name']
            for name in ('request.json', 'result.json', 'report.json', 'terminal.json', 'sources-verified.json'):
                paths.add(folder / name)
            request, report, terminal = [read(folder / name) for name in
                                        ('request.json', 'report.json', 'terminal.json')]
            require(report['numerical_pass'] and terminal['returncode'] == 0
                    and terminal['process_reaped'], 'Saved state lacks completed physical evidence.')
            sibling = 'sibling-lift' in old['name']
            literal = Path(job['source']).read_text()
            expected = literal.replace('0.0581', '0.0686') if sibling else literal
            require(literal.count('0.0581') == 1 and request['source'] == expected,
                    'Saved model differs from its declared literal/sibling-control input.')
            if sibling:
                sibling_path = Path(job['source']).with_name('Straight_60O.asw')
                paths.add(sibling_path)
                require('0.0686' in sibling_path.read_text(), 'Independent sibling slope absent.')
            require(request['condition'] == job['condition'] and request['panels'] == job['panels']
                    and request['gravity'] == job['gravity'] and request['operating_constraints'] == [CONSTRAINT]
                    and request['numerics'] == dict(beam_interpolation='drela-segspl-v1',
                                                    structural_operator='drela-moving-airflow-v1'),
                    'Saved operating setup differs from the declared diagnostic.')
            changed_kernel = [p['path'] for p in old_plan['pins'] if '/openswing/' in p['path']
                              and adapter._pin(p['path'])['sha256'] != p['sha256']]
            require(set(changed_kernel) <= {str(ROOT / 'openswing/local_geometry_matrix.py')},
                    'Unexpected physical-kernel change since saved equilibrium.')
            native = next(e for e in catalog['native_exports'] if e['operating_point'] == op)
            cases.append(dict(name=old['name'],folder=str(folder),job=job,
                              observations=[adapter._observation(o) for o in native['observations']],
                              control_lift_slope=.0686 if sibling else .0581,
                              changed_kernel_since_save=changed_kernel))
    OUT.mkdir()
    write(OUT / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
          cases=cases,pins=[adapter._pin(p) for p in sorted(paths)],limits=LIMITS,
          constraint=CONSTRAINT,primary_votes_added=0,method=__doc__,
          qualifications=[
              'Original MM base mask/build identity and derivative response convention remain unresolved.',
              'The sibling lift slope is independently sourced, not fitted or proven to generate native 20O exports.',
              'Only physical state is transferred after solving trim; the actual nonzero acceleration is then fixed.',
              'Both derivative base operators are moving-airflow. This does not claim coupled-versus-airflow parity.',
              'The saved-state kernel difference is the documented geometry-buffer lifetime fix; all residuals and outputs are freshly checked.',
              'No primary fractions, native tolerances or denominators change.']))
    print(json.dumps(dict(prepared=[c['name'] for c in cases],limits=LIMITS)),flush=True)


def reference_checks(observations, values):
    require(len(observations) == len({o['name'] for o in observations}) == 96,
            'The full native comparison requires 96 unique fields.')
    require(set(values) == {o['name'] for o in observations}, 'Missing or extra native outputs.')
    checks = []
    for o in observations:
        predicted = float(values[o['name']])
        require(math.isfinite(predicted), 'Nonfinite native prediction.')
        error = abs(predicted - o['expected'])
        checks.append(dict(**o,predicted=predicted,abs_error=error,
                           comparison='<=',passed=error <= o['tolerance']))
    return checks


def worker(request_path, digest):
    started, cpu = time.monotonic(), time.process_time()
    folder = Path(request_path).parent
    try:
        raw = Path(request_path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'Authenticated request changed.')
        packet = json.loads(raw)
        case = packet['case']
        for p in packet['input_pins']:
            require(adapter._pin(p['path']) == p, 'Saved input changed after source audit.')
        import numpy as np
        from openswing.asw import parse_asw
        from openswing.aero import FlightCondition
        from openswing.source_airflow import SourceAirflowNetwork
        from openswing.equilibrium_state import restore, identity, matching_identity
        from scripts.isae_ae3_observables import complete_observables

        old_folder = Path(case['folder'])
        request, saved = read(old_folder / 'request.json'), read(old_folder / 'result.json')
        model = parse_asw(request['source'],beam_interpolation='drela-segspl-v1')
        require(not model.diagnostics, 'Model parsing diagnostics.')
        c = deepcopy(request['condition'])
        for key in ('controls','powers','circulation_modes'):
            c[key] = {int(k):v for k,v in c[key].items()}
        original = SourceAirflowNetwork(model,request['panels'],FlightCondition(**c),request['gravity'],(),
                                       operating_constraints=[CONSTRAINT],steady_trim=True)
        require(matching_identity(identity(original),saved['equilibrium_state']['identity']),
                'Saved operator/mesh identity differs.')
        state = restore(original,saved['equilibrium_state'])
        require(original.nfev == 0, 'Restore unexpectedly evaluated a residual.')
        checks = []
        def check(name,value,gate):
            row = dict(name=name,metric=float(value),gate=gate,
                       passed=bool(np.isfinite(value) and value <= gate))
            checks.append(row)
            require(row['passed'], 'Failed transfer check: '+str(row))
        def relative(a,b):
            a,b = np.asarray(a),np.asarray(b)
            return np.max(abs(a-b),initial=0)/max(1.,np.max(abs(b),initial=0))
        residual, data = original.residual(state,detail=True)
        check('original_full_residual',np.max(abs(residual)),1e-8)
        condition,motion,operating_values = original.operating.apply(state[original.operating_start:])
        require(np.any(motion.angular_acceleration), 'Diagnostic requires nonzero solved acceleration.')
        for axis,value in zip('xyz',motion.angular_acceleration):
            check('saved_angular_acceleration_'+axis,abs(value-saved['operating_values']['angular_acceleration.'+axis]),2e-10)
        check('zero_angular_rates',np.max(abs(motion.rates)),0.)
        root = next(v['a'] for v in original.constraints if v['kind']=='ground')
        check('root_position',np.max(abs(data['r'][root]-case['job']['root_position'])),1e-10)
        check('root_frame',np.max(abs(data['Q'][root]-np.eye(3))),1e-10)
        qS = .5*condition.density*condition.speed**2*model.reference[0,0]
        net_moment = (data['moment']+np.cross(data['r']-model.reference[1],data['force'])).sum(axis=0)
        check('net_roll_moment',abs(net_moment[0])/max(1.,qS*model.reference[0,2]),1e-8)
        def mapped(a):
            return adapter.coefficients(a['distributed_aero_force'],a['distributed_aero_moment'],
                                        condition.alpha,qS,model.reference[0,1],model.reference[0,2])
        base = mapped(data['aero'])
        check('saved_coefficients',relative(list(base.values()),list(mapped(saved).values())),2e-10)
        fixed = SourceAirflowNetwork(model,request['panels'],condition,request['gravity'],(),steady_trim=True)
        require(fixed.size == fixed.operating_start == original.operating_start
                and fixed.nn == original.nn and fixed.ne == original.ne
                and all(np.array_equal(fixed.station_nodes[k][0],v[0]) for k,v in original.station_nodes.items()),
                'Physical state layout changed while freezing trim.')
        physical = state[:original.operating_start].copy()
        fixed_residual,fixed_data = fixed.residual(physical,detail=True)
        check('fixed_full_residual',np.max(abs(fixed_residual)),1e-8)
        check('physical_residual_transfer',relative(fixed_residual,residual[:original.operating_start]),2e-10)
        check('physical_geometry_transfer',relative(fixed_data['r'],data['r']),2e-10)
        check('physical_frame_transfer',relative(fixed_data['Q'],data['Q']),2e-10)
        check('physical_output_transfer',relative(list(mapped(fixed_data['aero']).values()),list(base.values())),2e-10)
        report = complete_observables(fixed,physical,None,base,derivatives=True)
        require(report['base_operator'] == report['source_operator'] == 'drela-moving-airflow-v1'
                and report['response'] == 'fixed_acceleration' and report['axes'] == 'stability'
                and report['numerical_gates'] == adapter.OBSERVABLE_GATES
                and report['factorization_count'] == 1 and report['response_columns'] == 7
                and len(report['checks']) == 31 and all(c['passed'] for c in report['checks'])
                and len(report['values']) == 90, 'Incomplete diagnostic derivative evidence.')
        check('saved_apparent_spatial_matrix',relative(report['mass_properties']['apparent_spatial_matrix'],
                                                     saved['apparent_mass']['spatial_matrix']),2e-10)
        strict = reference_checks(case['observations'],{**base,**report['values']})
        write(folder / 'raw-result.json',dict(status='pending_source_audit',numerical_pass=False,
              reference_checks=strict,reference_match=False,transfer_checks=checks,observable_report=report,
              actual_angular_acceleration=motion.angular_acceleration.tolist(),
              derivative_response='fixed at solved base acceleration; no derivative of the roll-trim constraint',
              cold_solves=0,restores=1,primary_votes_added=0,
              timing=dict(wall_seconds=time.monotonic()-started,cpu_seconds=time.process_time()-cpu,
                          peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))
    except Exception as exc:
        write(folder / 'raw-result.json',dict(status='error',numerical_pass=False,
              error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc(),primary_votes_added=0))


def launch(name):
    plan = read(OUT / 'plan.json')
    require(adapter._stable(plan['pins']), 'Planned source evidence changed.')
    case = next(c for c in plan['cases'] if c['name'] == name)
    folder = OUT / 'cases' / name
    folder.mkdir(parents=True,exist_ok=False)
    request = folder / 'request.json'
    write(request,dict(case=case,input_pins=[adapter._pin(Path(case['folder'])/p)
                                          for p in ('request.json','result.json')]))
    request_pin = adapter._pin(request)
    started = time.monotonic()
    with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
        child = subprocess.Popen([sys.executable,__file__,'worker',str(request),request_pin['sha256']],
                cwd=ROOT,env={**os.environ,**THREADS},stdout=out,stderr=err,
                start_new_session=True,preexec_fn=limits)
        timed_out = False
        try:
            child.wait(timeout=LIMITS['wall_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid,signal.SIGKILL)
            child.wait()
        finally:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait()
    terminal = dict(observed_utc=datetime.now(timezone.utc).isoformat(),returncode=child.returncode,
                    process_reaped=True,timed_out=timed_out,wall_seconds=time.monotonic()-started,limits=LIMITS)
    write(folder/'terminal.json',terminal)
    require(adapter._stable(plan['pins']) and adapter._pin(request)==request_pin,
            'Source or request evidence changed during worker.')
    result = read(folder/'raw-result.json') if (folder/'raw-result.json').exists() else {}
    if child.returncode == 0 and result.get('status') == 'pending_source_audit':
        result.update(status='computed',numerical_pass=True,
                      reference_match=all(c['passed'] for c in result['reference_checks']))
        write(folder/'strict-result.json',result)
        result = apply_reference_acceptance(result,relative_tolerance=.05)
        write(folder/'result.json',result)
        write(folder/'sources-verified.json',dict(all_pins_checked_before_and_after=True,
              plan=adapter._pin(OUT/'plan.json'),request=request_pin))
    print(json.dumps(dict(name=name,**terminal,status=result.get('status','no_result'),
          matched=sum(c['passed'] for c in result.get('reference_checks',[])),
          required=96,error=result.get('error'))),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','launch','worker'))
    parser.add_argument('arguments',nargs='*')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'launch':
        launch(*args.arguments)
    else:
        worker(*args.arguments)
