Implemented and frozen: exact-zero Weight objects are omitted from the analysis view while their original records and source text remain intact.

A Weight is null only if all twelve scaled physical fields are exactly zero: Weight, CDA, Vol, Hx/Hy/Hz and all six inertia entries. Geometry alone defines a massless rigid pylon. Steady Eqs.95–96 eliminate its loads; Eq164 eliminates its aerodynamic source/doublet; unsteady Eqs.46–47 retain the same invariance. This supports mathematical elimination, not a claim about legacy ASWING accepting an invalid anchor.

One shared active ordering now feeds mesh requirements, attachment geometry, network/source/dynamic consumers, inertia, aerodynamics, volume influence and wall-root handling. Derivative consumers inherit that same ordering. Raw point arrays with an incompatible count are rejected. Original record numbers remain in mesh labels and signed-weight diagnostics. Nonzero weights, CDA, volume, spin or inertia remain active; no anchor moves or tolerance-based zeroing occur.

| Original scope | Result |
|---|---|
| AE1 Pazy, two null weights at .558 | Unchanged source constructs an 80-interval mesh; source-coupled setup and finite residual pass. |
| ST2 undeformed/gravity modal models, four null weights | Both source-dynamic setups pass; no modal acceptance claimed. |
| Four ST2 static model copies, eight nonzero weights | Out-of-range .558 anchors still reject. |

152 focused tests passed in 38.63 seconds, including 43 new checks. Tests distinguish every physical field (positive and negative tiny nonzero values), scaled/defaulted fields, later activation by edits, active/null indexing, aerodynamic and inertial residuals, geometry/circulation derivatives, flap/engine controls, original-source preservation and separate sensor/engine/external-load anchors. Two initial test assertions were corrected to recognize existing negative-CDA/Vol validation preceding anchor validation. No physical acceptance threshold changed.

No new standalone equilibrium solve was needed. Existing regression suites include their synthetic solves. Historical AE1/ST2 comparison remains to be run against the fresh kernel. Exact sources, seven original model pins, code pins and terminal receipts are in the adjacent JSON files.
