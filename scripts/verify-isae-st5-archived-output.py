#!/usr/bin/env python3
"""Compare the unchanged ST-5 rigid-joint model with its archived ASWING listing.

Prepare freezes the source, decoder, kernel and three nested station grids.
Run performs three cold structural solves and independently restores each result
for a fresh residual and one-sided nodal recovery. No experimental data or fitted
parameters enter this comparison. See the target decoder for export limitations.
"""
import argparse
from dataclasses import fields
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TARGET = ROOT / 'docs/validation/isae-st5-reference-target.json'
SOURCE = ROOT / 'examples/isae-st5-static-20lb_80_20.asw'
STRUCTURAL = list(range(1, 13)) + [19, 20]
CONDITIONAL = list(range(13, 19)) + [22, 24, 26, 27]
INPUT_ECHO = [21, 23]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def pins():
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}


def coordinate(row):
    return row['printed_t'] if row['exact_anchor_t'] is None else row['exact_anchor_t']


def prepare(stage):
    target = json.loads(TARGET.read_text())
    assert sha(SOURCE) == target['source_pins'][0]['sha256']
    nodes = {str(b['beam']): sorted({coordinate(r) for r in b['rows']}) for b in target['beams']}
    meshes = []
    for level in range(3):
        counts = {k: len(v)-1 for k, v in nodes.items()}
        meshes.append(dict(level=level, intervals_by_beam=counts,
            panels={'default': max(counts.values()), 'beams': {k: {'nodes': v} for k, v in nodes.items()}}))
        nodes = {k: sorted(v+[(a+b)/2 for a, b in zip(v[:-1], v[1:])]) for k, v in nodes.items()}
    plan = dict(status='PREDECLARED_NOT_YET_RUN', acceptance=target['acceptance'],
        source=str(SOURCE.relative_to(ROOT)), source_sha256=sha(SOURCE),
        target=str(TARGET.relative_to(ROOT)), target_sha256=sha(TARGET),
        script_sha256=sha(__file__), kernel_pins=pins(), meshes=meshes,
        request=dict(action='solve', mode='structural'), cold_solves=3, fresh_residuals=3,
        numerical_gates=dict(residual=1e-8, force_and_moment_balance=1e-7,
            clamps_and_rigid_joints=1e-10, fine_structural_mesh_relative=1e-3),
        reference_rule='Report each printed half-last-place interval without fitted parameters or a widened tolerance.',
        coordinate_rule='Known literal anchors use exact model t; other samples use original printed centers. Preserve both sides of duplicate rows.',
        field_groups=dict(structural=STRUCTURAL, conditional_zero=CONDITIONAL,
            interval_input_echo=INPUT_ECHO, unresolved_scalar_weight_display=[25]),
        display_rule='chord/cm use the midpoint of successive archived t rows, including zero-width display intervals; final seven display columns are dummy zeros. f_reac scalar signed weight is diagnostic only.',
        mesh_rule='Nested original printed stations with exact anchors. These are not claimed to reconstruct the historical ASWING discretization.',
        limitations=target['uncertainties'])
    write(stage/'plan.json', plan)
    print(json.dumps(dict(prepared=str(stage/'plan.json'), meshes=[m['intervals_by_beam'] for m in meshes])), flush=True)


def euler(frame):
    import numpy as np
    s = frame[:, 1]
    phi, psi = np.arctan2(s[2], s[1]), -np.arcsin(np.clip(s[0], -1., 1.))
    c0 = np.array([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)])
    n0 = np.array([0., -np.sin(phi), np.cos(phi)])
    theta = np.arctan2(-frame[:, 0]@n0, frame[:, 0]@c0)
    return np.rad2deg([phi, theta, psi])


