"""Explicit, paired numerical policies at the JSON request boundary.

An omitted policy retains the historical application equations. ASW text does
not encode interpolation: an alternative must travel with every request and
must agree with any saved physical state used by that request.
"""
from .beam_spline import NATURAL, DRELA_SEGSPL
import math


MIDPOINT = 'midpoint-v1'
SOURCE_DISCRETE = 'drela-steady-zero-offset-v1'
SOURCE_SECTION = 'drela-steady-section-v1'
SOURCE_COUPLED = 'drela-steady-coupled-v1'
SOURCE_DYNAMIC = 'drela-fixed-vacuum-v1'
SOURCE_QUIESCENT = 'drela-fixed-still-air-v1'
SOURCE_MOVING = 'drela-moving-vacuum-v1'
SOURCE_AIRFLOW = 'drela-moving-airflow-v1'
SOURCE_MODAL = (SOURCE_DYNAMIC, SOURCE_QUIESCENT, SOURCE_MOVING, SOURCE_AIRFLOW)
SOURCE_OPERATORS = (SOURCE_DISCRETE, SOURCE_SECTION, SOURCE_COUPLED, *SOURCE_MODAL)
_KEYS = {'beam_interpolation', 'structural_operator'}


def default_policy():
    return dict(beam_interpolation=NATURAL, structural_operator=MIDPOINT)


def request_policy(request):
    """Resolve a complete supported pair without mutating the request."""
    if _KEYS.intersection(request):
        raise ValueError('Specify beam_interpolation and structural_operator together in request.numerics, not as top-level options.')
    if 'numerics' not in request:
        return default_policy()
    value = request['numerics']
    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ValueError('numerics must contain exactly beam_interpolation and structural_operator; partial or unknown policy keys are not supported.')
    interpolation, operator = value['beam_interpolation'], value['structural_operator']
    if not isinstance(interpolation, str) or interpolation not in (NATURAL, DRELA_SEGSPL):
        raise ValueError(f'Unknown beam interpolation policy: {interpolation!r}.')
    if not isinstance(operator, str) or operator not in (MIDPOINT, *SOURCE_OPERATORS):
        raise ValueError(f'Unknown structural operator policy: {operator!r}.')
    if (interpolation == NATURAL) != (operator == MIDPOINT):
        raise ValueError('Conflicting numerics pair: natural-v1 requires midpoint-v1; drela-segspl-v1 requires an explicit supported source structural operator.')
    return dict(value)


def validate_saved_policy(request, policy):
    """Reject policy mismatches before a route can ignore a saved state.

The physical-state reader still validates the complete packet and identity.
Only known state-bearing options and their packet wrappers are examined here.
"""
    if request.get('action') in ('extend_frequency', 'discard_frequency') and isinstance(request.get('session'), dict):
        session = request['session']
        saved = dict(beam_interpolation=session.get('beam_interpolation', NATURAL),
                     structural_operator=session.get('structural_operator', MIDPOINT))
        if saved != policy:
            raise ValueError('Frequency session numerical policy does not match request.numerics.')
    state_keys = ('initial_state', 'equilibrium_state', 'checkpoint')
    pending = [request[key] for key in state_keys if key in request]
    for key in ('frequency', 'modes', 'time', 'rom', 'stability'):
        options = request.get(key)
        if isinstance(options, dict):
            pending.extend(options[name] for name in state_keys if name in options)
    visited = set()
    while pending:
        value = pending.pop()
        if not isinstance(value, dict) or id(value) in visited:
            continue
        visited.add(id(value))
        identity = value.get('identity')
        if isinstance(identity, dict):
            saved = dict(beam_interpolation=identity.get('beam_interpolation', NATURAL),
                         structural_operator=identity.get('structural_operator', MIDPOINT))
            if saved != policy:
                raise ValueError('Saved state numerical policy does not match request.numerics; select its exact interpolation and structural operator or compute a new state.')
        pending.extend(value[key] for key in (*state_keys, 'context') if key in value)


