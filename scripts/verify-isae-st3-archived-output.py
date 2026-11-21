#!/usr/bin/env python3
"""Replay every column of the original ST-3 [m15_0] static ASWING table.

Prepare first, then run the pinned plan. Original signed weights are unchanged.
Numerical consistency gates are separate from agreement at printed precision.
This script does not require experimental data or an ASWING executable.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGET = ROOT / 'docs/validation/isae-st3-reference-target.json'
COLUMNS = ['y_m', 'z_m', 'twist_deg', 'Mc_prime_Nm', 'Ms_prime_Nm', 'Fn_N', 'cl', 'a_flap']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def pins():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}


def prepare(stage):
    target = json.loads(TARGET.read_text())
    source = ROOT/'examples/isae-st3-static-m15_0.asw'
    assert sha(source) == target['files'][0]['sha256']
    # Keep all printed centers; separately insert the known doubled flap break.
    nodes = sorted({r['physical_values'][0] for r in target['rows']} | {.6*.558})
    meshes = []
    for level in range(3):
        meshes.append(dict(level=level, intervals=len(nodes)-1,
            panels={'default': len(nodes)-1, 'beams': {'1': {'nodes': nodes}}}))
        nodes = sorted(nodes + [(a+b)/2 for a, b in zip(nodes[:-1], nodes[1:])])
    assert [m['intervals'] for m in meshes] == [44, 88, 176]
    plan = dict(status='PREDECLARED_NOT_YET_RUN', acceptance='Archived ASWING outputs, not experiment',
        source=str(source.relative_to(ROOT)), source_sha256=sha(source), target_sha256=sha(TARGET),
        script_sha256=sha(__file__), helper_sha256=sha(ROOT/'scripts/isae_st3_static_reference.py'),
        kernel_pins=pins(), meshes=meshes,
        request=dict(action='solve', mode='structural'), cold_solves=3,
        fresh_residual_evaluations=3, numerical_gates=dict(residual=1e-8, balance_N_or_Nm=1e-7,
            pure_couple_identity_N_or_Nm=1e-7, root_pose=1e-10, fine_field_envelope_relative=1e-3),
        reference_rule='Each output inside its printed half-last-place interval, with no fitted property or widened tolerance.',
        coordinate_rule='Root, tip and both flap-break rows use exact model t; other rows use printed t centers. Interior coordinate rounding remains unresolved.',
        zero_channels=dict(Fn_N='Computed nodal force trace', cl='ASWING zero-airflow reporting convention; not an aerodynamic prediction',
            a_flap='Zero prescribed flap; final cl/a_flap entries are table dummy zeros'),
        limitations=['Producing ASWING NODE and automatic .set/.pnt startup are unknown.',
            'The supplied grid is a nested convergence grid, not a reconstruction of the historical ASWING mesh.',
            'A printed-center mismatch alone cannot rule out agreement at the unknown unrounded coordinate.',
            'No dynamic, aerodynamic, or experimental validation follows from this static case.'])
    write(stage/'plan.json', plan)
    print(json.dumps({'prepared': str(stage/'plan.json'), 'intervals': [m['intervals'] for m in meshes]}), flush=True)


def run(stage):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.equilibrium_state import restore
    from openswing.network import StaticNetwork
    from isae_st3_static_reference import observables

    plan = json.loads((stage/'plan.json').read_text())
    assert sha(__file__) == plan['script_sha256'] and pins() == plan['kernel_pins']
    assert sha(ROOT/'scripts/isae_st3_static_reference.py') == plan['helper_sha256']
    assert sha(TARGET) == plan['target_sha256']
    source = (ROOT/plan['source']).read_text()
    assert sha(ROOT/plan['source']) == plan['source_sha256']
    target = json.loads(TARGET.read_text())
    expected = np.array([r['physical_values'][1:] for r in target['rows']])
    half = np.array([r['printed_half_ulp_physical'][1:] for r in target['rows']])
    records = []
    all_checks = []
    write(stage/'owner.json', dict(pid=os.getpid(), state='RUNNING', stage=str(stage)))
    for mesh in plan['meshes']:
        count = mesh['intervals']
        out = stage/f'n{count}'
        out.mkdir(exist_ok=False)
        events = []
        started = time.monotonic()
        print(f'BEGIN cold original-model structural solve: {count} intervals', flush=True)
        request = dict(**plan['request'], source=source, panels=mesh['panels'])
        result = dispatch(request, progress=lambda *event: events.append([time.monotonic()-started, *event]))
        seconds = time.monotonic()-started
        write(out/'result.json', result)
        write(out/'progress.json', events)
        # New model/network, restored physical fields, one fresh residual; no corrector solve.
        model = parse_asw(source)
        network = StaticNetwork(model, mesh['panels'], None, None, [],
            allow_signed_point_weights=True, allow_signed_distributed_weights=True)
        x = restore(network, result['equilibrium_state'])
        residual, data = network.residual(x, detail=True)
        write(out/'fresh-residual.json', residual.tolist())
        pa, pb = network.geometry(data['r'], data['Q'])[:2]
        ts, ids = network.station_nodes[1]
        assert network.ne == count and len(ids) == count+1
        # Literal jig frame is the identity and all sectional offsets are zero.
        # Save both endpoint traces; do not use midpoint moment_local as a node value.
        fields = []
        for t, i in zip(ts, ids):
            traces = {}
            for side, endpoint_ids, end, sign in [('left', network.b, 1, -1), ('right', network.a, 0, 1)]:
                js = np.flatnonzero(endpoint_ids == i)
                if not len(js):
                    continue
                assert len(js) == 1
                j = int(js[0])
                offset = (pb[j] if end else pa[j])-data['r'][i]
                force = data['N'][j]+sign*data['element_forces'][j, end]
                moment = data['M'][j]+sign*np.cross(pb[j]-pa[j], data['N'][j])/2
                moment += np.cross(offset, data['N'][j])+sign*data['element_moments'][j, end]
                q = data['Q'][i]
                local_n, local_m = q.T@force, q.T@moment
                traces[side] = dict(element=j, force_body=force.tolist(), moment_body=moment.tolist(),
                    force_local=local_n.tolist(), moment_local=local_m.tolist())
            fields.append(dict(t=float(t), index=int(i), position=data['r'][i].tolist(),
                jig_position=network.rj[i].tolist(), rotation=data['Q'][i].tolist(), traces=traces,
                twist_deg=observables(data['r'][i], data['Q'][i])['twist_asw_deg']))
        rows = []
        predictions = []
        break_rows = [i for i, r in enumerate(target['rows']) if r['physical_values'][0] == .335]
        assert len(break_rows) == 2
        for row_id, ref in enumerate(target['rows']):
            t = .6*.558 if row_id in break_rows else ref['physical_values'][0]
            k = int(np.argmin(abs(ts-t)))
            assert abs(ts[k]-t) < 1e-14
            field = fields[k]
            side = 'right' if row_id == break_rows[1] or k == 0 else 'left'
            trace = field['traces'][side]
            values = [field['position'][1], field['position'][2]-field['jig_position'][2], field['twist_deg'],
                trace['moment_local'][0], trace['moment_local'][1], trace['force_local'][2], 0., 0.]
            predictions.append(values)
            diff = np.asarray(values)-expected[row_id]
            rows.append(dict(source_line=ref['source_line'], t_printed=ref['physical_values'][0],
                t_evaluated=float(t), trace=side, native_node_index=k, values=values,
                expected=expected[row_id].tolist(), half_last_place=half[row_id].tolist(),
                difference=diff.tolist(), within_printed_interval=(abs(diff) <= half[row_id]).tolist()))
        predictions = np.array(predictions)
        chord = data['Q'][ids[-1]][:, 0]
        pair = .14*.5451*9.81*np.array([-chord[1], chord[0], 0.])
        checks = dict(fresh_residual=float(np.max(abs(residual))), stored_residual=result['residual'],
            force_balance=float(np.max(abs(np.array(result['force_balance'])))),
            moment_balance=float(np.max(abs(np.array(result['moment_balance'])))),
            zero_internal_force=float(np.max(abs(data['N']))),
            constant_body_moment=float(np.max(abs(data['M']-pair))),
            applied_pair_moment=float(np.max(abs(np.array(result['applied_moment'])-pair))),
            support_pair_moment=float(np.max(abs(np.array(result['support_moment'])+pair))),
            zero_distributed_element_force=float(np.max(abs(data['element_forces']))),
            zero_distributed_element_moment=float(np.max(abs(data['element_moments']))),
            root_position=float(np.max(abs(data['r'][ids[0]]))),
            root_rotation=float(np.max(abs(data['Q'][ids[0]]-np.eye(3)))))
        passed = checks['fresh_residual'] <= 1e-8 and checks['stored_residual'] <= 1e-8
        passed &= all(v <= 1e-7 for k, v in checks.items() if k not in ('fresh_residual', 'stored_residual', 'root_position', 'root_rotation'))
        passed &= checks['root_position'] <= 1e-10 and checks['root_rotation'] <= 1e-10
        assert result['structural_only'] and result['strips'] == []
        assert result['mass_properties']['physical'] is False and 'launch' not in result['equilibrium_state']
        assert len(result['equilibrium_state']['circulation']) == 0
        metrics = {name: dict(max_abs_difference=float(np.max(abs(predictions[:, j]-expected[:, j]))),
            rmse=float(np.sqrt(np.mean((predictions[:, j]-expected[:, j])**2))),
            printed_interval_matches=int(np.sum(abs(predictions[:, j]-expected[:, j]) <= half[:, j])))
            for j, name in enumerate(COLUMNS)}
        packet = dict(intervals=count, seconds=seconds, checks=checks, numerical_gates_pass=bool(passed),
            pure_pair_moment=pair.tolist(), metrics=metrics, rows=rows, fields=fields,
            full_rows_inside_printed_intervals=int(np.sum(np.all(abs(predictions-expected) <= half, axis=1))))
        write(out/'comparison.json', packet)
        records.append(packet)
        all_checks.append(bool(passed))
        print(json.dumps(dict(done=count, seconds=seconds, checks_pass=bool(passed),
            residual=checks['fresh_residual'], matches={k: v['printed_interval_matches'] for k, v in metrics.items()})), flush=True)
    mesh_checks = []
    for coarse, fine in zip(records[:-1], records[1:]):
        a, b = np.array([r['values'] for r in coarse['rows']]), np.array([r['values'] for r in fine['rows']])
        jig = np.array([fine['fields'][r['native_node_index']]['jig_position'][1] for r in fine['rows']])
        measures = {}
        for j, name in enumerate(COLUMNS[:5]):
            envelope = np.max(abs(b[:, j]-jig if j == 0 else b[:, j]))
            change = np.max(abs(a[:, j]-b[:, j]))
            assert envelope > 0
            measures[name] = dict(max_absolute_change=float(change), fine_field_envelope=float(envelope),
                relative_change=float(change/envelope), pass_0_1_percent=bool(change/envelope <= 1e-3))
        mesh_checks.append(dict(coarse=coarse['intervals'], fine=fine['intervals'], measures=measures))
    summary = dict(status='COMPARISON_COMPLETE_REFERENCE_DIFFERENCES_REMAIN',
        goal_complete=False, acceptance=plan['acceptance'], source_sha256=plan['source_sha256'],
        plan_sha256=sha(stage/'plan.json'), target_sha256=sha(TARGET), kernel_pins=plan['kernel_pins'],
        columns=COLUMNS, rows=45, computed_structural_outputs=270, conditional_zero_entries=90,
        cold_solves=3, fresh_residual_evaluations=3, all_numerical_gates_pass=all(all_checks),
        all_fine_mesh_gates_pass=all(r['pass_0_1_percent'] for r in mesh_checks[-1]['measures'].values()),
        meshes=[{k: v for k, v in r.items() if k not in ('rows', 'fields')} for r in records],
        mesh_changes=mesh_checks, limitations=plan['limitations'], zero_channels=plan['zero_channels'])
    write(stage/'summary.json', summary)
    assert pins() == plan['kernel_pins']
    write(stage/'owner.json', dict(pid=os.getpid(), state='FINISHED', stage=str(stage)))
    print(json.dumps({k: summary[k] for k in ['status', 'all_numerical_gates_pass', 'all_fine_mesh_gates_pass']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    args.stage.mkdir(parents=True, exist_ok=True)
    (prepare if args.action == 'prepare' else run)(args.stage)
