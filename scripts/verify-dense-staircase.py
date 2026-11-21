"""Complete-spectrum regression for the ST-3 descriptor staircase repair.

Literal inputs and the independent beam reference are pinned by the preceding
ST-3 study. No material properties, loads or experimental data are adjusted.
"""
from pathlib import Path
import hashlib,json,runpy,sys,time
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data
from openswing.aero import FlightCondition

ns=runpy.run_path(str(ROOT/'scripts/verify-isae-st3.py'))
sha=ns['sha'];pins=ns['pins']

def compute(text,spec):
    model,_=ns['inspect_model'](text,spec['name'])
    condition=None if spec['speed']==0 else FlightCondition(speed=spec['speed'],alpha=0,beta=0,density=1.23,mach=0,stall=False)
    start=time.perf_counter()
    system,_=make_system(model,condition,panels=spec['panels'],gravity=[0,0,-spec['gravity']],structured_base=True)
    a,m=linearize(system);assembled=time.perf_counter()
    base=system.base_report();assert base['residual']<1e-8
    searches=[];spectra=[]
    for tolerance in [1e-9,1e-12]:
        roots,diagnostics=eigensystem(a,m,time_scale=system.W,count=100000,rank_tolerance=tolerance)
        assert max(max(r['right_backward_error'],r['left_backward_error']) for r in roots)<1e-9
        expected=(6 if spec['name']=='m15_0' else 8)*(spec['panels']+1)
        if condition is None:assert diagnostics['finite_dimension']==expected,(spec,diagnostics['finite_dimension'],expected)
        positive=sorted([r for r in roots if r['eigenvalue'][1]>np.pi],key=lambda r:r['eigenvalue'][1])
        physical=[]
        for r in positive[:8]:
            shape=r['right'][:6*system.network.nn].reshape(-1,6).copy();shape[:,:3]*=system.L
            physical.append(dict(eigenvalue=r['eigenvalue'],frequency_Hz=r['eigenvalue'][1]/(2*np.pi),shape=complex_data(shape),
                right_backward_error=r['right_backward_error'],left_backward_error=r['left_backward_error']))
        searches.append(dict(shift=[-.01,0.],rank_tolerance=tolerance,diagnostics=diagnostics,roots=physical))
        spectra.append(dict(eigenvalues=[r['eigenvalue'] for r in roots],
            right_backward_errors=[r['right_backward_error'] for r in roots],left_backward_errors=[r['left_backward_error'] for r in roots]))
    x,y=[np.array([complex(*v) for v in s['eigenvalues']]) for s in spectra]
    assert len(x)==len(y)
    cost=abs(x[:,None]-y)/np.maximum(1.,abs(y));i,j=linear_sum_assignment(cost)
    discrepancy=float(np.max(cost[i,j]));assert discrepancy<1e-8,(spec,discrepancy)
    return dict(specification=spec,seconds=time.perf_counter()-start,assembly_seconds=assembled-start,base=base,
        jig_positions=system.network.rj.tolist(),searches=searches,spectra=spectra,
        complete_spectrum_rank_refinement_error=discrepancy,
        assembly=dict(matrices=2,searches=2,reuse='One physical A/M pair reused for both complete dense spectra.'))

def main():
    baseline=json.loads((ROOT/'docs/validation/isae-st3.json').read_text());modules=pins()
    assert set(modules)==set(baseline['provenance']['modules'])
    assert {k for k in modules if modules[k]!=baseline['provenance']['modules'][k]}=={'linear_dynamics.py'}
    cache=ROOT/'.reference/dense-staircase';cache.mkdir(exist_ok=True)
    specs=[dict(name=name,panels=n,gravity=g,speed=0.) for name in ['0_3_90','p15_0','m15_0'] for n in [8,16,32] for g in [0.,9.81]]
    specs += [dict(name=name,panels=16,gravity=9.81,speed=.01) for name in ['0_3_90','p15_0','m15_0']]
    rows=[]
    for spec in specs:
        path=ns['source_path'](spec['name']);source=ns['CACHE']/path
        assert sha(source)==baseline['provenance']['sources'][path]['sha256']
        identity=dict(specification=spec,modules=modules,source_sha256=sha(source),script_sha256=sha(Path(__file__)),
            baseline_sha256=sha(ROOT/'docs/validation/isae-st3.json'))
        file=cache/(hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()+'.json')
        if file.exists():
            row=json.loads(file.read_text());assert row['identity']==identity
        else:
            result=compute(source.read_text(),spec)
            reference=baseline['references'][spec['name']][str(spec['gravity'])][-1]
            result['matches']=ns['match'](result,reference)
            previous=next(r['result'] for r in baseline['runs'] if r['status']=='computed' and
                all(r['identity']['specification'][k]==v for k,v in spec.items()) and
                r['identity']['specification']['method']=='full_shift_invert' and r['identity']['specification']['step']==1e-5)
            comparisons=[]
            for old,new in zip(previous['matches'][0]['modes'],result['matches'][0]['modes']):
                assert old['label']==new['label']
                error=abs(old['frequency_Hz']-new['frequency_Hz'])
                oldshape=ns['physical_shapes']([previous['searches'][0]['roots'][old['root_index']]],spec['name']).reshape(1,-1)
                newshape=ns['physical_shapes']([result['searches'][0]['roots'][new['root_index']]],spec['name']).reshape(1,-1)
                mac=float(ns['assurance'](oldshape,newshape)[0,0])
                assert error<2e-6 and mac>1-2e-8,(spec,old['label'],error,mac)
                comparisons.append(dict(label=old['label'],frequency_difference_Hz=error,physical_shape_assurance=mac))
            row=dict(identity=identity,result=result,previous_full_descriptor_comparison=comparisons)
            assert pins()==modules;file.write_text(json.dumps(row,indent=2)+'\n')
        rows.append(row);print(spec,'dimension',row['result']['searches'][0]['diagnostics']['finite_dimension'],'seconds',round(row['result']['seconds'],2),flush=True)
    report=dict(status='PASS_ST3_COMPLETE_SPECTRA_AND_PHYSICAL_MODES',modules=modules,baseline_modules=baseline['provenance']['modules'],
        baseline_sha256=sha(ROOT/'docs/validation/isae-st3.json'),script_sha256=sha(Path(__file__)),runs=rows,
        full_suite_validated=False,goal_complete=False,
        remaining='Experimental discrepancies, input/property conflicts, static comparisons and 31 other ISAE families remain unresolved.')
    (ROOT/'docs/validation/dense-staircase.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
