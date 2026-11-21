"""All rows of three original AE-2 layups and FFWT-1 Flare10/A5 exports.

Planning and blocked-row validation use stdlib only. Each executable job calls
one existing pinned worker: one cold solve and one restored residual. The suite
owns deadlines/processes. Historical settings remain conditional; no current
state is reused and no experimental observation enters acceptance.
"""
from copy import deepcopy
from decimal import Decimal
import contextlib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import tempfile
import traceback
import zipfile

POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-coupled-v1')
AE_CHANNELS = ('RY_m', 'Psi_deg', 'sensor_V_m_s', 'sensor_beta_deg')
FF_CHANNELS = dict(lift='Lift_N', root_Mc='Mcprime_sensor1_Nm',
                   left_tip_bank='Phi_sensor2_deg', left_tip_alpha='alpha_sensor2_deg')
HELPERS = {'AE-2': 'verify-source-coupled-integration.py', 'FFWT-1': 'verify-isae-ffwt-reference.py'}
AE_COUPLED_PAIRS = 'docs/validation/isae-suite-st2-ap1-20261026/next-original-pairs.json'
AE_COUPLED_PAIRS_SHA256 = '62b274f26819b4da5234ed3e210ae3aac4c9770623a4bf1ff85dcbc4986ababd'
ISAE_REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
AE_COUPLED_COUNTS = {'m15_02': (21,21,16,15), 'p15_02': (31,31,27,22)}
_PLAN_CACHE = {}


def _read(path):
    return json.loads(Path(path).read_text())


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _verified(pin):
    actual = _pin(pin['path'])
    # Historical catalogs retain the .reference alias. Verify the original
    # bytes, then issue a canonical pin without rewriting archived evidence.
    _require(all(actual[key] == pin[key] for key in ('bytes', 'sha256')),
             'Original source changed: '+pin['path'])
    return actual


def _literal_row(row, output, script, *, ae):
    """Cross-check literal bytes, command coordinates and decimal half units."""
    lines = Path(output['path']).read_text().splitlines()
    number = row['output_file_line_1based'] if ae else row['file_line']
    _require(lines[number-1] == row['raw_line'], 'Archived raw row changed.')
    _require(lines[number-1].split() == row['raw_tokens'], 'Archived token mapping changed.')
    commands = Path(script['path']).read_text().splitlines()
    command_line = row['command_line_1based'] if ae else row['command_line']
    lexeme = row['command_value_lexeme'] if ae else row['commanded_IAS_token']
    _require(commands[command_line-1].strip() == '!V '+lexeme, 'Original IAS command mapping changed.')
    _require(float(lexeme) == row['commanded_IAS_m_s'], 'Command speed differs from source lexeme.')
    observations = []
    for index, (channel, original) in enumerate(((k, k) for k in AE_CHANNELS) if ae else FF_CHANNELS.items(), 2):
        token = row['raw_tokens'][index]
        missing = token.lower() == 'nan'
        if missing:
            _require(ae and row['values'][original] is None and row['printed_resolution'][original] is None,
                     'Undeclared missing original output.')
            value = half = None
        else:
            decimal = Decimal(token)
            value = float(decimal)
            half = float(Decimal(5).scaleb(decimal.as_tuple().exponent-1))
            declared_value = row['values'][original] if ae else row['values'][original]['value']
            declared_half = (row['printed_resolution'][original]['nearest_rounding_half_unit_decimal'] if ae
                             else row['values'][original]['half_printing_unit'])
            _require(math.isfinite(value) and value == declared_value and half == float(declared_half),
                     'Original output value/precision differs from literal token.')
        observations.append(dict(name=channel, original_name=original, token=token,
            expected=value, tolerance=half, missing=missing, source_line=number, source_column_1based=index+1))
    return observations


def _ae_sources(root):
    catalog_path = root/'docs/validation/isae-ae2-aswing-catalog.json'
    catalog = _read(catalog_path)
    archive = root/'docs/validation/isae-source-coupled-20261026-evidence.zip'
    with zipfile.ZipFile(archive) as stream:
        audit = json.loads(stream.read('case-audit/report.json'))
        pilot_plan = json.loads(stream.read('native/plan.json'))
    _require(catalog['model']['pin'] == audit['model']['pin'], 'AE2 model provenance differs.')
    return catalog, audit, pilot_plan, [_pin(catalog_path), _pin(archive)]


