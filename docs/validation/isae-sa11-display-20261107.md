# SA-11: section chords and the ASWING streamwise plotting option

2026-11-07. The earlier explanation correctly identified ASWING's input chord
convention but incorrectly treated it as sufficient justification for plotting
only normal sections. The authoritative documentation explicitly distinguishes
input dimensions from displayed chord lines.

## Direct source evidence

- [Drela's FAQ](https://web.mit.edu/drela/Public/web/aswing/aswing_faq.txt),
  question about normal versus streamwise chords: the aero/structural inputs
  are beam-normal chords. The given conversion multiplies each streamwise chord
  by `sqrt(dy²+dz²)/sqrt(dx²+dy²+dz²)`. Sweep breaks require a chosen average.
- [ASWING version notes](https://web.mit.edu/drela/Public/web/aswing/version_notes.txt),
  5.45: plotting was changed to show streamwise chords on swept wings.
  Version 5.75 adds the Options / U flag to choose normal or projected chords.
  A later entry records a correction for large deformations.
- [Steady theory](https://web.mit.edu/drela/Public/web/aswing/asw_theory.pdf),
  §1.1 and §1.5.2: the local Cartesian frame and chord-aligned representation
  establish the section-plane convention. Figure 16 separately defines the
  vortex system and wind-aligned offsets.

The official flying-wing BFF animation was downloaded and its first frame
inspected. The ISAE report's Figure 40 was also inspected. These figures support
the distinction but do not provide numerical coordinates for a pixel-exact
native plotting comparison.

## Implementation

**Streamwise chords** is now enabled above the aircraft view. Turning it off
shows normal sections, retaining the existing display-only root clipping.
Both WebGL and the software fallback consume the same choice. Horseshoes keep
their actual influence geometry in either view, and toggling the drawing does
not request a solve.

Raw `quads` remain normal sections. A separate `streamwise_quads` field describes
the projected skin, with the same topology. Its construction shears the chord
vector along the current local span direction. If `d` is the normal chord vector,
`s` the unit span, and `s_perp` its projection perpendicular to body x:

`d_plot = d − s (d · s_perp)/(s_perp · s_perp)`.

The component normal to `s`, the local surface plane, twist and the beam-axis
anchor are retained. For an untwisted section the result lies along body x and
has length `chord/cos(sweep)`, matching the FAQ conversion. When the span is
parallel to body x this projection is undefined; the normal section is retained.
The documentation identifies the plotting option, but does not publish its
complete large-deformation rendering algorithm. This formula is an explicit
implementation choice, not a recovered native source-code expression.

Time views transform both geometries into Earth coordinates. Modal and Bode
outputs differentiate both geometries from their physical snapshots; the viewer
then applies the same complex amplitude and phase. Old saved responses lacking
the projected derivative retain their moving normal geometry. Renderer recovery
retains the user's projection selection.

## Validation scope

Focused checks cover the FAQ chord conversion, axis anchoring, unchanged normal
chord length, twisted/deformed section planes, the singular projection, unchanged
horseshoe previews, and complex output translation in body/Earth frames. JavaScript
checks cover selection, transforms, phase and old-result fallback. Browser checks
exercise the actual WASM preview on desktop/mobile and the renderer recovery path.
Final outcomes and source hashes are recorded in the
[verification receipt](../../artifacts/isae/sa11-display-audit-20261107/verification.json).

Seven native projection/output-derivative checks and five existing vortex-display
checks pass; six JavaScript checks pass. The actual Pyodide desktop/mobile test
passes in 50.9 seconds, and the WebGL context-loss/recovery test passes in 20.2
seconds with this host's Mesa renderer. Its initial SwiftShader attempt reached
the 100-second process limit; no child processes remained before the Mesa retry.
The first new native test attempts exposed missing fixture units and a two-panel
request below the supported minimum. Both fixtures were corrected before passing.
The production build succeeds, including the offline local-app package.

No circulation, force, moment, reference-input or acceptance equation changes.
The SA-11 aerodynamic comparison remains **163/4,592 at 5%**. This display repair
does not resolve the aerodynamic discrepancy or validate the full project.