def validate_source_steady_constraints(constraints, *, moving=False):
    """Keep source trim inside the selected operator's physical equations.

    Targets share OperatingSystem's full residual and validation, including
    custom sensor equations and equality-constrained control allocation.
    Only the moving operator can release frame rates and accelerations.
    """
    if not isinstance(constraints, (list, tuple)):
        raise ValueError('Source mounted operating constraints must be a list.')
    for row in constraints:
        variable = row.get('variable') if isinstance(row, dict) else getattr(row, 'variable', None)
        quantity = row.get('quantity') if isinstance(row, dict) else getattr(row, 'quantity', None)
        if not isinstance(variable, str) or not isinstance(quantity, str):
            raise ValueError('Source mounted operating constraints require variable and quantity strings.')
        if not moving and variable.startswith(('rates.', 'acceleration.', 'angular_acceleration.')):
            raise ValueError('Source mounted trim requires prescribed zero frame rates and accelerations.')


def validate_source_request(request):
    """Reject settings the selected bounded steady operator cannot honor."""
    operator = request_policy(request)['structural_operator']
    coupled = operator in (SOURCE_COUPLED, SOURCE_AIRFLOW)
    dynamic = operator in SOURCE_MODAL
    still_air = operator == SOURCE_QUIESCENT
    flowing = operator == SOURCE_AIRFLOW
    moving = operator in (SOURCE_MOVING, SOURCE_AIRFLOW)
    medium = 'still-air' if still_air else 'vacuum'
    action = request['action']
    if request.get('strut_mode', 'bilateral') not in ('bilateral', 'wire'):
        raise ValueError('Strut mode must be bilateral or wire.')
    common = {'action', 'source', 'panels', 'numerics'}
    specific = {
        'inspect': {'loads'},
        'vortex_preview': {'view'},
        'canonical_asw': set(),
        'distribution': {'beam', 'name'},
        'edit_distribution': {'beam', 'name', 'edit'},
        'solve': {'mode', 'condition', 'gravity', 'loads', 'initial_state',
                  'operating_constraints', 'controller', 'derivatives', 'strut_mode',
                  'tolerance', 'continuation_steps', 'continuation'},
    }
    if dynamic:
        if not flowing:
            specific.pop('solve')
        specific['modes'] = {'mode', 'condition', 'gravity', 'loads', 'modes',
                             'operating_constraints', 'strut_mode'}
        specific['frequency'] = {'mode', 'condition', 'gravity', 'loads', 'frequency',
                                 'operating_constraints', 'strut_mode', 'retain_frequency', 'frequency_spacing'}
        specific['extend_frequency'] = {'session', 'frequencies'}
        specific['discard_frequency'] = {'session', 'retain_model'}
    if moving:
        specific.update(time={'mode', 'condition', 'loads', 'initial_loads', 'time', 'strut_mode'},
                        launch_time={'mode', 'equilibrium_state', 'time'},
                        resume_time={'mode', 'checkpoint', 'time'})
    if action not in specific:
        if flowing:
            raise ValueError('Source airflow equations support inspection, editing, mounted steady trim, eigenmodes, frequency response and time response.')
        if dynamic:
            if moving:
                raise ValueError('Source moving vacuum equations support inspection, editing, eigenmodes, frequency and time response only; airflow is unavailable.')
            frame_scope = 'moving-frame' if moving else 'fixed-frame'
            raise ValueError(f'Source {medium} equations support inspection, distribution editing and {frame_scope} {medium} eigenmodes and frequency response only.')
        if coupled:
            raise ValueError('The source-coupled policy supports inspection, distribution editing and mounted steady solves only; dynamics, response and flow-survey actions are unavailable.')
        raise ValueError('The selected source-discrete numerical policy supports inspection, distribution editing and structural static solves only; aerodynamic, dynamic and flow-survey actions are unavailable.')
    unexpected = set(request)-common-specific[action]
    if unexpected:
        raise ValueError('Unsupported source-discrete request options: '+', '.join(sorted(unexpected))+'.')
    for load_key in ('loads', 'initial_loads'):
        if load_key not in request:
            continue
        loads = request[load_key]
        if load_key == 'initial_loads' and loads is None:
            continue
        if not isinstance(loads, (list, tuple)):
            raise ValueError('Source-discrete loads must be a list of beam/t nodal force or moment records.')
        for load in loads:
            if (not isinstance(load, dict) or not {'beam', 't'}.issubset(load)
                    or set(load)-{'beam', 't', 'force', 'moment'}):
                raise ValueError('Source-discrete loads support only beam, t, force and moment; frame, offset, follower and other load options are unavailable.')
    if moving and action in ('time', 'launch_time', 'resume_time'):
        _validate_moving_time_request(request, airflow=flowing)
        return
    if dynamic and action in ('modes', 'frequency'):
        if flowing:
            _validate_airflow_dynamic_request(request)
            return
        if request.get('mode', action) != action or request.get('condition') not in (None, {}):
            raise ValueError(f'Source {medium} modes require no FlightCondition; specify gravity and modal attitude directly.')
        if request.get('operating_constraints', ()) not in ((), []):
            raise ValueError(f'Source {medium} modes do not support operating constraints.')
        options = request.get(action, {})
        allowed = {'frame', 'step', 'matrices',
                   'vacuum', 'tolerance', 'continuation_steps', 'position', 'attitude',
                   'gravity_magnitude', 'initial_state', 'structured_base', 'controller', 'load_targets'}
        if action == 'modes':
            allowed.update(('count', 'shift', 'method', 'rank_tolerance'))
        else:
            allowed.discard('structured_base')
            allowed.update(('frequencies', 'inputs', 'initial_shift', 'initial_rank_tolerance'))
            if type(request.get('retain_frequency', False)) is not bool:
                raise ValueError('retain_frequency must be boolean.')
            if request.get('frequency_spacing', 'log') not in ('log', 'linear'):
                raise ValueError('Frequency display spacing must be log or linear.')
        if still_air:
            allowed.update(('quiescent_density', 'quiescent_body_added_mass_factor'))
        if moving:
            allowed.update(('velocity', 'motion'))
        if not isinstance(options, dict) or set(options)-allowed:
            raise ValueError(f'Unsupported source {medium} modal options.')
        if action == 'frequency':
            inputs = options.get('inputs')
            if not isinstance(inputs, (list, tuple)) or not inputs:
                raise ValueError('Source frequency response requires explicit initial disturbances or moving-frame inputs.')
            for value in inputs:
                initial = isinstance(value, dict) and value.get('kind') == 'initial'
                frame_input = (moving and options.get('frame', 'fixed') != 'fixed' and isinstance(value, str)
                    and value.startswith(('target.', 'acceleration.', 'angular_acceleration.')))
                if not initial and not frame_input:
                    raise ValueError('Source frequency inputs are structural initial disturbances or moving-frame loads/accelerations; airflow inputs are unavailable.')
        if moving:
            _validate_moving_modal_options(options)
            if request.get('gravity') is not None:
                raise ValueError(f'Source moving vacuum response specifies gravity_magnitude in {action}, not top-level gravity.')
        elif options.get('frame', 'fixed') != 'fixed':
            raise ValueError(f'Source {medium} modes require frame fixed.')
        if options.get('controller') is not None or (not moving and options.get('load_targets') not in (None, {})):
            raise ValueError(f'Source {medium} modes do not support controllers or frame load targets.')
        if still_air:
            from .quiescent import density_value
            from .body_apparent import coefficient
            density_value(options.get('quiescent_density'))
            coefficient(options.get('quiescent_body_added_mass_factor', 1.))
            if options.get('vacuum', False) is not False:
                raise ValueError('Source still-air modes require vacuum false.')
        elif options.get('vacuum', True) is not True:
            raise ValueError('Source vacuum modes cannot enable airflow.')
        return
    if action != 'solve':
        return
    if coupled:
        if request.get('mode') != 'mounted':
            raise ValueError('The source-coupled numerical policy requires solve mode mounted.')
        condition = request.get('condition')
        if not isinstance(condition, dict):
            raise ValueError('Source-coupled mounted analysis requires a FlightCondition object.')
        for name in ('rates', 'acceleration', 'angular_acceleration'):
            value = condition.get(name, (0., 0., 0.))
            if (not isinstance(value, (list, tuple)) or len(value) != 3
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) for v in value)):
                requirement = 'a finite xyz vector for' if flowing else 'zero'
                raise ValueError(f'Source-coupled mounted analysis requires {requirement} {name}.')
            if not flowing and any(v != 0 for v in value):
                raise ValueError(f'Source-coupled mounted analysis requires zero {name}.')
    else:
        if request.get('mode') != 'structural':
            raise ValueError('The source-discrete numerical policy requires solve mode structural; aerodynamic solves are unavailable.')
        if request.get('condition') not in (None, {}):
            raise ValueError('Source-discrete structural static analysis has no FlightCondition; specify gravity and loads directly.')
    scope = 'Source-coupled mounted analysis' if coupled else 'Source-discrete structural static analysis'
    if coupled:
        validate_source_steady_constraints(request.get('operating_constraints', ()), moving=flowing)
    elif request.get('operating_constraints', ()) not in ((), []):
        raise ValueError(f'{scope} does not support operating constraints.')
    for key in ('controller', 'derivatives'):
        if request.get(key) is not None and not flowing:
            raise ValueError(f'{scope} does not support {key}.')


