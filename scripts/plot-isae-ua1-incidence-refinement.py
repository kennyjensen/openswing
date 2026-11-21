"""Render a readable convergence figure from completed UA-1 audit results."""
from hashlib import sha256
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua1-incidence-periodic-refined-20261101'
STEM=ROOT/'docs/validation/isae-ua1-incidence-periodic-refined-20261101'


def main():
    receipt=BASE/'figure.json'
    assert not receipt.exists()
    data=json.loads(STEM.with_suffix('.json').read_text())
    paths=[Path(__file__).resolve(),STEM.with_suffix('.json'),STEM.with_suffix('.md')]
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    fig,ax=plt.subplots(figsize=(8,5),constrained_layout=True)
    for key,color,label in (('CL','#2563eb','Lift'),('circulation','#d97706','Circulation'),('circulation_rate','#059669','Circulation rate')):
        errors=[100*data['grids'][str(n)]['cycles'][-1]['error_fractions'][key] for n in (80,160,320)]
        ax.loglog([80,160,320],errors,color=color,marker='o',label=label)
    ax.axhline(.1,color='.4',linestyle=':',label='Fine waveform limit (0.1%)')
    ax.xaxis.set_major_locator(FixedLocator([80,160,320]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.set(xlabel='Steps per cycle',ylabel='Final-cycle waveform error (%)',
        title='UA-1 inclined periodic response: time refinement\n9°, k=0.94, peak-to-peak A/c=0.5; unchanged equations and limits')
    ax.grid(alpha=.2,which='both');ax.legend()
    out=STEM.with_name(STEM.name+'-convergence')
    for suffix in ('.svg','.png'):fig.savefig(out.with_suffix(suffix),dpi=170)
    plt.close(fig)
    before=STEM.with_suffix('.md').read_text()
    old='![Time refinement, waveform and motion accuracy](isae-ua1-incidence-periodic-refined-20261101.svg)'
    new='![Periodic lift, circulation and rate error under time refinement](isae-ua1-incidence-periodic-refined-20261101-convergence.svg)'
    assert old in before
    STEM.with_suffix('.md').write_text(before.replace(old,new))
    outputs=[out.with_suffix('.svg'),out.with_suffix('.png'),STEM.with_suffix('.md')]
    receipt.write_text(json.dumps(dict(input_sha256=pins,
        output_sha256={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in outputs},
        scope='Presentation only: replace overlapping log-axis labels with fixed sample-count ticks; original four-panel figure retained.',
        numerical_results_changed=False),indent=2)+'\n')
    print('Saved convergence figure; numerical results unchanged.')


if __name__=='__main__':main()
