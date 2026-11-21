"""Pazy modal mesh study with pinned source and independent beam comparisons."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import numpy as np
from scipy.optimize import linear_sum_assignment
from isae_st2 import ROOT, CACHE, sha, modal_model
from isae_st2_modal_reference import modes as reference_modes, assurance
from openswing.linear_dynamics import make_system, linearize, eigensystem, complex_data


def compute(spec):
    model,text,reconstruction=modal_model(spec['orientation'])
    system,steps=make_system(model,None,panels=spec['panels'],gravity=[0.,0.,-spec['gravity']],structured_base=True)
    a,m=linearize(system,step=1e-6)
    roots,diagnostics=eigensystem(a,m,time_scale=system.W,count=16,shift=[-.1,0.],method='dense')
    rows=[]
    for r in roots:
        z=complex(*r['eigenvalue'])
        if z.imag<=1e-6:continue
        q=r['right'][:6*system.network.nn].reshape(-1,6).copy();q[:,:3]*=system.L
        rows.append(dict(frequency_Hz=float(z.imag/(2*np.pi)),eigenvalue=r['eigenvalue'],shape=complex_data(q),
            right_backward_error=r['right_backward_error'],left_backward_error=r['left_backward_error']))
    return dict(specification=spec,status='computed',modes=rows,diagnostics=diagnostics,base=system.base_report(),
        jig=system.network.rj.tolist(),derived_source=text,reconstruction=reconstruction),a,m


def match(run,reference):
    upright=run['specification']['orientation']=='upright'
    physical=[]
    for row in run['modes']:
        q=np.array(row['shape']['real'])+1j*np.array(row['shape']['imag'])
        cg=q[:,:3]+np.cross(q[:,3:],[-.005,0.,0.])
        physical.append(np.column_stack([-cg[:,1] if upright else cg[:,2],cg[:,0],q[:,5] if upright else q[:,4]]))
    nodes=np.array(run['jig'])[:,2 if upright else 1]
    scores=assurance(reference,nodes,np.asarray(physical))
    wanted=['OOP1','OOP2','T1','IP1','OOP3'];ri=[reference['labels'].index(k) for k in wanted]
    ii,jj=linear_sum_assignment(-scores[ri]);out=[]
    for i,j in zip(ii,jj):
        index=ri[i];row=run['modes'][j]
        out.append(dict(label=wanted[i],frequency_Hz=row['frequency_Hz'],reference_Hz=reference['frequencies_Hz'][index],
            relative_difference=row['frequency_Hz']/reference['frequencies_Hz'][index]-1,shape_assurance=float(scores[index,j]),mode_index=int(j)))
    return out


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'docs/validation/isae-st2-modes.json')
    parser.add_argument('--cache',type=Path,default=ROOT/'.reference/isae-st2-modal-runs');args=parser.parse_args();args.cache.mkdir(parents=True,exist_ok=True)
    modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    scripts={p.name:sha(p) for p in [Path(__file__),ROOT/'scripts/isae_st2.py',ROOT/'scripts/isae_st2_modal_reference.py']}
    references={str(g):[reference_modes(n,g) for n in [48,96,192]] for g in [0.,9.81]}
    out=dict(status='RUNNING',modules=modules,scripts=scripts,references=references,runs=[])
    for panels in [8,16,32,64]:
        for gravity in [0.,9.81]:
            for orientation in ['upright','horizontal']:
                spec=dict(orientation=orientation,panels=panels,gravity=gravity)
                _,_,proof=modal_model(orientation)
                identity=dict(specification=spec,modules=modules,scripts=scripts,source_sha256=proof['source_sha256'])
                key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=args.cache/(key+'.json')
                if path.exists():
                    run=json.loads(path.read_text());assert run['identity']==identity
                else:
                    start=time.perf_counter()
                    try:
                        run,a,m=compute(spec)
                        matrices=path.with_suffix('.npz');np.savez_compressed(matrices,A=a,M=m)
                        run['matrices']=dict(path=str(matrices.relative_to(ROOT)),sha256=sha(matrices),shape=list(a.shape))
                    except (ValueError,RuntimeError) as exc:
                        run=dict(specification=spec,status='rejected',error=type(exc).__name__+': '+str(exc))
                    run.update(identity=identity,seconds=time.perf_counter()-start);path.write_text(json.dumps(run,indent=2)+'\n')
                if run['status']=='computed':
                    assert run['base']['residual'] < 1e-8
                    assert max(max(r['right_backward_error'],r['left_backward_error']) for r in run['modes'])<1e-9
                    # Horizontal gravity changes the equilibrium geometry; a
                    # zero-gravity reference is used only for mode labeling.
                    ref=references[str(gravity if orientation=='upright' else 0.)][-1]
                    matches=match(run,ref)
                else:matches=[]
                record=dict(specification=spec,status=run['status'],cache=str(path.relative_to(ROOT)),sha256=sha(path),matches=matches)
                if run['status']!='computed':record['error']=run['error']
                out['runs'].append(record);args.output.write_text(json.dumps(out,indent=2)+'\n')
                print(spec,run['status'],[(r['label'],round(r['frequency_Hz'],6),round(r['shape_assurance'],5)) for r in matches] or run.get('error'),flush=True)
    out.update(status='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED',
        limits=['Two zero physical objects removed explicitly; original literal files still reject.',
            'No aerodynamic apparent mass: condition=None. Both gravity-free and gravity-loaded orientations are separate.',
            'Original simplified section properties remain unchanged and unfitted.',
            'Independent linear reference neglects finite axial shortening. Horizontal loaded reference is for labels only.',
            'Primary experimental table labels identify skin-on frequencies; the ISAE summary caption skin-off is inconsistent.',
            'No full modal or experimental-validation pass is asserted.'])
    args.output.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
