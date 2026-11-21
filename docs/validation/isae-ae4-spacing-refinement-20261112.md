# AE-4: spacing refinement and a bounded modal-memory fix

The 40/80/160-interval comparison is complete at 69 and 103 m/s for cosine and
modified cosine. **Changing spacing does not produce a stable match to the
archived sensitive real components.** Modified cosine briefly matches the
flutter-mode damping at 80 intervals, then moves outside 5% on refinement.
The primary score remains **122/1,200**; these diagnostic alternatives add no
votes.

The study also found and fixed an implementation issue: local eigenpair
refinement retained one large LU factorization while allocating the next.
Releasing it after its checked adjoint solve lets both previously failing
160-interval mode calculations finish within the original resource caps.
No equations, material properties, mesh defaults or acceptance gates changed.

![AE-4 spacing refinement](../../artifacts/isae/ae4-spacing-refinement-20261112/spacing-refinement.png)

## Results against archived ASWING

Each nominal mesh adds the same required material station at `t=0.52`, giving
41/81/161 physical intervals. The five new states complete the earlier
[spacing study](isae-ae4-mesh-stiffness-20261112.md) and
[cosine refinement](isae-ae4-onset-refinement-20261112.md). The original model,
sided GJ values, gravity, wall, flow, pointwise circulation, lag, updated
influences, four-mode search and complex shift are retained.

| Spacing | Base intervals | Flutter-mode Re(λ), IAS 69 (1/s) | Native error | Candidate slow Re(λ), IAS 103 (1/s) | Conditional native error |
|---|---:|---:|---:|---:|---:|
| Archived ASWING | — | −0.1780785000 | — | +0.0333341770 | — |
| Cosine | 40 | −0.0911608982 | 48.809% | +0.0932973898 | 179.885% |
| Cosine | 80 | −0.1254639112 | 29.546% | +0.1019417270 | 205.817% |
| Cosine | 160 | −0.1340178245 | 24.742% | +0.1041004353 | 212.293% |
| Modified cosine | 40 | −0.2062774706 | 15.835% | +0.0132913354 | 60.127% |
| Modified cosine | 80 | −0.1781457492 | 0.038% | +0.0606434554 | 81.926% |
| Modified cosine | 160 | −0.1593323015 | 10.527% | +0.0829915823 | 148.968% |

The 103 m/s reference remains the separate NN10 continuation candidate from
the [transition audit](isae-ae4-transition-coverage-20261112.md). Its printed
imaginary component `3.6546462e−7 /s` is retained. The primary NN4 export has a
slightly different candidate real part and an additional tiny complex root;
all eight primary components per mesh remain unpaired there. This diagnostic
does not authenticate native mode identity or substitute NN10 for NN4.

The fine-grid spacing difference decreases at both speeds. However, none of
the four sensitive real-component sequences meets the existing **0.1% mesh
gate**: the 80→160 changes are 6.38% /11.81% at 69 m/s and 2.07% /26.93% at
103 m/s, for cosine /modified cosine respectively. A single matching result
at 80 intervals is insufficient evidence for changing the default.

Cosine exhibits approximately second-order corrections in these three-grid
sequences. Modified cosine gives observed orders 0.58 and 1.08; extrapolation
is less settled. At 103 m/s, their diagnostic limiting estimates are +0.10482
and +0.10297 /s, both far from the archived +0.03333 /s. At 69 m/s the
estimates differ more, −0.13686 and −0.12135 /s. These are three-point
extrapolations, **not verified continuum solutions or new passing results**.
The evidence does not establish different limiting equations for the two
spacing rules.

All four computed modes retain close mechanical shapes between the two finest
meshes. Minimum assigned MAC is **0.999997** at 69 m/s and **0.999998** at
103 m/s. Comparison uses dimensionless translations/rotations, interpolation
at common physical jig-span coordinates and trapezoidal weights. The
independently selected critical modes agree with the best complete shape
assignment. This supports correspondence between current computed branches;
native eigenvectors are still unavailable.

## Why the fine-grid mode jobs failed, and what changed

Both initial 103 m/s, 160-interval mode jobs raised `MemoryError` in the
second bordered LU factorization. Their base and full A/M assembly checks
had already passed. A separately bounded diagnostic logged virtual memory
before and after the first factor: **366,072→499,680 KiB**. Before the second
allocation, the old factor and new border occupied **517,576 KiB**, leaving
too little of the **524,288 KiB** address-space cap for another factor.
These values describe virtual address use, not resident memory.

