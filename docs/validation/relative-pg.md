# Relative-coordinate aerodynamic precision repair

The reconstructed FFWT-1 30° case now reaches full load in a native run without
relaxing its 1e−12 acceptance gate. The earlier calculation stopped after six
minutes with only a small fraction of the requested load accepted. The new
cold run takes 125.36 seconds and its saved state independently reproduces
the full residual, 8.52611e−13. These are observed runs with different iteration
histories and instrumentation, not a controlled speed benchmark.

The repair forms point-to-vortex displacements before applying the
Prandtl–Glauert coordinate transformation. Previously, transforming separate
absolute positions rounded them before subtraction. The equations, geometry,
core radii, principal-value exclusions and ground-image rules are unchanged.
Analytic influence derivatives and cached influence evaluations now use the
same relative operands as the residual.

An independent 80-digit reference checks eight target rows and all 184 source
elements at each of two saved states. The maximum force-location influence
error falls from 1.803e−11 to 4.820e−13 in one state and from 5.124e−11 to
2.358e−13 in the other. The largest control-point error is unchanged. Earlier
geometry rounding remains a separate limitation; no universal improvement of
every coefficient or residual is claimed.

## Verification

The candidate passes 148 targeted native checks, including independent
high-precision values, translated geometry, analytic derivatives, ground
images, exclusion masks, cache invalidation and coupled geometry. The
previous arithmetic fails ten of the eleven added regression cases. After
installation, those eleven cases pass again in 3.68 seconds; they overlap the
148 checks and are not additional unique coverage.

Actual Chromium/Pyodide checks import all 103 pinned modules and pass the
high-precision kernel controls and 218 cache comparisons. Four complete
184-by-184 velocity fields match the native arrays exactly in this runtime.
This kernel test takes 37.02 seconds including startup, with 2.85 seconds in
the Python checks. It is separate from the full application equilibrium test.

The actual offline application imports the reconstructed 30° model and original
mesh settings, then solves at full load in approximately 516 seconds after
28.3 seconds of runtime startup and input preparation. The returned residual
is 5.83372e−13. Fresh residual-only replays of the exported state give exactly
the same value in WebAssembly and 6.02669e−13 natively. Both pass the original
gate without a correction or a second equilibrium solve.

Worker progress records seven full tangent builds, occupying 357.71 seconds
of the 516.20-second request-to-result interval. The repeated matrix counters
describe successive builds within continuation/Newton updates. The browser
uses a different iteration history from the native run, so their timing ratio
does not measure WebAssembly overhead alone. Reducing this remaining matrix
work safely requires further profiling and convergence checks.

The original application-test process exits with a retained post-export
assertion failure: it requires bitwise equality of all generated mesh values
across runtimes. Mesh settings, required-node identities and topology match;
the measured maximum node-coordinate difference is 5.55e−17 m and the largest
physical fold difference is 7.11e−15 degrees. This numerical comparison does
not erase the original harness failure or replace the equilibrium gate with
a new acceptance threshold. Browser runtime remains a limitation.

Fresh residual evaluation accepts the retained 10° equilibrium. The original
20° state narrowly exceeds the gate under the new arithmetic; a separately
recorded public warm-start correction and fresh exported-state replay pass.
All three numerical roots and their differing initialization histories are
documented in the [current nominal comparison](isae-ffwt1-nominal-07.md).

## Limits

The arithmetic change adds temporary pairwise displacement arrays in the
influence cache. It is a precision repair, without a claim that each influence
assembly is faster. Strict convergence can still require substantial work.
The selected checks are not a fresh full-repository suite, and earlier studies
retain their historical source hashes.

Experimental setup, branch selection, mesh refinement and physical agreement
remain unresolved. Coverage and literal parser counts are unchanged at
17 partial / 24 pending / 0 fully validated families and 177 accepted / 102
rejected original inputs. No original ASWING executable is available; archived
results and independent numerical references remain the comparison sources.

## Evidence and reproduction

The [source transition](relative-pg-transition.json) identifies all 103 modules,
the three-file change, unchanged UI sources, selected test scope and remaining
limits. The [report manifest](relative-pg-evidence/manifest.json) pins copies of
the original stage reports; their historical statuses are preserved.

The [selected precision archive](relative-pg-evidence.zip) includes the numerical
controls, source snapshots, retained failures, exported-state replays and browser
evidence. Extract it and run `python3 -B verify_selected_evidence.py` to verify
its members and reproduce its factual summary without running the solver.
The wider nominal-comparison inputs are in the separately linked
[nominal archive](isae-ffwt1-nominal-07-evidence.zip). These selected archives do
not constitute the complete raw FFWT study archive.
