"""Check literal ST-4 modes against independent energy integrals and refinement."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from isae_st4_reference import LENGTH,CG_X,EA_X,MASS,T0

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def weighted(nodes,shapes,points,rotary):
    grid=np.linspace(0,LENGTH,513);ds=grid[1]-grid[0];weights=np.full(len(grid),ds);weights[[0,-1]]*=.5
    rows=[]
    for shape in shapes:
        h,dh,phi=[np.interp(grid,nodes,shape[:,j]) for j in range(3)]
        values=np.column_stack([np.sqrt(MASS)*(h+(CG_X-EA_X)*phi),np.sqrt(rotary)*dh,np.sqrt(rotary)*phi])*np.sqrt(weights[:,None])
        point_velocities=[]
        for mass,t,x,y,z in points:
            s=(t-T0)*LENGTH/(LENGTH-T0);v=np.array([np.interp(s,nodes,shape[:,j]) for j in range(3)])
            point_velocities.append(np.sqrt(mass)*(v[0]+(z-s)*v[1]+(x-EA_X)*v[2]))
        rows.append(np.r_[values.ravel(),point_velocities])
    return np.array(rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work
    native=json.loads((w/'st4-native.json').read_text());ref=json.loads((w/'st4-reference.json').read_text())
    transfer=json.loads((w/'transfer.json').read_text())
    assert transfer['status']=='PASS_CONTINUOUS_TRANSFER_REFERENCE'
    assert transfer['script_sha256']==sha(ROOT/'scripts/verify-isae-st4-transfer.py')
    assert transfer['reference_sha256']==sha(ROOT/'scripts/isae_st4_transfer.py')
    assert transfer['energy_reference_sha256']==sha(w/'st4-reference.json')
    continuous={r['source_sha256']:np.array(r['frequencies_Hz']) for r in transfer['rows']}
    assert native['status']=='COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED'
    assert ref['status']=='INDEPENDENT_REFERENCE_COMPUTED_NOT_PHYSICALLY_VALIDATED'
    assert native['modules']==ref['native_modules']
    assert native['script_sha256']==sha(ROOT/'scripts/verify-isae-st4.py')
    assert ref['reference_sha256']==sha(ROOT/'scripts/isae_st4_reference.py')
    assert ref['script_sha256']==sha(ROOT/'scripts/verify-isae-st4-reference.py')
    references={}
    for r in ref['runs']:
        path=ROOT/r['cache'];assert sha(path)==r['sha256'];references[r['source_sha256'],r['elements']]=json.loads(path.read_text())
    rows=[];groups={}
    for row in native['runs']:
        path=ROOT/row['cache'];assert sha(path)==row['sha256'];r=json.loads(path.read_text());assert r['status']=='computed'
        assert sha(ROOT/r['matrices']['path'])==r['matrices']['sha256'];data=r['result'];key=row['specification']['source_sha256']
        eigen=sorted([v for v in data['modes'] if v['eigenvalue'][1]>0],key=lambda x:x['frequency']);assert len(eigen)==6
        assert data['diagnostics']['base_residual']<1e-8
        assert all(max(v['left_backward_error'],v['right_backward_error'])<1e-9 for v in eigen)
        frequency=np.array([v['frequency'] for v in eigen]);reference=references[key,256];exact=continuous[key]
        nodes=np.array([v['position'][2] for v in data['base']['nodes']]);shapes=[]
        for mode in eigen:
            u=np.array([v['displacement']['real'] for v in mode['output']['nodes']])+1j*np.array([v['displacement']['imag'] for v in mode['output']['nodes']])
            rotation=np.array([v['rotation']['real'] for v in mode['output']['nodes']])+1j*np.array([v['rotation']['imag'] for v in mode['output']['nodes']])
            shapes.append(np.column_stack([u[:,1]+EA_X*rotation[:,2],-rotation[:,0],rotation[:,2]]))
        points=reference['identity']['points'];rotary=reference['identity']['rotary']
        x=weighted(nodes,shapes,points,rotary);y=weighted(reference['result']['nodes'],np.array(reference['result']['shapes']),points,rotary)
        mac=abs(np.sum(x.conj()*y,axis=1))**2/(np.sum(abs(x)**2,axis=1)*np.sum(abs(y)**2,axis=1))
        delta=abs(frequency/exact-1)
        r=dict(paths=row['paths'],source_sha256=key,panels=row['specification']['panels'],
               frequencies_Hz=frequency.tolist(),independent_frequencies_Hz=exact.tolist(),relative_errors=delta.tolist(),
               kinetic_shape_assurance=mac.tolist(),finite_dimension=data['diagnostics']['finite_dimension'])
        rows.append(r);groups.setdefault(key,[]).append(r)
    checks=[]
    for key,runs in groups.items():
        runs=sorted(runs,key=lambda r:r['panels']);assert [r['panels'] for r in runs]==[8,16,32]
        errors=np.array([r['relative_errors'] for r in runs]);assert np.all(np.diff(errors,axis=0)<0),(runs[0]['paths'],errors)
        frequencies=np.array([references[key,n]['result']['frequencies_Hz'] for n in [64,128,256]])
        steps=abs(np.diff(frequencies,axis=0));reference_errors=abs(frequencies/continuous[key]-1)
        # Dense energy solves can reach an absolute roundoff floor on low
        # eigenvalues. Bound their error against the continuous solution;
        # retain nonmonotonic cases rather than asserting strict refinement.
        assert np.max(reference_errors[-1])<1e-4,(key,reference_errors)
        checks.append(dict(source_sha256=key,independent_relative_change_128_to_256=(steps[1]/frequencies[-1]).tolist(),
                           energy_reference_errors=reference_errors.tolist(),
                           energy_nonmonotonic_modes=(np.where(steps[1]>=steps[0])[0]+1).tolist(),
                           native_error_reduction_16_to_32=(errors[1]/errors[2]).tolist()))
    fine=[r for r in rows if r['panels']==32]
    result=dict(status='PASS_LITERAL_ST4_NUMERICAL_REFERENCE_AND_MESH_CHECKS_NOT_EXPERIMENTAL_VALIDATION',
                modules=native['modules'],script_sha256=sha(__file__),native_report_sha256=sha(w/'st4-native.json'),
                independent_report_sha256=sha(w/'st4-reference.json'),transfer_report_sha256=sha(w/'transfer.json'),
                native_states=len(rows),independent_states=len(ref['runs']),continuous_models=len(continuous),
                unique_models=len(groups),matched_modes=len(rows)*6,rows=rows,refinement=checks,
                maximum_N32_frequency_error=max(max(r['relative_errors']) for r in fine),
                minimum_N32_kinetic_shape_assurance=min(min(r['kinetic_shape_assurance']) for r in fine),
                maximum_reference_refinement_change=max(max(r['independent_relative_change_128_to_256']) for r in checks),
                maximum_energy_reference_error=max(max(r['energy_reference_errors'][-1]) for r in checks),
                full_physical_validation=False,
                limitations=['Literal input values are retained, including .0078 versus .0035 rotary-inertia inconsistency.',
                    'The reference compares the same literal physical model, independently discretized; it is not an independent reconstruction of the experiment.',
                    'All runs use gravity=0 and omit aerodynamic/apparent-mass loads. Actual hanging still-air measurements require a separate setup reconciliation.',
                    'Primary NACA frequency rows and ISAE CSV discrepancies remain to be reconciled. No experimental pass or flutter prediction is claimed.'])
    (w/'structural-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','native_states','independent_states','unique_models','matched_modes',
        'maximum_N32_frequency_error','minimum_N32_kinetic_shape_assurance','maximum_reference_refinement_change']},indent=2))


if __name__=='__main__':main()
