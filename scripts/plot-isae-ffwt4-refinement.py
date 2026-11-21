"""Plot native agreement and separately scaled time-refinement differences."""
import argparse
import json
from pathlib import Path
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assessment',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    args=ap.parse_args();fine=json.loads(args.assessment.read_text())
    assert fine['status']=='REFINED_HISTORY_ASSESSED' and fine['complete']
    coarse=json.loads(Path(fine['coarse_assessment']['path']).read_text())
    time=np.array([coarse['samples'][str(i)]['time'] for i in range(200)])
    c=np.array([coarse['samples'][str(i)]['moment'] for i in range(200)])
    f=np.array([fine['samples'][str(i*fine['divisor'])]['moment'] for i in range(200)])
    rows=[r for r in fine['checks'] if r['name'].startswith('FFWT_Fixed-1:')]
    native=np.array([r['expected'] for r in rows]);assert len(native)==200
    palette=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',(ROOT/'web/plot-colors.js').read_text(),re.S)
    colors=re.findall(r'#[0-9a-fA-F]{6}',palette[1])
    fig,axes=plt.subplots(3,1,figsize=(9,8),sharex=True)
    axes[0].plot([r['time'] for r in rows],native,color=colors[0],label='Archived ASWING')
    axes[0].plot(time,c,color=colors[1],linestyle='--',label='OpenSwing · dt=0.0149 s')
    axes[0].plot(time,f,color=colors[3],linestyle=':',label=f'OpenSwing · dt={fine["dt"]} s')
    axes[0].set_ylabel('Root Mc′ (N m)');axes[0].legend(frameon=False)
    axes[1].plot(time,100*(c-native)/abs(native),color=colors[1],label='Original step')
    axes[1].plot(time,100*(f-native)/abs(native),color=colors[3],label='Half step')
    axes[1].set_ylabel('Native error (%)');axes[1].axhline(0,color='#888',lw=.7)
    axes[2].axhspan(-.1,.1,color=colors[3],alpha=.15,label='0.1% refinement gate')
    axes[2].plot(time,100*(c-f)/max(abs(f)),color=colors[1],label='Total moment scale')
    axes[2].plot(time,100*((c-c[0])-(f-f[0]))/max(abs(f-f[0])),color=colors[3],label='Gust increment scale')
    axes[2].set(ylabel='Refinement change (%)',xlabel='Time (s)');axes[2].legend(frameon=False,fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('ISAE FFWT-4 · Fixed-1: full-history time refinement')
    fig.text(.5,.015,'Unchanged nominal32 mesh, physical inputs and equations. Spatial convergence and other histories remain open.',
             ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,.96));args.output_dir.mkdir(parents=True,exist_ok=False)
    for suffix in ('png','svg'):fig.savefig(args.output_dir/('comparison.'+suffix),dpi=150,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':main()
