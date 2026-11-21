"""Audit Drela Eq.48 and partition its coarse-to-fine wing compatibility defect.

Saved full-aircraft response/adjoints are reused; no aircraft parameter is fit.
The partition holds the actual fine left-null direction and adjoint fixed.
It is an equation identity, not an independently retrimmed sensitivity study.
"""
import argparse
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, read
from check_daedalus_mesh_residual import STUDY as PREVIOUS, packet, accepted, map_folder, CHANNELS
from check_daedalus_mesh_zeros import paths
from daedalus_bounded_job import run

STUDY = ROOT/'artifacts/daedalus-position-compatibility-20261114'


def capture(folder, args):
    import numpy as np
    from check_daedalus_structural_resolution import dynamic
    data = packet(PREVIOUS/'capture')
    arrays = {}
    rows = []
    for mesh in ('coarse', 'fine'):
        system = dynamic(SimpleNamespace(seed=paths(mesh)[2]))
        n = system.network
        np.testing.assert_array_equal(system.r0, data[mesh+'_r'])
        np.testing.assert_array_equal(system.Q0, data[mesh+'_Q'])
        pa, pb, ra, rb, oa, ob = n.geometry(system.r0, system.Q0)
        assert np.max(abs(oa)) == np.max(abs(ob)) == 0
        np.testing.assert_allclose(n.source_axial_compliance, 0, atol=0, rtol=0)
        node_span = np.zeros((n.nn, 3))
        node_reference = np.zeros((n.nn, 3))
        counts = np.zeros(n.nn, int)
        for nodes, frames, reference in ((n.a, ra, n.R0a), (n.b, rb, n.R0b)):
            for node, span, ref in zip(nodes, frames[:, :, 1], reference[:, :, 1]):
                if counts[node]:
                    np.testing.assert_allclose(node_span[node], span, atol=3e-14, rtol=0)
                    np.testing.assert_allclose(node_reference[node], ref, atol=3e-14, rtol=0)
                node_span[node] = span
                node_reference[node] = ref
                counts[node] += 1
        assert np.min(counts) > 0
        steady = (pb-pa-.5*n.ds[:, None]*(ra[:, :, 1]+rb[:, :, 1]))/n.L
        arrays.update({mesh+'_'+k: v for k, v in dict(a=n.a, b=n.b, ds=n.ds,
            node_span=node_span, node_reference=node_reference, steady_residual=steady,
            wing_elements=np.arange(n.ne)[n.beam_elements[1]],
            wing_nodes=n.station_nodes[1][1], wing_stations=n.station_nodes[1][0],
            L=np.array(n.L)).items()})
        rows.append(dict(mesh=mesh, nodes=n.nn, elements=n.ne,
            maximum_steady_position_residual=float(np.max(abs(steady)))))
    np.savez_compressed(folder/'arrays.npz', **arrays)
    return dict(meshes=rows, assumptions='Literal zero axis offsets, zero axial compliance, and continuous section span vectors at every shared node verified.')


def skew(v):
    import numpy as np
    x, y, z = v
    return np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])


