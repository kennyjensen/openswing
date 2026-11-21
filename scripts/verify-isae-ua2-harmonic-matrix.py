"""Bounded independent finite-span harmonic audit; never a native UA-2 pass.

Prepare once, run each mesh separately, then combine. No production files are
changed. The reference C matrix comes from separately integrated horseshoes,
not from the production residual or the corrected archived 2D curves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/isae/ua2-harmonic-matrix-20261103'
LIMIT = 1e-8
FREQUENCIES = [.95 * i / 14 for i in range(15)]
DIAGNOSTIC_FREQUENCIES = [10., 100.]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def read(path):
    return json.loads(path.read_text())


def pins(paths):
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def verify(values):
    for name, value in values.items():
        if digest(ROOT / name) != value:
            raise ValueError('Source changed: ' + name)


def prepare():
    BASE.mkdir(parents=True, exist_ok=True)
    kernel = pins(list((ROOT / 'openswing').glob('*.py')))
    assert len(kernel) == 136
    inputs = pins([Path(__file__).resolve(),
        ROOT / 'scripts/isae_suite_unsteady.py',
        ROOT / 'scripts/isae_ua_wing_nonlinear.py',
        ROOT / 'docs/validation/isae-straight-wing-heave-reference.md',
        ROOT / '.reference/asw_theory.txt',
        ROOT / '.reference/asw_uns_theory.txt'])
    plan = dict(meshes=[20, 40], published_frequencies=FREQUENCIES,
        diagnostic_frequencies=DIAGNOSTIC_FREQUENCIES,
        aspect_ratio=10., chord=1., speed=10., alpha_deg=0., mach=0.,
        stall=False, aero_lag=True, derivative_step=1e-5,
        complex_scaled_error_limit=LIMIT,
        comparison_scale='max(1, abs(independent complex CL))',
        prescribed_displacement_phasor=.5,
        source_sha256=kernel, input_sha256=inputs,
        native_ASWING_comparison=False, nonlinear_time_validation=False,
        provenance='AR10 reconstruction; the original native model/driver are unavailable.',
        equations='(C + 2 i omega/(pi V) I) Gamma = -w; '
            'CL_cir = 2/(V b) (1 + i omega/V) widths.Gamma; '
            'CL_added = -pi a/(2 V^2). Unit chord, zero incidence, small motion.',
        qualifications=['The 15 frequencies are the archived sample coordinates.',
            'k=10 and 100 are asymptotic diagnostics, not archived targets.',
            'The .85/.90 circulation factors are not applied to production.',
            'This checks the documented discretization, not arbitrary geometry or nonlinear stall.'])
    write(BASE / 'plan.json', plan)
    print(json.dumps(dict(prepared=True, meshes=plan['meshes'],
        plan_sha256=digest(BASE / 'plan.json'))))


def run(panels):
    import numpy as np
    from isae_ua_wing_nonlinear import StraightWing
    from isae_suite_unsteady import harmonic_response

    started = time.monotonic()
    plan = read(BASE / 'plan.json')
    verify(plan['source_sha256']); verify(plan['input_sha256'])
    assert panels in plan['meshes']
    wing = StraightWing(panels, span=plan['aspect_ratio'], chord=plan['chord'])
    speed = plan['speed']
    frequencies = plan['published_frequencies'] + plan['diagnostic_frequencies']
    independent = []
    for k in frequencies:
        omega = 2 * speed * k
        velocity = .5j * omega
        acceleration = -.5 * omega**2
        operator = wing.C + 2j * omega / (np.pi * speed) * np.eye(panels)
        unit_response = np.linalg.solve(operator, np.ones(panels))
        gamma = -velocity * unit_response
        circulation_lift = (2 / (speed * wing.span)
            * (1 + 1j * omega / speed) * (wing.widths @ gamma))
        added = -np.pi * acceleration / (2 * speed**2)
        # This ratio remains defined at k=0 by the steady unit-velocity limit.
        unit_2d_response = np.pi / (1 + 2j * omega / speed)
        ratio = (wing.widths @ unit_response) / (wing.span * unit_2d_response)
        independent.append((circulation_lift + added, circulation_lift, added, ratio))

    production = harmonic_response(ROOT, dict(panels=panels,
        **{name: plan[name] for name in ('aspect_ratio', 'speed', 'alpha_deg',
            'mach', 'stall', 'aero_lag', 'derivative_step')}), frequencies=frequencies)
    rows = []
    for index, (result, values) in enumerate(zip(production['response'], independent)):
        expected, circulatory, added, ratio = values
        actual = complex(result['CL_real'], result['CL_imag'])
        total_error = abs(actual - expected) / max(1., abs(expected))
        circulation_error = abs(actual - added - circulatory) / max(1., abs(circulatory))
        rows.append(dict(k=result['k'], archived_sample=index < 15,
            production_CL=[actual.real, actual.imag],
            independent_CL=[float(expected.real), float(expected.imag)],
            independent_circulatory_CL=[float(circulatory.real), float(circulatory.imag)],
            independent_added_mass_CL=float(added),
            circulatory_ratio_to_2D=[float(ratio.real), float(ratio.imag)],
            circulatory_ratio_magnitude=float(abs(ratio)),
            circulatory_ratio_phase_deg=float(np.angle(ratio, deg=True)),
            complex_total_scaled_error=float(total_error),
            complex_circulatory_scaled_error=float(circulation_error),
            passed=bool(total_error <= LIMIT and circulation_error <= LIMIT)))
    verify(plan['source_sha256']); verify(plan['input_sha256'])
    result = dict(panels=panels, passed=production['numerical_passed']
        and len(rows) == 17 and all(r['passed'] for r in rows), rows=rows,
        production=production, wall_seconds=time.monotonic() - started,
        native_ASWING_comparison=False, new_native_passes=0,
        plan_sha256=digest(BASE / 'plan.json'),
        source_sha256=plan['source_sha256'], input_sha256=plan['input_sha256'])
    write(BASE / f'n{panels}.json', result)
    print(json.dumps(dict(panels=panels, passed=result['passed'],
        maximum_complex_scaled_error=max(max(r['complex_total_scaled_error'],
            r['complex_circulatory_scaled_error']) for r in rows),
        wall_seconds=result['wall_seconds'])))
    if not result['passed']:
        raise SystemExit(1)


def combine():
    plan = read(BASE / 'plan.json')
    verify(plan['source_sha256']); verify(plan['input_sha256'])
    runs = [read(BASE / f'n{n}.json') for n in plan['meshes']]
    for run in runs:
        assert run['plan_sha256'] == digest(BASE / 'plan.json')
        assert run['source_sha256'] == plan['source_sha256']
        assert run['input_sha256'] == plan['input_sha256']
        assert run['passed'] and run['new_native_passes'] == 0
    summary = dict(passed=True, native_ASWING_comparison=False,
        new_native_passes=0, published_frequency_checks_passed=30,
        separate_asymptotic_diagnostics_passed=4,
        maximum_complex_scaled_error=max(max(row['complex_total_scaled_error'],
            row['complex_circulatory_scaled_error']) for run in runs for row in run['rows']),
        mesh_complex_change_scaled=max(abs(complex(*a['production_CL'])
            - complex(*b['production_CL'])) / max(1., abs(complex(*b['production_CL'])))
            for a, b in zip(runs[0]['rows'][:15], runs[1]['rows'][:15])),
        mesh_change_has_acceptance_gate=False,
        fine_circulatory_gain=[{key: row[key] for key in ('k', 'archived_sample',
            'circulatory_ratio_magnitude', 'circulatory_ratio_phase_deg')}
            for row in runs[1]['rows']],
        source_sha256=plan['source_sha256'],
        input_sha256=pins([BASE / 'plan.json', BASE / 'n20.json', BASE / 'n40.json']),
        qualifications=plan['qualifications'])
    write(BASE / 'summary.json', summary)
    print(json.dumps({k: v for k, v in summary.items()
        if k not in ('source_sha256', 'input_sha256', 'fine_circulatory_gain')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'combine'))
    parser.add_argument('--panels', type=int, choices=(20, 40))
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'run':
        if args.panels is None:
            parser.error('run requires --panels')
        run(args.panels)
    else:
        combine()
