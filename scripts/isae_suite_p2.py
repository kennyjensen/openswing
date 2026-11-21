"""P-2 archived CT/eta curves with independently reconstructed driving inputs.

The report describes calibrating CdA from measured CT/CP. Reconstruct the
quadratic using only the original forward-flow measurement rows, excluding the
separate static row. No archived model output participates in that calculation.
The precise upstream fitting program is absent: this remains a declared input
reconstruction, including the study's variable-CdA extension to ASWING.
Planning/source validation uses only the standard library, without physics.
"""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys

SCHEMA = 'isae-p2-reconstructed-inputs-v1'
SCOPE = 'p2-reconstructed-inputs'
GATE = 2e-12
CONFIGS = (
    (2, 2000, 'da4022_9x6.75_0769rd_2018.txt', '1953.333', 8),
    (2, 4000, 'da4022_9x6.75_0771rd_4042.txt', '3950.000', 18),
    (4, 2000, 'da4022_9x6.75_4b_1087ga_2034.txt', '1958.333', 8),
    (4, 4000, 'da4022_9x6.75_4b_1089ga_4036.txt', '3938.333', 18),
)
CHOICES = ('polynomial', 'constant_zero', 'constant_max')
LIMITS = [
    'Original P-2 driver and exact fitting procedure are absent; reconstructed inputs are explicitly conditional.',
    'Only forward-flow measurements calibrate CdA; the separately identified static sample supplies CP at J=0.',
    'Measured power is supplied, not predicted. Acceptance targets are archived model curves, never experiments.',
    'The polynomial curve is the report authors\' variable-CdA extension; constants exercise the ASWING model directly.',
    'Nominal nine-inch diameter follows the report/P-1 reproduction; primary UIUC normalization uses its measured diameter.',
    'Nominal RPM and density set dimensional units; their historical exact values are not asserted.',
    'No aircraft, wake, P-factor, browser, or whole-family validation claim.',
]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def pin(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=sha256(raw).hexdigest())


def table(path, columns):
    rows = []
    for line, raw in enumerate(Path(path).read_text().splitlines(), 1):
        words = raw.split()
        if not words or not words[0][0].isdigit():
            continue
        values = list(map(float, words))
        require(len(values) == columns and all(map(math.isfinite, values)), 'Invalid primary row')
        rows.append(dict(line=line, tokens=words, values=values))
    return rows


def unique_series(series):
    result = []
    for row in series:
        require(row['nonfinite_coordinates'] == 0, 'Nonfinite P-2 source')
        matches = [old for old in result if row['xy'] == old['xy']]
        if matches:
            require(not row['label'] or row['label'] == matches[0]['label'], 'Duplicate curve has conflicting labels')
        else:
            result.append(row)
    require(len(result) == 4, 'Expected experiment and three distinct model curves')
    return result


