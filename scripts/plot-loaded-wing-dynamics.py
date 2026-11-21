"""Plot retained independent loaded-wing dynamics checks."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('study',type=Path)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
rows=[json.loads((args.study/'run-02'/f'case-{i:02d}.json').read_text()) for i in range(6)]
root=json.loads((args.study/'root-refinement.json').read_text())['cases']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,3,figsize=(14,4.8))
for wing,color,marker,shift in [('25','#10837e','o',-.17),('75','#c5603e','s',.17)]:
    group=[r for r in rows if r['wing']==wing]
    axes[0].loglog([r['panels'] for r in group],[100*max(x['relative'] for x in r['responses']) for r in group],
                   color=color,marker=marker,label=f'{wing}% spar')
    refinements=[r for r in root if r['wing']==wing]
    axes[1].loglog([r['divisions'] for r in refinements],[100*r['relative'] for r in refinements],color=color,marker=marker)
    axes[2].bar(np.arange(1,5)+shift,[100*m['frequency_relative'] for m in group[-1]['modes']],width=.32,color=color)
axes[0].set(title='Complete nodal mobility\nLargest error over five spectral points',xlabel='Requested intervals',ylabel='Relative Frobenius difference (%)',xticks=[8,16,32],xticklabels=['8','16','32'])
axes[0].legend(frameon=False)
axes[1].set(title='Weak near-root axial response\nOnly the first 12 mm interval is refined',xlabel='Subdivisions of first interval',ylabel='Response difference (%)',xticks=[1,2,4,8],xticklabels=['1','2','4','8'])
axes[2].set(title='Four matched structural modes\n32 requested intervals',xlabel='Mode in increasing frequency',ylabel='Frequency difference (%)',xticks=[1,2,3,4])
for axis in axes:
    axis.grid(alpha=.22);axis.set_axisbelow(True)
    axis.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
fig.suptitle('Loaded-wing dynamics under frozen nodal loads',fontsize=17,y=.98)
fig.text(.5,.02,'Distributed real inertia included. Aerodynamic feedback and apparent mass excluded; matrix-norm errors do not bound every weak point-load response.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.07,1,.93])
for extension in ['svg','png','pdf']:
    fig.savefig(args.output.with_suffix('.'+extension),dpi=180)
