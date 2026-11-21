"""Two serial, explicitly unpaired SA-11 cant0 geometry diagnostics.

The original file is preserved, including invalid joint stations. Native AVL
and the direct production aerodynamic calls use independently meshed rigid
beams; they do not validate structural assembly or authenticate a source pair.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate', ROOT / 'scripts/verify-sa11-fixed-pg-candidate.py')
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.geometry import mesh_beam, model_meshes, surface_frame
from openswing.frozen_influence import FrozenInfluences, lifting_geometry
from openswing.factored_influence import FactoredInfluence

sha = D.sha
read = D.read
write = D.write
utc = D.utc


def audit_model(model):
    joints = []
    for row in model.records['joint']:
        for number, t in zip(row[:2], row[2:4]):
            b = next(b for b in model.beams if b.index == number)
            if not b.domain[0] <= t <= b.domain[1]:
                joints.append(dict(beam=b.index, station=t, domain=b.domain))
    assert len(joints) == 2
    try:
        model_meshes(model, 16)
    except ValueError as exc:
        assert 'Attachment station is outside beam' in str(exc)
        error = str(exc)
    else:
        raise AssertionError('The original invalid joints must remain rejected.')
    beams = [dict(index=b.index, physical_index=b.physical_index, domain=b.domain,
                  endpoints=b.position(np.array(b.domain)).tolist(),
                  twist=b.value('twist', np.array(b.domain)).tolist(),
                  alpha=b.value('alpha', np.array(b.domain)).tolist(),
                  slope=b.value('dCLda', np.array(b.domain)).tolist()) for b in model.beams]
    return dict(joint_errors=joints, normal_mesh_error=error, beams=beams,
                reference=model.reference.tolist(), constants=model.constants.tolist())


def check(plan):
    for name, digest in plan['pins'].items():
        assert sha(ROOT / name) == digest, name


def prepare(out):
    assert not out.exists()
    model = parse_asw(D.CANT.read_text())
    sources = list((ROOT / 'openswing').glob('*.py')) + [D.CANT, Path(__file__), Path(D.__file__),
        ROOT / 'scripts/verify-sa11-avl-baseline.py', ROOT / 'scripts/audit-sa11-avl-conversion.py',
        ROOT / 'scripts/verify-avl-matched-fields.py', D.BASE.BINARY, D.BASE.BINARY.parent / 'build.json',
        ROOT / 'docs/validation/ISAE_STATUS.md', ROOT / 'docs/validation/isae-progress/history.json',
        ROOT / 'docs/validation/isae-progress-scopes.json', ROOT / 'reference/aswing_doc.txt',
        ROOT / 'docs/validation/aswing-authoritative-sources.json',
        ROOT / 'artifacts/isae/sa11-fixed-pg-candidate-20261108/analysis.json']
    sources += list(D.SOURCE.rglob('*.txt')) + list(D.SOURCE.rglob('*.sh'))
    for entry in read(ROOT / 'docs/validation/aswing-authoritative-sources.json')['files']:
        if entry['id'] in ('isae-part-1', 'drela-steady'):
            p = ROOT / entry['local_pdf']; assert sha(p) == entry['sha256']; sources.append(p)
    assert sha(D.BASE.BINARY) == read(D.BASE.BINARY.parent / 'build.json')['binary_sha256']
    plan = dict(observed_utc=utc(), previous_goal_turn='progress: fixed-PG baseline hypothesis constrained; upper-winglet mismatch and extension conversion blocker verified',
        cases=[dict(id=f'cant0-a{alpha}', alpha=alpha) for alpha in (0., 1.)],
        pins={str(p.relative_to(ROOT)): sha(p) for p in sources}, source_audit=audit_model(model),
        protocol='Original cant0 full-scale geometry/properties/references, zero global PG, alpha0/1, true speed255, density1.2256, body-x frozen wake, one chord row and64 native vortices. Direct production aero uses identical independently meshed rigid beams; original joint errors remain rejected by model_meshes. Standard stall and local Mach checks retained.',
        limitations='Cant0 has no paired archive or driver. Comparisons with upper .75/.78 are hypothesis checks, not accepted reference comparisons. No original input repair, source pairing, force convention change or primary pass. Native AVL lacks profile and section Cm laws; no native totalCD or Cm match is claimed.')
    out.mkdir(); write(out / 'plan.json', plan)
    (out / 'driver-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(cases=2, source_audit=plan['source_audit'])), flush=True)


def mapped_beams(model, fields, segments):
    """Invert a transverse coordinate, including the vertical cant0 winglets."""
    meshes, details, start = [], [], 0
    for b in model.beams:
        count = sum(s['count'] for s in segments if s['beam'] == b.index)
        sl = slice(start, start + count)
        ends = b.position(np.array(b.domain))
        # A quarter-chord offset is along body x. The varying transverse
        # coordinate can therefore recover the original material parameter.
        axis = 1 + int(abs(ends[1, 2]-ends[0, 2]) > abs(ends[1, 1]-ends[0, 1]))
        a, z = b.domain
        rate = (ends[1, axis] - ends[0, axis]) / (z - a)
        assert abs(rate) > .1
        t_probe = np.linspace(a, z, 19)
        assert np.max(abs(b.position(t_probe)[:, axis] - (ends[0, axis] + rate*(t_probe-a)))) < 1e-12
        parameter = lambda pts: a + (pts[:, axis] - ends[0, axis]) / rate
        nodes = parameter(np.concatenate((fields['RV1'][sl], fields['RV2'][start+count-1:start+count])))
        nodes[0], nodes[-1] = b.domain
        samples = parameter(fields['RV'][sl])
        mesh = mesh_beam(b, dict(default=16, beams={str(b.index):dict(nodes=nodes.tolist())}))
        assert len(mesh.tm) == count
        mesh = replace(mesh, tm=samples, rm=b.position(samples), frames=surface_frame(b, samples))
        meshes.append(mesh)
        details.append(dict(beam=b.index, transverse_axis=axis, parameter_rate=rate, nodes=nodes.tolist(), samples=samples.tolist()))
        start += count
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    errors = {key:float(np.max(abs(g[key]-fields[name]))) for key,name in [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC')]}
    assert max(errors.values()) < 2e-11, errors
    return meshes, g, errors, details


def run(out, index):
    plan = read(out / 'plan.json'); check(plan)
    case = plan['cases'][index]; folder = out / case['id']; folder.mkdir()
    model = parse_asw(D.CANT.read_text())
    assert json.loads(json.dumps(audit_model(model))) == plan['source_audit']
    text, segments = D.BASE.CONVERT.conversion(model, 1)
    (folder / 'model.avl').write_text(text)
    commands = f"LOAD model.avl\nOPER\nO\nA\n\nA A {case['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (folder / 'commands.txt').write_text(commands)
    begin = time.monotonic()
    p = subprocess.run([str(D.BASE.BINARY)], input=commands, text=True, capture_output=True, cwd=folder, timeout=25)
    (folder / 'stdout.txt').write_text(p.stdout); (folder / 'stderr.txt').write_text(p.stderr)
    write(folder / 'process.json', dict(returncode=p.returncode, seconds=time.monotonic()-begin, observed_utc=utc()))
    assert p.returncode == 0
    f = D.BASE.CONVERT.MATCHED.read_fields(folder / 'elements.txt'); assert len(f['GAM']) == 64
    np.savez(folder / 'native-fields.npz', **f)
    meshes, g, errors, mapping = mapped_beams(model, f, segments)
    write(folder / 'mapped-beams.json', dict(segments=segments, geometry_errors=errors, mapping=mapping))
    condition = FlightCondition(speed=255., density=model.constants[1], alpha=case['alpha'], mach=0., freeze_influences=True)
    write(folder / 'condition.json', asdict(condition))
    def expired(*args):
        raise TimeoutError('Cant0 diagnostic exceeded15seconds')
    signal.signal(signal.SIGALRM, expired); signal.alarm(15)
    try:
        state, values, gamma, velocity = D.production(model, meshes, condition, FrozenInfluences(model, meshes), folder, None)
    finally:
        signal.alarm(0)
    labels = D.BASE.CONVERT.MATCHED.NATIVE.labeled(folder / 'total.txt')
    assert labels["Mach, rb/2V, r'b/2V"][0] == 0.
    ff = labels['Trefftz Plane: CLff, CDff, CYff, e']
    native = dict(CL=labels['CLtot'][0], CDi=ff[1], efficiency=ff[3], CY=labels['CYtot, Cmtot'][0], CD_near=labels['CDvis, CDind'][1])
    targets = {}
    for suffix in ('0_75','0_78'):
        raw = np.loadtxt(D.SOURCE / 'Wing_tip_up' / f'wingtip_up_Ma_{suffix}.txt')
        target = raw[raw[:,71] == case['alpha']]; assert target.shape == (1,82)
        refs = {k:float(target[0,i]) for k,i in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
        targets[suffix] = dict(values=refs, native_error_percent={k:100*(native[k]/refs[k]-1) for k in ('CL','CDi','efficiency')})
    k = 4*np.pi*.079577472; ng = f['GAM'].ravel()
    cp = FactoredInfluence(g['cp'],g['a'],g['b'],[1.,0.,0.],np.eye(3))
    hv = FactoredInfluence(g['hv'],g['a'],g['b'],[1.,0.,0.],np.eye(3),exclude_bound=np.eye(64,dtype=bool))
    cg = np.linalg.solve(np.einsum('ijk,ik->ij',cp.matrix(),f['ENC']),-np.sum(f['VINF']*f['ENC'],axis=1))
    gamma_error = float(np.max(abs(cg/k-ng))/np.max(abs(ng))); assert gamma_error < 1e-6
    field_error = float(np.max(abs(hv.apply(gamma)+255*f['VINF']-velocity))); assert field_error < 1e-6
    check(plan)
    report = dict(observed_utc=utc(), case=case, native=native, production=state, production_values=values,
        reference_hypotheses=targets, geometry_errors=errors,
        native_gamma_reconstruction_relative_error=gamma_error,
        production_native_gamma_relative_error=float(np.max(abs(gamma/255-ng))/np.max(abs(ng))),
        production_velocity_reconstruction_error=field_error,
        native_field_reconstruction_error=float(np.max(abs(k*hv.apply(ng)-f['VV']))),
        artifact_sha256={str(p.relative_to(folder)):sha(p) for p in folder.iterdir() if p.is_file()},
        original_setup_authenticated=False, original_joint_errors_preserved=True, accepted_primary_checks=0)
    write(folder / 'report.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('artifact_sha256','production')}), flush=True)
    print(json.dumps(dict(production_status=state['status'], maximum=state['maximum'], residual=state['residual'], stalled_strips=state['stalled_strips'])),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',type=Path,required=True)
    group=ap.add_mutually_exclusive_group(required=True);group.add_argument('--prepare',action='store_true');group.add_argument('--case',type=int)
    args=ap.parse_args()
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    if args.prepare: prepare(args.output.resolve())
    else: run(args.output.resolve(), args.case)


if __name__=='__main__': main()
