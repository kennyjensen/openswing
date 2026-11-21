#!/usr/bin/env python3
"""Consolidate terminal AE-3 saved results and draw pressure-center comparisons.

No numerical solvers or OpenSwing modules are imported. Each --run-root contains
contract.json, batch.json and results/<case>/{status,result,...}. Supply the
original run first and extension runs afterwards. Refuse unfinished batches.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, action='append', required=True)
    parser.add_argument('--wasm-root', type=Path)
    parser.add_argument('--verify-native-only', action='store_true', help='Write only a saved-native arithmetic review; do not freeze final tables or plots.')
    parser.add_argument('--colors', type=Path, default=Path('/home/userland/aswing/web/plot-colors.js'))
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    roots = [path.resolve() for path in args.run_root]
    wasm_root = args.wasm_root.resolve() if args.wasm_root else None
    dest = args.dest.resolve()
    assert args.verify_native_only or wasm_root is not None, '--wasm-root required for final consolidation'
    initial = roots[0]
    pins, contracts, batches, statuses, directories, specifications = {}, [], [], {}, {}, {}

    def pin(path):
        data = path.read_bytes()
        pins[str(path)] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        return data

    def read(path):
        return json.loads(pin(path))

    for root in roots:
        contract = read(root/'contract.json')
        batch = read(root/'batch.json')
        assert str(batch['status']).lower() not in ('running', 'pending', 'starting'), f'Batch not terminal: {root}'
        assert len(batch['cases']) == len(contract['cases']), f'Incomplete batch: {root}'
        assert all(case.get('reaped') is True for case in batch['cases']), f'Unreaped child: {root}'
        contracts.append(contract); batches.append(batch)
        for spec in contract['cases']:
            assert spec['id'] not in statuses
            directory = root/'results'/spec['id']
            saved = read(directory/'status.json')
            assert saved['status'] in ('pass', 'failed'), f'Nonterminal native case: {directory}'
            statuses[spec['id']] = saved
            directories[spec['id']] = directory
            specifications[spec['id']] = spec
    contract = contracts[0]
    normalization = contract['normalization']
    ratio = normalization['literal_area_m2']*normalization['literal_span_m']/(normalization['primary_area_m2']*normalization['primary_span_m'])
    gates = contract['gates']
    initial_report = read(initial/'report.json')
    corrected_initial = read(initial/'report-original-gate.json')
    erratum = read(initial/'plan-erratum-01.json')
    provenance = read(initial/'control-provenance-review.json')
    extension_reports = [read(root/'report.json') for root in roots[1:]]
    extension_metadata_notes = [read(root/'metadata-note.json') for root in roots[1:] if (root/'metadata-note.json').exists()]
    # Verify every frozen input/source tree, including extension copies.
    for root, frozen in zip(roots,contracts):
        for name, expected in frozen['pins'].items():
            pin(root/name)
            assert pins[str(root/name)] == expected, str(root/name)
        source_plan = Path(frozen['source_plan']['path'])
        pin(source_plan)
        assert pins[str(source_plan)]==frozen['source_plan']['pin'], str(source_plan)

    numerical_checks, arithmetic, base_by_point, finite_groups = [], [], {}, {}
    for case_id, saved in statuses.items():
        folder = directories[case_id]
        if saved['status'] != 'pass':
            numerical_checks.append(dict(case_id=case_id, check='case completion', passed=False))
            continue
        result = read(folder/'result.json')
        verify = read(folder/'verification.json')
        obs = read(folder/'observables.json')
        condition = read(folder/'condition.json')
        spec = specifications[case_id]
        for key in ('id','observation_id','model','mode','panels','control','q_Pa','speed_m_s'):
            assert saved[key]==spec[key], (case_id,key)
        expected_condition = dict(contract['condition'],speed=spec['speed_m_s'],controls={'1':spec['control']})
        assert condition==expected_condition, f'Frozen operating condition mismatch: {case_id}'
        q = saved['q_Pa']
        denom = q*normalization['literal_area_m2']*normalization['literal_span_m']
        body_mx = result['distributed_aero_moment'][0]
        native_cl = -body_mx/denom
        primary_cl = native_cl*ratio
        comparisons = {
            'native_Cl_from_body_moment_minus_status': native_cl-saved['native_Cl'],
            'native_Cl_from_body_moment_minus_observable': native_cl-obs['native_stability_Cl'],
            'area_span_ratio_minus_observable': ratio-obs['primary_over_literal_normalization'],
            'primary_Cl_from_body_moment_minus_observable': native_cl*ratio-obs['primary_normalized_Cl'],
            'native_Cl_from_body_moment_minus_complete_result': native_cl-result['Cl'],
            'pressure_from_speed_density_minus_spec_Pa': .5*condition['density']*condition['speed']**2-q,
        }
        assert condition['alpha'] == 0 and condition['beta'] == 0
        assert obs['primary_delta_deg'] == -saved['control']
        assert math.isclose(native_cl, saved['native_Cl'], rel_tol=2e-12, abs_tol=2e-14)
        assert math.isclose(native_cl, result['Cl'], rel_tol=2e-12, abs_tol=2e-14)
        assert math.isclose(native_cl*ratio, obs['primary_normalized_Cl'], rel_tol=2e-12, abs_tol=2e-14)
        assert math.isclose(.5*condition['density']*condition['speed']**2, q, rel_tol=2e-12, abs_tol=2e-12)
        residual_path = folder/'fresh-residual.npz'
        pin(residual_path)
        with np.load(residual_path) as archive:
            fresh_residual = float(np.max(np.abs(archive['residual'])))
        assert fresh_residual == verify['fresh_physical_residual'] == saved['residual']
        numerical_checks.append(dict(case_id=case_id, check='fresh physical residual', value=fresh_residual,
                                     gate=gates['fresh_physical_residual'], passed=fresh_residual<=gates['fresh_physical_residual']))
        summary = dict(case_id=case_id, mode=saved['mode'], panels=saved['panels'],frozen_condition_matches=True,
                       native_body_Mx=body_mx, native_stability_Cl=native_cl,
                       primary_Cl=primary_cl, primary_delta_deg=-saved['control'], consistency_differences=comparisons)
        if saved['mode'] == 'base':
            derivative = read(folder/'derivatives.json')
            assert derivative['axes'] == 'stability'
            assert derivative['coefficient_rows'][3] == 'Cl'
            assert [p['name'] for p in derivative['parameters']] == ['control.1','p']
            assert np.allclose(derivative['output_rotation'],np.diag([-1.,1.,-1.]),atol=0,rtol=0)
            from_wrench = [-derivative['matrices']['distributed_aero_wrench'][3][i]/denom for i in range(2)]
            coefficient_values = derivative['matrices']['coefficients'][3]
            errors = [from_wrench[i]-coefficient_values[i] for i in range(2)]
            assert np.allclose(from_wrench, coefficient_values, rtol=2e-12, atol=2e-14)
            assert saved['Cl_control'] == coefficient_values[0] and saved['Cl_p'] == coefficient_values[1]
            assert math.isclose(saved['primary_Cl_delta'], -coefficient_values[0]*ratio, rel_tol=2e-12, abs_tol=2e-14)
            summary.update(native_Cl_F1=from_wrench[0], native_Cl_p=from_wrench[1],
                           primary_Cl_delta_per_degree=-from_wrench[0]*ratio,
                           derivative_moment_normalization_errors=errors)
            linear_residual = max(derivative['linear_residuals'])
            numerical_checks.append(dict(case_id=case_id, check='derivative linear residual', value=linear_residual,
                                         gate=gates['derivative_linear_residual'], passed=linear_residual<=gates['derivative_linear_residual']))
            base_by_point.setdefault(saved['observation_id'], []).append(saved)
        else:
            key = (saved['observation_id'],saved['panels'],abs(saved['control']))
            finite_groups.setdefault(key,{})[1 if saved['control']>0 else -1] = saved
        arithmetic.append(summary)

    finite_checks = []
    for (point, panels, step), signs in sorted(finite_groups.items()):
        if set(signs) != {-1,1}:
            finite_checks.append(dict(observation_id=point,panels=panels,h=step,passed=False,reason='Missing opposite-control solution'))
            continue
        base = next(row for row in base_by_point[point] if row['panels']==panels)
        centered = (signs[1]['native_Cl']-signs[-1]['native_Cl'])/(2*step)
        error = abs(centered-base['Cl_control'])
        limit = gates['centered_resolve_absolute']+gates['centered_resolve_relative']*abs(base['Cl_control'])
        finite_checks.append(dict(observation_id=point,panels=panels,h=step,
            centered_native_Cl_F1=centered,implicit_native_Cl_F1=base['Cl_control'],
            primary_centered_Cl_delta=-centered*ratio,absolute_difference=error,acceptance_limit=limit,
            relative_difference=error/max(abs(base['Cl_control']),1e-30),passed=error<=limit))

    rows, refinement = [], []
    for point in contract['observations']:
        bases = sorted(base_by_point.get(point['id'],[]), key=lambda case: case['panels'])
        assert len(bases)>=2, f'Missing base states: {point["id"]}'
        point_mesh = []
        for coarse, fine in zip(bases,bases[1:]):
            relative = abs(fine['Cl_control']-coarse['Cl_control'])/max(abs(fine['Cl_control']),1e-30)
            item = dict(observation_id=point['id'],coarse_case=coarse['id'],fine_case=fine['id'],
                        coarse_panels=coarse['panels'],fine_panels=fine['panels'],
                        coarse_actual_elements=coarse['actual_elements'],fine_actual_elements=fine['actual_elements'],
                        relative_change=relative,gate=gates['mesh_control_derivative_relative'],
                        passed=relative<=gates['mesh_control_derivative_relative'],
                        native_Cl_F1_coarse=coarse['Cl_control'],native_Cl_F1_fine=fine['Cl_control'],
                        native_Cl_p_coarse=coarse['Cl_p'],native_Cl_p_fine=fine['Cl_p'],
                        p_relative_change_report_only=abs(fine['Cl_p']-coarse['Cl_p'])/max(abs(fine['Cl_p']),abs(coarse['Cl_p']),1e-30))
            assert fine['actual_elements']>coarse['actual_elements']
            point_mesh.append(item); refinement.append(item)
        selected = bases[-1]
        prediction = selected['primary_Cl_delta']
        measured = point['Cl_per_degree']
        rows.append(dict(observation_id=point['id'],model=point['model'],aileron=point['aileron'],
            q_psf=point['q_psf'],q_Pa=point['q_Pa'],speed_m_s=point['speed_m_s'],
            q_psf_digitization_bounds=point['q_psf_digitization_bounds'],q_Pa_digitization_bounds=point['q_Pa_digitization_bounds'],
            measured_Cl_per_degree=measured,Cl_per_degree_digitization_bounds=point['Cl_per_degree_digitization_bounds'],
            native_signed_Cl_F1=selected['Cl_control'],native_signed_Cl_p=selected['Cl_p'],
            primary_predicted_Cl_per_degree=prediction,signed_difference_per_degree=prediction-measured,
            signed_relative_difference_percent=100*(prediction/measured-1),
            chosen_case=selected['id'],chosen_requested_panels=selected['panels'],
            chosen_actual_elements=selected['actual_elements'],chosen_actual_nodes=selected['actual_nodes'],
            chosen_adjacent_refinement=point_mesh[-1],
            centered_checks_at_chosen_mesh=[item for item in finite_checks if item['observation_id']==point['id'] and item['panels']==selected['panels']],
            inside_vertical_digitization_interval_at_center_only=point['Cl_per_degree_digitization_bounds'][0]<=prediction<=point['Cl_per_degree_digitization_bounds'][1],
            original_archive_pair=point['archive_pair']))
    assert len(rows)==18
    original_mesh = [entry for entry in refinement if entry['coarse_panels']==32 and entry['fine_panels']==64]
    for entry in original_mesh:
        recorded = next(item for item in corrected_initial['mesh_checks'] if item['observation_id']==entry['observation_id'])
        assert entry['relative_change']==recorded['relative_change'] and entry['passed']==recorded['pass_gate']

    if args.verify_native_only:
        pin(Path(__file__).resolve())
        review = dict(status='COMPLETED_SAVED_NATIVE_ARITHMETIC_REVIEW', no_new_solves=True,
            final_study_frozen=False, native_cases=len(statuses), independent_saved_array_arithmetic=arithmetic,
            numerical_case_checks=numerical_checks, centered_control_checks=finite_checks,
            all_adjacent_refinement_checks=refinement,
            coefficient_mapping='Cl_native=-Mx_aero_body/(q*S_literal*b_literal); Cl_primary=Cl_native*area_span_ratio; delta_primary=-F1, hence dCl_primary/ddelta=-dCl_native/dF1*area_span_ratio.',
            scope='Arithmetic consistency of complete saved outputs, moment derivative columns and residual arrays. Not an independent physical derivative evaluation or new solve.',input_pins=pins)
        dest.mkdir(parents=True,exist_ok=True)
        (dest/'native-arithmetic-review.json').write_text(json.dumps(review,indent=2,allow_nan=False)+'\n')
        print(json.dumps(dict(status=review['status'],native_cases=len(statuses),dest=str(dest)),indent=2))
        return

    native_closeout = read(initial/'native-closeout.json')
    assert not native_closeout['remaining_owned_live_sessions']
    assert all(session['reaped'] for session in native_closeout['owned_sessions'])
    assert native_closeout['counts']['native_states']==len(statuses)
    for name, expected in native_closeout['pins'].items():
        pin(initial/name)
        assert pins[str(initial/name)]==expected, str(initial/name)
    wasm_execution = read(wasm_root/'execution.json')
    wasm_report = read(wasm_root/'report.json')
    wasm_plan = read(wasm_root/'plan.json')
    assert wasm_execution['status'] in ('PASS','FAILURES_RETAINED'), 'WASM not terminal'
    assert len(wasm_execution['cases'])==len(wasm_plan['cases'])==4
    assert all(case['reaped'] for case in wasm_execution['cases']), 'WASM child not reaped'
    assert len(wasm_report['cases'])==4
    saved_json_review = None
    if (wasm_root/'saved-json-review.json').exists():
        saved_json_review = read(wasm_root/'saved-json-review.json')
        assert saved_json_review['status'] != 'RUNNING'
    if wasm_execution['status'] == 'FAILURES_RETAINED':
        assert saved_json_review is not None, 'Final consolidation waits for the separate persisted-JSON review'
    for item in wasm_report['cases']:
        cid = item['lifecycle']['id']
        comparison = wasm_root/'results'/cid/'comparison.json'
        if comparison.exists():
            read(comparison)
    wasm_closeout = read(wasm_root/'closeout.json')
    assert wasm_closeout['all_four_children_reaped'] and not wasm_closeout['live_handles']
    wasm_pins = read(wasm_root/'artifact-pins.json')
    for name, expected in wasm_pins.items():
        pin(wasm_root/name)
        assert pins[str(wasm_root/name)] == expected, str(wasm_root/name)
    assert saved_json_review is not None
    wasm_comparisons = [comparison for case in saved_json_review['cases']
                        for comparison in list(case['comparisons'].values())+list(case['original_fresh_vector_comparisons'].values())]
    wasm_numerics = dict(
        numeric_values_compared=sum(item['numeric_values'] for item in wasm_comparisons),
        maximum_dimensionless_tolerance_ratio=max(item['maximum_tolerance_ratio'] for item in wasm_comparisons),
        maximum_fresh_normalized_residual=max(case['fresh_residual_inf_recomputed'] for case in saved_json_review['cases']),
        maximum_derivative_linear_residual=max(case['derivative_linear_residual'] or 0 for case in saved_json_review['cases']),
        network_fetch_attempts=sum(len(case['network_fetch_attempts']) for case in saved_json_review['cases']),
        comparison_failures=sum(not item['pass'] for item in wasm_comparisons),
        original_case_failures=sum(case['status']!='PASS' for case in wasm_execution['cases']),
        separate_saved_json_case_passes=sum(case['status']=='PASS_SAVED_JSON_COMPARISON' for case in saved_json_review['cases']))
    assert wasm_numerics['numeric_values_compared']==wasm_closeout['numeric_values_compared']

    colors_text = pin(args.colors.resolve()).decode()
    color_block = re.search(r'export const plotColors = Object.freeze\(\[(.*?)\]\)',colors_text,re.S).group(1)
    colors = re.findall(r"'(#\w+)'",color_block)[:5]
    assert len(colors)==5
    counts = dict(primary_points=18,variants=5,native_cases=len(statuses),
        native_case_passes=sum(case['status']=='pass' for case in statuses.values()),
        native_base_states=sum(case['mode']=='base' for case in statuses.values()),
        native_finite_control_states=sum(case['mode']=='finite' for case in statuses.values()),
        initial_cases=len(contracts[0]['cases']),extension_cases=sum(len(c['cases']) for c in contracts[1:]),
        initial_refinement_failures=sum(not item['passed'] for item in original_mesh),
        all_adjacent_mesh_comparisons=len(refinement),finite_derivative_checks=len(finite_checks),
        finite_derivative_check_failures=sum(not item['passed'] for item in finite_checks),
        native_residual_gate_failures=sum(not item['passed'] for item in numerical_checks),
        selected_mesh_failures=sum(not row['chosen_adjacent_refinement']['passed'] for row in rows),
        wasm_equilibria=wasm_plan['expected_wasm_equilibria'],wasm_derivative_calls=wasm_plan['expected_wasm_derivative_calls'])
    numerical_failures = [dict(kind='residual_or_centered_control',**item) for item in numerical_checks+finite_checks if not item['passed']]
    numerical_failures += [dict(kind='selected_mesh_refinement',**row['chosen_adjacent_refinement'])
                           for row in rows if not row['chosen_adjacent_refinement']['passed']]
    report = dict(format='openswing-isae-ae3-locked-control',version=1,
        status='CONDITIONAL_PRESSURE_CENTER_COMPARISONS_EXPERIMENTAL_VALIDATION_PENDING',
        experimental_validation=False,fully_validated=False,coverage=dict(partial=17,pending=24,fully_validated=0,AE3='pending'),
        counts=counts,conditions=contract['condition'],normalization=normalization,
        native_run_contracts=contracts,native_batch_lifecycles=batches,native_closeout=native_closeout,
        exact_primary_area_span_ratio=ratio,
        mesh_gate_formula='abs(fine-coarse)/max(abs(fine),1e-30)',
        initial_contract_gate_record_preserved=gates,
        applied_numerical_gates=dict(gates,
            mesh_formula='abs(fine-coarse)/max(abs(fine),1e-30)',
            centered_formula='abs(D_h-D_implicit_same_mesh) <= 1e-9 + 1e-5*abs(D_implicit_same_mesh), for h=.05 and .025 at the frozen sentinels.'),
        gate_record_note='The initial contract mesh_formula transcription is retained above and corrected by the separate erratum. The 128 extension retains a copied D_implicit64 label, but its refinement.finite_checks explicitly specifies its own 128 base; the applied centered comparison uses the same mesh and unchanged numerical threshold.',
        mesh_gate_erratum=erratum,original_initial_reduction=initial_report,corrected_initial_reduction=corrected_initial,
        extension_reports=extension_reports,extension_metadata_notes=extension_metadata_notes,
        rows=rows,all_adjacent_refinement_checks=refinement,
        centered_control_checks=finite_checks,numerical_case_checks=numerical_checks,numerical_failures=numerical_failures,
        independent_saved_array_arithmetic=arithmetic,native_case_statuses=statuses,
        wasm_execution=wasm_execution,wasm=wasm_report,wasm_saved_json_review=saved_json_review,
        wasm_closeout=wasm_closeout,wasm_numerical_summary=wasm_numerics,
        control_provenance=provenance,
        plot=dict(colors=dict(zip(['20O','40O','60O','80O','95O'],colors)),
                  pressure_endpoints_evaluated=False,predictions_at_digitized_centers_only=True,
                  bounds='Horizontal and vertical bars are scan/marker digitization intervals, not experimental uncertainty or acceptance bounds.'),
        limitations=[
            'Primary plotted Cl/delta is a finite-deflection ratio. The predictions are local derivatives about F1=0; experimental amplitudes remain unknown.',
            'Experimental incidence and positive control convention remain unresolved. Alpha=beta=0 and delta_primary=-F1 are fixed conditional assumptions for the whole study, not per-point fits.',
            'Literal section slopes and stiffness are retained. Their disagreement with the ISAE report and the primary static fixture remains unresolved.',
            'Values are evaluated only at digitized pressure centers. Horizontal interval endpoints, reversal, driven zero-average-moment rolling and free-roll time response are not evaluated.',
            'The p column uses normalized stability roll p*b/(2V); its mesh change is diagnostic only, not certified by the control-derivative gate.',
            'The four Pyodide replays cover selected 64-panel cases, not every pressure point, the 128-panel extension, browser UI or original ASWING executable parity.',
            'Adjacent mesh agreement and local finite-control checks are numerical evidence, not a continuum error bound or experimental acceptance.'
        ],
        remaining=['Investigate derivative performance and retained centered-control discrepancies, then refine any remaining selected-mesh gate failures; no 256-panel extension is part of this evidence stage.',
                   'Resolve section-control provenance and finite-amplitude/incidence/sign conventions.',
                   'Reconcile mechanical specimen/fixture discrepancies.',
                   'Complete driven-roll and reversal comparisons with appropriate primary source interpretation.',
                   'Complete remaining ASWING features and full experimental validation; no coverage promotion follows from this study.'],
        coverage_decision=dict(status='pending',
            reason='The 18-point calculation is complete as a conditional local-derivative study, but the primary finite Cl/delta observable is not yet matched: finite amplitudes, incidence and positive-control convention remain unresolved.',
            partial_promotion_evidence='Recover a primary-compatible finite-control convention/amplitude, or establish from a documented applicable range that the finite-ratio/local-derivative distinction is negligible. Completing every roll/reversal study is not a prerequisite for partial coverage; matching a scientifically comparable part of the family is.',
            consistency='SA-13 remains supplemental under unresolved reconstruction/normalization. SA-6 finite-control comparisons and ST-4 frequency comparisons use the corresponding measured observable, while retaining other physical discrepancies.'),
        source_reports=dict(mechanics='isae-ae3-mechanics.md',pilot='isae-ae3-progress.json'),
        scope='Workspace saved-evidence reduction and standalone plot. No new physics solve or hosted-release certification.',input_pins=pins)
    pin(Path(__file__).resolve())
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'isae-ae3-locked-control.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    draw(rows,colors,dest)
    write_markdown(report,dest)
    print(json.dumps(dict(status=report['status'],counts=counts,numerical_failure_count=len(numerical_failures),dest=str(dest)),indent=2))


def draw(rows,colors,dest):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    variants=['20O','40O','60O','80O','95O']
    unresolved_mesh = any(not row['chosen_adjacent_refinement']['passed'] for row in rows)
    with plt.rc_context({'font.size':10,'svg.hashsalt':'isae-ae3-locked-control'}):
        fig,axes=plt.subplots(2,3,figsize=(12,7.6),constrained_layout=True)
        for axis,variant,color in zip(axes.flat,variants,colors):
            points=[row for row in rows if row['aileron']==variant]
            q=np.array([row['q_psf'] for row in points])
            measured=np.array([row['measured_Cl_per_degree'] for row in points])
            q_bounds=np.array([row['q_psf_digitization_bounds'] for row in points])
            c_bounds=np.array([row['Cl_per_degree_digitization_bounds'] for row in points])
            axis.errorbar(q,measured,xerr=np.stack([q-q_bounds[:,0],q_bounds[:,1]-q]),
                yerr=np.stack([measured-c_bounds[:,0],c_bounds[:,1]-measured]),fmt='o',
                markerfacecolor='white',markeredgecolor='#263238',markersize=5.5,
                ecolor='#667085',elinewidth=1,capsize=3,linestyle='none',zorder=2)
            axis.scatter(q,[row['primary_predicted_Cl_per_degree'] for row in points],
                marker='D',s=37,color=color,edgecolors='#333333',linewidths=.5,zorder=3)
            failed=[row for row in points if not row['chosen_adjacent_refinement']['passed']]
            if failed:
                axis.scatter([row['q_psf'] for row in failed],[row['primary_predicted_Cl_per_degree'] for row in failed],
                    marker='x',s=80,color='#263238',linewidths=1.4,zorder=4)
            axis.set_title(f'{variant[:-1]}% outboard aileron',color=color,fontweight='bold',
                           bbox=dict(facecolor='#18212b',edgecolor='none',boxstyle='round,pad=.3'))
            axis.set_xlabel('Dynamic pressure q (psf)')
            axis.set_ylabel(r'$C_l/\delta$ or local derivative (degree$^{-1}$)')
            axis.grid(alpha=.18)
            axis.ticklabel_format(axis='y',style='sci',scilimits=(-3,-3),useMathText=True)
        note=axes.flat[-1];note.axis('off')
        handles=[Line2D([],[],marker='o',color='#667085',mfc='white',mec='#263238',linestyle='none',label='Primary finite-ratio markers'),
                 Line2D([],[],marker='D',color='#333333',linestyle='none',label='Local derivative at pressure center')]
        if unresolved_mesh:
            handles.append(Line2D([],[],marker='x',color='#263238',linestyle='none',label='Selected mesh fails 1% refinement gate'))
        note.legend(handles=handles,
                    loc='upper left',frameon=False)
        note.text(.03,.68,'Horizontal and vertical bars:\nscan/marker digitization intervals.\nThey are not measurement uncertainty.\n\nPredictions only at pressure centers;\nno endpoint or reversal calculations.\n\nConditional α = β = 0, δ = −F1.\nFinite experimental δ is unknown.',
                  transform=note.transAxes,va='top',linespacing=1.5)
        fig.suptitle('AE-3 locked-wing comparison — conditional derivatives, unresolved numerical and physical discrepancies',fontsize=12)
        fig.savefig(dest/'isae-ae3-locked-control.svg',metadata={'Date':None})
        fig.savefig(dest/'isae-ae3-locked-control.png',dpi=160)
        plt.close(fig)


def write_markdown(report,dest):
    c=report['counts']; rows=report['rows']
    max_res=max(item['value'] for item in report['numerical_case_checks'] if item['check']=='fresh physical residual')
    max_dres=max(item['value'] for item in report['numerical_case_checks'] if item['check']=='derivative linear residual')
    max_mesh=max(row['chosen_adjacent_refinement']['relative_change'] for row in rows)
    selected_counts=', '.join(f'{count} points at {mesh}' for mesh,count in sorted(Counter(row['chosen_requested_panels'] for row in rows).items()))
    finite_passes=sum(item['passed'] for item in report['centered_control_checks'])
    failed_finite=[item for item in report['centered_control_checks'] if not item['passed']]
    failed_finite_description=' '.join(
        f"**{item['observation_id']} at mesh {item['panels']}, h = {item['h']:.3g}° fails:** the absolute centered-minus-implicit native derivative difference is {item['absolute_difference']:.7g} degree⁻¹, above the unchanged {item['acceptance_limit']:.7g} degree⁻¹ limit."
        for item in failed_finite)
    retained20=[item for item in failed_finite if item['observation_id']=='20O-05' and item['panels']==128]
    if len(retained20)==2:
        failed_finite_description+=' Halving h from 0.05° to 0.025° leaves the discrepancy essentially unchanged. The nonlinear equation residuals and implicit derivative linear residual pass; the cause remains unresolved.'
    lines=['# AE-3 locked-wing comparisons at primary pressure readings','',
      f"All 18 primary markers across five aileron spans now have conditional local-derivative predictions at their digitized pressure centers. This completes the authorized {c['native_cases']}-state evidence stage; **AE-3 remains pending.** These are not experimentally validated control curves or reversal predictions. The [machine-readable report](isae-ae3-locked-control.json) preserves signed coefficients, numerical failures, assumptions and source hashes; the [mechanical comparison](isae-ae3-mechanics.md) and [earlier pilot](isae-ae3-progress.json) remain separate evidence.",'',
      'The model uses α = β = 0, Mach 0, literal density 1.2256 kg/m³, frozen aerodynamic influences and literal stiffness/section slopes. One file-control unit is interpreted as one degree, with the single convention δ_primary = −F1. The moment coefficient is converted from the literal 0.185 m² reference area to the primary 0.18580608 m² area. Experimental incidence, finite control amplitudes and positive-deflection convention remain unresolved: a measured finite Cl/δ ratio is not automatically the local derivative about zero control.','',
      f"The study retains {c['initial_cases']} initial and {c['extension_cases']} additional native states ({c['native_base_states']} bases and {c['native_finite_control_states']} finite-control states). Initial 32→64 refinement has {c['initial_refinement_failures']} failures; these remain recorded. The original gate uses |fine−coarse|/max(|fine|, 10⁻³⁰) ≤ 1%; an initial denominator transcription error was corrected in a separate saved-data reduction, without rerunning states or relaxing the gate. Final selected meshes use {selected_counts} requested intervals; the largest selected adjacent change is {100*max_mesh:.4g}%, with {c['selected_mesh_failures']} selected-mesh failures. Maximum fresh and derivative residuals are {max_res:.4g} and {max_dres:.4g}. {finite_passes}/{c['finite_derivative_checks']} centered-control checks at ±0.05° and ±0.025° pass their unchanged gates; **{c['finite_derivative_check_failures']} centered-control failures remain**, separately from the mesh failures. Individual checks and their original thresholds remain in the report.",'',
      failed_finite_description,'',
      '| Point | q (psf) | Primary Cl/δ (1/deg) | Predicted derivative (1/deg) | Signed difference (1/deg) | Difference (%) | Mesh | Adjacent change (%) |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        gate_note='' if row['chosen_adjacent_refinement']['passed'] else ' **FAIL**'
        finite_note=' †' if any(not item['passed'] for item in row['centered_checks_at_chosen_mesh']) else ''
        lines.append(f"| {row['observation_id']} | {row['q_psf']:.4f} | {row['measured_Cl_per_degree']:.7f} | {row['primary_predicted_Cl_per_degree']:.7f}{finite_note} | {row['signed_difference_per_degree']:+.7f} | {row['signed_relative_difference_percent']:+.2f} | {row['chosen_requested_panels']} | {100*row['chosen_adjacent_refinement']['relative_change']:.4f}{gate_note} |")
    if c['finite_derivative_check_failures']:
        lines.extend(['','† At least one same-mesh centered-control check fails its unchanged gate; this remains a numerical discrepancy, with no assigned cause.'])
    wasm_status=report['wasm_execution']['status']
    correction=report['wasm_saved_json_review']
    w=report['wasm_numerical_summary']
    correction_text='' if correction is None else f" A separate comparison of the already saved JSON has status **{correction['status']}**. It addresses in-memory integer control keys versus persisted JSON string keys; all {w['original_case_failures']} original replay failures remain unchanged, and no physical cases were rerun. The saved comparisons pass {w['numeric_values_compared']:,} numeric values at unchanged componentwise absolute/relative gates of 2×10⁻⁸; the largest dimensionless tolerance ratio is {w['maximum_dimensionless_tolerance_ratio']:.5g}, and the largest fresh normalized residual is {w['maximum_fresh_normalized_residual']:.5g} against 10⁻⁸."
    failure_caption=' Crosses mark failed selected-mesh refinement.' if c['selected_mesh_failures'] else ''
    if failed_finite:
        failure_caption+=' '+', '.join(sorted({item['observation_id'] for item in failed_finite}))+f" also retains {len(failed_finite)} failed centered-control checks, described above."
    lines += ['', '![Primary digitization intervals and conditional predictions](isae-ae3-locked-control.svg)','',
      'Horizontal and vertical bars show digitization bounds from the scanned figure, not laboratory measurement uncertainty or an acceptance threshold. Model predictions are at the pressure centers only; neither pressure endpoints nor a reversal crossing were computed. No source measurements or model properties were fitted.'+failure_caption,'',
      'The ISAE report attributes section lift/moment control slopes 0.0581/−0.0107 per degree to XFOIL, but the literal files mix coefficients: 20O uses 0.0581/−0.0102, 40O uses 0.0686/−0.0107, and 60O/80O/95O use 0.0686/−0.0102 per degree. The specific assignments are unexplained in the inspected sources. The 20O section lift-control slope is 15.306% lower than the others; this is not a whole-wing correction factor. The primary finite-ratio markers remain separate from Pearson/Cole theoretical curves and archived ASWING/ASWING-m predictions.','',
      f"Four selected 64-panel cases were replayed in actual local Pyodide, including two complete derivative calculations; terminal replay status is **{wasm_status}**.{correction_text} Complete state/output comparisons and every retained failure are included in the report. This covers the kernel API, not the browser interface or finer-mesh extensions. It establishes no original ASWING executable parity.",'',
      'Further refinement of the remaining mesh failures will follow the derivative-performance investigation; this stage includes no 256-panel cases. Retained centered-control discrepancies also need investigation. Section-control provenance, mechanical specimen/fixture discrepancies and finite-amplitude/incidence/sign conventions remain unresolved. Driven zero-average-moment rolling and reversal comparisons are still unfinished; the diagnostic p column is not a free-roll response. AE-3 remains pending because the local derivative has not yet been shown to represent the primary finite-ratio observable. Partial coverage requires a primary-compatible finite-control convention/amplitude or documented evidence that the finite-ratio distinction is negligible; it does not require every roll/reversal subcase to be finished. Coverage stays **17 partial / 24 pending / 0 fully validated**. These workspace research results do not certify a hosted release.','']
    (dest/'isae-ae3-locked-control.md').write_text('\n'.join(lines))


if __name__=='__main__':
    main()
