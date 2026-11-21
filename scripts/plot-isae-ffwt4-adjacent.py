"""Show all three FFWT-4 grids and successive gust-increment differences."""
import argparse
import json
from pathlib import Path
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assessment',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args();adjacent=read(args.assessment)
    assert adjacent['status']=='ADJACENT_GRIDS_ASSESSED'
    half=read(adjacent['coarser_assessment']['path']);quarter=read(adjacent['finer_assessment']['path'])
    original=read(half['coarse_assessment']['path'])
    rows=[r for r in quarter['checks'] if r['name'].startswith('FFWT_Fixed-1:')]
    native=np.array([r['expected'] for r in rows]);assert len(native)==200
    palette=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',(ROOT/'web/plot-colors.js').read_text(),re.S)
    colors=re.findall(r'#[0-9a-fA-F]{6}',palette[1])
    fig,axes=plt.subplots(3,1,figsize=(9,8),sharex=True)
    axes[0].plot([r['time'] for r in rows],native,color=colors[0],label='Archived ASWING')
    for data,divisor,color,style in [(original,1,colors[1],'--'),(half,2,colors[2],'-.'),(quarter,4,colors[3],':')]:
        states=[data['samples'][str(i)] for i in range(199*divisor+1)]
        t=np.array([s['time'] for s in states]);v=np.array([s['moment'] for s in states])
        axes[0].plot(t,v,color=color,linestyle=style,label=f'OpenSwing · dt={.0149/divisor:g} s')
        axes[1].plot(t[::divisor],100*(v[::divisor]-native)/abs(native),color=color,linestyle=style)
    axes[0].set_ylabel('Root Mc′ (N m)');axes[0].legend(frameon=False,fontsize=8)
    axes[1].set_ylabel('Native error (%)');axes[1].axhline(0,color='#888',lw=.7)
    for low,high,divisor,color,label in [(original,half,1,colors[1],'Original → half step'),
                                      (half,quarter,2,colors[3],'Half → quarter step')]:
        c=np.array([low['samples'][str(i)]['moment'] for i in range(199*divisor+1)])
        f=np.array([high['samples'][str(2*i)]['moment'] for i in range(199*divisor+1)])
        t=[low['samples'][str(i)]['time'] for i in range(199*divisor+1)]
        axes[2].plot(t,100*((c-c[0])-(f-f[0]))/max(abs(f-f[0])),color=color,label=label)
    axes[2].axhspan(-.1,.1,color=colors[3],alpha=.15,label='0.1% increment gate')
    axes[2].set(ylabel='Increment change (%)',xlabel='Time (s)');axes[2].legend(frameon=False,fontsize=8)
    for ax in axes:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('ISAE FFWT-4 · Fixed-1: three time resolutions')
    fig.text(.5,.015,'Exact common ticks, unchanged physical inputs and nominal32 mesh. Spatial accuracy and other histories remain open.',
             ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,.96));args.output_dir.mkdir(parents=True,exist_ok=False)
    for suffix in ('png','svg'):fig.savefig(args.output_dir/('comparison.'+suffix),dpi=150,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':main()
