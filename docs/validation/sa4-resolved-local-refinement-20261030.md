# SA-4 resolved local geometry and nonlinear follow-up

2026-10-30. Resolving the narrow quarter-chord bend does **not** settle the
current force-point velocity at fixed circulation. The measured logarithmic
growth matches the coefficient derived from the local bound-line curvature
and shared wake. This makes a resolution-only explanation insufficient for
the observed local field problem; it does not establish a native-ASWING fix.

The [field study](../../artifacts/isae/sa4-resolved-local-refinement-20261030/report.md)
retains all six saved SA-4 loadings, three fixed material locations and nine
local resolutions, plus an exterior-grid check: **180 configurations**.
The finest local interval is 0.3905% of the measured tangent-transition width.
All **162/162** finest slope checks pass; maximum force-point bound-slope error
is **0.01320%**. The same logarithmic growth is absent at the downstream
control point in this test. All **1,080** independent long-double velocity
comparisons pass, with maximum scaled component error **4.48e−10**.

The [nonlinear follow-up](../../artifacts/isae/sa4-resolved-local-refinement-20261030/solve-report.md)
completes **24 cold calls**, with no timeouts:

- Six original-mesh replays reproduce saved CL/CD/CDi/near-CDi/Cm exactly and
  remain valid.
- Twelve locally refined K18/K36 solves converge their modal projections but
  fail the unchanged normal-Mach gate; local residuals remain large.
- Six complete pointwise solves use those same finest refined meshes. Three
  converge their local equations but fail the Mach gate; three fail nonlinear
  convergence. No refined solve is accepted.

The extreme local Mach values describe rejected states, not plausible
physical flows. The pointwise results show that the observed failures are
not removed simply by replacing the retained modal approximation with one
unknown per strip. They do not prove uniqueness, exclude every alternative
branch, or establish a complete whole-wing refinement limit.

Original model, natural splines, wind alignment, shared wake origins, all
neighboring sources and the own-bound convention are retained. No physical
gate, production equation, public mesh limit or browser bundle changes.
All attempted cases and exceptions remain in the records. The source-line
endpoint and singular force-sampling conventions still need stronger native
evidence; this study does not authorize a core, neighbor removal, fitted
correction or another code’s geometry treatment.

**SA-4 remains 562/588** in its qualified complete two-table configuration.
Default registered counts and the other ISAE case statuses are unchanged.
