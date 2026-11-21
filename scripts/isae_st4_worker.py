"""Bounded ST4 execution and saved-matrix evidence, separate from accounting."""
import json
from pathlib import Path
import sys

import verify_st4_mechanics_current as original


def solve(folder, index):
    saved = original.common.write

    def write(path, value):
        if path.name != 'result.json':
            return saved(path, value)
        # Same numbers and complete vectors, without expensive pretty printing.
        text = json.dumps(value, allow_nan=False, separators=(',', ':'))
        with path.open('x') as stream:
            stream.write(text + '\n')

    original.common.write = write
    try:
        original.run(folder, index)
    finally:
        original.common.write = saved


def audit(folder):
    import numpy as np
    from scipy.sparse import load_npz
    from summarize_st4_mechanics_current import assurance
    from isae_st4_transfer import frequencies as continuous_frequencies
    from isae_suite_st4_mechanics import read, sha, require, request_for

    plan = read(folder / 'plan.json')
    original.common.authenticate(plan['pins'])
    job = plan['comparison_job']
    count = job['expected_outputs']
    packets = []
    for i, state_job in enumerate(plan['jobs']):
        child = folder / f'job-{i:02d}'
        report = read(child / 'report.json')
        require(report['job'] == state_job and report['plan_sha256'] == sha(folder / 'plan.json'), 'child setup changed')
        for name, digest in report['artifacts'].items():
            require(sha(child / name) == digest, 'child artifact changed')
        request = read(child / 'request.json')
        require(request == request_for(original.ROOT, job, state_job['panels']), 'physical request changed')
        raw = read(child / 'result.json')
        require(raw['converged'] and raw['base']['converged'] and raw['vacuum'] and
                raw['frame_mode'] == 'fixed' and raw['base']['gravity_body'] == [0., 0., 0.], 'invalid vacuum base')
        a, m = load_npz(child / 'A.npz'), load_npz(child / 'M.npz')
        n = len(raw['base']['nodes'])
        require(a.shape == m.shape == (18*n, 18*n), 'matrix dimensions')
        modes = raw['modes']
        positive = sorted((r for r in modes if r['eigenvalue'][1] > 1e-6), key=lambda r: r['eigenvalue'][1])
        require(len(modes) == 16 and len({r['index'] for r in modes}) == 16 and len(positive) >= count, 'missing modes')
        audits = []
        shapes = []
        for mode in modes:
            lam = complex(*mode['eigenvalue'])
            row = dict(index=mode['index'], neutral_relative=abs(lam.real)/max(1., abs(lam.imag)))
            vectors = {}
            for side in ('left', 'right'):
                v = np.asarray(mode[side]['real']) + 1j*np.asarray(mode[side]['imag'])
                require(v.shape == (18*n,), 'vector dimensions')
                av, mv = (a@v, m@v) if side == 'right' else (v.conjugate()@a, v.conjugate()@m)
                row[side] = float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv)))
                vectors[side] = v
            row['mass_pairing'] = float(abs(np.vdot(vectors['left'], m@vectors['right'])-1))
            require(all(0 <= row[k] < 1e-8 for k in ('left', 'right', 'neutral_relative', 'mass_pairing')), 'matrix or neutrality gate')
            audits.append(row)
        for mode in positive:
            v = np.asarray(mode['right']['real']) + 1j*np.asarray(mode['right']['imag'])
            shapes.append(v[:6*n].reshape(n, 6))
        frequencies = [r['eigenvalue'][1]/(2*np.pi) for r in positive]
        require(frequencies == report['positive_frequencies_Hz'], 'report frequencies detached from eigenvalues')
        packets.append(dict(stations=np.asarray([r['jig_position'][2] for r in raw['base']['nodes']]),
                            shapes=np.asarray(shapes[:3] if job['comparison_scope'] == 'st4-mechanics' else shapes),
                            frequencies=frequencies, matrix_audits=audits))
        del raw, a, m
    coarse, fine = packets
    mac = assurance(coarse, fine)
    model = plan['models'][job['configuration']]
    helper = original.load(original.ROOT/'scripts/verify-isae-st4-transfer-current.py', 'st4_independent')
    points = (helper.audited_inputs((original.ROOT/job['model_path']).read_text(), Path(job['model_path']).parent.name)
              if job['comparison_scope'] == 'st4-native' else model['points'])
    np.testing.assert_allclose(points, model['points'], rtol=1e-15, atol=1e-15)
    centers = fine['frequencies'][:count]
    rotary = model['properties']['mgcc']/9.81
    discrete, witnesses = helper.roots(lambda f: helper.discrete_boundary(f, points, fine['stations'], rotary=rotary), centers)
    continuous = (continuous_frequencies(points, rotary, centers)
                  if job['comparison_scope'] == 'st4-native' else None)
    mesh = []
    for i, target in enumerate(job['observations']):
        pair = [p['frequencies'][i] for p in packets]
        scale = 2*np.pi if target['quantity'] == 'frequency_rad_s' else 1.
        mesh.append(dict(name=target['name'], predictions=[v*scale for v in pair],
            relative_change=abs(pair[0]/pair[1]-1), shape_MAC=float(mac[i, i]),
            mutual_shape_assignment=bool(int(np.argmax(mac[i])) == i and int(np.argmax(mac[:, i])) == i),
            discrete_relative=float(abs(discrete[i]/pair[1]-1)),
            continuous_relative=abs(pair[1]/continuous['frequencies_Hz'][i]-1) if continuous else None))
    original.common.authenticate(plan['pins'])
    original.common.write(folder/'evidence.json', dict(mesh_checks=mesh, matrix_audits=[p['matrix_audits'] for p in packets],
        shape_MAC=mac.tolist(), independent_discrete_Hz=discrete.tolist(), discrete_witnesses=witnesses,
        independent_continuous=continuous, plan_sha256=sha(folder/'plan.json')))


if __name__ == '__main__':
    original.common.bounded()
    output = Path(sys.argv[2]).resolve()
    if sys.argv[1] == 'solve':
        solve(output, int(sys.argv[3]))
    elif sys.argv[1] == 'audit':
        audit(output)
    else:
        raise ValueError('Unknown ST4 worker action')
