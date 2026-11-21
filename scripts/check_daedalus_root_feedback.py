"""Bounded diagnostic of fin-root-motion aerodynamic feedback.

Delete only a declared aerodynamic tangent contribution at the accepted base.
All mechanical, joint, real-inertia and free-frame equations remain intact.
This is an affine diagnostic, not a changed aircraft or an ASWING match.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

from check_daedalus_load_sensitivity import ROOT, SOURCE, LIMITS, read, write, pin, utc

STUDY = ROOT/'artifacts/daedalus-root-feedback-20261113'
MATRIX = SOURCE/'assembled-6.7'
CASES = {'dip': (1.15737773741517, 'reference-dip'), 'slow': (.2, 'slow-animation')}
AXES = ['translation_x', 'translation_y', 'translation_z', 'rotation_x', 'rotation_y', 'rotation_z']


def basis(system, omega):
    import numpy as np
    n = system.network
    root = n.node(3, 0.); _, nodes = n.station_nodes[3]
    offset = system.r0[nodes]-system.r0[root]
    transport = np.zeros((system.size, 6), complex)
    extract = np.zeros((6, system.size))
    extract[:, 6*root:6*root+6] = np.diag([system.L]*3+[1.]*3)
    for axis in range(6):
        direction = np.eye(3)[axis % 3]
        pose = transport[:6*n.nn, axis].reshape(n.nn, 6)
        velocity, rotation_rate = transport[system.velocity_start:system.frame_start, axis].reshape(2, n.nn, 3)
        if axis < 3:
            pose[nodes, :3] = direction/system.L
            velocity[nodes] = 1j*omega*direction/system.V
        else:
            shift = np.cross(direction, offset)
            pose[nodes, :3] = shift/system.L
            pose[nodes, 3:] = direction
            velocity[nodes] = 1j*omega*shift/system.V
            rotation_rate[nodes] = 1j*omega*direction/system.W
    np.testing.assert_allclose(extract@transport, np.eye(6), atol=1e-14, rtol=0)
    return transport, extract, root


def column(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    system = dynamic(); n = system.network
    omega = 2*np.pi*CASES[args.case][0]
    transport, extract, root = basis(system, omega)
    z = transport[:, args.axis]; rate = 1j*omega*z

    def sample(v, dv):
        state, _, options = system.physical_state(v, dv, None)
        residual, data = n.residual(state.x, detail=True, **options)
        values, _, _ = groups(system, data)
        # Real inertia/gravity are excluded; circulation retains its COMPLETE
        # residual, including tangency, section polar, lag and stall terms.
        result = sum(value for key, value in values.items() if key != 'real_mass_gravity_applied')
        result[n.gamma_start:n.operating_start] = residual[n.gamma_start:n.operating_start]
        return result

    estimates = []
    for step in (1e-3, 5e-4):
        derivative = np.zeros(system.size, complex)
        for part, function in enumerate((np.real, np.imag)):
            for offset, weight in [(-2, 1), (-1, -8), (1, 8), (2, -1)]:
                h = step*offset
                derivative += weight/(12*step)*(1 if part == 0 else 1j)*sample(h*function(z), h*function(rate))
        estimates.append(derivative)
    error = float(max(abs(estimates[1]-estimates[0])))
    assert error < 2e-8, error
    a, m = (sp.load_npz(MATRIX/name) for name in ('A.npz', 'M.npz'))
    k = 1j*omega*m-a
    kinematic_error = float(max(abs((k@z)[system.velocity_start:system.frame_start])))
    assert kinematic_error < 2e-11
    allowed = np.r_[np.arange(6*n.ne, 6*(n.ne+n.nn)), np.arange(n.gamma_start, n.size)]
    omitted = np.setdiff1d(np.arange(system.size), allowed)
    assert not np.any(estimates[1][omitted])
    np.savez_compressed(folder/'arrays.npz', column=estimates[1], coarse=estimates[0], transport=z, extract=extract)
    return dict(frequency_hz=CASES[args.case][0], axis=AXES[args.axis], root_node=root,
        coordinate_units='ft for translations, rad for spatial rotations, relative to the aircraft frame',
        max_scaled_derivative_step_difference=error, kinematic_error=kinematic_error,
        max_column=float(max(abs(estimates[1]))), nonlinear_evaluations=16)


def solve(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from openswing.frequency_response import harmonic_solve
    from openswing.harmonic_structure import ReusableBeamStructure
    system = dynamic(); n = system.network
    frequency, saved_tag = CASES[args.case]; omega = 2*np.pi*frequency
    datasets = [np.load(STUDY/f'{args.case}-{axis}'/'arrays.npz') for axis in range(6)]
    u = np.column_stack([data['column'] for data in datasets]); extract = datasets[0]['extract']
    transport = np.column_stack([data['transport'] for data in datasets])
    for data in datasets:np.testing.assert_array_equal(data['extract'], extract)
    _, expected_extract, root = basis(system, omega)
    np.testing.assert_array_equal(extract, expected_extract)
    a, m = (sp.load_npz(MATRIX/name) for name in ('A.npz', 'M.npz'))
    maps = np.load(MATRIX/'maps.npz'); b = maps['B'][:, 0]; c = maps['C']; k = 1j*omega*m-a
    for pencil in (a, m):
        for array in (pencil.data, pencil.indices, pencil.indptr):array.flags.writeable=False
    structure = ReusableBeamStructure(a,m,np.r_[np.arange(618),np.arange(1266,1296)],np.arange(1266),np.arange(1384,2032),np.arange(1384,2032))
    solved, baseline_checks = harmonic_solve(a, m, np.column_stack([b, u]), omega, _structure=structure)
    z, inverse_u = solved[:, 0], solved[:, 1:]
    saved = np.load(ROOT/'artifacts/daedalus-load-sensitivity-20261113'/saved_tag/'arrays.npz')['state']
    replay = float(max(abs(z-saved))); assert replay < 2e-11
    q = extract@z
    gamma = np.arange(n.gamma_start, n.operating_start)
    gamma_response = np.linalg.solve(k[gamma][:, gamma].toarray(), u[gamma])
    resolved_u = u-k[:, gamma]@gamma_response
    tangency = float(np.max(abs(resolved_u[gamma]))); assert tangency < 2e-11
    prior_replay = {}
    if args.case == 'dip':
        for label, indices in [('fin_translation', np.arange(3)), ('fin_rotation', np.arange(3,6))]:
            prior = ROOT/'artifacts/daedalus-motion-loads-20261113'/label
            keys = read(prior/'result.json')['keys']
            loads = np.load(prior/'arrays.npz')['component_residuals']
            expected = loads[:, [i for i,key in enumerate(keys) if key != 'real_mass_gravity_applied']].sum(axis=1)
            expected[gamma] = 0.  # Earlier accounting separately stored stall, not tangency.
            error = float(max(abs(resolved_u[:, indices]@q[indices]-expected)))
            assert error < 2e-8, (label, error)
            prior_replay[label] = error
    def complex_record(value):return dict(real=value.real.tolist(), imag=value.imag.tolist())
    entries = []; states = []
    for label, indices in [('translation', np.arange(3)), ('rotation', np.arange(3,6)), ('both', np.arange(6))]:
        loop = extract[indices]@inverse_u[:, indices]
        small = np.eye(len(indices))+loop
        removed = z-inverse_u[:, indices]@np.linalg.solve(small, q[indices])
        # This direct full-coordinate solve independently checks the low-rank
        # identity and subjects the MODIFIED pencil to the usual condition gate.
        update = sp.csc_matrix(u[:, indices])@sp.csc_matrix(extract[indices])
        direct, checks = harmonic_solve(a-update, m, b, omega)
        state_error = float(max(abs(direct-removed))); assert state_error < 2e-10
        residual = float(max(abs(k@removed+u[:, indices]@(extract[indices]@removed)-b)))
        assert residual < 2e-9
        # dH/deta at eta=1, where eta multiplies the named feedback.
        derivative = c@(inverse_u[:, indices]@q[indices]); output = c@z
        entries.append(dict(removed_feedback=label, output=complex_record(c@direct),
            magnitude=abs(c@direct).tolist(), root_motion=complex_record(extract@direct),
            local_log_magnitude_sensitivity=np.real(derivative/output).tolist(),
            local_phase_sensitivity_deg=(np.imag(derivative/output)*180/np.pi).tolist(),
            identity_condition=float(np.linalg.cond(small)), loop=complex_record(loop),
            direct_vs_low_rank_state_error=state_error, modified_residual=residual, solve_checks=checks))
        states.append(direct)
    full_q = extract@z
    # Individual root axes' first variations add exactly to translation/rotation groups.
    individual = c@inverse_u*full_q[None,:]
    candidates = [v for v in n.constraints if v['kind']=='joint' and v['a']==n.node(4,20.) and v['b']==root]
    assert len(candidates)==1 and candidates[0]['type']==0
    reaction_start = 6*(n.nn+n.ne)+candidates[0]['sl'].start
    fin_reaction = -z[reaction_start:reaction_start+6]*np.array([n.F]*3+[n.F*n.L]*3)
    np.savez_compressed(folder/'arrays.npz', state=z, states=np.column_stack(states), u=u,
        extract=extract, transport=transport, inverse_u=inverse_u, gamma_response=gamma_response,
        resolved_u=resolved_u, root_motion=full_q, individual_output_derivatives=individual)
    result = dict(frequency_hz=frequency, channels=['yaw_rate','roll_rate','sideslip','bank'],
        baseline_output=complex_record(c@z), baseline_magnitude=abs(c@z).tolist(),
        baseline_root_motion=complex_record(full_q), baseline_fin_attachment_wrench=complex_record(fin_reaction),
        reaction_units='lb and lb ft, body axes, force/couple applied by boom to fin at its root',
        baseline_solve_checks=baseline_checks, saved_baseline_replay_error=replay,
        resolved_circulation_error=tangency, prior_motion_load_replay=prior_replay,
        individual_axes=AXES, individual_log_magnitude_sensitivity=np.real(individual/(c@z)[:,None]).tolist(),
        diagnostics=entries, qualification='Fixed-equilibrium deletion of ONLY the aerodynamic tangent caused by fin rigid transport about its root. Fin deformation, real inertia, boom mechanics, joints, free frame and complete circulation coupling remain. No trim, physical parameter change, native reference pass or independent equation validation is claimed.')
    print(json.dumps(dict(frequency=frequency, baseline=result['baseline_magnitude'],
        diagnostics=[{k:v for k,v in entry.items() if k in ('removed_feedback','magnitude','local_log_magnitude_sensitivity')} for entry in entries])), flush=True)
    return result


def report(folder, args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    samples = [read(STUDY/tag/'result.json') for tag in ('slow-solve','dip-solve-v2')]
    with (ROOT/'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:
        reference, = [row for row in csv.DictReader(stream) if row['channel']=='yaw_rate' and abs(float(row['frequency_Hz'])-CASES['dip'][0])<1e-12]
    reference_magnitude = float(reference['reference_drawing_magnitude'])
    palette = re.findall(r"'([^']+)'", (ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827',
        'text.color':'white','axes.labelcolor':'white','xtick.color':'white','ytick.color':'white',
        'axes.edgecolor':'#9ca3af','font.size':9})
    fig, axes = plt.subplots(1,2,figsize=(12,5),layout='constrained')
    values = np.array([[s['baseline_magnitude'][0]]+[d['magnitude'][0] for d in s['diagnostics']] for s in samples])
    labels = ['Full model','Translation feedback removed','Rotation feedback removed','Both removed']
    x = np.arange(len(samples)); width=.19
    for index,label in enumerate(labels):
        axes[0].bar(x+(index-1.5)*width,values[:,index],width,color=palette[index],label=label)
    axes[0].scatter([1],[reference_magnitude],color='white',marker='_',s=220,zorder=5,label='Drela drawing at 1.157 Hz')
    axes[0].set_xticks(x,['0.2 Hz','1.157 Hz']); axes[0].set_ylabel('Yaw magnitude [deg/s per native F3]')
    axes[0].set_title('Coupled response with specified feedback deleted')
    axes[0].legend(fontsize=8,facecolor='#111827',labelcolor='white',loc='upper left')
    axes[0].set_ylim(0,.275)
    selected = [1,3,5]
    for index,s in enumerate(samples):
        sens=np.array(s['individual_log_magnitude_sensitivity'])[0,selected]
        axes[1].bar(np.arange(3)+(index-.5)*.35,sens,.35,color=palette[index],label=f"{s['frequency_hz']:.3g} Hz")
    axes[1].set_xticks(np.arange(3),['Lateral translation','Roll rotation','Yaw rotation'])
    axes[1].set_ylabel('Yaw magnitude change [%] for +1% feedback multiplier')
    axes[1].set_title('Local sensitivity at the unchanged full model')
    axes[1].legend(facecolor='#111827',labelcolor='white')
    for ax in axes:ax.axhline(0,color='white',alpha=.4,linewidth=.8);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    fig.suptitle('Daedalus fin-root aerodynamic feedback\nFixed-equilibrium diagnostics; no physical parameter fitted or default changed')
    fig.savefig(folder/'root-feedback.png',dpi=160);fig.savefig(folder/'root-feedback.svg');plt.close(fig)
    with (folder/'outputs.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['frequency_hz','diagnostic','channel','real','imag','magnitude'])
        for s in samples:
            for label,value in [('full',s['baseline_output'])]+[(d['removed_feedback']+'_removed',d['output']) for d in s['diagnostics']]:
                for i,channel in enumerate(s['channels']):
                    v=complex(value['real'][i],value['imag'][i]);writer.writerow([s['frequency_hz'],label,channel,v.real,v.imag,abs(v)])
    jobs = [p for p in STUDY.iterdir() if (p/'terminal.json').exists()]
    terminals = [read(p/'terminal.json') for p in jobs]
    pin_checks=0
    for job,terminal in zip(jobs,terminals):
        assert terminal['process_reaped'] and terminal['inputs_unchanged'] and not terminal['timed_out']
        assert terminal['cpu_seconds'] < LIMITS['cpu_seconds'] and terminal['wall_seconds'] < LIMITS['wall_seconds']
        assert terminal['returncode'] == (1 if job.name=='dip-solve' else 0)
        pins=read(job/'plan.json')['inputs_sha256']
        for path,expected in pins.items():
            actual=pin(job/'runner.py') if path==str(Path(__file__)) else pin(path)
            assert actual==expected,(job,path)
            pin_checks+=1
    columns=[read(STUDY/f'{case}-{axis}'/'result.json') for case in CASES for axis in range(6)]
    result = dict(samples=samples, reference_drawing=reference, derivative_columns=len(columns), nonlinear_evaluations=sum(c['nonlinear_evaluations'] for c in columns),
        maximum_column_step_difference=max(c['max_scaled_derivative_step_difference'] for c in columns),
        maximum_transport_kinematic_error=max(c['kinematic_error'] for c in columns),
        jobs_checked=len(jobs), input_hash_checks=pin_checks, failed_retained_jobs=['dip-solve'],
        maximum_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        maximum_wall_seconds=max(t['wall_seconds'] for t in terminals),
        maximum_peak_rss_kib=max(t['peak_rss_kib'] for t in terminals),
        full_matrix_comparisons=sum(len(s['diagnostics']) for s in samples),
        maximum_direct_vs_low_rank_state_error=max(d['direct_vs_low_rank_state_error'] for s in samples for d in s['diagnostics']),
        baseline_yaw_reduction_relative_to_feedback_removed_percent=[100*(1-s['baseline_magnitude'][0]/s['diagnostics'][-1]['magnitude'][0]) for s in samples])
    print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['column','solve','report'])
    parser.add_argument('--case', choices=list(CASES))
    parser.add_argument('--axis', type=int, choices=range(6))
    parser.add_argument('--tag', required=True); args = parser.parse_args()
    if args.stage=='column' and args.axis is None:parser.error('--axis is required')
    if args.stage!='report' and args.case is None:parser.error('--case is required')
    STUDY.mkdir(exist_ok=True); folder=STUDY/args.tag; folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs = [Path(__file__), ROOT/'scripts/check_daedalus_wing_paper.py', ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_source_operator.py', ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json',
        SOURCE/'trim-6.7-1/state.json', ROOT/'docs/validation/aswing-authoritative-sources.json']
    inputs += [ROOT/'reference/aswing-authoritative-20261108'/f'drela-aswing-{kind}.pdf' for kind in ('steady','unsteady')]
    inputs += [MATRIX/name for name in ('A.npz','M.npz','maps.npz')]
    if args.stage=='solve':
        inputs += [STUDY/f'{args.case}-{i}'/name for i in range(6) for name in ('arrays.npz','result.json','terminal.json')]
        inputs += [ROOT/'artifacts/daedalus-load-sensitivity-20261113'/CASES[args.case][1]/'arrays.npz']
        if args.case=='dip':inputs += [ROOT/'artifacts/daedalus-motion-loads-20261113'/label/name for label in ('fin_translation','fin_rotation') for name in ('arrays.npz','result.json')]
    if args.stage=='report':
        inputs += [path/name for path in STUDY.iterdir() if (path/'terminal.json').exists() for name in ('plan.json','terminal.json','runner.py')]
        inputs += [STUDY/tag/'result.json' for tag in ['slow-solve','dip-solve-v2']+[f'{case}-{axis}' for case in CASES for axis in range(6)]]
        inputs.append(ROOT/'web/plot-colors.js')
        inputs.append(ROOT/'docs/validation/daedalus-rudder-four-outputs.csv')
    pins = {str(p):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    write(folder/'plan.json', dict(observed_utc=utc(), arguments=vars(args), limits=LIMITS, inputs_sha256=pins,
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}))
    started=time.monotonic(); sys.stdout.flush(); pid=os.fork()
    if pid==0:
        code=0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2);sys.path.insert(0,str(ROOT))
        with (folder/'stdout.log').open('x') as out,(folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
            try:write(folder/'result.json',globals()[args.stage](folder,args))
            except BaseException:traceback.print_exc();code=1
            sys.stdout.flush();sys.stderr.flush()
        os._exit(code)
    reaped=0;timed_out=False
    try:
        while not reaped:
            reaped,status,usage=os.wait4(pid,os.WNOHANG)
            if reaped:break
            if time.monotonic()-started>LIMITS['wall_seconds']:
                timed_out=True;os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0);break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid,signal.SIGKILL);reaped,status,usage=os.wait4(pid,0)
    terminal=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,
        timed_out=timed_out,cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',terminal);print(json.dumps(terminal),flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__=='__main__':main()
