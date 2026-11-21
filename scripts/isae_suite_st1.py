"""Complete ST1 native inventory and one qualified static position snapshot.

Planning and blocked validation use the standard library only. The unchanged
literal [45_0]_3a candidate uses the source section operator, with one cold
solve and one restored residual per prospective mesh. Other literal grammar
errors, all complex modal roots, shared/unpaired outputs and model inventories
remain visible; no input repair or modal-frequency substitution is performed.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import traceback

CATALOG = 'docs/validation/isae-st1-readiness-20261027/report.json'
CATALOG_SHA256 = 'a43d32673419e3a17a71bde84848603a1cdd09c88ab8654cf086f9bf9a2589aa'
NOMINALS = (100, 200)
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-section-v1')
GATES = dict(residual=1e-8, relative_balance=1e-7, restored_parity=2e-10, clamp=1e-10)
NAMES = tuple('row001_sensor1_r'+axis+'_body_m' for axis in 'xyz')
SENSOR = [1., 1., -.22, 0., -.22, 0., 1., 1., 1., 1., 1., 1.]
WEIGHT = [1., -.28, 0., -.28, 0., .4*9.81] + [0.]*11
REFERENCE = [[1., 1., 1.], [0., 0., 0.], [0., 0., 0.], [0., 0., 0.]]
MANDATORY = [-.28, -.22, .28]
NULL_SENSOR_FIELDS = ('axes_body', 'axes_earth', 'air_velocity_sensor', 'rates_sensor',
    'acceleration_sensor', 'angular_acceleration_sensor', 'alpha', 'beta', 'bank', 'speed', 'flow_singular')
QUALIFICATIONS = [
    'All 197 stored native scalars from 27 original files remain required; only the three static [45_0]_3a position targets repeat across two declared meshes.',
    'All 76 complex eigenvalue rows retain both real and imaginary components, including 25 real-only roots. They are not converted to selected positive frequencies.',
    'The final producer mass0.4 and twist adder0 agree with the retained [45_0]_3a snapshot, but no run transcript establishes historical source bytes or executable identity.',
    'Original NODE I100 and OPER iteration limit100 are retained as source commands. Current100/200 cosine intervals are prospective reconstruction choices, not recovered historical node arrays.',
    'The current comparison is structural-only with explicit body gravity[0,0,-9.81], no FlightCondition and no aerodynamic load. Historical startup airflow, pose, gravity direction and nonlinear continuation are unknown.',
    'Lowercase rx/ry/rz are body-relative beam-anchor position at t=-.22. No sensor relocation, baseline subtraction, absolute value, Earth-coordinate substitution or fitted reference is applied.',
    'Explicit parallel sensor vectors remain unchanged. Undefined triad-dependent outputs stay unavailable; the independent anchor/body/GPS/section quantities are retained. A defined V direction may still supply heading/elevation.',
    'The other nine models retain their original unfinished Engine blocks and surplus scaling fields. No implicit End, field truncation, negative-mass correction or Weight deletion is used.',
    'Shared and command-unpaired files stay separate, including byte-identical static CSV/TXT copies. Supplemental mesh-tree duplicates add no independent target slots.',
    'The 197 native scalars do not exhaust source-labelled postprocessor arrays, nine static sweep groups, 14 experimental CSV candidates or 20 undecoded plots. All61 output candidates remain inventoried; this is not a full-family denominator.',
    'Printed half-last-place tolerances remain exact. Mesh differences are descriptive and do not establish a family or historical reproduction pass.']
UNKNOWN_SETUP = ['producing ASWING_R_5_98 executable/build and exact input bytes at generation',
    'startup atmosphere, airflow, pose and body gravity direction', 'historical NODE arrays and nonlinear continuation',
    'shared/unpaired output writers and additional postprocessor/plot target provenance']
PHYSICAL_CHECK_SPECS = {
    **{name:dict(kind='exact') for name in ('same_operator_identity', 'restore_without_evaluation', 'one_restored_residual',
        'converged', 'no_parser_diagnostics', 'literal_source_hash', 'literal_reference', 'literal_weight_rows',
        'literal_sensor_rows', 'active_tip_weight', 'source_policy', 'cold_structural_setup', 'restored_structural_setup',
        'mesh_panel_setting', 'mandatory_stations_present', 'root_clamp_count', 'sensor_frame_scope', 'finite_positions')},
    'fresh_full_residual':dict(kind='metric', gate='residual'),
    **{name:dict(kind='balance', gate='relative_balance') for name in ('force_balance', 'moment_balance')},
    **{name:dict(kind='clamp', gate='clamp') for name in ('root_clamp_position', 'root_clamp_frame')},
    'independent_tip_weight_wrench':dict(kind='weight_wrench', gate='restored_parity'),
    'independent_sensor_anchor':dict(kind='sensor_anchor', gate='restored_parity'),
    'restored_position_parity':dict(kind='parity', gate='restored_parity')}
REQUIRED_PHYSICAL_CHECKS = tuple(PHYSICAL_CHECK_SPECS)


def _require(ok, message):
    if not ok:
        raise ValueError('ST1 '+message)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _decimal(token):
    value = Decimal(token.replace('D', 'E').replace('d', 'e'))
    _require(value.is_finite(), 'nonfinite original target.')
    half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    return value, half


def _context(root):
    root = Path(root).resolve(); path = root/CATALOG
    _require(_pin(path)['sha256'] == CATALOG_SHA256, 'readiness catalog changed; source re-audit required.')
    catalog = json.loads(path.read_bytes())
    _require(catalog['format'] == 'openswing-isae-st1-source-readiness' and catalog['version'] == 1,
             'invalid source catalog schema.')
    # Historical production pins describe the earlier audit and must not be
    # misrepresented as the current kernel. Current modules are pinned per job.
    originals = (catalog['original_source_pins'] +
        [p for p in catalog['supporting_source_pins'] if not p['path'].startswith('openswing/')] +
        [item['source'] for item in catalog['supplemental_duplicate_tree']['files_with_family_bindings']])
    pins = []
    for item in originals:
        actual = _pin(root/item['path'])
        _require(all(actual[k] == item[k] for k in ('bytes', 'sha256')), 'source changed: '+item['path'])
        if actual not in pins:
            pins.append(actual)
    pins += [_pin(path), _pin(Path(__file__))]
    _require(len(catalog['models']) == 10 and len(catalog['native_outputs']) == 27, 'source inventory incomplete.')
    counts = dict(sensor_position=0, eigenvalue=0); roots = real_only = 0
    for table in catalog['native_outputs']:
        lines = (root/table['source']['path']).read_text().splitlines()
        for header in table['header_lines']:
            _require(lines[header['line']-1] == header['text'], 'native header changed.')
        _require(len(table['rows']) == len(lines)-len(table['header_lines']), 'unaccounted native row.')
        for row in table['rows']:
            _require(lines[row['line_number']-1] == row['raw_line'] and row['raw_line'].split() == row['tokens'],
                     'native source row changed.')
            expected_width = 5 if table['kind'] == 'sensor_position' else 3
            _require(len(row['tokens']) == expected_width, 'native column count changed.')
            offset = 2 if table['kind'] == 'sensor_position' else 1
            _require([o['token'] for o in row['observations']] == row['tokens'][offset:], 'native output column omitted.')
            counts[table['kind']] += len(row['observations'])
            if table['kind'] == 'eigenvalue':
                roots += 1; real_only += Decimal(row['tokens'][2]) == 0
    _require(counts == dict(sensor_position=45, eigenvalue=152) and roots == 76 and real_only == 25,
             'complete native scalar/root scope changed.')
    return root, catalog, pins


def _observations(table):
    result = []
    for row in table['rows']:
        tokens = list(re.finditer(r'\S+', row['raw_line']))
        offset = 2 if table['kind'] == 'sensor_position' else 1
        for column, original in enumerate(row['observations'], offset):
            item = deepcopy(original); value, half = _decimal(item['token'])
            _require(item['expected'] == float(value) and item['expected_hex'] == float(value).hex() and
                item['tolerance'] == float(half) and item['exact_decimal_expected'] == str(value) and
                item['exact_decimal_half_last_place'] == str(half), 'source target precision changed.')
            item.update(source_name=item['name'], name=f"row{row['row_number']:03d}_"+item['name'],
                expected_token=item['token'], exact_decimal_tolerance=str(half),
                source_line=row['line_number'], source_column_1based=column+1,
                source_character_1based=tokens[column].start()+1, row_number=row['row_number'],
                raw_line=row['raw_line'], raw_tokens=deepcopy(row['tokens']),
                category='native_position' if table['kind'] == 'sensor_position' else 'native_eigenvalue',
                real_only_root=table['kind'] == 'eigenvalue' and Decimal(row['tokens'][2]) == 0)
            result.append(item)
    return result


def _jobs(root, catalog, pins, only=None):
    candidate = catalog['smallest_candidate']; candidate_path = candidate['output']['source']['path']
    model_lookup = {item['source']['path']:item for item in catalog['models']}
    kernels = None
    def packet(identifier, kind, coordinate, model, table, observations, rows, nominal=None, extra=None):
        nonlocal kernels
        if only is not None and identifier != only:
            return None
        worker = kind == 'native_position'
        if worker and kernels is None:
            kernels = [_pin(p) for p in sorted((root/'openswing').glob('*.py'))]
        job = dict(id=identifier, case_id='ST-1', adapter='st1', target_kind=kind,
            coordinate_id=coordinate, execution_route='worker' if worker else 'unsupported',
            model_path=model, table_path=table, source=None if model is None else str(root/model),
            observations=observations, reference_rows=rows, expected_outputs=len(observations),
            source_group='model_inventory' if kind == 'model_inventory' else 'native_original',
            nominal=nominal, mesh='none' if nominal is None else f'm{nominal}',
            panels=None if nominal is None else dict(default=nominal, beams={'1':dict(count=nominal, spacing='cosine')}),
            settings=deepcopy(POLICY) if worker else None, condition=None, gravity=[0., 0., -9.81] if worker else None,
            source_pins=pins, kernel_pins=kernels if worker else [], numerical_gates=deepcopy(GATES) if worker else None,
            expected_operations=dict(cold_solves=int(worker), fresh_residuals=int(worker), retries=0),
            suggested_cap_seconds=180, original_file_modified=False, historical_settings_recovered=False,
            complete_family_reproduction=False, qualifications=list(QUALIFICATIONS), unknown_setup=list(UNKNOWN_SETUP),
            reference_scope='All197 native stored scalars; additional arrays and plots remain outside this provenance-bound denominator.')
        if worker:
            job.update(literal_model_sha256=candidate['model']['sha256'], literal_reference=deepcopy(REFERENCE),
                literal_weight_rows=[list(WEIGHT)], literal_sensor_rows=[list(SENSOR)],
                root_position=[0., .28, 0.], mandatory_stations=list(MANDATORY),
                expected_elements=nominal+1, expected_nodes=nominal+2, source_node_request=100,
                source_oper_iteration_limit=100, continuation_steps=4,
                mesh_scope='Current100/200 cosine intervals plus exact sensor station; original NODE I100 arrays unknown.',
                driver_path=candidate['driver']['path'], source_candidate=deepcopy(candidate))
        else:
            job.update(blocker_code='LITERAL_GRAMMAR_AND_MODAL_SETUP_UNRESOLVED' if kind == 'blocked_native_eigenvalues'
                else 'SOURCE_PAIRING_OR_LITERAL_GRAMMAR_UNRESOLVED' if kind == 'blocked_native_position' else 'LITERAL_MODEL_UNSUPPORTED',
                unsupported_reason='Original input/setup is unresolved. Preserve every source row and both complex components; no repairs or substitute physics.')
        if kind == 'model_inventory':
            job['required_components'] = []
        if extra:
            job.update(extra)
        return job
    for index, table in enumerate(catalog['native_outputs'], 1):
        observations = _observations(table); coordinate = f'native-{index:03d}'
        writers = table['writer_bindings']; models = sorted({w['model_path'] for w in writers})
        model = models[0] if len(models) == 1 else None
        rows = [dict(row_number=row['row_number'], line_number=row['line_number'], raw_line=row['raw_line'],
                     tokens=deepcopy(row['tokens']), real_only_root=table['kind'] == 'eigenvalue' and Decimal(row['tokens'][2]) == 0)
                for row in table['rows']]
        worker = table['source']['path'] == candidate_path
        for nominal in NOMINALS if worker else (None,):
            identifier = (f'ST-1-static-45_0_3a-position-m{nominal}' if worker else
                          f'ST-1-{coordinate}-{table["kind"]}')
            job = packet(identifier, 'native_position' if worker else 'blocked_native_'+
                ('position' if table['kind'] == 'sensor_position' else 'eigenvalues'), coordinate,
                model, table['source']['path'], observations, rows, nominal,
                dict(native_output=deepcopy(table), pairing_status=table['pairing_status'],
                     writer_bindings=deepcopy(writers), source_model_blockers={m:deepcopy(model_lookup[m]['blockers']) for m in models}))
            if job:
                yield job
    for index, model in enumerate(catalog['models'], 1):
        if model['source']['path'] == candidate['model']['path']:
            continue
        job = packet(f'ST-1-model-{index:02d}', 'model_inventory', f'model-{index:02d}',
                     model['source']['path'], None, [], [], extra=dict(model_inventory=deepcopy(model),
                     source_model_blockers=deepcopy(model['blockers']), output_candidates=deepcopy(catalog['output_candidates']),
                     supplemental_duplicate_tree=deepcopy(catalog['supplemental_duplicate_tree'])))
        if job:
            yield job


def plan(root, *, comparison_scopes=()):
    if comparison_scopes:
        _require(list(comparison_scopes)==['st1-mechanics'], 'unknown mechanics selection')
        import isae_suite_st1_mechanics as mechanics
        return mechanics.plan(root)
    root, catalog, pins = _context(root); jobs = list(_jobs(root, catalog, pins))
    _require(len(jobs) == len({j['id'] for j in jobs}) == 37 and sum(j['expected_outputs'] for j in jobs) == 200 and
             sum(j['execution_route'] == 'worker' for j in jobs) == 2, 'complete registration scope changed.')
    return jobs


build_jobs = plan


def verify_reference_sources(root, job):
    if job.get('comparison_scope')=='st1-mechanics':
        import isae_suite_st1_mechanics as mechanics
        return mechanics.verify_reference_sources(root,job)
    root, catalog, pins = _context(root); expected = list(_jobs(root, catalog, pins, job.get('id')))
    _require(len(expected) == 1 and all(job.get(k) == v for k, v in expected[0].items()),
             'job differs from canonical original inputs, rows, declared settings or current code.')
    return True


def reference_contract(job):
    if job.get('comparison_scope')=='st1-mechanics':
        import isae_suite_st1_mechanics as mechanics
        return mechanics.reference_contract(job)
    _require(job.get('case_id') == 'ST-1' and job.get('adapter') == 'st1' and job.get('target_kind') in
        ('native_position', 'blocked_native_position', 'blocked_native_eigenvalues', 'model_inventory'), 'invalid family/scope.')
    observations = job.get('observations', []); names = [item['name'] for item in observations]
    _require(len(names) == len(set(names)) == job['expected_outputs'], 'missing/duplicate scalar names.')
    if job['target_kind'] == 'native_position':
        _require(tuple(names) == NAMES and job['nominal'] in NOMINALS and job['settings'] == POLICY and
                 job['numerical_gates'] == GATES and job['condition'] is None, 'position scope/policy/gates changed.')
    for item in observations:
        value, half = _decimal(item['expected_token'])
        _require((item['expected'], item['tolerance'], item['exact_decimal_expected'], item['exact_decimal_tolerance']) ==
                 (float(value), float(half), str(value), str(half)), 'printed target precision changed.')
    return {item['name']:{k:v for k,v in item.items() if k != 'name'} for item in observations}


def _checks(job, values, reason=None):
    rows = []
    for name, ref in reference_contract(job).items():
        value = values.get(name); valid = _finite(value)
        error = abs(value-ref['expected']) if valid else None
        passed = valid and abs(Decimal(str(value))-Decimal(ref['exact_decimal_expected'])) <= Decimal(ref['exact_decimal_tolerance'])
        rows.append(dict(name=name, **ref, predicted=value if valid else None, abs_error=error,
            comparison='<=', passed=bool(passed), unavailable_reason=None if valid else reason))
    return rows


def validate_blocked(root, job):
    _require(job['execution_route'] == 'unsupported', 'static candidate requires a worker.')
    verify_reference_sources(root, job)
    return dict(id=job['id'], case_id='ST-1', adapter='st1', status='unsupported', numerical_pass=False,
        reference_match=False, reference_checks=_checks(job, {}, job['unsupported_reason']), physical_checks=[],
        operations=deepcopy(job['expected_operations']), physical_calls=0, production_imports=0,
        source_pins_unchanged=True, kernel_pins_unchanged=True, blocker_code=job['blocker_code'],
        unsupported_reason=job['unsupported_reason'], complete_family_reproduction=False)


def _relative(a, b):
    _require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b) > 0 and all(_finite(x) for x in a+b),
             'invalid independent vector evidence.')
    return max(abs(x-y) for x,y in zip(a,b))/(1.+max(map(abs, a+b)))


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _expectations(job):
    setup = dict(condition=None, gravity=job['gravity'], engines=0, loads=0, struts=0, hinges=0, sensors=1)
    return dict(restore_without_evaluation=0, one_restored_residual=1, converged=True, no_parser_diagnostics=[],
        literal_source_hash=job['literal_model_sha256'], literal_reference=REFERENCE,
        literal_weight_rows=[WEIGHT], literal_sensor_rows=[SENSOR], active_tip_weight=1,
        source_policy=dict(numerics=POLICY, operator=POLICY['structural_operator'], launch=False, structural_only=True),
        cold_structural_setup=setup, restored_structural_setup=setup,
        mesh_panel_setting=dict(panels=job['panels'], nodes=job['expected_nodes'], elements=job['expected_elements']),
        mandatory_stations_present={str(t):True for t in MANDATORY}, root_clamp_count=1,
        sensor_frame_scope=dict(axes_available=False, v_axis_available=True, reason_present=True,
            null_fields={name:True for name in NULL_SENSOR_FIELDS}, heading_finite=True, elevation_finite=True,
            section_force_finite=True, section_moment_finite=True), finite_positions={name:True for name in NAMES})


def validate_physical_checks(job, checks):
    _require(job.get('numerical_gates') == GATES, 'physical gates changed.')
    names = [item.get('name') for item in checks]
    _require(len(names) == len(set(names)) == len(REQUIRED_PHYSICAL_CHECKS) and set(names) == set(REQUIRED_PHYSICAL_CHECKS),
             'physical check set incomplete or duplicated.')
    expected = _expectations(job)
    for item in checks:
        name = item['name']; spec = PHYSICAL_CHECK_SPECS[name]; kind = spec['kind']
        if kind == 'exact':
            _require('actual' in item and 'expected' in item, 'missing exact evidence.')
            if name in expected:
                _require(item['expected'] == expected[name], 'canonical physical expectation changed.')
            elif name == 'same_operator_identity':
                _require(isinstance(item['expected'],dict) and
                    item['expected'].get('model_sha256') == job['literal_model_sha256'] and
                    item['expected'].get('structural_operator') == POLICY['structural_operator'],
                    'identity is not bound to the literal source/operator.')
            passed = item['actual'] == item['expected']
        else:
            value = item.get('metric'); gate = GATES[spec['gate']]
            _require(_finite(value) and value >= 0 and item.get('gate') == gate, 'invalid metric or changed gate.')
            if kind == 'balance':
                a,b = item['applied'],item['support']
                _require(len(a) == len(b) == 3 and all(_finite(x) for x in a+b), 'invalid balance vectors.')
                recomputed = math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b))
                _require(math.isclose(value,recomputed,rel_tol=2e-15,abs_tol=1e-30), 'balance metric changed.')
            elif kind == 'clamp':
                target = job['root_position'] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                _require(item['expected'] == target and len(item['reported']) == len(target) and
                    all(_finite(x) for x in item['reported']) and value == max(abs(x-y) for x,y in zip(item['reported'],target)),
                    'clamp metric changed.')
            elif kind == 'weight_wrench':
                _require(len(item['position']) == 3 and all(_finite(x) for x in item['position']), 'invalid load position.')
                force = [WEIGHT[5]/9.81*g for g in job['gravity']]
                moment = _cross(item['position'], force)
                _require(item['force'] == force and item['moment'] == moment and
                    value == max(_relative(item['reported_force'],force),_relative(item['reported_moment'],moment)),
                    'independent tip load/wrench changed.')
            elif kind == 'sensor_anchor':
                node = item['node']; _require(node['beam'] == 1 and node['t'] == -.22 and
                    node['jig_position'] == [0.,-.22,0.], 'sensor moved or relabelled.')
                reconstructed = dict(zip(NAMES,node['position']))
                _require(item['reconstructed'] == reconstructed and set(item['reported']) == set(NAMES), 'sensor mapping changed.')
                metrics = [_relative(list(item['reported'].values()),[reconstructed[k] for k in item['reported']]),
                           _relative(item['body_position'],node['position']),_relative(item['earth_position'],node['position'])]
                _require(value == max(metrics), 'anchor/body/GPS metric changed.')
            elif kind == 'parity':
                a,b = item['reported'],item['restored']
                _require(set(a) == set(b) == set(NAMES), 'restored channels incomplete.')
                channels = {name:_relative([a[name]],[b[name]]) for name in NAMES}
                _require(item['channels'] == channels and value == max(channels.values()), 'restored metric changed.')
            passed = value <= gate
        _require(isinstance(item.get('passed'),bool) and item['passed'] is bool(passed), 'physical boolean changed.')
    return all(item['passed'] for item in checks)


def validate_result_contract(job, result):
    if job.get('comparison_scope')=='st1-mechanics':
        import isae_suite_st1_mechanics as mechanics
        return mechanics.validate_result_contract(job,result)
    contract = reference_contract(job); checks = result.get('reference_checks',[])
    _require(result.get('complete_family_reproduction') is not True and
             result.get('historical_settings_recovered') is not True,
             'conditional native scope cannot claim full historical reproduction.')
    names = [item.get('name') for item in checks]
    _require(len(names) == len(set(names)) and set(names) <= set(contract), 'duplicate or unknown result channel.')
    for item in checks:
        _require(all(item.get(k) == v for k,v in contract[item['name']].items()) and item.get('comparison') == '<=',
                 'saved reference metadata changed.')
    if job['execution_route'] == 'unsupported':
        _require(result.get('status') != 'computed' and result.get('numerical_pass') is not True and
            result.get('reference_match') is not True and result.get('physical_calls',0) == 0 and
            result.get('operations') == job['expected_operations'] and all(
                item.get('predicted') is None and item.get('passed') is False for item in checks), 'blocked scope claims physics.')
        if result.get('status') == 'unsupported':
            _require(len(checks) == len(contract) and result.get('source_pins_unchanged') is True, 'incomplete blocked record.')
    elif result.get('status') == 'computed':
        _require(result.get('numerical_pass') is True and result.get('source_pins_unchanged') is True and
            result.get('kernel_pins_unchanged') is True and result.get('physical_calls') == 2 and
            result.get('operations') == job['expected_operations'] and validate_physical_checks(job,result.get('physical_checks',[])),
            'computed position lacks full physical evidence.')
        evidence = {item['name']:item for item in result['physical_checks']}
        values = evidence['independent_sensor_anchor']['reported']
        wrench = evidence['independent_tip_weight_wrench']
        _require(evidence['force_balance']['applied'] == wrench['reported_force'] and
                 evidence['moment_balance']['applied'] == wrench['reported_moment'],
                 'balance evidence differs from the independently checked tip wrench.')
        _require(values == evidence['restored_position_parity']['reported'] and len(checks) == 3 and
            all(item['predicted'] == values[item['name']] for item in checks), 'predictions detached from checked position.')
        for item in checks:
            error = abs(item['predicted']-item['expected'])
            passed = abs(Decimal(str(item['predicted']))-Decimal(item['exact_decimal_expected'])) <= Decimal(item['exact_decimal_tolerance'])
            _require(item['abs_error'] == error and item['passed'] is passed, 'printed comparison changed.')
        _require(result.get('reference_match') is all(item['passed'] for item in checks), 'full-state match changed.')
    return True


def _stable(pins):
    try:
        return all(_pin(item['path']) == item for item in pins)
    except OSError:
        return False


def _execute(root, job, stage):
    import numpy as np
    import openswing
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.source_discrete import SourceSectionNetwork
    from openswing.equilibrium_state import identity, matching_identity, warm_start_recipe, restore
    from openswing.network import network_snapshot
    from openswing.point_objects import active_weights
    _require(Path(openswing.__file__).resolve().parent == root/'openswing', 'worker imported another checkout.')
    raw = Path(job['source']).read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == job['literal_model_sha256'], 'literal source changed.')
    request = dict(action='solve', mode='structural', source=raw.decode(), panels=job['panels'],
        numerics=job['settings'], gravity=job['gravity'], loads=[], tolerance=GATES['residual'],
        continuation_steps=job['continuation_steps'])
    _write(stage/'request.json', request)
    model = parse_asw(raw.decode(), beam_interpolation=POLICY['beam_interpolation'])
    operations = dict(cold_solves=1, fresh_residuals=0, retries=0); _write(stage/'operations.json', operations)
    result = dispatch(request); _write(stage/'result.json', result)
    recipe = warm_start_recipe(model,job['panels'],result['equilibrium_state'])
    network = SourceSectionNetwork(model,job['panels'],None,job['gravity'],(),mesh_recipe=recipe,
        allow_signed_point_weights=True,allow_signed_distributed_weights=True)
    _require(matching_identity(result['equilibrium_state']['identity'],identity(network)), 'restored identity changed.')
    checks = []
    def exact(name,actual,expected):
        checks.append(dict(name=name,actual=actual,expected=expected,passed=actual==expected))
    def metric(name,value,**evidence):
        gate = GATES[PHYSICAL_CHECK_SPECS[name]['gate']]
        checks.append(dict(name=name,metric=value,gate=gate,passed=bool(value<=gate),**evidence))
    exact('same_operator_identity',identity(network),result['equilibrium_state']['identity'])
    state = restore(network,result['equilibrium_state']);exact('restore_without_evaluation',network.nfev,0)
    operations['fresh_residuals'] = 1;_write(stage/'operations.json',operations)
    residual,data = network.residual(state,detail=True);fresh = network_snapshot(network,residual,data)
    _write(stage/'restored-result.json',fresh)
    expected = _expectations(job)
    exact('one_restored_residual',network.nfev,1);exact('converged',result['converged'],True)
    exact('no_parser_diagnostics',list(model.diagnostics),[])
    metric('fresh_full_residual',float(np.max(abs(residual))))
    exact('literal_source_hash',hashlib.sha256(raw).hexdigest(),expected['literal_source_hash'])
    exact('literal_reference',model.reference.tolist(),REFERENCE)
    exact('literal_weight_rows',[row.tolist() for row in model.records['weight']],[WEIGHT])
    exact('literal_sensor_rows',[row.tolist() for row in model.records['sensor']],[SENSOR])
    exact('active_tip_weight',len(active_weights(model)),1)
    exact('source_policy',dict(numerics=result.get('numerics'),operator=result['structural_operator'],
        launch='launch' in result['equilibrium_state'],structural_only=result.get('structural_only')),expected['source_policy'])
    def setup(packet):
        return dict(condition=network.condition,gravity=packet['gravity_body'],engines=len(network.engines),
            loads=len(network.loads),struts=len(packet['struts']),hinges=len(packet['hinges']),sensors=len(packet['sensors']))
    exact('cold_structural_setup',setup(result),expected['cold_structural_setup'])
    exact('restored_structural_setup',setup(fresh),expected['restored_structural_setup'])
    exact('mesh_panel_setting',dict(panels=result['mesh_discretization']['settings'],nodes=network.nn,elements=network.ne),expected['mesh_panel_setting'])
    exact('mandatory_stations_present',{str(t):t in network.station_nodes[1][0] for t in MANDATORY},expected['mandatory_stations_present'])
    for name in ('force','moment'):
        a,b = result['applied_'+name],result['support_'+name]
        metric(name+'_balance',math.hypot(*(x+y for x,y in zip(a,b)))/max(1.,math.hypot(*a)+math.hypot(*b)),applied=a,support=b)
    clamps = [c['a'] for c in network.constraints if c['kind']=='ground']
    exact('root_clamp_count',len(clamps),1);_require(len(clamps)==1,'root clamp missing/duplicated.')
    position,frame = data['r'][clamps[0]].tolist(),data['Q'][clamps[0]].ravel().tolist()
    eye = [1.,0.,0.,0.,1.,0.,0.,0.,1.]
    metric('root_clamp_position',max(abs(a-b) for a,b in zip(position,job['root_position'])),reported=position,expected=job['root_position'])
    metric('root_clamp_frame',max(abs(a-b) for a,b in zip(frame,eye)),reported=frame,expected=eye)
    tip = next(node for node in result['nodes'] if node['beam']==1 and node['t']==-.28)
    force = [WEIGHT[5]/9.81*g for g in job['gravity']];moment = _cross(tip['position'],force)
    metric('independent_tip_weight_wrench',max(_relative(result['applied_force'],force),_relative(result['applied_moment'],moment)),
        position=tip['position'],force=force,moment=moment,reported_force=result['applied_force'],reported_moment=result['applied_moment'])
    sensor = result['sensors'][0];restored_sensor=fresh['sensors'][0]
    _require(sensor['index']==restored_sensor['index']==1 and sensor['beam']==restored_sensor['beam']==1 and
             sensor['t']==restored_sensor['t']==-.22, 'sensor identity changed.')
    exact('sensor_frame_scope',dict(axes_available=sensor['axes_available'],v_axis_available=sensor['v_axis_available'],
        reason_present=isinstance(sensor['axes_unavailable_reason'],str) and bool(sensor['axes_unavailable_reason']),
        null_fields={name:sensor[name] is None for name in NULL_SENSOR_FIELDS},heading_finite=_finite(sensor['heading']),
        elevation_finite=_finite(sensor['elevation']),section_force_finite=all(_finite(x) for x in sensor['force_local']),
        section_moment_finite=all(_finite(x) for x in sensor['moment_local'])),expected['sensor_frame_scope'])
    values = dict(zip(NAMES,sensor['anchor_position_body']));restored_values=dict(zip(NAMES,restored_sensor['anchor_position_body']))
    node = next(node for node in fresh['nodes'] if node['beam']==1 and node['t']==-.22)
    reconstructed = dict(zip(NAMES,node['position']))
    metric('independent_sensor_anchor',max(_relative(list(values.values()),node['position']),
        _relative(sensor['position_body'],node['position']),_relative(sensor['position_earth'],node['position'])),
        node=node,reported=values,reconstructed=reconstructed,body_position=sensor['position_body'],earth_position=sensor['position_earth'])
    exact('finite_positions',{name:_finite(value) for name,value in values.items()},expected['finite_positions'])
    channels = {name:_relative([values[name]],[restored_values[name]]) for name in NAMES}
    metric('restored_position_parity',max(channels.values()),reported=values,restored=restored_values,channels=channels)
    validate_physical_checks(job,checks);_write(stage/'physical-checks.json',checks)
    return values,checks


def run(root, job):
    if job.get('comparison_scope')=='st1-mechanics':
        import isae_suite_st1_mechanics as mechanics
        return mechanics.run(root,job)
    root = Path(root).resolve()
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root,job)
    verify_reference_sources(root,job)
    stage = Path(tempfile.mkdtemp(prefix='openswing-isae-suite-st1-'+job['id']+'-'));_write(stage/'job.json',job)
    values,physical,error = {},[],None
    try:
        values,physical = _execute(root,job,stage)
    except Exception as exc:
        error = dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());_write(stage/'exception.json',error)
    operations = json.loads((stage/'operations.json').read_text()) if (stage/'operations.json').exists() else dict(cold_solves=0,fresh_residuals=0,retries=0)
    checks = _checks(job,values,'Worker failed or output unavailable.');source_stable=_stable(job['source_pins'])
    kernel_stable = _stable(job['kernel_pins']) and {p['path'] for p in job['kernel_pins']} == {str(p.resolve()) for p in (root/'openswing').glob('*.py')}
    numerical = bool(error is None and physical and validate_physical_checks(job,physical) and source_stable and
        kernel_stable and operations == job['expected_operations'] and all(c['predicted'] is not None for c in checks))
    result = dict(id=job['id'],case_id='ST-1',adapter='st1',status='computed' if numerical else 'numerical_failure',numerical_pass=numerical,
        reference_match=numerical and all(item['passed'] for item in checks),reference_checks=checks,physical_checks=physical,
        physical_calls=operations['cold_solves']+operations['fresh_residuals'],operations=operations,source_pins_unchanged=source_stable,
        kernel_pins_unchanged=kernel_stable,error=error,artifact_directory=str(stage),artifact_files=[_pin(p) for p in sorted(stage.iterdir()) if p.is_file()],
        historical_settings_recovered=False,complete_family_reproduction=False,unknown_setup=job['unknown_setup'],
        qualifications=job['qualifications'],reference_scope=job['reference_scope'])
    validate_result_contract(job,result);_write(stage/'adapter-result.json',result)
    return result


def mesh_diagnostics(jobs,results):
    if any(j.get('comparison_scope')=='st1-mechanics' for j in jobs):
        import isae_suite_st1_mechanics as mechanics
        return mechanics.mesh_diagnostics(jobs,results)
    pair = sorted([j for j in jobs if j.get('adapter')=='st1' and j.get('target_kind')=='native_position'],key=lambda j:j['nominal'])
    if not pair:
        return []
    _require(len(pair)<=2 and len({j['nominal'] for j in pair})==len(pair),'duplicate prospective mesh.')
    packets = [results.get(j['id'],{}) for j in pair]
    row = dict(coordinate_id=pair[0]['coordinate_id'],jobs=[j['id'] for j in pair],passed=None,acceptance_gate=None,
        scope='Prospective100/200 interval position sensitivity; no historical-grid or full-family pass.')
    if len(pair)!=2 or any(p.get('status')!='computed' for p in packets):
        row.update(status='UNAVAILABLE',channels={})
    else:
        values = [{c['name']:c['predicted'] for c in p['reference_checks']} for p in packets]
        channels = {}
        for name in NAMES:
            a,b = (v[name] for v in values);delta=abs(b-a)
            channels[name]=dict(coarse=a,fine=b,abs_change=delta,relative_change=delta/abs(b) if b else (0. if delta==0 else None))
        row.update(status='COMPARED',channels=channels)
    return [row]
