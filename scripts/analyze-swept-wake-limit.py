"""Audit and plot prescribed swept-wake continuum and attached-leg controls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    data={};pins=None;manifests={};plans={}
    for label,folder in [('cosine','swept-wake-limit-20261108-cosine'),
                         ('uniform','swept-wake-limit-20261108-uniform'),
                         ('attached','swept-attached-wake-20261108')]:
        path=ROOT/'artifacts/isae'/folder
        manifest=json.loads((path/'verification.json').read_text())
        for name,digest in manifest['artifacts'].items(): assert sha(path/name)==digest,name
        manifests[str(path.relative_to(ROOT))]=sha(path/'verification.json')
        plan=json.loads((path/'plan.json').read_text());plans[label]=plan
        if pins is None: pins=plan['unchanged_pins']
        assert pins==plan['unchanged_pins']
        data[label]=json.loads((path/'results.json').read_text())
    for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
    comparisons=[]
    for spacing in ('cosine','uniform'):
        for raw in data[spacing]['records']:
            attached=next(r for r in data['attached']['records'] if r['spacing']==spacing and
                all(r[k]==raw[k] for k in ('panels','sweep_degrees','asymmetry')))
            np.testing.assert_allclose(attached['native_velocity'],raw['wake'][0],atol=0.,rtol=0.)
            assert abs(np.linalg.norm(np.array(attached['attached_velocity'])-attached['continuous_reference'])-attached['continuous_error'])<1e-14
            if raw['sweep_degrees']==30. and raw['asymmetry']==.2:
                comparisons.append(dict(spacing=spacing,panels=raw['panels'],
                    raw_z=raw['wake'][0][2],attached_z=attached['attached_velocity'][2],
                    attached_reference_z=attached['continuous_reference'][2],
                    attached_reference_error=attached['continuous_error'],
                    off_line_errors=raw['off_line_reference_error']))
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'analysis-driver-used.py')
    fig,axes=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
    colors={'cosine':'#0072B2','uniform':'#D55E00'}
    counts=plans['cosine']['panels']
    for spacing,color in colors.items():
        rows=[r for r in comparisons if r['spacing']==spacing]
        axes[0,0].plot(counts,[r['raw_z'] for r in rows],'o-',color=color,label=f'Direct wake, {spacing}')
        axes[0,0].plot(counts,[r['attached_z'] for r in rows],'s--',color=color,label=f'Attached legs, {spacing}')
        steps=[r for r in data[spacing]['log_increments'] if r['sweep_degrees']==30.]
        axes[0,1].plot([r['second'] for r in steps],
            [r['observed']/np.log(r['second']/r['first']) for r in steps],'o-',color=color,label=spacing)
        axes[1,1].loglog(counts,[r['attached_reference_error'] for r in rows],'o-',color=color,label=spacing)
    axes[0,0].axhline(comparisons[0]['attached_reference_z'],color='#333333',linestyle=':',label='Attached continuous reference')
    coefficient=-.2*np.tan(np.pi/6)/(2*np.pi)
    axes[0,1].axhline(coefficient,color='#333333',linestyle=':',label='Analytic coefficient; no fit')
    rows=[r for r in comparisons if r['spacing']=='cosine']
    for index,height,color in [(0,.1,'#009E73'),(1,.01,'#CC79A7'),(2,.001,'#E69F00')]:
        axes[1,0].loglog(counts,[r['off_line_errors'][index] for r in rows],'o-',color=color,label=f'Distance {height:g} m')
    titles=['Fixed point on the straight bound line','Logarithmic growth of the asymmetric contribution',
            'Direct wake: error against off-line continuous integral','Attached legs: error against finite continuous reference']
    ylabels=['Wake z velocity (m/s)','Delta velocity / log(N2/N1) (m/s)',
             'Velocity error norm (m/s)','Velocity error norm (m/s)']
    for ax,title,ylabel in zip(axes.flat,titles,ylabels):
        ax.set_xscale('log',base=2);ax.set_title(title,fontsize=10)
        ticks=counts[1:] if ax is axes[0,1] else counts
        ax.set_xticks(ticks);ax.set_xticklabels([str(n) for n in ticks]);ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel('Bound intervals');ax.set_ylabel(ylabel);ax.grid(True,which='both',alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('30° sweep; prescribed smooth Gamma; fixed receivers; zero core; no circulation solve',fontsize=12)
    fig.savefig(args.output/'swept-wake-limit.png',dpi=160)
    fig.savefig(args.output/'swept-wake-limit.svg');plt.close(fig)
    final_steps=[dict(spacing=spacing,**r) for spacing in ('cosine','uniform')
                 for r in data[spacing]['log_increments'] if r['second']==511]
    summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),unchanged_pins=pins,source_manifests=manifests,
        primary_comparisons=comparisons,final_log_increments=final_steps,
        maximum_discrete_scalar_error=max(data[s]['maximum_scalar_check_error'] for s in ('cosine','uniform')),
        maximum_analytic_exclusion_error=max(data[s]['maximum_cutoff_identity_error'] for s in ('cosine','uniform')),
        maximum_final_attached_reference_error=max(r['continuous_error'] for r in data['attached']['records'] if r['panels']==511),
        recorded_seconds=sum(d['total_seconds'] for d in data.values()),direct_fields=72,attached_fields=72,
        new_circulation_solves=0,production_and_primary_counts_unchanged=True,
        artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
    (args.output/'analysis.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('unchanged_pins','source_manifests','artifacts','primary_comparisons')},indent=2))
    print(json.dumps(comparisons,indent=2))


if __name__=='__main__': main()