def plan(root):
    root = Path(root).resolve()
    manifest_path = root/'docs/validation/isae-p2-sources.json'
    static_manifest_path = root/'docs/validation/isae-p1-sources.json'
    inventory_path = root/'docs/validation/isae-figure-inventory.json'
    manifest, static_manifest, inventory = map(read, (manifest_path, static_manifest_path, inventory_path))
    kernels = [pin(path) for path in sorted((root/'openswing').glob('*.py'))]
    jobs = []
    for blades, rpm, name, static_rpm, count in CONFIGS:
        primary = root/'.reference/isae-p2'/name
        static_name = 'da4022_9x6.75'+('_4b_static_1086ga' if blades == 4 else '_static_0767rd')+'.txt'
        static = root/'.reference/isae-p1'/static_name
        for path, entry in ((primary, manifest['files'][name]), (static, static_manifest['files'][static_name])):
            actual = pin(path)
            require(all(actual[key] == entry[key] for key in ('bytes', 'sha256')), 'Primary source changed')
        forward = table(primary, 4)
        static_rows = [row for row in table(static, 3) if row['tokens'][0] == static_rpm]
        require(len(static_rows) == 1 and len(forward) == count-1, 'P-2 primary row pairing changed')
        static_row = static_rows[0]
        samples = [dict(index=0, J=0., CP=static_row['values'][2], measured_CT=static_row['values'][1],
                        source=str(static), line=static_row['line'], tokens=static_row['tokens'])]
        samples += [dict(index=i, J=row['values'][0], CP=row['values'][2], measured_CT=row['values'][1],
                         source=str(primary), line=row['line'], tokens=row['tokens']) for i, row in enumerate(forward, 1)]
        files = [Path(__file__).resolve(), manifest_path, static_manifest_path, inventory_path, primary, static,
                 root/'.reference/isae-validation/reports/Experimental_validation_of_ASWING_Part_2_Propellers_V2.txt']
        curves = {}
        for output in ('CT', 'eta'):
            suffix = f'P2_DA4022_{blades}B_{rpm}RPM_{output}.fig'
            entries = [f for f in inventory['figures'] if f['path'].endswith(suffix)]
            require(len(entries) == 1, 'P-2 figure identity changed')
            entry = entries[0]
            original = root/'.reference/isae-validation'/inventory['revision']/entry['path']
            extracted = root/'.reference/isae-validation/figure-series'/(entry['sha256']+'.json')
            require(pin(original)['sha256'] == entry['sha256'] and
                    pin(extracted)['sha256'] == entry['extracted_sha256'], 'P-2 figure changed')
            files += [original, extracted]
            curves[output] = unique_series(read(extracted)['series'])
        require(curves['CT'][0]['xy'] == [[s['J'], s['measured_CT']] for s in samples],
                'Primary measurements do not identify archived input rows')
        require([s['label'] for s in curves['eta']][::2] == ['Exp', 'CDA(\\lambda = 0)'] and
                curves['eta'][3]['label'] == 'CDA(\\lambda_{max})', 'P-2 curve labels changed')
        # All four CT/eta pairs must satisfy eta = J*CT/CP, including signs.
        # This binds otherwise unlabeled CT curves to their labeled eta curves.
        for ct_curve, eta_curve in zip(curves['CT'], curves['eta']):
            require(len(ct_curve['xy']) == len(eta_curve['xy']) == count, 'P-2 coordinate count changed')
            for sample, (j, ct), (ej, eta) in zip(samples, ct_curve['xy'], eta_curve['xy']):
                require(j == ej == sample['J'] and abs(eta-j*ct/sample['CP']) < 2e-14,
                        'P-2 CT/eta/source CP attribution failed')
        label = curves['eta'][1]['label']
        rounded = [float(x) for x in re.findall(r'[+-]?\d\.\de[+-]\d\d', label)]
        require(len(rounded) == 3, 'Printed polynomial must provide three coefficients')
        observations = [dict(name=f'{choice}:{output}:row{i:02d}', choice=choice, output=output,
                             index=i, J=sample['J'], expected=curves[output][c]['xy'][i][1],
                             source_label=curves['eta'][c]['label'])
                        for c, choice in enumerate(CHOICES, 1) for output in ('CT', 'eta')
                        for i, sample in enumerate(samples)]
        jobs.append(dict(id=f'P-2-{blades}blade-{rpm}RPM', case_id='P-2', family='P-2', adapter='p2',
            schema=SCHEMA, comparison_scope=SCOPE, settings=dict(diameter_m=.2286, nominal_rpm=rpm,
                density_kg_m3=1.2256, blades=blades), samples=samples, observations=observations,
            rounded_coefficients=rounded, coefficient_label=label,
            input_reconstruction='Unweighted quadratic least squares of reverse-EADT CdA on forward-flow measurements only.',
            expected_outputs=count*6, strict_tolerance=GATE, numerical_tolerance=GATE,
            source_pins=[pin(path) for path in files], kernel_pins=kernels,
            limits=LIMITS, suggested_cap_seconds=60))
    require(sum(j['expected_outputs'] for j in jobs) == 312, 'Incomplete P-2 scope')
    return jobs


