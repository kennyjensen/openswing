# Aircraft viewport recovery after graphics failure

2026-10-25. The blank viewport retained in the earlier
[wall-root browser check](isae-ae1-wall-root.md) was reproduced as a lost WebGL
context. The viewer now switches to its existing software projection when
WebGL fails at startup or is lost later. The focused regression and two built
application checks pass. **All rendering checks performed zero new physics
solves.** The earlier numerical dataset and experimental comparisons are unchanged.

The retained diagnostic recorded natural context loss at 2.4847 seconds. The
canvas still occupied 907 × 700 CSS pixels, but its WebGL drawing buffer was
0 × 0. Fit, mobile Plots hide/show and desktop return left the context lost.
The saved result still exported unchanged. This establishes the cause of that
reproduction; it does not diagnose every possible blank page. An earlier
diagnostic attempt failed to initialize the runtime because its temporary
server omitted the `.mjs` MIME type. That failed attempt remains recorded.

The stable viewer interface retains the latest beams, attachments and physical
ground plane, plus the selected named view and grid visibility. Recovery removes
the old canvas, renderer resources, orbit controls, animation callback, resize
observer and registered events. Late events cannot revive the old renderer.
Partial startup failures also release resources before fallback. Hidden mobile
tabs retain their scene and last valid canvas dimensions until visible again.
No geometry generation or numerical calculation changed.

The final [browser regression](../../tests/browser/viewer-recovery.spec.js)
passes **4/4 cases** against frozen source. The earlier three-case run also
passed and remains retained: seven passing executions, four distinct final
cases, no failed tests. The fixtures use chosen display coordinates and forbid
Worker construction.

| Final case | Verified behavior |
| --- | --- |
| Live WebGL context loss | Actual `WEBGL_lose_context`, retained geometry/attachments/wall/view/grid, changed animation-style update without refitting, painted output, orbit/zoom/fit controls, stale events and cleanup |
| Loss while mobile Plots is hidden | Latest scene replay, actual responsive-workbench reparenting, mobile display and desktop return, exactly one viewer canvas |
| Initial WebGL creation failure | Working software display and controls |
| Partial WebGL setup failure | Cleanup of the incomplete backend before software display |

The live-context tests used Chromium with Mesa Vulkan/lavapipe through ANGLE
(`llvmpipe`, LLVM 21.1.8). Driver paths, flags, source hashes, output hashes and
terminal process receipts are in the [machine report](isae-viewport-recovery.json).

The real built application was then exercised through project import, saved
solution loading, view controls, mobile navigation and result export:

| Graphics setup | Observed path | Whole check | Result |
| --- | --- | ---: | --- |
| Mesa Vulkan | Visible WebGL geometry, then forced context loss and software recovery | 34.34 s | Pass |
| SwiftShader configuration | WebGL creation failed; software fallback worked from startup | 34.83 s | Pass |

The SwiftShader run is **not** a successful SwiftShader WebGL test. Its retained
console reports missing `OES_packed_depth_stencil` support and WebGL2 creation
failure. Both application checks have no page errors; graphics/readback warnings
and a local 404 remain in their logs. Each made only two `inspect` and two
`distribution` requests. Each re-exported all 230,992 bytes of the original
result identically. Desktop and mobile pixel checks confirmed visible geometry;
the Mesa screenshots also received visual inspection. Both processes exited
successfully and were reaped. These elapsed times include runtime startup and
display operations, and are not solver performance measurements.

The displayed data come from the **previously computed derived primary-property
Pazy half-wing**, at 5° incidence and 30 m/s, with 30 intervals, density
1.23 kg/m³, Mach 0, zero Earth gravity and an ideal solid wall of body normal
`(0,1,0)`. Its skin-on Technion section properties and CONM2-audited inertia
mapping originate in the pinned primary AePW3 dataset; section aerodynamic
defaults come from the literal ISAE input. The declared stiffness projection
and other reconstruction assumptions remain those of the
[prior model study](isae-ae1-pilot.md) and
[source record](isae-ae1-source-readiness.json). This is a computed derived model,
not measured geometry or the separate conditional literal-model gravity pilot.

To display it without recomputing, import
[the saved half-wing project](../../examples/pazy-isae-wall-half-project.json)
through **Project & saved cases → Open project**, then choose **Open solution**.
This file contains both the editable configuration and the existing computed
solution. Its bytes match the project used in the two application checks.

Recovery refits the last named view: a manual orbit/zoom pose is not transferred
between GPU and software projections. Shading can differ. Coverage here is
software-driver Chromium and responsive layouts, not every GPU, browser or
physical mobile device. This change resolves the retained viewport failure;
it does not establish Pazy experimental agreement or complete ISAE validation.

The [bounded evidence archive](isae-ae1-literal-and-viewer-20261025-evidence.zip)
retains the rendering records separately from the conditional literal pilot.
Its [archive receipt](isae-ae1-literal-and-viewer-archive.json) records packaging
verification; the machine report pins the original sources and saved inputs.
