"""Independent scalar replay and plot of the SA-11 paired-speed moment audit."""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FIRST=ROOT/'artifacts/isae/sa11-moment-speed-20261108'
SECOND=ROOT/'artifacts/isae/sa11-moment-receivers-20261108'
OUT=ROOT/'artifacts/isae/sa11-moment-speed-review-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
D=lambda x:Decimal(str(float(x)))


def main():
    assert not OUT.exists();OUT.mkdir(parents=True)
    first=read(FIRST/'analysis.json');plan=read(SECOND/'plan.json')
    pins={};metadata_changes={}
    for source in (first['source_sha256'],plan['pins']):
        for name,digest in source.items():
            actual=sha(ROOT/(new_name := 'docs/validation/ISAE_STATUS.md' if name == 'ISAE_STATUS.md' else name))
            if actual!=digest:
                assert name in ('ISAE_STATUS.md', 'docs/validation/ISAE_STATUS.md'),name
                metadata_changes[name]=dict(prior=digest,current=actual)
            pins[new_name]=actual
    for name,digest in first['artifact_sha256'].items():assert sha(FIRST/name)==digest,name
    for p in (FIRST/'analysis.json',SECOND/'plan.json',Path(__file__)):
        pins[str(p.relative_to(ROOT))]=sha(p)
    pairs=[]
    for spec in plan['cases']:
        folder=SECOND/spec['id'];record=read(folder/'moment-comparison.json');report=read(folder/'report.json')
        for name,digest in report['artifact_sha256'].items():assert sha(folder/name)==digest,name
        for p in folder.iterdir():
            if p.is_file():pins[str(p.relative_to(ROOT))]=sha(p)
        pairs.append(record)
    rows=first['cases']+pairs
    scalar_errors=[];rejections=[]
    for row in rows:
        p=(SECOND/row['id']/'moment-replay.npz') if row['id'].startswith('whole-beam') else FIRST/(row['id']+'.npz')
        pins[str(p.relative_to(ROOT))]=sha(p)
        with np.load(p) as data:
            # Decimal square roots at50digits are independent of NumPy's
            # vectorized arithmetic and the production moment calculation.
            with localcontext() as context:
                context.prec=50
                mach=[D(x) for x in data['mach']];ratio=Decimal(266)/Decimal(255)
                invalid=[i for i,m in enumerate(mach) if (m*ratio)**2>=1]
                if invalid:
                    assert row['predicted_delta_Cm'] is None
                    rejections.append(dict(id=row['id'],strips=invalid,maximum_M_high=row['maximum_M_high']))
                    continue
                terms=[D(w)*((1-(m*ratio)**2).sqrt()**-1-(1-m*m).sqrt()**-1)
                       for w,m in zip(data['weight'],mach)]
                total=float(sum(terms))
            error=abs(total-row['predicted_delta_Cm']);assert error<2e-17,(row['id'],error)
            scalar_errors.append(dict(id=row['id'],absolute_error=error))
            a,b=map(Decimal,row['reference']['Cm_tokens']);assert float(b-a)==row['reference']['delta_Cm']
            expected=100*(total/float(b-a)-1)
            assert abs(expected-row['delta_error_percent'])<1e-10
            if row['id'].startswith('whole-beam'):
                total_change=float(np.sum(data['flow_factor_difference']+data['geometry_weight_difference']))
                assert abs(total_change-row['native_minus_whole_delta'])<1e-16
                row['flow_share_percent']=100*row['flow_factor_contribution']/row['native_minus_whole_delta']
    assert len(rows)==10 and len(scalar_errors)==9 and len(rejections)==1
    summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,
        scalar_replay=scalar_errors,rejected=rejections,source_sha256=pins,metadata_changes=metadata_changes,
        physical_calls=2,physical_seconds=sum(r['physical_seconds'] for r in pairs),
        saved_high_speed_checks=4,maximum_saved_high_speed_error=max(r.get('paired_prediction_error',0) for r in rows),
        primary_passes_added=0,production_changed=False,primary_scope_changed=False,
        interpretation='Whole-beam receivers reduce the baseline paired-moment discrepancy with identical vortex endpoints. Extension fields agree closely in three valid replays; its fine1deg field crosses localMach1 at266m/s. These source-backed setup hypotheses remain unauthenticated; no global replacement of section velocity or validity guard is supported.')
    with (OUT/'analysis.json').open('x') as stream:json.dump(summary,stream,indent=2,allow_nan=False);stream.write('\n')
    plot(rows)
    print(json.dumps(dict(rows=len(rows),valid_scalar_checks=len(scalar_errors),rejected=len(rejections),
        max_scalar_error=max(r['absolute_error'] for r in scalar_errors),
        maximum_saved_high_speed_error=summary['maximum_saved_high_speed_error'],
        physical_seconds=summary['physical_seconds'],receiver_results=[{k:r[k] for k in
            ('alpha','delta_error_percent','native_receiver_error_percent','flow_share_percent')} for r in pairs])),flush=True)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10})
    fig,axes=plt.subplots(1,2,figsize=(11,4.8))
    # VibeLattice order: red, orange, yellow, green, cyan. Dark outlines make
    # the yellow series legible on a paper background.
    series=[('baseline_original','Original slope · AVL receivers','#ff0000','o'),
            ('baseline_slope634','Slope 6.34 · AVL receivers','#ff8c00','s'),
            ('whole-beam','Slope 6.34 · whole-beam receivers','#ffff00','D')]
    for prefix,label,color,marker in series:
        selected=sorted([r for r in rows if r['id'].startswith(prefix)],key=lambda r:r['alpha'])
        axes[0].plot([r['alpha'] for r in selected],[r['delta_error_percent'] for r in selected],
            marker=marker,color=color,markeredgecolor='#333',label=label)
    for n,color,marker in [(64,'#00ff00','o'),(128,'#00ffff','s')]:
        selected=sorted([r for r in rows if r['id'].startswith('candidate75') and r['id'].endswith(f'n{n}')],key=lambda r:r['alpha'])
        accepted=[r for r in selected if r['predicted_delta_Cm'] is not None]
        axes[1].plot([r['alpha'] for r in accepted],[r['delta_error_percent'] for r in accepted],
            marker=marker,color=color,markeredgecolor='#333',label=f'{70 if n==64 else 134} strips · whole-beam')
    axes[1].annotate('134 strips at 1°: rejected\nM⊥ = 1.0059 at 266 m/s',xy=(.83,.15),ha='center',fontsize=9,
                     bbox=dict(facecolor='#f8eeee',edgecolor='#9a5555',boxstyle='round'))
    for ax,title,variant in zip(axes,['Baseline: same endpoints, different receiver rule','Curved extension: saved production fields'],['wing_alone','wing_extension']):
        refs=[next(r['reference'] for r in rows if r['variant']==variant and r['alpha']==a) for a in (0.,1.)]
        widths=[100*(r['delta_interval'][1]-r['delta_interval'][0])/2/abs(r['delta_Cm']) for r in refs]
        y=np.array([widths[0],*widths,widths[-1]])
        ax.fill_between([-.12,0,1,1.12],-y,y,color='#999',alpha=.15,label='Reference rounding band')
        ax.axhline(0,color='#777',lw=.8);ax.set_xticks([0,1]);ax.set_xlabel('Aircraft incidence (degrees)')
        ax.set_ylabel('Error in ΔCm between 255 and 266 m/s (%)');ax.set_title(title,fontsize=11)
        ax.grid(alpha=.2);ax.legend(fontsize=8,loc='upper left');ax.set_xlim(-.12,1.12)
    axes[0].set_ylim(-2,48);axes[1].set_ylim(-.85,.7)
    fig.suptitle('SA-11 moment speed dependence · no parameter fitting',fontsize=13)
    fig.text(.5,.015,'Alternative setup diagnostics; historical inputs remain unverified. No new primary ISAE passes.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,.94))
    fig.savefig(OUT/'moment-speed.png',dpi=160);fig.savefig(OUT/'moment-speed.svg');plt.close(fig)


if __name__=='__main__':main()
