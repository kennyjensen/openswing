"""Decompose retained native AVL root rays; no equilibrium solves or core changes.

The signed sum of collinear root rays is rewritten as finite streamwise
segments plus one residual downstream ray. This is an identity for the saved
field, not an added vortex or an alternative accepted solution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/sa11-native-chord-refinement-20261108'
READ = lambda p: json.loads(p.read_text())
SHA = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
SPEED = 240.
PG = np.diag([1/np.sqrt(1-(SPEED/340.21)**2), 1., 1.])
PI4INV = .079577472  # Native AVL's retained, rounded constant.


def rays(point, origins):
    r = point-origins
    radius2 = np.sum(r[:, 1:]**2, axis=1)
    assert np.all(radius2 > 0)
    return np.cross([1., 0., 0.], r)*((1+r[:, 0]/np.linalg.norm(r, axis=1))/radius2)[:, None]*PI4INV


def finite(point, a, b):
    r1, r2 = point-a, point-b
    cross = np.cross(r1, r2)
    cross2 = np.sum(cross**2, axis=1)
    d1, d2 = np.linalg.norm(r1, axis=1), np.linalg.norm(r2, axis=1)
    dot = np.sum(r1*r2, axis=1)
    scalar = np.empty(len(a))
    # The usual cross-squared expression is ill-conditioned on the extension
    # of a straight vortex. Use its equivalent endpoint-length expression
    # there, including the exact zero field of a collinear exterior receiver.
    exterior = dot >= 0
    scalar[exterior] = ((d1+d2)/(d1*d2*(d1*d2+dot)))[exterior]
    interior = ~exterior
    assert np.all(cross2[interior] > 0)
    factor = np.sum((b-a)*(r1/d1[:, None]-r2/d2[:, None]), axis=1)
    scalar[interior] = factor[interior]/cross2[interior]
    return cross*scalar[:, None]*PI4INV


def root_sections(path):
    """Read literal AVL section data at the positive wing/winglet junction."""
    lines = path.read_text().splitlines()
    sections = []
    for i, line in enumerate(lines):
        if line == 'SECTION':
            row = [float(x) for x in lines[i+1].split()]
            if abs(row[1]-1.2426) < 1e-12:
                sections.append(dict(leading_edge=row[:3], streamwise_chord=row[3], incidence_degrees=row[4],
                                     trailing_edge_x=row[0]+row[3]))
    assert len(sections) == 2
    assert np.max(abs(np.array(sections[0]['leading_edge'][1:])-sections[1]['leading_edge'][1:])) < 1e-14
    return sections


def analyze(directory):
    report = READ(directory/'report.json')
    for name, expected in report['artifact_sha256'].items():
        assert SHA(directory/name) == expected, (directory, name)
    with np.load(directory/'native-fields.npz') as data:
        f = {key: data[key].copy() for key in data.files}
    with np.load(directory/'derived-fields.npz') as data:
        beam = data['beam_indices'].copy()
    case = report['case']; nc = case['chord_rows']
    main = np.flatnonzero((beam == 1) & (abs(f['RV2'][:, 1]-1.2426) < 1e-12))
    upper = np.flatnonzero((beam == 2) & (abs(f['RV1'][:, 1]-1.2426) < 1e-12))
    assert len(main) == len(upper) == nc
    gamma = f['GAM'].ravel()*SPEED
    origins = np.concatenate([f['RV2'][main], f['RV1'][upper]])
    strengths = np.concatenate([gamma[main], -gamma[upper]])
    order = np.argsort(origins[:, 0]); origins = origins[order]; strengths = strengths[order]
    assert np.max(abs(origins[:, 1:]-origins[0, 1:])) < 1e-14
    assert np.all(np.diff(origins[:, 0]) > 0)
    cumulative = np.cumsum(strengths)
    i = report['native_force_points']['worst_index']
    assert beam[i] == 2
    p = f['RV'][i]@PG
    a, b = f['RV1']@PG, f['RV2']@PG
    mask = np.arange(len(gamma)) != i
    bound = np.sum(finite(p, a[mask], b[mask])*gamma[mask, None], axis=0)@PG
    total_wake = np.sum((rays(p, b)-rays(p, a))*gamma[:, None], axis=0)@PG
    root = np.sum(rays(p, origins@PG)*strengths[:, None], axis=0)@PG
    segment_velocities = finite(p, origins[:-1]@PG, origins[1:]@PG)*cumulative[:-1, None]@PG
    finite_sum = segment_velocities.sum(axis=0)
    tail = (rays(p, origins[-1:]@PG)*cumulative[-1])@PG
    tail = tail[0]
    identity_error = float(np.max(abs(root-finite_sum-tail)))
    assert identity_error < 1e-7
    native_error = float(np.max(abs(bound+total_wake-SPEED*f['VV'][i])))
    assert native_error < 1e-3, (case['id'], native_error, bound.tolist(), total_wake.tolist())  # Zero core versus native's tiny numerical core.
    other_wake = total_wake-root
    distances = abs(f['RV2'][main, None, 0]-f['RV1'][None, upper, 0])
    rows = []
    for j, v in enumerate(segment_velocities):
        rows.append(dict(start_x_m=float(origins[j, 0]), end_x_m=float(origins[j+1, 0]),
                         cumulative_circulation_m2_s=float(cumulative[j]), velocity_m_s=v.tolist()))
    root_gap = float(np.linalg.norm(f['RV'][i, 1:]-origins[0, 1:]))
    nearest = float(np.min(distances))
    return dict(case=case, root_sections=root_sections(directory/'model.avl'),
        main_root_indices=main.tolist(), upper_root_indices=upper.tolist(),
        main_origins_m=f['RV2'][main].tolist(), upper_origins_m=f['RV1'][upper].tolist(),
        main_circulations_m2_s=gamma[main].tolist(), upper_circulations_m2_s=gamma[upper].tolist(),
        paired_root_origins_within_1e_10_m=int(np.sum(np.min(distances, axis=1) < 1e-10)),
        minimum_root_x_mismatch_m=nearest, closest_origin_gap_over_receiver_radius=nearest/root_gap,
        main_total_circulation_m2_s=float(gamma[main].sum()), upper_total_circulation_m2_s=float(gamma[upper].sum()),
        total_circulation_jump_percent=float(100*(gamma[main].sum()-gamma[upper].sum())/gamma[main].sum()),
        receiver_index=i, receiver_m=f['RV'][i].tolist(), receiver_radius_m=root_gap,
        maximum_normal_mach=report['native_force_points']['maximum_normal_mach'],
        sorted_origins_m=origins.tolist(), signed_strengths_m2_s=strengths.tolist(),
        cumulative_strengths_m2_s=cumulative.tolist(), segments=rows,
        velocities_m_s=dict(bound=bound.tolist(), root=root.tolist(), finite_segments=finite_sum.tolist(),
                            residual_ray=tail.tolist(), other_wake=other_wake.tolist(), total_wake=total_wake.tolist()),
        velocity_norms_m_s={k:float(np.linalg.norm(v)) for k, v in dict(bound=bound, root=root,
            finite_segments=finite_sum, residual_ray=tail, other_wake=other_wake, total_wake=total_wake).items()},
        root_reexpression_error_m_s=identity_error, native_field_error_m_s=native_error)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); out = args.output.resolve()
    assert not out.exists(), out
    plan = READ(BASE/'plan.json')
    # A prior prose-only status update is the only change allowed in the old pins.
    for path, expected in plan['pins'].items():
        if path not in ('ISAE_STATUS.md', 'docs/validation/ISAE_STATUS.md'):
            assert SHA(ROOT/path) == expected, path
    pins = {p: SHA(ROOT/p) for p in plan['pins'] if p != 'ISAE_STATUS.md'}
    pins['docs/validation/ISAE_STATUS.md'] = SHA(ROOT/'docs/validation/ISAE_STATUS.md')
    for path in [Path(__file__), BASE/'plan.json', ROOT/'docs/validation/isae-progress-scopes.json']:
        pins[str(path.relative_to(ROOT))] = SHA(path)
    table_rows = [line for line in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if re.match(r'^\| \[[A-Z]+-\d+\]', line)]
    assert len(table_rows) == 42
    rows = []
    for case in plan['cases']:
        directory = BASE/case['id']
        assert READ(directory/'process.json')['returncode'] == 0
        rows.append(analyze(directory))
        for name in ('report.json', 'native-fields.npz', 'derived-fields.npz', 'model.avl'):
            pins[str((directory/name).relative_to(ROOT))] = SHA(directory/name)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=rows,
        source_pins=pins, unchanged_status_rows=table_rows, new_solver_calls=0,
        production_changed=False, comparison_fraction_or_scope_changed=False,
        maximum_root_identity_error_m_s=max(r['root_reexpression_error_m_s'] for r in rows),
        maximum_native_field_error_m_s=max(r['native_field_error_m_s'] for r in rows),
        caveat='Root rays are decomposed at saved native circulation. Finite-segment and residual-ray terms are an algebraic identity; no part is removed. No counterfactual velocity is accepted as a solution. Native force points are not generally ASWING quarter-chord receivers. Conforming origins alone would not force chordwise strengths to match.')
    out.mkdir(parents=True)
    (out/'analysis.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    (out/'analyzer-used.py').write_text(Path(__file__).read_text())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = re.findall(r"'(#\w+)'", (ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig, axes = plt.subplots(3, 1, figsize=(9.5, 9), sharex=True)
    for ax, nc in zip(axes, (2, 4, 8)):
        selected = [r for r in rows if r['case']['chord_rows'] == nc]
        for color, r in zip(colors, selected):
            x = np.array(r['sorted_origins_m'])[:, 0]
            y = np.array(r['cumulative_strengths_m2_s'])
            # The terminal constant is the residual ray beyond the last origin.
            ax.step(np.r_[x, 1.16], np.r_[y, y[-1]], where='post', color=color,
                label=f"{r['case']['span_strips']} span strips; root distance {1000*r['receiver_radius_m']:.3f} mm")
            ax.axvline(r['receiver_m'][0], color=color, linestyle=':', linewidth=1.1)
        ax.axhline(0, color='#555555', linewidth=.7)
        sec = selected[0]['root_sections']
        lo = max(s['leading_edge'][0] for s in sec)
        hi = min(s['trailing_edge_x'] for s in sec)
        ax.axvspan(lo, hi, color='#888888', alpha=.09)
        ax.set_title(f'{nc} chordwise rows: signed cumulative root circulation', fontsize=11)
        ax.set_ylabel('Circulation (m²/s)'); ax.grid(alpha=.25); ax.legend(fontsize=8, loc='upper right')
        for label, key, ylevel in [('Main', 'main_origins_m', -.12), ('Winglet', 'upper_origins_m', -.19)]:
            origins = np.array(selected[0][key])[:, 0]
            ax.plot(origins, np.full(len(origins), ylevel), '|', color='#333333', transform=ax.get_xaxis_transform(), clip_on=False)
            ax.text(.98, ylevel, label, transform=ax.transAxes, ha='right', va='center', fontsize=8)
    axes[-1].set_xlabel('Body x at the shared wing/winglet root (m)', labelpad=37)
    fig.suptitle('Native AVL SA-11: chordwise root origins do not coincide', fontsize=13)
    fig.text(.5, .015, 'Dotted lines: worst force-point x. Gray: overlapping root chords. Saved fields only; no new validation passes.',
             ha='center', fontsize=9)
    fig.subplots_adjust(top=.92, bottom=.12, hspace=.57)
    fig.savefig(out/'root-circulation.png', dpi=160)
    fig.savefig(out/'root-circulation.svg'); plt.close(fig)
    print(json.dumps(dict(cases=len(rows), new_solver_calls=0,
        maximum_identity_error=result['maximum_root_identity_error_m_s'],
        maximum_native_error=result['maximum_native_field_error_m_s'],
        rows=[{k:r[k] for k in ('case','receiver_radius_m','minimum_root_x_mismatch_m',
             'total_circulation_jump_percent','velocity_norms_m_s')} for r in rows])))


if __name__ == '__main__':
    main()
