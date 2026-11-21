# AE-4: coverage and mode continuity near divergence

The registered zero-incidence comparison advances from **106/1,200 to
122/1,200 at 5%**. Eight cold runs at 100, 102, 103 and 104 m/s on both
declared meshes add sixteen passing components and refresh four existing
results. This is increased coverage with unchanged production physics and
acceptance gates. **AE-4 is not fully validated.** The primary assessment was
observed at 2026-11-12T14:07:11.357366+00:00; the subsequent diagnostics retain
their own UTC observations.

The new diagnostic finding is that OpenSwing's modes remain continuous through
the 103 m/s mismatch. Conditional comparison with the separate native divergence
export finds a persistent slow-root offset across 100–105 m/s, not just a single
problematic near-zero value. Exact native discretization and frame settings
remain unresolved.

![Conditional modal continuation near divergence](../../artifacts/isae/ae4-transition-coverage-20261112/continuation.png)

## Registered comparison results

| IAS (m/s) | Nominal 40 | Largest paired error | Nominal 80 | Largest paired error | Mesh gates at 0.1% |
|---:|---:|---:|---:|---:|---:|
| 100 | 4/4 | 1.978% | 3/4 | 5.913% | 1/4 |
| 102 | 4/4 | 1.401% | 4/4 | 3.885% | 1/4 |
| 103 | 0/8 | Unmatched | 0/8 | Unmatched | 0/8, unavailable |
| 104 | 4/4 | 1.085% | 4/4 | 2.847% | 1/4 |

The batch passes **23/40** native components: 24 are paired, one fails and
16 remain unmatched. The 100 m/s fine-grid failure and all 103 m/s unmatched
entries reproduce previous evidence. The four refreshed jobs are counted once.
Previously paired predictions reproduce exactly; at 103 m/s there are no paired
primary predictions for such a change metric. All 28 computed jobs in the
cumulative ledger now carry current-code evidence from 2026-11-12.

Cumulative accounting retains **128 paired components: 122 pass and six fail**,
plus **16 unmatched**, **12 unknown-initial-state components**, and **1,044
unrun**. Selected scope is 156/1,200. Failed paired-component errors have median
**11.466%**, range **5.913–48.809%**. The complete
[CSV](../../artifacts/isae/ae4-transition-coverage-20261112/comparisons.csv)
includes all 1,200 slots, with named columns, unique component keys and a
read-back comparison against the audited records.

The batch's mesh checks pass **3/20**: three of twelve paired components pass,
and eight remain unavailable at 103 m/s. Native accuracy and spatial convergence
are separate gates. The earlier overlapping 86/108 sample and the eighteen
historical modal tables containing 9,480 components remain separate. No
diagnostic below adds primary passes or removes required values.

## Current mode shapes do not switch branches

Four bounded postprocessing workers extract all four saved right modes from
twelve current-code states: IAS 100–105 on both meshes. They do not solve new
systems. Every full raw artifact is checked against its source pin before and
after extraction.

The comparison uses dimensionless nodal translations divided by the model
length and rotations in radians, with undeformed-span trapezoidal weights.
For each adjacent speed pair, all 24 possible assignments of the four modes
are compared by total modal assurance criterion (MAC). The winning permutation
preserves all four mode indices throughout. The smallest assigned overlap is
**0.999153155**; the smallest winning-minus-runner-up total is **0.956889450**.
This supports continuity of the computed mechanical fields. It does not
authenticate native eigenvectors or their boundary conditions.

At 103 m/s, continuation of the two native oscillatory frequencies from 102 and
104 m/s identifies the two large oscillatory roots using native values alone.
Their conditional OpenSwing component errors are at most **3.293%** across both
meshes. The original complete-set matching rule still leaves all eight primary
components per mesh unmatched because the archive also contains the tiny complex
root and unpaired real root. This diagnostic does not silently filter them or
relax that rule.

## The separate native divergence export exposes a consistent offset

The source audit verifies `divergence_speed.sh`, its exact output
`divergence_alpha_0_eig.txt`, the model, and the primary driver/table against
the retained upstream manifest. The divergence driver requests the same
`Pazy_wing`, `I 40`, solid wall and `0+200i` shift, with `NN10` instead of
`NN4`. Its literal insertion-stack mapping is native index = IAS − 58;
the primary mapping remains IAS + 1. The initial unknown point is retained.
The two principal oscillatory roots are identical between the native exports
at every speed from 100 through 105 m/s.

