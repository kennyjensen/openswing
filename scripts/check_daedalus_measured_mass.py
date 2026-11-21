"""Measured-weight sensitivity with full source gravity and inertia tangents.

The original mean state is held by a constant residual offset. These are
conditional dynamic diagnostics, not retrimmed aircraft or native-ASWING runs.
Measured totals do not specify the mass distribution: each disclosed case
scales an existing beam distribution, leaving aerodynamic properties intact.
"""
import argparse
from pathlib import Path
from types import SimpleNamespace
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from check_daedalus_mesh_zeros import load, paths, factor_at, CHANNELS
from check_daedalus_mesh_residual import accepted
from daedalus_bounded_job import run

STUDY = ROOT / 'artifacts/daedalus-measured-mass-20261114'
PROPERTIES = ROOT / 'artifacts/daedalus-paper-properties-20261114'
DIP = 1.15737773741517


def system():
    from check_daedalus_structural_resolution import dynamic
    return dynamic(SimpleNamespace(seed=paths('coarse')[2]))


class MassChange:
    """Transient, internally consistent scaling of selected distributed mass."""
    def __init__(self, network, increments):
        self.n = network
        self.increments = increments

    def __enter__(self):
        n = self.n
        self.original = (n.source_weights, n.source_mass_samples,
                         n.source_rotary_samples, n.inertia_model.data)
        n.source_weights = n.source_weights.copy()
        for beam, delta in self.increments.items():
            n.source_weights[n.beam_elements[beam]] *= 1 + delta
        n.source_mass_samples = [(beam, sl, end, mass * (1 + self.increments.get(beam, 0)), arm)
                                 for beam, sl, end, mass, arm in n.source_mass_samples]
        n.source_rotary_samples = [inertia * (1 + self.increments.get(sample[0], 0))
                                   for sample, inertia in zip(self.original[1], self.original[2])]
        n.inertia_model.data = {beam: [(m * (1 + self.increments.get(beam, 0)), c, normal,
                                       icc * (1 + self.increments.get(beam, 0)),
                                       inn * (1 + self.increments.get(beam, 0)))
                                      for m, c, normal, icc, inn in records]
                                for beam, records in n.inertia_model.data.items()}
        return self

    def __exit__(self, *exc):
        self.n.source_weights, self.n.source_mass_samples, self.n.source_rotary_samples, self.n.inertia_model.data = self.original


