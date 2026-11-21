"""Extend the report/file twist-sign comparison over archived rows 0..5 deg.

One --row invocation runs two small, serial native AVL/OpenSwing comparisons.
The already retained 1 degree pair is reused, with its original timestamps.
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
PARENT = ROOT/'artifacts/isae/sa11-winglet-incidence-20261108'
TABLE = INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()
write = INC.write


def prepare(out):
    assert not out.exists(), out
    parent = read(PARENT/'plan.json')
    pins = dict(parent['unchanged_pins'])
    for file in [Path(INC.__file__), INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_polar_Ma_0_70.sh',
                 INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up.asw']:
        pins[str(file.relative_to(ROOT))] = sha(file)
    for name, pin in pins.items():
        assert sha(ROOT/name) == pin, name
    table = np.loadtxt(TABLE)
    assert table.shape == (41, 82) and np.array_equal(table[:21, 71], np.arange(21)*.25)
    cases = []
    for row in range(21):
        for variant, twist in [('literal_plus4', 4.), ('report_minus4', -4.)]:
            case = dict(id=f'row{row:02d}-{variant}', row=row, alpha=float(table[row,71]), twist=twist)
            if row == 4:
                file = PARENT/variant/'report.json'
                case['reused_report'] = str(file.relative_to(ROOT))
                case['reused_sha256'] = sha(file)
            cases.append(case)
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, unchanged_pins=pins,
        binary_sha256=parent['binary_sha256'], driver_sha256=sha(Path(__file__)),
        previous_goal_turn='progress: report/file upper-winglet sign conflict established and tested at one operating point',
        selection='All first21 archived rows, 0 to5 degrees in0.25-degree steps. No row chosen or dropped by its error. Verify section stall margins individually; no post-stall correction or input fitting.',
        protocol='Only upper-winglet twist changes +4 to -4. Native64 grid, shared endpoints/receivers, body-x wake, Mach240/340.21, speed240, density1.2256. Production retains stall and local Mach guard. The1-degree pair is reused unchanged.',
        limitation='Native AVL vortex CL omits profile-force lift. Rejected production fields are diagnostics only. No archived producing settings are authenticated and no registered comparison passes are added.'))
    shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(prepared=True, retained_cases=42, new_pairs=20)))


def check(plan):
    for name, pin in plan['unchanged_pins'].items():
        assert sha(ROOT/name) == pin, name
    assert sha(Path(__file__)) == plan['driver_sha256']
    assert sha(INC.BINARY) == plan['binary_sha256']


def run_case(out, case):
    directory = out/case['id']
    assert not directory.exists(), directory
    directory.mkdir()
    model = INC.model_at(case['twist'])
    text, segments = INC.CONVERT.conversion(model, 1)
    lines = text.splitlines(); lines[1] = f'{240/340.21:.17g}'
    (directory/'model.avl').write_text('\n'.join(lines)+'\n')
    commands = f"LOAD model.avl\nOPER\nO\nA\n\nA A {case['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (directory/'commands.txt').write_text(commands)
    start = time.monotonic()
    proc = subprocess.run([str(INC.BINARY)], input=commands, text=True, capture_output=True, cwd=directory, timeout=20)
    (directory/'stdout.txt').write_text(proc.stdout); (directory/'stderr.txt').write_text(proc.stderr)
    write(directory/'process.json', dict(observed_utc=utc(), returncode=proc.returncode, seconds=time.monotonic()-start))
    assert proc.returncode == 0, proc.stderr
    f = INC.CONVERT.MATCHED.read_fields(directory/'elements.txt')
    assert len(f['GAM']) == 64
    np.savez(directory/'native-fields.npz', **f)
    meshes, geom, errors, settings = INC.CONVERT.mapped_meshes(model, f, segments)
    write(directory/'mesh.json', dict(settings=settings, geometry_errors=errors))
    gamma = velocity = cl = None
    start = time.monotonic()
    try:
        result = INC.evaluate_aerodynamics(model, INC.FlightCondition(
            speed=240., alpha=case['alpha'], density=1.2256, mach=None, freeze_influences=True), meshes)
        write(directory/'openswing.json', result)
        gamma = np.array([s['circulation'] for s in result['strips']])
        velocity = np.array([s['relative_velocity'] for s in result['strips']])
        cl = np.array([s['cl'] for s in result['strips']])
        state = dict(status='computed', residual=result['residual'], maximum_section_normal_mach=max(s['normal_mach'] for s in result['strips']))
    except INC.AnalysisError as exc:
        state = dict(status='rejected', error=str(exc), details=exc.details)
        if exc.details and exc.details.get('kind') == 'section_normal_mach':
            tb = exc.__traceback__
            while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics':
                tb = tb.tb_next
            assert tb is not None
            local = tb.tb_frame.f_locals
            gamma, velocity, cl = [local[key].copy() for key in ('gamma', 'v', 'cl')]
            state.update(residual=exc.details['circulation_residual'], maximum_section_normal_mach=exc.details['maximum']['normal_mach'])
        write(directory/'openswing-rejected.json', state)
    seconds = time.monotonic()-start
    diagnostic = {}
    if gamma is not None:
        limits = []; offset = 0
        for mesh in meshes:
            end = offset + len(mesh.tm); local_cl = cl[offset:end]
            limits.extend(np.minimum(mesh.beam.value('CLmax', mesh.tm)-local_cl,
                                     local_cl-mesh.beam.value('CLmin', mesh.tm)))
            offset = end
        limits = np.array(limits)
        np.savez(directory/'diagnostic-state.npz', gamma=gamma, velocity=velocity, cl=cl, stall_margin=limits)
        diagnostic = dict(minimum_stall_margin_widths=float(limits.min()/.05), stalled_strips=int(np.sum(limits<0)),
            native_production_gamma_relative_linf=float(np.max(abs(gamma/240-f['GAM'].ravel()))/np.max(abs(f['GAM']))))
    labels = INC.CONVERT.MATCHED.NATIVE.labeled(directory/'total.txt')
    assert abs(labels["Mach, rb/2V, r'b/2V"][0]-240/340.21) < 1e-14
    native = dict(CL=labels['CLtot'][0], CDi=labels['Trefftz Plane: CLff, CDff, CYff, e'][1], CD_near=labels['CDvis, CDind'][1])
    table = np.loadtxt(TABLE); row = table[case['row']]; assert row[71] == case['alpha']
    reference = dict(CL=float(row[77]), CDi=float(row[79]), CD=float(row[78]))
    tangent = np.concatenate([m.frames[...,1] for m in meshes])
    v = f['VV']+f['VINF']; normal = v-np.sum(v*tangent,axis=1)[:,None]*tangent
    report = dict(observed_utc=utc(), case=case, native=native, reference=reference, production=state,
        openswing_seconds=seconds, maximum_geometry_error=max(errors.values()),
        native_error_percent={key:100*(native[key]/reference[key]-1) for key in ('CL','CDi')},
        native_maximum_section_normal_mach_using_asw_axis=float(240/340.21*np.linalg.norm(normal,axis=1).max()), **diagnostic)
    report['artifact_sha256'] = {p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json', report)
    return dict(alpha=case['alpha'], twist=case['twist'], error_percent=report['native_error_percent'],
                status=state['status'], maximum_mach=state.get('maximum_section_normal_mach'),
                stall_margin_widths=diagnostic.get('minimum_stall_margin_widths'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true'); group.add_argument('--row', type=int)
    args = p.parse_args(); out = args.output.resolve()
    if args.prepare:
        prepare(out)
        return
    plan = read(out/'plan.json'); check(plan)
    cases = [case for case in plan['cases'] if case['row'] == args.row]
    assert len(cases) == 2
    for case in cases:
        if 'reused_report' in case:
            assert sha(ROOT/case['reused_report']) == case['reused_sha256']
            print(json.dumps(dict(reused=case['reused_report'])))
        else:
            print(json.dumps(run_case(out, case)), flush=True)
    check(plan)


if __name__ == '__main__':
    main()
