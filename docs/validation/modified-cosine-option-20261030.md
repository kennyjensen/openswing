# Selectable modified cosine spacing

The node editor and native API now accept `modified-cosine`. In the browser,
open **Nodes**, choose a beam, select **Modified cosine in arc length**, set
the interval count and apply. Numeric mesh settings still select ordinary
cosine spacing. Mesh exports, portable cases, saved equilibria and time
checkpoints preserve the selected distribution.

This exposes the fixed rule used in the
[SA-1–SA-5 spacing comparison](isae-sa1-sa5-spacing-20261029.md):
`u = sin((2j/N − 1) asin(q))`, `eta = 0.7u + 0.3u³`, where `q` is the
largest binary32 value below one. Exact endpoints and the even-count center
are assigned before mapping `(1+eta)/2` into undeformed material arc length.
The arc inverse supplies beam parameters, and the existing mandatory-node
insertion follows. Counts remain base intervals before extra required nodes.

This distribution was inferred from printed native coordinates, without
fitting force results. It is not authenticated as the universal ASWING mesh
generator. It improved SA-2 and SA-5 but did not resolve the SA-1 or SA-4
discrepancies. Aerodynamic equations, wake geometry, default spacing,
reference targets and acceptance thresholds are unchanged.

The [retained audit](../../artifacts/isae/modified-cosine-option-20261030/geometry-summary.md)
compares all twelve saved SA-1–SA-5 meshes, including both SA-4 mesh pairs.
All **156 array comparisons are bitwise equal**: the named option reproduces
the explicit-node construction, and default nodes reproduce the saved cosine
nodes. This uses 36 geometry constructions and no flow solves. Equality is
qualified to the current `accurate-arc-v2` recipe. Selecting the new spacing
with an older saved recipe retains that recipe's historical arc mapping.

The targeted native suite passes **53/53**, covering material-parameter
invariance, required stations, state/checkpoint reconstruction, and existing
mesh behavior. Portable JavaScript case tests pass **7/7**. Geometry equality
verifies faithful packaging of the retained rule; it does not establish new
native ASWING reference matches.

The [ten fresh SA-2 cold solves](../../artifacts/isae/modified-cosine-option-20261030/summary.md)
cover all five incidences at N100 and N200. All **70/70 native reference
checks** pass the unchanged 3% policy. All **360/360 compatibility checks**
against retained explicit-node results pass, with maximum scaled difference
1.14e−13, maximum circulation residual 1.70e−13 and maximum section-normal
Mach 0.621. Every process exited successfully; there were no retries or
timeouts. Four unrelated production modules already differed from the
historical controls before this option was added, so this is a compatibility
replay across code versions. No same-code explicit flow controls were added.
The separate geometry comparison is exact on current code. The registered
default SA-2 score remains 50/70; this reproduces the existing opt-in 70/70.

The [packaged WASM audit](../../artifacts/isae/modified-cosine-option-20261030/wasm-summary.md)
passes **192/192 checks** across all twelve meshes, including 120 array
comparisons and exact station/count requirements. Maximum scaled difference
from native geometry is 1.11e−14 against a declared 2e−12 limit. All 130
packaged kernel modules match current sources and the native audit's source
pins. This uses local runtime files and no flow solves.

Both relevant production-browser tests pass offline: the new spacing preview,
mesh export and portable-case restoration test, and the existing mesh editing,
mounted solve, incompatible-state rejection and mobile-layout test. The latter
initially timed out because it tried to scroll to nodes while the mobile Plots
tab was selected; selecting Editor fixes the test navigation. No UI behavior
was changed for that failure. Earlier missing-browser/library and development
dependency-startup failures are preserved in the execution logs. Browser
acceptance here uses the completed static build, not a successful development
startup run. `npm run build` passes and the local/source downloads contain the
new option and updated documentation.

Detailed source pins, protocols, arrays and execution records are retained in
[the study directory](../../artifacts/isae/modified-cosine-option-20261030/).
