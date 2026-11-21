"""Compare computed primary ST-4 vacuum spectra with all readable triplets.

The experiment was in air. These vacuum results are a conditional diagnostic,
not a matched-medium experimental validation or an accuracy acceptance test.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--figure', action='store_true')
    args = parser.parse_args()
    numerical_path = args.work/'primary-numerical.json'
    observation_path = args.work/'experimental-comparison-reciprocal/primary_spectral_comparison.json'
    numerical = json.loads(numerical_path.read_text())
    observations = json.loads(observation_path.read_text())
    assert numerical['complete'] and numerical['native_states']==252 and not numerical['rejected']
    assert numerical['script_sha256']==sha(ROOT/'scripts/summarize-isae-st4-primary.py')
    assert observations['provenance']['table_sha256']==sha(ROOT/'.reference/isae-st4-experiment-inputs/primary-table.json')
    assert observations['provenance']['physical_sha256']==sha(ROOT/'.reference/isae-st4-experiment-inputs/physical-setup.json')
    assert observations['method']['nearest_frequency_assignment_used'] is False
    assert observations['method']['frequency_fitting_or_input_tuning_used'] is False
    assert len(observations['observations'])==78 and len(observations['not_clear_cells'])==6
    for name, digest in numerical['report_sha256'].items():
        assert sha(Path(numerical['report_snapshots'])/name)==digest
    predictions = {}
    for row in numerical['native_rows']:
        spec = row['specification']; key=(spec['variant'],spec['position_in'],spec['icc_endpoint'],spec['panels'])
        assert key not in predictions; predictions[key]=row
    residuals = []
    for observation in observations['observations']:
        if not observation['complete_triplet']:
            assert observation['included_in_spectral_comparison'] is False
            continue
        printed = observation['printed_mode_cells']
        ordered = sorted(((cell['value_hz'],label,cell['status']) for label,cell in printed.items()))
        assert len(ordered)==3
        for endpoint in ['lower','upper']:
            for panels in [8,16,32]:
                row = predictions[observation['variant'],observation['position_in_from_root'],endpoint,panels]
                for rank, ((measured,label,confidence), frequency) in enumerate(zip(ordered,row['frequencies_Hz'][:3]),1):
                    residuals.append(dict(observation_id=observation['observation_id'],run=observation['run'],
                        configuration_id=observation['configuration_id'],phase=observation['phase'],
                        icc_endpoint=endpoint,panels=panels,spectral_rank=rank,
                        source_printed_label=label,source_cell_status=confidence,
                        observed_frequency_Hz=measured,native_frequency_Hz=frequency,
                        native_minus_observed_Hz=frequency-measured,
                        relative_discrepancy_percent=100*(frequency/measured-1),
                        source_sha256=row['source_sha256']))
    assert len(residuals)==72*2*3*3
    summaries=[]
    for endpoint in ['lower','upper']:
        for panels in [8,16,32]:
            rows=[r for r in residuals if r['icc_endpoint']==endpoint and r['panels']==panels]
            values=np.array([r['relative_discrepancy_percent'] for r in rows]);assert len(values)==216 and np.isfinite(values).all()
            summaries.append(dict(icc_endpoint=endpoint,panels=panels,scalar_comparisons=len(values),
                mean_absolute_discrepancy_percent=float(np.mean(abs(values))),
                median_absolute_discrepancy_percent=float(np.median(abs(values))),
                maximum_absolute_discrepancy_percent=float(np.max(abs(values))),
                largest_discrepancy=max(rows,key=lambda r:abs(r['relative_discrepancy_percent']))))
    report=dict(status='CONDITIONAL_NATIVE_VACUUM_EXPERIMENTAL_COMPARISON_COMPLETE',
        full_physical_validation=False,accuracy_acceptance_established=False,
        source_sha256=sha(__file__),numerical_report_sha256=sha(numerical_path),
        observation_report_sha256=sha(observation_path),modules=numerical['modules'],
        method=observations['method'],native_medium='vacuum',experiment_medium='air; density unspecified in primary frequency rows',
        all_observations=observations['observations'],not_clear_cells=observations['not_clear_cells'],
        scalar_comparisons=len(residuals),individual_spectral_residuals=residuals,summary=summaries,
        limitations=[
            'These native calculations omit still-air inertia; vacuum and test conditions differ.',
            'Sorted measured B1/B2/T triplets are compared with the computed lowest three modes. Physical mode identity is not inferred from closest measured frequencies.',
            'The bounds on one distributed inertia component do not bound all unknown fixture, pylon and section properties.',
            'Before/after readings, moderate-confidence cells and unreadable cells are retained separately. No measured frequencies are averaged or used to fit inputs.',
            'Higher-mode numerical mixing and two nonmonotonic refinement sequences remain recorded in the numerical audit.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    if args.figure:
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib import pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(12,4),constrained_layout=True)
        for rank,ax in enumerate(axes,1):
            for endpoint,color,marker in [('lower','#2171b5','o'),('upper','#b14a21','x')]:
                rows=[r for r in residuals if r['panels']==32 and r['spectral_rank']==rank and r['icc_endpoint']==endpoint]
                ax.scatter([r['observed_frequency_Hz'] for r in rows],[r['native_frequency_Hz'] for r in rows],s=22,alpha=.65,c=color,marker=marker,label=f'Icc {endpoint}')
            values=[v for r in residuals if r['spectral_rank']==rank and r['panels']==32 for v in [r['observed_frequency_Hz'],r['native_frequency_Hz']]]
            limits=[min(values)*.94,max(values)*1.04];ax.plot(limits,limits,'k--',lw=.8,label='Equal frequencies')
            ax.set(xlim=limits,ylim=limits,title=f'Frequency rank {rank}',xlabel='Primary measurement in air [Hz]',ylabel='OpenSwing vacuum, 32 panels [Hz]');ax.grid(alpha=.2)
        axes[0].legend(fontsize=8)
        fig.suptitle('Conditional ST-4 comparison: hanging wing, two inertia endpoints\nSorted complete triplets; no fitted inputs; air density and pylon details unresolved',fontsize=11)
        for suffix in ['.png','.pdf']:
            fig.savefig(args.output.with_suffix(suffix),dpi=170)
        plt.close(fig)
    print(json.dumps(dict(status=report['status'],scalar_comparisons=len(residuals),summary=summaries),indent=2))


if __name__=='__main__':
    main()
