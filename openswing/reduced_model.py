"""Selected-mode input/output models, ASWING unsteady theory §13.3.4.

Real coordinates retain complete conjugate pairs. A separately checked
algebraic input lift recovers constraint reactions and acceleration feedthrough
which cannot be represented by homogeneous eigenvectors alone.
"""
import json
import numpy as np
from scipy.linalg import block_diag, lstsq, svd
from .aero import AnalysisError
from .linear_dynamics import make_system, linearize, eigensystem, finite_subspace, state_layout, complex_data
from .frequency_response import HarmonicInput, input_partials, harmonic_solve, HarmonicPole
from .rom_outputs import MeasurementOutputs
from .rom_initial import initial_comparisons


def real_projection(a, m, modes, selected=None):
    """Real right basis and mass-dual left projection; complete each pair."""
    selected = list(range(len(modes))) if selected is None else selected
    if (not isinstance(selected, (list, tuple)) or not selected or
        any(type(i) is not int or not 0 <= i < len(modes) for i in selected) or
        len(set(selected)) != len(selected)):
        raise AnalysisError('ROM mode indices must be distinct zero-based indices in the computed mode list.')
    vectors, lefts, blocks, retained, used = [], [], [], [], set()
    for index in selected:
        if index in used:
            continue
        mode = modes[index]; lam = complex(*mode['eigenvalue'])
        v, w = np.asarray(mode['right']), np.asarray(mode['left'])
        if not mode['biorthogonal_normalized']:
            raise AnalysisError('Selected ROM mode has no left/right mass pairing (possibly a defective pole). Use the full descriptor response.')
        used.add(index)
        # Classification must not depend on the chosen file time unit.
        threshold = 1e-8*max(np.finfo(float).tiny, abs(lam))
        if abs(lam.imag) <= threshold:
            if max(np.linalg.norm(v.imag)/np.linalg.norm(v), np.linalg.norm(w.imag)/np.linalg.norm(w)) > 1e-7:
                raise AnalysisError('Real ROM pole has a complex basis; refine or resolve the repeated eigenspace.')
            vectors.append(v.real[:, None]); lefts.append(w.real[:, None]); blocks.append(np.ones((1, 1)))
            retained.append(dict(source_index=index, eigenvalue=[float(lam.real), 0.], coordinates=[sum(b.shape[0] for b in blocks)-1]))
        else:
            # A real pencil supplies the missing conjugate even if the requested
            # eigenvalue count/shift ended halfway through a pair. Match vectors,
            # not just eigenvalues, so repeated independent pairs are retained.
            partner = None
            for j in selected:
                other = modes[j]
                if j in used or abs(complex(*other['eigenvalue'])-lam.conjugate()) > threshold:
                    continue
                q = np.asarray(other['right'])
                if abs(np.vdot(v.conj(), q))/(np.linalg.norm(v)*np.linalg.norm(q)) > 1-1e-7:
                    partner = j; used.add(j); break
            if lam.imag < 0:
                lam, v, w = lam.conjugate(), v.conj(), w.conj()
            vectors.append(np.column_stack((v, v.conj())))
            lefts.append(np.column_stack((w, w.conj())))
            blocks.append(np.array([[.5, -.5j], [.5, .5j]]))
            first = sum(b.shape[0] for b in blocks)-2
            retained.append(dict(source_index=index, conjugate_source_index=partner,
                eigenvalue=[float(lam.real), float(lam.imag)], coordinates=[first, first+1]))
    v, w, transform = np.column_stack(vectors), np.column_stack(lefts), block_diag(*blocks)
    gram = w.conj().T@m@v
    singular = svd(gram, compute_uv=False)
    if singular[-1] < 1e-9*singular[0]:
        raise AnalysisError('Selected ROM modes are dependent or nearly defective; mass-dual projection is ill-conditioned.')
    lift = v@transform
    dual = np.linalg.solve(transform, np.linalg.solve(gram, w.conj().T))
    reduced = dual@a@lift
    for array in (lift, dual, reduced):
        if np.linalg.norm(array.imag) > 1e-7*max(np.linalg.norm(array.real), 1e-30):
            raise AnalysisError('ROM conjugate conversion did not produce a real model.')
    lift, dual, reduced = lift.real, dual.real, reduced.real
    residual = a@lift-m@lift@reduced
    error = np.linalg.norm(residual)/(np.linalg.norm(a)*np.linalg.norm(lift)+np.linalg.norm(m)*np.linalg.norm(lift@reduced)+1e-30)
    pairing = float(np.max(abs(dual@m@lift-np.eye(lift.shape[1]))))
    if error > 1e-7 or pairing > 1e-7:
        raise AnalysisError('ROM projection fails the original descriptor invariance or mass-dual check.')
    return reduced, lift, dual, dict(retained=retained, dimension=lift.shape[1],
        mass_pairing_error=pairing, invariant_backward_error=float(error),
        pairing_reciprocal_condition=float(singular[-1]/singular[0]))


