"""Build the ISAE coverage ledger from current, source-pinned study results."""
from pathlib import Path
from collections import Counter
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/validation'


def source_continuity(studies, modules):
    """Retain original runs across the documented source transitions."""
    transition=json.loads((DEST/'reference-compatibility.json').read_text())
    modal=json.loads((DEST/'dense-staircase-transition.json').read_text())
    static=json.loads((DEST/'structural-static-transition.json').read_text())
    distributed=json.loads((DEST/'distributed-static-transition.json').read_text())
    adjoint_path=DEST/'modal-adjoint-transition.json'
    adjoint=json.loads(adjoint_path.read_text()) if adjoint_path.exists() else None
    zero_path=DEST/'zero-reference-transition.json'
    zero=json.loads(zero_path.read_text()) if zero_path.exists() else None
    after_adjoint=modules
    if zero is not None:
        assert zero['status']=='PASS_ZERO_REFERENCE_SOURCE_AND_NUMERICAL_CONTINUITY'
        assert zero['candidate_modules']==modules and zero['new_literal_imports']==64
        assert zero['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-zero-reference-transition.py').read_bytes()).hexdigest()
        for name,pin in zero['evidence_sha256'].items():assert hashlib.sha256((DEST/name).read_bytes()).hexdigest()==pin
        after_adjoint=zero['baseline_modules']
    after_endpoint=after_adjoint
    if adjoint is not None:
        assert adjoint['status']=='PASS_SPARSE_ADJOINT_SOURCE_AND_NUMERICAL_CONTINUITY'
        assert adjoint['candidate_modules']==after_adjoint
        assert adjoint['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-modal-adjoint-transition.py').read_bytes()).hexdigest()
        assert adjoint['changed_functions']=={'linear_dynamics.py':['eigensystem']}
        assert adjoint['added_functions']==['_sparse_adjoint'] and adjoint['native_pencils']==26
        for name,pin in adjoint['evidence_sha256'].items():assert hashlib.sha256((DEST/name).read_bytes()).hexdigest()==pin
        after_endpoint=adjoint['baseline_modules']
    endpoint_path=DEST/'endpoint-source-transition.json'
    endpoint=json.loads(endpoint_path.read_text()) if endpoint_path.exists() else None
    before_endpoint=modules
    if endpoint is not None:
        assert endpoint['status']=='PASS_ENDPOINT_SOURCE_BOUNDARY_AND_FULL_REGRESSION_ACCOUNTING'
        assert endpoint['candidate_modules']==after_endpoint
        assert endpoint['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-endpoint-transition.py').read_bytes()).hexdigest()
        assert endpoint['changed_functions']=={'asw.py':['Distribution.evaluate']}
        before_endpoint=endpoint['baseline_modules']
    assert transition['status']=='PASS_PARSER_EQUIVALENCE_NOT_PHYSICAL_VALIDATION'
    assert modal['status']=='PASS_SOURCE_BOUNDARY_NOT_NUMERICAL_RERUN'
    assert static['status']=='PASS_SOURCE_BOUNDARY_NOT_NUMERICAL_RERUN'
    assert distributed['status']=='PASS_SOURCE_BOUNDARY_NOT_NUMERICAL_RERUN'
    assert distributed['candidate_modules']==before_endpoint and distributed['baseline_modules']==static['candidate_modules']
    assert distributed['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-distributed-static-transition.py').read_bytes()).hexdigest()
    assert modal['candidate_modules']==static['baseline_modules']
    assert static['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-structural-static-transition.py').read_bytes()).hexdigest()
    assert modal['changed_functions']==['finite_subspace']
    assert modal['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-staircase-transition.py').read_bytes()).hexdigest()
    parser_modules=modal['baseline_modules']
    assert transition['candidate_modules']==parser_modules
    assert transition['script_sha256']==hashlib.sha256((ROOT/'scripts/verify-reference-compatibility.py').read_bytes()).hexdigest()
    old=transition['baseline_modules']
    assert set(old)==set(parser_modules) and {n for n in old if old[n]!=parser_modules[n]}=={'asw.py'}
    before={r['path']:r for r in transition['baseline_snapshot']['records']}
    after={r['path']:r for r in transition['candidate_snapshot']['records']}
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    cache=ROOT/'.reference/isae-validation'/manifest['revision']
    def inputs(node):
        found={}
        if isinstance(node,dict):
            for key,value in node.items():
                if key.endswith('.asw') and isinstance(value,dict) and 'sha256' in value:
                    found[value.get('path',key)]=value['sha256']
                else:found.update(inputs(value))
        elif isinstance(node,list):
            for value in node:found.update(inputs(value))
        return found
    records={}
    for name,study in studies.items():
        if name=='pazy-primary-comparison':
            assert study['status']=='HISTORICAL_COMPARISON_SUPERSEDED_INPUT_CONVENTION'
            records[name]=dict(status='historical_input_convention_superseded',superseded_by='pazy-loaded-comparison.json',
                basis='The primary-model correction changed derived input product signs, not solver modules. Original evidence remains reproducible; the corrected study retains its own source pins.')
            continue
        pins=study.get('modules',study.get('provenance',{}).get('modules'))
        if pins is None:
            pins={Path(k).name:v for k,v in study['source_sha256'].items() if k.startswith('openswing/')}
        if pins==modules:
            records[name]=dict(status='run_on_current_source');continue
        if zero is not None and pins==after_adjoint:
            records[name]=dict(status='original_run_preserved_before_zero_area_support',rerun_on_current_source=False,
                basis='Only zero-area parser eligibility and early aerodynamic normalization guards changed. Physical assembly is unchanged; prior studies retain original source hashes.')
            continue
        if adjoint is not None and pins==after_endpoint:
            records[name]=dict(status='original_run_preserved_before_sparse_adjoint_recovery',rerun_on_current_source=False,
                basis='Only left-vector recovery changed. Twenty-six saved Pazy modal pencils and three fresh browser cases are checked separately; earlier physical studies retain their original source hashes.')
            continue
        if endpoint is not None and pins==before_endpoint:
            records[name]=dict(status='original_run_preserved_before_exact_endpoint_repair',rerun_on_current_source=False,
                basis='Only exact segment terminal value queries changed to return the stored knot. The279 literal import outcomes and4767 sampled distributions are audited; derivatives1..3 are bitwise unchanged. Prior physical results retain original source pins and are not presented as new runs.')
            continue
        if pins==distributed['baseline_modules']:
            records[name]=dict(status='original_point_static_workflow_preserved',rerun_on_current_source=False,
                basis='The later distributed-static extension changes signed mg/Dmg classification and explicit static eligibility. Original point-load results retain their source pins; three current-source literal point-load controls are recorded in distributed-static.json.')
            continue
        if pins==static['baseline_modules']:
            records[name]=dict(status='original_run_preserved_before_static_workflow',rerun_on_current_source=False,
                basis='Signed static-weight support, inspection and pure structural static dispatch changed in three modules. Earlier results retain their original source pins; direct current-source static replays are separate.')
            continue
        if pins==parser_modules:
            records[name]=dict(status='original_modal_study_preserved',rerun_on_current_source=False,
                basis='Subsequent modal reduction and static-workflow changes are audited separately; the previous full-descriptor searches retain their original evidence.')
            continue
        assert pins==old,name
        sources=inputs(study)
        assert sources or name=='isae-p1',name
        for path,digest in sources.items():
            a,b=before['isae/'+path],after['isae/'+path]
            assert digest==a['source_sha256']==b['source_sha256'],path
            assert a['literal']==b['literal'],path
            assert hashlib.sha256((cache/path).read_bytes()).hexdigest()==digest,path
        records[name]=dict(status='original_run_preserved_with_verified_parser_continuity',
            unchanged_literal_inputs=sources,
            basis=('At the parser transition: identical complete parsed model data/diagnostics or identical import rejection; all 96 other modules unchanged.'
                   if sources else 'Isolated propeller component invokes no ASW parser; all engine modules unchanged.'),
            subsequent_change='Later modal-reduction and structural-static workflow changes are recorded in their own source audits; these prior studies are historical runs, not current numerical reruns.',
            rerun_on_current_source=False)
    return dict(report='reference-compatibility.json',
        zero_reference_transition=None if zero is None else dict(report='zero-reference-transition.json',sha256=hashlib.sha256(zero_path.read_bytes()).hexdigest()),
        adjoint_transition=None if adjoint is None else dict(report='modal-adjoint-transition.json',sha256=hashlib.sha256(adjoint_path.read_bytes()).hexdigest()),
        endpoint_transition=None if endpoint is None else dict(report='endpoint-source-transition.json',sha256=hashlib.sha256(endpoint_path.read_bytes()).hexdigest()),
        sha256=hashlib.sha256((DEST/'reference-compatibility.json').read_bytes()).hexdigest(),
        modal_transition=dict(report='dense-staircase-transition.json',sha256=hashlib.sha256((DEST/'dense-staircase-transition.json').read_bytes()).hexdigest()),
        static_transition=dict(report='structural-static-transition.json',sha256=hashlib.sha256((DEST/'structural-static-transition.json').read_bytes()).hexdigest()),
        distributed_transition=dict(report='distributed-static-transition.json',sha256=hashlib.sha256((DEST/'distributed-static-transition.json').read_bytes()).hexdigest()),studies=records)


