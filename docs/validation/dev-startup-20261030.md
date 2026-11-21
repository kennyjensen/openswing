# Development startup with an empty dependency cache

The development configuration now starts dependency discovery at `index.html`
and follows its application imports. It also stops watching the experiment,
reference, Python virtual-environment, third-party and release-staging trees.
Application sources and public kernel/runtime/example files remain watched.
The source download includes `vite.config.js` so rebuilding that download
retains the same settings.

Without an explicit entry, Vite searches the repository for HTML files. Its
default omissions do not cover this repository's large evidence trees, and
dependency resolution can wait for that scan to finish. The inspected installed
Vite source and the [official entry configuration documentation](https://vite.dev/config/dep-optimization-options#optimizedeps-entries)
establish this mechanism. The previous browser run timed out after 120 seconds
without the workbench's solve button appearing; that log did not separately
profile scan and watcher time, so the exact contribution of each is unknown.

One fresh-cache browser run on this development machine now passes:

| Measurement | Result |
| --- | ---: |
| Vite server ready from harness start | 0.64 s |
| Workbench present from navigation | 4.93 s |
| Numerical runtime ready from navigation | 22.45 s |
| Recorded checks | 14/14 pass |
| External HTTP requests / failed requests / page errors | 0 / 0 / 0 |

The cache directory was newly created and empty. Three.js and OrbitControls
were both discovered and prebundled normally. The browser applied and exported
a modified-cosine mesh through the actual worker; no physical solve was run.
The screenshot shows the loaded aircraft and node editor. This headless host
reported unavailable WebGL; the existing software viewer continued rendering.
No WebGL-specific startup claim is made from this run. Timings are a single
local observation, not a hardware-independent guarantee or a controlled
measurement isolating scan from watcher cost.

The [retained evidence](../../artifacts/isae/dev-startup-20261030/README.md)
contains installed-source locations, hashes, the empty-cache harness, report,
browser screenshot and terminal records. Large validation ZIP contents are not
parsed by dependency scanning; their production-build copy cost is a separate
issue and is not changed here.

A concurrent [SA-4 force/projection review](../../artifacts/isae/dev-startup-20261030/sa4-force-review.md)
found no new source-backed correction. Material-length force weights and
Glauert-angle residual weights match their respective published equations.
The already documented bound-endpoint/receiver interpolation ambiguity remains.
No aerodynamic equations, physical settings, tolerances or ISAE scores changed.
