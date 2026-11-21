"""Reduce the source-pinned modal study without hiding failed searches."""
from pathlib import Path
from collections import Counter
import hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/validation'


def main():
    data=json.loads((DEST/'isae-st3.json').read_text());sources=json.loads((DEST/'isae-st3-sources.json').read_text())
    assert data['provenance']['modules']=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'openswing').glob('*.py')}
    runs=data['runs'];computed=[r['result'] for r in runs if r['status']=='computed'];failures=[r for r in runs if r['status']!='computed']
    def choose(name,n,g,speed=0.,step=1e-5,method='full_shift_invert'):
        found=[r for r in computed if all(r['specification'][k]==v for k,v in dict(name=name,panels=n,gravity=g,speed=speed,step=step,method=method).items())]
        assert len(found)==1,(name,n,g,speed,step,method);return found[0]
    def frequencies(run):return {m['label']:m['frequency_Hz'] for m in run['matches'][0]['modes']}
    finest=max(data['settings']['meshes']);coarser=sorted(data['settings']['meshes'])[-2]
    refinement=[];reference_changes=[];step_changes=[];comparisons=[];axial_checks=[];dense_checks=[];frequency_sets=[]
    for name in ['0_3_90','p15_0','m15_0']:
        for g in [0.,9.81]:
            last=choose(name,finest,g);before=choose(name,coarser,g)
            mass=.283 if name=='0_3_90' else .231
            exact=-mass*g*.558**2/(2*1.132e7)
            delta=last['base']['nodes'][-1]['position'][2]-.558
            axial_checks.append(dict(name=name,gravity=g,exact_shortening_m=exact,computed_shortening_m=delta,absolute_error_m=abs(delta-exact)))
            a,b=frequencies(last),frequencies(before)
            for mode in last['matches'][0]['modes']:
                label=mode['label'];refinement.append(dict(name=name,gravity=g,label=label,
                    last_frequency_Hz=a[label],relative_mesh_change=a[label]/b[label]-1,
                    relative_independent_error=mode['relative_reference_error'],shape_assurance=mode['shape_assurance']))
            refs=data['references'][name][str(g)];reference_changes.append(dict(name=name,gravity=g,
                maximum_relative_change=float(max(abs(np.array(refs[-1]['frequencies_Hz'][:3])/refs[-2]['frequencies_Hz'][:3]-1)))))
        a,b=frequencies(choose(name,16,9.81)),frequencies(choose(name,16,9.81,step=3e-6))
        step_changes.append(dict(name=name,maximum_relative_change=max(abs(a[k]/b[k]-1) for k in a)))
        primary=dict(zip(sources['primary']['order'],sources['primary']['experiment_Hz'][name]))
        dry=frequencies(choose(name,finest,9.81));unloaded=frequencies(choose(name,finest,0.))
        air=frequencies(choose(name,32,9.81,speed=.01));air_fast=frequencies(choose(name,32,9.81,speed=.1));air_coarse=frequencies(choose(name,16,9.81,speed=.01))
        predicted=np.sort(list(air.values()));archived=np.sort(sources['upstream_workbook']['aswing_Hz'][name])
        frequency_sets.append(dict(name=name,computed_Hz=predicted.tolist(),archived_Hz=archived.tolist(),
            relative_differences=(predicted/archived-1).tolist(),
            meaning='Ascending-frequency set comparison only; not verification of modal identity or exact ASWING setup.'))
        for label in sources['primary']['order']:
            comparisons.append(dict(name=name,label=label,primary_experiment_Hz=primary[label],
                gravity_off_air_free_Hz=unloaded[label],self_weight_air_free_Hz=dry[label],
                self_weight_small_positive_speed_Hz=air[label],speed_m_s=.01,air_mesh=32,
                air_free_error_percent=100*(dry[label]/primary[label]-1),
                small_speed_error_percent=100*(air[label]/primary[label]-1),
                air_mesh_change_percent=100*(air[label]/air_coarse[label]-1),
                air_speed_change_percent=100*(air[label]/air_fast[label]-1)))
    for run in computed:
        s=run['specification']
        if s['method']=='dense':
            a,b=frequencies(run),frequencies(choose(s['name'],8,0.))
            dense_checks.append(dict(specification=s,maximum_relative_difference=max(abs(a[k]/b[k]-1) for k in a)))
    gates=dict(maximum_reference_refinement=max(r['maximum_relative_change'] for r in reference_changes),
        maximum_native_refinement=max(abs(r['relative_mesh_change']) for r in refinement),
        maximum_native_reference_error=max(abs(r['relative_independent_error']) for r in refinement),
        minimum_finest_shape_assurance=min(r['shape_assurance'] for r in refinement),
        maximum_axial_shortening_error_m=max(r['absolute_error_m'] for r in axial_checks),
        maximum_successful_dense_difference=max((r['maximum_relative_difference'] for r in dense_checks),default=0.),
        maximum_difference_step_change=max(r['maximum_relative_change'] for r in step_changes))
    limits=dict(maximum_reference_refinement=2e-4,maximum_native_refinement=.004,
        maximum_native_reference_error=.002,minimum_finest_shape_assurance=.999,
        maximum_difference_step_change=2e-6,maximum_axial_shortening_error_m=2e-10,maximum_successful_dense_difference=1e-7)
    checks={k:(value>limits[k] if k.startswith('minimum') else value<limits[k]) for k,value in gates.items()}
    report=dict(status='PASS_COMPONENT_CHECKS_WITH_RETAINED_SOLVER_FAILURES' if all(checks.values()) else 'FAIL_COMPONENT_CHECKS',
        full_suite_validated=False,all_requested_solves_computed=not failures,
        provenance=dict(study_sha256=hashlib.sha256((DEST/'isae-st3.json').read_bytes()).hexdigest(),sources_sha256=hashlib.sha256((DEST/'isae-st3-sources.json').read_bytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        run_counts=dict(Counter(r['status'] for r in runs)),gates=gates,limits=limits,checks=checks,
        refinement=refinement,independent_refinement=reference_changes,difference_step=step_changes,
        axial_shortening=axial_checks,
        successful_dense_comparisons=dense_checks,archived_frequency_sets=frequency_sets,
        comparisons=comparisons,failures=[dict(specification=r['identity']['specification'],error=r['error']) for r in failures],
        archived_aswing=dict(order=sources['upstream_workbook']['order'],frequencies_Hz=sources['upstream_workbook']['aswing_Hz'],
            status='Unresolved branch correspondence; primary/ISAE coupled-mode labels conflict. No scalar-frequency relabeling is used to claim a modal match.'))
    (DEST/'isae-st3-checks.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# ISAE ST-3 composite-wing modal comparisons','',
        '**ST-3 is partially compared, not fully validated.** This study uses the three literal vertical-wing files. Static force/moment deflection comparisons remain pending. The production kernel is unchanged.','',
        f"The native study contains {len(computed)} computed operating-point/solver records and {len(failures)} rejected records. Each computed record reuses one A/M assembly for two eigenvalue searches. All failures are retained in [the checks](isae-st3-checks.json).",'',
        '## Primary-source audit','',
        "[Dunn’s 1992 MIT thesis](https://dspace.mit.edu/entities/publication/55aa429a-7a4a-4908-87e6-7ecc1ece5ae5), Table 2 on printed page 99 (PDF page 125), was checked visually. Its coupled-laminate mode order is 1B, 1T, 2B. The ISAE workbook/report instead labels those same experimental columns 1B, 2B, 1T. It also changes the author-analysis first-bending frequencies from 3.9/4.0 Hz to 4.5/3.6 Hz. Both transcriptions are retained in [the source audit](isae-st3-sources.json). No scalar-frequency relabeling is used to manufacture agreement.",'',
        'The primary pluck tests used upright clamped specimens between wind-tunnel runs. They were not described as evacuated tests. The stated FFT resolution is about 0.1 Hz; this is not a complete uncertainty estimate. Dunn explicitly cautions that bending/torsion labels become approximate for strongly coupled laminates.','',
        'OpenSwing modes are matched to an independent beam solution using physical shapes with kinetic-energy weights. Reference branches are followed from zero coupling in 48 increments; measured frequencies do not choose the labels. The independent beam uses cubic Hermite bending, linear torsion, rotary inertia and self-weight geometric stiffness. It imports no OpenSwing physics.','',
        '## Frequencies against primary measurements','',
        '| Layup | Branch | Measured Hz | No gravity/no air Hz | Self-weight/no air Hz | Self-weight, 0.01 m/s Hz | Last error % |',
        '|---|---|---:|---:|---:|---:|---:|']
    for row in comparisons:
        lines.append(f"| {row['name']} | {row['label']} | {row['primary_experiment_Hz']:.2f} | {row['gravity_off_air_free_Hz']:.4f} | {row['self_weight_air_free_Hz']:.4f} | {row['self_weight_small_positive_speed_Hz']:.4f} | {row['small_speed_error_percent']:+.2f} |")
    lines += ['',
        'Air-free values use 64 requested intervals per beam; air-loaded values use 32. Required distribution stations may add intervals. The 0.01 m/s column is a small-positive-speed sensitivity, not an exact zero-flow solution. Separate 0.1 m/s and 16-interval air runs quantify speed and mesh changes in the checks. No physical parameter or acceptance tolerance is fitted to measurements.','',
        '![Primary modal comparisons](isae-st3-comparison.png)','',
        '## Literal inputs and remaining setup differences','',
        'The literal uncoupled file uses 0.283 kg/m while ISAE Table 10 gives 0.231 kg/m. The negative-coupling file uses EIcc=1.29, GJ=1.2 and EInn=0 (the documented rigid-direction convention); the report gives 1.2947, 1.4 and 2.2775e4. Other extension, coupling and axis-offset differences remain. All three files share the same internal Name despite different properties, so records are identified by source path/hash. Files are not repaired or retuned.','',
        'The archived ASWING table is retained with its supplied labels. Its scalar frequencies alone cannot establish branch correspondence after the primary/secondary label conflict. Exact archived ASWING parity is not claimed. The primary plate model also includes fairing/warping effects outside this centered beam reference.','',
        '## Numerical checks and retained failures','',
        f"Component-check status: **{report['status']}**. Maximum independent 96→192-element change is {100*gates['maximum_reference_refinement']:.5f}%; maximum native 32→64 change is {100*gates['maximum_native_refinement']:.5f}%; maximum finest native/reference frequency difference is {100*gates['maximum_native_reference_error']:.5f}%. Minimum finest physical-shape assurance is {gates['minimum_finest_shape_assurance']:.9f}.",'',
        f"The difference-step comparison changes selected roots by at most {gates['maximum_difference_step_change']:.3g} relative. Independent axial self-weight shortening agrees within {gates['maximum_axial_shortening_error_m']:.3g} m. Original-pencil left/right backward errors are checked below 1e-9; shifted searches must agree within 1e-7 relative. These numerical gates do not establish experimental agreement.",'',
        'The dense constraint-reduction solver rejects all three models at its default 1e-9 rank tolerance. The uncoupled and positive-coupling models also fail at 1e-11 and 1e-12. The negative-coupling model succeeds at those two smaller tolerances and agrees with the full descriptor roots within 5.4e-14 relative. This remains a product limitation; selecting a different tolerance is not a general fix. A separate scaling probe is diagnostic only and is not integrated into the kernel.','',
        'An additional ascending-frequency-set comparison against the archived ASWING triples is retained in the checks. It can quantify differences between the three scalar frequencies without assigning disputed mode labels. It does not verify modal identity or reproduce the unknown archived startup state.','',
        'Sources and all raw outcomes: [native study](isae-st3.json), [checks and differences](isae-st3-checks.json), [primary/workbook audit](isae-st3-sources.json). Portability records are separate: [WebAssembly](isae-st3-wasm.json).','',
        '## Reproduce','', '```sh',
        '.venv/bin/python scripts/fetch-isae-validation.py',
        '.venv/bin/python scripts/fetch-isae-st3.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_isae_st3_reference.py',
        'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/verify-isae-st3.py',
        '.venv/bin/python scripts/summarize-isae-st3.py',
        '.venv/bin/python scripts/plot-isae-st3.py',
        'node scripts/test-isae-st3-wasm.mjs',
        'npm run test:browser -- tests/browser/isae-st3.spec.js',
        '```','',
        'Completed native records are cached by full source/module/input/settings identity under `.reference/isae-st3-runs`. Re-running resumes matching records; changed settings or source create new identities. Upstream scripts are read as setup evidence and never executed. The primary PDF remains excluded from distributions.','']
    if (DEST/'isae-st3-wasm.json').exists() and (DEST/'isae-st3-browser.json').exists():
        wasm=json.loads((DEST/'isae-st3-wasm.json').read_text());browser=json.loads((DEST/'isae-st3-browser.json').read_text())
        assert wasm['study_sha256']==browser['study_sha256']==report['provenance']['study_sha256']
        assert wasm['modules']==browser['kernelModules']==data['provenance']['modules']
        index=lines.index('## Reproduce')
        lines[index:index]=['## Browser and WebAssembly checks','',
            f"The [WebAssembly replay](isae-st3-wasm.json) repeats four computed points and three default dense rejections. Its maximum native frequency difference is {wasm['maximum_frequency_difference_Hz']:.3g} Hz; {wasm['physical_shape_values']:,} physical shape values are checked with phase-independent shape assurance.",'',
            'All three literal models also solve and export through the [offline browser](isae-st3-browser.json), which preserves the dense rejection. These checks verify portability, not agreement with the experiment.','']
    (DEST/'isae-st3.md').write_text('\n'.join(lines))
    print(json.dumps({k:report[k] for k in ['status','run_counts','gates','checks']},indent=2))
    assert all(checks.values()),'Component gate failed; retain evidence and refine the study, not its tolerances.'


if __name__=='__main__':main()
