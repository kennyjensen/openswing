"""Audit every saved nonzero-incidence pilot snapshot and temporal refinement."""
import gzip
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-time-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    if (BASE/'audit.json').exists() or (BASE/'audit-plan.json').exists():
        raise SystemExit('Preserve existing audit evidence')
    plan=dict(source_sha256={str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).resolve())},
        normalization='CL and circulation errors use their cold-reference maximum departure from the pre-motion steady value; rate uses its reference peak. Every strip is checked.',
        source='Unchanged gates from the time-worker plans; first-step rate, velocity and position remain additional diagnostics.',
        native_ASWING_comparison=False)
    (BASE/'audit-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    inputs={};results={};all_seconds=[]
    alpha=math.radians(9.);direction=np.array([-math.sin(alpha),0.,math.cos(alpha)])
    qs=.5*1.225*100*200000
    steady_cl=2*math.pi*math.tan(alpha);steady_gamma=math.pi*10*math.tan(alpha)
    for steps in (80,160):
        rows=[];previous_raw=None
        for part in range(steps//40):
            name=f'n{steps}-part{part:02d}';folder=BASE/name
            request=json.loads((folder/'plan.json').read_text())
            report=json.loads((folder/'report.json').read_text())
            receipt=json.loads((BASE/(name+'-execution.json')).read_text())
            assert receipt['exit_code']==0 and report['converged'] and report['source_unchanged']
            assert report['accepted_steps']==40 and report['rejected_steps']==0
            for n,h in {**request['source_sha256'],**request['parent_sha256']}.items():assert digest(ROOT/n)==h,n
            for p in (folder/'plan.json',folder/'report.json',folder/'trajectory.json.gz',BASE/(name+'-execution.json')):
                inputs[str(p.relative_to(ROOT))]=digest(p)
            all_seconds.append(report['solver_seconds'])
            with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
            samples=raw['snapshots'];assert len(samples)==len(report['rows'])==41
            if previous_raw is not None:
                assert samples[0]['frame']==previous_raw['frame']
                for key in ('force','circulation_rate'):assert samples[0][key]==previous_raw[key],key
                assert [r['circulation'] for r in samples[0]['strips']]==[r['circulation'] for r in previous_raw['strips']]
            for sample,row in zip(samples,report['rows']):
                assert sample['time']==row['time']
                assert float(np.array(sample['force'])@direction/qs)==row['CL']
                assert [r['circulation'] for r in sample['strips']]==row['circulation']
                assert sample['circulation_rate']==row['circulation_rate']
                assert sample['residual']==row['residual']
            rows.extend(report['rows'] if part==0 else report['rows'][1:])
            previous_raw=samples[-1]
        assert len(rows)==steps+1
        assert all(r['order']==(1 if i==1 else 2) for i,r in enumerate(rows) if i)
        refs=[r['reference'] for r in rows]
        actual_cl=np.array([r['CL'] for r in rows]);ref_cl=np.array([r['CL'] for r in refs])
        actual_g=np.array([r['circulation'] for r in rows]);ref_g=np.array([r['circulation'] for r in refs])
        actual_rate=np.array([r['circulation_rate'] for r in rows]);ref_rate=np.array([r['circulation_rate'] for r in refs])
        scales=dict(CL=float(np.max(abs(ref_cl-steady_cl))),circulation=float(np.max(abs(ref_g-steady_gamma))),
                    rate=float(np.max(abs(ref_rate))))
        errors=dict(CL=float(np.max(abs(actual_cl-ref_cl))/scales['CL']),
            circulation=float(np.max(abs(actual_g-ref_g[:,None]))/scales['circulation']),
            rate=float(np.max(abs(actual_rate-ref_rate[:,None]))/scales['rate']))
        diagnostics=dict(initial_circulation_absolute_error=float(np.max(abs(actual_g[0]-steady_gamma))),
            first_step_rate_relative_error=float(np.max(abs(actual_rate[1]-ref_rate[1]))/abs(ref_rate[1])),
            maximum_velocity_error=max(abs(r['heave_velocity']-r['reference']['velocity']) for r in rows),
            maximum_position_error=max(abs(r['heave_position']-r['reference']['displacement']) for r in rows),
            maximum_residual=max(r['residual'] for r in rows))
        results[str(steps)]=dict(samples=len(rows),scales=scales,error_fractions=errors,diagnostics=diagnostics,rows=rows)
    gates=request['gates']
    ratios={key:results['160']['error_fractions'][key]/results['80']['error_fractions'][key] for key in ('CL','circulation','rate')}
    fine=results['160']['error_fractions']
    passed=(fine['CL']<gates['fine_waveform_fraction'] and fine['circulation']<gates['fine_circulation_fraction']
        and fine['rate']<gates['fine_rate_fraction'] and max(ratios.values())<gates['fine_to_coarse_ratio']
        and max(r['diagnostics']['maximum_residual'] for r in results.values())<gates['normalized_residual'])
    output=dict(plan=plan,input_sha256=inputs,results=results,gates=gates,fine_to_coarse_ratios=ratios,
        refinement_check_passed=bool(passed),audited_unique_snapshots=242,
        solver_seconds=dict(min=min(all_seconds),max=max(all_seconds),total=sum(all_seconds)),
        native_ASWING_comparison=False,periodic_production_validation=False)
    assert all(digest(ROOT/n)==h for n,h in {**inputs,**plan['source_sha256']}.items())
    (BASE/'audit.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=passed,coarse=results['80']['error_fractions'],fine=fine,ratios=ratios,
        fine_diagnostics=results['160']['diagnostics'],solver_seconds=output['solver_seconds'])))
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
