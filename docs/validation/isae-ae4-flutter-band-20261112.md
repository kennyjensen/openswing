# AE-4: undeformed modes at 76–79 m/s

Eight new cold runs add **46/48 passing native comparisons**, advancing the
declared sweep from **181/1,200 to 227/1,200 at 5%**. Both meshes pass every
comparison at 76–78 m/s. At 79 m/s, both fail the lowest-frequency mode's
imaginary component. The growing flutter mode still passes there.

The cumulative assessment was observed at
**2026-11-12T16:07:18.706554+00:00**. No production code, model setting or
acceptance gate changed. AE-4 is not fully validated.

## New comparisons

| IAS (m/s) | Nominal 40 | Largest paired error | Nominal 80 | Largest paired error | Mesh gates at 0.1% |
|---:|---:|---:|---:|---:|---:|
| 76 | 6/6 | 1.403% | 6/6 | 1.694% | 4/6 |
| 77 | 6/6 | 1.202% | 6/6 | 1.616% | 3/6 |
| 78 | 6/6 | 2.253% | 6/6 | 2.360% | 2/6 |
| 79 | 5/6 | 7.870% | 5/6 | 8.288% | 2/6 |

All three printed positive-frequency modes retain both real and imaginary
comparisons. All four computed roots remain in the raw evidence. There are
no missing predictions in this batch. The separate spatial-convergence gate
passes only **11/24 components**; native agreement does not imply mesh
convergence.

The new runs fill the remaining gap in the contiguous 68–80 m/s interval.
Across that interval, **144/152 native components pass**, an overlapping
subset of the primary total, not an additional scope. The native export lists
only two positive-frequency modes at 80 m/s, so that speed has four scalar
targets per mesh; the other speeds in the interval have six.

![Flutter and low-frequency mode comparisons](../../artifacts/isae/ae4-flutter-band-20261112/flutter-branch-comparison.png)

The [SVG](../../artifacts/isae/ae4-flutter-band-20261112/flutter-branch-comparison.svg)
and plotted [flutter-mode values](../../artifacts/isae/ae4-flutter-band-20261112/flutter-branch-values.json)
and [low-frequency values](../../artifacts/isae/ae4-flutter-band-20261112/low-frequency-values.json)
are retained. Curves use the adapter's frequency-order pairing; native
eigenvectors are unavailable, so modal identity is not independently
authenticated. No curve is extended through an absent native target.

## What fails at 79 m/s

The low-frequency native pair is **−28.565868 ± 6.3190243i /s**. Its damping
rate is much larger than its oscillation frequency.

| Result | Real part (1/s) | Positive imaginary part (rad/s) | Frequency (Hz) | Frequency error |
|---|---:|---:|---:|---:|
| Archived ASWING | −28.565868 | 6.3190243 | 1.005704 | — |
| OpenSwing nominal 40 | −28.688237 | 5.8217298 | 0.926557 | 7.870% |
| OpenSwing nominal 80 | −28.692956 | 5.7952747 | 0.922347 | 8.288% |

The real parts differ by only **0.428% /0.445%**. For a conjugate pair
`a ± ib`, the product is `p = a² + b²`, and `b² = p − a²`. The computed pair
products differ from the native product by **0.113% /0.109%**. Because `a²`
and `p` are close, these small relative discrepancies leave a larger relative
difference in `b`. This algebra explains the sensitivity of the frequency
comparison; it does not identify a production equation error or justify a
different acceptance gate. A pair product is not the full system's physical
stiffness matrix.

At 80 m/s the existing OpenSwing evidence has two negative real roots in
addition to the two oscillatory pairs returned by the local search. The
native export no longer lists the low-frequency pair, and supplies no paired
real-root targets here. This is consistent with a transition from oscillatory
to nonoscillatory decay, but does not establish the native transition speed
or exact root identity. No synthetic zero-frequency native values were added.

The growing flutter mode remains a separate issue. Across the new interval,
its real-component errors are at most **1.403% /1.694%**, and its frequency
errors at most **0.0180% /0.0660%**. Absolute growth-rate offsets remain
**+0.0490 to +0.0668 /s** on cosine40 and **+0.0807 to +0.0939 /s** on
cosine80. The finer mesh does not uniformly improve native agreement.

## Accounting and provenance

The full ledger now contains **236 paired components: 227 pass and nine
fail**, plus **16 unmatched**, **12 unknown-initial-state values** and
**936 unrun**. The selected scope is **264/1,200**, covering 46 computed
jobs and two explicitly unavailable initial-state jobs. Failed paired errors
have median **8.288%**, range **5.913–48.809%**. Six failures concern
flutter-mode growth rates at 68–71 m/s, two are the 79 m/s frequencies above,
and one is a real component at 100 m/s.

The [comparison CSV](../../artifacts/isae/ae4-flutter-band-20261112/comparisons.csv)
retains all 1,200 unique required slots. Counts, named columns and exported
values were checked by reading the file back against the accepted records.
The earlier overlapping **86/108** sample and the historical modal scope's
**9,480** components remain separate. Inherited results keep their original
code epochs and source pins; only the eight new jobs are fresh solves.

The [authoritative reference index](aswing-authoritative-references.md), its
checksummed source catalog, Jan Part IV §3.4, p. 15, the original Pazy input,
`alpha_0.sh` and native eigenvalue export were checked before selecting the
interval. Selection covered every unrun integer IAS76–79 on both meshes,
before observing numerical errors. The native stack mapping stays
index = IAS + 1. Declared zero incidence, density 1.23, PG Mach 0, gravity
9.81, solid wall, fixed frame, pointwise circulation, lag, updated influences
and cosine40/80 remain unchanged. The mandatory material station gives
41/81 actual intervals. Exact native `I 40`, startup and restraint settings
remain unauthenticated. The declared updated-influence setting remains
distinct from OpenSwing's frozen-influence production default.

All **128 helper numerical checks** pass, together with the adapter's result
contracts. All eight jobs ran serially with one BLAS thread and completed
under the unchanged **512 MiB /15 CPU /25 wall-second** limits. The largest
observed CPU time was **9.73 s**, supervised wall time **14.26 s**, and peak
RSS **299.7 MiB**. All children are reaped; the 142 production modules keep
their batch-start hashes. Assessment and figure generation also completed
serially under the same limits. No browser, Node test or build job ran.

## Next investigation

Audit the new **79 m/s low-frequency discrepancy** before extending sweep
coverage. Use bounded diagnostics of the local pair and its damping/coupling
terms, preserving the native targets and both meshes. The close pair product
and small real-part error narrow the question but do not establish its cause.
Keep near-onset flutter damping, native setup, tiny-root identity around
103 m/s, actual wall/frame support, spatial convergence, deformed branches
and time histories open.

Evidence: [prospective selection](../../artifacts/isae/ae4-flutter-band-20261112/selection.json),
[cumulative assessment](../../artifacts/isae/ae4-flutter-band-20261112/assessment.json),
[figure receipt](../../artifacts/isae/ae4-flutter-band-20261112/plot-receipt.json).
