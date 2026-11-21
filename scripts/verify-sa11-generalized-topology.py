"""Audit portability of connected-line grouping on saved SA-11 geometries.

No production imports or equilibrium solves. Execute pinned MachUpX grouping
methods on explicit metadata fixtures; retain exact physical endpoints. Also
decompose the original root-ray field with signed three-branch circulation.
"""
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from types import MethodType

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / 'artifacts/isae/sa11-winglet-junction-20261107'
SOURCE = ROOT / 'third_party/machupx'
HELPER = ROOT / 'scripts/verify-winglet-generalized-fields.py'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def serial(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def write(p, value):
    p.write_text(json.dumps(serial(value), indent=2, allow_nan=False) + '\n')


def fixture(data, policy, helper, coincident=False):
    segments = []
    for name, beam, side in (
        ('main_left', 1, 'left'), ('main_right', 1, 'right'),
        ('upper_left', 3, 'left'), ('upper_right', 2, 'right'),
        ('lower_left', 5, 'left'), ('lower_right', 4, 'right'),
    ):
        mask = data['beam'] == beam
        if beam == 1:
            mask &= data['t'] < 0 if side == 'left' else data['t'] > 0
        indices = np.flatnonzero(mask)
        if len(indices) == 0:
            continue
        a, b = data['a'][indices], data['b'][indices]
        np.testing.assert_allclose(a[1:], b[:-1], atol=2e-14, rtol=0.)
        nodes = np.vstack([a[0], b])
        is_main = beam == 1
        mirror = is_main or policy != 'explicit-sides'
        s = helper.SegmentFixture()
        if is_main:
            offset = np.zeros(3)
        else:
            main = next(s for s in segments if s.name == 'main_' + side)
            root = nodes[-1 if side == 'left' else 0]
            offset = root - main.get_tip_loc()
        original_offset = offset.copy()
        if coincident and not is_main:
            nodes = nodes - offset
            offset = np.zeros(3)
        if policy == 'joint-alias':
            offset = np.zeros(3)  # Deliberately test a structural-Joint-only mapping.
        ident = 1 if is_main else (beam if not mirror else (2 if 'upper' in name else 4))
        s.__dict__.update(name=name, side=side, ID=ident, N=len(indices), nodes=nodes,
            has_mirror=mirror, parent_has_mirror=True, y_offset=0., wing_ID=-1,
            _connected_to_ID=0 if is_main else 1, _connected_to_loc='tip',
            _delta_origin=offset, original_offset=original_offset, beam=beam,
            physical_indices=indices)
        s.get_tip_loc = MethodType(lambda self: self.nodes[0 if self.side == 'left' else -1], s)
        segments.append(s)
    h = helper.GeometryHarness()
    h.wing_segments = {s.name: s for s in segments}
    h._sort_segments_into_wings()
    assert sorted(s.name for s in h.segments) == sorted(s.name for s in segments)
    return h


def graph(h):
    # Tolerance only identifies endpoints for analysis; it never moves nodes.
    endpoints = []; degree = []; edges = []
    for s in h.wing_segments.values():
        ids = []
        for p in (s.nodes[0], s.nodes[-1]):
            candidates = [i for i, q in enumerate(endpoints) if np.linalg.norm(p-q) <= 1e-12]
            assert len(candidates) <= 1
            if not candidates:
                candidates = [len(endpoints)]; endpoints.append(p.copy()); degree.append(0)
            i = candidates[0]; degree[i] += 1; ids.append(i)
        edges.append(ids)
    adjacency = [set() for _ in endpoints]
    for i, j in edges:
        adjacency[i].add(j); adjacency[j].add(i)
    seen = set(); components = 0
    for i in range(len(endpoints)):
        if i in seen:
            continue
        components += 1; queue = [i]
        while queue:
            j = queue.pop()
            if j in seen:
                continue
            seen.add(j); queue.extend(adjacency[j] - seen)
    gaps = []
    for group in h._segments_in_wings:
        for first, second in zip(group[:-1], group[1:]):
            delta = second.nodes[0] - first.nodes[-1]
            if np.linalg.norm(delta) > 1e-12:
                gaps.append(dict(first=first.name, second=second.name,
                    first_endpoint=first.nodes[-1], second_endpoint=second.nodes[0],
                    vector=delta, distance=float(np.linalg.norm(delta))))
    return dict(physical_components=components, maximum_endpoint_degree=max(degree),
        endpoints=endpoints, endpoint_degrees=degree,
        groups=[[s.name for s in group] for group in h._segments_in_wings],
        source_group_count=h._num_wings, consecutive_noncoincident_entries=gaps,
        maximum_consecutive_gap=max((g['distance'] for g in gaps), default=0.),
        continuation_flags={s.name: bool(s.is_continuation()) for s in h.wing_segments.values()},
        input_offsets={s.name: s._delta_origin for s in h.wing_segments.values()},
        actual_root_offsets={s.name: s.original_offset for s in h.wing_segments.values() if s.beam != 1})


def ray(points, origins, pg):
    r = (points[:, None, :] - origins[None, :, :]) @ pg.T
    norm = np.linalg.norm(r, axis=-1)
    h2 = r[:, :, 1]**2 + r[:, :, 2]**2
    assert np.min(h2) > 0
    f = (1 + r[:, :, 0]/norm)/h2
    upstream = r[:, :, 0] < 0
    f[upstream] = 1/(norm[upstream]*(norm[upstream]-r[:, :, 0][upstream]))
    return np.cross([1., 0., 0.], r)*f[:, :, None]/(4*np.pi) @ pg


def root_fields(data, saved):
    point = np.asarray(saved['details']['vortex_breakdown']['influence_receiver'])[None, :]
    mach = saved['condition']['speed']/340.21
    pg = np.diag([1/np.sqrt(1-mach*mach), 1., 1.])
    a, b, gamma = data['a'], data['b'], data['gamma']
    original = np.einsum('ijk,j->ik', ray(point, b, pg)-ray(point, a, pg), gamma)[0]
    expected = np.asarray(saved['details']['vortex_breakdown']['wake_velocity'])
    np.testing.assert_allclose(original, expected, atol=2e-7, rtol=2e-12)
    records = []
    for sign in (1, -1):
        ids = {beam: np.flatnonzero(data['beam'] == beam) for beam in np.unique(data['beam'])}
        mi = ids[1][-1 if sign > 0 else 0]
        ui = ids[2 if sign > 0 else 3][0 if sign > 0 else -1]
        lower = 4 if sign > 0 else 5
        li = ids[lower][0 if sign > 0 else -1] if lower in ids else None
        main = b[mi] if sign > 0 else a[mi]
        upper = a[ui] if sign > 0 else b[ui]
        low = (a[li] if sign > 0 else b[li]) if li is not None else main.copy()
        gm, gu, gl = gamma[mi], gamma[ui], gamma[li] if li is not None else 0.
        np.testing.assert_array_equal(main[1:], upper[1:])
        flat = low.copy(); flat[1:] = main[1:]
        vm, vu, vl, vf = ray(point, np.array([main, upper, low, flat]), pg)[0]
        total = sign*(gm*vm-gu*vu-gl*vl)
        jump = sign*(gm-gu-gl)*vu
        main_connector = sign*gm*(vm-vu)
        lower_connector = -sign*gl*(vf-vu)
        height = -sign*gl*(vl-vf)
        np.testing.assert_allclose(total, jump+main_connector+lower_connector+height, atol=2e-8, rtol=3e-12)
        # Independent analytic finite-segment expression for the collinear parts.
        def finite(first, last):
            r0, r1 = pg@(point[0]-first), pg@(point[0]-last)
            h = r0.copy(); h[0] = 0
            return (np.cross([1., 0., 0.], h)/(4*np.pi*(h@h)) *
                (r0[0]/np.linalg.norm(r0)-r1[0]/np.linalg.norm(r1))) @ pg
        fm = sign*gm*finite(main, upper)
        fl = -sign*gl*finite(flat, upper)
        np.testing.assert_allclose(fm, main_connector, atol=2e-8, rtol=3e-12)
        np.testing.assert_allclose(fl, lower_connector, atol=2e-8, rtol=3e-12)
        terms = dict(main_connector=main_connector, lower_connector=lower_connector,
            lower_height_difference=height, signed_circulation_jump=jump,
            geometry_remainder=main_connector+lower_connector+height, total=total)
        records.append(dict(side='right' if sign > 0 else 'left', main_gamma=gm,
            upper_gamma=gu, lower_gamma=gl, signed_gamma_balance=gm-gu-gl,
            relative_gamma_balance=(gm-gu-gl)/gm, receiver=point[0],
            receiver_is_this_side=bool(sign*point[0, 1] > 0), root_positions=[main, upper, low],
            vectors=terms, speeds={k:np.linalg.norm(v) for k,v in terms.items()},
            finite_identity_maximum_error=max(np.max(abs(fm-main_connector)),np.max(abs(fl-lower_connector)))))
    return dict(full_wake_reconstruction_error=float(np.max(abs(original-expected))), roots=records)


def plot(rows, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True)
    for ax, n in zip(axes, (48, 96)):
        row = next(r for r in rows if r['panels']==n and r['example'].endswith('up-and-down'))
        r = next(r for r in row['root_field']['roots'] if r['receiver_is_this_side'])
        labels = ['Main connector', 'Lower connector', '70 μm height offset', 'Circulation imbalance', 'Total root field']
        keys = ['main_connector', 'lower_connector', 'lower_height_difference', 'signed_circulation_jump', 'total']
        ax.barh(labels, [r['speeds'][k] for k in keys], color=['#0072B2','#E69F00','#009E73','#CC79A7','#555555'])
        ax.set_xscale('log'); ax.set_xlabel('Velocity contribution magnitude [m/s]')
        ax.set_title(f'Upper/lower winglets, N{n}\nSigned Γ balance {100*r["relative_gamma_balance"]:.3f}%')
        ax.grid(axis='x', alpha=.2); ax.invert_yaxis()
    fig.suptitle('Saved rejected SA-11 states: exact root-ray decomposition\nMagnitudes do not add; terms are vectors. No new equilibrium or geometry change.')
    for ext in ('png', 'svg'):
        fig.savefig(path/f'root-field-decomposition.{ext}', dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory; previous observations are retained.')
    manifest = json.loads((SOURCE/'SOURCE.json').read_text())
    assert all(sha(SOURCE/f['path']) == f['sha256'] for f in manifest['files'])
    previous = json.loads((SAVED/'analysis.json').read_text())
    assert sha(SAVED/'results.json') == previous['results_sha256']
    assert all(sha(SAVED/p) == pin for p,pin in previous['data_sha256'].items())
    source_plan = json.loads((SAVED/'plan.json').read_text())
    assert source_plan['modules'] == {p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    pins = {str(p.relative_to(ROOT)):sha(p) for p in list((ROOT/'openswing').glob('*.py')) +
        [ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/isae-progress-scopes.json']}
    spec = importlib.util.spec_from_file_location('generalized_helper', HELPER)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    for name in ('_sort_segments_into_wings', '_sort_segments_left_to_right'):
        setattr(helper.GeometryHarness, name, helper.source_method(SOURCE/'machupX/airplane.py', 'Airplane', name))
    helper.SegmentFixture.is_continuation = helper.source_method(SOURCE/'machupX/wing_segment.py', 'WingSegment', 'is_continuation')
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__, args.output/'driver-used.py')
    for name in ('SOURCE.json', 'LICENSE', 'machupX/airplane.py', 'machupX/wing_segment.py'):
        target = args.output/'reference'/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE/name, target)
    plan = dict(utc=datetime.now(timezone.utc).isoformat(), driver_sha256=sha(Path(__file__)),
        helper_sha256=sha(HELPER), unchanged_pins=pins, source_revision=manifest['revision'],
        saved_analysis_sha256=sha(SAVED/'analysis.json'), input_artifacts=previous['data_sha256'],
        policies=['explicit-sides', 'mirrored-sides', 'joint-alias'],
        scope='Four saved states; source grouping only, no geometry correction or circulation solves. '
              'Joint-alias deliberately equates structural attachment with zero quarter-chord offset. '
              'Two coincident controls translate whole winglets; they are not changed SA-11 inputs.',
        numerical_equilibrium_calls=0)
    write(args.output/'plan.json', plan)
    rows = []
    for saved in json.loads((SAVED/'results.json').read_text()):
        if saved['panels'] not in (48,96):
            continue
        assert sha(ROOT/'examples'/(saved['example']+'.asw')) == saved['input_sha256']
        with np.load(SAVED/f"{saved['example']}-{saved['panels']}.npz") as loaded:
            data = {k:loaded[k] for k in loaded.files}
        comparisons = {policy:graph(fixture(data, policy, helper)) for policy in plan['policies']}
        expected_components = 5 if saved['example'].endswith('up-and-down') else 3
        assert all(g['physical_components']==expected_components for g in comparisons.values())
        assert comparisons['explicit-sides']['maximum_consecutive_gap'] <= 1e-12
        assert comparisons['mirrored-sides']['source_group_count'] == (3 if expected_components==5 else 2)
        assert comparisons['joint-alias']['source_group_count'] == 1
        control = graph(fixture(data, 'mirrored-sides', helper, coincident=True)) if saved['panels']==48 else None
        if control:
            assert control['physical_components'] == 1
            assert control['maximum_endpoint_degree'] == (3 if expected_components==5 else 2)
            if expected_components==3:
                assert control['maximum_consecutive_gap'] <= 1e-12
        row = dict(example=saved['example'],panels=saved['panels'],
            grouping=comparisons, translated_coincident_control=control,
            root_field=root_fields(data, saved), status='diagnostic_only')
        rows.append(row); write(args.output/'results.json', rows)
        r = next(r for r in row['root_field']['roots'] if r['receiver_is_this_side'])
        print(saved['example'],saved['panels'],'balance %',100*r['relative_gamma_balance'],
            'geometry speed',r['speeds']['geometry_remainder'],'imbalance speed',r['speeds']['signed_circulation_jump'],flush=True)
    assert len(rows)==4
    plot(rows,args.output)
    assert all(sha(ROOT/p)==pin for p,pin in pins.items())
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    write(args.output/'verification.json',dict(utc=datetime.now(timezone.utc).isoformat(),
        scientific_solves=0,actual_geometry_grouping_audits=12,translated_controls=2,
        signed_root_decompositions=8,production_status_scope_unchanged=True,
        artifacts={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*') if p.is_file()}))
    print('COMPLETE: 12 grouping audits, 2 translated controls, 8 root identities; no new solves.',flush=True)


if __name__ == '__main__':
    main()