def assemble(folder, args):
    """Analytic zero-base-rate mass tangent, checked against full residuals."""
    import numpy as np
    import scipy.sparse as sp
    from openswing.structure import skew
    s = system(); n = s.network; size = s.size; zero = np.zeros(size)
    assert size == 2044 and not n.hinges and not n.loads
    assert not np.any(n.offa) and not np.any(n.offb)
    assert not np.any(s.Omega0) and not np.any(s.Omegadot0) and not np.any(s.motion.acceleration)
    assert [c.quantity for c in n.operating.constraints] == ['force.' + x for x in 'xyz'] + ['moment.' + x for x in 'xyz']
    _, _, options = s.physical_state(zero, zero)
    gravity = options['gravity_override']
    # Extract only the canonical coordinate-to-physical maps. These contain
    # no aerodynamic or elastic response and are independently stencil-checked.
    dg = np.zeros((3, size)); da = np.zeros_like(dg); dalpha = np.zeros_like(dg)
    columns = list(range(n.operating_start, n.size)) + list(range(s.frame_start + 9, s.frame_start + 12))
    for j in columns:
        dz = zero.copy(); dz[j] = 1e-4
        values = []
        for k in (-2, -1, 1, 2):
            state, _, opt = s.physical_state(k * dz, zero)
            _, motion, _ = n.operating.apply(state.x[n.operating_start:],
                condition_override=opt['condition_override'], motion_override=opt['motion_override'])
            values.append(np.r_[opt['gravity_override'], motion.acceleration, motion.angular_acceleration])
        derivative = (values[0] - 8 * values[1] + 8 * values[2] - values[3]) / (12e-4)
        dg[:, j], da[:, j], dalpha[:, j] = derivative.reshape(3, 3)
    a = np.zeros((size, size)); m = np.zeros_like(a)
    fa = np.zeros((3 * n.nn, size)); ma = np.zeros_like(fa)
    fm = np.zeros_like(fa); mm = np.zeros_like(fa); base_force = np.zeros((n.nn, 3))
    _, _, ra, rb, *_ = n.geometry(s.r0, s.Q0)
    weight = 0.
    for sample, rotary in zip(n.source_mass_samples, n.source_rotary_samples):
        beam, sl, end, masses, arms = sample
        if beam != args['beam']: continue
        for local, e in enumerate(range(sl.start, sl.stop)):
            mass = masses[local]; weight += mass * n.model.constants[0]
            source = int((n.a if end == 0 else n.b)[e])
            rotation = (ra if end == 0 else rb)[e]
            offset = rotation @ arms[local]
            diagonal = rotary[local] + mass * n.ds[e]**2 / 12 * np.array([1., 0., 1.])
            inertia = (rotation * diagonal[None, :]) @ rotation.T
            df = mass * (dg - da + skew(s.r0[source] + offset - n.model.reference[2]) @ dalpha)
            dm = skew(offset) @ df - inertia @ dalpha
            dm[:, 6 * source + 3:6 * source + 6] += mass * skew(gravity) @ skew(offset)
            # M is minus the residual derivative with respect to state rate.
            dfm = np.zeros((3, size)); dmm = np.zeros_like(dfm)
            u = s.velocity_start + 3 * source; w = s.velocity_start + 3 * n.nn + 3 * source
            dfm[:, u:u + 3] = mass * s.V * np.eye(3)
            dfm[:, w:w + 3] = -mass * s.W * skew(offset)
            dmm[:] = skew(offset) @ dfm
            dmm[:, w:w + 3] += s.W * inertia
            for target in (int(n.a[e]), int(n.b[e])):
                rows = slice(3 * target, 3 * target + 3)
                fa[rows] += df / 2; ma[rows] += dm / 2
                fm[rows] += dfm / 2; mm[rows] += dmm / 2
                base_force[target] += mass * gravity / 2
    close_weight = float(n.source_weights[n.beam_elements[args['beam']]].sum())
    assert abs(weight - close_weight) < 1e-12
    fr = slice(6 * n.ne, 6 * n.ne + 3 * n.nn)
    mr = slice(6 * n.ne + 3 * n.nn, 6 * (n.ne + n.nn))
    a[fr] = fa / n.F; a[mr] = ma / (n.F * n.L)
    m[fr] = fm / n.F; m[mr] = mm / (n.F * n.L)
    for i in range(n.nn):
        rows = slice(3 * i, 3 * i + 3); arm = skew(s.r0[i] - n.model.reference[1])
        a[n.operating_start:n.operating_start + 3] += fa[rows] / n.F
        a[n.operating_start + 3:n.size] += (ma[rows] + arm @ fa[rows]) / (n.F * n.L)
        a[n.operating_start + 3:n.size, 6 * i:6 * i + 3] -= skew(base_force[i]) / n.F
        m[n.operating_start:n.operating_start + 3] += fm[rows] / n.F
        m[n.operating_start + 3:n.size] += (mm[rows] + arm @ fm[rows]) / (n.F * n.L)
    a, m = sp.csc_matrix(a), sp.csc_matrix(m)
    del fa, ma, fm, mm
    rng = np.random.default_rng(66141 + args['beam'])
    dz = rng.normal(size=size); rate = rng.normal(size=size)
    expected = a @ dz - m @ rate; checks = []
    baseline = s.residual(zero, zero)
    with MassChange(n, {args['beam']: 1.}): changed = s.residual(zero, zero)
    for h in (1e-4, 5e-5):
        values = []
        for k in (-2, -1, 1, 2):
            old = s.residual(k * h * dz, k * h * rate)
            with MassChange(n, {args['beam']: 1.}): new = s.residual(k * h * dz, k * h * rate)
            values.append(new - old)
        actual = (values[0] - 8 * values[1] + 8 * values[2] - values[3]) / (12 * h)
        absolute = float(max(abs(actual - expected)))
        relative = float(np.linalg.norm(actual - expected) / np.linalg.norm(expected))
        assert absolute < 3e-9 and relative < 1e-8, (absolute, relative)
        checks.append(dict(step=h,maximum_error=absolute,relative_error=relative))
    assert max(abs(s.residual(zero, zero) - baseline)) < 1e-14
    sp.save_npz(folder / 'A.npz', a); sp.save_npz(folder / 'M.npz', m)
    np.savez_compressed(folder / 'arrays.npz', static_offset=changed - baseline,
                        state_direction=dz, rate_direction=rate, expected_action=expected)
    return dict(beam=args['beam'], original_weight_lb=weight, full_dimension=size,
        state_nonzeros=a.nnz, rate_nonzeros=m.nnz, checks=checks,
        base_residual=float(max(abs(baseline))), static_residual_offset=float(max(abs(changed - baseline))),
        complete_residual_evaluations=19,
        qualification='Unit fractional increase of this beam distributed mass and section inertia. Aerodynamics, geometry, point masses and matrix scaling are unchanged.')