def reconstruct_drag(forward_samples, diameter):
    """Inputs contain measured J/CT/CP only, never archived model targets."""
    import numpy as np
    j = np.array([s['J'] for s in forward_samples])
    ct = np.array([s['measured_CT'] for s in forward_samples])
    cp = np.array([s['CP'] for s in forward_samples])
    require(len(j) >= 3 and bool(np.all(j > 0)), 'Use original forward-flow measurements only')
    dv = -j + np.sqrt(j*j + 8*ct/np.pi)
    inviscid = np.pi/4*(j+(1+5*(j/np.pi)**2)*dv/2)*(j+dv/2)*dv
    area = 8*diameter**2*(cp-inviscid)/(np.sqrt(j*j+np.pi**2)*(j*j+3*np.pi**2))
    coefficients = np.polyfit(j, area, 2)
    require(bool(np.isfinite(coefficients).all()) and bool((area >= 0).all()), 'Invalid reconstructed drag input')
    return dict(coefficients=coefficients.tolist(), measured_drag_areas_m2=area.tolist(),
                forward_row_count=len(j), static_row_included=False, model_targets_used=False)


def physical_metrics(sample, settings, area, state):
    """Recompute dimensional balances from the saved raw production state."""
    n, rho, diameter = settings['nominal_rpm']/60, settings['density_kg_m3'], settings['diameter_m']
    v, omega, radius = sample['J']*n*diameter, 2*math.pi*n, diameter/2
    power = sample['CP']*rho*n**3*diameter**5
    dv, thrust = state['delta_velocity'], state['thrust']
    viscous = rho/8*math.sqrt(v*v+(omega*radius)**2)*(v*v+3*(omega*radius)**2)*area
    ideal = rho*math.pi*radius**2*(v+dv/2)*dv
    transported = (v+(1+5*(v/(omega*radius))**2)*dv/2)*ideal
    return dict(momentum=abs(thrust-ideal)/max(1., abs(thrust)),
        power=abs(transported+viscous-power)/max(1., abs(power)),
        viscous=abs(viscous-state['viscous_power'])/max(1., abs(power)),
        inviscid=abs(transported-state['inviscid_power'])/max(1., abs(power)),
        torque=abs(state['torque']*omega+power)/max(1., abs(power)),
        requested=abs(state['requested_power']-power)/max(1., abs(power)),
        force=max(abs(state['force'][i]-(thrust if i == 0 else 0.)) for i in range(3))/max(1., abs(thrust)),
        clipped=float(state['power_clipped']))


def evaluate(samples, settings, coefficients):
    import numpy as np
    from openswing.propulsion import engine_load
    n, rho, diameter = settings['nominal_rpm']/60, settings['density_kg_m3'], settings['diameter_m']
    rows = []
    for choice in CHOICES:
        for sample in samples:
            j = sample['J'] if choice == 'polynomial' else 0. if choice == 'constant_zero' else samples[-1]['J']
            area = float(np.polyval(coefficients, j))
            row = np.zeros(25)
            row[[0, 1, 7, 12, 13, 14]] = [1, 1, 1, diameter/2, 2*np.pi*n, area]
            power = sample['CP']*rho*n**3*diameter**5
            # Thrust +x, so engine_axes' incoming-flow axis is -x.
            state = engine_load(row, power, rho, np.zeros(3), np.array([-sample['J']*n*diameter, 0., 0.]))
            keep = ('thrust', 'torque', 'delta_velocity', 'viscous_power', 'inviscid_power',
                    'requested_power', 'minimum_power', 'power_clipped')
            saved = {key: state[key] for key in keep}
            saved['force'] = state['force'].tolist()
            ct = state['thrust']/(rho*n*n*diameter**4)
            rows.append(dict(choice=choice, index=sample['index'], drag_area_m2=area, state=saved,
                             CT=ct, eta=sample['J']*ct/sample['CP'],
                             physical_metrics=physical_metrics(sample, settings, area, saved)))
    return rows


def verify_reference_sources(root, job):
    canonical = next(j for j in plan(root) if j['id'] == job['id'])
    require(all(job.get(key) == value for key, value in canonical.items()), 'Prepared P-2 source/setting changed')
    return canonical


