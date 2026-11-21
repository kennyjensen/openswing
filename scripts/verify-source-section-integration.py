#!/usr/bin/env python3
"""Bounded bridge verification for the opt-in source section operator.

Preparation is stdlib-only. Execution needs a root authorization tied to the
frozen plan. Three independent child processes perform exactly one cold bridge
solve each, followed by saved-state residual checks, never an extra corrector.
The two original cases test regression, not new archived-ASWING acceptance.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = Path('/tmp/openswing-source-section-integration-20261026')
PRIOR = Path('/tmp/openswing-source-discrete-integration-20261026')
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-section-v1')
OLD_OPERATOR = 'drela-steady-zero-offset-v1'
FIELDS = ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions')
THREADS = {k: '1' for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
PRIMARY = Path('/tmp/openswing-source-general-primary-20261026')
SYNTHETIC_SOURCE = '''Name
Synthetic coupled section integration check - no ASWING reference
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
10 1.225 340
End
Reference
2 1 2
.4 -.3 2
End
Ground
1 1 0
End
Weight
1 3 .15 2 .1 .25
End
Sensor
1 1 1 .1 0 .2
2 1 2 .3 1 -.1
3 1 3 -.2 2 .1
End
Beam 1
Synthetic finite-shear coupled sections
t x y z chord
1 0 0 0 .2
3 0 2 0 .2
t EIcc GJ EInn EIcs EIcn EIsn EA GKc GKn Cea Nea Cta Nta
1 100 75 150 8 -13 9 800 300 400 -.1 .07 .3 -.2
3 140 100 160 6 2 5 1600 900 1000 .2 -.03 -.1 .4
t Cshell Nshell Atshell
1 .4 .2 .01
3 .4 .2 .01
t mg Ccg Ncg Dmg DCcg DNcg
1 .2 .2 .1 .1 -.2 .4
3 .6 -.1 .3 .3 .5 -.2
End
'''
SYNTHETIC_SPEC = dict(synthetic=True, interpolation='two_endpoint_linear', t=[1., 3.],
    nodes=[1.+i/4 for i in range(9)], gravity=10., reference=[.4, -.3, 2.], sensor_count=3,
    point_weights=[dict(t=3., position=[.15, 2., .1], weight=.25)],
    properties=dict(EIcc=[100., 140.], GJ=[75., 100.], EInn=[150., 160.], EIcs=[8., 6.], EIcn=[-13., 2.], EIsn=[9., 5.],
                    EA=[800., 1600.], GKc=[300., 900.], GKn=[400., 1000.], Cea=[-.1, .2], Nea=[.07, -.03], Cta=[.3, -.1], Nta=[-.2, .4],
                    Cshell=[.4, .4], Nshell=[.2, .2], Atshell=[.01, .01], mg=[.2, .6], Dmg=[.1, .3], Ccg=[.2, -.1], Ncg=[.1, .3], DCcg=[-.2, .5], DNcg=[.4, -.2]),
    provenance='Section, CG, sensor and shell inputs follow the independent test_source_sections fixture. This browser case explicitly selects positive modest mg/Dmg and adds a 0.25 N point weight; it is synthetic, with no archived target or fitting.')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def require(passed, message):
    if not passed:
        raise RuntimeError(message)


def kernels():
    return {p.name: pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))}


def unchanged(plan):
    return kernels() == plan['kernel_pins'] and all(pin(p['path']) == p for p in plan['pins'])


def prepare(stage, fixture, specification):
    require((fixture is None) == (specification is None), 'Supply both custom fixture and specification, or use the embedded synthetic fixture.')
    require(not stage.exists(), f'Refusing to replace stage {stage}')
    stage.mkdir(parents=True)
    cases = []
    inputs = [Path(__file__), PRIOR/'plan.json', PRIOR/'session-closeout.json', ROOT/'tests/test_source_sections.py', PRIMARY/'spec.md', PRIMARY/'oracles.json', PRIMARY/'manifest.json',
              ROOT/'scripts/test-source-section-browser.mjs', Path('/tmp/openswing-source-section-boundary-20261026/receipt.json'),
              Path('/tmp/openswing-source-section-tests-20261026/receipt.json')]
    inputs.extend(sorted((ROOT/'web').rglob('*.js')))
    if fixture is not None:
        inputs.extend([fixture, specification])
    for name, mesh_index, previous in (('st3', 2, 'n176'), ('st5', 0, 'level0')):
        oldplan = read(PRIOR/name/'plan.json')
        mesh = oldplan['meshes'][mesh_index]
        sourcepath = ROOT/oldplan['source']
        oldresult = PRIOR/name/previous/'result.json'
        oldfields = PRIOR/name/previous/'fresh-fields.npz'
        source = sourcepath.read_text()
        require(hashlib.sha256(source.encode()).hexdigest() == read(oldresult)['equilibrium_state']['identity']['model_sha256'], f'{name}: literal source differs from accepted state')
        request = dict(action='solve', mode='structural', source=source, panels=mesh['panels'], condition=None, gravity=None, numerics=POLICY)
        folder = stage/'cases'/name
        write(folder/'request.json', request)
        (folder/'model.asw').write_text(source)
        expected_elements = 176 if name == 'st3' else 70
        expected_nodes = 177 if name == 'st3' else 72
        cases.append(dict(name=name, request=str(folder/'request.json'), expected_elements=expected_elements,
                          expected_nodes=expected_nodes, previous_result=str(oldresult), previous_fields=str(oldfields),
                          cold_solves=1, new_policy_fresh_residuals=1, old_policy_fresh_residuals=1,
                          scope='Original literal model and exact prior grid; compare policy regression only. Existing reference failures remain unchanged.'))
        inputs.extend([PRIOR/name/'plan.json', sourcepath, oldresult, oldfields, folder/'request.json', folder/'model.asw'])
    synthetic_source = SYNTHETIC_SOURCE if fixture is None else fixture.read_text()
    spec = copy.deepcopy(SYNTHETIC_SPEC) if specification is None else read(specification)
    require(spec['synthetic'] is True and spec['interpolation'] == 'two_endpoint_linear', 'Synthetic specification must declare independent linear endpoint inputs.')
    nodes = spec['nodes']
    require(len(nodes) in (5, 9), 'Synthetic case must have four or eight explicit intervals.')
    require(nodes[0] == spec['t'][0] and nodes[-1] == spec['t'][1], 'Synthetic node domain mismatch.')
    required = ('Cea', 'Nea', 'Cta', 'Nta', 'Ccg', 'Ncg', 'DCcg', 'DNcg', 'EA', 'GKc', 'GKn', 'EIcc', 'GJ', 'EInn', 'EIcs', 'EIcn', 'EIsn', 'mg', 'Dmg', 'Cshell', 'Nshell', 'Atshell')
    require(all(k in spec['properties'] and len(spec['properties'][k]) == 2 for k in required), 'Incomplete synthetic property specification.')
    require(all(all(v != 0 for v in spec['properties'][k]) for k in required), 'Synthetic required properties must be nonzero.')
    folder = stage/'cases'/'section'
    request = dict(action='solve', mode='structural', source=synthetic_source,
                   panels={'default': len(nodes)-1, 'beams': {'1': {'nodes': nodes}}}, condition=None, gravity=None, numerics=POLICY)
    write(folder/'request.json', request)
    (folder/'model.asw').write_text(synthetic_source)
    write(folder/'independent-inputs.json', spec)
    cases.append(dict(name='section', request=str(folder/'request.json'), independent_inputs=str(folder/'independent-inputs.json'),
                      expected_elements=len(nodes)-1, expected_nodes=len(nodes), cold_solves=1,
                      new_policy_fresh_residuals=1, old_policy_fresh_residuals=0,
                      scope='Synthetic all-offset finite-shear coupled-section gravity integration check; no ASWING reference or experiment claim.'))
    inputs.extend([folder/'request.json', folder/'model.asw', folder/'independent-inputs.json'])
    inputs.extend(sorted((ROOT/'openswing').glob('*.py')))
    unique = sorted(set(Path(p).resolve() for p in inputs))
    plan = dict(status='PREPARED_NOT_EXECUTED', policy=POLICY, cases=cases,
                cold_solves=3, fresh_restore_residuals=5, new_policy_fresh_residuals=3, old_policy_fresh_residuals=2,
                regression_fields=list(FIELDS), regression_absolute=2e-10, regression_relative=2e-10,
                gates=dict(fresh_residual=1e-8, original_absolute_balance=1e-7, relative_force_balance=1e-7, relative_moment_balance=1e-7,
                           rigid_pose=1e-10, independent_algebra_absolute=2e-10, independent_algebra_relative=2e-10),
                child_cap_seconds=120, termination_grace_seconds=5, concurrency=1, retries=0,
                failure_policy='Stop at the first failed child; preserve partial scientific output and all receipts.',
                kernel_pins=kernels(), pins=[pin(p) for p in unique], thread_environment=THREADS,
                operations_at_prepare=dict(production_imports=0, cold_solves=0, residuals=0),
                source_scope='New section policy is explicit. Old policy is restored with its original identity; no retagging or warm-start conversion.',
                acceptance_scope='Numerical and regression checks only. No existing archived precision or mesh gate is replaced.')
    require(unchanged(plan), 'Preparation source changed while pinning.')
    write(stage/'plan.json', plan)
    print(json.dumps(dict(status=plan['status'], plan=pin(stage/'plan.json'), kernels=len(plan['kernel_pins']), cases=len(cases))), flush=True)


def worker(stage, name):
    # All scientific imports are below the frozen-plan and authorization checks.
    plan = read(stage/'plan.json')
    authorization = read(stage/'authorization.json')
    require(authorization.get('authorized') is True and authorization.get('plan_sha256') == pin(stage/'plan.json')['sha256'], 'Missing exact-plan root authorization.')
    require(unchanged(plan), 'Frozen source mismatch before worker imports.')
    case = next(c for c in plan['cases'] if c['name'] == name)
    folder = stage/'cases'/name
    require(not (folder/'result.json').exists() and not (folder/'worker-start.json').exists(), 'Worker already attempted; no retry.')
    write(folder/'worker-start.json', dict(pid=os.getpid(), plan=pin(stage/'plan.json'), cold_solve_budget=1, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())))
    import numpy as np
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.equilibrium_state import identity, restore
    from openswing.network import network_snapshot
    import openswing.source_discrete as sd
    checks = []

    def check(label, passed, detail=None):
        checks.append(dict(name=label, passed=bool(passed), detail=detail))

    def same(label, actual, expected, atol=2e-10, rtol=2e-10):
        a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
        valid = a.shape == b.shape and np.all(np.isfinite(a)) and np.all(np.isfinite(b))
        error = None if not valid else float(np.max(abs(a-b), initial=0.))
        passed = valid and bool(np.all(abs(a-b) <= atol+rtol*abs(b)))
        check(label, passed, dict(actual_shape=list(a.shape), expected_shape=list(b.shape), max_absolute_difference=error,
                                  absolute=atol, relative=rtol, exact=bool(valid and np.array_equal(a, b))))

    request = read(case['request'])
    solve_calls = []
    original = sd.solve_source_discrete

    def counted(*args, **kwargs):
        require(not solve_calls, 'More than one cold solve attempted in this child.')
        solve_calls.append(dict(operator=kwargs.get('structural_operator'), initial_state=kwargs.get('initial_state')))
        write(folder/'cold-call.json', dict(cold_call_number=1, arguments=solve_calls[0], pid=os.getpid(), state='ENTERED'))
        return original(*args, **kwargs)

    sd.solve_source_discrete = counted
    began = time.monotonic()
    result = dispatch(copy.deepcopy(request))
    solve_seconds = time.monotonic()-began
    write(folder/'result.json', result)
    check('exactly_one_cold_bridge_solve', len(solve_calls) == 1 and solve_calls[0] == dict(operator=POLICY['structural_operator'], initial_state=None))
    check('literal_request_unchanged', read(case['request']) == request)
    check('bridge_policy', result.get('numerics') == POLICY and result.get('structural_operator') == POLICY['structural_operator'])
    check('normal_structural_presentation', result.get('analysis') == 'structural_static' and result.get('structural_only') is True and result.get('strips') == [])
    check('element_node_counts', (result['structural_elements'], result['structural_nodes']) == (case['expected_elements'], case['expected_nodes']))
    check('static_state_no_dynamic_launch', 'launch' not in result['equilibrium_state'] and result['equilibrium_state']['circulation'] == [])

    def forbidden(*args, **kwargs):
        raise AssertionError('No equilibrium calls are allowed after the single cold bridge solve.')

    sd.equilibrate = sd.solve_source_discrete = forbidden
    model = parse_asw(request['source'], beam_interpolation=POLICY['beam_interpolation'])
    require(model.dumps() == request['source'], 'Parsing changed literal source.')
    net = sd.SourceSectionNetwork(model, request['panels'], None, request['gravity'], [],
                                  allow_signed_point_weights=True, allow_signed_distributed_weights=True)
    check('new_identity_exact', identity(net) == result['equilibrium_state']['identity'])
    x = restore(net, result['equilibrium_state'])
    check('new_restore_has_no_residual', net.nfev == 0)
    residual, data = net.residual(x, detail=True)
    snapshot = network_snapshot(net, residual, data)
    check('one_new_fresh_residual', net.nfev == 1)
    maximum = float(np.max(abs(residual), initial=0.))
    check('fresh_full_residual', maximum <= plan['gates']['fresh_residual'], maximum)
    pa, pb, ra, rb, *_ = net.geometry(data['r'], data['Q'])
    raw = dict(residual=residual, r=data['r'], Q=data['Q'], N=data['N'], M=data['M'], rj=net.rj,
               a=net.a, b=net.b, pa=pa, pb=pb, ra=ra, rb=rb, ds=net.ds,
               force=data['force'], moment=data['moment'], element_forces=data['element_forces'], element_moments=data['element_moments'])
    np.savez_compressed(folder/'fresh-fields.npz', **raw)
    write(folder/'restored-report.json', snapshot)
    balances = {}
    for kind in ('force', 'moment'):
        applied = np.asarray(snapshot['applied_'+kind]); support = np.asarray(snapshot['support_'+kind])
        defect = float(np.linalg.norm(applied+support)); scale = max(float(np.linalg.norm(applied)), float(np.linalg.norm(support)))
        relative = defect/scale if scale else (0. if defect == 0 else None)
        passed = (max(abs(applied+support)) <= plan['gates']['original_absolute_balance'] if name in ('st3', 'st5')
                  else relative is not None and relative <= plan['gates']['relative_'+kind+'_balance'])
        check(kind+'_balance', passed, dict(defect=defect, scale=scale, relative=relative,
              criterion='Original componentwise 1e-7 absolute gate' if name in ('st3', 'st5') else 'Relative 1e-7, denominator=max(norm(applied),norm(support)); exact zero handled'))
        same('cold_vs_restored_'+kind+'_balance', result[kind+'_balance'], snapshot[kind+'_balance'])
        balances[kind] = dict(defect=defect, scale=scale, relative=relative)
    poses = []
    for c in net.constraints:
        i, j = c['a'], c['b']
        if j is None:
            poses.extend([float(np.max(abs(data['r'][i]-net.rj[i]))), float(np.max(abs(data['Q'][i]-np.eye(3))))])
        else:
            poses.extend([float(np.max(abs(data['r'][j]-data['r'][i]-data['Q'][i]@(net.rj[j]-net.rj[i])))), float(np.max(abs(data['Q'][i]-data['Q'][j])))])
    check('rigid_ground_joint_pose', bool(poses) and max(poses) <= plan['gates']['rigid_pose'], max(poses, default=None))
    old_calls = 0
    if name in ('st3', 'st5'):
        previous = read(case['previous_result'])
        for field in FIELDS:
            same('new_vs_prior_'+field, result['equilibrium_state'][field], previous['equilibrium_state'][field])
        expected_identity = copy.deepcopy(previous['equilibrium_state']['identity'])
        expected_identity['structural_operator'] = POLICY['structural_operator']
        check('identity_differs_only_by_operator', result['equilibrium_state']['identity'] == expected_identity)
        old = sd.SourceDiscreteNetwork(model, request['panels'], None, request['gravity'], [],
                                       allow_signed_point_weights=True, allow_signed_distributed_weights=True)
        check('old_identity_untouched', identity(old) == previous['equilibrium_state']['identity'])
        oldx = restore(old, previous['equilibrium_state'])
        check('old_restore_has_no_residual', old.nfev == 0)
        oldresidual, olddata = old.residual(oldx, detail=True)
        old_calls += 1
        check('one_old_fresh_residual', old.nfev == 1)
        check('old_fresh_full_residual', float(np.max(abs(oldresidual), initial=0.)) <= plan['gates']['fresh_residual'])
        with np.load(case['previous_fields']) as prior:
            for key, value in [('residual', oldresidual), ('r', olddata['r']), ('Q', olddata['Q']), ('N', olddata['N']), ('M', olddata['M']), ('element_forces', olddata['element_forces']), ('element_moments', olddata['element_moments'])]:
                same('old_policy_unchanged_'+key, value, prior[key])
        np.savez_compressed(folder/'old-policy-fresh-fields.npz', residual=oldresidual, r=olddata['r'], Q=olddata['Q'], N=olddata['N'], M=olddata['M'])
        write(folder/'old-policy-restoration.json', dict(identity=identity(old), fresh_residual=float(np.max(abs(oldresidual))), residual_calls=old.nfev, original_state_untouched=True))
    else:
        independent_section_checks(case, net, data, snapshot, result, pa, pb, ra, rb, same, check, folder)
    check('all_frozen_pins_unchanged', unchanged(plan))
    failures = [c for c in checks if not c['passed']]
    report = dict(status='PASS_SECTION_INTEGRATION' if not failures else 'FAIL_RETAINED', case=name,
                  checks_passed=len(checks)-len(failures), checks_total=len(checks), checks=checks, failures=failures,
                  solve_seconds=solve_seconds, solver_reported_evaluations=result['evaluations'], fresh_residual=maximum,
                  balances=balances, operations=dict(cold_bridge_solves=len(solve_calls), new_policy_fresh_residuals=1, old_policy_fresh_residuals=old_calls),
                  reference_scope=case['scope'], request=pin(folder/'request.json'), result=pin(folder/'result.json'))
    write(folder/'report.json', report)
    print(json.dumps(dict(case=name, status=report['status'], checks=report['checks_passed'], total=report['checks_total'], solve_seconds=solve_seconds)), flush=True)
    require(not failures, f'{name}: verification failed; all outputs retained.')


def independent_section_checks(case, net, data, snapshot, result, pa, pb, ra, rb, same, check, folder):
    """Literal linear properties and direct matrix algebra, not candidate helpers."""
    import numpy as np
    spec = read(case['independent_inputs'])
    t = np.asarray(spec['nodes']); span = spec['t'][1]-spec['t'][0]
    f = (t-spec['t'][0])/span
    values = {name: pair[0]*(1-f)+pair[1]*f for name, pair in spec['properties'].items()}
    average = {name: (v[:-1]+v[1:])/2 for name, v in values.items()}
    reference = np.asarray(spec['reference']); gravity = np.array([0., 0., -spec['gravity']])
    same('synthetic_gravity_from_literal', snapshot['gravity_body'], gravity)
    same('synthetic_reference_from_literal', net.model.reference[1], reference)
    same('synthetic_straight_material_lengths', net.ds, np.diff(t))
    for name, expected in values.items():
        same('literal_property_'+name, net.model.beams[0].value(name, t), expected, atol=2e-13, rtol=2e-13)
    transform = (ra.transpose(0, 2, 1)+rb.transpose(0, 2, 1))/2
    local_force = np.einsum('nij,nj->ni', transform, data['N'])
    local_moment = np.einsum('nij,nj->ni', transform, data['M'])
    stiffness = np.array([[[average['EIcc'][i], average['EIcs'][i], average['EIcn'][i]],
                           [average['EIcs'][i], average['GJ'][i], average['EIsn'][i]],
                           [average['EIcn'][i], average['EIsn'][i], average['EInn'][i]]] for i in range(net.ne)])
    h = np.array([[[0., average['Nta'][i], 0.], [-average['Nea'][i], 0., average['Cea'][i]],
                   [0., -average['Cta'][i], 0.]] for i in range(net.ne)])
    shifted = local_moment+np.einsum('nij,nj->ni', h, local_force)
    curvature = np.linalg.solve(stiffness, shifted[..., None])[..., 0]
    direct = np.column_stack([1/average['GKc'], 1/average['EA'], 1/average['GKn']])
    strain = direct*local_force+np.einsum('nji,nj->ni', h, curvature)
    same('independent_coupled_offset_curvature', data['source_discrete']['curvature_change'], curvature)
    same('independent_coupled_offset_strain', data['source_discrete']['translation_strain'], strain)
    check('all_E_positive_definite', np.all(np.linalg.eigvalsh(stiffness) > 0))
    check('finite_nonzero_shear_active', float(np.max(abs(strain[:, [0, 2]]))) > 1e-9)
    mass = 0.; first = np.zeros(3); forces = np.zeros((net.nn, 3)); moments = np.zeros_like(forces)
    samples = []
    for prefix in ('', 'D'):
        endpoint_mass = [values[prefix+'mg'][:-1]*net.ds/(2*spec['gravity']), values[prefix+'mg'][1:]*net.ds/(2*spec['gravity'])]
        weight_force = (endpoint_mass[0]+endpoint_mass[1])[:, None]*gravity
        np.add.at(forces, net.a, weight_force/2); np.add.at(forces, net.b, weight_force/2)
        couple = np.zeros((net.ne, 3))
        for end, frame in enumerate((ra, rb)):
            v = slice(None, -1) if end == 0 else slice(1, None)
            arms = np.column_stack([values[prefix+'Ccg'][v], np.zeros(net.ne), values[prefix+'Ncg'][v]])
            bodyarm = np.einsum('nij,nj->ni', frame, arms)
            position = (pa+pb)/2+bodyarm
            m = endpoint_mass[end]
            mass += float(m.sum()); first += np.sum(m[:, None]*(position-reference), axis=0)
            couple += np.cross(bodyarm, m[:, None]*gravity)
            samples.append(dict(prefix=prefix, end=end, mass=m.tolist(), position=position.tolist(), body_arm=bodyarm.tolist()))
        np.add.at(moments, net.a, couple/2); np.add.at(moments, net.b, couple/2)
    for record in spec.get('point_weights', []):
        node = int(np.flatnonzero(t == record['t'])[0]); m = record['weight']/spec['gravity']
        initial = np.asarray(record['position']); position = data['r'][node]+data['Q'][node]@(initial-net.rj[node])
        force = m*gravity; mass += m; first += m*(position-reference)
        forces[node] += force; moments[node] += np.cross(position-data['r'][node], force)
        samples.append(dict(kind='point', node=node, mass=m, position=position.tolist()))
    same('independent_nodal_gravity_forces', data['force'], forces)
    same('independent_nodal_CG_gravity_couples', data['moment'], moments)
    same('static_mass', snapshot['mass_properties']['mass'], mass)
    same('static_first_moment', snapshot['mass_properties']['first_moment'], first)
    same('gravity_force_equals_mass_times_gravity', snapshot['applied_force'], mass*gravity)
    same('gravity_moment_equals_first_cross_gravity', snapshot['applied_moment'], np.cross(first, gravity))
    check('positive_static_mass', mass > 0)
    properties = result['mass_properties']
    check('dynamic_mass_unavailable', properties.get('dynamic_inertia_available') is False and all(properties.get(k) is None for k in ('inertia_reference', 'inertia_cg', 'spatial_matrix', 'spin_angular_momentum')))
    check('sensor_count', len(result['sensors']) == spec['sensor_count'] and spec['sensor_count'] > 0)
    for index, sensor in enumerate(result['sensors']):
        check('finite_sensor_strain_'+str(index), np.all(np.isfinite(sensor['strain'])) and np.all(np.isfinite(sensor['curvature_change'])))
    traces = [tr for e in result['elements'] for tr in e['endpoint_traces']]
    check('all_endpoint_shells_available', len(traces) == 2*net.ne and all(tr['shell']['axial_strain_bound'] is not None and tr['shell']['shear_stress_abs'] is not None for tr in traces))
    write(folder/'independent-gravity.json', dict(mass=mass, reference=reference.tolist(), first_moment=first.tolist(), gravity=gravity.tolist(), samples=samples,
                                                force=forces.tolist(), moment=moments.tolist(), strain=strain.tolist(), curvature=curvature.tolist(),
                                                scope='Independent literal two-endpoint interpolation and matrix/weight arithmetic at the saved current geometry; no additional field evaluation or solve.'))


def run(stage):
    plan = read(stage/'plan.json')
    authorization = read(stage/'authorization.json')
    require(authorization.get('authorized') is True and authorization.get('plan_sha256') == pin(stage/'plan.json')['sha256'], 'Exact-plan root authorization is required.')
    require(unchanged(plan), 'Frozen inputs changed before execution.')
    require(not (stage/'execution.json').exists(), 'Execution already attempted; no automatic retry.')
    execution = dict(status='RUNNING', pid=os.getpid(), plan=pin(stage/'plan.json'), children={}, retries=0)
    write(stage/'execution.json', execution)
    started = time.monotonic()
    try:
        for case in plan['cases']:
            name = case['name']; folder = stage/'cases'/name
            command = [sys.executable, str(Path(__file__).resolve()), 'worker', '--stage', str(stage), '--case', name]
            began = time.monotonic()
            with (folder/'run.log').open('x') as log:
                child = subprocess.Popen(command, env=dict(os.environ, **plan['thread_environment']), stdout=log, stderr=subprocess.STDOUT)
                receipt = dict(pid=child.pid, command=command, state='RUNNING')
                execution['children'][name] = receipt
                write(folder/'process.json', receipt); write(stage/'execution.json', execution)
                timed_out = False
                try:
                    code = child.wait(timeout=plan['child_cap_seconds'])
                except subprocess.TimeoutExpired:
                    timed_out = True; child.terminate()
                    try:
                        code = child.wait(timeout=plan['termination_grace_seconds'])
                    except subprocess.TimeoutExpired:
                        child.kill(); code = child.wait()
                except BaseException:
                    child.kill(); child.wait()
                    receipt.update(state='INTERRUPTED', exit_code=child.returncode, reaped=True)
                    write(folder/'process.json', receipt)
                    raise
            receipt.update(state='TERMINAL', exit_code=code, reaped=True, timed_out=timed_out, seconds=time.monotonic()-began, log=pin(folder/'run.log'))
            if (folder/'report.json').exists():
                receipt['report'] = pin(folder/'report.json')
            write(folder/'process.json', receipt); write(stage/'execution.json', execution)
            require(code == 0 and not timed_out, f'{name} failed; no retry, later cases unlaunched.')
            require(unchanged(plan), 'Source changed during execution.')
            print(json.dumps(dict(case=name, process=receipt)), flush=True)
        reports = {c['name']: read(stage/'cases'/c['name']/'report.json') for c in plan['cases']}
        operations = {key: sum(r['operations'][key] for r in reports.values()) for key in ('cold_bridge_solves', 'new_policy_fresh_residuals', 'old_policy_fresh_residuals')}
        require(operations == dict(cold_bridge_solves=3, new_policy_fresh_residuals=3, old_policy_fresh_residuals=2), 'Unexpected operation counts.')
        summary = dict(status='PASS_SOURCE_SECTION_INTEGRATION', policy=POLICY, operations=operations,
                       checks_passed=sum(r['checks_passed'] for r in reports.values()), checks_total=sum(r['checks_total'] for r in reports.values()),
                       cases={name: dict(report=pin(stage/'cases'/name/'report.json'), result=pin(stage/'cases'/name/'result.json'), solve_seconds=r['solve_seconds'], fresh_residual=r['fresh_residual']) for name, r in reports.items()},
                       seconds=time.monotonic()-started, plan=pin(stage/'plan.json'),
                       scope='Two original-state regression checks and one synthetic section check. No new reference sweep, fitted parameter, or expanded archived-ASWING acceptance.')
        write(stage/'summary.json', summary)
        execution['status'] = 'TERMINAL_COMPLETE'
    except BaseException as exc:
        execution.update(status='TERMINAL_FAILED_RETAINED', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        execution.update(seconds=time.monotonic()-started, all_launched_children_reaped=all(c.get('reaped', False) for c in execution['children'].values()), input_pins_unchanged=unchanged(plan))
        write(stage/'execution.json', execution)
    print(json.dumps(dict(summary=pin(stage/'summary.json'), execution=pin(stage/'execution.json'))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'worker'))
    parser.add_argument('--stage', type=Path, default=DEFAULT_STAGE)
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--specification', type=Path)
    parser.add_argument('--case', choices=('st3', 'st5', 'section'))
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.stage.resolve(), args.fixture, args.specification)
    elif args.action == 'worker':
        require(args.case is not None, 'Worker case is required.')
        worker(args.stage.resolve(), args.case)
    else:
        run(args.stage.resolve())
