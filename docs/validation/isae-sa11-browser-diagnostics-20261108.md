# SA-11: inspect rejected local airflow in the browser

2026-11-08 UTC. SA-11 remains the priority; SA-2 stall work remains deferred.
The browser now preserves the existing structured local-Mach rejection instead
of reducing it to exception text. This is a diagnostic improvement, not an
aerodynamic correction or a new ISAE pass. The primary score remains
**163/9,184 at 5%**.

## Follow-up: partial surface forces

The [partial-force implementation](isae-sa11-partial-forces-20261108.md) now
shows the already evaluated circulatory, circulation-rate and profile forces,
their per-beam sums, and the included subtotal at Mach-invalid strips. The
separate diagnostic coefficients are explicitly incomplete and unvalidated;
pitching moment remains unavailable. Apparent mass, bodies, point drag and
engines are outside this force budget. All 26 Python, four JavaScript and one
real-worker browser checks pass. Accepted low-speed output remains exactly
unchanged. No primary passes follow.

## Follow-up: all rejected sections

The error envelope now also retains every section with `M_perp >= 1`, sorted
by Mach with stable panel-index ordering for ties. The aircraft view marks all
these force locations; the largest cross identifies the worst section. An
expandable table lists their beams, stations, Mach values and body coordinates.
Distinct frozen influence receivers remain separate from current force points.
The source-contribution table and source lines explicitly describe the worst
section only. All section records are included in the diagnostic download.

This uses existing velocity arrays; it performs no additional influence
assembly or physical solve and does not modify any velocity or acceptance
threshold. Legacy diagnostics that contain only the maximum still render.

Verification: **18 Python checks, 4 JavaScript checks and 1 real-worker browser
check pass**. The browser test took 47.78 seconds and captured both winglet roots
at Mach 1.100918 in the bundled +4° example, 240 m/s, alpha 1°, 12 requested
intervals per beam. This is distinct from the report-minus4 diagnostic studies.
The test checks the section list through the actual worker/JSON/UI path,
marker toggling, independent Horseshoes overlays, empty rejected coefficients,
disabled result export, mobile layout, and clearing on edits and a valid solve.
The Python boundary test verifies that the native exception is preserved.

Evidence: [browser report](../../artifacts/isae/sa11-all-rejected-sections-20261108/browser-report.json)
and [verification receipt](../../artifacts/isae/sa11-all-rejected-sections-20261108/verification.json).
Desktop and mobile screenshots and the exported diagnostic accompany the report
in its `browser/` subdirectory. No new primary pass or progress fraction follows.

## Inspecting the failure

When a solve rejects local section-normal Mach, the aircraft view marks the
rejected force points with red crosses and up to three strongest physical bound
segments and grouped wake rays at the worst section in cyan and violet. The ordinary Horseshoes
overlay can be displayed independently. Drawing a wake ray for one reference
span does not truncate the solver's semi-infinite vortex.

The panel below the aircraft identifies the beam, material station, Mach and
circulation residual. Its expandable table reports each source contribution's
vector magnitude and distance from the influence receiver. These magnitudes
must not be added as scalar speeds: large terms can cancel. Grouped wake terms
already combine coincident source endpoints before ranking.

All positions use body coordinates from the rejected-state evidence. Frozen
influences retain their jig positions. A distinct influence receiver is marked
in amber when it differs from the actual force point. The aircraft surface
shows the jig shape, not an accepted deformed solution. Physical source lines
do not draw ground images, although their coefficients include configured
image effects. Diagnostic overlays do not enlarge the viewer's fit bounds.

**Download diagnostic JSON** retains the error, full structured attribution,
exact numerical request and loaded kernel fingerprint. Normal result coefficient fields stay
empty and ordinary result exports stay disabled. Input/model changes and new
solve attempts clear the old diagnostic. Both GPU and software renderers use
the existing overlay interface.

The implementation changes the Python/worker transport and presentation only.
Native `run_json` callers still receive exceptions; the browser-specific wrapper
returns an error envelope without a complete result or equilibrium. No circulation equation, force
evaluation, wake geometry, stall law or Mach threshold changed.

## Verification

The native boundary/source-attribution checks pass **17/17**. The overlay
coordinate tests pass **3/3**, including distinct frozen/current receivers,
coincident receivers, unavailable attribution and nonfinite geometry guards.
The real-worker browser test exercises the SA-11 upper-winglet example at
240 input L/T, 1° and 12 default intervals per beam, with frozen influences.
This explicitly labeled example corrects original Joint-station scale errors;
it is not a replacement for the archived primary test input.

The browser integration test checks the rejection, empty coefficients, disabled
result export, marker toggling, independent Horseshoes toggling, diagnostic
download with kernel provenance, mobile layout, input invalidation and recovery
to a successful lower-speed solve. Evidence is retained under
`artifacts/isae/sa11-browser-diagnostics-20261108/`.

## Additional reference availability check

The [authoritative index](aswing-authoritative-references.md) and catalog were
consulted. No new native ASWING outputs or undocumented settings were recovered.
HAL's public metadata for the 2026 Jan aerodynamics/propeller journal paper
identifies a **notice**, with `openAccess_bool: false`; it does not supply a
full-text file. This is an availability observation, not evidence about the
unread paper's contents. The public Aswing.py wrapper tree contains inputs and
a command file, but no native executable or output.

The receipts and exact API responses are retained in
`reference/sa11-native-evidence-20261108/`. SHA-256:

| Retained evidence | SHA-256 |
|---|---|
| HAL metadata | `41d801c8b4bb6ab4f6153018bb6d642880b3041d7fc6fe00e1f9aed8b4d2e407` |
| Aswing.py tree | `e814306bb8608e34540026de01bc261f30d06e001009aa4ce249ad9b91bd32fb` |

The [curved-extension comparison](isae-sa11-curved-extension-20261108.md)
and earlier winglet field comparisons remain the numerical evidence. Authentic
archived setup and the pre-stall local-flow failure are still unresolved.
