"""Plot computed loaded-wing crossings and show the unresolved published gap."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();root=args.root;args.output.mkdir(parents=True,exist_ok=True)
audit=json.loads((root/'portable-audit.json').read_text());assert audit['status']=='PASS_SCOPED_NUMERICAL_AUDIT'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(11,4.7),layout='constrained')
b=audit['boundaries'];n=[v['panels'] for v in b];u=[v['speed_m_s'] for v in b]
axes[0].plot(n,u,'o-',color='#8b4b85',label='Reconstructed 75% spar wing')
for x,y in zip(n,u):axes[0].annotate(f'{y:.4f}',(x,y),xytext=(0,-18),textcoords='offset points',ha='center')
axes[0].axhline(24.58,color='#444',ls='--',label='Published ASWING: 24.58 m/s')
axes[0].set(xlabel='Requested structural intervals',ylabel='Local crossing airspeed (m/s)',xticks=n,ylim=(21.5,25.1),title='Matched oscillatory crossing\nPublished setup remains incompletely known')
axes[0].legend(frameon=False,loc='upper left',fontsize=9)
records=[]
for name,color,marker in [('case-00.json','#007c83','o'),('case-01.json','#8b4b85','s')]:
    case=json.loads((root/'main73-run-01'/name).read_text());spec=case['spec']
    modes=[m for m in case['searches'][0]['modes'] if .1<m['frequency_Hz']<40]
    axes[1].scatter([m['eigenvalue_per_s'][0] for m in modes],[m['frequency_Hz'] for m in modes],color=color,marker=marker,label=f"{spec['wing']}% spar at {spec['speed_m_s']} m/s",s=42)
    records.append(dict(case=name,roots=[m['eigenvalue_per_s'] for m in modes]))
axes[1].axvline(0,color='#555',lw=1);axes[1].set(xlabel='Growth rate (1/s)',ylabel='Frequency (Hz)',ylim=(0,35),title='Sampled low modes at published speeds\nCurrent release, N = 32; not complete spectra')
axes[1].legend(frameon=False,loc='upper left',fontsize=9)
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Loaded Durrant reconstruction — mesh study with unresolved ASWING agreement',fontsize=12)
artifacts={}
for extension in ('svg','png','pdf'):
    path=args.output/f'loaded-flutter.{extension}';fig.savefig(path,dpi=170);artifacts[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
record=dict(plotter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),audit_sha256=hashlib.sha256((root/'portable-audit.json').read_bytes()).hexdigest(),roots=records,artifacts=artifacts,scope='Native reconstructed cases; no full-spectrum, exact-ASWING-setup, continuum-limit or experimental-validation claim.')
(args.output/'plot-provenance.json').write_text(json.dumps(record,indent=2)+'\n')
print(args.output/'loaded-flutter.png')
