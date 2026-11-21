"""Serial audit of actual SA-11 winglet geometry in native AVL.

This is a linear, incompressible conversion diagnostic, not a rescore of the
archived transonic cases. Original ASW files and production code stay fixed.
Each invocation runs one native solve followed by one production solve.
"""
import argparse
from dataclasses import replace
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
from openswing.asw import parse_asw
from openswing.discretization import mesh_breaks
from openswing.factored_influence import FactoredInfluence
from openswing.frozen_influence import lifting_geometry
from openswing.geometry import model_meshes, surface_frame

PARENT = ROOT/'artifacts/isae/avl-matched-fields-r1-20261108'
SPEC = importlib.util.spec_from_file_location('matched', ROOT/'scripts/verify-avl-matched-fields.py')
MATCHED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATCHED)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def write(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
def unit(v): return v/np.linalg.norm(v, axis=-1, keepdims=True)


def prepare(out, lower_only=False):
    assert not out.exists(), out
    parent = json.loads((PARENT/'plan.json').read_text())
    MATCHED.unchanged(parent)
    binary = PARENT/'avl-fields'
    assert sha(binary) == json.loads((PARENT/'build.json').read_text())['binary_sha256']
    sources = ['examples/isae-sa11-wingtip-up.asw', 'examples/isae-sa11-wingtip-up-and-down.asw']
    if lower_only: sources = sources[1:]
    pins = {**parent['unchanged_pins'], **{s: sha(ROOT/s) for s in sources},
            'examples/isae-sa11-winglet-sources.json': sha(ROOT/'examples/isae-sa11-winglet-sources.json'),
            'scripts/verify-avl-matched-fields.py': sha(ROOT/'scripts/verify-avl-matched-fields.py')}
    cases = [dict(source=s, refinement=r, id=f'{Path(s).stem}-r{r}') for s in sources for r in (1, 2)]
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=utc(), cases=cases, unchanged_pins=pins,
        binary=str(binary.relative_to(ROOT)), binary_sha256=sha(binary), driver_sha256=sha(Path(__file__)),
        conditions='Alpha 5 degrees, Mach 0, unit speed, frozen body-x wake, no stall. Native AVL has no profile drag or section pitching moment. Production retains original section data; compare circulation, fields and isolated vortex force, not raw total CD/Cm.',
        conversion='ASW normal chord divided by |x cross beam tangent|; leading edge = beam axis - Xax*streamwise_chord*x. One chord row with Cspace=0 and CLAF=dCLda/(2*pi). Projected zero-lift incidence atan(across*tan(twist+alpha)). Split at actual property/sweep breaks; all surfaces preserve physical component 1. No gaps closed or roots moved.',
        limitations='Native normal is perpendicular to the quarter-chord bound leg; ASW normal is perpendicular to the beam. These differ on tapered twisted surfaces and are explicitly measured. Shared native endpoints/receivers isolate this difference from span discretization. Bundled Joint scaling corrections are disclosed in the pinned provenance. Not an original ASWING result or a new ISAE pass.'))
    shutil.copyfile(__file__, out/'driver-used.py')
    print(json.dumps(dict(prepared=True, cases=len(cases))))


def conversion(model, refinement):
    refs = model.reference
    lines = ['SA11 actual winglet geometry conversion audit', '0', '0 0 0',
             ' '.join(map(str, refs[0])), ' '.join(map(str, refs[1])), '0']
    segments = []
    for beam in model.beams:
        cuts = np.r_[beam.domain[0], mesh_breaks(beam), beam.domain[1]]
        for j, (left, right) in enumerate(zip(cuts[:-1], cuts[1:])):
            n = (4 if beam.index == 1 else 16)*refinement
            lines += ['SURFACE', f'Beam {beam.index} interval {j}', '1 0', 'COMPONENT', str(beam.physical_index)]
            for t, side in ((left, 'right'), (right, 'left')):
                tangent = surface_frame(beam, t, side)[..., 1]
                across = float(np.linalg.norm(np.cross([1., 0., 0.], tangent)))
                chord = float(beam.value('chord', t, side=side))/across
                rle = beam.position(t, side=side)-[float(beam.value('Xax', t, side=side))*chord, 0., 0.]
                theta = np.deg2rad(beam.value('twist', t, side=side)+beam.value('alpha', t, side=side))
                incidence = float(np.rad2deg(np.arctan(across*np.tan(theta))))
                claf = float(beam.value('dCLda', t, side=side)/(2*np.pi))
                lines += ['SECTION', ' '.join(f'{v:.17g}' for v in (*rle, chord, incidence))+f' {n} 1', 'CLAF', f'{claf:.17g}']
            segments.append(dict(beam=beam.index, left=float(left), right=float(right), count=n))
    return '\n'.join(lines)+'\n', segments


