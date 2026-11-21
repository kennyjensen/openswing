"""ISAE P-1: compare the production isolated propeller with 55 measured samples.

Requires fetch-isae-validation.py, extract-isae-figures.py, fetch-isae-p1.py.
The published CdA values are used without fitting. They were calibrated in the
original study; this is not an independent validation of those parameters.
"""
from pathlib import Path
import hashlib
import json
import os
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('OPENSWING_KERNEL', ROOT))
sys.path.insert(0, str(KERNEL))
import numpy as np
import scipy
from openswing.propulsion import engine_load


def statistics(predicted, reference):
    error = np.asarray(predicted) - reference
    return dict(count=len(error), bias=float(error.mean()),
                rmse=float(np.sqrt(np.mean(error**2))), maximum_absolute_error=float(max(abs(error))),
                mean_absolute_percentage_error=float(100*np.mean(abs(error/reference))))


def evaluate(rpm, cp, diameter, drag_area, density=1.2256):
    n = rpm / 60
    power = cp * density * n**3 * diameter**5
    row = np.zeros(25)
    row[[0, 1, 7, 12, 13, 14]] = [1, 1, 1, diameter/2, 2*np.pi*n, drag_area]
    state = engine_load(row, power, density, np.zeros(3), np.zeros(3))
    ct = state['thrust'] / (density*n*n*diameter**4)
    # Closed form obtained independently from hover momentum and power balance.
    cp_viscous = 3*np.pi**3*drag_area/(8*diameter**2)
    analytic_ct = (np.pi/2)**(1/3)*max(cp-cp_viscous, 0.)**(2/3)
    assert not state['power_clipped']
    errors = [abs(ct-analytic_ct),
              abs(state['inviscid_power']+state['viscous_power']-power)/power,
              abs(state['torque']*row[13]+power)/power,
              float(np.max(abs(state['force']-[state['thrust'], 0, 0])))/state['thrust']]
    assert max(errors) < 2e-12, errors
    return dict(CT=float(ct), power=float(power), thrust=state['thrust'], torque=state['torque'],
                viscous_power=state['viscous_power'], inviscid_power=state['inviscid_power'],
                independent_check_error=max(errors))


def main():
    manifest = json.loads((ROOT/'docs/validation/isae-p1-sources.json').read_text())
    figures = json.loads((ROOT/'docs/validation/isae-figure-inventory.json').read_text())
    modules = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((KERNEL/'openswing').glob('*.py'))}
    cases = []
    for blades in [2, 3, 4]:
        ending = '_static' if blades == 2 else f'_{blades}b_static'
        source = next(p for p in manifest['files'] if ending in p)
        raw = (ROOT/'.reference/isae-p1'/source).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest['files'][source]['sha256']
        measured = np.loadtxt(ROOT/'.reference/isae-p1'/source, skiprows=1)
        entry = next(f for f in figures['figures'] if f'P1_CT_{blades}_' in f['path'])
        fig_path = ROOT/'.reference/isae-validation/figure-series'/(entry['sha256']+'.json')
        assert hashlib.sha256(fig_path.read_bytes()).hexdigest() == entry['extracted_sha256']
        series = json.loads(fig_path.read_text())['series']
        experimental = np.asarray(next(s['xy'] for s in series if s['label']=='Experiments'))
        # Verify data extraction using the independent primary tables, including RPM.
        assert np.array_equal(measured[:, :2], experimental)
        archived = {key: np.asarray(next(s['xy'] for s in series if f'Pv {key}:' in s['label']))
                    for key in ['ON', 'OFF']}
        assert all(np.array_equal(a[:, 0], measured[:, 0]) for a in archived.values())
        runs = []
        for diameter_name, diameter in [('nominal_9_in', .2286), ('true_9_1_in_sensitivity', .23114)]:
            for viscous in ['ON', 'OFF']:
                drag_area = blades*.8e-4 if viscous == 'ON' else 0.
                outputs = [evaluate(rpm, cp, diameter, drag_area) for rpm, _, cp in measured]
                density_check = max(abs(evaluate(rpm, cp, diameter, drag_area, .91)['CT']-v['CT'])
                                    for (rpm, _, cp), v in zip(measured, outputs))
                assert density_check < 2e-12
                predicted = [v['CT'] for v in outputs]
                comparison = statistics(predicted, archived[viscous][:, 1])
                if diameter_name == 'nominal_9_in':
                    assert comparison['maximum_absolute_error'] < 2e-12
                runs.append(dict(diameter_name=diameter_name, diameter_m=diameter, viscous=viscous,
                    drag_area_m2=drag_area, density_coefficient_error=density_check, outputs=outputs,
                    experimental_errors=statistics(predicted, measured[:, 1]), archived_aswing_errors=comparison))
        cases.append(dict(blades=blades, primary_source=manifest['files'][source], figure_source=entry,
                          measured_RPM_CT_CP=measured.tolist(), archived_aswing={k:v.tolist() for k,v in archived.items()}, runs=runs))
    result = dict(status='ARCHIVED_P1_COMPONENT_REPRODUCED_EXPERIMENT_DISCREPANCY_RECORDED',
        full_suite_validated=False, scope='Isolated static type-1 engine_load, not aircraft-level zero-speed flight',
        provenance=dict(upstream_revision=figures['revision'], modules=modules,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            uiuc_manifest_sha256=hashlib.sha256((ROOT/'docs/validation/isae-p1-sources.json').read_bytes()).hexdigest()),
        runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        settings=dict(density=1.2256, axial_velocity=0., CdA_source='ISAE Part 2 V2, page 15, Figure 6: 1.6, 2.4, 3.2 times 1e-4 m2'),
        limitations=[
            'Power coefficients are measured UIUC inputs; predicting thrust does not independently predict power.',
            'Published CdA was calibrated using experimental data in the original study; no parameters were fitted here.',
            'Nominal 9-inch diameter reproduces every archived curve to floating-point precision. The primary two-blade geometry plot specifies true diameter 9.1 inches. The latter is also applied to all blade counts as an explicit diameter sensitivity, not an independently established three/four-blade geometry.',
            'The four-blade FIG legend says 11 percent; the PDF page 15 says 12 percent. The computed nominal mean absolute error is about 11.994 percent.',
            'Experimental uncertainty and an acceptance threshold are not established; numerical reproduction is not experimental agreement.'],
        cases=cases)
    output = ROOT/'docs/validation/isae-p1.json'
    output.write_text(json.dumps(result, indent=2)+'\n')
    print('Recorded 55 primary samples, 220 production comparisons, and 220 density checks:', output)


if __name__ == '__main__':
    main()
