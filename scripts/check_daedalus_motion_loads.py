"""Decompose the accepted harmonic airflow by prescribed motion source.

This is linear superposition at the saved coupled solution, not independent
aircraft responses, altered stiffnesses, or a fit to the reference drawing.
Each motion source receives the circulation solving the complete aerodynamic
block, including induced-flow feedback and the documented circulation lag.
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

STUDY = ROOT/'artifacts/daedalus-motion-loads-20261113'
SAVED = ROOT/'artifacts/daedalus-load-sensitivity-20261113/reference-dip'
MATRIX = SOURCE/'assembled-6.7'
FREQUENCY = 1.15737773741517
NAMES = ['control', 'frame', 'beam1', 'beam2', 'beam3', 'beam4', 'beam5']
COMPONENT_TAGS = dict(zip(NAMES, NAMES), full='full-v2')
FIN_NAMES = ['fin_translation', 'fin_rotation', 'fin_deformation']


def partition(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    system = dynamic(); n = system.network
    a, m = (sp.load_npz(MATRIX/name) for name in ('A.npz', 'M.npz'))
    b = np.load(MATRIX/'maps.npz')['B'][:, 0]
    z = np.load(SAVED/'arrays.npz')['state']
    omega = 2*np.pi*FREQUENCY; k = 1j*omega*m-a
    full_error = float(max(abs(k@z-b)))
    assert full_error < 2e-10, full_error
    gamma = np.arange(n.gamma_start, n.operating_start)
    operator = k[gamma][:, gamma].toarray()
    motions = np.zeros((system.size, len(NAMES)), complex)
    owner = np.full(system.size, -1, int)
    frame = np.r_[np.arange(n.operating_start, n.size), np.arange(system.frame_start, system.size)]
    motions[frame, 1] = z[frame]; owner[frame] = 1
    for i, beam in enumerate(range(1, 6), 2):
        _, nodes = n.station_nodes[beam]
        slots = np.r_[(6*nodes[:, None]+np.arange(6)).ravel(),
            (system.velocity_start+3*nodes[:, None]+np.arange(3)).ravel(),
            (system.velocity_start+3*n.nn+3*nodes[:, None]+np.arange(3)).ravel()]
        assert np.all(owner[slots] == -1)
        motions[slots, i] = z[slots]; owner[slots] = i
    omitted = np.flatnonzero((owner < 0) & ~np.isin(np.arange(system.size), gamma))
    omitted_circulation_error = float(max(abs(k[gamma][:, omitted]@z[omitted])))
    assert omitted_circulation_error < 1e-14
    rhs = -(k[gamma]@motions); rhs[:, 0] += b[gamma]
    solved = np.linalg.solve(operator, rhs)
    motions[gamma] = solved
    circulation_error = float(max(abs(solved.sum(axis=1)-z[gamma])))
    block_error = float(np.max(abs(operator@solved-rhs)))
    assert circulation_error < 2e-11 and block_error < 2e-12
    np.savez_compressed(folder/'arrays.npz', state=z, motions=motions,
        circulation=solved, circulation_operator=operator, circulation_rhs=rhs,
        owner=owner, omitted=omitted)
    return dict(frequency_hz=FREQUENCY, groups=NAMES, size=system.size,
        nodes=n.nn, circulation=n.ng, full_harmonic_absolute_residual=full_error,
        circulation_block_condition=float(np.linalg.cond(operator)),
        circulation_sum_absolute_error=circulation_error,
        circulation_block_absolute_error=block_error,
        omitted_internal_load_reaction_circulation_error=omitted_circulation_error,
        qualification='Motion components are prescribed from the accepted full coupled response. Their induced circulations include all surfaces and engine-flow feedback. They are not independently realizable coupled aircraft responses.')


def component(folder, args):
    import numpy as np
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    from openswing.frequency_response import HarmonicInput
    system = dynamic(); n = system.network; omega = 2*np.pi*FREQUENCY
    fine = args.group in FIN_NAMES
    saved = np.load(STUDY/('fin-partition' if fine else 'partition')/'arrays.npz')
    z = saved['state'] if args.group == 'full' else saved['motions'][:, (FIN_NAMES if fine else NAMES).index(args.group)]
    rate = 1j*omega*z
    forcing, _ = HarmonicInput(system, 'control.3', 0).at_frequency(omega)
    has_control = args.group in ('full', 'control')

    def sample(v, dv, force):
        state, _, options = system.physical_state(v, dv, force)
        residual, data = n.residual(state.x, detail=True, **options)
        values, wrenches, checks = groups(system, data)
        return values, wrenches, checks, residual[n.gamma_start:n.operating_start]

    zero = np.zeros(system.size); base = sample(zero, zero, None)
    keys = list(base[0]); stencils = []
    for step in (args.step, args.step/2):
        loads = np.zeros((system.size, len(keys)), complex)
        wrenches = np.zeros((6, len(keys)), complex)
        tangency = np.zeros(n.ng, complex)
        closure = 0.
        for part, function in enumerate((np.real, np.imag)):
            for offset, weight in [(-2, 1), (-1, -8), (1, 8), (2, -1)]:
                h = step*offset
                values, moment, checks, residual = sample(h*function(z), h*function(rate),
                    forcing(part, h) if has_control else None)
                factor = weight/(12*step)*(1 if part == 0 else 1j)
                loads += factor*np.column_stack([values[key] for key in keys])
                wrenches += factor*np.column_stack([moment[key] for key in keys])
                tangency += factor*residual
                closure = max(closure, checks['aerodynamic_wrench_closure'])
        stencils.append((loads, wrenches, tangency, closure))
    loads, wrenches, tangency, closure = stencils[-1]
    load_error = float(np.max(abs(loads-stencils[0][0])))
    wrench_error = float(np.max(abs(wrenches-stencils[0][1])))
    tangency_error = float(max(abs(tangency)))
    assert load_error < 2e-8 and wrench_error < 2e-6 and tangency_error < 2e-8
    replay = None
    if args.group == 'full':
        previous = np.load(SAVED/'arrays.npz')
        replay = dict(loads=float(np.max(abs(loads-previous['component_residuals']))),
            wrenches=float(np.max(abs(wrenches-previous['wrenches']))))
        assert replay['loads'] < 2e-8 and replay['wrenches'] < 2e-6
    np.savez_compressed(folder/'arrays.npz', state=z, component_residuals=loads,
        wrenches=wrenches, circulation_residual=tangency)
    rows = [dict(component=key, real=wrenches[:, i].real.tolist(),
        imag=wrenches[:, i].imag.tolist()) for i, key in enumerate(keys)]
    for key in ('beam1:lift', 'beam3:lift', 'beam3:rate_lift', 'beam3:apparent'):
        index = keys.index(key); print(args.group, key, wrenches[5, index], flush=True)
    return dict(group=args.group, frequency_hz=FREQUENCY, components=rows,
        keys=keys, max_scaled_load_step_difference=load_error,
        max_wrench_step_difference=wrench_error, harmonic_tangency_error=tangency_error,
        max_nonlinear_wrench_closure=closure, previous_full_replay=replay,
        qualification='Linear load contribution of a prescribed subset of the already-coupled motion, with induced circulation re-solved. Zero tangency does not imply this isolated motion satisfies structural or joint equations.')


def fin_partition(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    system = dynamic(); n = system.network; omega = 2*np.pi*FREQUENCY
    original = np.load(STUDY/'partition/arrays.npz')
    z = original['motions'][:, NAMES.index('beam3')]
    root = n.node(3, 0.); _, nodes = n.station_nodes[3]
    offset = system.r0[nodes]-system.r0[root]
    q = z[:6*n.nn].reshape(n.nn, 6)
    u, w = z[system.velocity_start:system.frame_start].reshape(2, n.nn, 3)
    motions = np.zeros((system.size, 3), complex)
    for i in range(2):
        pose = motions[:6*n.nn, i].reshape(n.nn, 6)
        velocity, rates = motions[system.velocity_start:system.frame_start, i].reshape(2, n.nn, 3)
        if i == 0:
            pose[nodes, :3] = q[root, :3]; velocity[nodes] = u[root]
        else:
            pose[nodes, :3] = np.cross(q[root, 3:], offset)/system.L
            pose[nodes, 3:] = q[root, 3:]
            velocity[nodes] = np.cross(system.W*w[root], offset)/system.V
            rates[nodes] = w[root]
    motions[:, 2] = z-motions[:, 0]-motions[:, 1]
    gamma = np.arange(n.gamma_start, n.operating_start); motions[gamma] = 0
    a, m = (sp.load_npz(MATRIX/name) for name in ('A.npz', 'M.npz'))
    k = 1j*omega*m-a
    rhs = -(k[gamma]@motions)
    motions[gamma] = np.linalg.solve(original['circulation_operator'], rhs)
    error = float(max(abs(motions.sum(axis=1)-z))); assert error < 2e-11
    # Rigid transport has the same zero-base local velocity definitions.
    kin = k[system.velocity_start:system.frame_start]@motions
    kin_error = float(np.max(abs(kin))); assert kin_error < 2e-11
    np.savez_compressed(folder/'arrays.npz', motions=motions, state=z)
    def complex_record(v):return dict(real=v.real.tolist(), imag=v.imag.tolist())
    return dict(frequency_hz=FREQUENCY, groups=FIN_NAMES, root_node=int(root), root_material_t=0.,
        root_translation_ft=complex_record(system.L*q[root, :3]),
        root_rotation_radians=complex_record(q[root, 3:]),
        root_velocity_ft_per_s=complex_record(system.V*u[root]),
        root_angular_rate_rad_per_s=complex_record(system.W*w[root]),
        state_sum_error=error, kinematic_definition_error=kin_error,
        qualification='Rigid transport is defined about the current loaded fin root. Remaining deformation is relative to that moving root. All three are parts of the same accepted motion, not new boundary conditions.')


def fin_report(folder, args):
    import numpy as np
    arrays = [np.load(STUDY/name/'arrays.npz') for name in FIN_NAMES]
    for name in FIN_NAMES:
        receipt = read(STUDY/name/'terminal.json'); assert receipt['returncode'] == 0 and receipt['process_reaped']
    original = np.load(STUDY/'beam3/arrays.npz')
    errors = {key:float(np.max(abs(sum(a[key] for a in arrays)-original[key])))
        for key in ('component_residuals', 'wrenches')}
    assert errors['component_residuals'] < 2e-8 and errors['wrenches'] < 2e-6
    keys = read(STUDY/'beam3/result.json')['keys']; rows = []
    for name, a in zip(FIN_NAMES, arrays):
        selected = [i for i, key in enumerate(keys) if key.startswith('beam3:') and key != 'beam3:stall']
        z = a['wrenches'][:, selected].sum(axis=1)
        rows.append(dict(motion=name, fin_wrench_real=z.real.tolist(), fin_wrench_imag=z.imag.tolist()))
        print(name, z[5], flush=True)
    return dict(frequency_hz=FREQUENCY, rows=rows, superposition_errors=errors,
        qualification='Exact first-order partition of the fin contribution within the saved coupled response. It does not measure a modified-aircraft Bode response.')


def report(folder, args):
    import numpy as np
    import csv
    for name, tag in COMPONENT_TAGS.items():
        terminal = read(STUDY/tag/'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        assert read(STUDY/tag/'plan.json')['arguments']['group'] == name
    records = {name:read(STUDY/tag/'result.json') for name, tag in COMPONENT_TAGS.items()}
    arrays = {name:np.load(STUDY/tag/'arrays.npz') for name, tag in COMPONENT_TAGS.items()}
    keys = records['full']['keys']
    assert all(v['keys'] == keys for v in records.values())
    errors = {key:float(np.max(abs(sum(arrays[name][key] for name in NAMES)-arrays['full'][key])))
        for key in ('component_residuals', 'wrenches')}
    assert errors['component_residuals'] < 2e-8 and errors['wrenches'] < 2e-6
    rows = []
    for name in NAMES:
        for i, key in enumerate(keys):
            z = arrays[name]['wrenches'][:, i]
            rows.append(dict(motion=name, load=key, real=z.real.tolist(), imag=z.imag.tolist()))
    with (folder/'yaw-moments.csv').open('x', newline='') as f:
        writer = csv.writer(f); writer.writerow(['motion', 'load', 'yaw_real_lbft_per_F3', 'yaw_imag_lbft_per_F3'])
        for row in rows:writer.writerow([row['motion'], row['load'], row['real'][5], row['imag'][5]])
    return dict(frequency_hz=FREQUENCY, rows=rows, superposition_errors=errors,
        qualification='This partitions prescribed actual motion and its aerodynamic response; it neither removes a beam from the coupled dynamics nor establishes the historical ASWING setup.')


def plot(folder, args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import re
    primary = read(STUDY/'report/result.json'); fine = read(STUDY/'fin-report/result.json')
    def moment(motion, load):
        return sum(complex(row['real'][5], row['imag'][5]) for row in primary['rows']
            if row['motion'] == motion and load(row['load']))
    fin = lambda key:key.startswith('beam3:') and key != 'beam3:stall'
    left = [('Rudder input', moment('control', fin)), ('Aircraft frame motion', moment('frame', fin))]
    left += [(label, complex(row['fin_wrench_real'][5], row['fin_wrench_imag'][5]))
        for label, row in zip(['Fin-root translation', 'Fin-root rotation', 'Fin deformation'], fine['rows'])]
    left += [('Other beams: induced flow', sum(moment(name, fin) for name in ['beam1', 'beam2', 'beam4', 'beam5']))]
    right = [('Aircraft frame motion', moment('frame', lambda key:key == 'beam1:lift')),
        ('Wing elastic motion', moment('beam1', lambda key:key == 'beam1:lift')),
        ('Control / other beams', sum(moment(name, lambda key:key == 'beam1:lift') for name in ['control', 'beam2', 'beam3', 'beam4', 'beam5']))]
    palette = re.findall(r'#[0-9a-fA-F]{6}', (ROOT/'web/plot-colors.js').read_text().split('surfaceColors = Object.freeze([')[1].split(']);')[0])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout='constrained')
    for ax, rows, title in zip(axes, [left, right], ['Fin: all aerodynamic loads', 'Wing: circulation lift']):
        ax.set_facecolor('#111827')
        for i, (label, value) in enumerate(rows):
            color = palette[i % len(palette)]
            ax.annotate('', xy=(value.real, value.imag), xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', color=color, lw=2))
            ax.plot([], [], color=color, lw=2, label=label)
        total = sum(v for _, v in rows)
        ax.plot(total.real, total.imag, '*', color='white', markersize=12, label='Sum')
        x = [0, total.real]+[v.real for _, v in rows]; y = [0, total.imag]+[v.imag for _, v in rows]
        margin = .12*max(np.ptp(x), np.ptp(y), 1.)
        ax.set_xlim(min(x)-margin, max(x)+margin); ax.set_ylim(min(y)-margin, max(y)+margin)
        ax.axhline(0, color='white', alpha=.25); ax.axvline(0, color='white', alpha=.25)
        ax.grid(color='white', alpha=.15); ax.set_aspect('equal', adjustable='box')
        ax.set_xlabel('Real moment [lb ft / native F3]'); ax.set_ylabel('Imaginary moment [lb ft / native F3]')
        ax.set_title(title); ax.legend(loc='upper center', bbox_to_anchor=(.5, -.20), ncol=2,
            facecolor='#111827', labelcolor='white', fontsize=7)
    fig.suptitle('Daedalus at 1.157378 Hz: body-z load cancellation\nPrescribed components of the same coupled motion; no physics or parameters changed')
    fig.savefig(folder/'motion-loads.png', dpi=160); fig.savefig(folder/'motion-loads.svg'); plt.close(fig)
    return dict(frequency_hz=FREQUENCY, fin=[dict(label=label, real=v.real, imag=v.imag) for label, v in left],
        wing_lift=[dict(label=label, real=v.real, imag=v.imag) for label, v in right],
        convention='ASWING body-z moments and exp(i*omega*t) phasors. These are not separate yaw-rate responses.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['partition', 'component', 'report', 'fin_partition', 'fin_report', 'plot'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--group', choices=NAMES+FIN_NAMES+['full'])
    parser.add_argument('--step', type=float, default=1e-3)
    args = parser.parse_args()
    if args.stage == 'component' and args.group is None:parser.error('--group is required')
    STUDY.mkdir(exist_ok=True); folder = STUDY/args.tag; folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs = [Path(__file__), ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_wing_paper.py', ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'examples/dae.asw', ROOT/'examples/dae-cruise-physical-mesh-project.json',
        SOURCE/'trim-6.7-1/state.json', ROOT/'docs/validation/aswing-authoritative-sources.json']
    inputs += [ROOT/'reference/aswing-authoritative-20261108'/f'drela-aswing-{kind}.pdf' for kind in ('steady', 'unsteady')]
    inputs += [MATRIX/name for name in ('A.npz', 'M.npz', 'maps.npz')]
    inputs += [SAVED/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    if args.stage in ('component', 'fin_partition'):
        partition_tag = 'fin-partition' if args.group in FIN_NAMES else 'partition'
        inputs += [STUDY/partition_tag/name for name in ('arrays.npz', 'result.json', 'terminal.json')]
    if args.stage == 'report':inputs += [STUDY/tag/name for tag in COMPONENT_TAGS.values() for name in ('arrays.npz', 'result.json', 'terminal.json', 'plan.json')]
    if args.stage == 'fin_report':inputs += [STUDY/tag/name for tag in FIN_NAMES+['beam3'] for name in ('arrays.npz', 'result.json', 'terminal.json', 'plan.json')]
    if args.stage == 'plot':
        inputs += [STUDY/tag/name for tag in ('report', 'fin-report') for name in ('result.json', 'terminal.json', 'plan.json')]
        inputs.append(ROOT/'web/plot-colors.js')
    pins = {os.path.abspath(p):pin(p) for p in inputs+list((ROOT/'openswing').glob('*.py'))}
    write(folder/'plan.json', dict(observed_utc=utc(), arguments=vars(args), inputs_sha256=pins, limits=LIMITS,
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_MMAP_THRESHOLD_', 'MALLOC_TRIM_THRESHOLD_')}))
    started = time.monotonic(); sys.stdout.flush(); pid = os.fork()
    if pid == 0:
        code = 0
        for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):os.environ[key] = '1'
        resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2); sys.path.insert(0, str(ROOT))
        with (folder/'stdout.log').open('x') as out, (folder/'stderr.log').open('x') as err:
            os.dup2(out.fileno(), 1); os.dup2(err.fileno(), 2)
            try:write(folder/'result.json', globals()[args.stage](folder, args))
            except BaseException:traceback.print_exc(); code = 1
            sys.stdout.flush(); sys.stderr.flush()
        os._exit(code)
    reaped = 0; timed_out = False
    try:
        while not reaped:
            reaped, status, usage = os.wait4(pid, os.WNOHANG)
            if reaped:break
            if time.monotonic()-started > LIMITS['wall_seconds']:
                timed_out = True; os.kill(pid, signal.SIGKILL); reaped, status, usage = os.wait4(pid, 0); break
            time.sleep(.05)
    finally:
        if not reaped:os.kill(pid, signal.SIGKILL); reaped, status, usage = os.wait4(pid, 0)
    terminal = dict(observed_utc=utc(), returncode=os.waitstatus_to_exitcode(status), process_reaped=True,
        timed_out=timed_out, cpu_seconds=usage.ru_utime+usage.ru_stime, wall_seconds=time.monotonic()-started,
        peak_rss_kib=usage.ru_maxrss, limits=LIMITS, inputs_unchanged=all(pin(p) == h for p, h in pins.items()))
    write(folder/'terminal.json', terminal); print(json.dumps(terminal), flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__ == '__main__':main()