def configurations():
    weights = {i: accepted(STUDY / f'beam-{i}')['original_weight_lb'] for i in range(1, 6)}
    measured = accepted(PROPERTIES / 'measured')['comparisons']
    target = [row['published_measured_lb'] for row in measured]
    surface = {i: target[i - 1] / weights[i] - 1 for i in (1, 2, 3)}
    extra = target[3] - (weights[4] + weights[5] + 8.)
    return {
        'wing': {1: surface[1]}, 'elevator': {2: surface[2]}, 'rudder': {3: surface[3]},
        'wing_tail': surface,
        'all_boom': {**surface, 4: extra / weights[4]},
        'all_fairing': {**surface, 5: extra / weights[5]},
        'all_shared': {**surface, 4: extra / (weights[4] + weights[5]), 5: extra / (weights[4] + weights[5])},
    }, weights


def response(folder, args):
    import numpy as np
    import scipy.sparse as sp
    from openswing.harmonic_structure import ReusableBeamStructure
    a, m, b, c, layout, seed, structure = load('coarse')
    configurations_, weights = configurations(); rows = []; states = []; outputs = []
    original, base_check = factor_at(a, m, 2j * np.pi * args['frequency'], structure)(b)
    y0 = c @ original
    for name, factors in configurations_.items():
        aa, mm = a.copy(), m.copy()
        for beam, delta in factors.items():
            aa += delta * sp.load_npz(STUDY / f'beam-{beam}' / 'A.npz')
            mm += delta * sp.load_npz(STUDY / f'beam-{beam}' / 'M.npz')
        # Factor reuse is tied to a particular descriptor identity. The
        # modified mass model requires its own exact structural factor.
        nn, ne = layout['nodes'], layout['elements']; gs = layout['circulation']['start']
        velocities = np.arange(layout['local_velocity']['start'], layout['frame']['start'])
        for matrix in (aa, mm):
            for array in (matrix.data, matrix.indices, matrix.indptr): array.flags.writeable = False
        changed_structure = ReusableBeamStructure(aa, mm,
            np.r_[np.arange(6 * ne), np.arange(6 * (nn + ne), gs)],
            np.arange(6 * (nn + ne)), velocities, velocities)
        z, checks = factor_at(aa, mm, 2j * np.pi * args['frequency'], changed_structure)(b)
        y = c @ z; states.append(z); outputs.append(y)
        rows.append(dict(configuration=name, fractional_mass_increases=factors,
            added_weight_lb=sum(weights[i] * v for i, v in factors.items()),
            output_magnitude=abs(y).tolist(), amplitude_change_percent=(100 * (abs(y) / abs(y0) - 1)).tolist(),
            checks=checks))
    np.savez_compressed(folder / 'arrays.npz', states=states, outputs=outputs,
                        original_state=original, original_output=y0)
    return dict(frequency_hz=args['frequency'], configurations=rows, full_dimension=len(b),
        original_output_magnitude=abs(y0).tolist(), baseline_checks=base_check,
        qualification='Complete harmonic solves at original equilibrium held by constant residual offsets. Uniform existing beam mass distributions; body/fairing placements are disclosed alternatives, not inferred locations or physical retrims.')


