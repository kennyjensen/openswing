# ST-4 finer spatial convergence and sparse modal matrices

Study started 2026-11-03; assessment and delivery completed 2026-11-04.

The original Weight7a flowing-air pilot now passes **12/12 tracked component
mesh checks** from 96 to 128 cosine intervals, at the unchanged **0.1%** limit.
It still matches only **1/12 archived scalar components**, solely the near-zero
imaginary part of a real root; **0/6 complete roots** match at half the printed
decimal precision. The lowest oscillation-frequency error remains **11.51%**.
This establishes the registered mesh gate for this pilot, not native ASWING
agreement or convergence of the complete spectrum.

## Fixed scope and results

The literal `Weight7a/7a_b17.asw` input, speed 120, density 1.0771417304,
zero incidence/sideslip, Mach zero, gravity 9.81 in Earth −z, fixed perturbation
frame, active aerodynamic lag and stall law, and live influence geometry are
unchanged. The same published moving-airflow operator, pointwise circulation,
16-root full-pencil Arnoldi search and shift 0+300i are used. Mesh count and
spacing are explicit; mandatory attachment stations are retained. The historical
mesh, startup sidecars, pose and native eigenvector identities are unavailable.
No parameter is fitted to the archive and no original input is repaired.

Frequency below means Im(λ), in rad/input-time. Mesh checks compare both real
and imaginary components of six consistently tracked poles against the preceding
resolution of the same spacing; the real pole uses the existing absolute check
for its zero imaginary component.

| Spacing | Requested intervals | Lowest Im(λ) | Error versus archive | Mesh checks |
|---|---:|---:|---:|---:|
| cosine | 32 | 5.2452135 | 10.749% | — |
| cosine | 64 | 5.2086592 | 11.371% | 5/12 |
| cosine | 96 | 5.2025813 | 11.475% | 8/12 |
| cosine | 128 | 5.2007131 | 11.506% | 12/12 |
| modified-cosine | 32 | 6.0353031 | 2.695% | — |
| modified-cosine | 64 | 5.6285402 | 4.227% | 3/12 |
| modified-cosine | 96 | 5.4890103 | 6.601% | 9/12 |

The 96→128 cosine comparison has maximum nonzero-component change
**0.06757%** and minimum combined displacement/rotation shape MAC
**0.999999330**. Mode assignments remain one-to-one and consistent across grids.
These internal shape checks do not establish native branch identity. The
modified-cosine 64→96 comparison remains **9/12**, with lowest-frequency change
**2.542%**; its apparent closeness on a coarse mesh does not prove greater accuracy.

The 128-interval comparison retains the following native differences:

| Archive ordinal | ASWING Re, Im | OpenSwing Re, Im | Real-component error | Imaginary-component error |
|---:|---|---|---:|---:|
| 1 | -24.8224670, 5.8769355 | -24.8877930, 5.2007131 | 0.2632% | 11.5064% |
| 2 | -4.4445976, 101.9036200 | -4.4635386, 101.8233089 | 0.4262% | 0.0788% |
| 3 | -3.4945118, 187.8581000 | -3.4803909, 187.6279547 | 0.4041% | 0.1225% |
| 4 | -8.3365203, 355.7366700 | -8.3452243, 355.5598653 | 0.1044% | 0.0497% |
| 5 | -394.8426800, 0.0000000 | -392.9375603, 0.0000000 | 0.4825% | 4.81e-13 absolute |
| 6 | -8.2748982, 542.5078600 | -8.3151390, 540.6322436 | 0.4863% | 0.3457% |

Other oscillating-frequency errors are **0.050–0.346%** and real-component
errors are **0.104–0.486%**. All still fail the strict printed-precision gate.
The registered vacuum baseline **0/3,749** is unchanged. This is a six-pole,
one-operating-point conditional diagnostic, not a rerun of all ST-4 archive rows.

## Why the first frequency is sensitive

The first native pair is close to critical damping: ζ≈0.9730985, versus
0.9788565 on the fine cosine mesh. The exact algebraic
factor for a conjugate pair is `λ² − 2 Re(p) λ + |p|²`. Here the pole magnitude
differs by only -0.3266%, and the linear
and constant coefficients differ by 0.2632%
and -0.6522%. Small changes near critical
damping can therefore produce a much larger relative imaginary-part difference.
This is an algebraic diagnostic, not a separately identified one-degree-of-freedom
model, an explanation of the remaining physical discrepancy, or a relaxed gate.

