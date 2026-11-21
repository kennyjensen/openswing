# Steady clamped roots on an ideal solid wall

2026-10-25. Production support now admits an explicitly clamped thin-wing
endpoint on a solid image plane. This removes the root-contact rejection for
the **derived** Pazy half-wing configuration. It does not repair the literal
ISAE model's out-of-range attachment, establish experimental agreement, or
implement unsteady wall-root motion. Coverage remains **18 partial / 23 pending /
0 fully validated**; the overall goal remains incomplete.

## Physical scope and numerical method

A supported mount requires an explicit type-0 structural Ground constraint at
a lifting beam's physical endpoint. Both ends of its entire undeformed and
current root chord must lie on a solid (`ground_effect=1`) image plane within
32 machine epsilons times the model geometry scale. This is roundoff allowance,
not an epsilon stand-off or a moved image plane. The imposed wind must be
parallel to the wall. Gusts, frame motion, elastic rates, circulation rate and
engines are rejected for this initial steady implementation. A zero-rate
`NetworkMotion` is accepted; unknown motion objects are rejected explicitly.
Free-surface, hinged, unclamped, interior-chord and other geometry contact remain
rejected. A point mass on the eligible root is accepted only when its drag area
and volume are both zero; its mass and inertia are retained.

The image-vortex/source equations, aerodynamic loads, constitutive properties
and clamp equations are unchanged. Physical residuals and Newton trial states
retain strict clearance checks. Finite-difference Jacobians need a smooth
extension away from the root constraint: the private derivative context admits
only the already validated root chord and inert root-point geometry, within
one eighth of the nearest positive sample/receiver clearance. A changed plane,
other crossing geometry or an invalid nested base is rejected. Context exit
invalidates the aerodynamic cache, including on exceptions.

At a valid constrained state, the six clamp equations impose zero root-pose
increment. Changing only those off-constraint Jacobian columns therefore leaves
the free-coordinate solution and recovered reaction increments unchanged. The
regression randomizes those columns to check this constrained-system invariance.
This is a declared mathematical continuation, not physical contact tolerance or
a claim of historical ASWING code equivalence. Apparent-mass wall corrections remain unimplemented; nonzero unsteady rates
are rejected.

## Verification

The 11 new regression cases pass across 13 executions. They cover straight and
curved image/mirror loads at Mach 0 and 0.55, retained root point-mass records, image
receiver masks, zero wall-normal induced velocity, strict contact/flow guards,
bounded derivative contexts, complete and structured Jacobians, constrained
extension invariance, coupled half/full solutions, native half-wing equilibrium
and public saved-state reuse. The final reuse check compares the complete saved
physical state and global loads and observes the final rank-check progress.

Exact discrete image/mirror comparisons use a declared **test-only shared
mesh adapter**: whole-beam Glauert receiver fractions differ between native
half and full meshes even when their physical panel endpoints coincide. The
adapter changes only the test discretization; it does not alter a guard,
aerodynamic field or solver. Separate native-half and Pazy checks use the
unmodified public discretization. Thus exact shared-grid equivalence is not
claimed for two independently generated native meshes.

The 23 existing ground, AE-1 and structured-ground tests pass in 58.88 seconds
on the initial candidate. Ten new tests passed with stable source pins before
the later unknown-motion-object guard. A subsequent passing single test overlapped
that guard edit; its before/after pins are retained and it is not counted as a
stable final-source run. Two final tests repeat the rate guard and exercise
saved-state reuse against all 112 stable source/test pins. There were no failed
tests and no weakened tolerances. Historical source bytes and all receipts are
retained; this is not a claim that the entire suite was rerun on the final source.

The fixed gates include rigid image/mirror relative/absolute 3e-10/3e-11,
wall-normal velocity 1e-13, coupled state/field 2e-7/2e-9, constrained-extension
response 2e-10/2e-11, fresh coupled residual 1e-10, and saved-state reuse
2e-8/2e-9. Full-Jacobian directional differences use 2e-5/2e-6 for the existing
forward-difference implementation. See the machine report for the full receipt.

## Derived Pazy result

One fresh 30-interval half-wing solve uses the already documented primary-property
reconstruction, 5 degrees incidence, 30 m/s, density 1.23 kg/m³, Mach 0, zero
Earth gravity and a solid wall with body normal `(0,1,0)`. The original
6.1185/rad lift slope is retained. The complete 28-field condition, ASW text,
explicit panel nodes, state and output are archived.