def main():
    inventory=json.loads((DEST/'isae-suite-inventory.json').read_text())
    modules={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'openswing').glob('*.py'))}
    assert modules==inventory['kernel_modules']
    study_names=['isae-sa1-current','isae-sa2-current','isae-sa34','isae-sa5','isae-sa6','isae-sa10','isae-sa11-comparison','isae-sa12','isae-sa14-comparison','isae-tandem','isae-p1','isae-st5','isae-st3','dense-staircase','isae-st3-static','structural-static-workflow','distributed-static','isae-st2-comparison','pazy-primary-comparison','pazy-loaded-comparison']
    studies={name:json.loads((DEST/(name+'.json')).read_text()) for name in study_names}
    continuity=source_continuity(studies,modules)
    physical_modules=modules
    if continuity['adjoint_transition'] is not None:
        physical_modules=json.loads((DEST/'modal-adjoint-transition.json').read_text())['baseline_modules']
    numerical_modules=modules
    if continuity['endpoint_transition'] is not None:
        numerical_modules=json.loads((DEST/'endpoint-source-transition.json').read_text())['baseline_modules']
    evidence={**{f'SA-{n}':f'isae-sa{n}-current.json' for n in [1,2]},'SA-3':'isae-sa34.json','SA-4':'isae-sa34.json','SA-5':'isae-sa5.json','SA-6':'isae-sa6.md','SA-7':'isae-tandem.json','SA-8':'isae-tandem.json','SA-10':'isae-sa10.md','P-1':'isae-p1.json','ST-5':'distributed-static.md','ST-3':'isae-st3-static.md'}
    evidence['SA-12']='isae-sa12.md'
    evidence['SA-11']='isae-sa11-comparison.md'
    evidence['SA-14']='isae-sa14-comparison.md'
    evidence['ST-2']='isae-st2-comparison.md'
    evidence['ST-4']='st4-primary-air.json'
    st2_checks=json.loads((DEST/'isae-st2-checks.json').read_text())
    assert st2_checks['status']=='PASS_ST2_COVERAGE_AUDIT_NOT_PHYSICAL_VALIDATION'
    assert st2_checks['snapshot_sha256']==hashlib.sha256((DEST/'isae-st2-comparison.json').read_bytes()).hexdigest()
    assert st2_checks['script_sha256']==hashlib.sha256((ROOT/'scripts/summarize-isae-st2.py').read_bytes()).hexdigest()
    assert st2_checks['modules']==physical_modules and st2_checks['measurement_rows']==77
    assert st2_checks['static_requests']==462 and st2_checks['computed_static_conditions']==246
    assert st2_checks['rejected_static_conditions']==0 and st2_checks['modal_conditions']==16
    assert st2_checks['literal_construction_rejections']==6 and not st2_checks['full_family_validated']
    primary_checks=json.loads((DEST/'pazy-primary-checks.json').read_text())
    assert primary_checks['status']=='PASS_HISTORICAL_PRIMARY_REPRODUCTION_SUPERSEDED_INPUT_CONVENTION'
    assert primary_checks['snapshot_sha256']==hashlib.sha256((DEST/'pazy-primary-comparison.json').read_bytes()).hexdigest()
    assert primary_checks['script_sha256']==hashlib.sha256((ROOT/'scripts/summarize-pazy-primary.py').read_bytes()).hexdigest()
    assert primary_checks['modules']==physical_modules and primary_checks['counts']['native_states']==10
    assert primary_checks['counts']['computed']==10 and primary_checks['counts']['rejected']==0
    assert primary_checks['counts']['wasm_states']==primary_checks['counts']['offline_browser_states']==6
    loaded_checks=json.loads((DEST/'pazy-loaded-checks.json').read_text())
    assert loaded_checks['status']=='PASS_CORRECTED_PAZY_NUMERICAL_CHECKS_NOT_PHYSICAL_VALIDATION'
    assert loaded_checks['snapshot_sha256']==hashlib.sha256((DEST/'pazy-loaded-comparison.json').read_bytes()).hexdigest()
    assert loaded_checks['script_sha256']==hashlib.sha256((ROOT/'scripts/summarize-pazy-loaded.py').read_bytes()).hexdigest()
    assert loaded_checks['modules']==physical_modules and not loaded_checks['full_family_validated']
    assert loaded_checks['counts']==dict(zero_gravity_modal_states=10,gravity_loaded_modal_states=16,static_states=225,independent_static_references=28,measured_static_rows=77,wasm_states=10,offline_browser_states=10)
    sa11_checks=json.loads((DEST/'isae-sa11-checks.json').read_text())
    assert sa11_checks['status']=='PASS_NUMERICAL_CHECKS_NOT_EXPERIMENTAL_VALIDATION'
    assert sa11_checks['snapshot_sha256']==hashlib.sha256((DEST/'isae-sa11-comparison.json').read_bytes()).hexdigest()
    assert sa11_checks['modules']==numerical_modules and sa11_checks['completed_requests']==5304 and sa11_checks['pending_requests']==0
    sa14_checks=json.loads((DEST/'isae-sa14-family-checks.json').read_text())
    assert sa14_checks['status']=='PASS_SA14_FAMILY_COVERAGE_AUDIT_NOT_PHYSICAL_VALIDATION'
    assert sa14_checks['snapshot_sha256']==hashlib.sha256((DEST/'isae-sa14-comparison.json').read_bytes()).hexdigest()
    assert sa14_checks['script_sha256']==hashlib.sha256((ROOT/'scripts/consolidate-isae-sa14.py').read_bytes()).hexdigest()
    assert sa14_checks['modules']==numerical_modules and sa14_checks['pending_numeric_dataset_mappings']==0
    assert sa14_checks['digitized_points']==116 and sa14_checks['archive_polar_rows']==180 and sa14_checks['archive_distribution_rows']==426
    next_steps={
        'SA-1':'Resolve near-stall drag deficit and deep-stall branch selection; recover exact ASWING startup/discretization settings.',
        'SA-2':'Reconstruct the primary 45-degree planform, reconcile pressure-only force reduction, and resolve finer-mesh branch failures.',
        'SA-3':'Reconcile experimental versus archived span/area; resolve failed branches and discretization/startup settings.',
        'SA-4':'Resolve the numerous finer-mesh continuation failures and the experimental/archived geometry mismatch.',
        'SA-5':'Recover the CFD geometry, reference area and force-axis integration convention; this is a CFD comparison, not an experiment.',
        'SA-6':'Primary angles, body/stability axes and yaw normalization are reconciled; resolve model/control geometry, section properties, omitted fuselage, remaining moment discrepancies and measurement uncertainty.',
        'SA-7':'Match tandem/canard geometry, per-surface coefficients, pressure correction and recorded trim settings.',
        'SA-8':'Reconstruct airframe inclusion and match the distinct CFD fore/hind/total lift series.',
        'SA-10':'Resolve literal joint/geometry conflicts, primary setup and uncertainty, archived moment reference, near-stall drag and growing junction velocities. All six variants are mapped; one explicit joint reconstruction and failed states are retained.',
        'SA-11':'Completed 5304-state sweep and 166 matched-lift requests retain 4077 rejected states and 128 missing roots. Resolve swept/junction flow, literal geometry, archived normalization/discretization and measurement uncertainty; PG alone does not resolve shocks.',
        'SA-12':'All six polars and 75 lift/71 drag measured points compared across three meshes; resolve archived pitch/PG/discretization, plain-wing angle datum, equivalent flap section properties, near-ground slot effects and remaining measured discrepancies.',
        'SA-14':'All116 digitized points,180 polar rows and426 load-export rows are mapped. Resolve swept-force mesh behavior, high-angle/stall errors, original incidence/geometry/section-polar provenance, archive settings, moment reference and measurement uncertainty.',
        'SA-15':'Resolve variant parsing and map joined-wing units, trim and measured load/moment conventions.',
        'P-1':'Quantify measurement uncertainty; resolve nominal/true diameter and assess CdA independently of its calibration data.',
        'AP-1':'Recover propeller RPM, input power and radial lift coordinates before comparing the slipstream-loaded wing.',
        'AP-2':'Map each engine lateral/vertical position, power and measured lift-to-drag condition.',
        'ST-2':'77 measured static rows compared using simplified and corrected primary properties. The corrected primary study adds225 static states,26 modal states,28 independent nonlinear references and10 WASM/browser replays. Resolve literal attachments, exact load/fixture geometry, intrinsic extension-torsion representation, loaded-modal reference, experimental discrepancies and uncertainty. Earlier primary inertia conversion is explicitly superseded.',
        'ST-3':'Resolve static/modal experimental discrepancies, source properties, torque conversion and measurement/setup uncertainty; extend dense rank robustness beyond checked spectra. Literal signed static files now have a checked no-airflow UI workflow.',
        'ST-4':'252 vacuum and252 assumed-density still-air states compared against672 independent solutions and72 complete primary measured triplets. Resolve measured frequency discrepancies (about9.3% mean,55% maximum), unknown air density, sectional/pylon/support properties and physical mode identity; higher modes6/7 remain mixed. One literal missing-End file remains rejected. No flutter or stock-ASWING parity claim.',
        'ST-5':'Three literal rigid-joint load cases now solve across five meshes. Resolve out-of-range attachments and rejected syntax, implement the custom link joint, and reconcile reference scaling, spline/geometry differences and experimental setup/uncertainty.',
        'AE-1':'Resolve the Pazy attachment station mismatch before matching the large-deflection operating points and measurements.',
        'AE-2':'Match each composite layup and speed/incidence condition to measured displacement and twist with mesh refinement.',
        'AE-3':'Resolve both high-pressure control-derivative mesh failures, now retained through 256 requested panels; resolve section-control provenance, fixture/stiffness and finite-control conventions; complete matched finite-control, driven-roll and reversal comparisons.',
        'AE-4':'Resolve Pazy attachment stations, then reconstruct loaded and unloaded flutter sweeps and distinguish linear onset from limit-cycle response.',
        'AE-5':'Match the low-aspect-ratio wing supports, laminate, base deformation and measured flutter boundary.',
        'AE-6':'Zero-area models now import for structural/vacuum analysis. Recover a documented positive aerodynamic reference area and reproduce the exact pylon masses, gas mixtures, hanging preload and flutter conditions; ST-4 numerical checks do not validate aeroelasticity.',
        'AE-7':'Reconstruct the low-aspect-ratio nonlinear time-response settings and compare limit-cycle amplitude/frequency with time-step and mesh refinement.',
        'FFWT-2':'Resolve rejected inputs and reproduce free-roll constraints, hinge motion and time-history sampling.',
        'FFWT-4':'Resolve rejected hinge inputs and reproduce each recorded gust, support condition and root-moment reduction.',
        'FFWT-5':'Resolve nonmonotone joint tables and reconstruct the equilibrium branch and flutter sweep.'}
    cases=[]
    for case in inventory['cases']:
        models=[m for m in inventory['models'] if m['path'] in case['model_paths']]
        count=Counter(m['status'] for m in models)
        errors=list(dict.fromkeys(m['error'] for m in models if m['status']=='rejected'))
        if case['id']=='P-1': status='archived_component_reproduced_experimental_discrepancy'
        elif case['id']=='ST-5':status='reconstructed_static_comparisons_partial'
        elif case['id']=='ST-3':status='modal_and_reconstructed_static_comparisons_partial'
        elif case['id']=='ST-4':status='modal_comparisons_partial'
        elif case['id'] in evidence:status='numerical_comparisons_partial'
        elif not models:status='no_archived_asw_reconstruction_pending'
        elif count['parsed']==0:status='blocked_at_literal_import'
        else:status='imports_available_physical_comparison_pending'
        next_step=next_steps.get(case['id'])
        if next_step is None:
            next_step=('Recover model and operating/load/measurement setup from the report and primary source.' if not models else
                       'Resolve documented legacy input semantics before reproducing the recorded loads, constraints and comparison quantities.')
        cases.append(dict(id=case['id'],name=case['name'],path=case['path'],models=len(models),parsed=count['parsed'],rejected=count['rejected'],
                          status=status,evidence=evidence.get(case['id']),first_import_errors=errors,next_step=next_step,fully_validated=False))
    counts=Counter(c['status'] for c in cases)
    report=dict(repository=inventory['repository'],revision=inventory['revision'],modules=modules,full_suite_validated=False,
        scope='All 41 families inventoried and all 279 literal models checked. Quantitative studies cover SA-1 through SA-8, SA-10 through SA-12, SA-14, isolated P-1, ST-2 explicit static/modal reconstructions, ST-3 modes/static loads, conditional primary ST-4 modes and ST-5 rigid-joint loads, including direct literal signed static files. Seventeen families have completed studies of part of their scope; 24 await completed studies. No family is fully validated. The earlier SA-12 release contained 13 partial families and 28 pending; new distributions include this current source ledger. SA-13 diagnostics remain a supplemental conditional reconstruction study.',
        released_coverage=dict(release='endpoint-20261015',partial_families=15,pending_families=26,
            note='Historical endpoint-repair release coverage. New distributions include this source ledger, which adds ST-2. This record does not certify a later build.'),
        supplemental_evidence={'SA-13':'isae-sa13.md','ST-2-primary':'pazy-loaded-comparison.md','ST-2-primary-historical':'pazy-primary-comparison.md','ST-4-numerical':'zero-reference.md','AE-3-numerical':'isae-ae3-progress.json','AE-3-mechanics':'isae-ae3-mechanics.md','AE-3-locked-control':'isae-ae3-locked-control.md','AE-3-derivative-step':'isae-ae3-derivative-step.md','AE-3-mesh-refinement':'isae-ae3-mesh-refinement.md'},
        case_status_counts=dict(counts),cases=cases,source_continuity=continuity,
        study_sha256={name+'.json':hashlib.sha256((DEST/(name+'.json')).read_bytes()).hexdigest() for name in study_names})
    (DEST/'isae-coverage.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# ISAE validation coverage','',
        'This is a coverage and failure ledger, **not a full-suite pass**. Parsing does not establish mesh construction or validate physical predictions. Every case remains short of complete experimental validation.','',
        'Earlier numerical studies retain their original source hashes. The [parser audit](reference-compatibility.json), [modal source audit](dense-staircase-transition.json), [point-static source audit](structural-static-transition.json), and [distributed-static source audit](distributed-static-transition.json) document the changes. These studies are not presented as fresh numerical reruns. The [distributed static workflow](distributed-static.md) contains literal-file solves and point-load controls. The [SA-6 study](isae-sa6.md) adds primary aileron comparisons, and the [SA-10 study](isae-sa10.md) adds winglet/tip-sail polars and matched-lift drag, with literal input conflicts, failed states and local-flow growth retained.','',
        'The [SA-12 study](isae-sa12.md) adds all six ground-effect polars, exact measured-angle calculations, three meshes, independent image-velocity checks and offline browser/WASM replays. Pose/datum and equivalent-flap section limitations remain. The completed [SA-11 comparison](isae-sa11-comparison.md) adds 5,304 states and 166 matched-lift requests with rejections and missing roots retained. The [SA-14 consolidation](isae-sa14-comparison.md) maps all116 digitized points,180 original polar rows and426 load-export rows, with conditional incidence geometry, high-angle errors and the swept-force defect retained. The [ST-2 comparison](isae-st2-comparison.md) adds77 Pazy static measurements,16 modal states, explicit setup conflicts and independent/runtime checks. The [primary ST-4 comparison](st4-primary-study.md) adds conditional vacuum/still-air comparisons with primary measurements and independent references. Seventeen families now have completed quantitative studies of part of their scope; 24 await completed studies. No family is fully validated.','',
        'The [corrected primary Pazy study](pazy-loaded-comparison.md) audits CONM2 inertia signs against original Nastran mass matrices and adds225 static states,26 modal states,28 independent nonlinear references, all77 measured static rows and10 WASM/browser replays. The [earlier primary conversion](pazy-primary-comparison.md) is explicitly superseded. A small intrinsic extension–torsion term remains projected and bounded. Numerical agreement and mesh convergence do not resolve the experimental discrepancies or establish a full physical pass.','',
        'The earlier SA-12 downloads contained13 partial families and28 pending; the endpoint-repair release contained15 and26. The pre-primary-ST-4 release contained16 and25. New distributions include this source ledger of17 partial families and24 pending. The [SA-13 conditional diagnostics](isae-sa13.md) and primary Pazy supplement do not increase either count.','',
        '| Case | Literal models parsed / total | Current evidence | Work remaining |','|---|---:|---|---|']
    labels={'modal_comparisons_partial':'Conditional primary vacuum/still-air comparisons; physical discrepancies remain',
            'archived_component_reproduced_experimental_discrepancy':'Archived propeller curves reproduced; measurement differences remain',
            'modal_and_reconstructed_static_comparisons_partial':'Modal and static comparisons, including literal static/UI support; experimental discrepancies and torque/source conflicts remain',
            'reconstructed_static_comparisons_partial':'Literal and reconstructed rigid-joint comparisons; experimental discrepancies, attachments and custom link joint remain',
            'numerical_comparisons_partial':'Numerical comparisons; setup/discrepancy limits remain',
            'no_archived_asw_reconstruction_pending':'No archived model; reconstruction pending',
            'blocked_at_literal_import':'All literal models rejected',
            'imports_available_physical_comparison_pending':'Import checked; physical comparison pending'}
    for case in cases:
        label=labels[case['status']]
        if case['evidence']:label=f"[{label}]({case['evidence']})"
        if case['id']=='ST-4':
            label='[Conditional primary vacuum/still-air comparisons; physical discrepancies remain](st4-primary-study.md)'
        if case['id']=='AE-3' and (DEST/'isae-ae3-progress.json').exists():
            label='[Source audit and numerical pilot; physical comparison pending](isae-ae3-progress.json)'
        if case['id']=='AE-3' and (DEST/'isae-ae3-mechanics.json').exists():
            label='[Unit-load comparison and primary pressure readings; aerodynamic validation pending](isae-ae3-mechanics.md)'
        if case['id']=='AE-3' and (DEST/'isae-ae3-locked-control.json').exists():
            label='[18 conditional locked-wing comparisons; numerical failures retained, physical validation pending](isae-ae3-locked-control.md)'
        lines.append(f"| {case['id']} | {case['parsed']} / {case['models']} | {label} | {case['next_step']} |")
    lines += ['', 'SA-9 is absent upstream. The 279-model total also includes numerical-convergence directories outside these case folders.', '',
              'Exact file paths and import errors are retained in [the inventory](isae-suite-inventory.json) and [the machine-readable coverage ledger](isae-coverage.json).', '']
    if continuity['endpoint_transition'] is not None:
        lines+=['The [exact-endpoint source transition](endpoint-source-transition.json) records the terminal-knot interpolation repair and completed regression accounting. Earlier studies retain their original solver hashes; none is relabelled as a fresh physical rerun on the repaired source.','']
    if continuity['adjoint_transition'] is not None:
        lines+=['The [sparse modal adjoint audit](modal-adjoint.md) checks a faster left-vector recovery on all 26 saved corrected Pazy modal matrices and three fresh offline browser cases. Physical equations and finite-root classification are unchanged. Historical studies retain their original source pins; this numerical optimization adds no fully validated family.','']
    if continuity['zero_reference_transition'] is not None:
        lines+=['The [zero-reference/ST-4 audit](zero-reference.md) accepts 64 additional literal inputs for structural/vacuum use, giving177 parsed and102 rejected models. It checks81 modal states against independent energy and continuous beam solutions, plus three WASM and three offline browser cases. Experimental setup and source discrepancies remained at that stage; ST-4 was supplemental numerical evidence and the historical16/25 family totals were unchanged.','']
    (DEST/'isae-coverage.md').write_text('\n'.join(lines))
    print(json.dumps(counts,indent=2))


if __name__=='__main__':main()
