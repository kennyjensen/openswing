"""Primary Pazy section/inertia mapping, exact-reference and native modal study."""
from pathlib import Path
import argparse
import json
import hashlib
import sys
import time
import numpy as np
from scipy.optimize import linear_sum_assignment
from pazy_primary import ROOT,CACHE,FOLDER,source,projection,model,mesh,sha
from pazy_primary_reference import modes as reference_modes
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.structure import Section
from openswing.inertia import point_tensor
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data

LABELS=['OOP1','OOP2','T1','OOP3','IP1']


def mapping():
    records=[];models={}
    for skin in [0,1]:
        data=source(skin);stiffness=[]
        for i,k in enumerate(data['stiffness']):
            fields,projected,bound=projection(k);native=np.diag([1,1,-1,1])@projected@np.diag([1,1,-1,1])
            s=Section(**fields).compliance()[np.ix_([1,4,3,5],[1,4,3,5])]
            error=float(np.max(abs(np.linalg.inv(s)-native)/np.sqrt(np.outer(np.diag(native),np.diag(native)))))
            assert error<1e-12
            stiffness.append(dict(element=i+1,stations_m=data['coordinates'][i:i+2,1].tolist(),
                full_primary=k.tolist(),projected_primary=projected.tolist(),asw_fields=fields,
                max_strain_energy_relative_perturbation=bound,scaled_mapping_error=error))
        for orientation in ['horizontal','upright']:
            text,_=model(skin,orientation);parsed=parse_asw(text)
            rotation=np.eye(3) if orientation=='horizontal' else np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
            for i,row in enumerate(parsed.records['weight']):
                assert abs(row[5]/9.81-data['mass'][i])<1e-15
                assert np.max(abs(row[2:5]-(data['coordinates'][i]+data['offset'][i])@rotation.T))<1e-15
                assert np.max(abs(point_tensor(row,9.81)-rotation@data['inertia'][i]@rotation.T))<1e-18
            for i,fields in enumerate([r['asw_fields'] for r in stiffness]):
                station=1+np.mean(data['coordinates'][i:i+2,1])
                for key,value in fields.items():assert abs(parsed.beams[0].value(key,station)-value)<1e-12*max(1,abs(value))
            path=ROOT/'examples'/f'pazy-primary-skin{skin}-{orientation}.asw';path.write_text(text)
            models[f'skin{skin}_{orientation}']=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),
                                                   reference_axis_fraction=.441,physical_length_m=float(data['coordinates'][-1,1]))
        refs={name:reference_modes(data,projected) for name,projected in [('full',False),('asw_projection',True)]}
        archived=np.loadtxt(CACHE/f'03_2023_JA_Riso_Cesnik/01_Modal_Undeformed/06_Beam_Final/frequencies_skin{skin}.txt')
        assert len(archived)==5
        records.append(dict(skin=skin,sources=data['sources'],mass_kg=float(data['mass'].sum()),stiffness=stiffness,references=refs,
            archived_um_frequencies_Hz=dict(zip(LABELS,archived.tolist())),
            full_vs_projected_frequency_differences_Hz=[a['frequency_Hz']-b['frequency_Hz'] for a,b in zip(refs['full']['modes'],refs['asw_projection']['modes'])]))
    return dict(records=records,models=models)


def compute(spec):
    text,data=model(spec['skin'],spec['orientation']);parsed=parse_asw(text);panels=mesh(data,spec['refinement'])
    start=time.perf_counter()
    system,_=make_system(parsed,None,panels=panels,gravity=[0.,0.,0.],structured_base=True)
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
    return dict(specification=spec,status='computed',source=text,panels=panels,base=system.base_report(),modes=rows,
        jig=system.network.rj.tolist(),diagnostics=diagnostics,
        seconds=dict(base=base_seconds,linearization=matrix_seconds,eigensystem=eigen_seconds)),a,m


