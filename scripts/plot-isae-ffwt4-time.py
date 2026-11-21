"""Plot the original Fixed-1 history and verified computed values, retaining gaps."""
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
    args=ap.parse_args();data=json.loads(args.assessment.read_text())
    assert data['status']=='SAVED_HISTORY_ASSESSED' and data['physical_solves']==0
    rows=[c for c in data['checks'] if c['name'].startswith('FFWT_Fixed-1:')]
    assert len(rows)==200 and data['acceptance']['relative_tolerance']==.05
    native_time=np.array([c['time'] for c in rows]);native=np.array([c['expected'] for c in rows])
    computed=[c for c in rows if c['predicted'] is not None]
    time=np.array([data['samples'][str(c['row']-1)]['time'] for c in computed])
    moment=np.array([c['predicted'] for c in computed]);reference=np.array([c['expected'] for c in computed])
    color_block=re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',(ROOT/'web/plot-colors.js').read_text(),re.S)
    colors=re.findall(r'#[0-9a-fA-F]{6}',color_block[1])
    fig,(ax,error)=plt.subplots(2,1,figsize=(9,6),sharex=True,gridspec_kw=dict(height_ratios=[2,1]))
    ax.plot(native_time,native,color=colors[0],label='Archived ASWING',lw=1.6)
    ax.plot(time,moment,color=colors[1],label=f'OpenSwing · nominal{data["nominal"]}',lw=1.4,linestyle='--')
    ax.set_ylabel('Root Mc′ (N m)');ax.legend(frameon=False)
    error.axhspan(-5,5,color=colors[3],alpha=.14,label='5% allowance')
    error.axhline(0,color='#777',lw=.7)
    error.plot(time,100*(moment-reference)/abs(reference),color=colors[1],lw=1.3)
    error.set(ylabel='Error (%)',xlabel='Time (s)');error.legend(loc='upper right',frameon=False)
    relative_error=100*(moment-reference)/abs(reference)
    error.set_ylim(min(-6,float(np.min(relative_error))-.5),
                   max(6,float(np.max(relative_error))+.5))
    for panel in (ax,error):
        panel.grid(alpha=.2);panel.spines[['top','right']].set_visible(False)
        if len(computed)<200:panel.axvspan(time[-1],native_time[-1],color='#aaa',alpha=.12)
    passed=sum(c['passed'] for c in computed)
    fig.suptitle(f'ISAE FFWT-4 · Fixed-1: {passed}/{len(computed)} computed root moments pass')
    fig.text(.5,.015,'Literal model and gust inputs; declared numerical settings. Time/mesh convergence and other histories remain open.',
             ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,.96));args.output_dir.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.output_dir/'comparison.svg',bbox_inches='tight')
    fig.savefig(args.output_dir/'comparison.png',dpi=150,bbox_inches='tight');plt.close(fig)


if __name__=='__main__':main()
