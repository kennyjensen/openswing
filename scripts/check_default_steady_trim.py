"""Check the exact cold-trim UI request under short, serial resource limits."""
import argparse
import json
import time
from daedalus_bounded_job import run
from check_daedalus_load_sensitivity import ROOT, read, write, pin, LIMITS

STUDY = ROOT/'artifacts/default-steady-trim-20261115'


def audit_saved_trim(folder):
    """Rebuild the original request and evaluate its saved fields without solving."""
    import numpy as np
    from unittest.mock import patch
    from openswing.bridge import dispatch
    from openswing.equilibrium_state import restore
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.time_state import read_condition

    completed = STUDY/'cold-trim-complete-1'
    saved = read(completed/'solved-state.json')
    summary = read(completed/'solved-summary.json')
    request = read(STUDY/'request.json')
    plan = read(completed/'plan.json')
    checked_sources = [p for p in sorted((ROOT/'openswing').glob('*.py'))
                       if str(p) in plan['inputs_sha256']]
    assert checked_sources
    assert all(pin(p) == plan['inputs_sha256'][str(p)] for p in checked_sources)
    assert pin(STUDY/'request.json') == plan['inputs_sha256'][str(STUDY/'request.json')]
    assert request['source'] == (ROOT/'public/examples/dae.asw').read_text()
    assert not request.get('initial_state')
    networks = []

    def capture(net, tolerance, continuation_steps, initial_state, progress, **kwargs):
        assert initial_state is None
        networks.append(net)
        return {'captured_network': True}

    with patch('openswing.source_discrete._solve_source_network', side_effect=capture):
        dispatch(request)
    assert len(networks) == 1
    net = networks[0]
    x = restore(net, saved)
    light = net.residual(x).copy()
    full, data = net.residual(x, detail=True)
    np.testing.assert_allclose(full, light, rtol=1e-13, atol=1e-13)
    error = float(np.max(abs(full)))
    assert error < 1e-9
    np.testing.assert_allclose(error, summary['residual'], rtol=1e-5, atol=1e-14)
    for key, value in summary['operating_values'].items():
        np.testing.assert_allclose(data['operating_values'][key], value, rtol=1e-13, atol=1e-13)
    # Recompute the frame loads from the full nodal loads and moment arms,
    # independently of the seven operating-equation report rows.
    force = data['force'].sum(axis=0)
    moment = (data['moment']+np.cross(data['r']-net.model.reference[1], data['force'])).sum(axis=0)
    assert np.max(abs(force))/net.F < 1e-9
    assert np.max(abs(moment))/(net.F*net.L) < 1e-9
    assert abs(data['aero']['earth_state']['flight_path']) < 1e-7
    assert net.iteration_fields is None and net.tangent_influences is None

    # Release the trim targets exactly as response analysis does and rebuild
    # from the serialized solved condition, rather than retaining live objects.
    launch = saved['launch']
    condition = read_condition(launch['condition'])
    constraints = time_load_constraints('free')
    free = SourceAirflowNetwork(net.model, launch['panels'], condition,
        launch['gravity'], launch['loads'], operating_constraints=constraints,
        strut_mode=launch['strut_mode'], mesh_recipe=net.mesh_recipe, steady_trim=False)
    free_x = restore(free, saved)
    free_error = float(np.max(abs(free.residual(free_x, detail=True)[0])))
    assert free_error < 1e-9
    zero = np.zeros_like(free.rj)
    system = _dynamic_base(free, free_x, constraints, 'free',
        dict(elastic_motion=(zero, zero, zero, zero), circulation_rate=np.zeros(free.ng)),
        position=condition.position_earth, attitude=condition.attitude,
        velocity=(0, 0, 0), gravity_magnitude=condition.gravity_magnitude)
    z = np.zeros(system.size)
    dynamic_error = float(np.max(abs(system.residual(z, z))))
    base = system.base_report()
    assert dynamic_error < 1e-9 and base['modal_base']['kinematically_steady']
    assert abs(base['earth_state']['flight_path']) < 1e-7
    return dict(kind='independent cold-trim saved-state reload', nodes=net.nn,
        steady_unknowns=net.size, dynamic_states=system.size,
        solver_sources_checked=len(checked_sources), source_and_request_unchanged=True,
        full_residual=error, light_full_difference=float(np.max(abs(full-light))),
        force=force.tolist(), moment=moment.tolist(),
        free_frame_residual=free_error, dynamic_residual=dynamic_error,
        flight_path_deg=base['earth_state']['flight_path'],
        qualification='Rebuilt networks, strict state identity, full nodal loads and zero-rate free-flight equations. No Newton solve, matrix assembly, time integration, frequency sweep, browser or WASM execution.')