def _decode_coupled_rows(output_text, commands, beta, layup):
    """Bind every original sensor row to its exact, ordered IAS command."""
    lines = output_text.splitlines()
    _require(len(lines) >= 4 and lines[1] == '# Operating point sequence...' and
             lines[2].split() == ['#','i','t','RY','pos[','1]','Psi[','1]','V[','1]','beta[','1]'],
             'AE2 coupled sensor header changed.')
    data = [(i+1,line) for i,line in enumerate(lines) if line.strip() and not line.lstrip().startswith('#')]
    _require(len(data) == len(commands), 'AE2 coupled IAS/output row count differs.')
    rows = []
    for index, ((line_number, raw), command) in enumerate(zip(data,commands),1):
        tokens = raw.split()
        _require(len(tokens) == 6 and tokens[0] == str(index) and Decimal(tokens[1]) == index,
                 'AE2 coupled output row order/width changed.')
        speed = float(command['token'])
        _require(math.isfinite(speed) and speed == index-1, 'AE2 coupled IAS sequence changed.')
        values, precision, finite = {}, {}, []
        for channel, token in zip(AE_CHANNELS,tokens[2:]):
            if token == 'NaN':
                value = printing = None
            else:
                decimal = Decimal(token)
                value = float(decimal)
                _require(math.isfinite(value), 'AE2 coupled nonfinite output token.')
                printing = dict(last_printed_unit_decimal=str(Decimal(1).scaleb(decimal.as_tuple().exponent)),
                    nearest_rounding_half_unit_decimal=str(Decimal(5).scaleb(decimal.as_tuple().exponent-1)))
            values[channel], precision[channel] = value, printing
            finite.append(value is not None)
        _require((not any(finite)) if speed == 0 else all(finite), 'AE2 coupled missing-output pattern changed.')
        rows.append(dict(id=f'{layup}-b{beta:02d}-ias{int(speed):03d}', beta_deg=beta,
            commanded_IAS_m_s=speed, command_line_1based=command['line_number'], command_value_lexeme=command['token'],
            output_data_row_1based=index, output_file_line_1based=line_number, raw_line=raw, raw_tokens=tokens,
            stack_index=index, stack_parameter=float(tokens[1]), values=values, finite_mask=finite,
            printed_resolution=precision, status='FINITE_ARCHIVED_STATE' if all(finite) else 'INITIAL_ALL_NAN_RETAINED_UNCOMPUTED'))
    return rows


