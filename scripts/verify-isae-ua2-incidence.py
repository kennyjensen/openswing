"""One capped reference or instantaneous-state job for inclined UA-2."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time
import numpy as np

from isae_ua_wing_incidence import InclinedWing
from isae_ua_periodic import fourier

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-20261101-r2'
GATES=dict(reference_fraction=1e-8,periodic_closure_fraction=1e-10,
    force_absolute=2e-10,residual_absolute=2e-11,rotation_absolute=2e-10)


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('reference','probe'))
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--alpha',type=int,choices=(5,9),required=True)
    parser.add_argument('--k',type=float,choices=(.475,.95),required=True)
    args=parser.parse_args()
    case=f'n{args.panels}-a{args.alpha}-k{round(args.k*1000):04d}'
    folder=BASE/f'{args.action}-{case}'
    if folder.exists():parser.error('Preserve completed or interrupted evidence')
    folder.mkdir(parents=True)
    source=[Path(__file__).resolve(),*[ROOT/'scripts'/n for n in (
        'isae_ua_wing_incidence.py','isae_ua_wing_nonlinear.py','isae_ua_periodic.py',
        'isae_ua_section_reference.py','isae_ua_wing_incidence_production.py','isae_suite_unsteady.py')],
        ROOT/'tests/test_isae_ua_wing_incidence.py',ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt',
        ROOT/'artifacts/isae/ua1-incidence-20261101/source-review.json']
    if args.action=='probe':source.extend(sorted((ROOT/'openswing').glob('*.py')))
    pins={str(p.relative_to(ROOT)):digest(p) for p in source}
    plan=dict(action=args.action,case=case,panels=args.panels,alpha_deg=args.alpha,k=args.k,
        amplitude_ratio=.5,span=10.,chord=1.,speed=10.,stall=False,mach=0.,source_sha256=pins,gates=GATES,
        native_ASWING_comparison=False,independent_spatial_reference=True)
    (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for p in source:
        target=BASE/'frozen-code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():assert digest(target)==digest(p)
        else:shutil.copyfile(p,target)
    wing=InclinedWing(args.panels,alpha_deg=args.alpha)
    period=np.pi/(10*args.k);times=period*np.arange(161)/160
    started=time.monotonic()
    if args.action=='reference':
        results={};seconds={}
        for method in ('DOP853','Radau'):
            before=time.monotonic()
            cold=wing.integrate(times,amplitude_ratio=.5,k=args.k,method=method)
            periodic=wing.periodic(times,amplitude_ratio=.5,k=args.k,method=method)
            closure=float(np.max(abs(np.array(periodic['rows'][-1]['circulation'])-periodic['rows'][0]['circulation']))/max(1.,np.max(np.abs(periodic['rows'][0]['circulation']))))
            periodic.update(measured=fourier(times,[r['CL'] for r in periodic['rows']],period),closure_fraction=closure)
            assert closure<GATES['periodic_closure_fraction']
            results[method]=dict(cold=cold,periodic=periodic);seconds[method]=time.monotonic()-before
            print(json.dumps(dict(method=method,seconds=seconds[method],iterations=periodic['boundary_iterations'],closure=closure)),flush=True)
        differences={}
        for kind in ('cold','periodic'):
            for key in ('CL','circulation','circulation_rate','CF'):
                x,y=(np.array([r[key] for r in results[m][kind]['rows']]) for m in ('DOP853','Radau'))
                # Each strip's own peak for strip variables; one vector peak for CF.
                peak=np.max(abs(y),axis=0) if key in ('circulation','circulation_rate') else np.max(abs(y))
                differences[kind+'_'+key]=float(np.max(abs(x-y)/peak))
        passed=max(differences.values())<GATES['reference_fraction']
        report=dict(passed=passed,reference=results,method_differences=differences,method_seconds=seconds)
    else:
        from isae_ua_wing_incidence_production import evaluate
        p=BASE/f'reference-{case}'/'report.json';reference=json.loads(p.read_text())
        assert reference['passed']
        reference_sha256=digest(p)
        checks=[]
        for index in range(0,160,20):
            row=reference['reference']['DOP853']['periodic']['rows'][index]
            g=np.array(row['circulation']);rate=np.array(row['circulation_rate'])
            outputs={};errors={}
            for coordinate in ('body','wind'):
                r=evaluate(g,rate,row['velocity'],row['acceleration'],alpha_deg=args.alpha,representation=coordinate)
                np.testing.assert_allclose(r['stations'],wing.stations,rtol=0,atol=2e-13)
                np.testing.assert_allclose(r['nodes'],wing.nodes,rtol=0,atol=2e-13)
                errors[coordinate]=dict(force=max(float(np.max(abs(r[key]-row[key]))) for key in ('CF','CF_rate','CF_apparent')),
                    residual=float(np.max(abs(r['residual']-row['residual']))))
                outputs[coordinate]={key:value.tolist() for key,value in r.items()}
            rotation=max(float(np.max(abs(np.array(outputs['body'][key])-outputs['wind'][key]))) for key in ('CF','CF_rate','CF_apparent','residual'))
            passed=all(v['force']<GATES['force_absolute'] and v['residual']<GATES['residual_absolute'] for v in errors.values()) and rotation<GATES['rotation_absolute']
            checks.append(dict(phase=index/160,reference=row,outputs=outputs,errors=errors,rotation_error=rotation,passed=passed))
        report=dict(passed=all(c['passed'] for c in checks),checks=checks,reference_sha256={str(p.relative_to(ROOT)):reference_sha256},
            physical_states=8,production_evaluations=16)
    unchanged=all(digest(ROOT/n)==h for n,h in pins.items())
    assert unchanged
    report.update(seconds=time.monotonic()-started,source_unchanged=unchanged,native_ASWING_comparison=False)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(case=case,action=args.action,passed=report['passed'],seconds=report['seconds'])),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