def comparisons(run,ref,data):
    positions=np.array(run['jig']);upright=run['specification']['orientation']=='upright'
    rotation=np.eye(3) if not upright else np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    positions=positions@rotation
    ids=[int(np.argmin(np.linalg.norm(positions-p,axis=1))) for p in data['coordinates']]
    assert np.max(abs(positions[ids]-data['coordinates']))<1e-12
    shapes=[]
    for r in run['modes']:
        q=(np.array(r['shape']['real'])+1j*np.array(r['shape']['imag']))[ids]
        q[:,:3]=q[:,:3]@rotation;q[:,3:]=q[:,3:]@rotation;shapes.append(q)
    # Nodal kinetic-energy inner product from the independently assembled M.
    from pazy_primary_reference import matrices
    _,mass=matrices(data,True)
    a=np.array([r['shape'] for r in ref['modes']]).reshape(len(ref['modes']),-1)
    b=np.array(shapes).reshape(len(shapes),-1)
    scores=abs(a.conj()@mass@b.T)**2/np.outer(np.einsum('ij,jk,ik->i',a.conj(),mass,a).real,np.einsum('ij,jk,ik->i',b.conj(),mass,b).real)
    ii,jj=linear_sum_assignment(-scores)
    rows=[]
    for i,j in zip(ii,jj):
        f=run['modes'][j]['frequency_Hz'];expected=ref['modes'][i]['frequency_Hz']
        rows.append(dict(reference_index=int(i),native_index=int(j),label=LABELS[i] if i<5 else f'reference_mode_{i+1}',
            frequency_Hz=f,reference_Hz=expected,relative_difference=f/expected-1,mass_weighted_shape_assurance=float(scores[i,j])))
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'docs/validation/pazy-primary-mapping.json')
    parser.add_argument('--cache',type=Path,default=ROOT/'.reference/pazy-primary-native')
    parser.add_argument('--pilot',action='store_true');args=parser.parse_args();args.cache.mkdir(parents=True,exist_ok=True)
    mapped=mapping();modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    scripts={p.name:sha(p) for p in [Path(__file__),ROOT/'scripts/pazy_primary.py',ROOT/'scripts/pazy_primary_reference.py']}
    report=dict(status='RUNNING',modules=modules,scripts=scripts,mapping=mapped,runs=[],
        sources=dict(repository='https://github.com/UM-A2SRL/AePW3-LDWG',revision='396710a19a80004c65c767e9955fe60d59565c39'),
        limits=['Intrinsic axial/torsion K12 is explicitly removed to fit documented ASWING section fields; all remaining constants are mapped exactly.',
            'Full primary stiffness and its projected counterpart are both evaluated by an independent exact linear nodal-mass beam.',
            'The reference axis is .441 chord in the paper and rounded to .44 in the README. No aerodynamic validation is claimed.',
            'Reference K/M have no distributed mass. Original nodal inertia locations and full tensors are retained, including root mass constrained by the clamp.',
            'Primary UM/NAST uses a different finite-element discretization; its coarse frequencies are not assumed to be a continuum reference.',
            'Gravity-free comparisons do not establish loaded/static/experimental validation. Original literal Pazy attachment behavior is still unresolved.'])
    specs=[dict(skin=skin,orientation='horizontal',refinement=n) for n in ([1,4] if args.pilot else [1,2,4,8]) for skin in ([0] if args.pilot else [0,1])]
    if not args.pilot:specs+=[dict(skin=skin,orientation='upright',refinement=4) for skin in [0,1]]
    for spec in specs:
        text,data=model(spec['skin'],spec['orientation'])
        identity=dict(specification=spec,modules=modules,scripts=scripts,source_sha256=hashlib.sha256(text.encode()).hexdigest())
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=args.cache/(key+'.json')
        if path.exists():
            run=json.loads(path.read_text());assert run['identity']==identity
        else:
            try:
                run,a,m=compute(spec);npz=path.with_suffix('.npz');np.savez_compressed(npz,A=a,M=m)
                run['matrices']=dict(path=npz.relative_to(ROOT).as_posix(),sha256=sha(npz),shape=list(a.shape))
            except (ValueError,RuntimeError) as e:run=dict(status='rejected',specification=spec,error=type(e).__name__+': '+str(e))
            run['identity']=identity;path.write_text(json.dumps(run,indent=2)+'\n')
        row=dict(specification=spec,status=run['status'],cache=path.relative_to(ROOT).as_posix(),sha256=sha(path))
        if run['status']=='computed':
            assert run['base']['residual']<1e-8
            assert max(max(r['left_backward_error'],r['right_backward_error']) for r in run['modes'])<1e-9
            row.update(comparisons=comparisons(run,mapped['records'][spec['skin']]['references']['asw_projection'],data),seconds=run['seconds'])
        else:row['error']=run['error']
        report['runs'].append(row);args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(spec,row['status'],[(r['label'],round(r['frequency_Hz'],6),round(r['mass_weighted_shape_assurance'],6)) for r in row.get('comparisons',[])],flush=True)
    report['status']='PILOT_COMPLETE' if args.pilot else 'COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED'
    args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
