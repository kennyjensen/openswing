"""Audit UA-2 time marching against separately integrated coupled 3D matrices."""
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua2-time-20261101'


def audit_run(folder, reference):
    plan = json.loads((folder/'plan.json').read_text())
    report = json.loads((folder/'report.json').read_text())
    assert report['converged'] and report['production_unchanged'] and report['rejected_steps'] == 0
    assert report['structural_operator'] == 'drela-moving-airflow-v1'
    assert report['temporal_policy'] == 'drela-euler-bdf-v1'
    request = plan['request']
    assert plan['aspect_ratio'] == 10 and plan['amplitude_ratio'] == .001
    assert not request['condition']['stall'] and request['condition']['aero_lag']
    assert request['panels'] == reference['settings']['panels']
    for name,digest in plan['code_sha256'].items():
        assert sha256((BASE/'frozen-code'/name).read_bytes()).hexdigest() == digest,name
        if name.startswith('openswing/'):
            assert sha256((ROOT/name).read_bytes()).hexdigest() == digest,name
    with gzip.open(folder/'trajectory.json.gz','rt') as stream:
        raw = json.load(stream)
    samples, snapshots = report['comparison']['samples'], raw['snapshots']
    comparison = report['linear_wing_comparison']
    assert not comparison['native_ASWING_comparison'] and not comparison['independent_spatial_physics_reference']
    assert len(samples) == len(snapshots) == report['accepted_steps']+1 == len(comparison['rows'])
    times = np.array([s['time'] for s in snapshots])
    speed, k, h = request['condition']['speed'], plan['k'], plan['amplitude_ratio']/2
    omega = 2*speed*k
    m = reference['matrices']
    K,M,rv,ra,fg,fd = [np.asarray(m[key]) for key in ('K','M','rv','ra','fg','fd')]
    def derivative(t,gamma):
        w,a = -h*omega*math.sin(omega*t), -h*omega**2*math.cos(omega*t)
        return np.linalg.solve(M,-K@gamma-rv*w-ra*a)
    ode = solve_ivp(derivative, (0.,times[-1]), np.zeros(len(K)), t_eval=times,
        method='DOP853', rtol=1e-12, atol=1e-14)
    assert ode.success
    expected, expected_rates = [], []
    for t,gamma in zip(times,ode.y.T):
        w,a = -h*omega*math.sin(omega*t), -h*omega**2*math.cos(omega*t)
        rate = derivative(t,gamma)
        expected_rates.append(rate)
        expected.append(fg@gamma+fd@rate+m['fv']*w+m['fa']*a)
    expected = np.array(expected)
    saved_reference = np.array([r['expected']['CL'] for r in comparison['rows']])
    ode_difference = float(np.max(np.abs(expected-saved_reference)))
    assert ode_difference < 2e-11
    qs = .5*1.225*speed**2*10
    actual = np.array([s['force'][2]/qs for s in snapshots])
    for s,r in zip(snapshots,samples):
        assert s['time'] == r['time'] and s['force'][2]/qs == r['CL_vertical']
        assert s['residual'] == r['residual'] and s['residual'] < 1e-10
        assert abs(r['acceleration_error']) < 1e-14
        assert max(abs(v) for v in s['frame']['rates_body']+s['frame']['attitude']) < 1e-12
    error = float(np.max(np.abs(actual-expected))/np.max(np.abs(expected)))
    assert abs(error-comparison['maximum_waveform_error_fraction']) < 1e-8
    actual_rates = np.array([s['circulation_rate'] for s in snapshots])
    expected_rates = np.array(expected_rates)
    actual_gamma = np.array([[r['circulation'] for r in s['strips']] for s in snapshots])
    gamma_error = float(np.max(np.abs(actual_gamma-ode.y.T))/np.max(np.abs(ode.y)))
    rate_error = float(np.max(np.abs(actual_rates-expected_rates))/np.max(np.abs(expected_rates)))
    assert abs(gamma_error-comparison['maximum_circulation_error_fraction']) < 1e-8
    assert abs(rate_error-comparison['maximum_circulation_rate_error_fraction']) < 1e-8
    rate_time,rate_strip = np.unravel_index(np.argmax(np.abs(actual_rates-expected_rates)),actual_rates.shape)
    record = dict(steps=report['accepted_steps'], seconds=report['seconds'],
        maximum_waveform_error_percent=100*error,
        maximum_circulation_error_percent=100*gamma_error,
        maximum_circulation_rate_error_percent=100*rate_error,
        circulation_rate_error_location=dict(snapshot=int(rate_time),strip_index=int(rate_strip),
            time_over_period=float(times[rate_time]/times[-1]),
            predicted=float(actual_rates[rate_time,rate_strip]),reference=float(expected_rates[rate_time,rate_strip])),
        maximum_residual=report['comparison']['maximum_residual'],
        independent_ODE_max_CL_difference=ode_difference, rejected_steps=0,
        jacobian_builds=report['jacobian_builds'], audited_snapshots=len(snapshots),
        evidence=str(folder.relative_to(ROOT)),
        evidence_sha256={n:sha256((folder/n).read_bytes()).hexdigest()
            for n in ('plan.json','report.json','trajectory.json.gz')})
    curves = dict(times=times.tolist(),actual=actual.tolist(),reference=expected.tolist())
    return record,curves