def mapped_meshes(model, fields, segments):
    settings, samples = {}, {}
    start = 0
    for beam in model.beams:
        count = sum(s['count'] for s in segments if s['beam'] == beam.index)
        sl = slice(start, start+count)
        # In these specific models t=y exactly, including the reflected wing.
        ends = np.r_[fields['RV1'][sl, 1], fields['RV2'][start+count-1, 1]]
        ends[0], ends[-1] = beam.domain
        settings[str(beam.index)] = dict(nodes=ends.tolist())
        samples[beam.index] = fields['RV'][sl, 1]
        start += count
    meshes = model_meshes(model, dict(default=16, beams=settings))
    meshes = [replace(m, tm=samples[m.beam.index], rm=m.beam.position(samples[m.beam.index]),
                      frames=surface_frame(m.beam, samples[m.beam.index])) for m in meshes]
    g = lifting_geometry(meshes, np.array([1., 0., 0.]))
    errors = {key: float(np.max(abs(g[key]-fields[name]))) for key, name in
              [('a', 'RV1'), ('b', 'RV2'), ('hv', 'RV'), ('cp', 'RC')]}
    assert max(errors.values()) < 2e-11, errors
    return meshes, g, errors, settings


def run(out, index):
    plan = json.loads((out/'plan.json').read_text())
    for name, pin in plan['unchanged_pins'].items(): assert sha(ROOT/name) == pin, name
    assert sha(Path(__file__)) == plan['driver_sha256']
    binary = ROOT/plan['binary']; assert sha(binary) == plan['binary_sha256']
    case = plan['cases'][index]
    directory = out/case['id']; assert not directory.exists(); directory.mkdir()
    source = (ROOT/case['source']).read_text(); model = parse_asw(source)
    assert not model.diagnostics, model.diagnostics
    (directory/'model.asw').write_text(source)
    avl, segments = conversion(model, case['refinement'])
    (directory/'model.avl').write_text(avl)
    write(directory/'conversion.json', dict(segments=segments, reference=model.reference.tolist()))
    commands = 'LOAD model.avl\nOPER\nO\nA\n\nA A 5\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n'
    (directory/'commands.txt').write_text(commands)
    start = time.monotonic()
    p = subprocess.run([str(binary)], input=commands, text=True, capture_output=True, cwd=directory, timeout=30)
    native_seconds = time.monotonic()-start
    (directory/'stdout.txt').write_text(p.stdout); (directory/'stderr.txt').write_text(p.stderr)
    write(directory/'process.json', dict(observed_utc=utc(), returncode=p.returncode, seconds=native_seconds))
    assert p.returncode == 0, p.stderr
    f = MATCHED.read_fields(directory/'elements.txt')
    assert len(f['GAM']) == sum(s['count'] for s in segments)
    np.savez(directory/'native-fields.npz', **f)
    meshes, g, geometry_errors, settings = mapped_meshes(model, f, segments)
    write(directory/'mapped-mesh.json', dict(settings=settings, geometry_errors=geometry_errors,
        receiver_policy='Exact native RV span stations, retained separately from generated ASW Glauert stations.'))
    tangent = np.concatenate([m.frames[..., 1] for m in meshes])
    normal = np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 0]
                             + np.cos(np.deg2rad(m.beam.value('alpha', m.tm)))[:, None]*m.frames[..., 2] for m in meshes])
    beam_delta = tangent*g['ds'][:, None]
    bound_delta = g['b']-g['a']
    span = np.array([0., 1., 1.])*tangent
    across = np.linalg.norm(span, axis=1); span = unit(span)
    n0 = np.cross([1., 0., 0.], span)
    theta = np.concatenate([np.deg2rad(m.beam.value('twist', m.tm)+m.beam.value('alpha', m.tm)) for m in meshes])
    section_ainc = np.arctan(across*np.tan(theta))
    # AVL interpolates chord-weighted sine/cosine of incidence, whereas ASW
    # interpolates twist itself. This matters on the twisted, tapered lower
    # winglet. Reconstruct the literal exported AVL input, not the ASW value.
    angles = []
    offset = 0
    for segment in segments:
        beam = next(b for b in model.beams if b.index == segment['beam'])
        left, right, count = segment['left'], segment['right'], segment['count']
        cs, sn = [], []
        for t, side in ((left, 'right'), (right, 'left')):
            tangent_end = surface_frame(beam, t, side)[..., 1]
            across_end = np.linalg.norm(np.cross([1., 0., 0.], tangent_end))
            chord_end = beam.value('chord', t, side=side)/across_end
            theta_end = np.deg2rad(beam.value('twist', t, side=side)+beam.value('alpha', t, side=side))
            incidence_end = np.arctan(across_end*np.tan(theta_end))
            cs.append(chord_end*np.cos(incidence_end)); sn.append(chord_end*np.sin(incidence_end))
        fraction = (f['RV'][offset:offset+count, 1]-left)/(right-left)
        angles.extend(np.arctan2((1-fraction)*sn[0]+fraction*sn[1], (1-fraction)*cs[0]+fraction*cs[1]))
        offset += count
    ainc = np.array(angles)
    ec = np.cos(ainc)[:, None]*[1., 0., 0.]-np.sin(ainc)[:, None]*n0
    predicted_native_normal = unit(np.cross(ec, bound_delta))
    native_normal_error = float(np.max(abs(predicted_native_normal-f['ENC'])))
    assert native_normal_error < 2e-11, native_normal_error
    normal_angles = np.rad2deg(np.arctan2(np.linalg.norm(np.cross(normal, f['ENC']), axis=1), np.sum(normal*f['ENC'], axis=1)))
    cp = FactoredInfluence(g['cp'], g['a'], g['b'], [1., 0., 0.], np.eye(3))
    hv = FactoredInfluence(g['hv'], g['a'], g['b'], [1., 0., 0.], np.eye(3), exclude_bound=np.eye(len(normal), dtype=bool))
    matrix = cp.matrix()
    native_normal_matrix = np.einsum('ijk,ik->ij', matrix, f['ENC'])
    gamma_native_normals = np.linalg.solve(native_normal_matrix, -np.sum(f['VINF']*f['ENC'], axis=1))
    ng = f['GAM'].ravel()
    native_kernel_factor = 4*np.pi*.079577472
    native_field_error = float(np.max(abs(native_kernel_factor*hv.apply(ng)-f['VV'])))
    gamma_native_error = float(np.max(abs(gamma_native_normals/native_kernel_factor-ng))/np.max(abs(ng)))
    assert gamma_native_error < 1e-6, gamma_native_error
    gamma_beam_normals = np.linalg.solve(np.einsum('ijk,ik->ij', matrix, normal), -np.sum(f['VINF']*normal, axis=1))
    start = time.monotonic()
    try:
        result = evaluate_aerodynamics(model, FlightCondition(speed=1., density=1.2256, alpha=5., mach=0., stall=False, freeze_influences=True), meshes)
        write(directory/'openswing.json', result)
        gamma = np.array([s['circulation'] for s in result['strips']])
        production = dict(status='computed', residual=result['residual'])
    except AnalysisError as exc:
        # Preserve a rejected unit-speed state and its already-solved circulation;
        # this does not bypass the production Mach guard or publish valid loads.
        assert exc.details and exc.details.get('kind') == 'section_normal_mach', str(exc)
        tb = exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics': tb = tb.tb_next
        assert tb is not None
        gamma = tb.tb_frame.f_locals['gamma'].copy()
        production = dict(status='rejected', error=str(exc), details=exc.details)
        write(directory/'openswing-rejected.json', production)
    python_seconds = time.monotonic()-start
    gamma_beam_error = float(np.max(abs(gamma-gamma_beam_normals))/np.max(abs(gamma)))
    assert gamma_beam_error < 1e-7, gamma_beam_error
    v = f['VINF']+hv.apply(gamma)
    nv = f['VINF']+f['VV']
    area = float(model.reference[0, 0])
    lift_axis = np.array([-np.sin(np.deg2rad(5.)), 0., np.cos(np.deg2rad(5.))])
    drag_axis = f['VINF'][0]
    def loads(strength, velocity, delta):
        force = np.sum(2*strength[:, None]*np.cross(velocity, delta)/area, axis=0)
        return dict(force=force.tolist(), CL=float(force@lift_axis), CD=float(force@drag_axis))
    native_load = loads(ng, nv, bound_delta)
    labels = MATCHED.NATIVE.labeled(directory/'total.txt')
    actual = np.array([labels['CXtot, Cltot, Cl\'tot'][0], labels['CYtot, Cmtot'][0], labels['CZtot, Cntot, Cn\'tot'][0]])
    reconstruction_error = float(np.max(abs(actual-native_load['force'])))
    assert reconstruction_error < 2e-10, reconstruction_error
    np.savez(directory/'diagnostic-fields.npz', normal=normal, beam_delta=beam_delta, bound_delta=bound_delta,
             gamma=gamma, gamma_native_normals=gamma_native_normals, gamma_beam_normals=gamma_beam_normals,
             velocity=v, native_normal_angles_deg=normal_angles)
    report = dict(observed_utc=utc(), case=case, vortices=len(ng), geometry_errors=geometry_errors,
        native_seconds=native_seconds, openswing_seconds=python_seconds, production=production,
        native_normal_reconstruction_max_error=native_normal_error,
        native_vs_asw_incidence_interpolation_max_deg=float(np.max(abs(np.rad2deg(ainc-section_ainc)))),
        normal_angle_difference_deg=dict(maximum=float(np.max(normal_angles)), rms=float(np.sqrt(np.mean(normal_angles**2)))),
        bound_vs_beam_segment_length_difference_percent=float(np.max(abs(np.linalg.norm(bound_delta, axis=1)/g['ds']-1))*100),
        native_field_reproduction_max_error=native_field_error,
        native_gamma_reproduction_relative_error=gamma_native_error, production_gamma_reproduction_relative_error=gamma_beam_error,
        production_native_gamma_relative_linf=float(np.max(abs(gamma-ng))/np.max(abs(ng))),
        native_force_reconstruction_max_error=reconstruction_error,
        vortex_force_diagnostics=dict(native=native_load, openswing=loads(gamma, v, beam_delta),
            native_gamma_velocity_with_beam_force_direction=loads(ng, nv, beam_delta)),
        maximum_bound_speed_over_freestream=dict(native=float(np.max(np.linalg.norm(nv, axis=1))), openswing=float(np.max(np.linalg.norm(v, axis=1)))),
        native_totals=labels,
        limits=plan['limitations'])
    for name, pin in plan['unchanged_pins'].items(): assert sha(ROOT/name) == pin, name
    report['artifact_sha256'] = {p.name: sha(p) for p in sorted(directory.iterdir()) if p.is_file()}
    write(directory/'report.json', report)
    print(json.dumps({key: report[key] for key in ['case', 'vortices', 'geometry_errors', 'normal_angle_difference_deg', 'production_native_gamma_relative_linf', 'native_gamma_reproduction_relative_error', 'vortex_force_diagnostics', 'maximum_bound_speed_over_freestream']}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--lower-only', action='store_true', help='Prepare just the two upper/lower winglet cases.')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare', action='store_true'); g.add_argument('--case', type=int)
    a = p.parse_args()
    if a.prepare: prepare(a.output.resolve(), a.lower_only)
    else: run(a.output.resolve(), a.case)


if __name__ == '__main__': main()
