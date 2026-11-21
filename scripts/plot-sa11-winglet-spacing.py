"""Plot retained SA-11 spacing results; performs no aerodynamic solve."""
import hashlib
import json
from pathlib import Path
import re
import resource
import signal

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
resource.setrlimit(resource.RLIMIT_CPU,(15,15))
signal.alarm(25)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, LogLocator, NullFormatter

root=Path(__file__).resolve().parents[1]
folder=root/'artifacts/isae/sa11-winglet-spacing-20261108'
source=folder/'analysis.json'
data=json.loads(source.read_text())['cases']
palette=(root/'web/plot-colors.js').read_text()
plot_palette=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette,re.S)
assert plot_palette is not None
colors=re.findall(r'#[0-9a-fA-F]{6}',plot_palette[1])[:3]
assert len(colors)==3
fig,axes=plt.subplots(1,2,figsize=(10,4.4),layout='constrained')
for rule,label,color in zip(['cosine','uniform','tip_clustered'],
                           ['Cosine at both ends','Uniform','Clustered toward tip'],colors):
    rows=[r for r in data if r['case']['rule']==rule]
    n=[r['case']['winglet_intervals'] for r in rows]
    for ax,values in zip(axes,[[r['maximum_normal_mach'] for r in rows],
                             [r['reference_error_percent']['CD'] for r in rows]]):
        ax.plot(n,values,color=color,label=label,linewidth=1.8)
        for count,value,row in zip(n,values,rows):
            ax.plot(count,value,'o',color=color,markerfacecolor=color if row['rejected_sections']==0 else 'white',markersize=6)
for ax in axes:
    ax.set_xscale('log',base=2);ax.set_xticks([16,32,64,128])
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.set_xlabel('Intervals per winglet (main wing fixed at 32)')
    ax.grid(True,which='major',alpha=.3)
axes[0].set_yscale('log');axes[0].set_ylim(.5,110)
axes[0].set_yticks([1,10,100]);axes[0].yaxis.set_major_formatter(ScalarFormatter())
axes[0].yaxis.set_minor_locator(LogLocator(base=10,subs=range(2,10)))
axes[0].yaxis.set_minor_formatter(NullFormatter());axes[0].grid(True,which='minor',axis='y',alpha=.12)
axes[0].axhline(1,color='#555555',linestyle='--',linewidth=1)
axes[0].set_ylabel('Maximum section-normal Mach')
axes[0].set_title('Uniform 16 / 32: valid section moments')
axes[0].legend(fontsize=8,loc='upper left')
axes[1].axhspan(-5,5,color='#00804a',alpha=.08)
axes[1].axhline(0,color='#555555',linewidth=.7)
axes[1].set_ylabel('Surface CD error against archive (%)')
axes[1].set_title('Open markers: rejected-state force sums')
fig.suptitle('SA-11 at 1°: geometry, zero core and equations unchanged',fontsize=12)
for suffix in ('svg','png'):
    path=folder/f'winglet-spacing.{suffix}'
    assert not path.exists(),path
    fig.savefig(path,dpi=160)
plt.close(fig)
(folder/'plot-provenance.json').write_text(json.dumps(dict(
    analysis_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    palette_sha256=hashlib.sha256((root/'web/plot-colors.js').read_bytes()).hexdigest()),indent=2)+'\n')
signal.alarm(0)
print('Saved winglet-spacing.svg and winglet-spacing.png')
