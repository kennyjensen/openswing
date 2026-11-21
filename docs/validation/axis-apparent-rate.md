# Apparent pitch-rate self-influence correction

The integrated correction excludes only a lifting panel's own physical bound-vortex segment from the beam-axis velocity used by apparent pitch-rate loads. Its wakes, neighboring segments, other beams, ground images, volume flow and jets remain. Independent evidence identifies a discontinuous 1/(Xax−0.25) contribution in the original implementation and a continuous finite-mesh axis limit after correction.

The [portable evidence archive](axis-apparent-rate-evidence.zip) preserves both 58-module kernels, the exact one-line change, complete independent reference sources, original records and reproducible replay commands. [Checks](axis-apparent-rate-checks.json) and [archive audit](axis-apparent-rate-archive-audit.json) retain the proof and file hashes.

| Check | Result |
|---|---|
| Historical literal-kernel loaded tangent and four harmonic frequencies | Original implementation reproduced within 2.114e-11 scaled component difference |
| Twelve axis-limit cases and analytic pole | Maximum pole-coefficient difference 8.424e-12 m/s |
| Original/corrected independent tests | Five expected original failures; five corrected passes |
| Integrated targeted native tests | 64 distinct passes, no failures/errors/skips |
| Frozen influences, Mach 0.6, two physical beams | Independent wrench difference 8.33e-17 |
| Packaged WASM | Ten axis/ground cases plus one frozen/PG/two-beam case; 288 real wrench components; maximum independent difference 2.332e-14 and native difference 5.552e-17 |
| Four modal diagnostic cases | Identical nonlinear bases; source-pinned local descriptor searches |

The historical tangent comparison reproduced the old velocity-sampling rule;
it did not validate that self-field convention. The later analytic pole,
two-sided axis limit and independently integrated corrected wrenches distinguish
the physical defect from an error in evaluating the original formula. Their
source scopes are retained separately in the archive.

The correction changes the returned 25% wing U=24 m/s pair from growing to damped; the 75% wing at 24.58 m/s retains a growing pair. Those cases do not establish a complete spectrum, refined flutter boundary, continuum limit or agreement with published flutter experiments.

The archived 1,216-test full native pass is explicitly the **pre-fix** baseline.
The post-fix snapshot contains 1,221 tests across 73 files; its full regression
is now running after the browser processes were confirmed stopped. No complete
post-fix suite pass is claimed yet. The [loaded offline browser workflow](axis-apparent-rate-browser.json) also
passes, including two corrected roots, physical mode shapes, exports and
inspected desktop/mobile WebGL captures. Maximum native/browser root component
difference is 1.79e-9 per second. The separate
[frozen/PG WASM replay](axis-apparent-rate-frozen-pg-wasm.json) passes its unchanged
1e-9 gate, with independent error 8.33e-17 and native component difference
2.78e-17. Its complete inputs, sources, outputs and terminal result are in the
adjacent ZIP. The unloaded browser attempt passed numerical/export checks but
failed on a lost WebGL context. Its instrumented follow-up reached a healthy
desktop gate but stopped without a terminal result or mobile checks. All three
attempts, source pins and severe-memory-pressure observations are preserved in
the [browser closeout](durrant-unloaded-browser-closeout.md). A subsequent
[renderer change](renderer-fix.md) and rebuilt unloaded-wing browser workflow
now pass the complete original numerical/export/desktop/mobile gates; see its
separate [record](durrant-unloaded-browser-repaired.json). The earlier loaded
workflow retains its original UI asset pins, while the numerical kernel is
unchanged by the renderer work. No full-spectrum or flutter claim follows.

After extraction, `python verify-bundle.py` audits existing evidence without numerical solves. The unchanged standalone native verifier accepts either archived kernel root. The original WASM runner accepts `--repo /path/to/checkout --execute --output /new/output`; its historical “root go” wording is workflow provenance, not a new permission requirement. Runtime binaries come from the named built checkout. Full native/tangent/modal replay instructions are in the archive README.
