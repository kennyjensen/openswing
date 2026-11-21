"""Retain local fields at a bounded subset of the corrected SA-6 comparison.

The public aerodynamic evaluator and its existing read-only capture hook are
used without equation changes. All five coefficients must reproduce the prior
single-aileron calculation. Saved CP and force-point fields allow a separate
reader to reconstruct the documented sectional loads without an aircraft solve.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.geometry import model_meshes
from openswing.structured_static import IterationFields

spec = importlib.util.spec_from_file_location('single_aileron', ROOT/'scripts/compare-isae-sa6-single-aileron.py')
SINGLE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SINGLE)
DEST = ROOT/'docs/validation'
SHA = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def solve(model, sign, condition_spec, baseline):
    condition = FlightCondition(speed=20, alpha=condition_spec['body_pitch_deg'],
                                mach=0., controls={1: sign*condition_spec['right_deflection_deg']},
                                freeze_influences=False)
    meshes = model_meshes(model, 160)
    fields = IterationFields()
    fields.capture_circulation = True
    started = time.monotonic()
    result = evaluate_aerodynamics(model, condition, meshes, _iteration_fields=fields)
    seconds = time.monotonic()-started
    assert result['converged'] and result['residual'] < 1e-8
    parity = max(abs(result[k]-baseline[k]) for k in ('Cl', 'Cn', 'CL', 'CD', 'Cm'))
    assert parity < 2e-10
    captured = fields.circulation_aero
    p, gamma = captured['p'], captured['gamma']
    assert len(result['strips']) == 164
    assert not captured['engine_rows'] and not captured['bodies']
    assert np.max(abs(captured['lag_rate'])) == 0
    assert np.max(abs(captured['rates'])) == 0
    assert np.max(abs(np.asarray(result['apparent_force']))) == 0
    wind = np.array(captured['direction'])
    locations = {}
    for name in ('cp', 'hv'):
        volume = fields.values['volume', name]
        jet = fields.values['jet', name]
        assert np.max(abs(volume)) == 0 and np.max(abs(jet)) == 0
        free = np.broadcast_to(condition.speed*wind, p[name].shape).copy()
        induced = fields.values['vortex', name].apply(gamma)
        locations[name] = dict(free=free.tolist(), induced=induced.tolist(),
                               velocity=(free+induced).tolist())
    cp_velocity = np.array(locations['cp']['velocity'])
    cp_tangency = np.sum(cp_velocity*p['normal'], axis=1)
    field_error = max(float(np.max(abs(cp_tangency-captured['tangency']))),
                      float(np.max(abs(np.array(locations['hv']['velocity'])-captured['velocity']))))
    assert field_error < 2e-12
    beam = model.beams[0]
    material_names = ('alpha', 'twist', 'chord', 'dCLda', 'dCLdF1', 'CLmin',
                      'CLmax', 'Cdf', 'Cdp', 'dCDdF1', 'Cm', 'dCMdF1', 'Xax')
    raw = dict(parameters={k: v.tolist() for k, v in p.items()},
               material={k: beam.value(k, p['t']).tolist() for k in material_names},
               reference=model.reference.tolist(), density=captured['rho'],
               F1=condition.controls[1], speed=condition.speed,
               stall_factor=condition.stall_factor, stall_width=condition.stall_width,
               cp=locations['cp'], hv=locations['hv'],
               tangency=captured['tangency'].tolist(),
               circulation=gamma.tolist())
    return dict(status='computed', specification=condition_spec, seconds=seconds,
                baseline_coefficient_error=parity, captured_field_error=field_error,
                raw=raw, result=result)


def main():
    baseline_path = DEST/'isae-sa6-single-aileron.json'
    baseline = json.loads(baseline_path.read_text())
    for name, digest in baseline['plan']['source_sha256'].items():
        assert SHA(ROOT/name) == digest, 'Baseline source changed: '+name
    sources = json.loads((DEST/'isae-sa6-sources.json').read_text())
    entry = next(v for v in sources['models'] if v['id'] == '20b_35c')
    source = SINGLE.CACHE/entry['path']
    model, sign, changes = SINGLE.one_aileron(source.read_text())
    pins = dict(baseline['plan']['source_sha256'])
    pins[str(Path(__file__).relative_to(ROOT))] = SHA(Path(__file__))
    pins[str(baseline_path.relative_to(ROOT))] = SHA(baseline_path)
    plan = dict(source_sha256=pins, case='20b_35c_literal', panels=160,
                body_pitch_deg=[0, 8, 12], right_deflection_deg=[0, 4, -4, 20, -20, 44, -44],
                requested_states=21, speed=20, pg_mach=0, frozen_influences=False,
                residual_limit=1e-8, baseline_coefficient_limit=2e-10,
                captured_field_limit=2e-12,
                purpose='Resolve local terms at existing comparison conditions; no fitted inputs or equation changes.')
    identity = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    cache = ROOT/'.reference/isae-sa6-local'/identity
    cache.mkdir(parents=True, exist_ok=True)
    write(cache/'plan.json', plan)
    previous = {(r['specification']['body_pitch_deg'], r['specification']['right_deflection_deg']):r['result']
                for r in baseline['states'] if r['specification']['case']==plan['case']
                and r['specification']['panels']==plan['panels']}
    rows = []
    new_count = 0
    for pitch in plan['body_pitch_deg']:
        for delta in plan['right_deflection_deg']:
            specification = dict(case=plan['case'], panels=160,
                                 body_pitch_deg=pitch, right_deflection_deg=delta)
            key = hashlib.sha256(json.dumps(specification, sort_keys=True).encode()).hexdigest()
            path = cache/(key+'.json')
            if path.exists():
                row = json.loads(path.read_text())
                assert row['specification'] == specification and row['identity'] == identity
            else:
                row = solve(model, sign, specification, previous[pitch, delta])
                row['identity'] = identity
                write(path, row)
                new_count += 1
            rows.append(row)
            print(f'pitch={pitch}, right deflection={delta}: residual={row["result"]["residual"]:.3g}, '
                  f'baseline error={row["baseline_coefficient_error"]:.3g}', flush=True)
    assert len(rows) == 21
    assert all(SHA(ROOT/p) == h for p, h in pins.items())
    report = dict(status='LOCAL_FIELDS_RETAINED', full_suite_validated=False,
                  identity=identity, plan=plan, control_changes=changes, states=rows,
                  accounting=dict(requested=21, completed=len(rows), newly_computed=new_count,
                                  reused=len(rows)-new_count),
                  scope=['Same source, inputs, conditions and five output coefficients as the corrected comparison.',
                         'CP velocity is retained separately from force-point velocity; own bound segment is excluded only at the force point.',
                         'The existing capture hook observes the unmodified aerodynamic evaluator.',
                         'No new experimental observations or mesh-convergence claim.'])
    write(DEST/'isae-sa6-local.json', report)
    print(json.dumps(report['accounting']), flush=True)


if __name__ == '__main__':
    main()