[modal_refinement.py](../../openswing/modal_refinement.py) now solves the
checked adjoint immediately after each accepted Newton correction, then
releases the factor and border before the next iteration. It retains the
last accepted adjoint if the next correction is rejected. The full bordered
equations, row scaling, local-correction restriction, stopping tolerances,
left/right residual gates and mass pairing are unchanged. No matrix entries
or physical coordinates are discarded.

Both failed stages now complete using the **exact saved full sparse A/M
matrices**. Their 16 numerical checks each pass. The successful modified
cosine80 control returns **identical eigenvalues**, including the sensitive
slow real component, and passes another 18 checks. This is an isolated
storage-lifetime fix, not evidence that the native discrepancy was resolved.
Original failed jobs, logs, old source copy and UTC observations remain intact.

The focused regression suite passes **13 tests**, including two that detect
overlapping factor lifetimes and verify recovery of the last accepted
adjoint. The full-pencil Arnoldi suite passes **19 tests**. Its first run
inadvertently overlapped the end of the last numerical worker; it was rerun
successfully under the same exclusive lock after that worker exited. No
resource limit was raised. Solver workers themselves ran serially, and all
workers and test processes have exited. These timings are not browser
benchmarks; UI modal-output recovery was not part of this workload.

The completed study has **120 numerical checks**, plus **18 recovery-control
checks**, all passing. The final fine-grid mode workers use at most **8.22 CPU
seconds, 9.36 supervised wall seconds and 219.8 MiB RSS**. Every numerical
worker retains one BLAS thread and **512 MiB address space /15 CPU seconds
/25 wall seconds**. The assessment records the original and repaired code
epochs explicitly; it does not relabel the old results as fresh solves.

## Source interpretation and next work

The authoritative [index](aswing-authoritative-references.md), checksummed
catalog, Jan Part IV §3.4 (printed p.15), original `Pazy_wing.asw`,
`alpha_0.sh` and native modal tables remain the setup authority. No source
authenticates the exact node coordinates or count convention behind `I 40`.
The previous GJ ambiguity and spacing findings remain relevant, but neither
permits fitting a mesh to the outputs.

Drela's steady description supports both pointwise circulation and Fourier
circulation: Eqs.62–63, p.15; midpoint sampling Eqs.150–153, p.31; and the
weighted flow-tangency residual Eq.201, p.40. OpenSwing implements both in
[circulation.py](../../openswing/circulation.py), but the current AE-4 declared
comparison explicitly uses pointwise circulation. The extended manual's
§1.3.5/Fig.1.13 shows a **180-node example with modes 1–19**. That is evidence
of an available representation, not evidence that AE-4 used 19 modes.
The literal AE-4 driver specifies `I 40` and the modal search but does not
print or select a circulation-mode count.

The next discriminator is a controlled circulation-representation audit:
first verify full-basis equivalence on the actual Pazy pencil, then examine
predeclared truncations and convergence independently of structural spacing.
Retain the original pointwise primary and all native targets. Missing native
restraint settings, wall/frame capability, tiny-root identity, the other sweep
points, deformed branches and time histories remain open.

Primary accounting stays **122/1,200**: 128 paired components, six mismatches,
16 unmatched, 12 unknown initial values and 1,044 unrun. Failed paired errors
remain median 11.47%, range 5.91–48.81%. This study changes no tracked scope,
denominator or acceptance fraction. The separate 9,480 historical modal
components also remain in their declared scope.

- [Original five-state plan](../../artifacts/isae/ae4-spacing-refinement-20261112/plan.json)
- [Initial successes and memory failures](../../artifacts/isae/ae4-spacing-refinement-20261112/initial-outcome.json)
- [Memory diagnostic and source preservation](../../artifacts/isae/ae4-refinement-memory-20261112/before-change.json)
- [Repair replay plan and source pins](../../artifacts/isae/ae4-refinement-memory-20261112/recovered/plan.json)
- [Combined assessment](../../artifacts/isae/ae4-spacing-refinement-20261112/assessment.json), observed 2026-11-12T14:57:16.527618+00:00
- [Standalone plot SVG](../../artifacts/isae/ae4-spacing-refinement-20261112/spacing-refinement.svg)
