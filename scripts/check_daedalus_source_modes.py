"""Small serial modal diagnostics of the accepted current Daedalus pencil.

Drela unsteady Eqs.145--149 and 177--189. No aircraft parameter is changed.
Unobservable Earth position/heading integrators are eliminated by exact row
operations before the pole query; their response is not an output here.
"""
import argparse
from pathlib import Path
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-source-modes-20261114'
CHANNELS=['yaw_rate','roll_rate','sideslip','bank']


def load_modes(tag,side):
    import numpy as np
    with np.load(STUDY/tag/'arrays.npz') as archive:
        data={key:archive[key] for key in archive.files}
    if side+'_vectors' in data:data['vectors']=data[side+'_vectors']
    if side+'_values' in data:data['values']=data[side+'_values']
    return data


def matrices():
    import numpy as np
    import scipy.sparse as sp
    base=SOURCE/'assembled-6.7'
    a,m=(sp.load_npz(base/name).tocsc() for name in ('A.npz','M.npz'))
    maps=np.load(base/'maps.npz');b=maps['B'][:,0];c=maps['C']
    layout=read(SOURCE/'mass-6.7/layout.json');frame=layout['frame']['start'];size=frame+12
    assert layout['frame']['width']==12 and layout['feedback'] is None
    assert a.shape==m.shape==(size,size)
    position=frame+np.array([6,7,8]);first=np.delete(np.arange(size),position)
    assert np.max(abs(a[first,:][:,position].data),initial=0)==0
    assert np.max(abs(m[first,:][:,position].data),initial=0)==0
    assert np.max(abs(c[:,position]),initial=0)==0
    a=a[first,:][:,first];m=m[first,:][:,first];b=b[first];c=c[:,first]
    removed=np.flatnonzero(first==frame+11);keep=np.delete(np.arange(len(first)),removed)
    assert np.max(abs(a[:,removed].data),initial=0)==0
    assert np.max(abs(c[:,removed]),initial=0)==0
    # Heading rate enters the bank/elevation equations at a pitched base.
    # Merely deleting matching rows/columns would change these equations.
    # Eliminate heading rate using its own equation, after removing Earth
    # position. Heading itself drives Earth position, but neither feeds back.
    d=m[removed,:][:,removed].toarray()
    transform=sp.csc_matrix(np.linalg.solve(d.T,m[keep,:][:,removed].toarray().T).T)
    ar=a[keep,:]-transform@a[removed,:]
    mr=m[keep,:]-transform@m[removed,:]
    assert np.max(abs(mr[:,removed].data),initial=0)<2e-15
    return ar[:,keep].tocsc(),mr[:,keep].tocsc(),b[keep]-transform@b[removed],c[:,keep],first[keep]


def poles(folder,args):
    import numpy as np
    from scipy.sparse.linalg import splu,LinearOperator,eigs
    a,m,b,c,keep=matrices();shift=args['shift'];side=args['side']
    lu=splu((a-shift*m).tocsc());calls=[0]
    aa,mm=(a,m) if side=='right' else (a.T,m.T)
    def action(v):
        calls[0]+=1
        return lu.solve(mm@v,trans='N' if side=='right' else 'T')
    operator=LinearOperator(a.shape,matvec=action,dtype=float)
    seed=np.random.default_rng(90351).standard_normal(len(keep))
    values,vectors=eigs(operator,k=args['count'],which='LM',v0=seed,
        ncv=max(2*args['count']+8,64),tol=2e-11,maxiter=1000)
    values=shift+1/values;order=np.argsort(abs(values));values=values[order];vectors=vectors[:,order]
    av=aa@vectors;mv=mm@vectors
    residual=np.linalg.norm(av-mv*values,axis=0)/(np.linalg.norm(av,axis=0)+abs(values)*np.linalg.norm(mv,axis=0))
    np.savez_compressed(folder/'arrays.npz',values=values,vectors=vectors,keep=keep,residual=residual)
    print('poles',side,'calls',calls[0],'residual',max(residual),flush=True)
    print(values,flush=True)
    assert max(residual)<1e-7,residual.tolist()
    return dict(side=side,shift=shift,count=len(values),shift_invert_actions=calls[0],
        max_action_relative_eigen_residual=float(max(residual)),
        eigenvalues=np.c_[values.real,values.imag].tolist(),
        removed_coordinates=np.setdiff1d(np.arange(len(keep)+4),keep).tolist(),dimension=len(keep),
        qualification='Exact cyclic-coordinate rate elimination, one sparse factorization and fixed-start Arnoldi. Selection is by proximity to the stated shift, not by agreement with the reference plot.')


