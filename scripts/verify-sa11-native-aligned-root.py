"""Two serial native AVL controls with shared root chordwise vortex origins.

Partition the unchanged main-wing planform into three chordwise surfaces:
ahead of, overlapping, and behind the upper winglet's root chord. The overlap
has the same four cosine chordwise rows as the winglet. All pieces retain
component 1, original span stations, incidence, CLAF and physical boundaries.
This changes discretization only; it is not an ASWING model or pass-count update.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('chord_driver', ROOT/'scripts/verify-sa11-native-chord-refinement.py')
DRIVER = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(DRIVER)
INC, read, sha, write = DRIVER.INC, DRIVER.read, DRIVER.sha, DRIVER.write
BASE = ROOT/'artifacts/isae/sa11-native-chord-refinement-20261108'


def check(plan):
    assert sha(Path(__file__)) == plan['driver_sha256']
    for path, expected in plan['pins'].items():
        assert sha(ROOT/path) == expected, path


def convert(source):
    text = (source/'model.avl').read_text()
    header, *raw = text.split('SURFACE\n')
    segments = read(source/'conversion.json')['segments']
    assert len(raw) == len(segments) == 10
    parsed = []
    for block in raw:
        lines = block.splitlines()
        indices = [i+1 for i, line in enumerate(lines) if line == 'SECTION']
        assert len(indices) == 2
        parsed.append((lines, indices, [np.array([float(x) for x in lines[i].split()]) for i in indices]))
    main_root, upper_root = parsed[7][2][1], parsed[8][2][0]
    cuts = [0., (upper_root[0]-main_root[0])/main_root[3],
            (upper_root[0]+upper_root[3]-main_root[0])/main_root[3], 1.]
    assert 0 < cuts[1] < cuts[2] < 1
    blocks = []; mapped = []; boundary_error = 0.
    for segment, (lines, indices, sections) in zip(segments, parsed):
        partitions = [(cuts[j], cuts[j+1], n) for j, n in enumerate((1, 4, 1))] if segment['beam'] == 1 else [(0., 1., 4)]
        converted_sections = []
        for lo, hi, nc in partitions:
            new = list(lines); new[0] += f' chord {lo:.12g}..{hi:.12g}'
            new[1] = f'{nc} 1'
            part = []
            for idx, section in zip(indices, sections):
                row = section.copy(); row[0] += lo*row[3]; row[3] *= hi-lo
                new[idx] = ' '.join(f'{v:.17g}' for v in row)
                assert np.array_equal(row[[1,2,4,5,6]], section[[1,2,4,5,6]])
                part.append(row)
            converted_sections.append(part)
            blocks.append('SURFACE\n'+'\n'.join(new)+'\n')
            mapped.append(dict(**segment, chord_rows=nc, chord_fraction=[lo,hi]))
        for j, original in enumerate(sections):
            parts = [pair[j] for pair in converted_sections]
            assert abs(sum(s[3] for s in parts)-original[3]) < 1e-14
            errors = [abs(parts[0][0]-original[0]), abs(parts[-1][0]+parts[-1][3]-original[0]-original[3])]
            errors += [abs(left[0]+left[3]-right[0]) for left,right in zip(parts[:-1],parts[1:])]
            boundary_error = max(boundary_error, *errors)
    assert boundary_error < 1e-14
    return header+''.join(blocks), mapped, dict(main_root_fraction_cuts=cuts,
        maximum_boundary_reconstruction_error_m=boundary_error,
        subdivisions='Main wing: 1 forward + 4 shared-chord + 1 rear cosine rows; upper winglets: 4 cosine rows. Unchanged physical planform, per-section incidence/CLAF, span spacing and component 1.')


def prepare(out):
    assert not out.exists(), out
    audit = read(ROOT/'artifacts/isae/sa11-native-root-conformity-20261108/analysis.json')
    pins = dict(audit['source_pins'])
    for path, expected in pins.items():
        assert sha(ROOT/path) == expected, path
    for path in ['scripts/verify-sa11-native-chord-refinement.py',
                 'artifacts/isae/sa11-native-root-conformity-20261108/analysis.json']:
        pins[path] = sha(ROOT/path)
    out.mkdir(parents=True)
    cases = [dict(id=f'aligned-s{n}', span_strips=n, expected_vortices=n*5,
                  source=str((BASE/f'c4-s{n}').relative_to(ROOT))) for n in (64,128)]
    plan = dict(observed_utc=datetime.now(timezone.utc).isoformat(), cases=cases, pins=pins,
        driver_sha256=sha(Path(__file__)),
        basis='AVL manual spacing rules 3/4 permit chordwise SURFACE subdivisions with shared component and identical span stations. Root conformity is a diagnostic hypothesis, not a documented native ASWING rule.',
        protocol='Report-minus4 upper-winglet input; alpha1; native normalized speed1; PG240/340.21; body-x wakes; diagnostic Mach scaled240m/s. Four cosine rows over the physical shared root chord, one over each exposed main-wing remainder. No boundary, incidence, CLAF, physical core, reference, profile or stall law changes. Two bounded native processes, serial.',
        interpretation='Compare with retained c4-s64/c4-s128; this is a different discretization, not an equal-vortex-count control. Check matched root origins, native field/force identities, integrated loads and local refinement. Aligned origins alone do not impose matching chordwise circulation.')
    check(plan); write(out/'plan.json', plan); shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(prepared=True, cases=len(cases))))


def run(out, index):
    plan = read(out/'plan.json'); check(plan); case = plan['cases'][index]
    directory = out/case['id']; directory.mkdir()
    text, segments, geometry = convert(ROOT/case['source'])
    (directory/'model.avl').write_text(text)
    model = INC.model_at(-4.)
    write(directory/'conversion.json', dict(segments=segments, reference=model.reference.tolist(), geometry=geometry))
    commands = (ROOT/case['source']/'commands.txt').read_text()
    (directory/'commands.txt').write_text(commands)
    start = time.monotonic()
    process = subprocess.run([str(INC.BINARY)], input=commands, text=True,
                             capture_output=True, cwd=directory, timeout=30)
    seconds = time.monotonic()-start
    for name, data in [('stdout.txt',process.stdout),('stderr.txt',process.stderr)]:
        (directory/name).write_text(data)
    write(directory/'process.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(), returncode=process.returncode, seconds=seconds))
    assert process.returncode == 0, process.stderr
    f = INC.CONVERT.MATCHED.read_fields(directory/'elements.txt')
    assert len(f['GAM']) == case['expected_vortices']
    assert all(np.all(np.isfinite(v)) for v in f.values())
    np.savez(directory/'native-fields.npz', **f)
    labels = INC.CONVERT.MATCHED.NATIVE.labeled(directory/'total.txt')
    assert abs(labels["Mach, rb/2V, r'b/2V"][0]-240/340.21) < 1e-14
    native = dict(CL=labels['CLtot'][0], CDi=labels['Trefftz Plane: CLff, CDff, CYff, e'][1], CD_near=labels['CDvis, CDind'][1])
    force = 2*f['GAM']*np.cross(f['VINF']+f['VV'], f['RV2']-f['RV1'])/model.reference[0,0]
    alpha = np.deg2rad(1.)
    force_error = max(abs(float(force.sum(axis=0)@[-np.sin(alpha),0.,np.cos(alpha)])-native['CL']),
                      abs(float(force.sum(axis=0)@f['VINF'][0])-native['CD_near']))
    assert force_error < 1e-10
    tangents = []; beams = []; portions = []; start = 0
    for segment in segments:
        count = segment['count']*segment['chord_rows']
        beam = next(b for b in model.beams if b.index == segment['beam'])
        t = f['RV'][start:start+count,1]
        assert np.min(t) > segment['left'] and np.max(t) < segment['right']
        tangents.extend(INC.surface_frame(beam,t)[...,1]); beams.extend([beam.index]*count)
        portions.extend([segment['chord_fraction']]*count); start += count
    tangent = np.array(tangents); beam = np.array(beams); fractions = np.array(portions)
    v = 240*(f['VINF']+f['VV']); normal = v-np.sum(v*tangent,axis=1)[:,None]*tangent
    mach = np.linalg.norm(normal,axis=1)/340.21; i = int(np.argmax(mach))
    main = np.flatnonzero((beam==1)&(fractions[:,0]>0)&(fractions[:,1]<1)&(abs(f['RV2'][:,1]-1.2426)<1e-12))
    upper = np.flatnonzero((beam==2)&(abs(f['RV1'][:,1]-1.2426)<1e-12))
    assert len(main) == len(upper) == 4
    root_error = float(np.max(abs(f['RV2'][main]-f['RV1'][upper])))
    assert root_error < 1e-14
    original = read(ROOT/case['source']/'report.json')
    summary = dict(observed_utc=datetime.now(timezone.utc).isoformat(),case=case, native=native,
        reference=original['reference'], native_error_percent={k:100*(native[k]/original['reference'][k]-1) for k in ('CL','CDi')},
        versus_original_native_percent={k:100*(native[k]/original['native'][k]-1) for k in native},
        geometry=geometry, maximum_shared_root_origin_error_m=root_error, maximum_force_reconstruction_error=force_error,
        native_force_points=dict(maximum_normal_mach=float(mach[i]),points_above_unity=int(np.sum(mach>=1)),
            worst_index=i,worst_beam=int(beam[i]),worst_position=f['RV'][i].tolist(),
            maxima_by_beam={str(j):float(mach[beam==j].max()) for j in np.unique(beam)}),
        seconds=seconds,production_calls=0,primary_comparison_changed=False)
    np.savez(directory/'derived-fields.npz',beam_indices=beam,tangent=tangent,normal_mach=mach,force_coefficients=force,chord_fraction=fractions)
    check(plan)
    summary['artifact_sha256'] = {p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='artifact_sha256'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true'); action.add_argument('--case',type=int,choices=(0,1))
    args = p.parse_args()
    if args.prepare: prepare(args.output.resolve())
    else: run(args.output.resolve(),args.case)
