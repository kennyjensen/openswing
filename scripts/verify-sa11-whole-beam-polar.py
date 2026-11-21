"""Extend the fixed-endpoint SA-11 receiver comparison to all 0--5 deg rows.

One bounded production call per --case; reuse the two previously checked rows.
Rejected-state force diagnostics never become accepted loads or primary passes.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('receiver_study', ROOT/'scripts/verify-sa11-winglet-receivers.py')
STUDY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STUDY)
PRIOR = ROOT/'artifacts/isae/sa11-winglet-receivers-20261108'
read, write, sha = STUDY.read, STUDY.write, STUDY.sha
utc = lambda: datetime.now(timezone.utc).isoformat()


def prepare(out):
    assert not out.exists(), out
    previous = read(PRIOR/'analysis.json')
    pins = dict(read(PRIOR/'plan.json')['pins'])
    STUDY.check(pins)
    STUDY.check(previous['report_pins'])
    budget = read(STUDY.PRIOR/'analysis.json')
    for item in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        assert sha(ROOT/item['local_pdf']) == item['sha256']
    reused = []
    for report in previous['cases']:
        path = PRIOR/report['case']['id']/'report.json'
        reused.append(dict(alpha=report['case']['alpha'], path=str(path.relative_to(ROOT)), sha256=sha(path)))
    assert [r['alpha'] for r in reused] == [0., 1.]
    cases = []
    for i, report in enumerate(budget['cases']):
        alpha = .25*i
        if alpha in (0., 1.):
            continue
        cases.append(dict(id=f'whole-beam-a{alpha:g}', alpha=alpha, row=i, source_report=report['source_report']))
    assert len(budget['cases']) == 21 and len(cases) == 19
    for p in (Path(__file__), ROOT/'scripts/verify-sa11-winglet-receivers.py', PRIOR/'analysis.json'):
        pins[str(p.relative_to(ROOT))] = sha(p)
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out/'driver-used.py')
    write(out/'plan.json', dict(observed_utc=utc(), pins=pins, cases=cases, reused=reused,
        previous_turn='Progress: moment-only feasibility is too weak at5%; root receiver positions are unchanged and root-flow changes come through circulation.',
        protocol='All archived alpha0..5 by0.25 on the same native64 endpoints, report-derived minus4 twist and disclosed Joint correction. Existing whole-beam receivers, original sections, speed240, PG240/340.21, frozen influences, stall40/.05 and local Mach guard. Reuse0/1degrees; one new serial call for each remaining row.',
        question='Does the two-angle formal lift/drag agreement persist through the archived pre-stall interval, and where do local Mach/stall gates fail?',
        limitations='This is the disclosed report-derived alternative, not authenticated archived startup or mesh. Rejected states remain diagnostics; no complete moments, clipping, altered original targets or new primary scope/passes.',
        references='Drela steady Eqs.64-74 and150-157; Jan PartI p35 and AppendixD. Joint pylon semantics in aswing_doc.txt:820-852 retain offsets.'))
    print(json.dumps(dict(prepared=True, new_calls=19, reused_calls=2)), flush=True)


def run(out, index):
    plan = read(out/'plan.json')
    STUDY.check(plan['pins'])
    case = plan['cases'][index]
    log = out/f'{case["id"]}.stdout.txt'
    assert not log.exists(), log
    with log.open('w') as handle, contextlib.redirect_stdout(handle):
        STUDY.run(out, index)
    report = read(out/case['id']/'report.json')
    row = report['replays']['whole-new']
    print(json.dumps(dict(index=index, alpha=case['alpha'], status=report['production']['status'],
        physical_seconds=report['physical_seconds'], formal_errors_percent=report['new_formal_reference_error_percent'],
        maximum_mach=row['maximum_mach'], invalid_receivers=row['mach_rejected_receivers'],
        minimum_stall_margin_widths=row['minimum_stall_margin_widths'])), flush=True)


def summarize(out):
    plan = read(out/'plan.json')
    STUDY.check(plan['pins'])
    assert not (out/'analysis.json').exists()
    assert sha(Path(__file__)) == sha(out/'driver-used.py')
    paths = [out/r['id']/'report.json' for r in plan['cases']]
    for reused in plan['reused']:
        path = ROOT/reused['path']
        assert sha(path) == reused['sha256']
        paths.append(path)
    reports = sorted([(p, read(p)) for p in paths], key=lambda pair: pair[1]['case']['alpha'])
    assert [r['case']['alpha'] for _, r in reports] == [.25*i for i in range(21)]
    errors = dict(compensated_force_sum=0., decomposition=0., endpoint=0., velocity_replay=0.)
    rows = []
    for path, report in reports:
        for name, pin in report['artifact_sha256'].items():
            assert sha(path.parent/name) == pin, name
        assert sha(ROOT/report['source_report']) == report['source_report_sha256']
        for label, replay in report['replays'].items():
            with np.load(path.parent/f'{label}.npz') as data:
                for key in ('CL', 'CD'):
                    value = math.fsum(map(float, data[f'{key}_terms'].ravel()))
                    errors['compensated_force_sum'] = max(errors['compensated_force_sum'], abs(value-replay[f'formal_{key}']))
                assert float(data['mach'].max()) == replay['maximum_mach']
                assert int(np.count_nonzero(data['mach'] >= 1)) == replay['mach_rejected_receivers']
        for key, d in report['symmetric_decomposition'].items():
            a, b, c, e = [report['replays'][label][key] for label in ('native-old', 'whole-old', 'native-new', 'whole-new')]
            reconstructed = dict(change=e-a, receiver=.5*math.fsum([b, -a, e, -c]), circulation=.5*math.fsum([c, -a, e, -b]))
            errors['decomposition'] = max(errors['decomposition'], *(abs(v-d[k]) for k, v in reconstructed.items()))
        errors['endpoint'] = max(errors['endpoint'], report['endpoint_max_error'])
        errors['velocity_replay'] = max(errors['velocity_replay'], report['old_velocity_replay_error'], report['new_velocity_replay_error'])
        old, new = [report['replays'][label] for label in ('native-old', 'whole-new')]
        for key in ('CL', 'CD'):
            assert abs(100*(new[f'formal_{key}']/report['reference'][key]-1)-report['new_formal_reference_error_percent'][key]) < 2e-12
        rows.append(dict(alpha=report['case']['alpha'], report=str(path.relative_to(ROOT)), report_sha256=sha(path),
            reused=path.is_relative_to(PRIOR), production_status=report['production']['status'],
            physical_seconds=report['physical_seconds'], residual=report['production']['residual'],
            reference=report['reference'], old_formal_errors_percent=report['old_reference_error_percent'],
            new_formal_errors_percent=report['new_formal_reference_error_percent'],
            old_formal_CD=old['formal_CD'], new_formal_CD=new['formal_CD'], new_formal_CL=new['formal_CL'],
            old_maximum_mach=old['maximum_mach'], new_maximum_mach=new['maximum_mach'],
            invalid_receivers=new['mach_rejected_receivers'], worst_receiver=new['maximum'],
            minimum_stall_margin_widths=new['minimum_stall_margin_widths'], CD_terms=new['CD_terms'],
            gamma_change_relative_linf=report['gamma_change_relative_linf'],
            drag_receiver_share_percent=report['symmetric_decomposition']['formal_CD']['receiver_share_percent']))
    assert max(errors['compensated_force_sum'], errors['decomposition']) < 2e-14
    assert errors['endpoint'] < 2e-14 and errors['velocity_replay'] < 3e-9
    result = dict(observed_utc=utc(), cases=rows, verification_errors=errors,
        source_pins_verified=len(plan['pins']), new_physical_calls=19, reused_physical_calls=2,
        new_physical_seconds=sum(r['physical_seconds'] for r in rows if not r['reused']),
        production_statuses={status:sum(r['production_status'] == status for r in rows) for status in sorted({r['production_status'] for r in rows})},
        absolute_formal_error_ranges_percent={key:[min(abs(r['new_formal_errors_percent'][key]) for r in rows), max(abs(r['new_formal_errors_percent'][key]) for r in rows)] for key in ('CL', 'CD')},
        maximum_residual=max(r['residual'] for r in rows), minimum_stall_margin_widths=min(r['minimum_stall_margin_widths'] for r in rows),
        primary_passes_added=0, production_changes=False,
        scope='All21 report-minus4 whole-beam receiver diagnostics over0..5degrees. Fixed native endpoints. No original reference, tracked primary scope, validity gate or acceptance change.')
    write(out/'analysis.json', result)
    print(json.dumps({k:result[k] for k in ('production_statuses','new_physical_calls','new_physical_seconds','absolute_formal_error_ranges_percent','maximum_residual','minimum_stall_margin_widths','verification_errors')}), flush=True)


def plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    analysis = read(out/'analysis.json')
    plan = read(out/'plan.json')
    STUDY.check(plan['pins'])
    rows = analysis['cases']
    for row in rows:
        assert sha(ROOT/row['report']) == row['report_sha256']
    assert not (out/'whole-beam-polar.png').exists()
    palette = (ROOT/'web/plot-colors.js').read_text()
    colors = re.findall(r"'(#\w+)'", palette.split('export const plotColors')[1].split(']);')[0])
    x = [r['alpha'] for r in rows]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.2))
    for j, (label, color, setting) in enumerate([('Native receivers', colors[0], 'old'), ('Whole-beam receivers', colors[1], 'new')]):
        for ax, key in zip(axes[:2], ('CL', 'CD')):
            ax.plot(x, [r[f'{setting}_formal_errors_percent'][key] for r in rows], '.-', color=color, label=label)
        axes[2].plot(x, [r[f'{setting}_maximum_mach'] for r in rows], '.-', color=color, label=label)
    axes[0].set_ylabel('Formal CL error (%)')
    axes[1].set_ylabel('Formal CD error (%)')
    axes[2].set_ylabel('Maximum section-normal Mach')
    axes[2].axhline(1, color='#555555', linestyle='--', linewidth=1, label='Mach limit')
    for ax in axes:
        ax.set_xlabel('Aircraft angle of attack (deg)')
        ax.grid(alpha=.25)
    axes[0].legend(fontsize=8)
    axes[2].legend(fontsize=8)
    fig.suptitle('SA-11 upper winglet: fixed endpoints, documented whole-beam sampling')
    fig.text(.5, .02, 'All states remain rejected. Formal forces are diagnostic sums, not accepted loads or new passes.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .05, 1, .94))
    for ext in ('png', 'svg'):
        fig.savefig(out/f'whole-beam-polar.{ext}', dpi=160)
    plt.close(fig)
    write(out/'plot-receipt.json', dict(observed_utc=utc(), source_sha256=sha(out/'analysis.json'), script_sha256=sha(Path(__file__)),
        palette_sha256=sha(ROOT/'web/plot-colors.js'), artifacts={f'whole-beam-polar.{ext}':sha(out/f'whole-beam-polar.{ext}') for ext in ('png','svg')}))
    print(json.dumps(dict(plot='whole-beam-polar.png', cases=len(rows))), flush=True)


def main():
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true')
    action.add_argument('--case', type=int, choices=range(19))
    action.add_argument('--summarize', action='store_true')
    action.add_argument('--plot', action='store_true')
    args = p.parse_args()
    out = args.output.resolve()
    if args.prepare: prepare(out)
    elif args.case is not None: run(out, args.case)
    elif args.summarize: summarize(out)
    else: plot(out)


if __name__ == '__main__': main()