def _ae_coupled_catalogs(root, baseline):
    """Source-only catalogs for the eight reviewed coupled-layup driver pairs."""
    pair_path = root/AE_COUPLED_PAIRS
    manifest_path = root/'reference/isae-validation/manifest.json'
    _require(_pin(pair_path)['sha256'] == AE_COUPLED_PAIRS_SHA256, 'AE2 coupled source-pair evidence changed.')
    _require(_pin(manifest_path)['sha256'] == MANIFEST_SHA256, 'Original ISAE manifest changed.')
    manifest = _read(manifest_path)
    _require(manifest['revision'] == ISAE_REVISION, 'Original ISAE revision changed.')
    cache = (root/'reference/isae-validation'/ISAE_REVISION).resolve()
    pairs = [record for record in _read(pair_path)['records'] if record['family'] == 'AE-2']
    _require(len(pairs) == 8, 'AE2 coupled source-pair count changed.')
    original_model = Path(baseline['model']['pin']['path']).read_text().splitlines()
    catalogs = []
    for layup, counts in AE_COUPLED_COUNTS.items():
        sweeps = []
        model_pin = None
        for beta, count in zip((1,5,10,15),counts):
            matching = [p for p in pairs if Path(p['model']['path']).name == f'[{layup}]_S.asw' and p['beta_deg'] == beta]
            _require(len(matching) == 1, 'AE2 coupled layup/beta pair missing or duplicated.')
            pair = matching[0]
            pins = {}
            for key in ('model','driver','output'):
                path = (root/pair[key]['path']).resolve()
                actual = _pin(path)
                original = manifest['files'][path.relative_to(cache).as_posix()]
                _require(all(actual[field] == pair[key][field] == original[field] for field in ('bytes','sha256')),
                         'AE2 coupled literal source changed: '+str(path))
                pins[key] = actual
            model_pin = pins['model']
            model_path, script_path, output_path = (Path(pins[k]['path']) for k in ('model','driver','output'))
            _require(model_path.parent == script_path.parent == output_path.parent == Path(baseline['model']['pin']['path']).resolve().parent and
                     script_path.name == f'[{layup}]_s_A{beta}.sh' and output_path.name == f'[{layup}]_S_A{beta}.txt',
                     'AE2 coupled exact source filenames changed.')
            model_lines = model_path.read_text().splitlines()
            # Same geometry, sensor, clamp and control breakpoints justify the
            # existing count+1 topology check. Material/offset rows stay literal.
            allowed_changes = {35,36,37,41,42}
            _require(len(model_lines) == len(original_model) and
                     all(line.split() == original_model[i-1].split() for i,line in enumerate(model_lines,1) if i not in allowed_changes),
                     'AE2 coupled topology/sensor/control source contract changed.')
            for line_number in (36,37):
                _require(model_lines[line_number-1].split()[:7] == original_model[line_number-1].split()[:7],
                         'AE2 coupled geometry stations changed.')
            commands = script_path.read_text().splitlines()
            _require(re.fullmatch(r'.*/aswing '+re.escape(f'[{layup}]_S')+r'\s*<<EOF',commands[1]) is not None,
                     'AE2 coupled launch/model pairing changed.')
            _require([line.strip() for line in commands[4:12]] == ['oper','g','1','0 0 1','%','a','d',f'!B {beta}'],
                     'AE2 coupled original initialization/beta commands changed.')
            speed_commands = [dict(line_number=i+1,token=line.split()[1]) for i,line in enumerate(commands) if line.strip().startswith('!V ')]
            _require(speed_commands == pair['speed_commands'] and len(speed_commands) == pair['row_count'] == count,
                     'AE2 coupled ordered speed commands changed.')
            writes = [commands[i+1].strip() for i,line in enumerate(commands) if line.strip() == 'w']
            _require(writes == [output_path.name], 'AE2 coupled output write pairing changed.')
            sensor_lines = [(i+1,line.split()) for i,line in enumerate(commands) if line.strip() in ('14 1','19 1','20 1','18 1')]
            _require([tokens for _,tokens in sensor_lines] == [['14','1'],['19','1'],['20','1'],['18','1']],
                     'AE2 coupled sensor channel selection changed.')
            additional_outputs = []
            for i,line in enumerate(commands):
                if line.strip() == 'ww':
                    name = commands[i+1].strip()
                    _require(layup == 'm15_02' and beta == 15 and name == '[m15_02]_S_A15_dist.txt',
                             'AE2 unreviewed supplementary output command.')
                    path = output_path.parent/name
                    pin = _pin(path)
                    original = manifest['files'][path.relative_to(cache).as_posix()]
                    _require(all(pin[field] == original[field] for field in ('bytes','sha256')),
                             'AE2 supplementary distribution export changed.')
                    additional_outputs.append(dict(source=pin,write_command_line_1based=i+1,
                        scope='Supplementary span distribution retained as provenance; outside the four-sensor-channel adapter. Exact span output recovery remains a separate required family task.'))
            _require(len(additional_outputs) == int(layup == 'm15_02' and beta == 15),
                     'AE2 supplementary distribution-export provenance changed.')
            rows = _decode_coupled_rows(output_path.read_text(),speed_commands,beta,layup)
            sweeps.append(dict(beta_deg=beta,script_pin=pins['driver'],output_pin=pins['output'],rows=rows,
                additional_driver_outputs=additional_outputs,
                source_pairing=dict(model=model_pin,script=pins['driver'],output=pins['output'],
                    launch_line_1based=2,beta_command_line_1based=12,
                    sensor_selections=[dict(line_number=line,selection=int(tokens[0]),sensor=int(tokens[1])) for line,tokens in sensor_lines],
                    row_count=count,source_pair_evidence=_pin(pair_path))))
        catalogs.append(dict(model=dict(pin=model_pin),layup=layup,sweeps=sweeps,
            historical_unknowns=baseline['historical_unknowns'],
            source_dependencies=[_pin(pair_path),_pin(manifest_path)]))
    _require(sum(len(s['rows']) for c in catalogs for s in c['sweeps']) == 184, 'AE2 coupled row accounting changed.')
    return catalogs


