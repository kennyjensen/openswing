"""One bounded prescribed-heave run through the production JSON time path.

The analytic comparison includes the zero-circulation startup transient.
UA-1 uses section equations. UA-2 can compare a saved linearized 3D operator
with independent matrix-exponential propagation. Neither is a native time record.
Run timestep refinements as separate serial processes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback

from isae_suite_unsteady import model_text
from isae_ua_artifacts import write_trajectory

ROOT = Path(__file__).resolve().parents[1]


def cold_heave(time_value, *, amplitude_ratio, k, speed):
    """Independent c=1 flat-plate ODE solution, including apparent mass.

    tau*Gamma_dot+Gamma=-pi*z_dot, tau=2/V;
    CL=2*Gamma/V+2*Gamma_dot/V^2-pi*z_ddot/(2*V^2).
    z=(A/c)/2*cos(omega*t), Gamma(0)=0, omega=2Vk.
    """
    omega, tau, height = 2*speed*k, 2/speed, amplitude_ratio/2
    phase = omega*time_value
    sine, cosine, decay = math.sin(phase), math.cos(phase), math.exp(-time_value/tau)
    factor = math.pi*height*omega/(1+(omega*tau)**2)
    gamma = factor*(sine-omega*tau*cosine+omega*tau*decay)
    gamma_dot = factor*omega*(cosine+omega*tau*sine-decay)
    acceleration = -height*omega**2*cosine
    added = -math.pi*acceleration/(2*speed**2)
    return dict(z=height*cosine, velocity=-height*omega*sine, acceleration=acceleration,
        circulation=gamma, circulation_rate=gamma_dot,
        CL=2*gamma/speed+2*gamma_dot/speed**2+added, CL_added=added)


def make_request(*, steps, amplitude_ratio, k, aspect_ratio=200000., panels=4, startup_subdivisions=1, startup_growth=1.5):
    speed = 10.
    period = math.pi/(speed*k)
    if startup_subdivisions == 1:
        times = [period*i/steps for i in range(steps+1)]
    else:
        from isae_ua_startup import heave_grid
        times = heave_grid(period,steps,startup_subdivisions,startup_growth)
    forcing = 'time Az\n'+'\n'.join(
        f"{t:.17g} {cold_heave(t, amplitude_ratio=amplitude_ratio, k=k, speed=speed)['acceleration']:.17g}"
        for t in times)+'\n'
    return dict(action='time', mode='time', source=model_text(aspect_ratio), panels=panels,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=speed, alpha=0., mach=0., stall=False, aero_lag=True,
            gravity_magnitude=0., position_earth=[0., 0., amplitude_ratio/2]),
        time=dict(frame='prescribed', duration=period, dt=period/steps, order=2,
            tolerance=1e-10, max_steps=4*steps, forcing=forcing))


def compare(result, request, *, amplitude_ratio, k, aspect_ratio):
    speed = request['condition']['speed']
    qs = .5*1.225*speed**2*aspect_ratio
    samples = []
    for s in result['snapshots']:
        expected = cold_heave(s['time'], amplitude_ratio=amplitude_ratio, k=k, speed=speed)
        frame = s['frame']
        predicted = s['force'][2]/qs
        samples.append(dict(time=s['time'], CL_vertical=predicted, CL_wind_axes=s['CL'],
            expected=expected, CL_error=predicted-expected['CL'],
            velocity_error=frame['velocity_origin_body'][2]-expected['velocity'],
            position_error=frame['position_earth'][2]-expected['z'],
            acceleration_error=frame['acceleration_reference_body'][2]-expected['acceleration'],
            frame_rates=frame['rates_body'], frame_attitude=frame['attitude'],
            residual=s['residual'], order=s['order'], step=s['step'],
            circulation=[row['circulation'] for row in s['strips']],
            circulation_rate=s['circulation_rate']))
    maximum_error = max(abs(r['CL_error']) for r in samples)
    peak = max(abs(r['expected']['CL']) for r in samples)
    return dict(samples=samples, maximum_absolute_CL_error=maximum_error,
        maximum_waveform_error_fraction=maximum_error/peak,
        maximum_residual=max(s['residual'] for s in samples),
        maximum_velocity_error=max(abs(s['velocity_error']) for s in samples),
        maximum_position_error=max(abs(s['position_error']) for s in samples),
        maximum_acceleration_error=max(abs(s['acceleration_error']) for s in samples),
        interpretation='For finite AR this is a descriptive difference from 2D theory, not a native-ASWING error.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=int, choices=(40, 80, 160, 320), required=True)
    parser.add_argument('--amplitude-ratio', type=float, default=.001)
    parser.add_argument('--k', type=float, default=.475)
    parser.add_argument('--aspect-ratio', type=float, default=200000.)
    parser.add_argument('--panels', type=int, choices=(4, 8, 20, 40), default=4)
    parser.add_argument('--nonlinear-section-reference', action='store_true',
        help='Also compare the independent live-wind, attached-flow 2D equations.')
    parser.add_argument('--linear-wing-reference', type=Path,
        help='Compare a saved AR10 spatial operator using independent exact-matrix time propagation.')
    parser.add_argument('--startup-subdivisions', type=int, choices=(1,8,16,32,64,128,256), default=1,
        help='Reduce the first step by this factor, then grow steps by at most 1.5 to the original maximum.')
    parser.add_argument('--startup-growth', type=float, choices=(1.125,1.2,1.25,1.5), default=1.5,
        help='Growth ratio imposed by the smooth forcing-table knots during startup refinement.')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if not all(math.isfinite(v) and v > 0 for v in (args.k, args.amplitude_ratio, args.aspect_ratio)):
        parser.error('Positive finite frequency, amplitude and aspect ratio required')
    if args.nonlinear_section_reference and args.aspect_ratio != 200000.:
        parser.error('The nonlinear 2D acceptance diagnostic requires the declared AR200000 limit')
    wing_reference = None
    if args.startup_subdivisions == 1 and args.startup_growth != 1.5:
        parser.error('Startup growth requires startup subdivisions')
    if args.startup_subdivisions != 1 and not args.linear_wing_reference:
        parser.error('The startup-refinement diagnostic requires a matched linear wing reference')
    if args.linear_wing_reference:
        if args.nonlinear_section_reference or args.aspect_ratio != 10. or args.amplitude_ratio != .001:
            parser.error('The 3D linear integration check requires AR10, A/c=.001 and no 2D nonlinear reference')
        wing_reference = json.loads(args.linear_wing_reference.read_text())
        if not wing_reference['numerical_passed'] or not wing_reference['unchanged_code']:
            parser.error('Invalid wing reference')
        settings = wing_reference['settings']
        if any(settings[k] != v for k,v in dict(panels=args.panels,aspect_ratio=10.,speed=10.,
                alpha_deg=0.,mach=0.,stall=False,aero_lag=True).items()):
            parser.error('Wing reference does not match the requested model and operating point')
        for name, digest in wing_reference['source_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
                parser.error('Wing reference source changed: '+name)
    if args.output_dir.exists():
        parser.error('Preserve completed or interrupted evidence; choose a new output directory')
    args.output_dir.mkdir(parents=True)
    request = make_request(steps=args.steps, amplitude_ratio=args.amplitude_ratio, k=args.k,
        aspect_ratio=args.aspect_ratio, panels=args.panels, startup_subdivisions=args.startup_subdivisions,
        startup_growth=args.startup_growth)
    pins = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*sorted((ROOT/'openswing').glob('*.py')),
                  Path(__file__).resolve(), ROOT/'scripts/isae_suite_unsteady.py',
                  ROOT/'scripts/isae_ua_artifacts.py']}
    if args.nonlinear_section_reference:
        for path in (ROOT/'scripts/isae_ua_section_reference.py', ROOT/'.reference/asw_theory.txt',
                     ROOT/'.reference/asw_uns_theory.txt'):
            pins[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    if wing_reference is not None:
        pins.update(wing_reference['source_sha256'])
        path = args.linear_wing_reference.resolve()
        pins[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.startup_subdivisions != 1:
        path = ROOT/'scripts/isae_ua_startup.py'
        pins[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    plan = dict(request=request, code_sha256=pins, k=args.k, amplitude_ratio=args.amplitude_ratio,
        aspect_ratio=args.aspect_ratio, source_convention='heave semi-amplitude/chord=(A/c)/2',
        target='UA-1 published small-signal equation, with analytically derived startup transient',
        experimental_comparison=False, native_ASWING_time_comparison=False,
        forcing='Exact cosine accelerations at each requested BDF knot; no forcing beyond end is sampled.',
        refinement_gate='For AR200000/A=.001 compare 40/80/160: each waveform error ratio < .35; finest error fraction < .001. No guard/tolerance relaxation.',
        unchanged_production_required=True)
    if args.nonlinear_section_reference:
        plan['nonlinear_section_reference']=dict(
            target='Independent live-wind attached-flow 2D equations; no fitted coefficients.',
            sources=['steady eqs155-157','unsteady eqs34-35,43,49'],
            gate='At each published amplitude/frequency, 80/160 errors must decrease by ratio <.35; finest waveform error <.1%. Linear-MATLAB differences remain descriptive and are retained.')
    if wing_reference is not None:
        plan['target'] = 'UA-2 AR10 integration parity with the linearized production spatial equations'
        plan['refinement_gate'] = 'At each mesh/frequency compare 40/80/160: each waveform error ratio <.35; finest max CL waveform error <.1%. No tolerance relaxation.'
        plan['linear_wing_reference'] = dict(path=str(args.linear_wing_reference),
            native_ASWING_comparison=False, independent_spatial_physics_reference=False,
            scope='A/c=.001, alpha=0, AR10; constant coupled 3D matrices, independently propagated in time.')
    if args.startup_subdivisions != 1:
        plan['startup_refinement'] = dict(subdivisions=args.startup_subdivisions,maximum_growth=args.startup_growth,
            nominal_steps=args.steps,first_step=request['time']['dt']/args.startup_subdivisions,
            planned_steps=len(request['time']['forcing'].splitlines())-2,
            source='Unsteady description section12.1, Eqs123-125; production variable BDF coefficients unchanged.',
            gate='Max lift waveform error <0.1%; max rate waveform error normalized by each strip peak <0.1%; first-step relative rate error at every strip <1%.')
        plan['refinement_gate'] = plan['startup_refinement']['gate']
    (args.output_dir/'plan.json').write_text(json.dumps(plan,indent=2,allow_nan=False)+'\n')
    started = time.monotonic()
    def progress(*values):
        if len(values) == 2 and isinstance(values[0], (float, int)):
            elapsed = time.monotonic()-started
            status=dict(time=values[0], accepted_steps=values[1], seconds=elapsed)
            (args.output_dir/'progress.json').write_text(json.dumps(status)+'\n')
            if values[1] % 10 == 0:
                print(json.dumps(status),flush=True)
    try:
        sys.path.insert(0,str(ROOT))
        from openswing.bridge import dispatch
        result = dispatch(request, progress=progress)
        elapsed = time.monotonic()-started
        (args.output_dir/'solver.json').write_text(json.dumps(dict(status='solver_returned',
            seconds=elapsed,converged=result['converged'],accepted_steps=result['accepted_steps'],
            rejected_steps=result['rejected_steps'],snapshots=len(result['snapshots']),
            final_time=result['snapshots'][-1]['time'],raw_persistence='pending'),indent=2)+'\n')
        persistence_start = time.monotonic()
        write_trajectory(args.output_dir/'trajectory.json.gz',result)
        persistence_seconds = time.monotonic()-persistence_start
        compared = compare(result,request,amplitude_ratio=args.amplitude_ratio,k=args.k,aspect_ratio=args.aspect_ratio)
        nonlinear = None
        if args.nonlinear_section_reference:
            from isae_ua_section_reference import compare as compare_nonlinear
            nonlinear=compare_nonlinear(compared['samples'],amplitude_ratio=args.amplitude_ratio,k=args.k,
                speed=request['condition']['speed'])
        wing = None
        if wing_reference is not None:
            from isae_ua_wing_reference import compare as compare_wing
            wing = compare_wing(wing_reference, compared['samples'],
                amplitude_ratio=args.amplitude_ratio, k=args.k)
        stable = all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in pins.items())
        report = dict(status='computed', seconds=elapsed, comparison=compared,
            persistence_seconds=persistence_seconds,
            production_unchanged=stable, converged=result['converged'],
            structural_operator=result.get('structural_operator'), temporal_policy=result.get('temporal_policy'),
            accepted_steps=result['accepted_steps'], rejected_steps=result['rejected_steps'],
            jacobian_builds=result['jacobian_builds'], evaluations=result['evaluations'],
            time_seconds=result.get('seconds'), plan='plan.json', raw_trajectory='trajectory.json.gz')
        if nonlinear is not None:
            report['nonlinear_section_comparison']=nonlinear
        if wing is not None:
            report['linear_wing_comparison']=wing
        if args.startup_subdivisions != 1:
            from isae_ua_startup import rate_metrics
            metrics = rate_metrics(compared['samples'],wing['rows'])
            metrics['accuracy_gate_passed'] = (wing['maximum_waveform_error_fraction'] < .001
                and metrics['maximum_per_strip_rate_waveform_error_fraction'] < .001
                and metrics['maximum_first_step_relative_error_fraction'] < .01)
            report['startup_rate_comparison'] = metrics
        (args.output_dir/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('comparison','nonlinear_section_comparison','linear_wing_comparison')}),flush=True)
        print(json.dumps({k:v for k,v in compared.items() if k!='samples'}),flush=True)
        if nonlinear is not None:
            print(json.dumps({k:v for k,v in nonlinear.items() if k!='rows'}),flush=True)
        if wing is not None:
            print(json.dumps({k:v for k,v in wing.items() if k!='rows'}),flush=True)
        if not stable or not result['converged']:
            raise SystemExit(1)
    except Exception as error:
        (args.output_dir/'failure.json').write_text(json.dumps(dict(error=str(error),
            traceback=traceback.format_exc(), seconds=time.monotonic()-started),indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()