## Sparse modal implementation and verification

The first 96-interval attempt exhausted the 512 MiB address-space limit while
forming a dense complex adjoint residual. Vector products now evaluate those
same residuals without allocating `A − λM`. The first 128-interval attempt then
failed in dense row scaling. The full-pencil path now keeps A/M sparse through
row equilibration, shifted Arnoldi, left inverse iteration, original-equation
checks and selected-vector mass pairing. Dense matrices are created only for
requested JSON matrix export or the existing Schur/SVD recovery fallback.
No constraint, weak inertia, mode, coupling, derivative or physical equation is
discarded. Input matrices are preserved, and reduced dense methods are retained.

The successful 96-interval modified/cosine solves take **64.88 / 57.87 s**;
the final 128-interval cosine solve takes **87.35 s** at
**207.5 MiB peak RSS**, with 2,469 unknowns,
480,552 A nonzeros and 12,668 M nonzeros. These include imports, public API
solution/output recovery and sparse evidence capture, without dense JSON matrices.
They are single-run observations, not a matched timing benchmark against the
older matrix-export runs. All 16 fine-grid left vectors used inverse iteration
without dense fallback. Larger dense recovery/export may still need more memory.

- **29 selected regression tests pass**: 23 Arnoldi/adjoint cases and six complete
  structured-versus-ungrouped modal analyses, including JSON matrix export,
  aerodynamic lag on/off, pointwise/Fourier circulation and vacuum. New CSC/CSR
  cases forbid dense conversion and verify that physical input matrices are
  unchanged; repeated-pole and recovery tests retain the fallback behavior.
- **96 new and 128 retained independent left/right eigenvector checks pass**;
  the new maximum full-pencil backward error is **1.17e-15** against
  1e-8. This checks solver accuracy, not the correctness of the physical model.
- A separate replay of the saved physical 64-interval pencil returns exactly
  the same eigenvalues. Relative left-vector change is
  **1.37e-15**; all 32 independent vector
  checks and selected mass pairings pass. Failed/replayed 96- and 128-interval
  physical A/M matrices are exactly equal.
- The offline browser solves the retained 16-interval, eight-Fourier-mode case
  in **21.465 s**, agrees with the pre-change native Python poles
  to **9.67e-13**, and saves/reopens the result exactly.
  Graphics are disabled for this solver/workbench test. This is Python/WASM
  parity, not a native ASWING execution or a 128-interval browser benchmark.

The 96-interval results use the intermediate residual-storage correction;
the 128-interval replay uses the final fully sparse path. Exact historical
kernel copies and current pins are retained and verified. Initial sparse tests
exposed an ambiguous `len(sparse_matrix)` metadata lookup; those failures are
retained, and the final 23-case rerun passes after replacing it with `shape[0]`.
The 128-replay terminal handle expired before its exit status was observed;
its computed result and execution receipt are independently verified, and no
worker remains. Its exit status is recorded as unknown, not retrospectively zero.
All numerical jobs were serial, one BLAS thread, 180 s and 512 MiB address-space
limits. Neither cap nor any accuracy gate was increased; browser work ran separately.

The next scientific step is to audit the physical and historical settings behind
this near-critically-damped pair, using the now mesh-stable cosine pilot. The
existing modified-cosine/Fourier studies remain useful diagnostics, not settings
to select for closer archive agreement. Full ST-4 and full-project validation
remain incomplete.

The [portable evidence summary](isae-st4-spatial-convergence-20261103.json) ships
in the source download. Raw worktree evidence: [assessment](../../artifacts/isae/st4-spatial-convergence-20261103/assessment.json),
[saved-pencil replay](../../artifacts/isae/st4-spatial-convergence-20261103/eigen-reuse.json),
[128-interval receipt](../../artifacts/isae/st4-spatial-convergence-20261103/cosine128_replay/execution.json),
[browser replay](../../artifacts/isae/st4-spatial-convergence-20261103/browser.json).
The [preceding spacing study](isae-st4-airflow-discretization-20261103.md) retains
the uniform and Fourier comparisons and the documented formulation audit.