def audit(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.network import exp, log
    geometry = packet(STUDY/'capture')
    data = packet(PREVIOUS/'capture')
    mapped = packet(map_folder('compatible-repeat'))
    uncompleted = packet(map_folder('objective-repeat'))
    checks = []
    for mesh in ('coarse', 'fine'):
        layout = read(paths(mesh)[1]); nn, ne = layout['nodes'], layout['elements']
        a, b, ds, spans = (geometry[mesh+'_'+k] for k in ('a', 'b', 'ds', 'node_span'))
        L = float(geometry[mesh+'_L'])
        A = sp.load_npz(paths(mesh)[0]/'A.npz')
        M = sp.load_npz(paths(mesh)[0]/'M.npz')
        pos = (6*np.arange(ne)[:, None]+np.arange(3)).ravel()
        Kpos = -A[pos]
        assert M[pos].nnz == 0
        assert np.max(abs(Kpos[:, 6*nn:].data), initial=0.) == 0
        matrix_error = 0.
        analytic = []
        for e in range(ne):
            # Saved A is the residual's state Jacobian. Position rows have
            # no M term, so K=i*omega*M-A contains minus the Eq.48 derivative.
            block = -np.c_[-np.eye(3), ds[e]/(2*L)*skew(spans[a[e]]),
                            np.eye(3), ds[e]/(2*L)*skew(spans[b[e]])]
            cols = np.r_[6*a[e]+np.arange(6), 6*b[e]+np.arange(6)]
            saved = Kpos[3*e:3*e+3, cols].toarray()
            matrix_error = max(matrix_error, float(np.max(abs(saved-block))))
            outside = Kpos[3*e:3*e+3].copy().tolil(); outside[:, cols] = 0
            assert np.max(abs(outside.tocsr().data), initial=0.) == 0
            analytic.append(block)
        assert matrix_error < 3e-10, (mesh, matrix_error)
        pose = data[mesh+'_state'][:6*nn].reshape(nn, 6)
        exact = np.array([j@np.r_[pose[ia], pose[ib]] for j, ia, ib in zip(analytic, a, b)])
        saved = (Kpos@data[mesh+'_state']).reshape(ne, 3)
        action_error = float(np.max(abs(exact-saved)))
        assert action_error < 2e-12
        # Independent centered differences of endpoint-frame rotations.
        directions = np.array([[.2, -.3, .4], [-.5, .1, .2]])
        fd_errors = []
        for h in (1e-3, 5e-4):
            def residual_at(t):
                ua = np.einsum('ij,nj->ni', exp(t*directions[0])-np.eye(3), spans[a])
                ub = np.einsum('ij,nj->ni', exp(t*directions[1])-np.eye(3), spans[b])
                return -.5*ds[:, None]*(ua+ub)/L
            fd = (8*(residual_at(h)-residual_at(-h))-(residual_at(2*h)-residual_at(-2*h)))/(12*h)
            direct = -.5*ds[:, None]*(np.cross(directions[0], spans[a])+np.cross(directions[1], spans[b]))/L
            error = float(np.max(abs(fd-direct))); assert error < 2e-12
            fd_errors.append(error)
        checks.append(dict(mesh=mesh, maximum_matrix_entry_error=matrix_error,
            saved_response_action_error=action_error, rotation_difference_errors=fd_errors,
            elements_checked=ne, position_rows_checked=3*ne,
            other_state_dependencies_zero=True, position_mass_rows_zero=True))
    nf, nc = len(data['fine_r']), len(data['coarse_r'])
    L = float(geometry['fine_L'])
    np.testing.assert_equal(L, geometry['coarse_L'])
    ca, cb, fa, fb = (geometry[k] for k in ('coarse_a', 'coarse_b', 'fine_a', 'fine_b'))
    cs, fs = geometry['coarse_node_span'], geometry['fine_node_span']
    cds, fds = geometry['coarse_ds'], geometry['fine_ds']
    coarse_pose = data['coarse_state'][:6*nc].reshape(nc, 6)
    fine_pose = mapped['state'][:6*nf].reshape(nf, 6)
    common = data['common_fine_nodes']
    np.testing.assert_array_equal(fine_pose[common], uncompleted['state'][:6*nf].reshape(nf, 6)[common])
    duals = np.array([packet(PREVIOUS/f'adjoint-{channel}')['adjoint'] for channel in CHANNELS])
    terms = ['coarse_residual', 'subdivision', 'mean_endpoint_rotations', 'position_transport']
    rows, parts, sum_error, null_error, residual_error = [], [], 0., 0., 0.
    for parent in geometry['coarse_wing_elements']:
        children = np.flatnonzero(data['element_parent']==parent)
        assert len(children)==2
        e1, e2 = children
        left, middle, right = fa[e1], fb[e1], fb[e2]
        assert fa[e2]==middle and left==common[ca[parent]] and right==common[cb[parent]]
        a, b = ca[parent], cb[parent]
        s, s1, s2 = cds[parent], fds[e1], fds[e2]
        np.testing.assert_allclose(s1+s2, s, atol=3e-13, rtol=3e-14)
        n = fs[middle]
        null = np.r_[n, n]/np.sqrt(2.)
        local = np.r_[np.c_[np.eye(3), s1/(2*L)*skew(n)],
                      np.c_[-np.eye(3), s2/(2*L)*skew(n)]]
        null_error = max(null_error, float(np.max(abs(null@local))))
        va, vb = np.cross(coarse_pose[a, 3:], cs[a]), np.cross(coarse_pose[b, 3:], cs[b])
        dp = L*(coarse_pose[b, :3]-coarse_pose[a, :3])
        endpoint_a = data['fine_r'][left]-data['coarse_r'][a]
        endpoint_b = data['fine_r'][right]-data['coarse_r'][b]
        vectors = np.array([dp-.5*s*(va+vb),
            .5*(s-s1)*va+.5*(s-s2)*vb,
            -.5*s1*np.cross(coarse_pose[a, 3:], fs[left]-cs[a])
            -.5*s2*np.cross(coarse_pose[b, 3:], fs[right]-cs[b]),
            np.cross(coarse_pose[b, 3:], endpoint_b)-np.cross(coarse_pose[a, 3:], endpoint_a)])
        scalar_parts = -vectors@n/(np.sqrt(2.)*L)
        ix = (6*children[:, None]+np.arange(3)).ravel()
        r = mapped['residual'][ix]
        exact_scalar = null@r
        reconstructed = null*sum(scalar_parts)
        sum_error = max(sum_error, float(abs(sum(scalar_parts)-exact_scalar)))
        residual_error = max(residual_error, float(np.max(abs(reconstructed-r))))
        contributions = -np.conj(duals[:, ix])@np.outer(null, scalar_parts)
        actual = mapped['actual_change']
        percentages = 100*np.real(contributions*np.conj(actual[:, None]))/abs(actual[:, None])**2
        parts.append(contributions)
        # Steady Eq.48 subdivision defect with the original section rotations.
        fraction = float(data['fraction'][middle])
        qm = data['coarse_Q'][a]@exp(fraction*log(data['coarse_Q'][a].T@data['coarse_Q'][b]))
        um = qm@geometry['fine_node_reference'][middle]
        ua, ub = cs[a], cs[b]
        base = data['coarse_r'][b]-data['coarse_r'][a]-.5*s*(ua+ub)
        subdivision = .5*(s-s1)*ua+.5*(s-s2)*ub-.5*s*um
        rotation_change = -.5*s1*(fs[left]-ua)-.5*s*(fs[middle]-um)-.5*s2*(fs[right]-ub)
        position_change = endpoint_b-endpoint_a
        fine_sum = sum(geometry['fine_steady_residual'][children])*L
        steady_error = float(np.max(abs(base+subdivision+rotation_change+position_change-fine_sum)))
        assert steady_error<3e-13
        rows.append(dict(parent=int(parent), material_interval=geometry['coarse_wing_stations'][[int(parent),int(parent)+1]].tolist(),
            loaded_span_ft=float(data['fine_r'][middle, 1]), inserted_fraction=fraction,
            scalar_parts_real=scalar_parts.real.tolist(), scalar_parts_imag=scalar_parts.imag.tolist(),
            scalar_actual=[float(exact_scalar.real), float(exact_scalar.imag)],
            projections_percent=percentages.tolist(),
            mean_endpoint_span_change_degrees=[float(np.degrees(np.arctan2(np.linalg.norm(np.cross(fs[node], cs[old])),np.dot(fs[node], cs[old])))) for node,old in ((left,a),(right,b))],
            steady_original_residual_ft=base.tolist(), steady_subdivision_defect_ft=subdivision.tolist(),
            steady_rotation_change_ft=rotation_change.tolist(), steady_position_change_ft=position_change.tolist(),
            steady_split_closure_ft=steady_error))
    assert max(sum_error, residual_error)<2e-12 and null_error<2e-14
    totals = sum(parts)
    total_percent = 100*np.real(totals*np.conj(mapped['actual_change'][:, None]))/abs(mapped['actual_change'][:, None])**2
    expected = accepted(PREVIOUS/'projection')
    expected_values = []
    for channel in CHANNELS:
        entry = next(e for e in expected['entries'] if e['channel']==channel and e['case']=='compatible-repeat')
        j = expected['groups'].index('beam1:position')
        expected_values.append(complex(entry['contribution_real'][j], entry['contribution_imag'][j]))
    total_replay = float(max(abs(totals.sum(axis=1)-expected_values)))
    assert total_replay<2e-11
    np.savez_compressed(folder/'arrays.npz', contributions=parts, totals=totals, percentages=total_percent)
    return dict(frequency_hz=1.5, channels=CHANNELS, terms=terms, derivative_checks=checks,
        maximum_scalar_partition_error=sum_error, maximum_completed_residual_reconstruction_error=residual_error,
        maximum_left_null_error=null_error, total_wing_account_replay_error=total_replay,
        totals_percent=total_percent.tolist(), rows=rows,
        qualification='All components use the actual fine mean span at the inserted node and the same fine adjoint. This exact compatibility-row partition does not isolate full-aircraft equilibrium or discretization sensitivities. No aircraft solution or physical parameter changed.')


def report(folder, args):
    import csv
    import numpy as np
    result = accepted(STUDY/'audit-v2')
    data = packet(PREVIOUS/'capture')
    mapped = packet(map_folder('compatible-repeat'))
    previous = accepted(PREVIOUS/'projection')
    values = packet(STUDY/'audit-v2')['totals']
    rows = []
    totals = []
    for i, channel in enumerate(CHANNELS):
        entry = next(e for e in previous['entries'] if e['channel']==channel and e['case']=='compatible-repeat')
        j = previous['groups'].index('beam1:position')
        saved = complex(entry['contribution_real'][j], entry['contribution_imag'][j])
        actual = mapped['actual_change'][i]
        for term, value in zip(result['terms']+['numerical_remainder'], [*values[i], saved-sum(values[i])]):
            rows.append(dict(channel=channel, term=term, real=float(value.real), imag=float(value.imag),
                signed_projection_on_mesh_change_percent=float(100*np.real(value*actual.conjugate())/abs(actual)**2),
                complex_magnitude_percent_of_original_output=float(100*abs(value)/abs(data['coarse_output'][i]))))
        totals.append(dict(channel=channel, wing_position_real=saved.real, wing_position_imag=saved.imag,
            signed_projection_on_mesh_change_percent=float(100*np.real(saved*actual.conjugate())/abs(actual)**2),
            complex_magnitude_percent_of_original_output=float(100*abs(saved)/abs(data['coarse_output'][i])),
            whole_mesh_complex_change_percent_of_original=float(100*abs(actual)/abs(data['coarse_output'][i]))))
    span = []
    for item in result['rows']:
        for i, channel in enumerate(CHANNELS):
            for j, term in enumerate(result['terms']):
                span.append(dict(channel=channel, parent=item['parent'], loaded_span_ft=item['loaded_span_ft'], term=term,
                    signed_projection_on_mesh_change_percent=item['projections_percent'][i][j]))
    for name, records in [('equation-partition.csv', rows), ('output-context.csv', totals), ('spanwise-partition.csv', span)]:
        with (folder/name).open('x', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    colors = ['#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f']
    x = [row['loaded_span_ft'] for row in result['rows']]
    for j, label in enumerate(['Subdivision', 'Mean endpoint rotations', 'Position transport'], start=1):
        axes[0].plot(x, [row['projections_percent'][1][j] for row in result['rows']], '.-', color=colors[j-1], label=label)
    axes[0].plot(x, [sum(row['projections_percent'][1]) for row in result['rows']], '--', color=colors[3], label='Combined position account')
    axes[0].axhline(0, color='#555', linewidth=.6)
    axes[0].set(xlabel='Loaded spanwise position (ft)', ylabel='Signed projection onto complex roll mesh change (%)',
        title='Wing Eq.48: subdivision is the main term')
    axes[0].legend(fontsize=8)
    axes[1].bar(np.arange(4)-.2, [row['whole_mesh_complex_change_percent_of_original'] for row in totals], .4, color=colors[0], label='Whole mesh change')
    axes[1].bar(np.arange(4)+.2, [row['complex_magnitude_percent_of_original_output'] for row in totals], .4, color=colors[1], label='Wing position equation account')
    axes[1].set(xticks=np.arange(4), xticklabels=['Yaw rate', 'Roll rate', 'Sideslip', 'Bank'],
        ylabel='Complex change magnitude / original output (%)', title='Magnitude in context; these are not native errors')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.set_axisbelow(True); ax.grid(axis='y', alpha=.2)
    fig.suptitle('Daedalus at 1.5 Hz: exact row partition with the fine adjoint held fixed', fontsize=11)
    fig.savefig(folder/'position-compatibility.png', dpi=150)
    fig.savefig(folder/'position-compatibility.svg')
    plt.close(fig)
    return dict(channels=CHANNELS, frequency_hz=1.5, rows=rows, totals=totals,
        maximum_numerical_remainder_projection_percent=max(abs(row['signed_projection_on_mesh_change_percent']) for row in rows if row['term']=='numerical_remainder'),
        qualification='Signed equation-account projections can cancel. Complex magnitudes are not signed amplitude changes; all results compare OpenSwing meshes and do not establish a native ASWING pass.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['capture', 'audit', 'report'])
    parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts'/p for p in ('check_daedalus_mesh_residual.py', 'check_daedalus_mesh_zeros.py',
        'check_daedalus_structural_resolution.py', 'check_daedalus_source_operator.py')]
    inputs += [ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json', ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.pdf']
    inputs += list((ROOT/'openswing').glob('*.py'))
    for mesh in ('coarse', 'fine'):
        matrix, layout, seed = paths(mesh)
        inputs += [layout, seed]+[matrix/p for p in ('A.npz', 'M.npz')]
    folders = [PREVIOUS/'capture']
    if args['stage'] in ('audit', 'report'):
        folders += [STUDY/'capture', PREVIOUS/'projection', map_folder('compatible-repeat'), map_folder('objective-repeat')]
        folders += [PREVIOUS/f'adjoint-{channel}' for channel in CHANNELS]
    if args['stage']=='report':
        folders += [STUDY/'audit-v2']
    inputs += [folder/p for folder in folders for p in ('arrays.npz', 'result.json', 'terminal.json')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__=='__main__':
    main()
