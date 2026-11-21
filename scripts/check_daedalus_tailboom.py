"""Small serial tailboom diagnostics; never change production model defaults.

Each invocation owns one capped child. `audit` prepares the CURRENT structural
derivative on the historical corrected C16 state; `response` reuses the OLD
aircraft matrices and replaces only that verified constitutive block. This is
a fixed-equilibrium incremental-stiffness experiment, not a new trimmed case.
`beam` checks the current vacuum boom against an independent Euler--Bernoulli
calculation with literal, piecewise-linear EI and weight distributions.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SAVED = Path('/tmp/openswing-daedalus-shell-mesh-20261025/results')
LIMITS = dict(address_space_bytes=512*1024**2, cpu_seconds=15, wall_seconds=25)
FREQUENCIES = [.2, .7, .9, 1., 1.0964781961432, 1.157377737, 1.3, 1.5, 2.]


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pin(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def imports():
    global np, sp, la, spla, parse_asw, StaticNetwork, DynamicSystem
    global linearize, compatibility_columns, harmonic_solve
    import numpy as np
    import scipy.sparse as sp
    import scipy.linalg as la
    import scipy.sparse.linalg as spla
    from openswing.asw import parse_asw
    from openswing.network import StaticNetwork
    from openswing.linear_dynamics import DynamicSystem, linearize
    from openswing.structural_outputs import compatibility_columns
    from openswing.frequency_response import harmonic_solve


def complex_row(z):
    return dict(real=float(z.real), imag=float(z.imag), magnitude=float(abs(z)),
                phase_degrees=float(np.angle(z, deg=True)))


def current_saved_system():
    from openswing.equilibrium_state import restore, warm_start_recipe
    from openswing.operating import time_load_constraints
    from openswing.time_state import read_condition
    request = read(ROOT/'tests/data/daedalus-curved-mechanics/request.json')
    config = read(ROOT/request['project'])['cases'][request['case_index']]['configuration']
    packet = config['equilibrium']['state']
    launch = packet['launch']

    class NoResidualNetwork(StaticNetwork):
        def residual(self, *args, **kwargs):
            raise AssertionError('Saved-matrix diagnosis must not evaluate an aircraft residual.')

    model = parse_asw(config['source'])
    n = NoResidualNetwork(model, launch['panels'], read_condition(launch['condition']),
        launch['gravity'], launch['loads'], operating_constraints=time_load_constraints('free'),
        strut_mode=launch['strut_mode'], mesh_recipe=warm_start_recipe(model, launch['panels'], packet))
    system = DynamicSystem(n, restore(n, packet), 'free')
    assert [n.nn, n.ne, n.ng, n.nc, n.size, system.size] == request['dimensions']
    assert np.all(n.damping_times == 0)
    np.testing.assert_allclose(system.base, np.load(SAVED/'base-unknowns.npz')['value'], atol=2e-13, rtol=2e-13)
    return system


def audit(folder):
    literal = parse_asw((ROOT/'examples/dae.asw').read_text())
    boom = next(b for b in literal.beams if b.index == 4)
    t = np.array([-6.5, 0., 4., 8., 12., 16., 20.])
    expected_ei = np.interp(t, [-6.5, 4., 12., 20.], [50000., 100000., 11000., 7500.])
    expected_gj = np.interp(t, [-6.5, 4., 12., 20.], [25000., 25000., 11000., 7500.])
    expected_mg = np.interp(t, [-6.5, 4., 12., 20.], [.15, .15, .11, .06])
    for key, expected in [('EIcc', expected_ei), ('EInn', expected_ei), ('GJ', expected_gj), ('mg', expected_mg)]:
        np.testing.assert_allclose(boom.value(key, t), expected, rtol=2e-14, atol=2e-14)
    for key in ('EA', 'GKc', 'GKn'):
        assert np.all(np.isinf(boom.value(key, t)))
    for key in ('tdeps', 'tdgam', 'mgcc', 'mgnn', 'Ccg', 'Ncg'):
        assert np.all(boom.value(key, t) == 0)
    system = current_saved_system()
    n = system.network
    c = compatibility_columns(system)
    c = sp.hstack([c, sp.csr_matrix((6*n.ne, system.size-n.size))], format='csr')
    oracle = sp.load_npz(ROOT/'tests/data/daedalus-curved-mechanics/independent-compatibility.npz')
    a = sp.load_npz(SAVED/'A.npz').tocsr()
    difference = c-a[:6*n.ne]
    oracle_difference = c-oracle
    max_difference = float(abs(difference).max())
    max_oracle = float(abs(oracle_difference).max())
    assert max_difference < 2e-9 and max_oracle < 2e-9
    original_s = n.S.copy()
    n.S[n.beam_elements[4]] = 0.
    rigid = compatibility_columns(system)
    rigid = sp.hstack([rigid, sp.csr_matrix((6*n.ne, system.size-n.size))], format='csr')
    delta = sp.vstack([rigid-c, sp.csr_matrix((system.size-6*n.ne, system.size))], format='csc')
    n.S[:] = original_s
    rows = np.unique(delta.tocoo().row)
    assert all(6*n.beam_elements[4].start <= row < 6*n.beam_elements[4].stop for row in rows)
    sp.save_npz(folder/'rigid-boom-delta-A.npz', delta)
    # Relative motion removes root rigid translation AND rotation.
    c_out = np.zeros((5, system.size))
    c_out[0, system.frame_start+5] = system.W*180/np.pi
    root, tip, fin, top = n.node(4, 0.), n.node(4, 20.), n.node(3, 0.), n.node(3, 5.)
    for row, endpoint in ((1, tip), (2, top)):
        c_out[row, 6*endpoint+1] = n.L
        c_out[row, 6*root+1] = -n.L
        d = system.r0[endpoint]-system.r0[root]
        c_out[row, 6*root+3:6*root+6] = [d[2], 0., -d[0]]
    for row, endpoint in ((3, tip), (4, fin)):
        c_out[row, 6*endpoint+5] = 180/np.pi
        c_out[row, 6*root+5] = -180/np.pi
    np.save(folder/'outputs.npy', c_out)
    np.testing.assert_allclose(c_out[0], np.load(SAVED/'output-map.npy')[0]*180/np.pi, atol=1e-14)
    np.testing.assert_allclose(n.rj[fin]-n.rj[tip], [0., 1., 0.], atol=1e-14)
    assert n.nfev == 0
    return dict(status='PASS', observed_utc=utc(), stations_ft=t.tolist(), EI_lb_ft2=expected_ei.tolist(),
        GJ_lb_ft2=expected_gj.tolist(), weight_lb_per_ft=expected_mg.tolist(), gravity_ft_s2=32.18,
        whole_boom_weight_lb=3.295, aft_boom_weight_lb=2.32, fin_joint_offset_ft=[0., 1., 0.],
        current_vs_saved_compatibility_max_abs=max_difference, current_vs_independent_max_abs=max_oracle,
        changed_equation_rows=len(rows), aircraft_residual_calls=0, new_aircraft_linearizations=0,
        output_names=['yaw_deg_s', 'boom_tip_relative_y_ft', 'fin_top_relative_y_ft',
                      'boom_tip_relative_z_rotation_deg', 'fin_root_relative_z_rotation_deg'],
        qualification='Current structural derivative only; all other coupled matrices are the 2026-10-25 snapshot.')


def independent_beam(elements):
    """Cubic Hermite EB elements; literal properties, no production imports used."""
    stations = np.unique(np.r_[np.linspace(0., 20., elements+1), 4., 12.])
    size = 2*len(stations)
    k, m = np.zeros((size, size)), np.zeros((size, size))
    xi, weights = np.polynomial.legendre.leggauss(4)
    for e, (a, b) in enumerate(zip(stations[:-1], stations[1:])):
        h = b-a
        dofs = np.arange(2*e, 2*e+4)
        for r, weight in zip((xi+1)/2, weights/2):
            x = a+h*r
            ei = np.interp(x, [-6.5, 4., 12., 20.], [50000., 100000., 11000., 7500.])
            mu = np.interp(x, [-6.5, 4., 12., 20.], [.15, .15, .11, .06])/32.18
            shape = np.array([1-3*r*r+2*r**3, h*(r-2*r*r+r**3), 3*r*r-2*r**3, h*(-r*r+r**3)])
            curvature = np.array([-6+12*r, h*(-4+6*r), 6-12*r, h*(-2+6*r)])/h**2
            k[np.ix_(dofs, dofs)] += weight*h*ei*np.outer(curvature, curvature)
            m[np.ix_(dofs, dofs)] += weight*h*mu*np.outer(shape, shape)
    eigenvalues = la.eigh(k[2:, 2:], m[2:, 2:], subset_by_index=[0, 1], eigvals_only=True)
    # Exact continuum Castigliano integrals, with every EI break explicit.
    from scipy.integrate import quad
    compliance = np.zeros((2, 2))
    for i in range(2):
        for j in range(2):
            for a, b in ((0., 4.), (4., 12.), (12., 20.)):
                compliance[i, j] += quad(lambda x: (20-x)**(2-i-j)/np.interp(x,
                    [-6.5, 4., 12., 20.], [50000., 100000., 11000., 7500.]), a, b, epsabs=1e-13, epsrel=1e-12)[0]
    return np.sqrt(eigenvalues)/(2*np.pi), compliance


def beam(folder, panels):
    source = (ROOT/'examples/dae.asw').read_text().split('Beam 4\n', 1)[1].split('End', 1)[0]
    source = source.replace(' -6.5    -6.5    0.0    0.0', ' 0.0     0.0    0.0    0.0', 1)
    text = 'Name\nDaedalus aft boom vacuum cantilever\nEnd\nUnits\nL 1 ft\nT 1 s\nF 1 lb\nEnd\nConstant\n32.18 .002378 1115\nEnd\nReference\n0 1 20\nEnd\nGround\n4 0 0\nEnd\nBeam 4\n'+source+'End\n'
    (folder/'boom.asw').write_text(text)
    model = parse_asw(text)
    assert model.beams[0].domain == (0., 20.)
    n = StaticNetwork(model, panels, None, [0., 0., 0.], [])
    system = DynamicSystem(n, np.zeros(n.size), 'fixed')
    zero = np.zeros(system.size)
    assert np.max(abs(system.residual(zero, zero))) < 1e-13
    a, m = linearize(system, sparse=True)
    tip = n.node(4, 20.)
    b = np.zeros((system.size, 2))
    b[6*n.ne+3*tip+1, 0] = 1/n.F
    b[6*n.ne+3*n.nn+3*tip+2, 1] = 1/(n.F*n.L)
    static, diagnostics = harmonic_solve(a, m, b, 0.)
    compliance = np.array([n.L*static[6*tip+1], static[6*tip+5]]).real
    factor = spla.splu(-a.tocsc())
    operator = spla.LinearOperator(a.shape, matvec=lambda x: factor.solve(m@x), dtype=float)
    mu, vectors = spla.eigs(operator, k=8, which='LM', v0=np.linspace(.3, 1.3, system.size), tol=1e-11)
    poles = -1/mu
    indices = sorted((i for i, pole in enumerate(poles) if pole.imag > 1e-6), key=lambda i: poles[i].imag)
    assert len(indices) == 4
    frequencies = [float(poles[i].imag/(2*np.pi)) for i in indices]
    modal_residual = max(float(np.linalg.norm(a@vectors[:, i]-poles[i]*(m@vectors[:, i]))/
        (np.linalg.norm(a@vectors[:, i])+abs(poles[i])*np.linalg.norm(m@vectors[:, i]))) for i in indices)
    assert modal_residual < 1e-7 and max(abs(poles[i].real) for i in indices) < 1e-6
    reference, compliance_ref = independent_beam(80)
    tightened, _ = independent_beam(160)
    assert np.max(abs(reference/tightened-1)) < 1e-5
    error = np.abs(np.array(frequencies)/np.repeat(tightened, 2)-1)
    compliance_error = np.abs(compliance/compliance_ref-1)
    np.testing.assert_allclose(compliance, compliance.T, rtol=1e-9, atol=1e-12)
    passed = bool(np.max(error) < .01 and np.max(compliance_error) < .01)
    return dict(status='PASS' if passed else 'REFINEMENT_NEEDED', nominal_panels=panels, elements=n.ne,
        scope='Unloaded aft boom only, x=0..20 ft, clamped at x=0; no fin, stabilizer, fluid or flight dynamics.',
        compliance=[[float(v) for v in row] for row in compliance],
        reference_compliance=compliance_ref.tolist(), compliance_error_percent=(100*compliance_error).tolist(),
        bending_frequencies_hz=frequencies, reference_frequencies_hz=tightened.tolist(),
        frequency_error_percent=(100*error).tolist(), reference_tightening_relative=float(np.max(abs(reference/tightened-1))),
        modal_residual=modal_residual, harmonic_diagnostics=diagnostics,
        gate='1% on both static matrix entries and first two duplicated lateral bending frequencies; continuum tightening 1e-5.')


def response(folder, study, factor, component='all'):
    a, m = (sp.load_npz(SAVED/name) for name in ('A.npz', 'M.npz'))
    delta = sp.load_npz(study/'audit/rigid-boom-delta-A.npz')
    if component != 'all':
        # Literal boom has zero section offsets and cross-stiffness, so its
        # local curvature equations split exactly into c/n bending and s twist.
        model = parse_asw((ROOT/'examples/dae.asw').read_text())
        boom = next(b for b in model.beams if b.index == 4)
        for key in ('EIcs', 'EIcn', 'EIsn', 'Cea', 'Nea', 'Cta', 'Nta'):
            assert key not in boom.distributions, 'A coupled section requires a newly derived split.'
        rows = np.unique(delta.tocoo().row)
        assert np.all(np.isin(rows % 6, [3, 4, 5]))
        components = [3, 5] if component == 'bending' else [4]
        delta = sp.diags(np.isin(np.arange(a.shape[0]) % 6, components).astype(float))@delta
    a = a+(1-1/factor)*delta
    b = np.load(SAVED/'control-rhs.npz')['value'][:, 0]
    outputs = np.load(study/'audit/outputs.npy')
    samples = []
    for frequency in FREQUENCIES:
        vector, diagnostics = harmonic_solve(a, m, b, 2*np.pi*frequency)
        values = outputs@vector
        samples.append(dict(frequency_hz=frequency, outputs=[complex_row(z) for z in values], diagnostics=diagnostics))
    return dict(status='COMPUTED', boom_stiffness_multiplier=factor, changed_component=component,
        frequencies_hz=FREQUENCIES, samples=samples,
        scope='Historical corrected C16 aircraft matrices with current verified boom compliance derivative; fixed loaded shape, prestress, mass and aerodynamic matrices; no re-trim.',
        interpretation='Compensating constant constitutive residual holds the base equilibrium. This diagnoses incremental stiffness sensitivity, not a realizable changed-jig aircraft prediction.')


def report(folder, study, beam_study):
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter
    jobs = [study/'audit']+[study/f'response-{v}' for v in ('0.5', '1', '2', '100')]
    jobs += [beam_study/f'beam-{v}' for v in (16, 32)]
    versions = [v for v in (study/'runner-v1.py', beam_study/'runner-v2.py', Path(__file__)) if v.is_file()]
    terminals = []
    for job in jobs:
        terminal = read(job/'terminal.json')
        assert terminal['returncode'] == 0 and terminal['process_reaped'] and terminal['inputs_unchanged']
        assert terminal['limits'] == LIMITS and not terminal['timed_out']
        for path, expected in read(job/'plan.json')['inputs_sha256'].items():
            if path == str(Path(__file__).resolve()):
                candidates = versions + ([job/'runner.py'] if (job/'runner.py').is_file() else [])
                assert any(pin(v) == expected for v in candidates)
            else:
                assert pin(path) == expected, path
        terminals.append(terminal)
    responses = {v: read(study/f'response-{v}/result.json') for v in ('0.5', '1', '2', '100')}
    # Recover old saved ordinates, including complex phase, before interpreting
    # the new parameter screen. This does not authenticate current aero physics.
    baseline_error = 0.
    for old in read(SAVED/'samples.json'):
        matches = [r for r in responses['1']['samples'] if r['frequency_hz'] == old['frequency_Hz']]
        if not matches:
            continue
        got = matches[0]['outputs'][0]
        want = complex(old['H_real'][0], old['H_imag'][0])*180/np.pi
        error = abs(complex(got['real'], got['imag'])-want)
        baseline_error = max(baseline_error, error)
        assert error < 1e-11
    with (ROOT/'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:
        reference = [(float(r['frequency_Hz']), float(r['reference_drawing_magnitude']))
                     for r in csv.DictReader(stream) if r['channel'] == 'yaw_rate']
    rows = []
    for key, result in responses.items():
        minimum = min(result['samples'], key=lambda row: row['outputs'][0]['magnitude'])
        one = next(row for row in result['samples'] if row['frequency_hz'] == 1.)
        at_reference = next(row for row in result['samples'] if row['frequency_hz'] == 1.157377737)
        rows.append(dict(stiffness_multiplier=float(key), yaw_at_1hz=one['outputs'][0],
            yaw_at_reference_dip=at_reference['outputs'][0],
            boom_relative_y_mm_at_1hz=one['outputs'][1]['magnitude']*304.8,
            lowest_sample_hz=minimum['frequency_hz'], lowest_sample_yaw=minimum['outputs'][0]['magnitude']))
    with plt.rc_context({'font.size': 10, 'svg.fonttype': 'none'}):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5))
        colors = {'0.5': '#ff9f1a', '1': '#ff4a3d', '2': '#00a6a6', '100': '#7067cf'}
        for key, result in responses.items():
            f = [row['frequency_hz'] for row in result['samples']]
            axes[0].loglog(f, [row['outputs'][0]['magnitude'] for row in result['samples']],
                          marker='o', markersize=3.5, color=colors[key], label=f'Boom stiffness ×{key}')
            axes[1].loglog(f, [304.8*row['outputs'][1]['magnitude'] for row in result['samples']],
                          marker='o', markersize=3.5, color=colors[key])
        axes[0].loglog(*zip(*reference), color='#555555', linestyle='--', label='Drela drawing; operating point unknown')
        axes[0].set(ylabel='Yaw rate [deg/s per native F3]', ylim=(.025, .25), title='Boom flexibility changes the yaw notch')
        axes[1].set(ylabel='Relative boom-tip lateral motion [mm per native F3]',
                    title='Tip motion relative to the boom root')
        for ax in axes:
            ax.set(xlim=(.18, 2.1), xlabel='Frequency [Hz]')
            for axis in (ax.xaxis, ax.yaxis):
                axis.set_major_locator(LogLocator(base=10))
                axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
                axis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:g}'))
                axis.set_minor_formatter(NullFormatter())
            ax.grid(which='major', color='#aeb4bd', linewidth=.7)
            ax.grid(which='minor', color='#dfe2e6', linewidth=.45)
        axes[0].legend(fontsize=8)
        fig.suptitle('Daedalus tailboom stiffness diagnostic — nine sampled frequencies')
        fig.text(.5, .015, 'Historical C16 coupled matrices; fixed loaded shape, prestress and mass. '
                 'Lines connect samples; no new trim or exact notch search.', ha='center', fontsize=8)
        fig.tight_layout(rect=(0, .05, 1, .95))
        fig.savefig(folder/'tailboom-sensitivity.svg')
        fig.savefig(folder/'tailboom-sensitivity.png', dpi=150)
        plt.close(fig)
    return dict(status='COMPLETED_DIAGNOSTIC_REFERENCE_MISMATCH_OPEN', observed_utc=utc(),
        audit=read(study/'audit/result.json'), stiffness_screen=rows,
        beam_checks=[read(beam_study/f'beam-{v}/result.json') for v in (16, 32)],
        baseline_complex_reproduction_max_abs_deg_s=baseline_error,
        maximum_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        maximum_wall_seconds=max(t['wall_seconds'] for t in terminals),
        maximum_peak_rss_kib=max(t['peak_rss_kib'] for t in terminals), all_workers_reaped=True,
        numerical_response_checks=36, physics_defaults_changed=False,
        qualifications=['Historical aircraft matrix sensitivity, not a fresh current-aircraft Bode prediction.',
            'The independent vacuum beam excludes attached tail masses, air, preload and free-flight coupling.',
            'Nominal C16 bare-boom higher-mode error exceeds 1%; C32 is below the predeclared 1% gate.',
            'First beam attempt rejected before any solve because its diagnostic input omitted Reference; retained unchanged.',
            'Default spatial midpoint structural discretization differs from the optional published endpoint-average operator.',
            'No new native ASWING comparison, ISAE pass, fitted parameter or default change.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['audit', 'beam', 'response', 'report'])
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--beam-study', type=Path)
    parser.add_argument('--panels', type=int, choices=[16, 32], default=16)
    parser.add_argument('--factor', type=float, choices=[.5, 1., 2., 100.], default=1.)
    parser.add_argument('--component', choices=['all', 'bending', 'torsion'], default='all')
    args = parser.parse_args()
    study = args.study.resolve()
    name = args.stage if args.stage in ('audit', 'report') else f'beam-{args.panels}' if args.stage == 'beam' else f'response-{args.factor:g}'
    if args.stage == 'response' and args.component != 'all':
        name = f'response-{args.component}-{args.factor:g}'
    folder = study/name
    folder.mkdir(parents=True, exist_ok=False)
    (folder/'runner.py').write_bytes(Path(__file__).read_bytes())
    inputs = list((ROOT/'openswing').glob('*.py'))+[Path(__file__), ROOT/'examples/dae.asw']
    if args.stage in ('audit', 'response'):
        inputs += [SAVED/x for x in ('A.npz', 'M.npz', 'control-rhs.npz', 'output-map.npy', 'base-unknowns.npz')]
        inputs += [ROOT/'examples/dae-cruise-physical-mesh-project.json',
                   ROOT/'tests/data/daedalus-curved-mechanics/independent-compatibility.npz']
    if args.stage == 'response':
        assert read(study/'audit/terminal.json')['returncode'] == 0
        inputs += [study/'audit'/x for x in ('result.json', 'rigid-boom-delta-A.npz', 'outputs.npy')]
    if args.stage == 'report':
        if args.beam_study is None:
            parser.error('--beam-study is required for report')
        inputs += [ROOT/'docs/validation/daedalus-rudder-four-outputs.csv', SAVED/'samples.json']
        jobs = [study/'audit']+[study/f'response-{v}' for v in ('0.5', '1', '2', '100')]
        jobs += [args.beam_study/f'beam-{v}' for v in (16, 32)]
        inputs += [job/file for job in jobs for file in ('result.json', 'terminal.json', 'plan.json')]
    pins = {str(p): pin(p) for p in inputs}
    write(folder/'plan.json', dict(observed_utc=utc(), stage=args.stage, limits=LIMITS, inputs_sha256=pins,
        panels=args.panels, stiffness_factor=args.factor, frequencies_hz=FREQUENCIES,
        stiffness_component=args.component,
        physics_defaults_changed=False, no_new_full_aircraft_solve=True))
    sys.stdout.flush()
    started = time.monotonic()
    pid = os.fork()
    if pid == 0:
        code = 0
        try:
            for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
                os.environ[key] = '1'
            resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
            resource.setrlimit(resource.RLIMIT_CPU, (LIMITS['cpu_seconds'],)*2)
            sys.path.insert(0, str(ROOT))
            with (folder/'stdout.log').open('x') as out, (folder/'stderr.log').open('x') as err:
                os.dup2(out.fileno(), 1); os.dup2(err.fileno(), 2)
                try:
                    imports()
                    if args.stage == 'audit':
                        result = audit(folder)
                    elif args.stage == 'beam':
                        result = beam(folder, args.panels)
                    elif args.stage == 'response':
                        result = response(folder, study, args.factor, args.component)
                    else:
                        result = report(folder, study, args.beam_study.resolve())
                    write(folder/'result.json', result)
                except BaseException:
                    traceback.print_exc(); code = 1
                sys.stdout.flush(); sys.stderr.flush()
        except BaseException:
            traceback.print_exc(); sys.stderr.flush(); code = 1
        finally:
            os._exit(code)
    reaped = 0
    timed_out = False
    try:
        while not reaped:
            reaped, status, usage = os.wait4(pid, os.WNOHANG)
            if reaped:
                break
            if time.monotonic()-started > LIMITS['wall_seconds']:
                timed_out = True
                os.kill(pid, signal.SIGKILL)
                reaped, status, usage = os.wait4(pid, 0)
                break
            time.sleep(.05)
    finally:
        if not reaped:
            os.kill(pid, signal.SIGKILL)
            reaped, status, usage = os.wait4(pid, 0)
    terminal = dict(observed_utc=utc(), returncode=os.waitstatus_to_exitcode(status), process_reaped=True,
        timed_out=timed_out, wall_seconds=time.monotonic()-started, cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss, limits=LIMITS, inputs_unchanged=all(pin(p) == h for p, h in pins.items()))
    write(folder/'terminal.json', terminal)
    print(json.dumps(terminal), flush=True)
    raise SystemExit(terminal['returncode'] or (1 if not terminal['inputs_unchanged'] else 0))


if __name__ == '__main__':
    main()
