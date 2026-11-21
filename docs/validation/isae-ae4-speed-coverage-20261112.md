# AE-4: broader registered speed-sweep coverage

Observed 2026-11-12T12:40:39.650322+00:00. The existing undeformed-wing comparison advances
from **50/1,200 to 106/1,200 at 5%**. Twelve current-code cold solves cover
six speeds on both declared meshes; **60/60 native scalar components pass**.
This is additional coverage, not a change to the physical model or tolerances.
AE-4 remains unvalidated as a whole.

![Native and computed selected modal spectra](../../artifacts/isae/ae4-speed-coverage-20261112/spectrum.png)

## New comparisons

| IAS (m/s) | Nominal 40 passes | Largest native error | Nominal 80 passes | Largest native error | Mesh passes at 0.1% |
|---:|---:|---:|---:|---:|---:|
| 10 | 6/6 | 0.109% | 6/6 | 0.239% | 4/6 |
| 30 | 6/6 | 0.374% | 6/6 | 0.506% | 4/6 |
| 50 | 6/6 | 0.671% | 6/6 | 0.760% | 5/6 |
| 80 | 4/4 | 0.740% | 4/4 | 1.583% | 1/4 |
| 90 | 4/4 | 0.478% | 4/4 | 4.445% | 0/4 |
| 105 | 4/4 | 0.974% | 4/4 | 2.498% | 1/4 |

Each native error is the maximum among finite paired real and imaginary
components at that speed/mesh. An unavailable component never becomes a pass.
The plot shows selected roots, not tracked native branch identities. Native
points use the retained literal index = IAS + 1 mapping; the unknown initial
point is not assigned a speed. Hollow computed markers identify inherited
historical evidence. Neither drawing a root nor matching one plotted coordinate
establishes full validation. Additional computed real poles without a paired
archive entry are shown for visibility; they do not receive native-reference
passes. Their appearance below the archived damping points is not an accepted
match to an unprinted native value.

The six new mesh pairs pass **15/30** component comparisons at the
unchanged 0.1% gate. The reference allowance remains 5%, with the original
absolute and near-zero rules. These distinct gates are not interchangeable.

The maximum native error grows on nominal 80 at every speed in this batch,
although it remains below 5%; the largest is 4.445% at 90 m/s. The archived
driver explicitly requests `I 40`, so finer-grid agreement with that finite
native calculation is not expected to improve monotonically. Exact historical
spacing and interval-count bookkeeping are still unknown. This pattern makes
discretization matching a useful next discriminator; it does not authenticate
our coarse mesh or justify fitting physical parameters.

## Cumulative accounting

The selected primary denominator is **140/1,200**. Of it,
**112 components are finite and paired: 106 pass and 6 fail**.
There are **16 unmatched components**, **12 unknown-initial-state values**,
and **1060 further unrun components**. Every original denominator is retained
in the [complete comparison CSV](../../artifacts/isae/ae4-speed-coverage-20261112/comparisons-corrected.csv).

The batch adds 56 previously unselected primary slots. IAS 80 / nominal 40
already existed in the prior ledger and is refreshed without duplicate votes.
Its largest paired change from the saved historical output is
**0 /s**. The cumulative ledger now contains
24 unique computed jobs, of which 4 remain inherited historical
evidence; not every retained point was rerun in this batch.

The finite failures have median relative error **11.466%** and range
**5.913–48.809%**. Existing near-onset critical damping failures
remain open. The [40/80/160 refinement](isae-ae4-onset-refinement-20261112.md)
has a nearly second-order trend but leaves fine-grid errors of 24.74% and
7.79% at 69/70 m/s. Onset interpolation agrees within 0.0795%; that does not
replace the damping gates. The [independent unsteady-load audit](isae-ae4-apparent-quadrature-20261112.md)
supports the section equations and rules out apparent-load quadrature as the
main explanation on the audited points.

The earlier overlapping sample remains **86/108**, explicitly historical and
separate from this cumulative sweep. All eighteen historical modal tables retain
their **9,480** separately inventoried components. No alternative grid or
diagnostic setting is added to the primary score.

## Source and numerical checks

The [authoritative source index](aswing-authoritative-references.md), checksummed
catalog and Jan Part IV §3.4, pp.13–16, were consulted. The report distinguishes
vertical unloaded Pazy tests, flutter/divergence and nonlinear limit cycles.
The original model, `alpha_0.sh` and `alpha_0_eig.txt` remain the comparison
sources. Experimental agreement is not the acceptance target.

The existing declared setup is unchanged: zero incidence, fixed frame, solid
wall, density 1.23, PG Mach zero, pointwise circulation, lag, updated influences,
nominal cosine 40/80 with the material break retained, four local modes and
shift `0+200i`. These are declared alternatives where historical startup
settings are unavailable. No claim of recovered `.set` or native node data is
made. Drela's unsteady §13.3.1, Eqs.147–152, pp.28–29, supplies the shifted-LU,
Arnoldi and left-mode normalization algorithm.

All **192 helper numerical checks** pass. The independent adapter also
checks complete right/left matrix equations, mass pairing, clamping and real-pole
classification. Each worker authenticates the full raw artifacts; the final
audit repeats source, raw-file and compact-contract verification and deduplicates
the inherited operating point. Complete matrices, vectors and original decimal
targets are retained.

The final CSV read-back caught an omitted status field in the first positional
export. Its original file and generating assessment are retained. The linked
corrected export uses named columns and verifies all 1,200 rows against the
audited records: 106 passes, 112 finite values, 16 unmatched, 12 blocked initial
values and 1,060 unrun. No numerical result or primary count changed. The
[CSV audit](../../artifacts/isae/ae4-speed-coverage-20261112/csv-audit.json)
records the correction and both file hashes.

All **twelve numerical workers are terminal and reaped**, with one BLAS thread
and unchanged **512 MiB address space /15 CPU /25 wall-second** caps.
Maximum observed CPU, supervised wall and peak RSS are **11.18 seconds,
22.99 seconds and 299.5 MiB**. Library preload is separately bounded.
All **142 production modules** retain their source hashes.
No background solver, browser or build job was started.

## Remaining work

Continue the unrun registered speed sweep, including transitions in the selected
modal set. Preserve the 103 m/s tiny/slow-root mismatch, historical setup
uncertainty and incomplete spatial convergence. Other incidence/deformed branches,
divergence-driver pairing, prescribed-wall frame support and nonlinear LCO/time
histories remain outside completed validation.

- [Cumulative assessment, source hashes, roots and timings](../../artifacts/isae/ae4-speed-coverage-20261112/assessment.json)
- [Batch selection and its timing qualification](../../artifacts/isae/ae4-speed-coverage-20261112/selection.json)
- [All primary comparison slots](../../artifacts/isae/ae4-speed-coverage-20261112/comparisons-corrected.csv)
- [Standalone spectrum SVG](../../artifacts/isae/ae4-speed-coverage-20261112/spectrum.svg)
- [Reusable bounded runner](../../scripts/replay_isae_ae4_bounded.py)
