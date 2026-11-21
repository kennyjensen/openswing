"""Independent saved-state/source-column checks for the SA-11 chord study."""
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
SAVED=ROOT/'artifacts/isae/sa11-winglet-junction-20261107'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def cross(a,b):
    return np.array([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]])


def raw_horseshoes(points,source,gamma,pg,vlm):
    result=[]
    a,b=source['a']@pg,source['b']@pg
    for i,p in enumerate(points@pg):
        keep=np.arange(len(gamma))!=i
        bound=vlm.finite_segment(p,a[keep],b[keep])
        wake=vlm.semi_infinite(p,b,[1.,0.,0.])-vlm.semi_infinite(p,a,[1.,0.,0.])
        result.append((np.einsum('ij,i->j',bound,gamma[keep])+np.einsum('ij,i->j',wake,gamma))@pg)
    return np.asarray(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batches',type=Path,nargs=4,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory.')
    rows=[];audits=[];pins=[];seen=set()
    sys.path.insert(0,str((args.batches[0]/'reference').resolve()));import vlm
    for batch in args.batches:
        plan=json.loads((batch/'plan.json').read_text());v=json.loads((batch/'verification.json').read_text())
        assert all(sha(batch/p)==h for p,h in v['artifacts'].items())
        assert all(sha(ROOT/p)==h for p,h in plan['unchanged_pins'].items())
        assert sha(Path(vlm.__file__))==plan['reference_pins']['vlm.py']
        saved_path=SAVED/f"{plan['example']}-{plan['span']}.npz"
        assert sha(saved_path)==plan['input_sha256']
        with np.load(saved_path) as z:source={k:z[k] for k in z.files}
        pins.append(dict(batch=str(batch),results_sha256=sha(batch/'results.json'),plan_sha256=sha(batch/'plan.json')))
        current=json.loads((batch/'results.json').read_text())
        assert [r['chord_rows'] for r in current]==plan['chord_rows']
        for row in current:
            nc=row['chord_rows'];key=(plan['example'],plan['span'],nc)
            assert key not in seen;seen.add(key)
            with np.load(batch/row['artifact']['path']) as z:d={k:z[k] for k in z.files}
            assert row['status']=='linear_solution'
            scalar=np.array([math.fsum(float(a)*float(g) for a,g in zip(line,d['gamma']))-float(rhs)
                             for line,rhs in zip(d['matrix'],d['rhs'])])
            assert np.max(abs(scalar))<2e-11
            # Compare every unit-source field with unsplit closed-ring formulas.
            p=d['offsheet_probes']@d['pg'];pg=d['pg']
            finite=vlm.finite_segment(p[:,None,:],(d['starts']@pg)[None,:,:],(d['ends']@pg)[None,:,:])
            rays=vlm.semi_infinite(p[:,None,:],(d['ray_starts']@pg)[None,:,:],[1.,0.,0.])
            atom=(np.einsum('iek,ej->ijk',finite,d['edge_coefficients'])+
                  np.einsum('iek,ej->ijk',rays,d['ray_coefficients']))@pg
            topology=dict(corners=d['corners']@pg,trailing=d['chord_index']==nc-1,wake_direction=np.array([1.,0.,0.]))
            ring=vlm.influence_velocity(p,topology)@pg
            np.testing.assert_allclose(atom,ring,atol=2e-10,rtol=2e-10)
            field=np.einsum('ijk,j->ik',atom,d['gamma'])+d['ambient']
            np.testing.assert_allclose(field,d['offsheet_velocity'],atol=2e-11,rtol=2e-11)
            strength=np.array([math.fsum(float(c)*float(g) for c,g in zip(line,d['gamma']))
                               for line in d['body_edge_coefficients']])
            force=np.array([1.2256*900*g*cross(v,b-a) for g,v,a,b in zip(strength,d['edge_velocity'],d['starts'],d['ends'])])
            moments=np.array([cross(p-[18.5,0.,0.],f) for p,f in zip(d['edge_midpoints'],force)])
            np.testing.assert_allclose(force,d['edge_forces'],atol=2e-9,rtol=2e-11)
            np.testing.assert_allclose(moments,d['edge_moments'],atol=4e-8,rtol=2e-11)
            total=np.array([math.fsum(force[:,i]) for i in range(3)])
            np.testing.assert_allclose(total,row['force'],atol=2e-8,rtol=2e-11)
            bridge=None
            if nc==1:
                original=raw_horseshoes(d['quarter_chord_probes'],source,source['gamma']/30.,pg,vlm)+d['ambient']
                np.testing.assert_allclose(original,d['prescribed_velocity'],atol=7e-9,rtol=3e-11)
                bridge=float(np.max(abs(original-d['prescribed_velocity']))*30.)
            audit=dict(example=plan['example'],span=plan['span'],chord_rows=nc,
                maximum_scalar_boundary_residual=float(np.max(abs(scalar))),
                maximum_unit_source_field_difference=float(np.max(abs(atom-ring))),
                full_one_row_horseshoe_field_difference_mps=bridge,
                force_maximum_component_difference=float(np.max(abs(force-d['edge_forces']))),
                symmetric_sideforce_absolute=float(abs(total[1])))
            audits.append(audit);rows.append(dict(example=plan['example'],span=plan['span'],**row))
    expected={(model,n,c) for model in ('isae-sa11-wingtip-up','isae-sa11-wingtip-up-and-down')
              for n in (48,96) for c in ((1,2,4) if n==48 else (1,2))}
    assert seen==expected and len(rows)==10
    refinement=[]
    for model in ('isae-sa11-wingtip-up','isae-sa11-wingtip-up-and-down'):
        for nc in (1,2):
            coarse=next(r for r in rows if (r['example'],r['span'],r['chord_rows'])==(model,48,nc))
            fine=next(r for r in rows if (r['example'],r['span'],r['chord_rows'])==(model,96,nc))
            refinement.append(dict(example=model,chord_rows=nc,change_percent={
                k:100*(fine[k]/coarse[k]-1) for k in ('quarter_chord_peak_speed_ratio','edge_peak_speed_ratio','CL_full_edges','CD_full_edges')}))
    args.output.mkdir(parents=True);shutil.copyfile(__file__,args.output/'analysis-driver-used.py')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,3,figsize=(11.5,7),constrained_layout=True)
    for i,(model,title) in enumerate((('isae-sa11-wingtip-up','Upper winglets'),('isae-sa11-wingtip-up-and-down','Upper and lower winglets'))):
        for n,color,style in ((48,'#0072B2','o-'),(96,'#D55E00','s--')):
            subset=sorted([r for r in rows if r['example']==model and r['span']==n],key=lambda r:r['chord_rows'])
            for j,key in enumerate(('quarter_chord_peak_speed_ratio','edge_peak_speed_ratio','CD_full_edges')):
                axes[i,j].plot([r['chord_rows'] for r in subset],[r[key] for r in subset],style,color=color,label=f'N{n} per beam')
                axes[i,j].set_xticks([1,2,4]);axes[i,j].set_xlabel('Chordwise rows');axes[i,j].grid(alpha=.25)
                if j<2:axes[i,j].set_yscale('log')
        axes[i,0].set_ylabel(title+'\nPeak speed / freestream')
        axes[i,0].set_title('Original quarter-chord probes')
        axes[i,1].set_title('Actual finite body-edge probes');axes[i,1].legend(fontsize=8)
        axes[i,2].set_title('Full finite-edge CD');axes[i,2].set_ylabel('CD')
    fig.suptitle('SA-11 frozen geometry: independent linear finite-chord controls\nOffsets preserved; no stall/profile drag; no ASWING-reference or physical-validity claim')
    for ext in ('png','svg'):fig.savefig(args.output/('finite-chord-comparison.'+ext),dpi=160)
    plt.close(fig)
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),batch_pins=pins,retained_linear_solutions=10,
        prescribed_field_states=10,new_solves_in_analysis=0,audits=audits,refinement=refinement,
        maximum_scalar_boundary_residual=max(r['maximum_scalar_boundary_residual'] for r in audits),
        maximum_unit_source_field_difference=max(r['maximum_unit_source_field_difference'] for r in audits),
        maximum_one_row_field_difference_mps=max(r['full_one_row_horseshoe_field_difference_mps'] or 0 for r in audits),
        retained_root_solve_seconds=sum(r['solve_seconds'] for r in rows),
        stages_seconds=sum(r['stage_seconds'] for r in rows),production_status_scope_unchanged=True,
        original_failed_attempt='artifacts/isae/sa11-finite-chord-20261107-up48/failure.json',
        original_failed_attempt_linear_solves=1,records=rows,
        files={p.name:sha(p) for p in args.output.iterdir() if p.is_file()})
    (args.output/'analysis.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:summary[k] for k in ('retained_linear_solutions','maximum_scalar_boundary_residual',
        'maximum_unit_source_field_difference','maximum_one_row_field_difference_mps','refinement')},indent=2),flush=True)


if __name__=='__main__':main()
