"""Bounded native AVL/OpenSwing checks of an explicitly conditional SA-11 setup.

Reference dimensions come from the original cant0 input at one-tenth length.
No fit is performed and original inputs/primary comparisons are unchanged.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('baseline', ROOT/'scripts/verify-sa11-avl-baseline.py')
BASE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE)
from openswing.aero import AnalysisError, FlightCondition, evaluate_aerodynamics
from openswing.asw import Distribution, parse_asw
from openswing.frozen_influence import FrozenInfluences

SOURCE = BASE.SOURCE
CANT = SOURCE/'Wing_tip_up_cant0/wingtip_up_cant0.asw'
CHOICES = ('baseline_original', 'baseline_slope634', 'extension', 'upper_plus4', 'upper_minus4')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
utc = lambda: datetime.now(timezone.utc).isoformat()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def model_for(choice):
    if choice.startswith('upper'):
        path = ROOT/'examples/isae-sa11-wingtip-up.asw'
        variant = 'wingtip_up'
    elif choice == 'extension':
        path = SOURCE/'wing_extension/wing_extension.asw'
        variant = 'wing_extension'
    else:
        path = SOURCE/'wing_alone/wing_alone.asw'
        variant = 'wing_alone'
    model = parse_asw(path.read_text())
    before = model.reference.copy()
    donor = parse_asw(CANT.read_text())
    model.reference[0] = donor.reference[0]/np.array([100., 10., 10.])
    assert np.allclose(model.reference[0], [.9767, .37874, 2.4852], rtol=0, atol=1e-15)
    changes = []
    if choice == 'baseline_slope634':
        b = model.beams[0]
        d = b.distributions['dCLda']
        supplied = donor.beams[0].value('dCLda', 10*d.t)
        assert np.all(supplied == 6.34)
        changes.append(dict(beam=b.index, field='dCLda', before=d.values.tolist(), after=supplied.tolist()))
        b.distributions['dCLda'] = Distribution('dCLda', d.t.copy(), supplied.copy(), d.line)
    if choice == 'upper_minus4':
        for b in model.beams[1:]:
            d = b.distributions['twist']
            assert np.all(d.values == 4.)
            changes.append(dict(beam=b.index, field='twist', before=d.values.tolist(), after=(-d.values).tolist()))
            b.distributions['twist'] = Distribution('twist', d.t.copy(), -d.values, d.line)
    return model, dict(source=str(path.relative_to(ROOT)), variant=variant,
                       reference_before=before.tolist(), reference_after=model.reference.tolist(),
                       normalization_donor=str(CANT.relative_to(ROOT)), changes=changes,
                       source_joint_correction=choice.startswith('upper'),
                       dimensional_forces_compared=False)


def check(plan):
    for name, digest in plan['pins'].items():
        assert sha(ROOT/name) == digest, name


def prepare(out):
    assert not out.exists(), out
    cases = [dict(id=f'{choice}-a{alpha}-pg0', choice=choice, alpha=alpha, pg='zero')
             for choice in CHOICES for alpha in (0., 1.)]
    cases += [dict(id=f'{choice}-a1-dynamic', choice=choice, alpha=1., pg='dynamic')
              for choice in ('baseline_slope634', 'upper_plus4')]
    files = list((ROOT/'openswing').glob('*.py'))
    files += [Path(__file__), ROOT/'scripts/verify-sa11-avl-baseline.py',
              ROOT/'scripts/audit-sa11-avl-conversion.py', ROOT/'scripts/verify-avl-matched-fields.py',
              BASE.BINARY, BASE.BINARY.parent/'build.json',
              ROOT/'examples/isae-sa11-wingtip-up.asw', ROOT/'examples/isae-sa11-winglet-sources.json',
              ROOT/'reference/aswing_doc.txt', ROOT/'docs/validation/ISAE_STATUS.md',
              ROOT/'docs/validation/isae-progress-scopes.json', ROOT/'docs/validation/isae-progress/history.json',
              ROOT/'artifacts/isae/sa11-speed-signature-20261108/analysis.json',
              ROOT/'docs/validation/aswing-authoritative-sources.json']
    files += [p for p in SOURCE.rglob('*') if p.suffix in ('.asw', '.txt', '.sh')]
    catalog = read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:
        if item['id'] in ('isae-part-1', 'drela-steady'):
            assert sha(ROOT/item['local_pdf']) == item['sha256']
            files.append(ROOT/item['local_pdf'])
    assert sha(BASE.BINARY) == read(BASE.BINARY.parent/'build.json')['binary_sha256']
    models = {choice: model_for(choice)[1] for choice in CHOICES}
    pins = {str(p.relative_to(ROOT)): sha(p) for p in files}
    out.mkdir(parents=True)
    plan = dict(observed_utc=utc(), cases=cases, pins=pins, models=models,
                previous_goal_turn='progress: length-allocation hypothesis tested and rejected; original speed dependence supports different global PG choices',
                protocol='Ten zeroPG native solves, each followed by serial production255/266m/s calls reusing frozen matrices and scaled circulation. Two dynamicPG255 controls. Alpha0/1 predeclared. Native/production share exact source endpoints and receivers. Production stall/local Mach guards retained.',
                normalization='One-tenth cant0 reference dimensions:0.9767,0.37874,2.4852. Physical source geometries stay at supplied small scale. Coefficients only; original full-scale geometry, density and settings are not authenticated.',
                alternatives='Original baseline slope7, independently supplied6.34, original extension, literal+4 upper twist and report-derived-4. No fitted coefficients, core, mesh selection or parameter search.',
                limitations='Native AVL lacks ASWING profile/stall/section-moment laws. Compare vortex lift,CDi,efficiency separately from total drag/Cm. Cm archive mapping uses body origin. Fixed zeroPG is a hypothesis, not a recovered startup setting. No primary pass or scope change.')
    check(plan)
    write(out/'plan.json', plan)
    (out/'driver-used.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(prepared=True, native_cases=len(cases), production_calls=22, models=models)), flush=True)


def production(model, meshes, condition, frozen, folder, seed):
    begin = time.monotonic()
    try:
        result = evaluate_aerodynamics(model, condition, meshes, frozen_influences=frozen,
                                       initial_circulation=seed)
        write(folder/'openswing.json', result)
        gamma = np.array([s['circulation'] for s in result['strips']])
        velocity = np.array([s['relative_velocity'] for s in result['strips']])
        cl = np.array([s['cl'] for s in result['strips']])
        state = dict(status='computed', residual=result['residual'], maximum=result['lifting_airflow']['maximum'])
        values = {k: result[k] for k in ('CL', 'CD', 'CDi', 'efficiency')}
        values['Cm'] = result['Cm_origin']
    except AnalysisError as exc:
        assert exc.details and exc.details['kind'] == 'section_normal_mach', str(exc)
        tb = exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name != 'evaluate_aerodynamics':
            tb = tb.tb_next
        assert tb is not None
        local = tb.tb_frame.f_locals
        gamma, velocity, cl = [local[k].copy() for k in ('gamma', 'v', 'cl')]
        state = dict(status='rejected', residual=exc.details['circulation_residual'],
                     maximum=exc.details['maximum'], details=exc.details, error=str(exc))
        write(folder/'openswing-rejected.json', state)
        values = None
    margins, offset = [], 0
    for mesh in meshes:
        end = offset+len(mesh.tm)
        margins.extend(np.minimum(mesh.beam.value('CLmax', mesh.tm)-cl[offset:end],
                                  cl[offset:end]-mesh.beam.value('CLmin', mesh.tm)))
        offset = end
    state.update(minimum_stall_margin_widths=float(min(margins)/.05),
                 stalled_strips=int(np.sum(np.asarray(margins)<0)), seconds=time.monotonic()-begin)
    np.savez(folder/'state.npz', gamma=gamma, velocity=velocity, cl=cl, stall_margin=margins)
    return state, values, gamma, velocity


def run(out, index):
    plan = read(out/'plan.json'); check(plan)
    case = plan['cases'][index]
    folder = out/case['id']; folder.mkdir()
    model, choice = model_for(case['choice'])
    assert choice == plan['models'][case['choice']]
    write(folder/'input-choice.json', choice)
    refinement = 1 if case['choice'].startswith('upper') else 2
    text, segments = BASE.CONVERT.conversion(model, refinement)
    mach = 0. if case['pg'] == 'zero' else 255/model.constants[2]
    lines = text.splitlines(); lines[1] = f'{mach:.17g}'
    (folder/'model.avl').write_text('\n'.join(lines)+'\n')
    commands = f"LOAD model.avl\nOPER\nO\nA\n\nA A {case['alpha']}\nX\nMRF\nFT total.txt\nFS strips.txt\nFSB body-strips.txt\nFE elements.txt\n\nQUIT\n"
    (folder/'commands.txt').write_text(commands)
    begin = time.monotonic()
    p = subprocess.run([str(BASE.BINARY)], input=commands, capture_output=True, text=True, cwd=folder, timeout=25)
    (folder/'stdout.txt').write_text(p.stdout); (folder/'stderr.txt').write_text(p.stderr)
    write(folder/'process.json', dict(returncode=p.returncode, seconds=time.monotonic()-begin, observed_utc=utc()))
    assert p.returncode == 0, p.stderr
    fields = BASE.CONVERT.MATCHED.read_fields(folder/'elements.txt')
    np.savez(folder/'native-fields.npz', **fields)
    meshes, geometry, errors, settings = BASE.CONVERT.mapped_meshes(model, fields, segments)
    assert len(fields['GAM']) == 64
    write(folder/'mapped-mesh.json', dict(geometry_errors=errors, settings=settings, segments=segments))
    labels = BASE.CONVERT.MATCHED.NATIVE.labeled(folder/'total.txt')
    assert abs(labels['Mach, rb/2V, r\'b/2V'][0]-mach) < 1e-14
    ff = labels['Trefftz Plane: CLff, CDff, CYff, e']
    native = dict(CL=labels['CLtot'][0], CDi=ff[1], efficiency=ff[3], CD_near=labels['CDvis, CDind'][1])
    frozen = FrozenInfluences(model, meshes)
    states, previous, previous_speed = [], None, None
    for speed in ([255., 266.] if case['pg'] == 'zero' else [255.]):
        sub = folder/f'u{int(speed)}'; sub.mkdir()
        condition = FlightCondition(speed=speed, alpha=case['alpha'], density=model.constants[1],
                                    mach=0. if case['pg'] == 'zero' else None, freeze_influences=True)
        write(sub/'condition.json', asdict(condition))
        cached = dict(frozen.cache)
        seed = None if previous is None else previous*(speed/previous_speed)
        def expired(*args):
            raise TimeoutError('SA11 production diagnostic exceeded15seconds')
        signal.signal(signal.SIGALRM, expired); signal.alarm(15)
        try:
            state, values, gamma, velocity = production(model, meshes, condition, frozen, sub, seed)
        finally:
            signal.alarm(0)
        unchanged_cache = all(frozen.cache.get(key) is value for key, value in cached.items())
        assert unchanged_cache
        gamma_scaling_error = None if previous is None else float(np.max(abs(gamma/speed-previous/previous_speed)))
        ng = fields['GAM'].ravel()
        state.update(speed=speed, values=values,
                     native_gamma_relative_linf=float(np.max(abs(gamma/speed-ng))/np.max(abs(ng))),
                     retained_cached_arrays=len(cached), cached_arrays_reused=unchanged_cache,
                     normalized_gamma_speed_change=gamma_scaling_error)
        label = '0_75' if speed == 255 else '0_78'
        dirname = 'Wing_tip_up' if choice['variant'] == 'wingtip_up' else choice['variant']
        raw = np.loadtxt(SOURCE/dirname/f'{choice["variant"]}_Ma_{label}.txt')
        rows = raw[raw[:,71] == case['alpha']]; assert rows.shape == (1,82)
        state['reference'] = {key: float(rows[0,col]) for key,col in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
        state['native_error_percent'] = {k:100*(native[k]/state['reference'][k]-1) for k in ('CL','CDi','efficiency')}
        state['production_error_percent'] = None if values is None else {k:100*(v/state['reference'][k]-1) for k,v in values.items()}
        state['artifact_sha256'] = {p.name:sha(p) for p in sub.iterdir() if p.is_file()}
        write(sub/'report.json', state)
        states.append(state); previous, previous_speed = gamma, speed
    check(plan)
    report = dict(observed_utc=utc(), case=case, native=native, native_totals=labels,
                  geometry_errors=errors, production=states, reference_dimensions=model.reference[0].tolist(),
                  artifact_sha256={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()},
                  accepted_primary_checks=0, original_setup_authenticated=False)
    write(folder/'report.json', report)
    print(json.dumps(dict(case=case, native=native, results=[{
        k:r[k] for k in ('speed','status','maximum','native_error_percent','production_error_percent',
                         'minimum_stall_margin_widths','native_gamma_relative_linf','normalized_gamma_speed_change')}
        for r in states])), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--output', type=Path, required=True)
    group = ap.add_mutually_exclusive_group(required=True); group.add_argument('--prepare', action='store_true'); group.add_argument('--case', type=int)
    args = ap.parse_args()
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    if args.prepare:
        prepare(args.output.resolve())
    else:
        run(args.output.resolve(), args.case)


if __name__ == '__main__':
    main()
