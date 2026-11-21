"""Bounded wing-junction mass diagnostic and physical retrim.

Weights come from the independently retained Figure 7 excess-area trace.
Concentrating those areas at existing 14/42 ft stations is a declared model
assumption. It is not an authenticated historical input or a Bode fit.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_mesh_zeros import load, paths, factor_at, CHANNELS
from check_daedalus_mesh_residual import accepted
from check_daedalus_measured_mass import system, MassChange
from daedalus_bounded_job import run

STUDY = ROOT / 'artifacts/daedalus-wing-peak-mass-20261114'
PROPERTIES = ROOT / 'artifacts/daedalus-paper-properties-20261114'
UNIFORM = ROOT / 'artifacts/daedalus-measured-mass-20261114/beam-1'
DIP = 1.15737773741517


def point_rows(n, station, cg):
    import numpy as np
    from openswing.geometry import surface_frame
    beam = next(b for b in n.model.beams if b.index == 1); rows = []
    for t in (-station, station):
        node = n.node(1, t)
        offset = surface_frame(beam, t) @ np.array([beam.value('Ccg', t), 0., beam.value('Ncg', t)]) if cg else np.zeros(3)
        row = np.zeros(17); row[:2] = [1, t]; row[2:5] = n.rj[node] + offset; row[5] = 1.
        rows.append(row)
    return rows


class PointChange:
    def __init__(self, n, rows): self.n, self.rows = n, rows
    def __enter__(self):
        import numpy as np
        n = self.n; im = n.inertia_model
        self.old = (n.weights, n.model.records['weight'], im.rows, im.point_inertias, im.source_point_indices)
        n.weights = [*n.weights, *self.rows]
        n.model.records['weight'] = [*n.model.records['weight'], *self.rows]
        im.rows = [*im.rows, *self.rows]
        im.point_inertias = [*im.point_inertias, *[np.zeros((3, 3)) for row in self.rows]]
        im.source_point_indices = [*im.source_point_indices, *range(len(self.old[1]), len(n.model.records['weight']))]
        n.aero_key = n.mass_key = None
        return self
    def __exit__(self, *exc):
        n = self.n; im = n.inertia_model
        n.weights, n.model.records['weight'], im.rows, im.point_inertias, im.source_point_indices = self.old
        n.aero_key = n.mass_key = None


def variants():
    peaks = accepted(PROPERTIES / 'compare')['peaks']
    w = [p['excess_weight_above_local_baseline_lb'] for p in peaks]
    uncertainty = [p['conservative_two_pixel_area_bound_lb'] for p in peaks]
    total = 2 * sum(w)
    cases = {}
    for label, sign in [('nominal', 0), ('lower_trace', -1), ('upper_trace', 1)]:
        cases[label] = {f'point-{t}-cg': w[i] + sign * uncertainty[i] for i, t in enumerate((14, 42))}
    cases['beam_axis'] = {f'point-{t}-axis': w[i] for i, t in enumerate((14, 42))}
    cases['equal_weight_uniform'] = {'uniform': total / accepted(UNIFORM)['original_weight_lb']}
    return cases


def physical_rows(configuration):
    import numpy as np
    rows = []
    for tag, coefficient in variants()[configuration].items():
        assert tag != 'uniform'
        for row in accepted(STUDY / tag)['unit_weight_rows']:
            value = np.array(row); value[5] *= coefficient; rows.append(value)
    return rows


def assemble(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.structure import skew
    s = system(); n = s.network; size = s.size; zero = np.zeros(size)
    assert not n.hinges and not n.loads and not np.any(n.offa) and not np.any(n.offb)
    assert not np.any(s.Omega0) and not np.any(s.Omegadot0) and not np.any(s.motion.acceleration)
    rows = point_rows(n, args['station'], args['arm'] == 'cg')
    _, _, opt = s.physical_state(zero, zero); gravity = opt['gravity_override']
    dg = np.zeros((3, size)); da = np.zeros_like(dg); dalpha = np.zeros_like(dg)
    for j in [*range(n.operating_start, n.size), *range(s.frame_start + 9, s.frame_start + 12)]:
        dz = zero.copy(); dz[j] = 1e-4; values = []
        for k in (-2, -1, 1, 2):
            state, _, options = s.physical_state(k * dz, zero)
            _, motion, _ = n.operating.apply(state.x[n.operating_start:],
                condition_override=options['condition_override'], motion_override=options['motion_override'])
            values.append(np.r_[options['gravity_override'], motion.acceleration, motion.angular_acceleration])
        dg[:, j], da[:, j], dalpha[:, j] = ((values[0] - 8 * values[1] + 8 * values[2] - values[3]) / 12e-4).reshape(3, 3)
    a = np.zeros((size, size)); m = np.zeros_like(a)
    for row in rows:
        i = n.node(*row[:2]); mass = row[5] / n.model.constants[0]
        offset = s.Q0[i] @ (row[2:5] - n.rj[i]); position = s.r0[i] + offset
        df = mass * (dg - da + skew(position - n.model.reference[2]) @ dalpha)
        dm = skew(offset) @ df
        dm[:, 6 * i + 3:6 * i + 6] += mass * skew(gravity) @ skew(offset)
        dfm = np.zeros((3, size)); dmm = np.zeros_like(dfm)
        u = s.velocity_start + 3 * i; w = s.velocity_start + 3 * n.nn + 3 * i
        dfm[:, u:u + 3] = mass * s.V * np.eye(3)
        dfm[:, w:w + 3] = -mass * s.W * skew(offset); dmm[:] = skew(offset) @ dfm
        fr = slice(6 * n.ne + 3 * i, 6 * n.ne + 3 * i + 3)
        mr = slice(6 * n.ne + 3 * n.nn + 3 * i, 6 * n.ne + 3 * n.nn + 3 * i + 3)
        a[fr] += df / n.F; a[mr] += dm / (n.F * n.L)
        m[fr] += dfm / n.F; m[mr] += dmm / (n.F * n.L)
        arm = skew(s.r0[i] - n.model.reference[1])
        a[n.operating_start:n.operating_start + 3] += df / n.F
        a[n.operating_start + 3:n.size] += (dm + arm @ df) / (n.F * n.L)
        a[n.operating_start + 3:n.size, 6 * i:6 * i + 3] -= skew(mass * gravity) / n.F
        m[n.operating_start:n.operating_start + 3] += dfm / n.F
        m[n.operating_start + 3:n.size] += (dmm + arm @ dfm) / (n.F * n.L)
    a, m = sp.csc_matrix(a), sp.csc_matrix(m)
    rng = np.random.default_rng(732 + args['station']); z = rng.normal(size=size); rate = rng.normal(size=size)
    expected = a @ z - m @ rate; checks = []; baseline = s.residual(zero, zero)
    with PointChange(n, rows): changed = s.residual(zero, zero)
    for h in (1e-4, 5e-5):
        values = []
        for k in (-2, -1, 1, 2):
            original = s.residual(k * h * z, k * h * rate)
            with PointChange(n, rows): modified = s.residual(k * h * z, k * h * rate)
            values.append(modified - original)
        actual = (values[0] - 8 * values[1] + 8 * values[2] - values[3]) / (12 * h)
        absolute = float(max(abs(actual - expected))); relative = float(np.linalg.norm(actual - expected) / np.linalg.norm(expected))
        assert absolute < 3e-9 and relative < 1e-8, (absolute, relative)
        checks.append(dict(step=h, maximum_error=absolute, relative_error=relative))
    assert max(abs(s.residual(zero, zero) - baseline)) < 1e-14
    sp.save_npz(folder / 'A.npz', a); sp.save_npz(folder / 'M.npz', m)
    np.savez_compressed(folder / 'arrays.npz', static_offset=changed - baseline)
    return dict(station_ft=args['station'], arm=args['arm'], unit_weight_rows=[r.tolist() for r in rows],
        full_dimension=size, added_weight_lb=2., checks=checks, complete_residual_evaluations=19,
        qualification='Two 1 lb point masses with zero intrinsic inertia/drag/volume/spin. Pylon rotation and its inertia/gravity moments are retained; no finite-interval inertia is added to point masses.')


def response(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.harmonic_structure import ReusableBeamStructure
    a, m, b, c, layout, seed, structure = load('coarse'); f = args['frequency']
    original, baseline = factor_at(a, m, 2j * np.pi * f, structure)(b); y0 = c @ original
    results = []; states = []; outputs = []
    for name, factors in variants().items():
        aa, mm = a.copy(), m.copy()
        for tag, coefficient in factors.items():
            path = UNIFORM if tag == 'uniform' else STUDY / tag
            aa += coefficient * sp.load_npz(path / 'A.npz'); mm += coefficient * sp.load_npz(path / 'M.npz')
        for matrix in (aa, mm):
            for array in (matrix.data, matrix.indices, matrix.indptr): array.flags.writeable = False
        nn, ne = layout['nodes'], layout['elements']; gs = layout['circulation']['start']
        velocities = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
        factor = ReusableBeamStructure(aa, mm, np.r_[np.arange(6 * ne), np.arange(6 * (nn + ne), gs)],
            np.arange(6 * (nn + ne)), velocities, velocities)
        state, checks = factor_at(aa, mm, 2j * np.pi * f, factor)(b); y = c @ state
        states.append(state); outputs.append(y)
        results.append(dict(configuration=name, coefficients=factors, output_magnitude=abs(y).tolist(),
            amplitude_change_percent=(100 * (abs(y) / abs(y0) - 1)).tolist(), checks=checks))
    np.savez_compressed(folder / 'arrays.npz', states=states, outputs=outputs, original_state=original, original_output=y0)
    return dict(frequency_hz=f, baseline_checks=baseline, original_output_magnitude=abs(y0).tolist(), configurations=results,
        qualification='Full 2044-state solves at original mean shape held by constant residual offsets. Point placement, intrinsic inertia and CG assumptions remain conditional.')


def export_case(folder, args):
    import numpy as np
    from openswing.asw import parse_asw
    rows = physical_rows('nominal'); text = (ROOT / 'examples/dae.asw').read_text(); lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == 'Weight')
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == 'End')
    added = ['! Conditional Figure 7 peak-excess point weights; not historical Bode inputs.',
             '! 1.738957 lb at each +/-14 ft station; 0.631546 lb at each +/-42 ft station.']
    added += ['  ' + '  '.join(format(v, '.17g') for v in row) for row in rows]
    modified = '\n'.join([*lines[:end], *added, *lines[end:]]) + '\n'
    model = parse_asw(modified, beam_interpolation='drela-segspl-v1'); original = parse_asw(text, beam_interpolation='drela-segspl-v1')
    np.testing.assert_array_equal(model.records['weight'][:-4], original.records['weight'])
    np.testing.assert_allclose(model.records['weight'][-4:], rows, atol=0, rtol=2e-15)
    for before, after in zip(original.beams, model.beams):
        for name, table in before.distributions.items():
            np.testing.assert_array_equal(table.t, after.distributions[name].t)
            np.testing.assert_array_equal(table.values, after.distributions[name].values)
    with (folder / 'dae-wing-peak-mass.asw').open('x') as stream: stream.write(modified)
    return dict(rows=[r.tolist() for r in rows], added_weight_lb=float(sum(r[5] for r in rows)), requires_new_trim=True,
        qualification='Nominal raster-excess case selected before responses: physical centroids assumed at existing section CGs; point objects have zero intrinsic inertia, drag, volume and spin.')


def setup(seed=None):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore, restore_physical_fields
    from openswing.time_state import read_condition
    original = read(paths('coarse')[2]); packet = original if seed is None else read(seed); launch = packet['launch']
    model = parse_asw((STUDY / 'case/dae-wing-peak-mass.asw').read_text(), beam_interpolation='drela-segspl-v1')
    panels = dict(default=16, beams={k: dict(nodes=v[0]) for k, v in original['identity']['stations'].items()})
    n = SourceAirflowNetwork(model, panels, read_condition(launch['condition']), launch['gravity'], launch['loads'],
        operating_constraints=launch['released_constraints'], strut_mode=launch['strut_mode'],
        mesh_recipe='physical-breaks-v1', steady_trim=True)
    for k, (stations, indices) in n.station_nodes.items():
        np.testing.assert_array_equal(stations, original['identity']['stations'][str(k)][0])
    assert n.nn == 108 and n.ne == 103 and n.ng == 82 and len(n.weights) == 9
    x = restore_physical_fields(n, packet) if seed is None else restore(n, packet)
    return n, x


def trim(folder, args):
    import scipy.sparse as sp
    import scipy.sparse.linalg as spla
    import check_daedalus_source_operator as source
    n, x = setup(Path(args['seed']) if args['seed'] else None)
    matrix = sp.load_npz(SOURCE / 'trim-6.7-1/trim-tangent.npz')
    assert matrix.shape == (n.size, n.size)
    # A chord-Newton accelerator only. Every accepted step evaluates the
    # changed physical aircraft's full nonlinear trim residual, with no offset.
    solve = spla.splu(matrix); history = [float(max(abs(n.residual(x))))]
    for _ in range(6):
        residual = n.residual(x); norm = float(max(abs(residual)))
        if norm <= 1e-9: break
        step = solve.solve(-residual)
        for power in range(9):
            candidate = x + step / 2**power
            try: error = float(max(abs(n.residual(candidate))))
            except ValueError: continue
            if error < norm * (1 - 1e-4 / 2**power) or error <= 1e-9:
                x = candidate; history.append(error); break
        else: raise RuntimeError('Changed-aircraft trim line search failed.')
    return source.save_state(folder, n, x, residual_history=history,
        qualification='Physical nonlinear trim of nominal added-point-mass aircraft; no affine offset. Reused literal-aircraft tangent is an accelerator, not a changed-aircraft rank certificate.')


def retrim_system(seed):
    import numpy as np
    from openswing.linear_dynamics import _dynamic_base
    from openswing.operating import time_load_constraints
    n, x = setup(seed)
    assert max(abs(n.residual(x))) <= 1e-9
    zero = np.zeros_like(n.rj)
    return _dynamic_base(n, x, time_load_constraints('free'), 'free',
        dict(elastic_motion=(zero, zero, zero, zero), circulation_rate=np.zeros(n.circulation_basis.panels)),
        position=(0, 0, 0), attitude=(0, 0, 0), velocity=(0, 0, 0), gravity_magnitude=None)


def retrim_step(folder, args):
    """Correct full new-aircraft harmonic residuals using the old factor only as a preconditioner."""
    import numpy as np
    from openswing.frequency_response import HarmonicInput
    s = retrim_system(Path(args['seed'])); n = s.network; zero = np.zeros(s.size)
    a, m, b, old_c, layout, packet, structure = load('coarse')
    assert s.size == len(b) and s.frame_start == layout['frame']['start']
    np.testing.assert_allclose([s.L, s.V, s.W], [layout['node_coordinates']['translation_scale'],
        layout['local_velocity']['scale'], layout['local_rates']['scale']], rtol=2e-14)
    omega = 2 * np.pi * args['frequency']; solve = factor_at(a, m, 1j * omega, structure)
    original, original_checks = solve(b)
    if args['source']:
        previous = accepted(STUDY / args['source'])
        assert previous['frequency_hz'] == args['frequency']
        assert previous['physical_seed'] == str(Path(args['seed']).resolve())
        with np.load(STUDY / args['source'] / 'arrays.npz') as saved: z = saved[args['state']]
    else: z = original
    c = old_c.copy()
    alpha, beta = np.deg2rad([s.condition.alpha, s.condition.beta])
    c[2, s.frame_start:s.frame_start + 3] = s.V / s.condition.speed * 180 / np.pi * np.array([
        np.cos(alpha) * np.sin(beta), np.cos(beta), np.sin(alpha) * np.sin(beta)])
    forcing, _ = HarmonicInput(s, 'control.3', 0).at_frequency(omega)
    base = s.residual(zero, zero); assert max(abs(base)) < 1e-9
    history = []; calls = 1
    for iteration in range(args['iterations']):
        pieces = []; h = args['width']
        for part, component in enumerate((np.real, np.imag)):
            def sample(amplitude):
                return s.residual(amplitude * component(z), amplitude * component(1j * omega * z),
                                  forcing=forcing(part, amplitude)) - base
            pieces.append((sample(-2 * h) - 8 * sample(-h) + 8 * sample(h) - sample(2 * h)) / (12 * h))
        residual = pieces[0] + 1j * pieces[1]; calls += 8
        correction, checks = solve(residual)
        output = c @ z; output_correction = c @ correction
        absolute = float(max(abs(residual)))
        relative_change = float(max(abs(output_correction) / np.maximum(abs(output), 1e-30)))
        valid = absolute < 2e-11 and relative_change < 2e-7
        history.append(dict(iteration=iteration, complete_harmonic_residual=absolute,
            next_relative_output_change=relative_change, evaluated_state_accepted=valid, preconditioner_solve_checks=checks))
        if valid or iteration == args['iterations'] - 1: break
        z = z + correction
    np.savez_compressed(folder / 'arrays.npz', state=z, next_state=z + correction, output=output,
        next_output=c @ (z + correction), full_harmonic_residual=residual, output_correction=output_correction,
        original_output=old_c @ original)
    return dict(frequency_hz=args['frequency'], physical_seed=str(Path(args['seed']).resolve()),
        source=args['source'], state=args['state'], width=args['width'], history=history,
        evaluated_state_accepted=valid, output_magnitude=abs(output).tolist(),
        original_output_magnitude=abs(old_c @ original).tolist(), full_dimension=s.size,
        base_residual=float(max(abs(base))), complete_residual_evaluations=calls,
        qualification='Full nonlinear-residual linear response at a physically retrimmed changed aircraft, without affine offsets. Old complete descriptor is only an iterative preconditioner; its condition estimate does not certify the changed operator.')


PAIRS = [('low', 'physical-low-3', 'physical-low-check'),
         ('dip', 'physical-dip-width-0.002', 'physical-dip-width-0.004'),
         ('roll', 'physical-roll-4', 'physical-roll-check')]


def report(folder, args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator, FuncFormatter, NullFormatter
    with (ROOT / 'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:
        raw = list(csv.DictReader(stream))
    reference = {ch: np.array(sorted((float(r['frequency_Hz']), float(r['reference_drawing_magnitude']))
                                    for r in raw if r['channel'] == ch)) for ch in CHANNELS}
    rows = []; checks = []
    for fixed_tag, first, second in PAIRS:
        fixed = accepted(STUDY / fixed_tag); p, q = accepted(STUDY / first), accepted(STUDY / second)
        assert p['evaluated_state_accepted'] and q['evaluated_state_accepted']
        assert p['width'] == .002 and q['width'] == .004
        assert p['physical_seed'] == q['physical_seed'] == str((STUDY / 'trim-1/state.json').resolve())
        with np.load(STUDY / first / 'arrays.npz') as data: left = dict(data)
        with np.load(STUDY / second / 'arrays.npz') as data: right = dict(data)
        np.testing.assert_array_equal(left['state'], right['state'])
        difference = float(max(abs(left['output_correction'] - right['output_correction']) / abs(left['output'])))
        assert difference < 2e-7
        f = p['frequency_hz']; assert f == q['frequency_hz'] == fixed['frequency_hz']
        checks.append(dict(frequency_hz=f, first=first, second=second,
            first_residual=p['history'][-1]['complete_harmonic_residual'],
            second_residual=q['history'][-1]['complete_harmonic_residual'],
            width_output_correction_difference_relative=difference))
        configs = [dict(configuration='literal', output_magnitude=fixed['original_output_magnitude']),
                   *fixed['configurations'], dict(configuration='physically_retrimmed', output_magnitude=p['output_magnitude'])]
        for config in configs:
            for j, ch in enumerate(CHANNELS):
                target = float(np.exp(np.interp(np.log(f), np.log(reference[ch][:, 0]), np.log(reference[ch][:, 1]))))
                value = config['output_magnitude'][j]
                rows.append(dict(frequency_hz=f, channel=ch, configuration=config['configuration'],
                    magnitude=value, reference_magnitude=target, reference_error_percent=100 * (value / target - 1)))
    n, x = setup(STUDY / 'trim-1/state.json'); residual, data = n.residual(x, detail=True)
    weight = float(sum(np.sum(record['mass']) for record in data['masses']) * n.model.constants[0])
    original_weight = read(ROOT / 'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json')['weight_lb']
    added = accepted(STUDY / 'case')['added_weight_lb']
    assert abs(weight - original_weight - added) < 1e-10 and max(abs(residual)) < 1e-9
    root = data['r'][n.node(1, 0)]
    trim_summary = dict(weight_lb=weight, added_weight_lb=added, alpha_deg=data['condition'].alpha,
        maximum_section_cl=max(s['cl'] for s in data['aero']['strips'] if s['cl'] is not None),
        wing_tip_height_above_root_ft=[float(data['r'][n.node(1, t), 2] - root[2]) for t in (-56, 56)],
        physical_trim_residual=float(max(abs(residual))))
    with (folder / 'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (SOURCE / 'report/comparison.csv').open() as stream:
        baseline = [r for r in csv.DictReader(stream) if float(r['speed_m_s']) == 6.7]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    for j, (ax, ch) in enumerate(zip(axes.flat, CHANNELS)):
        original = sorted((float(r['frequency_hz']), float(r['magnitude_display'])) for r in baseline if r['channel'] == ch)
        ax.loglog(reference[ch][:, 0], reference[ch][:, 1], color='#333333', label='Drela published magnitude')
        ax.loglog([v[0] for v in original], [v[1] for v in original], color='#ff4a3d', label='Literal aircraft (retained sweep)')
        for config, color, marker, label in [('nominal', '#ff9f1a', '^', 'Peak masses, held mean shape'),
                ('physically_retrimmed', '#ffd166', 'o', 'Peak masses, physical retrim')]:
            selected = [r for r in rows if r['channel'] == ch and r['configuration'] == config]
            ax.loglog([r['frequency_hz'] for r in selected], [r['magnitude'] for r in selected],
                color=color, marker=marker, linestyle='none', markersize=6, markeredgecolor='#333333', markeredgewidth=.6, label=label)
        ax.set_title(ch.replace('_', ' ').title()); ax.set_xlabel('Frequency (cycles/s)')
        ax.set_ylabel(('deg/s' if j < 2 else 'deg') + ' per F3 unit'); ax.set_xlim(.1, 10)
        for axis in (ax.xaxis, ax.yaxis):
            axis.set_major_locator(LogLocator(base=10)); axis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10)))
            axis.set_major_formatter(FuncFormatter(lambda value, pos: f'{value:g}')); axis.set_minor_formatter(NullFormatter())
        ax.grid(which='major', color='#aaaaaa', alpha=.6); ax.grid(which='minor', color='#dddddd', alpha=.65)
        if j == 0: ax.legend(fontsize=8)
    fig.suptitle('Daedalus: Figure 7 wing-peak mass diagnostic\nNew results are three frequency samples; four point masses and their centroids are disclosed assumptions')
    fig.savefig(folder / 'comparison.png', dpi=150); fig.savefig(folder / 'comparison.svg'); plt.close(fig)
    return dict(trim=trim_summary, paired_stencil_checks=checks, rows=rows,
        fixed_mean_full_solves=18, physically_retrimmed_frequencies=3,
        qualification='Nominal raster peak excess, not the complete Figure 7 density distribution or an authenticated Bode setup. New physical responses are isolated samples, not a sweep or a native-reference pass count.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['assemble', 'response', 'export_case', 'trim', 'retrim_step', 'report'])
    parser.add_argument('--tag', required=True); parser.add_argument('--station', type=int, choices=[14, 42])
    parser.add_argument('--arm', choices=['cg', 'axis'], default='cg')
    parser.add_argument('--frequency', type=float, default=DIP); parser.add_argument('--seed')
    parser.add_argument('--source'); parser.add_argument('--state', choices=['state', 'next_state'], default='next_state')
    parser.add_argument('--width', type=float, default=.001); parser.add_argument('--iterations', type=int, choices=[1, 2], default=2)
    args = vars(parser.parse_args())
    inputs = [ROOT / 'scripts' / name for name in ('check_daedalus_measured_mass.py', 'check_daedalus_mesh_zeros.py',
        'check_daedalus_mesh_residual.py', 'check_daedalus_structural_resolution.py', 'check_daedalus_source_operator.py')]
    inputs += list((ROOT / 'openswing').glob('*.py'))
    inputs += [ROOT / name for name in ('examples/dae.asw', 'examples/dae-cruise-physical-mesh-project.json', 'docs/validation/ISAE_STATUS.md',
        'docs/validation/aswing-authoritative-sources.json', 'docs/validation/isae-st4-node-placement-sources-20261109.json',
        'reference/st4-node-placement-20261109/drela-1989-wing-loads.pdf',
        'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf')]
    matrix, layout, seed = paths('coarse'); inputs += [layout, seed]
    folders = [matrix, PROPERTIES / 'compare', UNIFORM]
    if args['stage'] != 'assemble': folders += [STUDY / f'point-{t}-{arm}' for t in (14, 42) for arm in ('cg', 'axis')]
    if args['stage'] in ('trim', 'retrim_step', 'report'):
        folders += [STUDY / 'case']; inputs += [SOURCE / 'trim-6.7-1/trim-tangent.npz']
    if args['seed']: inputs += [Path(args['seed']).resolve()]
    if args['source']: folders += [STUDY / args['source']]
    if args['stage'] == 'report':
        folders += [STUDY / 'trim-1', *[STUDY / tag for group in PAIRS for tag in group]]
        inputs += [ROOT / 'docs/validation/daedalus-rudder-four-outputs.csv', SOURCE / 'report/comparison.csv',
            ROOT / 'artifacts/daedalus-wing-paper-20261113/static-and-pages-v3/result.json']
    for folder in folders: inputs += [p for p in folder.iterdir() if p.suffix in ('.json', '.npz', '.asw')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
