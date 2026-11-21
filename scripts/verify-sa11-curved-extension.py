"""Serial native AVL comparison retaining the original curved SA-11 extension.

AVL sections sample each original ASW mesh node, including one-sided property
breaks. Source endpoints match exactly; the different receiver rules remain
explicit. Neither the old straightened exports nor primary results are changed.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('fixed_pg', ROOT/'scripts/verify-sa11-fixed-pg-candidate.py')
FIXED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXED)
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.discretization import mesh_breaks
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import FrozenInfluences, lifting_geometry
from openswing.geometry import model_meshes, surface_frame
from avl_vorvelc_reference import matrix as native_core_matrix

SOURCE = FIXED.SOURCE/'wing_extension'
BINARY = FIXED.BASE.BINARY
NATIVE = FIXED.BASE.CONVERT.MATCHED
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
utc = lambda: datetime.now(timezone.utc).isoformat()
write = FIXED.write


def section(beam, t, side='right'):
    """Normal ASW chord to streamwise AVL chord, without moving the beam."""
    frame = surface_frame(beam, t, side)
    across = float(np.linalg.norm(np.cross([1., 0., 0.], frame[..., 1])))
    assert across > 1e-6
    chord = float(beam.value('chord', t, side=side))/across
    le = beam.position(t, side=side)-[float(beam.value('Xax', t, side=side))*chord, 0., 0.]
    theta = np.deg2rad(beam.value('twist', t, side=side)+beam.value('alpha', t, side=side))
    incidence = float(np.arctan(across*np.tan(theta)))
    return dict(le=le, chord=chord, incidence=incidence,
                claf=float(beam.value('dCLda', t, side=side)/(2*np.pi)))


def export(model, meshes, mach):
    lines = ['SA11 original curved extension sampled at ASW nodes', f'{mach:.17g}', '0 0 0',
             ' '.join(map(str, model.reference[0])), ' '.join(map(str, model.reference[1])), '0']
    strips, groups = [], []
    errors = dict(leading_edge=0., streamwise_chord=0., quarter_chord=0.)
    for mesh in meshes:
        beam = mesh.beam
        assert beam.lifting, 'This comparison does not export fuselage beams.'
        cuts = np.r_[beam.domain[0], mesh_breaks(beam), beam.domain[1]]
        for group, (left, right) in enumerate(zip(cuts[:-1], cuts[1:])):
            indices = np.flatnonzero((mesh.t0 >= left) & (mesh.t1 <= right))
            assert len(indices) and np.all(np.diff(indices) == 1)
            nodes = np.r_[mesh.t0[indices], mesh.t1[indices[-1]]]
            assert nodes[0] == left and nodes[-1] == right
            lines += ['SURFACE', f'Beam {beam.index} physical interval {group}',
                      '1 0', 'COMPONENT', str(beam.physical_index)]
            ends = [section(beam, t, 'left' if k == len(nodes)-1 else 'right')
                    for k, t in enumerate(nodes)]
            for e in ends:
                values = [*e['le'], e['chord'], np.rad2deg(e['incidence'])]
                lines += ['SECTION', ' '.join(f'{v:.17g}' for v in values)+' 1 0',
                          'CLAF', f"{e['claf']:.17g}"]
            groups.append(dict(beam=beam.index, left=float(left), right=float(right), count=len(indices)))
            for i, (a, b) in enumerate(zip(ends[:-1], ends[1:])):
                ra = a['le']+np.array([.25*a['chord'], 0., 0.])
                rb = b['le']+np.array([.25*b['chord'], 0., 0.])
                rv = .5*(ra+rb)
                rc = rv+np.array([.25*(a['chord']*a['claf']+b['chord']*b['claf']), 0., 0.])
                inc = np.arctan2(a['chord']*np.sin(a['incidence'])+b['chord']*np.sin(b['incidence']),
                                 a['chord']*np.cos(a['incidence'])+b['chord']*np.cos(b['incidence']))
                transverse = rb-ra; transverse[0] = 0.; transverse /= np.linalg.norm(transverse)
                normal0 = np.cross([1., 0., 0.], transverse)
                chord_direction = np.cos(inc)*np.array([1., 0., 0.])-np.sin(inc)*normal0
                normal = np.cross(chord_direction, rb-ra); normal /= np.linalg.norm(normal)
                strips.append(dict(a=ra, b=rb, hv=rv, cp=rc, normal=normal,
                                   t=.5*(nodes[i]+nodes[i+1]), beam=beam.index))
                # Report sampled interpolation error, not a certified supremum.
                for fraction in np.linspace(0., 1., 9)[1:-1]:
                    t = (1-fraction)*nodes[i]+fraction*nodes[i+1]
                    actual = section(beam, t)
                    le = (1-fraction)*a['le']+fraction*b['le']
                    chord = (1-fraction)*a['chord']+fraction*b['chord']
                    q = actual['le']+np.array([.25*actual['chord'], 0., 0.])
                    errors['leading_edge'] = max(errors['leading_edge'], float(np.linalg.norm(actual['le']-le)))
                    errors['streamwise_chord'] = max(errors['streamwise_chord'], abs(actual['chord']-chord))
                    errors['quarter_chord'] = max(errors['quarter_chord'], float(np.linalg.norm(q-((1-fraction)*ra+fraction*rb))))
    expected = {key: np.asarray([s[key] for s in strips]) for key in strips[0]}
    return '\n'.join(lines)+'\n', expected, dict(groups=groups, strips=len(strips),
        sampled_curve_error=errors, section_policy='One AVL section at each original ASW node; one span strip per interval. Preserve physical components and one-sided property breaks. Uniform within each single-strip interval.',
        receiver_policy='AVL arithmetic receiver on each one-strip section interval; production retains its unmodified Glauert/material-arc receiver. Receiver differences are measured, not overridden.')


def model_for(case):
    if case['setup'] == 'literal70':
        model = parse_asw((SOURCE/'wing_extension.asw').read_text())
        choice = dict(source=str((SOURCE/'wing_extension.asw').relative_to(ROOT)),
                      changes=[], reference_before=model.reference.tolist(), reference_after=model.reference.tolist())
    else:
        assert case['setup'] == 'candidate75'
        model, choice = FIXED.model_for('extension')
    assert not model.diagnostics
    return model, choice


def check(plan):
    for name, digest in plan['pins'].items():
        assert sha(ROOT/name) == digest, name


def prepare(out):
    assert not out.exists(), out
    cases = []
    for setup, speed, angles in [('literal70', 240., (1.,)), ('candidate75', 255., (0., 1.))]:
        for alpha in angles:
            for count in (64, 128):
                cases.append(dict(id=f'{setup}-a{alpha:g}-n{count}', setup=setup, speed=speed,
                                  alpha=alpha, requested_count=count))
    files = list((ROOT/'openswing').glob('*.py'))+[Path(__file__), BINARY, BINARY.parent/'build.json',
        ROOT/'scripts/avl_vorvelc_reference.py',
        ROOT/'scripts/verify-sa11-fixed-pg-candidate.py', ROOT/'scripts/verify-sa11-avl-baseline.py',
        ROOT/'scripts/audit-sa11-avl-conversion.py', ROOT/'scripts/verify-avl-matched-fields.py',
        ROOT/'scripts/verify-avl-native-controls.py', ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'reference/aswing_doc.txt',
        ROOT/'docs/validation/isae-progress/history.json', ROOT/'docs/validation/isae-progress-scopes.json',
        ROOT/'docs/validation/aswing-authoritative-sources.json', FIXED.CANT]
    files += [p for p in SOURCE.iterdir() if p.is_file()]
    avl_root = ROOT/'reference/avl-native-20261108/source/AVL3.52rel09032025'
    files += [avl_root/'src/amake.f', avl_root/'src/aic.f', avl_root/'avl_doc-AVL350-04242025.txt']
    for item in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        if item['id'] in ('isae-part-1', 'drela-steady'):
            path = ROOT/item['local_pdf']; assert sha(path) == item['sha256']; files.append(path)
    assert sha(BINARY) == read(BINARY.parent/'build.json')['binary_sha256']
    plan = dict(observed_utc=utc(), cases=cases, pins={str(p.relative_to(ROOT)):sha(p) for p in files},
        previous_goal_turn='progress: reconciled ISAE wake criticism with the retrieved Chreim manuscript; no supported force-law substitution, known curved-extension conversion defect remains actionable.',
        protocol='Six native AVL cases and six production calls, serially. An identical completed native case may be reused with hashes and exact input/command equality. Original extension geometry/section data. Two literal .70 points at alpha1 and two grids; four fixed-zero-PG/cant0-normalization candidate .75 points at alpha0/1 and two grids. All guards retained. Source endpoints match; original receiver conventions remain distinct and are measured. Native field replay retains its quartic core; separate zero-core discrepancy is reported.',
        limitations='Native AVL has no ASWING profile drag, stall or section Cm here. Frozen body-x influences match AVL; native startup remains unknown. The .75 reference dimensions/zeroPG remain an explicit hypothesis. No primary passes or original input changes. Refinement is for the concrete curved conversion and its receiver error, not a proposed winglet-junction repair.')
    out.mkdir(parents=True); write(out/'plan.json', plan)
    (out/'driver-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(prepared=True, cases=cases)), flush=True)


def run(out, index, reuse_native=None):
    plan = read(out/'plan.json'); check(plan); case = plan['cases'][index]
    folder = out/case['id']; folder.mkdir()
    model, choice = model_for(case)
    write(folder/'input-choice.json', choice)
    meshes = model_meshes(model, case['requested_count'])
    mach = case['speed']/model.constants[2] if case['setup'] == 'literal70' else 0.
    avl, expected, conversion = export(model, meshes, mach)
    (folder/'model.avl').write_text(avl); write(folder/'conversion.json', conversion)
    np.savez(folder/'expected-geometry.npz', **expected)
    geom = lifting_geometry(meshes, np.array([1., 0., 0.]))
    tangent = np.concatenate([m.frames[..., 1] for m in meshes])
    np.savez(folder/'production-geometry.npz', **geom, tangent=tangent,
             sample_t=np.concatenate([m.tm for m in meshes]))
    commands = f"LOAD model.avl\nOPER\nO\nA\n\nA A {case['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (folder/'commands.txt').write_text(commands)
    if reuse_native is not None:
        assert (reuse_native/'model.avl').read_bytes() == (folder/'model.avl').read_bytes()
        assert (reuse_native/'commands.txt').read_bytes() == (folder/'commands.txt').read_bytes()
        old_plan = read(reuse_native.parent/'plan.json')
        assert old_plan['pins'][str(BINARY.relative_to(ROOT))] == sha(BINARY)
        assert read(reuse_native/'process.json')['returncode'] == 0
        copied = ['stdout.txt','stderr.txt','process.json','elements.txt','total.txt','strips.txt','body-strips.txt']
        for name in copied: shutil.copyfile(reuse_native/name,folder/name)
        write(folder/'native-reuse.json',dict(observed_utc=utc(),source=str(reuse_native.relative_to(ROOT)),
            file_sha256={name:sha(reuse_native/name) for name in copied},new_native_call=False))
    else:
        begin = time.monotonic()
        p = subprocess.run([str(BINARY)], input=commands, capture_output=True, text=True, cwd=folder, timeout=25)
        (folder/'stdout.txt').write_text(p.stdout); (folder/'stderr.txt').write_text(p.stderr)
        write(folder/'process.json', dict(returncode=p.returncode, seconds=time.monotonic()-begin, observed_utc=utc()))
        assert p.returncode == 0, p.stderr
    fields = NATIVE.read_fields(folder/'elements.txt')
    np.savez(folder/'native-fields.npz', **fields)
    assert len(fields['GAM']) == len(expected['t'])
    native_geometry_error = {key:float(np.max(abs(expected[key]-fields[name]))) for key,name in
        [('a','RV1'),('b','RV2'),('hv','RV'),('cp','RC'),('normal','ENC')]}
    assert max(native_geometry_error.values()) < 2e-11, native_geometry_error
    source_error = max(float(np.max(abs(geom[key]-fields[name]))) for key,name in [('a','RV1'),('b','RV2')])
    assert source_error < 2e-11, source_error
    receiver_error = {key:float(np.max(np.linalg.norm(geom[key]-fields[name],axis=1)))
                      for key,name in [('hv','RV'),('cp','RC')]}
    labels = NATIVE.NATIVE.labeled(folder/'total.txt')
    assert abs(labels["Mach, rb/2V, r'b/2V"][0]-mach) < 1e-14
    ng = fields['GAM'].ravel(); n = len(ng)
    pg = np.diag([1/np.sqrt(1-mach*mach), 1., 1.])
    cp = FactoredInfluence(fields['RC'], fields['RV1'], fields['RV2'], [1.,0.,0.], pg)
    hv = FactoredInfluence(fields['RV'], fields['RV1'], fields['RV2'], [1.,0.,0.], pg, exclude_bound=np.eye(n,dtype=bool))
    factor = 4*np.pi*.079577472
    core_cp = native_core_matrix(fields['RC'],fields['RV1'],fields['RV2'],mach)
    core_hv = native_core_matrix(fields['RV'],fields['RV1'],fields['RV2'],mach,exclude_self=True)
    rhs = -np.sum(fields['VINF']*fields['ENC'],axis=1)
    reconstructed = np.linalg.solve(np.einsum('ijk,ik->ij',core_cp,fields['ENC']),rhs)
    native_gamma_error = float(np.max(abs(reconstructed-ng))/np.max(abs(ng)))
    zero_core_gamma = np.linalg.solve(np.einsum('ijk,ik->ij',cp.matrix(),fields['ENC']),rhs)/factor
    zero_core_gamma_difference = float(np.max(abs(zero_core_gamma-ng))/np.max(abs(ng)))
    zero_core_velocity_difference = float(np.max(abs(factor*hv.apply(ng)-fields['VV'])))
    native_velocity_error = float(np.max(abs(np.sum(core_hv*ng[None,:,None],axis=1)-fields['VV'])))
    native_velocity_scaled_error = native_velocity_error/max(1.,float(np.max(abs(fields['VV']))))
    force = np.sum(2*ng[:,None]*np.cross(fields['VINF']+fields['VV'], fields['RV2']-fields['RV1']),axis=0)/model.reference[0,0]
    listed_force = np.array([labels["CXtot, Cltot, Cl'tot"][0],labels['CYtot, Cmtot'][0],labels["CZtot, Cntot, Cn\'tot"][0]])
    force_error = float(np.max(abs(force-listed_force)))
    assert native_gamma_error < 1e-6 and native_velocity_scaled_error < 1e-6 and force_error < 2e-10
    sub = folder/'production'; sub.mkdir()
    condition = FlightCondition(speed=case['speed'], alpha=case['alpha'], density=model.constants[1],
                                mach=mach, freeze_influences=True)
    write(sub/'condition.json', asdict(condition))
    def expired(*_): raise TimeoutError('Curved extension production solve exceeded 15 seconds')
    signal.signal(signal.SIGALRM, expired); signal.alarm(15)
    try:
        state, values, gamma, velocity = FIXED.production(model, meshes, condition, FrozenInfluences(model,meshes), sub, None)
    finally:
        signal.alarm(0)
    phv = FactoredInfluence(geom['hv'],geom['a'],geom['b'],[1.,0.,0.],pg,exclude_bound=np.eye(n,dtype=bool))
    production_velocity_error = float(np.max(abs(phv.apply(gamma)+case['speed']*fields['VINF']-velocity)))
    assert production_velocity_error < 1e-6, production_velocity_error
    label = '0_70' if case['setup'] == 'literal70' else '0_75'
    rows = np.loadtxt(SOURCE/f'wing_extension_Ma_{label}.txt')
    row = rows[rows[:,71] == case['alpha']]; assert row.shape == (1,82)
    reference = {key:float(row[0,col]) for key,col in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
    ff = labels['Trefftz Plane: CLff, CDff, CYff, e']
    native = dict(CL=labels['CLtot'][0],CDi=ff[1],efficiency=ff[3],CD_near=labels['CDvis, CDind'][1])
    report = dict(observed_utc=utc(),case=case,strips=n,conversion=conversion,production=state,
        native_geometry_reconstruction_error=native_geometry_error,shared_source_endpoint_error=source_error,
        native_production_receiver_distance=receiver_error,native_gamma_reconstruction_relative_error=native_gamma_error,
        native_velocity_reconstruction_error=native_velocity_error,native_velocity_reconstruction_scaled_error=native_velocity_scaled_error,
        native_zero_core_gamma_relative_difference=zero_core_gamma_difference,
        native_zero_core_velocity_difference=zero_core_velocity_difference,
        native_reused_from=None if reuse_native is None else str(reuse_native.relative_to(ROOT)),
        native_force_reconstruction_error=force_error,production_velocity_reconstruction_error=production_velocity_error,
        discrete_gamma_relative_difference=float(np.max(abs(gamma/case['speed']-ng))/np.max(abs(ng))),
        gamma_comparison_scope='Different native/ASW receiver rules on identical source segments; not an exact-operator equivalence.',
        native=native,values=values,reference=reference,
        native_error_percent={k:100*(native[k]/reference[k]-1) for k in ('CL','CDi','efficiency')},
        production_error_percent=None if values is None else {k:100*(v/reference[k]-1) for k,v in values.items()},
        primary_passes_added=0,original_setup_authenticated=False)
    check(plan)
    report['artifact_sha256']={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
    write(folder/'report.json',report)
    print(json.dumps({k:report[k] for k in ('case','strips','shared_source_endpoint_error','native_production_receiver_distance',
        'native_error_percent','production_error_percent','production','discrete_gamma_relative_difference')}),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--reuse-native',type=Path,help='Reuse a terminal native case only after exact input/command/binary checks.')
    group=ap.add_mutually_exclusive_group(required=True); group.add_argument('--prepare',action='store_true');group.add_argument('--case',type=int)
    args=ap.parse_args()
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    if args.prepare: prepare(args.output.resolve())
    else: run(args.output.resolve(),args.case,None if args.reuse_native is None else args.reuse_native.resolve())


if __name__=='__main__': main()
