# Renderer diagnostics: incomplete graphics validation

This is the historical five-attempt record. Subsequent bounded tests and the
integrated renderer change are recorded separately in [renderer-fix.md](renderer-fix.md).
The original outcomes and archive below remain unchanged.

Five bounded fixture runs separate idle rendering from numerical work. None imports the numerical kernel or WASM. The original renderer and three diagnostic variants use the same Mesa/Vulkan/Chromium environment except for the explicitly recorded compositing-flag experiment. Every run retained a 100-second hard wall guard, 1,048,576 KiB GPU resident-memory ceiling and 2,097,152 KiB minimum host available-memory threshold. The original static runner samples resources after initial readiness; its guards do not establish a measured memory bound before WebGL initializes.

| Attempt | Outcome | Maximum observed GPU RSS (KiB) | Completed evidence |
| --- | --- | ---: | --- |
| Original continuous renderer | Failed resource guard | 1,118,408 | Seven complete samples, frames 9–79; constant 5 geometries, 4 programs, 1 texture. Eighth resource sample crossed the guard. |
| On-demand candidate, static workflow | Passed | 231,932 | Sixteen samples, frames 2–6; zero frame growth in both idle intervals; top view, changed geometry, grid and mobile checks. |
| Candidate with explicit fit invalidation, interaction workflow | Failed resource guard | 1,069,288 | Initial idle, top view and front view passed. Stopped during orbit/damping settlement; animation and restoration checks were not reached. |
| Original renderer, only `--disable-gpu-compositing` removed | Failed WebGL initialization | Unmeasured | `THREE.WebGLRenderer: Error creating WebGL context.` Initial ready/render wait expired at 15 seconds. No render/resource samples. |
| Original renderer plus `gl.finish()` after each render | Failed resource guard | 1,108,764 | Seven complete samples, frames 8–80; constant 5 geometries, 4 programs, 1 texture. Eighth resource sample crossed the guard. |

The static on-demand result supports stopping unnecessary idle draws. It does not establish acceptable memory behavior during normal interaction or playback. The fit-hardened candidate still exceeded the unchanged GPU ceiling during orbit/damping. Removing the compositing flag prevented WebGL initialization, and waiting for GL command completion did not prevent rapid GPU-process memory growth. These observations do not identify a graphics-driver defect or its cause. They do not prove why the earlier unloaded-wing browser context was lost or why its follow-up processes disappeared. No tested application renderer repair or replacement graphics configuration has passed the required interaction coverage.

No main source file was edited. `interaction/viewer-production-candidate.js` is the unintegrated candidate with explicit fit invalidation and no probe global; its SHA256 is `be001bee2452c91dcb07bfbdaa032bbf1714c53ea1117b5ed97c4cb2b7a39709`. The isolated interaction copy adds precisely the probe assignment shown in `interaction/instrumentation-only.diff`. Read `interaction/REVIEW.md` for the code-path review and remaining lifecycle checks. The interaction test contains ready checks for wheel zoom, 24 geometry updates and pause, ground/grid, mobile, synthetic context loss with updates and restoration, and clearing/repopulating geometry; these checks were not reached in the failed run.

The initial, top and front interaction screenshots were visually inspected. The initial image shows the segmented vertical wing; top and front are edge-on views for this fixture and show the corresponding grid and axes. Their changed pixels confirm a camera redraw, not completion of the remaining interaction workflow. The parent inspected the three passing static-candidate screenshots separately.

The [summary](renderer-diagnostics.json) is derived from the retained run records. Original status fields remain untouched, including an unfinished per-variant status inside a terminal failed run. `original/run-01/runner.mjs` preserves the exact first runner; later runs pin their respective runner versions. Every preparation pin and recorded runner hash is checked by the portable archive verifier. `history/viewer-review-evidence.zip` retains the earlier two-failure review bundle unchanged. External browser/Mesa executables are not bundled; original environment paths and flags are provenance, not a portable browser launch recipe.

Extract `verify_archive.py` from the [evidence archive](renderer-diagnostics-records.zip), then audit it without running browsers or numerical work:

```sh
python3 verify_archive.py renderer-diagnostics-records.zip
```

The audit verifies bytes, preparation pins, terminal statuses, resource summaries and the original runner version. An evidence-audit pass leaves graphics acceptance incomplete. All graphics runs stopped after the `gl.finish()` failure; no timeout, resource limit or assertion was relaxed and no failed attempt was overwritten.
