"""Literal AE1 sensor sweeps with conditional mounted setup and blocked starts.

Planning and source validation use the standard library only. A worker retains
the complete original input and makes one cold solve and one fresh residual.
The two initial stack points have unknown operating settings and never execute.
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

from scripts.isae_suite_ap1 import reconstruct_wrenches


REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
READINESS = 'docs/validation/isae-suite-readiness/ae1-adapter-readiness.json'
READINESS_SHA256 = '2f5be7e1aabb4a9b933bee2f737291fde29e739059a7faa5adeb0e46daeee4c8'
FAMILY = '4 - Aeroelasticity/AE - Aeroelastic Cases/AE-1-S Pazy Wing - Steady Deflection'
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')
GATES = dict(residual=1e-8, relative_balance=1e-7, restored_parity=2e-10, clamp=1e-10)
NOMINALS = (40, 80)
FROZEN_SCOPE = 'ae1-frozen-influences'
CHANNELS = (
    ('sensor1_RX_earth_m', 1, 'position_earth', 0, 'm'),
    ('sensor1_RZ_earth_m', 1, 'position_earth', 2, 'm'),
    ('sensor2_RX_earth_m', 2, 'position_earth', 0, 'm'),
    ('sensor2_RZ_earth_m', 2, 'position_earth', 2, 'm'),
    ('sensor3_RZ_earth_m', 3, 'position_earth', 2, 'm'),
    ('sensor3_Theta_elevation_deg', 3, 'elevation', None, 'deg'))
NAMES = tuple(row[0] for row in CHANNELS)
SENSOR_ROWS = [[i, 1, .55, x, .55, 0., 1., 0., 0., 0., 0., 1.]
               for i, x in ((1, -.05), (2, .05), (3, 0.))]
WEIGHT_ROWS = [[1., .558, .05, .558, 0.] + [0.]*12 for _ in range(2)]
UNKNOWN_SETUP = [
    'Initial stack speed and incidence; first + precedes !A/!V and no !V0 is present.',
    'Alpha5 startup constraints/autoload state; unlike alpha7 it does not select anchored defaults.',
    'Historical atmosphere/IAS-to-TAS, PG, frame pose, gravity and control startup.',
    'Original K/F/core, node arrays, binary/build and nonlinear continuation/branch history.']
QUALIFICATIONS = [
    'All original input bytes and both null Weight rows are retained. Exact-zero point-object elimination is current analysis semantics, not recovered legacy input-validation behavior.',
    'Both scripts request NODE I40. Current 40/80 nominal cosine intervals are a prospectively declared refinement pair, not recovered historical 40-node arrays. The .52 property jump remains mandatory.',
    'Each positive IAS command is conditionally treated as TAS at literal rhoSL=1.23, PG Mach0, beta0, identity pose, gravity[0,0,-9.81], zero rates/accelerations and ground imageG1 normal[0,1,0].',
    'Mounted constraints, updated influences (freeze_influences=False), core ratio.25, pointwise circulation and current cold continuation are declared current choices, not recovered historical startup.',
    'Keep literal EIcc4.4, GJ6.5/16.9, EInn3300, EIcn-.12, EA9.6e6, rigid shear, section/CG offsets and mass. No properties, coordinates or tolerances are fitted.',
    'The six native outputs are absolute Earth positions and sensor3 elevation. Do not subtract initial sag, relocate sensors, swap axes or substitute local twist.',
    'The initial stack point in each export remains blocked on both grids despite finite targets. A zero-speed or known-alpha initial condition is not inferred.',
    'All printed half-last-place gates remain unchanged; experiments and old derived-input results are not acceptance targets.',
    'Mesh changes are descriptive. Numerical success or selected output agreement does not establish historical setup or complete family reproduction.']
PHYSICAL_CHECK_SPECS = {
    **{name: dict(kind='exact') for name in (
        'same_operator_identity', 'restore_without_evaluation', 'one_restored_residual', 'converged',
        'cold_operating_setup', 'restored_operating_setup', 'restored_condition',
        'source_policy', 'literal_source_hash', 'literal_sensor_rows', 'literal_weight_rows',
        'inactive_null_weights', 'no_engines_or_extra_loads', 'node_element_counts', 'property_jump_present',
        'gravity_body', 'root_clamp_count', 'finite_sensor_outputs')},
    'fresh_full_residual': dict(kind='metric', gate='residual'),
    **{name: dict(kind='balance', gate='relative_balance') for name in ('force_balance', 'moment_balance')},
    **{name: dict(kind='clamp', gate='clamp') for name in ('root_clamp_position', 'root_clamp_frame')},
    **{'independent_'+name: dict(kind='vector', gate='restored_parity') for name in (
        'distributed_aero_force', 'distributed_aero_moment', 'force', 'moment')},
    'independent_sensor_geometry': dict(kind='sensors', gate='restored_parity'),
    'restored_sensor_parity': dict(kind='parity', gate='restored_parity')}
REQUIRED_PHYSICAL_CHECKS = tuple(PHYSICAL_CHECK_SPECS)


def _require(ok, message):
    if not ok:
        raise ValueError('AE1 '+message)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _decimal(token):
    value = Decimal(token.replace('D', 'E').replace('d', 'e'))
    _require(value.is_finite(), 'nonfinite native target.')
    half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    return float(value), float(half), str(value), str(half)


def _context(root):
    root = Path(root).resolve()
    readiness = root/READINESS; manifest_path = root/'.reference/isae-validation/manifest.json'
    _require(_pin(readiness)['sha256'] == READINESS_SHA256, 'source-readiness record changed.')
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256, 'upstream manifest changed.')
    evidence = json.loads(readiness.read_text()); manifest = json.loads(manifest_path.read_text())
    _require(manifest['revision'] == REVISION, 'upstream revision changed.')
    base = root/'.reference/isae-validation'/REVISION/FAMILY
    pins = [_pin(readiness), _pin(manifest_path), _pin(Path(__file__)), _pin(root/'scripts/isae_suite_ap1.py')]
    for name in ('Pazy_wing.asw', 'alpha5.sh', 'alpha7.sh', 'aswing_alpha_05.txt',
                 'aswing_alpha_07.txt', 'Static_Aeroelastic.m', 'README.txt'):
        actual = _pin(base/name); original = manifest['files'][FAMILY+'/'+name]
        _require(all(actual[key] == original[key] for key in ('bytes', 'sha256')), 'original source changed: '+name)
        pins.append(actual)
    _require(_pin(base/'Pazy_wing.asw')['sha256'] == evidence['model']['sha256'], 'literal model pairing changed.')
    _require(evidence['counts']['archived_rows'] == 100 and evidence['counts']['finite_archived_scalars'] == 600,
             'native reference denominator changed.')
    for series in evidence['series']:
        alpha = series['alpha']; commands = (base/f'alpha{alpha}.sh').read_text().splitlines()
        output = (base/f'aswing_alpha_{alpha:02d}.txt').read_text().splitlines()
        _require('aswing Pazy_wing <<EOF' in commands[1] and commands[3].strip() == 'I 40' and
                 f'aswing_alpha_{alpha:02d}.txt' in commands, 'literal driver model/output or NODE request changed.')
        positive = [(i+1, line.split()[1]) for i, line in enumerate(commands) if re.fullmatch(r'\s*!V\s+\d+\s*', line)]
        _require([int(token) for _, token in positive] == list(range(1, (56 if alpha == 5 else 42)+1)),
                 'positive IAS sequence changed.')
        _require(commands.index('+') < next(i for i, line in enumerate(commands) if line.strip().startswith('!A')),
                 'unknown initial operating state was replaced.')
        selections = [line.split() for line in commands if re.fullmatch(r'\s*(?:13|15|17)\s+[123]\s*', line)]
        _require(selections == [['17','3'],['15','3'],['15','1'],['15','2'],['13','1'],['13','2']],
                 'native sensor selection changed.')
        _require(len(output) == len(series['rows'])+3 and len(series['rows']) == len(positive)+1 and
                 output[2].split() == ['#','i','t','RX','pos[','1]','RZ','pos[','1]','RX','pos[','2]',
                                      'RZ','pos[','2]','RZ','pos[','3]','Theta[','3]'], 'native row/header scope changed.')
        for ordinal, row in enumerate(series['rows'], 1):
            tokens = output[ordinal+2].split()
            _require(row['file_line'] == ordinal+3 and row['raw_line'] == output[ordinal+2] and
                     row['raw_tokens'] == tokens and len(tokens) == 8 and int(tokens[0]) == ordinal,
                     'original row or stack ordering changed.')
            _require((row['command'] is None and row['alpha_deg'] is None) if ordinal == 1 else
                     (row['command']['line'], row['command']['token']) == positive[ordinal-2] and row['alpha_deg'] == alpha,
                     'operating command pairing changed.')
            for column, (spec, observation) in enumerate(zip(CHANNELS, row['observations'], strict=True), 3):
                name, sensor, field, component, unit = spec
                expected, tolerance, _, _ = _decimal(tokens[column-1])
                _require(observation['name'] == name and observation['sensor'] == sensor and
                         observation['snapshot_field'] == field and observation['component'] == component and
                         observation['unit'] == unit and observation['file_column_1based'] == column and
                         observation['token'] == tokens[column-1] and observation['expected'] == expected and
                         float(Decimal(observation['half_last_place'])) == tolerance, 'native sensor target mapping changed.')
    return root, base, evidence, pins


def _jobs(root, base, evidence, pins, only=None, *, frozen=False):
    kernels = None; model = base/'Pazy_wing.asw'; model_pin = _pin(model)
    for series in evidence['series']:
        alpha = series['alpha']
        for ordinal, row in enumerate(series['rows'], 1):
            base_coordinate = f'a{alpha:02d}-row{ordinal:03d}'
            coordinate = base_coordinate+('-frozen' if frozen else '')
            for nominal in NOMINALS:
                base_identifier = f'AE-1-{base_coordinate}-m{nominal}'
                identifier = base_identifier+('-frozen' if frozen else '')
                if only is not None and only != identifier:
                    continue
                blocked = row['command'] is None
                if kernels is None:
                    kernels = [_pin(p) for p in sorted((root/'openswing').glob('*.py'))]
                observations = []
                for column, spec in enumerate(CHANNELS, 3):
                    name, sensor, field, component, unit = spec
                    token = row['raw_tokens'][column-1]
                    expected, tolerance, exact, half = _decimal(token)
                    observations.append(dict(name=name, expected=expected, tolerance=tolerance, expected_token=token,
                        exact_decimal_expected=exact, exact_decimal_tolerance=half, source_line=row['file_line'],
                        source_column_1based=column, sensor=sensor, snapshot_field=field, component=component, units=unit,
                        precision_scope='Native absolute sensor output half-last-place; no baseline subtraction.'))
                condition = None if blocked else dict(speed=float(row['command']['value']), alpha=float(alpha), beta=0.,
                    density=1.23, mach=0., controls={}, powers={}, attitude=[0.,0.,0.], position_earth=[0.,0.,0.],
                    rates=[0.,0.,0.], acceleration=[0.,0.,0.], angular_acceleration=[0.,0.,0.],
                    ground_effect=1, ground_normal=[0.,1.,0.], freeze_influences=frozen, wake_core_ratio=.25,
                    circulation_modes={'1':0})
                job = dict(id=identifier, case_id='AE-1', adapter='ae1', coordinate_id=coordinate,
                    target_kind='initial_operating_unknown' if blocked else 'paired_sensor',
                    execution_route='unsupported' if blocked else 'worker', model_path=model.relative_to(root).as_posix(),
                    source=str(model), literal_model_sha256=model_pin['sha256'],
                    driver_path=(base/f'alpha{alpha}.sh').relative_to(root).as_posix(),
                    table_path=(base/f'aswing_alpha_{alpha:02d}.txt').relative_to(root).as_posix(),
                    reference_rows=[dict(row_number=ordinal, line_number=row['file_line'], raw_line=row['raw_line'],
                                         tokens=list(row['raw_tokens']), command=deepcopy(row['command']), alpha_deg=row['alpha_deg'])],
                    observations=observations, expected_outputs=6, nominal=nominal, mesh=f'm{nominal}',
                    panels=dict(default=nominal, beams={'1':dict(count=nominal, spacing='cosine')}),
                    expected_elements=nominal+1, expected_nodes=nominal+2, mandatory_property_break=.52,
                    source_node_request=40, mesh_scope='Current nominal intervals40/80; historical NODE I40 arrays are not recovered.',
                    settings=deepcopy(POLICY), condition=condition, gravity=[0.,0.,-9.81],
                    literal_sensor_rows=deepcopy(SENSOR_ROWS), literal_weight_rows=deepcopy(WEIGHT_ROWS),
                    source_pins=pins, kernel_pins=kernels, numerical_gates=deepcopy(GATES),
                    expected_operations=dict(cold_solves=0 if blocked else 1, fresh_residuals=0 if blocked else 1, retries=0),
                    suggested_cap_seconds=120, original_file_modified=False, historical_settings_recovered=False,
                    unknown_setup=list(UNKNOWN_SETUP), qualifications=list(QUALIFICATIONS), complete_family_reproduction=False,
                    reference_scope='All six native absolute sensor outputs for this original row under a conditional mounted reconstruction.')
                if frozen:
                    job.update(comparison_scope=FROZEN_SCOPE, base_static_job_id=base_identifier,
                        reference_scope='All six native absolute sensor outputs under the explicitly selected frozen-influence alternative; historical K/F remains unknown.')
                    job['qualifications'][3] = ('Mounted constraints, frozen jig-geometry influence matrices (freeze_influences=True), core ratio.25, pointwise circulation and current cold continuation are declared choices. This exercises the documented OPER K/F fast option; the original scripts do not select K/F and no historical .set file is available.')
                    job['qualifications'].append('This optional scope preserves the updated-influence baseline. Its outputs, errors and unknown initial rows are accounted separately; agreement does not identify the historical flag.')
                if blocked:
                    job.update(blocker_code='INITIAL_OPERATING_STATE_UNIDENTIFIED',
                        unsupported_reason='Initial stack point precedes the first alpha/IAS commands; its speed, incidence and startup constraints are not uniquely recovered.')
                yield job


def plan(root, *, comparison_scopes=()):
    _require(len(set(comparison_scopes)) == len(comparison_scopes) and
             all(scope == FROZEN_SCOPE for scope in comparison_scopes),
             'Provide unique reviewed AE1 comparison scopes.')
    root, base, evidence, pins = _context(root)
    jobs = list(_jobs(root, base, evidence, pins))
    _require(len(jobs) == 200 and sum(job['expected_outputs'] for job in jobs) == 1200 and
             sum(job['execution_route'] == 'worker' for job in jobs) == 196, 'complete AE1 scope changed.')
    if FROZEN_SCOPE in comparison_scopes:
        jobs.extend(_jobs(root, base, evidence, pins, frozen=True))
    return jobs


def verify_reference_sources(root, job):
    root, base, evidence, pins = _context(root)
    _require(job.get('comparison_scope') in (None, FROZEN_SCOPE), 'Unknown AE1 comparison scope.')
    canonical = list(_jobs(root, base, evidence, pins, only=job.get('id'),
                           frozen=job.get('comparison_scope') == FROZEN_SCOPE))
    _require(len(canonical) == 1 and all(job.get(key) == value for key, value in canonical[0].items()),
             'job differs from original model/driver/output, declared setup or current numerical code.')
    return True


def reference_contract(job):
    scope = job.get('comparison_scope')
    _require(scope in (None, FROZEN_SCOPE), 'Unknown AE1 comparison scope.')
    if scope == FROZEN_SCOPE:
        _require(isinstance(job.get('base_static_job_id'), str) and
                 job.get('id') == job['base_static_job_id']+'-frozen' and
                 job.get('coordinate_id', '').endswith('-frozen'),
                 'Frozen AE1 comparison requires its own job and mesh-pair identity.')
    if job.get('condition') is not None:
        _require(job['condition'].get('freeze_influences') is (scope == FROZEN_SCOPE),
                 'AE1 influence flag differs from its declared comparison scope.')
    _require(job.get('case_id') == 'AE-1' and job.get('adapter') == 'ae1' and job.get('expected_outputs') == 6 and
             job.get('settings') == POLICY and job.get('numerical_gates') == GATES and job.get('nominal') in NOMINALS,
             'invalid declared family, policy, grid or target scope.')
    _require([item['name'] for item in job['observations']] == list(NAMES), 'six sensor channels changed.')
    row, = job['reference_rows']
    for column, (spec, item) in enumerate(zip(CHANNELS, job['observations'], strict=True), 3):
        expected, tolerance, exact, half = _decimal(row['tokens'][column-1])
        name, sensor, field, component, unit = spec
        _require(item['expected'] == expected and item['tolerance'] == tolerance and item['expected_token'] == row['tokens'][column-1] and
                 item['exact_decimal_expected'] == exact and item['exact_decimal_tolerance'] == half and
                 item['source_line'] == row['line_number'] and item['source_column_1based'] == column and
                 (item['sensor'], item['snapshot_field'], item['component'], item['units']) == (sensor, field, component, unit),
                 'original precision or sensor mapping changed.')
    return {item['name']:{key:value for key,value in item.items() if key != 'name'} for item in job['observations']}


def _checks(job, values, reason=None):
    rows = []
    for name, reference in reference_contract(job).items():
        value = values.get(name); available = _finite(value)
        error = abs(value-reference['expected']) if available else None
        rows.append(dict(name=name, **reference, predicted=value if available else None, abs_error=error,
                         comparison='<=', passed=bool(available and error <= reference['tolerance']),
                         unavailable_reason=None if available else reason))
    return rows


def validate_blocked(root, job):
    _require(job['execution_route'] == 'unsupported', 'positive sensor row requires a worker.')
    verify_reference_sources(root, job)
    return dict(id=job['id'], case_id='AE-1', adapter='ae1', status='unsupported', numerical_pass=False,
        reference_match=False, reference_checks=_checks(job, {}, job['unsupported_reason']), physical_checks=[],
        operations=dict(cold_solves=0, fresh_residuals=0, retries=0), physical_calls=0, production_imports=0,
        source_pins_unchanged=True, kernel_pins_unchanged=True, blocker_code=job['blocker_code'],
        unsupported_reason=job['unsupported_reason'], complete_family_reproduction=False)


def sensor_values(sensors):
    by_index = {sensor['index']:sensor for sensor in sensors}
    _require(len(sensors) == len(by_index) == 3 and set(by_index) == {1,2,3}, 'missing or duplicate original sensors.')
    return {name:(by_index[index][field] if component is None else by_index[index][field][component])
            for name,index,field,component,_ in CHANNELS}


def reconstruct_sensors(nodes, sensor_rows=SENSOR_ROWS):
    """Independent rigid-pylon positions/axes at identity Earth pose; no flow query."""
    tips = [node for node in nodes if node['beam'] == 1 and node['t'] == .55]
    _require(len(tips) == 1 and sensor_rows == SENSOR_ROWS, 'literal tip/sensor identity changed.')
    node = tips[0]; rotation = node['rotation']; position = node['position']; jig = node['jig_position']
    _require(len(rotation) == 3 and all(len(row) == 3 for row in rotation) and len(position) == len(jig) == 3 and
             all(_finite(value) for value in position+jig+sum(rotation, [])), 'invalid tip geometry evidence.')
    sensors = []
    for row in sensor_rows:
        offset = [row[i+3]-jig[i] for i in range(3)]
        point = [position[i]+sum(rotation[i][j]*offset[j] for j in range(3)) for i in range(3)]
        axis = [rotation[i][0] for i in range(3)]
        sensors.append(dict(index=int(row[0]), position_earth=point, axes_earth=deepcopy(rotation),
                            elevation=math.degrees(math.atan2(-axis[2], math.hypot(axis[0], axis[1])))))
    return sensors


def _relative(a, b):
    if not isinstance(a, list): a, b = [a], [b]
    _require(isinstance(b, list) and len(a) == len(b) and len(a) > 0 and all(_finite(x) for x in a+b),
             'invalid independent metric evidence.')
    return max(abs(x-y) for x,y in zip(a,b))/(1.+max(map(abs, a+b)))


def _sensor_metric(reported, reconstructed):
    by_index = {row['index']:row for row in reconstructed}
    _require(len(reported) == 3 and {row['index'] for row in reported} == set(by_index) == {1,2,3},
             'sensor geometry evidence incomplete.')
    metrics = []
    for row in reported:
        other = by_index[row['index']]
        metrics += [_relative(row['position_earth'], other['position_earth']),
                    _relative(sum(row['axes_earth'], []), sum(other['axes_earth'], [])),
                    _relative(row['elevation'], other['elevation'])]
    return max(metrics)


def _expectations(job):
    frozen = job.get('comparison_scope') == FROZEN_SCOPE
    setup = dict(ground_flag=1, normal_earth=[0.,1.,0.], ground_offset=0.,
        position_earth=[0.,0.,0.], attitude=[0.,0.,0.], frozen=frozen,
        wind_angles=[0.,0.] if frozen else [job['condition']['alpha'],0.], pg_mach=0., core_ratio=.25,
        density=1.23, dynamic_pressure=.5*1.23*job['condition']['speed']**2, gravity_body=[0.,0.,-9.81])
    return dict(restore_without_evaluation=0, one_restored_residual=1, converged=True,
        cold_operating_setup=setup, restored_operating_setup=setup, restored_condition=job['condition'],
        source_policy=dict(numerics=POLICY, operator=POLICY['structural_operator'], launch=False),
        literal_source_hash=job['literal_model_sha256'], literal_sensor_rows=SENSOR_ROWS, literal_weight_rows=WEIGHT_ROWS,
        inactive_null_weights=0, no_engines_or_extra_loads=dict(engines=0, loads=0, struts=0, hinges=0),
        node_element_counts=[job['expected_nodes'], job['expected_elements']], property_jump_present=True,
        gravity_body=[0.,0.,-9.81], root_clamp_count=1, finite_sensor_outputs={name:True for name in NAMES})


def _setup_evidence(result):
    ground, influences = result['ground_plane'], result['aerodynamic_influences']
    return dict(ground_flag=ground['flag'], normal_earth=ground['normal_earth'], ground_offset=ground['offset'],
        position_earth=ground['position_earth'], attitude=ground['attitude'], frozen=influences['frozen'],
        wind_angles=influences['wind_angles'], pg_mach=influences['pg_mach'], core_ratio=result['wake_core']['ratio'],
        density=result['atmosphere']['density'], dynamic_pressure=result['atmosphere']['dynamic_pressure'],
        gravity_body=result['gravity_body'])


def validate_physical_checks(job, checks):
    _require(job['numerical_gates'] == GATES, 'physical gates changed.')
    names = [item.get('name') for item in checks]
    _require(len(names) == len(set(names)) == len(REQUIRED_PHYSICAL_CHECKS) and set(names) == set(REQUIRED_PHYSICAL_CHECKS),
             'physical check set incomplete or duplicated.')
    for item in checks:
        name = item['name']; spec = PHYSICAL_CHECK_SPECS[name]
        if spec['kind'] == 'exact':
            _require('actual' in item and 'expected' in item, 'missing exact physical evidence.')
            if name in _expectations(job):
                _require(item['expected'] == _expectations(job)[name], 'physical expectation changed.')
            passed = item['actual'] == item['expected']
        else:
            metric = item.get('metric'); gate = GATES[spec['gate']]
            _require(_finite(metric) and metric >= 0 and item.get('gate') == gate, 'invalid physical metric/gate.')
            if spec['kind'] == 'vector':
                _require(metric == _relative(item.get('reported'), item.get('reconstructed')), 'independent wrench metric changed.')
            elif spec['kind'] == 'balance':
                a, b = item.get('applied'), item.get('support')
                _require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 3 and all(_finite(x) for x in a+b),
                         'balance vector evidence missing.')
                value = math.hypot(*(x+y for x,y in zip(a,b)))/max(1., math.hypot(*a)+math.hypot(*b))
                _require(math.isclose(metric, value, rel_tol=2e-15, abs_tol=1e-30), 'balance metric changed.')
            elif spec['kind'] == 'clamp':
                a, b = item.get('reported'), item.get('expected')
                _require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and len(a) in (3,9) and
                         all(_finite(x) for x in a+b), 'clamp geometry evidence missing.')
                expected = [0.,0.,0.] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                _require(b == expected and metric == max(abs(x-y) for x,y in zip(a,b)), 'clamp metric/expectation changed.')
            elif spec['kind'] == 'sensors':
                reconstructed = reconstruct_sensors(item['tip_nodes'], job['literal_sensor_rows'])
                _require(item['reconstructed'] == reconstructed and metric == _sensor_metric(item['reported'], reconstructed),
                         'sensor positions/axes/elevation differ from independent tip geometry.')
            elif spec['kind'] == 'parity':
                a, b = item.get('reported'), item.get('restored')
                _require(isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b) == set(NAMES) and
                         all(_finite(x) for x in list(a.values())+list(b.values())), 'restored sensor outputs incomplete.')
                values = {name:_relative(a[name], b[name]) for name in NAMES}
                _require(item['channels'] == values and metric == max(values.values()), 'restored sensor metric changed.')
            passed = metric <= gate
        _require(isinstance(item.get('passed'), bool) and item['passed'] is bool(passed), 'physical pass flag changed.')
    return all(item['passed'] for item in checks)


def validate_result_contract(job, result):
    contract = reference_contract(job); checks = result.get('reference_checks', [])
    names = [item.get('name') for item in checks]
    _require(len(names) == len(set(names)) and set(names) <= set(contract), 'duplicated or unknown result channels.')
    for item in checks:
        _require(all(item.get(key) == value for key,value in contract[item['name']].items()) and
                 item.get('comparison', '<=') == '<=', 'saved reference metadata changed.')
    if job['execution_route'] == 'unsupported':
        _require(result.get('status') != 'computed' and result.get('numerical_pass') is not True and
                 result.get('numerical_passed') is not True and result.get('reference_match') is not True and
                 result.get('physical_calls', 0) == result.get('physical_solver_calls', 0) == 0 and
                 result.get('operations') == dict(cold_solves=0, fresh_residuals=0, retries=0) and
                 all(item.get('predicted') is None and item.get('passed') is False for item in checks),
                 'unknown initial state cannot claim a solve or output match.')
        if result.get('status') == 'unsupported':
            _require(len(checks) == 6 and result.get('source_pins_unchanged') is True, 'incomplete blocked target record.')
    elif result.get('status') == 'computed':
        _require(job['target_kind'] == 'paired_sensor' and result.get('numerical_pass') is True and
                 result.get('source_pins_unchanged') is True and result.get('kernel_pins_unchanged') is True and
                 result.get('physical_calls') == 2 and result.get('operations') == dict(cold_solves=1, fresh_residuals=1, retries=0) and
                 validate_physical_checks(job, result.get('physical_checks', [])), 'computed row lacks complete physical evidence.')
        physical = {item['name']:item for item in result['physical_checks']}
        values = sensor_values(physical['independent_sensor_geometry']['reported'])
        _require(values == physical['restored_sensor_parity']['reported'] and len(checks) == 6 and
                 all(item['predicted'] == values[item['name']] for item in checks), 'reference predictions differ from checked sensor geometry.')
        for item in checks:
            error = abs(item['predicted']-item['expected'])
            _require(item.get('abs_error') == error and item.get('passed') is (error <= item['tolerance']), 'saved precision boolean changed.')
        _require(result.get('reference_match') is all(item['passed'] for item in checks), 'whole-row reference flag changed.')
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
    from openswing.aero import FlightCondition
    from openswing.bridge import dispatch
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.equilibrium_state import identity, matching_identity, warm_start_recipe, restore
    from openswing.network import network_snapshot
    from openswing.point_objects import active_weights
    _require(Path(openswing.__file__).resolve().parent == root/'openswing', 'worker imported another checkout.')
    source = Path(job['source']).read_bytes()
    _require(hashlib.sha256(source).hexdigest() == job['literal_model_sha256'], 'literal input bytes changed.')
    request = dict(action='solve', mode='mounted', source=source.decode(), panels=job['panels'],
                   numerics=job['settings'], condition=job['condition'], gravity=job['gravity'])
    _write(stage/'request.json', request)
    model = parse_asw(request['source'], beam_interpolation=job['settings']['beam_interpolation'])
    condition = deepcopy(job['condition'])
    for key in ('powers', 'controls', 'circulation_modes'):
        condition[key] = {int(k):v for k,v in condition[key].items()}
    preflight = SourceCoupledNetwork(model, job['panels'], FlightCondition(**condition), job['gravity'])
    _require(preflight.ne == job['expected_elements'] and preflight.nn == job['expected_nodes'] and
             .52 in preflight.station_nodes[1][0] and len(model.records['weight']) == 2 and not active_weights(model),
             'literal null-object or mandatory-break mesh preflight failed.')
    _write(stage/'preflight.json', dict(nodes=preflight.nn, elements=preflight.ne,
        stations=preflight.station_nodes[1][0].tolist(), raw_weight_rows=[row.tolist() for row in model.records['weight']],
        active_weight_count=len(active_weights(model)), source_sha256=hashlib.sha256(source).hexdigest(), residuals=preflight.nfev))
    operations = dict(cold_solves=1, fresh_residuals=0, retries=0); _write(stage/'operations.json', operations)
    result = dispatch(request); _write(stage/'result.json', result)
    recipe = warm_start_recipe(model, job['panels'], result['equilibrium_state'])
    network = SourceCoupledNetwork(model, job['panels'], FlightCondition(**condition), job['gravity'], mesh_recipe=recipe)
    _require(matching_identity(result['equilibrium_state']['identity'], identity(network)), 'saved operator/mesh identity changed.')
    checks = []
    def exact(name, actual, expected):
        checks.append(dict(name=name, actual=actual, expected=expected, passed=actual == expected))
    def metric(name, value, **details):
        gate = GATES[PHYSICAL_CHECK_SPECS[name]['gate']]
        checks.append(dict(name=name, metric=value, gate=gate, passed=bool(value <= gate), **details))
    exact('same_operator_identity', identity(network), result['equilibrium_state']['identity'])
    state = restore(network, result['equilibrium_state']); exact('restore_without_evaluation', network.nfev, 0)
    operations['fresh_residuals'] = 1; _write(stage/'operations.json', operations)
    residual, data = network.residual(state, detail=True)
    fresh = network_snapshot(network, residual, data); _write(stage/'restored-result.json', fresh)
    exact('one_restored_residual', network.nfev, 1); exact('converged', result['converged'], True)
    metric('fresh_full_residual', float(np.max(np.abs(residual))))
    expected = _expectations(job)
    exact('cold_operating_setup', _setup_evidence(result), expected['cold_operating_setup'])
    exact('restored_operating_setup', _setup_evidence(fresh), expected['restored_operating_setup'])
    restored_condition = {key:getattr(network.condition, key) for key in job['condition']}
    for key in ('powers', 'controls', 'circulation_modes'):
        restored_condition[key] = {str(k):v for k,v in restored_condition[key].items()}
    exact('restored_condition', restored_condition, job['condition'])
    exact('source_policy', dict(numerics=result.get('numerics'), operator=result['structural_operator'],
                               launch='launch' in result['equilibrium_state']), expected['source_policy'])
    exact('literal_source_hash', hashlib.sha256(Path(job['source']).read_bytes()).hexdigest(), expected['literal_source_hash'])
    exact('literal_sensor_rows', [row.tolist() for row in model.records['sensor']], SENSOR_ROWS)
    exact('literal_weight_rows', [row.tolist() for row in model.records['weight']], WEIGHT_ROWS)
    exact('inactive_null_weights', len(active_weights(model)), 0)
    exact('no_engines_or_extra_loads', dict(engines=len(result['engines']), loads=len(network.loads),
        struts=len(result['struts']), hinges=len(result['hinges'])), expected['no_engines_or_extra_loads'])
    exact('node_element_counts', [network.nn, network.ne], expected['node_element_counts'])
    exact('property_jump_present', .52 in network.station_nodes[1][0], True)
    exact('gravity_body', result['gravity_body'], job['gravity'])
    for name in ('force', 'moment'):
        a, b = result['applied_'+name], result['support_'+name]
        value = math.hypot(*(x+y for x,y in zip(a,b)))/max(1., math.hypot(*a)+math.hypot(*b))
        metric(name+'_balance', value, applied=a, support=b)
    clamps = [c['a'] for c in network.constraints if c['kind'] == 'ground']
    exact('root_clamp_count', len(clamps), 1)
    _require(len(clamps) == 1, 'literal root clamp changed.')
    node = clamps[0]
    position, frame = data['r'][node].tolist(), data['Q'][node].ravel().tolist()
    metric('root_clamp_position', max(abs(x) for x in position), reported=position, expected=[0.,0.,0.])
    eye = [1.,0.,0.,0.,1.,0.,0.,0.,1.]
    metric('root_clamp_frame', max(abs(x-y) for x,y in zip(frame, eye)), reported=frame, expected=eye)
    reconstructed = reconstruct_wrenches(result, model.reference[1])
    for name in ('distributed_aero_force', 'distributed_aero_moment', 'force', 'moment'):
        metric('independent_'+name, _relative(result[name], reconstructed[name]),
               reported=result[name], reconstructed=reconstructed[name])
    sensors = [{key:sensor[key] for key in ('index', 'position_earth', 'axes_earth', 'elevation')} for sensor in result['sensors']]
    tips = [node for node in result['nodes'] if node['beam'] == 1 and node['t'] == .55]
    recovered = reconstruct_sensors(tips, job['literal_sensor_rows'])
    metric('independent_sensor_geometry', _sensor_metric(sensors, recovered), reported=sensors,
           reconstructed=recovered, tip_nodes=tips)
    values, restored = sensor_values(sensors), sensor_values(fresh['sensors'])
    exact('finite_sensor_outputs', {name:_finite(value) for name,value in values.items()}, expected['finite_sensor_outputs'])
    changes = {name:_relative(values[name], restored[name]) for name in NAMES}
    metric('restored_sensor_parity', max(changes.values()), channels=changes, reported=values, restored=restored)
    validate_physical_checks(job, checks); _write(stage/'physical-checks.json', checks)
    return values, checks


def run(root, job):
    root = Path(root).resolve()
    if job['execution_route'] == 'unsupported':
        return validate_blocked(root, job)
    verify_reference_sources(root, job)
    stage = Path(tempfile.mkdtemp(prefix='openswing-isae-suite-ae1-'+job['id']+'-'))
    _write(stage/'job.json', job)
    values, physical, error = {}, [], None
    try:
        values, physical = _execute(root, job, stage)
    except Exception as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        _write(stage/'exception.json', error)
    operations = json.loads((stage/'operations.json').read_text()) if (stage/'operations.json').exists() else dict(cold_solves=0, fresh_residuals=0, retries=0)
    checks = _checks(job, values, 'Worker failed or output unavailable.')
    source_stable = _stable(job['source_pins'])
    kernel_stable = _stable(job['kernel_pins']) and {p['path'] for p in job['kernel_pins']} == {str(p.resolve()) for p in (root/'openswing').glob('*.py')}
    numerical = bool(error is None and physical and validate_physical_checks(job, physical) and source_stable and kernel_stable and
                     operations == job['expected_operations'] and all(item['predicted'] is not None for item in checks))
    result = dict(id=job['id'], case_id='AE-1', adapter='ae1', status='computed' if numerical else 'numerical_failure',
        numerical_pass=numerical, reference_match=numerical and all(item['passed'] for item in checks), reference_checks=checks,
        physical_checks=physical, physical_calls=operations['cold_solves']+operations['fresh_residuals'], operations=operations,
        source_pins_unchanged=source_stable, kernel_pins_unchanged=kernel_stable, error=error,
        artifact_directory=str(stage), artifact_files=[_pin(p) for p in sorted(stage.iterdir()) if p.is_file()],
        historical_settings_recovered=False, complete_family_reproduction=False,
        unknown_setup=job['unknown_setup'], qualifications=job['qualifications'], reference_scope=job['reference_scope'])
    validate_result_contract(job, result); _write(stage/'adapter-result.json', result)
    return result


def mesh_diagnostics(jobs, results):
    groups = {}
    for job in jobs:
        if job.get('adapter') == 'ae1':
            groups.setdefault(job['coordinate_id'], []).append(job)
    rows = []
    for coordinate, pair in sorted(groups.items()):
        pair = sorted(pair, key=lambda job:job['nominal'])
        _require(len(pair) <= 2 and len({job['nominal'] for job in pair}) == len(pair), 'duplicate mesh coordinate.')
        packets = [results.get(job['id'], {}) for job in pair]
        row = dict(coordinate_id=coordinate, jobs=[job['id'] for job in pair], passed=None, acceptance_gate=None,
                   scope='Declared current40/80 interval sensitivity; no historical grid or full-family claim.')
        if len(pair) != 2 or any(packet.get('status') != 'computed' for packet in packets):
            row.update(status='UNAVAILABLE', channels={})
        else:
            values = [{item['name']:item['predicted'] for item in packet['reference_checks']} for packet in packets]
            changes = {}
            for name in NAMES:
                a, b = (value[name] for value in values); delta = abs(b-a)
                changes[name] = dict(coarse=a, fine=b, abs_change=delta,
                                     relative_change=delta/abs(b) if b else (0. if delta == 0 else None))
            row.update(status='COMPARED', channels=changes)
        rows.append(row)
    return rows
