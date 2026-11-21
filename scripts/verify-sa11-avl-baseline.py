"""One serial native AVL / production baseline comparison at archived speed.

The independent extension supplies an alternative section slope. Neither input
is fitted, and no diagnostic result is substituted into registered ISAE totals.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from openswing.asw import Distribution, parse_asw
from openswing.factored_influence import FactoredInfluence

SPEC = importlib.util.spec_from_file_location('conversion', ROOT/'scripts/audit-sa11-avl-conversion.py')
CONVERT = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CONVERT)
CACHE = ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'
SOURCE = next(CACHE.glob('1 - Aerodynamics/SA*/SA - 11 - *'))/'Aswing_Simulations'
BINARY = ROOT/'artifacts/isae/avl-matched-fields-r1-20261108/avl-fields'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()
def write(p, value): p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def prepare(out):
    assert not out.exists(), out
    parent = json.loads((BINARY.parent/'plan.json').read_text())
    CONVERT.MATCHED.unchanged(parent)
    assert sha(BINARY) == json.loads((BINARY.parent/'build.json').read_text())['binary_sha256']
    names = ['wing_alone/wing_alone.asw', 'wing_extension/wing_extension.asw',
             'wing_alone/wing_alone_Ma_0_70.txt', 'wing_alone/wing_alone_polar_Ma_0_70.sh']
    manifest = json.loads((CACHE.parent/'manifest.json').read_text())
    source_pins = {}
    for name in names:
        path = SOURCE/name
        assert sha(path) == manifest['files'][str(path.relative_to(CACHE))]['sha256']
        source_pins[str(path.relative_to(ROOT))] = sha(path)
    pins = {**parent['unchanged_pins'], **source_pins,
            'scripts/audit-sa11-avl-conversion.py': sha(ROOT/'scripts/audit-sa11-avl-conversion.py'),
            'scripts/verify-avl-matched-fields.py': sha(ROOT/'scripts/verify-avl-matched-fields.py')}
    cases = [dict(id=f'{slope}-alpha{alpha}', slope=slope, alpha=float(alpha), speed=240.)
             for alpha in (0, 1) for slope in ('original', 'extension_slope')]
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, unchanged_pins=pins,
        binary=str(BINARY.relative_to(ROOT)), binary_sha256=sha(BINARY), driver_sha256=sha(Path(__file__)),
        protocol='Original SA11 baseline geometry and section inputs, with one separately labeled alternative changing only dCLda to the extension value 6.34. Native AVL one chord row, 64 span strips split at original property/sweep breaks. Exact native endpoints and receiver stations also used in production. Frozen body-x influence, PG Mach=240/340.21, density1.2256, no rotation. Production stall and local Mach checks retained. Native profile drag and section Cm absent; compare vortex loads and Trefftz drag separately from production totals.',
        limitations='No actual native ASWING executable, verified historical startup settings or recovered original mesh. The section-slope alternative is independently sourced but not the unchanged baseline. Native AVL is an authoritative method comparison, not proof of the archived generating input. No new ISAE passes.'))
    shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(prepared=True, cases=len(cases))))


def run(out, index):
    plan = json.loads((out/'plan.json').read_text())
    for name, pin in plan['unchanged_pins'].items(): assert sha(ROOT/name) == pin, name
    assert sha(Path(__file__)) == plan['driver_sha256'] and sha(BINARY) == plan['binary_sha256']
    c = plan['cases'][index]; directory = out/c['id']; assert not directory.exists(); directory.mkdir()
    source = (SOURCE/'wing_alone/wing_alone.asw').read_text()
    model = parse_asw(source); original = parse_asw(source)
    donor = parse_asw((SOURCE/'wing_extension/wing_extension.asw').read_text())
    assert len(model.beams) == 1 and not model.diagnostics
    if c['slope'] == 'extension_slope':
        b = model.beams[0]; d = b.distributions['dCLda']
        values = donor.beams[0].value('dCLda', d.t)
        assert np.all(values == 6.34)
        b.distributions['dCLda'] = Distribution('dCLda', d.t.copy(), values.copy(), d.line)
    for key, d in original.beams[0].distributions.items():
        e = model.beams[0].distributions[key]
        assert np.array_equal(d.t, e.t)
        if key != 'dCLda': assert np.array_equal(d.values, e.values), key
    (directory/'original.asw').write_text(source)
    write(directory/'input-choice.json', dict(slope=c['slope'], dCLda=model.beams[0].distributions['dCLda'].values.tolist(),
        only_changed_distribution='dCLda' if c['slope'] == 'extension_slope' else None))
    speed = c['speed']; mach = speed/model.constants[2]
    text, segments = CONVERT.conversion(model, 2)
    lines = text.splitlines(); lines[0] = 'SA11 archived-speed baseline diagnostic'; lines[1] = f'{mach:.17g}'
    (directory/'model.avl').write_text('\n'.join(lines)+'\n')
    commands = f"LOAD model.avl\nOPER\nO\nA\n\nA A {c['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (directory/'commands.txt').write_text(commands)
    start = time.monotonic()
    p = subprocess.run([str(BINARY)], input=commands, text=True, capture_output=True, cwd=directory, timeout=30)
    native_seconds = time.monotonic()-start
    (directory/'stdout.txt').write_text(p.stdout); (directory/'stderr.txt').write_text(p.stderr)
    write(directory/'process.json', dict(observed_utc=utc(), returncode=p.returncode, seconds=native_seconds))
    assert p.returncode == 0, p.stderr
    f = CONVERT.MATCHED.read_fields(directory/'elements.txt')
    np.savez(directory/'native-fields.npz', **f)
    meshes, geom, errors, settings = CONVERT.mapped_meshes(model, f, segments)
    assert len(f['GAM']) == 64
    condition = FlightCondition(speed=speed, density=model.constants[1], mach=None, alpha=c['alpha'], freeze_influences=True)
    write(directory/'setup.json', dict(condition=asdict(condition), pg_mach=float(mach), mesh=settings, geometry_errors=errors))
    start = time.monotonic()
    try:
        result = evaluate_aerodynamics(model, condition, meshes)
        write(directory/'openswing.json', result)
        gamma = np.array([s['circulation'] for s in result['strips']])/speed
        velocity = np.array([s['relative_velocity'] for s in result['strips']])/speed
        state = dict(status='computed', residual=result['residual'], stalled_strips=sum(s['stalled'] for s in result['strips']),
                     max_section_normal_mach=max(s['normal_mach'] for s in result['strips']))
    except AnalysisError as exc:
        assert exc.details and exc.details.get('kind') == 'section_normal_mach', str(exc)
        tb = exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics': tb = tb.tb_next
        assert tb is not None
        local = tb.tb_frame.f_locals
        gamma = local['gamma'].copy()/speed; velocity = local['v'].copy()/speed
        state = dict(status='rejected', details=exc.details, error=str(exc)); result = None
        write(directory/'openswing-rejected.json', state)
    python_seconds = time.monotonic()-start
    ng = f['GAM'].ravel(); pg = np.diag([1/np.sqrt(1-mach**2), 1., 1.])
    cp = FactoredInfluence(geom['cp'], geom['a'], geom['b'], [1.,0.,0.], pg)
    hv = FactoredInfluence(geom['hv'], geom['a'], geom['b'], [1.,0.,0.], pg, exclude_bound=np.eye(len(ng), dtype=bool))
    k = 4*np.pi*.079577472
    gamma_same_normal = np.linalg.solve(np.einsum('ijk,ik->ij', cp.matrix(), f['ENC']), -np.sum(f['VINF']*f['ENC'], axis=1))
    gamma_kernel_error = float(np.max(abs(gamma_same_normal/k-ng))/np.max(abs(ng)))
    assert gamma_kernel_error < 1e-6, gamma_kernel_error
    field_kernel_error = float(np.max(abs(k*hv.apply(ng)-f['VV'])))
    labels = CONVERT.MATCHED.NATIVE.labeled(directory/'total.txt')
    assert abs(labels["Mach, rb/2V, r'b/2V"][0]-mach) < 1e-14
    tangent = np.concatenate([m.frames[..., 1] for m in meshes])
    beam_delta = tangent*geom['ds'][:,None]
    alpha = np.deg2rad(c['alpha']); lift = np.array([-np.sin(alpha),0.,np.cos(alpha)])
    force = np.sum(2*gamma[:,None]*np.cross(velocity, beam_delta)/model.reference[0,0],axis=0)
    native = dict(CL=labels['CLtot'][0], CD_near=labels['CDvis, CDind'][1], CDi=labels['Trefftz Plane: CLff, CDff, CYff, e'][1])
    raw = np.loadtxt(SOURCE/'wing_alone/wing_alone_Ma_0_70.txt')
    matches = raw[raw[:,71] == c['alpha']]; assert matches.shape == (1,82)
    row = matches[0]; reference = dict(CL=float(row[77]), CD=float(row[78]), CDi=float(row[79]), Cm=float(row[80]), efficiency=float(row[81]))
    values = dict(native=native, reference=reference,
        openswing_vortex=dict(CL=float(force@lift), CD_near=float(force@f['VINF'][0])),
        openswing_total=None if result is None else {key:result[key] for key in ['CL','CD','CDi','Cm','efficiency']})
    errors_to_reference = {name:{key:100*(values[name][key]/reference[key]-1) for key in ['CL','CDi']}
        for name in ['native']+(['openswing_total'] if result is not None else [])}
    limits = []; begin = 0
    for mesh in meshes:
        local_cl = 2*gamma[begin:begin+len(mesh.tm)]/(mesh.beam.value('chord',mesh.tm)*np.linalg.norm(velocity[begin:begin+len(mesh.tm)]-
            np.sum(velocity[begin:begin+len(mesh.tm)]*mesh.frames[...,1],axis=1)[:,None]*mesh.frames[...,1],axis=1))
        limits.extend(np.minimum(mesh.beam.value('CLmax',mesh.tm)-local_cl, local_cl-mesh.beam.value('CLmin',mesh.tm))/.05)
        begin += len(mesh.tm)
    report = dict(observed_utc=utc(), case=c, native_seconds=native_seconds, openswing_seconds=python_seconds,
        production=state, geometry_errors=errors, values=values, errors_to_reference_percent=errors_to_reference,
        minimum_stall_limit_margin_widths=float(min(limits)),
        native_production_gamma_relative_linf=float(np.max(abs(gamma-ng))/np.max(abs(ng))),
        native_gamma_operator_reproduction_error=gamma_kernel_error, native_field_operator_reproduction_error=field_kernel_error,
        native_max_section_normal_mach_using_asw_axis=float(mach*np.max(np.linalg.norm(f['VV']+f['VINF']-
            np.sum((f['VV']+f['VINF'])*tangent,axis=1)[:,None]*tangent,axis=1))),
        native_totals=labels, limitations=plan['limitations'])
    for name, pin in plan['unchanged_pins'].items(): assert sha(ROOT/name) == pin, name
    report['artifact_sha256'] = {p.name:sha(p) for p in directory.iterdir() if p.is_file()}
    write(directory/'report.json', report)
    print(json.dumps({key:report[key] for key in ['case','production','values','errors_to_reference_percent','minimum_stall_limit_margin_widths','native_production_gamma_relative_linf','native_gamma_operator_reproduction_error']}))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--case',type=int)
    a=p.parse_args()
    if a.prepare: prepare(a.output.resolve())
    else: run(a.output.resolve(),a.case)


if __name__ == '__main__': main()