def balance(folder, args):
    import numpy as np
    from openswing.frequency_response import HarmonicInput
    data = accepted(STUDY / args['source'])
    row = next(r for r in data['configurations'] if r['configuration'] == args['configuration'])
    with np.load(STUDY / args['source'] / 'arrays.npz') as saved:
        z = saved['states'][data['configurations'].index(row)]
    s = system(); n = s.network; zero = np.zeros(s.size); omega = 2 * np.pi * data['frequency_hz']
    forcing, _ = HarmonicInput(s, 'control.3', 0).at_frequency(omega)
    checks = []; stencils = []
    with MassChange(n, {int(k): v for k, v in row['fractional_mass_increases'].items()}):
        base = s.residual(zero, zero)
        for h in (.001, .0005):
            values = []
            for part, component in enumerate((np.real, np.imag)):
                def sample(amplitude):
                    return s.residual(amplitude * component(z), amplitude * component(1j * omega * z),
                                      forcing=forcing(part, amplitude)) - base
                values.append((sample(-2 * h) - 8 * sample(-h) + 8 * sample(h) - sample(2 * h)) / (12 * h))
            error = values[0] + 1j * values[1]; absolute = float(max(abs(error)))
            assert absolute < 2e-9, absolute
            stencils.append(error); checks.append(dict(step=h, maximum_complete_harmonic_residual=absolute))
    return dict(configuration=args['configuration'], source=args['source'], frequency_hz=data['frequency_hz'],
        full_dimension=s.size, checks=checks, stencil_difference=float(max(abs(stencils[0] - stencils[1]))),
        static_offset=float(max(abs(base))), complete_residual_evaluations=17,
        qualification='Full nonlinear residual derivative including rudder forcing, with changed gravity and inertia and a constant mean residual offset. Not a physical retrim.')


def cases(folder, args):
    """Export reviewable conditional inputs without changing the public file."""
    import numpy as np
    from openswing.asw import parse_asw
    source = (ROOT / 'examples/dae.asw').read_text()
    original = parse_asw(source, beam_interpolation='drela-segspl-v1')
    variants, weights = configurations(); records = []
    mass_fields = {'mg', 'Dmg', 'mgcc', 'mgnn', 'Dmgcc', 'Dmgnn'}
    for name, increments in variants.items():
        beam = None; columns = None; lines = []
        for line in source.splitlines():
            body = line.split('#')[0].split('!')[0]; tokens = body.split()
            if len(tokens) == 2 and tokens[0] == 'Beam':
                beam = int(tokens[1]); columns = None
            elif tokens == ['End']: beam = None; columns = None
            elif beam is not None and tokens:
                if tokens[0] == 't': columns = tokens
                elif columns and tokens[0] != '*' and beam in increments:
                    changed = False
                    for j, field in enumerate(columns):
                        if field in mass_fields:
                            tokens[j] = format(float(tokens[j]) * (1 + increments[beam]), '.17g'); changed = True
                    if changed: line = '  ' + '  '.join(tokens) + line[len(body):]
            lines.append(line)
        text = '\n'.join(lines) + '\n'
        model = parse_asw(text, beam_interpolation='drela-segspl-v1')
        for old, new in zip(original.beams, model.beams):
            assert old.index == new.index and old.distributions.keys() == new.distributions.keys()
            for field, table in old.distributions.items():
                np.testing.assert_array_equal(table.t, new.distributions[field].t)
                factor = 1 + increments.get(old.index, 0) if field in mass_fields else 1
                np.testing.assert_allclose(new.distributions[field].values, table.values * factor, rtol=2e-15, atol=0)
        filename = f'dae-measured-{name.replace("_", "-")}.asw'
        with (folder / filename).open('x') as stream: stream.write(text)
        records.append(dict(configuration=name, filename=filename, fractional_mass_increases=increments,
            source_operator_added_weight_lb=sum(weights[i] * v for i, v in increments.items()),
            requires_new_trim=True))
    return dict(cases=records, qualification='Conditional uniform-distribution models for later physical retrim. Only existing distributed mass/inertia table ordinates change; aerodynamic tables, all attachments and point weights remain literal. These files do not identify Drela historical Bode inputs.')


