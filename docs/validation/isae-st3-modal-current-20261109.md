# ST-3 current modal comparison at the requested 5% tolerance

**All nine original ASWING workbook frequencies now pass at 5% on both
meshes.** Six fresh serial solves reproduce the previous frequencies to
roundoff. No production equation, material property, source model or reference
frequency changed. The one additional pass comes from applying the user's
existing 5% allowance to this adapter; its previous printed-precision result
remains **8/9**.

| Original layup | ASWING frequency set, Hz | Current OpenSwing, 128 intervals, Hz | Maximum error | Passing at 5% |
|---|---|---|---:|---:|
| `0_3_90` | 3.7, 24.3, 25.9 | 3.798389, 24.267960, 25.912461 | 2.6592% | 3/3 |
| `p15_0` | 3.63, 22.5, 26.6 | 3.629656, 22.525354, 26.585569 | 0.1127% | 3/3 |
| `m15_0` | 3.62, 22.5, 26.6 | 3.621312, 22.481931, 26.578141 | 0.0822% | 3/3 |

Median fine-grid error is **0.08031%**. The remaining discrepancy at original
printed precision is 3.798389 versus 3.7 Hz: 0.098389 Hz, or 2.6592%, against
the existing ±0.05 Hz interval. That numerical difference has not been fixed
or hidden by changing its reference.

## Setup and source qualifications

Part III §4.3, pp. 35 and 37, describes the low-aspect-ratio wing bench;
Table 5 on p. 38 reports the frequencies. The report and workbook use
`1B, 2B, 1T` headings, while the coupled experimental values follow Dunn's
`1B, 1T, 2B` order. The [original source audit](isae-st3-sources.json)
preserves this conflict. The comparison therefore remains a **frequency-set
comparison**, retaining each original cell and label without claiming native
mode identity. No target-nearest mode selection is used.

All three `.asw` files are literal and round-trip unchanged. Their scaled
stiffness, coupling, mass, rotary inertia, axis offsets and geometry were
checked against the existing independent source-property audit. Part III,
Drela steady and unsteady PDF/text hashes match the authoritative catalog.

The operating point remains the previously declared fixed upright wing under
self-weight, zero mean flow and still-air density 1.23 kg/m³. The model retains
Drela's strip apparent inertia. These settings are not claimed to be recovered
native startup merely because the directory is named `Vaccum_anaysis`.
The 64/128 cosine grids include the existing mandatory property break, giving
66/130 structural nodes. No mesh is chosen by fitting the native frequencies.

## Fresh physical and numerical checks

Each of the six bounded invocations solves one equilibrium and one full
descriptor modal problem. The first three positive frequencies are selected
from the same fixed 12-root survey. All roots are distinct, have unique
conjugate partners, and satisfy the neutral-mode check. Full matrices and both
eigenvector sides are saved.

* All **144 independently evaluated left/right eigen-equation residuals** pass;
  maximum action-relative residual is 3.92e−13.
* Maximum normalized real component is 2.00e−13. Raw complex eigenvalues are
  retained, rather than replaced with purely imaginary values.
* All **nine mesh/shape checks** pass. Maximum frequency change is 0.08384%,
  below the unchanged 0.1% gate; minimum mass/inertia-weighted shape MAC is
  0.999996917. Shape matching preserves the frequency ranks without consulting
  the workbook targets.
* Fresh equilibrium residuals, root constraints, global force/moment balance
  and independently integrated gravity forces/moments pass. The largest raw
  component among these checks is 1.56e−15 in its respective units.

The six solves take 3.25–5.48 seconds each after imports, totalling 26.18 seconds.
Peak RSS is 151,312 KiB. Jobs use one BLAS thread, 512 MiB address space,
15 CPU seconds and 25 wall seconds, and run serially. No physical job failed
or retried. Browser/build and kernel-loading checks remain held.

## Acceptance and reporting changes

The modal adapter previously marked continuous frequencies ineligible for any
relative allowance. It now permits the configured reference-error policy,
including the requested 5% default. Strict decimal comparisons, original
targets and numerical gates are unchanged. Setting relative tolerance to zero
still gives the original precision result.

This exposed an integration issue: mesh reporting assumed that an accepted
policy view was identical to the strict result. The mesh path now reconstructs
the strict checks from the saved numerical evidence, validates them, reapplies
the canonical policy and requires an exact match to the supplied policy view.
Tampered pass flags or tolerance metadata are rejected.

All **22 focused adapter/accounting tests** pass, including configurable
3%/5%/strict boundaries, unrun denominators, corrupted evidence and altered
policy views. The first run's 18 passes and one mesh-policy failure are
retained separately. The real six-job study also passes the shared scalar
accounting and adapter mesh-reporting functions: **18/18 repeated mesh slots**
at 5%, with **16/18 strict slots**. The primary progress measure counts the
same **nine distinct cells**, requiring both meshes; it does not add the
mesh repeats or count numerical checks as native matches.

The historical **930/1,080 static scope** is untouched and has not been rerun
or reassessed here. Next work is the static curve coverage across all three
layups with their original signed-load scripts. Historical operating settings,
disputed modal labels, the incompatible `test.asw`/`test.txt` torsion pair and
full ST-3 validation remain open. All 141 production modules are unchanged.

Evidence: [plan and original cells](../../artifacts/isae/st3-modal-current-20261109/plan.json),
[current frequencies, mesh checks and accounting](../../artifacts/isae/st3-modal-current-20261109/summary.json),
[22 tests](../../artifacts/isae/st3-modal-current-20261109/adapter-final-tests.xml),
[fresh-run script](../../scripts/verify_st3_modal_current.py),
[shared modal adapter](../../scripts/isae_suite_st3_modal.py).
Every job directory retains its request, complete physical result, sparse
matrices, modal shapes, strict result, 5% result and checksummed report.
