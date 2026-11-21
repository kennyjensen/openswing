"""Compare saved current-source component grids with independent continuum."""
import argparse
from check_daedalus_load_sensitivity import ROOT,SOURCE,read
from daedalus_bounded_job import run
STUDY=ROOT/'artifacts/daedalus-wing-root-20261114'
GRIDS=['compact-14-v3','n28-v2','n56']
CASES=['slow','dip']
INPUTS=['Root x','Root y','Root z','Root rotation x','Root rotation y','Root rotation z']


def work(folder,args):
    import csv
    import re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import NullFormatter
    plan=read(ROOT/'docs/validation/daedalus-wing-root-20261114-plan.json')
    limit=plan['agreement_target'];tightening_limit=plan['integration_tightening_gate']
    weights=np.array([1/56]*3+[1.]*3)[None,:,None];wrench_weights=np.array([1.]*3+[1/56]*3)[:,None]
    def relative(a,b,axes):
        denominator=np.max(abs(b),axis=axes);assert np.all(denominator>0)
        return np.max(abs(a-b),axis=axes)/denominator
    results=[];errors=np.empty((3,2,2,6));derived=[];tightening=[];geometries=[]
    scalar=read(SOURCE/'mass-6.7/layout.json')['node_coordinates']['translation_scale']
    cut=int(np.load(STUDY/'prepare/layout.npz')['cut'])
    for k,case in enumerate(CASES):
        low=np.load(STUDY/f'samples-loose-{case}/arrays.npz');ref=np.load(STUDY/f'samples-tight-{case}/arrays.npz')
        metadata=read(STUDY/f'samples-tight-{case}/result.json');frequency=metadata['frequency_hz']
        em=relative(low['motion']*weights,ref['motion']*weights,(0,1))
        er=relative(low['reaction']*wrench_weights,ref['reaction']*wrench_weights,0)
        assert max(max(em),max(er))<tightening_limit,(em,er)
        tightening.append(dict(frequency_hz=frequency,motion=em.tolist(),reaction=er.tolist()))
        tag='slow-animation' if case=='slow' else 'reference-dip'
        z=np.load(ROOT/'artifacts/daedalus-load-sensitivity-20261113'/tag/'arrays.npz')['state']
        root=z[6*cut:6*cut+6]*np.array([scalar]*3+[1.]*3)
        reference_reaction=ref['reaction']@root
        for g,grid in enumerate(GRIDS):
            native=np.load(STUDY/grid/'arrays.npz');idx=np.searchsorted(ref['stations'],native['stations'])
            np.testing.assert_array_equal(ref['stations'][idx],native['stations'])
            expected=ref['motion'][idx];actual=native[f'motion_{k}'];reaction=native[f'reaction_{k}']
            em=relative(actual*weights,expected*weights,(0,1));er=relative(reaction*wrench_weights,ref['reaction']*wrench_weights,0)
            errors[g,k,0]=em;errors[g,k,1]=er
            result=dict(grid=grid,elements=len(native['stations'])-1,frequency_hz=frequency,
                motion_relative_errors=em.tolist(),reaction_relative_errors=er.tolist(),
                passed=[bool(m<limit and r<limit) for m,r in zip(em,er)])
            results.append(result)
            observed=reaction@root;projection=actual@root;expected_projection=expected@root
            scaled=np.array([1/56]*3+[1.]*3)[None,:]
            derived.append(dict(grid=grid,frequency_hz=frequency,
                motion_relative_error=float(np.max(abs((projection-expected_projection)*scaled))/np.max(abs(expected_projection*scaled))),
                yaw_moment_native=dict(real=float(observed[5].real),imag=float(observed[5].imag)),
                yaw_moment_reference=dict(real=float(reference_reaction[5].real),imag=float(reference_reaction[5].imag)),
                yaw_moment_complex_relative_error=float(abs(observed[5]-reference_reaction[5])/abs(reference_reaction[5])),
                yaw_moment_phase_difference_deg=float(np.angle(observed[5]/reference_reaction[5],deg=True))))
            if k==0:
                displacement=np.max(abs(native['positions']-ref['base_state'][idx,:3]))
                geometries.append(dict(grid=grid,position_absolute_error_ft=float(displacement)))
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    plt.rcParams.update({'figure.facecolor':'#111827','axes.facecolor':'#111827','text.color':'white',
        'axes.labelcolor':'white','xtick.color':'white','ytick.color':'white','axes.edgecolor':'#9ca3af','font.size':9})
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    for k,case in enumerate(CASES):
        for measure in range(2):
            ax=axes[k,measure]
            for j,name in enumerate(INPUTS):ax.loglog([14,28,56],100*errors[:,k,measure,j],'-o',color=palette[j],label=name,ms=4)
            ax.axhline(100*limit,color='white',ls='--',lw=.8,label='1% target')
            ax.set_xticks([14,28,56],['14','28','56']);ax.xaxis.set_minor_formatter(NullFormatter())
            ax.set_xlabel('Half-wing intervals')
            ax.set_ylabel('Reference-relative error [%]');ax.grid(which='both',alpha=.15)
            ax.set_title(f"{plan['frequencies_hz'][k]:.6g} Hz — "+('complete nodal motion' if measure==0 else 'root reaction'))
    handles,labels=axes[0,0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncols=4,facecolor='#111827',labelcolor='white')
    fig.suptitle('Current Daedalus wing/brace mechanics versus independent continuum\nPrescribed root motion; real mass and live brace; aerodynamic/gravity loads held fixed')
    fig.savefig(folder/'wing-root.png',dpi=150);fig.savefig(folder/'wing-root.svg');plt.close(fig)
    with (folder/'comparisons.csv').open('x') as stream:
        writer=csv.writer(stream);writer.writerow(['elements','frequency_hz','input','motion_error_percent','reaction_error_percent','passed_1_percent'])
        for row in results:
            for name,m,r,passed in zip(INPUTS,row['motion_relative_errors'],row['reaction_relative_errors'],row['passed']):
                writer.writerow([row['elements'],row['frequency_hz'],name,100*m,100*r,passed])
    np.savez_compressed(folder/'arrays.npz',errors=errors)
    output=dict(inputs=INPUTS,results=results,derived_complex_root_motion=derived,base_geometry=geometries,
        integration_tightening=tightening,finest_passes=sum(sum(row['passed']) for row in results if row['elements']==56),
        primary_cases=12,agreement_target=limit,
        qualification='Component mechanics with live brace and real inertia, fixed body-axis nodal dead loads and prescribed root motion. Independent continuum base and dynamic ODEs; no current production physics change or full-aircraft/native-ASWING Bode validation.')
    print(output,flush=True);return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);args=vars(p.parse_args())
    inputs=[ROOT/'docs/validation/daedalus-wing-root-20261114-plan.json',ROOT/'web/plot-colors.js',ROOT/'docs/validation/ISAE_STATUS.md',
        SOURCE/'mass-6.7/layout.json',STUDY/'prepare/layout.npz']
    tags=GRIDS+[f'samples-{tol}-{case}' for tol in ('loose','tight') for case in CASES]
    inputs += [STUDY/tag/name for tag in tags for name in ('arrays.npz','result.json','terminal.json')]
    inputs += [ROOT/'artifacts/daedalus-load-sensitivity-20261113'/tag/'arrays.npz' for tag in ('slow-animation','reference-dip')]
    run(STUDY,args['tag'],inputs,work,args,__file__)


if __name__=='__main__':main()
