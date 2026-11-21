# AE-4: onset refinement through nominal 160

Observed 2026-11-12 UTC. Refinement improves the near-onset damping comparison,
but **does not remove the native discrepancy**. On nominal 160, the critical
real-component errors are **24.742% at 69 m/s** and **7.792% at 70 m/s**.
All other components pass the unchanged 5% reference allowance. The separate
80-to-160 component convergence gate passes **10/12 at 0.1%**; the two critical
real parts remain unconverged at that stricter level.

The registered scope remains **50/1,200**, with 1,116 components still unrun.
This finer-grid diagnostic reuses existing native targets and adds no primary
votes. The [registered comparison](isae-ae4-crossing-current-20261112.md) retains
its complete original denominator, unavailable values and failed attempts.

![AE-4 damping and refinement](../../artifacts/isae/ae4-onset-refinement-20261112/refinement.png)

## Damping and mesh trend

| Nominal intervals | Critical real part at 69 m/s (1/s) | Native error | Critical real part at 70 m/s (1/s) | Native error |
|---:|---:|---:|---:|---:|
| 40 | −0.0911608982 | 48.809% | +0.7282434540 | 13.915% |
| 80 | −0.1254639112 | 29.546% | +0.6969335164 | 9.017% |
| 160 | −0.1340178245 | 24.742% | +0.6890984943 | 7.792% |
| Archived ASWING | −0.1780785000 | — | +0.6392872200 | — |

The latest absolute mesh corrections are 0.008554/s and 0.007835/s. The
remaining absolute native errors are 0.044061/s and 0.049811/s. Critical-real
changes relative to the finer values are **6.383% and 1.137%**, so neither
passes the existing 0.1% component gate. Every other compared component passes
that mesh gate. The two fine critical frequencies differ from ASWING by
0.0753% and 0.0762%; all six fine frequency comparisons remain within 5%.

The three-grid damping corrections give observed orders **2.0037 and 1.9986**.
A three-grid extrapolation would leave native errors of **23.15% and 7.38%**.
This is a trend diagnostic, not a verified continuum solution or an accepted
comparison. It suggests that refining this cosine-mesh sequence alone will
not close the full gap. It does not identify whether the residual difference
comes from archived discretization/settings or implementation differences.

The critical computed mode remains consistent: its span-weighted mechanical
coordinate correlation is **0.99999854 across the 80/160 meshes at 69 m/s**,
and **0.99784326 from 69 to 70 m/s on nominal 160**. The former interpolates
the coarse nodal translation/rotation field to the finer material stations.
These are current-mode continuity diagnostics; unavailable native eigenvectors
cannot be authenticated by them.

Both meshes still reproduce the **69–70 m/s stable-to-unstable bracket**.
Linear interpolation gives onset IAS **69.162818 m/s** on nominal 160 versus
**69.217869 m/s** for the archived values: 0.055051 m/s or **0.07953%**.
The previous nominal 80 estimate was 69.152559 m/s. Interpolation does not
replace an exact neutral-state solve or the failed damping comparisons.

## Numerical verification and bounded stages

The production equations and all 142 production modules are unchanged.
Each state is split into a cold equilibrium, complete sparse matrix assembly,
and the original four-mode local search at shift `0+200i`. This retains the
entire physical pencil, all clamp equations, left/right modes, mass pairing,
reference components and acceptance gates. Matrices are saved as exact sparse
NPZ files; no coefficients are dropped or thresholded.

The staged nominal 80 control reproduces the registered cold result to
**4.84e−14 relative error**, with a **3.49e−14/s** difference in its critical
real component. Thus staging is verified independently of the mesh change.
Every restored equilibrium checks its model/mesh identity and fresh residual.
Both matrix derivatives are checked against separate physical residual actions.
Every selected mode passes complete left/right pencil residuals, mass
normalization and root-clamp checks.

All **74 numerical/source checks** pass across **nine terminal, reaped
workers**. Each worker retains one BLAS thread and the unchanged **512 MiB
address-space /15 CPU /25 wall-second** limits. The largest worker uses
**6.42 CPU seconds, 7.52 supervised wall seconds and 228.6 MiB peak RSS**.
Libraries are preloaded in a separate bounded stage. No background solver or
browser/build job is started.

The first aggregate audit reached its 25-second cap while repeatedly validating
identical source-pin lists. Its receipt and script are retained. The final audit
requires every worker's list to equal the prospective plan, verifies those
source files before and after assessment, and verifies each distinct dependency
once. It completes under the same limits. No numerical work was repeated.

The script can be inspected at
[run.py](../../artifacts/isae/ae4-onset-refinement-20261112/run.py). Existing stage
directories cannot be overwritten. This is a supplementary staged study, not
the registered adapter's one-cold-call execution contract.

## Source interpretation and next discriminator

The [authoritative reference index](aswing-authoritative-references.md) and
checksummed source catalog were consulted. Jan Part IV §3.4, pp.13–16,
describes the vertical unloaded Pazy-wing case and distinguishes flutter from
nonlinear limit cycles. Drela's unsteady §13.3.1, Eqs.147–152, pp.28–29,
specifies the shifted-LU/Arnoldi search and left-mode normalization used here.

The literal source model, stiffness break, inertia distribution and driver are
unchanged. Nominal 80/160 cosine counts retain the same material break and
produce 81/161 elements. The driver commands `I 40` but does not authenticate
its original node distribution; it also leaves historical startup/aerodynamic
settings qualified. Updated influences remain an explicit existing declared
alternative. The sensor export contains position/angle channels, not density,
Mach or node-coordinate evidence. It cannot settle those unknowns.

The source audit also checked the documented wake-core rule:
`max((r/c)*chord, interval_width)`. Current aerodynamic and tangent paths use
that rule. The manual says its parameter has no effect for a single surface;
there is no evidence here for changing the core radius to fit damping.

Next, audit the native discretization and the unsteady load/mass couplings
against their independent source equations. Keep exact historical setup,
full component convergence, the 103 m/s modal-identity/wall-frame issue, other
operating branches and nonlinear histories open. The present trend is evidence
against treating insufficient mesh count as the sole explanation, not proof
that OpenSwing or the archived ASWING result is wrong.

- [Complete audit, source hashes, timings and component comparisons](../../artifacts/isae/ae4-onset-refinement-20261112/assessment.json)
- [Prospective stage plan](../../artifacts/isae/ae4-onset-refinement-20261112/plan.json)
- [Wake-core and sensor-channel source audit](../../artifacts/isae/ae4-onset-refinement-20261112/source-audit.json)
- [Plot SVG](../../artifacts/isae/ae4-onset-refinement-20261112/refinement.svg)
- [Retained first audit timeout](../../artifacts/isae/ae4-onset-refinement-20261112/assessment-first-attempt.json)