def _base(root, family, coordinate, mesh, source, pins, kernels, observations, condition, panels, gates, unknowns):
    missing = any(o['missing'] for o in observations)
    return dict(id=f'{family}-{coordinate}-{mesh}', case_id=family, adapter='aeroelastic',
        execution_route='unsupported' if missing else 'worker', coordinate_id=coordinate, mesh=mesh,
        expected_outputs=4, outputs_per_row=4, observations=observations,
        source=source, source_pins=pins, kernel_pins=kernels,
        helper=str(root/'scripts'/HELPERS[family]), settings=POLICY.copy(),
        condition=condition, panels=panels, numerical_gates=gates,
        expected_operations=dict(cold_solves=0 if missing else 1, fresh_residuals=0 if missing else 1),
        suggested_cap_seconds=120, historical_settings_recovered=False, historical_unknowns=unknowns,
        reference_scope=('All four printed sensor channels of all twelve sweeps for original [03_90], [m15_02]_S and [p15_02]_S models; supplemental span exports and other models remain outside this adapter.'
            if family == 'AE-2' else 'All four printed channels of Flare10/A5 only; other FFWT1 model/incidence exports are outside this adapter.'),
        qualifications=[
            'Original model bytes and exact commanded IAS/incidence are unchanged; no experiment or fitted parameter is used.',
            'Reconstruction assumes speed equals commanded IAS at the declared atmosphere. Historical TAS, atmosphere, PG/KF settings and node arrays remain unknown.',
            'Independent cold starts do not reproduce unknown historical continuation or nonlinear branch history.',
            'Numerical validity, strict printed precision and two-mesh sensitivity are separate; no complete-family or historical-setting match is asserted.'])


