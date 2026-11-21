"""Compare adjoint recovery on unchanged, archived full descriptor pencils."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
import time
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);loaded=importlib.util.module_from_spec(spec)
    sys.modules[name]=loaded;spec.loader.exec_module(loaded);return loaded


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--baseline',type=Path,required=True)
    args=parser.parse_args();w=args.work.resolve();candidate=args.candidate.resolve();baseline=args.baseline.resolve()
    sys.path.insert(0,str(candidate));from openswing import linear_dynamics as new
    old=module(baseline/'openswing/linear_dynamics.py','openswing._baseline_linear_dynamics')
    assert Path(new.__file__).resolve()==candidate/'openswing/linear_dynamics.py'
    pins={side:{p.name:sha(p) for p in sorted((folder/'openswing').glob('*.py'))} for side,folder in [('baseline',baseline),('candidate',candidate)]}
    assert set(pins['baseline'])==set(pins['candidate']) and len(pins['baseline'])==97
    assert [n for n in pins['baseline'] if pins['baseline'][n]!=pins['candidate'][n]]==['linear_dynamics.py']
    requests=[];reports={}
    for name in ['zero','modes']:
        path=ROOT/'docs/validation'/f'pazy-loaded-{name}.json';report=json.loads(path.read_text())
        assert report['status']=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED' and report['modules']==pins['baseline']
        reports[path.name]=sha(path);requests.extend(report['runs'])
    assert len(requests)==26
    output=w/'pencil-replay.json';out=dict(status='RUNNING',modules=pins,native_reports=reports,script_sha256=sha(__file__),requested=len(requests),rows=[])
    arrays=w/'pencils';arrays.mkdir(exist_ok=True)
    for i,request in enumerate(requests):
        cache=ROOT/request['cache'];assert sha(cache)==request['sha256'];run=json.loads(cache.read_text())
        path=ROOT/run['matrices']['path'];assert sha(path)==run['matrices']['sha256'];pencil=np.load(path);a,m=pencil['A'],pencil['M']
        before=[hashlib.sha256(v.tobytes()).hexdigest() for v in [a,m]];answers={};timing={}
        order=['baseline','candidate'] if i%2==0 else ['candidate','baseline']
        for side in order:
            solver=old if side=='baseline' else new;start=time.perf_counter();cpu=time.process_time()
            modes,report=solver.eigensystem(a,m,time_scale=run['diagnostics']['time_scale'],count=16,shift=[-.1,0.],method='dense')
            timing[side]=dict(cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-start)
            answers[side]=(modes,report)
            assert report['finite_dimension']==run['diagnostics']['finite_dimension']
        assert before==[hashlib.sha256(v.tobytes()).hexdigest() for v in [a,m]],'Input pencil mutated'
        x,y=answers['baseline'][0],answers['candidate'][0]
        ev=lambda rows:np.array([complex(*r['eigenvalue']) for r in rows])
        xv,yv=ev(x),ev(y);ii,jj=linear_sum_assignment(abs(xv[:,None]-yv)/np.maximum(1.,abs(xv[:,None])))
        comparisons=[]
        for j,k in zip(ii,jj):
            one,two=x[j],y[k];r,l=one['right'],one['left'];s,t=two['right'],two['left']
            factor=np.vdot(s,r)/np.vdot(s,s);s=s*factor;t=t/np.conj(factor)
            residue_bound=(np.linalg.norm(r-s)*np.linalg.norm(l)+np.linalg.norm(s)*np.linalg.norm(l-t))/(np.linalg.norm(r)*np.linalg.norm(l))
            mac=lambda p,q:float(abs(np.vdot(p,q))**2/(np.vdot(p,p).real*np.vdot(q,q).real))
            frequency_error=float(abs(xv[j]-yv[k])/max(1.,abs(xv[j])))
            assert frequency_error<2e-8 and mac(r,s)>1-2e-8 and mac(l,t)>1-2e-8
            assert residue_bound<2e-8,(request['specification'],xv[j],residue_bound)
            for row in [one,two]:assert max(row['left_backward_error'],row['right_backward_error'])<1e-9 and row['biorthogonal_normalized']
            comparisons.append(dict(eigenvalue=one['eigenvalue'],relative_eigenvalue_difference=frequency_error,
                right_assurance=mac(r,s),left_assurance=mac(l,t),relative_residue_error_bound=float(residue_bound),
                baseline_left_backward_error=one['left_backward_error'],candidate_left_backward_error=two['left_backward_error']))
        saved=arrays/f'case-{i:02d}.npz'
        np.savez_compressed(saved,baseline_eigenvalues=xv,candidate_eigenvalues=yv,
            baseline_right=np.array([r['right'] for r in x]),baseline_left=np.array([r['left'] for r in x]),
            candidate_right=np.array([r['right'] for r in y]),candidate_left=np.array([r['left'] for r in y]))
        row=dict(specification=request['specification'],source_cache=request['cache'],source_cache_sha256=request['sha256'],
            pencil=run['matrices'],shape=list(a.shape),nnz=dict(A=int(np.count_nonzero(a)),M=int(np.count_nonzero(m))),
            compared_modes=len(comparisons),comparisons=comparisons,timing=timing,cpu_speedup=timing['baseline']['cpu_seconds']/timing['candidate']['cpu_seconds'],
            execution_order=order,diagnostics={side:answers[side][1] for side in answers},
            arrays=dict(path=saved.relative_to(w).as_posix(),sha256=sha(saved)))
        out['rows'].append(row);output.write_text(json.dumps(out,indent=2)+'\n')
        print(i+1,len(requests),request['specification'],f"CPU speedup {row['cpu_speedup']:.3f}",row['diagnostics']['candidate']['left_recovery_counts'],flush=True)
    out['status']='PASS_UNCHANGED_PENCIL_SPECTRA_ADJOINTS_AND_RESIDUES'
    output.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
