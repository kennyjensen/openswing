"""Audit every inclined periodic snapshot, refinement and settled harmonics."""
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
from isae_ua_incidence_periodic import GATES,PERIOD,CYCLES
from isae_ua_periodic import fourier,phase_difference

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-periodic-20261101'
OLD=ROOT/'artifacts/isae/ua1-incidence-time-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    if (BASE/'audit.json').exists() or (BASE/'audit-plan.json').exists():raise SystemExit('Preserve completed audit')
    batch=json.loads((BASE/'batch-plan.json').read_text())
    assert batch['gates']==GATES
    reference=json.loads((BASE/'reference.json').read_text())
    assert reference['passed']
    plan=dict(source_sha256={str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).resolve()),
        'scripts/isae_ua_periodic.py':digest(ROOT/'scripts/isae_ua_periodic.py')},
        gates=GATES,normalization=batch['normalization'],first_cycle_replay_absolute_gate=1e-10,
        native_ASWING_comparison=False)
    (BASE/'audit-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    verified_sources={}
    def verify_cached(n,h):
        if n not in verified_sources:verified_sources[n]=digest(ROOT/n)
        assert verified_sources[n]==h,n
    for n,h in batch['source_sha256'].items():verify_cached(n,h)
    inputs={};results={};solver_seconds=[];wall_seconds=[]
    alpha=math.radians(9.);direction=np.array([-math.sin(alpha),0.,math.cos(alpha)])
    qs=.5*1.225*100*200000
    steady_cl=2*math.pi*math.tan(alpha);steady_gamma=math.pi*10*math.tan(alpha)
    for steps in (80,160):
        rows=[];previous=None
        for part in range(CYCLES*steps//40):
            name=f'n{steps}-part{part:02d}';folder=BASE/name
            request=json.loads((folder/'plan.json').read_text())
            report=json.loads((folder/'report.json').read_text())
            receipt=json.loads((BASE/(name+'-execution.json')).read_text())
            assert request['gates']==GATES and request['full_request']['time']['duration']==CYCLES*PERIOD
            assert receipt['exit_code']==0 and receipt['report_sha256']==digest(folder/'report.json')
            assert report['converged'] and report['source_unchanged'] and report['rejected_steps']==0
            assert report['accepted_steps']==40
            for n,h in {**request['source_sha256'],**request['parent_sha256']}.items():verify_cached(n,h)
            for p in (folder/'plan.json',folder/'report.json',folder/'trajectory.json.gz',BASE/(name+'-execution.json')):
                inputs[str(p.relative_to(ROOT))]=digest(p)
            solver_seconds.append(report['solver_seconds']);wall_seconds.append(receipt['wall_seconds'])
            with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
            samples=raw['snapshots'];assert len(samples)==len(report['rows'])==41
            if previous is not None:
                for key in ('force','circulation_rate','frame'):assert samples[0][key]==previous[key],key
                assert [r['circulation'] for r in samples[0]['strips']]==[r['circulation'] for r in previous['strips']]
            for sample,row in zip(samples,report['rows']):
                assert sample['time']==row['time'] and sample['residual']==row['residual']
                assert float(np.array(sample['force'])@direction/qs)==row['CL']
                assert [r['circulation'] for r in sample['strips']]==row['circulation']
                assert sample['circulation_rate']==row['circulation_rate']
                index=round(row['time']/PERIOD*160)
                assert row['reference']==reference['reference']['cold_rows'][index]
            rows.extend(report['rows'] if part==0 else report['rows'][1:]);previous=samples[-1]
        assert len(rows)==CYCLES*steps+1
        assert all(r['order']==(1 if i==1 else 2) for i,r in enumerate(rows) if i)
        actual={key:np.array([r[key] for r in rows]) for key in ('CL','circulation','circulation_rate')}
        cold={key:np.array([r['reference'][key] for r in rows]) for key in actual}
        cold_scales=dict(CL=float(np.max(abs(cold['CL']-steady_cl))),
                         circulation=float(np.max(abs(cold['circulation']-steady_gamma))),
                         circulation_rate=float(np.max(abs(cold['circulation_rate']))))
        cold_errors={key:float(np.max(abs(actual[key]-(target if key=='CL' else target[:,None])))/cold_scales[key])
                     for key,target in cold.items()}
        phase_rows=reference['reference']['periodic']['rows'][::160//steps]
        phase=np.array([r['time'] for r in phase_rows])
        periodic={key:np.array([r[key] for r in phase_rows]) for key in actual}
        periodic_means={key:fourier(phase,values,PERIOD)['mean'] for key,values in periodic.items()}
        periodic_scales={key:float(np.max(abs(values-(periodic_means[key] if key!='circulation_rate' else 0))))
                         for key,values in periodic.items()}
        measured_ref=fourier(phase,periodic['CL'],PERIOD)
        cycles=[]
        for cycle in range(1,CYCLES+1):
            sl=slice((cycle-1)*steps,cycle*steps+1)
            errors={key:float(np.max(abs(actual[key][sl]-(target if key=='CL' else target[:,None])))/periodic_scales[key])
                    for key,target in periodic.items()}
            measured=fourier(phase,actual['CL'][sl],PERIOD)
            harmonic=[]
            for a,b in zip(measured['harmonics'],measured_ref['harmonics']):
                harmonic.append(dict(order=a['order'],amplitude_error_fraction=a['amplitude']/b['amplitude']-1,
                                     phase_error_deg=phase_difference(a['phase_deg'],b['phase_deg'])))
            change=None
            if cycle>1:
                prior=slice((cycle-2)*steps,(cycle-1)*steps+1)
                change={key:float(np.max(abs(values[sl]-values[prior]))/periodic_scales[key]) for key,values in actual.items()}
            cycles.append(dict(cycle=cycle,error_fractions=errors,measured=measured,harmonic_errors=harmonic,
                mean_CL_error_dynamic_fraction=(measured['mean']-measured_ref['mean'])/periodic_scales['CL'],
                cycle_change_fractions=change))
        original=[]
        for part in range(steps//40):
            p=OLD/f'n{steps}-part{part:02d}'/'report.json'
            saved=json.loads(p.read_text());inputs[str(p.relative_to(ROOT))]=digest(p)
            original.extend(saved['rows'] if part==0 else saved['rows'][1:])
        replay=max(float(np.max(abs(np.array(a[key])-b[key]))) for a,b in zip(rows,original)
                   for key in ('CL','circulation','circulation_rate','heave_velocity','heave_position'))
        assert replay<plan['first_cycle_replay_absolute_gate']
        diagnostics=dict(first_step_rate_relative_error=float(np.max(abs(actual['circulation_rate'][1]-cold['circulation_rate'][1]))/abs(cold['circulation_rate'][1])),
            maximum_heave_velocity_error=max(abs(r['heave_velocity']-r['reference']['velocity']) for r in rows),
            maximum_heave_position_error=max(abs(r['heave_position']-r['reference']['displacement']) for r in rows),
            cycle_end_heave_position_errors=[rows[c*steps]['heave_position']-rows[c*steps]['reference']['displacement'] for c in range(1,9)],
            maximum_residual=max(r['residual'] for r in rows),first_cycle_replay_maximum_absolute_difference=replay)
        results[str(steps)]=dict(samples=len(rows),cold_error_fractions=cold_errors,cold_scales=cold_scales,
            periodic_scales=periodic_scales,periodic_means=periodic_means,periodic_reference=measured_ref,
            cycles=cycles,diagnostics=diagnostics,rows=rows)
    fine=results['160'];coarse=results['80'];final=fine['cycles'][-1]
    ratios={scope:{key:fine[scope][key]/coarse[scope][key] for key in fine[scope]}
            for scope in ('cold_error_fractions',)}
    ratios['periodic_error_fractions']={key:final['error_fractions'][key]/coarse['cycles'][-1]['error_fractions'][key]
                                       for key in final['error_fractions']}
    gates={}
    for key,label in (('CL','CL'),('circulation','circulation'),('circulation_rate','rate')):
        gates['periodic_'+key]=final['error_fractions'][key]<GATES['periodic_'+label+'_fraction']
        gates['cold_'+key]=fine['cold_error_fractions'][key]<GATES['cold_'+label+'_fraction']
        gates['last_cycle_change_'+key]=final['cycle_change_fractions'][key]<GATES['last_cycle_change_fraction']
    gates.update(refinement=all(value<GATES['fine_to_coarse_ratio'] for row in ratios.values() for value in row.values()),
        amplitude=abs(final['harmonic_errors'][0]['amplitude_error_fraction'])<GATES['amplitude_fraction'],
        phase=abs(final['harmonic_errors'][0]['phase_error_deg'])<GATES['phase_deg'],
        mean=abs(final['mean_CL_error_dynamic_fraction'])<GATES['mean_CL_dynamic_fraction'],
        residual=max(r['diagnostics']['maximum_residual'] for r in results.values())<GATES['normalized_residual'])
    output=dict(plan=plan,input_sha256=inputs,results=results,checks=gates,
        passed=all(gates.values()),fine_to_coarse_ratios=ratios,audited_unique_snapshots=1922,
        solver_seconds=dict(min=min(solver_seconds),max=max(solver_seconds),total=sum(solver_seconds)),
        worker_wall_seconds=dict(min=min(wall_seconds),max=max(wall_seconds),total=sum(wall_seconds)),
        native_ASWING_comparison=False)
    # Revalidate every unique source and input after the complete read-through.
    assert all(digest(ROOT/n)==h for n,h in {**verified_sources,**inputs,**plan['source_sha256']}.items())
    (BASE/'audit.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=output['passed'],checks=gates,final_errors=final['error_fractions'],
        fundamental=final['harmonic_errors'][0],mean_error=final['mean_CL_error_dynamic_fraction'],
        cycle_change=final['cycle_change_fractions'],ratios=ratios,diagnostics=fine['diagnostics'])))
    if not output['passed']:raise SystemExit(1)


if __name__=='__main__':main()