def _validate_moving_modal_options(options, label='Source moving vacuum'):
    """Validate JSON motion and canonical frame targets before decoding Motion."""
    def finite(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)

    def vector(value, name):
        if not isinstance(value, (list, tuple)) or len(value) != 3 or not all(map(finite, value)):
            raise ValueError(f'{label} {name} must be a finite xyz vector.')

    frame = options.get('frame', 'fixed')
    if frame not in ('fixed', 'prescribed', 'free', 'mixed'):
        raise ValueError(f'{label} frame must be fixed, prescribed, free or mixed.')
    for name in ('velocity', 'position', 'attitude'):
        if name in options:
            vector(options[name], name)
    motion = options.get('motion')
    if motion is not None:
        names = {'rates', 'acceleration', 'angular_acceleration'}
        if not isinstance(motion, dict) or set(motion)-names:
            raise ValueError(f'{label} motion supports only rates, acceleration and angular_acceleration.')
        for name, value in motion.items():
            vector(value, name)
    gravity = options.get('gravity_magnitude')
    if gravity is not None and (not finite(gravity) or gravity < 0):
        raise ValueError(f'{label} gravity_magnitude must be finite and nonnegative, or null for file gravity.')
    targets = options.get('load_targets')
    if targets is None:
        targets = {}
    keys = {f'{kind}.{axis}' for kind in ('force', 'moment') for axis in 'xyz'}
    if not isinstance(targets, dict) or set(targets)-keys or not all(map(finite, targets.values())):
        raise ValueError(f'{label} load_targets must map force.x/y/z or moment.x/y/z to finite values.')
    if frame in ('fixed', 'prescribed') and targets:
        raise ValueError('Fixed or prescribed source motion cannot have frame load targets.')
    if frame == 'mixed' and not targets:
        raise ValueError('Mixed source motion requires at least one force or moment target.')


