# ST-4 targeted N224 refinement

At 139.5 m/s, refining the production mesh from N160 to N224 brings the
previously failing damping component within its unchanged 0.1% reference gate:
the error falls from **0.16005% to 0.08183%**. The near-zero real pole improves
from **2.73146% to 1.31931%**, but still fails. The four selected modes pass
**7/8 reference comparisons and 7/8 mesh comparisons**. These are a smaller,
separate scope from the retained 24/26 comparisons at two earlier anchors.

| Native archive ordinal, used only as a mode label | N224 pole (/s) | Fine independent reference (/s) | Real-component error | Result |
|---|---|---|---:|---|
| 3 | +0.0348991230 | +0.0353657051 | 1.31931% | Fail |
| 4 | -69.61647702 | -69.61531683 | 0.001667% | Pass |
| 5 | -3.243050064 + 96.03886017 i | -3.243508618 + 96.03647124 i | 0.014138% | Pass |
| 6 | -1.308118348 + 182.86526345 i | -1.309189652 + 182.85773271 i | 0.081830% | Pass |

All four imaginary components pass: nonzero values use the 0.1% relative gate;
near-zero values use the retained 5e-8 /s absolute gate. The slow real pole's
N160-to-N224 change is 1.43103%, also above the mesh gate. Mode-shape correlations
exceed 0.99999999 against both the independent reference and the interpolated
N160 shapes. Eight full-matrix left/right residual checks pass. Fresh nonlinear
directional checks at two state widths pass for every selected mode; the base
residual is 4.59e-16.

The original physical request, source equations, weights, gravity and airflow
are retained. N224 gives 225 elements and 226 nodes after inserting a mandatory
weight station. The full matrix dimension is 4,293. Requesting four roots near
the local search shift selects modes without removing physical coordinates.
The reference retains the earlier independent 768-strip/512-element calculation.

The direct public call saved its complete matrices, then failed at sparse
factorization under the 512 MiB address-space cap. Subsequent recovery attempts
and their failures remain in the study directory. A completed right-mode search
was reused for the successful 1 GiB capped recovery, which took 35.29 seconds
including 29.54 seconds of eigensystem work and peaked at 360.9 MiB resident
memory. This is a staged recovery, not a successful uninterrupted public solve.

A diagnostic compact CSC assembly of the Newton bordered matrix avoids sparse
intermediate copies while preserving every coefficient. It passes 32 exact
matrix comparisons and all four existing refinement tests. Sparse factor
ordering was also changed in this diagnostic. Neither change has been promoted
to the production kernel. The final public-output reconstruction reused the
saved matrices and modes and checked fresh physical equations in 26.91 seconds;
the saved-result assessment took 3.15 seconds. Its initial path-type error is
recorded separately and was fixed without changing comparison data or gates.

The [speed-sensitivity diagnostic](isae-st4-speed-sensitivity-20261104.md)
explains 99.85% of the earlier slow-pole discrepancy through the small static
divergence-speed difference. It does not correct any scored result. Native
ASWING settings and disagreements remain unresolved; no native pass, family
validation or project completion is claimed. Production kernels and the
previously verified browser distribution are unchanged.

[Portable evidence](isae-st4-targeted-refinement-20261104.json) includes the
assessment, execution receipts and source hashes. Complete matrices, vectors,
failed attempts and runners remain in
`artifacts/isae/st4-targeted-refinement-20261104/`.
