"""Four diagnostic Newton steps beyond AE-2's original backtracking range.

Start from the explicitly unconverged centered trial. Rebuild every complete
centered tangent and retain the original physical-residual Armijo criterion.
This is a numerical investigation, not an accepted equilibrium or native vote.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts.probe_isae_ae2_centered_incidence import centered_geometry
from scripts.probe_isae_ae2_cold_trace import read, write, pin


def prepare(out):
    assert not out.exists()
    parent = ROOT / 'artifacts/isae/ae2-later-centered-20261110'
    old = base.checked(parent)
    for phase in ('capture', 'centered', 'verify'):
        base.receipt(parent, phase)
    assessment = read(parent / 'assessment.json')
    assert assessment['status'] == 'DIRECTIONAL_GATE_PASS'
    assert next(r['power'] for r in assessment['trials'] if r['accepted_by_merit']) == 9
    paths = [Path(p['path']) for p in old['pins']]
    paths += [Path(__file__), parent / 'plan.json', parent / 'assessment.json']
    for phase in ('capture', 'centered', 'verify'):
        paths += [parent / phase / f for f in ('terminal.json', 'sources-verified.json')]
    paths += [parent / 'capture' / f for f in ('trial.npz', 'state.json', 'report.json')]
    write(out / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        method=__doc__, parent=str(parent), pins=[pin(p) for p in sorted(set(paths))],
        phases=['iterate'], limits=base.LIMITS, geometry_difference_order=4,
        geometry_difference_step=1e-6, maximum_iterations=4, maximum_halvings=20,
        physical_residual_gate=1e-12, directional_step=1e-6, primary_votes_added=0,
        qualifications=[
            'Original eight-halving bound is extended to twenty only in this diagnostic.',
            'Each direction uses a newly assembled full centered matrix and exact beam elimination.',
            'No acceptance gate is relaxed; any converged candidate would still require independent verification.',
            'A stalled trace cannot establish nonexistence, a fold, uniqueness or stability.']))
    print('Prepared four bounded extended-search diagnostic steps.', flush=True)


def iterate(out, plan):
    import numpy as np
    from openswing.newton_structure import NewtonBeamFactor
    from openswing.aero import AnalysisError
    from openswing.equilibrium_state import capture
    n, x, residual = base.trial(Path(plan['parent']))
    initial = x.copy()
    records = []
    before = time.monotonic()
    for iteration in range(plan['maximum_iterations']):
        error = float(np.max(abs(residual)))
        if error <= plan['physical_residual_gate']:
            break
        with centered_geometry(plan):
            jac = n.jacobian(x, 1., _sparse=True, _direct_geometry=True)
        factor = NewtonBeamFactor(n, jac)
        direction = factor.solve(-residual)
        predicted = jac @ direction
        defect = float(np.max(abs(predicted + residual)))
        assert defect <= 1e-10
        h = plan['directional_step']
        actual = (n.residual(x+h*direction)-n.residual(x-h*direction))/(2*h)
        record = dict(iteration=iteration, before=error,
            direction_norm=float(np.linalg.norm(direction)), linear_defect=defect,
            directional_error=float(np.linalg.norm(actual-predicted)/np.linalg.norm(predicted)),
            trials=[])
        accepted = False
        for power in range(plan['maximum_halvings'] + 1):
            scale = 2.**-power
            try:
                trial = n.residual(x+scale*direction)
                next_error = float(np.max(abs(trial)))
            except (AnalysisError, ValueError, FloatingPointError) as exc:
                record['trials'].append(dict(power=power, error=None, exception=str(exc), accepted=False))
                continue
            accepted = bool(np.isfinite(next_error) and (
                next_error < error*(1-1e-4*scale) or next_error <= plan['physical_residual_gate']))
            record['trials'].append(dict(power=power, error=next_error,
                ratio=next_error/error, accepted=accepted))
            if accepted:
                x = x+scale*direction
                residual = trial.copy()
                record.update(accepted_power=power, after=next_error,
                              accepted_step_norm=float(np.linalg.norm(scale*direction)))
                break
        # Release the previous matrix and factor before the next full build.
        del factor, jac
        records.append(record)
        write(out / 'iterate/progress.json', records)
        if not accepted:
            break
    fresh = n.residual(x)
    np.testing.assert_allclose(fresh, residual, atol=1e-12, rtol=1e-8)
    error = float(np.max(abs(fresh)))
    np.savez_compressed(out / 'iterate/trial.npz', x=x, residual=fresh)
    write(out / 'iterate/state.json', capture(n, x, residual=error, include_launch=False))
    write(out / 'assessment.json', dict(status='DIAGNOSTIC_ITERATIONS_COMPLETE',
        records=records, final_residual=error, converged_candidate=error<=plan['physical_residual_gate'],
        accepted_equilibrium=False, primary_votes_added=0,
        coordinate_change_norm=float(np.linalg.norm(x-initial)), seconds=time.monotonic()-before,
        pins=[pin(out / 'iterate' / f) for f in ('progress.json', 'trial.npz', 'state.json')]))
    print(dict(final_residual=error, accepted_powers=[r.get('accepted_power') for r in records],
               accepted_equilibrium=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve())
    else:
        base.iterate = iterate
        base.launch(args.output.resolve(), 'iterate')
