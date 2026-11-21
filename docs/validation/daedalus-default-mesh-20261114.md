# Daedalus default mesh: closer to the native GIF drawing

**Superseded spacing:** the [regular mesh update](daedalus-regular-mesh-20261114.md)
redistributes nodes between required stations and recomputes the checked app
case. The 107-interval grid below is the earlier preset, retained as evidence.

At the user's request, a fresh Daedalus import initially selected uniform material-arc
spacing with different counts for each component. The settings approximate the
visual density of Drela's rudder GIF; they are not recovered native node
coordinates or a verified ASWING default. This supersedes the previous app's
48-cosine-intervals-on-every-beam behavior for Daedalus only.

| Component | Requested intervals | Actual intervals | Chord-line stations |
| --- | ---: | ---: | ---: |
| Wing | 48 | 50 | 51 |
| Horizontal tail | 12 | 14 | 15 |
| Vertical tail | 10 | 12 | 13 |
| Tail boom | 16 | 21 | 22 tube stations |
| Cabin fairing | 8 | 10 | 11 |

There are **107 intervals total**, versus 261 at the previous fresh-import
default. The existing mesher retains every mandatory property break and
attachment. The wing has 46 intervals of 112/48 = 2.33333 ft; the four remaining
intervals surround its two required tip breaks. No physical input table,
break-selection policy, force equation or historical comparison state changed.
Reducing the mesh count is not itself evidence of dynamic convergence or a
solution to the Daedalus Bode discrepancy.

The subsequent [fresh trim and three-frequency response check](daedalus-default-mesh-response-20261114.md)
confirms the new discrete solution with direct full-equation checks. It changes
yaw at the published dip by only −0.57%, leaving the discrepancy open. Roll
remains more mesh-sensitive; this does not establish a converged default.

## Application behavior

Selecting the Daedalus example or opening a recognized five-beam Daedalus
`.asw` file applies the new defaults. Recognition checks the model name and
all five beam identities, not just the filename. An ordinary inspection,
property edit or saved-project load preserves the current mesh.

The **Use Daedalus default mesh** button below the example selector also
applies the preset to an existing case. It preserves flight settings, control
inputs and trim constraints, clears the incompatible loaded equilibrium, and
invalidates computed results through the existing case-loading path. It is
disabled while a solve is running. A fresh solution is required. Individual
counts and spacing remain editable under **Beam nodes**. The per-beam overrides
take precedence over the global default-interval field.

The [shared JSON preset](../../web/daedalus-mesh.json) is consumed by the
[UI helper](../../web/daedalus-mesh.js) and the
[mesh check](../../scripts/check_daedalus_default_mesh.py). The updated modules
are available from the existing development server. Automatic reload remains
disabled; refresh manually after a running calculation finishes. Packaged
downloads have not been rebuilt under the existing build hold.

## Verification and limits

The bounded serial mesh check passes for both old and new settings, preserving
all required stations, mirrored-wing/tail symmetry, positive interval lengths,
unchanged aircraft text, and the correspondence between drawn faces and
computational intervals. It used 1.607 CPU seconds, 3.600 wall seconds and
80,320 KiB peak RSS; the process completed and was reaped. No flight or harmonic
solve ran. Its first attempt stopped on an overly strict absolute roundoff
tolerance in the old cosine-mesh symmetry check (3.55e-14 ft observed versus
3e-14 allowed). The revised check uses eight machine epsilons times span; no
physics or production tolerance changed.

Three focused JavaScript tests pass **26 assertions** in a V8 isolate using
the actual helper and preset. They check recognition, independent settings,
preserved flight inputs and removal of the incompatible equilibrium. Three
additional checks execute the actual application's import function through
request generation: fresh Daedalus receives the preset, an existing Daedalus
case retains its mesh, and another aircraft retains the general default.
The main module parses, and the existing Vite server successfully transforms
and serves the helper, JSON module and application. Browser integration remains
unexecuted under the hold. An initial syntax error in the new test fixture was
corrected before these JavaScript checks; it did not affect production code or
the completed native mesh calculation.

[Mesh results](../../artifacts/daedalus-default-mesh-20261114/preset-verified/result.json),
[terminal receipt](../../artifacts/daedalus-default-mesh-20261114/preset-verified/terminal.json),
[JavaScript checks](../../artifacts/daedalus-default-mesh-20261114/javascript-checks.json),
[source verification](../../artifacts/daedalus-default-mesh-20261114/verification.json).
ISAE fractions, scopes and progress history remain unchanged. The earlier
[component audit](daedalus-viewer-base-and-mesh-20261114.md) describes the
superseded default and retains its original evidence.
