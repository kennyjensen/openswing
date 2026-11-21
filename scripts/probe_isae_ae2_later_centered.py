"""Capture the later centered AE-2 stall and independently check its tangent.

The original failed request, incidence, seed, physical residual, Newton search
and resource limits are retained. The capture stops before dense allocation.
An unconverged trial is never an accepted equilibrium or continuation seed.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts import probe_isae_ae2_centered_tangent as centered_probe
from scripts.probe_isae_ae2_centered_incidence import centered_geometry
from scripts.probe_isae_ae2_incidence_iteration import iteration_geometry
from scripts.probe_isae_ae2_cold_trace import read, write, pin


def prepare(out):
    assert not out.exists()
    parent = ROOT / 'artifacts/isae/ae2-centered-near275-20261110'
    old = base.checked(parent)
    failed = parent / 'beta0275'
    terminal = read(failed / 'solve/terminal.json')
    proof = read(failed / 'solve/sources-verified.json')
    assert terminal['returncode'] == 1 and terminal['process_reaped']
    assert not terminal['supervisor_timeout'] and proof['all_pins_checked_before_and_after']
    assert proof['terminal'] == pin(failed / 'solve/terminal.json')
    assert proof['plan'] == pin(parent / 'plan.json')
    assert not (failed / 'result.json').exists()
    request = read(failed / 'request.json')
    seed = ROOT / 'artifacts/isae/ae2-centered-refined-20261110/beta026875'
    base.stage_receipt(seed.parent, seed.name, 'verify')
    assert request['initial_state'] == read(seed / 'result.json')['equilibrium_state']
    assert request['condition']['beta'] == 2.75 and request['condition']['speed'] == 17.
    paths = [Path(p['path']) for p in old['pins']]
    paths += [Path(__file__), ROOT / 'scripts/probe_isae_ae2_stalled_tangent.py',
              ROOT / 'scripts/probe_isae_ae2_centered_tangent.py', parent / 'plan.json']
    paths += [failed / name for name in ('request.json', 'solve/terminal.json',
        'solve/sources-verified.json', 'solve/progress.jsonl', 'solve/stderr.log')]
    # Recheck the authoritative case/theory catalog before extending the study.
    catalog = ROOT / 'docs/validation/aswing-authoritative-sources.json'
    paths.append(catalog)
    for reference in read(catalog)['files']:
        if reference['id'] in ('isae-part-4', 'drela-steady'):
            for kind, checksum in [('pdf', 'sha256'), ('text', 'text_sha256')]:
                path = ROOT / reference['local_' + kind]
                assert pin(path)['sha256'] == reference[checksum]
                paths.append(path)
    write(out / 'request.json', request)
    paths.append(out / 'request.json')
    write(out / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        method=__doc__, parent=str(out), original_progress=str(failed / 'solve/progress.jsonl'),
        pins=[pin(p) for p in sorted(set(paths))], limits=base.LIMITS,
        phases=['capture', 'centered', 'verify'], geometry_difference_order=4,
        geometry_difference_step=1e-6, directional_steps=[1e-3, 1e-4, 1e-5, 1e-6],
        maximum_directional_relative_error=1e-4, trial_powers=list(range(13)),
        replay_atol=1e-12, replay_rtol=1e-7, primary_votes_added=0,
        qualifications=[
            'The trial remains explicitly unconverged; it cannot seed a physical solve.',
            'Replay history uses the same declared absolute/relative gate as the previous capture.',
            'Independent physical directional differences test the existing centered assembly.',
            'No physical model, native tolerance, Newton search or production source is changed.']))
    print('Prepared later centered capture and derivative check; no numerical job started.', flush=True)


def capture(out, plan):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import correct, capture as packet
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.network import network_snapshot
    from openswing.steady_continuation import plain
    request = read(out / 'request.json')
    n = network(request)
    cls = SourceCoupledNetwork
    owned = 'jacobian' in cls.__dict__
    native = cls.jacobian
    history = []
    events = []
    captured = []
    before = time.monotonic()
    old = [event for line in Path(plan['original_progress']).read_text().splitlines()
           if (event := json.loads(line))['stage'] == 'equilibrium_iteration']

    class CapturedTrial(Exception):
        pass

    def intercept(net, x, factor, **kwargs):
        if kwargs.get('_sparse', False) or kwargs.get('_direct_geometry') is not False:
            return native(net, x, factor, **kwargs)
        assert net is n and factor == 1 and not captured
        assert len(history) == len(old)
        for actual, expected in zip(history, old):
            assert actual['current'] == expected['current']
            assert abs(actual['total'] - expected['total']) <= (
                plan['replay_atol'] + plan['replay_rtol'] * abs(expected['total']))
        residual, data = n.residual(x, detail=True)
        error = float(np.max(abs(residual)))
        assert error > request['tolerance'] and abs(error - history[-1]['total']) <= 1e-12
        np.savez_compressed(out / 'capture/trial.npz', x=x, residual=residual)
        write(out / 'capture/state.json', packet(n, x, residual=error, include_launch=False))
        fields = network_snapshot(n, residual, data)
        fields.update(analysis='unconverged_diagnostic_trial', converged=False, accepted=False)
        write(out / 'capture/fields.json', plain(fields))
        write(out / 'capture/report.json', plain(dict(status='CAPTURED_UNCONVERGED_TRIAL',
            accepted=False, full_residual=error, history=history, original_history=old,
            replay_atol=plan['replay_atol'], replay_rtol=plan['replay_rtol'],
            maximum_history_absolute_difference=max(abs(a['total']-b['total']) for a, b in zip(history, old)),
            maximum_history_relative_difference=max(abs(a['total']-b['total'])/abs(b['total']) for a, b in zip(history, old)),
            tangent_calls=events, primary_votes_added=0,
            pins=[pin(out / 'capture' / name) for name in ('trial.npz', 'state.json', 'fields.json')])) )
        captured.append(True)
        raise CapturedTrial()

    with (out / 'capture/progress.jsonl').open('x') as log:
        def progress(stage, current, total):
            event = dict(stage=stage, current=current, total=total, wall_seconds=time.monotonic()-before)
            log.write(json.dumps(event, default=float) + '\n')
            log.flush()
            if stage == 'equilibrium_iteration':
                history.append(event)
        cls.jacobian = intercept
        try:
            with centered_geometry(plan), iteration_geometry(events):
                try:
                    correct(n, request['initial_state'], request['tolerance'], {}, progress=progress)
                except CapturedTrial:
                    pass
                else:
                    raise AssertionError('Expected dense fallback checkpoint, not accepted solve.')
        finally:
            if owned:
                cls.jacobian = native
            else:
                del cls.jacobian
            assert cls.jacobian is native
    assert captured == [True]
    report = read(out / 'capture/report.json')
    print(dict(status=report['status'], residual=report['full_residual'],
               replay_difference=report['maximum_history_relative_difference']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['capture', 'centered', 'verify'])
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        base.capture = capture
        base.centered = centered_probe.centered
        base.verify = centered_probe.verify
        base.launch(args.output.resolve(), args.phase)
