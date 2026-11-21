"""Ordered steady operating points with inherited specifications and checked seeds.

ASWING's public guide, OPER: '+' inherits the previous point's settings;
'XX' computes the complete stack. This JSON workflow does not decode .pnt/.set
memory dumps or infer a native continuation/branch-selection algorithm.
"""
from copy import deepcopy
from dataclasses import asdict, fields
import json
import math
from types import SimpleNamespace

from .aero import FlightCondition, _validate as validate_flight
from .numerical_policy import SOURCE_OPERATORS, SOURCE_COUPLED, SOURCE_AIRFLOW, validate_source_request
from .operating import OperatingConstraint, OperatingSystem


MAX_POINTS = 200
_MAPS = {'controls', 'powers', 'circulation_modes'}
_VECTORS = {'rates', 'acceleration', 'angular_acceleration', 'position_earth', 'attitude', 'ground_normal'}
_BOOLEANS = {'stall', 'aero_lag', 'freeze_influences'}
_NULLABLE = {'density', 'mach', 'gravity_magnitude'}
_FIELDS = {item.name for item in fields(FlightCondition)}
_REQUEST_KEYS = {'action', 'source', 'panels', 'numerics', 'mode', 'condition',
    'operating_points', 'operating_constraints', 'gravity', 'loads', 'strut_mode',
    'controller', 'derivatives', 'initial_state', 'circulation_method', 'tolerance', 'continuation_steps',
    'fourier_wake_diagnostic'}


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number.')


def _vector(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f'{label} must contain three finite numbers.')
    for item in value:
        _number(item, label)


def _channels(value, name):
    if not isinstance(value, dict):
        raise ValueError(f'Condition {name} must map positive indices to values.')
    result = {}
    for key, item in value.items():
        if isinstance(key, bool) or not (isinstance(key, int) or isinstance(key, str) and key.isdecimal()):
            raise ValueError(f'Condition {name} requires positive integer indices.')
        index = int(key)
        if index <= 0 or index in result:
            raise ValueError(f'Condition {name} has an invalid or duplicate index.')
        _number(item, name)
        if name == 'circulation_modes' and (not isinstance(item, int) or not 0 <= item <= 512):
            raise ValueError('Circulation modes must be integers from 0 to 512.')
        result[index] = item
    return result


def _condition(previous, override):
    if not isinstance(override, dict) or set(override)-_FIELDS:
        raise ValueError('Point condition must contain only FlightCondition fields.')
    result = deepcopy(previous)
    for key, value in override.items():
        if key in _MAPS:
            result[key].update(_channels(value, key))
        elif key in _VECTORS:
            _vector(value, key)
            result[key] = list(value)
        elif key in _BOOLEANS:
            if not isinstance(value, bool):
                raise ValueError(f'Condition {key} must be boolean.')
            result[key] = value
        elif key == 'gust':
            if value is not None and not isinstance(value, dict):
                raise ValueError('Condition gust must be an object or null.')
            result[key] = deepcopy(value)
        elif key == 'sensor_flow':
            if value not in ('full', 'kinematic'):
                raise ValueError('Sensor flow must be full or kinematic.')
            result[key] = value
        else:
            if value is not None or key not in _NULLABLE:
                _number(value, key)
            result[key] = value
    if result['speed'] <= 0:
        raise ValueError('Flight speed must be positive.')
    if result['ground_effect'] not in (-1, 0, 1):
        raise ValueError('Ground effect must be -1, 0 or 1.')
    return result


def _constraints(value):
    if not isinstance(value, (list, tuple)) or len(value) > 200:
        raise ValueError('Operating constraints must be a list of at most 200 records.')
    allowed = {item.name for item in fields(OperatingConstraint)}
    for row in value:
        if not isinstance(row, dict) or not {'variable', 'quantity'} <= set(row) or set(row)-allowed:
            raise ValueError('Operating constraints require variable, quantity and supported target options.')
        for key in ('variable', 'quantity'):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError(f'Constraint {key} must be nonempty text.')
        for key in ('target', 'weight', 'preferred', 'residual_scale'):
            if key in row and (row[key] is not None or key in ('target', 'weight', 'preferred')):
                _number(row[key], 'Constraint '+key)
        for key in ('expression', 'unit'):
            if key in row and row[key] is not None and not isinstance(row[key], str):
                raise ValueError(f'Constraint {key} must be text or null.')
    return deepcopy(list(value))


