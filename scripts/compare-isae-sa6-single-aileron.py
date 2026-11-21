"""Match NACA SA-6 combined tables using separate single-aileron calculations.

Both wings remain present. Positive physical deflection raises only the right
aileron; negative deflection lowers it. Combined roll/yaw is C(up)-C(down),
the observable defined by TR298/TR343, rather than a simultaneous-control solve.
Original inputs, historical simultaneous calculations and thresholds are kept.
"""
from pathlib import Path
import csv
import copy
import hashlib
import importlib.util
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from openswing.aero import FlightCondition, solve_rigid, AnalysisError
from openswing.asw import Distribution
from openswing.geometry import model_meshes
from isae_sa6_reference import CACHE, primary_tables

SPEC = importlib.util.spec_from_file_location('sa6_verifier', ROOT / 'scripts/verify-isae-sa6.py')
OLD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OLD)
DEST = ROOT / 'docs/validation'
SHA = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def one_aileron(source, reconstructed=False):
    model = OLD.model_for(source, reconstructed)
    beam = model.beams[0]
    sign = -float(np.sign(beam.value('dCLdF1', .7)))
    changes = {}
    for key in ('dCLdF1', 'dCMdF1', 'dCDdF1'):
        if key not in beam.distributions:
            continue
        old = beam.distributions[key]
        assert old.t[0] < 0 < old.t[-1], 'Expected explicitly two-sided control table'
        new = old.values.copy()
        new[old.t < 0] = 0
        beam.distributions[key] = Distribution(old.name, old.t.copy(), new, old.line)
        changes[key] = dict(t=old.t.tolist(), original=old.values.tolist(), right_only=new.tolist())
    assert sign in (-1, 1)
    assert np.all(beam.value('dCLdF1', np.linspace(-.76, -.001, 51)) == 0)
    assert sign * beam.value('dCLdF1', .7) < 0
    return model, sign, changes


def compute(model, sign, spec):
    condition = FlightCondition(speed=20, alpha=spec['body_pitch_deg'], mach=0.,
                                controls={1: sign * spec['right_deflection_deg']},
                                freeze_influences=False)
    r = solve_rigid(model, condition, panels=spec['panels'])
    assert r['converged'] and r['residual'] < 1e-8
    strips = r['strips']
    force = np.array([s['force'] for s in strips])
    position = np.array([s['position'] for s in strips])
    section_moment = np.array([s['moment'] for s in strips])
    moment = np.cross(position - model.reference[1], force) + section_moment
    qS = .5 * model.constants[1] * 20 ** 2 * model.reference[0, 0]
    qSb = qS * model.reference[0, 2]
    check = max(abs(-moment[:, 0].sum() / qSb - r['Cl']),
                abs(-moment[:, 2].sum() / qSb - r['Cn']),
                np.max(abs(force.sum(axis=0) - r['force'])) / qS)
    assert check < 2e-10
    # This straight steady wing has span axis (0,1,0), zero point aero loads
    # and zero apparent/rate force. Separate circulatory and profile moments
    # using the returned fields without changing or re-solving the equations.
    velocity = np.array([s['relative_velocity'] for s in strips])
    gamma = np.array([s['circulation'] for s in strips])
    length = np.array([s['length'] for s in strips])
    lift = model.constants[1] * (gamma * length)[:, None] * np.cross(velocity, [0., 1., 0.])
    assert np.max(abs(np.asarray(r['apparent_force']))) < 1e-12
    assert np.max(abs(np.asarray(r['circulation_rate_force']))) < 1e-12
    assert np.max(abs(section_moment[:, [0, 2]])) < 1e-12
    contributions = {}
    for label, forces in [('circulatory', lift), ('profile', force-lift)]:
        m = np.cross(position-model.reference[1], forces).sum(axis=0)
        contributions[label] = dict(Cl=float(-m[0]/qSb), Cn=float(-m[2]/qSb))
    assert max(abs(sum(v[k] for v in contributions.values())-r[k])
               for k in ('Cl', 'Cn')) < 2e-10
    return dict(**{k: float(r[k]) for k in ('Cl', 'Cn', 'CL', 'CD', 'Cm', 'residual')},
                actual_strips=len(strips), F1=sign*spec['right_deflection_deg'],
                independent_wrench_error=float(check), moment_contributions=contributions,
                force=r['force'], moment=r['moment'])


