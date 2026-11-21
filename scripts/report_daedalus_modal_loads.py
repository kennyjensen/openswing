"""Present verified, fixed-equilibrium modal load sensitivities."""
import argparse
from check_daedalus_load_sensitivity import ROOT,read
from daedalus_bounded_job import run

STUDY=ROOT/'artifacts/daedalus-modal-loads-20261114'
TAGS=['wing','boom','wing-lag-check','wing-rate-check','boom-lag-check','boom-rate-check']


def report(folder,args):
    import csv,re
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
    rows=[read(STUDY/tag/'result.json') for tag in TAGS[:2]]
    checks=[read(STUDY/tag/'result.json') for tag in TAGS[2:]]
    palette=re.findall(r"'([^']+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    terms=['lift','rate_lift','circulation_lag','apparent']
    labels=['Ordinary lift','Circulation-rate lift','Shed-wake lag','Apparent inertia']
    for i,(row,beam,name) in enumerate(zip(rows,[1,3],['Wing-dominated mode','Tailboom-dominated mode'])):
        data={r['component']:r for r in row['components']}
        for j,(field,xlabel) in enumerate([
            ('decay_rate_change_per_1_percent','Decay-rate change [1/s] for +1% term multiplier'),
            ('frequency_hz_change_per_1_percent','Frequency change [Hz] for +1% term multiplier')]):
            ax=axes[i,j];values=[data[f'beam{beam}:{term}'][field] for term in terms]
            ax.barh(np.arange(len(terms)),values,color=palette[i]);ax.set_yticks(np.arange(len(terms)),labels)
            ax.invert_yaxis();ax.axvline(0,color='#374151',lw=.8);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
            ax.set_xlabel(xlabel,fontsize=9)
            ax.set_title(f"{name}: {row['frequency_hz']:.4f} Hz\nDamping ratio {row['damping_ratio']:.3f}",fontsize=11)
    fig.suptitle('Daedalus: opposing effects of the two published unsteady terms\nPositive decay-rate change means faster decay; multipliers are diagnostics, not proposed parameters',fontsize=12)
    fig.savefig(folder/'modal-load-sensitivity.png',dpi=160);fig.savefig(folder/'modal-load-sensitivity.svg');plt.close(fig)
    with (folder/'modal-load-sensitivity.csv').open('x',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['mode','frequency_hz','component','d_lambda_real','d_lambda_imag','decay_change_per_1_percent','frequency_change_per_1_percent'])
        for row in rows:
            for term in row['components']:writer.writerow([row['mode'],row['frequency_hz'],term['component'],*term['eigenvalue_derivative'],term['decay_rate_change_per_1_percent'],term['frequency_hz_change_per_1_percent']])
    result=dict(modes=rows,independent_rate_checks=checks,
        maximum_centered_derivative_relative_error=max(max(c['centered_derivative_relative_errors']) for c in checks),
        maximum_fine_centered_derivative_relative_error=max(c['centered_derivative_relative_errors'][-1] for c in checks),
        maximum_perturbed_eigen_residual=max(p['residual'] for c in checks for p in c['perturbed_roots']),
        perturbed_eigensolutions=sum(len(c['perturbed_roots']) for c in checks),
        qualification='Source-model sensitivities with unchanged physical inputs and full-system baseline. No damping coefficient, mode count, aircraft property, native reference pass or ISAE scope is fitted or changed.')
    print({k:v for k,v in result.items() if k not in ('modes','independent_rate_checks')},flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tag',required=True);args=vars(parser.parse_args())
    inputs=[ROOT/'web/plot-colors.js',ROOT/'scripts/check_daedalus_modal_loads.py',ROOT/'scripts/check_daedalus_modal_rate_perturbation.py']
    inputs += [STUDY/tag/name for tag in TAGS for name in ('result.json','terminal.json')]
    run(STUDY,args['tag'],inputs,report,args,__file__)


if __name__=='__main__':main()
