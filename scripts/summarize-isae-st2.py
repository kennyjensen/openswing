"""Audit and summarize Pazy comparisons from immutable, fully saved solutions.

No new solve or fitted parameter. The primary x-z chord projection is recovered
from full rotations, keeping the earlier chord-elevation diagnostic separate.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
matplotlib.rcParams['svg.hashsalt'] = 'openswing-isae-st2-20261015'
import matplotlib.pyplot as plt
from isae_st2_archive import read_archive_profile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'docs/validation'
LABELS = ['OOP1', 'OOP2', 'T1', 'IP1', 'OOP3']
LAYOUTS = ['archive_pylon', 'measured_tip']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, digest=None):
    path = Path(path)
    if digest is not None:
        assert sha(path) == digest, path
    return json.loads(path.read_text())


def projected_twist(node):
    q = np.array(node['rotation'])
    assert q[0, 0] > 0  # No quadrant crossing in these states.
    return float(np.rad2deg(np.arctan2(-q[2, 0], q[0, 0])))


def local_twist(node):
    q = np.array(node['rotation']); span = q[:, 1]
    phi = np.arctan2(span[2], span[1]); psi = -np.arcsin(np.clip(span[0], -1, 1))
    c = [np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)]
    n = [0., -np.sin(phi), np.cos(phi)]
    return float(np.rad2deg(np.arctan2(-q[:, 0]@n, q[:, 0]@c)))


def stats(errors):
    errors = np.asarray(errors)
    assert len(errors) and np.isfinite(errors).all()
    return dict(count=len(errors), rmse=float(np.sqrt(np.mean(errors**2))),
                max_abs=float(np.max(abs(errors))), mean=float(np.mean(errors)))


def complex_shape(mode):
    return np.array(mode['shape']['real']) + 1j*np.array(mode['shape']['imag'])


def mac(a, b):
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    return float(abs(np.vdot(a, b))**2 / (np.vdot(a, a).real*np.vdot(b, b).real))


def static_comparisons(static, cache):
    datasets = []
    for data in static['datasets']:
        quantity = 'twist_xz_deg' if data['quantity'].endswith('_deg') else 'z_m'
        out = {k: data[k] for k in ['kind', 'skin', 'source_path', 'source_sha256', 'original_values', 'values']}
        out.update(quantity=quantity, comparisons=[])
        for layout in LAYOUTS:
            for j, panels in enumerate([16, 32, 64]):
                zero = cache[data['requests'][0]['keys'][layout][j]]
                rows = []
                for request, (mass, measured) in zip(data['requests'], data['values']):
                    key = request['keys'][layout][j]; run = cache[key]
                    tip = run['result']['nodes'][-1]
                    predicted = (tip['position'][2]-zero['result']['nodes'][-1]['position'][2]
                                 if quantity == 'z_m' else projected_twist(tip))
                    row = dict(key=key, mass_kg=mass, measured=measured, predicted=predicted, error=predicted-measured)
                    if quantity == 'twist_xz_deg':
                        row.update(chord_elevation_deg=run['observables']['twist_projected_deg'],
                                   local_twist_deg=local_twist(tip),
                                   archive_plot_negated_local_deg=-local_twist(tip))
                    rows.append(row)
                summary = stats([r['error'] for r in rows])
                if quantity == 'twist_xz_deg':
                    summary['max_xz_minus_elevation_deg'] = max(abs(r['predicted']-r['chord_elevation_deg']) for r in rows)
                out['comparisons'].append(dict(layout=layout, panels=panels, rows=rows, **summary))
        # Mesh differences at exactly the same measured masses; no interpolation.
        out['refinement'] = []
        for layout in LAYOUTS:
            rows = [r for r in out['comparisons'] if r['layout'] == layout]
            for a, b in zip(rows[:-1], rows[1:]):
                out['refinement'].append(dict(layout=layout, panels=[a['panels'], b['panels']],
                    **stats([x['predicted']-y['predicted'] for x,y in zip(a['rows'], b['rows'])])))
        datasets.append(out)
    return datasets


def frame_covariance(modal, cache):
    # Rx(+90 degrees) maps horizontal coordinates to upright coordinates.
    rotation = np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])
    out = []
    for panels in [8, 16, 32, 64]:
        pair = {r['specification']['orientation']: cache[r['cache']] for r in modal['runs']
                if r['specification']['panels'] == panels and r['specification']['gravity'] == 0}
        horizontal, upright = pair['horizontal'], pair['upright']
        assert np.max(abs(np.array(horizontal['jig'])@rotation.T-np.array(upright['jig']))) < 1e-14
        assert len(horizontal['modes']) == len(upright['modes']) == 8
        rows = []
        for a,b in zip(horizontal['modes'], upright['modes']):
            shape = complex_shape(a).copy()
            shape[:, :3] = shape[:, :3]@rotation.T
            shape[:, 3:] = shape[:, 3:]@rotation.T
            df = abs(a['frequency_Hz']-b['frequency_Hz']); score = mac(shape, complex_shape(b))
            assert df < 2e-6 and score > 1-2e-8
            rows.append(dict(frequency_Hz=b['frequency_Hz'], difference_Hz=df, shape_assurance=score))
        out.append(dict(panels=panels, modes=rows))
    return out


def archive_profile(static, cache, folder):
    path = folder/'03_Static_Structural/temp.txt'
    data = np.asarray(read_archive_profile(path)['values'])
    rows = []
    for key, row in static['runs'].items():
        spec = row['specification']
        if not (spec['kind']=='bending' and spec['mass_kg']==3 and spec['layout']=='archive_pylon'):
            continue
        run=cache[key]; nodes=run['result']['nodes']; stations=[n['t'] for n in nodes]
        predicted=np.column_stack([np.interp(data[:,0],stations,[n['position'][1] for n in nodes]),
                                   np.interp(data[:,0],stations,[n['position'][2] for n in nodes]),
                                   np.interp(data[:,0],stations,[local_twist(n) for n in nodes])])
        rows.append(dict(panels=spec['panels'], key=key, interpolated_values=predicted.tolist(),
            quantities={name:stats(predicted[:,i]-data[:,i+1]) for i,name in enumerate(['y_m','z_m','local_twist_deg'])},
            tip_differences=(predicted[-1]-data[-1,1:4]).tolist(),
            applied_force=run['result']['applied_force'],applied_moment=run['result']['applied_moment']))
    return dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), rows=data.tolist(), comparisons=rows,
        status='CONDITIONAL_ARCHIVED_PROFILE_COMPARISON',
        inference='The 31.45 N downward force, nonzero positive twist and final tip coordinates suggest the final 3 kg bending state. The export does not record its input file or discretization.',
        limits='Printed stations/values are rounded. Native fields are linearly interpolated to those printed stations. No exact original grid or printed-precision full-profile pass is asserted.')


def plots(datasets, tables):
    fig,axes=plt.subplots(3,2,figsize=(11,10),layout='constrained')
    colors=['#d95f02','#0072b2']; names=['Archive-coordinate pylon','Tip-centred comparison variant']
    for data in datasets:
        index=0 if data['kind']=='bending' else (2 if data['quantity'].endswith('_deg') else 1)
        ax=axes[index,data['skin']]; factor=1 if data['quantity'].endswith('_deg') else 1000
        values=np.array(data['values']);ax.plot(values[:,0],factor*values[:,1],'ko',ms=4,label='Measurements')
        for layout,color,name in zip(LAYOUTS,colors,names):
            for comparison in (r for r in data['comparisons'] if r['layout']==layout):
                n=comparison['panels'];r=comparison['rows']
                ax.plot([v['mass_kg'] for v in r],[factor*v['predicted'] for v in r],
                    color=color,ls={16:':',32:'--',64:'-'}[n],lw=1.5 if n==64 else .8,
                    label=name if n==64 else None)
        ax.set_title(('Bending' if index==0 else 'Bending–torsion')+f", skin {'on' if data['skin'] else 'off'}")
        ax.set_xlabel('Added mass (kg)');ax.set_ylabel('Signed x–z chord twist (°)' if index==2 else 'Tip displacement from zero load (mm)')
        ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=8)
    fig.suptitle('Pazy ST-2: explicit load reconstructions; original simplified properties\nN16 dotted · N32 dashed · N64 solid; neither reconstruction is a literal-file pass',fontsize=12)
    files=[]
    for ext in ['png','svg']:
        p=DEST/f'isae-st2-static-comparison.{ext}';fig.savefig(p,dpi=180,metadata={'Date':None} if ext=='svg' else {});files.append(p)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,orientation in zip(axes,['upright','horizontal']):
        rows=[r for r in tables if r['orientation']==orientation and r['gravity']==9.81 and r['panels']==64]
        xx=np.arange(len(rows))
        ax.scatter(xx,[r['predicted_Hz'] for r in rows],label='OpenSwing N64',marker='s')
        ax.scatter(xx,[r['archived_aswing_Hz'] for r in rows],label='Archived ASWING',marker='x')
        measured=[(x,r['experimental_Hz']) for x,r in zip(xx,rows) if r['experimental_Hz'] is not None]
        ax.scatter([r[0] for r in measured],[r[1] for r in measured],label='GVT: accelerometers' if orientation=='upright' else 'GVT: strain PSD',color='black')
        ax.set_xticks(xx,[r['label'] for r in rows]);ax.set_ylabel('Frequency (Hz)');ax.set_title(orientation.capitalize()+', gravity 9.81 m/s²')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Pazy modes: shape-matched branches; simplified section properties retained')
    for ext in ['png','svg']:
        p=DEST/f'isae-st2-modal-comparison.{ext}';fig.savefig(p,dpi=180,metadata={'Date':None} if ext=='svg' else {});files.append(p)
    plt.close(fig)
    return {p.name:sha(p) for p in files}


def main():
    names=['isae-st2-source-audit','isae-st2-static','isae-st2-modes','isae-st2-wasm','isae-st2-browser']
    source,static,modal,wasm,browser=[read(DEST/(n+'.json')) for n in names]
    modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert len(modules)==97
    for report in [source,static,modal,wasm,browser]:assert report['modules']==modules
    assert source['status']=='PASS_SOURCE_INTEGRITY_WITH_EXPLICIT_SETUP_CONFLICTS'
    assert static['status']==modal['status']=='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED'
    assert wasm['status']==browser['status']=='PASS_EXPECTED_OUTCOMES'
    assert browser['offline'] and browser['served_build']
    scripts={}
    for report in [static,modal,wasm]:
        for name,digest in report['scripts'].items():
            assert sha(ROOT/'scripts'/name)==digest; scripts[name]=digest
    for report,path in [(source,'scripts/audit-isae-st2-sources.py'),(wasm,'scripts/test-isae-st2-wasm.mjs'),(browser,'tests/browser/isae-st2.spec.js')]:
        digest=report.get('test_sha256',report.get('script_sha256'));assert sha(ROOT/path)==digest;scripts[path]=digest
    for report in [wasm,browser]:
        assert report['static_sha256']==sha(DEST/'isae-st2-static.json')
        assert report['modal_sha256']==sha(DEST/'isae-st2-modes.json')
    cache_root=ROOT/'.reference/isae-validation'/source['upstream_revision']
    primary_root=ROOT/'.reference/pazy-primary'/source['primary']['revision']
    for path,pin in source['sources'].items():assert sha(cache_root/path)==pin['sha256']
    for path,pin in source['primary']['files'].items():assert sha(primary_root/path)==pin['sha256']
    assert len(source['sources'])==146 and len(source['primary']['files'])==105
    assert len(source['literal_models'])==6 and all(r['construction']=='rejected' for r in source['literal_models'])
    assert len(wasm['literal_rejections'])==6
    assert len(static['requests'])==462 and static['measurement_rows']==77
    assert static['computed']==static['unique_conditions']==246 and static['rejected']==0
    cache={}
    for key,row in static['runs'].items():
        run=read(ROOT/row['cache'],row['sha256']);assert run['status']=='computed'
        assert run['identity']['modules']==modules and run['identity']['scripts']==static['scripts']
        assert run['specification']==row['specification'] and run['identity']['specification']==row['specification']
        assert hashlib.sha256(json.dumps(row['specification'],sort_keys=True).encode()).hexdigest()==key
        assert run['result']['residual']<1e-8
        cache[key]=run
    assert Counter(r['key'] for r in static['requests'])==Counter(k for d in static['datasets'] for r in d['requests'] for keys in r['keys'].values() for k in keys)
    datasets=static_comparisons(static,cache)
    modal_cache={}
    for row in modal['runs']:
        run=read(ROOT/row['cache'],row['sha256']);assert row['status']==run['status']=='computed'
        assert run['identity']['modules']==modules and run['identity']['scripts']==modal['scripts']
        assert run['specification']==row['specification']
        assert sha(ROOT/run['matrices']['path'])==run['matrices']['sha256']
        assert run['base']['residual']<1e-8
        assert max(max(r['right_backward_error'],r['left_backward_error']) for r in run['modes'])<1e-9
        modal_cache[row['cache']]=run
    assert len(modal_cache)==16
    covariance=frame_covariance(modal,modal_cache)
    tables=[]
    for run in modal['runs']:
        spec=run['specification'];orientation=spec['orientation']
        measured=source['measured_modal_Hz']['skin1_upright' if orientation=='upright' else 'skin1_horizontal_strain_PSD']
        for mode in run['matches']:
            label=mode['label'];f=mode['frequency_Hz'];observed=measured.get(label)
            tables.append(dict(**spec,label=label,predicted_Hz=f,experimental_Hz=observed,
                experimental_relative_error=None if observed is None else f/observed-1,
                archived_aswing_Hz=source['archived_modal_Hz'][orientation][label],
                independent_Hz=mode['reference_Hz'] if orientation=='upright' or spec['gravity']==0 else None,
                reference_for_labeling_Hz=mode['reference_Hz'],shape_assurance=mode['shape_assurance']))
    independent=[]
    for panels in [16,32,64]:
        rows=[o for r in static['independent'] for o in r['observations'] if o['panels']==panels]
        assert len(rows)==8 and all(r['status']=='compared' for r in rows)
        independent.append(dict(panels=panels,profiles=8,max_position_difference_m=max(r['max_position_difference_m'] for r in rows),
                                max_rotation_component_difference=max(r['max_rotation_component_difference'] for r in rows)))
    for row in static['independent']:
        for a,b in zip(row['observations'][:-1],row['observations'][1:]):
            assert b['max_position_difference_m']<.3*a['max_position_difference_m']
            assert b['max_rotation_component_difference']<.3*a['max_rotation_component_difference']
    runtime=dict(wasm_static_states=len(wasm['static_rows']),wasm_modal_states=len(wasm['modal_rows']),
        browser_static_states=len(browser['statics']),browser_modal_states=len(browser['modes']),literal_wasm_rejections=6,
        wasm_max_scaled_matrix_error=max(v for r in wasm['modal_rows'] for v in r['matrix_errors'].values()),
        wasm_max_frequency_difference_Hz=max(m['frequency_difference_Hz'] for r in wasm['modal_rows'] for m in r['modes']),
        browser_max_frequency_difference_Hz=max(m['frequency_difference_Hz'] for r in browser['modes'] for m in r['comparisons']),
        browser_max_static_field_difference=max(v for r in browser['statics'] for v in r['differences'].values()),
        note='Runtime agreement verifies implementation consistency. It does not establish agreement with experiment.')
    assert [runtime[k] for k in ['wasm_static_states','wasm_modal_states','browser_static_states','browser_modal_states']]==[8,4,6,4]
    folder=cache_root/'3 - Structure/CASE - ST2 Pazy_Wing'
    archive=archive_profile(static,cache,folder)
    script_pin=sha(__file__)
    out=dict(status='COMPARISONS_COMPLETE_NOT_PHYSICALLY_VALIDATED',modules=modules,script_sha256=script_pin,scripts=scripts,
        upstream_revision=source['upstream_revision'],report_sha256={n+'.json':sha(DEST/(n+'.json')) for n in names},
        counts=dict(isae_files=146,primary_files=105,literal_construction_rejections=6,measurement_rows=77,static_requests=462,
                    unique_static_conditions=246,computed_static_conditions=246,rejected_static_conditions=0,modal_conditions=16,independent_static_profiles=24),
        measurement_convention=dict(twist='degrees(atan2(-Q[2,0], Q[0,0])): x-z chord projection, positive nose-up in the comparison convention.',
            displacement='Tip midchord z minus its zero-added-mass z, retaining downward negative sign. Reference line is at midchord.',
            correction='The raw static report field twist_projected_deg is chord elevation, with hypot(Q[0,0],Q[1,0]) denominator. It remains immutable; this report recomputes the x-z projection from full rotations. Neither quantity is the archive plot negation of local section twist.'),
        reconstruction_scope=dict(archive_pylon='Anchor .55, physical y=.558, x=.05 for bending or -.09/-.13 for torsion. Original physical load coordinates retained on an explicit rigid pylon.',
            measured_tip='Historical cache name: tip-centred comparison variant at y=.55, x=0 for bending or +.09/+.13 for torsion. Chordwise placement follows the primary description; the experimental paper gives y=.558. This is not an exact experiment reconstruction.',
            modal='Remove only two identically zero physical Weight objects with invalid .558 anchors. All beam fields retained.',
            material='Original simplified section distributions unchanged, including using the same static properties for skin-on and skin-off. No fitting.'),
        additional_source_findings=[
            'Avin IV.B reports a bending load station y=558 mm and a 15.5 g reinforcing rod. The tip-centred variant omits the 8 mm extension and does not separately reconstruct rod/instrument masses.',
            'The ISAE skin-on torsion plotting block reads a skin-off GFEM rotation file. That mislabeled plotted curve is not treated as skin-on experimental data.',
            'All five original workbook contents, including upstream #VALUE! cells, and the primary mode-type mapping remain in the source audit.'],
        static_datasets=datasets,independent_static=independent,modal_comparisons=tables,frame_covariance=covariance,
        independent_modal_refinements=[dict(gravity=float(g),states=[{k:r[k] for k in ['elements','frequencies_Hz','labels','approximation']} for r in rows]) for g,rows in modal['references'].items()],
        measured_horizontal_skin1_methods_Hz=dict(displacement_PSD=dict(OOP1=4.48,OOP2=29.4,T1=41.,OOP3=81.3),
            displacement_SPOD=dict(OOP1=4.69,OOP2=30.,T1=41.3,OOP3=81.6),strain_PSD=source['measured_modal_Hz']['skin1_horizontal_strain_PSD']),
        archived_profile=archive,runtime=runtime,source_conflicts=source['conflicts'],primary_references=source['primary_references'],
        remaining=['Recover documented ASWING handling of out-of-domain attachments; literal construction remains rejected.',
            'Reconstruct full primary stiffness/inertia, skin-specific properties, exact spanwise/chordwise load geometry and instrumentation/rod masses.',
            'Compare the remaining primary FE/beam variant curves and measured shapes with matched quantities and setups.',
            'Resolve static and modal experimental discrepancies, calibration dependence and quantified measurement/setup uncertainty. No experimental pass threshold has been invented.',
            'Aerodynamic loaded modes, static aeroelasticity and flutter belong to separate AE cases; they are not validated by this air-free structural comparison.'],
        full_family_validated=False,full_suite_validated=False)
    out['figures']=plots(datasets,tables)
    path=DEST/'isae-st2-comparison.json';path.write_text(json.dumps(out,indent=2)+'\n')
    write_markdown(out,source)
    checks=dict(status='PASS_ST2_COVERAGE_AUDIT_NOT_PHYSICAL_VALIDATION',modules=modules,script_sha256=script_pin,
                snapshot_sha256=sha(path),**out['counts'],runtime=runtime,full_family_validated=False)
    (DEST/'isae-st2-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(dict(status=checks['status'],counts=out['counts'],runtime=runtime),indent=2))


def write_markdown(out,source):
    lines=['# Pazy wing ST-2 comparison','',
        '**Partial comparison complete; no experimental validation pass.** All 77 supplied static measurement rows were compared at N16/32/64 for two explicit load reconstructions. The 462 requests reduce to 246 distinct static solves; all computed. Sixteen air-free modal states cover two orientations, gravity off/on and N8/16/32/64. All 97 production modules and original upstream files are unchanged.','',
        'All six literal `.asw` files parse but fail network construction: their Weight anchors are at t=0.558, outside a beam ending at t=0.55. None is counted as a literal-file solve. The [source audit](isae-st2-source-audit.json) pins 146 ISAE files and 105 primary-author files; 97 corresponding files are byte-identical.','',
        'The ISAE source is [Jan’s structural validation repository](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/'+out['upstream_revision']+'/3%20-%20Structure/CASE%20-%20ST2%20Pazy_Wing). The primary model/data collection is [Riso and Cesnik’s AePW3 repository](https://github.com/UM-A2SRL/AePW3-LDWG/tree/'+source['primary']['revision']+').','',
        '## Load and measurement conventions','',
        '| Variant | Anchor | Physical load coordinates (m) | Interpretation |','|---|---:|---|---|',
        '| Archive-coordinate pylon | .55 | y=.558; x=.05 bending, −.09/−.13 torsion | Retains archive coordinates on an explicit rigid tip extension |',
        '| Tip-centred comparison (`measured_tip` in caches) | .55 | y=.55; x=0 bending, +.09/+.13 torsion | Primary chordwise locations; spanwise load position remains approximate |','',
        'The experiment describes midchord bending loads at y=558 mm, aft torsion loads and an additional reinforcing rod. Thus the tip-centred variant does **not** recover its complete setup. Original simplified stiffness and mass distributions remain unchanged; the two skin cases are not separately fitted. The static and modal distributed masses are 0.205975 and 0.3732785 kg, while the primary lumped beam files sum to 0.347330 and 0.356596 kg without/with skin. [Experimental setup, §IV.B](https://doi.org/10.2514/1.J060621); [low-order model study, §IV.B](https://doi.org/10.2514/1.C036869).','',
        'Vertical displacement is the midchord tip z change from the zero-added-mass state. Twist uses the chord projection in the x–z plane: `degrees(atan2(-Q[2,0], Q[0,0]))`, with positive nose-up sign. The initial raw report’s `twist_projected_deg` instead measures chord elevation using a horizontal-norm denominator. Its saved results are unchanged; the final angle is recomputed here from full rotations. The archive’s negated local section twist is a third quantity and remains a separate diagnostic. [Experimental angle reduction, §IV.B](https://doi.org/10.2514/1.J060621).','',
        '## Static discrepancies','',
        '| Data | Points | Archive-pylon N64 RMSE | Tip-centred N64 RMSE | Tip-centred max N32→64 change |','|---|---:|---:|---:|---:|']
    for data in out['static_datasets']:
        rows={r['layout']:r for r in data['comparisons'] if r['panels']==64}
        ref=next(r for r in data['refinement'] if r['layout']=='measured_tip' and r['panels']==[32,64])
        degree=data['quantity'].endswith('_deg');factor=1 if degree else 1000;unit='°' if degree else 'mm'
        title=f"{data['kind'].capitalize()}, skin {'on' if data['skin'] else 'off'}, {'twist' if degree else 'displacement'}"
        lines.append(f"| {title} | {len(data['values'])} | {factor*rows['archive_pylon']['rmse']:.5f} {unit} | {factor*rows['measured_tip']['rmse']:.5f} {unit} | {factor*ref['max_abs']:.5f} {unit} |")
    lines+=['','![Static measurements and both explicit reconstructions](isae-st2-static-comparison.png)','',
        'Mesh changes are substantially smaller than the experimental discrepancies. The archived torsion load location gives the opposite signed chord twist; applying its plotting sign reversal would conceal that setup difference. Neither a sign reversal nor a stiffness fit is used to improve the measured comparison. The skin-on MATLAB plotting block also reads a skin-off GFEM rotation file; that plotted curve is not used as skin-on evidence.','',
        'An independent continuous Kirchhoff rod shooting calculation uses quaternion kinematics, spatial force/moment balance and the rotating tip-pylon load. It imports no OpenSwing code. Eight selected states are compared at three meshes:','',
        '| Panels | Profiles | Max position-component difference | Max rotation-matrix-component difference |','|---:|---:|---:|---:|']
    for r in out['independent_static']:
        lines.append(f"| {r['panels']} | {r['profiles']} | {1000*r['max_position_difference_m']:.6f} mm | {r['max_rotation_component_difference']:.6g} |")
    lines+=['','Each refinement reduces those differences by approximately four. This verifies the simplified nonlinear structural equations for the checked states, not the experimental material model.','',
        'The saved ASWING `temp.txt` is also compared at all printed stations. Its force, positive twist and tip displacement suggest the final 3 kg bending case; that identification is an inference because the export omits the source file and mesh. At N32 the reconstructed tip is y=0.455903 m, z=−0.279142 m and local twist=5.11513°, versus printed 0.456 m, −0.279 m and 5.11°. Full-profile interpolation differences and source rounding limits are retained in the JSON; no exact archive replay is claimed.','',
        '## Modal discrepancies','',
        'Modes are assigned by physical shape, not table row. The supplied workbook and primary experiment identify the upright GVT as **skin on**; the ISAE summary caption says skin off. The summary also interchanges the primary UM/NAST in-plane and third-bending entries. The corrected type mapping is retained. [Primary GVT tables 3–5](https://doi.org/10.2514/1.J060621).','',
        '| Orientation | Mode | OpenSwing N64, gravity on (Hz) | Archived ASWING (Hz) | Measured (Hz) | Difference from measurement |','|---|---|---:|---:|---:|---:|']
    for r in out['modal_comparisons']:
        if r['panels']!=64 or r['gravity']!=9.81:continue
        observed='—' if r['experimental_Hz'] is None else f"{r['experimental_Hz']:.2f}"
        error='—' if r['experimental_relative_error'] is None else f"{100*r['experimental_relative_error']:+.2f}%"
        lines.append(f"| {r['orientation']} | {r['label']} | {r['predicted_Hz']:.6f} | {r['archived_aswing_Hz']:.2f} | {observed} | {error} |")
    lines+=['','Horizontal measurements in this table use strain PSD. The primary displacement PSD and SPOD results differ and are separately recorded in the JSON. The in-plane experimental discrepancy is large and also present in the archived ASWING model. It remains unresolved.','',
        '![Modal comparison by physical branch](isae-st2-modal-comparison.png)','',
        'Independent Hermite/Rayleigh beam calculations retain two coupled bending planes, distributed rotary inertia, torsion, and the stiffness break at 0.52 m. The 49/97/193-element reference refinements and native N8/16/32/64 results are saved. For upright gravity, the reference includes compressive geometric stiffness and neglects finite axial shortening. The horizontal gravity-loaded reference is used only to assign branches; it is not an independent loaded-frequency check. Its in-plane shape-assurance value is about 0.738, so that assignment is less certain than the other checked branches.','',
        'All four gravity-free orientation pairs agree after rotating displacements and rotation vectors, across eight positive-frequency modes each. Full descriptor A/M matrices and left/right eigenpair backward errors are retained. No aerodynamic apparent mass is included.','',
        '## Runtime checks and reproducibility','',
        'The [WebAssembly replay](isae-st2-wasm.json) passes eight full static-field comparisons, four modal A/M/frequency/shape comparisons and all six expected literal construction rejections. The [actual served browser app](isae-st2-browser.json), offline after boot, passes six static and four modal solves with exported input equality and all 97 source hashes checked. The mobile Plots view also passes its width check. These samples do not replay every native condition.','',
        'Raw calculations: [static](isae-st2-static.json), [modal](isae-st2-modes.json). Final postprocessing: [comparison JSON](isae-st2-comparison.json), [coverage audit](isae-st2-checks.json). Standalone figures: [static SVG](isae-st2-static-comparison.svg), [modal SVG](isae-st2-modal-comparison.svg).','',
        'From the repository root, after fetching the pinned source datasets:','',
        '```sh','OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/audit-isae-st2-sources.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-isae-st2-static.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-isae-st2-modes.py',
        'node scripts/test-isae-st2-wasm.mjs',
        '# Run tests/browser/isae-st2.spec.js against the local served build and retain its JSON export.',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/summarize-isae-st2.py','```','',
        '## Work remaining','']
    lines+=['- '+r for r in out['remaining']]
    lines+=['','The primary static and GVT measurements were used for model adaptation, so they are not an independent calibration holdout. The experimental paper gives an order-of-magnitude twist measurement error up to about 1.2°; it does not supply a statistical acceptance band for these comparisons. [Experimental uncertainty and adaptation](https://doi.org/10.2514/1.J060621).','']
    (DEST/'isae-st2-comparison.md').write_text('\n'.join(lines))


if __name__=='__main__':
    main()