| Quantity | Final native result |
|---|---:|
| Solve plus output/fresh residual check | 3.55910 s |
| Fresh maximum scaled residual | 1.21518e-14 |
| Root-pose error | 1.68426e-29 |
| Tip midchord vertical displacement / nominal semispan | 9.5488328% |
| Projected tip twist | 0.5752452 degrees |

All 111 production-module hashes are unchanged over this final run. The output
is a physical evaluation, with the derivative-probe flag false. An earlier
3.30427-second run is retained separately; the final source-frozen result above
is authoritative. These are timings on this host, not a general browser or
performance guarantee.

The historical native full-mirror mesh gives 9.5443491% and 0.5754911 degrees
at this condition. The small differences are not a matched-discretization check
or an improvement in experimental agreement. No full half-wing sweep or mesh
convergence study was performed here. The prior experimental comparisons,
source pins and their unresolved displacement/twist differences remain unchanged.

## Browser and source transition

The built application passes **693/693 browser checks** in offline Chromium.
After the local runtime becomes ready, one cold mounted solve completes in
7.83258 seconds. All 4,536 numeric physical values agree with the final native
result within the fixed 2e-8 absolute plus 2e-8 relative gate; the largest
absolute difference is 1.40332e-13. Root-pose error is 2.80008e-30. The test also
checks all physical/non-numeric leaves, raw export, displayed progress and
111-module native/source/public/dist identity before and after the run.
Routine evaluation counts and the documented zero-gravity source label are
excluded, with the physical equivalences stated in the machine report.

A separate request moves the aircraft 1 mm through the wall and is visibly
rejected in 0.68710 seconds, without a result or positive-load continuation.
Exactly one equilibrium and one expected rejection were requested. No network
requests occurred after offline mode; there were no page errors or network
failures. Runtime startup took 29.07291 seconds and the whole browser exercise
55.80051 seconds on this host. Solve timing excludes runtime initialization;
this does not establish cross-device performance.

The screenshots show scalar results, the circulation plot and the expected
collision message, but the 3D viewport appears blank white. Geometry rendering
is therefore **not accepted by this test**; its cause remains a separate
open visual issue. Read-only comparison finds the same browser flags and frontend
asset hashes as the earlier successful full-wing run, and finite/nonempty
30-panel half-wing geometry. A headless context/compositor/capture issue is
plausible, but no canvas/context/GPU diagnostics were recorded to establish a
cause. This does not alter the exported solver comparisons.

The first browser attempt failed before Chromium startup because its shared
library path was missing; all 337 source/build preflight checks had passed and
no physics ran. Restoring the prior AE-1 host-library environment fixed startup.
The driver, production source, built app and numerical gates were unchanged.
Both attempts and their process receipts are retained. The local production
build passes; no hosted deployment is performed by this work.

Four production modules integrate the guard and derivative context, and the
new `wall_root.py` raises the kernel count from 110 to 111. The
[source transition](isae-ae1-wall-root-source.json) retains before/after hashes;
old studies remain historical rather than being relabelled as fresh runs.

## Remaining ISAE work

A fresh geometry-only construction of the unchanged literal `Pazy_wing.asw`
still raises `Attachment station is outside beam 1's parameter range.` Its
Weight station 0.558 lies beyond the 0.55 beam domain. No station is clamped,
dropped or silently moved. Resolve the intended attachment from source evidence
before claiming a literal-file solve. Independent section data, measurement
axes/uncertainty, the experiment's finite fixture versus ideal-wall assumption,
and the published high-speed dynamics remain open. General moving/unsteady
wall-root support needs the missing physics and independent validation.

The [machine-readable result](isae-ae1-wall-root.json),
[source transition](isae-ae1-wall-root-source.json),
[execution receipt](isae-ae1-wall-root-execution.json) and
[bounded evidence archive](isae-ae1-wall-root-20261025-evidence.zip)
retain the successful checks and their limits. No family is promoted by this
implementation increment.

Archive paths: stage-relative filenames in the machine report resolve under
`stage/` in the evidence ZIP; test attempt receipt names resolve under
`stage/tests/`. `MANIFEST.json` maps historical absolute paths to bundled members.
The [archive receipt](isae-ae1-wall-root-archive.json) is outside its own ZIP.
