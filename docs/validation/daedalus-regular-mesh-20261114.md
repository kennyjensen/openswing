# Regular Daedalus chord-line spacing

Both **Use Daedalus default mesh** and **Load checked level-flight case** now
use a mesh that is uniform **between required stations**. The previous preset
started with a global uniform grid and inserted attachment/property stations
afterward. This produced accidental close pairs, including a 0.10 ft fin
interval and a 0.125 ft boom interval. The renderer correctly showed those
analysis boundaries; the irregularity was in the mesh, not extra drawn lines.

![Actual station spacing before and after redistribution](../../artifacts/daedalus-regular-mesh-20261114/plot/spacing.png)

[SVG comparison](../../artifacts/daedalus-regular-mesh-20261114/plot/spacing.svg).
Each component occupies the same plot width independently; this is a spacing
comparison, not a scaled aircraft planform.

| Component | Previous intervals | New intervals | Previous gap range, ft | New gap range, ft |
| --- | ---: | ---: | ---: | ---: |
| Wing | 50 | 50 | 0.58–2.333 | 0.58–2.333 |
| Horizontal tail | 14 | 12 | 0.25–1.25 | 1.0–1.3 |
| Vertical tail | 12 | 10 | 0.10–0.85 | 0.8–1.0 |
| Tail boom | 21 | 17 | 0.125–1.656 | 1.25–1.833 |
| Cabin/fairing | 10 | 9 | 0.30–0.70 | 0.40–0.667 |

The mesh has **98 intervals and 103 nodes**. Every required station survives.
The wing's 0.58 ft tip spans remain because the literal `.asw` has a chord
break there; they are not accidental neighboring nodes. Main-wing spans have
2.333 ft spacing, and the outer 6.42 ft spans each have three equal 2.14 ft
intervals. It is therefore more regular, but not globally equal-spaced through
short physical tip segments.

The new `uniform-breaks` option appears as **Uniform between required
stations** in Beam nodes. It converts required stations to material arc
length, assigns each intervening span the nearest integer interval count to
the requested average density (at least one), then spaces its nodes evenly.
It preserves mirrored spans and works independently of the input parameter's
scale. Existing `uniform`, cosine, modified-cosine and explicit-node settings
retain their previous behavior. Applying a changed mesh clears an incompatible
saved equilibrium; this is a real analysis mesh change, not display smoothing.

The [authoritative index](aswing-authoritative-references.md) and source catalog
were reviewed. Drela's [user manual](../../reference/aswing_doc.txt),
**Considerations for Data Discontinuities**, says selected doubled-point
breaks require computational stations and warns that close breaks can produce
irregular spacing. That supports retaining necessary breaks, but does not
specify this redistribution algorithm or identify the GIF's mesh. No exact
native NODE reconstruction or mesh-convergence claim is made.

## Fresh checked level-flight case

The app's checked case was recomputed on the new mesh. Interpolating the old
fields gave residual **0.005897**, so that state was rejected as a solution.
All 618 geometry derivative columns and the remaining trim columns were
rebuilt in serial blocks. Three complete-residual directional checks have
maximum relative error **2.523e-10**. The rank certificate has reciprocal
condition lower bound **6.668e-8**. Nonlinear correction gives maximum scaled
residual **4.680e-10**, below the unchanged 1e-9 acceptance tolerance.

The independent released free-flight base has the same residual, **1,953
dynamic states**, zero flight path to numerical precision, speed **6.7 m/s**
and weight **232.5336 lb**. The publisher copies this accepted state verbatim
and requires its mesh to equal the app default. Both exported cases were
replayed from their actual editable fields, including the steady case's seven
trim targets and the Bode case's released free-flight constraints.

This replaces the prior checked case; it does not identify Drela's original
operating point or validate the new mesh's full Bode curve. A subsequent
[yaw-output audit](daedalus-yaw-output-20261114.md) rebuilds the full dynamic
matrices, checks four frequencies, and verifies the Earth animation against
the plotted frame rate. The published yaw dip remains unmatched. The previous-mesh
frequency sweep was stopped after its first six-point batch when the user
reported the spacing issue; no such sweep is left running.

## Verification and use

**33 native mesh checks pass**, including curved arc spacing, parameter
invariance, all Daedalus required stations, symmetry, and legacy minimum
spacing behavior. **71 JavaScript assertions pass** in isolated V8, and both
cases pass all **171** saved-setting checks. Both meshes match the fresh-import
preset. No Node, browser, build or WASM test was started; the existing
UserLAnd test hold remains in effect. The development server serves the current
source files and project. Refresh the page after any ongoing calculation
finishes, then click either Daedalus button. Existing saved calculations keep
their original mesh until explicitly replaced.

No ISAE completion fraction, comparison scope or progress observation changed.
All numerical jobs were serial, limited to one BLAS thread, and reaped. See
the [verification receipt](../../artifacts/daedalus-regular-mesh-20261114/verification.json).

[Mesh data](../../artifacts/daedalus-regular-mesh-20261114/mesh/result.json),
[trim result](../../artifacts/daedalus-regular-mesh-20261114/trim-1/result.json),
[dynamic-base audit](../../artifacts/daedalus-regular-mesh-20261114/audit/result.json),
[published-case replay](../../artifacts/daedalus-level-flight-case-20261114/replay-regular-mesh/result.json),
[JavaScript checks](../../artifacts/daedalus-regular-mesh-20261114/javascript-checks.json),
[bounded driver](../../scripts/check_daedalus_regular_mesh.py).
