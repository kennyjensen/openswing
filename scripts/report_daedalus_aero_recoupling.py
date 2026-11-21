"""Report converged fixed-equilibrium aerodynamic recoupling and its limits."""
import argparse
from check_daedalus_aero_recoupling import ROOT,STUDY,PRIOR,SAMPLES,FREQUENCY,accepted,arrays,update_folder
from daedalus_bounded_job import run


def report(folder,args):
    import csv
    import numpy as np
    n=args['iteration']; final=update_folder(n); wide=STUDY/f'update-{n}-wide'
    records=[accepted(update_folder(i)) for i in range(n+1)]
    assert records[-1]['converged'] and accepted(wide)['converged']
    base=arrays(STUDY/'base'); a=arrays(final); w=arrays(wide)
    np.testing.assert_array_equal(a['state'],w['state'])
    load_width_error=float(max(abs(a['load_difference']-w['load_difference'])))
    output_width_error=float(max(abs(a['next_output']-w['next_output'])/abs(a['output'])))
    gamma=arrays(STUDY/f'circulation-{n}-fine')['fine_response']
    gamma_wide=arrays(STUDY/f'circulation-{n}-wide')['fine_response']
    gamma_width_error=float(max(abs(gamma-gamma_wide))/max(abs(gamma)))
    assert load_width_error<2e-10 and output_width_error<1e-7 and gamma_width_error<2e-7
    H0=base['C']@base['state']; H1=base['C']@base['expected_first_state']; H=a['output']
    with np.load(SAMPLES/'fine-samples/arrays.npz') as mesh:
        j=int(np.argmin(abs(mesh['frequencies']-FREQUENCY)))
        assert abs(mesh['frequencies'][j]-FREQUENCY)<1e-14
        full=mesh['outputs'][j]
    rows=[]
    for i,name in enumerate(('yaw_rate','roll_rate','sideslip','bank')):
        rows.append(dict(channel=name,original_amplitude=float(abs(H0[i])),first_order_extrapolated_amplitude=float(abs(H1[i])),
            converged_amplitude=float(abs(H[i])),full_mesh_and_retrim_amplitude=float(abs(full[i])),
            first_variation_percent=float(100*((H1[i]-H0[i])/H0[i]).real),
            first_order_extrapolated_amplitude_change_percent=float(100*(abs(H1[i])/abs(H0[i])-1)),
            converged_amplitude_change_percent=float(100*(abs(H[i])/abs(H0[i])-1)),
            higher_feedback_complex_change_percent_of_original=float(100*abs(H[i]-H1[i])/abs(H0[i])),
            full_mesh_and_retrim_amplitude_change_percent=float(100*(abs(full[i])/abs(H0[i])-1))))
    with (folder/'comparison.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    x=np.arange(4); width=.24
    for j,(key,label,color) in enumerate((
        ('full_mesh_and_retrim_amplitude_change_percent','Full mesh + retrim','#ff4a3d'),
        ('first_order_extrapolated_amplitude_change_percent','Fixed trim: one correction','#ff9f1a'),
        ('converged_amplitude_change_percent','Fixed trim: converged','#ffd166'))):
        axes[0].bar(x+(j-1)*width,[r[key] for r in rows],width,color=color,edgecolor='#555',linewidth=.5,label=label)
    axes[0].set(xticks=x,xticklabels=['Yaw','Roll','Sideslip','Bank'],ylabel='Amplitude change / original amplitude (%)',title='Response at 1.5 Hz')
    axes[0].legend(fontsize=8);axes[0].axhline(0,color='#555',linewidth=.8)
    axes[1].semilogy(range(n+1),[r['modified_full_residual'] for r in records],'o-',color='#ff4a3d',label='Complete modified equations')
    axes[1].axhline(2e-11,color='#2f7bff',linestyle='--',label='Absolute residual gate')
    axes[1].set(xlabel='Corrections already applied',ylabel='Maximum scaled residual',title='Full-equation convergence',xticks=list(range(n+1)))
    axes[1].legend(fontsize=8)
    for ax in axes:ax.grid(axis='y',which='both',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('164 aerodynamic panels; original structure and equilibrium held by a constant residual offset',fontsize=11)
    fig.savefig(folder/'aero-recoupling.png',dpi=150);fig.savefig(folder/'aero-recoupling.svg');plt.close(fig)
    result=dict(frequency_hz=FREQUENCY,accepted_iteration=n,comparisons=rows,iterations=records,
        wide_step_result=accepted(wide),load_width_difference=load_width_error,
        next_output_relative_width_difference=output_width_error,circulation_relative_width_difference=gamma_width_error,
        output_real=H.real.tolist(),output_imag=H.imag.tolist(),
        qualification='All modified harmonic equations converge at the fixed original equilibrium; no structural refinement or physical retrim. A constant residual offset holds the changed mean aerodynamic load. Native ASWING agreement is not established.')
    print(rows,flush=True);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--iteration',type=int,required=True);parser.add_argument('--tag',required=True)
    args=vars(parser.parse_args());n=args['iteration'];assert n>0
    inputs=[ROOT/'scripts/check_daedalus_aero_recoupling.py',ROOT/'docs/validation/ISAE_STATUS.md',
        ROOT/'docs/validation/aswing-authoritative-sources.json',SAMPLES/'fine-samples/arrays.npz']
    folders=[STUDY/'base',*[update_folder(i) for i in range(n+1)],STUDY/f'update-{n}-wide',
        STUDY/f'circulation-{n}-fine',STUDY/f'circulation-{n}-wide']
    inputs += [p/name for p in folders for name in ('arrays.npz','result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
