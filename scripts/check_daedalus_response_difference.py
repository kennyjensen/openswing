"""Exact equation-block accounting of a change between two full responses.

For K=i*w*M-A and K*x=B:
  dx = inv(K1) [dB - dK*x0] = inv(K0) [dB - dK*x1].
Both identities use unchanged endpoint matrices; no hybrid physical model or
fitted parameter is introduced. Report both endpoint-dependent decompositions.
"""
import argparse
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, read, write, pin
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-response-difference-20261114'
CASES = [ROOT/'artifacts/daedalus-regular-mesh-response-20261114',
         ROOT/'artifacts/daedalus-pitch-balanced-base-20261114']
REPORTS = [CASES[0]/'report', CASES[1]/'report-v2']


def row_groups(layout):
    """Row order from Network.residual and DynamicSystem.residual."""
    ne, nn = layout['elements'], layout['nodes']
    reaction = layout['reactions']['start']
    gamma = layout['circulation']['start']
    operating = layout['operating']['start']
    velocity = layout['local_velocity']['start']
    rotation = layout['local_rates']['start']
    frame = layout['frame']['start']
    assert reaction == 6*(nn+ne)
    return [
        ('beam compatibility', 0, 6*ne),
        ('nodal force balance', 6*ne, 6*ne+3*nn),
        ('nodal moment balance', 6*ne+3*nn, reaction),
        ('connections', reaction, gamma),
        ('circulation', gamma, operating),
        ('aircraft force balance', operating, operating+3),
        ('aircraft moment balance', operating+3, velocity),
        ('local translation kinematics', velocity, rotation),
        ('local rotation kinematics', rotation, frame),
        ('frame velocity kinematics', frame, frame+3),
        ('frame angular-rate kinematics', frame+3, frame+6),
        ('Earth position kinematics', frame+6, frame+9),
        ('Euler-angle kinematics', frame+9, frame+12)]


def execute(folder, arguments):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    for report in REPORTS:
        for path, digest in read(report/'source-pins.json').items():
            assert pin(Path(path)) == digest, path
    layouts = [read(case/'mass/layout.json') for case in CASES]
    assert layouts[0] == layouts[1]
    layout = layouts[0]
    groups = row_groups(layout)
    size = layout['frame']['start']+12
    indices = [i for _, start, stop in groups for i in range(start, stop)]
    assert indices == list(range(size))
    frequency = arguments['frequency']
    omega = 2*np.pi*frequency
    endpoints = []
    for case in CASES:
        a, m = [sp.load_npz(case/'assembled'/name) for name in ['A.npz', 'M.npz']]
        with np.load(case/'assembled/maps.npz') as maps:
            b, c = maps['B'][:, 0].copy(), maps['C'].copy()
        assert a.shape == m.shape == (size, size)
        for matrix in [a, m]:
            for values in [matrix.data, matrix.indices, matrix.indptr]:
                values.flags.writeable = False
        nn, ne = layout['nodes'], layout['elements']
        velocities = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
        structure = ReusableBeamStructure(a, m,
            np.r_[np.arange(6*ne), np.arange(6*(nn+ne), layout['circulation']['start'])],
            np.arange(6*(nn+ne)), velocities, velocities)
        x, checks = harmonic_solve(a, m, b, omega, _structure=structure)
        endpoints.append(dict(a=a, m=m, b=b, c=c, x=x, y=c@x,
                              structure=structure, checks=checks))
    old, new = endpoints
    delta = new['x']-old['x']
    output_delta = new['y']-old['y']
    da, dm, db, dc = [new[key]-old[key] for key in ['a', 'm', 'b', 'c']]
    directions = []
    for label, operator, reference in [('new operator', new, old), ('old operator', old, new)]:
        terms = {'A change': da@reference['x'],
                 'M change': -1j*omega*(dm@reference['x']), 'input change': db}
        columns, metadata = [], []
        for group, start, stop in groups:
            for term, vector in terms.items():
                value = np.zeros(size, dtype=complex)
                value[start:stop] = vector[start:stop]
                columns.append(value)
                metadata.append(dict(group=group, term=term, row_start=start, row_stop=stop))
        rhs = np.column_stack(columns)
        k = 1j*omega*operator['m']-operator['a']
        identity_error = float(np.linalg.norm(k@delta-rhs.sum(axis=1))/
            max(np.linalg.norm(rhs.sum(axis=1)), 1e-30))
        assert identity_error < 1e-9, identity_error
        responses, checks = harmonic_solve(operator['a'], operator['m'], rhs, omega,
                                           _structure=operator['structure'])
        reconstruction = responses.sum(axis=1)
        state_error = float(np.linalg.norm(reconstruction-delta)/max(np.linalg.norm(delta), 1e-30))
        assert state_error < 1e-9, state_error
        contributions = operator['c']@responses
        output_map = dc@reference['x']
        total = contributions.sum(axis=1)+output_map
        errors = abs(total-output_delta)/np.maximum(abs(output_delta), 1e-30)
        assert max(errors) < 1e-9, errors
        rows = []
        for meta, value in zip(metadata, contributions.T):
            rows.append(dict(meta, real=value.real.tolist(), imag=value.imag.tolist()))
        rows.append(dict(group='output map', term='C change',
            real=output_map.real.tolist(), imag=output_map.imag.tolist()))
        group_rows = []
        for group in [g[0] for g in groups]+['output map']:
            value = sum((np.array(r['real'])+1j*np.array(r['imag']) for r in rows if r['group'] == group), np.zeros(4, dtype=complex))
            projection = 100*np.real(value*np.conj(output_delta))/abs(output_delta)**2
            group_rows.append(dict(group=group, real=value.real.tolist(), imag=value.imag.tolist(),
                change_direction_projection_percent=projection.tolist()))
        np.testing.assert_allclose(np.sum([r['change_direction_projection_percent'] for r in group_rows], axis=0),
                                   np.full(4, 100.), rtol=1e-9, atol=1e-9)
        directions.append(dict(operator=label, rhs_identity_relative_error=identity_error,
            state_reconstruction_relative_error=state_error,
            output_reconstruction_relative_errors=errors.tolist(), checks=checks,
            groups=group_rows, terms=rows))
    return dict(frequency_hz=frequency, states=size,
        channels=['yaw_rate', 'roll_rate', 'sideslip', 'bank'],
        units=['deg/s/F3', 'deg/s/F3', 'deg/F3', 'deg/F3'],
        endpoints=[dict(case=str(case), real=e['y'].real.tolist(), imag=e['y'].imag.tolist(),
                        magnitude=abs(e['y']).tolist(), checks=e['checks'])
                   for case, e in zip(CASES, endpoints)],
        difference=dict(real=output_delta.real.tolist(), imag=output_delta.imag.tolist()),
        directions=directions, layout=layout,
        qualification=('Exact equation-row accounting in the shared normalized perturbation chart. '
            'Contributions are complex, may cancel, and depend on the endpoint operator. '
            'Projection percentages sum to 100% of the complex response change, not '
            'of response magnitude or physical force. These are not isolated component '
            'tests, parameter sensitivities, hybrid flight cases or native validation.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--frequency', required=True, type=float)
    args = vars(parser.parse_args())
    inputs = list((ROOT/'openswing').glob('*.py'))+[ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    for case, report in zip(CASES, REPORTS):
        inputs.extend(case/'assembled'/name for name in ['A.npz', 'M.npz', 'maps.npz', 'plan.json', 'result.json', 'terminal.json'])
        inputs.extend([case/'mass/layout.json', report/'source-pins.json'])
    run(STUDY, args['tag'], inputs, execute, args, __file__)
