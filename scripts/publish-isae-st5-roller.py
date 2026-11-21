"""Publish completed original ST5 roller comparisons without another solve."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'artifacts/isae/st5-roller-20261103'
NAME='isae-st5-roller-20261103'


def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def main():
    assessment=read(STAGE/'assessment.json'); browser=read(STAGE/'browser/report.json')
    assert assessment['physical_solves_passed']==assessment['fresh_restored_residuals_passed']==12
    assert assessment['qualified_matches_excluding_unresolved']==14708
    assert browser['status']=='PASS_OFFLINE_ST5_ROLLER_AND_SAVED_PROJECT'
    assert browser['checks_passed']==browser['checks_total']==1205
    assert browser['request_counts']['solve']==1
    for pin in assessment['evidence']:
        assert sha(pin['path'])==pin['sha256'],pin['path']
    for pin in [browser['script'],browser['plan'],browser['native_summary'],browser['target'],*browser['built_assets'],
                *[p for c in browser['cases'] for p in (c['native'],c['case_plan'],c['source'],c['result'],c['project'])]]:
        assert sha(pin['path'])==pin['sha256'],pin['path']
    before=STAGE/'publication-before';before.mkdir(exist_ok=False)
    ledgers=['docs/validation/ISAE_STATUS.md','docs/STATUS.md','docs/validation/isae-suite-backlog.md',
             'docs/validation/isae-suite-backlog.json','docs/REQUIREMENTS.md']
    for name in ledgers:
        p=before/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    case=browser['cases'][0]
    examples={
        'isae-st5-roller-20lb_90_10.asw':Path(case['source']['path']),
        'isae-st5-roller-project.json':Path(case['project']['path']),
    }
    example_pins={}
    for name,source in examples.items():
        for directory in ('examples','public/examples','dist/examples'):
            dest=ROOT/directory/name;assert not dest.exists();shutil.copyfile(source,dest)
            assert dest.read_bytes()==source.read_bytes()
        example_pins[name]=dict(source=str(source.relative_to(ROOT)),sha256=sha(source))
    machine=dict(assessment=assessment,browser={k:browser[k] for k in ('status','checks_passed','checks_total','startup_seconds','total_seconds','parity','request_counts','built_assets')},
        browser_solve_seconds=case['solve_seconds'],examples=example_pins,
        source_audit_checks=dict(passed=320,total=320),production_solver_changes=False,goal_complete=False,
        evidence={'native_assessment':sha(STAGE/'assessment.json'),'browser_report':sha(STAGE/'browser/report.json'),
                  'publisher':sha(__file__)})
    write(ROOT/'docs/validation'/f'{NAME}.json',machine)
    rows=[]
    for name,c in assessment['cases'].items():
        coarse,fine=c['levels'][0],c['levels'][-1]
        qualified=sum(l['counts'][k]['matches'] for l in c['levels'] for k in ('structural','conditional_zero','input_echo'))
        vals=[coarse['errors'][k]['median_percent'] for k in ('z-z0','tw-tw0','Mc_prime')]
        vals2=[fine['errors'][k]['median_percent'] for k in ('z-z0','tw-tw0','Mc_prime')]
        rows.append(f"| {name.replace('_',' / ')} | {qualified:,}/6,480 | "+' / '.join(f'{x:.6f}%' for x in vals)+
                    ' | '+' / '.join(f'{x:.4f}%' for x in vals2)+f" | {c['mesh_changes'][-1]['passed']}/14 |")
    report='''# ST-5: four original roller-joint cases

All four archived **Link_Joint** load snapshots now have completed comparisons on three nested grids: **12 cold solves and 12 fresh restored residual checks pass**. This expands original ASWING coverage beyond the four previously tested rigid-joint snapshots. No original input, physical equation, load, material property or archived-output tolerance changed.

The most useful finding is that the archive's printed-node grids reproduce the archived response much more closely than the refined grids. Median twist differences on those initial grids are **0.00012–0.00062%**, compared with **0.38–0.60%** on the finest tested grids. This supports a substantial historical discretization contribution to the discrepancy; it does not prove the exact historical mesh or executable. Matching an archived finite-grid solution and demonstrating continuum convergence are separate questions.

The unchanged files specify **KJtype=2**. The [ASWING User Guide](https://web.mit.edu/drela/Public/web/aswing/aswing_doc.txt), Joint section, defines this as rotation matched with translation free: a roller joint. The directory name is not used to substitute a pinned joint. The four models have the same numerical inputs as their rigid-joint counterparts except for this joint type; whitespace/comments are ignored only for that source comparison. The models themselves are never rewritten.

The originals are pinned at [ISAE revision f62943d](https://github.com/rom1isae/ISAE_Aswing_Experimental_Validation/tree/f62943df20e9e4d7d9f50e070477b22426b5f865/3%20-%20Structure/CASE%20-%20ST5%20Joined%20Wing/Link_Joint). Each retained script identifies its own input/output and performs one static solve. All 320 source-decoding checks pass, including root force/moment balance, rear root geometry, shell strain/stress rounding intervals and no-flow/zero-motion metadata. Per-file exponents are read afresh; the case-specific selective exporter interpretation remains qualified because the original exporter source is unavailable.

Each grid retains all **80 rows and 27 outputs**, including duplicate traces and exact known attachment coordinates. Intervals per forward/rear beam are **38/32, 76/64 and 152/128**. Interior printed centers are prospective mesh coordinates, not fitted or recovered unrounded historical nodes. The printed 2.000999 joint ordinate and literal 2.001 attachment remain separately recorded.

The error columns below are median nonzero-reference errors for **vertical deflection / twist / chordwise bending moment**, in that order. Passing counts include every required slot on all three grids.

| Original load case | Qualified matches | Initial-grid errors: Z / twist / Mc | Finest-grid errors: Z / twist / Mc | Fine mesh checks |
|---|---:|---|---|---:|
'''+ '\n'.join(rows)+'''

The **14,708/25,920 qualified matches** comprise 3,272/13,440 structural entries, 9,600/9,600 conditional zeros and 1,836/1,920 input echoes. Conditional zeros and echoes do not independently validate structural physics. The remaining 960 `f_reac` entries stay unresolved: 42 happen to match the scalar-weight diagnostic, giving 14,750 raw printed matches, but those 42 are excluded from the qualified score. No complete 14-channel structural row matches on the finest grids. The earlier rigid baseline score of 13,833/25,920 is retained unchanged, including its original counting convention.

Only **21/56** fine-pair mesh measures pass the unchanged **0.1%** limit. The largest changes per case are 0.205–0.211%. These failures are retained; a converged nonlinear solve is not proof of spatial convergence. Further refinement may establish the continuum limit, but should not be expected to reproduce an archived coarse-grid result more closely.

Maximum fresh residual is **8.57e-14**, total-force imbalance **2.14e-14 lb**, and total-moment imbalance **1.54e-10 lb·ft**. Each roller carries exactly zero force and equal/opposite couples; rotation continuity is exact in the saved results. Maximum free relative translations on the finest grids are **0.00461–0.01265 ft**, confirming that the unconstrained translation is actually exercised. Root clamps and all original numerical gates pass. Signed weights remain static loads, not physical negative masses for dynamics.

All numerical children ran serially with one BLAS thread, a 180-second limit and a 512 MiB address-space limit. The twelve solver calls total **47.61 s**; the largest child peak RSS is below 114 MiB. No solve was retried. The independent saved-result audit rechecks all original numeric tokens/intervals, node positions, reaction mechanics and comparison counts without production imports or another solve.

The audit initially required bit-identical dimensional reactions after saved-state restoration. Ten moment components differed by one binary64 ULP due to capture/restoration/reporting scale multiplication order. That failed audit and its diagnosis are retained. The corrected audit permits at most four ULPs only for these dimensional reaction moments; forces and identity metadata remain exact, and physical/mesh/archived-output criteria are unchanged. The observed maximum is one ULP.

The actual offline browser solves the original **20 lb, 90/10 roller case** on the 152/128 grid in **3.17 s** after **17.24 s** startup. It passes **1,205/1,205 checks** and compares **66,328 numeric values** with native output; maximum absolute difference is **1.33e-11**. The existing `2e-8 + 2e-8*abs(reference)` parity allowance is unchanged. Roller forces, couples, rotations and free translations are checked independently. The saved result and project reopen byte-for-byte with no second solve. Desktop/mobile checks pass; GPU rendering is disabled, so this is not GPU-rendering validation.

Open [isae-st5-roller-project.json](../../examples/isae-st5-roller-project.json) using **Project & saved cases → Open project**, then choose **Open solution** to inspect the saved result. **Load case → Run analysis** recomputes it. The [unchanged ASW input](../../examples/isae-st5-roller-20lb_90_10.asw) is also supplied. This browser check establishes runtime parity for one tested grid, not mesh convergence or native ASWING agreement.

The next comparison work is to resolve historical node/output definitions and cover remaining forward-only, alternate loading and modal variants. The original roller models and type-2 law are now tested; they are no longer merely unexamined candidates. No whole ST-5 family or broad project requirement is complete.

The [machine report](isae-st5-roller-20261103.json) retains all per-case/per-grid errors. Full source pins, unchanged original targets, generated-verifier diffs, raw results, fresh fields, the failed audit and browser evidence are under `artifacts/isae/st5-roller-20261103/`.

To reproduce, first populate the pinned `.reference/isae-validation` archive and the cached user guide as described by the repository's validation setup. Use a new stage:

```sh
python3 scripts/verify-isae-st5-roller.py prepare --stage /tmp/st5-roller
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
  .venv/bin/python scripts/verify-isae-st5-roller.py run \\
  --stage /tmp/st5-roller --case 20lb_80_20 --level 0
```

Run levels 1 and 2 in order, then the other three case names listed by `--help`, one job at a time. `scripts/assess-isae-st5-roller.py --stage /tmp/st5-roller` audits the completed batch without solving again. Source, source-decoder and kernel pins are checked before and after each job; failed attempts cannot be overwritten.
'''
    (ROOT/'docs/validation'/f'{NAME}.md').write_text(report)
    paragraph='''<!-- ST5-ROLLER-20261103 -->
The [four original ST-5 roller cases](isae-st5-roller-20261103.md)
now complete all **12 solves and 12 fresh residual checks**, with **14,708/25,920
qualified matches**; the 960 unresolved reaction-display entries remain required.
Initial printed-node grids have median twist errors **0.00012–0.00062%**; finer
grids move away from the archived values, supporting a historical discretization
contribution without proving exact original nodes. Finest median deflection/twist
errors are **0.247–0.315% / 0.376–0.603%**; only **21/56 mesh checks** pass.
The literal type-2 joints match rotation and carry zero force while translating
freely. One offline browser case passes **1,205 checks**, full native parity and
exact save/reopen. The original rigid baseline remains unchanged. No physical
equation or archived accuracy gate changed; ST-5 is still incomplete.
<!-- /ST5-ROLLER-20261103 -->

'''
    for name in ('docs/validation/ISAE_STATUS.md','docs/STATUS.md','docs/validation/isae-suite-backlog.md'):
        p=ROOT/name;text=p.read_text();assert '<!-- ST5-ROLLER-20261103 -->' not in text
        link='validation/' if name=='docs/STATUS.md' else ''
        piece=paragraph.replace('docs/validation/',link)
        i=text.index('\n')+1;text=text[:i]+'\n'+piece+text[i:].lstrip('\n')
        if name=='docs/validation/ISAE_STATUS.md':
            lines=text.splitlines()
            index=next(i for i,line in enumerate(lines) if line.startswith('| [ST-5]'))
            lines[index]='| [ST-5](isae-st5-roller-20261103.md) | Joined-wing structure | Rigid baseline 13,833/25,920; roller 14,708/25,920 qualified matches. Rigid refinement 56/56; roller 21/56 mesh checks. | Roller initial-grid twist median 0.00012–0.00062%; finest Z 0.247–0.315%, twist 0.376–0.603%. Rigid finest Z 0.295–0.411%, twist 0.794–0.980%. | Eight original snapshots tested across rigid and roller joints. Finer roller grids move away from archived values; historical discretization/output identity remains qualified. One browser case per joint type passes native parity and save/reopen. Forward-only, alternate loads, modal variants and reaction display remain open. |'
            text='\n'.join(lines)+'\n'
        elif name.endswith('isae-suite-backlog.md'):
            lines=text.splitlines()
            index=next(i for i,line in enumerate(lines) if line.startswith('| 36 | **ST-5**'))
            lines[index]='| 36 | **ST-5** | Four rigid snapshots retain their baseline; four original type-2 roller snapshots now add 12 successful solves and 14,708/25,920 qualified matches. Roller fine mesh checks 21/56; rigid extension 56/56. One roller browser case passes 1,205 checks. | Resolve historical coordinate/exporter precision and separately establish roller continuum convergence; then bind forward-only, alternate loading and modal snapshots. Preserve the strong initial-grid agreement, every failed refinement measure and the unresolved f_reac column. |'
            text='\n'.join(lines)+'\n'
        p.write_text(text)
    ledger=read(ROOT/'docs/validation/isae-suite-backlog.json')
    family=next(f for f in ledger['families'] if f['id']=='ST-5')
    family['roller_original_comparison']=dict(report=f'docs/validation/{NAME}.json',
        original_cases=4,grids_per_case=3,completed_cold_solves=12,fresh_residuals=12,
        qualified_matches=14708,required_slots=25920,raw_printed_matches=14750,
        unresolved_f_reac_slots=960,mesh_checks_passed=21,mesh_checks_total=56,browser_checks_passed=1205,
        registry_scope='Separate completed original-model expansion; earlier default four-job rigid registry retained.',
        no_physical_equation_change=True,whole_family_complete=False)
    family['remaining_gap']='Forward-only, alternate distributed-loading and modal variants remain outside this tested expansion. Roller mesh convergence, historical unrounded nodes/exporter behavior and reaction-display conventions remain unresolved.'
    family['first_implementable_step']='Use retained initial-grid versus refined roller results to distinguish historical discretization from continuum accuracy; resolve source coordinate/output precision without fitting, and bind remaining original forward-only or alternate-loading snapshots.'
    write(ROOT/'docs/validation/isae-suite-backlog.json',ledger)
    p=ROOT/'docs/REQUIREMENTS.md';text=p.read_text()
    needle='Current work prioritizes regression comparisons across **all 41 archived ISAE'
    assert text.count(needle)==1
    text=text.replace(needle,'''The [original ST-5 roller comparisons](validation/isae-st5-roller-20261103.md)
add four unchanged ASWING snapshots on three grids, documented type-2 joint
mechanics, all output columns and one offline browser/save-restore check.
They add original-case coverage; remaining mesh and archived-output failures
are retained. No broad completion state or production equation changes.

'''+needle)
    p.write_text(text)
    write(STAGE/'publication.json',dict(examples=example_pins,report_sha256=sha(ROOT/'docs/validation'/f'{NAME}.md'),
        machine_report_sha256=sha(ROOT/'docs/validation'/f'{NAME}.json'),
        ledgers={name:sha(ROOT/name) for name in ledgers},publisher_sha256=sha(__file__)))
    print(json.dumps(dict(published=True,qualified_matches=14708,required_slots=25920,browser_checks=1205,goal_complete=False)))


if __name__=='__main__':main()
