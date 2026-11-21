"""Check modal load sensitivities with independently assembled rate blocks.

Small centered perturbations of published circulation lag/rate-lift terms;
never saved as production matrices or selected by Bode agreement.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-modal-loads-20261114'
AERO=ROOT/'artifacts/daedalus-circulation-phase-20261114'


def analyze(folder,args):
    import pickle
    import numpy as np
    import scipy.sparse as sp
    from scipy.sparse.linalg import splu
    from check_daedalus_source_modes import matrices
    with (AERO/'capture-base/base.pkl').open('rb') as stream:packet=pickle.load(stream)
    fixture=packet['fixture'];physical=packet['packet']['inputs'];layout=read(SOURCE/'mass-6.7/layout.json')
    nn=layout['nodes'];ne=layout['elements'];ng=layout['circulation']['width'];gs=layout['circulation']['start']
    fs=layout['internal_loads']['force_scale'];ms=layout['internal_loads']['moment_scale'];op=layout['operating']['start']
    with np.load(AERO/'mass-columns/arrays.npz') as saved:
        rate_force=saved['rate_force'];profile_force=saved['profile_force'];beam=saved['beam'];expected=saved['expected_mass']
    sections=[m for m in physical['meshes'] if m['lifting']]
    fields={key:np.concatenate([m[key] for m in sections]) for key in ('r0','r1','rm','frames')}
    lifting=[b for b in fixture['beams'] if b['lifting']]
    material=lambda key:np.concatenate([b['material_receiver'][key] for b in lifting])
    quarter=((.25-material('Xax'))*material('chord'))[:,None]*fields['frames'][:,:,0]
    midpoint=(fields['r0']+fields['r1'])/2
    ends=np.concatenate([fixture['ends'][b['element_ids']] for b in lifting])
    assert len(ends)==ng
    def transferred(force,couple):
        result=np.zeros((2044,ng));nf=np.zeros((nn,3,ng));nm=np.zeros_like(nf)
        for j,(first,last) in enumerate(ends):
            for node in (first,last):nf[node,:,j]+=force[j]/2;nm[node,:,j]+=couple[j]/2
        result[6*ne:6*ne+3*nn]=-nf.reshape(3*nn,ng)/fs
        result[6*ne+3*nn:6*(ne+nn)]=-nm.reshape(3*nn,ng)/ms
        moment=nm.sum(axis=0)+np.cross((physical['r']-fixture['reference'][1])[None,:,:],nf.transpose(2,0,1)).sum(axis=1).T
        result[op:op+6]=-np.vstack([nf.sum(axis=0)/fs,moment/ms])
        return result
    rate=transferred(rate_force,np.cross(fields['rm']+quarter-midpoint,rate_force))
    profile=transferred(profile_force,np.zeros_like(profile_force))
    lag=np.zeros_like(rate);lag[gs:gs+ng]=expected[gs:gs+ng]
    construction_error=float(np.max(abs(rate+profile+lag-expected)))
    assert construction_error<2e-13,construction_error
    selected=np.flatnonzero(beam==args['beam'])
    block=(rate if args['term']=='rate_lift' else lag)[:,selected]
    coo=sp.coo_matrix(block)
    dm=sp.csc_matrix((coo.data,(coo.row,gs+selected[coo.col])),shape=(2044,2044))
    a,m,_,_,keep=matrices();removed=np.setdiff1d(np.arange(2044),keep)
    assert dm[removed,:].nnz==0 and dm[:,removed].nnz==0
    dr=dm[keep,:][:,keep]
    source=STUDY/args['source'];row=read(source/'result.json');value=complex(*row['eigenvalue'])
    with np.load(source/'arrays.npz') as saved:z=saved['state'];w=saved['left'];overlap=complex(saved['overlap'])
    key=f"beam{args['beam']}:{args['term']}"
    original=complex(*next(r for r in row['components'] if r['component']==key)['eigenvalue_derivative'])
    derivative=-value*(w@(dm@z))/overlap
    slope_agreement=float(abs(derivative-original)/(1+abs(original)))
    assert slope_agreement<2e-7,slope_agreement
    # Initialize the real sparse-solver workspace before complex factors on ARM.
    bootstrap=splu((a+.01*m).tocsc());bootstrap.solve(np.ones(len(keep)));del bootstrap
    results=[];slopes=[]
    for step in (1e-3,5e-4):
        roots=[]
        for epsilon in (-step,step):
            modified=m+epsilon*dr;shift=value+1e-4*max(1.,abs(value))
            lu=splu((a-shift*modified).tocsc());v=z[keep].copy();left=w[keep]
            error=1.
            for iteration in range(8):
                v=lu.solve(modified@v);v/=np.linalg.norm(v)
                av=a@v;mv=modified@v;pole=(left@av)/(left@mv)
                error=float(np.linalg.norm(av-pole*mv)/(np.linalg.norm(av)+abs(pole)*np.linalg.norm(mv)))
                if error<2e-12:break
            assert error<2e-10,(epsilon,error)
            assert abs(pole-value)<.1
            roots.append(pole)
            results.append(dict(epsilon=epsilon,pole=[float(pole.real),float(pole.imag)],iterations=iteration+1,residual=error))
            del lu
        slopes.append((roots[1]-roots[0])/(2*step))
    slope_errors=[float(abs(s-derivative)/(1+abs(derivative))) for s in slopes]
    step_agreement=float(abs(slopes[1]-slopes[0])/(1+abs(slopes[1])))
    assert max(slope_errors)<1e-4 and step_agreement<1e-4,(slope_errors,step_agreement)
    result=dict(source=args['source'],component=key,pole=[value.real,value.imag],
        independent_block_construction_error=construction_error,independent_vs_load_derivative=slope_agreement,
        eigenvalue_derivative=[float(derivative.real),float(derivative.imag)],
        centered_derivatives=[[float(s.real),float(s.imag)] for s in slopes],
        centered_derivative_relative_errors=slope_errors,step_agreement=step_agreement,perturbed_roots=results,
        qualification='Four fresh sparse inverse-iteration eigensolutions at predetermined +/-0.1% and +/-0.05% changes to one published rate term. Exact cyclic-coordinate elimination is retained. These verify first derivatives, not a proposed aircraft setting or native reference agreement.')
    sp.save_npz(folder/'mass_component.npz',dm)
    print(result,flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['wing','boom'],required=True)
    parser.add_argument('--beam',type=int,choices=[1,3],required=True)
    parser.add_argument('--term',choices=['rate_lift','circulation_lag'],required=True)
    parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_source_modes.py',ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf',
        AERO/'capture-base/base.pkl',AERO/'mass-columns/arrays.npz',AERO/'mass-columns/result.json',
        SOURCE/'mass-6.7/layout.json',STUDY/args['source']/'result.json',STUDY/args['source']/'arrays.npz']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz','maps.npz')]
    run(STUDY,args['tag'],inputs,analyze,args,__file__)


if __name__=='__main__':main()
