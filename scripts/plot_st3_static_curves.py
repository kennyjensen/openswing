"""Plot the complete current ST-3 static comparison from its retained summary."""
import argparse
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    summary=json.loads((a.directory/'summary.json').read_text())
    assert summary['required']==86 and summary['available']==84
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    names={'0_3_90':('[0₃/90]s','#5b58ad'),'p15_0':('[+15₂/0₂]s','#c86717'),'m15_0':('[-15₂/0₂]s','#15806b')}
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for ax,(kind,quantity) in zip(axes.flat,[('F','Z'),('M','T'),('F','T'),('M','Z')]):
        for name,(label,color) in names.items():
            rows=sorted([r for r in summary['rows'] if r['kind']==kind and r['quantity']==quantity and r['name']==name],key=lambda r:r['script_load'])
            ax.plot([r['script_load'] for r in rows],[r['predictions'][1] for r in rows],color=color,lw=1.6)
            available=[r for r in rows if r['source_available']]
            ax.plot([r['script_load'] for r in available],[r['expected'] for r in available],ls='none',marker='s',ms=5,mfc='none',color=color,label=label)
            missing=[r for r in rows if not r['source_available']]
            ax.plot([r['script_load'] for r in missing],[r['predictions'][1] for r in missing],ls='none',marker='x',ms=7,color=color)
        ax.set_xlabel('Force (N)' if kind=='F' else 'Original script torque abscissa*')
        ax.set_ylabel('Plotted tip deflection (m)' if quantity=='Z' else 'Plotted section twist (deg)')
        ax.grid(alpha=.25);ax.set_title(f'{quantity}({kind})')
    axes[0,0].legend(fontsize=9)
    fig.legend(handles=[Line2D([0],[0],color='#444',label='OpenSwing, fine mesh'),
        Line2D([0],[0],color='#444',ls='none',marker='s',mfc='none',label='Archived ASWING markers'),
        Line2D([0],[0],color='#444',ls='none',marker='x',label='Computed only; source clipped')],
        loc='outside lower center',ncol=3,fontsize=9)
    fig.suptitle(f"ST-3 static curves: {summary['passed']}/{summary['required']} comparisons pass at 5%\n"
        '*Physical undeformed torque = 1.3734 × script abscissa (N m)',fontsize=12)
    for suffix in ('png','svg'):
        output=a.directory/f'comparison.{suffix}';assert not output.exists()
        fig.savefig(output,dpi=160)
    plt.close(fig)


if __name__=='__main__':main()
