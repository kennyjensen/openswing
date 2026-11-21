"""Native gravity-loaded modal and static studies of primary Pazy properties."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
from scipy.optimize import linear_sum_assignment
from pazy_loaded import ROOT,CACHE,GRAVITY,configuration,datasets,observables,sha
from pazy_primary_reference import matrices,modes as reference_modes
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.network import StaticNetwork,network_result
from openswing.structured_static import equilibrate
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data


def compute(spec):
    text,data,panels=configuration(spec);parsed=parse_asw(text);gravity=[0.,0.,-spec['gravity']]
    start=time.perf_counter()
    if spec['analysis']=='static':
        network=StaticNetwork(parsed,panels,None,gravity,[]);state,steps=equilibrate(network)
        result=network_result(network,state);tip=result['nodes'][-1]
        assert result['residual']<1e-8
        assert max(abs(np.array(result['force_balance'])))<1e-7
        assert max(abs(np.array(result['moment_balance'])))<1e-7
        return dict(status='computed',specification=spec,source=text,panels=panels,
            result=result,observables=observables(tip['position'],tip['rotation']),seconds=time.perf_counter()-start),None
    system,_=make_system(parsed,None,panels=panels,gravity=gravity,structured_base=True)
    base_seconds=time.perf_counter()-start
    start=time.perf_counter();a,m=linearize(system,step=1e-6);matrix_seconds=time.perf_counter()-start
    start=time.perf_counter();roots,diagnostics=eigensystem(a,m,time_scale=system.W,count=16,shift=[-.1,0.],method='dense');eigen_seconds=time.perf_counter()-start
    rows=[]
    for r in roots:
        z=complex(*r['eigenvalue'])
        if z.imag<=1e-6:continue
        q=r['right'][:6*system.network.nn].reshape(-1,6).copy();q[:,:3]*=system.L
        rows.append(dict(frequency_Hz=float(z.imag/(2*np.pi)),eigenvalue=r['eigenvalue'],shape=complex_data(q),
            right_backward_error=r['right_backward_error'],left_backward_error=r['left_backward_error']))
    assert len(rows)==8 and system.base_report()['residual']<1e-8
    assert max(max(r['right_backward_error'],r['left_backward_error']) for r in rows)<1e-9
    return dict(status='computed',specification=spec,source=text,panels=panels,base=system.base_report(),
        modes=rows,diagnostics=diagnostics,jig=system.network.rj.tolist(),
        seconds=dict(base=base_seconds,linearization=matrix_seconds,eigensystem=eigen_seconds)),(a,m)


def label_modes(run):
    spec=run['specification'];_,data,_=configuration(spec)
    reference=reference_modes(data,True)['modes']
    rotation=np.eye(3) if spec['orientation']=='horizontal' else np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    positions=np.array(run['jig'])@rotation
    ids=[int(np.argmin(np.linalg.norm(positions-p,axis=1))) for p in data['coordinates']]
    assert np.max(abs(positions[ids]-data['coordinates']))<1e-12
    shapes=[]
    for row in run['modes']:
        q=(np.array(row['shape']['real'])+1j*np.array(row['shape']['imag']))[ids]
        q[:,:3]=q[:,:3]@rotation;q[:,3:]=q[:,3:]@rotation;shapes.append(q)
    _,mass=matrices(data,True)
    a=np.array([r['shape'] for r in reference]).reshape(8,-1);b=np.array(shapes).reshape(8,-1)
    scores=abs(a.conj()@mass@b.T)**2/np.outer(np.einsum('ij,jk,ik->i',a.conj(),mass,a).real,np.einsum('ij,jk,ik->i',b.conj(),mass,b).real)
    ii,jj=linear_sum_assignment(-scores);labels=['OOP1','OOP2','T1','OOP3','IP1']
    return [dict(label=labels[i] if i<5 else f'reference_mode_{i+1}',native_index=int(j),
        frequency_Hz=run['modes'][j]['frequency_Hz'],zero_gravity_shape_assurance=float(scores[i,j])) for i,j in zip(ii,jj)]


def specifications(mode):
    if mode=='pilot':
        specs=[dict(analysis='modes',skin=s,orientation='horizontal',refinement=1,gravity=g) for g in [GRAVITY,9.81] for s in [0,1]]
        specs += [dict(analysis='static',skin=s,kind=k,mass_kg=m,orientation='horizontal',refinement=1,gravity=GRAVITY)
                  for s in [0,1] for k in ['bending','torsion'] for m in [0.,2.]]
        return specs
    if mode=='modes':
        return [dict(analysis='modes',skin=s,orientation=o,refinement=n,gravity=GRAVITY)
                for n in [1,2,4,8] for o in ['horizontal','upright'] for s in [0,1]]
    if mode=='zero':
        return [dict(analysis='modes',skin=s,orientation='horizontal',refinement=n,gravity=0.)
                for n in [1,2,4,8] for s in [0,1]] + [
                dict(analysis='modes',skin=s,orientation='upright',refinement=4,gravity=0.) for s in [0,1]]
    # All experimental masses and all nonlinear GFEM sample masses; the
    # archived dense UM/NAST curve is compared at these same load levels.
    keys=set()
    for data in datasets():
        if data['reference']=='UM/NAST' or data['linear']:continue
        for mass,*_ in data['values']:
            for n in [1,2,4]:keys.add((data['skin'],data['kind'],float(mass),n))
    return [dict(analysis='static',skin=s,kind=k,mass_kg=m,orientation='horizontal',refinement=n,gravity=GRAVITY)
            for s,k,m,n in sorted(keys,key=lambda r:(r[3],r[0],r[1],r[2]))]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['pilot','modes','static','zero'])
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    path=args.output or ROOT/'docs/validation'/f'pazy-loaded-{args.mode}.json'
    cache=ROOT/'.reference/pazy-loaded-native';cache.mkdir(exist_ok=True)
    modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    scripts={p.name:sha(p) for p in [Path(__file__),ROOT/'scripts/pazy_loaded.py',ROOT/'scripts/pazy_primary_conm2.py',ROOT/'scripts/pazy_primary.py',ROOT/'scripts/pazy_primary_reference.py']}
    specs=specifications(args.mode);out=dict(status='RUNNING',modules=modules,scripts=scripts,requested=len(specs),runs=[],datasets=datasets() if args.mode=='static' else [])
    for spec in specs:
        text,_,_=configuration(spec);identity=dict(specification=spec,modules=modules,scripts=scripts,source_sha256=hashlib.sha256(text.encode()).hexdigest())
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();cached=cache/(key+'.json')
        if cached.exists():run=json.loads(cached.read_text());assert run['identity']==identity
        else:
            try:
                run,pencil=compute(spec)
                if pencil is not None:
                    npz=cached.with_suffix('.npz');np.savez_compressed(npz,A=pencil[0],M=pencil[1]);run['matrices']=dict(path=npz.relative_to(ROOT).as_posix(),sha256=sha(npz))
            except (ValueError,RuntimeError) as e:run=dict(specification=spec,status='rejected',error=type(e).__name__+': '+str(e))
            run['identity']=identity;cached.write_text(json.dumps(run,indent=2)+'\n')
        row=dict(specification=spec,status=run['status'],cache=cached.relative_to(ROOT).as_posix(),sha256=sha(cached))
        if run['status']=='computed':
            if spec['analysis']=='modes':row['matches']=label_modes(run)
            else:row['observables']=run['observables']
        else:row['error']=run['error']
        out['runs'].append(row);path.write_text(json.dumps(out,indent=2)+'\n')
        print(len(out['runs']),len(specs),spec,run['status'],
            [(r['label'],round(r['frequency_Hz'],6)) for r in row.get('matches',[])][:5] or row.get('observables',row.get('error')),flush=True)
    out['status']='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED';path.write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