def main():
    batch = json.loads((BASE/'batch-plan.json').read_text())
    cases, curves, parity = [], {}, []
    figure, axes = plt.subplots(2,2,figsize=(10,6.5),constrained_layout=True)
    for column,(tag,k) in enumerate((('k0475',.475),('k095',.95))):
        for panels in (20,40):
            reference = json.loads((BASE/f'reference-n{panels}.json').read_text())
            assert reference['numerical_passed'] and reference['unchanged_code']
            assert not reference['native_ASWING_comparison']
            previous = json.loads((ROOT/f'artifacts/isae/ua-time-20261101/wing-ar10-n{panels}.json').read_text())
            difference = max(abs(complex(p['CL_real'],p['CL_imag'])-complex(q['CL_real'],q['CL_imag']))
                for p,q in zip(reference['harmonic_response'],previous['production']['response']))
            derivative = json.loads((BASE/f'derivative-refinement-n{panels}.json').read_text())
            assert derivative['passed'] and derivative['references'][0] == reference
            assert derivative['refinement_ratio'] < .35 and derivative['relative_CL_uncertainty'] < 1e-7
            assert all(d <= b for d,b in zip(derivative['previous_difference'],derivative['measured_consistency_bound']))
            assert abs(difference-derivative['maximum_previous_harmonic_difference']) < 1e-12
            if column == 0:
                parity.append(dict(panels=panels,maximum_complex_CL_difference=difference,
                    derivative_refinement_ratio=derivative['refinement_ratio'],
                    relative_CL_derivative_uncertainty=derivative['relative_CL_uncertainty'],
                    measured_truncation_bound_passed=True,
                    meaning='Frame-motion V10 matrices vs prior nodal-motion V30 harmonic response per A/c.'))
            records = []
            for steps in (40,80,160):
                record,curve = audit_run(BASE/f'{tag}-n{panels}-t{steps}',reference)
                assert record['steps'] == steps
                records.append(record)
                if steps == 160:
                    curves[k,panels] = curve
                    x = np.asarray(curve['times'])/curve['times'][-1]
                    axes[0,column].plot(x,np.asarray(curve['actual'])/.001,label=f'{panels} strips, BDF2',lw=1.2)
                    if panels == 40:
                        axes[0,column].plot(x,np.asarray(curve['reference'])/.001,'k--',label='40-strip matrix reference',lw=1)
            errors = [r['maximum_waveform_error_percent'] for r in records]
            ratios = [errors[i+1]/errors[i] for i in (0,1)]
            passed = max(ratios) < batch['successive_error_ratio_maximum'] and errors[-1]/100 < batch['temporal_error_fraction_maximum']
            assert passed
            cases.append(dict(k=k,panels=panels,records=records,successive_error_ratios=ratios,
                refinement_gate_passed=passed))
            axes[1,column].loglog([40,80,160],errors,'o-',label=f'{panels} strips')
        axes[0,column].set(title=f'UA-2 AR10, k={k:g}, A/c=0.001',xlabel='Time / period (zero-circulation start)',ylabel='Vertical CL / (A/c)')
        axes[1,column].set(xlabel='Steps per cycle',ylabel='Maximum waveform error (%)',xticks=[40,80,160],xticklabels=['40','80','160'])
        for row in (0,1):
            axes[row,column].grid(which='both',alpha=.25)
            axes[row,column].legend(fontsize=8)
    mesh = []
    for k in (.475,.95):
        coarse,fine = curves[k,20],curves[k,40]
        np.testing.assert_allclose(coarse['times'],fine['times'],atol=1e-14,rtol=0)
        changes = {key:float(np.max(np.abs(np.asarray(coarse[key])-fine[key]))/np.max(np.abs(fine[key])))
            for key in ('actual','reference')}
        passed = max(changes.values()) < batch['spatial_waveform_change_fraction_maximum']
        assert passed
        mesh.append(dict(k=k,time_response_mesh_change_percent=100*changes['actual'],
            exact_matrix_mesh_change_percent=100*changes['reference'],mesh_gate_passed=passed))
    output = dict(date='2026-11-01',scope='UA-2 reconstructed AR10 small-amplitude integration parity',
        native_ASWING_comparison=False,independent_spatial_physics_reference=False,
        time_refinement_checks_passed=len(cases),mesh_stability_checks_passed=len(mesh),cases=cases,
        audited_snapshots=sum(r['audited_snapshots'] for c in cases for r in c['records']),
        mesh_checks=mesh,harmonic_parity=parity,production_files_unchanged=136,
        limitations=['Only two frequencies, zero mean incidence, A/c=.001, attached flow.',
            'First startup cycle, not periodic amplitude/phase or finite-amplitude validation.',
            'Matrix reference shares production spatial physics; it tests time integration, not native 3D accuracy.',
            'Native UA-2 deck/root-wall treatment, driver and curve provenance remain unverified.',
            'No browser/WASM execution or bundle refresh.'],
        summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest())
    stem = ROOT/'docs/validation/isae-ua2-time-20261101'
    stem.with_suffix('.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    figure.savefig(stem.with_suffix('.svg'));figure.savefig(stem.with_suffix('.png'),dpi=150)
    plt.close(figure)
    print(json.dumps(dict(time_checks=len(cases),mesh_checks=mesh,audited_snapshots=output['audited_snapshots'],
        finest_errors_percent=[c['records'][-1]['maximum_waveform_error_percent'] for c in cases],
        maximum_ODE_CL_difference=max(r['independent_ODE_max_CL_difference'] for c in cases for r in c['records']))))


if __name__ == '__main__':
    main()
