# Source-preserving rigid point attachments

The three driver-selected FFWT-4 PM2 models now load and mesh with their
original source records in CPython and the built browser app. Analysis
anchors Weight 52 on beam 2 at +0.364 instead of +0.3521, and Weight 57 on
beam 3 at -0.364 instead of -0.3521. Their physical XYZ coordinates, mass,
inertia and spin do not change. The original `.asw` text also remains intact,
including after an unrelated property edit and serialization.

This is the explicit `whole-rigid-beam-endpoint-pylon-v1` analysis policy,
supported by the completed [section-load and steady-matrix](isae-ffwt4-rigid-extension-20261106.md),
[integrated oscillator](isae-ffwt4-rigid-time-20261106.md) and
[continuous dynamic-matrix](isae-ffwt4-rigid-dynamic-20261106.md) studies.
It does **not** establish native ASWING out-of-range input semantics.
FFWT-4 remains **200/8,000**; this work adds no native comparison passes.

## Eligibility and implementation

The resolver first retains the existing exact-decimal station aliases. An
out-of-domain mechanical Weight can then use the nearest endpoint only if
the entire beam is exactly rigid and has zero material damping. All six
diagonal stiffness tables must be absent or contain only literal scaled
zeros, the ASW infinite-stiffness encoding. Cross stiffnesses and both damping
tables must be absent or exactly zero. Complete current tables and compiled
interpolants must agree; mesh sampling or large finite stiffness is not a
certificate. Point CDA and volume must be zero. Other invalid anchors retain
the existing validation failure.

Meshing, structural/dynamic analysis, pylon display and wall-root handling
share this resolver. The source serializer continues using only the original
exact-decimal alias resolver. Analysis results and saved-state identities
record each affected source record, beam, original/effective anchor, physical
point position and policy. Unaffected equilibrium identities retain their
previous fields. Affected checkpoints reject missing or changed metadata.
The browser displays the qualification under **ASWING input compatibility**.

## Verification

| Check group | Result | Scope |
| --- | --- | --- |
| Attachment and null-object checks | 84 passed | Source preservation; exact eligibility; edited-table rejection; both beam ends and material charts; original PM2 meshes under both interpolation policies; independent moving-point section loads; saved states |
| Decimal-station and wall-root regressions | 44 passed | Exact aliases remain separate; flexible adjacent/out-of-range stations still reject; unchanged row ownership and wall-root behavior |
| Time-checkpoint rechecks | 2 passed | Midpoint and source moving equations; two steps and one resumed step per formulation; altered/missing policy rejected |
| Built browser checks | 21 passed | Three exact source imports, visible notes, source preservation, independent point force/moment, source time continuation, checkpoint rejection, no page errors or external requests |
| Local application build | Passed | Current 138-module kernel packaged and loaded by the browser worker |

The checkpoint group overlaps the earlier group and must not be added as
independent physical cases. Browser imports are paired with their exact
source-bearing worker requests; merely observing a previous result is
insufficient. The final screenshot was visually inspected.

Evidence is in `artifacts/isae/rigid-attachment-production-20261106/`:
`pytest-final.xml`, `regression-final.xml`, `source-time.xml`, `build.log`,
and `browser-verified/report.json`. The browser report authenticates all
loaded kernel modules; its directory retains inputs, full mechanical/time
outputs, the executed runner and the screenshot.

Early failed attempts remain available. The first new fixture omitted its
required Unit block; later position assertions incorrectly demanded bitwise
equality after subtraction/addition (maximum discrepancy 8.33e-17). Raw source
records still require exact equality. Regression expectations were updated
to isolate decimal aliasing on a flexible beam and to check row ownership
instead of the list already copied by prior null-object filtering. The first
browser mechanical request used an unsupported static route; it was corrected
to the public midpoint static API, while time checks use the source moving
API. A subsequent import-test race was corrected before the final browser
verification. No physical or native acceptance gate was relaxed.

The pre-change kernel is preserved at
`.reference/solver-snapshots/ffwt4-before-rigid-attachment-20261106/`.
The ongoing Fixed-1 refinement continues to use its separate older pinned
kernel. Historical source audits and their original six mesh rejections
remain unchanged as historical evidence.

## Coupled PM2 preflight and remaining work

A bounded cold Flare20 equilibrium is recorded separately under
`flare20-n8/`, using the literal PM2 source, alpha 6°, speed 22 and its
explicit beta 16°. The nominal eight-interval mesh has 55 actual nodes,
52 elements and 712 unknowns; it is not the original 100/40/40 driver mesh.
The process **hit its 150-second limit (exit 124)** without a converged
result. Its request, full progress log and terminal receipt are retained.
No native values are added by this preflight.

The initial grouped matrix took about 2.27 seconds, but the rank check then
requested a full 712-column finite-difference matrix taking 78.07 seconds.
The solve subsequently tried progressively smaller load fractions; the last
reported attempted fraction was 9.966e-6. A separate bounded diagnostic
reproduces the grouped matrix in 2.66 seconds: both existing mechanical rank
certificates are inconclusive, the circulation block is nonsingular, and
force/circulation coupling is exactly zero at zero load. The physical rigid
tree certificate does not cover this operator, and the main beam has finite
compliance, so that rigid-only proof cannot simply be enabled. The optional
initial-load predictor also declines this source operator. These are concrete
startup targets for further work, not permission to bypass a rank or residual
gate. See `startup-diagnostic.json` and its retained script.

Native semantics, historical defaults, complete PM2 gust histories and
spatial/time refinement remain open. General point-airflow support and
three-dimensional integrated motion require further checks. Finite-BDF
differences between explicit extensions and endpoint pylons remain real;
the continuous equivalence proof is not permission to skip refinement.
