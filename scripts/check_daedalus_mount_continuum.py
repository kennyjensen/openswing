"""Small serial continuum/source checks of the wing--fairing mounting span."""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read, write
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-mount-continuum-20261114'
CAPTURE = STUDY/'prepare-v2'
FREQUENCIES = [('static', 0j), ('slow', 2j*3.141592653589793*.2),
    ('dip', 2j*3.141592653589793*1.15737773741517),
    ('yaw_zero', complex(-2.8681937339896386, 7.418277157899976)),
    ('roll_zero', complex(1.0455996342716736, 9.0764320823061))]


def prepare(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_boom_drivers import mechanical_function
    from daedalus_mount_reference import properties
    system = dynamic(); n = system.network
    t, ids = n.station_nodes[4]; keep = (t >= 0) & (t <= 2.5)
    t, nodes = t[keep], ids[keep]
    elements = np.flatnonzero(np.isin(n.a, nodes) & np.isin(n.b, nodes))
    np.testing.assert_array_equal(n.a[elements], nodes[:-1])
    np.testing.assert_array_equal(n.b[elements], nodes[1:])
    assert len(elements) == 2
    beam = next(b for b in n.model.beams if b.index == 4)
    assert not beam.lifting
    for name in ('EA', 'GKc', 'GKn'):
        assert np.all(np.isposinf(beam.value(name, t))), name
    for name in ('EIcn', 'EIcs', 'EIsn', 'Cea', 'Nea', 'Cta', 'Nta',
                 'Ccg', 'Ncg', 'Dmg', 'mgcc', 'mgnn', 'tdeps', 'tdgam'):
        assert not np.any(beam.value(name, t)), name
    for name, axis in [('EIcc', 0), ('GJ', 1), ('EInn', 2)]:
        np.testing.assert_allclose(beam.value(name, t), [properties(x)[0][axis] for x in t], rtol=2e-14)
    np.testing.assert_allclose(beam.value('mg', t), .15, rtol=2e-14)
    assert not np.any(n.offa) and not np.any(n.offb) and not np.any(n.damping_times)
    zero = np.zeros(system.size); state, _, options = system.physical_state(zero, zero, None)
    residual, data = n.residual(state.x, detail=True, **options)
    assert max(abs(residual)) < 1e-9
    r, q, N, M, _, _ = n.unpack(system.base)
    _, _, ra, rb, *_ = n.geometry(r, q)
    frames = np.r_[ra[elements], rb[elements[-1:]]]
    np.testing.assert_allclose(rb[elements[:-1]], ra[elements[1:]], atol=2e-14, rtol=0)
    dr = r[n.b[elements]]-r[n.a[elements]]
    left = np.r_[N[elements[0]], M[elements[0]]+np.cross(dr[0], N[elements[0]])/2]
    right = np.r_[N[elements[-1]], M[elements[-1]]-np.cross(dr[-1], N[elements[-1]])/2]
    dead_force = data['force'][nodes].copy(); dead_moment = data['moment'][nodes].copy()
    dead_force[[0, -1]] = 0; dead_moment[[0, -1]] = 0
    # Wing-end external wrench is minus the inward internal wrench. Right end
    # is a prescribed support; no other beam or endpoint load is included.
    dead_force[0] = -left[:3]; dead_moment[0] = -left[3:]
    free = nodes[:-1]
    rows = np.r_[(6*elements[:, None]+np.arange(6)).ravel(),
        (6*n.ne+3*free[:, None]+np.arange(3)).ravel(),
        (6*n.ne+3*n.nn+3*free[:, None]+np.arange(3)).ravel()]
    columns = np.r_[(6*free[:, None]+np.arange(6)).ravel(),
        (6*n.nn+6*elements[:, None]+np.arange(6)).ravel(), 6*nodes[-1]+np.arange(6)]
    full_evaluate = mechanical_function(system, rows)
    def evaluate(z):
        value = full_evaluate(z)
        # The full node at t=0 also touches the nose interval. This component
        # contains only the inward wrench of the first selected interval;
        # exclude the nose's loaded moving-arm derivative at the cut.
        pose = z[:6*n.nn].reshape(n.nn, 6)
        delta = n.L*(pose[nodes[1], :3]-pose[nodes[0], :3])
        e = elements[0]
        internal = (system.base+z[:n.size])[6*n.nn+6*e:6*n.nn+6*e+6]
        f = internal[:3]*n.F
        m = internal[3:]*n.F*n.L+np.cross(dr[0]+delta, f)/2
        value[6*len(elements):6*len(elements)+3] = f/n.F
        value[9*len(elements):9*len(elements)+3] = m/(n.F*n.L)
        return value
    matrices = []
    for h in (1e-5, 5e-6):
        matrix = np.empty((len(rows), len(columns)))
        for j, col in enumerate(columns):
            d = zero.copy(); d[col] = h
            matrix[:, j] = (8*(evaluate(d)-evaluate(-d))-(evaluate(2*d)-evaluate(-2*d)))/(12*h)
        matrices.append(matrix)
    step_error = float(np.max(abs(matrices[0]-matrices[1])))
    assert step_error < 2e-8, step_error
    saved = sp.load_npz(SOURCE/'assembled-6.7/A.npz')
    source_error = float(np.max(abs(matrices[-1][:12]-saved[rows[:12]][:, columns].toarray())))
    assert source_error < 2e-8, source_error
    # Native element mass inputs and interval rotary inertia, retained as
    # independent targets for the compact adapter's literal construction.
    mass = np.zeros_like(matrices[-1]); rowmap = {int(v): j for j, v in enumerate(rows)}
    colmap = {int(v): j for j, v in enumerate(columns)}
    for sample, section in zip(n.source_mass_samples, n.source_rotary_samples):
        beam_id, sl, end, weights, arms = sample
        if beam_id != 4: continue
        assert not np.any(arms)
        for e in elements:
            i = e-sl.start; src = (n.a if end == 0 else n.b)[e]
            rotation = (ra if end == 0 else rb)[e]
            assert not np.any(section[i])
            rotary = (rotation*(weights[i]*n.ds[e]**2/12*np.array([1., 0., 1.])))@rotation.T
            physical = np.zeros((6, 6)); physical[:3, :3] = weights[i]*np.eye(3); physical[3:, 3:] = rotary
            physical *= np.r_[[n.L]*3, [1.]*3][None, :]/np.r_[[n.F]*3, [n.F*n.L]*3][:, None]
            cc = [colmap[int(6*src+j)] for j in range(6)]
            for dst in (n.a[e], n.b[e]):
                if dst not in free: continue
                rr = [rowmap[int(6*n.ne+3*dst+j)] for j in range(3)]
                rr += [rowmap[int(6*n.ne+3*n.nn+3*dst+j)] for j in range(3)]
                mass[np.ix_(rr, cc)] += physical/2
    fixture = dict(stations=t.tolist(), positions=r[nodes].tolist(), frames=frames.tolist(),
        force=N[elements].tolist(), moment=M[elements].tolist(), dead_force=dead_force.tolist(),
        dead_moment=dead_moment.tolist(), left_wrench=left.tolist(), right_wrench=right.tolist(),
        gravity_constant=float(n.model.constants[0]), L=n.L, F=n.F,
        qualification='Isolated 0..2.5 ft boom. Fairing pose prescribed; wing-end wrench and interior dead loads prescribed. Real local inertia retained. No aerodynamic, gravity-direction or aircraft-frame derivatives.')
    write(folder/'fixture.json', fixture)
    np.savez_compressed(folder/'arrays.npz', matrix=matrices[-1], mass=mass, rows=rows, columns=columns)
    return dict(elements=2, unknowns=len(rows), derivative_step_error=step_error,
        full_compatibility_error=source_error, aircraft_residual=float(max(abs(residual))),
        qualification=fixture['qualification'])


class Discrete:
    """Compact current source operator, explicitly not the independent oracle."""
    def __init__(self, fixture, factor):
        import numpy as np
        from scipy.spatial.transform import Rotation, Slerp
        from daedalus_mount_reference import properties
        self.f = fixture; self.L = fixture['L']; self.F = fixture['F']
        old = np.array(fixture['stations'])
        self.t = np.r_[np.concatenate([np.linspace(a, b, factor+1)[:-1] for a, b in zip(old[:-1], old[1:])]), old[-1]]
        self.ne = len(self.t)-1; self.size = 12*self.ne; self.ds = np.diff(self.t)
        self.r = np.column_stack([np.interp(self.t, old, np.array(fixture['positions'])[:, j]) for j in range(3)])
        self.q = Slerp(old, Rotation.from_matrix(fixture['frames']))(self.t).as_matrix()
        idx = np.searchsorted(old, (self.t[:-1]+self.t[1:])/2)-1
        mid = (self.r[:-1]+self.r[1:])/2
        oldr = np.array(fixture['positions']); oldmid = (oldr[:-1]+oldr[1:])/2
        self.N = np.array(fixture['force'])[idx]
        self.M = np.array(fixture['moment'])[idx]+np.cross(oldmid[idx]-mid, self.N)
        if factor == 1:
            self.r = np.array(fixture['positions']); self.q = np.array(fixture['frames'])
            self.N = np.array(fixture['force']); self.M = np.array(fixture['moment'])
        self.dead = np.zeros((len(self.t), 6))
        for t, f, m in zip(old, fixture['dead_force'], fixture['dead_moment']):
            node, = np.flatnonzero(self.t == t); self.dead[node] = np.r_[f, m]
        self.C = np.array([2/(properties(a)[0]+properties(b)[0]) for a, b in zip(self.t[:-1], self.t[1:])])

    def unpack(self, z):
        import numpy as np
        from openswing.local_motion import rotation_matrix
        pose = np.r_[z[:6*self.ne].reshape(self.ne, 6), z[self.size:][None, :]]
        internal = z[6*self.ne:self.size].reshape(self.ne, 6)
        return (self.r+self.L*pose[:, :3], rotation_matrix(pose[:, 3:])@self.q,
                self.N+self.F*internal[:, :3], self.M+self.F*self.L*internal[:, 3:])

    def value(self, z):
        import numpy as np
        from openswing.source_discrete import angles_from_frame, angle_matrix, _increments
        r, q, N, M = self.unpack(z); dr = np.diff(r, axis=0)
        mean = (q[:-1]+q[1:])/2
        angles = angles_from_frame(q, True); k = angle_matrix(angles, True)
        translation = dr-mean[:, :, 1]*self.ds[:, None]
        rotation = np.einsum('nij,nj->ni', (k[:-1]+k[1:])/2, _increments(angles[:-1], angles[1:]))
        rotation -= self.ds[:, None]*self.C*np.einsum('nji,nj->ni', mean, M)
        force = self.dead[:, :3].copy(); moment = self.dead[:, 3:].copy()
        force[:-1] += N; force[1:] -= N
        moment[:-1] += M+np.cross(dr, N)/2; moment[1:] += -M+np.cross(dr, N)/2
        return np.r_[np.c_[translation/self.L, rotation].ravel(),
            (force[:-1]/self.F).ravel(), (moment[:-1]/(self.F*self.L)).ravel()]

    def matrix(self, h=5e-6):
        import numpy as np
        matrix = np.empty((self.size, self.size+6))
        for j in range(self.size+6):
            d = np.zeros(self.size+6); d[j] = h
            matrix[:, j] = (8*(self.value(d)-self.value(-d))-(self.value(2*d)-self.value(-2*d)))/(12*h)
        return matrix

    def mass(self):
        import numpy as np
        mass = np.zeros((self.size, self.size+6))
        for e, ds in enumerate(self.ds):
            scalar = .15*ds/(2*self.f['gravity_constant'])
            for src in (e, e+1):
                q = self.q[src]
                inertia = (q*(scalar*ds**2/12*np.array([1., 0., 1.])))@q.T
                block = np.zeros((6, 6)); block[:3, :3] = scalar*np.eye(3); block[3:, 3:] = inertia
                block *= np.r_[[self.L]*3, [1.]*3][None, :]/np.r_[[self.F]*3, [self.F*self.L]*3][:, None]
                cols = 6*src+np.arange(6) if src < self.ne else self.size+np.arange(6)
                for dst in (e, e+1):
                    if dst == self.ne: continue
                    rows = np.r_[6*self.ne+3*dst+np.arange(3), 9*self.ne+3*dst+np.arange(3)]
                    mass[np.ix_(rows, cols)] += block/2
        return mass


def discrete(folder, args):
    import numpy as np
    fixture = read(CAPTURE/'fixture.json'); model = Discrete(fixture, args['factor'])
    zero = np.zeros(model.size+6); history = []
    for iteration in range(5):
        residual = model.value(zero); error = float(max(abs(residual))); history.append(error)
        if error < 2e-12: break
        matrix = model.matrix()[:, :model.size]
        row = np.max(abs(matrix), axis=1); col = np.max(abs(matrix/row[:, None]), axis=0)
        delta = np.linalg.solve(matrix/row[:, None]/col, -residual/row)/col
        model.r, model.q, model.N, model.M = model.unpack(np.r_[delta, np.zeros(6)])
    assert history[-1] < 2e-12, history
    wide, matrix = model.matrix(1e-5), model.matrix(5e-6)
    derivative_error = float(np.max(abs(wide-matrix))); assert derivative_error < 2e-8
    mass = model.mass(); native = {}
    if args['factor'] == 1:
        target = np.load(CAPTURE/'arrays.npz')
        native = dict(matrix=float(np.max(abs(matrix-target['matrix']))), mass=float(np.max(abs(mass-target['mass']))))
        assert native['matrix'] < 2e-8 and native['mass'] < 2e-14, native
    saved = dict(stations=model.t, positions=model.r, frames=model.q, force=model.N, moment=model.M, matrix=matrix, mass=mass)
    cases = []
    for name, s in FREQUENCIES:
        operator = matrix-s*s*mass
        cut = np.diag(np.r_[[1/model.L]*3, [1.]*3])
        rhs = np.zeros((model.size, 12), complex)
        rows = np.r_[6*model.ne+np.arange(3), 9*model.ne+np.arange(3)]
        rhs[np.ix_(rows, np.arange(6))] = np.diag(1/np.r_[[model.F]*3, [model.F*model.L]*3])
        rhs[:, 6:] -= operator[:, model.size:]@cut
        a = operator[:, :model.size]; row = np.max(abs(a), axis=1); col = np.max(abs(a/row[:, None]), axis=0)
        scaled = a/row[:, None]/col; rcond = float(1/np.linalg.cond(scaled)); assert rcond > 1e-12
        answer = np.linalg.solve(scaled, rhs/row[:, None])/col[:, None]
        defect = float(np.max(abs((a@answer-rhs)/row[:, None]))); assert defect < 2e-9
        total = np.r_[answer, np.c_[np.zeros((6, 6)), cut]]
        pose = np.r_[answer[:6*model.ne].reshape(model.ne, 6, 12), total[-6:][None, :, :]]
        motion = pose*np.r_[[model.L]*3, [1.]*3][None, :, None]
        saved[name+'_motion'] = motion
        saved[name+'_state'] = total
        cases.append(dict(name=name, s=[s.real, s.imag], scaled_residual=defect, rcond=rcond))
    np.savez_compressed(folder/'arrays.npz', **saved)
    result = dict(factor=args['factor'], elements=model.ne, equilibrium_history=history,
        derivative_step_error=derivative_error, native_comparison=native, cases=cases)
    print(result, flush=True); return result


def continuum(folder, args):
    import numpy as np
    from daedalus_mount_reference import Mount
    fixture = read(CAPTURE/'fixture.json'); model = Mount(fixture, args['rtol'])
    base, wrench, history = model.equilibrium()
    q = base['values'][:, 3:12].reshape(-1, 3, 3)
    orthogonality = float(np.max(abs(q.transpose(0, 2, 1)@q-np.eye(3))))
    assert orthogonality < 2e-10, orthogonality
    saved = dict(base=base['values'], right_wrench=wrench, stations=model.stations)
    cases = []
    for name, s in FREQUENCIES:
        states, residual, rcond = model.response(base, s)
        saved[name+'_motion'] = states[:, :6]; saved[name+'_internal'] = states[:, 6:]
        cases.append(dict(name=name, s=[s.real, s.imag], boundary_residual=residual, rcond=rcond))
    np.savez_compressed(folder/'arrays.npz', **saved)
    result = dict(rtol=args['rtol'], equilibrium_history=history, rotation_orthogonality=orthogonality,
        cases=cases, operations=model.counts)
    print(result, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'discrete', 'continuum'])
    parser.add_argument('--tag', required=True); parser.add_argument('--factor', type=int, choices=[1, 2, 4, 8], default=1)
    parser.add_argument('--rtol', type=float, default=1e-10)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/daedalus_mount_reference.py', ROOT/'scripts/check_daedalus_wing_paper.py',
        ROOT/'scripts/check_daedalus_boom_drivers.py', ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json', SOURCE/'trim-6.7-1/state.json',
        SOURCE/'assembled-6.7/A.npz', ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += list((ROOT/'openswing').glob('*.py'))
    if args['stage'] != 'prepare':
        inputs += [CAPTURE/name for name in ('fixture.json', 'arrays.npz', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