def stats(rows, predicted, observed, key):
    if not rows:
        return None
    error = np.array([r[predicted][key]-r[observed][key] for r in rows])
    return dict(count=len(error), bias=float(error.mean()), rmse=float(np.sqrt(np.mean(error**2))),
                maximum_absolute_error=float(np.max(abs(error))))


def main():
    sources = json.loads((DEST/'isae-sa6-sources.json').read_text())
    simultaneous = json.loads((DEST/'isae-sa6-current.json').read_text())
    original_primary = primary_tables()
    assert original_primary == sources['primary']
    primary = copy.deepcopy(original_primary)
    single_primary = json.loads((DEST/'isae-sa6-single-primary.json').read_text())
    corrections = [r for r in single_primary['combined_visual_review']['cases']
                   if r['classification'] == 'existing_combined_transcription_error']
    assert len(corrections) == 3
    for correction in corrections:
        row = next(r for r in primary if r['id'] == '20b_35c'
                   and r['body_alpha'] == correction['body_pitch_deg'])
        i = row['delta'].index(correction['delta_deg'])
        assert abs(row['CN_tail_body'][i]-float(correction['existing_transcription'])) < 5e-17
        row['CN_tail_body'][i] = float(correction['visually_printed_combined'])
        row['Cn_body'][i] = row['CN_tail_body'][i] * 25 / 60
    # The current baseline is reused only with its unchanged numerical sources.
    for name, digest in simultaneous['plan']['source_sha256'].items():
        assert SHA(ROOT/name) == digest, 'Baseline source changed: '+name
    paths = [Path(__file__), ROOT/'scripts/verify-isae-sa6.py',
             ROOT/'scripts/isae_sa6_reference.py', DEST/'isae-sa6-sources.json',
             DEST/'isae-sa6-current.json', DEST/'isae-sa6-single-primary.json',
             *sorted((ROOT/'openswing').glob('*.py'))]
    pins = {str(p.relative_to(ROOT)): SHA(p) for p in paths}
    for entry in sources['models']:
        p = CACHE/entry['path']
        assert SHA(p) == entry['sha256']
        pins[str(p.relative_to(ROOT))] = SHA(p)
    plan = dict(source_sha256=pins, requested_states=966, panels=[80, 160],
                body_pitch_deg=[0, 8, 12], absolute_deflection_deg=list(range(4, 45, 4)),
                observable='C(single right up)-C(single right down); other aileron neutral',
                speed=20, pg_mach=0, frozen_influences=False,
                original_gates=dict(residual=1e-8, wrench_error=2e-10, neutral_coefficient_identity=2e-10),
                experimental_acceptance_threshold=None, mesh_acceptance_threshold=None)
    identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/isae-sa6-single-aileron'/identity
    cache.mkdir(parents=True, exist_ok=True)
    write(cache/'plan.json', plan)
    states, combined, metadata = [], [], []
    lookup = {}
    old = {(r['specification']['case'], r['specification']['panels'],
            r['specification']['alpha'], r['specification']['delta']): r
           for r in simultaneous['cases']}
    new_count = reused_count = 0
    for entry in sources['models']:
        reconstructed = entry['id'] == '10b_25c'
        case = entry['id']+('_reconstructed' if reconstructed else '_literal')
        source = (CACHE/entry['path']).read_text()
        model, sign, changes = one_aileron(source, reconstructed)
        base_model = OLD.model_for(source, reconstructed)
        geometry_checks = 0
        for panels in plan['panels']:
            before, after = model_meshes(base_model, panels), model_meshes(model, panels)
            assert len(before) == len(after) == 1
            for key in ('t0', 't1', 'tm', 'r0', 'r1', 'rm', 'frames', 'length', 'ts'):
                np.testing.assert_array_equal(getattr(before[0], key), getattr(after[0], key))
                geometry_checks += 1
            for alpha in plan['body_pitch_deg']:
                for delta in [0]+[s*d for d in plan['absolute_deflection_deg'] for s in (1, -1)]:
                    spec = dict(case=case, panels=panels, body_pitch_deg=alpha,
                                right_deflection_deg=delta)
                    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
                    path = cache/(key+'.json')
                    if path.exists():
                        row = json.loads(path.read_text())
                        assert row['specification'] == spec and row['identity'] == identity
                        reused_count += 1
                    else:
                        started = time.monotonic()
                        try:
                            row = dict(status='computed', result=compute(model, sign, spec))
                        except AnalysisError as exc:
                            row = dict(status='rejected', error=str(exc))
                        row.update(specification=spec, identity=identity, seconds=time.monotonic()-started)
                        write(path, row)
                        new_count += 1
                    states.append(row)
                    lookup[case, panels, alpha, delta] = row
                neutral = lookup[case, panels, alpha, 0]
                assert neutral['status'] == 'computed'
                error = max(abs(neutral['result'][k]-old[case, panels, alpha, 0]['result'][k])
                            for k in ('Cl', 'Cn', 'CL', 'CD', 'Cm'))
                assert error < 2e-10
                print(f'{case}: N={panels}, pitch={alpha}: 23 single-control states; neutral error {error:.3g}', flush=True)
                ref = next(r for r in primary if r['id'] == entry['id'] and r['body_alpha'] == alpha)
                old_ref = next(r for r in original_primary if r['id'] == entry['id'] and r['body_alpha'] == alpha)
                for i, delta in enumerate(ref['delta'][1:], 1):
                    up, down = lookup[case, panels, alpha, delta], lookup[case, panels, alpha, -delta]
                    pair = dict(case=case, panels=panels, body_pitch_deg=alpha, deflection_deg=delta,
                        reference=dict(Cl=ref['Cl_body'][i], Cn=ref['Cn_body'][i]),
                        original_reference=dict(Cl=old_ref['Cl_body'][i], Cn=old_ref['Cn_body'][i]),
                        simultaneous={k: old[case, panels, alpha, delta]['result'][k] for k in ('Cl', 'Cn')},
                        status='computed' if up['status'] == down['status'] == 'computed' else 'unavailable')
                    if pair['status'] == 'computed':
                        pair['matched'] = {k: up['result'][k]-down['result'][k] for k in ('Cl', 'Cn')}
                        pair['single_up'] = {k: up['result'][k]-neutral['result'][k] for k in ('Cl', 'Cn')}
                        pair['single_down'] = {k: down['result'][k]-neutral['result'][k] for k in ('Cl', 'Cn')}
                        pair['combined_moment_contributions'] = {
                            part: {k: up['result']['moment_contributions'][part][k]
                                   -down['result']['moment_contributions'][part][k] for k in ('Cl', 'Cn')}
                            for part in ('circulatory', 'profile')}
                    combined.append(pair)
        metadata.append(dict(case=case, model_sha256=entry['sha256'],
                             control_changes=changes, exact_geometry_checks=geometry_checks))
    assert len(states) == 966 and len(combined) == 462
    assert all(SHA(ROOT/p) == h for p, h in pins.items()), 'Source changed during run'
    comparisons, meshes = [], []
    for case in [r['case'] for r in metadata]:
        for alpha in plan['body_pitch_deg']:
            rows = [r for r in combined if r['case'] == case and r['body_pitch_deg'] == alpha
                    and r['panels'] == 160 and r['status'] == 'computed']
            comparisons.append(dict(case=case, body_pitch_deg=alpha, requested=11, completed=len(rows),
                matched_errors={k: stats(rows, 'matched', 'reference', k) for k in ('Cl', 'Cn')},
                previous_simultaneous_errors={k: stats(rows, 'simultaneous', 'reference', k) for k in ('Cl', 'Cn')},
                observable_change={k: stats(rows, 'matched', 'simultaneous', k) for k in ('Cl', 'Cn')}))
            pair_rows = []
            for fine in rows:
                coarse = next(r for r in combined if r['case'] == case and r['body_pitch_deg'] == alpha
                              and r['panels'] == 80 and r['deflection_deg'] == fine['deflection_deg'])
                if coarse['status'] == 'computed':
                    pair_rows.append(dict(coarse=coarse['matched'], fine=fine['matched']))
            meshes.append(dict(case=case, body_pitch_deg=alpha, completed=len(pair_rows),
                difference={k: stats(pair_rows, 'coarse', 'fine', k) for k in ('Cl', 'Cn')}))
    single_rows, single_comparisons = [], []
    for ref in single_primary['series']:
        case, alpha = '20b_35c_literal', ref['body_pitch_deg']
        for direction, sign in [('up', 1), ('down', -1)]:
            for panels in plan['panels']:
                neutral = lookup[case, panels, alpha, 0]['result']
                group = []
                for i, delta in enumerate(ref['delta_deg'][1:], 1):
                    state = lookup[case, panels, alpha, sign*delta]
                    row = dict(case=case, panels=panels, body_pitch_deg=alpha, direction=direction,
                        deflection_deg=delta, status=state['status'], source=ref['source'],
                        reference=dict(Cl=ref['Cl_'+direction][i], Cn=ref['CN_tail_'+direction][i]*25/60))
                    if state['status'] == 'computed':
                        row['prediction'] = {k: state['result'][k]-neutral[k] for k in ('Cl', 'Cn')}
                        group.append(row)
                    single_rows.append(row)
                single_comparisons.append(dict(case=case, panels=panels, body_pitch_deg=alpha,
                    direction=direction, requested=11, completed=len(group),
                    errors={k: stats(group, 'prediction', 'reference', k) for k in ('Cl', 'Cn')}))
    report = dict(status='MATCHED_OBSERVABLE_COMPARISON', full_suite_validated=False,
                  identity=identity, plan=plan, models=metadata, states=states, combined=combined,
                  comparisons=comparisons, mesh_comparisons=meshes,
                  reviewed_reference_corrections=corrections,
                  primary_internal_conflicts=[r for r in single_primary['combined_visual_review']['cases']
                                              if r['classification'] == 'primary_table_internal_inconsistency'],
                  single_aileron_rows=single_rows, single_aileron_comparisons=single_comparisons,
                  accounting=dict(requested=966, computed=sum(r['status']=='computed' for r in states),
                                  newly_computed=new_count, reused=reused_count,
                                  neutral_states=42, combined_locations_per_mesh=231),
                  limitations=['Primary combined values are sums of separately faired single-control observations.',
                      '20m/s is the archived numerical setting; the primary tables combine three tunnel speeds.',
                      'Wing-only geometry, constant section inputs and original simplified stall/drag laws remain.',
                      'No coefficients or tolerances were fitted; no production equations changed.',
                      'Original simultaneous results remain a separate nonlinear observable.'])
    write(DEST/'isae-sa6-single-aileron.json', report)
    with (DEST/'isae-sa6-single-aileron.csv').open('w', newline='') as stream:
        fields = ['case', 'panels', 'body_pitch_deg', 'deflection_deg', 'status',
                  'Cl_reference', 'Cn_reference', 'Cl_matched', 'Cn_matched', 'Cl_simultaneous', 'Cn_simultaneous']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in combined:
            out = {k: row[k] for k in fields[:5]}
            for kind in ('reference', 'matched', 'simultaneous'):
                for k in ('Cl', 'Cn'):
                    out[k+'_'+kind] = row.get(kind, {}).get(k)
            writer.writerow(out)
    print(json.dumps(report['accounting']), flush=True)


if __name__ == '__main__':
    main()