def report(folder, args):
    import csv
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tags = ['low', 'dip-v3', 'roll']; rows = []; summaries = []
    with (ROOT / 'docs/validation/daedalus-rudder-four-outputs.csv').open() as stream:
        raw = list(csv.DictReader(stream))
    reference = {ch: np.array(sorted((float(r['frequency_Hz']), float(r['reference_drawing_magnitude']))
                                     for r in raw if r['channel'] == ch)) for ch in CHANNELS}
    for tag in tags:
        result = accepted(STUDY / tag); f = result['frequency_hz']
        target = np.array([np.exp(np.interp(np.log(f), np.log(reference[ch][:, 0]), np.log(reference[ch][:, 1])))
                           for ch in CHANNELS])
        for config in [dict(configuration='literal', output_magnitude=result['original_output_magnitude'],
                            amplitude_change_percent=[0.] * 4), *result['configurations']]:
            for j, ch in enumerate(CHANNELS):
                rows.append(dict(frequency_hz=f, configuration=config['configuration'], channel=ch,
                    magnitude=config['output_magnitude'][j], reference_magnitude=float(target[j]),
                    amplitude_change_percent=config['amplitude_change_percent'][j],
                    reference_error_percent=float(100 * (config['output_magnitude'][j] / target[j] - 1))))
        complete = [r for r in result['configurations'] if r['configuration'].startswith('all_')]
        summaries.append(dict(frequency_hz=f, literal_yaw=result['original_output_magnitude'][0],
            reference_yaw=float(target[0]), all_measured_yaw_range=[min(r['output_magnitude'][0] for r in complete),
                                                                  max(r['output_magnitude'][0] for r in complete)]))
        accepted(STUDY / ('balance-' + {'low': 'low', 'dip-v3': 'dip', 'roll': 'roll'}[tag]))
    with (folder / 'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    labels = ['Literal dae.asw', 'Wing only', 'Elevator only', 'Rudder only', 'Wing + tail',
              'All: extra body weight on boom', 'All: extra body weight on fairing', 'All: extra body weight on both']
    colors = ['#ff4a3d', '#ff9f1a', '#ffd166', '#6dd36f', '#2f7bff', '#9b5de5', '#f472b6', '#22d3ee']
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout='constrained')
    for j, (ax, ch) in enumerate(zip(axes.flat, CHANNELS)):
        selected = [r for r in rows if r['frequency_hz'] == DIP and r['channel'] == ch]
        ax.barh(np.arange(8), [r['magnitude'] for r in selected], color=colors)
        ax.axvline(selected[0]['reference_magnitude'], color='#333333', ls='--', label='Drela published magnitude')
        ax.set_yticks(np.arange(8), labels, fontsize=8); ax.invert_yaxis()
        ax.set_title(ch.replace('_', ' ').title()); ax.set_xlabel(('deg/s' if j < 2 else 'deg') + ' per F3 unit')
        ax.grid(axis='x', alpha=.25); ax.set_axisbelow(True)
        if j == 0: ax.legend(fontsize=8)
    fig.suptitle('Measured-weight sensitivity at 1.15738 cycles/s\nFull 2044-state solves; original mean shape held by constant residual offsets, not retrimmed')
    fig.savefig(folder / 'comparison.png', dpi=150); fig.savefig(folder / 'comparison.svg'); plt.close(fig)
    return dict(frequencies=summaries, rows=rows, complete_descriptor_solves=24,
        qualification='Three sampled frequencies, not a sweep or a native-reference pass count. Uniform beam distributions and three body-weight placements do not exhaust location uncertainty. New physical trims remain required.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['assemble', 'response', 'balance', 'cases', 'report'])
    p.add_argument('--tag', required=True); p.add_argument('--beam', type=int, choices=range(1, 6))
    p.add_argument('--frequency', type=float, default=DIP); p.add_argument('--source')
    p.add_argument('--configuration', default='all_shared'); args = vars(p.parse_args())
    inputs = [ROOT / 'scripts' / name for name in ('check_daedalus_mesh_zeros.py', 'check_daedalus_mesh_residual.py',
        'check_daedalus_structural_resolution.py', 'check_daedalus_source_operator.py')]
    inputs += list((ROOT / 'openswing').glob('*.py'))
    inputs += [ROOT / name for name in ('examples/dae.asw', 'examples/dae-cruise-physical-mesh-project.json',
        'docs/validation/ISAE_STATUS.md', 'docs/validation/aswing-authoritative-sources.json',
        'docs/validation/daedalus-weight-sources-20261114.json',
        'reference/daedalus-weight-20261114/cruz-daedalus-weight.pdf',
        'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf')]
    matrix, layout, seed = paths('coarse'); inputs += [layout, seed]
    folders = [matrix, PROPERTIES / 'measured']
    if args['stage'] != 'assemble': folders += [STUDY / f'beam-{i}' for i in range(1, 6)]
    if args['source']: folders.append(STUDY / args['source'])
    if args['stage'] == 'report':
        inputs += [ROOT / 'docs/validation/daedalus-rudder-four-outputs.csv']
        folders += [STUDY / tag for tag in ('low', 'dip-v3', 'roll', 'balance-low', 'balance-dip', 'balance-roll')]
    for folder in folders: inputs += [path for path in folder.iterdir() if path.suffix in ('.json', '.npz')]
    run(STUDY, args['tag'], inputs, globals()[args['stage']], args, __file__)


if __name__ == '__main__': main()
