# SA-11 winglet examples in the browser

The normal **ISAE aerodynamics** picker now contains the original wing-alone
baseline and two explicitly adapted inspection examples: **upper winglets** and
**upper + lower winglets**. The winglet models have three and five lifting beams,
respectively. Picker and viewport headings identify the chosen variant even
though both original input Name blocks say `Wing_alone`.

The upper model's malformed Joint multiplier row is replaced with its two
station scales, `0.1, 0.1`. The combined model gains the same Joint station
scales to match its scaled beam parameters. Both files carry correction and
attribution comments. Geometry and section properties are unchanged from the
previously reviewed reconstructions, and original validation inputs remain
separate. [Provenance](../../examples/isae-sa11-winglet-sources.json).

The geometry audit checks each bundled file's hash and confirms identical
parsed geometry to its reviewed reconstruction. Inspection through the actual
browser/WASM bridge supplies finite display faces for every beam. No solve is
needed to view the aircraft or its horseshoe preview.

The browser workflow passes with both WebGL (Mesa) and Canvas2D fallback:

- Load both examples and verify their headings, beam counts and display faces.
- Inspect perspective, opposite-orbit and front views. On the software renderer,
  every surface contributes visible palette pixels across the two perspective
  angles.
- Enable horseshoes and inspect a 390-pixel mobile Plots view without horizontal
  overflow.
- Return to the baseline and verify its single wing and no-winglets description.
- Confirm no aerodynamic solve requests or browser page errors occurred.

The initial pixel check incorrectly required every winglet to have visible face
area in one default view; a wing can occlude its far winglet. The revised check
requires visibility across opposing views. The front view shows both upper and
lower arrangements nearly edge-on. No geometry was moved to satisfy a visibility
assertion. Screenshots were inspected for the desktop orbit and mobile preview.

The geometry-only probe and browser screenshots are retained under
[`artifacts/isae/sa11-winglet-examples-20261107/`](../../artifacts/isae/sa11-winglet-examples-20261107/).
The executable workflow is
[`tests/browser/sa11-winglet-examples.spec.js`](../../tests/browser/sa11-winglet-examples.spec.js).

These are inspection examples, not newly validated aerodynamic cases. The
[Mach-error investigation](isae-sa11-winglet-junction-20261107.md) records the
remaining local-flow problem and the limited current-wind comparison. No ISAE
completion fraction or comparison scope changes.
