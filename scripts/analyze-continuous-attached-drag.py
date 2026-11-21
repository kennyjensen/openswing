"""Independent energy-integral audit and plot of continuous attached-force tests."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def primitive0(x):
    out=np.zeros_like(x);keep=x>0
    out[keep]=x[keep]*(np.log(x[keep])-1)
    return out


def primitive1(x):
    out=np.zeros_like(x);keep=x>0
    out[keep]=x[keep]**2*(np.log(x[keep])/2-.25)
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    data={};pins=None;manifests={}
    for name,folder in [('polynomial','continuous-attached-drag-20261108'),
                        ('reconstruction','attached-drag-reconstruction-20261108')]:
        p=ROOT/'artifacts/isae'/folder
        manifest=json.loads((p/'verification.json').read_text())
        for file,digest in manifest['artifacts'].items():assert sha(p/file)==digest
        plan=json.loads((p/'plan.json').read_text())
        if pins is None:pins=plan['unchanged_pins']
        assert pins==plan['unchanged_pins']
        manifests[str(p.relative_to(ROOT))]=sha(p/'verification.json')
        data[name]=json.loads((p/'results.json').read_text())
    for name,digest in pins.items():assert sha(ROOT/name)==digest
    energy_errors=[];comparisons=[]
    for row in data['polynomial']['records']:
        # D=-1/(2*pi)*integral R(delta)*log(delta) ddelta. Independent
        # closed polynomial log moments instead of the driver's Q/delta.
        r=np.asarray(row['gradient_correlation_coefficients'],dtype=np.longdouble)
        k=np.arange(1,len(r)+1,dtype=np.longdouble);end=np.longdouble(10)
        energy=-np.sum(r*end**k*(np.log(end)/k-1/k**2))/(2*np.pi)
        energy_errors.append(float(abs(energy-row['trefftz_drag'])))
        assert energy_errors[-1]<2e-12
    for row in data['reconstruction']['records']:
        alpha=row['original_incidence_degrees'];n=row['original_panels']
        p=ROOT/'artifacts/isae/attached-drag-reconstruction-20261108'/f'alpha{alpha:g}-n{n}.npz'
        with np.load(p) as d:
            x=d['correlation_knots'];R=d['R'];slope=d['dR'];gamma=d['gamma']
            a=R[:-1]-slope[:-1]*x[:-1]
            energy=-np.sum(a*np.diff(primitive0(x))+slope[:-1]*np.diff(primitive1(x)))/(2*np.pi)
        source=ROOT/row['source']
        with np.load(source/'sweep-+30.npz') as original:
            np.testing.assert_array_equal(gamma[1:-1],original['gamma'])
            assert gamma[0]==gamma[-1]==0
        saved=next(r for r in json.loads((source/'results.json').read_text())['records'] if r['sweep_degrees']==30)
        final=row['results'][-1]
        error=float(abs(energy-final['trefftz_drag']));energy_errors.append(error)
        assert error<2e-12
        comparisons.append(dict(panels=n,original_incidence=alpha,
            original_discrete_trefftz_drag=saved['trefftz_drag'],
            reconstructed_continuous_trefftz_drag=final['trefftz_drag'],
            trefftz_change_percent=100*(final['trefftz_drag']/saved['trefftz_drag']-1),
            original_sampled_total_difference_percent=saved['full_drag_difference_percent'],
            reconstructed_sampled_total_difference_percent=final['sampled_total_difference_percent'],
            reconstructed_integrated_total_difference_percent=final['integrated_total_difference_percent'],
            independent_energy_error=error))
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'analysis-driver-used.py')
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),constrained_layout=True)
    labels=['Polynomial\na=0','Polynomial\na=0.2','Saved N64\n5° Gamma','Saved N128\n5° Gamma','Saved N128\n1° Gamma']
    values=[r['sampled_total_difference_percent'] for r in data['polynomial']['records'] if r['sweep_degrees']==30]
    values += [r['reconstructed_sampled_total_difference_percent'] for r in comparisons]
    axes[0].bar(np.arange(5),values,color=['#009E73','#009E73','#0072B2','#0072B2','#0072B2'])
    axes[0].axhline(0,color='black',linewidth=.8)
    axes[0].set_xticks(np.arange(5),labels,fontsize=8)
    axes[0].set_ylabel('Difference from continuous Trefftz drag (%)')
    axes[0].set_title('Single-point attached-force sampling')
    orders=[4,8,16]
    for row,label in zip(data['reconstruction']['records'],labels[2:]):
        axes[1].semilogy(orders,[r['integrated_closure_error'] for r in row['results']],'o-',label=label.replace('\n',' '))
    axes[1].set_xticks(orders);axes[1].set_xlabel('Gauss order per correlation interval')
    axes[1].set_ylabel('Global drag-balance residual (N)')
    axes[1].set_title('Chord-integrated force: algebraic verification')
    axes[1].legend(fontsize=8)
    for ax in axes:ax.grid(axis='y',alpha=.25)
    fig.suptitle('Continuous planar controls, 30° sweep; no circulation solves or ASWING validation')
    fig.savefig(args.output/'continuous-attached-drag.png',dpi=150)
    fig.savefig(args.output/'continuous-attached-drag.svg');plt.close(fig)
    summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),unchanged_pins=pins,
        source_manifests=manifests,polynomial_cases=6,reconstructed_cases=3,new_circulation_solves=0,
        maximum_independent_energy_error=max(energy_errors),saved_gamma_samples_preserved_exactly=True,
        comparisons=comparisons,
        recorded_seconds=sum(r['seconds'] for r in data['polynomial']['records'])+data['reconstruction']['seconds'],
        production_and_primary_counts_unchanged=True,
        artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    (args.output/'analysis.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('unchanged_pins','source_manifests','artifacts')},indent=2))


if __name__=='__main__':main()
