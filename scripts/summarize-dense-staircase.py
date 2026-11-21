"""Audit and summarize the native, WASM and offline modal regression evidence."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'docs/validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--test-log',type=Path,required=True);args=parser.parse_args()
native=json.loads((DEST/'dense-staircase.json').read_text())
wasm=json.loads((DEST/'dense-staircase-wasm.json').read_text())
browser=json.loads((DEST/'dense-staircase-browser.json').read_text())
limit=json.loads((DEST/'dense-staircase-rank-limit.json').read_text())
transition=json.loads((DEST/'dense-staircase-transition.json').read_text())
modules={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
assert native['status']=='PASS_ST3_COMPLETE_SPECTRA_AND_PHYSICAL_MODES' and len(native['runs'])==21
assert native['modules']==wasm['modules']==browser['kernelModules']==limit['modules']==transition['candidate_modules']==modules
assert wasm['status']==browser['status']=='PASS' and len(wasm['cases'])==8 and len(browser['cases'])==5
assert wasm['study_sha256']==browser['study_sha256']==sha(DEST/'dense-staircase.json')
assert browser['test_sha256']==sha(ROOT/'tests/browser/isae-st3.spec.js')
assert native['script_sha256']==sha(ROOT/'scripts/verify-dense-staircase.py')
assert wasm['script_sha256']==sha(ROOT/'scripts/test-dense-staircase-wasm.mjs')
assert limit['script_sha256']==sha(ROOT/'scripts/verify-staircase-rank-limit.py')
assert transition['script_sha256']==sha(ROOT/'scripts/verify-staircase-transition.py')
assert browser['offline'] and browser['complete_dimensions_verified']
test_result=re.search(r'(\d+) passed in ([^\n]+)',args.test_log.read_text())
assert test_result and 'failed' not in args.test_log.read_text()
comparisons=[c for r in native['runs'] for c in r['previous_full_descriptor_comparison']]
checks=dict(status='PASS',kernel_modules=modules,native_operating_points=len(native['runs']),complete_spectra=2*len(native['runs']),
    total_finite_eigenvalues=sum(len(s['eigenvalues']) for r in native['runs'] for s in r['result']['spectra']),
    maximum_rank_refinement_relative_difference=max(r['result']['complete_spectrum_rank_refinement_error'] for r in native['runs']),
    maximum_previous_frequency_difference_Hz=max(c['frequency_difference_Hz'] for c in comparisons),
    minimum_previous_shape_assurance=min(c['physical_shape_assurance'] for c in comparisons),
    maximum_original_pencil_backward_error=max(max(s['right_backward_errors']+s['left_backward_errors']) for r in native['runs'] for s in r['result']['spectra']),
    tests=dict(passed=int(test_result[1]),time=test_result[2],log_sha256=sha(args.test_log)),
    wasm_cases=len(wasm['cases']),browser_cases=len(browser['cases']),
    evidence_sha256={p.name:sha(p) for p in [DEST/(n+'.json') for n in ['dense-staircase','dense-staircase-wasm','dense-staircase-browser','dense-staircase-rank-limit','dense-staircase-transition']]},
    script_sha256=sha(Path(__file__)),full_suite_validated=False,goal_complete=False)
lines=['# Dense modal constraint reduction','',
 'The three literal ST-3 laminate models now solve with the dense method at the default rank setting on meshes of 8, 16 and 32 panels. The repair changes only `finite_subspace`; physical residuals, A/M assembly, material properties, mesh rules and equilibrium tolerances are unchanged.','',
 '## What changed','',
 'The previous reduction repeatedly projected the original equations onto a shrinking state space. Roundoff in small singular vectors could introduce false differentiated constraints. Reusing the original absolute derivative cutoff after a restriction could also erase real high-frequency modes. Agreement of the first few frequencies alone did not reveal that loss.','',
 'The new reduction uses column-pivoted Householder QR bases and removes established algebraic rows together with their constrained coordinates. With `U.T @ M = [R; 0]` and `U.T @ A = [A1; C]`, a null basis `N` of `C` gives the next pair `A1 @ N, R @ N`; the physical lift accumulates `Z @ N`. Every accepted eigenpair is still checked in the original full descriptor equations.','',
 'The input derivative retains its requested rank cutoff and explicit weak-inertia rejection. Projected derivatives use the smaller of that cutoff and `100 * eps * max(norm(M, 2), 1)`, so resolved physical directions contracted by prior constraints are retained. Both thresholds are exported. Constraint rank checks and singular-pencil rejection remain. This numerical rank policy does not prove reliability for every possible badly conditioned descriptor pencil.','',
 'Orthogonal QR/SVD-like descriptor transformations are documented in [SLICOT TG01FD](https://www.slicot.org/objects/software/shared/doc/TG01FD.html). The implementation here is independent; the evidence below tests its particular rank policy.','',
 '## Native checks','',
 f"The study computes **21 operating points and 42 complete spectra**, containing {checks['total_finite_eigenvalues']:,} finite eigenvalues. Three laminates, three meshes and both zero gravity and upright self-weight give 18 vacuum points; three additional points include air at 0.01 m/s. Each point assembles A/M once and reuses them at rank settings 1e-9 and 1e-12.",'',
 '| Vacuum mesh | Uncoupled and positive-coupling finite dimensions | Negative-coupling finite dimension |','|---:|---:|---:|','| 8 | 72 | 54 |','| 16 | 136 | 102 |','| 32 | 264 | 198 |','',
 'The negative-coupling input specifies one rigid bending direction. These dimensions count the complete discrete mechanical states, including stiff axial and in-plane modes; they are not a selected low-frequency mode count.','',
 f"Complete spectra are identical between the two tested rank settings. The largest original-pencil left/right normwise backward error is {checks['maximum_original_pencil_backward_error']:.3g}. The three physical modes agree with the earlier independent full-descriptor searches within {checks['maximum_previous_frequency_difference_Hz']:.3g} Hz; the minimum physical shape assurance is {checks['minimum_previous_shape_assurance']:.16f}.",'',
 f"**{checks['tests']['passed']} native tests pass**, including analytic constrained mechanics, orthogonally mixed infinite chains through index six, unit/scaling changes, weak inertia, exact integrators, loaded wings, consistent initial disturbances, reduced models and controllers.",'',
 '## Browser and WebAssembly','',
 f"Eight Pyodide cases compare complete spectra and physical shapes. The maximum complete-spectrum relative difference is {wasm['maximum_complete_spectrum_relative_difference']:.3g}; low-frequency differences are at most {wasm['maximum_low_frequency_difference_Hz']:.3g} Hz. Five actual offline browser solves use the dense method and verify dimensions, physical shapes, gravity and original-pencil residuals against native results. All exported module hashes match the current 97-module kernel.",'',
 '## Remaining limits','',
 'At 64 panels, the uncoupled input still requires a tighter original rank setting: the default 1e-9 produces an explicit weak-inertia diagnostic. At 1e-12 it resolves 520 finite coordinates and reproduces the three previously checked physical modes. That check covers selected roots, not the entire 64-panel spectrum. No fallback hides the rank diagnostic.','',
 'This fixes a numerical failure; it does not remove the [ST-3 experimental discrepancies and source conflicts](isae-st3.md). Measured-frequency differences still reach 21.1%, static deflection comparisons remain unfinished, and 31 of the 41 ISAE families still lack physical comparisons. Full ASWING functionality and full-suite validation remain incomplete.','',
 '## Reproduction and evidence','',
 'Run `scripts/verify-dense-staircase.py`, `scripts/verify-staircase-rank-limit.py` and `scripts/verify-staircase-transition.py` with the project Python environment. Run `node scripts/test-dense-staircase-wasm.mjs` and the Playwright test `tests/browser/isae-st3.spec.js` against the built local app. The pinned ISAE inputs and original ST-3 reference report are required.','',
 'Machine-readable evidence: [native spectra](dense-staircase.json), [rank limit](dense-staircase-rank-limit.json), [WASM](dense-staircase-wasm.json), [offline browser](dense-staircase-browser.json), [source boundary](dense-staircase-transition.json), and [aggregate checks](dense-staircase-checks.json). Raw logs, source snapshots and unsuccessful prototypes are retained in `dense-staircase-20261014-raw.zip`.','']
(DEST/'dense-staircase-checks.json').write_text(json.dumps(checks,indent=2)+'\n')
(DEST/'dense-staircase.md').write_text('\n'.join(lines))
print(json.dumps({k:v for k,v in checks.items() if k not in ('kernel_modules','evidence_sha256')},indent=2))
