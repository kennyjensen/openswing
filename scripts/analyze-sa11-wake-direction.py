"""Audit the isolated wake rotation and compare its saved finite-chord states."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def portable(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:portable(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [portable(v) for v in x]
    return x


def cross(a,b):return np.array([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]])


def peak_decomposition(d,nc,vlm):
    rows=[];pg=d['pg'];ray_strength=d['ray_coefficients']@d['gamma']
    strength=d['edge_coefficients']@d['gamma']
    for label in ('quarter','body_edge'):
        if label=='quarter':
            index=int(np.argmax(np.linalg.norm(d['quarter_chord_velocity'],axis=1)))
            p=d['quarter_chord_probes'][index];velocity=d['quarter_chord_velocity'][index]
            own=None
            if nc==1:
                source=np.flatnonzero(d['chord_index']==0)[index]
                a,b=d['corners'][source,:2]
                found=np.flatnonzero((np.all(d['starts']==a,axis=1)&np.all(d['ends']==b,axis=1))|
                                     (np.all(d['starts']==b,axis=1)&np.all(d['ends']==a,axis=1)))
                assert len(found)==1;own=int(found[0])
        else:
            index=int(np.argmax(np.where(d['body_mask'],np.linalg.norm(d['edge_velocity'],axis=1),-1.)))
            p=d['edge_midpoints'][index];velocity=d['edge_velocity'][index];own=index
        active=np.flatnonzero(strength!=0.)
        if own is not None:active=active[active!=own]
        bound=vlm.finite_segment(p@pg,d['starts'][active]@pg,d['ends'][active]@pg)
        finite=np.einsum('ek,e->k',bound,strength[active])@pg
        ray=vlm.semi_infinite(p@pg,d['ray_starts']@pg,d['wake_direction']@pg)@pg
        contributions=ray*ray_strength[:,None];wake=contributions.sum(axis=0)
        np.testing.assert_allclose(finite+wake+d['ambient'],velocity,atol=2e-9,rtol=3e-11)
        dominant=int(np.argmax(np.linalg.norm(contributions,axis=1)))
        relative=p-d['ray_starts'][dominant]
        direction=d['wake_direction']/np.linalg.norm(d['wake_direction'])
        along=float(relative@direction);distance=float(np.linalg.norm(relative-along*direction))
        rows.append(dict(probe=label,index=index,point=p,speed_ratio=np.linalg.norm(velocity),
            finite_velocity=finite,wake_velocity=wake,ambient=d['ambient'],
            finite_speed_ratio=np.linalg.norm(finite),wake_speed_ratio=np.linalg.norm(wake),
            largest_ray_origin=d['ray_starts'][dominant],largest_ray_strength_unit_speed=ray_strength[dominant],
            largest_ray_velocity=contributions[dominant],largest_ray_perpendicular_distance_m=distance,
            largest_ray_downstream_distance_m=along))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batches',type=Path,nargs=4,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    sys.path.insert(0,str((args.batches[0]/'reference').resolve()));import vlm
    pins=[];rows=[];audits=[];seen=set()
    for batch in args.batches:
        plan=json.loads((batch/'plan.json').read_text());v=json.loads((batch/'verification.json').read_text())
        assert all(sha(batch/p)==h for p,h in v['artifacts'].items())
        assert all(sha(ROOT/p)==h for p,h in plan['unchanged_pins'].items())
        baseline=ROOT/plan['baseline'];prior=json.loads((baseline/'plan.json').read_text())
        assert sha(baseline/'plan.json')==plan['baseline_plan_sha256']
        assert sha(baseline/'results.json')==plan['baseline_results_sha256']
        bv=json.loads((baseline/'verification.json').read_text())
        assert all(sha(baseline/p)==h for p,h in bv['artifacts'].items())
        assert sha(Path(vlm.__file__))==prior['reference_pins']['vlm.py']
        old_rows=json.loads((baseline/'results.json').read_text());current=json.loads((batch/'results.json').read_text())
        assert [r['chord_rows'] for r in current]==plan['chord_rows']
        pins.append(dict(batch=str(batch),plan_sha256=sha(batch/'plan.json'),results_sha256=sha(batch/'results.json')))
        for row in current:
            nc=row['chord_rows'];key=(plan['example'],plan['span'],nc);assert key not in seen;seen.add(key)
            old=next(r for r in old_rows if r['chord_rows']==nc)
            assert row['baseline_artifact_sha256']==old['artifact']['sha256']
            with np.load(batch/row['artifact']['path']) as z:d={k:z[k] for k in z.files}
            with np.load(baseline/old['artifact']['path']) as z:before={k:z[k] for k in z.files}
            fixed=('corners','chord_index','collocation','normals','starts','ends','body_edge_coefficients',
                'body_mask','edge_midpoints','quarter_chord_probes','pg','ambient','rhs','beam','t','offsheet_probes')
            for k in fixed:np.testing.assert_array_equal(d[k],before[k])
            np.testing.assert_array_equal(d['held_gamma'],before['gamma'])
            np.testing.assert_array_equal(d['matrix'],before['matrix']+d['delta_matrix'])
            scalar=np.array([math.fsum(float(a)*float(g) for a,g in zip(line,d['gamma']))-float(b)
                             for line,b in zip(d['matrix'],d['rhs'])])
            assert row['status']=='linear_solution' and np.max(abs(scalar))<2e-11
            pg=d['pg'];p=d['offsheet_probes']@pg
            fv=vlm.finite_segment(p[:,None,:],(d['starts']@pg)[None,:,:],(d['ends']@pg)[None,:,:])
            rv=vlm.semi_infinite(p[:,None,:],(d['ray_starts']@pg)[None,:,:],d['wake_direction']@pg)
            unit=(np.einsum('iek,ej->ijk',fv,d['edge_coefficients'])+np.einsum('irk,rj->ijk',rv,d['ray_coefficients']))@pg
            topology=dict(corners=d['corners']@pg,trailing=d['chord_index']==nc-1,wake_direction=d['wake_direction']@pg)
            ring=vlm.influence_velocity(p,topology)@pg
            np.testing.assert_allclose(unit,ring,atol=2e-10,rtol=2e-10)
            np.testing.assert_allclose(np.einsum('ijk,j->ik',unit,d['gamma'])+d['ambient'],d['offsheet_velocity'],atol=2e-10,rtol=2e-10)
            body_strength=np.array([math.fsum(float(c)*float(g) for c,g in zip(line,d['gamma'])) for line in d['body_edge_coefficients']])
            forces=np.array([1.2256*900*g*cross(v,b-a) for g,v,a,b in zip(body_strength,d['edge_velocity'],d['starts'],d['ends'])])
            moments=np.array([cross(p-[18.5,0.,0.],f) for p,f in zip(d['edge_midpoints'],forces)])
            np.testing.assert_allclose(forces,d['edge_forces'],atol=2e-9,rtol=3e-11)
            np.testing.assert_allclose(moments,d['edge_moments'],atol=4e-8,rtol=3e-11)
            totals=np.array([math.fsum(forces[:,i]) for i in range(3)])
            np.testing.assert_allclose(totals,row['force'],atol=2e-8,rtol=3e-11)
            audit=dict(example=plan['example'],span=plan['span'],chord_rows=nc,fixed_arrays_verified=len(fixed),
                scalar_residual=float(np.max(abs(scalar))),unit_source_field_difference=float(np.max(abs(unit-ring))),
                force_maximum_difference=float(np.max(abs(forces-d['edge_forces']))),symmetry_sideforce=float(abs(totals[1])),
                peak_decomposition=peak_decomposition(d,nc,vlm))
            audits.append(audit)
            comparison={k:100*(row[k]/old[k]-1) for k in ('CL_full_edges','CD_full_edges')}
            rows.append(dict(example=plan['example'],span=plan['span'],**row,baseline=old,
                coefficient_change_from_frozen_percent=comparison))
    assert seen=={(model,n,c) for model in ('isae-sa11-wingtip-up','isae-sa11-wingtip-up-and-down')
                  for n in (48,96) for c in ((1,2,4) if n==48 else (1,2))}
    refinement=[]
    for model in ('isae-sa11-wingtip-up','isae-sa11-wingtip-up-and-down'):
        for nc in (1,2):
            coarse=next(r for r in rows if (r['example'],r['span'],r['chord_rows'])==(model,48,nc))
            fine=next(r for r in rows if (r['example'],r['span'],r['chord_rows'])==(model,96,nc))
            refinement.append(dict(example=model,chord_rows=nc,change_percent={k:100*(fine[k]/coarse[k]-1)
                for k in ('quarter_peak_speed_ratio','body_edge_peak_speed_ratio','CL_full_edges','CD_full_edges')}))
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'analysis-driver-used.py')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(10.5,7),constrained_layout=True)
    for j,(model,title) in enumerate((('isae-sa11-wingtip-up','Upper winglets'),('isae-sa11-wingtip-up-and-down','Upper and lower winglets'))):
        for n,color,marker in ((48,'#0072B2','o'),(96,'#D55E00','s')):
            selected=sorted([r for r in rows if r['example']==model and r['span']==n],key=lambda r:r['chord_rows'])
            x=[r['chord_rows'] for r in selected]
            for ax,new,old in ((axes[0,j],'CD_full_edges','CD_full_edges'),(axes[1,j],'body_edge_peak_speed_ratio','edge_peak_speed_ratio')):
                ax.plot(x,[r['baseline'][old] for r in selected],':',color=color,marker=marker,label=f'N{n}, frozen wake')
                ax.plot(x,[r[new] for r in selected],'-',color=color,marker=marker,label=f'N{n}, aligned wake')
                ax.set_xticks([1,2,4]);ax.set_xlabel('Chordwise rows');ax.grid(alpha=.25)
        axes[0,j].set_title(title);axes[0,j].set_ylabel('Full-edge CD (symmetric log)')
        axes[0,j].set_yscale('symlog',linthresh=.005)
        axes[1,j].set_yscale('log');axes[1,j].set_ylabel('Body-edge peak speed / freestream')
    axes[0,0].legend(fontsize=7)
    fig.suptitle('SA-11 finite-chord control: isolated wake direction\nSame geometry, PG map, section normals and force probes; not full ASWING K/F-off')
    for ext in ('png','svg'):fig.savefig(args.output/('wake-direction-comparison.'+ext),dpi=160)
    plt.close(fig)
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),batch_pins=pins,solved_states=len(rows),new_solves_in_analysis=0,
        audits=audits,records=rows,refinement=refinement,
        maximum_scalar_residual=max(r['scalar_residual'] for r in audits),
        maximum_unit_source_field_difference=max(r['unit_source_field_difference'] for r in audits),
        numerical_solve_seconds=sum(r['solve_seconds'] for r in rows),stage_seconds=sum(r['stage_seconds'] for r in rows),
        unchanged_production_status_scope=True,files={p.name:sha(p) for p in args.output.iterdir() if p.is_file()})
    (args.output/'analysis.json').write_text(json.dumps(portable(summary),indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:portable(summary[k]) for k in ('solved_states','maximum_scalar_residual','maximum_unit_source_field_difference','refinement')},indent=2),flush=True)


if __name__=='__main__':main()
