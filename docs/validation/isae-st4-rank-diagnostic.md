# ST-4 finer-mesh rank diagnosis

This is the retained dense-method diagnosis. The later
[paper-method integration](aswing-modal-integration.md) follows a different,
published local modal algorithm and succeeds on fresh finer ST-4 meshes and
in the browser. The dense-method failures below remain unresolved; they no
longer block that separate local Arnoldi comparison.

Updated 2026-10-26. The nominal 32-interval source-vacuum failure is now
reproduced with its complete matrices retained. **A safe production fix has
not been established.** Two candidate relaxations of the rank guard were
rejected after independent analytic tests exposed lost finite modes. The
production kernel has been restored byte-for-byte to the preceding verified
version (`linear_dynamics.py` SHA256
`10197034e6fe7e41901044cf86854949cdcbca9bafea7186f2a46c664d54f7b9`).

The original model, zero-gravity setup, matrix entries and requested tolerance
remain unchanged. One cold capture reproduced the original rejection in
9.09 s and retained the 612-by-612 A/M matrices. All 119 source hashes stayed
unchanged during capture. Subsequent diagnostic experiments reused saved
matrices; they did not rebuild or tune the aircraft model.

## What the evidence establishes

The raw derivative matrix has one resolved direction below the requested
cutoff: singular value 1.20009e-9 versus a cutoff of 1.41480e-9. It is about
54,047 times the existing roundoff bound. An independent reconstruction of
the literal endpoint and point-mass inertia agrees with the physical mass
block within 1.61e-16. This is a real weak inertia, not derivative noise.

About 99.43% of the rejected direction's squared coordinate amplitude is
rotation about the rigid normal-bending axis. It also violates the clamp.
The mass restricted analytically to the 66 compliant coordinates is positive;
its smallest eigenvalue is 1.52014e-7. The expected finite modal dimension is
132. The attachment creates an ordinary 0.01264 m minimum interval, not a
near-coincident mesh defect.

Fixed common row/column equilibration did not resolve the failure. Removing
exact zero-derivative rows before the existing reduction also failed. A direct
full generalized eigensolve gives spurious enormous roots when every nonzero
computed denominator is interpreted as a finite eigenvalue: 87 instead of
68 at the coarse mesh, and 163 instead of 132 at the finer mesh. That is not
a safe substitute for finite/infinite classification.

## Why the attempted fix was rejected

Provisionally retaining weak derivatives through constraint elimination
produced the expected 132 ST-4 roots and full-pencil residuals below 2.4e-16.
The original 68-root coarse census was unchanged. Those results alone did
not establish that the algorithm preserved modes in other coordinate systems.

An independent system consisting of a stable root −2 and the constrained
oscillator `epsilon*qdot=v`, `vdot=p`, `q+delta*p=0`, with
`epsilon=delta=1e-10`, has three finite roots: −2 and ±i1e10. The first
candidate could drop the oscillator pair during a later rank decision and
still pass its final mass check.

A subsequent per-step check against the original derivative matrix rejected
that aligned example. However, an independently prescribed dyadic Hadamard
row/column rotation of the same equations still returned only −2, with a
right backward residual around 8.05e-17. Its columnwise error scale could
hide a weak combination of otherwise strong columns. This counterexample
rejects the candidate despite good ST-4 residuals and many passing tests.

Both failures, source snapshots and execution receipts are retained. The
new regression tests cover these lost-mode risks. The two desired
constrained-weak-inertia acceptance cases remain strict expected failures
under the restored conservative solver; they do not count as implemented
capabilities or relaxed acceptance criteria.

## Remaining work

The later [paper-method review](aswing-modal-method.md) changes the production
direction: follow Drela's full-pencil shifted Arnoldi algorithm. Complete
finite-spectrum classification is not a prerequisite in that algorithm.
The existing local method passes checks on the saved finer matrix; custom
rank/structural reductions remain isolated and are not being promoted.

The failed dense-method tests remain failures, including both lost-mode
regressions. Any future claim to repair that reduction must address them.
The local Arnoldi comparison instead needs explicit selected-root coverage,
original-pencil residuals and fresh mesh/browser checks. No successful fresh
32/64 comparison, mesh-convergence pass or application release is claimed here.

The [machine report](isae-st4-rank-diagnostic.json) and
[evidence archive](isae-st4-rank-diagnostic-20261026-evidence.zip) retain the
diagnosis. The [preceding ST-4 comparison](isae-st4-source-modes.md) remains
the authoritative coarse reference result. The ASWING reference pass count
is unchanged, and experimental agreement remains outside the requirement.