def _plan(root, selected=None):
    """Build all jobs, or reconstruct only one canonical job in a fresh worker."""
    root = Path(root).resolve()
    kernels = [_pin(p) for p in sorted((root/'openswing').glob('*.py'))]
    _require(bool(kernels), 'Current production kernels are missing.')
    own = _pin(Path(__file__))
    catalog, audit, pilot, dependencies = _ae_sources(root)
    catalogs = [catalog]+_ae_coupled_catalogs(root,catalog)
    jobs = []
    for model_catalog, sweep in ((c,s) for c in catalogs for s in c['sweeps']):
        prefix = sweep['rows'][0]['id'].rsplit('-ias',1)[0]
        if selected is not None and not selected.startswith('AE-2-'+prefix+'-'):
            continue
        model = _verified(model_catalog['model']['pin'])
        script, output = (_verified(sweep[k]) for k in ('script_pin', 'output_pin'))
        commands = Path(script['path']).read_text().splitlines()
        _require(any(line.strip() == '!B '+str(sweep['beta_deg']) for line in commands), 'AE2 beta command absent.')
        pins = [own, _pin(root/'scripts'/HELPERS['AE-2']), model, script, output]+dependencies+model_catalog.get('source_dependencies',[])
        pins += [entry['source'] for entry in sweep.get('additional_driver_outputs',[])]
        for row in sweep['rows']:
            if selected is not None and not selected.startswith('AE-2-'+row['id']+'-'):
                continue
            observations = _literal_row(row, output, script, ae=True)
            condition = deepcopy(audit['proposed_condition'])
            condition.update(speed=row['commanded_IAS_m_s'], beta=row['beta_deg'], circulation_modes={'1': 0})
            _require(row['beta_deg'] == sweep['beta_deg'], 'Row/sweep incidence mismatch.')
            missing = any(o['missing'] for o in observations)
            _require((all(o['missing'] for o in observations) and condition['speed'] == 0.) if missing
                     else condition['speed'] > 0., 'Unsupported AE2 missing/speed pattern.')
            for count in (80, 160):
                if selected is not None and selected != f"AE-2-{row['id']}-m{count}":
                    continue
                job = _base(root, 'AE-2', row['id'], f'm{count}', model['path'], pins, kernels,
                    observations, condition, dict(default=count, beams={'1': dict(count=count, spacing='cosine')}),
                    pilot['gates'], model_catalog['historical_unknowns'])
                job.update(reference_row=deepcopy(row), source_script=script, source_output=output,
                    nominal=count, expected_elements=count+1,
                    mesh_group='AE-2:'+row['id'], mesh_order=count,
                    mesh_gate=dict(relative_limit=pilot['gates']['mesh_relative'], channels=list(AE_CHANNELS[:2])))
                if 'layup' in model_catalog:
                    job.update(layup=model_catalog['layup'],source_pairing=deepcopy(sweep['source_pairing']),
                               additional_driver_outputs=deepcopy(sweep['additional_driver_outputs']))
                    job['qualifications'] += [
                        'Coupled-layup filenames A1/A5/A10/A15 are paired to literal beta commands; alpha remains the declared0deg.',
                        'All literal stiffness, coupling and tension-axis offsets are retained. Neither the uncoupled properties nor a sensor relocation is substituted.',
                        'Geometry, sensor, clamp and flap breakpoints match the reviewed uncoupled topology; count+1 elements is a current mesh check, not a recovered historical node count.']
                if missing:
                    job['blocked_reason'] = 'The original zero-speed row has four literal NaN outputs. Retain all missing slots; no zero replacement, interpolation or reference comparison is defined.'
                jobs.append(job)
    contract_path = root/'docs/validation/isae-ffwt-reference-contract.json'
    contract = _read(contract_path)
    source = root/'examples/isae-ffwt-flare10.asw'
    model = _verified(contract['model'])
    _require(_pin(source)['sha256'] == model['sha256'], 'Packaged FFWT model differs from original.')
    script, output = (_verified(contract['source_pins'][key]) for key in ('script', 'output'))
    alpha_line, alpha_token = contract['script_contract']['alpha_command']
    _require(Path(script['path']).read_text().splitlines()[alpha_line-1].strip() == '!A '+alpha_token,
             'FFWT alpha command changed.')
    pins = [own, _pin(root/'scripts'/HELPERS['FFWT-1']), _pin(contract_path), _pin(source), model, script, output]
    for row in contract['reference_rows']:
        if selected is not None and not selected.startswith(f"FFWT-1-row{row['row']:02d}-"):
            continue
        observations = _literal_row(row, output, script, ae=False)
        _require(row['commanded_alpha_deg'] == float(alpha_token), 'FFWT row/command alpha mismatch.')
        condition = deepcopy(contract['condition'])
        condition.update(speed=row['commanded_IAS_m_s'], alpha=row['commanded_alpha_deg'])
        for order, case in enumerate(contract['cases']):
            if selected is not None and selected != f"FFWT-1-row{row['row']:02d}-{case['name']}":
                continue
            job = _base(root, 'FFWT-1', f"row{row['row']:02d}", case['name'], str(source), pins, kernels,
                observations, condition, deepcopy(case['panels']), contract['gates'], contract['historical_unknowns'])
            job.update(reference_row=deepcopy(row), source_script=script, source_output=output,
                reference_contract=str(contract_path), mesh_group=f"FFWT-1:row{row['row']:02d}", mesh_order=order,
                mesh_gate=dict(relative_limit=contract['gates']['mesh'], channels=list(FF_CHANNELS)),
                original_anchored_defaults_applied_to_this_row=row['row'] == 8)
            job['qualifications'] += [
                'Anchored defaults is commanded after selecting row8; rows1–7 constraint tables are not recovered. The same declared mounted reconstruction is used throughout.',
                'Root Mc uses the preselected left sensor trace; right trace is retained diagnostically without choosing the closer value.',
                'Original NODE100/40/40 are node counts; requested OpenSwing intervals and actual inserted stations are retained, not claimed identical.']
            jobs.append(job)
    if selected is None:
        _require(len(jobs) == 566 and sum(j['expected_outputs'] for j in jobs) == 2264
                 and sum(j['execution_route'] == 'worker' for j in jobs) == 542, 'Incomplete original row catalog.')
    return jobs


