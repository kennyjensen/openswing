"""Assemble the declared one-frequency plume diagnostic without aircraft solves."""
import argparse
from check_daedalus_load_sensitivity import ROOT, SOURCE, read, write
from check_daedalus_plume_receivers import STUDY
from daedalus_bounded_job import run


def report(folder, args):
    import csv
    import numpy as np
    channels = ['yaw_rate', 'roll_rate', 'sideslip', 'bank']
    final = read(STUDY/'nonwing-dip-3/result.json'); assert final['converged']
    check = final['samples'][-1]
    assert check['iteration'] == final['iterations'] and check['residual_relative'] < 2e-10
    assert check['next_correction_output'] < 2e-10
    frequency = final['frequency_hz']
    screen = read(STUDY/'screen-dip-v2/result.json')
    native = read(STUDY/'native-dip-v2/result.json'); assert max(native['errors'].values()) < 2e-8
    with (SOURCE/'report/comparison.csv').open() as stream:
        rows = {r['channel']: r for r in csv.DictReader(stream) if abs(float(r['frequency_hz'])-frequency)<1e-12}
    state = np.load(STUDY/'nonwing-dip-3/arrays.npz')
    maps = np.load(SOURCE/'assembled-6.7/maps.npz')
    np.testing.assert_allclose(maps['C']@state['state'], state['output'], atol=2e-15, rtol=2e-13)
    samples = []
    for i, channel in enumerate(channels):
        reference = float(rows[channel]['reference_magnitude']); original = float(rows[channel]['magnitude_display'])
        value = abs(state['output'][i])
        assert abs(value-final['output_magnitudes'][i]) < 2e-15
        assert abs(original-screen['original_magnitudes'][i]) < 2e-15
        samples.append(dict(channel=channel, frequency_hz=frequency, drawing_magnitude=reference,
            current_magnitude=original, conditional_magnitude=float(value),
            change_percent=float(100*(value/original-1)),
            current_drawing_error_percent=100*(original/reference-1),
            conditional_drawing_error_percent=float(100*(value/reference-1))))
    with (folder/'comparison.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(samples[0])); writer.writeheader(); writer.writerows(samples)
    terminals = [read(p) for p in sorted(STUDY.glob('*/terminal.json'))]
    assert len(terminals) == 8 and all(t['process_reaped'] and not t['timed_out'] and t['inputs_unchanged'] for t in terminals)
    assert sum(t['returncode']==0 for t in terminals) == 6
    source = read(ROOT/'reference/daedalus-plume-receivers-20261114/receipt.json')
    assert source['matches_retained_notes']
    result = dict(frequency_hz=frequency, comparison=samples,
        full_modified_residual_relative=check['residual_relative'], correction_output=check['next_correction_output'],
        native_comparison=native, source_receipt=source,
        scope='One-frequency, fixed-equilibrium affine diagnostic. Only the wing retains plume flow among beams; point-drag plume and engine loading remain active. Neither a retrimmed aircraft nor a recreation of the undocumented historical defect.',
        prior_jobs=8, prior_successes=6, prior_failures=2,
        reference_uncertainty='Errors are relative to digitized central curves, not uncertainty-adjusted pass counts. No reference acceptance is claimed.',
        maximum_cpu_seconds=max(t['cpu_seconds'] for t in terminals),
        maximum_wall_seconds=max(t['wall_seconds'] for t in terminals),
        maximum_rss_kib=max(t['peak_rss_kib'] for t in terminals))
    print(samples, flush=True); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--tag', required=True)
    args = vars(parser.parse_args())
    inputs = [ROOT/'scripts/check_daedalus_plume_receivers.py', SOURCE/'report/comparison.csv',
        SOURCE/'assembled-6.7/maps.npz', ROOT/'reference/daedalus-plume-receivers-20261114/receipt.json',
        ROOT/'reference/daedalus-plume-receivers-20261114/version_notes.txt',
        ROOT/'docs/validation/ISAE_STATUS.md', ROOT/'docs/validation/aswing-authoritative-sources.json']
    for tag in ('screen-dip-v2', 'nonwing-dip-3', 'native-dip-v2'):
        inputs += [STUDY/tag/name for name in ('arrays.npz', 'result.json')]
    inputs += list(STUDY.glob('*/terminal.json'))
    run(STUDY, args['tag'], inputs, report, args, __file__)


if __name__ == '__main__': main()
