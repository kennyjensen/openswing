"""Publish an audited full-cycle prefix without claiming a periodic browser pass."""
import argparse
from pathlib import Path
import json

from isae_ua1_stall_browser import ROOT, BASE, OLD, read, write, pins, verify, digest, completed
from isae_ua1_stall_periodic import summarize, GATES
from isae_ua_stall_reference import Section


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, required=True, choices=[80,160,240])
    args = parser.parse_args()
    plan = read(BASE/'plan.json')
    live = read(BASE/'live-browser.json')
    assert live['status'] == 'terminal' and live['success']
    rows = []; inputs = {}; boundaries = 0; largest = 0.; fingerprints = set()
    for index in range(args.jobs//8):
        chunk, bound = completed(f'audit-chunk{index:03d}')
        assert chunk['plan_sha256'] == digest(BASE/'plan.json')
        inputs.update(bound); inputs.update(chunk['input_sha256'])
        rows.extend(chunk['rows']); boundaries += chunk['boundary_checks']
        largest = max(largest, chunk['maximum_CPython_scaled_difference'])
        fingerprints.add(chunk['runtime_fingerprint'])
    assert len(rows) == args.jobs*8+1 and boundaries == args.jobs-1 and len(fingerprints) == 1
    cycles = args.jobs//80
    section = Section(**plan['section'])
    result = summarize(section,640,cycles,rows,read(OLD/'reference-DOP853.json'))
    reference_path = str((OLD/'reference-DOP853.json').relative_to(ROOT))
    assert digest(ROOT/reference_path) == plan['input_sha256'][reference_path]
    checks = dict(cold_waveforms=max(result['cold_error_fractions'].values()) < GATES['waveform_fraction'],
        motion=max(result['velocity_fraction'],result['position_fraction']) < GATES['motion_fraction'],
        residual=result['residual'] < GATES['residual'],
        first_rate=result['first_rate_error_fraction'] < GATES['first_rate_fraction'],
        CPython_agreement=largest < plan['gates']['CPython_scaled_difference'])
    verify({**plan['source_sha256'], **inputs})
    timings = []
    for part in range(args.jobs):
        folder = BASE/'production'/f'part{part:03d}'
        receipt = read(folder/'receipt.json')
        assert receipt['outcome'] == 'success'
        timings.append(read(folder/'report.json')['worker_seconds'])
    run_outcome = BASE/'runs'/live['run_id']/'outcome.json'
    assert read(run_outcome) == live
    inputs.update(pins([ROOT/reference_path, BASE/'plan.json', run_outcome, Path(__file__).resolve()]))
    report = dict(completed_cycles=cycles, planned_cycles=4, completed_browser_jobs=args.jobs, planned_browser_jobs=320,
        unique_states=len(rows), accepted_steps=args.jobs*8, boundary_checks=boundaries, rejected_steps=0,
        prefix_checks=checks, prefix_passed=all(checks.values()), full_study_passed=None,
        summary=result, maximum_CPython_scaled_difference=largest,
        request_seconds=dict(min=min(timings),max=max(timings),sum=sum(timings)),
        source_sha256=plan['source_sha256'], input_sha256=inputs,
        production_changed=False, native_ASWING_comparison=False, full_history_UI_validation=False,
        full_goal_complete=False, new_case_pass_count=0,
        scope='Audited cold-start prefix of the fixed four-cycle browser study; no periodic-browser pass claimed.')
    report_path = BASE/f'prefix-{args.jobs:03d}.json'
    write(report_path,report)
    assert report['prefix_passed']
    errors = result['cold_error_fractions']
    text = f'''# UA-1 repeated-stall browser study: {cycles}/4 cycles audited

The four-cycle study is **in progress**. Its first **{args.jobs*8} physical steps / {len(rows):,} unique states** pass the cold-history checks. This is a prefix of the full planned run, not a completed periodic comparison or native ASWING validation.

The actual built app worker starts from its own steady equilibrium. The setup is identical to the passing Python study: 9° mean incidence, k=0.94, peak-to-peak A/c=0.5, section limits ±1.5, stall leakage strength 40, smoothing width 0.05, and circulation lag enabled. The complete four-cycle forcing table is supplied before startup. All 136 loaded scientific modules match the retained Python source byte for byte.

Each serial request advances eight steps with a 45-second worker cap. The physical time grid remains 640 steps per cycle. Full snapshots and restart records are retained. The raw audits verify both BDF predecessors and coefficients across all **{boundaries} continuation boundaries**, with **zero rejected integration steps**.

| Quantity | Maximum cold-history error against independent equations |
|---|---:|
| Lift | {100*errors['CL']:.5f}% |
| Circulation, worst strip | {100*errors['circulation']:.5f}% |
| Circulation rate, worst strip | {100*errors['circulation_rate']:.5f}% |
| Pressure drag | {100*errors['CDp_fixed']:.5f}% |

All four waveform errors are below the unchanged 0.1% limit. Lift/circulation use peak departures from the independent pre-motion steady state; rate/pressure drag use their own reference peaks. Motion, normalized nonlinear residual and first-step rate also pass their existing limits.

Maximum scaled difference from the retained Python history is **{largest:.3e}**, below **2e-8**. The comparison covers fixed-axis lift, the complete force vector, fixed-speed pressure drag, every strip's circulation, circulation rate and section lift coefficient, and heave velocity, position and acceleration, at identical physical times. The scale is `max(1, abs(Python value))`.

The nine audit sensitivity tests pass. No production equation, solver tolerance, forcing sample, physical time step or acceptance limit changed. Worker requests took {min(timings):.2f}–{max(timings):.2f} seconds for this prefix; these timings include checkpoint restoration and transport and are not an uninterrupted solve benchmark.

**Remaining:** {320-args.jobs} browser requests, their raw-history audits, and the full four-cycle periodic accuracy/settling checks. UA-2 stall, broader physical conditions, native reference provenance, and the full ASWING feature goal remain open. This result adds no completed scientific-case or browser-periodic pass count.

[Machine-readable prefix](isae-ua1-stall-periodic-browser-prefix-20261102.json). [Full-study plan](../../artifacts/isae/ua1-stall-periodic-browser-20261102/plan.json). [Retained evidence](../../artifacts/isae/ua1-stall-periodic-browser-20261102). [Completed Python comparison](isae-ua1-stall-periodic-20261102.md).
'''
    doc = ROOT/'docs/validation/isae-ua1-stall-periodic-browser-prefix-20261102.md'
    doc.write_text(text)
    doc.with_suffix('.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    message = (f'The [UA-1 stalled browser study]({{link}}) is in progress: **{cycles}/4 cycles**, '
        f'**{args.jobs}/320 requests**, **{len(rows):,} unique states**, and **{boundaries} continuation boundaries** audited, '
        f'with zero rejected steps. Cold-history lift/circulation/rate/pressure-drag errors are '
        f'**{100*errors["CL"]:.5f}% / {100*errors["circulation"]:.5f}% / {100*errors["circulation_rate"]:.5f}% / {100*errors["CDp_fixed"]:.5f}%**. '
        f'Maximum scaled Python difference is **{largest:.3e}** (limit 2e-8). '
        'The full four-cycle browser comparison remains pending; no new periodic pass is counted. Equations and limits are unchanged.')
    marker = 'UA1-STALLED-BROWSER-PREFIX-20261102'
    for path,link in [(ROOT/'docs/validation/ISAE_STATUS.md','docs/validation/'+doc.name),
                      (ROOT/'docs/STATUS.md','validation/'+doc.name),
                      (ROOT/'docs/validation/isae-suite-backlog.md',doc.name)]:
        content = path.read_text(); old_rows = [r for r in content.splitlines() if r.startswith('| [')]
        block = f'<!-- {marker} -->\n'+message.format(link=link)+f'\n<!-- /{marker} -->'
        if '<!-- '+marker+' -->' in content:
            start = content.index('<!-- '+marker+' -->')
            end = content.index('<!-- /'+marker+' -->')+len('<!-- /'+marker+' -->')
            content = content[:start]+block+content[end:]
        else:
            first,rest = content.split('\n',1)
            content = first+'\n\n'+block+'\n'+rest
        assert [r for r in content.splitlines() if r.startswith('| [')] == old_rows
        path.write_text(content)
    write(BASE/f'prefix-{args.jobs:03d}-publication.json',dict(output_sha256=pins([
        report_path,doc,doc.with_suffix('.json'),ROOT/'docs/validation/ISAE_STATUS.md',ROOT/'docs/STATUS.md',
        ROOT/'docs/validation/isae-suite-backlog.md']),case_counts_changed=False))
    print(json.dumps(dict(prefix_passed=True,completed_cycles=cycles,completed_jobs=args.jobs,
        cold_error_percent={k:100*v for k,v in errors.items()},full_study_complete=False)),flush=True)


if __name__ == '__main__':
    main()
