"""Plot archived absolute sensors and current AE-1 errors, without new solves."""
import json
from pathlib import Path
import resource
import signal
import sys


def main(folder, summary_name='summary.json', prefix=''):
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=json.loads((folder/summary_name).read_text())
    rows=[r for r in summary['rows'] if r['speed'] is not None]
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for col,alpha in enumerate((5,7)):
        for index,(name,label,scale) in enumerate((('sensor3_RZ_earth_m','Tip Earth Z (mm)',1000),
                                                  ('sensor3_Theta_elevation_deg','Sensor elevation (deg)',1))):
            ax=axes[index,col]
            for mesh,color,style in ((40,'#ca6b20','--'),(80,'#2476ba','-')):
                selected=sorted((r for r in rows if r['alpha']==alpha and r['name']==name and r['mesh']==mesh),key=lambda r:r['speed'])
                x=[r['speed'] for r in selected]
                if mesh==40:ax.plot(x,[scale*r['expected'] for r in selected],color='#333333',lw=2,label='Archived ASWING')
                ax.plot(x,[scale*r['predicted'] if r['predicted'] is not None else float('nan') for r in selected],style,color=color,lw=1,
                        marker='o' if mesh==80 else 's',ms=2,label=f'OpenSwing nominal {mesh}')
            ax.set(title=f'Root incidence {alpha}°',xlabel='Commanded IAS / assigned TAS (m/s)',ylabel=label)
            ax.grid(alpha=.25);ax.legend(fontsize=8)
    coverage = ('gaps in OpenSwing curves are unrun states' if summary['unrun']
                else 'all 98 known speed points checked on both meshes')
    fig.suptitle(f'AE-1: literal Pazy model, frozen influences\nAbsolute outputs; {coverage}; startup speed is unknown',fontsize=12)
    fig.savefig(folder/(prefix+'sensor-curves.png'),dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    names=list(dict.fromkeys(r['name'] for r in rows))
    for ax,alpha in zip(axes,(5,7)):
        for name in names:
            selected=sorted((r for r in rows if r['alpha']==alpha and r['name']==name and r['mesh']==80),key=lambda r:r['speed'])
            ax.plot([r['speed'] for r in selected],[r['error_percent'] for r in selected],lw=1,
                    marker='o',ms=2,label=name.replace('_earth_m','').replace('_elevation_deg',''))
        ax.axhline(5,color='#b51f1f',ls='--',lw=1,label='5% allowance')
        ax.set(title=f'Root incidence {alpha}° — nominal 80',xlabel='Commanded IAS / assigned TAS (m/s)',ylabel='Absolute relative error (%)')
        ax.grid(alpha=.25);ax.legend(fontsize=7)
    fig.suptitle('AE-1: all six archived channels; percentage errors retain small reference values',fontsize=12)
    fig.savefig(folder/(prefix+'sensor-errors.png'),dpi=160);plt.close(fig)
    print(f'Wrote {prefix}sensor-curves.png and {prefix}sensor-errors.png; no physical calls.')


if __name__=='__main__':main(Path(sys.argv[1]).resolve(),*sys.argv[2:])
