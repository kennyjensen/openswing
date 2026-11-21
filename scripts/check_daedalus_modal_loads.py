"""Bounded load-law sensitivities of the two current cancelling Daedalus poles.

These are fixed-equilibrium first derivatives, not physical parameter fits or
additive damping fractions. No production matrix or aircraft input is edited.
"""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-modal-loads-20261114'
MODES=ROOT/'artifacts/daedalus-source-modes-20261114'
SHAPES=ROOT/'artifacts/daedalus-mode-shapes-20261114'


def analyze(folder,args):
    import numpy as np
    import scipy.sparse as sp
    from check_daedalus_wing_paper import dynamic
    from check_daedalus_load_sensitivity import groups
    system=dynamic();n=system.network
    assert system.size==2044 and n.nn==108 and n.ne==103 and n.ng==82
    a,m=(sp.load_npz(SOURCE/'assembled-6.7'/name).tocsc() for name in ('A.npz','M.npz'))
    with np.load(MODES/'compare-112-final/arrays.npz') as saved:
        values=saved['values'];lefts=saved['lefts']
    with np.load(MODES/'paired-112-batch3/arrays.npz') as saved:keep=saved['keep']
    removed=np.setdiff1d(np.arange(system.size),keep)
    row=read(SHAPES/'analyze/result.json')['modes'][args['mode']]
    value=complex(*row['eigenvalue']);index=int(np.argmin(abs(values-value)))
    assert abs(values[index]-value)<1e-12
    with np.load(SHAPES/'analyze/arrays.npz') as saved:z=saved[f"mode{args['mode']}_state"]*304.8
    # One-foot display envelope gives well-scaled finite-difference probes;
    # the adjoint quotient is independent of this arbitrary eigenvector scale.
    pencil=value*m-a;w=np.empty(system.size,complex);w[keep]=lefts[:,index]
    w[removed]=np.linalg.solve(pencil[removed,:][:,removed].toarray().T,
        -pencil[keep,:][:,removed].T@w[keep])
    right_error=np.linalg.norm(pencil@z)/(np.linalg.norm(a@z)+abs(value)*np.linalg.norm(m@z))
    left_error=np.linalg.norm(pencil.T@w)/(np.linalg.norm(a.T@w)+abs(value)*np.linalg.norm(m.T@w))
    assert max(right_error,left_error)<1e-7,(right_error,left_error)
    overlap=w@(m@z);assert abs(overlap)>1e-12
    zero=np.zeros(system.size)
    def sample(q,dq):
        state,_,options=system.physical_state(q,dq,None)
        residual,data=n.residual(state.x,detail=True,**options)
        loads,wrenches,diagnostics=groups(system,data)
        return loads,wrenches,data,float(max(abs(residual)))
    baseline=sample(zero,zero);assert baseline[-1]<1e-9
    keys=list(baseline[0]);stencils=[];rate=value*z
    for step in (1e-3,5e-4):
        loads=np.zeros((system.size,len(keys)),complex);wrenches=np.zeros((6,len(keys)),complex)
        for part,component in enumerate((np.real,np.imag)):
            for offset,weight in [(-2,1),(-1,-8),(1,8),(2,-1)]:
                q=step*offset
                observed,moments,_,_=sample(q*component(z),q*component(rate))
                factor=weight/(12*step)*(1 if part==0 else 1j)
                loads+=factor*np.column_stack([observed[k] for k in keys])
                wrenches+=factor*np.column_stack([moments[k] for k in keys])
        stencils.append((loads,wrenches))
    loads,wrenches=stencils[-1]
    step_error=float(np.max(abs(loads-stencils[0][0])));assert step_error<2e-8
    wrench_error=float(max(abs(wrenches.sum(axis=1))));assert wrench_error<2e-6,wrench_error
    # Eq.49 circulation lag, separately by lifting beam, at zero base Gamma-dot.
    # The block-matrix identity also checks the sign and coordinate scaling.
    all_lag=np.zeros(system.size,complex);cursor=n.gamma_start
    for mesh in baseline[2]['meshes']:
        if not mesh.beam.lifting:continue
        strips=baseline[2]['aero']['strips'][n.beam_elements[mesh.beam.index]]
        speed=np.array([s['normal_speed'] for s in strips]);stop=cursor+len(strips)
        action=np.zeros(system.size,complex)
        action[cursor:stop]=-2/np.pi*n.gamma_scale*rate[cursor:stop]/speed/baseline[2]['condition'].speed
        keys.append(f'beam{mesh.beam.index}:circulation_lag')
        loads=np.column_stack([loads,action]);wrenches=np.column_stack([wrenches,np.zeros(6)])
        all_lag+=action;cursor=stop
    assert cursor==n.gamma_start+n.ng
    expected=np.zeros(system.size,complex)
    expected[n.gamma_start:cursor]=-value*(m[n.gamma_start:cursor,:]@z)
    lag_error=float(max(abs(all_lag-expected)));assert lag_error<2e-10,lag_error
    derivatives=w@loads/overlap
    first=w@stencils[0][0]/overlap;second=derivatives[:len(first)]
    derivative_step_ratio=float(max(abs(first-second)/(1+abs(second))))
    assert derivative_step_ratio<2e-6,derivative_step_ratio
    rows=[]
    for key,d in zip(keys,derivatives):
        rows.append(dict(component=key,eigenvalue_derivative=[float(d.real),float(d.imag)],
            decay_rate_change_per_1_percent=float(-.01*d.real),
            frequency_hz_change_per_1_percent=float(.01*d.imag/(2*np.pi))))
    np.savez_compressed(folder/'arrays.npz',state=z,left=w,component_residuals=loads,
        wrenches=wrenches,eigenvalue_derivatives=derivatives,overlap=overlap)
    result=dict(mode=args['mode'],eigenvalue=[value.real,value.imag],frequency_hz=value.imag/(2*np.pi),
        decay_rate=-value.real,damping_ratio=-value.real/abs(value),components=rows,
        right_eigen_residual=float(right_error),left_eigen_residual=float(left_error),
        mass_overlap=[float(overlap.real),float(overlap.imag)],base_residual=baseline[-1],
        load_stencil_difference=step_error,derivative_stencil_relative_difference=derivative_step_ratio,
        net_wrench_error=wrench_error,lag_block_error=lag_error,nonlinear_evaluations=17,
        qualification='Derivative d(lambda)/d(epsilon) = w.T delta_R(v,lambda*v)/(w.T M v), with transpose bilinear left vectors. Each multiplier preserves the loaded equilibrium through an affine offset. These are not damping-energy fractions, retrimmed parameter changes, native ASWING results or a fit.')
    print('checks', {k:v for k,v in result.items() if k not in ('components','qualification')},flush=True)
    print('largest decay sensitivities',sorted(rows,key=lambda r:abs(r['decay_rate_change_per_1_percent']),reverse=True)[:10],flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',type=int,choices=[0,1],required=True)
    parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'scripts/check_daedalus_wing_paper.py',ROOT/'scripts/check_daedalus_source_operator.py',
        ROOT/'examples/dae.asw',ROOT/'examples/dae-cruise-physical-mesh-project.json',SOURCE/'trim-6.7-1/state.json',
        MODES/'compare-112-final/arrays.npz',MODES/'paired-112-batch3/arrays.npz',
        SHAPES/'analyze/result.json',SHAPES/'analyze/arrays.npz',
        ROOT/'docs/validation/aswing-authoritative-sources.json',
        ROOT/'reference/aswing-authoritative-20261108/drela-aswing-unsteady.pdf']
    inputs += [SOURCE/'assembled-6.7'/name for name in ('A.npz','M.npz')]+list((ROOT/'openswing').glob('*.py'))
    run(STUDY,args['tag'],inputs,analyze,args,__file__)


if __name__=='__main__':main()