def compare(folder,args):
    import csv
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    a,m,b,c,keep=matrices()
    # NpzFile does not cache arrays. Load each vector matrix once, otherwise
    # retained column views keep a new full decompression alive per mode.
    right=load_modes(args['right'],'right');left=load_modes(args['left'],'left')
    groups=[];values=[];vectors=[];lefts=[];matches=[]
    for i,value in enumerate(right['values']):
        v=right['vectors'][:,i]
        if value.imag < -1e-8*max(1.,abs(value)):
            if np.min(abs(right['values']-value.conjugate()))<1e-7*max(1.,abs(value)):continue
            value=value.conjugate();v=v.conj()
        # Real matrices supply a missing conjugate at an Arnoldi cutoff.
        direct=abs(left['values']-value);conjugate=abs(left['values'].conj()-value)
        flip=np.min(conjugate)<np.min(direct);distances=conjugate if flip else direct
        j=int(np.argmin(distances));mismatch=float(distances[j]/max(1.,abs(value)))
        assert mismatch<1e-7,(value,left['values'][j])
        w=left['vectors'][:,j].conj() if flip else left['vectors'][:,j]
        start=len(values);values.append(value);vectors.append(v);lefts.append(w);matches.append(mismatch)
        if value.imag>1e-8*max(1.,abs(value)):
            values.append(value.conjugate());vectors.append(v.conj());lefts.append(w.conj())
        groups.append(list(range(start,len(values))))
    values=np.array(values);v=np.column_stack(vectors);w=np.column_stack(lefts)
    gram=w.T@(m@v);overlap=np.diag(gram)
    assert min(abs(overlap))>1e-12,min(abs(overlap))
    residues=(c@v)*(w.T@b/overlap)[None,:]
    normalized_gram=gram/overlap[:,None]
    pairing_error=float(np.max(abs(normalized_gram-np.eye(len(values)))))
    assert pairing_error<2e-5,pairing_error
    raw=list(csv.DictReader((SOURCE/'report/comparison.csv').open()))
    freq=np.array(sorted({float(row['frequency_hz']) for row in raw}))
    full=np.empty((len(freq),4),complex);reference=np.empty((len(freq),4))
    for row in raw:
        assert float(row['speed_m_s'])==6.7
        i=int(np.flatnonzero(freq==float(row['frequency_hz']))[0]);j=CHANNELS.index(row['channel'])
        full[i,j]=complex(float(row['real_display']),float(row['imag_display']))
        reference[i,j]=float(row['reference_magnitude'])
    dip=int(np.argmin(abs(freq-1.15737773741517)));assert freq[dip]==1.15737773741517
    s=2j*np.pi*freq
    contributions=residues[None,:,:]/(s[:,None,None]-values[None,None,:])
    sums=[];summaries=[];projection_errors=[];retained=[]
    for requested in sorted(set([4,8,12,16,20,24,28,40,57,len(values)])):
        selected=[]
        for group in groups:
            if len(selected)+len(group)>requested:break
            selected.extend(group)
        if len(selected) in retained:continue
        retained.append(len(selected));response=contributions[:,:,selected].sum(axis=2);sums.append(response)
        # A separate mass-dual projected solve checks the residue sum.
        vv=v[:,selected];ww=w[:,selected];gg=ww.T@(m@vv)
        dual=np.linalg.solve(gg,ww.T);ar=dual@(a@vv);br=dual@b;cr=c@vv
        checks=[]
        for i in (0,dip,len(freq)-1):
            projected=cr@np.linalg.solve(s[i]*np.eye(len(selected))-ar,br)
            checks.append(float(max(abs(projected-response[i]))))
        assert max(checks)<2e-7,checks
        projection_errors.append(max(checks))
        window=(freq>=.7)&(freq<=2.)
        ids=np.flatnonzero(window);minimum=ids[np.argmin(abs(response[window,0]))]
        summaries.append(dict(requested_modes=requested,retained_modes=len(selected),
            dip_magnitude=abs(response[dip]).tolist(),
            dip_yaw_reference_error_percent=float((abs(response[dip,0])/reference[dip,0]-1)*100),
            window_yaw_minimum_frequency_hz=float(freq[minimum]),window_yaw_minimum=float(abs(response[minimum,0])),
            dip_complex_error_relative_to_full=(abs(response[dip]-full[dip])/abs(full[dip])).tolist(),
            mode_order='Ascending pole magnitude, complete conjugate pairs, no output-based selection'))
    # Fresh solves check the cyclic elimination against every retained state,
    # and against the existing complete-system output at three frequencies.
    base=SOURCE/'assembled-6.7';af,mf=(sp.load_npz(base/name).tocsc() for name in ('A.npz','M.npz'))
    maps=np.load(base/'maps.npz');bf=maps['B'][:,0];cf=maps['C'];elimination=[]
    for i in (0,dip,len(freq)-1):
        reduced=splu((s[i]*m-a).tocsc()).solve(b.astype(complex))
        exact=splu((s[i]*mf-af).tocsc()).solve(bf.astype(complex))
        error=float(max(abs(reduced-exact[keep])));output_error=float(max(abs(cf@exact-full[i])))
        assert error<2e-10 and output_error<2e-10,(error,output_error)
        elimination.append(dict(frequency_hz=float(freq[i]),state_absolute_error=error,output_absolute_error=output_error))
    ranked=[]
    for group in groups:
        value=values[group[0]];component=contributions[dip,:,group].sum(axis=0)
        ranked.append(dict(indices=group,eigenvalue=[float(value.real),float(value.imag)],
            damped_frequency_hz=float(value.imag/(2*np.pi)),
            dip_real=component.real.tolist(),dip_imag=component.imag.tolist(),dip_magnitude=abs(component).tolist()))
    ranked.sort(key=lambda entry:entry['dip_magnitude'][0],reverse=True)
    np.savez_compressed(folder/'arrays.npz',frequencies=freq,full=full,reference=reference,
        retained=np.array(retained),reduced=np.array(sums),values=values,residues=residues,vectors=v,lefts=w,
        overlap=overlap,normalized_gram=normalized_gram,dip_contributions=contributions[dip])
    result=dict(channels=CHANNELS,available_modes=len(values),pairing_error=pairing_error,
        max_left_right_pole_mismatch=max(matches),minimum_absolute_mass_overlap=float(min(abs(overlap))),
        max_projected_sum_difference=max(projection_errors),elimination_checks=elimination,
        reference_dip_frequency_hz=float(freq[dip]),full_dip_magnitudes=abs(full[dip]).tolist(),
        reference_dip_magnitudes=reference[dip].tolist(),truncations=summaries,ranked_components=ranked,
        qualification='Current-source modal truncation diagnostic. No mode count or aircraft parameter is fitted. The historical plot does not identify a full or reduced model. These selected modes do not establish completeness of the finite spectrum.')
    print('pairing',pairing_error,'overlap',min(abs(overlap)),flush=True)
    for row in summaries:print(row,flush=True)
    print('leading contributions',ranked[:5],flush=True)
    return result


