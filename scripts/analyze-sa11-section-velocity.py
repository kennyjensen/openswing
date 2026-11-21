"""Audit the eight retained SA-11 correction replays and their wake sources."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.factored_influence import FactoredInfluence


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(value):
    if isinstance(value,np.ndarray): return value.tolist()
    if isinstance(value,np.generic): return value.item()
    if isinstance(value,dict): return {k:portable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [portable(v) for v in value]
    return value


def write(path,value): path.write_text(json.dumps(portable(value),indent=2,allow_nan=False)+'\n')


def wake_sources(data,index):
    point=data['hv'][index]
    op=FactoredInfluence(point[None,:],data['a'],data['b'],data['direction'],data['pg'])
    gamma=data['gamma'];strength=op.wake_strengths(gamma)
    vectors=op.rays[0]*strength[:,None]
    total=vectors.sum(axis=0)
    np.testing.assert_allclose(total,data['wake_hv'][index],atol=2e-8,rtol=2e-11)
    rows=[]
    source,sign=op.representative_endpoints()
    for group in np.argsort(np.linalg.norm(vectors,axis=1))[-8:][::-1]:
        node=data['b' if sign[group]>0 else 'a'][source[group]]
        offset=point-node
        along=float(offset@data['direction'])
        distance=float(np.linalg.norm(offset-max(along,0.)*data['direction']))
        members=[]
        for endpoints,label,factor in ((op.starts,'a',-1.),(op.ends,'b',1.)):
            for i in np.flatnonzero(endpoints==group):
                members.append(dict(panel=int(i),beam=int(data['beam'][i]),t=float(data['t'][i]),
                                    endpoint=label,signed_gamma=float(factor*gamma[i])))
        rows.append(dict(group=int(group),origin=node,net_gamma=float(strength[group]),
                         velocity=vectors[group],speed=float(np.linalg.norm(vectors[group])),
                         axial_distance=along,ray_distance=distance,members=members))
    own=gamma[index]*(op.rays[0,op.ends[index]]-op.rays[0,op.starts[index]])
    return dict(index=index,total=total,own_horseshoe_wake=own,other_horseshoes_wake=total-own,
                top_grouped_rays=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Use a fresh output directory.')
    args.output.mkdir(parents=True)
    shutil.copyfile(__file__,args.output/'analysis-driver-used.py')
    summary=[];manifests={};plot_data={};all_pins=None;residuals=[];errors=[];native_time=0.;total_time=0.
    for shape in ('upper','both'):
        for mode in ('frozen','current'):
            for count in (48,96):
                path=ROOT/f'artifacts/isae/sa11-section-velocity-20261108-{shape}{count}-{mode}'
                manifest=json.loads((path/'verification.json').read_text())
                for name,digest in manifest['artifacts'].items(): assert sha(path/name)==digest,name
                manifests[str(path.relative_to(ROOT))]=sha(path/'verification.json')
                plan=json.loads((path/'plan.json').read_text())
                if all_pins is None: all_pins=plan['unchanged_pins']
                assert all_pins==plan['unchanged_pins']
                result=json.loads((path/'results.json').read_text())
                rows={r['label']:r for r in result['records']}
                with np.load(path/'fields.npz') as saved: data={k:saved[k] for k in saved.files}
                for label,row in rows.items():
                    velocity=data[label+'_velocity'];span=data['span']
                    perp=velocity-np.sum(velocity*span,axis=1)[:,None]*span
                    mach=np.linalg.norm(perp,axis=1)/340.21
                    np.testing.assert_allclose(mach,data[label+'_normal_mach'],atol=2e-13,rtol=2e-13)
                    assert abs(float(np.max(mach))-row['maximum_normal_mach'])<2e-13
                    wake=data['incompressible_wake_hv'] if label.startswith('incompressible') else data['wake_hv']
                    np.testing.assert_allclose(velocity,data['ambient']+wake+data[label+'_bound'],atol=2e-12,rtol=2e-13)
                original,primary=rows['native'],rows[plan['primary']]
                index=primary['worst']['index']
                span=data['span'][index]
                norm_perp=lambda v:float(np.linalg.norm(v-(v@span)*span))
                wake=data['wake_hv'][index]
                bound=data[plan['primary']+'_bound'][index]
                detail=wake_sources(data,index)
                alternatives=[r['maximum_normal_mach'] for k,r in rows.items()
                              if not k.startswith('incompressible') and k!='native']
                summary.append(dict(example=shape,influence=mode,panels=count,
                    native_max_mach=original['maximum_normal_mach'],primary_max_mach=primary['maximum_normal_mach'],
                    adaptation_max_mach_range=[min(alternatives),max(alternatives)],
                    incompressible_native_max_mach=rows['incompressible_native']['maximum_normal_mach'],
                    incompressible_primary_max_mach=rows['incompressible_local_chord_section_span']['maximum_normal_mach'],
                    primary_worst=primary['worst'],wake_normal_speed=norm_perp(wake),
                    corrected_bound_normal_speed=norm_perp(bound),
                    native_bound_normal_speed=norm_perp(data['bound_hv'][index]),
                    ambient_normal_speed=norm_perp(data['ambient']),
                    wake_to_corrected_bound_normal_ratio=norm_perp(wake)/norm_perp(bound),
                    raw_native_stall_residual=original['maximum_native_stall_residual'],
                    changed_native_stall_residual=primary['maximum_native_stall_residual'],
                    at_or_above_unity_before=original['at_or_above_unity'],
                    at_or_above_unity_after=primary['at_or_above_unity'],
                    wake_sources=detail))
                plot_data[(shape,mode,count)]=data
                errors.extend(c['maximum_difference'] for c in result['independent_checks'])
                residuals.append(original['maximum_native_stall_residual'])
                native_time+=result['native_solve_seconds'];total_time+=result['total_seconds']
    for name,digest in all_pins.items(): assert sha(ROOT/name)==digest,name
    # Isolate the free upper tip in the current-wind controls. The peak probe
    # moves with refinement: this is not a fixed-location convergence test.
    tips=[]
    for count in (48,96):
        data=plot_data[('upper','current',count)]
        indices=np.flatnonzero(data['beam']==2);i=int(indices[-1])
        node=data['b'][i];delta=data['hv'][i]-node
        direction=data['direction'];axial=float(delta@direction)
        ray_distance=float(np.linalg.norm(delta-max(axial,0.)*direction))
        tips.append(dict(panels=count,index=i,gamma=float(data['gamma'][i]),
                         tip=node,probe=data['hv'][i],ray_distance=ray_distance,
                         axial_distance=axial,
                         wake_speed=float(np.linalg.norm(data['wake_hv'][i])),
                         raw_mach=float(data['native_normal_mach'][i]),
                         corrected_mach=float(data['local_chord_section_span_normal_mach'][i])))
    tip_ratios={name:tips[1][name]/tips[0][name] for name in ('gamma','ray_distance','wake_speed','raw_mach','corrected_mach')}
    # Left panel compares maxima; right shows separate vector magnitudes at
    # the primary maximum, not a claim that magnitudes add as scalar speeds.
    fig,axes=plt.subplots(1,2,figsize=(11.5,5.4),constrained_layout=True)
    labels=[f"{'Up' if r['example']=='upper' else 'Up/down'} {r['panels']}\n{r['influence']}" for r in summary]
    x=np.arange(len(summary))
    axes[0].semilogy(x,[r['native_max_mach'] for r in summary],'o-',color='#333333',label='Original')
    axes[0].semilogy(x,[r['primary_max_mach'] for r in summary],'s--',color='#0072B2',label='Bound correction')
    axes[0].axhline(1.,color='#D55E00',linestyle=':',label='Local Mach = 1')
    axes[0].set_ylabel('Maximum section-normal Mach indicator')
    axes[0].set_title('The bound correction leaves the wake peaks')
    axes[1].semilogy(x,[r['wake_normal_speed'] for r in summary],'o-',color='#D55E00',label='Wake contribution')
    axes[1].semilogy(x,[r['corrected_bound_normal_speed'] for r in summary],'s-',color='#0072B2',label='Corrected bound contribution')
    axes[1].set_ylabel('Section-normal vector magnitude (m/s)')
    axes[1].set_title('Contributions at each corrected maximum')
    for ax in axes:
        ax.set_xticks(x);ax.set_xticklabels(labels,rotation=45,ha='right',fontsize=8)
        ax.grid(True,which='both',alpha=.25);ax.legend(fontsize=8)
    fig.suptitle('SA-11 prescribed fields: unchanged circulation; no corrected solve',fontsize=12)
    fig.savefig(args.output/'sa11-section-velocity.png',dpi=160)
    fig.savefig(args.output/'sa11-section-velocity.svg');plt.close(fig)
    report=dict(observed_utc=datetime.now(timezone.utc).isoformat(),source_manifests=manifests,
        unchanged_pins=all_pins,rows=summary,current_upper_tip=tips,current_upper_tip_refinement_ratios=tip_ratios,
        maximum_independent_bound_error=max(errors),maximum_native_stall_residual=max(residuals),
        native_solve_seconds=native_time,total_recorded_seconds=total_time,
        new_native_solves=4,candidate_circulation_solves=0,
        primary_scope='Six alternative mappings per saved Gamma; no native reference comparison or pass-count change.',
        artifacts={p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()})
    for name,digest in all_pins.items(): assert sha(ROOT/name)==digest,name
    write(args.output/'analysis.json',report)
    print(json.dumps(portable(dict(status='verified',cases=len(summary),max_bound_error=max(errors),
        native_residual=max(residuals),native_solve_seconds=native_time,total_recorded_seconds=total_time,
        tip_ratios=tip_ratios,
        wake_to_bound_range=[min(r['wake_to_corrected_bound_normal_ratio'] for r in summary),
                             max(r['wake_to_corrected_bound_normal_ratio'] for r in summary)]))))


if __name__=='__main__': main()
