#!/usr/bin/env python3
"""Two articulated cold bridge solves and four saved-policy restorations.

This verifies implementation integration, not agreement with archived ASWING.
The existing articulated model is used literally; no parameters are fitted.
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

ROOT = Path(__file__).resolve().parents[1]
THREADS = {k: '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
OLD = ('isae-st5-reference-project.json', 'isae-st5-source-static-project.json',
       'source-section-check-project.json', 'isae-ae2-source-coupled-project.json')


def read(p):
    return json.loads(Path(p).read_text())


def write(p, value):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def pin(p):
    p = Path(p).resolve(); b = p.read_bytes()
    return dict(path=str(p), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def unchanged(plan):
    return all(pin(p['path']) == p for p in plan['pins'])


def prepare(stage, retained_structural=None, retained_mounted=None):
    require(not stage.exists(), 'Use a new stage.')
    stage.mkdir(parents=True)
    template = read(ROOT/'examples'/OLD[-1])
    source = (ROOT/'examples/articulated.asw').read_text()
    panels = dict(default=12, beams={str(i): dict(count=12, spacing='cosine') for i in (1, 2, 3)})
    condition = deepcopy(template['solutions'][0]['data']['request']['condition'])
    condition.update(speed=30., alpha=5., beta=0., density=1.225, gravity_magnitude=9.80665,
                     mach=0., ground_effect=0., freeze_influences=False, controls={}, powers={}, circulation_modes={str(i): 0 for i in (1, 2, 3)})
    cases = []; inputs = [Path(__file__), ROOT/'examples/articulated.asw']
    for name, operator in (('structural', 'drela-steady-section-v1'), ('mounted', 'drela-steady-coupled-v1')):
        folder = stage/'cases'/name
        policy = dict(beam_interpolation='drela-segspl-v1', structural_operator=operator)
        request = dict(action='solve', mode=name, source=source, panels=panels,
                       condition=None if name == 'structural' else condition, numerics=policy)
        if name == 'structural':
            request['gravity'] = [0., 0., -9.80665]
        else:
            request.update(operating_constraints=[], strut_mode='bilateral', controller=None)
        configuration = deepcopy(template['cases'][0]['configuration'])
        configuration.update(source=source, filename='articulated.asw', mesh=panels, numerics=policy,
                             controls={}, powers={}, circulation={str(i): '0' for i in (1, 2, 3)},
                             constraints=[], equilibrium=dict(state=None, enabled=False, label=''))
        configuration['derivative_parameters'] = ['u', 'alpha', 'beta', 'p', 'q', 'r']
        configuration['fields'].update({'mode': name, 'speed': '30', 'alpha': '5', 'beta': '0',
            'density': '1.225', 'gravity-magnitude': '9.80665', 'static-gravity-z': '-9.80665',
            'static-gravity-mode': 'custom' if name == 'structural' else 'file',
            'pg-mach': '0', 'ground-effect': '0', 'freeze-influences': False,
            'trim-roll': '', 'trim-pitch': '', 'trim-yaw': '', 'trim-engine': ''})
        project = dict(format='openswing-project', version=2, name='Articulated '+name+' source check',
            selected='articulated-'+name, cases=[dict(id='articulated-'+name, name='Articulated '+name, configuration=configuration)],
            solutions=[], selected_solution=None)
        write(folder/'request.json', request); write(folder/'input-project.json', project)
        inputs += [folder/'request.json', folder/'input-project.json']
        cases.append(dict(name=name, kind='cold', request=str(folder/'request.json')))
        retained = retained_structural if name == 'structural' else retained_mounted
        if retained is not None:
            retained = retained.resolve()
            require(read(retained/'request.json') == request, 'Retained request differs.')
            cases[-1]['retained_result'] = str(retained/'result.json')
            cases[-1]['retained_report'] = str(retained/'report.json')
            inputs += [retained/'result.json', retained/'report.json', retained/'request.json']
    for index, filename in enumerate(OLD):
        path = ROOT/'examples'/filename; inputs.append(path)
        cases.append(dict(name='legacy-'+str(index), kind='restore', project=str(path)))
    inputs += sorted((ROOT/'openswing').glob('*.py')) + sorted((ROOT/'web').rglob('*.js'))
    inputs += [ROOT/'tests/test_source_joints.py', ROOT/'tests/numerical-policy.test.mjs']
    inputs += [Path('/tmp/openswing-source-joints-primary-20261026')/n for n in ('spec.md', 'oracles.json')]
    plan = dict(status='PREPARED_NOT_EXECUTED', cases=cases,
        cold_solves=2-int(retained_structural is not None)-int(retained_mounted is not None), fresh_residuals=6,
        child_cap_seconds=120, gates=dict(residual=1e-8, balance=1e-7, restored=2e-10),
        kernel_pins={p.name: pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))},
        pins=[pin(p) for p in sorted(set(inputs))], thread_environment=THREADS,
        scope='Documented joint mechanics and backward compatibility. No new archived-ASWING pass is claimed.')
    require(unchanged(plan), 'Preparation inputs changed.')
    write(stage/'plan.json', plan); print(json.dumps(pin(stage/'plan.json')), flush=True)


def worker(stage, name):
    plan = read(stage/'plan.json'); require(unchanged(plan), 'Inputs changed.')
    case = next(c for c in plan['cases'] if c['name'] == name); folder = stage/'cases'/name
    require(not (folder/'started.json').exists(), 'No repeated worker execution.')
    write(folder/'started.json', dict(pid=os.getpid(), started=time.time()))
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.network import StaticNetwork, network_snapshot, exp
    from openswing.source_discrete import SourceDiscreteNetwork, SourceSectionNetwork
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.equilibrium_state import identity, matching_identity, restore, warm_start_recipe
    from openswing.numerical_policy import request_policy
    began = time.monotonic()
    if case['kind'] == 'cold':
        request = read(folder/'request.json')
        result = read(case['retained_result']) if 'retained_result' in case else dispatch(request)
        write(folder/'result.json', result)
    else:
        project = read(case['project']); result = project['solutions'][0]['data']; request = result['request']
    solve_seconds = time.monotonic()-began if case['kind'] == 'cold' else None
    if 'retained_result' in case:
        solve_seconds = read(case['retained_report'])['solve_seconds']
    policy = request_policy(request); model = parse_asw(request['source'], beam_interpolation=policy['beam_interpolation'])
    state = result['equilibrium_state']; original_state = deepcopy(state)
    cls = {'midpoint-v1': StaticNetwork, 'drela-steady-zero-offset-v1': SourceDiscreteNetwork,
           'drela-steady-section-v1': SourceSectionNetwork, 'drela-steady-coupled-v1': SourceCoupledNetwork}[policy['structural_operator']]
    structural = request['mode'] == 'structural'; condition = None
    if not structural:
        values = deepcopy(request['condition'])
        for key in ('controls', 'powers'):
            values[key] = {int(k): v for k, v in values.get(key, {}).items()}
        condition = FlightCondition(**values)
    net = cls(model, request['panels'], condition, request.get('gravity'), request.get('loads', []),
        allow_signed_point_weights=structural, allow_signed_distributed_weights=structural,
        mesh_recipe=warm_start_recipe(model, request['panels'], state))
    checks = []
    def check(label, value, **detail):
        checks.append(dict(name=label, passed=bool(value), **detail))
    def same(label, actual, expected, atol=2e-10):
        a, b = np.asarray(actual), np.asarray(expected)
        check(label, a.shape == b.shape and np.allclose(a, b, rtol=2e-10, atol=atol))
    current_identity = identity(net)
    check('saved_identity', matching_identity(state['identity'], current_identity),
          byte_equal=current_identity == state['identity'],
          rule='Exact model/policy/topology; existing eight-epsilon mesh-generation roundoff allowance.')
    x = restore(net, state); check('restore_no_residual', net.nfev == 0)
    residual, data = net.residual(x, detail=True); snapshot = network_snapshot(net, residual, data)
    error = float(np.max(abs(residual)))
    check('one_fresh_residual', net.nfev == 1)
    check('full_equilibrium', error <= plan['gates']['residual'], maximum=error)
    check('saved_state_untouched', state == original_state)
    for key in ('force', 'moment'):
        a, b = np.asarray(snapshot['applied_'+key]), np.asarray(snapshot['support_'+key])
        defect = float(np.linalg.norm(a+b)); scale = max(1., float(np.linalg.norm(a)+np.linalg.norm(b)))
        check(key+'_balance', defect/scale <= plan['gates']['balance'], defect=defect, scale=scale)
    for key in ('nodes', 'reactions', 'elements'):
        check(key+'_count_preserved', len(snapshot[key]) == len(result[key]))
    same('saved_positions', [v['position'] for v in snapshot['nodes']], [v['position'] for v in result['nodes']])
    for kind in ('force', 'moment'):
        same('saved_reaction_'+kind, [v[kind] for v in snapshot['reactions']], [v[kind] for v in result['reactions']])
    if case['kind'] == 'cold':
        check('two_v2_hinge_charts_no_launch', state['version'] == 2 and len(state['hinge_charts']) == 2 and 'launch' not in state)
        check('joint_scope_reported', snapshot['joint_constraints']['joint_types'] == [0, 1, 2, 3])
        check('nonzero_hinge_response', all(abs(h['angle_deg']) > 1e-6 for h in snapshot['hinges']))
        for c in net.constraints:
            i, j = c['a'], c['b']
            if j is None:
                same('clamp_position', data['r'][i], net.rj[i]); same('clamp_frame', data['Q'][i], np.eye(3))
            else:
                same('joint_pylon_'+str(c['law'].index), data['r'][j]-data['r'][i], data['Q'][i]@(net.rj[j]-net.rj[i]))
                h = next(h for h in snapshot['hinges'] if h['joint'] == c['law'].index)
                angle = h['angle_deg']*np.pi/180
                same('hinge_finite_rotation_'+str(h['joint']), data['Q'][j], data['Q'][i]@exp(angle*c['law'].axis))
                sign = 1 if h['joint'] == 1 else -1
                check('literal_linear_law_'+str(h['joint']), abs(h['structural_moment']) < 4000 and abs(h['angle_deg']-sign*15*h['structural_moment']/4000) < 2e-8)
        same('opposite_mirror_hinge_angles', snapshot['hinges'][0]['angle_deg'], -snapshot['hinges'][1]['angle_deg'], atol=2e-8)
        if not structural:
            check('nonzero_airload', np.linalg.norm(snapshot['surface_force']) > 1.)
    else:
        check('rigid_only_metadata_preserved', 'joint_constraints' not in snapshot)
    np.savez_compressed(folder/'fresh-fields.npz', residual=residual, r=data['r'], Q=data['Q'], N=data['N'], M=data['M'],
                        element_forces=data['element_forces'], element_moments=data['element_moments'])
    write(folder/'restored-result.json', snapshot)
    report = dict(status='PASS' if all(c['passed'] for c in checks) else 'FAIL', case=name, checks=checks,
        checks_passed=sum(c['passed'] for c in checks), checks_total=len(checks), solve_seconds=solve_seconds,
        fresh_residual=error, hinges=snapshot['hinges'], cold_solves=int(case['kind'] == 'cold' and 'retained_result' not in case),
        retained_cold_solves=int('retained_result' in case), fresh_residuals=1)
    require(unchanged(plan), 'Inputs changed during worker.')
    write(folder/'report.json', report); print(json.dumps({k: report[k] for k in ('case', 'status', 'solve_seconds', 'fresh_residual')}), flush=True)
    require(report['status'] == 'PASS', 'Physical or compatibility check failed.')


def run(stage):
    plan = read(stage/'plan.json'); require(unchanged(plan), 'Inputs changed.')
    require(not (stage/'execution.json').exists(), 'Use a new plan after failures.')
    execution = dict(status='RUNNING', children=[]); write(stage/'execution.json', execution)
    for case in plan['cases']:
        folder = stage/'cases'/case['name']; folder.mkdir(exist_ok=True)
        with (folder/'run.log').open('w') as out:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'worker', str(stage), '--case', case['name']],
                cwd=ROOT, env={**os.environ, **THREADS}, stdout=out, stderr=subprocess.STDOUT)
            record = dict(case=case['name'], pid=child.pid, state='RUNNING'); execution['children'].append(record)
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
            record.update(state='TERMINAL', exit_code=code, reaped=True); write(stage/'execution.json', execution)
        require(code == 0, 'Worker failed: '+case['name'])
    reports = {c['name']: read(stage/'cases'/c['name']/'report.json') for c in plan['cases']}
    require(unchanged(plan), 'Inputs changed during integration.')
    execution.update(status='PASS', all_children_reaped=True, inputs_unchanged=True); write(stage/'execution.json', execution)
    summary = dict(status='PASS_SOURCE_JOINTS_INTEGRATION', cases=reports,
        checks_passed=sum(r['checks_passed'] for r in reports.values()), checks_total=sum(r['checks_total'] for r in reports.values()),
        operations=dict(cold_solves=sum(r['cold_solves'] for r in reports.values()),
                        retained_cold_solves=sum(r['retained_cold_solves'] for r in reports.values()), fresh_residuals=6),
        plan=pin(stage/'plan.json'), scope=plan['scope'])
    write(stage/'summary.json', summary)
    print(json.dumps(dict(status=summary['status'], checks=summary['checks_passed'], total=summary['checks_total'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('prepare', 'run', 'worker'))
    parser.add_argument('stage', type=Path); parser.add_argument('--case'); parser.add_argument('--retained-structural', type=Path)
    parser.add_argument('--retained-mounted', type=Path); args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.stage.resolve(), args.retained_structural, args.retained_mounted)
    elif args.action == 'worker':
        worker(args.stage.resolve(), args.case)
    else:
        try:
            run(args.stage.resolve())
        except Exception as exc:
            p = args.stage.resolve()/'execution.json'
            if p.exists():
                receipt = read(p); receipt.update(status='FAILURE_RETAINED', error=str(exc)); write(p, receipt)
            raise
