"""Trace AE-2 equilibrium by sensor deflection while solving incidence.

Diagnostic only: the full original physical equations remain, with beta as an
additional unknown and one sensor-Y constraint. Exact bordered elimination
uses two solves of the complete centered physical Jacobian. Converged candidates
require fresh physical and augmented matrices, both rank gates, and independent
physical verification. No archived incidence or target is substituted.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as base
from scripts import probe_isae_ae2_incidence as physical_checks
from scripts.probe_isae_ae2_centered_incidence import centered_geometry
from scripts.probe_isae_ae2_cold_trace import read, write, pin


def prepare(out, seed, target):
    assert not out.exists()
    source_plan = seed / 'plan.json' if (seed / 'plan.json').exists() else seed.parent / 'plan.json'
    old = base.checked(source_plan.parent)
    terminal = read(seed / 'verify/terminal.json')
    proof = read(seed / 'verify/sources-verified.json')
    assert terminal['returncode'] == 0 and terminal['process_reaped'] and not terminal['supervisor_timeout']
    assert proof['all_pins_checked_before_and_after'] and proof['plan'] == pin(source_plan)
    assert proof['terminal'] == pin(seed / 'verify/terminal.json')
    report = read(seed / 'report.json')
    assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
    assert report['result'] == pin(seed / 'result.json') and all(c['passed'] for c in report['checks'])
    request = deepcopy(read(seed / 'request.json'))
    request['initial_state'] = read(seed / 'result.json')['equilibrium_state']
    assert request['condition']['speed'] == 17 and request['tolerance'] == 1e-12
    write(out / 'initial-request.json', request)
    paths = [Path(p['path']) for p in old['pins']]
    paths += [Path(__file__), source_plan, ROOT / 'scripts/probe_isae_ae2_stalled_tangent.py',
        ROOT / 'scripts/probe_isae_ae2_centered_incidence.py', out / 'initial-request.json']
    paths += [seed / p for p in ('result.json', 'request.json', 'report.json',
        'verify/terminal.json', 'verify/sources-verified.json')]
    write(out / 'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        method=__doc__, seed=str(seed), target_sensor_Y_m=target,
        base_request=request, physical_residual_gate=1e-12, expected_elements=161,
        pins=[pin(p) for p in sorted(set(paths))], limits=base.LIMITS,
        phases=['solve', 'tangent', 'verify'], geometry_difference_order=4,
        geometry_difference_step=1e-6, beta_difference_step_deg=1e-4,
        sensor_difference_step=1e-5, maximum_iterations=8, maximum_halvings=12,
        primary_votes_added=0, qualifications=[
            'Target deflections select diagnostic branch points, not native ASWING matches.',
            'Beta is solved, all other physical inputs remain unchanged.',
            'The original fixed-beta equations and rank gate are independently verified at each resulting incidence.',
            'The augmented matrix is also checked with the unchanged full-matrix rank criterion.',
            'No production Newton or continuation default is changed.']))
    print(dict(prepared=True, target_Y=target, seed_beta=request['condition']['beta']), flush=True)


def sensor_y(n, x):
    import numpy as np
    assert n.operating.count == 0 and np.max(abs(n.condition.attitude)) == 0
    assert np.max(abs(n.condition.position_earth)) == 0
    row, = n.model.records['sensor']
    node = n.node(*row[1:3])
    beam = next(b for b in n.model.beams if b.index == int(row[1]))
    r, q, *_ = n.unpack(x)
    return float((r[node] + q[node] @ (row[3:6]-beam.position(row[2])))[1])


def border(n, x, plan):
    import numpy as np
    h = plan['beta_difference_step_deg']
    values = [n.residual(x, condition_override=replace(n.condition, beta=n.condition.beta+a*h))
              for a in (1, -1, 2, -2)]
    beta_column = (8*(values[0]-values[1])-(values[2]-values[3]))/(12*h)
    row, = n.model.records['sensor']
    node = n.node(*row[1:3])
    sensor_row = np.zeros(n.size)
    # Position is affine in the normalized translations; rotation is local.
    sensor_row[6*node+1] = 1.
    for column in range(6*node+3, 6*node+6):
        h = plan['sensor_difference_step']*max(1., abs(x[column]))
        delta = np.zeros(n.size)
        delta[column] = h
        values = [sensor_y(n, x+a*delta) for a in (1, -1, 2, -2)]
        sensor_row[column] = (8*(values[0]-values[1])-(values[2]-values[3]))/(12*h*n.L)
    return beta_column, sensor_row


def solve(out, plan):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore, capture
    from openswing.newton_structure import NewtonBeamFactor
    from openswing.aero import AnalysisError
    request = deepcopy(read(out / 'initial-request.json'))
    n = network(request)
    x = restore(n, request['initial_state'])
    beta = n.condition.beta
    records = []
    converged = False
    for iteration in range(plan['maximum_iterations'] + 1):
        request['condition']['beta'] = beta
        n = network(request)
        residual = n.residual(x)
        constraint = (sensor_y(n, x)-plan['target_sensor_Y_m'])/n.L
        error = max(float(np.max(abs(residual))), abs(constraint))
        if error <= plan['physical_residual_gate']:
            converged = True
            break
        if iteration == plan['maximum_iterations']:
            break
        with centered_geometry(plan):
            jac = n.jacobian(x, 1., _sparse=True, _direct_geometry=True)
        beta_column, sensor_row = border(n, x, plan)
        factor = NewtonBeamFactor(n, jac)
        fixed_correction = factor.solve(-residual)
        beta_response = factor.solve(-beta_column)
        slope = float(sensor_row @ beta_response)
        assert np.isfinite(slope) and abs(slope) > 1e-12
        delta_beta = (-constraint-float(sensor_row@fixed_correction))/slope
        correction = fixed_correction + beta_response*delta_beta
        linear_error = max(float(np.max(abs(jac@correction+beta_column*delta_beta+residual))),
                           abs(float(sensor_row@correction)+constraint))
        assert linear_error <= 1e-10
        record = dict(iteration=iteration, beta=beta, sensor_Y=sensor_y(n, x), error=error,
            physical_residual=float(np.max(abs(residual))), sensor_constraint=constraint,
            sensor_response_m_per_beta_deg=slope*n.L, delta_beta=delta_beta,
            linear_error=linear_error, trials=[])
        del factor, jac
        accepted = False
        for power in range(plan['maximum_halvings'] + 1):
            scale = 2.**-power
            next_beta = beta + scale*delta_beta
            trial_x = x + scale*correction
            try:
                r = n.residual(trial_x, condition_override=replace(n.condition, beta=next_beta))
                g = (sensor_y(n, trial_x)-plan['target_sensor_Y_m'])/n.L
                trial_error = max(float(np.max(abs(r))), abs(g))
            except (AnalysisError, ValueError, FloatingPointError) as exc:
                record['trials'].append(dict(power=power, exception=str(exc), accepted=False))
                continue
            accepted = bool(np.isfinite(trial_error) and (
                trial_error < error*(1-1e-4*scale) or trial_error <= plan['physical_residual_gate']))
            record['trials'].append(dict(power=power, error=trial_error, accepted=accepted))
            if accepted:
                x, beta = trial_x, next_beta
                record['accepted_power'] = power
                break
        records.append(record)
        write(out / 'solve/progress.json', records)
        assert accepted, 'Augmented physical-residual line search failed.'
    assert converged, 'Diagnostic continuation iteration limit reached.'
    write(out / 'request.json', request)
    np.savez_compressed(out / 'candidate.npz', x=x, residual=residual)
    write(out / 'state.json', capture(n, x, residual=float(np.max(abs(residual))), include_launch=False))
    write(out / 'candidate.json', dict(status='PENDING_VERIFICATION', accepted=False,
        beta=beta, sensor_Y=sensor_y(n, x), iterations=len(records),
        full_residual=float(np.max(abs(residual))), sensor_constraint=constraint,
        pins=[pin(out / name) for name in ('request.json', 'candidate.npz', 'state.json')],
        primary_votes_added=0))
    print(dict(status='PENDING_VERIFICATION', beta=beta, sensor_Y=sensor_y(n, x),
               iterations=len(records), residual=error), flush=True)


def candidate(out, plan):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore
    base.receipt(out, 'solve')
    pending = read(out / 'candidate.json')
    assert pending['status'] == 'PENDING_VERIFICATION' and pending['accepted'] is False
    assert all(pin(p['path']) == p for p in pending['pins'])
    n = network(read(out / 'request.json'))
    restored = restore(n, read(out / 'state.json'))
    with np.load(out / 'candidate.npz') as data:
        x, stored = data['x'].copy(), data['residual'].copy()
    np.testing.assert_allclose(restored, x, rtol=1e-14, atol=2e-15)
    fresh = n.residual(x)
    np.testing.assert_allclose(fresh, stored, rtol=1e-8, atol=1e-12)
    assert np.max(abs(fresh)) <= 1e-12
    assert abs(sensor_y(n, x)-plan['target_sensor_Y_m'])/n.L <= 1e-12
    return n, x, pending


def tangent(out, plan):
    from scipy.sparse import bmat, csc_matrix, save_npz
    n, x, pending = candidate(out, plan)
    with centered_geometry(plan):
        jac = n.jacobian(x, 1., _sparse=True, _direct_geometry=True)
    column, row = border(n, x, plan)
    augmented = bmat([[jac, csc_matrix(column[:, None])],
                      [csc_matrix(row[None, :]), csc_matrix((1, 1))]], format='csc')
    save_npz(out / 'tangent/physical.npz', jac)
    save_npz(out / 'tangent/augmented.npz', augmented)
    write(out / 'tangent/report.json', dict(status='COMPLETE_CENTERED_PHYSICAL_AND_BORDERED',
        candidate=pin(out / 'candidate.json'), physical=pin(out / 'tangent/physical.npz'),
        augmented=pin(out / 'tangent/augmented.npz'), primary_votes_added=0))
    print(dict(physical_shape=jac.shape, augmented_shape=augmented.shape), flush=True)


def verify(out, plan):
    from scipy.sparse import load_npz
    from openswing.equilibrium_state import check_tangent_rank, capture
    from openswing.source_discrete import source_network_result
    from openswing.steady_continuation import plain
    base.receipt(out, 'tangent')
    n, x, pending = candidate(out, plan)
    tangent = read(out / 'tangent/report.json')
    assert all(pin(tangent[k]['path']) == tangent[k] for k in ('candidate', 'physical', 'augmented'))
    jac = load_npz(out / 'tangent/physical.npz')
    rank = check_tangent_rank(jac)
    del jac
    augmented = load_npz(out / 'tangent/augmented.npz')
    augmented_rank = check_tangent_rank(augmented)
    del augmented
    result = source_network_result(n, x)
    assert result['converged'] and result['residual'] <= 1e-12
    result.update(numerics=read(out / 'request.json')['numerics'],
        equilibrium_state=capture(n, x, residual=result['residual'], include_launch=False),
        equilibrium_initialization=dict(initialization='saved physical equilibrium',
            method=__doc__, newton_iterations=pending['iterations'], residual=result['residual'], **rank),
        diagnostic_deflection_continuation=dict(target_Y_m=plan['target_sensor_Y_m'],
            solved_beta_deg=pending['beta'], augmented_rank=augmented_rank,
            candidate=pin(out / 'candidate.json'), tangent=pin(out / 'tangent/report.json'), primary_votes_added=0))
    write(out / 'result.json', plain(result))
    case = dict(name=out.name, beta=pending['beta'], predecessor=os.path.relpath(plan['seed'], out.parent))
    physical_checks.verify(out.parent, plan, case)
    report = read(out / 'report.json')
    assert abs(report['values']['RY_m']-plan['target_sensor_Y_m']) <= 1e-10
    report['checks'] += [dict(name='independent_sensor_Y_target', passed=True),
                         dict(name='complete_augmented_tangent_rank', passed=True)]
    report['continuation_parameter'] = dict(method=__doc__, solved_beta_deg=pending['beta'],
        prescribed_sensor_Y_m=plan['target_sensor_Y_m'], augmented_rank=augmented_rank)
    write(out / 'report.json', report)
    print(dict(status=report['status'], beta=pending['beta'], checks=len(report['checks'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--target', type=float)
    parser.add_argument('--phase', choices=['solve', 'tangent', 'verify'])
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output.resolve(), args.seed.resolve(), args.target)
    else:
        base.solve = solve
        base.tangent = tangent
        base.verify = verify
        base.launch(args.output.resolve(), args.phase)
