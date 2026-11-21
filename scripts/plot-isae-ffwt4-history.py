"""Plot the computed history while displaying the uncomputed interval explicitly."""
import argparse
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from isae_ffwt4_evidence import pin, read, require, write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    data = read(args.assessment)
    require(data['status'] == 'HISTORY_ASSESSED' and data['physical_solves'] == 0, 'Audited history required')
    require(pin(data['terminal_journal']['path']) == data['terminal_journal'], 'Changed terminal evidence')
    rows = [r for r in data['checks'] if r['name'].startswith('FFWT_Fixed-1:')]
    require(len(rows) == 200 and data['acceptance']['relative_tolerance'] == .05, 'Native scope changed')
    computed = [r for r in rows if r['predicted'] is not None]
    states = [data['samples'][str(i)] for i in range(data['accepted_steps']+1)]
    times = [data['samples'][str((r['row']-1)*data['divisor'])]['time'] for r in computed]
    errors = [100*(r['predicted']-r['expected'])/abs(r['expected']) for r in computed]
    palette = ROOT/'web/plot-colors.js'
    match = re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\);',palette.read_text(),re.S)
    colors = re.findall(r'#[0-9a-fA-F]{6}',match[1])
    fig,(ax,error) = plt.subplots(2,1,figsize=(9,6),sharex=True,gridspec_kw=dict(height_ratios=[2,1]))
    ax.plot([r['time'] for r in rows],[r['expected'] for r in rows],color=colors[0],label='Archived ASWING')
    ax.plot([s['time'] for s in states],[s['moment'] for s in states],color=colors[1],linestyle='--',
            label=f'OpenSwing · {data["nodes"]} nodes · dt={data["dt"]} s')
    ax.set_ylabel('Root Mc′ (N m)')
    error.axhspan(-5,5,color=colors[3],alpha=.14,label='5% native allowance')
    error.axhline(0,color='#777',lw=.7)
    error.plot(times,errors,color=colors[1])
    error.set(ylabel='Native error (%)',xlabel='Time (s)',ylim=(min(-6,min(errors)-.5),max(6,max(errors)+.5)))
    for axis in (ax,error):
        axis.grid(alpha=.2)
        axis.spines[['top','right']].set_visible(False)
        if not data['complete']:
            axis.axvspan(data['end_time'],float(data['required_steps'])*float(data['dt']),
                         color='#999',alpha=.16,label='Remaining history' if axis is ax else None)
    ax.legend(frameon=False,fontsize=8)
    error.legend(frameon=False,fontsize=8,loc='upper right')
    passed = sum(r['passed'] for r in computed)
    fig.suptitle(f'ISAE FFWT-4 · Fixed-1: {data["accepted_steps"]:,}/{data["required_steps"]:,} steps\n'
                 f'{len(computed)}/200 native values computed; {passed}/{len(computed)} pass',fontsize=12)
    fig.text(.5,.015,'Literal model and gust. Full-history spatial/time accuracy and the other 1,400 fixed-history values remain open.',
             ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,.94))
    args.output_dir.mkdir(parents=True,exist_ok=False)
    for suffix in ('png','svg'):
        fig.savefig(args.output_dir/('comparison.'+suffix),dpi=150,bbox_inches='tight')
    plt.close(fig)
    write(args.output_dir/'inputs.json',dict(inputs=[pin(args.assessment),data['terminal_journal'],pin(palette),pin(__file__)]))


if __name__ == '__main__':
    main()
