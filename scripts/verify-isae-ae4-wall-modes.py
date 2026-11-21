"""One declared AE-4 wall-mounted flutter anchor, with original files retained.

This is a conditional comparison, not a registration or a flutter-boundary pass.
The original stack's initial point and historical .set/.pnt state are unknown.
Run one mesh at a time; the caller supplies the process memory/time limits.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT/'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865'
FAMILY = REFERENCE/'4 - Aeroelasticity/AE - Aeroelastic Cases/AE-4-D Pazy Wing - Flutter boundaries'
ORIGINAL = FAMILY/'2-Flutter_Undeformed'


def pin(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=digest)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Full fine-grid matrices can be large. Stream the identical JSON encoding
    # instead of retaining both millions of formatting fragments and a string.
    with path.open('w') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def original_rows(path):
    result = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        fields = line.split()
        if not fields or not fields[0].isdigit():
            continue
        values = [float(v.replace('D', 'E')) for v in fields]
        result.append(dict(line=number, tokens=fields, values=values))
    return result


def declared_targets(driver, native, speed):
    """Bind a commanded IAS to the literal insertion stack, never by fit."""
    if type(speed) is not int or not 1 <= speed <= 108:
        raise ValueError('Choose an original commanded IAS from 1 through 108; initial and terminal modal points are unresolved.')
    commands = [line.strip().lower() for line in driver.splitlines() if line.strip()]
    assert commands[commands.index('nodes')+1] == 'i 40'
    assert commands[commands.index('g')+1:commands.index('g')+3] == ['1', '0 0 1']
    assert commands[commands.index('%')+1] == 'd'
    assert commands[commands.index('nn')+1:commands.index('nn')+3] == ['4', '0 200']
    speeds = [float(line.split()[1]) for line in commands if line.startswith('!v ')]
    assert speeds == list(range(1, 110)) and commands.count('+') == 109
    index = 1
    stack = []
    for command in commands:
        if command == '+':
            index += 1
        elif command.startswith('!v '):
            stack.append((index, float(command.split()[1])))
    assert stack == [(v+1, v) for v in range(1, 110)]
    targets = [r for r in native if r['values'][0] == speed+1]
    if not targets:
        raise ValueError('The declared original index has no archived roots.')
    return targets


def compare_roots(modes, targets, *, classifications=None):
    """Retain every native root; only bind complete positive-frequency sets.

    A real native pole has no authenticated branch identity in the current
    anchor comparison. It stays unavailable instead of shifting the frequency
    ordinal or being matched to the nearest predicted value.
    """
    unresolved = False
    if classifications is None:
        actual = [m['eigenvalue'] for m in modes if m['eigenvalue'][1] > 0]
    else:
        kinds = {'certified_real', 'positive_frequency', 'negative_frequency', 'unresolved_near_real'}
        if len(classifications) != len(modes) or any(
                c.get('mode_index') != i or c.get('eigenvalue') != mode['eigenvalue']
                or c.get('classification') not in kinds
                for i, (c, mode) in enumerate(zip(classifications, modes))):
            raise ValueError('Root classification must describe the same complete selected spectrum.')
        unresolved = any(c['classification'] == 'unresolved_near_real' for c in classifications)
        actual = [mode['eigenvalue'] for mode,c in zip(modes,classifications)
                  if c['classification'] == 'positive_frequency']
    actual = sorted(actual, key=lambda x:x[1])
    positive = sorted((r for r in targets if r['values'][2] > 0), key=lambda r:r['values'][2])
    pairing = ({r['line']:v for r,v in zip(positive,actual)}
               if not unresolved and len(actual)==len(positive) and len({r['values'][2] for r in positive})==len(positive) else {})
    comparison = []
    for i, target in enumerate(targets):
        row = dict(ordinal=i+1, original=target, status='unavailable',
                   unavailable_reason='Real-pole branch identity or complete positive-frequency set is unresolved.')
        if target['line'] in pairing:
            values = pairing[target['line']]
            expected = target['values'][1:]
            strict = [abs(Decimal.from_float(float(v))-Decimal(t)) <= Decimal(10)**Decimal(t).as_tuple().exponent/2
                      for v,t in zip(values,target['tokens'][1:])]
            row.update(status='computed',actual=values,
                relative_error_percent=[100*abs(v-e)/abs(e) if e else None for v,e in zip(values,expected)],
                printed_precision=strict)
            row.pop('unavailable_reason')
        comparison.append(row)
    return comparison


def prepare(folder, panels, speed=40):
    if folder.exists():
        raise ValueError('Use a new folder; earlier attempts must be retained.')
    driver = (ORIGINAL/'alpha_0.sh').read_text()
    native = original_rows(ORIGINAL/'alpha_0_eig.txt')
    sensor = original_rows(ORIGINAL/'aswing_alpha_0.txt')
    # Literal '+' stack: initial point 1, first explicitly commanded speed at 2.
    # This correspondence is declared prospectively, never selected by error.
    index = speed+1
    targets = declared_targets(driver,native,speed)
    original_sources = [pin(ORIGINAL/name) for name in
                        ('Pazy_wing.asw','alpha_0.sh','alpha_0_eig.txt','aswing_alpha_0.txt')]
    manifest_path = REFERENCE.parent/'manifest.json'
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['revision'] == REFERENCE.name
    for item in original_sources:
        relative = (ROOT/item['path']).relative_to(REFERENCE).as_posix()
        assert all(item[key] == manifest['files'][relative][key] for key in ('sha256','bytes'))
    request = dict(action='modes', source=(ORIGINAL/'Pazy_wing.asw').read_text(),
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
        panels=dict(default=panels, beams={'1': dict(count=panels, spacing='cosine')}),
        condition=dict(speed=speed, alpha=0., beta=0., density=1.23, mach=0.,
            gravity_magnitude=9.81, ground_effect=1, ground_normal=[0., 0., 1.],
            position_earth=[0., 0., 0.], attitude=[0., 0., 0.], rates=[0., 0., 0.],
            acceleration=[0., 0., 0.], angular_acceleration=[0., 0., 0.],
            circulation_modes={'1': 0}, freeze_influences=False, aero_lag=True,
            wake_core_ratio=.25, stall=True, stall_factor=40., stall_width=.05),
        modes=dict(frame='fixed', count=4, shift=[0., 200.], method='full_shift_invert',
            tolerance=1e-9, step=1e-5, rank_tolerance=1e-9, matrices=True))
    files = [p for p in FAMILY.rglob('*') if p.is_file()]
    inventory = [pin(p) for p in sorted(files)]
    plan = dict(status='prepared', original_driver=pin(ORIGINAL/'alpha_0.sh'),
        original_model=pin(ORIGINAL/'Pazy_wing.asw'), native_output=pin(ORIGINAL/'alpha_0_eig.txt'),
        inventory=inventory, nominal_intervals=panels, IAS=speed, TAS=speed,
        speed_scope='Density equals the file sea-level reference; IAS equals TAS.',
        declared_native_index=index, targets=targets,
        original_plus_count=109, literal_stack_points=110,
        original_sources=original_sources, reference_manifest=pin(manifest_path),
        sensor_rows=len(sensor), native_roots=len(native),
        native_indices=sorted({int(r['values'][0]) for r in native}),
        autoload_candidates=[pin(p) for p in sorted(files) if p.suffix.lower() in ('.set', '.pnt', '.con')],
        kernel_pins=[pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))],
        helper=pin(Path(__file__)),
        comparison_helper=pin(ROOT/'scripts/isae_modal_classification.py'),
        pencil_helper=pin(ROOT/'scripts/isae_pencil_actions.py'), native_passes_credited=0,
        qualification=[
            'OPER % D exits the constraint editor; it does not select anchored defaults.',
            'Fixed frame, alpha0, identity pose, sea-level density, PG0, pointwise circulation, lag enabled and updated influences are declared current settings, not recovered historical settings.',
            'Original NN4 with shift 0+200i is retained. It is a local eigenvalue search, not a frequency range or full spectrum.',
            'Original I40 has unknown historical spacing/count bookkeeping. Current meshes retain the material jump and every active attachment.',
            'Literal + stack implies index=IAS+1; the author MATLAB plot instead labels the operating index itself as speed.',
            'The sensor file contains 110 points, but modal output only indices1..109. The missing terminal point and initial settings remain unresolved.',
            'Positive selected frequencies are compared in ascending order. No native mode-shape correspondence has been established.',
            'Near-real predicted poles require phase-real left/right vectors and independent real-pencil certificates before exclusion from the positive-frequency ordinal set. All returned poles and all native targets remain retained.',
            'No original model bytes, stiffness, masses, sensor positions, tolerances or targets are fitted.'])
    write(folder/'request.json', request)
    write(folder/'plan.json', plan)
    return request, plan


def run(folder, panels, *, speed=None, assess_only=False):
    if assess_only:
        request, plan = (json.loads((folder/name).read_text()) for name in ('request.json', 'plan.json'))
        if speed is not None and speed != plan['IAS']:
            raise ValueError('Assessment must retain the saved declared speed.')
    else:
        request, plan = prepare(folder, panels, 40 if speed is None else speed)
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.bridge import dispatch
    from scripts.isae_modal_classification import classify_modes
    from scripts.isae_pencil_actions import pencil_residuals,real_pencil,matrix_norm
    started = time.monotonic()
    if not assess_only:
        write(folder/'started.json', dict(time=time.time(), request=pin(folder/'request.json')))
    progress_last = [0.]
    def progress(*args):
        now = time.monotonic()
        if now-progress_last[0] >= 5:
            print(json.dumps(dict(progress=args, seconds=now-started)), flush=True)
            progress_last[0] = now
    try:
        if assess_only:
            result = json.loads((folder/'result.json').read_text())
            timing = folder/'solve-timing.json'
            elapsed = json.loads(timing.read_text())['seconds'] if timing.exists() else None
        else:
            result = dispatch(request, progress=progress)
            elapsed = time.monotonic()-started
            write(folder/'solve-timing.json', dict(seconds=elapsed))
            write(folder/'result.json', result)
        checks = []
        def check(name, passed, **values):
            checks.append(dict(name=name, passed=bool(passed), **values))
        base = result['base']; diagnostic = result['diagnostics']
        check('fresh base residual', diagnostic['base_residual'] <= 1e-7,
              maximum=diagnostic['base_residual'])
        check('solid wall preserved', base['ground_plane']['flag'] == 1 and bool(base['ground_plane']['wall_roots']))
        check('local count and shift preserved', diagnostic['requested_count'] == 4 and diagnostic['shift'] == [0., 200.])
        check('literal model retained', request['source'] == (ORIGINAL/'Pazy_wing.asw').read_text())
        check('source pins unchanged', all(pin(ROOT/p['path']) == p for p in plan['kernel_pins']))
        if 'original_sources' in plan:
            check('archived source pins unchanged', all(pin(ROOT/p['path']) == p
                for p in plan['original_sources']+[plan['reference_manifest']]))
        if 'comparison_helper' in plan:
            check('comparison helper unchanged', pin(ROOT/plan['comparison_helper']['path']) == plan['comparison_helper'])
        if 'pencil_helper' in plan:
            check('pencil helper unchanged', pin(ROOT/plan['pencil_helper']['path']) == plan['pencil_helper'])
        a, m = real_pencil(result['matrices'])
        norm_a, norm_m = matrix_norm(a), matrix_norm(m)
        def complex_vector(value):
            return np.asarray(value['real'])+1j*np.asarray(value['imag'])
        for i, mode in enumerate(result['modes']):
            lam = complex(*mode['eigenvalue'])
            right, left = (complex_vector(mode[k]) for k in ('right', 'left'))
            rr, lr, pair = pencil_residuals(a,m,lam,right,left)
            er = np.linalg.norm(rr)/((norm_a+abs(lam)*norm_m)*np.linalg.norm(right))
            el = np.linalg.norm(lr)/((norm_a+abs(lam)*norm_m)*np.linalg.norm(left))
            check(f'mode {i+1} complete pencil', max(er, el) <= 1e-8, right=float(er), left=float(el))
            check(f'mode {i+1} mass normalization', abs(pair-1) <= 1e-6, defect=float(abs(pair-1)))
        classifications = classify_modes(result['modes'],a,m,shift=request['modes']['shift'],
                                          characteristic_rate=diagnostic['time_scale'])
        comparison = compare_roots(result['modes'],plan['targets'],classifications=classifications)
        report = dict(status='computed' if all(c['passed'] for c in checks) else 'check_failure',
            solve_seconds=elapsed, checks=checks, comparison=comparison, native_passes_credited=0,
            selected_eigenvalues=[mode['eigenvalue'] for mode in result['modes']],
            root_classifications=classifications,
            actual_elements=base['structural_elements'], actual_nodes=base['structural_nodes'],
            result=pin(folder/'result.json'), plan=pin(folder/'plan.json'),
            assessment_helper=pin(Path(__file__)), new_solves=0 if assess_only else 1)
        write(folder/'report.json', report)
        print(json.dumps(report), flush=True)
        if report['status'] != 'computed':
            raise ValueError('Retained physical check failure.')
        return result
    except Exception as exc:
        write(folder/('assessment-failure.json' if assess_only else 'failure.json'), dict(type=type(exc).__name__, message=str(exc),
            traceback=traceback.format_exc(), seconds=time.monotonic()-started))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--panels', type=int, choices=(20, 40, 80), default=40)
    parser.add_argument('--speed', type=int, help='Original commanded IAS, 1..108; default 40 for a new run.')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--assess-only', action='store_true')
    args = parser.parse_args()
    if args.prepare_only:
        prepare(args.folder.resolve(), args.panels, 40 if args.speed is None else args.speed)
    else:
        run(args.folder.resolve(), args.panels, speed=args.speed, assess_only=args.assess_only)