def plan(root):
    """542 executable jobs +24 missing-row records;2264 required output slots."""
    root = Path(root).resolve()
    jobs = _plan(root)
    _PLAN_CACHE[str(root)] = {j['id']:deepcopy(j) for j in jobs}
    return jobs


def _canonical(root, job):
    canonical = _PLAN_CACHE.get(str(root), {}).get(job.get('id'))
    if canonical is None:
        selected = _plan(root, selected=job.get('id', ''))
        _require(len(selected) == 1, 'Unknown aeroelastic job.')
        canonical = selected[0]
    else:
        # Caching only avoids reconstructing all packets. Every selected source
        # and kernel byte is still verified, including newly added modules.
        _require(all(_pin(p['path']) == p for p in canonical['source_pins']+canonical['kernel_pins']),
                 'Cached canonical source changed.')
        _require({p['path'] for p in canonical['kernel_pins']} ==
                 {str(p.resolve()) for p in (root/'openswing').glob('*.py')}, 'Kernel inventory changed.')
    for key, value in canonical.items():
        _require(job.get(key) == value, 'Prepared aeroelastic job changed: '+key)
    return canonical


def _checks(job, values):
    rows = []
    for original in job['observations']:
        row = dict(original)
        value = values.get(row['name'])
        available = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        row.update(predicted=value if available else None, comparison='<=',
            passed=bool(available and not row['missing'] and abs(value-row['expected']) <= row['tolerance']))
        rows.append(row)
    return rows


def validate_blocked(root, job):
    canonical = _canonical(Path(root).resolve(), job)
    _require(canonical['execution_route'] == 'unsupported', 'This job requires the physical worker.')
    return dict(id=canonical['id'], case_id=canonical['case_id'], adapter='aeroelastic', status='unsupported',
        numerical_pass=False, reference_match=False, reference_checks=_checks(canonical, {}),
        reason=canonical['blocked_reason'], source_pins_unchanged=True,
        operations=dict(cold_solves=0, fresh_residuals=0), reference_scope=canonical['reference_scope'])


def _prepare_worker(root, job, stage):
    """Only adapt worker input packets; preserve the existing worker verbatim."""
    name = job['mesh']
    request = dict(action='solve', mode='mounted', source=Path(job['source']).read_text(),
        panels=job['panels'], condition=job['condition'], numerics=job['settings'],
        operating_constraints=[], strut_mode='bilateral', controller=None)
    folder = stage/'cases'/name
    _write(folder/'request.json', request)
    pins = job['source_pins']+job['kernel_pins']+[_pin(folder/'request.json')]
    prepared = dict(status='PREPARED_BY_CURRENT_SUITE', cases=[dict(name=name, request=str(folder/'request.json'))],
        gates=job['numerical_gates'], pins=pins,
        kernel_pins={Path(p['path']).name:p['sha256'] for p in job['kernel_pins']},
        cold_solves=1, fresh_residuals=1, retries=0, child_cap_seconds=job['suggested_cap_seconds'],
        reference_scope=job['reference_scope'], qualifications=job['qualifications'])
    if job['case_id'] == 'AE-2':
        prepared['cases'][0].update(kind='source', nominal=job['nominal'], expected_elements=job['expected_elements'])
        prepared['archive'] = dict(script=job['source_script'], output=job['source_output'],
            coordinate=dict(id=job['coordinate_id'], beta_deg=job['condition']['beta'],
                commanded_IAS_m_s=job['condition']['speed'], archived_values=job['reference_row']['values']),
            raw_row=job['reference_row'])
        prepared['policy'] = POLICY
    else:
        reference = _read(job['reference_contract'])
        reference.update(condition=job['condition'], selected_reference=job['reference_row'],
            reference_values={o['name']:o['expected'] for o in job['observations']},
            half_units={o['name']:o['tolerance'] for o in job['observations']},
            scope=job['reference_scope'], cases=[dict(name=name, panels=job['panels'], archived_row=job['reference_row']['row'])])
        prepared['reference'] = reference
    _write(stage/'plan.json', prepared)
    # Existing AE2 worker requires this internal exact-plan dispatch receipt.
    _write(stage/'authorization.json', dict(authorized=True, plan_sha256=_pin(stage/'plan.json')['sha256'],
        origin='Current suite invoked this one-job worker; no old pilot authorization is reused.'))
    _write(stage/'adapter-job.json', job)
    return prepared


