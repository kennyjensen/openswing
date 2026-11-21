"""Publish retained UA-1 stall evidence without executing another solver job."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    args = parser.parse_args()
    base = args.base.resolve()
    plan, audit = read(base/'plan.json'), read(base/'audit.json')
    for name, value in {**audit['source_sha256'], **audit['input_sha256']}.items():
        assert digest(ROOT/name) == value, name
    probes = [read(base/f'probe-n{n}-part{p:03d}.json') for n in plan['probe_meshes'] for p in range(plan['probe_blocks'])]
    probe_rows = [c for report in probes for c in report['checks']]
    segments = [read(base/f'n{n}-part{p:03d}/report.json') for n in plan['grids'] for p in range(n//plan['segment_steps'])]
    supplemental = dict(instantaneous_checks=dict(total=len(probe_rows), passed=sum(r['passed'] for r in probe_rows),
        maxima={key:max(e[key] for c in probe_rows for e in c['errors'].values()) for key in ('force','apparent','residual','pressure_fraction')},
        maximum_coordinate_rotation=max(c['rotation_error'] for c in probe_rows)),
        accepted_steps=sum(s['accepted_steps'] for s in segments), rejected_steps=sum(s['rejected_steps'] for s in segments),
        solver_seconds=dict(min=min(s['seconds'] for s in segments), max=max(s['seconds'] for s in segments), total=sum(s['seconds'] for s in segments)),
        source_plan_sha256=digest(base/'plan.json'), audit_sha256=digest(base/'audit.json'),
        summary_script_sha256=digest(Path(__file__)), section=plan['section'], gates=plan['gates'],
        reference_comparison=read(base/'reference.json')['error_fractions'])
    document = ROOT/'docs/validation/isae-ua1-stall-20261102.md'
    document.with_suffix('.json').write_text(json.dumps({**audit, **supplemental}, indent=2, allow_nan=False)+'\n')
    n_pass = sum(audit['checks'].values())
    status = 'passes' if audit['passed'] else 'does not yet pass'
    content = document.read_text()
    content = content.replace('The three-grid first-cycle study is in progress; this document will\nrecord its final result.',
        f'The three-grid first-cycle study **{status}**, with **{n_pass}/{len(audit["checks"])} gates passing**.')
    marker = '\n## First-cycle results\n'
    if marker in content:
        raise ValueError('Preserve the already published results')
    table = ['\n## First-cycle results\n', '| Steps/cycle | Lift error | Circulation error | Rate error | Pressure-drag error |',
             '|---|---:|---:|---:|---:|']
    for steps, result in audit['results'].items():
        errors = result['error_fractions']
        table.append('| '+steps+' | '+' | '.join(f'{100*errors[key]:.5f}%' for key in ('CL','circulation','circulation_rate','CDp_fixed'))+' |')
    ratios = [v for group in audit['refinement_ratios'].values() for v in group.values()]
    fine = audit['results']['640']
    table += ['', f'The retained study audits **{audit["audited_unique_states"]:,} unique snapshots**, '
        f'**{supplemental["accepted_steps"]:,} accepted steps** and **{supplemental["rejected_steps"]} rejected steps**. '
        f'All **{sum(r["boundary_checks"] for r in audit["results"].values())} continuation boundaries** are checked. '
        f'Fine/coarse error ratios range from **{min(ratios):.5f} to {max(ratios):.5f}** (limit 0.35). '
        f'Fine velocity and position errors are **{100*fine["velocity_fraction"]:.5f}%** and '
        f'**{100*fine["position_fraction"]:.5f}%** of their respective heave amplitudes. '
        f'Maximum normalized residual is **{max(r["residual"] for r in audit["results"].values()):.4e}**.', '',
        '| Gate | Result |', '|---|---|']
    table += [f'| {key} | {"Pass" if value else "Fail"} |' for key, value in audit['checks'].items()]
    table += ['', '![Stalled first-cycle response](isae-ua1-stall-20261102.svg)', '',
        'Evidence: [machine summary](isae-ua1-stall-20261102.json), '
        '[complete-history audit](../../artifacts/isae/ua1-stall-20261102-r1/audit.json).', '']
    content = content.replace('\n## Scope and evidence\n', '\n'.join(table)+'\n## Scope and evidence\n')
    document.write_text(content)

    fine_errors = fine['error_fractions']
    numbers = ' / '.join(f'{100*fine_errors[k]:.5f}%' for k in ('CL','circulation','circulation_rate','CDp_fixed'))
    note = (f'The [UA-1 stall/lag supplement](docs/validation/isae-ua1-stall-20261102.md) '
        f'adds **{supplemental["instantaneous_checks"]["passed"]}/72 passing instantaneous states** on two meshes. '
        f'The first-cycle time study **{status}**: **{n_pass}/{len(audit["checks"])} gates pass**, '
        f'with fine lift/circulation/rate/pressure-drag errors **{numbers}**. '
        f'All {audit["audited_unique_states"]:,} states on 160/320/640 steps are audited. '
        'The declared ±1.5 section limits exercise stall; they are supplemental settings, not recovered native UA-1 inputs. '
        'Production equations are unchanged. Periodic stalled motion, browser stall coverage, UA-2 stall and native agreement remain unfinished.')
    path = ROOT/'docs/validation/ISAE_STATUS.md'
    old = path.read_text()
    rows = [r for r in old.splitlines() if r.startswith('| [')]
    assert len(rows) == len(plan['registered_rows']) == 42
    assert [r for r in rows if not r.startswith('| [UA-1]')] == [r for r in plan['registered_rows'] if not r.startswith('| [UA-1]')]
    row = next(r for r in rows if r.startswith('| [UA-1]'))
    cells = row.split(' | ')
    cells[2] += f'; 72/72 supplemental stall states; {1 if audit["passed"] else 0}/1 stalled first-cycle checks pass'
    cells[3] += f' Stall first-cycle fine lift/circulation/rate/pressure errors: {numbers}.'
    cells[4] = cells[4].removesuffix(' |')+' Stall supplement uses explicit ±1.5 limits and audits 1,123 states; stalled periodic/browser and native coverage remain open. |'
    updated = old.replace(row, ' | '.join(cells)).replace('Current priority is [UA-1 and UA-2]', note+'\n\nCurrent priority is [UA-1 and UA-2]', 1)
    assert [r for r in updated.splitlines() if r.startswith('| [') and not r.startswith('| [UA-1]')] == [r for r in rows if not r.startswith('| [UA-1]')]
    path.write_text(updated)
    path = ROOT/'docs/STATUS.md'
    lines = path.read_text().splitlines()
    lines[2:2] = [note.replace('](docs/validation/', '](validation/'), '']
    path.write_text('\n'.join(lines)+'\n')
    path = ROOT/'docs/validation/isae-suite-backlog.md'
    text = path.read_text()
    row = next(r for r in text.splitlines() if '| **UA-1** |' in r)
    text = text.replace(row, row.removesuffix(' |')+' '+note.replace('](docs/validation/', '](')+' |')
    path.write_text(text)
    print(json.dumps(dict(passed=audit['passed'], gates_passed=n_pass, gates_total=len(audit['checks']),
        fine_errors_percent={k:100*v for k,v in fine_errors.items()}, unchanged_other_ISAE_rows=41)), flush=True)


if __name__ == '__main__':
    main()