def refine_left(folder,args):
    import numpy as np
    from scipy.sparse.linalg import splu
    a,m,b,c,keep=matrices()
    # This ARM OpenBLAS build otherwise fails its first complex SuperLU
    # workspace allocation under RLIMIT_AS. Initialize through the real path,
    # as in the successful Arnoldi and first refinement batch, then release it.
    bootstrap=splu((a+.01*m).tocsc());bootstrap.solve(np.ones(len(keep)));del bootstrap
    right=load_modes(args['right'],'right');left=load_modes(args['left'],'left')
    vectors=[];right_vectors=[];values=[];left_values=[];residual=[];right_residual=[];records=[];pending=[]
    for i,value in enumerate(right['values']):
        direct=abs(left['values']-value);conjugate=abs(left['values'].conj()-value)
        flip=np.min(conjugate)<np.min(direct);distances=conjugate if flip else direct
        j=int(np.argmin(distances));w=left['vectors'][:,j].conj() if flip else left['vectors'][:,j].copy()
        mismatch=float(distances[j]/max(1.,abs(value)))
        left_value=left['values'][j].conjugate() if flip else left['values'][j]
        v=right['vectors'][:,i].copy();estimate=(w@(a@v))/(w@(m@v))
        quotient_error=float(abs(estimate-value)/max(1.,abs(value)))
        needed=mismatch>2e-8 or quotient_error>1e-9
        if needed and len(records)>=12:pending.append(i)
        if needed and len(records)<12:
            print('refining',i,value,'match',mismatch,'quotient',quotient_error,flush=True)
            shift=value+1e-4*max(1.,abs(value))
            if value.imag==0:
                assert max(abs(v.imag))<1e-10 and max(abs(w.imag))<1e-10
                shift=float(shift.real);v=v.real.copy();w=w.real.copy()
            print('memory before factor',[line for line in Path('/proc/self/status').read_text().splitlines() if line.startswith(('VmSize:','VmRSS:'))],flush=True)
            lu=splu((a-shift*m).tocsc())
            print('factor nnz',lu.nnz,flush=True)
            for iteration in range(3):
                v=lu.solve(m@v);v/=np.linalg.norm(v)
                w=lu.solve(m.T@w,trans='T');w/=np.linalg.norm(w)
            del lu
            records.append(dict(index=i,eigenvalue=[float(value.real),float(value.imag)],
                original_match_error=mismatch,original_quotient_error=quotient_error,inverse_iterations=3))
            value=(w@(a@v))/(w@(m@v));left_value=value
        # Two-sided Rayleigh quotient and original transpose equation jointly
        # check the refined row; eigenvalue agreement alone would be insufficient.
        aw=a.T@w;mw=m.T@w
        error=float(np.linalg.norm(aw-left_value*mw)/(np.linalg.norm(aw)+abs(left_value)*np.linalg.norm(mw)))
        av=a@v;mv=m@v
        right_error=float(np.linalg.norm(av-value*mv)/(np.linalg.norm(av)+abs(value)*np.linalg.norm(mv)))
        assert error<1e-7,error
        assert right_error<1e-7,right_error
        vectors.append(w);right_vectors.append(v);values.append(value);left_values.append(left_value);residual.append(error);right_residual.append(right_error)
    np.savez_compressed(folder/'arrays.npz',right_values=np.array(values),left_values=np.array(left_values),left_vectors=np.column_stack(vectors),
        right_vectors=np.column_stack(right_vectors),keep=keep,residual=np.array(residual),right_residual=np.array(right_residual))
    print('refined',records,'pending',pending,'max_residual',max(residual),flush=True)
    return dict(refined=records,count=len(values),max_action_relative_eigen_residual=max(residual),
        pending_indices=pending,
        max_right_action_relative_eigen_residual=max(right_residual),
        qualification='Targeted two-sided inverse iteration for inaccurate pole pairing or a discrepant two-sided Rayleigh quotient. Original pencil equations and mass pairing remain required; no physical parameter is altered.')


