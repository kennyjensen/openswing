"""Separate SA-14 wing/body lift from six saved, authenticated 5-degree states.

Uses only the standard library and the public force ledger; runs no solver.
Increment differences are diagnostics, not extra native-reference pass slots.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(out):
    plan = read(out / 'plan.json')
    assert len(plan['jobs']) == 6
    for name, digest in plan['pins'].items():
        assert sha(ROOT / name) == digest, name
    inputs = {'plan.json': sha(out / 'plan.json')}
    rows, physical = [], []
    closure_error = 0.
    for i, job in enumerate(plan['jobs']):
        folder = out / f'job-{i:02d}'
        report = read(folder / 'report.json')
        assert report['plan_sha256'] == inputs['plan.json']
        for name, digest in report['artifacts'].items():
            assert sha(folder / name) == digest, folder / name
            inputs[f'{folder.name}/{name}'] = digest
        state = read(folder / 'physical-result.json')
        strict = read(folder / 'strict-result.json')
        assert strict['numerical_pass'] and state['converged']
        settings = job['settings']
        assert settings['alpha'] == 5. and settings['beta'] == 0.
        assert settings['freeze_influences'] is True and settings['mach'] is None
        angle = math.radians(settings['alpha'])
        lift_axis = (-math.sin(angle), 0., math.cos(angle))
        q = .5 * settings['density'] * settings['speed'] ** 2
        scale = q * state['coefficient_normalization']['reference_area']

        def cl(force):
            return math.fsum(a * f for a, f in zip(lift_axis, force, strict=True)) / scale

        assert abs(q - state['reference_flow']['dynamic_pressure']) < 1e-10
        assert not state['body_shoulders']
        assert not state['point_forces'] and not state['engines']
        for lifting, key in ((True, 'surface_force'), (False, 'body_force')):
            forces = [s['force'] for s in state['strips'] if s['lifting'] == lifting]
            for k in range(3):
                error = abs(math.fsum(f[k] for f in forces) - state[key][k])
                closure_error = max(closure_error, error)
                assert error < 2e-10
        wing, body = cl(state['surface_force']), cl(state['body_force'])
        assert abs(wing + body - cl(state['force'])) < 2e-14
        assert abs(wing + body - state['CL']) < 2e-14
        rows.append(dict(id=job['id'], panels=settings['panels'],
            wing_cl=wing, body_cl=body, total_cl=state['CL'],
            archived_cl=job['reference_row']['fields']['CL']['value']))
        physical.append(state)

    increments = []
    for offset in (0, 1):
        body, infinite, wing = (rows[offset + k] for k in (0, 2, 4))
        assert body['panels'] == infinite['panels'] == wing['panels']
        # The unchanged input models actually produce identical wing lattices.
        assert physical[offset]['vortex_geometry'] == physical[offset + 2]['vortex_geometry']
        assert physical[offset + 2]['vortex_geometry'] == physical[offset + 4]['vortex_geometry']
        lhs = [s for s in physical[offset + 2]['strips'] if s['lifting']]
        rhs = [s for s in physical[offset + 4]['strips'] if s['lifting']]
        assert len(lhs) == len(rhs)
        for a, b in zip(lhs, rhs, strict=True):
            assert {k: v for k, v in a.items() if k != 'beam'} == {k: v for k, v in b.items() if k != 'beam'}
        assert infinite['body_cl'] == 0. and infinite['total_cl'] == wing['total_cl']
        expected = body['archived_cl'] - wing['archived_cl']
        actual = body['total_cl'] - wing['total_cl']
        increments.append(dict(panels=wing['panels'], finite_body_delta_cl=actual,
            wing_delta_cl=body['wing_cl'] - wing['wing_cl'], body_cl=body['body_cl'],
            archived_finite_body_delta_cl=expected,
            increment_error_percent=100 * (actual - expected) / abs(expected),
            infinite_body_delta_cl=infinite['total_cl'] - wing['total_cl'],
            archived_infinite_body_delta_cl=infinite['archived_cl'] - wing['archived_cl']))
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), rows=rows,
        increments=increments, maximum_force_closure_error=closure_error,
        matched_wing_lattices=True, infinite_body_wing_strip_results_identical=True,
        inputs=inputs, script_sha256=sha(Path(__file__)), source_pins_verified=len(plan['pins']),
        physical_calls=0, primary_passes_added=0,
        qualification='Differences of rounded CL values diagnose interference; they are not new acceptance targets. '
            'Frozen zero-angle volume influences on the straight constant-radius body have zero source and doublet strengths. '
            'This explains the current infinite-body result; it does not identify the historical executable implementation.')
    with (out / 'body-increment.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'rows': rows, 'increments': increments,
        'maximum_force_closure_error': closure_error}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    audit(parser.parse_args().output.resolve())
