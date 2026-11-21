"""Independent checks and root-field attribution for two retained aligned meshes."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/sa11-native-aligned-root-20261108'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


DRIVER = module('aligned_driver', 'verify-sa11-native-aligned-root.py')
FIELD = module('root_field', 'analyze-sa11-native-root-conformity.py')
VERIFY = module('original_field_checks', 'analyze-sa11-native-chord-refinement.py')
read, sha, write = DRIVER.read, DRIVER.sha, DRIVER.write


def main():
    plan = read(BASE/'plan.json'); DRIVER.check(plan)
    pins = dict(plan['pins'])
    for path in [Path(__file__), BASE/'plan.json', BASE/'driver-used.py']:
        pins[str(path.relative_to(ROOT))] = sha(path)
    rows = []
    original_audit = read(ROOT/'artifacts/isae/sa11-native-root-conformity-20261108/analysis.json')
    for case in plan['cases']:
        directory = BASE/case['id']; report = read(directory/'report.json')
        assert read(directory/'process.json')['returncode'] == 0
        for name, expected in report['artifact_sha256'].items():
            assert sha(directory/name) == expected, name
        pins[str((directory/'report.json').relative_to(ROOT))] = sha(directory/'report.json')
        with np.load(directory/'native-fields.npz') as data:
            f = {key:data[key].copy() for key in data.files}
        with np.load(directory/'derived-fields.npz') as data:
            beam = data['beam_indices'].copy(); fraction = data['chord_fraction'].copy()
        original_directory = ROOT/case['source']
        with np.load(original_directory/'native-fields.npz') as data:
            original_yz = data['RV'][:,1:].copy()
        with np.load(original_directory/'derived-fields.npz') as data:
            original_beam = data['beam_indices'].copy()
        for b in (1,2,3):
            old = np.unique(np.round(original_yz[original_beam==b],12),axis=0)
            new = np.unique(np.round(f['RV'][beam==b,1:],12),axis=0)
            assert np.array_equal(old,new), (case['id'],b)
        i = report['native_force_points']['worst_index']; p = f['RV'][i]@FIELD.PG
        gamma = f['GAM'].ravel()*240
        main = np.flatnonzero((beam==1)&(abs(f['RV2'][:,1]-1.2426)<1e-12))
        upper = np.flatnonzero((beam==2)&(abs(f['RV1'][:,1]-1.2426)<1e-12))
        shared = main[(fraction[main,0]>0)&(fraction[main,1]<1)]
        exposed = main[(fraction[main,0]==0)|(fraction[main,1]==1)]
        assert len(shared)==len(upper)==4 and len(exposed)==2
        assert np.array_equal(f['RV2'][shared],f['RV1'][upper])
        # Combine only the exactly coincident origins; no physical endpoints move.
        origins = np.concatenate([f['RV2'][shared],f['RV2'][exposed]])
        strengths = np.r_[gamma[shared]-gamma[upper],gamma[exposed]]
        order = np.argsort(origins[:,0]); origins=origins[order]; strengths=strengths[order]
        cumulative = np.cumsum(strengths)
        assert np.all(np.diff(origins[:,0])>0)
        root = np.sum(FIELD.rays(p,origins@FIELD.PG)*strengths[:,None],axis=0)@FIELD.PG
        paired = np.sum(FIELD.rays(p,f['RV2'][shared]@FIELD.PG)*(gamma[shared]-gamma[upper])[:,None],axis=0)@FIELD.PG
        unpaired = np.sum(FIELD.rays(p,f['RV2'][exposed]@FIELD.PG)*gamma[exposed,None],axis=0)@FIELD.PG
        finite = np.sum(FIELD.finite(p,origins[:-1]@FIELD.PG,origins[1:]@FIELD.PG)*cumulative[:-1,None],axis=0)@FIELD.PG
        tail = (FIELD.rays(p,origins[-1:]@FIELD.PG)*cumulative[-1]@FIELD.PG)[0]
        identity_error = max(float(np.max(abs(root-paired-unpaired))),float(np.max(abs(root-finite-tail))))
        assert identity_error < 1e-7
        bound,wake = VERIFY.QUADRATURE.independent_field(dict(a=f['RV1'],b=f['RV2'],hv=f['RV']),
            gamma*(4*np.pi*FIELD.PI4INV),np.array([1.,0.,0.]),i,96)
        bound_fine,_ = VERIFY.QUADRATURE.independent_field(dict(a=f['RV1'],b=f['RV2'],hv=f['RV']),
            gamma*(4*np.pi*FIELD.PI4INV),np.array([1.,0.,0.]),i,192)
        other = wake-root
        native_error = float(np.max(abs(bound+wake-240*f['VV'][i])))
        quadrature_error = float(np.max(abs(bound-bound_fine)))
        residual = VERIFY.control_residual(f)
        assert native_error < 1e-3
        assert quadrature_error < 1e-7
        assert residual < 1e-5
        vectors = dict(root=root,paired_roots=paired,exposed_roots=unpaired,finite_segments=finite,
                       residual_ray=tail,other_wake=other,bound=bound)
        original = read(original_directory/'report.json')
        rows.append(dict(case=case,native=report['native'],native_error_percent=report['native_error_percent'],
            original_native=original['native'],original_maximum_mach=original['native_force_points']['maximum_normal_mach'],
            maximum_mach=report['native_force_points']['maximum_normal_mach'],worst_index=i,
            receiver=f['RV'][i].tolist(),receiver_radius_m=float(np.linalg.norm(f['RV'][i,1:]-origins[0,1:])),
            sorted_origins_m=origins.tolist(),signed_strengths_m2_s=strengths.tolist(),cumulative_strengths_m2_s=cumulative.tolist(),
            main_total_circulation_m2_s=float(gamma[main].sum()),upper_total_circulation_m2_s=float(gamma[upper].sum()),
            total_circulation_jump_percent=float(100*(gamma[main].sum()-gamma[upper].sum())/gamma[main].sum()),
            exposed_circulation_m2_s=gamma[exposed].tolist(),paired_circulation_jumps_m2_s=(gamma[shared]-gamma[upper]).tolist(),
            velocities_m_s={k:v.tolist() for k,v in vectors.items()},velocity_norms_m_s={k:float(np.linalg.norm(v)) for k,v in vectors.items()},
            root_identity_error_m_s=identity_error,native_field_error_m_s=native_error,quadrature_error_m_s=quadrature_error,
            normal_control_residual_over_freestream=residual,seconds=report['seconds']))
    changes = {key:100*(rows[1]['native'][key]/rows[0]['native'][key]-1) for key in ('CL','CDi','CD_near')}
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,span_refinement_change_percent=changes,
        source_pins=pins,new_native_calls=2,production_calls=0,production_changed=False,comparison_fraction_or_scope_changed=False,
        native_seconds=sum(r['seconds'] for r in rows),
        caveat='Native force-point velocity diagnostics use the ASW beam-normal projection but not its receiver locations. Linear finite-chord controls have no ASWING profile/stall/section-moment laws. Shared origins remove geometric misalignment for the overlapping chord, but do not impose equal circulation; exposed root portions remain physical boundaries. No new ISAE passes.')
    write(BASE/'analysis.json',result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = re.findall(r"'(#\w+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig,axes=plt.subplots(1,2,figsize=(11,4.6))
    for color,key,label in zip(colors,('original_maximum_mach','maximum_mach'),('Independent chord grids','Aligned shared-root grid')):
        axes[0].plot([64,128],[r[key] for r in rows],'o-',color=color,label=label)
    axes[0].axhline(1,color='#555555',linestyle=':');axes[0].set_yscale('log')
    axes[0].set_xticks([64,128]);axes[0].set_xlabel('Total span positions (physical beams)')
    axes[0].set_ylabel('Peak normal Mach at native force points');axes[0].legend(fontsize=8)
    original=next(r for r in original_audit['cases'] if r['case']['id']=='c4-s128')
    for color,r,label in zip(colors,(original,rows[1]),('Independent chord grids','Aligned shared-root grid')):
        x=np.array(r['sorted_origins_m'])[:,0];y=r['cumulative_strengths_m2_s']
        axes[1].step(np.r_[x,1.16],np.r_[y,y[-1]],where='post',color=color,label=label)
    axes[1].axhline(0,color='#555555',linewidth=.7);axes[1].set_xlabel('Root body x (m)')
    axes[1].set_ylabel('Signed cumulative root circulation (m²/s)');axes[1].set_title('Finer span grid',fontsize=10)
    for ax in axes:ax.grid(alpha=.25)
    fig.suptitle('SA-11 native AVL: root alignment helps but does not resolve local refinement',fontsize=11)
    fig.text(.5,.02,'α = 1°, PG = 240/340.21, report-derived −4° twist. No new OpenSwing validation passes.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.07,1,.93))
    fig.savefig(BASE/'aligned-root.png',dpi=160);fig.savefig(BASE/'aligned-root.svg');plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_pins','cases')}))
    for r in rows: print(json.dumps({k:r[k] for k in ('case','total_circulation_jump_percent','velocity_norms_m_s','native_field_error_m_s','normal_control_residual_over_freestream')}))


if __name__=='__main__':main()
