"""Measure an alternative documented curvature discretization in full Bode solves.

The matrix form is normalized by Eq.5 (half the literal Eq.7 cross-dot).
It replaces only curvature kinematics, keeping the accepted base by a constant
residual offset. This is not a retrimmed alternate aircraft or native-ASWING pass.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read
from check_daedalus_circulation_phase import dump, restore
from check_daedalus_mesh_zeros import paths, load, factor_at, STUDY as SAMPLES, CHANNELS
from check_daedalus_mesh_residual import accepted, packet
from check_daedalus_source_strain import PROPERTIES
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-curvature-form-20261114'
FREQUENCIES = [.1, 1.15737773741517, 1.5]


def capture(folder, args):
    import numpy as np
    from check_daedalus_structural_resolution import dynamic
    system = dynamic(SimpleNamespace(seed=paths(args['mesh'])[2])); n = system.network
    r, Q, N, M, _, _ = n.unpack(system.base)
    assert not np.any(n.offa) and not np.any(n.offb) and not np.any(n.damping_times)
    material = {key: [] for key in PROPERTIES}; body = []; beams = []
    for mesh in n.meshes:
        for key in PROPERTIES:
            material[key].append(np.c_[mesh.beam.value(key, mesh.t0, side='right'),
                                      mesh.beam.value(key, mesh.t1, side='left')])
        body.extend([not mesh.beam.lifting]*len(mesh.length)); beams.extend([mesh.beam.index]*len(mesh.length))
    fixture = dict(ends=n.ends, positions=r, frames=np.stack([Q[n.a]@n.R0a, Q[n.b]@n.R0b], axis=1),
        jig_frames=np.stack([n.R0a, n.R0b], axis=1), force=N, moment=M, length=n.ds,
        material={key: np.concatenate(value) for key, value in material.items()}, body=np.array(body),
        beam=np.array(beams), L=n.L, F=n.F, ML=n.F*n.L, size=system.size)
    dump(folder/'fixture.pkl', fixture)
    return dict(mesh=args['mesh'], nodes=n.nn, elements=n.ne, dimension=system.size,
        scope='Supplied accepted trim, literal endpoint properties and unloaded arc lengths; no independent trim claim.')


def axial(m):
    import numpy as np
    return np.array([m[..., 2, 1]-m[..., 1, 2], m[..., 0, 2]-m[..., 2, 0], m[..., 1, 0]-m[..., 0, 1]]).T/2


def assemble(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from daedalus_source_strain_reference import Compatibility, GENERATORS
    from openswing.network import exp
    accepted(STUDY/('capture-'+args['mesh']))
    fixture = restore(STUDY/('capture-'+args['mesh'])/'fixture.pkl'); ref = Compatibility(fixture)
    ne, nn = len(ref.a), len(fixture['positions']); size = fixture['size']
    A = sp.load_npz(paths(args['mesh'])[0]/'A.npz')
    M = sp.load_npz(paths(args['mesh'])[0]/'M.npz')
    rows = (6*np.arange(ne)[:, None]+np.arange(3, 6)).ravel()
    native = A[rows].tocsr()
    assert M[rows].nnz == 0
    with np.load(paths(args['mesh'])[0]/'maps.npz') as maps: assert np.max(abs(maps['B'][rows])) == 0
    expected = sp.lil_matrix((3*ne, size)); alternative = expected.copy()
    kinematic53 = np.zeros((ne, 2, 3, 3)); kinematic52 = np.zeros_like(kinematic53)
    geometric_constitutive = np.zeros_like(kinematic53)
    zero_couplings = np.max(abs(ref.law[:, 3:, :3])); assert zero_couplings == 0
    for e in range(ne):
        ra, rb = ref.frame[e]
        for end, node in enumerate((ref.a[e], ref.b[e])):
            re = ref.frame[e, end]
            for axis, g in enumerate(GENERATORS):
                dq = np.linalg.solve(ref.K[e, end], re.T[:, axis])
                dk = np.einsum('ijk,k->ij', ref.K_partial[e, end], dq)/2
                d53 = dk@ref.delta_angles[e]+(-1 if end==0 else 1)*ref.mean_K[e]@dq
                d52 = (-1 if end==0 else 1)*axial(ra.T@g@rb)
                constitutive = -ref.length[e]*ref.law[e, 3:, 3:]@((g@re).T@ref.moment[e]/2)
                kinematic53[e, end, :, axis] = d53
                kinematic52[e, end, :, axis] = d52
                geometric_constitutive[e, end, :, axis] = constitutive
                expected[3*e:3*e+3, 6*node+3+axis] = (d53+constitutive)[:, None]
                alternative[3*e:3*e+3, 6*node+3+axis] = (d52+constitutive)[:, None]
        load = -ref.length[e]*ref.ML*ref.law[e, 3:, 3:]@ref.mean_frame[e].T
        cols = 6*nn+6*e+np.arange(3, 6)
        expected[3*e:3*e+3, cols] = load
        alternative[3*e:3*e+3, cols] = load
    expected, alternative = expected.tocsr(), alternative.tocsr()
    difference = expected-native
    maximum = float(np.max(abs(difference.data), initial=0.)); assert maximum < 3e-10, maximum
    # Preserve the baseline numerical matrix; replace only its kinematic form.
    local_change = alternative-expected; local_change.eliminate_zeros()
    coo = local_change.tocoo()
    change = sp.csc_matrix((coo.data, (rows[coo.row], coo.col)), shape=A.shape)
    np.testing.assert_equal(change[:, 6*nn:].nnz, 0)
    base52 = axial(ref.frame[:, 0].transpose(0, 2, 1)@ref.frame[:, 1])
    jig52 = axial(fixture['jig_frames'][:, 0].transpose(0, 2, 1)@fixture['jig_frames'][:, 1])
    base53 = np.einsum('nij,nj->ni', ref.mean_K, ref.delta_angles)
    base_offset = base52-jig52-(base53-ref.rest)
    # Probe the alternative's derivatives without Euler-angle recovery.
    checks = []
    for h in (1e-3, 5e-4):
        worst = 0.
        for end in (0, 1):
            for axis in range(3):
                def value(step):
                    ra, rb = ref.frame[:, 0], ref.frame[:, 1]
                    rot = exp(step*np.eye(3)[axis])
                    if end==0:ra = rot@ra
                    else:rb = rot@rb
                    return axial(ra.transpose(0, 2, 1)@rb)
                derivative = (8*(value(h)-value(-h))-(value(2*h)-value(-2*h)))/(12*h)
                worst = max(worst, float(np.max(abs(derivative-kinematic52[:, end, :, axis]))))
        assert worst < 2e-12, worst
        checks.append(dict(width=h, maximum_error=worst))
    # Under a superposed spatial rotation the matrix form is exactly invariant.
    patch53 = kinematic53.sum(axis=1); patch52 = kinematic52.sum(axis=1)
    assert np.max(abs(patch52)) == 0
    generator_checks = []
    for g in GENERATORS:
        t = np.eye(3); dt = -g
        crossdot = np.array([dt[1]@t[2]-dt[2]@t[1], dt[2]@t[0]-dt[0]@t[2], dt[0]@t[1]-dt[1]@t[0]])
        np.testing.assert_array_equal(crossdot, 2*axial(g)); generator_checks.append(crossdot.tolist())
    sp.save_npz(folder/'change.npz', change)
    np.savez_compressed(folder/'arrays.npz', kinematic53=kinematic53, kinematic52=kinematic52,
        geometric_constitutive=geometric_constitutive, patch53=patch53, patch52=patch52,
        base_offset=base_offset, beams=fixture['beam'])
    return dict(mesh=args['mesh'], dimension=size, elements=ne, rotation_rows=3*ne,
        complete_rotation_jacobian_maximum_error=maximum, change_nonzeros=change.nnz,
        maximum_base_offset=float(np.max(abs(base_offset))), alternative_derivative_checks=checks,
        maximum_euler_rigid_rotation_defect=float(np.max(abs(patch53))),
        maximum_matrix_rigid_rotation_defect=float(np.max(abs(patch52))),
        maximum_endpoint_angle_change=float(np.max(abs(ref.delta_angles))),
        generator_crossdot_values=generator_checks,
        per_beam=[dict(beam=int(beam), maximum_kinematic_change=float(np.max(abs(kinematic52[fixture['beam']==beam]-kinematic53[fixture['beam']==beam]))),
            maximum_euler_rigid_rotation_defect=float(np.max(abs(patch53[fixture['beam']==beam])))) for beam in sorted(set(fixture['beam']))],
        qualification='Eq.52 is normalized to Eq.5/8, using half the literal printed Eq.7 cross-dot. Existing Eq.53 remains preferred. The alternate tangent retains all constitutive, aerodynamic, inertia, constraint and output terms; a constant residual offset holds its supplied base.')


def response(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.harmonic_structure import ReusableBeamStructure
    accepted(STUDY/('assemble-'+args['mesh']))
    a, m, b, c, layout, _, old_structure = load(args['mesh'])
    with np.load(SAMPLES/(args['mesh']+'-samples')/'arrays.npz') as saved:
        idx = int(np.argmin(abs(saved['frequencies']-args['frequency'])))
        assert abs(saved['frequencies'][idx]-args['frequency'])<1e-13
        original = saved['states'][idx]; original_output = saved['outputs'][idx]
    omega = 2*np.pi*args['frequency']; original_residual = float(max(abs((1j*omega*m-a)@original-b)))
    assert original_residual<2e-9
    change = sp.load_npz(STUDY/('assemble-'+args['mesh'])/'change.npz')
    alt = (a+change).tocsc(); alt.sum_duplicates(); alt.eliminate_zeros()
    del old_structure
    for v in (alt.data, alt.indices, alt.indptr):v.flags.writeable=False
    nn, ne, gs = layout['nodes'], layout['elements'], layout['circulation']['start']
    velocity = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
    structure = ReusableBeamStructure(alt, m, np.r_[np.arange(6*ne), np.arange(6*(nn+ne), gs)],
        np.arange(6*(nn+ne)), velocity, velocity)
    solve = factor_at(alt, m, 1j*omega, structure)
    z, checks = solve(b)
    # Exact correction identity verifies sign and every feedback iteration.
    dz, correction_checks = solve(change@original)
    correction_error = float(max(abs(z-original-dz))); assert correction_error<2e-9
    y = c@z; delta = y-original_output
    np.savez_compressed(folder/'arrays.npz', state=z, original=original, output=y,
        original_output=original_output, delta=delta, correction=dz)
    return dict(mesh=args['mesh'], frequency_hz=args['frequency'], dimension=len(b),
        original_full_residual=original_residual, solve_checks=checks, correction_checks=correction_checks,
        correction_identity_error=correction_error, channels=CHANNELS,
        original_magnitudes=abs(original_output).tolist(), alternative_magnitudes=abs(y).tolist(),
        amplitude_change_percent=(100*(abs(y)/abs(original_output)-1)).tolist(),
        complex_change_percent=(100*abs(delta)/abs(original_output)).tolist(),
        qualification='Complete modified harmonic response at the original trim held by a constant residual offset. All feedback is resolved. This is not a new physical equilibrium, native ASWING result or recommendation to change the preferred Euler form.')


def report(folder, args):
    import csv
    import numpy as np
    entries = []
    for mesh in ('coarse', 'fine'):
        for i, frequency in enumerate(FREQUENCIES):
            r = accepted(STUDY/f'response-{mesh}-{i}'); assert r['frequency_hz']==frequency
            for j, channel in enumerate(CHANNELS):
                entries.append(dict(mesh=mesh, frequency_hz=frequency, channel=channel,
                    original_magnitude=r['original_magnitudes'][j], alternative_magnitude=r['alternative_magnitudes'][j],
                    amplitude_change_percent=r['amplitude_change_percent'][j], complex_change_percent=r['complex_change_percent'][j]))
    with (folder/'curvature-response.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(entries[0])); writer.writeheader(); writer.writerows(entries)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), layout='constrained')
    for j, (channel, color) in enumerate(zip(CHANNELS, ['#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f'])):
        for i, mesh in enumerate(('coarse', 'fine')):
            rows = [r for r in entries if r['mesh']==mesh and r['channel']==channel]
            axes[i].plot([r['frequency_hz'] for r in rows], [r['amplitude_change_percent'] for r in rows], 'o-', color=color, label=channel.replace('_',' '))
    for i, ax in enumerate(axes):
        ax.axhline(0,color='#555',linewidth=.6); ax.grid(alpha=.2); ax.legend(fontsize=8)
        ax.set(xlabel='Frequency (Hz)', ylabel='Amplitude change from Euler form (%)', title=['Original 108-node aircraft','Refined 211-node aircraft'][i])
    fig.suptitle('Normalized matrix curvature diagnostic; original trim held by an offset', fontsize=11)
    fig.savefig(folder/'curvature-response.png', dpi=150); fig.savefig(folder/'curvature-response.svg'); plt.close(fig)
    return dict(entries=entries, assemblies={mesh:accepted(STUDY/('assemble-'+mesh)) for mesh in ('coarse','fine')},
        maximum_amplitude_change_percent=max(abs(r['amplitude_change_percent']) for r in entries),
        maximum_complex_change_percent=max(r['complex_change_percent'] for r in entries),
        qualification='Three sampled frequencies on each mesh; no claim of a full spectrum, physical retrim, historical discretization identification or native-reference pass.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['capture','assemble','response','report'])
    p.add_argument('--tag',required=True);p.add_argument('--mesh',choices=['coarse','fine'],default='coarse');p.add_argument('--frequency',type=float,default=FREQUENCIES[1])
    args=vars(p.parse_args())
    inputs=[ROOT/'scripts'/s for s in ('daedalus_source_strain_reference.py','check_daedalus_source_strain.py','check_daedalus_structural_resolution.py',
        'check_daedalus_source_operator.py','check_daedalus_circulation_phase.py','check_daedalus_mesh_zeros.py','check_daedalus_mesh_residual.py')]
    inputs += [ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += list((ROOT/'openswing').glob('*.py'))
    for mesh in ('coarse','fine'):
        matrix,layout,seed=paths(mesh);inputs += [layout,seed]+[matrix/s for s in ('A.npz','M.npz','maps.npz')]
        inputs += [SAMPLES/(mesh+'-samples')/s for s in ('arrays.npz','result.json','terminal.json')]
    if args['stage']=='assemble':inputs += [STUDY/('capture-'+args['mesh'])/s for s in ('fixture.pkl','result.json','terminal.json')]
    if args['stage']=='response':inputs += [STUDY/('assemble-'+args['mesh'])/s for s in ('change.npz','arrays.npz','result.json','terminal.json')]
    if args['stage']=='report':
        inputs += [STUDY/('assemble-'+mesh)/s for mesh in ('coarse','fine') for s in ('result.json','terminal.json')]
        inputs += [STUDY/f'response-{mesh}-{i}'/s for mesh in ('coarse','fine') for i in range(len(FREQUENCIES)) for s in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
