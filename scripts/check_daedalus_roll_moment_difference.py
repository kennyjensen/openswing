"""Identify state couplings within the dominant global roll-moment row."""
import argparse
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, read, pin
from daedalus_bounded_job import run
import check_daedalus_response_difference as base
from check_daedalus_component_difference import SEEDS

FREQUENCY = 1.15737773741517
SOURCE = base.STUDY/'low-dip-components'


def column_groups(layout, packet):
    import numpy as np
    groups = []
    cursor = 0
    for beam, (stations, nodes) in packet['identity']['stations'].items():
        ids = np.asarray(nodes)
        for label, offset in [('translation', 0), ('rotation', 3)]:
            groups.append((f'beam {beam} {label}', (6*ids[:, None]+offset+np.arange(3)).ravel()))
        elements = np.arange(cursor, cursor+len(stations)-1)
        for label, offset in [('internal force', 0), ('internal moment', 3)]:
            groups.append((f'beam {beam} {label}', (layout['internal_loads']['start']+
                           6*elements[:, None]+offset+np.arange(3)).ravel()))
        for label, entry in [('local velocity', 'local_velocity'), ('local rate', 'local_rates')]:
            groups.append((f'beam {beam} {label}', (layout[entry]['start']+
                           3*ids[:, None]+np.arange(3)).ravel()))
        cursor += len(stations)-1
    groups.append(('reactions', np.arange(layout['reactions']['start'], layout['circulation']['start'])))
    for beam in layout['circulation']['discretization']['beams']:
        start = layout['circulation']['start']+beam['coefficient_start']
        groups.append((f"beam {beam['beam']} circulation", np.arange(start, start+beam['unknowns'])))
    for i, name in enumerate(layout['operating']['variables']):
        groups.append((name, np.array([layout['operating']['start']+i])))
    for k, label in enumerate(['frame velocity', 'frame rate', 'Earth position', 'Euler angle']):
        for i, axis in enumerate('xyz'):
            groups.append((label+' '+axis, np.array([layout['frame']['start']+3*k+i])))
    assert sorted(np.concatenate([indices for _, indices in groups]).tolist()) == list(range(layout['frame']['start']+12))
    return groups


def execute(folder, arguments):
    import numpy as np
    import scipy.sparse as sp
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    evidence = read(SOURCE/'result.json')
    for path, digest in read(SOURCE/'plan.json')['inputs_sha256'].items():
        assert pin(Path(path)) == digest, path
    layout = evidence['layout']
    groups = column_groups(layout, read(SEEDS[0]))
    omega = 2*np.pi*FREQUENCY
    row = layout['operating']['start']+3
    endpoints = []
    for case, expected in zip(base.CASES, evidence['endpoints']):
        a, m = [sp.load_npz(case/'assembled'/name) for name in ['A.npz', 'M.npz']]
        for matrix in [a, m]:
            for values in [matrix.data, matrix.indices, matrix.indptr]:
                values.flags.writeable = False
        with np.load(case/'assembled/maps.npz') as maps:
            b, c = maps['B'][:, 0], maps['C']
        with np.load(case/'response'/f'state-{FREQUENCY:.9g}.npz') as data:
            x = data['state']
        np.testing.assert_allclose(c@x, np.array(expected['real'])+1j*np.array(expected['imag']), rtol=1e-12, atol=1e-14)
        unit = np.zeros(a.shape[0])
        unit[row] = 1.
        nn, ne = layout['nodes'], layout['elements']
        velocities = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
        structure = ReusableBeamStructure(a, m,
            np.r_[np.arange(6*ne), np.arange(6*(nn+ne), layout['circulation']['start'])],
            np.arange(6*(nn+ne)), velocities, velocities)
        response, checks = harmonic_solve(a, m, unit, omega, _structure=structure)
        endpoints.append(dict(a=a, m=m, b=b, c=c, x=x, gain=c@response, checks=checks))
    old, new = endpoints
    da = (new['a']-old['a'])[row].toarray().ravel()
    dm = (new['m']-old['m'])[row].toarray().ravel()
    db = (new['b']-old['b'])[row]
    total_delta = np.array(evidence['difference']['real'])+1j*np.array(evidence['difference']['imag'])
    directions = []
    for label, operator, reference in [('new operator', new, old), ('old operator', old, new)]:
        rows = []
        for group, indices in groups:
            a_value = operator['gain']*(da[indices]@reference['x'][indices])
            m_value = operator['gain']*(-1j*omega*(dm[indices]@reference['x'][indices]))
            value = a_value+m_value
            projection = 100*np.real(value*np.conj(total_delta))/abs(total_delta)**2
            rows.append(dict(group=group, real=value.real.tolist(), imag=value.imag.tolist(),
                change_direction_projection_percent=projection.tolist(),
                a_change=dict(real=a_value.real.tolist(), imag=a_value.imag.tolist(),
                    projection_percent=(100*np.real(a_value*np.conj(total_delta))/abs(total_delta)**2).tolist()),
                m_change=dict(real=m_value.real.tolist(), imag=m_value.imag.tolist(),
                    projection_percent=(100*np.real(m_value*np.conj(total_delta))/abs(total_delta)**2).tolist())))
        value = operator['gain']*db
        rows.append(dict(group='input change', real=value.real.tolist(), imag=value.imag.tolist(),
            change_direction_projection_percent=(100*np.real(value*np.conj(total_delta))/abs(total_delta)**2).tolist()))
        direction = next(d for d in evidence['directions'] if d['operator'] == label)
        expected = next(g for g in direction['groups'] if g['group'] == 'aircraft moment balance x')
        expected_value = np.array(expected['real'])+1j*np.array(expected['imag'])
        reconstructed = sum((np.array(r['real'])+1j*np.array(r['imag']) for r in rows), np.zeros(4, dtype=complex))
        errors = abs(reconstructed-expected_value)/np.maximum(abs(expected_value), 1e-30)
        assert max(errors) < 1e-10, errors
        directions.append(dict(operator=label, row=row, unit_row_checks=operator['checks'],
            reconstruction_relative_errors=errors.tolist(), groups=rows))
    return dict(frequency_hz=FREQUENCY, channels=evidence['channels'], directions=directions,
        qualification=('Exact partition of changes in one normalized global roll-moment equation '
            'by perturbation state group. Percentages project on the full complex response '
            'change, not on this row alone; signed cancellation and endpoint dependence remain. '
            'State groups are not isolated aerodynamic/inertial load mechanisms.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = list((ROOT/'openswing').glob('*.py'))+[*SEEDS, ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'scripts/check_daedalus_response_difference.py',
        ROOT/'scripts/check_daedalus_component_difference.py']
    inputs.extend(SOURCE/name for name in ['plan.json', 'result.json', 'terminal.json'])
    for case in base.CASES:
        inputs.extend(case/'assembled'/name for name in ['A.npz', 'M.npz', 'maps.npz'])
        inputs.append(case/'response'/f'state-{FREQUENCY:.9g}.npz')
    run(base.STUDY, args['tag'], inputs, execute, args, __file__)
