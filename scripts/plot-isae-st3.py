"""Export original modal comparison plots with explicit setup distinctions."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/validation'
d=json.loads((DEST/'isae-st3-checks.json').read_text())
colors=['#ff4a3d','#ff9f1a','#ffd166']
fig,axes=plt.subplots(1,3,figsize=(11.5,4.6),layout='constrained')
names=['0_3_90','p15_0','m15_0'];labels=['1B','1T','2B'];x=np.arange(3)
for ax,name,title in zip(axes,names,[r'$[0_3/90]_s$',r'$[+15_2/0_2]_s$',r'$[-15_2/0_2]_s$']):
 rows={r['label']:r for r in d['comparisons'] if r['name']==name}
 ax.plot(x,[rows[k]['primary_experiment_Hz'] for k in labels],'ko',label='Dunn measured',markersize=6,zorder=5)
 for offset,key,label,color in zip([-.13,0,.13],['gravity_off_air_free_Hz','self_weight_air_free_Hz','self_weight_small_positive_speed_Hz'],
  ['No gravity / no air, N64','Self-weight / no air, N64','Self-weight / V=0.01 m/s, N32'],colors):
  ax.scatter(x+offset,[rows[k][key] for k in labels],marker='x',s=48,color=color,label=label,zorder=4)
 ax.set(xticks=x,xticklabels=labels,title=title,ylabel='Frequency (Hz)',ylim=(0,32));ax.grid(axis='y',alpha=.2)
handles,legend_labels=axes[0].get_legend_handles_labels()
fig.legend(handles,legend_labels,fontsize=8,loc='outside lower center',ncol=2)
fig.suptitle('ST-3 literal inputs versus the primary frequency table\nCoupled-mode labels approximate; setup/property differences remain',fontsize=12)
fig.savefig(DEST/'isae-st3-comparison.png',dpi=180);fig.savefig(DEST/'isae-st3-comparison.svg');plt.close(fig)
print('Saved ST-3 PNG and SVG comparison')
