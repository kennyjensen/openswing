#!/usr/bin/env python3
"""Evaluate fixed discrete operators on archived ST5 rows and saved candidate rows.

No equilibrium solve or production module import. Prepare pins original source,
independent polynomial coefficients, output decoding, and all saved inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
HELPER=ROOT/'scripts/isae_drela_discrete_diagnostic.py'
TARGET=ROOT/'docs/validation/isae-st5-reference-target.json'
BASIS=Path('/tmp/openswing-isae-st5-spline-observables-20261025/report.json')
RUN=Path('/tmp/openswing-isae-st5-spline-candidate-r2-20261025')


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x): p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def prepare(stage):
    files=[Path(__file__),HELPER,TARGET,BASIS,ROOT/'examples/isae-st5-static-20lb_80_20.asw',
           ROOT/'.reference/asw_theory.pdf']+[RUN/f'level{i}/comparison.json' for i in [0,2,4]]
    assert not (stage/'plan.json').exists()
    write(stage/'plan.json',dict(status='PREDECLARED_ARCHIVE_AND_SAVED_OPERATOR_DIAGNOSTIC',
        pins={str(p):sha(p) for p in files},kernel_pins={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'openswing').glob('*.py')},
        source_datasets=['archive/natural','archive/zero_third','candidate/level0','candidate/level2','candidate/level4'],
        interval_rule='All70 nonzero adjacent archive intervals, exact known anchors and printed centers otherwise; no fitting. Native samples also evaluated on this same archive node grid, not each native element grid.',
        frame_rule='Arithmetic endpoint T and K matrices, body resultants averaged before transformation. Preferred Eq53 Euler formulation; differences do not cross a branch cut.',
        bending_rule='Eq54 rendered E_a^{-1}: invert average endpoint stiffness. Earlier text-only average-inverse reading is superseded. Retain average-compliance alternative as labeled diagnostic.',
        axial_rule='Fs_a/EA_a, explicitly qualified since Eq48 does not print the scalar property average.',
        lengths=['unloaded_spline_arc','unloaded_endpoint_chord'],
        length_qualification='Eq48 explicitly specifies unloaded arc; chord is a comparison only. Eqs54–56 use ds without a specified historical finite-strain algorithm. Evaluate declared ds=ds0, not a claim of exact historical length.',
        jig_rule='Report absolute Eq48 and separate unloaded jig defect; do not silently subtract the latter from the source equation.',
        reference_rule='Report defects and magnitudes without widening output precision or asserting joint interval feasibility.',
        equilibrium_solves=0,production_imports=0,new_production_residuals=0))
    print(json.dumps(dict(prepared=str(stage/'plan.json'))))


def run(stage):
    import numpy as np
    from scipy.integrate import quad
    from isae_drela_discrete_diagnostic import transform, angles_from_frame, operators, algebra_checks
    plan=json.loads((stage/'plan.json').read_text())
    assert all(sha(p)==h for p,h in plan['pins'].items())
    basis=json.loads(BASIS.read_text());target=json.loads(TARGET.read_text())
    def val(kind,beam,name,t,derivative=False):
        c=basis['candidates'][kind]['coefficients'][f'{beam}/{name}']
        x=np.array(c['x'],float);t=abs(t);i=np.clip(np.searchsorted(x,t,side='right')-1,0,len(x)-2)
        a,b,c,d=map(float,c['local_cubic_coefficients'][i]);u=t-x[i]
        return b+u*(2*c+3*u*d) if derivative else a+u*(b+u*(c+u*d))
    def geometry(kind,beam,t,side):
        sign=-1 if t<0 or (t==0 and side=='left') else 1
        r=np.array([val(kind,beam,n,t) for n in ['x','y','z']]);r[1]*=sign
        dx,dy,dz=[val(kind,beam,n,t,True) for n in ['x','y','z']]
        angles=np.array([sign*np.arctan2(dz,dy),0.,sign*np.arctan2(-dx,np.hypot(dy,dz))])
        return r,angles
    def endpoint(kind,block,k,native=None):
        row=block['rows'][k];v=np.array(row['physical']);t=row['printed_t'] if row['exact_anchor_t'] is None else row['exact_anchor_t']
        side='right' if k==0 or (k and block['rows'][k-1]['printed_t']==row['printed_t']) else 'left'
        r0,q0=geometry(kind,block['beam'],t,side)
        if native is None:
            q=np.deg2rad(v[4:7]);T=transform(q)
            r=r0+np.array([v[1],v[2]-r0[1],v[3]]);F=T.T@v[10:13];M=T.T@v[7:10]
        else:
            q=angles_from_frame(np.array(native['frame']));r=np.array(native['position'])
            F=np.array(native['force_body']);M=np.array(native['moment_body'])
        E=np.diag([val(kind,block['beam'],n,t) for n in ['EIcc','GJ','EInn']])
        return dict(r=r,r0=r0,angles=q,angles0=q0,F=F,M=M,E=E,EA=val(kind,block['beam'],'EA',t),
            f=np.array([0.,0.,-val(kind,block['beam'],'mg',t)-val(kind,block['beam'],'Dmg',t)]),t=t,line=row['source_line'])
    results=[]
    for dataset in plan['source_datasets']:
        kind=dataset.split('/')[1] if dataset.startswith('archive/') else 'zero_third'
        saved=None
        if dataset.startswith('candidate/'):
            saved=json.loads((RUN/dataset.split('/')[1]/'comparison.json').read_text())['rows']
            saved={r['source_line']:r for r in saved}
        for block in target['beams']:
            nodes=[endpoint(kind,block,k,None if saved is None else saved[row['source_line']]) for k,row in enumerate(block['rows'])]
            for a,b in zip(nodes,nodes[1:]):
                if a['t']==b['t']:continue
                beam=block['beam']
                def speed(t):return np.linalg.norm([val(kind,beam,n,t,True) for n in ['x','y','z']])
                knots=sorted({abs(float(t)) for n in ['x','y','z'] for t in basis['candidates'][kind]['coefficients'][f'{beam}/{n}']['x']})
                lo,hi=sorted([abs(a['t']),abs(b['t'])]);assert lo<hi
                arc,error=quad(speed,lo,hi,epsabs=1e-12,epsrel=1e-12,points=[k for k in knots if lo<k<hi])
                chord=float(np.linalg.norm(b['r0']-a['r0']))
                for length,ds in [('unloaded_spline_arc',arc),('unloaded_endpoint_chord',chord)]:
                    o=operators(a,b,ds,ds)
                    results.append(dict(dataset=dataset,beam=beam,lines=[a['line'],b['line']],t=[a['t'],b['t']],length_policy=length,
                        ds0=ds,ds=ds,arc_quadrature_error=error,
                        operators={k:v.tolist() if isinstance(v,np.ndarray) else float(v) for k,v in o.items()}))
    metrics={}
    fields=['curvature_defect','alternative_average_compliance_defect','compatibility_defect','jig_compatibility_defect',
            'incremental_compatibility_diagnostic','force_balance','moment_balance']
    for dataset in plan['source_datasets']:
        for length in plan['lengths']:
            rr=[r for r in results if r['dataset']==dataset and r['length_policy']==length]
            assert len(rr)==70
            metrics[dataset+'/'+length]={}
            for field in fields:
                values=np.array([r['operators'][field] for r in rr]);j=np.unravel_index(np.argmax(abs(values)),values.shape)
                metrics[dataset+'/'+length][field]=dict(max_abs=float(np.max(abs(values))),rms=float(np.sqrt(np.mean(values**2))),
                    max_by_component=np.max(abs(values),axis=0).tolist(),worst_lines=rr[j[0]]['lines'])
    checks=algebra_checks();assert all(c['passes'] for c in checks)
    report=dict(status='COMPLETE_DISCRETE_OPERATOR_DIAGNOSTIC_NOT_REFERENCE_PASS',plan_sha256=sha(stage/'plan.json'),
        primary_correction=plan['bending_rule'],datasets=plan['source_datasets'],interval_evaluations=len(results),
        unique_intervals_per_dataset=70,metrics=metrics,algebra_checks=checks,rows=results,
        qualifications=[plan[k] for k in ['interval_rule','axial_rule','length_qualification','jig_rule','reference_rule']],
        equilibrium_solves=0,production_imports=0,new_production_residuals=0,goal_complete=False)
    write(stage/'report.json',report)
    write(stage/'summary.json',{k:v for k,v in report.items() if k not in ['rows','algebra_checks']})
    assert all(sha(p)==h for p,h in plan['pins'].items())
    assert all(sha(ROOT/p)==h for p,h in plan['kernel_pins'].items())
    print(json.dumps(dict(status=report['status'],evaluations=len(results),algebra_checks=len(checks),metrics=metrics['archive/zero_third/unloaded_spline_arc'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--stage',type=Path,required=True)
    args=p.parse_args();args.stage.mkdir(parents=True,exist_ok=True);(prepare if args.action=='prepare' else run)(args.stage)