The candidate slow branch is selected from the native sequence alone. At
100–102 and 104–105 m/s it is the exactly-real root nearest the origin. At
103 m/s, the closest complex root to the midpoint of the 102/104 native values
is selected. Its original imaginary component is retained. This is conditional
eigenvalue continuation, not verified native modal identity.

| IAS (m/s) | Native candidate real part (1/s) | OpenSwing nominal 40 | OpenSwing nominal 80 |
|---:|---:|---:|---:|
| 100 | −1.6555073 | −1.5964208 | −1.5883524 |
| 101 | −1.0860652 | −1.0268263 | −1.0185841 |
| 102 | −0.5236066 | −0.4640750 | −0.4556411 |
| 103 | +0.033334177 | +0.093297390 | +0.101941727 |
| 104 | +0.58613789 | +0.64667136 | +0.65554585 |
| 105 | +1.1361306 | +1.1973664 | +1.2064921 |

The nominal-40 offset is **+0.05909 to +0.06124 /s**; nominal 80 gives
**+0.06715 to +0.07036 /s**. Conditional relative errors consequently rise
sharply near zero: about **179.89% /205.82%** at 103 m/s, although the
absolute discrepancy changes little. The NN10 native candidate at that point
has imaginary part **3.6546462e−7 /s**; it is not rounded to a certified real
pole. The NN4 real value is slightly different, `0.033334576 /s`.

Linear interpolation across 102–103 m/s gives candidate neutral speeds
**102.83261 /102.81717 m/s** on nominal 40/80, versus **102.94015 m/s**
from NN10: differences **0.1045% /0.1195%**. These are interpolation
diagnostics, not exact neutral-point solves or substitutes for damping gates.
Tiny native roots differ between NN4 and NN10; all original entries remain
in the evidence and denominator.

## References, execution and remaining work

The [authoritative index](aswing-authoritative-references.md) and checksummed
catalog were consulted. Jan Part IV §3.4, especially p.15, distinguishes the
vertical unloaded Pazy configuration from the horizontal loaded case and
separates flutter/divergence from nonlinear limit cycles. Drela's unsteady
§13.3.1, Eqs.147–152, supplies the complex shifted inverse, reused LU and
Arnoldi formulation. The earlier
[full-pencil QZ audit](isae-ae4-spectrum-20261105.md) independently recovers
the same current 103 m/s roots; it was not rerun.

Declared fixed frame, solid wall, density 1.23, PG Mach zero, pointwise
circulation, lag, updated influences and nominal cosine 40/80 remain unchanged.
The retained material break gives 41/81 actual intervals. Native `I 40` node
counting/spacing and historical restraint settings have not been recovered.
The original `% D` command means DONE and does not establish anchored defaults;
steady Eqs.177–178 require respecting wall dependence on Earth pose and the
distinction between fixed-frame and prescribed-acceleration support.

All **128 helper numerical checks** and the adapter's full matrix-equation,
mass-pairing, clamp and classification contracts pass. The eight cold workers
are terminal and reaped; maximum CPU / supervised wall / RSS are
**10.15 s /12.28 s /308.3 MiB**. The four saved-vector workers are also reaped,
with maxima **2.53 s /2.72 s /324.6 MiB**. All jobs retain one BLAS thread
and **512 MiB address space /15 CPU /25 wall-second** limits. Library preload
is separately bounded. All 142 production modules retain their hashes.

Next, prioritize source-based checks of native interval placement/counting and
wall/frame constraints. The smooth slow-root offset is a more useful diagnostic
than assuming a branch-search failure. Keep the
[near-flutter damping discrepancies](isae-ae4-onset-refinement-20261112.md),
incomplete spatial convergence, remaining registered speeds, other incidence
and deformed branches, and sensor/LCO histories open. The present evidence does
not justify fitting physical parameters or changing equations. AE-3 remains
open at 434/725.

- [Cumulative assessment and cold-run receipts](../../artifacts/isae/ae4-transition-coverage-20261112/assessment.json)
- [Prospective batch selection](../../artifacts/isae/ae4-transition-coverage-20261112/selection.json)
- [Current-mode continuity evidence](../../artifacts/isae/ae4-transition-coverage-20261112/continuation/assessment.json)
- [Native continuation and source pins](../../artifacts/isae/ae4-transition-coverage-20261112/native-continuation.json)
- [Standalone comparison SVG](../../artifacts/isae/ae4-transition-coverage-20261112/continuation.svg)