def check(folder, args):
    if args['stage'] == 'audit':
        return audit_saved_trim(folder)
    from openswing.bridge import dispatch
    from openswing.aero import AnalysisError

    request = read(STUDY/'request.json')
    before = json.dumps(request, sort_keys=True)
    assert request['mode'] == 'mounted' and request['action'] == 'solve'
    assert not request.get('initial_state') and not request.get('controller')
    assert request['source'] == (ROOT/'public/examples/dae.asw').read_text()
    events = []
    stop_reason = None
    failure = None
    started, cpu_started = time.monotonic(), time.process_time()

    class ProbeFinished(Exception):
        pass

    with (folder/'progress.jsonl').open('x') as log:
        def progress(stage, current, total):
            nonlocal stop_reason
            event = dict(stage=stage, current=float(current), total=float(total),
                         cpu_seconds=time.process_time()-cpu_started,
                         wall_seconds=time.monotonic()-started)
            events.append(event)
            log.write(json.dumps(event)+'\n')
            log.flush()
            if args['stage']=='initial-rank' and stage=='static_load' and current>0:
                stop_reason = 'initial rank check passed; stopped before loaded continuation'
                raise ProbeFinished()
            # Stop at existing progress boundaries, with separate hard limits
            # recorded by the supervisor. The application solver is unchanged.
            if event['cpu_seconds'] >= (4 if args['stage']=='prefix' else 18):
                stop_reason = 'cooperative CPU budget reached'
                raise ProbeFinished()

        try:
            result = dispatch(request, progress=progress)
        except ProbeFinished:
            result = None
        except AnalysisError as error:
            failure = str(error)
            stop_reason = 'solver rejected the default setup'
            result = None

    assert json.dumps(request, sort_keys=True) == before
    if result is not None:
        write(folder/'solved-state.json',result['equilibrium_state'])
        write(folder/'solved-summary.json',{key:result.get(key) for key in
            ('analysis','converged','residual','operating_values','operating_constraints',
             'force_balance','moment_balance','support_force','support_moment',
             'continuation_steps','equilibrium_initialization','numerics')})
    return dict(
        kind='bounded default-input cold-trim probe',
        source='actual steady-flight configuration and main.js request builder',
        saved_equilibrium_used=False, request_unchanged=True, events=events,
        initial_rank_passed=any(e['stage']=='static_load' and e['current']>0 for e in events),
        stop_reason=stop_reason, solver_error=failure,
        solve_completed=result is not None,
        converged=None if result is None else result.get('converged'),
        residual=None if result is None else result.get('residual'),
        qualification=('Complete native cold-trim execution under the stated resource limits. '
                       'Convergence is recorded separately above; this is not a browser/WASM run.'
                       if result is not None else
                       'Real native solver prefix with the stated cooperative stop and resource limits. '
                       'Not a browser/WASM run or proof of cold-trim convergence.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--stage', choices=['prefix','initial-rank','complete','audit'], default='prefix')
    args = vars(parser.parse_args())
    if args['stage'] in ('initial-rank', 'complete'):
        # Scoped to this supervisor process; other diagnostics retain their
        # original 15 CPU / 25 wall second defaults and the same memory cap.
        LIMITS.update(cpu_seconds=25,wall_seconds=45)
    inputs = [STUDY/'request.json', ROOT/'public/examples/dae.asw',
              ROOT/'web/main.js', ROOT/'web/steady-flight.js', ROOT/'web/daedalus-mesh.json',
              ROOT/'tests/daedalus-request.test.mjs',
              *sorted((ROOT/'openswing').glob('*.py'))]
    if args['stage'] == 'audit':
        inputs.extend(STUDY/'cold-trim-complete-1'/name for name in
                      ('solved-state.json', 'solved-summary.json', 'plan.json', 'terminal.json'))
    run(STUDY, args['tag'], inputs, check, args, __file__)
