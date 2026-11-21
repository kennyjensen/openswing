"""Audit all raw snapshots of the inclined UA-2 one-cycle refinement pilot."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from isae_ua2_incidence_nested import GATES,PERIOD,grid
from isae_ua_wing_incidence import InclinedWing

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-nested-20261101'
OLD=ROOT/'artifacts/isae/ua2-incidence-startup-20261101'


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    assert not (BASE/'audit.json').exists() and not (BASE/'audit-plan.json').exists()
    batch=json.loads((BASE/'batch-plan.json').read_text());assert batch['gates']==GATES
    assert json.loads((BASE/'batch-complete.json').read_text())['computed_jobs']==25
    plan=dict(gates=GATES,source_sha256={str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).resolve())},
        normalization=batch['normalization'],native_ASWING_comparison=False)
    (BASE/'audit-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    pins={**batch['source_sha256'],**plan['source_sha256']};inputs={};results={};durations=[]
    wing=InclinedWing(20,alpha_deg=9.)
    steady=wing.steady();steady_cl=wing.fields(steady,0.,0.)['CL']
    reference=json.loads((BASE/'reference.json').read_text())['reference']['DOP853']['cold']['rows']
    reference_times=np.array([r['time'] for r in reference])
    for steps in (160,320):
        times=grid(steps)
        source_base=OLD if steps==160 else BASE
        rows=[];previous=None
        for part in range((len(times)-2)//16+1):
            expected_steps=min(16,len(times)-1-part*16)
            name=f'n{steps}-part{part:02d}';folder=source_base/name
            request=json.loads((folder/'plan.json').read_text());report=json.loads((folder/'report.json').read_text())
            receipt=json.loads((source_base/(name+'-execution.json')).read_text())
            assert receipt['exit_code']==0 and receipt['report_sha256']==digest(folder/'report.json')
            assert report['accepted_steps']==expected_steps and report['rejected_steps']==0 and report['converged'] and report['source_unchanged']
            assert request['full_request']['panels']==20 and request['full_request']['condition']['alpha']==9.
            assert request['gates']==GATES and request['full_request']['time']['duration']==PERIOD
            for n,h in {**request['source_sha256'],**request['parent_sha256']}.items():
                if n in pins:assert pins[n]==h,n
                pins[n]=h
            for p in (folder/'plan.json',folder/'report.json',folder/'trajectory.json.gz',source_base/(name+'-execution.json')):
                inputs[str(p.relative_to(ROOT))]=digest(p)
            with gzip.open(folder/'trajectory.json.gz','rt') as stream:raw=json.load(stream)
            samples=raw['snapshots'];assert len(samples)==len(report['rows'])==expected_steps+1
            if previous is not None:
                for key in ('force','circulation_rate','frame'):assert samples[0][key]==previous[key]
                assert [s['circulation'] for s in samples[0]['strips']]==[s['circulation'] for s in previous['strips']]
            for s,r in zip(samples,report['rows']):
                assert s['time']==r['time'] and s['residual']==r['residual']
                index=int(np.argmin(abs(reference_times-s['time'])))
                assert abs(reference_times[index]-s['time'])<1e-12
                for key in ('CL','circulation','circulation_rate','CF'):
                    np.testing.assert_allclose(r['reference'][key],reference[index][key],rtol=0,atol=2e-10)
                assert float(np.array(s['force'])@wing.heave/(.5*1.225*100*10))==r['CL']
                assert s['circulation_rate']==r['circulation_rate']
                assert [v['circulation'] for v in s['strips']]==r['circulation']
                assert float(np.array(s['frame']['velocity_origin_body'])@wing.heave)==r['heave_velocity']
                assert float(np.array(s['frame']['position_earth'])@wing.heave)==r['heave_position']
            previous=samples[-1];rows.extend(report['rows'] if part==0 else report['rows'][1:])
            durations.append(report['solver_seconds'])
        assert len(rows)==len(times)
        np.testing.assert_allclose([r["time"] for r in rows],times,rtol=0,atol=1e-12)
        assert all(r['order']==(1 if i==1 else 2) for i,r in enumerate(rows) if i)
        expected={key:np.array([r['reference'][key] for r in rows]) for key in ('CL','circulation','circulation_rate')}
        actual={key:np.array([r[key] for r in rows]) for key in expected}
        scales=dict(CL=float(np.max(abs(expected['CL']-steady_cl))),
            circulation=np.max(abs(expected['circulation']-steady),axis=0),
            circulation_rate=np.max(abs(expected['circulation_rate']),axis=0))
        assert all(np.min(v)>0 for v in scales.values())
        errors={key:float(np.max(abs(actual[key]-expected[key])/scales[key])) for key in expected}
        diagnostics=dict(first_step_rate_relative_error=float(np.max(abs(actual['circulation_rate'][1]-expected['circulation_rate'][1])/abs(expected['circulation_rate'][1]))),
            maximum_heave_velocity_error=max(abs(r['heave_velocity']-r['reference']['velocity']) for r in rows),
            maximum_heave_position_error=max(abs(r['heave_position']-r['reference']['displacement']) for r in rows),
            maximum_residual=max(r['residual'] for r in rows),
            initial_circulation_error=float(np.max(abs(actual['circulation'][0]-steady))))
        results[str(steps)]=dict(rows=rows,error_fractions=errors,diagnostics=diagnostics,
            scales={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in scales.items()})
    retained_path=OLD/'audit.json';inputs[str(retained_path.relative_to(ROOT))]=digest(retained_path)
    assert results['160']==json.loads(retained_path.read_text())['results']['160']
    fine=results['320'];coarse=results['160'];ratios={k:fine['error_fractions'][k]/coarse['error_fractions'][k] for k in fine['error_fractions']}
    checks={key:fine['error_fractions'][key]<GATES[gate] for key,gate in
        (('CL','cold_CL_fraction'),('circulation','cold_circulation_fraction'),('circulation_rate','cold_rate_fraction'))}
    checks.update(refinement=max(ratios.values())<GATES['fine_to_coarse_ratio'],
        residual=max(r['diagnostics']['maximum_residual'] for r in results.values())<GATES['normalized_residual'],
        first_step_rate=fine['diagnostics']['first_step_rate_relative_error']<GATES['first_step_rate_fraction'],
        velocity=fine['diagnostics']['maximum_heave_velocity_error']/(.25*19)<GATES['velocity_fraction'],
        position=fine['diagnostics']['maximum_heave_position_error']/.25<GATES['position_fraction'])
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    output=dict(passed=all(checks.values()),checks=checks,results=results,ratios=ratios,
        audited_unique_snapshots=602,input_sha256=inputs,source_sha256=pins,
        solver_seconds=dict(min=min(durations),max=max(durations),total=sum(durations)),native_ASWING_comparison=False)
    (BASE/'audit.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=output['passed'],checks=checks,fine_errors=fine['error_fractions'],ratios=ratios,diagnostics=fine['diagnostics'])))
    if not output['passed']:raise SystemExit(1)


if __name__=='__main__':main()