def run(stage):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.equilibrium_state import restore
    from openswing.network import StaticNetwork
    from openswing.recovery import recover_section
    from openswing.structure import Section

    plan = json.loads((stage/'plan.json').read_text())
    assert sha(__file__) == plan['script_sha256'] and pins() == plan['kernel_pins']
    assert sha(TARGET) == plan['target_sha256'] and sha(SOURCE) == plan['source_sha256']
    target, source = json.loads(TARGET.read_text()), SOURCE.read_text()
    names = [c['name'] for c in target['columns']]
    records = []
    for mesh in plan['meshes']:
        out = stage/f"level{mesh['level']}"
        out.mkdir(exist_ok=False)
        started, events = time.monotonic(), []
        print(f"BEGIN cold ST-5 solve {mesh['intervals_by_beam']}", flush=True)
        result = dispatch(dict(**plan['request'], source=source, panels=mesh['panels']),
            progress=lambda *event: events.append([time.monotonic()-started, *event]))
        seconds = time.monotonic()-started
        write(out/'result.json', result)
        write(out/'progress.json', events)
        model = parse_asw(source)
        network = StaticNetwork(model, mesh['panels'], None, None, [],
            allow_signed_point_weights=True, allow_signed_distributed_weights=True)
        state = restore(network, result['equilibrium_state'])
        residual, data = network.residual(state, detail=True)
        pa, pb, ra, rb, *_ = network.geometry(data['r'], data['Q'])
        np.savez_compressed(out/'fresh-fields.npz', residual=residual, r=data['r'], Q=data['Q'],
            N=data['N'], M=data['M'], rj=network.rj, a=network.a, b=network.b,
            pa=pa, pb=pb, ra=ra, rb=rb, R0a=network.R0a, R0b=network.R0b,
            element_forces=data['element_forces'], element_moments=data['element_moments'])
        rows = []
        for block in target['beams']:
            beam = next(b for b in model.beams if b.index == block['beam'])
            ts, ids = network.station_nodes[beam.index]
            assert len(ts)-1 == mesh['intervals_by_beam'][str(beam.index)]
            for k, ref in enumerate(block['rows']):
                t = coordinate(ref)
                at = int(np.argmin(abs(ts-t)))
                assert abs(ts[at]-t) < 1e-13
                node = int(ids[at])
                duplicate_second = k > 0 and coordinate(block['rows'][k-1]) == t
                side = 'right' if at == 0 or duplicate_second else 'left'
                indices = np.flatnonzero((network.a if side == 'right' else network.b) == node)
                assert len(indices) == 1
                element = int(indices[0])
                end, sign = (0, 1) if side == 'right' else (1, -1)
                frame = (ra if end == 0 else rb)[element]
                jig_frame = (network.R0a if end == 0 else network.R0b)[element]
                offset = (pa if end == 0 else pb)[element]-data['r'][node]
                force = data['N'][element]+sign*data['element_forces'][element, end]
                moment = data['M'][element]+sign*np.cross(pb[element]-pa[element], data['N'][element])/2
                moment += np.cross(offset, data['N'][element])+sign*data['element_moments'][element, end]
                local_force, local_moment = frame.T@force, frame.T@moment
                section = Section(**{f.name: float(beam.value(f.name, t, side=side)) for f in fields(Section)})
                recovery = recover_section(section, local_force, local_moment,
                    **{key: float(beam.value(prop, t, side=side)) for key, prop in
                       [('cshell', 'Cshell'), ('nshell', 'Nshell'), ('atshell', 'Atshell')]})
                angles, jig_angles = euler(frame), euler(jig_frame)
                angles[1] -= jig_angles[1]
                xyz, jig = data['r'][node], network.rj[node]
                values = [t, xyz[0]-jig[0], xyz[1], xyz[2]-jig[2], *angles,
                    *recovery['moment_axes'], *local_force, *([0.]*6),
                    recovery['shell']['axial_strain_bound'], recovery['shell']['shear_stress_abs']]
                midpoint = None if k == len(block['rows'])-1 else (t+coordinate(block['rows'][k+1]))/2
                display = [0.]*7 if midpoint is None else [float(beam.value('chord', midpoint)), 0.,
                    float(beam.value('Cm', midpoint)), 0.,
                    -float(beam.value('mg', midpoint)+beam.value('Dmg', midpoint)), 0., 0.]
                values.extend(display)
                expected = np.array(ref['physical'])
                half = np.array([float(Decimal(10)**Decimal(Decimal(token).as_tuple().exponent))/2
                    for token in ref['raw_tokens']])*np.array(block['physical_multipliers'])
                difference = np.asarray(values)-expected
                rows.append(dict(beam=beam.index, source_line=ref['source_line'], t_printed=ref['printed_t'],
                    t_evaluated=t, side=side, node=node, element=element, end=end, interval_midpoint=midpoint,
                    values=[float(v) for v in values], expected=expected.tolist(), half_last_place=half.tolist(),
                    difference=difference.tolist(), inside_printed_interval=(abs(difference) <= half).tolist(),
                    position=xyz.tolist(), jig_position=jig.tolist(), frame=frame.tolist(), jig_frame=jig_frame.tolist(),
                    force_body=force.tolist(), moment_body=moment.tolist(), recovery=recovery,
                    structural_deformation=[*list(xyz-jig), *list(angles-np.array([jig_angles[0], 0., jig_angles[2]])),
                        *recovery['moment_axes'], *local_force,
                        recovery['shell']['axial_strain_bound'], recovery['shell']['shear_stress_abs']]))
        clamp, joint_position, joint_rotation = [], [], []
        for c in network.constraints:
            i, j = c['a'], c['b']
            if j is None:
                clamp += [float(np.max(abs(data['r'][i]-network.rj[i]))), float(np.max(abs(data['Q'][i]-np.eye(3))))]
            else:
                joint_position.append(float(np.max(abs(data['r'][j]-data['r'][i]-data['Q'][i]@(network.rj[j]-network.rj[i])))))
                joint_rotation.append(float(np.max(abs(data['Q'][i]-data['Q'][j]))))
        checks = dict(fresh_residual=float(np.max(abs(residual))), stored_residual=result['residual'],
            force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
            moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
            clamps=max(clamp), joint_position=max(joint_position), joint_rotation=max(joint_rotation))
        gates = plan['numerical_gates']
        passed = all(checks[k] <= gates['residual'] for k in ('fresh_residual', 'stored_residual'))
        passed &= all(checks[k] <= gates['force_and_moment_balance'] for k in ('force_balance', 'moment_balance'))
        passed &= all(checks[k] <= gates['clamps_and_rigid_joints'] for k in ('clamps', 'joint_position', 'joint_rotation'))
        assert result['structural_only'] and not result['strips'] and not result['mass_properties']['physical']
        diffs = np.array([r['difference'] for r in rows])
        matches = np.array([r['inside_printed_interval'] for r in rows])
        metrics = {names[j]: dict(max_abs_difference=float(np.max(abs(diffs[:, j]))),
            rmse=float(np.sqrt(np.mean(diffs[:, j]**2))), matches=int(np.sum(matches[:, j]))) for j in range(1, 28)}
        packet = dict(level=mesh['level'], intervals_by_beam=mesh['intervals_by_beam'], seconds=seconds,
            numerical_gates_pass=bool(passed), checks=checks, metrics=metrics,
            applied_force=result['applied_force'], applied_moment_about_Xmom=result['applied_moment'],
            applied_moment_about_origin=(np.asarray(result['applied_moment'])+np.cross(model.reference[1], result['applied_force'])).tolist(),
            structural_matches=int(np.sum(matches[:, STRUCTURAL])), structural_entries=len(rows)*len(STRUCTURAL),
            full_structural_rows=int(np.sum(np.all(matches[:, STRUCTURAL], axis=1))), rows=rows)
        write(out/'comparison.json', packet)
        records.append(packet)
        print(json.dumps({k: v for k, v in packet.items() if k not in ('rows', 'metrics')}), flush=True)
    changes = []
    for coarse, fine in zip(records[:-1], records[1:]):
        a = np.array([r['structural_deformation'] for r in coarse['rows']])
        b = np.array([r['structural_deformation'] for r in fine['rows']])
        measures = {}
        for j, col in enumerate(STRUCTURAL):
            envelope, change = float(np.max(abs(b[:, j]))), float(np.max(abs(a[:, j]-b[:, j])))
            ratio = change/envelope if envelope else (0. if not change else None)
            measures[names[col]] = dict(max_abs_change=change, fine_deformation_envelope=envelope,
                relative_change=ratio, passes=ratio is not None and ratio <= plan['numerical_gates']['fine_structural_mesh_relative'])
        changes.append(dict(coarse=coarse['level'], fine=fine['level'], measures=measures))
    summary = dict(status='COMPARISON_COMPLETE_REFERENCE_DIFFERENCES_RETAINED', goal_complete=False,
        acceptance=plan['acceptance'], source_sha256=sha(SOURCE), target_sha256=sha(TARGET),
        plan_sha256=sha(stage/'plan.json'), kernel_pins=plan['kernel_pins'], columns=names,
        rows=80, structural_entries=1120, conditional_zero_entries=800, input_echo_entries=160,
        unresolved_display_entries=80, cold_solves=3, fresh_residuals=3,
        all_numerical_gates_pass=all(r['numerical_gates_pass'] for r in records),
        all_fine_mesh_gates_pass=all(v['passes'] for v in changes[-1]['measures'].values()),
        strict_structural_reference_match=records[-1]['structural_matches'] == 1120,
        meshes=[{k: v for k, v in r.items() if k != 'rows'} for r in records], mesh_changes=changes,
        limitations=plan['limitations'])
    write(stage/'summary.json', summary)
    assert pins() == plan['kernel_pins']
    print(json.dumps({k: summary[k] for k in ('status', 'all_numerical_gates_pass', 'all_fine_mesh_gates_pass', 'strict_structural_reference_match')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--stage', type=Path, required=True)
    args = parser.parse_args()
    args.stage.mkdir(parents=True, exist_ok=True)
    (prepare if args.action == 'prepare' else run)(args.stage)