def validate_result_contract(job, result):
    require(result['status'] == 'computed' and result['numerical_passed'] is True and
            result['schema'] == SCHEMA and result['comparison_scope'] == SCOPE,
            'P-2 result lost declared input scope')
    require(result['settings'] == job['settings'] and result['source_pins_unchanged'] is True, 'P-2 settings/pins changed')
    reconstruction = result['input_reconstruction']
    require(reconstruction == reconstruct_drag(job['samples'][1:], job['settings']['diameter_m']),
            'P-2 calibration differs from primary measurements')
    require(reconstruction['model_targets_used'] is False and reconstruction['static_row_included'] is False and
            reconstruction['forward_row_count'] == len(job['samples'])-1, 'P-2 input reconstruction changed')
    require([float(f'{x:.1e}') for x in reconstruction['coefficients']] == job['rounded_coefficients'],
            'Recovered input coefficients do not reproduce printed source labels')
    rows = result['rows']
    expected_keys = {(choice, s['index']) for choice in CHOICES for s in job['samples']}
    require(len(rows) == len(expected_keys) and {(r['choice'], r['index']) for r in rows} == expected_keys,
            'Missing or duplicate P-2 rows')
    mapped = {(r['choice'], r['index']): r for r in rows}
    for row in rows:
        sample = job['samples'][row['index']]
        j = sample['J'] if row['choice'] == 'polynomial' else 0. if row['choice'] == 'constant_zero' else job['samples'][-1]['J']
        a, b, c = reconstruction['coefficients']
        require(abs(row['drag_area_m2']-((a*j+b)*j+c)) < 1e-18, 'P-2 drag input changed')
        metrics = physical_metrics(sample, job['settings'], row['drag_area_m2'], row['state'])
        require(metrics == row['physical_metrics'] and all(math.isfinite(v) and 0 <= v < GATE for v in metrics.values()),
                'P-2 physical balance failed')
        n, rho, d = job['settings']['nominal_rpm']/60, job['settings']['density_kg_m3'], job['settings']['diameter_m']
        ct = row['state']['thrust']/(rho*n*n*d**4)
        require(row['CT'] == ct and row['eta'] == sample['J']*ct/sample['CP'], 'P-2 normalization changed')
    checks = result['reference_checks']
    require(len(checks) == job['expected_outputs'], 'P-2 output count changed')
    for check, observation in zip(checks, job['observations']):
        pred = mapped[observation['choice'], observation['index']][observation['output']]
        require(check['name'] == observation['name'] and check['predicted'] == pred and
                check['expected'] == observation['expected'] and check['tolerance'] == GATE and check['comparison'] == '<',
                'P-2 target/prediction/gate changed')
    require(result['operations'] == dict(engine_load_calls=6*len(job['samples']), aircraft_solves=0),
            'P-2 production call accounting changed')
    return True


def run(root, job):
    root = Path(root).resolve()
    job = verify_reference_sources(root, job)
    require(os.environ.get('OPENSWING_KERNEL') in (None, str(root)), 'Alternate production kernel selected')
    sys.path.insert(0, str(root))
    inputs = reconstruct_drag(job['samples'][1:], job['settings']['diameter_m'])
    require([float(f'{x:.1e}') for x in inputs['coefficients']] == job['rounded_coefficients'],
            'Reconstructed coefficients do not round to all twelve printed coefficients')
    rows = evaluate(job['samples'], job['settings'], inputs['coefficients'])
    rounded = evaluate(job['samples'], job['settings'], job['rounded_coefficients'])
    require(Path(sys.modules['openswing.propulsion'].__file__).resolve() == root/'openswing/propulsion.py',
            'Wrong production module imported')
    mapped = {(r['choice'], r['index']): r for r in rows}
    checks = []
    for obs in job['observations']:
        predicted = mapped[obs['choice'], obs['index']][obs['output']]
        checks.append(dict(name=obs['name'], predicted=predicted, expected=obs['expected'],
                           tolerance=GATE, comparison='<', passed=abs(predicted-obs['expected']) < GATE))
    pins_held = all(pin(p['path']) == p for p in job['source_pins']+job['kernel_pins'])
    result = dict(id=job['id'], case_id='P-2', adapter='p2', schema=SCHEMA, status='computed',
        comparison_scope=SCOPE, settings=job['settings'], input_reconstruction=inputs, rows=rows,
        rounded_input_diagnostic=rounded, reference_checks=checks,
        numerical_passed=True, reference_match=all(c['passed'] for c in checks), source_pins_unchanged=pins_held,
        source_pins=job['source_pins'], kernel_pins=job['kernel_pins'], limits=LIMITS,
        operations=dict(engine_load_calls=6*len(job['samples']), aircraft_solves=0))
    validate_result_contract(job, result)
    return result
