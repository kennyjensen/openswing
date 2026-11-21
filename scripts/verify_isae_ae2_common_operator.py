"""Evaluate both AE-2 equilibria against one fresh, shared physical operator.

No Newton solve, change of operating point, or reference vote is permitted.
Alternating the saved states checks that frozen-field/cache history does not
account for the previously observed two equilibria at identical incidence.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import probe_isae_ae2_stalled_tangent as supervisor
from scripts.probe_isae_ae2_cold_trace import read, write, pin


def prepare(out):
    assert not out.exists()
    folders = [ROOT/'artifacts/isae/ae2-double-root-20261110/lower',
               ROOT/'artifacts/isae/ae2-deflection-trace-0210-20261110']
    paths = {Path(__file__).resolve(), Path(supervisor.__file__).resolve()}
    requests = []
    for folder in folders:
        report = read(folder/'report.json')
        assert report['status'] == 'VERIFIED_WARM_EQUILIBRIUM'
        assert all(c['passed'] for c in report['checks'])
        assert report['result'] == pin(folder/'result.json')
        assert report['request'] == pin(folder/'request.json')
        proof = read(folder/'verify/sources-verified.json')
        parent = Path(proof['plan']['path'])
        assert pin(parent) == proof['plan']
        for item in read(parent)['pins']:
            assert pin(item['path']) == item
            paths.add(Path(item['path']))
        paths.add(parent)
        for phase in ('solve', 'tangent', 'verify'):
            terminal = read(folder/phase/'terminal.json')
            proof = read(folder/phase/'sources-verified.json')
            assert terminal['process_reaped'] and terminal['returncode'] == 0
            assert not terminal['supervisor_timeout']
            assert proof['all_pins_checked_before_and_after']
            assert proof['terminal'] == pin(folder/phase/'terminal.json')
            assert proof['plan'] == pin(parent)
            paths.update([folder/phase/'terminal.json', folder/phase/'sources-verified.json'])
        paths.update(folder/name for name in ('report.json', 'result.json', 'request.json'))
        request = read(folder/'request.json')
        request.pop('initial_state')
        requests.append(request)
    assert requests[0] == requests[1]
    assert requests[0]['condition']['freeze_influences']
    write(out/'request.json', requests[0])
    paths.add(out/'request.json')
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        method=__doc__, folders=[str(p) for p in folders], order=[0, 1, 0, 1],
        phases=['verify'], pins=[pin(p) for p in sorted(paths)], limits=supervisor.LIMITS,
        maximum_full_residual=1e-12, sensor_parity_relative=2e-10,
        repeated_residual_absolute=1e-14, primary_votes_added=0,
        qualifications=['Same finite-mesh equations only; no stability or uniqueness claim.',
                        'No inference about historical ASWING branch selection.']))


def verify(out, plan):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import restore
    from openswing.network import network_snapshot
    request = read(out/'request.json')
    assert 'initial_state' not in request
    n = network(request)
    assert n.operating.count == 0 and not n.hinges and n.nfev == 0
    frozen = n.frozen_influences
    assert frozen is not None
    results = [read(Path(p)/'result.json') for p in plan['folders']]
    states = [restore(n, r['equilibrium_state']) for r in results]
    assert n.nfev == 0

    def fields(sensor):
        return dict(RY_m=sensor['position_earth'][1], Psi_deg=sensor['heading'],
                    sensor_V_m_s=sensor['speed'], sensor_beta_deg=sensor['beta'])

    def coefficients():
        # Sample the same undeformed receiver/source set after each physical
        # evaluation. The original cache owner must remain unchanged too.
        assert n.frozen_influences is frozen
        g = frozen.geometry
        matrix = frozen.factored_vortex(g['cp'], g['physical']).matrix()
        values = {**g, 'direction': frozen.direction, 'pg': frozen.pg,
                  'core': frozen.core, 'matrix': matrix,
                  'ground_normal': frozen.ground.normal,
                  'ground_reflection': frozen.ground.reflection}
        h = hashlib.sha256()
        for key, value in sorted(values.items()):
            array = np.ascontiguousarray(value)
            assert np.isfinite(array).all(), key
            h.update(repr((key, array.shape, array.dtype.str)).encode())
            h.update(array.tobytes())
        h.update(repr((frozen.ground.flag, frozen.ground.offset)).encode())
        return h.hexdigest()

    records, repeated, hashes = [], {}, []
    for index in plan['order']:
        residual, data = n.residual(states[index], detail=True)
        error = float(np.max(np.abs(residual)))
        assert error <= plan['maximum_full_residual']
        fresh = network_snapshot(n, residual, data)
        observed, expected = fields(fresh['sensors'][0]), fields(results[index]['sensors'][0])
        parity = {k: abs(observed[k]-expected[k]) for k in observed}
        assert all(parity[k] <= plan['sensor_parity_relative']*(1+abs(expected[k])) for k in parity)
        repeat_error = None
        if index in repeated:
            repeat_error = float(np.max(np.abs(residual-repeated[index])))
            assert repeat_error <= plan['repeated_residual_absolute']
        else:
            repeated[index] = residual.copy()
        hashes.append(coefficients())
        records.append(dict(state=index, residual=error, values=observed,
                            sensor_parity=parity, repeated_residual_difference=repeat_error))
    assert len(set(hashes)) == 1 and n.nfev == len(plan['order']) == 4
    separation = records[1]['values']['RY_m']-records[0]['values']['RY_m']
    assert separation > .01
    write(out/'report.json', dict(status='COMMON_PHYSICAL_OPERATOR_PASS',
        observed_utc=datetime.now(timezone.utc).isoformat(), records=records,
        coefficient_sha256=hashes[0], one_shared_network=True,
        initial_guess_removed=True, frozen_coefficients_unchanged=True,
        maximum_full_residual=max(r['residual'] for r in records),
        maximum_sensor_parity=max(v for r in records for v in r['sensor_parity'].values()),
        sensor_Y_separation_m=separation, physical_evaluations=n.nfev,
        equilibrium_solves=0, primary_votes_added=0,
        plan=pin(out/'plan.json'), request=pin(out/'request.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'launch'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if args.action == 'prepare':
        prepare(out)
    else:
        supervisor.verify = verify
        supervisor.launch(out, 'verify')
        supervisor.receipt(out, 'verify')
