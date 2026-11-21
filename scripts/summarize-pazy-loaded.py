"""Audit corrected Pazy inputs, static curves, modal refinement and runtimes."""
from pathlib import Path
import json
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='openswing-pazy-loaded-20261015'
import matplotlib.pyplot as plt
from pazy_loaded import ROOT,CACHE,sha

D=ROOT/'docs/validation'
LABELS=['OOP1','OOP2','T1','OOP3','IP1']


def read(path,digest=None):
    if digest is not None:assert sha(path)==digest,path
    return json.loads(Path(path).read_text())


def key(s):
    return (s['skin'],s.get('kind'),s['orientation'],s.get('mass_kg',0.),s.get('refinement',0))


def shape(row):
    return np.array(row['shape']['real'])+1j*np.array(row['shape']['imag'])


def mac(a,b):
    return float(abs(np.vdot(a,b))**2/(np.vdot(a,a).real*np.vdot(b,b).real))


def main():
    modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))};assert len(modules)==97
    audit=read(D/'pazy-loaded-source-audit.json')
    assert audit['status']=='PASS_PRIMARY_CONM2_CONVENTION_AND_GRAVITY_LOAD_AUDIT'
    assert audit['script_sha256']==sha(ROOT/'scripts/audit-pazy-loaded-sources.py')
    manifest=read(CACHE.parent/'manifest.json')
    for name,pin in manifest['files'].items():assert sha(CACHE/name)==pin['sha256'],name
    assert len(manifest['files'])==105
    for item in audit['models'].values():assert sha(ROOT/item['path'])==item['sha256']
    assert all(r['corrected_max_rounding_units']<=1 and r['historical_max_rounding_units']>7000 for r in audit['records'])
    reports={};runs={};rows={}
    for name,count in [('zero',10),('modes',16),('static',225)]:
        report=read(D/f'pazy-loaded-{name}.json');reports[name]=report
        assert report['status']=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED'
        assert report['modules']==modules and report['requested']==len(report['runs'])==count
        for file,digest in report['scripts'].items():assert sha(ROOT/'scripts'/file)==digest,file
        runs[name]={};rows[name]={}
        for row in report['runs']:
            run=read(ROOT/row['cache'],row['sha256']);s=row['specification']
            assert row['status']==run['status']=='computed' and run['specification']==s
            assert run['identity']['modules']==modules and run['identity']['scripts']==report['scripts']
            assert run['identity']['source_sha256']==__import__('hashlib').sha256(run['source'].encode()).hexdigest()
            base=run['result'] if name=='static' else run['base'];assert base['residual']<1e-8
            if name=='static':
                assert max(abs(np.array(base['force_balance'])))<1e-7
                assert max(abs(np.array(base['moment_balance'])))<1e-7
            else:
                assert sha(ROOT/run['matrices']['path'])==run['matrices']['sha256']
                assert len(run['modes'])==8 and run['diagnostics']['finite_dimension']==(120 if s['refinement']==1 else 180)
                assert max(max(m['right_backward_error'],m['left_backward_error']) for m in run['modes'])<1e-9
            runs[name][key(s)]=run;rows[name][key(s)]=row
    runtime={}
    for name,path in [('wasm','scripts/test-pazy-loaded-wasm.mjs'),('browser','tests/browser/pazy-loaded.spec.js')]:
        r=read(D/f'pazy-loaded-{name}.json');runtime[name]=r
        assert r['status']=='PASS_EXPECTED_OUTCOMES' and r['modules']==modules
        assert len(r['statics'])==4 and len(r['modes'])==6
        assert r['test_sha256']==sha(ROOT/path)
        assert r['selector_sha256']==sha(ROOT/'scripts/pazy-loaded-runtime-cases.mjs')
        assert r['native_report_sha256']=={f'pazy-loaded-{n}.json':sha(D/f'pazy-loaded-{n}.json') for n in reports}
    assert runtime['browser']['offline'] and runtime['browser']['served_build']
    runtime_audit={}
    for name,r in runtime.items():
        static_error=max(e for row in r['statics'] for e in row['differences'].values())
        frequency_error=max(m['frequency_difference_Hz'] for row in r['modes'] for m in row['matches'])
        min_shape=min(m['shape_assurance'] for row in r['modes'] for m in row['matches'])
        assert static_error<2e-8 and frequency_error<2e-6 and min_shape>1-2e-8
        runtime_audit[name]=dict(max_static_field_difference=static_error,max_frequency_difference_Hz=frequency_error,
            minimum_shape_assurance=min_shape,elapsed_seconds=[dict(specification=row['specification'],seconds=row['seconds']) for row in r['statics']+r['modes']],
            timing_scope='Observed solve times in this environment during accuracy replay; not a controlled speed benchmark. Some browser and WASM checks ran concurrently.')
    matrix_error=max(e for row in runtime['wasm']['modes'] for e in row['matrix_errors'].values());assert matrix_error<2e-8
    runtime_audit['wasm']['max_scaled_matrix_difference']=matrix_error
    for row in runtime['browser']['statics']+runtime['browser']['modes']:assert row['result']['software_provenance']['modules']==modules
    source=read(D/'isae-st2-source-audit.json');frequencies=[];covariance=[];profiles=[]
    for skin in [0,1]:
        exact=audit['records'][skin]['zero_gravity_reference']
        archived={}
        for name,folder in [('zero','01_Modal_Undeformed/06_Beam_Final'),('modes','02_Modal_Gravity/02_Beam')]:
            path=CACHE/f'03_2023_JA_Riso_Cesnik/{folder}/frequencies_skin{skin}.txt'
            archived[name]=np.loadtxt(path);assert len(archived[name])==5
        for name in ['zero','modes']:
            for k,row in rows[name].items():
                if k[0]!=skin:continue
                s=row['specification'];measurements=source['measured_modal_Hz'].get(f'skin{skin}_upright' if s['orientation']=='upright' else f'skin{skin}_horizontal_strain_PSD',{})
                for i,label in enumerate(LABELS):
                    match=next(m for m in row['matches'] if m['label']==label);f=match['frequency_Hz']
                    observed=measurements.get(label) if name=='modes' else None
                    reference=exact['projected']['modes'][i]['frequency_Hz'] if name=='zero' else None
                    archive=float(archived[name][i]) if s['orientation']=='horizontal' else None
                    frequencies.append(dict(**s,label=label,frequency_Hz=f,zero_gravity_shape_assurance=match['zero_gravity_shape_assurance'],
                        exact_projected_Hz=reference,exact_full_Hz=exact['full']['modes'][i]['frequency_Hz'] if name=='zero' else None,
                        relative_exact_error=None if reference is None else f/reference-1,
                        archived_um_Hz=archive,relative_archive_difference=None if archive is None else f/archive-1,
                        experimental_Hz=observed,relative_experimental_error=None if observed is None else f/observed-1))
        for label in LABELS:
            selected=sorted([r for r in frequencies if r['skin']==skin and r['gravity']==0 and r['orientation']=='horizontal' and r['label']==label],key=lambda r:r['refinement'])
            errors=[abs(r['relative_exact_error']) for r in selected]
            assert len(errors)==4 and all(b<a for a,b in zip(errors,errors[1:])),(skin,label,errors)
        a=runs['zero'][(skin,None,'horizontal',0.,4)];b=runs['zero'][(skin,None,'upright',0.,4)]
        rotation=np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
        for x,y in zip(a['modes'],b['modes']):
            q=shape(x);q[:,:3]=q[:,:3]@rotation.T;q[:,3:]=q[:,3:]@rotation.T
            error=abs(x['frequency_Hz']-y['frequency_Hz']);score=mac(q,shape(y));assert error<2e-6 and score>1-2e-8
            covariance.append(dict(skin=skin,frequency_Hz=x['frequency_Hz'],difference_Hz=error,shape_assurance=score))
    # Published profiles contain only the dominant component, not a complete
    # experimentally measured six-component eigenvector.
    for refinement in [1,2,4,8]:
        k=(0,None,'horizontal',0.,refinement);run=runs['zero'][k]
        for i,(label,component) in enumerate(zip(LABELS,[2,2,4,2,0]),1):
            match=next(r for r in rows['zero'][k]['matches'] if r['label']==label)
            q=shape(run['modes'][match['native_index']])[:,component];y=np.array(run['jig'])[:,1]
            for suffix in ['','_GFEM']:
                p=CACHE/f'03_2023_JA_Riso_Cesnik/01_Modal_Undeformed/06_Beam_Final/mode{i}_skin0{suffix}.txt';v=np.loadtxt(p)
                predicted=np.interp(v[:,0],y,q.real)+1j*np.interp(v[:,0],y,q.imag)
                profiles.append(dict(label=label,refinement=refinement,reference='GFEM' if suffix else 'UM/NAST',
                    path=p.relative_to(CACHE).as_posix(),sha256=sha(p),main_component_assurance=mac(predicted,v[:,1])))
    def response(skin,kind,mass,refinement):
        now=runs['static'][(skin,kind,'horizontal',mass,refinement)]['observables']
        base=runs['static'][(skin,kind,'horizontal',0.,refinement)]['observables']
        displacement=(np.array(now['midchord_position_m'])-base['midchord_position_m'])*100/.55
        return dict(x=displacement[0],y=displacement[1],z=displacement[2],twist=now['twist_xz_deg']-base['twist_xz_deg'])
    datasets=[];dataset_metadata_corrections=[]
    for raw in reports['static']['datasets']:
        assert sha(CACHE/raw['path'])==raw['sha256'];values=np.loadtxt(CACHE/raw['path'])
        assert np.array_equal(values,np.array(raw['values']))
        # Interpret the published column names independently of the run index.
        # Its historical `_rot_` test missed UM filenames ending `_rot.txt`.
        # UM curves never select native load cases; quantity labels never enter
        # configuration(), equilibrium, or the modal calculation.
        tokens=Path(raw['path']).stem.split('_')
        assert ('rot' in tokens)!=('disp' in tokens),raw['path']
        quantity='twist' if 'rot' in tokens else 'displacement'
        d=dict(raw,quantity=quantity)
        if raw['quantity']!=quantity:
            assert raw['reference']=='UM/NAST' and values.shape[1]==2
            dataset_metadata_corrections.append(dict(path=raw['path'],raw_index_quantity=raw['quantity'],correct_quantity=quantity,
                reason='Published filename ends in _rot.txt. These columns are mass and twist; this reporting-only normalization does not change native input selection or numerical solves.'))
        assert values.shape[1]==2 if quantity=='twist' else 2<=values.shape[1]<=4
        components=['twist'] if d['quantity']=='twist' else ['z','y','x'][:values.shape[1]-1]
        selected=sorted({k[3] for k in runs['static'] if k[0]==d['skin'] and k[1]==d['kind']})
        comparisons=[]
        for n in [1,2,4]:
            # Match actual published load rows; no interpolated reference data.
            for mass in selected:
                ids=np.flatnonzero(abs(values[:,0]-mass)<1e-10)
                if not len(ids):continue
                assert len(ids)==1;observed=values[ids[0],1:];predicted=response(d['skin'],d['kind'],mass,n)
                for c,reference in zip(components,observed):
                    comparisons.append(dict(refinement=n,mass_kg=mass,component=c,reference=float(reference),prediction=float(predicted[c]),difference=float(predicted[c]-reference)))
        if d['reference']=='experiment':assert len(comparisons)==3*len(values)
        statistics=[]
        for n in [1,2,4]:
            for c in components:
                errors=np.array([r['difference'] for r in comparisons if r['refinement']==n and r['component']==c]);assert len(errors)
                statistics.append(dict(refinement=n,component=c,samples=len(errors),rmse=float(np.sqrt(np.mean(errors**2))),max_abs=float(max(abs(errors))),units='degree' if c=='twist' else 'percent nominal semispan'))
        datasets.append(dict(**d,components=components,comparisons=comparisons,statistics=statistics))
    assert sum(len(d['values']) for d in datasets if d['reference']=='experiment')==77
    assert len(dataset_metadata_corrections)==2
    mesh=[]
    for skin,kind,orientation,mass,n in runs['static']:
        if n!=1:continue
        v=[response(skin,kind,mass,j) for j in [1,2,4]]
        mesh.append(dict(skin=skin,kind=kind,mass_kg=mass,
            difference_15_to_30={c:float(v[1][c]-v[0][c]) for c in v[0]},difference_30_to_60={c:float(v[2][c]-v[1][c]) for c in v[0]}))
    independent=read(D/'pazy-loaded-reference.json');assert independent['status']=='PASS_INDEPENDENT_STATIC_REFERENCES'
    assert len(independent['runs'])==28
    for name,digest in independent['scripts'].items():assert sha(ROOT/'scripts'/name)==digest
    reference={};rod=[];projection=[]
    for row in independent['runs']:
        run=read(ROOT/row['cache'],row['sha256']);s=row['specification']
        assert run['identity']['scripts']==independent['scripts']
        assert run['tip_boundary_error_Nm']<2e-8 and run['quaternion_norm_error']<2e-9
        reference[(s['skin'],s['kind'],s['orientation'],s['mass_kg'],row['projected'])]=run
        if not row['projected']:continue
        for n in [1,2,4] if s['orientation']=='horizontal' else [1,2,4,8]:
            if s['orientation']=='horizontal':native=runs['static'][(s['skin'],s['kind'],'horizontal',s['mass_kg'],n)]['result']
            else:native=runs['modes'][(s['skin'],None,'upright',0.,n)]['base']
            nodes=native['nodes'];stations=np.array([p['t']-1 for p in nodes]);ref=np.array(run['stations_m'])
            ids=np.argmin(abs(stations[:,None]-ref),axis=1);assert max(abs(stations-ref[ids]))<1e-12
            pe=float(np.max(abs(np.array([p['position'] for p in nodes])-np.array(run['positions'])[ids])))
            qe=float(np.max(abs(np.array([p['rotation'] for p in nodes])-np.array(run['rotations'])[ids])))
            rod.append(dict(**s,refinement=n,max_position_error_m=pe,max_rotation_entry_error=qe))
    for k,full in reference.items():
        if k[-1]:continue
        projected=reference[(*k[:-1],True)]
        projection.append(dict(**full['specification'],max_position_difference_m=float(np.max(abs(np.array(full['positions'])-projected['positions']))),
            max_rotation_entry_difference=float(np.max(abs(np.array(full['rotations'])-projected['rotations'])))))
    for k in {tuple(r[x] for x in ['skin','kind','orientation','mass_kg']) for r in rod if r['orientation']=='horizontal'}:
        selected=sorted([r for r in rod if tuple(r[x] for x in ['skin','kind','orientation','mass_kg'])==k],key=lambda r:r['refinement'])
        assert all(b['max_position_error_m']<a['max_position_error_m']/3 for a,b in zip(selected,selected[1:])),(k,selected)
    historical_path=ROOT/'.reference/pazy-loaded-historical/pazy-loaded-static.json'
    historical=read(historical_path);assert len(historical['runs'])==225
    static_correction=[]
    for row in historical['runs']:
        old=read(ROOT/row['cache'],row['sha256']);new=runs['static'][key(row['specification'])]
        error=max(float(np.max(abs(np.array(a[field])-b[field]))) for a,b in zip(old['result']['nodes'],new['result']['nodes']) for field in ['position','rotation'])
        assert error<1e-12
        static_correction.append(error)
    palette_path=ROOT/'web/plot-colors.js';palette=re.findall(r'#[0-9a-fA-F]{6}',palette_path.read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0]);assert len(palette)==8
    figures={}
    fig,axes=plt.subplots(3,2,figsize=(11,10),layout='constrained')
    for skin in [0,1]:
        for i,(kind,quantity,component) in enumerate([('bending','displacement','z'),('torsion','displacement','z'),('torsion','twist','twist')]):
            ax=axes[i,skin]
            for reference,color in zip(['experiment','UM/NAST','GFEM'],palette[:3]):
                for d in datasets:
                    if (d['skin'],d['kind'],d['quantity'],d['reference'],d['linear'])!=(skin,kind,quantity,reference,False):continue
                    v=np.array(d['values']);ax.plot(v[:,0],v[:,1],'o' if reference=='experiment' else '--',color=color,label=reference,markersize=4)
            masses=sorted({k[3] for k in runs['static'] if k[0]==skin and k[1]==kind})
            for n,color in zip([1,2,4],palette[3:6]):ax.plot(masses,[response(skin,kind,m,n)[component] for m in masses],color=color,label=f'OpenSwing {15*n}')
            ax.set_title(f"Skin {'on' if skin else 'off'}: {kind}");ax.set_xlabel('Added bench mass (kg)');ax.set_ylabel('Twist change (deg)' if component=='twist' else 'Vertical displacement change (% 0.55 m)');ax.grid(alpha=.2);ax.legend(fontsize=7)
    fig.suptitle('Primary Pazy properties: static comparisons\nAll sweep values subtract their own zero-payload gravity state')
    for ext in ['png','svg']:
        p=D/f'pazy-loaded-static-comparison.{ext}';fig.savefig(p,dpi=180,metadata={'Date':None} if ext=='svg' else {});figures[p.name]=sha(p)
    plt.close(fig)
    report_names=[f'pazy-loaded-{name}.json' for name in ['source-audit','zero','modes','static','reference','wasm','browser']]+['isae-st2-source-audit.json']
    metrics=dict(max_coarse_zero_vs_um_relative=max(abs(r['relative_archive_difference']) for r in frequencies if r['gravity']==0 and r['refinement']==1),
        max_coarse_loaded_vs_um_relative=max(abs(r['relative_archive_difference']) for r in frequencies if r['gravity'] and r['refinement']==1 and r['orientation']=='horizontal'),
        max_fine_zero_vs_exact_relative=max(abs(r['relative_exact_error']) for r in frequencies if r['gravity']==0 and r['refinement']==8),
        max_N60_static_rod_position_error_m=max(r['max_position_error_m'] for r in rod if r['refinement']==4 and r['orientation']=='horizontal'),
        max_constitutive_projection_position_difference_m=max(r['max_position_difference_m'] for r in projection),
        max_static_inertia_correction_difference=max(static_correction))
    out=dict(status='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED',modules=modules,script_sha256=sha(__file__),
        report_sha256={n:sha(D/n) for n in report_names},historical_static=dict(path=historical_path.relative_to(ROOT).as_posix(),sha256=sha(historical_path)),
        counts=dict(zero_gravity_modal_states=10,gravity_loaded_modal_states=16,static_states=225,independent_static_references=28,measured_static_rows=77,wasm_states=10,offline_browser_states=10),
        correction=audit['convention_correction'],models=audit['models'],frequency_comparisons=frequencies,archived_shape_comparisons=profiles,
        frame_covariance=covariance,runtime_audit=runtime_audit,static_datasets=datasets,dataset_metadata_corrections=dataset_metadata_corrections,
        static_mesh_changes=mesh,independent_static_comparisons=rod,
        constitutive_projection_comparisons=projection,metrics=metrics,figures=figures,
        plot_palette=dict(path='web/plot-colors.js',sha256=sha(palette_path),colors=palette),
        full_family_validated=False,full_suite_validated=False,
        limitations=audit['limitations']+[
            'Gravity 9.807 m/s² is explicit in the published GFEM input. The archived UM/NAST output does not provide its gravity setting; numerical differences are not interpreted as a matched-setting accuracy tolerance.',
            'Zero-gravity exact references verify the beam discretization. Gravity-loaded modal frequencies are compared with published numerical/experimental values; there is no independent full loaded-modal reference.',
            'Published UM/NAST static curves use a denser load grid. Comparisons use exact matched loads from the native sweep; unmatched reference samples are plotted but not presented as native solves.',
            'Nominal 0.1 m chord, paper axis fraction 0.441 and tip load offsets are explicit. Exact experimental fixture coordinates and original UM/NAST static input are not published here.',
            'The nominal x-z chord-projection twist and gravity-baseline convention are explicit. Experimental uncertainty and model calibration dependence remain unresolved.',
            'The published model development used static/GVT measurements. These comparisons are not an independent calibration holdout; no additional material or frequency fit was made in this study.',
            'Skin-on upright in-plane frequency remains far above measured 60.7 Hz. The primary paper suggests clamp compliance; this is an unverified explanation, not a fitted correction.',
            'Ten runtime cases sample 4 static and 6 modal conditions; they do not replay all 251 native states or the 120-interval states.',
            'All 6 literal ISAE Pazy inputs retain unresolved out-of-domain attachments. Corrected generated inputs do not constitute literal-file compatibility.',
            'No flutter, unsteady aerodynamics, time-response or full ASWING parity claim. Family coverage remains 16 partial / 25 pending; all 40 broad requirements remain Partial.'])
    path=D/'pazy-loaded-comparison.json';path.write_text(json.dumps(out,indent=2)+'\n')
    lines=['# Pazy primary-model correction and loaded comparisons','',
        '**Numerical comparisons completed; experimental validation remains incomplete.** This study supersedes the previous primary-model inertia conversion. All 97 production solver modules are unchanged.','',
        '## Corrected input convention','',
        'The primary spreadsheet off-diagonals are signed CONM2 products, requiring their negatives in the physical inertia tensor. My earlier derived inputs interpreted them as tensor entries. The corrected reconstruction reproduces every entry of both original Nastran 6×6 rigid-body mass matrices to printed precision; the old interpretation differs by over 7,000 rounding units. Mass, CG and positive-definite tensors are checked independently of modal frequency agreement. [Source audit](pazy-loaded-source-audit.json).','',
        'Use the four `pazy-primary-conm2-*.asw` inputs below. The old `pazy-primary-skin*.asw` models and their archived study are retained as superseded evidence. Original source point masses already include their CONM2 calibration masses; no duplicate calibration mass was added.','',
        'The source is [Riso and Cesnik’s pinned primary data](https://github.com/UM-A2SRL/AePW3-LDWG/tree/396710a19a80004c65c767e9955fe60d59565c39/00_Models/01_Pazy_Technion/02_Models_Beam). The small intrinsic extension–torsion K12 term remains explicitly projected because documented ASWING section fields cannot represent it. Full and projected independent beam references quantify this limitation. [Model and test definitions](https://doi.org/10.2514/1.C036869).','',
        '## Modal results','',
        '| Skin | Mode | UM zero gravity, 15 intervals (Hz) | OpenSwing zero gravity, 15 (Hz) | UM with gravity, 15 (Hz) | OpenSwing with gravity, 15 (Hz) | OpenSwing with gravity, 120 (Hz) |','|---|---|---:|---:|---:|---:|---:|']
    for skin in [0,1]:
        for label in LABELS:
            matching=[r for r in frequencies if r['skin']==skin and r['label']==label and r['orientation']=='horizontal']
            z=next(r for r in matching if r['gravity']==0 and r['refinement']==1)
            g=next(r for r in matching if r['gravity'] and r['refinement']==1)
            f=next(r for r in matching if r['gravity'] and r['refinement']==8)
            lines.append(f"| {'on' if skin else 'off'} | {label} | {z['archived_um_Hz']:.6f} | {z['frequency_Hz']:.6f} | {g['archived_um_Hz']:.6f} | {g['frequency_Hz']:.6f} | {f['frequency_Hz']:.6f} |")
    upright=next(r for r in frequencies if r['skin']==1 and r['gravity'] and r['orientation']=='upright' and r['refinement']==8 and r['label']=='IP1')
    lines+=['',f"The largest first-five-mode difference from published coarse UM/NAST is {100*metrics['max_coarse_zero_vs_um_relative']:.7f}% without gravity and {100*metrics['max_coarse_loaded_vs_um_relative']:.5f}% with gravity. Every checked zero-gravity branch converges monotonically over 15/30/60/120 intervals toward the independent exact projected beam; the maximum 120-interval error is {100*metrics['max_fine_zero_vs_exact_relative']:.5f}%.",'',
        f"The skin-on upright in-plane mode remains {upright['frequency_Hz']:.3f} Hz versus measured 60.7 Hz ({100*upright['relative_experimental_error']:.1f}% high). Other measured modal comparisons, all 40 archived main-component profile correlations, eight-mode frame covariance, full A/M matrices and eigenpair errors are retained in the JSON. These comparisons do not establish an experimental pass. [Primary GVT tables 3–5](https://doi.org/10.2514/1.J060621).",'',
        '## Static measurements and independent nonlinear reference','',
        'All 77 measured static rows are compared at 15/30/60 intervals, together with exact matching samples of the primary nonlinear UM/NAST and GFEM curves. The 225 native conditions cover 75 unique skin/load/mass combinations. Linear GFEM curves are retained separately as controls. Gravity is 9.807 m/s², from the primary GRAV input. Every displacement component and twist subtracts its own zero-payload gravity baseline.','',
        '| Skin | Load | Observable | Measured rows | N60 RMSE | N60 maximum absolute error | Unit |','|---|---|---|---:|---:|---:|---|']
    for d in datasets:
        if d['reference']!='experiment':continue
        s=next(s for s in d['statistics'] if s['refinement']==4)
        lines.append(f"| {'on' if d['skin'] else 'off'} | {d['kind']} | {s['component']} | {s['samples']} | {s['rmse']:.4f} | {s['max_abs']:.4f} | {s['units']} |")
    lines+=['','![Static comparison curves](pazy-loaded-static-comparison.png)','',
        'The independent reference shoots a geometrically nonlinear massless rod with the complete source 4×4 constitutive matrix, nodal gravity forces, CG moment jumps and bench load. It imports no OpenSwing solver code. Full and projected references cover 28 conditions, including unloaded gravity, 2 kg and maximum tested loads, plus upright gravity. Native positions and rotations are compared along the whole beam, not just at the tip.','',
        f"All horizontal position errors decrease by more than a factor of 3 for each mesh doubling. At 60 intervals the largest profile-position error against the projected reference is {1e3*metrics['max_N60_static_rod_position_error_m']:.6f} mm. The largest full-versus-projected reference position change is {1e3*metrics['max_constitutive_projection_position_difference_m']:.6f} mm. All 225 static states have numerically identical positions and rotation matrices before and after the inertia-sign correction.",'',
        'The raw native run index mislabels the two UM/NAST files ending `_rot.txt` as displacement. This comparison identifies their mass/twist columns directly from the published filenames and verifies the complete file contents. The correction is recorded in `dataset_metadata_corrections`; it affects only reference reporting. UM/NAST curves do not select native load cases, and the quantity labels do not enter the equations.','',
        '## Runtime checks and inputs','',
        'Ten actual WebAssembly and ten offline served-browser cases pass: four maximum-load 60-interval statics, two 15-interval zero-gravity modal cases, and four 60-interval gravity-loaded modal cases. Checks cover full static fields, reactions, modal A/M matrices in WASM, frequencies, complex mode shapes, input equality and all 97 module hashes. Desktop/mobile screenshots and per-case elapsed times are retained. [WASM](pazy-loaded-wasm.json), [browser](pazy-loaded-browser.json).','']
    lines+=['- ['+Path(m['path']).name+'](../../'+m['path']+')' for m in audit['models'].values()]
    lines+=['','Import the matching `pazy-primary-mesh-15/30/60/120.json` through the mesh-file control. For modal runs, select vacuum modes, fixed frame and custom gravity magnitude 0 or 9.807 as specified in each report. For static runs, select structural analysis and its separate custom gravity vector `[0, 0, -9.807]`. Static payload inputs are preserved exactly in each native cache and browser export.','',
        '## Remaining limitations','']+['- '+s for s in out['limitations']]
    lines+=['','[Machine-readable comparison](pazy-loaded-comparison.json), [coverage ledger](isae-coverage.md), [historical primary study](pazy-primary-comparison.md).','']
    (D/'pazy-loaded-comparison.md').write_text('\n'.join(lines))
    (D/'pazy-loaded-checks.json').write_text(json.dumps(dict(status='PASS_CORRECTED_PAZY_NUMERICAL_CHECKS_NOT_PHYSICAL_VALIDATION',modules=modules,
        script_sha256=sha(__file__),snapshot_sha256=sha(path),counts=out['counts'],full_family_validated=False),indent=2)+'\n')
    print(json.dumps(dict(status=out['status'],counts=out['counts'],metrics=metrics),indent=2))


if __name__=='__main__':main()
