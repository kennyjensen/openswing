"""Report verified full-descriptor zeros and their conditional sensitivities."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from check_daedalus_transmission_zeros import STUDY
from daedalus_bounded_job import run

CHECKS=['yaw-forward-check','roll-forward-check','yaw-aft-check','roll-aft-check']


def report(folder,args):
    import csv,re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    zeros=[read(STUDY/tag/'result.json') for tag in ('yaw-verify','roll-verify')]
    stiffness=read(STUDY/'stiffness-split/result.json')
    perturbations=[read(STUDY/tag/'result.json') for tag in CHECKS]
    modes=read(ROOT/'artifacts/daedalus-mode-shapes-20261114/analyze/result.json')['modes']
    literal=read(STUDY/'literal-mount/result.json')
    lookup={(r['channel'],r['component']):r for r in stiffness['components']}
    ratios={channel:abs(lookup[channel,'mount_span-EInn']['zero_derivative'][0]/lookup[channel,'aft_boom-EInn']['zero_derivative'][0]) for channel in ('yaw','roll')}
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    fig,axes=plt.subplots(1,3,figsize=(14.6,5),layout='constrained')
    for i,(entry,name) in enumerate(zip(zeros,('Yaw zero','Roll zero'))):
        real,imag=entry['zero'];axes[0].scatter(real,imag/(2*np.pi),marker='o',facecolors='none',edgecolors=palette[i],s=90,linewidths=2,label=name)
    for i,entry in enumerate(modes):
        real,imag=entry['eigenvalue'];axes[0].scatter(real,imag/(2*np.pi),marker='x',color=palette[4+i],s=65,label=('Wing pole','Boom pole')[i])
    axes[0].axvline(0,color='#6b7280',lw=.8,ls=':')
    axes[0].set(xlabel='Real part [1/s]',ylabel='Imaginary part / 2π [Hz]',
        title='Current cancellation zeros and nearby poles',xlim=(-8,2),ylim=(1.1,1.52))
    axes[0].legend(fontsize=8)
    selected=['mount_span-EInn','wing-GJ','wing-EIcc','wing-EInn','aft_boom-EInn']
    labels=['Wing–fairing span\nYaw bending','Wing torsion','Wing EIcc','Wing EInn','Aft boom\nYaw bending']
    y=np.arange(len(selected))
    for i,channel in enumerate(('yaw','roll')):
        axes[1].barh(y+(i-.5)*.3,[lookup[channel,key]['real_part_change_per_1_percent'] for key in selected],height=.28,color=palette[i],label=channel.capitalize()+' zero')
    axes[1].set(yticks=y,yticklabels=labels,xlabel='Real-part change per +1% stiffness [1/s]',title='Fixed-equilibrium stiffness sensitivity')
    axes[1].invert_yaxis();axes[1].axvline(0,color='#6b7280',lw=.8);axes[1].legend(fontsize=8)
    groups=['wing','stabilizer','fin','forward_boom','aft_boom','fairing'];left=np.zeros(2)
    for i,group in enumerate(groups):
        values=100*np.array([stiffness['material_strain_fractions'][tag][group] for tag in ('yaw-verify','roll-verify')])
        axes[2].barh([0,1],values,left=left,color=palette[i],label=group.replace('_',' ').capitalize());left+=values
    axes[2].set(yticks=[0,1],yticklabels=['Yaw zero','Roll zero'],xlabel='Share of material-strain quadratic [%]',xlim=(0,100),
        title='Forced zero-state deformation\nExcludes brace, fluid and kinetic terms',ylim=(-.6,2.5))
    axes[2].legend(fontsize=8,ncol=2,loc='upper center')
    for ax in axes:ax.grid(alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('Daedalus: verified cancellations and the wing–fairing mounting path\nNo aircraft property fitted; these sensitivities do not identify the historical ASWING setup',fontsize=12)
    fig.savefig(folder/'transmission-zeros.png',dpi=160);fig.savefig(folder/'transmission-zeros.svg');plt.close(fig)
    with (folder/'stiffness.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['channel','component','d_real_per_1_percent','d_frequency_hz_per_1_percent'])
        for r in stiffness['components']:writer.writerow([r['channel'],r['component'],r['real_part_change_per_1_percent'],r['frequency_hz_change_per_1_percent']])
    with (folder/'load-sensitivities.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['channel','component','d_real_per_1_percent','d_frequency_hz_per_1_percent'])
        for zero in zeros:
            for r in zero['components']:writer.writerow([zero['channel'],r['component'],r['real_part_change_per_1_percent'],r['frequency_hz_change_per_1_percent']])
    summary=dict(zeros=zeros,stiffness=stiffness,literal_mount=literal,
        mount_to_aft_real_part_sensitivity_ratio=ratios,
        perturbed_zero_count=sum(len(r['perturbed_zeros']) for r in perturbations),
        perturbed_newton_steps=sum(len(root['history']) for r in perturbations for root in r['perturbed_zeros']),
        maximum_normalized_centered_derivative_errors=[max(r['normalized_centered_derivative_errors'][i] for r in perturbations) for i in (0,1)],
        maximum_perturbed_scaled_residual=max(h['scaled_residual'] for r in perturbations for root in r['perturbed_zeros'] for h in root['history']),
        minimum_perturbed_reciprocal_condition=min(h['reciprocal_condition'] for r in perturbations for root in r['perturbed_zeros'] for h in root['history']),
        qualification='Selected verified zeros of the current source model, not poles or native ASWING reference values. No full-spectrum completeness claim. Fixed-equilibrium coefficient/constitutive sensitivities include coupled response and do not authorize tuning. Material measures describe the supplied forced exponential states, not total modal energy.')
    print({k:v for k,v in summary.items() if k not in ('zeros','stiffness','literal_mount','qualification')},flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',required=True);args=vars(p.parse_args())
    tags=['yaw-verify','roll-verify','stiffness-split','literal-mount',*CHECKS]
    inputs=[STUDY/tag/name for tag in tags for name in ('result.json','terminal.json')]
    inputs += [ROOT/'artifacts/daedalus-mode-shapes-20261114/analyze/result.json',ROOT/'web/plot-colors.js',
        ROOT/'scripts/check_daedalus_transmission_zeros.py',ROOT/'scripts/check_daedalus_zero_stiffness.py']
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
