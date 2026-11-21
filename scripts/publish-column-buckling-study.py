"""Publish completed column evidence; no numerical solve is performed."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/st6-column-supplement-20261103'
DEST=ROOT/'docs/validation/isae-st6-column-supplement-20261103'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
native=read(BASE/'native-assessment.json');browser=read(BASE/'browser/report.json')
assert native['status']=='PASS_ANALYTICAL_COLUMN_SUPPLEMENT' and native['cases_pass']==native['cases_total']==19
assert browser['status']=='PASS_OFFLINE_COLUMN_BUCKLING_AND_PROJECTS' and len(browser['cases'])==2
assert browser['check_counts']=={'passed':426,'total':426}
for p,value in native['pins'].items():assert sha(ROOT/p)==value,p
for record in native['records'].values():
    for p,value in record['pins'].items():assert sha(ROOT/p)==value,p
for case in browser['cases']:
    for p in [*case['native_pins'],case['result'],case['project']]:assert sha(p['path'])==p['sha256']
assert (ROOT/'examples/euler-column-project.json').read_bytes()==(BASE/'browser/n64-over/project.json').read_bytes()
for name,value in browser['modules'].items():assert sha(ROOT/'openswing'/name)==value
parity=[c['base_parity'] for c in browser['cases']]+[m[key] for c in browser['cases'] for m in c['modes'] for key in ['output_parity','right_parity','left_parity']]
summary=dict(native=native,browser=dict(status=browser['status'],checks=browser['check_counts'],
    case_seconds={c['name']:c['solve_seconds'] for c in browser['cases']},
    numeric_parity_fields=sum(p['numeric'] for p in parity),maximum_parity_allowance_fraction=max(p['maximum_fraction'] for p in parity),
    matrix_output=browser['matrix_output'],scope=browser['scope'],report_sha256=sha(BASE/'browser/report.json')),
    original_ST6_status='NO_ARCHIVED_ASWING_TARGETS_IDENTIFIED',original_native_counts_unchanged=True,
    goal_complete=False,source_policy={'beam_interpolation':'drela-segspl-v1','structural_operator':'drela-fixed-vacuum-v1'},
    production_solver_changes=False,
    example_pins={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'examples/euler-column.asw',ROOT/'examples/euler-column-project.json']},
    reference_pins={p:sha(ROOT/p) for p in ['.reference/asw_theory.pdf','.reference/asw_uns_theory.pdf']},
    publication_script_sha256=sha(Path(__file__)))
DEST.with_suffix('.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
lines=['# ST-6 analytical column supplement','',
    '**19/19 analytical cases pass**, and both converged browser cases pass. The current source beam/modal equations correctly reproduce this column’s oscillation-to-buckling transition. No production solver equation changed.', '',
    'This is a synthetic **clamped/free Euler column**, not an original ISAE model or native ASWING export. The original [ST-6 source audit](isae-st6-readiness-20261027/report.md) still applies: its fixed-fixed Euler curves and experiments have no attributable native solution. This supplement adds physics verification without changing that native status.', '',
    'The beam is 2 m long, has EIcc = 100 N m², carries a 1 kg mass exactly at its free tip, and has no distributed mass. Other deformation directions are exactly rigid. Its parameter runs from 1 to 3 to avoid implicit reflection. Bank −90° and a prescribed gravity magnitude apply the dead compressive force P along the beam; the small floating-point transverse cosine component is retained. There is no airflow or damping.', '',
    'The derivation uses [Drela’s steady equations](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf) 48, 50 and 54–56, with the point-mass inertia described in the [unsteady formulation](https://web.mit.edu/drela/Public/web/aswing/asw_uns_theory.pdf). Source PDF hashes are recorded in the machine report. No archived frequency, fitted property, or experimentally inferred load is used.', '',
    'For a continuous massless cantilever with a tip mass, the transverse beam-column equation gives the tip stiffness and modal poles:', '',
    '```text',
    'q = sqrt(P/EI),  a = qL',
    'k(P) = P q cos(a) / [sin(a) − qL cos(a)]',
    'λ² = −k(P)/m',
    'Pcr = π² EI / (4 L²) = 61.6850275068 N',
    'k(0) = 3 EI/L³',
    '```', '',
    'The published endpoint-average equations yield a separate, exact finite-grid reference. For n uniform intervals, replace the propagation angle a by `a_n = 2n atan(qL/(2n))`; the factor qL in the denominator remains the physical length. Then:', '',
    '```text',
    'Pcr,n = EI [ (2n/L) tan(π/(4n)) ]²',
    'k_n(0) = 3 EI / [ L³ (1 − 1/(4n²)) ]',
    '```', '',
    'Every computed pole matches the independent discrete expression. All 5,940 normalized displacement/rotation components pass, with maximum error **3.55e-15**. Independent multiplication of the saved full A/M matrices verifies all 76 left/right eigenvector residuals; maximum backward error is **3.98e-17**. The dense four-interval control finds exactly two finite roots. The other cases use the published full-pencil shifted method; their total finite dimension remains explicitly unclassified.', '',
    '| Load | Final intervals | Error against continuous pole magnitude | Last mesh change |',
    '|---|---:|---:|---:|']
for label,text in [('zero','0'),('half','0.5 Pcr'),('over','1.5 Pcr')]:
    row=native['refinement'][label]
    lines.append(f"| {text} | {row['fine_intervals']} | {100*row['fine_continuum_relative_error']:.5f}% | {100*row['pairs'][-1]['relative_change']:.5f}% |")
lines += ['',
    'All final continuous-reference and mesh checks meet the predeclared **0.1%** limit. Errors decrease by approximately four with each bisection. Coarse failures remain in the machine report: in particular, the 16→32 growth-rate change at 1.5 Pcr is **0.15706%**; its predeclared 32→64 extension passes at **0.03921%**.', '',
    '| Intervals | Verified critical-load bracket (N) | Bracket-center difference from Euler |',
    '|---:|---:|---:|']
for row in native['critical_load_brackets']:
    lines.append(f"| {row['intervals']} | {row['lower']:.8f}–{row['upper']:.8f} | {100*row['center_continuum_relative_error']:.5f}% |")
lines += ['',
    'Each bracket uses predeclared loads at 0.9999 and 1.0001 times the exact discrete critical load. The lower case has imaginary oscillatory roots; the upper has a positive real growing root and its negative partner. The final bracket is 0.02% wide, its center is **0.01004%** above the continuous Euler value, and its 32→64 center change is **0.03013%**. These are verified brackets, not a fitted or iteratively estimated historical critical load.', '',
    'The straight base, fresh restored residual, mass, force/moment balance, poles and full modal shapes all pass. This does not test post-buckling deflections, fixed-fixed experimental fixtures, distributed-mass columns, material yielding, local skin buckling or strut failure loads.', '',
    'The actual offline workbench solves the converged **32-interval 0.5 Pcr** case in **24.88 s** and **64-interval 1.5 Pcr** case in **53.96 s**. All **426 audit checks** pass. The complete physical bases, poles, stability labels, left/right vectors and modal output fields agree with native results after removing arbitrary eigenvector phase/scale: **57,754 numeric comparisons**, maximum error **4.85e-6** of the unchanged `2e-8 + 2e-8*abs(reference)` allowance. Desktop/mobile layout and byte-identical saved-result/project restoration pass with no restore solve. GPU rendering is disabled for this resource-bounded test.', '',
    'The browser uses its normal optional-matrix-output setting (`matrices:false`). The pinned solver only appends A/M arrays after all calculations when that flag is true. Full native matrices remain available and independently checked; browser matrix-export parity is not claimed by this supplement.', '',
    'All native jobs run serially with one BLAS thread, a 180-second child limit and a 512 MiB address-space limit. The initial 64-interval growing-mode attempt returned from the solve but exhausted that allocation while building a full JSON string, before saving the result. It is retained as an unsuccessful output attempt. Replacing only the writer with streamed JSON allowed the identical request to finish under the same limits; the successful 64-interval peak RSS is below 269 MiB. The unsaved case was retried once; no successfully retained solve was repeated.', '',
    'Open [euler-column-project.json](../../examples/euler-column-project.json) using **Project & saved cases → Open project**. It contains the exact tested cases and computed solutions. Choose **Open solution** to view saved results, or **Load case → Run analysis** to recompute. In the above-critical result, select the positive real root (+4.38017 /s) to inspect the growing mode. The literal [ASW model](../../examples/euler-column.asw) is also included.', '',
    'For a single native regression, use a new output directory and the streaming checker. Its recorded reference pins require the steady and unsteady PDFs at `.reference/asw_theory.pdf` and `.reference/asw_uns_theory.pdf`; the links above provide the public documents.', '',
    '```sh',
    'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \\',
    '  timeout 180s .venv/bin/python scripts/check-euler-column.py \\',
    '  /tmp/column-check --intervals 32 --ratio .5',
    '```', '',
    '[Machine report](isae-st6-column-supplement-20261103.json). Full plans, all native results, the retained failed attempt, exact streaming transformation, independent matrix audit and browser receipts are under `artifacts/isae/st6-column-supplement-20261103/`. Native ASWING agreement and the full project goal remain open.']
DEST.with_suffix('.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(published=str(DEST.relative_to(ROOT)),analytical_cases=19,browser_cases=2,numeric_browser_comparisons=summary['browser']['numeric_parity_fields'])))
