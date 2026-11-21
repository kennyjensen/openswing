"""One bounded independent-reference or production-load UA-1 incidence job."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import time

import numpy as np
from isae_ua_incidence_reference import trajectory
from isae_ua_incidence_production import evaluate_point
from isae_ua_periodic import fourier, phase_difference
from isae_ua_phase import source_binding, source_curve

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua1-incidence-20261101'
GATES = dict(reference_agreement_fraction=1e-9, periodic_closure_fraction=1e-10,
             normalized_residual=5e-5, force_coefficient_absolute=5e-5,
             apparent_coefficient_absolute=1e-12, coordinate_rotation_absolute=2e-12)


def case_id(alpha, k):
    return f'ref-k{round(100*k):03d}-a{alpha:g}'


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def source_pins():
    binding = source_binding()
    paths = [*sorted((ROOT/'openswing').glob('*.py')), Path(__file__).resolve(),
        *[ROOT/'scripts'/name for name in ('isae_ua_incidence_reference.py', 'isae_ua_incidence_production.py',
            'isae_ua_periodic.py', 'isae_ua_section_reference.py', 'isae_ua_phase.py', 'isae_suite_unsteady.py')],
        ROOT/'tests/test_isae_ua_incidence_reference.py', BASE/'source-review.json',
        ROOT/'.reference/asw_theory.txt', ROOT/'.reference/asw_uns_theory.txt',
        ROOT/'docs/validation/isae-ua1-phase-sources-20261101.json',
        ROOT/binding['phase_average']['script']]
    pins = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    for p in paths:
        frozen = BASE/'frozen-code'/p.relative_to(ROOT)
        frozen.parent.mkdir(parents=True, exist_ok=True)
        if frozen.exists():
            assert digest(frozen) == pins[str(p.relative_to(ROOT))], p
        else:
            shutil.copyfile(p, frozen)
    return pins


def reference(alpha, k):
    period = math.pi/(10*k)
    references = {}
    agreements = []
    for boundary, count in (('periodic', 512), ('steady', 128)):
        times = np.linspace(0., period, count+1)
        references[boundary] = {}
        for method in ('quadrature', 'DOP853', 'Radau'):
            references[boundary][method] = trajectory(times, alpha_deg=alpha, k=k, boundary=boundary, method=method)
        oracle = references[boundary]['quadrature']['rows']
        for method in ('DOP853', 'Radau'):
            rows = references[boundary][method]['rows']
            differences = {}
            for key in ('circulation', 'circulation_rate', 'CL', 'CF'):
                a, b = np.array([r[key] for r in rows]), np.array([r[key] for r in oracle])
                differences[key] = float(np.max(abs(a-b))/np.max(abs(b)))
            agreements.append(dict(boundary=boundary, method=method, fractions=differences,
                                   passed=max(differences.values()) < GATES['reference_agreement_fraction']))
    periodic = references['periodic']['quadrature']
    rows = periodic['rows']
    measured = fourier([r['time'] for r in rows], [r['CL'] for r in rows], period)
    reduced = fourier([r['time'] for r in rows[::2]], [r['CL'] for r in rows[::2]], period)
    source = source_curve(k, alpha, np.linspace(0., 1., 513))
    actual = np.array([r['CL'] for r in rows])
    reference_phasor = source['phasor']
    first = measured['harmonics'][0]
    closure = max(abs(rows[-1][key]-rows[0][key])/max(abs(r[key]) for r in rows)
                  for key in ('circulation', 'circulation_rate', 'CL'))
    differences = dict(waveform_percent_of_linear_amplitude=100*float(np.max(abs(actual-source['CL']))/abs(reference_phasor)),
        mean_CL=measured['mean']-source['mean'], linear_mean_CL=source['mean'], nonlinear_mean_CL=measured['mean'],
        fundamental_amplitude_percent=100*(first['amplitude']/abs(reference_phasor)-1),
        fundamental_phase_deg=phase_difference(first['phase_deg'], math.degrees(np.angle(reference_phasor))%360),
        second_to_first_harmonic_percent=100*measured['harmonics'][1]['amplitude']/first['amplitude'],
        third_to_first_harmonic_percent=100*measured['harmonics'][2]['amplitude']/first['amplitude'])
    return dict(references=references, agreement_checks=agreements, periodic_closure_fraction=closure,
        passed=bool(all(row['passed'] for row in agreements) and closure < GATES['periodic_closure_fraction']),
        measured_periodic=measured, quadrature_resolution_check=dict(intervals=[256,512],
            mean_difference=measured['mean']-reduced['mean'],
            fundamental_amplitude_difference=first['amplitude']-reduced['harmonics'][0]['amplitude']),
        differences_from_linear_source=differences,
        difference_interpretation='Different approximation levels, not error against a native ASWING trajectory.')


def production_probe(panels, inputs):
    checks = []
    for alpha in (0.,5.,9.):
        for k in (.47,.94):
            folder = BASE/case_id(alpha,k)
            report_path = folder/'report.json'
            report = json.loads(report_path.read_text())
            assert report['passed'] and report['source_unchanged']
            assert report['plan']['source_sha256'] == inputs
            receipt = json.loads((BASE/(case_id(alpha,k)+'-execution.json')).read_text())
            assert receipt['exit_code'] == 0
            rows = report['references']['periodic']['quadrature']['rows'][:-1:64]
            assert len(rows) == 8
            for index, row in enumerate(rows):
                actual = {representation: evaluate_point(row['circulation'], row['circulation_rate'],
                    row['velocity'], row['acceleration'], alpha_deg=alpha, panels=panels, representation=representation)
                    for representation in ('body','wind')}
                errors = {}
                for name, output in actual.items():
                    component = max(float(np.max(abs(np.array(output[key])-row[key]))) for key in ('CF','CF_rate'))
                    component = max(component,float(np.max(abs(np.array(output['CF_circulation_and_profile'])-
                        np.array(row['CF_circulation'])-row['CF_profile']))),abs(output['CL_instantaneous']-row['CL_instantaneous']))
                    errors[name] = dict(force_coefficient_absolute=component,
                        apparent_coefficient_absolute=float(np.max(abs(np.array(output['CF_apparent'])-row['CF_apparent']))),
                        normalized_residual=output['maximum_residual'])
                rotation = max(float(np.max(abs(np.array(actual['body'][key])-actual['wind'][key])))
                               for key in ('CF','CF_rate','CF_apparent','circulation_residual'))
                passed = (rotation < GATES['coordinate_rotation_absolute'] and
                    all(all(value < GATES[key] for key,value in error.items()) for error in errors.values()))
                checks.append(dict(alpha_deg=alpha,k=k,phase=index/8,reference=row,
                    production=actual,errors=errors,coordinate_rotation_absolute=rotation,passed=bool(passed)))
    return dict(checks=checks,checks_passed=sum(c['passed'] for c in checks),checks_total=len(checks),
        passed=all(c['passed'] for c in checks),
        maximum_force_coefficient_error=max(v['force_coefficient_absolute'] for c in checks for v in c['errors'].values()),
        maximum_normalized_residual=max(v['normalized_residual'] for c in checks for v in c['errors'].values()),
        maximum_apparent_coefficient_error=max(v['apparent_coefficient_absolute'] for c in checks for v in c['errors'].values()),
        maximum_coordinate_rotation_error=max(c['coordinate_rotation_absolute'] for c in checks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='kind', required=True)
    ref = sub.add_parser('reference')
    ref.add_argument('--alpha', type=float, choices=(0.,5.,9.), required=True)
    ref.add_argument('--k', type=float, choices=(.47,.94), required=True)
    prod = sub.add_parser('production')
    prod.add_argument('--panels', type=int, choices=(4,8), required=True)
    args = parser.parse_args()
    name = case_id(args.alpha,args.k) if args.kind == 'reference' else f'production-n{args.panels}'
    folder = BASE/name
    if folder.exists():
        parser.error('Preserve existing results; use a new scope for a changed job')
    pins = source_pins()
    folder.mkdir(parents=True)
    reference_inputs = {}
    if args.kind == 'production':
        for alpha in (0.,5.,9.):
            for k in (.47,.94):
                for p in (BASE/case_id(alpha,k)/'report.json', BASE/(case_id(alpha,k)+'-execution.json')):
                    reference_inputs[str(p.relative_to(ROOT))] = digest(p)
    plan = dict(kind=args.kind,settings=vars(args),source_sha256=pins,reference_input_sha256=reference_inputs,
        gates=GATES,native_ASWING_comparison=False,production_time_integration=False,
        model=dict(amplitude_ratio=.5,speed=10.,chord=1.,mach=0.,stall=False,heave_direction='fixed freestream normal'),
        registered_rows_before=[r for r in (ROOT/'docs/validation/ISAE_STATUS.md').read_text().splitlines() if r.startswith('| [')])
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    started = time.monotonic()
    output = reference(args.alpha,args.k) if args.kind == 'reference' else production_probe(args.panels,pins)
    unchanged = all(digest(ROOT/n) == h for n,h in {**pins,**reference_inputs}.items())
    output.update(plan=plan,seconds=time.monotonic()-started,source_unchanged=unchanged,
        native_ASWING_comparison=False,production_time_integration=False)
    (folder/'report.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(job=name,seconds=output['seconds'],passed=output['passed'],
        result=output.get('differences_from_linear_source',
            {key:output.get(key) for key in ('checks_passed','checks_total','maximum_force_coefficient_error',
             'maximum_normalized_residual','maximum_coordinate_rotation_error')}))),flush=True)
    if not (output['passed'] and unchanged):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
