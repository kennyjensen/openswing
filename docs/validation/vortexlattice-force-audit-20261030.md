# Executed VortexLattice.jl force and Trefftz comparison

2026-10-30. **The independent force calculation agrees with OpenSwing, and a
complete change to arithmetic-midpoint receivers does not resolve the retained
drag gap.** All 1,164 predeclared comparisons pass across 194 evaluations.
This narrows the investigation; it does not fix the archived ASWING mismatch.

The pinned VortexLattice.jl package was executed in Julia, rather than translated
into Python. The compared quantities are forces and wake drag at prescribed
circulation, not independently converged aircraft solutions. No production
equation, numerical tolerance, ISAE count, or browser behavior changed.

## What was compared

The [protocol](../../artifacts/isae/vortexlattice-force-audit-20261030/protocol.md)
includes every state in the earlier SA-4 force-vector audit: six original fields
and ninety refinements covering uniform, cosine, and modified-cosine spacing
at 128, 256, 512, 1,024, and 2,048 intervals. The originals include all four
failed drag-table states from that cohort and the passing control on both
retained meshes. The SA-2 200-interval, 6.3-degree state from the earlier
quadratic-drag audit is also included, giving 97 fields.

Each field receives two complete evaluations:

1. Original bound endpoints, circulation, and Glauert force receivers.
2. The same endpoints and circulation, with every force receiver moved to its
   bound segment's arithmetic midpoint. All source influences and both drag
   integrals are recomputed at the new receivers.

For a common force convention, both implementations use the bound endpoint
vector in this comparison. OpenSwing's production ASWING force uses section
span times interval length; the difference was measured in the earlier
[force-vector audit](../../artifacts/isae/sa4-force-vector-audit-20261030/report.md)
and remains recorded separately in these results. Agreement here therefore
does not assert that the packages implement identical aircraft models.

The Julia harness represents each horseshoe by a one-row panel with coincident
front/rear endpoints, zero side-segment lengths, and explicit force receiver.
Its trailing rays begin at the original bound endpoints. Geometry is rotated
into wind axes; there is no finite core, symmetry image, ground, aircraft
motion, profile force, or unsteady term. The zero side forces and every
velocity/force component were checked, so the mapping is not justified merely
by similar aggregate coefficients. This is a controlled operator comparison,
not VortexLattice.jl's default finite-chord aircraft discretization.

## Independent numerical agreement

| Quantity, maximum over all evaluations | Observed difference | Predeclared limit |
|---|---:|---:|
| Velocity component, scaled by max(1, absolute expected component) | 4.42e-12 | 2e-8 |
| Per-strip force-coefficient component | 6.39e-17 | 2e-10 |
| Per-strip Trefftz CD | 7.93e-17 | 2e-10 |
| Total near-field CD | 2.47e-16 | 2e-9 |
| Total Trefftz CD | 1.39e-15 | 2e-9 |
| Side-force coefficient in the coincident-endpoint mapping | 0 | 2e-10 |

There are six checks per evaluation and **1,164/1,164 pass**. Expectations were
freshly computed using OpenSwing's current horseshoe and wake-force routines.
The original SA-4 endpoint-force and Trefftz totals also reproduce the retained
audit values. [Full results](../../artifacts/isae/vortexlattice-force-audit-20261030/results.json)
and [summary](../../artifacts/isae/vortexlattice-force-audit-20261030/summary.json)
retain every field, gate, and input/output hash.

## The full receiver change does not remove the gap

Here, gap means near-field induced CD minus Trefftz CD, with the common
endpoint-vector convention above. A negative value means near-field drag is
smaller. The change column compares absolute gap magnitudes.

| Saved field | Original-receiver gap | Arithmetic-midpoint gap | Change in gap magnitude |
|---|---:|---:|---:|
| SA-2, 6.3°, N200 | -0.00238642 | -0.00238269 | 0.156% smaller |
| SA-4 row 014, N36 | -0.00271343 | -0.00296943 | 9.43% larger |
| SA-4 row 015, N36 | -0.00305820 | -0.00333534 | 9.06% larger |
| SA-4 row 016, N36 | -0.00343102 | -0.00372713 | 8.63% larger |
| SA-4 row 020, N18 | -0.00488505 | -0.00498334 | 2.01% larger |
| SA-4 row 008, N18, control | -0.00100655 | -0.00101130 | 0.473% larger |
| SA-4 row 008, N36, control | -0.000938060 | -0.00104939 | 11.87% larger |

**All 96 retained SA-4 fields have a larger absolute gap with the arithmetic
receiver.** At N2048, the increase is 7.16–8.25% on uniform meshes,
5.25–6.15% on cosine meshes, and 3.64–4.52% on modified-cosine meshes.
These prescribed refinements are not additional converged solutions.

For SA-2, the previous audit established that an arithmetic receiver removes
the own-wake diagonal bias, but explicitly left the complete force change
uncomputed. The new [pair accounting](../../artifacts/isae/vortexlattice-force-audit-20261030/sa2-accounting.json)
closes that question:

| Contribution to the change in near-minus-far CD | Change |
|---|---:|
| Own-strip diagonal terms | +0.001466713623 |
| Other strips on the same half-wing | -0.001462971107 |
| Strips on the opposite half-wing | -0.000000013017 |
| Total | +0.000003729499 |

The own-strip residual at the midpoint is only 1.32e-16, but almost all of that
apparent improvement is offset by the other same-half strips. Removing the
diagonal alone would therefore misrepresent a consistent receiver change.

## Scope and remaining work

This independently checks the tested horseshoe/force/Trefftz arithmetic and
rules out a standalone midpoint-receiver substitution as a useful fix on
these retained fields. It does not establish native ASWING's detailed source
construction, matching circulation closure, historical settings, or matching
solutions after a different discretization is solved. Those remain distinct
questions. Drela's steady Eqs. 150–156 explicitly prescribe Glauert sampling,
and Eq. 67 prescribes the section-span force; this diagnostic does not justify
replacing either in production.

VortexLattice.jl revision `966c2f369ae2ab8dafcea18bbc6187d36b398b45` and its
20 unmodified package files are pinned in
[reference-source.json](../../artifacts/isae/vortexlattice-force-audit-20261030/reference-source.json).
The verified Linux/aarch64 Julia 1.10.10 runtime checksum and resolved dependency
manifest are retained. The runtime itself is temporary research tooling.

The first run stopped in an upstream convenience allocator:
`trefftz_panels(surface, fs, gamma)` refers to `panels` before defining it.
The initial log and harness are preserved. The successful harness allocates
storage and calls the package's existing `trefftz_panels!` API; no upstream
source or equation was patched. The completed run executes 194 evaluations
in 39.2 seconds after package loading/initial compilation. This timing is not
an aircraft-solve benchmark.

All 131 production Python modules and `ISAE_STATUS.md` retain their pre-audit
hashes. The full ASWING implementation goal and the SA-1–SA-5 discrepancies
remain incomplete. [Terminal receipt](../../artifacts/isae/vortexlattice-force-audit-20261030/terminal-receipt.json).
