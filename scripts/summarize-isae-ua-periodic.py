"""Summarize independently audited UA-1 periodic histories and retained errors."""
from hashlib import sha256
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-periodic-20261101'


def main():
    batch=json.loads((BASE/'plan.json').read_text())
    completed=json.loads((BASE/'batch-complete.json').read_text())
    assert completed['computed_jobs']==64
    cases=[];figure,axes=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    convergence,caxes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    seconds=[];persistence=[];checks=0;audited=0
    for axis,tag in zip(axes.flat,('005','010','030','050')):
        path=BASE/f'audit-a{tag}.json';data=json.loads(path.read_text())
        assert data['auditor_sha256']==sha256((ROOT/'scripts/audit-isae-ua-periodic.py').read_bytes()).hexdigest()
        checks+=data['checks_passed'];audited+=data['audited_unique_snapshots']
        fine=data['refinements'][-1];coarse=data['refinements'][0]
        amplitude=data['amplitude_ratio'];wave=fine['final_waveform'];period=math.pi/(10*.95)
        phase=np.asarray(wave['times'])/period
        axis.plot(phase,np.asarray(wave['predicted'])/amplitude,label='OpenSwing, cycle 8',lw=1.5)
        axis.plot(phase,np.asarray(wave['reference'])/amplitude,'--',label='Nonlinear periodic reference',lw=1.2)
        k=.95;b=2*math.pi*1j*k*(1+2j*k)/(1+4j*k)-math.pi*k*k
        axis.plot(phase,(-b*np.exp(2j*math.pi*phase)).real,':',label='Published linear formula',lw=1.2)
        final=fine['cycles'][-1]
        axis.set(title=f'A/c={amplitude:g}; waveform error {100*final["waveform_error_fraction"]:.4f}%',
            xlabel='Phase / cycle',ylabel='Vertical CL / (A/c)')
        axis.grid(alpha=.25);axis.legend(fontsize=7)
        for n,refinement in enumerate(data['refinements']):
            rows=refinement['cycles']
            seconds.extend(r['solver_seconds'] for r in rows);persistence.extend(r['persistence_seconds'] for r in rows)
            caxes[n].semilogy([r['cycle'] for r in rows],[100*r['waveform_error_fraction'] for r in rows],
                'o-',ms=3,label=f'A/c={amplitude:g}')
        cases.append(dict(amplitude_ratio=amplitude,k=k,passed=bool(data['checks_passed']),
            coarse_waveform_error_percent=100*coarse['cycles'][-1]['waveform_error_fraction'],
            fine_waveform_error_percent=100*final['waveform_error_fraction'],
            amplitude_error_percent=100*final['amplitude_error_fraction'],phase_error_deg=final['phase_error_deg'],
            mean_error_percent_of_peak=100*final['mean_error_peak_fraction'],
            last_cycle_change_percent=100*final['change_fraction'],waveform_error_ratio=data['final_waveform_error_ratio'],
            nonlinear_vs_linear_amplitude_difference_percent=100*data['nonlinear_vs_linear_amplitude_difference_fraction'],
            nonlinear_vs_linear_phase_difference_deg=data['nonlinear_vs_linear_phase_difference_deg'],
            third_harmonic_percent_of_fundamental=100*data['independent_periodic_reference']['harmonics'][2]['amplitude']/
                data['independent_periodic_reference']['harmonics'][0]['amplitude'],
            maximum_checkpoint_jump=max(r['maximum_checkpoint_join_jump'] for r in data['refinements']),
            maximum_residual=max(r['maximum_residual'] for r in data['refinements']),
            fine_full_history_cold_waveform_error_percent=100*fine['full_history_cold_waveform_error_fraction'],
            audit_path=str(path.relative_to(ROOT)),audit_sha256=sha256(path.read_bytes()).hexdigest()))
    for axis,steps in zip(caxes,(80,160)):
        axis.axhline(.1,color='black',lw=.8,ls=':',label='Fine-grid gate, 0.1%')
        axis.set(title=f'{steps} steps per cycle',xlabel='Cycle from cold start',ylabel='Periodic waveform error (%)')
        axis.set_xticks(range(1,9));axis.grid(which='both',alpha=.2);axis.legend(fontsize=7)
    summary=dict(date='2026-11-01',scope=batch['scope'],checks_passed=checks,checks_total=4,
        computed_jobs=64,continuous_trajectories=8,audited_unique_snapshots=audited,cases=cases,
        solver_seconds_range=[min(seconds),max(seconds)],persistence_seconds_range=[min(persistence),max(persistence)],
        total_solver_seconds=sum(seconds),production_files_unchanged=136,production_changed=False,app_defaults_changed=False,
        native_ASWING_comparison=False,experimental_comparison=False,gates=batch['gates'],
        summary_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['Zero mean incidence, k=.95 only; other frequencies/incidences remain.',
            'Infinite-span attached-flow reconstruction; not native executable output.',
            'Fine-grid periodic accuracy and timestep refinement do not establish arbitrary-model automatic error control.',
            'Mean lift is checked against zero-incidence symmetry, not experimental LEV shifts.',
            'Exact k=.47/.94 phase-average plot checks and UA-2 finite/periodic response remain.'])
    stem=ROOT/'docs/validation/isae-ua1-periodic-20261101'
    stem.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    figure.suptitle('UA-1: settled nonlinear heave response, k=0.95, 160 steps/cycle')
    figure.savefig(stem.with_suffix('.svg'));figure.savefig(stem.with_suffix('.png'),dpi=150);plt.close(figure)
    convergence.suptitle('UA-1: startup decay and temporal discretization error')
    cstem=Path(str(stem)+'-convergence')
    convergence.savefig(cstem.with_suffix('.svg'));convergence.savefig(cstem.with_suffix('.png'),dpi=150);plt.close(convergence)
    print(json.dumps(summary,indent=2),flush=True)
    if checks!=4:raise SystemExit(1)


if __name__=='__main__':
    main()
