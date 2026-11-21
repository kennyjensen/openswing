"""Bounded native AVL chord/span refinement of the SA-11 upper-winglet input.

Each --case invocation runs one foreground native process. This is a linear
reference diagnostic, not a replacement ASWING model or a primary ISAE rescore.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('incidence', ROOT/'scripts/verify-sa11-winglet-incidence.py')
INC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INC)
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    assert not path.exists(), path
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def check(plan):
    for path, expected in plan['pins'].items():
        assert sha(ROOT/path) == expected, path
    assert sha(Path(__file__)) == plan['driver_sha256']


def prepare(out):
    assert not out.exists(), out
    old = read(ROOT/'artifacts/isae/sa11-command-grouping-20261108/audit.json')
    pins = dict(old['unchanged_parent_pins'])
    for path in ['docs/validation/ISAE_STATUS.md', 'scripts/verify-sa11-winglet-incidence.py',
                 'reference/avl-native-20261108/source/AVL3.52rel09032025/avl_doc-AVL350-04242025.txt',
                 str(INC.BINARY.relative_to(ROOT))]:
        pins[path] = sha(ROOT/path)
    baseline = ROOT/'artifacts/isae/sa11-winglet-incidence-20261108/report_minus4'
    for name in ('report.json', 'native-fields.npz', 'model.avl', 'total.txt'):
        pins[str((baseline/name).relative_to(ROOT))] = sha(baseline/name)
    cases = [dict(id=f'c{c}-s{64*r}', chord_rows=c, span_refinement=r,
                  span_strips=64*r, vortices=64*r*c, chord_spacing=1.)
             for c in (2, 4, 8) for r in (1, 2)]
    out.mkdir(parents=True)
    plan = dict(observed_utc=utc(), cases=cases, pins=pins,
        driver_sha256=sha(Path(__file__)), baseline=str(baseline.relative_to(ROOT)),
        previous_goal_turn='progress: audited 17 archived command sequences and surface grouping; retained distinct startup and local-field uncertainties',
        source_basis='AVL documentation, Vortex Lattice Spacing Distributions rule 4: refine chordwise and spanwise spacing; span-only refinement can give incorrect local results at dihedral breaks and swept-wing centers.',
        protocol='Upper-winglet report-minus4 twist, alpha1 degree, speed240m/s for diagnostic Mach, PG240/340.21, frozen body-x wakes. Same supplied geometry, section CLAF and converted incidence as the matched one-row case. Native cosine chordwise rows2/4/8 and span64/128; one-row uniform reference reused separately. One foreground process per invocation.',
        limits='Native AVL has no ASWING stall law, profile drag or section Cm in these inputs. Native force-point M_perp uses the ASW beam tangent but different chordwise receiver locations; it is not an ASWING acceptance gate. No production call, guard bypass, input correction or new ISAE pass.')
    check(plan)
    write(out/'plan.json', plan)
    shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(prepared=True, cases=len(cases))))


def run(out, index):
    plan = read(out/'plan.json'); check(plan)
    case = plan['cases'][index]
    directory = out/case['id']; directory.mkdir()
    model = INC.model_at(-4.)
    text, segments = INC.CONVERT.conversion(model, case['span_refinement'])
    lines = text.splitlines(); lines[1] = f'{240/340.21:.17g}'
    for i, line in enumerate(lines):
        if line == 'SURFACE':
            assert lines[i+2] == '1 0'
            lines[i+2] = f"{case['chord_rows']} {case['chord_spacing']}"
    (directory/'model.avl').write_text('\n'.join(lines)+'\n')
    write(directory/'conversion.json', dict(segments=segments, reference=model.reference.tolist()))
    commands = 'LOAD model.avl\nOPER\nO\nA\n\nA A 1\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n'
    (directory/'commands.txt').write_text(commands)
    start = time.monotonic()
    process = subprocess.run([str(INC.BINARY)], input=commands, text=True,
        capture_output=True, cwd=directory, timeout=30)
    elapsed = time.monotonic()-start
    (directory/'stdout.txt').write_text(process.stdout)
    (directory/'stderr.txt').write_text(process.stderr)
    write(directory/'process.json', dict(observed_utc=utc(), returncode=process.returncode, seconds=elapsed))
    assert process.returncode == 0, process.stderr
    fields = INC.CONVERT.MATCHED.read_fields(directory/'elements.txt')
    assert len(fields['GAM']) == case['vortices']
    assert all(np.all(np.isfinite(a)) for a in fields.values())
    np.savez(directory/'native-fields.npz', **fields)
    labels = INC.CONVERT.MATCHED.NATIVE.labeled(directory/'total.txt')
    assert abs(labels["Mach, rb/2V, r'b/2V"][0]-240/340.21) < 1e-14
    coefficient_force = 2*fields['GAM']*np.cross(fields['VINF']+fields['VV'], fields['RV2']-fields['RV1'])/model.reference[0, 0]
    force = coefficient_force.sum(axis=0)
    alpha = np.deg2rad(1.)
    lift = float(force@[-np.sin(alpha), 0., np.cos(alpha)])
    drag = float(force@fields['VINF'][0])
    native = dict(CL=labels['CLtot'][0], CDi=labels['Trefftz Plane: CLff, CDff, CYff, e'][1],
                  CD_near=labels['CDvis, CDind'][1], Cm_reference=labels['CYtot, Cmtot'][1])
    error = max(abs(lift-native['CL']), abs(drag-native['CD_near']))
    assert error < 1e-10, error
    tangent = []; beam_indices = []; start = 0
    for segment in segments:
        count = segment['count']*case['chord_rows']
        beam = next(b for b in model.beams if b.index == segment['beam'])
        t = fields['RV'][start:start+count, 1]
        assert np.min(t) > segment['left'] and np.max(t) < segment['right']
        tangent.extend(INC.surface_frame(beam, t)[..., 1])
        beam_indices.extend([beam.index]*count); start += count
    tangent = np.array(tangent); beam_indices = np.array(beam_indices)
    velocity = 240*(fields['VV']+fields['VINF'])
    normal = velocity-np.sum(velocity*tangent, axis=1)[:, None]*tangent
    local_mach = np.linalg.norm(normal, axis=1)/340.21
    maximum_index = int(np.argmax(local_mach))
    # Native force moments translated to the origin: no ASW profile moments.
    cm_origin = float(np.cross(fields['RV'], coefficient_force).sum(axis=0)[1]/model.reference[0, 1])
    cm_ref = float(np.cross(fields['RV']-model.reference[1], coefficient_force).sum(axis=0)[1]/model.reference[0, 1])
    assert abs(cm_ref-native['Cm_reference']) < 1e-10
    baseline = read(ROOT/plan['baseline']/'report.json')
    reference = baseline['reference']
    summary = dict(observed_utc=utc(), case=case, native=native, reference=reference,
        native_error_percent={k:100*(native[k]/reference[k]-1) for k in ('CL','CDi')},
        Cm_origin_vortex_only=cm_origin, maximum_force_reconstruction_error=error,
        native_force_points=dict(maximum_normal_mach=float(local_mach.max()),
            points_above_unity=int(np.sum(local_mach >= 1)), worst_index=maximum_index,
            worst_beam=int(beam_indices[maximum_index]), worst_position=fields['RV'][maximum_index].tolist(),
            maxima_by_beam={str(i):float(local_mach[beam_indices==i].max()) for i in np.unique(beam_indices)}),
        seconds=elapsed, production_calls=0, primary_comparison_changed=False)
    np.savez(directory/'derived-fields.npz', beam_indices=beam_indices, tangent=tangent,
             normal_mach=local_mach, force_coefficients=coefficient_force)
    check(plan)
    summary['artifact_sha256'] = {p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='artifact_sha256'}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare', action='store_true'); g.add_argument('--case', type=int)
    args = p.parse_args()
    if args.prepare: prepare(args.output.resolve())
    else: run(args.output.resolve(), args.case)


if __name__ == '__main__':
    main()