def prepare_points(request, policy):
    """Resolve every specification and reject invalid packets before any solve."""
    if set(request)-_REQUEST_KEYS:
        raise ValueError('Unsupported operating-point request options: '+', '.join(sorted(set(request)-_REQUEST_KEYS))+'.')
    if not isinstance(request.get('source'), str) or not request['source'].strip():
        raise ValueError('An operating-point stack requires ASW source text.')
    # Check finite JSON before copying or allowing a later malformed row to
    # leave the user with a partially computed stack.
    try:
        json.dumps(request, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Operating-point inputs must be finite JSON data.') from exc
    mode = request.get('mode', 'rigid')
    if mode not in ('rigid', 'mounted'):
        raise ValueError('Operating-point stacks support rigid or mounted steady analysis only.')
    if request.get('initial_state') is not None:
        raise ValueError('Operating-point stacks do not yet accept an external initial_state; use previous-point initialization within the stack.')
    options = request.get('operating_points')
    if not isinstance(options, dict) or 'points' not in options or set(options)-{'points', 'initialization'}:
        raise ValueError('operating_points requires points and an optional initialization choice.')
    initialization = options.get('initialization', 'cold')
    if initialization not in ('cold', 'previous'):
        raise ValueError('Operating-point initialization must be cold or previous.')
    if initialization == 'previous' and request.get('circulation_method') == 'continuation':
        raise ValueError('Previous-point initialization cannot accompany explicit circulation continuation; use auto or direct.')
    points = options['points']
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_POINTS:
        raise ValueError(f'Use between 1 and {MAX_POINTS} operating points.')
    if request.get('strut_mode', 'bilateral') not in ('bilateral', 'wire'):
        raise ValueError('Strut mode must be bilateral or wire.')
    if request.get('gravity') is not None:
        _vector(request['gravity'], 'Gravity')
    if not isinstance(request.get('loads', []), (list, tuple)):
        raise ValueError('Loads must be a list of applied-load records.')
    for row in request.get('loads', []):
        if not isinstance(row, dict) or not {'beam', 't'} <= set(row) or set(row)-{'beam', 't', 'force', 'moment'}:
            raise ValueError('Applied loads require beam, t and optional force/moment vectors.')
        if isinstance(row['beam'], bool) or not isinstance(row['beam'], int) or row['beam'] <= 0:
            raise ValueError('Applied-load beam must be a positive integer.')
        _number(row['t'], 'Applied-load station')
        for key in ('force', 'moment'):
            if key in row:
                _vector(row[key], 'Applied-load '+key)
    for key in ('controller', 'derivatives'):
        if request.get(key) is not None and not isinstance(request[key], dict):
            raise ValueError(f'{key} must be an object or null.')
    if mode == 'rigid':
        if (request.get('gravity') is not None or request.get('loads') or
                any(request.get(key) is not None for key in ('controller', 'derivatives')) or
                request.get('strut_mode', 'bilateral') != 'bilateral'):
            raise ValueError('Rigid operating points do not support mounted loads, gravity overrides, controllers, derivatives or strut options.')
        if request.get('circulation_method', 'auto') not in ('auto', 'direct', 'continuation'):
            raise ValueError('Unknown circulation solve method.')
    elif 'circulation_method' in request:
        raise ValueError('Mounted operating points do not accept a separate circulation_method.')
    if {'tolerance', 'continuation_steps'}.intersection(request):
        if policy['structural_operator'] not in (SOURCE_COUPLED, SOURCE_AIRFLOW):
            raise ValueError('This single-point route exposes tolerance/continuation_steps only for the source-coupled policy.')
        if 'tolerance' in request:
            _number(request['tolerance'], 'Tolerance')
            if not 0 < request['tolerance'] <= 1e-5:
                raise ValueError('Tolerance must be positive and no greater than 1e-5.')
        if 'continuation_steps' in request and (isinstance(request['continuation_steps'], bool) or
                not isinstance(request['continuation_steps'], int) or request['continuation_steps'] < 1):
            raise ValueError('Continuation steps must be a positive integer.')
    condition = _condition(asdict(FlightCondition()), request.get('condition', {}))
    constraints = _constraints(request.get('operating_constraints', []))
    base = {key: deepcopy(value) for key, value in request.items() if key != 'operating_points'}
    base.update(action='solve', mode=mode)
    resolved = []
    for index, point in enumerate(points):
        if not isinstance(point, dict) or set(point)-{'name', 'condition', 'operating_constraints'}:
            raise ValueError(f'Point {index+1} accepts only name, condition and operating_constraints.')
        name = point.get('name', f'Point {index+1}')
        if not isinstance(name, str) or not name.strip() or len(name) > 160:
            raise ValueError('Point names must contain 1 to 160 characters.')
        condition = _condition(condition, point.get('condition', {}))
        if 'operating_constraints' in point:
            constraints = _constraints(point['operating_constraints'])
        if mode == 'rigid' and constraints:
            raise ValueError('Operating constraints require mounted operating points.')
        single = {**base, 'condition': deepcopy(condition), 'operating_constraints': deepcopy(constraints)}
        if policy['structural_operator'] in SOURCE_OPERATORS:
            validate_source_request(single)
        resolved.append(dict(index=index, name=name, request=single))
    return resolved


def _derivatives(options, model, condition, feedback):
    if options is None:
        return
    if set(options)-{'response', 'basis', 'parameters', 'axes', 'step'}:
        raise ValueError('Unsupported derivative options.')
    if options.get('response', 'fixed_acceleration') not in ('fixed_acceleration', 'free_flight'):
        raise ValueError('Derivative response must be fixed_acceleration or free_flight.')
    if (options.get('basis', 'standard') not in ('standard', 'body', 'body_origin') or
            options.get('axes', 'stability') not in ('body', 'stability', 'reverse_stability')):
        raise ValueError('Unsupported derivative input basis or output axes.')
    step = options.get('step', 1e-5)
    _number(step, 'Derivative step')
    if not 1e-7 <= step <= 1e-3:
        raise ValueError('Derivative step must be between 1e-7 and 1e-3.')
    if options.get('parameters') is not None:
        from .derivatives import parameter_catalog
        names = set(parameter_catalog(model, condition))
        if feedback is not None:
            for row in feedback.outputs:
                names.remove(('control.' if row['attribute'] == 'controls' else 'power.')+str(row['index']))
                names.add('command.'+row['actuator'])
            names.update('command.'+name for name in feedback.signals)
        parameters = options['parameters']
        if (not isinstance(parameters, (list, tuple)) or not parameters or
                any(not isinstance(name, str) or name not in names for name in parameters) or
                len(set(parameters)) != len(parameters)):
            raise ValueError('Derivative parameters must be distinct supported state, control or command names.')


def _validate_points(model, points, panels):
    """Reuse condition, controller and constraint validators without a solve."""
    from .geometry import model_meshes
    beam_ids = {beam.index for beam in model.beams}
    loads = points[0]['request'].get('loads', ())
    for load in loads:
        beam = next((beam for beam in model.beams if beam.index == load['beam']), None)
        if beam is None or not beam.domain[0] <= load['t'] <= beam.domain[1]:
            raise ValueError('Applied-load station must lie on its declared beam.')
    # Validate global explicit-node endpoints/attachments and the exact interval
    # counts before solving any point; no aerodynamic field is evaluated here.
    meshes = model_meshes(model, panels, loads)
    checked_modes = set()
    for point in points:
        request = point['request']
        condition = FlightCondition(**request['condition'])
        validate_flight(model, condition)
        from .atmosphere import operating_air
        mach = operating_air(model, condition)['ambient_mach'] if condition.mach is None else condition.mach
        if not 0 <= mach < 1:
            raise ValueError('Prandtl–Glauert Mach must be in [0, 1).')
        for key, allowed in [('controls', set(model.controls)), ('powers', set(model.engine_controls)),
                             ('circulation_modes', beam_ids)]:
            if set(getattr(condition, key))-allowed:
                raise ValueError(f'Point {point["index"]+1} {key} refers to undeclared indices.')
        modes = tuple(sorted(condition.circulation_modes.items()))
        if modes and modes not in checked_modes:
            from .circulation import CirculationBasis
            CirculationBasis(meshes, condition.circulation_modes)
            checked_modes.add(modes)
        extra, feedback = {}, None
        if request.get('controller') is not None:
            from .feedback import FeedbackSystem
            feedback = FeedbackSystem(SimpleNamespace(model=model, condition=condition), request['controller'])
            if set(feedback.signals)-set(request['controller'].get('commands', {})):
                # Such commands are defined by the single-point loaded-state
                # initialization, not by a prescribed number. Its warm API
                # retains saved commands; using it would change this target.
                point['cold_start_reason'] = 'Implicit controller measurement commands require independent initialization.'
            extra = {f'command.{name}': (0., 1.) for name in feedback.signals}
            extra.update({f'command.{row["actuator"]}': (0., 1.) for row in feedback.outputs})
            owned = {('control.' if row['attribute'] == 'controls' else 'power.')+str(row['index']) for row in feedback.outputs}
            if any(row['variable'] in owned for row in request['operating_constraints']):
                raise ValueError('A controller-owned actuator must be trimmed through its command.')
        OperatingSystem(model, condition, condition.motion(), request['operating_constraints'],
                        max(float(model.reference[0, 2]), 1.), 1., additional_variables=extra)
        _derivatives(request.get('derivatives'), model, condition, feedback)


def _actual_condition(condition, result):
    actual = deepcopy(condition)
    for key, value in result.get('operating_values', {}).items():
        if key in ('speed', 'alpha', 'beta'):
            actual[key] = value
        elif '.' in key:
            group, axis = key.split('.', 1)
            if group in ('control', 'power'):
                actual[group+'s'][int(axis)] = value
            elif group in _VECTORS:
                axes = ('bank', 'elevation', 'heading') if group == 'attitude' else ('x', 'y', 'z')
                actual[group] = list(actual[group])
                actual[group][axes.index(axis)] = value
    for key, value in result.get('feedback', {}).get('actuators', {}).items():
        actual['controls' if key.startswith('F') else 'powers'][int(key[1:])] = value
    return actual


def solve_points(model, request, points, panels, policy, solve, progress=None):
    _validate_points(model, points, panels)
    rows = []
    total = len(points)
    initialization = request['operating_points'].get('initialization', 'cold')
    for point in points:
        index, name, single = point['index'], point['name'], point['request']
        single = deepcopy(single)
        start = dict(kind='cold', source_index=None, reason='Independent point requested.')
        if initialization == 'previous':
            if not rows:
                start['reason'] = 'First point in sequence.'
            elif not rows[-1]['converged']:
                start['reason'] = 'Previous point failed; no state is propagated across the gap.'
            elif single['condition']['circulation_modes'] != rows[-1]['condition']['circulation_modes']:
                start['reason'] = 'Circulation discretization changed.'
            elif point.get('cold_start_reason'):
                start['reason'] = point['cold_start_reason']
            elif single.get('controller') is not None and (
                    {c['variable'] for c in rows[-1]['operating_constraints'] if c['variable'].startswith('command.')} -
                    {c['variable'] for c in single['operating_constraints']}):
                # Saved controller commands are deliberately retained by the
                # single-point warm API. Releasing a trim command here must
                # instead restore this point's prescribed command/bias.
                start['reason'] = 'Controller command released from trim; use its prescribed setting.'
            else:
                previous = rows[-1]['result']
                if request.get('mode', 'rigid') == 'rigid':
                    single['initial_circulation'] = [strip['circulation'] for strip in previous['strips']]
                else:
                    single['initial_state'] = deepcopy(previous['equilibrium_state'])
                start = dict(kind='previous_point', source_index=rows[-1]['index'],
                             reason='Correct the preceding converged physical state at the new specifications.')
        row = dict(index=index, name=name, condition=deepcopy(single['condition']),
                   operating_constraints=deepcopy(single['operating_constraints']),
                   initialization=start, converged=False, result=None, error=None, actual_condition=None)
        if progress is not None:
            progress('operating_point', index+1, total)
        def nested(stage, current, count):
            progress('operating_point/'+stage, current, count)
        try:
            result = solve(model, deepcopy(single), FlightCondition(**deepcopy(single['condition'])),
                           panels, policy, nested if progress is not None else None)
            if policy['structural_operator'] in SOURCE_OPERATORS:
                result['numerics'] = dict(policy)
            row['result'] = result
            seed_report = result.get('circulation_solver', {}).get('initialization')
            if seed_report is not None:
                start['cold_fallback'] = seed_report['cold_fallback']
            row['converged'] = bool(result.get('converged', False))
            if row['converged']:
                row['actual_condition'] = _actual_condition(single['condition'], result)
            else:
                row['error'] = dict(type='AnalysisError', message='The single-point solver did not converge.')
        except (KeyboardInterrupt, SystemExit, MemoryError):
            raise
        except Exception as exc:
            row['converged'] = False
            row['actual_condition'] = None
            row['error'] = dict(type=type(exc).__name__, message=str(exc))
            details = getattr(exc, 'details', None)
            if details is not None:
                try:
                    row['error']['details'] = json.loads(json.dumps(details, allow_nan=False))
                except (TypeError, ValueError, OverflowError):
                    row['error']['details_text'] = repr(details)
        rows.append(row)
        if progress is not None:
            progress('operating_point_done' if row['converged'] else 'operating_point_failed', index+1, total)
    passed = sum(row['converged'] for row in rows)
    return dict(analysis='operating_points', mode=request.get('mode', 'rigid'),
                initialization=initialization, converged=passed == total, total_points=total,
                converged_points=passed, failed_points=total-passed, points=rows,
                panels=deepcopy(panels), numerics=dict(policy))