def main():
    global SOURCE,STUDY
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['poles','compare','refine_left'])
    parser.add_argument('--tag',required=True)
    parser.add_argument('--side',choices=['right','left'],default='right')
    parser.add_argument('--count',type=int,default=28)
    parser.add_argument('--shift',type=float,default=-.01)
    parser.add_argument('--right',default='right-56')
    parser.add_argument('--left',default='left-56')
    parser.add_argument('--source',default=str(SOURCE),help='Pinned saved source-equation study.')
    parser.add_argument('--study',default=str(STUDY),help='Destination for new immutable job tags.')
    args=vars(parser.parse_args())
    SOURCE=Path(args['source']).resolve();STUDY=Path(args['study']).resolve()
    inputs=[SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz','result.json','terminal.json')]
    inputs += [ROOT/'reference/aswing_doc.txt',ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        ROOT/'docs/validation/aswing-authoritative-sources.json',SOURCE/'trim-6.7-1/state.json',SOURCE/'mass-6.7/layout.json']
    if (SOURCE/'certify-6.7/state.json').exists():inputs.append(SOURCE/'certify-6.7/state.json')
    if args['stage'] in ('compare','refine_left'):
        inputs += [STUDY/tag/name for tag in (args['right'],args['left']) for name in ('arrays.npz','result.json','terminal.json')]
        inputs += [SOURCE/'report/comparison.csv']
    run(STUDY,args['tag'],inputs,globals()[args['stage']],args,__file__)


if __name__=='__main__':main()
