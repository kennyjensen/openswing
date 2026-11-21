# Dense modal constraint reduction

The three literal ST-3 laminate models now solve with the dense method at the default rank setting on meshes of 8, 16 and 32 panels. The repair changes only `finite_subspace`; physical residuals, A/M assembly, material properties, mesh rules and equilibrium tolerances are unchanged.

## What changed

The previous reduction repeatedly projected the original equations onto a shrinking state space. Roundoff in small singular vectors could introduce false differentiated constraints. Reusing the original absolute derivative cutoff after a restriction could also erase real high-frequency modes. Agreement of the first few frequencies alone did not reveal that loss.

The new reduction uses column-pivoted Householder QR bases and removes established algebraic rows together with their constrained coordinates. With `U.T @ M = [R; 0]` and `U.T @ A = [A1; C]`, a null basis `N` of `C` gives the next pair `A1 @ N, R @ N`; the physical lift accumulates `Z @ N`. Every accepted eigenpair is still checked in the original full descriptor equations.

The input derivative retains its requested rank cutoff and explicit weak-inertia rejection. Projected derivatives use the smaller of that cutoff and `100 * eps * max(norm(M, 2), 1)`, so resolved physical directions contracted by prior constraints are retained. Both thresholds are exported. Constraint rank checks and singular-pencil rejection remain. This numerical rank policy does not prove reliability for every possible badly conditioned descriptor pencil.

Orthogonal QR/SVD-like descriptor transformations are documented in [SLICOT TG01FD](https://www.slicot.org/objects/software/shared/doc/TG01FD.html). The implementation here is independent; the evidence below tests its particular rank policy.

## Native checks

The study computes **21 operating points and 42 complete spectra**, containing 6,042 finite eigenvalues. Three laminates, three meshes and both zero gravity and upright self-weight give 18 vacuum points; three additional points include air at 0.01 m/s. Each point assembles A/M once and reuses them at rank settings 1e-9 and 1e-12.

| Vacuum mesh | Uncoupled and positive-coupling finite dimensions | Negative-coupling finite dimension |
|---:|---:|---:|
| 8 | 72 | 54 |
| 16 | 136 | 102 |
| 32 | 264 | 198 |

The negative-coupling input specifies one rigid bending direction. These dimensions count the complete discrete mechanical states, including stiff axial and in-plane modes; they are not a selected low-frequency mode count.

Complete spectra are identical between the two tested rank settings. The largest original-pencil left/right normwise backward error is 6.64e-13. The three physical modes agree with the earlier independent full-descriptor searches within 3.8e-13 Hz; the minimum physical shape assurance is 0.9999999999999994.

**165 native tests pass**, including analytic constrained mechanics, orthogonally mixed infinite chains through index six, unit/scaling changes, weak inertia, exact integrators, loaded wings, consistent initial disturbances, reduced models and controllers.

## Browser and WebAssembly

Eight Pyodide cases compare complete spectra and physical shapes. The maximum complete-spectrum relative difference is 2.04e-08; low-frequency differences are at most 3.69e-12 Hz. Five actual offline browser solves use the dense method and verify dimensions, physical shapes, gravity and original-pencil residuals against native results. All exported module hashes match the current 97-module kernel.

## Remaining limits

At 64 panels, the uncoupled input still requires a tighter original rank setting: the default 1e-9 produces an explicit weak-inertia diagnostic. At 1e-12 it resolves 520 finite coordinates and reproduces the three previously checked physical modes. That check covers selected roots, not the entire 64-panel spectrum. No fallback hides the rank diagnostic.

This fixes a numerical failure; it does not remove the [ST-3 experimental discrepancies and source conflicts](isae-st3.md). Measured-frequency differences still reach 21.1%, static deflection comparisons remain unfinished, and 31 of the 41 ISAE families still lack physical comparisons. Full ASWING functionality and full-suite validation remain incomplete.

## Reproduction and evidence

Run `scripts/verify-dense-staircase.py`, `scripts/verify-staircase-rank-limit.py` and `scripts/verify-staircase-transition.py` with the project Python environment. Run `node scripts/test-dense-staircase-wasm.mjs` and the Playwright test `tests/browser/isae-st3.spec.js` against the built local app. The pinned ISAE inputs and original ST-3 reference report are required.

Machine-readable evidence: [native spectra](dense-staircase.json), [rank limit](dense-staircase-rank-limit.json), [WASM](dense-staircase-wasm.json), [offline browser](dense-staircase-browser.json), [source boundary](dense-staircase-transition.json), and [aggregate checks](dense-staircase-checks.json). Raw logs, source snapshots and unsuccessful prototypes are retained in `dense-staircase-20261014-raw.zip`.
