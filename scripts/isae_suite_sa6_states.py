"""Opt-in original SA6 state targets; source planning/validation use stdlib only."""
import copy
from decimal import Decimal
import math
from pathlib import Path
import re
import time

try:
    from . import isae_suite_sa6_controls as common
except ImportError:
    import isae_suite_sa6_controls as common

SCOPE = 'sa6-state-rigid'
KIND = 'native_state_derivatives'
ROUTE = 'rigid_state_derivatives'
CHANNELS = ('CX', 'CY', 'CL', 'Cl', 'Cm', 'Cn')
PARAMETERS = ('u', 'alpha', 'beta', 'p', 'q', 'r')
SUFFIXES = ('u', 'a', 'b', 'p', 'q', 'r')
UNITS = ('fractional speed V/V0', 'rad', 'rad', 'p b/(2 V0)', 'q c/(2 V0)', 'r b/(2 V0)')
NAMES = tuple(c+s for c in CHANNELS for s in SUFFIXES)
GATES = dict(common.GATES)
OPERATIONS = dict(common.OPERATIONS)
QUALIFICATIONS = [
    'All36 original state derivatives at fixed BASE stability axes, dynamic pressure and reference lengths. Inputs are fractional speed V/V0, alpha/beta radians, and base-stability rates p*b/(2V0),q*c/(2V0),r*b/(2V0). Original controls remain fixed; no retrim.',
    'Complete steady operator with frozen jig/zero-wind source, receiver, wake and volume influences at fixed PG Mach. Current section frames, circulation and loads retain their derivatives.',
    'Historical derivative-response/global-frame, producer, NODE/basis/interpolation/K/F/startup and possible influence lagging remain unauthenticated.',
    *common.QUALIFICATIONS[2:],
    'State targets have a separate conditional ledger from static coefficients and F1 derivatives; no historical artifact is substituted for a current result.',
]
require, finite = common.require, common.finite
matrix, vector, dot, relative = common.matrix, common.vector, common.dot, common.relative


def identifies(job):
    return (job.get('target_kind') == KIND or job.get('comparison_scope') == SCOPE or
            job.get('execution_route') == ROUTE or job.get('id', '').endswith(':rigid-state'))


def decode(text):
    require(text.count('Derivatives in: Stability axes, x fwd, z down') == 1, 'Missing native state derivative axes.')
    fields = {}
    for name in NAMES:
        matches = list(re.finditer(r'\b'+name+r'\s*=\s*(\S+)', text))
        require(len(matches) == 1, 'Missing or duplicated original state target: '+name)
        match = matches[0]; token = match.group(1); value = Decimal(token.replace('D','E').replace('d','e'))
        require(value.is_finite(), 'Nonfinite original state target.')
        half = Decimal(5).scaleb(value.as_tuple().exponent-1)
        fields[name] = dict(token=token,value=float(value),tolerance=float(half),
            exact_decimal_expected=str(value),exact_decimal_tolerance=str(half),
            negative_zero=value.is_zero() and value.is_signed(),
            source_line=text.count('\n',0,match.start(1))+1,
            source_column_1based=match.start(1)-text.rfind('\n',0,match.start(1)),
            source_character_start_0based=match.start(1),source_character_end_0based=match.end(1))
    return fields


def plan(root, static_jobs, pin):
    helpers = [pin(Path(p).resolve(),root) for p in (__file__,common.__file__)]
    jobs = []
    for base in static_jobs:
        if base['execution_route'] != 'rigid_static_coefficients': continue
        job = copy.deepcopy(base)
        job.update(id=base['id']+':rigid-state',base_static_job_id=base['id'],target_kind=KIND,
            comparison_scope=SCOPE,execution_route=ROUTE,expected_outputs=36,required_outputs=list(NAMES),
            parameters=list(PARAMETERS),parameter_units=list(UNITS),numerical_gates=dict(GATES),
            expected_operations=dict(OPERATIONS),historical_derivative_response_authenticated=False,
            historical_producer_authenticated=False,influence_derivative_convention='complete_frozen_steady_operator')
        job['static_reference_row'] = copy.deepcopy(base['reference_row'])
        job['reference_row']['fields'] = decode((root/job['table_path']).read_text())
        job['sources'].extend(helpers)
        job['qualifications'] = [q for q in base['qualifications'] if not q.startswith('Six static')] + QUALIFICATIONS
        validate_record_contract(job); jobs.append(job)
    require(len(jobs) == len({j['id'] for j in jobs}) == 88, 'State scope requires all88 mesh jobs.')
    return jobs


