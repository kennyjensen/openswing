"""Checked continuation boundaries for small, serial equilibrium jobs.

This format is an unfinished OpenSwing load continuation, not an equilibrium,
an ASWING .pnt file or a time-launch state. Exact normalized coordinates retain
roundoff-sized displacements; their layout and physical scales are explicit.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from .aero import AnalysisError


class ContinuationPending(Exception):
    def __init__(self, checkpoint):
        super().__init__('Equilibrium continuation has accepted unfinished load steps.')
        self.checkpoint = checkpoint


def plain(value):
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def canonical(value):
    # JSON has one number type. JavaScript serializes 1.0 as 1 and -0.0 as 0;
    # hash the represented float64 value, not Python's integer/float spelling.
    # State storage stays unchanged. Inexact large integers must fail rather
    # than collide when transported through the browser's Number type.
    def numbers(item):
        if isinstance(item, bool):
            return item
        if isinstance(item, (int, float)):
            number = float(item)
            if isinstance(item, int) and number != item:
                raise ValueError('Integer is not exactly representable as float64.')
            return 0.0 if number == 0 else number
        if isinstance(item, dict):
            return {key: numbers(entry) for key, entry in item.items()}
        if isinstance(item, list):
            return [numbers(entry) for entry in item]
        return item
    try:
        return json.dumps(numbers(plain(value)), sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise AnalysisError('Continuation data must contain finite JSON values with exactly representable numbers.') from exc


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def context(net, tolerance, continuation_steps, reuse_matrices, full_structure):
    from .equilibrium_state import identity
    from .time_state import condition_data, motion_data
    # The same Python files are present in the native and self-hosted WASM
    # kernels. Hash once per job, never once per residual or load step.
    kernel = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        kernel.update(path.name.encode()+b'\0'+path.read_bytes()+b'\0')
    return plain(dict(identity=identity(net), kernel_sha256=kernel.hexdigest(),
        network=type(net).__module__+'.'+type(net).__qualname__,
        setup=dict(panels=net.panels, condition=condition_data(net.condition),
            motion=motion_data(net.motion), gravity=net.gravity if net.gravity_override else None,
            loads=net.loads, strut_mode='wire' if net.tension_only else 'bilateral',
            operating_constraints=[asdict(c) for c in net.operating.constraints],
            quiescent_density=net.quiescent_density,
            quiescent_body_added_mass_factor=net.quiescent_body_added_mass_factor),
        solver=dict(policy='structured-continuation-v1', tolerance=tolerance,
            continuation_steps=continuation_steps, reuse_matrices=reuse_matrices,
            full_structure=full_structure, rotation_limit_rad=float(np.deg2rad(5.)),
            physical_residual_target=min(tolerance, 1e-12)),
        coordinates=dict(size=net.size, nodes=net.nn, elements=net.ne,
            reaction_count=net.nc, gamma_start=net.gamma_start, operating_start=net.operating_start,
            length_scale=float(net.L), force_scale=float(net.F), circulation_scale=float(net.gamma_scale),
            layout='nodal translation/L and spatial rotation vectors; element force/F and moment/(F*L); scaled reactions; circulation/gamma_scale; operating coordinates')))


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError('Invalid continuation '+name+'.')
    try:
        value = float(value)
    except (ValueError, OverflowError) as exc:
        raise AnalysisError('Invalid continuation '+name+'.') from exc
    if not np.isfinite(value):
        raise AnalysisError('Invalid continuation '+name+'.')
    return value


def _count(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise AnalysisError('Invalid continuation '+name+'.')
    return value


def capture(net, state, ctx, reached, increment, steps, rejected_attempts):
    from .hinge_history import current
    residual = np.asarray(net.residual(state, reached))
    error = float(np.max(abs(residual)))
    if not np.all(np.isfinite(residual)) or error > ctx['solver']['physical_residual_target']:
        raise AnalysisError('Cannot checkpoint an unconverged continuation boundary.')
    packet = plain(dict(format='openswing-static-continuation', version=1, context=ctx,
        coordinates=np.asarray(state).tolist(), hinge_charts=current(net),
        operating_initial_values=deepcopy(net.operating.initial_values),
        load_fraction=float(reached), next_increment=float(increment),
        accepted_load_steps=steps, rejected_load_attempts=rejected_attempts,
        physical_residual=error,
        initialization=deepcopy(getattr(net, 'equilibrium_diagnostics',
            dict(initialization='undeformed load continuation')))))
    packet['sha256'] = digest(packet)
    return packet


def restore(net, packet, ctx):
    from .hinge_history import checked, current, joints
    fields = {'format','version','context','coordinates','hinge_charts','load_fraction',
              'next_increment','accepted_load_steps','rejected_load_attempts','physical_residual',
              'initialization','sha256'}
    if (not isinstance(packet, dict) or set(packet) not in (fields, fields | {'operating_initial_values'})
            or packet['format'] != 'openswing-static-continuation'
            or type(packet['version']) is not int or packet['version'] != 1):
        raise AnalysisError('Expected a version-1 static continuation checkpoint.')
    if packet['sha256'] != digest({k:v for k,v in packet.items() if k != 'sha256'}):
        raise AnalysisError('Static continuation checksum does not match its contents.')
    if canonical(packet['context']) != canonical(ctx):
        raise AnalysisError('Static continuation model, kernel, mesh, settings or solver controls do not match.')
    reached = _number(packet['load_fraction'], 'load fraction')
    increment = _number(packet['next_increment'], 'increment')
    steps = _count(packet['accepted_load_steps'], 'accepted count', 1)
    rejected = _count(packet['rejected_load_attempts'], 'rejected count')
    if not 0 < reached < 1 or not 0 < increment <= 1 or rejected >= 128:
        raise AnalysisError('Static continuation load range or rejection budget is invalid.')
    if not 0 <= _number(packet['physical_residual'], 'residual') <= ctx['solver']['physical_residual_target']:
        raise AnalysisError('Invalid continuation residual.')
    # Operating targets follow a homotopy from their original unloaded values.
    # Initializing those values at the saved partial state changes that path.
    # Older unconstrained packets need no origin; constrained packets without
    # it cannot be reconstructed unambiguously and must be restarted.
    origin = packet.get('operating_initial_values', [])
    if (not isinstance(origin, list) or len(origin) != len(net.operating.constraints)):
        raise AnalysisError('Continuation needs one original operating target value per constraint; restart checkpoints that omit them.')
    origin = [_number(value, 'operating target origin') for value in origin]
    values = packet['coordinates']
    if not isinstance(values, list) or len(values) != net.size:
        raise AnalysisError('Static continuation coordinates have the wrong size.')
    state = np.array([_number(v, 'coordinate') for v in values])
    centers = checked(net, packet['hinge_charts'])
    old = current(net)
    old_origin = deepcopy(net.operating.initial_values)
    try:
        net.operating.initial_values = origin
        for joint, center in zip(joints(net), centers):
            joint['angle_chart'] = center
        residual = np.asarray(net.residual(state, reached))
        error = float(np.max(abs(residual)))
        if not np.all(np.isfinite(residual)) or error > ctx['solver']['physical_residual_target']:
            raise AnalysisError('Saved continuation boundary fails the rebuilt physical residual.')
        if not isinstance(packet['initialization'], dict):
            raise AnalysisError('Invalid continuation initialization record.')
    except BaseException:
        net.operating.initial_values = old_origin
        raise
    finally:
        for joint, center in zip(joints(net), old):
            joint['angle_chart'] = center
        net.aero_key = None
    return state, reached, increment, steps, rejected, centers, deepcopy(packet['initialization'])


def solve_job(model, request, panels, policy, progress=None):
    """Opt-in JSON job; ordinary solves keep their existing unbounded route."""
    from .network import StaticNetwork, network_result
    from .source_discrete import SourceDiscreteNetwork, SourceSectionNetwork, source_network_result
    from .source_coupled import SourceCoupledNetwork
    from .source_airflow import SourceAirflowNetwork
    from .time_state import read_condition
    from .equilibrium_state import capture as capture_equilibrium
    from .structured_static import equilibrate
    options = request.get('continuation')
    if not isinstance(options, dict) or set(options)-{'checkpoint','max_load_steps'}:
        raise AnalysisError('Continuation jobs accept checkpoint and max_load_steps only.')
    budget = _count(options.get('max_load_steps',1), 'max_load_steps', 1)
    if request.get('action') != 'solve' or request.get('mode') not in ('mounted','structural'):
        raise AnalysisError('Continuation jobs require mounted or structural equilibrium.')
    if any(request.get(k) is not None for k in ('initial_state','controller','derivatives')):
        raise AnalysisError('Continuation jobs cannot use warm guesses, controllers or derivative requests.')
    # Read identifiers from the actual class policies rather than assume aliases.
    classes = {'midpoint-v1':StaticNetwork, **{c.structural_operator:c for c in
        (SourceDiscreteNetwork,SourceSectionNetwork,SourceCoupledNetwork,SourceAirflowNetwork)}}
    cls = classes.get(policy['structural_operator'])
    if cls is None:
        raise AnalysisError('This structural operator has no steady continuation job route.')
    structural = request['mode'] == 'structural'
    if structural and request.get('condition') not in (None, {}):
        raise AnalysisError('Structural continuation has no FlightCondition.')
    condition = None if structural else read_condition(request.get('condition', {}), saved=False)
    settings = dict(operating_constraints=request.get('operating_constraints', ()),
        strut_mode=request.get('strut_mode','bilateral'),
        allow_signed_point_weights=structural, allow_signed_distributed_weights=structural)
    if cls is SourceAirflowNetwork:
        settings['steady_trim'] = True
    net = cls(model, panels, condition, request.get('gravity'), request.get('loads', ()), **settings)
    tolerance = request.get('tolerance', 1e-8)
    continuation_steps = _count(request.get('continuation_steps',4), 'continuation_steps', 1)
    try:
        state, steps = equilibrate(net, tolerance, continuation_steps,
            progress=progress, checkpoint=options.get('checkpoint'),
            max_load_steps=budget)
    except ContinuationPending as pending:
        return dict(analysis='equilibrium_continuation',converged=False,
            continuation_status='pending',checkpoint=pending.checkpoint,
            load_fraction=pending.checkpoint['load_fraction'],
            accepted_load_steps=pending.checkpoint['accepted_load_steps'],
            continuation_log=plain(net.continuation_diagnostics),
            iteration_log=plain(net.structured_iterations),
            rank_check=plain(net.structured_rank_check))
    result = source_network_result(net,state) if isinstance(net,SourceDiscreteNetwork) else network_result(net,state)
    if not np.isfinite(result['residual']) or result['residual'] > min(tolerance,1e-12):
        raise AnalysisError('Completed continuation fails the full-load physical residual.')
    signed = bool(net.inertia_model.signed_point_weights or net.inertia_model.signed_distributed_weights)
    result.update(continuation_status='complete',continuation_steps=steps,
        equilibrium_state=capture_equilibrium(net,state,residual=result['residual'],
            include_launch=not signed and (cls is StaticNetwork or cls is SourceAirflowNetwork)),
        equilibrium_initialization=getattr(net,'equilibrium_diagnostics',dict(initialization='undeformed load continuation')),
        continuation_log=plain(net.continuation_diagnostics),iteration_log=plain(net.structured_iterations),
        rank_check=plain(net.structured_rank_check))
    if isinstance(net,SourceDiscreteNetwork) and cls is not SourceAirflowNetwork:
        result['equilibrium_state']['limitations'].append('Static source-discrete policy only; cannot initialize physical dynamics or a different structural operator.')
    if signed:
        note = ('Signed Weight, mg and Dmg entries specify static gravity forces at rotating pylon endpoints or section centroids. '
                'Mass properties are algebraic bookkeeping; this state cannot initialize physical dynamics.')
        result['limitations'].append(note)
        result['equilibrium_state']['limitations'].append(note)
    if structural:
        result.update(analysis='structural_static',structural_only=True,strips=[])
    return result
