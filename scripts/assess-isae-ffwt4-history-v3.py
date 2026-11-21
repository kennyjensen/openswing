"""Audit full or partial FFWT-4 histories without assuming a particular mesh."""
import argparse
from decimal import Decimal
import importlib.util
import math
from pathlib import Path
import statistics
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.isae_ffwt4_evidence import KernelArchive, pin, read, require, write
spec = importlib.util.spec_from_file_location('ffwt4_native_rows', ROOT/'scripts/assess-isae-ffwt4-time.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
DT = Decimal('.0149')


def snapshot_value(snapshot, tick, divisor):
    require(divisor in (2,4,8,16), 'Unsupported time grid')
    dt = float(DT/divisor)
    require(abs(snapshot['time']-float(tick*DT/divisor)) <= 1e-10, 'Snapshot clock differs')
    require(snapshot['converged'] and math.isfinite(snapshot['residual']) and snapshot['residual'] <= 1e-8,
            'Unconverged snapshot')
    if tick:
        method = snapshot['restart']['accepted_method']
        order = 1 if tick == 1 else 2
        expected = [1/dt,-1/dt,0.] if order == 1 else [1.5/dt,-2/dt,.5/dt]
        require(method['scheme'] == 'drela-euler-bdf-v1', 'Unexpected integration scheme')
        require(method['effective_order'] == order, 'Continuation restarted the integration order')
        require(len(method['coefficients']) == len(expected) and all(
            math.isclose(a,b,rel_tol=2e-11,abs_tol=1e-9) for a,b in zip(method['coefficients'],expected)),
            'Captured BDF coefficients differ from the physical time grid')
    sensors = [v for v in snapshot['sensors'] if v['index'] == 1]
    require(len(sensors) == 1 and sensors[0]['load_trace'] == 'left', 'Root sensor trace changed')
    moment = sensors[0]['moment_local'][0]
    require(math.isfinite(moment), 'Nonfinite root moment')
    return moment


def assess(folder):
    root = folder.resolve().parent
    last = read(folder/'plan.json')
    archive = KernelArchive(last['kernel_archive']['path'],last['kernel_pins'])
    require(last['kernel_archive'] == archive.manifest_pin, 'Archive manifest changed')
    checked, resolved = {}, {}
    def verify(record):
        if record['path'] in checked:
            require(checked[record['path']] == record, 'Conflicting evidence hashes')
        else:
            actual = archive.verify(record)
            checked[record['path']] = record
            require(actual['path'] not in resolved or resolved[actual['path']] == actual, 'Conflicting resolved hashes')
            resolved[actual['path']] = actual
    journal_pin = pin(root/'serial-terminal.json')
    jobs = read(journal_pin['path'])['jobs']
    receipts = {j['folder']:j for j in jobs}
    require(len(receipts) == len(jobs), 'Duplicate terminal receipt')
    chain, visited = [], set()
    while True:
        folder = folder.resolve()
        require(folder.parent == root and folder not in visited, 'Invalid continuation ancestry')
        visited.add(folder)
        plan, report = read(folder/'plan.json'), read(folder/'report.json')
        require(plan['schema'] == 'isae-ffwt4-fixed1-refinement-v3', 'Unexpected history schema')
        require(report['status'] == 'SEGMENT_COMPUTED' and report['source_pins_unchanged'] and
                report['kernel_pins_unchanged'], 'Incomplete segment evidence')
        require(receipts.get(folder.name,{}).get('exit_code') == 0, 'No successful process exit')
        require(plan['kernel_archive'] == report['kernel_archive'] == archive.manifest_pin and
                plan['runtime_kernel_pins'] == archive.runtime_pins, 'Runtime kernel changed')
        declared = {p['path'] for p in archive.runtime_pins}
        loaded = report['loaded_kernel_modules']
        require(loaded and all(v['path'] in declared for v in loaded) and
                {'openswing','openswing.bridge','openswing.time_integration'} <= {v['module'] for v in loaded},
                'Runtime modules were not attributed to the archive')
        records = plan['source_pins']+plan['kernel_pins']+plan['runtime_kernel_pins']+[plan[k] for k in
            ('helper','initial_helper','initial_plan','initial_request','initial_result','initial_report','kernel_archive','evidence_helper')]
        records += [plan[k] for k in ('parent_plan','parent_report','parent_checkpoint','parent_time_helper') if k in plan]
        records += [report[k] for k in ('request','result','checkpoint')]
        records += [receipts[folder.name][k] for k in ('helper','runner') if k in receipts[folder.name]]
        records += [pin(folder/'plan.json'),pin(folder/'report.json')]
        for record in records: verify(record)
        chain.append((folder,plan,report))
        if 'parent_checkpoint' not in plan: break
        folder = Path(plan['parent_checkpoint']['path']).parent
    chain.reverse()
    first = chain[0][1]
    initial_plan = read(first['initial_plan']['path'])
    initial_request = read(first['initial_request']['path'])
    initial_result = read(first['initial_result']['path'])
    identity = initial_result['equilibrium_state']['identity']
    require(first['nominal'] == initial_plan['nominal'] and first['source_pins'] == initial_plan['source_pins'] and
            first['kernel_pins'] == initial_plan['kernel_pins'], 'History changed the initial mesh, inputs or equations')
    require(first['accuracy_gate']['relative'] == .001, 'Accuracy limit changed')
    divisor = first['divisor']
    require(divisor in (2,4,8,16), 'Unsupported time grid')
    dt = DT/divisor
    samples, accepted, maximum_residual = {}, 0, 0.
    for index,(folder,plan,report) in enumerate(chain):
        for key in ('source_pins','kernel_pins','nominal','divisor','dt','native_dt','accuracy_gate',
                    'initial_plan','initial_request','initial_result','initial_report','initial_helper'):
            require(plan[key] == first[key], 'Continuation changed configuration: '+key)
        start,end = plan['start_step'],plan['end_step']
        require(start == accepted and 1 <= end-start <= 10 and end <= 199*divisor, 'Noncontiguous or oversized segment')
        require(Decimal(plan['dt']) == dt and Decimal(plan['native_dt']) == DT, 'Changed time grid')
        require((report['nominal'],report['start_step'],report['end_step'],report['accepted_steps'],report['rejected_steps']) ==
                (first['nominal'],start,end,end-start,0), 'Segment accounting differs')
        request = read(report['request']['path'])
        if index == 0:
            expected = read(first['initial_request']['path'])
            expected.update(action='time',mode='time')
            expected.pop('tolerance'); expected.pop('continuation_steps')
            expected['condition']['gust'] = dict(type='cosine',amplitude=[0.,0.,.6978],
                origin=[-10.9366,0.,0.],normal=[-1.,0.,0.],length=10.9366,speed=0.)
            expected['time'] = dict(frame='prescribed',duration=float(end*dt),dt=float(dt),order=2,
                tolerance=1e-8,continuation_steps=4,max_steps=end)
        else:
            expected = dict(action='resume_time',source=initial_request['source'],numerics=initial_request['numerics'],
                checkpoint=read(plan['parent_checkpoint']['path']),time=dict(duration=float((end-start)*dt),dt=float(dt),order=2))
        require(request == expected, 'History request changed physical inputs or its checkpoint')
        del request, expected
        data = read(report['result']['path'])
        require(data['converged'] and data['accepted_steps'] == end-start and data['rejected_steps'] == 0 and
                len(data['snapshots']) == end-start+1 and abs(data['maximum_step']-float(dt)) < 1e-12,
                'Incomplete saved segment')
        require(data['restart_context']['identity'] == identity and
                data['restart_context']['setup']['panels'] == initial_request['panels'], 'Saved history changed mesh')
        if index: require(data['checkpoint_validation']['discrete_replayed'], 'Checkpoint was not replayed')
        for offset,snapshot in enumerate(data['snapshots']):
            tick = start+offset
            moment = snapshot_value(snapshot,tick,divisor)
            if tick in samples: require(abs(moment-samples[tick]['moment']) <= 1e-8, 'Restart changed the shared moment')
            samples[tick] = dict(time=snapshot['time'],moment=moment,residual=snapshot['residual'])
            maximum_residual = max(maximum_residual,snapshot['residual'])
        del data
        accepted = end
    require(sorted(samples) == list(range(accepted+1)) and abs(samples[0]['moment']-first['initial_moment']) <= 1e-8,
            'Initial state or sample coverage differs')
    outputs = [Path(p['path']) for p in first['source_pins'] if Path(p['path']).suffix == '.txt']
    require(len(outputs) == 8, 'Fixed-history target inventory changed')
    checks = []
    for path in outputs:
        for row in native.native_rows(path):
            value = Decimal(row['token']); half = Decimal(10)**value.as_tuple().exponent/2
            tick = (row['row']-1)*divisor
            predicted = None
            if path.name == 'FFWT_Fixed-1.txt':
                t = Decimal(row['time_token']); rounding = Decimal(10)**t.as_tuple().exponent/2
                require(abs(t-(row['row']-1)*DT) <= rounding, 'Native physical clock differs')
                if tick in samples: predicted = samples[tick]['moment']
            checks.append(dict(row,name=path.stem+':row'+str(row['row']),predicted=predicted,
                exact_decimal_expected=str(value),exact_decimal_tolerance=str(half),comparison='<=',
                passed=predicted is not None and abs(Decimal(str(predicted))-value) <= half))
    require(len(checks) == 1600, 'Native denominator changed')
    comparison = native.apply_reference_acceptance(dict(status='computed',numerical_pass=True,reference_checks=checks))
    computed = [r for r in comparison['reference_checks'] if r['predicted'] is not None]
    errors = [100*r['relative_error'] for r in computed]
    for record in [pin(ROOT/'scripts/assess-isae-ffwt4-time.py'),pin(ROOT/'scripts/isae_acceptance.py')]: verify(record)
    require(pin(journal_pin['path']) == journal_pin, 'Terminal receipts changed during assessment')
    selected = {p.name for p,_,_ in chain}
    return dict(status='HISTORY_ASSESSED',complete=accepted == 199*divisor,nominal=first['nominal'],nodes=len(identity['nodes']),
        divisor=divisor,dt=str(dt),accepted_steps=accepted,required_steps=199*divisor,rejected_steps=0,
        end_time=samples[accepted]['time'],segments=len(chain),maximum_residual=maximum_residual,samples=samples,
        summary=dict(computed=len(computed),passed=sum(r['passed'] for r in computed),fixed_history_required=1600,
                     uncomputed=1600-len(computed),median_error_percent=statistics.median(errors),maximum_error_percent=max(errors)),
        checks=comparison['reference_checks'],acceptance=comparison['reference_acceptance_policy'],
        plans=[pin(p/'plan.json') for p,_,_ in chain],reports=[pin(p/'report.json') for p,_,_ in chain],
        inputs=list(resolved.values()),logical_inputs=list(checked.values()),kernel_archive=archive.manifest_pin,
        helper=pin(__file__),evidence_helper=pin(ROOT/'scripts/isae_ffwt4_evidence.py'),terminal_journal=journal_pin,
        excluded_attempts=[dict(folder=j['folder'],exit_code=j['exit_code']) for j in jobs if j['folder'] not in selected],
        time_accuracy=None,spatial_accuracy=None,physical_solves=0,full_family_validated=False,
        qualifications=first['qualifications'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--last-segment',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    require(not args.output.exists(),'Preserve earlier assessments')
    result = assess(args.last_segment)
    write(args.output,result)
    print(json.dumps({k:result[k] for k in ('complete','nominal','nodes','accepted_steps','required_steps','rejected_steps',
        'end_time','maximum_residual','summary','excluded_attempts')}),flush=True)


if __name__ == '__main__':
    main()