def _validate_airflow_dynamic_request(request):
    action = request['action']
    if request.get('mode', action) != action or not isinstance(request.get('condition'), dict):
        raise ValueError('Source airflow dynamics requires a FlightCondition object and the matching analysis mode.')
    if request.get('operating_constraints', ()) not in ((), []):
        raise ValueError('Source airflow dynamics uses canonical frame load targets and does not yet support trim options.')
    options = request.get(action)
    if not isinstance(options, dict):
        raise ValueError('Source airflow dynamics requires explicit analysis options.')
    if options.get('vacuum', False) is not False or options.get('quiescent_density') is not None:
        raise ValueError('Source airflow dynamics requires vacuum false and no separate quiescent fluid.')
    if any(key in options for key in ('motion','velocity','position','attitude','gravity_magnitude')):
        raise ValueError('Source airflow motion, pose and gravity are specified by FlightCondition, not duplicate dynamic options.')
    _validate_moving_modal_options(options, 'Source airflow dynamics')


def _validate_moving_time_request(request, *, airflow=False):
    action = request['action']
    label = 'Source airflow' if airflow else 'Moving vacuum'
    if request.get('mode', 'time') != 'time':
        raise ValueError(f'{label} time requests require mode time.')
    if action == 'time' and airflow and not isinstance(request.get('condition'), dict):
        raise ValueError('Source airflow time response requires a FlightCondition object.')
    if action == 'time' and not airflow and request.get('condition') is not None:
        raise ValueError(f'{label} time response requires condition:null and direct time motion, pose and gravity.')
    common = {'duration', 'dt', 'order', 'tolerance', 'max_steps', 'forcing', 'accuracy'}
    allowed = set(common)
    if action != 'resume_time':
        allowed.update(('frame', 'load_targets', 'actuator_constraints'))
    if action == 'time':
        allowed.add('continuation_steps')
        if airflow:
            allowed.add('controller')
        if not airflow:
            allowed.update(('velocity', 'motion', 'position', 'attitude', 'gravity_magnitude'))
    elif action == 'launch_time':
        allowed.update(('loads', 'disturbance', 'initial_difference_step', 'initial_rank_tolerance'))
    options = request.get('time')
    if not isinstance(options, dict) or set(options)-allowed:
        raise ValueError(f'Unsupported {label.lower()} time options; saved launch and continuation retain their saved physical setup.')
    if options.get('actuator_constraints') not in (None, [], ()):
        raise ValueError(f'{label} time response does not support actuator constraints.')
    if action != 'resume_time':
        frame = options.get('frame', 'prescribed')
        if frame not in ('prescribed', 'free', 'mixed'):
            raise ValueError(f'{label} time frame must be prescribed, free or mixed.')
        _validate_moving_modal_options(dict(options, frame=frame), label)
    if action != 'time':
        packet = request.get('equilibrium_state' if action == 'launch_time' else 'checkpoint')
        container = packet if action == 'launch_time' else packet.get('context') if isinstance(packet, dict) else None
        identity = container.get('identity') if isinstance(container, dict) else None
        expected = dict(beam_interpolation=DRELA_SEGSPL, structural_operator=SOURCE_AIRFLOW if airflow else SOURCE_MOVING)
        if not isinstance(identity, dict) or any(identity.get(k) != v for k, v in expected.items()):
            raise ValueError(f'{label} launch/checkpoint requires its exact saved numerical identity.')
        setup = container.get('launch' if action == 'launch_time' else 'setup')
        if (not isinstance(setup, dict) or (not isinstance(setup.get('condition'), dict) if airflow else setup.get('condition') is not None)
                or (not airflow and setup.get('controller') is not None) or setup.get('quiescent_density') is not None
                or setup.get('actuator_constraints') not in (None, [], ())):
            raise ValueError(f'Saved {label.lower()} setup has an incompatible medium, feedback or actuator constraints.')
    def finite(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    for name in ('duration', 'dt', 'tolerance'):
        value = options.get(name)
        required = name == 'duration' or (name == 'dt' and action != 'resume_time')
        if (required and value is None) or (value is not None and (not finite(value) or value <= 0)):
            raise ValueError(f'{label} time {name} must be positive and finite.')
    order = options.get('order')
    if order is not None and (isinstance(order, bool) or order not in (1, 2, 5)):
        raise ValueError(f'{label} time order must be 1, 2 or 5.')
    if 'forcing' in options and not (isinstance(options['forcing'], str) or (action == 'resume_time' and options['forcing'] is None)):
        raise ValueError(f'{label} forcing must be an ASWING table string.')
