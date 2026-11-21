"""Archived ISAE SA-1/2/3/4/5/7/8 polar jobs; importing/planning runs no physics.

Drivers are read as declarations, never executed.  Each printed row is its own
cold job on a reconstructed interval count using the numeric NODE/I node request
(or the documented 64 fallback), and twice that count.  These are not recovered
historical node arrays or circulation counts.  Printed precision is a reference
diagnostic, independent of numerical validity, mesh convergence and unresolved
historical settings.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import math
from pathlib import Path
import re
import time

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CASES = (1, 2, 3, 4, 5, 7, 8)
COLUMNS = ('index', 'time', 'alpha', 'lift', 'drag', 'CL', 'CD', 'CDi', 'Cm', 'efficiency')
OUTPUTS = COLUMNS[3:]
HEADER = ('i', 't', 'alpha', 'Lift', 'Drag', 'CL', 'CD', 'CDi', 'CM', 'span', 'eff.')
NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?\Z')
NODE_I_QUALIFICATION = (
    'ASWING v5.67 revision notes (22 Jan 2007, .reference/version_notes.txt:591-598) '
    'identify NODE/I as a requested node count, which can increase to fit breakpoints; '
    'it does not declare an interval count or circulation K.')
NODE_MESH_SOURCE = (
    'interval-count reconstruction using the numeric NODE/I node request; '
    'historical node array and circulation K unknown')
FALLBACK_MESH_SOURCE = (
    'fallback64 interval-count reconstruction; no NODE/I node request retained; '
    'historical node array and circulation K unknown')
RECONSTRUCTED_INFLUENCE_QUALIFICATION = (
    'Mach=0 and current influence geometry are fixed reconstruction choices. Historical startup/settings, including the state before driver F toggles, remain unresolved.')
QUALIFICATIONS = [
    'The unchanged original model/table/driver are pinned; the shell driver is never executed.',
    'Incidence is the archived table token at its exact printed center; driver incidence tokens are retained separately.',
    'Density is the original model Constant rhoSL with an explicit sea-level reconstruction assumption, not a recovered historical atmosphere.',
    RECONSTRUCTED_INFLUENCE_QUALIFICATION,
    NODE_I_QUALIFICATION,
    'The numeric node request is reused as the current nominal interval count and doubled, without subtracting one; this is a reconstruction choice, not recovered historical node placement or circulation K. Current mesh rules and default natural-v1 interpolation apply.',
    'A seven-column precision match alone does not certify historical setup, continuum convergence, or an entire case family.',
]


def _pin(path, root):
    data = path.read_bytes()
    return {'path': path.relative_to(root).as_posix(), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def _number(token):
    if not NUMBER.fullmatch(token):
        raise ValueError(f'Unsupported numeric token {token!r}')
    value = float(token.replace('D', 'E').replace('d', 'e'))
    if not math.isfinite(value):
        raise ValueError(f'Nonfinite numeric token {token!r}')
    return value


def printed_value(token):
    """Finite printed center and half of its last displayed decimal place.

    Explicit nonfinite/overflow exports remain unavailable, never zero.  Other
    malformed tokens are rejected rather than silently dropping their rows.
    """
    if token.lower().lstrip('+-') in ('nan', 'inf', 'infinity') or re.fullmatch(r'\*+', token):
        return {'token': token, 'value': None, 'tolerance': None,
                'unavailable_reason': 'Archived field is nonfinite or a printed overflow marker.'}
    value = _number(token)
    decimal = Decimal(token.replace('D', 'E').replace('d', 'e'))
    tolerance = float(Decimal(5).scaleb(decimal.as_tuple().exponent - 1))
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError(f'Unrepresentable printed precision {token!r}')
    return {'token': token, 'value': value, 'tolerance': tolerance}


def decode_polar(text):
    """Return rows only for the exact archived ten-column header, else None."""
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines)
               if line.lstrip().startswith('#') and tuple(line.lstrip()[1:].split()) == HEADER]
    if not headers:
        return None
    if len(headers) != 1:
        raise ValueError('Expected exactly one recognized polar header.')
    rows = []
    for index, line in enumerate(lines[headers[0] + 1:], headers[0] + 2):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        tokens = line.split()
        if len(tokens) != 10:
            raise ValueError(f'Line {index}: polar row requires exactly ten columns.')
        try:
            fields = {name: printed_value(token) for name, token in zip(COLUMNS, tokens)}
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f'Line {index}: malformed polar row: {exc}') from exc
        for name in ('index', 'time', 'alpha'):
            if fields[name]['value'] is None:
                raise ValueError(f'Line {index}: unavailable required coordinate {name}.')
        sequence = fields['index']['value']
        if sequence < 1 or not sequence.is_integer():
            raise ValueError(f'Line {index}: invalid archived row index.')
        rows.append({'row_index': len(rows), 'line_number': index, 'tokens': tokens,
                     'fields': fields})
    if not rows:
        raise ValueError('Recognized polar table has no data rows.')
    return rows


def _command_values(lines, command):
    values = []
    for i, line in enumerate(lines):
        parts = line.split()
        if parts and parts[0].upper() == command:
            if len(parts) == 2:
                values.append(parts[1])
            elif len(parts) == 1:
                following = next((x for x in lines[i + 1:] if x), '')
                if len(following.split()) != 1:
                    raise ValueError(f'Missing scalar {command} declaration.')
                values.append(following)
            else:
                raise ValueError(f'Ambiguous {command} declaration.')
    return values


def decode_driver(text):
    """Bounded declaration reader, deliberately not a shell interpreter."""
    launches = re.findall(r'(?:^|[/\s])aswing\s+([A-Za-z0-9_.+-]+)\s*<<\s*[\"\']?([A-Za-z0-9_]+)[\"\']?\s*$', text, re.M)
    if len(launches) != 1:
        raise ValueError('Expected one literal ASWING model/heredoc invocation.')
    model, delimiter = launches[0]
    match = re.search(r'<<\s*[\"\']?' + re.escape(delimiter) + r'[\"\']?\s*\n(.*?)^' + re.escape(delimiter) + r'\s*$', text, re.M | re.S)
    if not match:
        raise ValueError('Missing complete driver heredoc.')
    lines = [line.strip() for line in match[1].splitlines()]
    speeds = _command_values(lines, '!V')
    if not speeds or len({_number(token) for token in speeds}) != 1 or _number(speeds[0]) <= 0:
        raise ValueError('Driver must declare one unique positive speed.')
    outputs = []
    for i, line in enumerate(lines):
        if line.lower() == 'w':
            value = next((x for x in lines[i + 1:] if x), '')
            if not re.fullmatch(r'[A-Za-z0-9_.+-]+', value):
                raise ValueError('Unsupported nonliteral driver output filename.')
            outputs.append(value)
    node_tokens = []
    for i, line in enumerate(lines):
        if line.upper() == 'NODE':
            end = next((j for j in range(i + 1, len(lines)) if lines[j].upper() == 'OPER'), len(lines))
            node_tokens.extend(_command_values(lines[i + 1:end], 'I'))
    if len(node_tokens) > 1:
        raise ValueError('Multiple NODE/I mesh declarations are ambiguous.')
    requested_nodes = None
    if node_tokens:
        number = _number(node_tokens[0])
        if number < 1 or not number.is_integer():
            raise ValueError('NODE/I count must be a positive integer.')
        requested_nodes = int(number)
    return {'model_file': model if model.endswith('.asw') else model + '.asw',
            'output_files': outputs, 'speed': _number(speeds[0]), 'speed_tokens': speeds,
            'requested_nodes': requested_nodes, 'node_count_token': node_tokens[0] if node_tokens else None,
            'alpha_tokens': _command_values(lines, '!A')}


def _rho_sl(text):
    lines = [line.split('#', 1)[0].strip() for line in text.splitlines()]
    locations = [i for i, line in enumerate(lines) if line.lower() == 'constant']
    if len(locations) != 1:
        raise ValueError('Original model must contain one Constant block.')
    start = locations[0] + 1
    end = next((i for i in range(start, len(lines)) if lines[i].lower() == 'end'), None)
    fields = ' '.join(lines[start:end]).split() if end is not None else []
    if len(fields) != 3:
        raise ValueError('Expected three literal Constant entries.')
    rho = _number(fields[1])
    if rho <= 0:
        raise ValueError('rhoSL must be positive.')
    return rho, fields[1]


def plan(root):
    root = Path(root).resolve()
    base = root / '.reference/isae-validation' / REVISION / '1 - Aerodynamics/SA - Steady Aerodynamics Cases'
    jobs = []
    table_count = 0
    for case in CASES:
        folders = sorted(base.glob(f'SA - {case} - *'))
        if len(folders) != 1:
            raise ValueError(f'Expected one original SA-{case} directory.')
        for table in sorted(folders[0].rglob('*.txt')):
            rows = decode_polar(table.read_text())
            if rows is None:
                continue
            matches = []
            for driver in sorted(table.parent.glob('*.sh')):
                declaration = decode_driver(driver.read_text())
                if declaration['output_files'].count(table.name) == 1:
                    matches.append((driver, declaration))
                elif table.name in declaration['output_files']:
                    raise ValueError(f'Driver writes table more than once: {driver}')
            if len(matches) != 1:
                raise ValueError(f'Expected one adjacent driver declaring output {table.name}.')
            driver, declaration = matches[0]
            model = table.parent / declaration['model_file']
            if not model.is_file():
                raise ValueError(f'Declared original model missing: {model}')
            rho, rho_token = _rho_sl(model.read_text())
            sources = [_pin(path, root) for path in (model, table, driver)]
            nominal = declaration['requested_nodes'] or 64
            table_count += 1
            for row in rows:
                for level, count in enumerate((nominal, 2 * nominal)):
                    settings = {'panels': count, 'mesh_level': level, 'base_panels': nominal,
                                'mesh_source': NODE_MESH_SOURCE if declaration['requested_nodes'] else FALLBACK_MESH_SOURCE,
                                'alpha': row['fields']['alpha']['value'], 'alpha_token': row['fields']['alpha']['token'],
                                'speed': declaration['speed'], 'density': rho, 'density_token': rho_token,
                                'density_assumption': 'model Constant rhoSL; sea level assumed',
                                'mach': 0., 'freeze_influences': False, 'beta': 0.,
                                'beam_interpolation': 'natural-v1', 'circulation_method': 'auto',
                                'stall': True, 'stall_factor': 40., 'stall_width': .05,
                                'wake_core_ratio': .25, 'aero_lag': True, 'body_added_mass_factor': 1.}
                    jobs.append({'id': f'SA-{case}:{table.stem}:row{row["row_index"]:03d}:n{count}',
                                 'case_id': f'SA-{case}', 'adapter': 'polars',
                                 'model_path': sources[0]['path'], 'table_path': sources[1]['path'],
                                 'driver_path': sources[2]['path'], 'row_index': row['row_index'],
                                 'expected_outputs': 7, 'settings': settings, 'sources': sources,
                                 'reference_row': row, 'driver_declarations': declaration,
                                 'qualifications': list(QUALIFICATIONS)})
    if table_count != 10:
        raise ValueError(f'Expected all ten original polar tables; found {table_count}.')
    if len({job['id'] for job in jobs}) != len(jobs):
        raise ValueError('Nonunique polar job identifiers.')
    return jobs


def reference_checks(predicted, row):
    checks = []
    for name in OUTPUTS:
        ref = row['fields'][name]
        value = predicted.get(name)
        available = value is not None and math.isfinite(value) and ref['value'] is not None
        error = abs(value - ref['value']) if available else None
        checks.append({'name': name, 'predicted': value if value is not None and math.isfinite(value) else None,
                       'expected': ref['value'], 'expected_token': ref['token'],
                       'abs_error': error, 'tolerance': ref['tolerance'],
                       'passed': bool(available and error <= ref['tolerance']),
                       **({} if available else {'unavailable_reason': ref.get('unavailable_reason',
                          'Current solver did not provide a finite field; no value was substituted.')})})
    return checks


def reconstructed_wrench(model, result):
    """All reported aerodynamic loads about the declared moment reference.

    Distributed body loads are already in strips.  Shoulders, point-object
    drag and engine wrenches are separate; none may be omitted or counted twice.
    """
    import numpy as np
    force, moment = np.zeros(3), np.zeros(3)
    counts = {}
    for key in ('strips', 'body_shoulders', 'engines'):
        rows = result.get(key, [])
        counts[key] = len(rows)
        for row in rows:
            load = np.asarray(row['force'])
            force += load
            moment += np.cross(np.asarray(row['position']) - model.reference[1], load) + row['moment']
    originals = model.records.get('weight', [])
    # Independently identify exactly null objects from the scaled ASW fields.
    # The solver omits these massless, dragless, volumeless, zero-inertia
    # records from its analysis view, while retaining every original record.
    # Match that ordering without dropping a nonzero (however small) load.
    weights = []
    for weight in originals:
        values = np.asarray(weight)
        null = (values.shape == (17,) and np.all(np.isfinite(values))
                and np.all(values[5:17] == 0))
        if not null:
            weights.append(weight)
    if len(weights) != len(originals):
        counts['omitted_null_point_records'] = len(originals)-len(weights)
    points = result.get('point_forces', [])
    if len(weights) != len(points):
        raise ValueError('Point force/weight position count mismatch.')
    counts['point_forces'] = len(points)
    for weight, load in zip(weights, points):
        force += load
        moment += np.cross(np.asarray(weight[2:5]) - model.reference[1], load)
    return force, moment, counts


def run(root, job):
    """Exactly one cold production call; numerical failures cannot pass."""
    root = Path(root).resolve()
    start = time.monotonic()
    report = {key: job[key] for key in ('id', 'case_id', 'adapter', 'model_path', 'table_path',
                                       'driver_path', 'row_index', 'expected_outputs', 'settings', 'sources', 'qualifications')}
    report.update(status='error', reference_match=False, reference_checks=[], numerical_checks=[],
                  physical_calls=0, reference_scope='Seven printed polar outputs only; historical settings unresolved.')
    try:
        for item in job['sources']:
            if _pin(root / item['path'], root) != item:
                raise ValueError('Pinned source changed: ' + item['path'])
        # Deliberately lazy: inventory and decoder tests require only stdlib.
        import numpy as np
        from openswing import asw, aero
        for module in (asw, aero):
            if Path(module.__file__).resolve() != root / 'openswing' / (module.__name__.split('.')[-1] + '.py'):
                raise ValueError('Production import did not resolve to the declared repository.')
        parse_asw, FlightCondition, solve_rigid = asw.parse_asw, aero.FlightCondition, aero.solve_rigid
        model = parse_asw((root / job['model_path']).read_text(), beam_interpolation='natural-v1')
        s = job['settings']
        if float(model.constants[1]) != s['density']:
            raise ValueError('rhoSL declaration/parser mismatch.')
        condition = FlightCondition(**{key: s[key] for key in ('speed', 'alpha', 'beta', 'density', 'mach',
            'freeze_influences', 'stall', 'stall_factor', 'stall_width', 'wake_core_ratio', 'aero_lag', 'body_added_mass_factor')})
        report['physical_calls'] = 1
        result = solve_rigid(model, condition, panels=s['panels'], circulation_method=s['circulation_method'])
        checks = report['numerical_checks']
        checks.append({'name': 'no parser diagnostics', 'passed': not model.diagnostics, 'diagnostics': list(model.diagnostics)})
        checks.append({'name': 'converged', 'passed': bool(result['converged'])})
        residual = float(result['residual'])
        checks.append({'name': 'circulation residual', 'value': residual if math.isfinite(residual) else None,
                       'tolerance': 1e-8, 'passed': math.isfinite(residual) and residual <= 1e-8})
        force, moment, wrench_counts = reconstructed_wrench(model, result)
        alpha = np.deg2rad(s['alpha'])
        qS = .5 * condition.density * condition.speed ** 2 * model.reference[0, 0]
        lift = float(force @ [-np.sin(alpha), 0., np.cos(alpha)])
        drag = float(force @ [np.cos(alpha), 0., np.sin(alpha)])
        errors = {'CL force normalization': abs(lift / qS - result['CL']),
                  'CD force normalization': abs(drag / qS - result['CD']),
                  'Cm moment normalization': abs(moment[1] / (qS * model.reference[0, 1]) - result['Cm']),
                  'origin Cm moment normalization': abs((moment + np.cross(model.reference[1], force))[1]
                      / (qS * model.reference[0, 1]) - result['Cm_origin']),
                  'reconstructed origin moment': np.max(abs(moment + np.cross(model.reference[1], force)
                      - result['moment_origin'])) / (qS * model.reference[0, 1]),
                  'near-field drag decomposition': abs(result['CD'] - sum(result[key] for key in
                      ('CDi_near', 'CDp', 'CDbody', 'CDam', 'CDeng', 'CDrate'))),
                  'reconstructed total force': np.max(abs(force - result['force'])) / qS,
                  'reconstructed total moment': np.max(abs(moment - result['moment'])) / (qS * model.reference[0, 1])}
        for name, error in errors.items():
            error = float(error)
            checks.append({'name': name, 'value': error if math.isfinite(error) else None,
                           'tolerance': 2e-10, 'passed': math.isfinite(error) and error <= 2e-10})
        predicted = {'lift': lift, 'drag': drag, **{key: None if result.get(key) is None else float(result[key])
                                                  for key in OUTPUTS[2:]}}
        # Native polar CM follows the origin aerodynamic moment in steady
        # eqs. 221/225, distinct from the reference moment constraint (187).
        predicted['Cm'] = float(result['Cm_origin'])
        report['output_mapping'] = dict(Cm=dict(native_header='CM', production_field='Cm_origin',
            reference='body origin', evidence='Steady theory equations 221/225; user guide Reference-Parameter Listing.'))
        report['reference_checks'] = reference_checks(predicted, job['reference_row'])
        report['unsupported_outputs'] = [x for x in report['reference_checks'] if 'unavailable_reason' in x]
        report['numerical_pass'] = all(check['passed'] for check in checks)
        report['status'] = 'computed' if report['numerical_pass'] else 'numerical_failure'
        report['reference_match'] = report['numerical_pass'] and all(x['passed'] for x in report['reference_checks'])
        report['result'] = {'predicted': {key: value if value is None or math.isfinite(value) else None for key, value in predicted.items()},
                            'residual': residual if math.isfinite(residual) else None,
                            'panels': result['panels'], 'mesh_discretization': result.get('mesh_discretization'),
                            'reference': model.reference.tolist(), 'force': force.tolist(), 'moment': moment.tolist(),
                            'moment_origin': result['moment_origin'], 'Cm_reference': result['Cm'],
                            'wrench_component_counts': wrench_counts,
                            'coefficient_definitions': result.get('coefficient_definitions'),
                            'circulation_solver': result.get('circulation_solver')}
    except Exception as exc:
        report.update(status='error', reference_match=False, numerical_pass=False,
                      error_type=type(exc).__name__, error=str(exc))
    finally:
        try:
            stable = all(_pin(root / item['path'], root) == item for item in job['sources'])
        except OSError:
            stable = False
        report['sources_unchanged'] = stable
        if not stable:
            report.update(status='source_mismatch', reference_match=False, numerical_pass=False)
        report['seconds'] = time.monotonic() - start
    nonfinite = []
    def clean(value, path=''):
        if isinstance(value, float) and not math.isfinite(value):
            nonfinite.append(path)
            return None
        if isinstance(value, dict):
            return {key: clean(item, f'{path}.{key}' if path else key) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(item, f'{path}[{index}]') for index, item in enumerate(value)]
        return value
    report = clean(report)
    report['nonfinite_fields'] = nonfinite
    if nonfinite:
        report.update(status='numerical_failure', numerical_pass=False, reference_match=False)
    return report
