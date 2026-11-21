"""Audit fixed-probe SA-11 wake comparisons and decompose the largest far-offset change."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.aero import semi_infinite_vortex


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x,np.ndarray): return x.tolist()
    if isinstance(x,np.generic): return x.item()
    if isinstance(x,dict): return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)): return [portable(v) for v in x]
    return x


def grouped(data):
    values={};members={}
    for i,(a,b,g) in enumerate(zip(data['a'],data['b'],data['gamma'])):
        for point,sign in ((a,-1),(b,1)):
            key=tuple(point)
            values.setdefault(key,[]).append(sign*g)
            members.setdefault(key,[]).append(dict(panel=i,beam=int(data['beam'][i]),
                endpoint='b' if sign>0 else 'a',signed_gamma=float(sign*g)))
    return {k:math.fsum(v) for k,v in values.items()},members


def decompose(point,coarse,fine,expected):
    g0,m0=grouped(coarse);g1,m1=grouped(fine)
    nodes=sorted(set(g0)|set(g1));origins=np.asarray(nodes)
    delta=np.array([g1.get(k,0.)-g0.get(k,0.) for k in nodes])
    pg=fine['pg'];direction=fine['direction']
    kernel=semi_infinite_vortex((point-origins)@pg.T,0.,direction@pg.T)@pg
    contribution=kernel*delta[:,None]
    actual=np.array([math.fsum(contribution[:,k]) for k in range(3)])
    np.testing.assert_allclose(actual,expected,atol=2e-8,rtol=2e-10)
    top=[]
    for i in np.argsort(np.linalg.norm(contribution,axis=1))[-8:][::-1]:
        key=nodes[i]
        offset=point-origins[i];along=offset@direction
        top.append(dict(origin=origins[i],common_exact_origin=key in g0 and key in g1,
            coarse_strength=g0.get(key,0.),fine_strength=g1.get(key,0.),strength_change=delta[i],
            velocity_change=contribution[i],change_magnitude=float(np.linalg.norm(contribution[i])),
            shortest_ray_distance=float(np.linalg.norm(offset-max(along,0.)*direction)),
            coarse_members=m0.get(key,[]),fine_members=m1.get(key,[])))
    # Components need not align. Retain full vectors instead of interpreting
    # ratios of individual magnitudes as additive percentages of the total.
    return dict(total=actual,reconstruction_error=float(np.max(abs(actual-expected))),top_origins=top)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'analysis-driver-used.py')
    rows=[];pins=None;manifests={};circulation=[];aliases=[];decompositions=[];seconds=0.;subdivision=[]
    for shape in ('upper','both'):
        for mode in ('frozen','current'):
            source=ROOT/f'artifacts/isae/sa11-fixed-wake-probes-20261108-{shape}-{mode}'
            manifest=json.loads((source/'verification.json').read_text())
            for name,digest in manifest['artifacts'].items(): assert sha(source/name)==digest,name
            manifests[str(source.relative_to(ROOT))]=sha(source/'verification.json')
            plan=json.loads((source/'plan.json').read_text())
            if pins is None: pins=plan['unchanged_pins']
            assert pins==plan['unchanged_pins']
            result=json.loads((source/'results.json').read_text())
            with np.load(source/'probes.npz') as saved: data={k:saved[k] for k in saved.files}
            changes=np.linalg.norm(data['fine_wake']-data['coarse_wake'],axis=1)/30.
            np.testing.assert_allclose(changes,[r['wake_change_over_freestream'] for r in result['fixed_probes']],atol=2e-13,rtol=2e-13)
            for offset in plan['normal_offsets_over_local_chord']:
                indices=[i for i,r in enumerate(result['fixed_probes']) if r['offset_over_chord']==offset]
                worst=indices[int(np.argmax(changes[indices]))]
                rows.append(dict(example=shape,influence=mode,offset_over_chord=offset,probes=len(indices),
                    maximum_wake_change_percent_of_U=100*float(np.max(changes[indices])),
                    median_wake_change_percent_of_U=100*float(np.median(changes[indices])),
                    worst_probe=result['fixed_probes'][worst]))
                if offset==.1:
                    fields=[]
                    for n in (48,96):
                        p=ROOT/f'artifacts/isae/sa11-section-velocity-20261108-{shape}{n}-{mode}'
                        assert sha(p/'verification.json')==plan['source_manifests'][str(p.relative_to(ROOT))]
                        with np.load(p/'fields.npz') as stored: fields.append({k:stored[k] for k in stored.files})
                    detail=decompose(data['points'][worst],*fields,data['fine_wake'][worst]-data['coarse_wake'][worst])
                    decompositions.append(dict(example=shape,influence=mode,offset_over_chord=offset,
                                               point=data['points'][worst],**detail))
            circulation.extend([dict(example=shape,influence=mode,**r) for r in result['circulation_comparison']])
            aliases.extend([dict(example=shape,influence=mode,**r) for r in result['coarse_receiver_aliases']])
            seconds+=result['total_seconds']
            subdivision.extend([result['subdivision_bound_max_error'],result['subdivision_wake_max_error']])
    for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
    fig,axes=plt.subplots(1,2,figsize=(11,4.8),constrained_layout=True)
    for shape,mode,color in [('upper','frozen','#0072B2'),('upper','current','#56B4E9'),
                             ('both','frozen','#D55E00'),('both','current','#CC79A7')]:
        selected=[r for r in rows if r['example']==shape and r['influence']==mode]
        x=[100*r['offset_over_chord'] for r in selected]
        label=f"{'Upper' if shape=='upper' else 'Upper/lower'}, {mode}"
        for ax,key in zip(axes,['maximum_wake_change_percent_of_U','median_wake_change_percent_of_U']):
            ax.loglog(x,[r[key] for r in selected],'o-',color=color,label=label)
    for ax,title in zip(axes,['Largest change among fixed probes','Median change among fixed probes']):
        ax.set_title(title);ax.set_xlabel('Distance from own wake plane (% local chord)')
        ax.set_ylabel('N48 → N96 wake-velocity change / 30 m/s (%)')
        ax.set_xticks([.1,1.,10.]);ax.set_xticklabels(['0.1','1','10'])
        ax.xaxis.set_minor_formatter(NullFormatter());ax.grid(True,which='both',alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle('Identical probes; saved circulation on each grid; no new solves or finite core',fontsize=12)
    fig.savefig(args.output/'fixed-wake-probes.png',dpi=160)
    fig.savefig(args.output/'fixed-wake-probes.svg');plt.close(fig)
    analysis=dict(observed_utc=datetime.now(timezone.utc).isoformat(),unchanged_pins=pins,
        source_manifests=manifests,rows=rows,circulation_comparison=circulation,
        coarse_receiver_aliases=aliases,far_offset_change_decomposition=decompositions,
        total_unique_fixed_probes=sum(r['probes'] for r in rows),new_circulation_solves=0,
        recorded_seconds=seconds,maximum_subdivision_error=max(subdivision),
        scope='Wake changes normalized by flight speed, not ASWING reference error or an ISAE passing fraction.',
        artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    for name,digest in pins.items(): assert sha(ROOT/name)==digest,name
    (args.output/'analysis.json').write_text(json.dumps(portable(analysis),indent=2,allow_nan=False)+'\n')
    print(json.dumps(portable(dict(status='verified',fixed_probes=analysis['total_unique_fixed_probes'],
        seconds=seconds,subdivision_error=max(subdivision),
        far_offset_top_rays=[dict(example=r['example'],influence=r['influence'],total_change=np.linalg.norm(r['total']),
                                 top=r['top_origins'][0]) for r in decompositions]))))


if __name__=='__main__': main()
