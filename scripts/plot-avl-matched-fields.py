"""Plot saved matched winglet results; no native or OpenSwing solve."""
from pathlib import Path
import hashlib
import json
import re
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import LogLocator, NullFormatter
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/avl-matched-fields-review-20261108'
BASE=ROOT/'artifacts/isae/avl-matched-fields-r1-20261108'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not (OUT/'matched-winglet-fields.png').exists()
    report=json.loads((OUT/'report.json').read_text());assert report['status']=='verified'
    palette_source=ROOT/'web/plot-colors.js'
    palette=re.findall(r"'(#\w+)'",palette_source.read_text().split('export const plotColors')[1].split(']);')[0])
    fig,axes=plt.subplots(1,2,figsize=(10.8,4.6),layout='constrained')
    for color,n in zip(palette,(16,32,64)):
        directory=BASE/f'winglets-c1-s{n}'
        with np.load(directory/'native-fields.npz') as f:
            y=f['RV'][:,1].copy();z=f['RV'][:,2].copy();gamma=f['GAM'].ravel().copy()
            vx=f['VV'][:,0].copy()
        r=json.loads((directory/'openswing.json').read_text())
        ogamma=np.array([s['circulation'] for s in r['strips']])
        ovx=np.array([s['relative_velocity'][0] for s in r['strips']])-np.cos(np.deg2rad(5.))
        main=np.isclose(z,0)&(abs(y)<5)
        axes[0].plot(y[main],ogamma[main],color=color,lw=1.7,label=f'{n} wing strips')
        axes[0].plot(y[main],gamma[main],'o',color=color,mfc='none',ms=4,markevery=max(1,n//16))
        left=main&(y<0);distance=y[left]+5
        axes[1].loglog(distance,ovx[left],color=color,lw=1.7)
        axes[1].loglog(distance,vx[left],'o',color=color,mfc='none',ms=4,markevery=max(1,n//16))
    axes[0].set(xlabel='Wing span coordinate y [m]',ylabel='Circulation / freestream speed [m]',title='Circulation agrees on every mesh')
    axes[0].legend(fontsize=9)
    axes[1].set(xlabel='Distance from left winglet junction [m]',ylabel='Bound-induced streamwise velocity / freestream',title='Local junction velocity grows with refinement')
    axes[1].xaxis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
    axes[1].yaxis.set_minor_locator(LogLocator(base=10,subs=np.arange(2,10)))
    axes[1].xaxis.set_minor_formatter(NullFormatter());axes[1].yaxis.set_minor_formatter(NullFormatter())
    axes[1].legend(handles=[Line2D([],[],color='.3',label='OpenSwing'),Line2D([],[],color='.3',ls='none',marker='o',mfc='none',label='Native AVL')],fontsize=9)
    for ax in axes:
        ax.grid(which='major',alpha=.35);ax.grid(which='minor',alpha=.14)
    fig.suptitle('Matched one-row winglet control · original predictions · α = 5°, Mach = 0',fontsize=12)
    for suffix in ('png','svg'):fig.savefig(OUT/f'matched-winglet-fields.{suffix}',dpi=165)
    plt.close(fig)
    shutil.copyfile(__file__,OUT/'plot-driver-used.py')
    (OUT/'plot-verification.json').write_text(json.dumps(dict(report_sha256=sha(OUT/'report.json'),palette_sha256=sha(palette_source),new_solver_calls=0,
        note='Original unscaled native and production predictions. Different meshes approach the corner at different receiver positions; no fixed-position convergence claim.',
        files={name:sha(OUT/name) for name in ('matched-winglet-fields.png','matched-winglet-fields.svg','plot-driver-used.py')}),indent=2)+'\n')
    print('Saved matched-winglet-fields.png and .svg; no new solves.')


if __name__=='__main__':main()
