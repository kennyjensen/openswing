"""Audit primary Pazy conversion, native mesh convergence and runtime replays."""
from pathlib import Path
import json
import re
import numpy as np
from scipy.linalg import eigh
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt']='openswing-pazy-primary-20261015'
import matplotlib.pyplot as plt
from pazy_primary import ROOT,CACHE,source,sha
from pazy_primary_reference import matrices

D=ROOT/'docs/validation'
LABELS=['OOP1','OOP2','T1','OOP3','IP1']


def read(path,digest=None):
    if digest is not None:assert sha(path)==digest,path
    return json.loads(Path(path).read_text())


def shape(row):
    return np.array(row['shape']['real'])+1j*np.array(row['shape']['imag'])


def mac(a,b):
    a,b=np.asarray(a).ravel(),np.asarray(b).ravel()
    return float(abs(np.vdot(a,b))**2/(np.vdot(a,a).real*np.vdot(b,b).real))


def main():
    native=read(D/'pazy-primary-mapping.json');wasm=read(D/'pazy-primary-wasm.json');browser=read(D/'pazy-primary-browser.json')
    discrete=read(D/'pazy-primary-discrete.json')
    assert discrete['status']=='PASS_INDEPENDENT_COARSE_DISCRETIZATION'
    assert discrete['native_sha256']==sha(D/'pazy-primary-mapping.json')
    assert discrete['script_sha256']==sha(ROOT/'scripts/audit-pazy-primary-discrete.py')
    assert len(discrete['rows'])==2 and max(r['max_frequency_difference_Hz'] for r in discrete['rows'])<2e-6
    assert native['status']=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED'
    assert wasm['status']==browser['status']=='PASS_EXPECTED_OUTCOMES'
    modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert native['modules']==wasm['modules']==browser['modules']==modules
    assert len(modules)==97 and len(native['runs'])==10
    assert len(wasm['rows'])==len(browser['rows'])==6 and browser['offline'] and browser['served_build']
    for report,path in [(wasm,'scripts/test-pazy-primary-wasm.mjs'),(browser,'tests/browser/pazy-primary.spec.js')]:
        assert report['native_sha256']==sha(D/'pazy-primary-mapping.json')
        assert report['test_sha256']==sha(ROOT/path)
    for name,digest in native['scripts'].items():assert sha(ROOT/'scripts'/name)==digest
    for item in native['mapping']['models'].values():assert sha(ROOT/item['path'])==item['sha256']
    cache={};rows=[];shape_comparisons=[];numerical_references=[]
    for row in native['runs']:
        run=read(ROOT/row['cache'],row['sha256']);assert run['status']==row['status']=='computed'
        assert run['identity']['modules']==modules and run['identity']['scripts']==native['scripts']
        assert run['identity']['source_sha256']==__import__('hashlib').sha256(run['source'].encode()).hexdigest()
        assert sha(ROOT/run['matrices']['path'])==run['matrices']['sha256']
        assert run['base']['residual']<1e-8 and len(run['modes'])==8
        assert max(max(m['right_backward_error'],m['left_backward_error']) for m in run['modes'])<1e-9
        # The original midpoint mesh has 30 independent zero-shear
        # constraints on its 90 massive coordinates. An independent
        # constrained-energy calculation verifies all eight reported modes.
        assert run['diagnostics']['finite_dimension']==(120 if row['specification']['refinement']==1 else 180)
        cache[tuple(row['specification'][k] for k in ['skin','orientation','refinement'])]=run
        for match in row['comparisons']:
            rows.append(dict(**row['specification'],intervals=15*row['specification']['refinement'],**match))
    for skin in [0,1]:
        data=source(skin);record=native['mapping']['records'][skin]
        for path,pin in record['sources'].items():assert sha(CACHE/path)==pin['sha256']
        # Reciprocal generalized problem emphasizes the low modes and checks
        # cancellation from the very large axial stiffness in the direct solve.
        for projected,key in [(False,'full'),(True,'asw_projection')]:
            k,m=matrices(data,projected);k,m=k[6:,6:],m[6:,6:]
            mu,v=eigh(m,k,subset_by_index=[len(k)-8,len(k)-1]);f=1/np.sqrt(mu[::-1])/(2*np.pi)
            before=np.array([r['frequency_Hz'] for r in record['references'][key]['modes']])
            assert max(abs(f-before))<2e-6
            numerical_references.append(dict(skin=skin,projected=projected,reciprocal_frequencies_Hz=f.tolist(),
                direct_minus_reciprocal_Hz=(before-f).tolist(),max_difference_Hz=float(max(abs(f-before)))))
        for label in LABELS:
            selected=sorted([r for r in rows if r['skin']==skin and r['orientation']=='horizontal' and r['label']==label],key=lambda r:r['refinement'])
            errors=[abs(r['relative_difference']) for r in selected]
            assert len(errors)==4 and all(b<a for a,b in zip(errors[:-1],errors[1:])),(skin,label,errors)
        # Only skin-off main-component mode profiles are present upstream.
        if skin==0:
            for refinement in [1,2,4,8]:
                run=cache[(0,'horizontal',refinement)];positions=np.array(run['jig'])[:,1]
                for i,(label,component) in enumerate(zip(LABELS,[2,2,4,2,0]),1):
                    match=next(r for r in rows if r['skin']==0 and r['orientation']=='horizontal' and r['refinement']==refinement and r['label']==label)
                    q=shape(run['modes'][match['native_index']])[:,component]
                    for suffix in ['', '_GFEM']:
                        path=CACHE/f'03_2023_JA_Riso_Cesnik/01_Modal_Undeformed/06_Beam_Final/mode{i}_skin0{suffix}.txt'
                        samples=np.loadtxt(path)
                        assert samples.shape==(16,2) and np.all(np.diff(samples[:,0])>0)
                        assert samples[0,0]>=positions[0]-1e-12 and samples[-1,0]<=positions[-1]+1e-12
                        predicted=np.interp(samples[:,0],positions,q.real)+1j*np.interp(samples[:,0],positions,q.imag)
                        shape_comparisons.append(dict(skin=0,refinement=refinement,label=label,
                            reference='GFEM' if suffix else 'UM/NAST',path=path.relative_to(CACHE).as_posix(),sha256=sha(path),
                            main_component_assurance=mac(predicted,samples[:,1]),samples=len(samples),
                            note='One published component only; not a six-component experimental modal assurance.'))
    covariance=[];rotation=np.array([[1.,0,0],[0,0,-1.],[0,1.,0]])
    for skin in [0,1]:
        horizontal=cache[(skin,'horizontal',4)];upright=cache[(skin,'upright',4)];comparisons=[]
        for a,b in zip(horizontal['modes'],upright['modes']):
            q=shape(a);q[:,:3]=q[:,:3]@rotation.T;q[:,3:]=q[:,3:]@rotation.T
            df=abs(a['frequency_Hz']-b['frequency_Hz']);score=mac(q,shape(b));assert df<2e-6 and score>1-2e-8
            comparisons.append(dict(frequency_Hz=a['frequency_Hz'],frequency_difference_Hz=df,shape_assurance=score))
        covariance.append(dict(skin=skin,refinement=4,modes=comparisons))
    frequency_table=[]
    for skin in [0,1]:
        record=native['mapping']['records'][skin]
        for i,label in enumerate(LABELS):
            cases={r['refinement']:r for r in rows if r['skin']==skin and r['orientation']=='horizontal' and r['label']==label}
            archived=record['archived_um_frequencies_Hz'][label]
            frequency_table.append(dict(skin=skin,label=label,archived_um_Hz=archived,
                native_15_Hz=cases[1]['frequency_Hz'],native_120_Hz=cases[8]['frequency_Hz'],
                exact_full_Hz=record['references']['full']['modes'][i]['frequency_Hz'],
                exact_projected_Hz=cases[8]['reference_Hz'],
                coarse_vs_archive_relative=cases[1]['frequency_Hz']/archived-1,
                fine_vs_exact_projected_relative=cases[8]['relative_difference']))
    meshes={}
    for refinement in [1,2,4,8]:
        panels=cache[(0,'horizontal',refinement)]['panels']
        assert panels==cache[(1,'horizontal',refinement)]['panels']
        path=ROOT/'examples'/f'pazy-primary-mesh-{15*refinement}.json'
        path.write_text(json.dumps(dict(format='openswing-mesh',version=1,panels=panels),indent=2)+'\n')
        meshes[str(15*refinement)]=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))
    fig,axes=plt.subplots(1,2,figsize=(11,4.4),layout='constrained')
    palette_path=ROOT/'web/plot-colors.js'
    palette=re.findall(r"#[0-9a-fA-F]{6}",palette_path.read_text().split('export const plotColors = Object.freeze([')[1].split(']);')[0])
    assert len(palette)==8
    for skin,ax in enumerate(axes):
        for label,color in zip(LABELS,palette):
            cases=sorted([r for r in rows if r['skin']==skin and r['orientation']=='horizontal' and r['label']==label],key=lambda r:r['refinement'])
            ax.loglog([r['intervals'] for r in cases],[abs(r['relative_difference']) for r in cases],'o-',label=label,color=color)
        ax.set_title(f"Skin {'on' if skin else 'off'}");ax.set_xlabel('Structural intervals');ax.set_ylabel('Relative frequency difference from exact beam')
        ax.grid(alpha=.25,which='both');ax.legend(fontsize=8)
    fig.suptitle('Primary Pazy model: mesh refinement with unchanged source properties\nExplicit intrinsic extension–torsion projection; zero gravity, no aerodynamics')
    figures={}
    for ext in ['png','svg']:
        path=D/f'pazy-primary-refinement.{ext}';fig.savefig(path,dpi=180,metadata={'Date':None} if ext=='svg' else {});figures[path.name]=sha(path)
    plt.close(fig)
    bounds={str(r['skin']):max(s['max_strain_energy_relative_perturbation'] for s in r['stiffness']) for r in native['mapping']['records']}
    out=dict(status='HISTORICAL_COMPARISON_SUPERSEDED_INPUT_CONVENTION',modules=modules,script_sha256=sha(__file__),
        superseded_by='pazy-loaded-comparison.json',
        known_input_issue='Spreadsheet off-diagonals were interpreted as tensor entries. Original Nastran rigid-body mass matrices establish the opposite CONM2 product signs. Use pazy-primary-conm2-* inputs and pazy-loaded-source-audit.json. Numerical results below reproduce the historical inputs only.',
        report_sha256={n:sha(D/n) for n in ['pazy-primary-mapping.json','pazy-primary-wasm.json','pazy-primary-browser.json','pazy-primary-discrete.json']},
        counts=dict(native_states=10,computed=10,rejected=0,wasm_states=6,offline_browser_states=6,mapped_material_matrices=30,nodal_inertias_per_skin=16,generated_models=4),
        section_energy_relative_bounds=bounds,frequency_table=frequency_table,mesh_comparisons=rows,
        numerical_reference_audit=numerical_references,discrete_reference=discrete,archived_shape_comparisons=shape_comparisons,frame_covariance=covariance,figures=figures,
        plot_palette=dict(path='web/plot-colors.js',sha256=sha(palette_path),colors=palette),
        max_coarse_vs_archived_relative=max(abs(r['coarse_vs_archive_relative']) for r in frequency_table),
        max_fine_vs_exact_relative=max(abs(r['fine_vs_exact_projected_relative']) for r in frequency_table),
        models=native['mapping']['models'],meshes=meshes,limits=native['limits'],full_family_validated=False,full_suite_validated=False,
        attachment_audit=dict(status='NO_DOCUMENTED_OUT_OF_DOMAIN_RULE_FOUND',
            source_sha256={p:sha(ROOT/p) for p in ['.reference/aswing_doc.txt','.reference/asw_theory.txt','.reference/ASWING_Extended_User_Manual.pdf','.reference/version_notes.txt']},
            finding='The public guides identify t as the beam anchor and Cartesian coordinates as the pylon endpoint. They do not specify out-of-domain t behavior; no clamping or extrapolation change was made.'),
        next_steps=['Check self-weight equilibrium, gravity-loaded modes and complete static measured curves with these primary properties.',
            'Resolve original .asw attachment semantics using authoritative documentation or controlled ASWING observations.',
            'Reconcile precise test loads, reference-axis/chord geometry, calibration dependence and measurement uncertainty before any physical-validation pass.',
            'Complete remaining aerodynamic/aeroelastic and other family comparisons; this study does not validate flutter or time response.'])
    path=D/'pazy-primary-comparison.json';path.write_text(json.dumps(out,indent=2)+'\n')
    lines=['# Historical primary Pazy beam reconstruction','',
        '**SUPERSEDED INPUT CONVENTION.** The earlier derived models below contain an incorrect interpretation of spreadsheet inertia off-diagonals. Their numerical results remain reproducible historical evidence, but they must not be used as validation of the corrected primary model. Use the [corrected inputs and loaded study](pazy-loaded-comparison.md); the [original Nastran mass-matrix audit](pazy-loaded-source-audit.json) proves the correction. The original evidence ZIP is unchanged.','',
        '**Numerical comparison complete; experimental validation remains incomplete.** Four importable `.asw` models retain the primary skin-specific stiffness distributions, 16 point masses, centroid offsets and full inertia tensors. All 97 production modules remain unchanged. Ten native modal states, six actual WebAssembly replays and six offline browser states pass.','',
        'The source is [Riso and Cesnik’s primary data](https://github.com/UM-A2SRL/AePW3-LDWG/tree/396710a19a80004c65c767e9955fe60d59565c39/00_Models/01_Pazy_Technion/02_Models_Beam), pinned at revision `396710a19a80004c65c767e9955fe60d59565c39`. The paper defines local axes along the span, toward the leading edge, and upward. Therefore the out-of-plane curvature changes sign when mapped to ASWING’s aft-pointing chord axis. Point inertia matrix off-diagonals are converted to ASWING’s negative-product convention. [Model definitions, §III and Appendix A](https://doi.org/10.2514/1.C036869).','',
        '## Explicit constitutive limitation','',
        'The primary 4×4 matrix includes intrinsic extension–torsion stiffness K12. The documented `.asw` fields cannot express that term: their axial coupling comes from offsets in the section plane. It is explicitly set to zero; the other nine independent entries are preserved by an exact energy-equivalent mapping. No frequency or material parameter is fitted. The complete original matrices and all mapped fields remain in [the mapping report](pazy-primary-mapping.json).','',
        'For every possible section strain vector, the relative strain-energy perturbation is bounded by '+f"{100*bounds['0']:.5f}% without skin and {100*bounds['1']:.5f}% with skin. "+'This bound is obtained from the extreme generalized eigenvalues of the matrix difference relative to the full positive-definite source matrix. It is not an experimental tolerance. Full and projected matrices are both evaluated by the independent reference.','',
        '## Independent reference and mesh refinement','',
        'The reference integrates the exact end flexibility of each massless material interval and assembles the original nodal spatial inertias. Its unit-load work integrand is quadratic, so two-point Gauss integration is exact. Both direct and reciprocal generalized eigenproblems check numerical sensitivity. This reference imports no OpenSwing solver code.','',
        '| Skin | Mode | Published UM/NAST (Hz) | OpenSwing 15 intervals (Hz) | OpenSwing 120 intervals (Hz) | Exact projected beam (Hz) |','|---|---|---:|---:|---:|---:|']
    for r in frequency_table:
        lines.append(f"| {'on' if r['skin'] else 'off'} | {r['label']} | {r['archived_um_Hz']:.6f} | {r['native_15_Hz']:.6f} | {r['native_120_Hz']:.6f} | {r['exact_projected_Hz']:.6f} |")
    lines+=['',f"At the original 15-interval discretization, the largest first-five-mode difference from the archived UM/NAST frequencies is {100*out['max_coarse_vs_archived_relative']:.5f}%. At 120 intervals, the largest difference from the independent projected beam is {100*out['max_fine_vs_exact_relative']:.5f}%.",
        '','Every first-five-mode frequency approaches the exact reference monotonically over 15/30/60/120 intervals. The archived finite-element result is not treated as the refined limit. This distinction matters especially for third bending.','',
        'At 15 intervals the zero-shear midpoint constraints reduce 90 massive coordinates to 60 independent coordinates, giving 120 finite first-order states. With subdivision, massless internal nodes allow all 90 massive coordinates, giving 180 states. An independent constrained strain-energy model reproduces all eight coarse-mesh frequencies within 3×10⁻⁹ Hz; the difference in state count is explained by the discretization. [Discrete reference audit](pazy-primary-discrete.json).','',
        '![Frequency refinement](pazy-primary-refinement.png)','',
        'All five published skin-off main-component mode profiles are compared with both UM/NAST and GFEM exports at every mesh. Those one-component correlations are separate from the six-component kinetic-energy correlations against the independent reference. Horizontal/upright zero-gravity frames agree across eight modes for both skin conditions.','',
        '## Importable models and runtime evidence','',
        '| Model | Input file |','|---|---|']
    for key,r in out['models'].items():lines.append(f"| {key.replace('_',' ')} | [{Path(r['path']).name}](../../{r['path']}) |")
    lines+=['','Import a matching mesh through the Settings mesh-file control: '+', '.join(f"[{n} intervals](../../{r['path']})" for n,r in meshes.items())+'. These material-station meshes work with all four models.','',
        'Use vacuum modes, fixed frame and **gravity magnitude zero** to reproduce this study. The JSON native cache records the explicit mesh for each run. Arbitrary positive t labels avoid implicit mirroring; no attachment lies outside its beam. The beam spans 0.549843728 m, directly from the supplied coordinates. The reference chord fraction is 0.441 from the paper; its README rounds this to 0.44.','',
        'The [WASM report](pazy-primary-wasm.json) checks complete A/M matrices, frequencies and complex shapes. The [browser report](pazy-primary-browser.json) checks the actual unchanged application offline after boot, original input equality, explicit mesh import, module provenance, frequencies/shapes and the mobile Plots layout. The runtime sample covers 15 and 60 intervals, including both orientations; it does not replay the 120-interval states.','',
        '## What this resolves and what remains','',
        'The primary properties explain a substantial part of the simplified model’s in-plane frequency difference: the primary zero-gravity model predicts about 106–109 Hz, while the previous simplified model predicted about 128 Hz. The measured upright skin-on value remains 60.7 Hz. The new gravity-free comparison is not a matched loaded experimental test, and does not establish physical validation.','',
        'The literal ISAE attachment issue also remains. The public user guide, extended manual, theory and version notes do not state how to handle an anchor beyond a beam endpoint. No inferred clamping/extrapolation rule was added. These primary-data models are separately generated inputs, not repaired originals. [Drela’s Weight definition](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt).','']
    lines+=['- '+s for s in out['next_steps']]
    lines+=['','Full evidence: [comparison JSON](pazy-primary-comparison.json), [mapping and native runs](pazy-primary-mapping.json), [SVG figure](pazy-primary-refinement.svg). The original [ST-2 simplified-model study](isae-st2-comparison.md) remains unchanged. Family coverage stays at 16 partial/25 pending, with no fully validated family.','']
    (D/'pazy-primary-comparison.md').write_text('\n'.join(lines))
    (D/'pazy-primary-checks.json').write_text(json.dumps(dict(status='PASS_HISTORICAL_PRIMARY_REPRODUCTION_SUPERSEDED_INPUT_CONVENTION',
        modules=modules,script_sha256=sha(__file__),snapshot_sha256=sha(path),counts=out['counts']),indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','counts','section_energy_relative_bounds','max_coarse_vs_archived_relative','max_fine_vs_exact_relative']},indent=2))


if __name__=='__main__':main()
