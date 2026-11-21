#!/usr/bin/env python3
"""Original FFWT alpha-5 archived-ASWING pilot, with separate physical gates.

Two declared cold meshes, no fitted properties or experimental acceptance gate.
The finer solve runs only after the first passes every physical check.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
THREADS = {k: '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def unchanged(plan):
    return all(pin(p['path']) == p for p in plan['pins'])


def prepare(stage, contract):
    require(not stage.exists(), 'Use a new output directory.')
    stage.mkdir(parents=True)
    reference = read(contract)
    source_path = ROOT/'examples/isae-ffwt-flare10.asw'
    require(pin(source_path)['sha256'] == reference['model']['sha256'], 'Original source pin differs.')
    source = source_path.read_bytes().decode()
    template = read(ROOT/'examples/isae-ae2-source-coupled-project.json')
    cases = []; inputs = [Path(__file__), contract, source_path]
    for definition in reference['cases']:
        name = definition['name']; folder = stage/'cases'/name
        request = dict(action='solve', mode='mounted', source=source, panels=definition['panels'],
            condition=reference['condition'], numerics=reference['request_template']['numerics'],
            operating_constraints=[], strut_mode='bilateral', controller=None)
        config = deepcopy(template['cases'][0]['configuration'])
        config.update(source=source, filename='isae-ffwt-flare10.asw', mesh=definition['panels'],
            numerics=request['numerics'], controls={'1': '0'}, powers={},
            circulation={str(i): '0' for i in (1, 2, 3)}, constraints=[],
            equilibrium=dict(state=None, enabled=False, label=''))
        config['fields'].update({'mode': 'mounted', 'speed': str(reference['condition']['speed']),
            'alpha': '5', 'beta': '0', 'density': '1.2256', 'gravity-magnitude': '9.81',
            'static-gravity-z': '-9.81', 'static-gravity-mode': 'file', 'pg-mach': '0',
            'ground-effect': '0', 'freeze-influences': False, 'trim-roll': '1',
            'trim-pitch': '1', 'trim-yaw': '1', 'trim-engine': ''})
        case_id = 'isae-ffwt-'+name
        project = dict(format='openswing-project', version=2, name='ISAE original FFWT '+name,
            selected=case_id, cases=[dict(id=case_id, name='Original FFWT '+name, configuration=config)],
            solutions=[], selected_solution=None)
        write(folder/'request.json', request); write(folder/'input-project.json', project)
        inputs.extend([folder/'request.json', folder/'input-project.json'])
        cases.append(dict(name=name, request=str(folder/'request.json')))
    # Freeze code and the reference contract before any physical evaluation.
    inputs += sorted((ROOT/'openswing').glob('*.py'))
    plan = dict(status='PREPARED', reference=reference, cases=cases, pins=[pin(p) for p in inputs],
        kernel_pins={p.name: pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))},
        gates=reference['gates'], child_cap_seconds=reference['execution']['child_cap_seconds'],
        thread_environment=THREADS, cold_solves=2, fresh_residuals=2)
    write(stage/'plan.json', plan)
    print(json.dumps(pin(stage/'plan.json')), flush=True)


def worker(stage, name):
    plan = read(stage/'plan.json'); require(unchanged(plan), 'Inputs changed.')
    folder = stage/'cases'/name
    require(not (folder/'started.json').exists(), 'No repeated worker execution.')
    write(folder/'started.json', dict(pid=os.getpid(), started=time.time()))
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.discretization import requirements, report as mesh_report
    from openswing.network import network_snapshot, exp, log
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.equilibrium_state import identity, matching_identity, restore, warm_start_recipe

    request = read(folder/'request.json'); source = request['source']
    model = parse_asw(source, beam_interpolation=request['numerics']['beam_interpolation'])
    require(model.dumps() == source, 'Source changed on import.')
    condition_values = deepcopy(request['condition'])
    for key in ('controls', 'powers'):
        condition_values[key] = {int(k): v for k, v in condition_values[key].items()}
    condition = FlightCondition(**condition_values)
    net = SourceCoupledNetwork(model, request['panels'], condition, None, [])
    stations = {str(k): t.tolist() for k, (t, _) in net.station_nodes.items()}
    required = requirements(model, [], mesh_recipe=net.mesh_recipe)
    for beam, values in plan['reference']['geometry']['required_stations'].items():
        require(all(np.any(np.isclose(stations[beam], t, atol=1e-14, rtol=0)) for t in values), 'Missing attachment station.')
    require(net.nfev == 0, 'Geometry preflight evaluated a residual.')
    write(folder/'preflight.json', dict(stations=stations, required=required,
        mesh=mesh_report(model, net.meshes, net.panels, net.loads), nodes=net.nn, elements=net.ne,
        identity=identity(net), nfev=net.nfev, source=pin(ROOT/'examples/isae-ffwt-flare10.asw')))
    del net
    started = time.monotonic(); progress_count = 0
    with (folder/'progress.jsonl').open('w') as stream:
        def progress(*args):
            nonlocal progress_count
            progress_count += 1
            stream.write(json.dumps(dict(seconds=time.monotonic()-started, event=args))+'\n'); stream.flush()
        result = dispatch(request, progress=progress)
    elapsed = time.monotonic()-started
    write(folder/'result.json', result)
    state = result['equilibrium_state']; saved = deepcopy(state)
    net = SourceCoupledNetwork(model, request['panels'], condition, None, [],
        mesh_recipe=warm_start_recipe(model, request['panels'], state))
    checks = []
    def check(label, ok, **detail):
        checks.append(dict(name=label, passed=bool(ok), **detail))
    def close(label, a, b, atol=2e-10, rtol=2e-10):
        a, b = np.asarray(a), np.asarray(b)
        check(label, a.shape == b.shape and np.allclose(a, b, atol=atol, rtol=rtol),
            maximum=float(np.max(abs(a-b))) if a.shape == b.shape and a.size else 0.)
    check('saved_identity', matching_identity(state['identity'], identity(net)))
    x = restore(net, state)
    check('restore_without_physics', net.nfev == 0)
    residual, data = net.residual(x, detail=True)
    snapshot = network_snapshot(net, residual, data)
    error = float(np.max(abs(residual)))
    check('one_fresh_residual', net.nfev == 1)
    check('full_residual', np.isfinite(residual).all() and error <= plan['gates']['residual'], maximum=error)
    check('state_unchanged', saved == state)
    check('converged', result['converged'])
    check('two_hinge_charts_no_launch', state['version'] == 2 and len(state['hinge_charts']) == 2 and 'launch' not in state)
    for kind in ('force', 'moment'):
        a, b = np.asarray(snapshot['applied_'+kind]), np.asarray(snapshot['support_'+kind])
        scale = max(1., float(np.linalg.norm(a)+np.linalg.norm(b)))
        defect = float(np.linalg.norm(a+b))/scale
        check(kind+'_balance', defect <= plan['gates']['balance'], normalized_defect=defect)
    close('literal_mass', snapshot['mass_properties']['mass'], .8959168)
    close('restored_internal_force', data['N'], state['internal_force'])
    close('restored_internal_moment', data['M'], state['internal_moment'])
    for field in ('position', 'rotation'):
        close('restored_node_'+field, [n[field] for n in snapshot['nodes']], [n[field] for n in result['nodes']])
    for field in ('force', 'moment'):
        close('restored_reaction_'+field, [r[field] for r in snapshot['reactions']], [r[field] for r in result['reactions']])
    # Test kinematic angle independently of HingeLaw.report (which evaluates the law).
    chart = {r['joint']: r['angle_rad'] for r in state['hinge_charts']}
    witnesses = []
    for c in net.constraints:
        i, j = c['a'], c['b']
        if j is None:
            close('clamp_position', data['r'][i], net.rj[i], atol=1e-10, rtol=0)
            close('clamp_rotation', data['Q'][i], np.eye(3), atol=1e-10, rtol=0)
            continue
        law = c['law']; index = law.index; relative = data['Q'][i].T@data['Q'][j]
        local = log(exp(-chart[index]*law.axis)@relative)
        angle = chart[index]+float(local@law.axis)
        h = next(h for h in snapshot['hinges'] if h['joint'] == index)
        signed = 1 if index == 1 else -1
        expected = signed*np.pi/180*h['structural_moment']/1.7453e-8
        close('joint_pylon_'+str(index), data['r'][j]-data['r'][i],
            data['Q'][i]@(net.rj[j]-net.rj[i]), atol=1e-8, rtol=0)
        close('hinge_rotation_'+str(index), relative, exp(angle*law.axis), atol=1e-8, rtol=0)
        close('hinge_law_'+str(index), angle, expected, atol=1e-8, rtol=0)
        witnesses.append(dict(joint=index, angle_rad=angle, law_angle_rad=expected,
            moment=h['structural_moment'], defect_rad=angle-expected, chart_center=chart[index]))
    sensors = {s['index']: s for s in snapshot['sensors']}
    for original in result['sensors']:
        for field in ('position_body', 'force_local', 'moment_local', 'bank', 'alpha'):
            if field in original:
                close('restored_sensor_'+str(original['index'])+'_'+field, sensors[original['index']][field], original[field])
    check('root_preselected_left_trace', sensors[1]['load_trace'] == 'left')
    alpha = np.deg2rad(condition.alpha); lift_axis = np.array([-np.sin(alpha), 0., np.cos(alpha)])
    lift = float(np.asarray(snapshot['force'])@lift_axis)
    close('lift_coefficient_identity', lift, snapshot['CL']*.5*condition.density*condition.speed**2*model.reference[0][0])
    outputs = dict(lift=lift, root_Mc=sensors[1]['moment_local'][0],
        left_tip_bank=sensors[2]['bank'], left_tip_alpha=sensors[2]['alpha'])
    comparison = {}
    for key, value in outputs.items():
        reference = plan['reference']['reference_values'][key]; half = plan['reference']['half_units'][key]
        difference = value-reference
        comparison[key] = dict(value=value, reference=reference, difference=difference,
            relative_difference=difference/abs(reference), half_printing_unit=half,
            printed_agreement=abs(difference) <= half)
    right_moment = next(t['moment_local'][0] for t in sensors[1]['section_traces'] if t['side'] == 'right')
    np.savez_compressed(folder/'fresh-fields.npz', x=x, residual=residual, r=data['r'], Q=data['Q'],
        N=data['N'], M=data['M'], nodal_force=data['force'], nodal_moment=data['moment'],
        element_forces=data['element_forces'], element_moments=data['element_moments'])
    write(folder/'restored-result.json', snapshot)
    report = dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL', case=name,
        checks=checks, checks_passed=sum(c['passed'] for c in checks), checks_total=len(checks),
        solve_seconds=elapsed, fresh_residual=error, outputs=outputs, comparison=comparison,
        hinge_witnesses=witnesses, progress_events=progress_count, cold_solves=1, fresh_residuals=1,
        root_right_trace_diagnostic=dict(selected=False, value=right_moment,
            reference=plan['reference']['reference_values']['root_Mc'],
            difference=right_moment-plan['reference']['reference_values']['root_Mc']),
        archived_match=all(v['printed_agreement'] for v in comparison.values()),
        historical_unknowns=plan['reference']['historical_unknowns'])
    require(unchanged(plan), 'Inputs changed during worker.')
    write(folder/'report.json', report)
    print(json.dumps(report), flush=True)
    require(report['status'] == 'PASS', 'Physical gates failed; finer case remains unlaunched.')


def run(stage):
    plan = read(stage/'plan.json'); require(unchanged(plan), 'Inputs changed.')
    require(not (stage/'execution.json').exists(), 'Use a new stage; automatic retries are forbidden.')
    execution = dict(status='RUNNING', children=[]); write(stage/'execution.json', execution)
    reports = {}
    for case in plan['cases']:
        name = case['name']; folder = stage/'cases'/name
        with (folder/'run.log').open('w') as log_file:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', str(stage), '--case', name],
                cwd=ROOT, env={**os.environ, **THREADS}, stdout=log_file, stderr=subprocess.STDOUT)
            record = dict(case=name, pid=child.pid, state='RUNNING'); execution['children'].append(record)
            write(stage/'execution.json', execution)
            try:
                code = child.wait(timeout=plan['child_cap_seconds'])
            except subprocess.TimeoutExpired:
                child.terminate()
                try:
                    code = child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); code = child.wait()
                record['timed_out'] = True
            record.update(state='TERMINAL', exit_code=code, reaped=True)
            write(stage/'execution.json', execution)
        if (folder/'report.json').exists():
            reports[name] = read(folder/'report.json')
        if code != 0:
            execution.update(status='FAILED', all_children_reaped=True)
            write(stage/'execution.json', execution)
            write(stage/'summary.json', dict(status='FAILED', cases=reports, execution=execution,
                unlaunched=[c['name'] for c in plan['cases'] if c['name'] not in [r['case'] for r in execution['children']]]))
            raise RuntimeError('Worker failed: '+name+'; see retained run.log/progress.jsonl.')
        print(json.dumps(dict(case=name, physical=reports[name]['status'], seconds=reports[name]['solve_seconds'],
            outputs=reports[name]['outputs'], archived_match=reports[name]['archived_match'])), flush=True)
    mesh = {}
    for key, fine in reports['fine']['outputs'].items():
        delta = abs(fine-reports['coarse']['outputs'][key])
        fraction = delta/abs(fine) if fine else (0. if delta == 0. else None)
        mesh[key] = dict(absolute_change=delta, relative_change=fraction,
            passed=fraction is not None and fraction <= plan['gates']['mesh'])
    pins_match = unchanged(plan)
    execution.update(status='PASS' if pins_match else 'FAILED_INPUT_PINS',
        all_children_reaped=True, inputs_unchanged=pins_match)
    write(stage/'execution.json', execution)
    require(pins_match, 'Inputs changed before final completion.')
    write(stage/'summary.json', dict(status='PASS_PHYSICAL_CHECKS', cases=reports, mesh=mesh,
        mesh_passed=all(v['passed'] for v in mesh.values()), archived_match=reports['fine']['archived_match'],
        cold_solves=2, fresh_residuals=2, plan=pin(stage/'plan.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('prepare', 'worker', 'run'))
    parser.add_argument('stage', type=Path); parser.add_argument('--contract', type=Path); parser.add_argument('--case')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.stage.resolve(), args.contract.resolve())
    elif args.action == 'worker':
        try:
            worker(args.stage.resolve(), args.case)
        except Exception:
            write(args.stage/'cases'/args.case/'failure.json', dict(traceback=traceback.format_exc()))
            raise
    else:
        run(args.stage.resolve())
