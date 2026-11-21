"""Check the original weak-inertia guard on the finer ST-3 mesh."""
from pathlib import Path
import hashlib,json,runpy,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
ns=runpy.run_path(str(ROOT/'scripts/verify-isae-st3.py'))
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data
source=ns['CACHE']/ns['source_path']('0_3_90');model,_=ns['inspect_model'](source.read_text(),'0_3_90')
modules=ns['pins']();start=time.perf_counter()
system,_=make_system(model,panels=64,gravity=[0,0,0],structured_base=True);a,m=linearize(system)
rows=[]
for tol in [1e-9,1e-12]:
    try:roots,meta=eigensystem(a,m,time_scale=system.W,count=10,rank_tolerance=tol)
    except ValueError as exc:
        assert tol==1e-9 and 'weak inertia' in str(exc)
        rows.append(dict(rank_tolerance=tol,status='explicit_weak_inertia_rejection',error=str(exc)))
    else:
        assert meta['finite_dimension']==520
        assert max(max(r['right_backward_error'],r['left_backward_error']) for r in roots)<1e-9
        physical=[]
        for r in roots:
            if r['eigenvalue'][1]<np.pi:continue
            shape=r['right'][:6*system.network.nn].reshape(-1,6).copy();shape[:,:3]*=system.L
            physical.append(dict(eigenvalue=r['eigenvalue'],frequency_Hz=r['eigenvalue'][1]/2/np.pi,shape=complex_data(shape)))
        rows.append(dict(rank_tolerance=tol,status='computed',diagnostics=meta,physical_modes=physical))
assert rows[0]['status']=='explicit_weak_inertia_rejection' and rows[1]['status']=='computed'
baseline=json.loads((ROOT/'docs/validation/isae-st3.json').read_text())
previous=next(r['result'] for r in baseline['runs'] if r['status']=='computed' and
    all(r['identity']['specification'][k]==v for k,v in dict(name='0_3_90',panels=64,gravity=0.,speed=0.,method='full_shift_invert').items()))
physical=rows[1]['physical_modes'];comparisons=[]
for target in previous['matches'][0]['modes']:
    actual=min(physical,key=lambda r:abs(r['frequency_Hz']-target['frequency_Hz']))
    error=abs(actual['frequency_Hz']-target['frequency_Hz'])
    old=ns['physical_shapes']([previous['searches'][0]['roots'][target['root_index']]],'0_3_90').reshape(1,-1)
    new=ns['physical_shapes']([actual],'0_3_90').reshape(1,-1)
    mac=float(ns['assurance'](old,new)[0,0]);assert error<2e-6 and mac>1-2e-8
    comparisons.append(dict(label=target['label'],frequency_difference_Hz=error,physical_shape_assurance=mac))
assert ns['pins']()==modules
report=dict(status='PASS_EXPLICIT_FINE_MESH_RANK_LIMIT',modules=modules,source_sha256=ns['sha'](source),script_sha256=ns['sha'](Path(__file__)),
    seconds=time.perf_counter()-start,runs=rows,previous_full_descriptor_comparison=comparisons,
    limitation='At N64 the original input derivative is already too weak for the default rank cutoff. The guard remains explicit. A 1e-12 cutoff resolves 520 finite coordinates; only the selected roots, not the complete N64 spectrum, were checked here.',full_suite_validated=False)
(ROOT/'docs/validation/dense-staircase-rank-limit.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],round(report['seconds'],2),flush=True)
