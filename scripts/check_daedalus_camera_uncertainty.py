"""Finite camera-profile diagnostics for native Daedalus animation evidence.

Only image calibration parameters vary. No aerodynamic/structural parameter,
load, harmonic state or historical Bode target is fitted. Constrained profiles
demonstrate sensitivity, not statistical confidence intervals.
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

from check_daedalus_load_sensitivity import ROOT, LIMITS, read, write, pin, utc

CAMERA = ROOT/'artifacts/daedalus-animation-calibration-20261113'
STUDY = ROOT/'artifacts/daedalus-camera-uncertainty-20261113'


def profile(folder, args):
    import numpy as np
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation
    cameras = sum([read(CAMERA/f'camera-joint-{start}/result.json')['fits']
        for start in (0, 20, 40, 60, 80)], [])
    cam, = [row for row in cameras if row['name'] == args.movie and row['frame'] == args.frame and row['perspective']]
    assert cam['success']
    xz = np.array(read(CAMERA/'fairing-pieces/result.json')['literal_outline_xz'])
    fairing = np.c_[xz[:, 0], np.zeros(len(xz)), xz[:, 1]]
    angle = np.linspace(0, 2*np.pi, 181, endpoint=False)
    disk = np.c_[np.full(len(angle), -6.5), 5.5*np.cos(angle), 5.5*np.sin(angle)]
    angle = np.linspace(0, 2*np.pi, 180, endpoint=False)
    normals = np.c_[np.cos(angle), np.sin(angle)]
    target = np.concatenate([np.max(normals@np.array(cam[key]).T, axis=1)
        for key in ('observed_fairing', 'observed_disk')])
    seed = read(CAMERA/'full-states/equilibrium.json')
    stations, nodes = seed['identity']['stations']['3']; root = np.array(seed['positions'])[nodes[stations.index(0.)]]
    initial = np.array(cam['parameters'])
    active = np.array([0,1,2,4,5,7,8]) if args.fixed_optics else np.arange(9)
    low = np.r_[[-4.]*3, 5., 250., 300., -.02, 0., 0.]
    high = np.r_[[4.]*3, 20., 550., 550., .02, 1.5, 1.5]

    def project(p, shape):
        v = shape@Rotation.from_rotvec(p[:3]).as_matrix().T
        return p[3]*v[:, :2]/(1+p[6]*v[:, 2, None])+p[4:6]

    def residual(p):
        return np.concatenate([np.max(normals@project(p, shape).T, axis=1)+p[7+i]
            for i, shape in enumerate((fairing, disk))])-target

    base_residual = residual(initial); base_root = project(initial, root[None])[0]
    rms = lambda v:float(np.sqrt(np.mean(v*v)))
    assert abs(rms(base_residual)-cam['support_rms_px']) < 1e-11
    moving_shape = None; center_shift = None; baseline_center = None; fin_observed = None
    if args.fin_harmonic:
        from openswing.asw import parse_asw
        from openswing.geometry import surface_frame
        beam = next(b for b in parse_asw((ROOT/'examples/dae.asw').read_text(),
            beam_interpolation='drela-segspl-v1').beams if b.index == 3)
        frequency = 1. if args.movie == 'fast-rudder' else .2
        state, = [s for s in read(CAMERA/'full-states/result.json')['samples'] if s['frequency_hz'] == frequency]
        field = state['beams']['3']; ids = np.array(field['indices']); t = np.array(field['stations'])
        r = np.array(seed['positions'])[ids]
        q = Rotation.from_rotvec(np.array(seed['rotations'])[ids]).as_matrix()
        chord_direction = np.einsum('nij,nj->ni', q, surface_frame(beam,t)[:,:,0])
        translation = np.array(field['translation_real'])+1j*np.array(field['translation_imag'])
        rotation = np.array(field['rotation_real'])+1j*np.array(field['rotation_imag'])
        phase = 2*np.pi*args.frame/90; shapes = []
        for fraction in (0.,1.):
            arm = (beam.value('chord',t)*(fraction-beam.value('Xax',t)))[:,None]*chord_direction
            shapes.append(r+arm+40*np.real((translation+np.cross(rotation,arm))*np.exp(1j*phase)))
        moving_shape = np.concatenate(shapes)
        center = lambda p:(project(p,moving_shape).min(axis=0)+project(p,moving_shape).max(axis=0))/2
        baseline_center = center(initial)
        original, = [r for r in read(CAMERA/'fin-outline-connected/result.json')['comparisons'] if r['name'] == args.movie]
        sample, = [s for s in original['samples'] if s['frame'] == args.frame]
        fin_observed = np.array(sample['observed_hull'])
        np.testing.assert_allclose(baseline_center,sample['predicted_center_width_height'][:2],rtol=0,atol=1e-10)
        observed_fit = np.array(original['metrics']['observed']['mean_cos_sin'])[:, :2]
        predicted_fit = np.array(original['metrics']['predicted']['mean_cos_sin'])[:, :2]
        # Only the oscillatory discrepancy; the constant mean mismatch is
        # preserved. This is an ambiguity probe, not a replacement camera fit.
        center_shift = (observed_fit-predicted_fit)[1:].T@np.array([np.cos(phase),np.sin(phase)])
    # Dimensionless camera coordinates avoid mixing inverse-feet and pixels
    # in the diagnostic SVD. Active padding bounds are reported, not ignored
    # by the finite constrained profiles below.
    scales = np.array([1., 1., 1., 10., 100., 100., .01, 1., 1.])
    widths = (1e-5, 5e-6); derivatives = []
    for step in widths:
        j = []; h = []
        for i in range(9):
            d = np.zeros(9); d[i] = step*scales[i]
            j.append((residual(initial+d)-residual(initial-d))/(2*step))
            h.append((project(initial+d, root[None])[0]-project(initial-d, root[None])[0])/(2*step))
        derivatives.append((np.array(j).T, np.array(h).T))
    j, h = (value[:,active] for value in derivatives[-1])
    u, singular, vt = np.linalg.svd(j, full_matrices=False)
    assert singular[-1] > 1e-10
    propagation = (h@vt.T/singular)@u.T
    observation_gain = np.linalg.svd(propagation, compute_uv=False)*np.sqrt(len(target))
    profiles = []
    for displacement in ((1.,) if args.fin_harmonic else (-args.displacement, args.displacement)):
        wanted = baseline_center+center_shift if args.fin_harmonic else base_root[1]+displacement
        def constraint_value(p):
            return center(p)-wanted if args.fin_harmonic else np.array([project(p,root[None])[0,1]-wanted])
        def objective(p):return np.r_[residual(p),100*constraint_value(p)]
        def full(value):
            p = initial.copy();p[active] = value;return p
        fit = least_squares(lambda value:objective(full(value)), initial[active], bounds=(low[active],high[active]), x_scale=scales[active],
            max_nfev=100, ftol=1e-11, xtol=1e-11, gtol=1e-9)
        parameters = full(fit.x)
        observed = project(parameters,root[None])[0]
        r = residual(parameters);constraint = constraint_value(parameters)
        assert fit.success and max(abs(constraint)) < .002, (fit.message,constraint)
        row = dict(requested_vertical_shift_px=None if args.fin_harmonic else displacement,
            requested_fin_center_shift_px=None if center_shift is None else center_shift.tolist(),
            actual_fin_center_shift_px=None if moving_shape is None else (center(parameters)-baseline_center).tolist(),
            actual_root_shift_px=(observed-base_root).tolist(),
            constraint_error_px=constraint.tolist(), parameters=parameters.tolist(), optimizer_success=bool(fit.success),
            optimizer_message=fit.message, evaluations=int(fit.nfev),
            support_rms_px=rms(r), support_max_px=float(max(abs(r))),
            fairing_rms_px=rms(r[:180]), disk_rms_px=rms(r[180:]),
            support_prediction_change_rms_px=rms(r-base_residual),
            support_prediction_change_max_px=float(max(abs(r-base_residual))),
            active_bounds=fit.active_mask.tolist(),
            projected_fairing=project(parameters,fairing).tolist(),projected_disk=project(parameters,disk).tolist())
        if moving_shape is not None:
            def centered_support(shape):
                center = (shape.min(axis=0)+shape.max(axis=0))/2
                return np.max(normals@(shape-center).T,axis=1)
            before = centered_support(project(initial,moving_shape))
            after = centered_support(project(parameters,moving_shape))
            native = centered_support(fin_observed)
            row.update(baseline_fin_centered_outline_rms_px=rms(before-native),
                profiled_fin_centered_outline_rms_px=rms(after-native),
                fin_centered_outline_change_rms_px=rms(after-before))
        profiles.append(row)
        print(args.movie, args.frame, displacement, row['actual_root_shift_px'],
            'calibration RMS', row['support_rms_px'], 'change RMS', row['support_prediction_change_rms_px'], flush=True)
    np.savez_compressed(folder/'arrays.npz', camera_jacobian=j, root_jacobian=h,
        singular_values=singular, root_propagation=propagation, baseline_residual=base_residual,
        baseline_parameters=initial, parameter_scales=scales)
    return dict(movie=args.movie, frame=args.frame, frequency_hz=1. if args.movie == 'fast-rudder' else .2,
        mode='two-coordinate fin-center harmonic discrepancy' if args.fin_harmonic else 'vertical root sensitivity',
        fixed_optics=args.fixed_optics,active_camera_parameter_indices=active.tolist(),
        baseline_root_px=base_root.tolist(), root_body_ft=root.tolist(), baseline_camera=cam,
        baseline_support_rms_px=rms(base_residual), baseline_support_max_px=float(max(abs(base_residual))),
        normalized_jacobian_singular_values=singular.tolist(),
        normalized_jacobian_condition=float(singular[0]/singular[-1]),
        jacobian_width_max_absolute_difference=float(np.max(abs(j-derivatives[0][0][:,active]))),
        root_jacobian_width_max_absolute_difference=float(np.max(abs(h-derivatives[0][1][:,active]))),
        local_unconstrained_root_gain_px_per_support_rms_px=observation_gain.tolist(),
        profiles=profiles, qualifications=[
            'Finite bounded camera profiles use the same raw fairing/disk hulls and calibration model as the earlier image study. Fixed-optics profiles retain that frame\'s scale and inverse distance exactly; only orientation, image offset and raster padding vary.',
            'The fin root is a current-model probe point, not a newly measured native landmark.',
            'Vertical root probes do not use fin observations. The optional two-coordinate fin-center profile deliberately imposes the observed harmonic center discrepancy to test identifiability, without changing the predicted physical fin shape.',
            'Local SVD gains ignore active inequality bounds; the finite profiles retain all original bounds.',
            'Raster support directions are correlated. RMS is descriptive, not an independent Gaussian noise model or confidence interval.',
            'The current model state, native image and physical parameters are unchanged.'])


def report(folder, args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    records = []
    for part in args.parts:
        terminal = read(part/'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        records.append(read(part/'result.json'))
    records.sort(key=lambda row:(row['movie'], row['frame']))
    rows = [r for r in records if r['movie'] == 'fast-rudder' and r['fixed_optics']
        and r['mode'] == 'two-coordinate fin-center harmonic discrepancy']
    assert [r['frame'] for r in rows] == [0,20,40,60,80]
    frame = [r['frame'] for r in rows]
    fig, axes = plt.subplots(1,2,figsize=(11,5),layout='constrained')
    axes[0].plot(frame,[r['baseline_support_rms_px'] for r in rows],'ko-',label='Original camera')
    axes[0].plot(frame,[r['profiles'][0]['support_rms_px'] for r in rows],'o--',color='#ff0000',label='Camera-pose ambiguity probe')
    axes[0].set_ylabel('Fairing + propeller outline RMS [px]')
    axes[0].set_title('Calibration outlines')
    axes[1].plot(frame,[r['profiles'][0]['baseline_fin_centered_outline_rms_px'] for r in rows],'ko-',label='Original camera')
    axes[1].plot(frame,[r['profiles'][0]['profiled_fin_centered_outline_rms_px'] for r in rows],'o--',color='#ff0000',label='Camera-pose ambiguity probe')
    axes[1].set_ylabel('Fin outline RMS after centering [px]')
    axes[1].set_title('Fin shape: center translation removed')
    for ax in axes:ax.set_xlabel('1 Hz animation frame');ax.grid(alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('Fin-center motion discrepancy can be absorbed by camera pose\nScale and perspective held fixed; physical motion unchanged; this is not validation')
    fig.savefig(folder/'camera-profiles.png', dpi=160); fig.savefig(folder/'camera-profiles.svg'); plt.close(fig)
    return dict(records=records, qualification='Feasible camera sensitivity profiles, not a change to the accepted calibration, an inferred native motion, or a statistical confidence interval.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['profile', 'report']); parser.add_argument('--tag', required=True)
    parser.add_argument('--movie', choices=['slow-rudder', 'fast-rudder'], default='fast-rudder')
    parser.add_argument('--frame', type=int, default=0); parser.add_argument('--displacement', type=float, default=1.)
    parser.add_argument('--fin-harmonic', action='store_true')
    parser.add_argument('--fixed-optics', action='store_true')
    parser.add_argument('--parts', type=Path, nargs='+'); args = parser.parse_args()
    if args.stage == 'report' and not args.parts:parser.error('--parts required')
    STUDY.mkdir(exist_ok=True); folder = STUDY/args.tag; folder.mkdir(exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs = [Path(__file__), ROOT/'scripts/check_daedalus_load_sensitivity.py',
        ROOT/'scripts/check_daedalus_animation.py', ROOT/'examples/dae.asw',
        ROOT/'docs/validation/aswing-authoritative-sources.json', ROOT/'docs/validation/daedalus-animation-sources-20261113.json']
    inputs += [CAMERA/tag/name for tag in ['fairing-pieces', 'full-states']+[f'camera-joint-{i}' for i in (0,20,40,60,80)]
        for name in ('result.json', 'terminal.json')]
    inputs.append(CAMERA/'full-states/equilibrium.json')
    if args.fin_harmonic:
        inputs += [CAMERA/'fin-outline-connected'/name for name in ('result.json','terminal.json')]
        inputs += list((ROOT/'openswing').glob('*.py'))
    inputs += [ROOT/'reference/daedalus-rudder-animations-20261113'/f'{movie}.gif' for movie in ('slow-rudder','fast-rudder')]
    for part in args.parts or []:inputs += [part/name for name in ('result.json','terminal.json','plan.json')]
    pins = {os.path.abspath(p):pin(p) for p in inputs}
    arguments = {k:[str(p) for p in v] if isinstance(v,list) else v for k,v in vars(args).items()}
    write(folder/'plan.json', dict(observed_utc=utc(), arguments=arguments, inputs_sha256=pins, limits=LIMITS))
    started = time.monotonic(); sys.stdout.flush(); pid = os.fork()
    if pid == 0:
        code = 0
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key] = '1'
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
    terminal=dict(observed_utc=utc(),returncode=os.waitstatus_to_exitcode(status),process_reaped=True,timed_out=timed_out,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-started,peak_rss_kib=usage.ru_maxrss,
        limits=LIMITS,inputs_unchanged=all(pin(p)==h for p,h in pins.items()))
    write(folder/'terminal.json',terminal);print(json.dumps(terminal),flush=True)
    raise SystemExit(terminal['returncode'] or (0 if terminal['inputs_unchanged'] else 1))


if __name__ == '__main__':main()