def validate_record_contract(job):
    require(job.get('adapter') == 'sa6' and job.get('case_id') == 'SA-6' and job.get('target_kind') == KIND and
            job.get('comparison_scope') == SCOPE and job.get('execution_route') == ROUTE and
            job.get('id') == job.get('base_static_job_id','')+':rigid-state', 'Invalid SA6 state scope identity.')
    require(job.get('expected_outputs') == 36 and job.get('required_outputs') == list(NAMES) and
            set(job['reference_row']['fields']) == set(NAMES), 'State scope must retain all36 original targets.')
    require(job.get('parameters') == list(PARAMETERS) and job.get('parameter_units') == list(UNITS) and
            job.get('numerical_gates') == GATES and job.get('expected_operations') == OPERATIONS and
            job.get('historical_derivative_response_authenticated') is False and
            job.get('historical_producer_authenticated') is False and job.get('complete_family_reproduction') is False and
            job.get('influence_derivative_convention') == 'complete_frozen_steady_operator' and
            job['settings']['freeze_influences'] is True, 'State coordinates, operator, gates or qualifications changed.')
    reference_contract(job,validate=False)
    return True


def reference_contract(job, *, validate=True):
    if validate: validate_record_contract(job)
    result = {}
    for i,name in enumerate(NAMES):
        field = job['reference_row']['fields'][name]
        value = Decimal(field['token'].replace('D','E').replace('d','e')); half = Decimal(5).scaleb(value.as_tuple().exponent-1)
        require(value.is_finite() and field['value'] == float(value) and field['tolerance'] == float(half) and
                field['exact_decimal_expected'] == str(value) and field['exact_decimal_tolerance'] == str(half) and
                field['negative_zero'] is (value.is_zero() and value.is_signed()) and
                all(type(field[k]) is int and field[k] > 0 for k in ('source_line','source_column_1based')) and
                type(field['source_character_start_0based']) is int and field['source_character_start_0based'] >= 0 and
                field['source_character_end_0based'] == field['source_character_start_0based']+len(field['token']),
                'Original state precision or source position changed.')
        result[name] = dict(expected=field['value'],expected_token=field['token'],tolerance=field['tolerance'],
            **{k:field[k] for k in ('exact_decimal_expected','exact_decimal_tolerance','negative_zero','source_line',
                'source_column_1based','source_character_start_0based','source_character_end_0based')},
            coefficient=CHANNELS[i//6],parameter=PARAMETERS[i%6],units='per '+UNITS[i%6])
    return result


def reference_checks(job, values=None, reason=None):
    values = values or {}; checks = []
    for name,ref in reference_contract(job).items():
        value = values.get(name)
        error = abs(Decimal(str(value))-Decimal(ref['exact_decimal_expected'])) if finite(value) else None
        checks.append(dict(name=name,**ref,predicted=value if finite(value) else None,abs_error=float(error) if error is not None else None,
            passed=error is not None and error <= Decimal(ref['exact_decimal_tolerance']),
            **({} if error is not None else dict(unavailable_reason=reason or 'No finite current state derivative.'))))
    return checks


def predictions(api):
    return {name:api['coefficients'][i//6][i%6] for i,name in enumerate(NAMES)}


def evidence_checks(job, api, evidence):
    require(api['method'] == 'analytic implicit rigid state derivatives' and api['parameters'] == list(PARAMETERS) and
            api['coefficient_rows'] == list(CHANNELS) and api['units'] == list(UNITS) and api['axes'] == 'stability' and
            api['influence_derivative'] == 'complete current-wind source, receiver, wake, volume and PG derivatives',
            'Unexpected full state API semantics.')
    n,p = len(evidence['jacobian']),len(evidence['sample']); require(n > 0 and p > 0,'Empty state evidence.')
    jac = matrix(evidence['jacobian'],n,n,'J'); partial = matrix(evidence['input_partials'],n,6,'input partials')
    response = matrix(evidence['coefficient_response'],n,6,'response'); sample = matrix(evidence['sample'],p,n,'sampling')
    require(matrix(api['circulation_coefficients'],n,6,'API coefficient response') == response,'Detached state response.')
    gamma = matrix(api['circulation'],p,6,'physical Gamma response')
    wg = matrix(evidence['wrench_gamma'],6,n,'wrench Gamma partial'); wd = matrix(evidence['wrench_direct'],6,6,'direct wrench')
    wrench = matrix(api['distributed_aero_wrench'],6,6,'API wrench'); coeff = matrix(api['coefficients'],6,6,'API coefficients')
    tr = common.transform(job); recorded_tr = matrix(evidence['coefficient_transform'],6,6,'transform')
    base = evidence['base']; vector(base['gamma'],p,'base Gamma')
    base_wrench = vector(base['force'],3,'base force')+vector(base['moment'],3,'base moment')
    base_coeff = vector(api['base_coefficients'],6,'base coefficients')
    require(type(base['converged']) is bool and all(finite(base[k]) and base[k] >= 0 for k in ('residual','maximum_normal_mach')) and
            finite(api['base_residual']) and api['base_residual'] >= 0 and
            finite(api['reciprocal_condition']) and 0 <= api['reciprocal_condition'] <= 1, 'Invalid base evidence.')
    reported = vector(api['linear_residuals'],6,'reported tangent residuals')
    require(all(value >= 0 for value in reported), 'Negative reported tangent residual.')
    linear, wrench_errors, gamma_errors, coefficient_errors = [],[],[],[]
    for k in range(6):
        column = [r[k] for r in response]; rhs = [r[k] for r in partial]
        linear.append(max(abs(dot(row,column)+b) for row,b in zip(jac,rhs))/max(1.,max(map(abs,rhs))))
        full_wrench = [row[k]+dot(w,column) for row,w in zip(wd,wg)]
        wrench_errors.append(relative(full_wrench,[r[k] for r in wrench]))
        gamma_errors.append(relative([dot(row,column) for row in sample],[r[k] for r in gamma]))
        coefficient_errors.append(relative([dot(row,full_wrench) for row in tr],[r[k] for r in coeff]))
    numeric = [('base residual',max(base['residual'],api['base_residual']),'<=',GATES['base_residual']),
        ('local section Mach',base['maximum_normal_mach'],'<',1.),
        ('full tangent residual',max(linear),'<=',GATES['linear_residual']),
        ('reported tangent residual',max(reported),'<=',GATES['linear_residual']),
        ('reciprocal condition',api['reciprocal_condition'],'>=',GATES['reciprocal_condition']),
        ('coefficient transform',max(abs(a-b) for r,s in zip(tr,recorded_tr) for a,b in zip(r,s)),'<=',GATES['reconstruction']),
        ('base coefficient normalization',relative([dot(row,base_wrench) for row in tr],base_coeff),'<=',GATES['reconstruction']),
        ('total derivative wrench',max(wrench_errors),'<=',GATES['reconstruction']),
        ('physical circulation response',max(gamma_errors),'<=',GATES['reconstruction']),
        ('derivative coefficient normalization',max(coefficient_errors),'<=',GATES['reconstruction'])]
    checks = [dict(name=name,value=value,comparison=op,tolerance=gate,passed=bool(finite(value) and value >= 0 and
        (value < gate if op == '<' else value >= gate if op == '>=' else value <= gate))) for name,value,op,gate in numeric]
    checks += [dict(name='converged base',passed=base['converged']),dict(name='one outer base evaluation',passed=api['physical_evaluations']==1),
               dict(name='one derivative factorization',passed=api['factorizations']==1)]
    return checks


def validate_result_contract(job, result):
    validate_record_contract(job); contract = reference_contract(job); checks = result.get('reference_checks',[])
    require(len(checks) <= 36 and len({c.get('name') for c in checks}) == len(checks), 'Duplicate or excess state checks.')
    for check in checks:
        require(check.get('name') in contract and all(check.get(k) == v for k,v in contract[check['name']].items()), 'Changed state reference metadata.')
        wanted = reference_checks(job,{check['name']:check.get('predicted')})[NAMES.index(check['name'])]
        require(check.get('passed') is wanted['passed'] and check.get('abs_error') == wanted['abs_error'], 'Changed state Decimal comparison.')
    if result.get('status') != 'computed':
        require(result.get('numerical_pass') is not True and result.get('numerical_passed') is not True and result.get('reference_match') is not True,
                'Failed state result claims success.')
        return True
    require(all(result.get(k) == v for k,v in job.items() if k != 'result' and not k.startswith('_summary_')) and
            result.get('sources_unchanged') is True and result.get('physical_calls') == result.get('factorizations') == 1 and
            result.get('operations') == OPERATIONS and len(checks) == 36, 'Incomplete computed state contract.')
    api,evidence = result['api_result'],result['evidence']; canonical = evidence_checks(job,api,evidence)
    require(result.get('numerical_checks') == canonical and all(c['passed'] for c in canonical) and result.get('numerical_pass') is True,
            'Missing or inconsistent state numerical evidence.')
    require(checks == reference_checks(job,predictions(api)) and result.get('reference_match') is all(c['passed'] for c in checks),
            'Detached state prediction or match claim.')
    return True


def _execute(root, job):
    """Only numerical entry point: one complete steady-operator API call."""
    import numpy as np
    from openswing import asw, aero, rigid_derivatives
    for module in (asw,aero,rigid_derivatives):
        require(Path(module.__file__).resolve() == root/'openswing'/(module.__name__.split('.')[-1]+'.py'),'Wrong production import root.')
    s = job['settings']; model = asw.parse_asw((root/job['model_path']).read_text(),beam_interpolation=s['beam_interpolation'])
    require(not model.diagnostics and float(model.constants[1]) == s['density'] and
            np.array_equal(model.reference[0],[.3871,.254,1.524]) and np.array_equal(model.reference[1],[0.,0.,0.]),'Literal model/reference changed.')
    keys = ('speed','alpha','beta','density','mach','freeze_influences','stall','stall_factor','stall_width','wake_core_ratio','aero_lag','body_added_mass_factor')
    condition = aero.FlightCondition(**{k:s[k] for k in keys},controls={int(k):v for k,v in s['controls'].items()})
    captured = []
    api = rigid_derivatives.rigid_state_derivatives(model,condition,panels=s['panels'],parameters=list(PARAMETERS),
        circulation_method=s['circulation_method'],_audit=captured.append)
    require(len(captured) == 1,'Expected one state audit callback.')
    audit = captured[0]; base = audit['base']; data = audit['fields'].circulation_aero
    evidence = {key:np.asarray(audit[key]).tolist() for key in ('jacobian','input_partials','coefficient_response','wrench_gamma','wrench_direct','coefficient_transform')}
    evidence.update(sample=data['basis'].sample.tolist(),base=dict(gamma=np.asarray(data['gamma']).tolist(),
        force=np.asarray(base['distributed_aero_force']).tolist(),moment=np.asarray(base['distributed_aero_moment']).tolist(),
        residual=float(base['residual']),converged=bool(base['converged']),maximum_normal_mach=max(float(x['normal_mach']) for x in base['strips']),
        t=data['p']['t'].tolist(),beam=data['p']['beam'].tolist(),positions=data['p']['rm'].tolist(),
        mesh_discretization=base.get('mesh_discretization'),circulation_solver=base.get('circulation_solver')))
    return api,evidence

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
        result['reference_checks'] = reference_checks(job, predictions(api))
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
