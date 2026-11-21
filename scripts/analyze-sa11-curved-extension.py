"""Verify saved curved-extension comparisons without running a solver."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-curved-extension-r2-20261108'
spec=importlib.util.spec_from_file_location('curved',ROOT/'scripts/verify-sa11-curved-extension.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)


def arrays(path):
    with np.load(path) as data: return {k:data[k].copy() for k in data.files}


def main():
    plan=driver.read(OUT/'plan.json');driver.check(plan)
    assert driver.sha(OUT/'driver-used.py')==plan['pins']['scripts/verify-sa11-curved-extension.py']
    rows=[];artifact_pins={}
    for case in plan['cases']:
        p=OUT/case['id'];r=driver.read(p/'report.json')
        assert r['case']==case and r['primary_passes_added']==0
        assert driver.read(p/'process.json')['returncode']==0
        for name,digest in r['artifact_sha256'].items(): assert driver.sha(p/name)==digest,(case['id'],name)
        if r['native_reused_from']:
            reuse=driver.read(p/'native-reuse.json');source=ROOT/reuse['source']
            assert source==ROOT/r['native_reused_from']
            for name,digest in reuse['file_sha256'].items():
                assert driver.sha(source/name)==driver.sha(p/name)==digest
            for name in ('model.avl','commands.txt'): assert (source/name).read_bytes()==(p/name).read_bytes()
        model,choice=driver.model_for(case)
        assert choice==driver.read(p/'input-choice.json')
        meshes=driver.model_meshes(model,case['requested_count'])
        condition=driver.read(p/'production/condition.json')
        assert condition['stall'] and condition['freeze_influences'] and condition['speed']==case['speed']
        mach=case['speed']/model.constants[2] if case['setup']=='literal70' else 0.
        assert condition['mach']==mach
        text,expected,conversion=driver.export(model,meshes,mach)
        assert text==(p/'model.avl').read_text() and conversion==r['conversion']
        fields=arrays(p/'native-fields.npz');geometry=arrays(p/'production-geometry.npz')
        recomputed=driver.lifting_geometry(meshes,np.array([1.,0.,0.]))
        for key in recomputed: assert np.array_equal(recomputed[key],geometry[key]),key
        state=arrays(p/'production/state.npz');gamma=state['gamma'];v=state['velocity']
        normal=v-np.sum(v*geometry['tangent'],axis=1)[:,None]*geometry['tangent']
        max_mach=float(np.max(np.linalg.norm(normal,axis=1))/model.constants[2])
        assert abs(max_mach-r['production']['maximum']['normal_mach'])<1e-12
        assert r['production']['residual']<1e-8
        assert r['production']['stalled_strips']==0 and np.all(state['stall_margin']>0)
        assert abs(float(state['stall_margin'].min()/.05)-r['production']['minimum_stall_margin_widths'])<1e-12
        if r['production']['status']=='computed':
            result=driver.read(p/'production/openswing.json')
            values={k:result[k] for k in ('CL','CD','CDi','efficiency')};values['Cm']=result['Cm_origin']
            assert r['values']==values and max_mach<1
            drag={k:result[k] for k in ('CDp','CDi_near','CDi','CD')}
            assert abs(drag['CDp']+drag['CDi_near']-drag['CD'])<1e-12
        else:
            assert r['production']['status']=='rejected' and max_mach>=1
            assert r['values'] is None and not (p/'production/openswing.json').exists()
            drag=None
        assert np.max(abs(fields['RV'][:,1]-expected['t']))<2e-14
        # All retained extension records use t=y. Evaluate section normals at
        # native receivers, not at the different production sample stations.
        tangent=driver.surface_frame(model.beams[0],fields['RV'][:,1])[...,1]
        native_v=(fields['VINF']+fields['VV'])*case['speed']
        native_normal=native_v-np.sum(native_v*tangent,axis=1)[:,None]*tangent
        native_mach=float(np.max(np.linalg.norm(native_normal,axis=1))/model.constants[2])
        label='0_70' if case['setup']=='literal70' else '0_75'
        raw=np.loadtxt(driver.SOURCE/f'wing_extension_Ma_{label}.txt')
        raw=raw[raw[:,71]==case['alpha']];assert raw.shape==(1,82)
        ref={k:float(raw[0,col]) for k,col in [('CL',77),('CD',78),('CDi',79),('Cm',80),('efficiency',81)]}
        assert ref==r['reference']
        assert r['native_error_percent']=={k:100*(r['native'][k]/ref[k]-1) for k in ('CL','CDi','efficiency')}
        assert r['production_error_percent']==(None if r['values'] is None else {k:100*(v/ref[k]-1) for k,v in r['values'].items()})
        assert r['native_gamma_reconstruction_relative_error']<1e-6
        assert r['native_velocity_reconstruction_scaled_error']<1e-6
        assert r['native_force_reconstruction_error']<2e-10
        assert r['production_velocity_reconstruction_error']<1e-6
        # Supplement the scalar diagnostics with an independent extended-
        # precision replay of the native core and zero-core formulas.
        ng=fields['GAM'].ravel();k=4*np.pi*.079577472
        core=driver.native_core_matrix(fields['RV'],fields['RV1'],fields['RV2'],mach,exclude_self=True,dtype=np.longdouble)
        zero=driver.native_core_matrix(fields['RV'],fields['RV1'],fields['RV2'],mach,exclude_self=True,dtype=np.longdouble,core_fraction=0.)
        cv=np.sum(core*ng[None,:,None],axis=1)
        zv=np.sum(zero*ng[None,:,None],axis=1)
        pg=np.diag([1/np.sqrt(1-mach*mach),1.,1.])
        stable=driver.FactoredInfluence(fields['RV'],fields['RV1'],fields['RV2'],[1.,0.,0.],pg,exclude_bound=np.eye(len(ng),dtype=bool))
        stable_v=k*stable.apply(ng)
        extended_error=float(np.max(abs(cv-fields['VV'])))
        zero_error=float(np.max(abs(zv-stable_v)))
        assert extended_error<1e-7 and zero_error<1e-7,(case['id'],extended_error,zero_error)
        ar=model.reference[0,2]**2/model.reference[0,0]
        row={k:r[k] for k in ('case','strips','conversion','shared_source_endpoint_error','native_production_receiver_distance',
            'native_gamma_reconstruction_relative_error','native_velocity_reconstruction_error','native_force_reconstruction_error',
            'production_velocity_reconstruction_error','native_zero_core_gamma_relative_difference','native_zero_core_velocity_difference',
            'discrete_gamma_relative_difference','native','values','reference','native_error_percent','production_error_percent')}
        row.update(status=r['production']['status'],production_maximum_mach=max_mach,native_maximum_mach=native_mach,
            native_mach_scope='Diagnostic velocity projected normal to the ASW beam at native receivers; not an AVL acceptance gate.',
            residual=r['production']['residual'],minimum_stall_margin_widths=r['production']['minimum_stall_margin_widths'],
            production_seconds=r['production']['seconds'],drag=drag,native_extended_precision_velocity_error=extended_error,
            zero_core_extended_precision_vs_stable_error=zero_error,
            native_efficiency_from_near_CL=r['native']['CL']**2/(np.pi*ar*r['native']['CDi']),
            archive_efficiency_from_near_CL=ref['CL']**2/(np.pi*ar*ref['CDi']),
            native_reused=bool(r['native_reused_from']))
        rows.append(row)
        for path in p.rglob('*'):
            if path.is_file():artifact_pins[str(path.relative_to(ROOT))]=driver.sha(path)
    assert len(rows)==6
    pairs=[]
    for i in (0,2,4):
        a,b=rows[i:i+2]
        assert a['case']['requested_count']==64 and b['case']['requested_count']==128
        assert a['case']['setup']==b['case']['setup'] and a['case']['alpha']==b['case']['alpha']
        pairs.append(dict(setup=a['case']['setup'],alpha=a['case']['alpha'],
            curve_error_ratio={k:b['conversion']['sampled_curve_error'][k]/a['conversion']['sampled_curve_error'][k]
                               for k in a['conversion']['sampled_curve_error']},
            native_refinement_percent={k:100*(b['native'][k]/a['native'][k]-1) for k in ('CL','CDi','CD_near')},
            production_refinement_percent=None if a['values'] is None or b['values'] is None else
                {k:100*(b['values'][k]/a['values'][k]-1) for k in a['values']}))
    driver.check(plan)
    summary=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,pairs=pairs,
        native_cases=6,new_native_calls_in_r2=5,reused_native_cases=1,production_calls=6,
        computed=sum(r['status']=='computed' for r in rows),rejected=sum(r['status']=='rejected' for r in rows),
        production_seconds=sum(r['production_seconds'] for r in rows),source_pins=plan['pins'],artifact_pins=artifact_pins,
        plan_sha256=driver.sha(OUT/'plan.json'),analyzer_sha256=driver.sha(Path(__file__)),
        production_equations_changed=False,original_inputs_changed=False,primary_fraction_or_scope_changed=False,
        primary_passed=163,primary_required=9184)
    driver.write(OUT/'analysis.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('cases','source_pins','artifact_pins')}),flush=True)
    for r in rows:
        print(json.dumps({k:r[k] for k in ('case','status','native_maximum_mach','production_maximum_mach','native_zero_core_velocity_difference','conversion')}),flush=True)
    plot(rows)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=re.findall(r"'(#\w+)'",(ROOT/'web/plot-colors.js').read_text().split('export const plotColors')[1].split(']);')[0])
    fig,axes=plt.subplots(1,3,figsize=(12,4.4))
    for i,label,color in zip((0,2,4),('Original .70, alpha 1°','Candidate .75, alpha 0°','Candidate .75, alpha 1°'),colors):
        pair=rows[i:i+2];x=[r['strips'] for r in pair]
        for ax,key in zip(axes[:2],('CL','CDi')):
            ax.plot(x,[r['native_error_percent'][key] for r in pair],'o-',color=color,label=label)
            y=[np.nan if r['production_error_percent'] is None else r['production_error_percent'][key] for r in pair]
            ax.plot(x,y,'s--',color=color)
            ax.set(ylabel=f'Archive {key} error (%)')
        axes[2].plot(x,[r['native_maximum_mach'] for r in pair],'o-',color=color)
        axes[2].plot(x,[r['production_maximum_mach'] for r in pair],'s--',color=color)
    for ax in axes[:2]:ax.axhline(0,color='#888',linewidth=.7)
    axes[2].axhline(1,color='#777',linewidth=1);axes[2].set(ylabel='Maximum section-normal Mach')
    for ax in axes:
        ax.set(xlabel='Actual span strips',xticks=[70,134]);ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('SA-11 curved extension: solid = native AVL; dashed = production OpenSwing\nSeparate receiver/core rules; rejected production loads omitted; no primary passes added',fontsize=11)
    fig.tight_layout();fig.savefig(OUT/'curved-extension.png',dpi=150);fig.savefig(OUT/'curved-extension.svg');plt.close(fig)


if __name__=='__main__':main()