def algebraic_input_lift(a, m, b, time_scale=1., rank_tolerance=1e-9):
    """Find R with M R=0 and A R+B in the *full* finite dynamic range.

This is an overdetermined consistency solve, with rank and original-equation
checks. Inputs requiring derivatives in descriptor constraints are rejected;
a least-squares fit is never accepted as a substitute for consistency.
"""
    rows = np.maximum(np.maximum(np.linalg.norm(a, axis=1), np.linalg.norm(m*time_scale, axis=1)), 1e-30)
    aa, mm, bb = a/rows[:, None], m*time_scale/rows[:, None], b/rows[:, None]
    finite, history = finite_subspace(aa, mm, rank_tolerance)
    threshold = rank_tolerance*max(np.linalg.norm(aa, 2), np.linalg.norm(mm, 2), 1.)
    # A row containing exactly one nonzero coefficient in M R=0 forces that
    # coordinate of R to vanish exactly. Preserve those equations before an
    # orthogonal nullspace calculation can mix roundoff into rate-dependent
    # outputs. Removing proven zero coordinates can reveal more such rows.
    # No small entry is rounded or discarded here; the full-pencil rank guard
    # above still rejects unresolved weak inertia.
    active = np.arange(mm.shape[1]); locked = []
    while len(active):
        reduced_mass = mm[:, active]
        singleton = np.count_nonzero(reduced_mass, axis=1) == 1
        forced = np.flatnonzero(np.any(reduced_mass[singleton] != 0, axis=0))
        if not len(forced):
            break
        locked.extend(active[forced].tolist()); active = np.delete(active, forced)
    zero_columns = active[np.all(mm[:, active] == 0, axis=0)]
    remaining = active[np.any(mm[:, active] != 0, axis=0)]
    null = np.eye(mm.shape[1])[:, zero_columns]
    if len(remaining):
        _, singular, vh = svd(mm[:, remaining], full_matrices=True)
        reduced_null = vh[int(np.sum(singular > threshold)):].T
        embedded = np.zeros((mm.shape[1], reduced_null.shape[1]))
        embedded[remaining] = reduced_null
        null = np.column_stack((null, embedded))
    if null.shape[1] != mm.shape[1]-history[0]['derivative_rank']:
        raise AnalysisError('ROM derivative rank changes after exact algebraic constraints; refine the tangent/rank before constructing an input lift.')
    k = np.column_stack((-aa@null, mm@finite))
    scales = np.maximum(np.linalg.norm(k, axis=0), 1e-30)
    solved, _, rank, _ = lstsq(k/scales, bb, cond=1e-11)
    solved = solved/scales[:, None]
    error = np.max(abs(k@solved-bb), axis=0)/np.maximum(1., np.max(abs(bb), axis=0))
    if rank != k.shape[1] or max(error, default=0.) > 1e-7:
        raise AnalysisError('ROM inputs do not admit a resolved algebraic lift without input derivatives. Refine the tangent/rank or use the full descriptor response.')
    lift = null@solved[:null.shape[1]]
    mass_error = float(np.linalg.norm(mm@lift)/(np.linalg.norm(mm)*np.linalg.norm(lift)+1e-30))
    if mass_error > 10*rank_tolerance:
        raise AnalysisError('ROM algebraic input lift fails its zero-derivative-mass check.')
    return lift, dict(finite_dimension=finite.shape[1], algebraic_lift_scaled_residuals=error.tolist(),
                     algebraic_lift_mass_error=mass_error,
                     algebraic_lift_exact_zero_coordinates=sorted(locked),
                     algebraic_lift_zero_mass_columns=zero_columns.tolist())