def _load(path):
    spec = importlib.util.spec_from_file_location('_isae_suite_aeroelastic_worker', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(root, job):
    root = Path(root).resolve()
    canonical = _canonical(root, job)
    if canonical['execution_route'] == 'unsupported':
        return validate_blocked(root, canonical)
    stage = Path(tempfile.mkdtemp(prefix='openswing-isae-suite-aeroelastic-'+canonical['id']+'-'))
    _prepare_worker(root, canonical, stage)
    helper = _load(canonical['helper'])
    _require(helper.ROOT == root, 'Worker would import a different checkout.')
    error = None
    with (stage/'run.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            helper.worker(stage, canonical['mesh'])
        except Exception as exc:
            error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    folder = stage/'cases'/canonical['mesh']
    report = _read(folder/'report.json') if (folder/'report.json').is_file() else None
    stable = all(_pin(p['path']) == p for p in canonical['source_pins']+canonical['kernel_pins'])
    values = report.get('values', report.get('outputs', {})) if report else {}
    checks = _checks(canonical, values)
    physical = report.get('checks', []) if report else []
    numerical = bool(error is None and stable and physical and all(c['passed'] is True for c in physical)
                     and all(c['predicted'] is not None for c in checks))
    result = dict(id=canonical['id'], case_id=canonical['case_id'], adapter='aeroelastic',
        status='computed' if numerical else 'numerical_failure', numerical_pass=numerical,
        reference_match=numerical and all(c['passed'] for c in checks), reference_checks=checks,
        physical_checks=physical, worker_report=report, error=error, source_pins_unchanged=stable,
        artifact_directory=str(stage), artifact_files=[_pin(p) for p in sorted(stage.rglob('*')) if p.is_file()],
        operation_evidence=dict(worker_started=(folder/'started.json').exists(),
            cold_result_saved=(folder/'result.json').exists(), fresh_fields_saved=(folder/'fresh-fields.npz').exists()),
        expected_operations=canonical['expected_operations'], historical_settings_recovered=False,
        historical_unknowns=canonical['historical_unknowns'], qualifications=canonical['qualifications'],
        reference_scope=canonical['reference_scope'])
    _write(stage/'adapter-result.json', result)
    return result


def mesh_diagnostics(jobs, results):
    """Aggregate saved results with the prior unchanged family mesh gates."""
    groups = {}
    for job in jobs:
        if job.get('adapter') == 'aeroelastic':
            groups.setdefault(job['mesh_group'], []).append(job)
    records = []
    for group, pair in sorted(groups.items()):
        pair = sorted(pair, key=lambda j:j['mesh_order'])
        _require(len(pair) == 2 and pair[0]['mesh_gate'] == pair[1]['mesh_gate'], 'Incomplete declared mesh pair.')
        packets = [results.get(j['id'], {}) for j in pair]
        record = dict(group=group, jobs=[j['id'] for j in pair], gate=pair[0]['mesh_gate'])
        if any(p.get('status') != 'computed' for p in packets):
            record.update(status='UNAVAILABLE', passed=False, reason='Both finite physical states are required; missing/unrun/failed states are not a mesh pass.')
        else:
            values = [{c['name']:c['predicted'] for c in p['reference_checks']} for p in packets]
            changes = {}
            for key in pair[0]['mesh_gate']['channels']:
                coarse, fine = (v[key] for v in values)
                delta = abs(fine-coarse)
                relative = delta/abs(fine) if fine else (0. if delta == 0. else None)
                changes[key] = dict(coarse=coarse, fine=fine, relative_change=relative,
                    passed=relative is not None and relative <= pair[0]['mesh_gate']['relative_limit'])
            record.update(status='COMPARED', channels=changes, passed=all(c['passed'] for c in changes.values()))
        records.append(record)
    return records
