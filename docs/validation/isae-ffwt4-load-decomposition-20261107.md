# FFWT-4 circulation and mesh-spacing diagnostic

The FFWT-4 native score remains **200/8,000 at 5%**. This study adds no
native matches. The last increase in the tracked native pass count was
2026-11-06 at 04:25:51 UTC; the later denominator increase includes all
40 archived histories. No whole-family validation is claimed.

The current frozen Flare20 coupled equilibrium completes at 419 nodes, but
the 211/419 comparison still passes **0/7** original mesh checks, with
changes of **0.142–0.256%** against the unchanged 0.1% limit. The calculations
below isolate the aerodynamic part using a prescribed shape. They do not
replace those coupled checks.

## What causes the fixed-shape moment change?

The main beam is straight and the two rigid tips retain identical prescribed
fold angles on every mesh. Conditions are 22 m/s, 6° incidence and 16° sideslip.
Vortex influence matrices are frozen on the undeformed geometry. The literal
shared physical index retains zero mutual vortex core. Historical ASWING K/F
settings remain unknown.

The negative-half aerodynamic moment change from 211 to 419 nodes separates as:

| Contribution | Signed change in Mx (N m) |
| --- | ---: |
| Changed circulation in the free-stream lift term | -0.0016139601553 |
| Changed sampling positions in that term | +0.0001196228065 |
| Direct induced-velocity lift term | -0.0000000001257 |
| Total aerodynamic moment | -0.0014943374744 |

The remaining force terms are negligible for this diagnostic. Circulation
and sampling changes partially cancel, which explains why a smaller change
on a coarse pair did not establish convergence. The main sensitivity is in
the solved circulation distribution, rather than the direct induced-velocity
moment or a structural iteration in this prescribed-shape calculation.

## Independent calculation and endpoint spacing

An independent scalar planar horseshoe calculation uses closed-form vortex
integrals and its own nonlinear circulation solve, retaining the smooth
stall-leakage equation. It does not call the production vortex routine or
circulation solver. For the archived 107/211/419 meshes, circulation agrees
with production to **8.67e-14** on the scale `1 + abs(Gamma)`. Nine checks
against numerical Biot–Savart line integration and internal-wake cancellation
pass. This supports the implementation of these specific frozen planar
influences; it does not authenticate all ASWING setup conventions.

The alternative refinement inserts midpoints in each logical beam's Glauert
angle instead of its material coordinate. It preserves the original 55-node
anchors, the per-beam sampling convention and the physical equations. Changes
below are divided by the magnitude of the finer result.

| Nodes | Original refinement Mx (N m) | Change | Endpoint-clustered refinement Mx (N m) | Change |
| ---: | ---: | ---: | ---: | ---: |
| 107 | -0.9613972505 | — | -0.9636174677 | — |
| 211 | -0.9626730767 | 0.132530% | -0.9653729300 | 0.181843% |
| 419 | -0.9641674142 | 0.154987% | -0.9665114827 | 0.117800% |
| 835 | -0.9653907797 | 0.126722% | -0.9671452961 | **0.065534%** |

Endpoint clustering improves the finest adjacent comparison enough to pass
the 0.1% limit for this one moment. Full coupled fields, absolute discretization
error and gust histories remain unverified. No production mesh default changed.
All twelve successful independent solves have normalized flow residuals below
1e-12; the largest is 7.37e-13. The four endpoint-spacing child processes each
have a retained successful exit receipt, use one BLAS thread and a 512 MiB
memory limit, and finish within their 60-second process limits.

A separate diagnostic samples over one physical span instead of separate
logical beam spans. Its finest moment change is 0.008267%, but that convention
has not been authenticated for the native case and is not adopted. Better
agreement or faster convergence alone does not establish the correct setup.

## Next comparison milestone

Prioritize another complete, currently uncomputed FFWT-4 native gust history,
starting with the next fixed-wing history using the working solver. Retain
the source settings, report all 200 archived values and their errors, and
report time/mesh qualification separately. Do not count synthetic checks or
repeated targets as new native passes. Existing numerical gates remain in
force; completing a comparison does not by itself validate the family.

The folding-wing follow-up now has a specific spacing candidate, rather than
another unexplained global refinement. Its coupled mesh checks, native K/F
setting and attachment semantics remain open. The partial Fixed-1 refined
history remains saved at 1,162/1,592 steps and is not counted again.

## Reproducible evidence

- [Exact signed load decomposition](../../artifacts/isae/ffwt4-load-decomposition-20261107/sampling-decomposition.json)
- [Independent reference plan, input hashes and declared revisions](../../artifacts/isae/ffwt4-load-decomposition-20261107/reference-plan-v3.json)
- [Independent reference helper](../../scripts/isae_ffwt4_planar_reference.py)
- [835-node endpoint-spacing result](../../artifacts/isae/ffwt4-load-decomposition-20261107/reference-logical-835-glauert-refinement.json)
- [Successful 835-node process receipt](../../artifacts/isae/ffwt4-load-decomposition-20261107/reference-logical-835-glauert-refinement-execution.json)
- [Nine passing quadrature checks](../../artifacts/isae/ffwt4-load-decomposition-20261107/reference-quadrature-tests-v2.xml)

Earlier diagnostic failures remain in the same artifact directory: an invalid
beam-property lookup, a tuple/list scope assertion, and one insufficiently
resolved numerical quadrature. The quadrature fix splits at closest approach;
its acceptance tolerance is unchanged. The final four process receipts are
the execution evidence; their former outer session handle is no longer
available and was not restarted. No production kernel change was made in
this diagnostic, and previous browser verification is not presented as a
new run.
