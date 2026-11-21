"""Fixed first Pazy AE-1 comparison, with an explicitly mirrored ideal wall.

Eight states: two vacuum baselines and three source-exact flow conditions on
each of two meshes. No fitted inputs, epsilon wall displacement, or native
intersection-check override. See isae_ae1.py for the declared reconstruction.
"""
from pathlib import Path
import argparse
import hashlib
import json
import signal
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from isae_ae1 import configuration, condition
from openswing.asw import parse_asw
from openswing.network import StaticNetwork, network_result
from openswing.structured_static import equilibrate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def observable(position, rotation):
    """Recover material LE/TE, then project their chord into root x-z axes."""
    position, rotation = np.asarray(position), np.asarray(rotation)
    le = position + rotation @ np.array([-.0441, 0., 0.])
    te = position + rotation @ np.array([.0559, 0., 0.])
    chord = te - le
    return dict(leading_edge_m=le.tolist(), trailing_edge_m=te.tolist(),
                midchord_m=((le + te) / 2).tolist(),
                projected_twist_deg=float(np.degrees(np.arctan2(-chord[2], chord[0]))))


def compute(spec):
    text, data, panels = configuration(spec['refinement'])
    model = parse_asw(text)
    flight = None if spec['speed_m_s'] == 0 else condition(spec['alpha_deg'], spec['speed_m_s'])
    network = StaticNetwork(model, panels, flight, [0., 0., 0.], [])
    started = time.monotonic()
    last = [started]

    def progress(stage, current, total):
        now = time.monotonic()
        if now - last[0] >= 15:
            print(json.dumps(dict(specification=spec, stage=stage, current=current,
                                  total=total, elapsed_seconds=now-started)), flush=True)
            last[0] = now

    state, steps = equilibrate(network, tolerance=1e-8, continuation_steps=4, progress=progress)
    result = network_result(network, state)
    # Fresh full physical equations, with no retained tangent/field cache.
    assert network.iteration_fields is None and network.tangent_influences is None
    residual = network.residual(state, factor=1.)
    assert np.all(np.isfinite(residual)) and np.max(abs(residual)) <= 1e-8
    positions, rotations, *_ = network.unpack(state)
    reflection = np.diag([1., -1., 1.])
    # One ascending-span continuous beam: reversing its nodes pairs each half.
    position_error = float(np.max(abs(positions[::-1] - positions @ reflection)))
    rotation_error = float(np.max(abs(rotations[::-1] - reflection @ rotations @ reflection)))
    assert position_error / network.L <= 1e-8 and rotation_error <= 1e-8
    force_scale = max(1., np.linalg.norm(result['support_force']), np.linalg.norm(result['applied_force']))
    moment_scale = max(1., force_scale * network.L, np.linalg.norm(result['support_moment']))
    force_balance = float(np.max(abs(np.asarray(result['force_balance']))) / force_scale)
    moment_balance = float(np.max(abs(np.asarray(result['moment_balance']))) / moment_scale)
    assert force_balance <= 1e-7 and moment_balance <= 1e-7
    tip = int(np.argmax(network.rj[:, 1]))
    half_strips = [s for s in result.get('strips', []) if s.get('lifting') and s['t'] > 0]
    return dict(status='computed', specification=spec, source=text, panels=panels,
                source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                state=state.tolist(), result=result,
                observable=observable(positions[tip], rotations[tip]),
                checks=dict(fresh_residual=float(np.max(abs(residual))),
                            force_balance_scaled=force_balance, moment_balance_scaled=moment_balance,
                            mirror_position_error_m=position_error, mirror_rotation_error=rotation_error),
                counts=dict(nodes=network.nn, elements=network.ne,
                            half_lifting_strips=len(half_strips), residual_evaluations=network.nfev,
                            continuation_steps=steps),
                continuation=getattr(network, 'continuation_diagnostics', []),
                iterations=getattr(network, 'structured_iterations', []),
                seconds=time.monotonic()-started)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Refuse to overwrite an existing run; inspect its saved states first.'
    args.output.mkdir(parents=True)
    readiness = json.loads((ROOT/'docs/validation/isae-ae1-source-readiness.json').read_text())
    files = [Path(__file__), ROOT/'scripts/isae_ae1.py', ROOT/'scripts/pazy_primary.py',
             ROOT/'scripts/pazy_primary_conm2.py', ROOT/'tests/test_isae_ae1.py',
             ROOT/'docs/validation/isae-ae1-source-readiness.json', *sorted((ROOT/'openswing').glob('*.py'))]
    for entry in readiness['provenance_pins']:
        path = Path(entry['path'])
        assert path.is_file() and sha(path) == entry['sha256'], 'Source changed: '+str(path)
        files.append(path)
    fixtures = []
    for refinement in (2, 4):
        text, data, panels = configuration(refinement)
        for pin in data['source_pins']:
            path = Path(pin['path'])
            assert sha(path) == pin['sha256']
            files.append(path)
        fixtures.append(dict(refinement=refinement, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                             actual_semispan_m=data['actual_semispan'], nominal_semispan_m=data['nominal_semispan'],
                             assumptions=data['assumptions'],
                             maximum_section_projection_bound=max(s['energy_projection_bound'] for s in data['sections'])))
    source_pins = {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p): sha(p) for p in files}
    specifications = [dict(refinement=r, intervals_per_half=15*r, alpha_deg=a, speed_m_s=v)
                      for r in (2, 4) for a, v in ((0., 0.), (5., 30.), (5., 40.), (7., 30.))]
    plan = dict(schema='openswing-isae-ae1-pilot-v1', specifications=specifications, fixtures=fixtures,
                source_sha256=source_pins, conditions=dict(density=1.23, mach=0., gravity=[0.,0.,0.]),
                wall='Explicit reflected full wing; same physical beam, center clamp, report positive half.',
                path='Each state starts from jig and ramps its own load monotonically; four nominal continuation steps.',
                displacement_convention='Retain both root-normal dz and wind-normal -sin(alpha)*dx+cos(alpha)*dz from the model zero-flow baseline; processed experimental export does not resolve the axis choice.',
                branch_limit='Convergence and symmetry do not establish static or dynamic stability.',
                gates=dict(residual=1e-8, force_moment_balance_scaled=1e-7,
                           mirror_position_scaled=1e-8, mirror_rotation=1e-8,
                           displacement_mesh_relative=0.01),
                twist_mesh_gate=None, experimental_acceptance_threshold=None,
                wall_seconds_limit=600, maximum_states=8)
    identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    plan['identity'] = identity
    write(args.output/'plan.json', plan)
    records = []

    def timed_out(signum, frame):
        raise TimeoutError('Fixed 600 s batch limit reached; no automatic restart.')

    signal.signal(signal.SIGALRM, timed_out)
    signal.alarm(600)
    started = time.monotonic()
    try:
        for i, spec in enumerate(specifications):
            print(json.dumps(dict(starting=i+1, total=8, specification=spec)), flush=True)
            attempt = time.monotonic()
            try:
                row = compute(spec)
            except Exception as exc:
                row = dict(status='failed', specification=spec, seconds=time.monotonic()-attempt,
                           error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc())
                write(args.output/f'state-{i:02d}.json', row)
                records.append(row)
                raise
            row['identity'] = identity
            write(args.output/f'state-{i:02d}.json', row)
            records.append(row)
            print(json.dumps(dict(completed=i+1, seconds=row['seconds'], checks=row['checks'],
                                  observable=row['observable'])), flush=True)
        assert all(sha(ROOT/p) == digest for p, digest in source_pins.items()), 'Source changed during run'
    finally:
        signal.alarm(0)
        write(args.output/'execution.json', dict(identity=identity,
              status='completed' if len(records)==8 and all(r['status']=='computed' for r in records) else 'incomplete',
              completed=sum(r['status']=='computed' for r in records), attempted=len(records),
              seconds=time.monotonic()-started, outputs=[f'state-{i:02d}.json' for i in range(len(records))]))


if __name__ == '__main__':
    main()
