"""Original AP1 header comparisons and complete, explicitly blocked span scope.

Planning and source verification use the standard library only. Each executable
job makes one cold source-coupled solve and one restored residual. The suite owns
worker deadlines; this module neither retries nor executes archived scripts.
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


REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
FAMILY = '2 - Propellers/AP - Aero Propulsive Cases - Propeller Wing Interaction/AP-1 - Propeller Jet Effect on Lift Distribution'
READINESS = 'docs/validation/isae-suite-expanded-20261026/ap1-readiness.json'
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')
NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?')
COLUMNS = ('t', 'y', 'z-z0', 'tw-tw0', "Mc'/10", "Ms'/10", 'Fn/10', 'cl', 'a_flap')
HEADER_NAMES = ('sum Fx', 'sum Fy', 'sum Fz', 'sum Mx', 'sum My', 'sum Mz',
                'Lift', 'avg CL', 'avg CD', 'avg CDi', 'avg Cm', 'Span Eff', 'L/D')
HEADER_LABELS = ('Velocity', 'Heading', 'earth X', 'Beta', 'Elev.', 'earth Y', 'Alpha', 'Bank', 'earth Z',
    'sum Mx', 'Wx', 'Wdotx', 'sum My', 'Wy', 'Wdoty', 'sum Mz', 'Wz', 'Wdotz',
    'sum Fx', 'Ux', 'Udotx', 'sum Fy', 'Uy', 'Udoty', 'sum Fz', 'Uz', 'Udotz',
    'Flap 1', 'Lift', 'Density', 'Ref.Area', 'Weight', 'Dyn.Pr.', 'Ref.Span',
    'Load Fac', 'VIAS', 'Ref.Chrd', 'Mach', 'VTAS', 'MachPG', 'avg CL', 'avg CD',
    'L/D', 'Span Eff', 'avg CDi', 'avg Cm', 'altitude', 'Op.Point')
BLOCKERS = {
    'SPAN_DISPLAY_UNRESOLVED': 'Exact original node/display mapping and a_flap semantics are unresolved. '
        'Retain every nodal resultant, shifted interval field, dummy and duplicate row without invented predictions.',
    'ZERO_LIFT_SLOPE': 'PROWIMd contains literal zero dCLda at both knots. Current lifting aero rejects it; '
        'no source-supported sentinel or model modification is established.',
    'UNPAIRED_REFERENCE': 'No exact generating model, driver and power/setup pairing is established for this export.'}
QUALIFICATIONS = [
    'Only positive-slope PROWIM header targets execute; every span target remains explicitly blocked. No full-case or family pass is implied.',
    'Original source and printed half-last-place precision are retained; no experimental target, fitted parameter or tolerance relaxation is used.',
    'The original NODE/I150 setting is recovered; current150/300 nominal intervals are declared reconstructions, not the archived150-node grid.',
    'Current influence coefficients, default core ratio.25 and cold continuation are declared; original K/F/core/startup history remains unknown.',
    'Both engines share active power channel1=500W. Original !E2 333 has no declared engine channel and remains unused-command provenance.',
    'Lift/CL/CD exclude engine thrust; net force and moment retain engines. Preserve literal Sref.1536,Cref.24,Bref.64 despite geometric full span1.28.',
    'Cm uses distributed aerodynamic moment. For these massless rigid symmetric cases the engine resultant moment is zero, so it also equals net-moment normalization; a universal exporter convention is not inferred.',
    'Span efficiency uses Trefftz CLi/CYi and literal references; values above1 are not clamped.',
    'Mcprime/Msprime require one-sided translated moment_axes; cl is interval-derived and shifted up half a line. Exact display sampling remains unverified.']
UNKNOWN_SETUP = ['original K/F influence toggle', 'original core setting', 'startup/continuation state',
                 'exact unrounded nodes and display interpolation', 'unused E2 command handling']
GATES = dict(residual=1e-8, relative_balance=1e-7, restored_parity=2e-10, clamp=1e-10)
PHYSICAL_CHECK_SPECS = {
    **{name:dict(metric=None, gate=None) for name in (
        'same_operator_identity','restore_without_evaluation','one_restored_residual','converged',
        'source_policy','two_shared_power_engines','literal_reference_normalization','root_clamp_count','finite_header_outputs')},
    'fresh_full_residual':dict(metric='maximum',gate='residual'),
    **{name:dict(metric='relative',gate='relative_balance') for name in ('force_balance','moment_balance')},
    **{name:dict(metric='maximum',gate='clamp') for name in (
        'zero_engine_resultant_moment','root_clamp_position','root_clamp_frame')},
    **{name:dict(metric='relative',gate='restored_parity') for name in (
        'independent_distributed_aero_force','independent_distributed_aero_moment',
        'independent_engine_force','independent_engine_moment','independent_force','independent_moment',
        'independent_header_Lift','independent_header_avg CL','independent_header_avg CD','independent_header_avg Cm',
        'restored_header_parity')}}
REQUIRED_PHYSICAL_CHECKS = tuple(PHYSICAL_CHECK_SPECS)
for _name, _expected in {
    'restore_without_evaluation':0, 'one_restored_residual':1, 'converged':True,
    'source_policy':dict(numerics=POLICY,operator=POLICY['structural_operator'],launch=False),
    'two_shared_power_engines':[dict(power=500.,clipped=False)]*2,
    'literal_reference_normalization':[.1536,.24,.64], 'root_clamp_count':1,
    'finite_header_outputs':{name:True for name in HEADER_NAMES}}.items():
    PHYSICAL_CHECK_SPECS[_name]['expected'] = _expected


def _require(ok, message):
    if not ok:
        raise ValueError('AP1 '+message)


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _number(token, power10=0):
    _require(isinstance(token, str) and NUMBER.fullmatch(token) is not None, 'invalid numeric token.')
    value = Decimal(token.replace('D', 'E').replace('d', 'e'))
    half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    scale = Decimal(10)**power10
    result = dict(expected_token=token, expected=float(value*scale), tolerance=float(half*scale),
        printed_value=float(value), printed_tolerance=float(half), power10=power10,
        exact_decimal_expected=str(value*scale), exact_decimal_tolerance=str(half*scale))
    _require(all(math.isfinite(result[k]) for k in ('expected', 'tolerance', 'printed_value', 'printed_tolerance'))
             and result['tolerance'] > 0, 'unrepresentable target precision.')
    return result


def _tokens(raw):
    tokens = NUMBER.findall(raw)
    _require(not NUMBER.sub('', raw).strip(), 'unparsed numeric text: '+repr(raw))
    return tokens


def decode_table(text, name):
    """Strict dedicated AP1 decoder, including adjacent signed fixed-width fields."""
    lines = text.splitlines()
    _require(len(lines) > 33, 'truncated span table.')
    columns = lines[31].split()
    expected_columns = list(COLUMNS) if name != 'PROWIN.txt' else list(COLUMNS[:-1])+['f_aero', 'a_flap']
    _require(columns == expected_columns, 'span column scope changed.')
    powers = [int(t) for t in _tokens(lines[30])]
    _require(len(powers) == 3, 'resultant exponent count changed.')
    header = {}
    for label in HEADER_LABELS:
        matches = [(i+1, m.group(1)) for i, line in enumerate(lines[:27])
            if (m := re.search(r'(?<!\w)'+re.escape(label)+r'\s*:\s*('+NUMBER.pattern+')', line))]
        _require(len(matches) == 1, 'header label missing/duplicated: '+label)
        header[label] = dict(_number(matches[0][1]), source_line=matches[0][0])
    rows = []
    for line_number, raw in enumerate(lines[33:], 34):
        if not raw.strip():
            continue
        tokens = _tokens(raw)
        _require(len(tokens) == len(columns), 'span row width changed.')
        fields = {key: _number(token, powers[i-4] if 4 <= i <= 6 else 0)
                  for i, (key, token) in enumerate(zip(columns, tokens))}
        rows.append(dict(row_number=len(rows)+1, line_number=line_number, raw_line=raw,
                         tokens=tokens, fields=fields))
    _require(len(rows) == (100 if name == 'PROWIN.txt' else 150), 'complete span row count changed.')
    _require(rows[-1]['fields']['cl']['expected'] == 0, 'last derived dummy changed.')
    return dict(columns=columns, resultant_exponents=powers, header=header, rows=rows)


def _base(root):
    return Path(root).resolve()/'.reference/isae-validation'/REVISION/FAMILY/'Aswing_Simulation'


def _specs():
    specs = []
    for suffix in ('', 'd'):
        for alpha in (0, 4, 10):
            stem = f'PROWINA{alpha}{suffix}'
            for count in (150, 300):
                for kind in ('header', 'span'):
                    specs.append(dict(id=f'AP-1-{stem}-{kind}-m{count}', target_kind='paired_'+kind,
                        model='PROWIM'+suffix+'.asw', driver='PROWIM_d.sh' if suffix else 'PROWIM.sh',
                        table=stem+'.txt', alpha=alpha, nominal=count, zero_slope=bool(suffix)))
    specs += [dict(id='AP-1-PROWIN-unpaired', target_kind='unpaired_span_and_header', model=None,
                   driver=None, table='PROWIN.txt', alpha=None, nominal=None, zero_slope=False),
              dict(id='AP-1-PROWIM-t-unpaired', target_kind='unpaired_operating', model=None,
                   driver=None, table='PROWIM.t', alpha=None, nominal=None, zero_slope=False)]
    return specs


def _spec(job_id):
    selected = [s for s in _specs() if s['id'] == job_id]
    _require(len(selected) == 1, 'unknown job.')
    return selected[0]


def _source_paths(root, spec):
    root = Path(root).resolve()
    paths = [root/'scripts/isae_suite_ap1.py', root/READINESS, root/'.reference/isae-validation/manifest.json',
             root/'.reference/aswing_doc.txt', root/'.reference/asw_theory.txt', _base(root)/spec['table']]
    paths += [_base(root)/spec[k] for k in ('model', 'driver') if spec[k]]
    return sorted(set(paths))


def _originals(root, paths):
    root = Path(root).resolve()
    manifest = root/'.reference/isae-validation/manifest.json'
    _require(_pin(manifest)['sha256'] == MANIFEST_SHA256, 'immutable manifest changed.')
    data = json.loads(manifest.read_text())
    _require(data['revision'] == REVISION, 'original revision changed.')
    cache = root/'.reference/isae-validation'/REVISION
    for path in paths:
        path = Path(path)
        if path.is_relative_to(cache):
            actual = _pin(path)
            original = data['files'][path.relative_to(cache).as_posix()]
            _require(all(actual[k] == original[k] for k in ('bytes', 'sha256')), 'original source changed: '+str(path))


def _pairing(root, spec, profile):
    if spec['model'] is None:
        return None
    base = _base(root)
    lines = (base/spec['driver']).read_text().splitlines()
    writes = [lines[i+1].strip() for i, line in enumerate(lines) if line.strip().lower() == 'w']
    suffix = 'd' if spec['zero_slope'] else ''
    _require(writes == [f'PROWINA{a}{suffix}.txt' for a in (0, 4, 10)] and
             'I 150' in lines and '!V  50' in lines and '!E1 500' in lines and '!E2 333' in lines,
             'driver/output/power pairing changed.')
    source = (base/spec['model']).read_text().splitlines()
    start = next(i for i, line in enumerate(source) if line.strip() == 'Engine')
    end = next(i for i in range(start+1, len(source)) if source[i].strip() == 'End')
    engines = [dict(line_number=i+1, tokens=_tokens(source[i])) for i in range(start+1, end)
               if source[i].strip() and not source[i].lstrip().startswith('#')]
    _require(len(engines) == 2 and all([float(t) for t in e['tokens'][:3]] == [1., 1., 1.] for e in engines),
             'shared active engine power channels changed.')
    index = next(i for i, line in enumerate(source) if line.split() == ['t', 'twist', 'alpha', 'dCLda', 'Cm'])
    slopes = [float(_tokens(source[i])[3]) for i in (index+1, index+2)]
    _require(slopes == ([0., 0.] if spec['zero_slope'] else [5.72, 5.72]), 'literal lift slope changed.')
    h = profile['header']
    for key, value in {'Velocity':50., 'Alpha':spec['alpha'], 'MachPG':0., 'Beta':0., 'Flap 1':0.,
                       'Heading':0., 'Elev.':0., 'Bank':0., 'Weight':0.}.items():
        _require(h[key]['expected'] == value, 'paired condition changed: '+key)
    return dict(original_node_I=150, active_powers_W={'1':500.}, unused_driver_power_W={'2':333.},
        per_engine_power_W=[500.,500.], engine_records=engines, literal_dCLda=slopes,
        alpha_evidence='first output header' if spec['alpha'] == 0 else 'driver command and output header',
        write_line=next(i+1 for i, line in enumerate(lines) if line.strip() == spec['table']))


def _observations(profile, kind):
    observations = []
    if kind in ('paired_header', 'unpaired_span_and_header'):
        for name in HEADER_NAMES:
            observations.append(dict(name=name, **profile['header'][name], quantity=name,
                units='N m' if name.startswith('sum M') else 'N' if name.startswith('sum F') or name == 'Lift' else 'dimensionless',
                source_column_1based=None, missing=False))
    if kind in ('paired_span', 'unpaired_span_and_header'):
        for row in profile['rows']:
            for column, name in enumerate(profile['columns'][1:], 2):
                units = ('m' if name in ('y', 'z-z0') else 'deg' if name == 'tw-tw0' else
                    'N m' if name.startswith(('Mc', 'Ms')) else 'N' if name == 'Fn/10' else
                    'N/m' if name == 'f_aero' else 'unresolved display units' if name == 'a_flap' else 'dimensionless')
                observations.append(dict(name=f"row{row['row_number']:04d}:{name}", **row['fields'][name],
                    quantity=name, units=units, source_line=row['line_number'], source_column_1based=column,
                    row_number=row['row_number'], coordinate_token=row['tokens'][0],
                    coordinate_value=row['fields']['t']['expected'], missing=False))
    return observations


def _operating(text):
    lines = text.splitlines()
    _require(lines[2].split() == ['#', 'i', 't', 'CL'], 'unpaired operating header changed.')
    rows = [dict(row_number=1, line_number=i+1, raw_line=line, tokens=_tokens(line))
            for i, line in enumerate(lines) if line.strip() and not line.lstrip().startswith('#')]
    _require(len(rows) == 1 and len(rows[0]['tokens']) == 3, 'unpaired operating row scope changed.')
    row = rows[0]
    observation = dict(name='row0001:CL', **_number(row['tokens'][2]), quantity='CL', units='dimensionless',
        source_line=row['line_number'], source_column_1based=3, row_number=1,
        coordinate_token=row['tokens'][1], coordinate_value=float(row['tokens'][1]), missing=False)
    return rows, [observation]


def _make_job(root, spec):
    root = Path(root).resolve()
    paths = _source_paths(root, spec)
    _originals(root, paths)
    kind = spec['target_kind']
    profile = None if kind == 'unpaired_operating' else decode_table((_base(root)/spec['table']).read_text(), spec['table'])
    pairing = _pairing(root, spec, profile)
    if profile is None:
        rows, observations = _operating((_base(root)/spec['table']).read_text())
    else:
        rows = profile['rows'] if kind != 'paired_header' else []
        observations = _observations(profile, kind)
    worker = kind == 'paired_header' and not spec['zero_slope']
    blocker = (None if worker else 'UNPAIRED_REFERENCE' if spec['model'] is None else
               'SPAN_DISPLAY_UNRESOLVED' if kind == 'paired_span' else 'ZERO_LIFT_SLOPE')
    condition = dict(speed=50., alpha=float(spec['alpha']), beta=0., density=1.2256, mach=0.,
        controls={'1':0.}, powers={'1':500.}, freeze_influences=False, wake_core_ratio=.25,
        attitude=[0.,0.,0.], rates=[0.,0.,0.], acceleration=[0.,0.,0.], angular_acceleration=[0.,0.,0.]) if worker else None
    return dict(id=spec['id'], case_id='AP-1', adapter='ap1', target_kind=kind,
        execution_route='worker' if worker else 'unsupported', blocker_code=blocker,
        unsupported_reason=BLOCKERS[blocker] if blocker else None,
        source=str(_base(root)/spec['model']) if spec['model'] else None,
        model_path=(_base(root)/spec['model']).relative_to(root).as_posix() if spec['model'] else None,
        driver_path=(_base(root)/spec['driver']).relative_to(root).as_posix() if spec['driver'] else None,
        table_path=(_base(root)/spec['table']).relative_to(root).as_posix(),
        mesh=f"m{spec['nominal']}" if spec['nominal'] else 'none', nominal=spec['nominal'],
        grid_counts=[spec['nominal']] if spec['nominal'] else [], panels=spec['nominal'] if worker else None,
        settings=deepcopy(POLICY) if worker else None, condition=condition,
        reference_rows=rows, header=profile['header'] if profile else None,
        columns=profile['columns'] if profile else ['i','t','CL'],
        resultant_exponents=profile['resultant_exponents'] if profile else [], pairing=pairing,
        observations=observations, expected_outputs=len(observations),
        source_pins=[_pin(path) for path in paths],
        kernel_pins=[_pin(p) for p in sorted((root/'openswing').glob('*.py'))] if worker else [],
        expected_operations=dict(cold_solves=int(worker), fresh_residuals=int(worker), retries=0),
        numerical_gates=deepcopy(GATES) if worker else None, suggested_cap_seconds=150,
        complete_family_reproduction=False, literal_input_modified=False, historical_settings_recovered=False,
        unknown_setup=list(UNKNOWN_SETUP), qualifications=list(QUALIFICATIONS),
        reference_scope='Original AP1 headers plus all retained blocked span/unpaired targets; executable positive-slope header comparisons are partial declared reconstructions.')


def build_jobs(root):
    jobs = [_make_job(root, spec) for spec in _specs()]
    _require(len(jobs) == 26 and sum(j['expected_outputs'] for j in jobs) == 15470 and
             sum(j['execution_route'] == 'worker' for j in jobs) == 6, 'family target accounting changed.')
    return jobs


def plan(root):
    return build_jobs(root)


def validate_record_contract(job):
    spec = _spec(job.get('id'))
    worker = spec['target_kind'] == 'paired_header' and not spec['zero_slope']
    _require(job.get('case_id') == 'AP-1' and job.get('adapter') == 'ap1' and
             job.get('target_kind') == spec['target_kind'] and
             job.get('execution_route') == ('worker' if worker else 'unsupported'), 'record route/scope changed.')
    _require(job.get('numerical_gates') == (GATES if worker else None) and
             job.get('expected_operations') == dict(cold_solves=int(worker),fresh_residuals=int(worker),retries=0),
             'physical gate/operation contract changed.')
    kind = spec['target_kind']
    if kind == 'unpaired_operating':
        rows = job['reference_rows']
        rebuilt, expected = _operating('# name\n# sequence\n# i t CL\n'+rows[0]['raw_line'])
        rebuilt[0]['line_number'] = rows[0]['line_number']
        expected[0]['source_line'] = rows[0]['line_number']
        _require(rows == rebuilt, 'operating row contract changed.')
    else:
        profile = dict(header=job['header'], rows=job['reference_rows'], columns=job['columns'])
        expected_columns = list(COLUMNS) if kind != 'unpaired_span_and_header' else list(COLUMNS[:-1])+['f_aero','a_flap']
        _require(job['columns'] == expected_columns and len(job['resultant_exponents']) == 3, 'column/exponent contract changed.')
        for field in job['header'].values():
            _require(all(field[k] == v for k, v in _number(field['expected_token']).items()), 'header precision changed.')
        if kind == 'paired_header':
            _require(job['reference_rows'] == [], 'header must not duplicate span-row scope.')
        else:
            _require(len(profile['rows']) == (100 if spec['model'] is None else 150), 'span row count changed.')
            for i, row in enumerate(profile['rows'], 1):
                _require(row['row_number'] == i and row['tokens'] == _tokens(row['raw_line']) and
                         len(row['tokens']) == len(expected_columns), 'span raw row/coordinate changed.')
                for j, name in enumerate(expected_columns):
                    power = job['resultant_exponents'][j-4] if 4 <= j <= 6 else 0
                    _require(row['fields'][name] == _number(row['tokens'][j], power), 'span precision/scaling changed.')
        expected = _observations(profile, kind)
    _require(job['observations'] == expected and job['expected_outputs'] == len(expected), 'observation target/precision/count changed.')
    return True


def reference_contract(job):
    validate_record_contract(job)
    return {row['name']:{key:value for key,value in row.items() if key != 'name'} for row in job['observations']}


def verify_reference_sources(root, job):
    validate_record_contract(job)
    canonical = _make_job(root, _spec(job['id']))
    _require(all(job.get(key) == value for key,value in canonical.items()), 'prepared record differs from original sources or current pinned kernel.')
    return True


def _stable(pins):
    try:
        return all(_pin(p['path']) == p for p in pins)
    except OSError:
        return False


def _checks(job, values, reason=None):
    checks = []
    for observation in job['observations']:
        value = values.get(observation['name'])
        available = isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)
        error = abs(value-observation['expected']) if available else None
        checks.append(dict(observation, predicted=value if available else None, abs_error=error,
            comparison='<=', passed=bool(available and error <= observation['tolerance']), unavailable_reason=None if available else reason))
    return checks


def validate_blocked(root, job):
    validate_record_contract(job)
    _require(job['execution_route'] == 'unsupported', 'executable header requires a physical worker.')
    spec = _spec(job['id'])
    try:
        stable = job['source_pins'] == [_pin(p) for p in _source_paths(root, spec)] and job['kernel_pins'] == []
    except OSError:
        stable = False
    if stable:
        verify_reference_sources(root, job)
    reason = job['unsupported_reason'] if stable else 'Pinned source changed; no comparison attempted.'
    return dict(id=job['id'], case_id='AP-1', adapter='ap1', target_kind=job['target_kind'],
        status='unsupported' if stable else 'source_mismatch', numerical_pass=False, reference_match=False,
        reference_status='NOT_ESTABLISHED', reference_checks=_checks(job, {}, reason),
        source_pins_unchanged=stable, kernel_pins_unchanged=True, physical_checks=[], physical_calls=0,
        production_imports=0, operations=dict(cold_solves=0,fresh_residuals=0,retries=0),
        blocker_code=job['blocker_code'], unsupported_reason=reason, complete_family_reproduction=False,
        qualifications=job['qualifications'], reference_scope=job['reference_scope'])


def header_values(result, condition):
    """Source Eq185/207–211 mapping; no total-thrust coefficient substitution."""
    alpha = math.radians(condition['alpha'])
    s, c = math.sin(alpha), math.cos(alpha)
    force, moment = result['distributed_aero_force'], result['distributed_aero_moment']
    qs = .5*condition['density']*condition['speed']**2*.1536
    lift = -s*force[0]+c*force[2]
    drag = c*force[0]+s*force[2]
    values = dict(zip(HEADER_NAMES[:6], result['force']+result['moment']))
    values.update({'Lift':lift, 'avg CL':lift/qs, 'avg CD':drag/qs,
        'avg CDi':result['CDi'], 'avg Cm':moment[1]/(qs*.24), 'Span Eff':result['efficiency'],
        'L/D':lift/drag if drag else None})
    return values


def reconstruct_wrenches(result, reference):
    """Independently sum saved strip and engine wrenches about the literal origin."""
    def add(a, b):
        return [x+y for x,y in zip(a,b)]
    def cross(a, b):
        return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
    def sum_wrenches(rows):
        force, moment = [0.,0.,0.], [0.,0.,0.]
        for row in rows:
            force = add(force, row['force'])
            arm = [p-r for p,r in zip(row['position'],reference)]
            moment = add(moment, add(row['moment'],cross(arm,row['force'])))
        return force, moment
    aero_force, aero_moment = sum_wrenches(result['strips'])
    engine_force, engine_moment = sum_wrenches(result['engines'])
    return dict(distributed_aero_force=aero_force, distributed_aero_moment=aero_moment,
        engine_force=engine_force, engine_moment=engine_moment,
        force=add(aero_force,engine_force), moment=add(aero_moment,engine_moment))


def validate_physical_checks(job, checks):
    """Require complete, unique metric evidence before accepting numerical pass."""
    _require(job['numerical_gates'] == GATES, 'physical gates changed.')
    names = [check.get('name') for check in checks]
    _require(len(names) == len(set(names)) == len(REQUIRED_PHYSICAL_CHECKS) and
             set(names) == set(REQUIRED_PHYSICAL_CHECKS), 'physical-check set incomplete or duplicated.')
    for check in checks:
        spec = PHYSICAL_CHECK_SPECS[check['name']]
        if spec['metric'] is None:
            _require('actual' in check and 'expected' in check, 'physical comparison evidence missing.')
            if 'expected' in spec:
                _require(check['expected'] == spec['expected'], 'physical comparison expectation changed.')
            passed = check['actual'] == check['expected']
        else:
            metric = check.get(spec['metric'])
            gate = job['numerical_gates'][spec['gate']]
            _require(isinstance(metric,(int,float)) and not isinstance(metric,bool) and
                     math.isfinite(metric) and metric >= 0 and check.get('gate') == gate,
                     'physical metric/gate evidence invalid.')
            passed = metric <= gate
            if check['name'].startswith('independent_'):
                reported, reconstructed = check.get('reported'), check.get('reconstructed')
                _require(reported is not None and reconstructed is not None, 'independent load evidence missing.')
                if not isinstance(reported,list):
                    reported, reconstructed = [reported], [reconstructed]
                _require(len(reported) == len(reconstructed) and len(reported) in (1,3) and
                    all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
                        for v in reported+reconstructed), 'independent load vectors invalid.')
                recomputed = max(abs(a-b) for a,b in zip(reported,reconstructed))/(1.+max(map(abs,reported+reconstructed)))
                _require(metric == recomputed, 'independent load metric inconsistent with vectors.')
            elif check['name'] in ('force_balance','moment_balance'):
                applied, support = check.get('applied'), check.get('support')
                _require(isinstance(applied,list) and isinstance(support,list) and len(applied) == len(support) == 3 and
                    all(isinstance(v,(int,float)) and math.isfinite(v) for v in applied+support), 'balance vectors unavailable.')
                # Norm implementations can differ by an ulp; this is metric
                # reconstruction precision, not a physical acceptance gate.
                recomputed = math.hypot(*(a+b for a,b in zip(applied,support)))/max(1.,math.hypot(*applied)+math.hypot(*support))
                _require(math.isclose(metric,recomputed,rel_tol=2e-15,abs_tol=1e-30), 'balance metric inconsistent with vectors.')
            elif check['name'] == 'restored_header_parity':
                reported, restored = check.get('reported'), check.get('restored')
                _require(isinstance(reported,dict) and isinstance(restored,dict) and
                    set(reported) == set(restored) == set(HEADER_NAMES) and
                    all(isinstance(v,(int,float)) and math.isfinite(v) for v in list(reported.values())+list(restored.values())),
                    'restored header evidence unavailable.')
                channels = {k:abs(reported[k]-restored[k])/(1+abs(reported[k])) for k in HEADER_NAMES}
                _require(check.get('channels') == channels and metric == max(channels.values()), 'restored header metric inconsistent.')
        _require(isinstance(check.get('passed'),bool) and check['passed'] == bool(passed), 'physical pass flag inconsistent.')
    return all(check['passed'] for check in checks)


def _execute(root, job, stage):
    """One bounded cold solve followed by one same-operator restored residual."""
    import numpy as np
    from openswing.bridge import dispatch
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.equilibrium_state import identity, restore
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.network import network_snapshot
    import openswing

    _require(Path(openswing.__file__).resolve().parent == Path(root).resolve()/'openswing',
             'worker imported a different checkout.')

    request = dict(action='solve', mode='mounted', source=Path(job['source']).read_text(),
        panels=job['panels'], numerics=job['settings'], condition=job['condition'])
    _write(stage/'request.json', request)
    operations = dict(cold_solves=0, fresh_residuals=0, retries=0)
    _write(stage/'operations.json', operations)
    operations['cold_solves'] = 1
    _write(stage/'operations.json', operations)
    result = dispatch(request)
    _write(stage/'result.json', result)
    model = parse_asw(request['source'], beam_interpolation=job['settings']['beam_interpolation'])
    condition = deepcopy(job['condition'])
    for key in ('powers','controls'):
        condition[key] = {int(k):v for k,v in condition[key].items()}
    network = SourceCoupledNetwork(model, job['panels'], FlightCondition(**condition))
    checks = []
    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))
    check('same_operator_identity', identity(network) == result['equilibrium_state']['identity'],
          actual=identity(network), expected=result['equilibrium_state']['identity'])
    state = restore(network, result['equilibrium_state'])
    check('restore_without_evaluation', network.nfev == 0, actual=network.nfev, expected=0)
    operations['fresh_residuals'] = 1
    _write(stage/'operations.json', operations)
    residual, data = network.residual(state, detail=True)
    fresh = network_snapshot(network, residual, data)
    _write(stage/'restored-result.json', fresh)
    check('one_restored_residual', network.nfev == 1, actual=network.nfev, expected=1)
    check('converged', result['converged'] is True, actual=result['converged'], expected=True)
    error = float(np.max(np.abs(residual)))
    check('fresh_full_residual', error <= GATES['residual'], maximum=error, gate=GATES['residual'])
    actual_policy = dict(numerics=result.get('numerics'),operator=result['structural_operator'],launch='launch' in result['equilibrium_state'])
    expected_policy = dict(numerics=POLICY,operator=POLICY['structural_operator'],launch=False)
    check('source_policy', actual_policy == expected_policy, actual=actual_policy, expected=expected_policy)
    for key in ('force','moment'):
        applied, support = np.asarray(result['applied_'+key]), np.asarray(result['support_'+key])
        relative = float(np.linalg.norm(applied+support)/max(1., np.linalg.norm(applied)+np.linalg.norm(support)))
        check(key+'_balance', relative <= GATES['relative_balance'], relative=relative, gate=GATES['relative_balance'],
              applied=applied.tolist(), support=support.tolist())
    actual_powers = [dict(power=e['requested_power'],clipped=e['power_clipped']) for e in result['engines']]
    expected_powers = [dict(power=500.,clipped=False)]*2
    check('two_shared_power_engines', actual_powers == expected_powers, actual=actual_powers, expected=expected_powers)
    check('literal_reference_normalization', np.array_equal(model.reference[0], [.1536,.24,.64]),
          actual=model.reference[0].tolist(), expected=[.1536,.24,.64])
    maximum = float(np.max(np.abs(result['engine_moment'])))
    check('zero_engine_resultant_moment', maximum <= GATES['clamp'], maximum=maximum, gate=GATES['clamp'])
    reconstructed = reconstruct_wrenches(result, model.reference[1])
    for key, independent in reconstructed.items():
        reported = np.asarray(result[key])
        independent = np.asarray(independent)
        relative = float(np.max(abs(reported-independent))/(1.+max(np.max(abs(reported)),np.max(abs(independent)))))
        check('independent_'+key, relative <= GATES['restored_parity'], relative=relative,
              gate=GATES['restored_parity'], reported=reported.tolist(), reconstructed=independent.tolist())
    clamps = [constraint['a'] for constraint in network.constraints if constraint['kind'] == 'ground']
    check('root_clamp_count', len(clamps) == 1, actual=len(clamps), expected=1)
    maximum = float(max((np.max(abs(data['r'][node]-network.rj[node])) for node in clamps),default=1.))
    check('root_clamp_position', maximum <= GATES['clamp'], maximum=maximum, gate=GATES['clamp'])
    maximum = float(max((np.max(abs(data['Q'][node]-np.eye(3))) for node in clamps),default=1.))
    check('root_clamp_frame', maximum <= GATES['clamp'], maximum=maximum, gate=GATES['clamp'])
    values, restored = header_values(result, job['condition']), header_values(fresh, job['condition'])
    independent_values = header_values(dict(reconstructed, CDi=result['CDi'], efficiency=result['efficiency']), job['condition'])
    for name in ('Lift','avg CL','avg CD','avg Cm'):
        difference = abs(values[name]-independent_values[name])/(1.+max(abs(values[name]),abs(independent_values[name])))
        check('independent_header_'+name, difference <= GATES['restored_parity'],
              relative=difference, gate=GATES['restored_parity'], reported=values[name], reconstructed=independent_values[name])
    finite = {k:isinstance(v,(int,float)) and math.isfinite(v) for k,v in values.items()}
    check('finite_header_outputs', all(finite.values()), actual=finite, expected={k:True for k in HEADER_NAMES})
    parity = {k:abs(values[k]-restored[k])/(1+abs(values[k])) if values[k] is not None and restored[k] is not None else 1.
              for k in HEADER_NAMES}
    relative = max(parity.values())
    check('restored_header_parity', relative <= GATES['restored_parity'], relative=relative,
          gate=GATES['restored_parity'], channels=parity, reported=values, restored=restored)
    validate_physical_checks(job, checks)
    _write(stage/'physical-checks.json', checks)
    return values, checks


def run(root, job):
    root = Path(root).resolve()
    if job.get('execution_route') == 'unsupported':
        return validate_blocked(root, job)
    verify_reference_sources(root, job)
    _require(job['execution_route'] == 'worker' and job['target_kind'] == 'paired_header', 'unsupported worker route.')
    stage = Path(tempfile.mkdtemp(prefix='openswing-isae-suite-ap1-'+job['id']+'-'))
    _write(stage/'job.json', job)
    values, physical, error = {}, [], None
    try:
        values, physical = _execute(root, job, stage)
    except Exception as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        _write(stage/'exception.json', error)
    operations = json.loads((stage/'operations.json').read_text()) if (stage/'operations.json').is_file() else dict(cold_solves=0,fresh_residuals=0,retries=0)
    source_stable = _stable(job['source_pins'])
    kernel_stable = (_stable(job['kernel_pins']) and {p['path'] for p in job['kernel_pins']} ==
                     {str(p.resolve()) for p in (root/'openswing').glob('*.py')})
    checks = _checks(job, values, 'Worker failed or output unavailable.')
    numerical = bool(error is None and source_stable and kernel_stable and physical and
                     validate_physical_checks(job,physical) and all(c['predicted'] is not None for c in checks) and
                     operations == job['expected_operations'])
    result = dict(id=job['id'], case_id='AP-1', adapter='ap1', target_kind=job['target_kind'],
        status='computed' if numerical else 'numerical_failure', numerical_pass=numerical,
        reference_match=numerical and all(c['passed'] for c in checks), reference_checks=checks,
        physical_checks=physical, physical_calls=sum(operations[k] for k in ('cold_solves','fresh_residuals')),
        operations=operations, error=error, source_pins_unchanged=source_stable, kernel_pins_unchanged=kernel_stable,
        artifact_directory=str(stage), artifact_files=[_pin(p) for p in sorted(stage.iterdir()) if p.is_file()],
        historical_settings_recovered=False, unknown_setup=job['unknown_setup'], complete_family_reproduction=False,
        qualifications=job['qualifications'], reference_scope=job['reference_scope'])
    _write(stage/'adapter-result.json', result)
    return result


def mesh_diagnostics(jobs, results):
    """Saved header changes only; no new physical or mesh acceptance gate."""
    groups = {}
    for job in jobs:
        if job.get('adapter') == 'ap1' and job.get('execution_route') == 'worker':
            groups.setdefault(job['table_path'], []).append(job)
    diagnostics = []
    for table, pair in sorted(groups.items()):
        pair = sorted(pair, key=lambda job:job['nominal'])
        _require(len(pair) <= 2 and len({j['nominal'] for j in pair}) == len(pair) and
                 all(j['nominal'] in (150,300) for j in pair), 'invalid header mesh pair.')
        packets = [results.get(j['id'], {}) for j in pair]
        row = dict(table=table, jobs=[j['id'] for j in pair], passed=None, acceptance_gate=None,
                   scope='Descriptive mesh change only; neither numerical validity nor archived agreement is inferred.')
        if len(pair) != 2 or any(p.get('status') != 'computed' for p in packets):
            row.update(status='UNAVAILABLE', channels={})
        else:
            values = [{c['name']:c['predicted'] for c in p['reference_checks']} for p in packets]
            channels = {}
            for name in HEADER_NAMES:
                coarse, fine = (v[name] for v in values)
                delta = abs(fine-coarse)
                channels[name] = dict(coarse=coarse, fine=fine, abs_change=delta,
                    relative_change=delta/abs(fine) if fine else (0. if delta == 0 else None))
            row.update(status='COMPARED', channels=channels)
        diagnostics.append(row)
    return diagnostics
