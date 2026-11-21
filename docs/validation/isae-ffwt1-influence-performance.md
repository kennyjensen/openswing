# Influence performance and mounted geometry reuse

Updated 2026-10-16. This records the revision-05 numerical/performance follow-up to
the [influence integration](isae-ffwt1-influence-integration.md). It does not
establish experimental validation or original-ASWING parity. Coverage remains
**17 partial / 24 pending / 0 fully validated**. No original ASWING executable
is available for comparison. The later
[sparse wake release](isae-ffwt1-sparse-wake-performance.md) supersedes this
revision's runtime and release status; the original outcomes below are retained.

## Source changes

The vector influence operator now stores its bound and wake-ray coefficients
in contiguous matrices and applies them with separate matrix products. Shared
wake strengths are still combined before multiplying large ray coefficients.
Matrix directions share the incidence calculation; cache updates preserve the
packed storage and immutable ownership. Bound and ray coefficients are not
pre-added. A separate graph-compression prototype was rejected after a
synthetic coefficient-arithmetic counterexample; that counterexample is not a
demonstrated physical-vortex failure.

Mounted full Newton corrections now explicitly request the complete geometry
decomposition already available to frequency analysis. This includes moving
field, local structural and circulation terms. Unsupported geometry retains
the original physical stencil. An explicit disabling option preserves the
original Jacobian path for comparisons; no persistent frequency-mode flag is
changed. Solver acceptance and continuation defaults are unchanged.

The wider tests exposed an arithmetic mismatch in full physical geometry
samples: they projected an already-contracted velocity, while the aerodynamic
residual projects coefficients before applying circulation. Revision 05 makes
those physical samples use the same scalar projection. Retained linear field
maps keep their existing derivative approximation. The original failed test
is retained, and its tolerance was not changed.

## Default Daedalus mounted case

The cold case uses the literal `examples/dae.asw`, 48 discretization intervals,
30 ft/s, 5 degrees incidence and Mach 0.1, with otherwise unchanged defaults.
The assembled network has 275 nodes, 270 elements, 217 circulation unknowns
and 3,517 steady unknowns. The fixture is checked through the existing identity
validator, including its coordinate-roundoff allowance; it is not used as a
starting guess.

| Check | Result |
| --- | --- |
| Released baseline cold attempt | Process capped at 240 s; no returned equilibrium |
| Packed revision 03, before mounted routing change | Process capped at 240 s; no returned equilibrium |
| Revision 05 cold solve | Returned in 179.233 s while other functional checks ran |
| Fresh full physical residual, new state | 8.50847e-14 |
| Fresh full physical residual, saved fixture | 8.27476e-14 |
| State, circulation, node, load and residual arrays | All 11 comparisons passed their existing bounds |
| Complete recovered-output comparison | Failed: 10 of 43,962 numeric fields exceeded existing bounds |

All three full Newton tangents used the complete geometry path, with 1,650
direct geometry columns, two field evaluations each and no unsupported
geometry, vortex, volume or structural fallbacks. The first two tangents took
45.619 and 44.847 seconds. These are observed concurrent-run timings, not an
uncontended speed ratio or an original-ASWING timing comparison.

The ten failed fields are signed/absolute shell shear-stress pairs at five
Tailboom elements. Their unchanged area-times-thickness is 0.000232 ft³.
Local torque changes of about 3.04e-10 lb·ft are amplified by division by twice
that value, producing stress differences up to 6.56204e-7 lb/ft², or about
1.93e-8 relative. A 100-digit replay of stored values attributes more than
98% of the difference to changed global moments; recovery roundoff is at most
1.083e-14 lb/ft². This is sensitivity to tiny differences in accepted states,
not an identified stress-recovery arithmetic defect. The original
`1e-8 + 1e-8*abs(reference)` output gate remains failed.

## Other performance and runtime evidence

An earlier frozen packed revision 02 reduced the Daedalus rigid overhead
relative to the initial integration. Its quiet native medians were 0.200512 s
for the released baseline and 0.228154 s for the candidate. Flexible-wing
medians were 0.015306 s and 0.019891 s. All physical-output comparisons passed,
but both candidates remained slower than the released baseline. These numbers
predate batched incidence and the later geometry changes.

Actual offline browser rigid checks used the unchanged served UI with the
candidate kernel injected only into its fresh context. Baseline and revision
04 both passed, including 12,754 numeric and 825 exact output comparisons,
complete exports and verified module/runtime bytes. Observed worker completion
was 1.456 s and 1.662 s; concurrent work prevents a speedup claim. The original
aircraft screenshots were identically blank. A separate view-only baseline
refit rendered the aircraft correctly without a solve, supporting a capture
or redraw issue; its exact trigger was not isolated.

Revision 05 passes all 269 native regression tests in 523.23 seconds, including
geometry, cache, frequency, time, output and seven mounted-path cases. Its 51
coefficient and three independent physical-field WASM checks also pass. Five
targeted native checks passed after the projection repair, including the
unchanged strict full-mesh Daedalus stencil test. Earlier failures remain in
the [evidence summary](isae-ffwt1-influence-performance.json).

## Remaining work

The mounted full-output fixture gate still fails. Full-scale mounted browser
execution and publication therefore remain unperformed. The source tree has
105 kernel modules; the served 104-module release, application assets and
production process remain unchanged.

The direct geometry path still spends substantial time in wake-derivative
composition. A separate prototype skips exactly zero endpoint groups and core
directions while preserving receiver-dependent core exclusions and independently
moving source ownership. Its 127 targeted checks pass. In one fresh sequential
comparison, a complete 3,517-by-3,517 tangent took 78.365 seconds with revision
05 and 5.805 seconds with the prototype. All 12,369,289 matrix entries and the
before/after residuals were bitwise identical. This is a single tangent timing,
not a complete-solve or browser speedup. Cold-solve evidence is recorded separately.
The prototype is not part of revision 05 or its evidence archive. The subsequent
[sparse wake study](isae-ffwt1-sparse-wake-performance.md) records its 41.450-second
cold solve, exact output equivalence and integration into the working source.

Further performance work, the retained stress-output discrepancy, experimental
setup questions and full ASWING feature parity remain open.

Working evidence is retained under
`/tmp/openswing-isae-ffwt1-20261015/influence-performance-17`, including frozen
source revisions, original failures, plans, native arrays, browser exports and
diagnostics. This follow-up does not supersede the earlier physical-validation
limitations or turn a numerical consistency check into an experimental pass.

The selected revision-05 evidence is available in the
[13.5 MB archive](isae-ffwt1-influence-performance-evidence.zip) with its
[member manifest](isae-ffwt1-influence-performance-evidence.json). All 1,976 ZIP
members passed CRC, size, SHA-256 and clean-extraction checks. The archive
includes all 105 source modules and retains the original failures; external
runtime dependencies and bulky profile captures are explicitly omitted.
