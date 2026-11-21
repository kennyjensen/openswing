# FFWT-4 fixed-wing gust comparison

Follow-up: the [full-history half-step study](isae-ffwt4-refinement-20261106.md)
passes the same native targets but only 1/2 strict time-accuracy gates. This
page retains the original dt=0.0149 s results.

The literal Fixed-1 history passes **200/200** archived root-moment values at
5%, or **200/1,600** across all eight fixed-wing histories. The retained chain
reaches 2.9651 s, covering the gust and subsequent decay. Median/max error is
0.531%/0.631%, with maximum state residual 9.238e-9. All 199 retained steps
converge without rejection. Other histories and mesh/time convergence remain
open; passing this history does not validate the entire FFWT-4 family.

![Archived ASWING and OpenSwing first fixed-wing gust history](../../artifacts/isae/ffwt4-time-20261106/plots-s199/comparison.png)

The earlier [initial-state study](isae-ffwt4-initial-20261106.md) remains
separate evidence. All literal physical inputs, nominal32 mesh, circulation
settings, BDF2 scheme with its original BDF1 startup, dt=.0149, and residual
tolerance 1e-8 are unchanged. No amplitude, phase, mass or stiffness is fitted.

A first 20-step continuation solved through 0.596 s but failed while building
the indented JSON string under the 512 MiB address-space cap. Its `s040`
directory has no complete result/report/checkpoint and contributes no reference
passes. The new `verify-isae-ffwt4-time-v2.py` streams JSON to a temporary file
and then renames it; 10- and 20-step jobs from the original verified checkpoint
complete within the same cap. The last job contains 19 steps. The original
helper remains unchanged to preserve its
source pins. Checkpoint resumes retain integration order and replay the saved
discrete state.

`scripts/assess-isae-ffwt4-time.py` independently traverses the complete ancestry,
checks every source/kernel/helper and result hash, verifies contiguous accepted
states, and rejects invalid residuals, changed root traces and integration
restarts. All 1,600 original fixed-wing values remain explicit, including
1,400 uncomputed ones. The first table has 200 rows including t=0. The 5%
reference policy retains native printed precision and strict near-zero handling.
All 13 focused assessment tests pass.

Evidence: `artifacts/isae/ffwt4-time-20261106/assessment-s199.json` and the
completed `s020`, `s030`, `s040-streamed`, `s060`, `s080`, `s100`, `s120`,
`s140`, `s160`, `s180`, `s199` chain. Earlier 41- and 81-value assessments
remain as historical observations. The failed `s040` attempt is retained
separately. Comparison PNG/SVG files are in `plots-s199/`; the plot uses the
native printed times and actual computed times without interpolation or
phase alignment. No physical solver equation changed; no whole-family
validation claim is made. The progress dashboard records each assessed count
change and retains all 1,600 fixed-history targets in its denominator.
