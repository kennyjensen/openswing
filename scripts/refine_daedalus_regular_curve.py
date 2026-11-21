"""Locate response extrema using the complete current-mesh descriptor."""
import argparse
from check_daedalus_load_sensitivity import ROOT, read
from daedalus_bounded_job import run
import check_daedalus_regular_mesh_response as response

FEATURES = {
    'yaw-low-min': (0, 'min', 1.02, 1.16),
    'roll-low-min': (1, 'min', 1.42, 1.54),
    'yaw-high-min': (0, 'min', 6.9, 7.1),
    'roll-high-min': (1, 'min', 6.7, 6.9),
    'yaw-high-max': (0, 'max', 8.7, 8.9),
}


def refine(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from scipy.optimize import minimize_scalar
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    directory = response.STUDY/'assembled'
    a = sp.load_npz(directory/'A.npz'); m = sp.load_npz(directory/'M.npz')
    with np.load(directory/'maps.npz') as data:
        b, c = data['B'][:, 0], data['C']
    layout = read(response.STUDY/'mass/layout.json'); nn, ne = layout['nodes'], layout['elements']
    velocity = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
    for matrix in (a, m):
        for array in (matrix.data, matrix.indices, matrix.indptr):
            array.flags.writeable = False
    structure = ReusableBeamStructure(a, m,
        np.r_[np.arange(6*ne), np.arange(6*(nn+ne), layout['circulation']['start'])],
        np.arange(6*(nn+ne)), velocity, velocity)
    index, kind, left, right = FEATURES[args['feature']]
    samples = {}
    def evaluate(f):
        if f not in samples:
            z, checks = harmonic_solve(a, m, b, 2*np.pi*f, _structure=structure)
            out = c@z
            filename = f'state-{f:.17g}.npz'
            np.savez_compressed(folder/filename, state=z, output=out)
            samples[f] = dict(frequency_hz=f, real=out.real.tolist(), imag=out.imag.tolist(),
                magnitude=abs(out).tolist(), checks=checks, state_file=filename)
        value = samples[f]['magnitude'][index]
        return value if kind == 'min' else -value
    edges = [evaluate(left), evaluate(right)]
    optimum = minimize_scalar(evaluate, bounds=(left, right), method='bounded',
                              options=dict(xatol=1e-6, maxiter=25))
    assert optimum.success and left < optimum.x < right and optimum.fun < min(edges)
    # Re-evaluate both sides near the candidate; this is a local, bracketed
    # extremum of the computed curve, not optimization of a physical parameter.
    neighbors = [evaluate(optimum.x-.0001), evaluate(optimum.x+.0001)]
    assert optimum.fun < min(neighbors)
    return dict(feature=args['feature'], bracket_hz=[left, right], kind=kind,
        channels=['yaw_rate', 'roll_rate', 'sideslip', 'bank'],
        optimum=samples[optimum.x], evaluations=len(samples),
        samples=sorted(samples.values(), key=lambda r: r['frequency_hz']),
        qualification='Bracketed extremum of the full-state transfer. No physical parameter fitted; historical operating point, reference digitization error and mesh convergence remain unresolved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('feature', choices=FEATURES)
    args = vars(parser.parse_args())
    inputs = response.inputs()+[ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        response.STUDY/'mass/layout.json', response.STUDY/'curve-observation.json']
    inputs.extend(p for p in (response.STUDY/'assembled').iterdir() if p.suffix in ('.npz', '.json'))
    run(response.STUDY, 'refine-'+args['feature'], inputs, refine, args, __file__)
