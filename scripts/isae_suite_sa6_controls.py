"""Opt-in original SA6 F1 targets; planning and evidence validation are stdlib-only."""
import copy
from decimal import Decimal
import math
from pathlib import Path
import re
import time

SCOPE = 'sa6-f1-rigid'
KIND = 'native_control_derivatives'
ROUTE = 'rigid_control_derivatives'
CHANNELS = ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')
NAMES = tuple(name+'dF1' for name in CHANNELS)
GATES = dict(base_residual=1e-8, linear_residual=1e-8, reciprocal_condition=1e-10,
             reconstruction=2e-10)
OPERATIONS = dict(cold_rigid_calls=1, derivative_factorizations=1, perturbed_calls=0, retries=0)
QUALIFICATIONS = [
    'Six original F1 derivatives at fixed base stability axes, dynamic pressure and reference lengths; per literal file control unit.',
    'Conditional prescribed-geometry derivative: historical producer, derivative-response/global-frame, NODE and K/F startup settings are not authenticated.',
    'The four unchanged decks have infinite stiffness under the published zero/omitted-stiffness convention. Elastic shape response vanishes at the same body anchor, fixed base, aerodynamic convention and mesh; this does not authenticate global-frame or aerodynamic settings.',
    'One outer base aerodynamic evaluation includes its internal nonlinear iterations; one factorization counts the derivative LU only. No perturbed flow solves or finite-difference production fallback.',
    'This supplemental scope leaves all registered static targets and historical results intact. All original zeros and failures remain required; no whole-family acceptance is implied.',
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def identifies(job):
    return (job.get('target_kind') == KIND or job.get('comparison_scope') == SCOPE or
            job.get('execution_route') == ROUTE or job.get('id', '').endswith(':rigid-F1'))


def decode(text):
    require(text.count('Derivatives in: Stability axes, x fwd, z down') == 1,
            'Missing original stability-axis derivative heading.')
    fields = {}
    for name in NAMES:
        matches = list(re.finditer(r'\b'+name+r'\s*=\s*(\S+)', text))
        require(len(matches) == 1, 'Missing or duplicated original F1 target: '+name)
        match = matches[0]; token = match.group(1)
        value = Decimal(token.replace('D', 'E').replace('d', 'e'))
        require(value.is_finite(), 'Nonfinite original F1 target.')
        half = Decimal(5).scaleb(value.as_tuple().exponent-1)
        fields[name] = dict(token=token, value=float(value), tolerance=float(half),
            exact_decimal_expected=str(value), exact_decimal_tolerance=str(half),
            source_line=text.count('\n', 0, match.start(1))+1,
            source_column_1based=match.start(1)-text.rfind('\n', 0, match.start(1)))
    return fields


def plan(root, static_jobs, pin):
    helper = pin(Path(__file__).resolve(), root)
    jobs = []
    for base in static_jobs:
        if base['execution_route'] != 'rigid_static_coefficients':
            continue
        job = copy.deepcopy(base)
        job.update(id=base['id']+':rigid-F1', base_static_job_id=base['id'],
            target_kind=KIND, comparison_scope=SCOPE, execution_route=ROUTE,
            required_outputs=list(NAMES), numerical_gates=dict(GATES),
            expected_operations=dict(OPERATIONS), historical_derivative_response_authenticated=False,
            historical_producer_authenticated=False)
        job['static_reference_row'] = copy.deepcopy(base['reference_row'])
        job['reference_row']['fields'] = decode((root/job['table_path']).read_text())
        job['sources'].append(helper)
        job['qualifications'] = [q for q in base['qualifications'] if not q.startswith('Six static')] + QUALIFICATIONS
        validate_record_contract(job)
        jobs.append(job)
    require(len(jobs) == 88 and len({j['id'] for j in jobs}) == 88, 'F1 scope requires all 88 mesh jobs.')
    return jobs


def validate_record_contract(job):
    require(job.get('adapter') == 'sa6' and job.get('case_id') == 'SA-6' and
            job.get('target_kind') == KIND and job.get('comparison_scope') == SCOPE and
            job.get('execution_route') == ROUTE and
            job.get('id') == job.get('base_static_job_id', '')+':rigid-F1', 'Invalid SA6 F1 scope identity.')
    require(job.get('expected_outputs') == 6 and job.get('required_outputs') == list(NAMES) and
            set(job['reference_row']['fields']) == set(NAMES), 'F1 scope must retain all six original targets.')
    require(job.get('numerical_gates') == GATES and job.get('expected_operations') == OPERATIONS and
            job.get('historical_derivative_response_authenticated') is False and
            job.get('historical_producer_authenticated') is False and
            job.get('complete_family_reproduction') is False, 'F1 gates, operations or qualifications changed.')
    reference_contract(job, validate=False)
    return True


def reference_contract(job, *, validate=True):
    if validate:
        validate_record_contract(job)
    contract = {}
    for name in NAMES:
        field = job['reference_row']['fields'][name]
        value = Decimal(field['token'].replace('D', 'E').replace('d', 'e'))
        half = Decimal(5).scaleb(value.as_tuple().exponent-1)
        require(value.is_finite() and field['value'] == float(value) and field['tolerance'] == float(half) and
                field['exact_decimal_expected'] == str(value) and field['exact_decimal_tolerance'] == str(half) and
                type(field['source_line']) is int and field['source_line'] > 0 and
                type(field['source_column_1based']) is int and field['source_column_1based'] > 0,
                'Original F1 precision or source position changed.')
        contract[name] = dict(expected=field['value'], expected_token=field['token'], tolerance=field['tolerance'],
            exact_decimal_expected=field['exact_decimal_expected'], exact_decimal_tolerance=field['exact_decimal_tolerance'],
            source_line=field['source_line'], source_column_1based=field['source_column_1based'],
            units='per file control unit')
    return contract


def reference_checks(job, values=None, reason=None):
    values = values or {}
    checks = []
    for name, ref in reference_contract(job).items():
        value = values.get(name)
        error = abs(Decimal(str(value))-Decimal(ref['exact_decimal_expected'])) if finite(value) else None
        checks.append(dict(name=name, **ref, predicted=value if finite(value) else None,
            abs_error=float(error) if error is not None else None,
            passed=error is not None and error <= Decimal(ref['exact_decimal_tolerance']),
            **({} if error is not None else dict(unavailable_reason=reason or 'No finite current derivative.'))))
    return checks


def matrix(value, rows, columns, label):
    require(isinstance(value, list) and len(value) == rows and all(isinstance(row, list) and
        len(row) == columns and all(map(finite, row)) for row in value), 'Invalid finite matrix: '+label)
    return value


def vector(value, size, label):
    require(isinstance(value, list) and len(value) == size and all(map(finite, value)), 'Invalid finite vector: '+label)
    return value


def dot(a, b):
    return math.fsum(x*y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def relative(a, b):
    return max((abs(x-y) for x, y in zip(a, b)), default=0.)/max(1., max(map(abs, b), default=0.))


def transform(job):
    s = job['settings']; qS = .5*s['density']*s['speed']**2*.3871
    c, sn = math.cos(math.radians(s['alpha'])), math.sin(math.radians(s['alpha']))
    return [[-c/qS, 0., -sn/qS, 0., 0., 0.], [0., 1/qS, 0., 0., 0., 0.],
        [-sn/qS, 0., c/qS, 0., 0., 0.], [0., 0., 0., -c/(qS*1.524), 0., -sn/(qS*1.524)],
        [0., 0., 0., 0., 1/(qS*.254), 0.], [0., 0., 0., sn/(qS*1.524), 0., -c/(qS*1.524)]]


def evidence_checks(job, api, evidence):
    """Reconstruct the full saved tangent and direct separation term, no NumPy."""
    require(api['method'] == 'analytic implicit rigid control derivatives' and api['controls'] == [1] and
            api['coefficient_rows'] == list(CHANNELS) and api['units'] == 'per file flap setting' and
            api['axes'] == 'stability', 'Unexpected analytic API semantics.')
    n = len(evidence['jacobian']); p = len(evidence['surface'])
    require(n > 0 and p > 0, 'Empty analytic tangent evidence.')
    jac = matrix(evidence['jacobian'], n, n, 'J')
    rhs = [v[0] for v in matrix(evidence['input_partials'], n, 1, 'input partials')]
    response = [v[0] for v in matrix(evidence['coefficient_response'], n, 1, 'response')]
    wg = matrix(evidence['wrench_gamma'], 6, n, 'wrench Gamma partial')
    wd = [v[0] for v in matrix(evidence['wrench_direct'], 6, 1, 'wrench direct partial')]
    sample = matrix(evidence['sample'], p, n, 'circulation sampling')
    api_response = [v[0] for v in matrix(api['circulation_coefficients'], n, 1, 'API coefficient response')]
    api_gamma = [v[0] for v in matrix(api['circulation'], p, 1, 'API circulation response')]
    api_wrench = [v[0] for v in matrix(api['distributed_aero_wrench'], 6, 1, 'API wrench')]
    api_coeff = [v[0] for v in matrix(api['coefficients'], 6, 1, 'API coefficient derivatives')]
    require(response == api_response, 'Detached coefficient response.')
    computed_wrench = [direct+dot(row, response) for direct, row in zip(wd, wg)]
    tr = transform(job); recorded_tr = matrix(evidence['coefficient_transform'], 6, 6, 'coefficient transform')
    base = evidence['base']
    base_wrench = vector(base['force'], 3, 'base force')+vector(base['moment'], 3, 'base moment')
    base_coeff = vector(api['base_coefficients'], 6, 'API base coefficients')
    vector(base['gamma'], p, 'base Gamma')
    require(type(base['converged']) is bool and all(finite(base[k]) for k in ('residual','maximum_normal_mach')) and
            finite(api['base_residual']) and finite(api['reciprocal_condition']), 'Nonfinite base evidence.')
    reported_linear = vector(api['linear_residuals'], 1, 'API linear residual')
    linear = max(abs(dot(row, response)+b) for row, b in zip(jac, rhs))/max(1., max(map(abs, rhs)))
    force, moment = [0.]*3, [0.]*3
    tangency_error = 0.
    for row in evidence['surface']:
        for key in ('normal','section_normal','c','s','velocity','cp_velocity','position','profile_arm'):
            vector(row[key], 3, key)
        require(all(finite(row[k]) for k in ('ds','chord','slope','dCLdF1','dCDdF1','dCMdF1','tangency')) and
                row['ds'] > 0 and row['chord'] > 0 and row['slope'] > 0 and
                row['dCDdF1'] == row['dCMdF1'] == 0., 'Literal SA6 direct-control premise changed.')
        normal, section, chord, span = (row[k] for k in ('normal','section_normal','c','s'))
        dn = [row['dCLdF1']/row['slope']*(dot(normal, section)*c-dot(normal, chord)*a)
              for c, a in zip(chord, section)]
        v = row['velocity']; along = dot(v, span); vp = [a-along*b for a, b in zip(v, span)]
        speed = math.sqrt(dot(vp, vp)); require(speed > 0, 'Undefined section speed.')
        tau = dot(row['cp_velocity'], normal)
        tangency_error = max(tangency_error, abs(tau-row['tangency'])/max(1., abs(tau)))
        scale = 4*job['settings']['density']*row['ds']*row['chord']*tau*dot(row['cp_velocity'], dn)/speed
        df = [scale*x for x in vp]; arm = [a+b for a, b in zip(row['position'], row['profile_arm'])]
        dm = cross(arm, df)
        force = [a+b for a, b in zip(force, df)]; moment = [a+b for a, b in zip(moment, dm)]
    numeric = [
        ('base residual', max(base['residual'], api['base_residual']), '<=', GATES['base_residual']),
        ('local section Mach', base['maximum_normal_mach'], '<', 1.),
        ('full tangent residual', linear, '<=', GATES['linear_residual']),
        ('reported tangent residual', max(reported_linear), '<=', GATES['linear_residual']),
        ('reciprocal condition', api['reciprocal_condition'], '>=', GATES['reciprocal_condition']),
        ('direct separation closure', relative(force+moment, wd), '<=', GATES['reconstruction']),
        ('CP tangency recovery', tangency_error, '<=', GATES['reconstruction']),
        ('coefficient transform', max(abs(a-b) for r, s in zip(tr, recorded_tr) for a, b in zip(r, s)), '<=', GATES['reconstruction']),
        ('base coefficient normalization', relative([dot(r, base_wrench) for r in tr], base_coeff), '<=', GATES['reconstruction']),
        ('total derivative wrench', relative(computed_wrench, api_wrench), '<=', GATES['reconstruction']),
        ('physical circulation response', relative([dot(r, response) for r in sample], api_gamma), '<=', GATES['reconstruction']),
        ('derivative coefficient normalization', relative([dot(r, computed_wrench) for r in tr], api_coeff), '<=', GATES['reconstruction'])]
    checks = [dict(name=name, value=value, comparison=op, tolerance=gate,
                   passed=bool(finite(value) and value >= 0 and
                    (value < gate if op == '<' else value >= gate if op == '>=' else value <= gate)))
              for name, value, op, gate in numeric]
    checks += [dict(name='converged base', passed=base['converged']),
               dict(name='one outer base evaluation', passed=api['physical_evaluations'] == 1),
               dict(name='one derivative factorization', passed=api['factorizations'] == 1)]
    return checks


def validate_result_contract(job, result):
    validate_record_contract(job)
    contract = reference_contract(job)
    checks = result.get('reference_checks', [])
    require(len(checks) <= 6 and len({c.get('name') for c in checks}) == len(checks), 'Duplicate or excess F1 checks.')
    for check in checks:
        require(check.get('name') in contract and all(check.get(k) == v for k, v in contract[check['name']].items()),
                'Changed F1 reference metadata.')
        expected = reference_checks(job, {check['name']:check.get('predicted')})[NAMES.index(check['name'])]
        require(check.get('passed') is expected['passed'] and check.get('abs_error') == expected['abs_error'], 'Changed F1 decimal comparison.')
    if result.get('status') != 'computed':
        require(result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and
                result.get('reference_match') is not True, 'Failed F1 result claims success.')
        return True
    require(all(result.get(k) == v for k, v in job.items() if k != 'result' and not k.startswith('_summary_')) and result.get('sources_unchanged') is True and
            result.get('physical_calls') == 1 and result.get('factorizations') == 1 and
            result.get('operations') == OPERATIONS and len(checks) == 6, 'Incomplete computed F1 contract.')
    api, evidence = result['api_result'], result['evidence']
    canonical = evidence_checks(job, api, evidence)
    require(result.get('numerical_checks') == canonical and all(c['passed'] for c in canonical) and
            result.get('numerical_pass') is True, 'Missing or inconsistent F1 numerical evidence.')
    values = {name: row[0] for name, row in zip(NAMES, api['coefficients'])}
    require(checks == reference_checks(job, values) and
            result.get('reference_match') is all(c['passed'] for c in checks), 'Detached F1 prediction or match claim.')
    return True


def _execute(root, job):
    """Only numerical entry point; one unchanged analytic production API call."""
    import numpy as np
    from openswing import asw, aero, rigid_derivatives
    for module in (asw, aero, rigid_derivatives):
        require(Path(module.__file__).resolve() == root/'openswing'/(module.__name__.split('.')[-1]+'.py'), 'Wrong production import root.')
    s = job['settings']; model = asw.parse_asw((root/job['model_path']).read_text(), beam_interpolation=s['beam_interpolation'])
    require(not model.diagnostics and float(model.constants[1]) == s['density'] and
            np.array_equal(model.reference[0], [.3871,.254,1.524]) and np.array_equal(model.reference[1], [0.,0.,0.]),
            'Literal model/reference/parser changed.')
    keys = ('speed','alpha','beta','density','mach','freeze_influences','stall','stall_factor','stall_width',
            'wake_core_ratio','aero_lag','body_added_mass_factor')
    condition = aero.FlightCondition(**{k:s[k] for k in keys}, controls={int(k):v for k,v in s['controls'].items()})
    captured = []
    api = rigid_derivatives.rigid_control_derivatives(model, condition, panels=s['panels'], controls=[1],
        circulation_method=s['circulation_method'], _audit=captured.append)
    require(len(captured) == 1, 'Expected one analytic audit callback.')
    audit = captured[0]; base = audit['base']; data = audit['fields'].circulation_aero; p = data['p']
    surface = []
    for i in range(len(data['gamma'])):
        beam = next(b for b in model.beams if b.index == int(p['beam'][i]))
        row = {name:np.asarray(p[name][i]).tolist() for name in ('normal','section_normal','c','s','ds','chord','slope','profile_arm')}
        row.update(position=p['rm'][i].tolist(), velocity=data['velocity'][i].tolist(),
            cp_velocity=data['cp_velocity'][i].tolist(), tangency=float(data['tangency'][i]),
            t=float(p['t'][i]), beam=int(p['beam'][i]))
        row.update({name:float(beam.value(name, p['t'][i])) for name in ('dCLdF1','dCDdF1','dCMdF1')})
        surface.append(row)
    evidence = {key:np.asarray(audit[key]).tolist() for key in ('jacobian','input_partials','coefficient_response',
        'wrench_gamma','wrench_direct','coefficient_transform')}
    evidence.update(sample=data['basis'].sample.tolist(), surface=surface, base=dict(
        gamma=np.asarray(data['gamma']).tolist(), force=np.asarray(base['distributed_aero_force']).tolist(),
        moment=np.asarray(base['distributed_aero_moment']).tolist(), residual=float(base['residual']),
        converged=bool(base['converged']), maximum_normal_mach=max(float(x['normal_mach']) for x in base['strips']),
        mesh_discretization=base.get('mesh_discretization'), circulation_solver=base.get('circulation_solver')))
    return api, evidence


def run(root, job, verify):
    root = Path(root).resolve(); start = time.monotonic()
    result = dict(copy.deepcopy(job), status='error', numerical_pass=False, reference_match=False,
        physical_calls=0, factorizations=0, sources_unchanged=False, numerical_checks=[],
        reference_checks=reference_checks(job), operations=dict(OPERATIONS, cold_rigid_calls=0, derivative_factorizations=0))
    try:
        verify(root, job)
        result['physical_calls'] = 1
        result['operations']['cold_rigid_calls'] = 1
        api, evidence = _execute(root, job)
        result.update(api_result=api, evidence=evidence, factorizations=api['factorizations'])
        result['operations']['derivative_factorizations'] = api['factorizations']
        result['numerical_checks'] = evidence_checks(job, api, evidence)
        result['reference_checks'] = reference_checks(job, {name:row[0] for name,row in zip(NAMES,api['coefficients'])})
        result['numerical_pass'] = all(c['passed'] for c in result['numerical_checks'])
        result['status'] = 'computed' if result['numerical_pass'] else 'numerical_failure'
        result['reference_match'] = result['numerical_pass'] and all(c['passed'] for c in result['reference_checks'])
    except Exception as exc:
        result.update(status='error', error_type=type(exc).__name__, error=str(exc), numerical_pass=False, reference_match=False)
    finally:
        try:
            verify(root, job)
            result['sources_unchanged'] = True
        except (OSError, ValueError):
            result.update(status='source_mismatch', numerical_pass=False, reference_match=False, sources_unchanged=False)
        result['seconds'] = time.monotonic()-start
    nonfinite = []
    def clean(value, path=''):
        if isinstance(value, float) and not math.isfinite(value):
            nonfinite.append(path)
            return None
        if isinstance(value, dict):
            return {key:clean(item, path+'.'+key) for key,item in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(item, path+f'[{i}]') for i,item in enumerate(value)]
        return value
    result = clean(result)
    result['nonfinite_fields'] = nonfinite
    if nonfinite:
        result.update(status='numerical_failure', numerical_pass=False, reference_match=False)
    return result