def solve_reduced_model(model, condition, panels=8, *, inputs=None, outputs=None, selected=None,
                        count=16, shift=(-.01, 0.), method='dense', frame='fixed', step=1e-5,
                        rank_tolerance=1e-9, frequencies=(0., 1., 10.), initial_inputs=(),
                        initial_times=(0., .05, .1, .2, .5, 1.), initial_shift=0., progress=None, **base_options):
    omega = np.asarray(frequencies, dtype=float)
    if omega.ndim != 1 or not len(omega) or not np.all(np.isfinite(omega)) or np.any(omega < 0) or np.any(np.diff(omega) <= 0):
        raise AnalysisError('ROM comparison frequencies must be finite, nonnegative and strictly increasing [rad/input T].')
    if base_options.get('quiescent_density') is not None:
        raise AnalysisError('Quiescent fluid is currently supported for fixed-frame modes only, not ROM.')
    system, continuation = make_system(model, condition, panels, frame=frame, **base_options)
    if inputs is None:
        inputs = [f'control.{k}' for k in model.controls]+[f'power.{k}' for k in model.engine_controls]
    if not isinstance(inputs, (list, tuple)) or (not inputs and not initial_inputs):
        raise AnalysisError('Select at least one ROM input or physical initial profile.')
    channels = [HarmonicInput(system, spec, i) for i, spec in enumerate(inputs)]
    if len({c.report['name'] for c in channels}) != len(channels):
        raise AnalysisError('ROM input names must be distinct.')
    if any(c.kind == 'gust' and c.wave != 'uniform' for c in channels):
        raise AnalysisError('A constant real ROM requires a fixed spatial gust (wave=uniform); convected gust phase depends on frequency. Use full frequency response for convected gusts.')
    measured = MeasurementOutputs(system, ['Ax', 'Ay', 'Az'] if outputs is None else outputs)
    a, m = linearize(system, step, None if progress is None else lambda i, n:progress('linearizing', i, n))
    modes, spectrum = eigensystem(a, m, time_scale=system.W, count=count, shift=shift,
        method=method, rank_tolerance=rank_tolerance)
    ar, lift, dual, diagnostics = real_projection(a, m, modes, selected)
    b, forcings, profiles = input_partials(system, channels, 0., step) if channels else (np.empty((system.size,0),complex),[],[])
    if channels and np.max(abs(b.imag)) > 1e-10*max(1., np.max(abs(b.real))):
        raise AnalysisError('Constant real ROM input has a complex spatial phase.')
    b = b.real; br = dual@b
    if channels:direct, constraint = algebraic_input_lift(a, m, b, system.W, rank_tolerance)
    else:direct, constraint = np.empty((system.size,0)),dict(finite_dimension=spectrum['finite_dimension'])
    cr = np.column_stack([measured.tangent(lift[:, j], lift@ar[:, j], step) for j in range(len(ar))])
    dr = np.column_stack([measured.tangent(direct[:, j], lift@br[:, j], step, forcings[j], channels[j].scale) for j in range(len(channels))]) if channels else np.empty((len(measured.names),0))
    d_rate = np.column_stack([measured.tangent(np.zeros(system.size), direct[:, j], step) for j in range(len(channels))]) if channels else np.empty((len(measured.names),0))
    initial,initial_diagnostics=initial_comparisons(system,a,m,ar,lift,dual,cr,measured,initial_inputs,
        initial_times,omega,initial_shift,step,rank_tolerance,progress)
    if initial_diagnostics is not None:constraint['finite_dimension']=initial_diagnostics['finite_dimension']
    samples = []
    for i, w in enumerate(omega if channels else []):
        sample = dict(omega=float(w))
        try:
            modal, _ = harmonic_solve(ar, np.eye(len(ar)), br, w)
            approx = cr@modal+dr+1j*w*d_rate
            full, full_diagnostic = harmonic_solve(a, m, b, w)
            exact = np.column_stack([measured.tangent(full[:, j].real, (1j*w*full[:, j]).real, step, forcings[j], channels[j].scale)+
                1j*measured.tangent(full[:, j].imag, (1j*w*full[:, j]).imag, step) for j in range(len(channels))])
            sample.update(converged=True, reduced=complex_data(approx), full=complex_data(exact),
                absolute_error=abs(approx-exact).tolist(), full_diagnostics=full_diagnostic)
        except HarmonicPole as exc:
            sample.update(converged=False, error=str(exc))
        samples.append(sample)
        if progress is not None:progress('comparison', i+1, len(omega))
    valid = [s for s in samples if s['converged']]
    if valid:
        reference = np.array([np.array(s['full']['real'])+1j*np.array(s['full']['imag']) for s in valid])
        errors = np.max([s['absolute_error'] for s in valid], axis=0)
        norm = np.max(abs(reference), axis=0)
        relative = [[None if norm[j,k] <= 1e-12 else float(errors[j,k]/norm[j,k]) for k in range(len(channels))] for j in range(len(measured.names))]
    else:
        relative = None
    base = system.base_report(); base['continuation_steps'] = continuation
    diagnostics.update(constraint, difference_step=step, derivative_linearization=system.derivative_diagnostics, continuation_steps=continuation,
        full_dimension=system.size, state_layout=state_layout(system), maximum_normalized_transfer_errors=relative,
        initial_conditions=initial_diagnostics,
        projection='Left mass-dual projection with complete real conjugate pairs; algebraic input lift uses the full finite subspace.')
    return dict(analysis='reduced_order_model', format='openswing-rom', format_version=1, converged=True,
        frame_mode=frame, frame_load_targets=base['modal_base']['load_targets'], base=base, inputs=[c.report for c in channels], outputs=measured.metadata,
        output_base=measured.base.tolist(), matrices=dict(A=ar.tolist(), B=br.tolist(), C=cr.tolist(), D=dr.tolist(), D_rate=d_rate.tolist()),
        state_lift=lift.tolist(), state_input_lift=direct.tolist(), state_projection=(dual@m).tolist(),
        available_modes=[dict(index=i, eigenvalue=mode['eigenvalue']) for i, mode in enumerate(modes)],
        spectrum=spectrum, diagnostics=diagnostics, samples=samples, gust_profiles=profiles,initial_responses=initial,
        controller=None if system.feedback is None else system.feedback.report(),
        equations=['zdot = A z + B du', 'dy = C z + D du + D_rate d(du)/dt', 'dx = state_lift z + state_input_lift du',
            'For an initial profile: z(0) = state_projection dx(0); du = 0; z(t) = exp(A t) z(0)'],
        limitations=[
            'This is a local frozen linear model. Truncated stable, unstable or lightly damped modes can change response and stability conclusions; compare the full system across the intended frequency range and refine the mode set and mesh.',
            'Conjugate pairs are retained together. Dependent or defective selected modes are rejected; generalized eigenvector/Jordan models are not yet supported.',
            'Constant real inputs support flap/engine settings, selected controller commands, active frame targets, prescribed accelerations and fixed spatial gusts. Convected gust phase requires frequency-dependent input matrices and is not supported by this constant-matrix export.',
            'The algebraic lift retains direct constraint and acceleration response. Inputs requiring derivatives in the descriptor state are rejected. D_rate explicitly represents derivative-input output feedthrough.',
            'Named global and Sensor measurements use file physical units and degrees for angles. Explicit physical selectors retain their reported units, including radians for spatial rotation and elastic incidence. Sample index, beam and material coordinate bind each distributed output to the base mesh; no interpolation across jumps is implied. State-lift rows use scaled descriptor coordinates.',
            'Initial profiles are completed in the full finite descriptor space before mass-dual projection. Omitted state and output errors are reported; this is a frozen linear free response, not nonlinear time initialization. Laplace convergence is checked against the full spectrum, including omitted unstable modes.',
            'OpenSwing ROM JSON and text are versioned original formats. Legacy ASWING .rom byte compatibility and published aircraft/experimental ROM validation remain unverified.'
        ])


def rom_text(result):
    """Self-describing, precision-preserving matrix exchange; not legacy .rom."""
    lines = ['# OpenSwing ROM 1', '# Original format; not an ASWING legacy .rom file.']
    lines += ['# '+equation for equation in result['equations']]
    for key in ('inputs', 'outputs', 'output_base'):
        lines.append('# '+key+' '+json.dumps(result[key], ensure_ascii=True, separators=(',', ':')))
    if result.get('initial_responses'):
        profiles=[{k:v for k,v in row.items() if k not in ('samples','time_samples')} for row in result['initial_responses']]
        lines.append('# initial_conditions '+json.dumps(profiles,ensure_ascii=True,separators=(',', ':')))
    for name, value in {**result['matrices'], 'state_lift':result['state_lift'],
                        'state_input_lift':result['state_input_lift'], 'state_projection':result['state_projection']}.items():
        array = np.asarray(value)
        lines.append(f'{name} {array.shape[0]} {array.shape[1]}')
        lines.extend(' '.join(f'{x:.17g}' for x in row) for row in array)
    return '\n'.join(lines)+'\n'
